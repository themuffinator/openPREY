/*
===========================================================================

openQ4 generation-scoped level-load byte pipeline

Copyright (C) 2026 openQ4 contributors

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

===========================================================================
*/

#include "LevelLoadPipeline.h"

#include <algorithm>
#include <array>
#include <cstring>
#include <limits>
#include <utility>

#if defined( min )
	#undef min
#endif
#if defined( max )
	#undef max
#endif

namespace {

enum class PipelineItemState : unsigned int {
	QUEUED = 0,
	READING,
	DECODING,
	READY,
	CANCELLED,
	FAILED
};

static constexpr std::uint32_t LEVEL_LOAD_DECODED_FRAMING_VERSION = 1;
static constexpr std::uint64_t FNV1A64_OFFSET = 14695981039346656037ull;
static constexpr std::uint64_t FNV1A64_PRIME = 1099511628211ull;
static constexpr std::uint32_t MAX_FRAME_UNITS = 1024u * 1024u;

void UpdatePeak( std::atomic<std::uint64_t> &peak, const std::uint64_t value ) {
	std::uint64_t observed = peak.load( std::memory_order_relaxed );
	while ( observed < value &&
		!peak.compare_exchange_weak( observed, value,
			std::memory_order_relaxed, std::memory_order_relaxed ) ) {
	}
}

std::uint64_t UpdateTransportChecksum( std::uint64_t checksum,
		const unsigned char *bytes, const std::size_t byteCount ) {
	for ( std::size_t index = 0; index < byteCount; ++index ) {
		checksum ^= bytes[ index ];
		checksum *= FNV1A64_PRIME;
	}
	return checksum;
}

void SealBytes( std::uint64_t &seal, const void *data, const std::size_t byteCount ) {
	seal = UpdateTransportChecksum( seal,
		static_cast<const unsigned char *>( data ), byteCount );
}

void SealU32( std::uint64_t &seal, const std::uint32_t value ) {
	unsigned char encoded[4];
	for ( std::size_t index = 0; index < 4; ++index ) {
		encoded[index] = static_cast<unsigned char>( value >> ( index * 8 ) );
	}
	SealBytes( seal, encoded, sizeof( encoded ) );
}

void SealU64( std::uint64_t &seal, const std::uint64_t value ) {
	unsigned char encoded[8];
	for ( std::size_t index = 0; index < 8; ++index ) {
		encoded[index] = static_cast<unsigned char>( value >> ( index * 8 ) );
	}
	SealBytes( seal, encoded, sizeof( encoded ) );
}

std::uint64_t ComputeFramingSeal( const idLevelLoadDecodedSource &decoded ) {
	std::uint64_t seal = FNV1A64_OFFSET;
	static constexpr unsigned char domain[] = {
		'o', 'p', 'e', 'n', 'Q', '4', '-', 'p', 'r', 'e', 'l', 'o', 'a', 'd'
	};
	SealBytes( seal, domain, sizeof( domain ) );
	SealU32( seal, decoded.framingVersion );
	SealU64( seal, decoded.generation );
	SealU64( seal, decoded.normalizedPath.size() );
	SealBytes( seal, decoded.normalizedPath.data(), decoded.normalizedPath.size() );
	SealU32( seal, decoded.type );
	SealU32( seal, static_cast<std::uint32_t>( decoded.frameKind ) );
	SealU64( seal, decoded.sourceBytes );
	SealU64( seal, decoded.payloadOffset );
	SealU64( seal, decoded.payloadBytes );
	SealU32( seal, decoded.frameUnitCount );
	SealU64( seal, decoded.sourceTimestamp );
	SealU32( seal, decoded.containerChecksum );
	SealU64( seal, decoded.transportChecksum );
	SealBytes( seal, decoded.contentIntegrity.data(), decoded.contentIntegrity.size() );
	return seal;
}

bool HasContentIntegrity( const std::array<unsigned char, 32> &integrity ) {
	return std::any_of( integrity.begin(), integrity.end(),
		[]( const unsigned char value ) { return value != 0; } );
}

bool HasExtension( const std::string &path, const char *extension ) {
	const std::size_t extensionLength = std::strlen( extension );
	return path.size() >= extensionLength &&
		path.compare( path.size() - extensionLength, extensionLength, extension ) == 0;
}

std::uint32_t ReadLittleU32( const unsigned char *bytes ) {
	return static_cast<std::uint32_t>( bytes[0] ) |
		( static_cast<std::uint32_t>( bytes[1] ) << 8 ) |
		( static_cast<std::uint32_t>( bytes[2] ) << 16 ) |
		( static_cast<std::uint32_t>( bytes[3] ) << 24 );
}

std::uint32_t ReadBigU32( const unsigned char *bytes ) {
	return ( static_cast<std::uint32_t>( bytes[0] ) << 24 ) |
		( static_cast<std::uint32_t>( bytes[1] ) << 16 ) |
		( static_cast<std::uint32_t>( bytes[2] ) << 8 ) |
		static_cast<std::uint32_t>( bytes[3] );
}

struct DecodeControl {
	const idJobCancellationToken *cancellation;
	std::atomic<std::uint64_t> *bytesDecoded;
	std::uint64_t maximumBytes;
	std::uint64_t reportedBytes;
	bool invalidProgress;
};

bool DecodeCancellationRequested( void *opaque ) {
	const DecodeControl *control = static_cast<const DecodeControl *>( opaque );
	return control == nullptr || control->cancellation == nullptr ||
		control->cancellation->IsCancellationRequested();
}

bool ReportDecodeProgress( void *opaque, const std::size_t byteCount ) {
	DecodeControl *control = static_cast<DecodeControl *>( opaque );
	if ( control == nullptr || control->bytesDecoded == nullptr ||
		DecodeCancellationRequested( opaque ) ) {
		return false;
	}
	if ( byteCount == 0 || byteCount > control->maximumBytes - control->reportedBytes ) {
		control->invalidProgress = true;
		return false;
	}
	control->reportedBytes += byteCount;
	control->bytesDecoded->fetch_add( byteCount, std::memory_order_relaxed );
	return true;
}

} // namespace

