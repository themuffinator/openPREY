// Copyright (C) 2026 DarkMatter Productions
//

#include "src/renderer/GpuFrameTimingCore.h"

#include <climits>
#include <cstdint>
#include <cstdio>
#include <limits>

static int failures = 0;

static void Check( bool condition, const char *message ) {
	if ( condition ) {
		return;
	}
	std::fprintf( stderr, "GpuFrameTimingTest: %s\n", message );
	failures++;
}

int main() {
	gpuFrameTimingCoreState_t state;
	GpuFrameTimingCore_Initialize( state );
	Check( !state.supported && !state.valid && state.frameNumber == -1,
		"initial state must be unsupported and invalid" );

	GpuFrameTimingCore_SetBackend( state, 1, true );
	Check( state.supported && state.backend == 1 && state.generation == 1
			&& state.resetCount == 1,
		"backend selection must begin a fresh generation" );
	GpuFrameTimingCore_RecordResolved( state, 1, 20, state.generation, 4123, 4 );
	Check( state.valid && state.frameNumber == 20 && state.elapsedMicroseconds == 4123
			&& state.latencyFrames == 4 && state.resolvedSamples == 1,
		"resolved sample must publish coherently" );

	const std::uint32_t oldGeneration = state.generation;
	GpuFrameTimingCore_Reset( state );
	Check( !state.valid && state.generation == oldGeneration + 1
			&& state.resetCount == 2 && state.resolvedSamples == 1,
		"reset must invalidate while preserving cumulative counters" );
	GpuFrameTimingCore_RecordResolved( state, 1, 21, oldGeneration, 1000, 1 );
	Check( state.droppedSamples == 1 && !state.valid,
		"stale-generation results must be dropped" );
	GpuFrameTimingCore_RecordResolved( state, 1, 22, state.generation, 0, 1 );
	Check( state.droppedSamples == 2 && !state.valid,
		"zero-microsecond results must not become budget samples" );

	Check( GpuFrameTimingCore_TimestampDelta( 100, 180, 64 ) == 80,
		"64-bit timestamp delta mismatch" );
	Check( GpuFrameTimingCore_TimestampDelta( 250, 5, 8 ) == 11,
		"valid-bit timestamp wrap mismatch" );
	Check( GpuFrameTimingCore_TimestampDelta( 1, 2, 0 ) == 0,
		"zero valid bits must reject timestamp math" );
	Check( GpuFrameTimingCore_TicksToMicroseconds( 1500000, 1.0 ) == 1500,
		"timestamp-period conversion mismatch" );
	Check( GpuFrameTimingCore_TicksToMicroseconds( 1, 0.1 ) == 0,
		"sub-half-microsecond duration must round to unavailable" );

	Check( GpuFrameTimingCore_FrameLatency( 10, 14 ) == 4,
		"ordinary frame latency mismatch" );
	Check( GpuFrameTimingCore_FrameLatency( INT_MAX, INT_MIN ) == 1,
		"signed frame-counter wrap must resolve to one frame" );
	Check( GpuFrameTimingCore_FrameLatency( INT_MIN, INT_MAX )
			== std::numeric_limits<std::uint32_t>::max(),
		"wide frame latency must clamp without signed overflow" );

	if ( failures != 0 ) {
		return 1;
	}
	std::printf( "GpuFrameTimingTest: PASS\n" );
	return 0;
}
