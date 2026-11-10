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

#ifndef __LEVEL_LOAD_PIPELINE_H__
#define __LEVEL_LOAD_PIPELINE_H__

#include "ParallelJobSystem.h"

#include <atomic>
#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

class idFile;

struct idLevelLoadPipelineConfig {
	std::size_t maxEntries;
	std::uint64_t maxSourceBytes;
	std::uint64_t maxTotalBytes;
	std::uint64_t maxDecodedBytes;
	std::size_t readChunkBytes;
	std::size_t decodeChunkBytes;

	idLevelLoadPipelineConfig();
};

struct idLevelLoadPipelineSource {
	std::string normalizedPath;
	std::uint32_t type;
	std::uint32_t priority;
	std::uint32_t firstUseOrder;
	idFile *file;
	std::uint64_t sourceBytes;
	std::uint64_t sourceTimestamp;
	std::uint32_t containerChecksum;

	idLevelLoadPipelineSource();
};

struct idLevelLoadPipelineMetrics {
	std::uint64_t generation;
	std::uint64_t admittedEntries;
	std::uint64_t rejectedEntries;
	std::uint64_t completedEntries;
	std::uint64_t cancelledEntries;
	std::uint64_t failedEntries;
	std::uint64_t bytesRead;
	std::uint64_t peakStagingBytes;
	std::uint64_t decodeStartedEntries;
	std::uint64_t decodeCompletedEntries;
	std::uint64_t decodeCancelledEntries;
	std::uint64_t decodeFailedEntries;
	std::uint64_t decodeBudgetRejectedEntries;
	std::uint64_t bytesDecoded;
	std::uint64_t admittedDecodedBytes;
	std::uint64_t decodeBudgetBytes;
	std::uint64_t peakDecodedBytes;
	std::uint64_t cacheHits;
	bool synchronousFallback;
	bool active;
	bool cancelled;

	idLevelLoadPipelineMetrics();
};

enum class idLevelLoadDecodedFrameKind : std::uint32_t {
	INVALID = 0,
	OPAQUE_VFS_BYTES = 1,
	RIFF_WAVE = 2,
	OGG = 3,
	PNG = 4,
	JPEG = 5
};

enum class idLevelLoadDecodeStatus : std::uint32_t {
	COMPLETE = 0,
	MALFORMED,
	CANCELLED
};

struct idLevelLoadDecodeOutput {
	idLevelLoadDecodedFrameKind frameKind;
	std::uint64_t decodedBytes;
	std::uint64_t payloadOffset;
	std::uint64_t payloadBytes;
	std::uint32_t frameUnitCount;
	std::uint64_t transportChecksum;
	std::array<unsigned char, 32> contentIntegrity;

	idLevelLoadDecodeOutput();
};

struct idLevelLoadDecodeContext;

// Portable, allocation-free framing validation used by the production
// decoder and its native malformed/truncation/trailing-data tests. DDS remains
// opaque here because its complete mip/array layout is owned by the renderer.
idLevelLoadDecodeStatus idLevelLoadDecodeSourceFrame(
	const idLevelLoadPipelineSource &source,
	const unsigned char *bytes,
	std::size_t byteCount,
	idLevelLoadDecodeOutput &output,
	const idLevelLoadDecodeContext *context = nullptr );

// A decoder may only publish a result after reporting every inspected byte.
// Both operations are safe to call from a worker and make long decode loops
// cooperatively cancellable without exposing engine globals to that worker.
struct idLevelLoadDecodeContext {
	std::uint64_t generation;
	std::size_t chunkBytes;

	bool IsCancellationRequested() const;
	bool ReportDecodedBytes( std::size_t byteCount ) const;

private:
	typedef bool ( *CancellationFunction )( void *state );
	typedef bool ( *ProgressFunction )( void *state, std::size_t byteCount );

	CancellationFunction cancellationFunction;
	ProgressFunction progressFunction;
	void *state;

	idLevelLoadDecodeContext();
	friend class idLevelLoadPipeline;
};

typedef idLevelLoadDecodeStatus ( *idLevelLoadDecodeFunction )(
	const idLevelLoadPipelineSource &source,
	const unsigned char *bytes,
	std::size_t byteCount,
	const idLevelLoadDecodeContext &context,
	idLevelLoadDecodeOutput &output,
	void *userData );

typedef int ( *idLevelLoadReadFunction )(
	idFile *file,
	void *buffer,
	int byteCount,
	void *userData );