idLevelLoadDecodeStatus idLevelLoadDecodeSourceFrame(
		const idLevelLoadPipelineSource &source, const unsigned char *bytes,
		const std::size_t byteCount, idLevelLoadDecodeOutput &output,
		const idLevelLoadDecodeContext *context ) {
	if ( bytes == nullptr || byteCount == 0 || source.type == 0 ) {
		return idLevelLoadDecodeStatus::MALFORMED;
	}
	output.frameKind = idLevelLoadDecodedFrameKind::OPAQUE_VFS_BYTES;
	output.decodedBytes = static_cast<std::uint64_t>( byteCount );
	output.payloadOffset = 0;
	output.payloadBytes = static_cast<std::uint64_t>( byteCount );
	output.frameUnitCount = 1;

	// DDS layout depends on legacy/DX10 headers, texture kind, mip dimensions,
	// block formats, arrays, and cubemap faces. The renderer remains the only
	// owner of that full validation, so a DDS preload is deliberately opaque.
	if ( HasExtension( source.normalizedPath, ".dds" ) ) {
		return idLevelLoadDecodeStatus::COMPLETE;
	}
	if ( HasExtension( source.normalizedPath, ".wav" ) ) {
		output.frameKind = idLevelLoadDecodedFrameKind::RIFF_WAVE;
		if ( byteCount < 12 || std::memcmp( bytes, "RIFF", 4 ) != 0 ||
			std::memcmp( bytes + 8, "WAVE", 4 ) != 0 ||
			static_cast<std::uint64_t>( ReadLittleU32( bytes + 4 ) ) + 8ull != byteCount ) {
			return idLevelLoadDecodeStatus::MALFORMED;
		}
		std::size_t cursor = 12;
		std::uint32_t unitCount = 0;
		bool sawFormat = false;
		bool sawData = false;
		while ( cursor < byteCount ) {
			if ( context != nullptr && context->IsCancellationRequested() ) {
				return idLevelLoadDecodeStatus::CANCELLED;
			}
			if ( byteCount - cursor < 8 || unitCount == MAX_FRAME_UNITS ) {
				return idLevelLoadDecodeStatus::MALFORMED;
			}
			const std::uint32_t chunkBytes = ReadLittleU32( bytes + cursor + 4 );
			const std::uint64_t storedBytes = 8ull + chunkBytes + ( chunkBytes & 1u );
			if ( storedBytes > byteCount - cursor ) {
				return idLevelLoadDecodeStatus::MALFORMED;
			}
			if ( std::memcmp( bytes + cursor, "fmt ", 4 ) == 0 ) {
				if ( sawFormat || chunkBytes < 16 ) {
					return idLevelLoadDecodeStatus::MALFORMED;
				}
				sawFormat = true;
			} else if ( std::memcmp( bytes + cursor, "data", 4 ) == 0 ) {
				if ( !sawFormat ) {
					return idLevelLoadDecodeStatus::MALFORMED;
				}
				sawData = true;
			}
			cursor += static_cast<std::size_t>( storedBytes );
			++unitCount;
		}
		if ( cursor != byteCount || !sawFormat || !sawData || unitCount == 0 ) {
			return idLevelLoadDecodeStatus::MALFORMED;
		}
		output.frameUnitCount = unitCount;
		return idLevelLoadDecodeStatus::COMPLETE;
	}
	if ( HasExtension( source.normalizedPath, ".ogg" ) ) {
		output.frameKind = idLevelLoadDecodedFrameKind::OGG;
		std::size_t cursor = 0;
		std::uint32_t pageCount = 0;
		while ( cursor < byteCount ) {
			if ( context != nullptr && context->IsCancellationRequested() ) {
				return idLevelLoadDecodeStatus::CANCELLED;
			}
			if ( byteCount - cursor < 27 || pageCount == MAX_FRAME_UNITS ||
				std::memcmp( bytes + cursor, "OggS", 4 ) != 0 || bytes[cursor + 4] != 0 ) {
				return idLevelLoadDecodeStatus::MALFORMED;
			}
			const std::size_t segmentCount = bytes[cursor + 26];
			if ( segmentCount > byteCount - cursor - 27 ) {
				return idLevelLoadDecodeStatus::MALFORMED;
			}
			std::uint64_t pageBytes = 27ull + segmentCount;
			for ( std::size_t index = 0; index < segmentCount; ++index ) {
				pageBytes += bytes[cursor + 27 + index];
			}
			if ( pageBytes > byteCount - cursor ) {
				return idLevelLoadDecodeStatus::MALFORMED;
			}
			cursor += static_cast<std::size_t>( pageBytes );
			++pageCount;
		}
		if ( cursor != byteCount || pageCount == 0 ) {
			return idLevelLoadDecodeStatus::MALFORMED;
		}
		output.frameUnitCount = pageCount;
		return idLevelLoadDecodeStatus::COMPLETE;
	}
	if ( HasExtension( source.normalizedPath, ".png" ) ) {
		static constexpr unsigned char PNG_SIGNATURE[8] = {
			0x89, 'P', 'N', 'G', 0x0d, 0x0a, 0x1a, 0x0a
		};
		output.frameKind = idLevelLoadDecodedFrameKind::PNG;
		if ( byteCount < sizeof( PNG_SIGNATURE ) + 12 ||
			std::memcmp( bytes, PNG_SIGNATURE, sizeof( PNG_SIGNATURE ) ) != 0 ) {
			return idLevelLoadDecodeStatus::MALFORMED;
		}
		std::size_t cursor = sizeof( PNG_SIGNATURE );
		std::uint32_t chunkCount = 0;
		bool sawHeader = false;
		bool sawData = false;
		bool sawEnd = false;
		while ( cursor < byteCount ) {
			if ( context != nullptr && context->IsCancellationRequested() ) {
				return idLevelLoadDecodeStatus::CANCELLED;
			}
			if ( sawEnd || byteCount - cursor < 12 || chunkCount == MAX_FRAME_UNITS ) {
				return idLevelLoadDecodeStatus::MALFORMED;
			}
			const std::uint32_t chunkBytes = ReadBigU32( bytes + cursor );
			const std::uint64_t storedBytes = 12ull + chunkBytes;
			if ( storedBytes > byteCount - cursor ) {
				return idLevelLoadDecodeStatus::MALFORMED;
			}
			const unsigned char *type = bytes + cursor + 4;
			const bool isHeader = std::memcmp( type, "IHDR", 4 ) == 0;
			const bool isData = std::memcmp( type, "IDAT", 4 ) == 0;
			const bool isEnd = std::memcmp( type, "IEND", 4 ) == 0;
			if ( chunkCount == 0 && ( !isHeader || chunkBytes != 13 ) ) {
				return idLevelLoadDecodeStatus::MALFORMED;
			}
			if ( isHeader ) {
				if ( sawHeader || chunkBytes != 13 || ReadBigU32( bytes + cursor + 8 ) == 0 ||
					ReadBigU32( bytes + cursor + 12 ) == 0 ) {
					return idLevelLoadDecodeStatus::MALFORMED;
				}
				sawHeader = true;
			}
			if ( isEnd && chunkBytes != 0 ) {
				return idLevelLoadDecodeStatus::MALFORMED;
			}
			sawData = sawData || isData;
			cursor += static_cast<std::size_t>( storedBytes );
			++chunkCount;
			sawEnd = isEnd;
		}
		if ( cursor != byteCount || !sawHeader || !sawData || !sawEnd || chunkCount < 3 ) {
			return idLevelLoadDecodeStatus::MALFORMED;
		}
		output.frameUnitCount = chunkCount;
		return idLevelLoadDecodeStatus::COMPLETE;
	}
	if ( HasExtension( source.normalizedPath, ".jpg" ) ||
		HasExtension( source.normalizedPath, ".jpeg" ) ) {
		output.frameKind = idLevelLoadDecodedFrameKind::JPEG;
		if ( byteCount < 4 || bytes[0] != 0xff || bytes[1] != 0xd8 ||
			bytes[byteCount - 2] != 0xff || bytes[byteCount - 1] != 0xd9 ) {
			return idLevelLoadDecodeStatus::MALFORMED;
		}
		return idLevelLoadDecodeStatus::COMPLETE;
	}
	return idLevelLoadDecodeStatus::COMPLETE;
}

