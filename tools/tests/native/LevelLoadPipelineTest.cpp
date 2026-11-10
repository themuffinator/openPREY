#include "src/framework/LevelLoadPipeline.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <thread>
#include <vector>

namespace {

int failures = 0;

void Expect( const bool condition, const char *label ) {
	if ( !condition ) {
		std::fprintf( stderr, "LevelLoadPipelineTest failed: %s\n", label );
		++failures;
	}
}

struct FakeFile {
	std::vector<unsigned char> bytes;
	std::size_t position = 0;
	std::atomic<unsigned int> reads{ 0 };
	unsigned int delayMilliseconds = 0;
};

idFile *OpaqueFile( FakeFile &file ) {
	return reinterpret_cast<idFile *>( &file );
}

int ReadFakeFile( idFile *opaque, void *buffer, const int byteCount, void * ) {
	FakeFile *file = reinterpret_cast<FakeFile *>( opaque );
	if ( file == nullptr || buffer == nullptr || byteCount <= 0 ) {
		return 0;
	}
	if ( file->delayMilliseconds != 0 ) {
		std::this_thread::sleep_for( std::chrono::milliseconds( file->delayMilliseconds ) );
	}
	if ( file->position >= file->bytes.size() ) {
		return 0;
	}
	const std::size_t requested = static_cast<std::size_t>( byteCount );
	const std::size_t copied = std::min( requested, file->bytes.size() - file->position );
	std::memcpy( buffer, file->bytes.data() + file->position, copied );
	file->position += copied;
	file->reads.fetch_add( 1, std::memory_order_release );
	return static_cast<int>( copied );
}

struct DecodeHarness {
	std::atomic<unsigned int> completed{ 0 };
	std::atomic<unsigned int> started{ 0 };
	unsigned int delayMilliseconds = 0;
};

std::uint64_t UpdateChecksum( std::uint64_t checksum,
		const unsigned char *bytes, const std::size_t byteCount ) {
	for ( std::size_t index = 0; index < byteCount; ++index ) {
		checksum ^= bytes[index];
		checksum *= 1099511628211ull;
	}
	return checksum;
}

idLevelLoadDecodeStatus DecodeTestSource( const idLevelLoadPipelineSource &source,
		const unsigned char *bytes, const std::size_t byteCount,
		const idLevelLoadDecodeContext &context, idLevelLoadDecodeOutput &output,
		void *userData ) {
	DecodeHarness *harness = static_cast<DecodeHarness *>( userData );
	if ( bytes == nullptr || byteCount == 0 || harness == nullptr ) {
		return idLevelLoadDecodeStatus::MALFORMED;
	}
		harness->started.fetch_add( 1, std::memory_order_release );
	const idLevelLoadDecodeStatus frameStatus = idLevelLoadDecodeSourceFrame(
		source, bytes, byteCount, output, &context );
	if ( frameStatus != idLevelLoadDecodeStatus::COMPLETE ) {
		return frameStatus;
	}
	std::uint64_t checksum = 14695981039346656037ull;
	std::size_t offset = 0;
	while ( offset < byteCount ) {
		if ( context.IsCancellationRequested() ) {
			return idLevelLoadDecodeStatus::CANCELLED;
		}
		if ( harness->delayMilliseconds != 0 ) {
			std::this_thread::sleep_for(
				std::chrono::milliseconds( harness->delayMilliseconds ) );
		}
		const std::size_t chunkBytes = std::min( context.chunkBytes, byteCount - offset );
		checksum = UpdateChecksum( checksum, bytes + offset, chunkBytes );
		if ( !context.ReportDecodedBytes( chunkBytes ) ) {
			return context.IsCancellationRequested()
				? idLevelLoadDecodeStatus::CANCELLED
				: idLevelLoadDecodeStatus::MALFORMED;
		}
		offset += chunkBytes;
	}
	output.transportChecksum = checksum;
	for ( std::size_t index = 0; index < output.contentIntegrity.size(); ++index ) {
		output.contentIntegrity[index] = static_cast<unsigned char>(
			( checksum >> ( ( index % 8 ) * 8 ) ) ^ index );
	}
	harness->completed.fetch_add( 1, std::memory_order_relaxed );
	return idLevelLoadDecodeStatus::COMPLETE;
}

idLevelLoadPipelineSource MakeSource( const char *path, FakeFile &file,
		const unsigned int priority, const unsigned int order,
		const std::uint64_t timestamp, const std::uint32_t checksum ) {
	idLevelLoadPipelineSource source;
	source.normalizedPath = path;
	source.type = 1;
	source.priority = priority;
	source.firstUseOrder = order;
	source.file = OpaqueFile( file );
	source.sourceBytes = file.bytes.size();
	source.sourceTimestamp = timestamp;
	source.containerChecksum = checksum;
	return source;
}

void AppendTag( std::vector<unsigned char> &bytes, const char *tag ) {
	bytes.insert( bytes.end(), tag, tag + 4 );
}

void AppendLittleU32( std::vector<unsigned char> &bytes, const std::uint32_t value ) {
	for ( std::size_t index = 0; index < 4; ++index ) {
		bytes.push_back( static_cast<unsigned char>( value >> ( index * 8 ) ) );
	}
}

void AppendBigU32( std::vector<unsigned char> &bytes, const std::uint32_t value ) {
	for ( std::size_t index = 0; index < 4; ++index ) {
		bytes.push_back( static_cast<unsigned char>( value >> ( ( 3 - index ) * 8 ) ) );
	}
}

void StoreLittleU32( std::vector<unsigned char> &bytes, const std::size_t offset,
		const std::uint32_t value ) {
	for ( std::size_t index = 0; index < 4; ++index ) {
		bytes[offset + index] = static_cast<unsigned char>( value >> ( index * 8 ) );
	}
}

void StoreBigU32( std::vector<unsigned char> &bytes, const std::size_t offset,
		const std::uint32_t value ) {
	for ( std::size_t index = 0; index < 4; ++index ) {
		bytes[offset + index] = static_cast<unsigned char>( value >> ( ( 3 - index ) * 8 ) );
	}
}

idLevelLoadPipelineSource FrameSource( const char *path ) {
	idLevelLoadPipelineSource source;
	source.normalizedPath = path;
	source.type = 1;
	return source;
}

void ExpectFrame( const char *path, const std::vector<unsigned char> &bytes,
		const bool valid, const idLevelLoadDecodedFrameKind expectedKind,
		const std::uint32_t expectedUnits, const char *label ) {
	idLevelLoadDecodeOutput output;
	const idLevelLoadDecodeStatus status = idLevelLoadDecodeSourceFrame(
		FrameSource( path ), bytes.data(), bytes.size(), output );
	Expect( ( status == idLevelLoadDecodeStatus::COMPLETE ) == valid, label );
	if ( valid ) {
		Expect( output.frameKind == expectedKind && output.decodedBytes == bytes.size() &&
			output.payloadOffset == 0 && output.payloadBytes == bytes.size() &&
			output.frameUnitCount == expectedUnits,
			"production frame metadata is bounded and complete" );
	}
}

void ExerciseProductionFramingValidation() {
	std::vector<unsigned char> wave;
	AppendTag( wave, "RIFF" );
	AppendLittleU32( wave, 0 );
	AppendTag( wave, "WAVE" );
	AppendTag( wave, "fmt " );
	AppendLittleU32( wave, 16 );
	wave.insert( wave.end(), 16, 0 );
	AppendTag( wave, "data" );
	AppendLittleU32( wave, 4 );
	wave.insert( wave.end(), 4, 0x7f );
	StoreLittleU32( wave, 4, static_cast<std::uint32_t>( wave.size() - 8 ) );
	ExpectFrame( "sound/valid.wav", wave, true,
		idLevelLoadDecodedFrameKind::RIFF_WAVE, 2, "complete RIFF/WAVE framing succeeds" );
	std::vector<unsigned char> truncatedWave = wave;
	truncatedWave.pop_back();
	ExpectFrame( "sound/truncated.wav", truncatedWave, false,
		idLevelLoadDecodedFrameKind::INVALID, 0, "truncated RIFF framing fails closed" );
	std::vector<unsigned char> trailingWave = wave;
	trailingWave.push_back( 0 );
	ExpectFrame( "sound/trailing.wav", trailingWave, false,
		idLevelLoadDecodedFrameKind::INVALID, 0, "RIFF trailing data fails closed" );
	std::vector<unsigned char> oversizedWave = wave;
	StoreLittleU32( oversizedWave, 16, 0xffffffffu );
	ExpectFrame( "sound/oversized.wav", oversizedWave, false,
		idLevelLoadDecodedFrameKind::INVALID, 0, "oversized RIFF chunk fails closed" );

	std::vector<unsigned char> ogg( 27, 0 );
	std::memcpy( ogg.data(), "OggS", 4 );
	ogg[4] = 0;
	ogg[26] = 1;
	ogg.push_back( 3 );
	ogg.push_back( 1 );
	ogg.push_back( 2 );
	ogg.push_back( 3 );
	ExpectFrame( "sound/valid.ogg", ogg, true,
		idLevelLoadDecodedFrameKind::OGG, 1, "complete Ogg page framing succeeds" );
	std::vector<unsigned char> truncatedOgg = ogg;
	truncatedOgg.pop_back();
	ExpectFrame( "sound/truncated.ogg", truncatedOgg, false,
		idLevelLoadDecodedFrameKind::INVALID, 0, "truncated Ogg page fails closed" );
	std::vector<unsigned char> trailingOgg = ogg;
	trailingOgg.push_back( 0 );
	ExpectFrame( "sound/trailing.ogg", trailingOgg, false,
		idLevelLoadDecodedFrameKind::INVALID, 0, "Ogg trailing data fails closed" );
	std::vector<unsigned char> oversizedOgg = ogg;
	oversizedOgg[26] = 255;
	ExpectFrame( "sound/oversized.ogg", oversizedOgg, false,
		idLevelLoadDecodedFrameKind::INVALID, 0, "oversized Ogg segment table fails closed" );

	std::vector<unsigned char> png = { 0x89, 'P', 'N', 'G', 0x0d, 0x0a, 0x1a, 0x0a };
	AppendBigU32( png, 13 );
	AppendTag( png, "IHDR" );
	AppendBigU32( png, 1 );
	AppendBigU32( png, 1 );
	png.insert( png.end(), 5, 0 );
	AppendBigU32( png, 0 );
	AppendBigU32( png, 1 );
	AppendTag( png, "IDAT" );
	png.push_back( 0 );
	AppendBigU32( png, 0 );
	AppendBigU32( png, 0 );
	AppendTag( png, "IEND" );
	AppendBigU32( png, 0 );
	ExpectFrame( "textures/valid.png", png, true,
		idLevelLoadDecodedFrameKind::PNG, 3, "complete PNG chunk framing succeeds" );
	std::vector<unsigned char> truncatedPng = png;
	truncatedPng.pop_back();
	ExpectFrame( "textures/truncated.png", truncatedPng, false,
		idLevelLoadDecodedFrameKind::INVALID, 0, "truncated PNG IEND fails closed" );
	std::vector<unsigned char> trailingPng = png;
	trailingPng.push_back( 0 );
	ExpectFrame( "textures/trailing.png", trailingPng, false,
		idLevelLoadDecodedFrameKind::INVALID, 0, "PNG trailing data fails closed" );
	std::vector<unsigned char> oversizedPng = png;
	StoreBigU32( oversizedPng, 8, 0xffffffffu );
	ExpectFrame( "textures/oversized.png", oversizedPng, false,
		idLevelLoadDecodedFrameKind::INVALID, 0, "oversized PNG chunk fails closed" );

	const std::vector<unsigned char> jpeg = { 0xff, 0xd8, 0xff, 0xd9 };
	ExpectFrame( "textures/valid.jpg", jpeg, true,
		idLevelLoadDecodedFrameKind::JPEG, 1, "terminal JPEG EOI succeeds" );
	std::vector<unsigned char> trailingJpeg = jpeg;
	trailingJpeg.push_back( 0 );
	ExpectFrame( "textures/trailing.jpg", trailingJpeg, false,
		idLevelLoadDecodedFrameKind::INVALID, 0, "JPEG trailing data fails closed" );

	const std::vector<unsigned char> dds = { 'n', 'o', 't', '-', 'a', '-', 'd', 'd', 's' };
	ExpectFrame( "textures/deferred.dds", dds, true,
		idLevelLoadDecodedFrameKind::OPAQUE_VFS_BYTES, 1,
		"DDS remains opaque for renderer-owned complete layout validation" );
}

void ExerciseSetupFailureHandleRecovery() {
	FakeFile file;
	file.bytes.assign( 8, 0x31 );
	std::vector<idLevelLoadPipelineSource> sources;
	sources.push_back( MakeSource( "models/setup-failure.ase", file, 1, 0, 2, 0 ) );
	idLevelLoadPipelineConfig config;
	config.maxEntries = 1;
	config.maxSourceBytes = 8;
	config.maxTotalBytes = 8;
	config.maxDecodedBytes = 8;
	config.readChunkBytes = 4;
	config.decodeChunkBytes = 4;
	idLevelLoadPipeline pipeline;
	Expect( !pipeline.Begin( 2, config, std::move( sources ), &ReadFakeFile ),
		"missing production decode stage rejects pipeline setup" );
	std::vector<idFile *> handles;
	pipeline.DrainOpenFiles( handles );
	Expect( handles.size() == 1,
		"setup failure returns every independently opened source handle" );
	pipeline.Reset();
}

void ExerciseBoundedSynchronousReplay() {
	idJobSystemConfig jobs;
	jobs.synchronous = true;
	jobs.workerThreads = 0;
	jobs.maxQueuedLists = 4;
	Expect( jobSystem.Initialize( jobs ), "synchronous job system initializes" );

	FakeFile first;
	first.bytes.assign( 8, 0x11 );
	FakeFile critical;
	critical.bytes.assign( 12, 0x22 );
	FakeFile oversized;
	oversized.bytes.assign( 40, 0x33 );

	std::vector<idLevelLoadPipelineSource> sources;
	sources.push_back( MakeSource( "models/first.ase", first, 1, 2, 41, 0 ) );
	sources.push_back( MakeSource( "maps/test.proc", critical, 3, 1, 0, 0x12345678u ) );
	sources.push_back( MakeSource( "textures/oversized.tga", oversized, 2, 3, 42, 0 ) );

	idLevelLoadPipelineConfig config;
	config.maxEntries = 2;
	config.maxSourceBytes = 40;
	config.maxTotalBytes = 60;
	config.maxDecodedBytes = 20;
	config.readChunkBytes = 3;
	config.decodeChunkBytes = 3;
	DecodeHarness decoder;
	idLevelLoadPipeline pipeline;
	Expect( pipeline.Begin( 7, config, std::move( sources ), &ReadFakeFile, nullptr,
		&DecodeTestSource, &decoder ), "bounded replay begins" );
	pipeline.Wait();

	const idLevelLoadPipelineMetrics metrics = pipeline.GetMetrics();
	Expect( metrics.generation == 7, "generation identity retained" );
	Expect( metrics.admittedEntries == 2 && metrics.rejectedEntries == 1,
		"entry and byte budgets reject lower-priority overflow" );
	Expect( metrics.completedEntries == 2 && metrics.failedEntries == 0,
		"admitted synchronous reads complete" );
	Expect( metrics.synchronousFallback,
		"jobs-disabled execution is reported as an explicit synchronous path" );
	Expect( metrics.bytesRead == 20 && metrics.peakStagingBytes <= 20,
		"read and peak staging metrics stay bounded" );
	Expect( metrics.decodeBudgetRejectedEntries == 1 &&
		metrics.admittedDecodedBytes == 20 && metrics.decodeBudgetBytes == 20 &&
		metrics.peakDecodedBytes <= 20,
		"decode admission and retained-result metrics stay within their budget" );
	Expect( metrics.decodeStartedEntries == 2 && metrics.decodeCompletedEntries == 2 &&
		metrics.bytesDecoded == 20 && decoder.completed.load( std::memory_order_relaxed ) == 2,
		"decode callback inspects and publishes every admitted byte" );

	const std::shared_ptr<const idLevelLoadDecodedSource> acquired = pipeline.Acquire(
		7, "maps/test.proc", 1, 12, 0, 0x12345678u );
	Expect( acquired != nullptr && acquired->bytes != nullptr &&
		acquired->bytes->size() == 12 && ( *acquired->bytes )[0] == 0x22 &&
		acquired->frameKind == idLevelLoadDecodedFrameKind::OPAQUE_VFS_BYTES &&
		acquired->payloadOffset == 0 && acquired->payloadBytes == 12 &&
		acquired->frameUnitCount == 1,
		"exact source identity acquires an immutable framed decode result" );
	Expect( pipeline.Acquire( 8, "maps/test.proc", 1, 12, 0, 0x12345678u ) == nullptr,
		"generation mismatch cannot adopt a completed result" );
	Expect( pipeline.Acquire( 7, "maps/test.proc", 1, 12, 1, 0x12345678u ) == nullptr,
		"timestamp mismatch cannot acquire bytes" );

	std::vector<idFile *> handles;
	pipeline.DrainOpenFiles( handles );
	Expect( handles.size() == 3, "admitted and rejected handles are returned after join" );
	pipeline.Reset();
	jobSystem.Shutdown();
}

void ExerciseCooperativeCancellation() {
	idJobSystemConfig jobs;
	jobs.synchronous = false;
	jobs.workerThreads = 2;
	jobs.maxQueuedLists = 4;
	Expect( jobSystem.Initialize( jobs ), "threaded job system initializes" );

	FakeFile slow;
	slow.bytes.assign( 2u * 1024u * 1024u, 0x5a );
	slow.delayMilliseconds = 1;
	std::vector<idLevelLoadPipelineSource> sources;
	sources.push_back( MakeSource( "maps/cancel.proc", slow, 3, 0, 0, 0x89abcdefu ) );

	idLevelLoadPipelineConfig config;
	config.maxEntries = 1;
	config.maxSourceBytes = slow.bytes.size();
	config.maxTotalBytes = slow.bytes.size();
	config.maxDecodedBytes = slow.bytes.size();
	config.readChunkBytes = 4096;
	config.decodeChunkBytes = 4096;
	DecodeHarness decoder;
	idLevelLoadPipeline pipeline;
	Expect( pipeline.Begin( 8, config, std::move( sources ), &ReadFakeFile,
		nullptr, &DecodeTestSource, &decoder ),
		"threaded replay begins" );
	const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds( 2 );
	while ( slow.reads.load( std::memory_order_acquire ) < 4 &&
		std::chrono::steady_clock::now() < deadline ) {
		std::this_thread::yield();
	}
	Expect( slow.reads.load( std::memory_order_acquire ) >= 4,
		"worker enters chunked read before cancellation" );
	pipeline.CancelAndWait();
	const idLevelLoadPipelineMetrics metrics = pipeline.GetMetrics();
	Expect( metrics.cancelled && metrics.cancelledEntries == 1,
		"generation cancellation reaches the active item" );
	Expect( metrics.bytesRead < slow.bytes.size() && !metrics.active,
		"cancelled item stops before full read and joins" );
	Expect( pipeline.Acquire( 8, "maps/cancel.proc", 1, slow.bytes.size(), 0,
		0x89abcdefu ) == nullptr,
		"cancelled bytes are never published" );
	std::vector<idFile *> handles;
	pipeline.DrainOpenFiles( handles );
	Expect( handles.size() == 1, "cancelled source handle is returned" );
	pipeline.Reset();
	jobSystem.Shutdown();
}

void ExerciseCooperativeDecodeCancellation() {
	idJobSystemConfig jobs;
	jobs.synchronous = false;
	jobs.workerThreads = 1;
	jobs.maxQueuedLists = 4;
	Expect( jobSystem.Initialize( jobs ), "decode-cancellation job system initializes" );

	FakeFile file;
	file.bytes.assign( 64u * 1024u, 0x6d );
	std::vector<idLevelLoadPipelineSource> sources;
	sources.push_back( MakeSource( "models/cancel-decode.ase", file, 3, 0, 18, 0 ) );
	idLevelLoadPipelineConfig config;
	config.maxEntries = 1;
	config.maxSourceBytes = file.bytes.size();
	config.maxTotalBytes = file.bytes.size();
	config.maxDecodedBytes = file.bytes.size();
	config.readChunkBytes = file.bytes.size();
	config.decodeChunkBytes = 256;
	DecodeHarness decoder;
	decoder.delayMilliseconds = 1;
	idLevelLoadPipeline pipeline;
	Expect( pipeline.Begin( 18, config, std::move( sources ), &ReadFakeFile,
		nullptr, &DecodeTestSource, &decoder ), "decode-cancellation replay begins" );
	const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds( 2 );
	while ( decoder.started.load( std::memory_order_acquire ) == 0 &&
		std::chrono::steady_clock::now() < deadline ) {
		std::this_thread::yield();
	}
	Expect( decoder.started.load( std::memory_order_acquire ) == 1,
		"worker enters decode before cancellation" );
	pipeline.CancelAndWait();
	const idLevelLoadPipelineMetrics metrics = pipeline.GetMetrics();
	Expect( metrics.cancelled && metrics.decodeStartedEntries == 1 &&
		metrics.decodeCancelledEntries == 1 && metrics.cancelledEntries == 1,
		"decode observes generation cancellation cooperatively" );
	Expect( metrics.bytesRead == file.bytes.size() &&
		metrics.bytesDecoded < file.bytes.size() && metrics.decodeCompletedEntries == 0,
		"decode cancellation occurs after read and before result publication" );
	Expect( pipeline.Acquire( 18, "models/cancel-decode.ase", 1,
		file.bytes.size(), 18, 0 ) == nullptr,
		"cancelled decode cannot be adopted" );
	std::vector<idFile *> handles;
	pipeline.DrainOpenFiles( handles );
	Expect( handles.size() == 1, "decode-cancelled source handle is returned" );
	pipeline.Reset();
	jobSystem.Shutdown();
}

void ExerciseMalformedFramingFallback() {
	idJobSystemConfig jobs;
	jobs.synchronous = true;
	jobs.workerThreads = 0;
	jobs.maxQueuedLists = 4;
	Expect( jobSystem.Initialize( jobs ), "malformed-frame job system initializes" );

	FakeFile malformed;
	malformed.bytes.assign( 128, 0x44 );
	std::vector<idLevelLoadPipelineSource> sources;
	sources.push_back( MakeSource( "sound/malformed.wav", malformed, 2, 0, 21, 0 ) );
	idLevelLoadPipelineConfig config;
	config.maxEntries = 1;
	config.maxSourceBytes = malformed.bytes.size();
	config.maxTotalBytes = malformed.bytes.size();
	config.maxDecodedBytes = malformed.bytes.size();
	config.readChunkBytes = 64;
	config.decodeChunkBytes = 64;
	DecodeHarness decoder;
	idLevelLoadPipeline pipeline;
	Expect( pipeline.Begin( 21, config, std::move( sources ), &ReadFakeFile,
		nullptr, &DecodeTestSource, &decoder ), "malformed frame replay begins" );
	pipeline.Wait();
	const idLevelLoadPipelineMetrics metrics = pipeline.GetMetrics();
	Expect( metrics.decodeStartedEntries == 1 && metrics.decodeFailedEntries == 1 &&
		metrics.failedEntries == 1 && metrics.decodeCompletedEntries == 0,
		"malformed framing fails only the speculative decode" );
	Expect( pipeline.Acquire( 21, "sound/malformed.wav", 1,
		malformed.bytes.size(), 21, 0 ) == nullptr,
		"malformed framing leaves authoritative VFS fallback available" );
	std::vector<idFile *> handles;
	pipeline.DrainOpenFiles( handles );
	Expect( handles.size() == 1, "malformed framed source handle is returned" );
	pipeline.Reset();
	jobSystem.Shutdown();
}

struct Blocker {
	std::mutex mutex;
	std::condition_variable condition;
	bool started = false;
	bool release = false;
};

void BlockingJob( const idJobContext &context ) {
	Blocker *blocker = static_cast<Blocker *>( context.data );
	std::unique_lock<std::mutex> lock( blocker->mutex );
	blocker->started = true;
	blocker->condition.notify_all();
	blocker->condition.wait( lock, [blocker, &context]() {
		return blocker->release || context.IsCancellationRequested();
	} );
}

void ExerciseQueueSaturationFallback() {
	idJobSystemConfig jobs;
	jobs.synchronous = false;
	jobs.workerThreads = 1;
	jobs.maxQueuedLists = 1;
	Expect( jobSystem.Initialize( jobs ), "saturation job system initializes" );
	Blocker blocker;
	std::unique_ptr<idJobList> occupied = jobSystem.CreateJobList( "occupied", 1, 0 );
	Expect( occupied != nullptr && occupied->AddJob( &BlockingJob, &blocker ),
		"occupying list is created" );
	Expect( occupied->Submit() == idJobSubmitResult::ACCEPTED,
		"occupying list is submitted" );
	{
		std::unique_lock<std::mutex> lock( blocker.mutex );
		Expect( blocker.condition.wait_for( lock, std::chrono::seconds( 2 ), [&blocker]() {
			return blocker.started;
		} ), "occupying job starts" );
	}

	FakeFile file;
	file.bytes.assign( 16, 0x77 );
	std::vector<idLevelLoadPipelineSource> sources;
	sources.push_back( MakeSource( "models/fallback.ase", file, 2, 0, 5, 0 ) );
	idLevelLoadPipelineConfig config;
	config.maxEntries = 1;
	config.maxSourceBytes = 16;
	config.maxTotalBytes = 16;
	config.maxDecodedBytes = 16;
	config.readChunkBytes = 4;
	config.decodeChunkBytes = 4;
	DecodeHarness decoder;
	idLevelLoadPipeline pipeline;
	Expect( pipeline.Begin( 9, config, std::move( sources ), &ReadFakeFile,
		nullptr, &DecodeTestSource, &decoder ),
		"queue-full replay executes inline" );
	const idLevelLoadPipelineMetrics metrics = pipeline.GetMetrics();
	Expect( metrics.synchronousFallback && metrics.completedEntries == 1,
		"queue saturation is explicit and never drops work" );

	{
		std::lock_guard<std::mutex> lock( blocker.mutex );
		blocker.release = true;
	}
	blocker.condition.notify_all();
	occupied->Wait();
	pipeline.Wait();
	std::vector<idFile *> handles;
	pipeline.DrainOpenFiles( handles );
	Expect( handles.size() == 1, "fallback source handle is returned" );
	pipeline.Reset();
	jobSystem.Shutdown();
}

} // namespace

int main() {
	ExerciseProductionFramingValidation();
	ExerciseSetupFailureHandleRecovery();
	ExerciseBoundedSynchronousReplay();
	ExerciseCooperativeCancellation();
	ExerciseCooperativeDecodeCancellation();
	ExerciseMalformedFramingFallback();
	ExerciseQueueSaturationFallback();
	if ( failures != 0 ) {
		std::fprintf( stderr, "LevelLoadPipelineTest: %d failure(s)\n", failures );
		return 1;
	}
	std::printf( "LevelLoadPipelineTest passed\n" );
	return 0;
}