// Immutable worker-produced framing/integrity DTO. Asset-specific parsers
// remain main-thread owners; this only authorizes a byte-view substitution.
struct idLevelLoadDecodedSource {
	std::uint32_t framingVersion;
	std::uint64_t generation;
	std::string normalizedPath;
	std::uint32_t type;
	idLevelLoadDecodedFrameKind frameKind;
	std::uint64_t sourceBytes;
	std::uint64_t payloadOffset;
	std::uint64_t payloadBytes;
	std::uint32_t frameUnitCount;
	std::uint64_t sourceTimestamp;
	std::uint32_t containerChecksum;
	std::uint64_t transportChecksum;
	std::array<unsigned char, 32> contentIntegrity;
	std::shared_ptr<const std::vector<unsigned char> > bytes;
	std::uint64_t framingSeal;

	idLevelLoadDecodedSource();
};

class idLevelLoadPipeline {
public:
	idLevelLoadPipeline();
	~idLevelLoadPipeline();

	idLevelLoadPipeline( const idLevelLoadPipeline & ) = delete;
	idLevelLoadPipeline &operator=( const idLevelLoadPipeline & ) = delete;

	// Every source file must be independently opened on the main thread.  The
	// pipeline owns no VFS resolution state and returns all handles to the owner
	// through DrainOpenFiles() after a join.
	bool Begin( std::uint64_t generation,
		const idLevelLoadPipelineConfig &config,
		std::vector<idLevelLoadPipelineSource> sources,
		idLevelLoadReadFunction readFunction,
		void *readUserData = nullptr,
		idLevelLoadDecodeFunction decodeFunction = nullptr,
		void *decodeUserData = nullptr );

	void CancelAndWait();
	void Wait();
	bool IsActive() const;
	std::uint64_t GetGeneration() const;

	// Returns an immutable decoded DTO only after a main-thread caller supplies
	// the active generation plus the exact authoritative VFS source identity.
	// Returned shared ownership remains valid across Reset() and map teardown.
	std::shared_ptr<const idLevelLoadDecodedSource> Acquire(
		std::uint64_t expectedGeneration,
		const char *normalizedPath,
		std::uint32_t expectedType,
		std::uint64_t expectedBytes,
		std::uint64_t expectedTimestamp,
		std::uint32_t expectedContainerChecksum );

	void DrainOpenFiles( std::vector<idFile *> &files );
	void Reset();
	idLevelLoadPipelineMetrics GetMetrics() const;

private:
	struct Item;

	static void RunJob( const idJobContext &context );
	void RunItem( Item &item, const idJobCancellationToken &cancellation );
	void WaitInternal( bool cancel );
	bool ValidateDecodedSource( const idLevelLoadDecodedSource &decoded ) const;

	idLevelLoadPipelineConfig currentConfig;
	std::uint64_t generation;
	std::vector<std::unique_ptr<Item> > items;
	std::vector<idFile *> rejectedOpenFiles;
	std::unique_ptr<idJobList> jobList;
	idLevelLoadReadFunction readFunction;
	void *readUserData;
	idLevelLoadDecodeFunction decodeFunction;
	void *decodeUserData;

	std::atomic<std::uint64_t> admittedEntries;
	std::atomic<std::uint64_t> rejectedEntries;
	std::atomic<std::uint64_t> completedEntries;
	std::atomic<std::uint64_t> cancelledEntries;
	std::atomic<std::uint64_t> failedEntries;
	std::atomic<std::uint64_t> bytesRead;
	std::atomic<std::uint64_t> currentStagingBytes;
	std::atomic<std::uint64_t> peakStagingBytes;
	std::atomic<std::uint64_t> decodeStartedEntries;
	std::atomic<std::uint64_t> decodeCompletedEntries;
	std::atomic<std::uint64_t> decodeCancelledEntries;
	std::atomic<std::uint64_t> decodeFailedEntries;
	std::atomic<std::uint64_t> decodeBudgetRejectedEntries;
	std::atomic<std::uint64_t> bytesDecoded;
	std::atomic<std::uint64_t> admittedDecodedBytes;
	std::atomic<std::uint64_t> currentDecodedBytes;
	std::atomic<std::uint64_t> peakDecodedBytes;
	std::atomic<std::uint64_t> cacheHits;
	std::atomic<bool> synchronousFallback;
	std::atomic<bool> active;
	std::atomic<bool> cancelled;
};

#endif