struct idLevelLoadPipeline::Item {
	idLevelLoadPipeline *owner;
	idLevelLoadPipelineSource source;
	std::shared_ptr<std::vector<unsigned char> > stagingBytes;
	std::shared_ptr<const idLevelLoadDecodedSource> decoded;
	std::uint64_t readTransportChecksum;
	std::atomic<PipelineItemState> state;

	Item()
		: owner( nullptr )
		, stagingBytes( std::make_shared<std::vector<unsigned char> >() )
		, readTransportChecksum( FNV1A64_OFFSET )
		, state( PipelineItemState::QUEUED ) {
	}
};

idLevelLoadPipelineConfig::idLevelLoadPipelineConfig()
	: maxEntries( 512 )
	, maxSourceBytes( 128ull * 1024ull * 1024ull )
	, maxTotalBytes( 384ull * 1024ull * 1024ull )
	, maxDecodedBytes( 384ull * 1024ull * 1024ull )
	, readChunkBytes( 256u * 1024u )
	, decodeChunkBytes( 256u * 1024u ) {
}

idLevelLoadPipelineSource::idLevelLoadPipelineSource()
	: type( 0 )
	, priority( 0 )
	, firstUseOrder( 0 )
	, file( nullptr )
	, sourceBytes( 0 )
	, sourceTimestamp( 0 )
	, containerChecksum( 0 ) {
}

idLevelLoadPipelineMetrics::idLevelLoadPipelineMetrics()
	: generation( 0 )
	, admittedEntries( 0 )
	, rejectedEntries( 0 )
	, completedEntries( 0 )
	, cancelledEntries( 0 )
	, failedEntries( 0 )
	, bytesRead( 0 )
	, peakStagingBytes( 0 )
	, decodeStartedEntries( 0 )
	, decodeCompletedEntries( 0 )
	, decodeCancelledEntries( 0 )
	, decodeFailedEntries( 0 )
	, decodeBudgetRejectedEntries( 0 )
	, bytesDecoded( 0 )
	, admittedDecodedBytes( 0 )
	, decodeBudgetBytes( 0 )
	, peakDecodedBytes( 0 )
	, cacheHits( 0 )
	, synchronousFallback( false )
	, active( false )
	, cancelled( false ) {
}

idLevelLoadDecodeOutput::idLevelLoadDecodeOutput()
	: frameKind( idLevelLoadDecodedFrameKind::INVALID )
	, decodedBytes( 0 )
	, payloadOffset( 0 )
	, payloadBytes( 0 )
	, frameUnitCount( 0 )
	, transportChecksum( 0 ) {
	contentIntegrity.fill( 0 );
}

idLevelLoadDecodeContext::idLevelLoadDecodeContext()
	: generation( 0 )
	, chunkBytes( 0 )
	, cancellationFunction( nullptr )
	, progressFunction( nullptr )
	, state( nullptr ) {
}

bool idLevelLoadDecodeContext::IsCancellationRequested() const {
	return cancellationFunction == nullptr || cancellationFunction( state );
}

bool idLevelLoadDecodeContext::ReportDecodedBytes( const std::size_t byteCount ) const {
	return progressFunction != nullptr && progressFunction( state, byteCount );
}

idLevelLoadDecodedSource::idLevelLoadDecodedSource()
	: framingVersion( LEVEL_LOAD_DECODED_FRAMING_VERSION )
	, generation( 0 )
	, type( 0 )
	, frameKind( idLevelLoadDecodedFrameKind::INVALID )
	, sourceBytes( 0 )
	, payloadOffset( 0 )
	, payloadBytes( 0 )
	, frameUnitCount( 0 )
	, sourceTimestamp( 0 )
	, containerChecksum( 0 )
	, transportChecksum( 0 )
	, framingSeal( 0 ) {
	contentIntegrity.fill( 0 );
}

idLevelLoadPipeline::idLevelLoadPipeline()
	: generation( 0 )
	, readFunction( nullptr )
	, readUserData( nullptr )
	, decodeFunction( nullptr )
	, decodeUserData( nullptr )
	, admittedEntries( 0 )
	, rejectedEntries( 0 )
	, completedEntries( 0 )
	, cancelledEntries( 0 )
	, failedEntries( 0 )
	, bytesRead( 0 )
	, currentStagingBytes( 0 )
	, peakStagingBytes( 0 )
	, decodeStartedEntries( 0 )
	, decodeCompletedEntries( 0 )
	, decodeCancelledEntries( 0 )
	, decodeFailedEntries( 0 )
	, decodeBudgetRejectedEntries( 0 )
	, bytesDecoded( 0 )
	, admittedDecodedBytes( 0 )
	, currentDecodedBytes( 0 )
	, peakDecodedBytes( 0 )
	, cacheHits( 0 )
	, synchronousFallback( false )
	, active( false )
	, cancelled( false ) {
}

idLevelLoadPipeline::~idLevelLoadPipeline() {
	CancelAndWait();
}

bool idLevelLoadPipeline::Begin( const std::uint64_t newGeneration,
		const idLevelLoadPipelineConfig &config,
		std::vector<idLevelLoadPipelineSource> sources,
		const idLevelLoadReadFunction newReadFunction,
		void *newReadUserData,
		const idLevelLoadDecodeFunction newDecodeFunction,
		void *newDecodeUserData ) {
	if ( active.load( std::memory_order_acquire ) || jobList != nullptr ) {
		return false;
	}

	Reset();
	currentConfig = config;
	generation = newGeneration;
	readFunction = newReadFunction;
	readUserData = newReadUserData;
	decodeFunction = newDecodeFunction;
	decodeUserData = newDecodeUserData;

	if ( readFunction == nullptr || decodeFunction == nullptr || currentConfig.maxEntries == 0 ||
		currentConfig.maxSourceBytes == 0 || currentConfig.maxTotalBytes == 0 ||
		currentConfig.maxDecodedBytes == 0 || currentConfig.readChunkBytes == 0 ||
		currentConfig.decodeChunkBytes == 0 ) {
		// Preserve ownership of every already-open main-thread handle so the
		// caller can close it through DrainOpenFiles even on setup failure.
		for ( idLevelLoadPipelineSource &source : sources ) {
			if ( source.file != nullptr ) {
				rejectedOpenFiles.push_back( source.file );
				source.file = nullptr;
			}
		}
		return false;
	}
	currentConfig.readChunkBytes = std::min<std::size_t>(
		currentConfig.readChunkBytes,
		static_cast<std::size_t>( 4u * 1024u * 1024u ) );
	currentConfig.decodeChunkBytes = std::min<std::size_t>(
		currentConfig.decodeChunkBytes,
		static_cast<std::size_t>( 4u * 1024u * 1024u ) );

	// Stable priority/order sorting makes budget admission deterministic.
	std::stable_sort( sources.begin(), sources.end(),
		[]( const idLevelLoadPipelineSource &a, const idLevelLoadPipelineSource &b ) {
			if ( a.priority != b.priority ) {
				return a.priority > b.priority;
			}
			if ( a.firstUseOrder != b.firstUseOrder ) {
				return a.firstUseOrder < b.firstUseOrder;
			}
			return a.normalizedPath < b.normalizedPath;
		} );

	std::uint64_t admittedBytes = 0;
	std::uint64_t decodedAdmissionBytes = 0;
	items.reserve( std::min<std::size_t>( sources.size(), currentConfig.maxEntries ) );
	for ( idLevelLoadPipelineSource &source : sources ) {
		const bool invalid = source.file == nullptr || source.normalizedPath.empty() ||
			source.sourceBytes == 0 || source.sourceBytes > currentConfig.maxSourceBytes ||
			source.sourceBytes > static_cast<std::uint64_t>( std::numeric_limits<std::size_t>::max() );
		const bool stagingSaturated = items.size() >= currentConfig.maxEntries ||
			source.sourceBytes > currentConfig.maxTotalBytes - admittedBytes;
		const bool decodeSaturated = source.sourceBytes >
			currentConfig.maxDecodedBytes - decodedAdmissionBytes;
		const bool saturated = stagingSaturated || decodeSaturated;
		if ( invalid || saturated ) {
			rejectedEntries.fetch_add( 1, std::memory_order_relaxed );
			if ( !invalid && decodeSaturated ) {
				decodeBudgetRejectedEntries.fetch_add( 1, std::memory_order_relaxed );
			}
			if ( source.file != nullptr ) {
				rejectedOpenFiles.push_back( source.file );
				source.file = nullptr;
			}
			continue;
		}

		std::unique_ptr<Item> item( new Item() );
		item->owner = this;
		item->source = std::move( source );
		items.push_back( std::move( item ) );
		admittedBytes += items.back()->source.sourceBytes;
		decodedAdmissionBytes += items.back()->source.sourceBytes;
		admittedEntries.fetch_add( 1, std::memory_order_relaxed );
		admittedDecodedBytes.fetch_add( items.back()->source.sourceBytes,
			std::memory_order_relaxed );
	}

	if ( items.empty() ) {
		return true;
	}

	jobList = jobSystem.CreateJobList(
		"level-load-read-decode",
		items.size(),
		0,
		idJobPriority::HIGH );
	if ( jobList != nullptr ) {
		for ( const std::unique_ptr<Item> &item : items ) {
			if ( !jobList->AddJob( &idLevelLoadPipeline::RunJob, item.get() ) ) {
				jobList.reset();
				break;
			}
		}
	}

	active.store( true, std::memory_order_release );
	if ( jobList != nullptr ) {
		const idJobSubmitResult submitResult = jobList->Submit();
		if ( submitResult == idJobSubmitResult::ACCEPTED ) {
			return true;
		}
		if ( submitResult == idJobSubmitResult::EXECUTED_SYNCHRONOUSLY ) {
			// Report jobs-disabled/deterministic execution through the same
			// explicit synchronous-path metric used for admission fallback.
			synchronousFallback.store( true, std::memory_order_relaxed );
			active.store( false, std::memory_order_release );
			return true;
		}
		jobList.reset();
	}

	// Admission saturation or an unavailable service must not affect correctness:
	// execute the bounded prefetch batch inline and leave ordinary VFS fallback
	// authoritative for anything that was not admitted.
	synchronousFallback.store( true, std::memory_order_relaxed );
	idJobCancellationToken noCancellation;
	for ( const std::unique_ptr<Item> &item : items ) {
		RunItem( *item, noCancellation );
	}
	active.store( false, std::memory_order_release );
	return true;
}

void idLevelLoadPipeline::RunJob( const idJobContext &context ) {
	Item *item = static_cast<Item *>( context.data );
	if ( item == nullptr || item->owner == nullptr ) {
		return;
	}
	item->owner->RunItem( *item, context.cancellation );
}

void idLevelLoadPipeline::RunItem( Item &item,
		const idJobCancellationToken &cancellation ) {
	if ( cancellation.IsCancellationRequested() ) {
		item.state.store( PipelineItemState::CANCELLED, std::memory_order_release );
		cancelledEntries.fetch_add( 1, std::memory_order_relaxed );
		return;
	}

	item.state.store( PipelineItemState::READING, std::memory_order_release );
	try {
		item.stagingBytes->resize( static_cast<std::size_t>( item.source.sourceBytes ) );
	} catch ( ... ) {
		item.stagingBytes->clear();
		item.state.store( PipelineItemState::FAILED, std::memory_order_release );
		failedEntries.fetch_add( 1, std::memory_order_relaxed );
		return;
	}

	const std::uint64_t staging = currentStagingBytes.fetch_add(
		item.source.sourceBytes, std::memory_order_relaxed ) + item.source.sourceBytes;
	UpdatePeak( peakStagingBytes, staging );

	std::size_t offset = 0;
	while ( offset < item.stagingBytes->size() ) {
		if ( cancellation.IsCancellationRequested() ) {
			item.stagingBytes->clear();
			currentStagingBytes.fetch_sub( item.source.sourceBytes, std::memory_order_relaxed );
			item.state.store( PipelineItemState::CANCELLED, std::memory_order_release );
			cancelledEntries.fetch_add( 1, std::memory_order_relaxed );
			return;
		}
		const std::size_t remaining = item.stagingBytes->size() - offset;
		const std::size_t request = std::min( remaining, currentConfig.readChunkBytes );
		const int read = readFunction( item.source.file, item.stagingBytes->data() + offset,
			static_cast<int>( request ), readUserData );
		if ( read <= 0 || static_cast<std::size_t>( read ) > request ) {
			item.stagingBytes->clear();
			currentStagingBytes.fetch_sub( item.source.sourceBytes, std::memory_order_relaxed );
			item.state.store( PipelineItemState::FAILED, std::memory_order_release );
			failedEntries.fetch_add( 1, std::memory_order_relaxed );
			return;
		}
		item.readTransportChecksum = UpdateTransportChecksum(
			item.readTransportChecksum, item.stagingBytes->data() + offset,
			static_cast<std::size_t>( read ) );
		offset += static_cast<std::size_t>( read );
		bytesRead.fetch_add( static_cast<std::uint64_t>( read ), std::memory_order_relaxed );
	}

	item.state.store( PipelineItemState::DECODING, std::memory_order_release );
	decodeStartedEntries.fetch_add( 1, std::memory_order_relaxed );
	DecodeControl control;
	control.cancellation = &cancellation;
	control.bytesDecoded = &bytesDecoded;
	control.maximumBytes = item.source.sourceBytes;
	control.reportedBytes = 0;
	control.invalidProgress = false;
	idLevelLoadDecodeContext context;
	context.generation = generation;
	context.chunkBytes = currentConfig.decodeChunkBytes;
	context.cancellationFunction = &DecodeCancellationRequested;
	context.progressFunction = &ReportDecodeProgress;
	context.state = &control;
	idLevelLoadDecodeOutput output;
	idLevelLoadDecodeStatus decodeStatus = idLevelLoadDecodeStatus::CANCELLED;
	if ( !cancellation.IsCancellationRequested() ) {
		decodeStatus = decodeFunction( item.source, item.stagingBytes->data(),
			item.stagingBytes->size(), context, output, decodeUserData );
	}
	const bool wasCancelled = cancellation.IsCancellationRequested() ||
		decodeStatus == idLevelLoadDecodeStatus::CANCELLED;
	const bool invalidDecode = decodeStatus != idLevelLoadDecodeStatus::COMPLETE ||
		control.invalidProgress || control.reportedBytes != item.source.sourceBytes ||
		output.decodedBytes != item.source.sourceBytes ||
		output.payloadOffset > output.decodedBytes ||
		output.payloadBytes > output.decodedBytes - output.payloadOffset ||
		output.payloadBytes == 0 || output.frameUnitCount == 0 ||
		output.frameUnitCount > MAX_FRAME_UNITS ||
		output.transportChecksum != item.readTransportChecksum ||
		!HasContentIntegrity( output.contentIntegrity ) ||
		output.frameKind == idLevelLoadDecodedFrameKind::INVALID ||
		static_cast<std::uint32_t>( output.frameKind ) >
			static_cast<std::uint32_t>( idLevelLoadDecodedFrameKind::JPEG );
	if ( wasCancelled || invalidDecode ) {
		item.stagingBytes->clear();
		currentStagingBytes.fetch_sub( item.source.sourceBytes, std::memory_order_relaxed );
		item.state.store( wasCancelled ? PipelineItemState::CANCELLED : PipelineItemState::FAILED,
			std::memory_order_release );
		if ( wasCancelled ) {
			cancelledEntries.fetch_add( 1, std::memory_order_relaxed );
			decodeCancelledEntries.fetch_add( 1, std::memory_order_relaxed );
		} else {
			failedEntries.fetch_add( 1, std::memory_order_relaxed );
			decodeFailedEntries.fetch_add( 1, std::memory_order_relaxed );
		}
		return;
	}

	std::shared_ptr<idLevelLoadDecodedSource> decoded;
	try {
		decoded = std::make_shared<idLevelLoadDecodedSource>();
		decoded->generation = generation;
		decoded->normalizedPath = item.source.normalizedPath;
		decoded->type = item.source.type;
		decoded->frameKind = output.frameKind;
		decoded->sourceBytes = item.source.sourceBytes;
		decoded->payloadOffset = output.payloadOffset;
		decoded->payloadBytes = output.payloadBytes;
		decoded->frameUnitCount = output.frameUnitCount;
		decoded->sourceTimestamp = item.source.sourceTimestamp;
		decoded->containerChecksum = item.source.containerChecksum;
		decoded->transportChecksum = output.transportChecksum;
		decoded->contentIntegrity = output.contentIntegrity;
		decoded->bytes = item.stagingBytes;
		decoded->framingSeal = ComputeFramingSeal( *decoded );
	} catch ( ... ) {
		item.stagingBytes->clear();
		currentStagingBytes.fetch_sub( item.source.sourceBytes, std::memory_order_relaxed );
		item.state.store( PipelineItemState::FAILED, std::memory_order_release );
		failedEntries.fetch_add( 1, std::memory_order_relaxed );
		decodeFailedEntries.fetch_add( 1, std::memory_order_relaxed );
		return;
	}
	item.decoded = decoded;
	item.stagingBytes.reset();
	currentStagingBytes.fetch_sub( item.source.sourceBytes, std::memory_order_relaxed );
	const std::uint64_t decodedResident = currentDecodedBytes.fetch_add(
		item.source.sourceBytes, std::memory_order_relaxed ) + item.source.sourceBytes;
	UpdatePeak( peakDecodedBytes, decodedResident );
	item.state.store( PipelineItemState::READY, std::memory_order_release );
	completedEntries.fetch_add( 1, std::memory_order_relaxed );
	decodeCompletedEntries.fetch_add( 1, std::memory_order_relaxed );
}

void idLevelLoadPipeline::CancelAndWait() {
	WaitInternal( true );
}

void idLevelLoadPipeline::Wait() {
	WaitInternal( false );
}

void idLevelLoadPipeline::WaitInternal( const bool cancel ) {
	if ( cancel ) {
		cancelled.store( true, std::memory_order_relaxed );
		if ( jobList != nullptr ) {
			jobList->Cancel();
		}
	}
	if ( jobList != nullptr ) {
		jobList->Wait();
		jobList.reset();
	}
	active.store( false, std::memory_order_release );
}

bool idLevelLoadPipeline::IsActive() const {
	return active.load( std::memory_order_acquire );
}

std::uint64_t idLevelLoadPipeline::GetGeneration() const {
	return generation;
}

std::shared_ptr<const idLevelLoadDecodedSource> idLevelLoadPipeline::Acquire(
		const std::uint64_t expectedGeneration,
		const char *path,
		const std::uint32_t expectedType,
		const std::uint64_t expectedBytes,
		const std::uint64_t expectedTimestamp,
		const std::uint32_t expectedContainerChecksum ) {
	if ( path == nullptr || path[ 0 ] == '\0' ) {
		return std::shared_ptr<const idLevelLoadDecodedSource>();
	}
	for ( const std::unique_ptr<Item> &item : items ) {
		if ( expectedGeneration != generation || item->source.normalizedPath != path ||
			item->source.type != expectedType ||
			item->source.sourceBytes != expectedBytes ||
			item->source.sourceTimestamp != expectedTimestamp ||
			item->source.containerChecksum != expectedContainerChecksum ) {
			continue;
		}
		if ( item->state.load( std::memory_order_acquire ) != PipelineItemState::READY ) {
			return std::shared_ptr<const idLevelLoadDecodedSource>();
		}
		if ( item->decoded == nullptr || !ValidateDecodedSource( *item->decoded ) ||
			item->decoded->generation != expectedGeneration ||
			item->decoded->normalizedPath != path ||
			item->decoded->type != expectedType ||
			item->decoded->sourceBytes != expectedBytes ||
			item->decoded->sourceTimestamp != expectedTimestamp ||
			item->decoded->containerChecksum != expectedContainerChecksum ) {
			return std::shared_ptr<const idLevelLoadDecodedSource>();
		}
		cacheHits.fetch_add( 1, std::memory_order_relaxed );
		return item->decoded;
	}
	return std::shared_ptr<const idLevelLoadDecodedSource>();
}

bool idLevelLoadPipeline::ValidateDecodedSource(
		const idLevelLoadDecodedSource &decoded ) const {
	return decoded.framingVersion == LEVEL_LOAD_DECODED_FRAMING_VERSION &&
		decoded.generation == generation && !decoded.normalizedPath.empty() &&
		decoded.type != 0 && decoded.frameKind != idLevelLoadDecodedFrameKind::INVALID &&
		static_cast<std::uint32_t>( decoded.frameKind ) <=
			static_cast<std::uint32_t>( idLevelLoadDecodedFrameKind::JPEG ) &&
		decoded.sourceBytes != 0 && decoded.bytes != nullptr &&
		decoded.bytes->size() == decoded.sourceBytes &&
		decoded.payloadOffset <= decoded.sourceBytes && decoded.payloadBytes != 0 &&
		decoded.payloadBytes <= decoded.sourceBytes - decoded.payloadOffset &&
		decoded.frameUnitCount != 0 && decoded.frameUnitCount <= MAX_FRAME_UNITS &&
		HasContentIntegrity( decoded.contentIntegrity ) &&
		decoded.framingSeal == ComputeFramingSeal( decoded );
}

void idLevelLoadPipeline::DrainOpenFiles( std::vector<idFile *> &files ) {
	for ( const std::unique_ptr<Item> &item : items ) {
		if ( item->source.file != nullptr ) {
			files.push_back( item->source.file );
			item->source.file = nullptr;
		}
	}
	files.insert( files.end(), rejectedOpenFiles.begin(), rejectedOpenFiles.end() );
	rejectedOpenFiles.clear();
}

void idLevelLoadPipeline::Reset() {
	CancelAndWait();
	items.clear();
	rejectedOpenFiles.clear();
	generation = 0;
	readFunction = nullptr;
	readUserData = nullptr;
	decodeFunction = nullptr;
	decodeUserData = nullptr;
	admittedEntries.store( 0, std::memory_order_relaxed );
	rejectedEntries.store( 0, std::memory_order_relaxed );
	completedEntries.store( 0, std::memory_order_relaxed );
	cancelledEntries.store( 0, std::memory_order_relaxed );
	failedEntries.store( 0, std::memory_order_relaxed );
	bytesRead.store( 0, std::memory_order_relaxed );
	currentStagingBytes.store( 0, std::memory_order_relaxed );
	peakStagingBytes.store( 0, std::memory_order_relaxed );
	decodeStartedEntries.store( 0, std::memory_order_relaxed );
	decodeCompletedEntries.store( 0, std::memory_order_relaxed );
	decodeCancelledEntries.store( 0, std::memory_order_relaxed );
	decodeFailedEntries.store( 0, std::memory_order_relaxed );
	decodeBudgetRejectedEntries.store( 0, std::memory_order_relaxed );
	bytesDecoded.store( 0, std::memory_order_relaxed );
	admittedDecodedBytes.store( 0, std::memory_order_relaxed );
	currentDecodedBytes.store( 0, std::memory_order_relaxed );
	peakDecodedBytes.store( 0, std::memory_order_relaxed );
	cacheHits.store( 0, std::memory_order_relaxed );
	synchronousFallback.store( false, std::memory_order_relaxed );
	active.store( false, std::memory_order_relaxed );
	cancelled.store( false, std::memory_order_relaxed );
}

idLevelLoadPipelineMetrics idLevelLoadPipeline::GetMetrics() const {
	idLevelLoadPipelineMetrics metrics;
	metrics.generation = generation;
	metrics.admittedEntries = admittedEntries.load( std::memory_order_relaxed );
	metrics.rejectedEntries = rejectedEntries.load( std::memory_order_relaxed );
	metrics.completedEntries = completedEntries.load( std::memory_order_relaxed );
	metrics.cancelledEntries = cancelledEntries.load( std::memory_order_relaxed );
	metrics.failedEntries = failedEntries.load( std::memory_order_relaxed );
	metrics.bytesRead = bytesRead.load( std::memory_order_relaxed );
	metrics.peakStagingBytes = peakStagingBytes.load( std::memory_order_relaxed );
	metrics.decodeStartedEntries = decodeStartedEntries.load( std::memory_order_relaxed );
	metrics.decodeCompletedEntries = decodeCompletedEntries.load( std::memory_order_relaxed );
	metrics.decodeCancelledEntries = decodeCancelledEntries.load( std::memory_order_relaxed );
	metrics.decodeFailedEntries = decodeFailedEntries.load( std::memory_order_relaxed );
	metrics.decodeBudgetRejectedEntries = decodeBudgetRejectedEntries.load( std::memory_order_relaxed );
	metrics.bytesDecoded = bytesDecoded.load( std::memory_order_relaxed );
	metrics.admittedDecodedBytes = admittedDecodedBytes.load( std::memory_order_relaxed );
	metrics.decodeBudgetBytes = currentConfig.maxDecodedBytes;
	metrics.peakDecodedBytes = peakDecodedBytes.load( std::memory_order_relaxed );
	metrics.cacheHits = cacheHits.load( std::memory_order_relaxed );
	metrics.synchronousFallback = synchronousFallback.load( std::memory_order_relaxed );
	metrics.active = active.load( std::memory_order_relaxed );
	metrics.cancelled = cancelled.load( std::memory_order_relaxed );
	return metrics;
}
