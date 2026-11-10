// Copyright (C) 2026 DarkMatter Productions
//

#ifndef __GPU_FRAME_TIMING_CORE_H__
#define __GPU_FRAME_TIMING_CORE_H__

#include <cstdint>
#include <limits>

// Renderer-API-independent state and timestamp math. Keeping this header free
// of GL/Vulkan/idlib types lets the native test exercise wrap, generation, and
// counter behavior without a graphics device.
typedef struct gpuFrameTimingCoreState_s {
	bool			supported;
	bool			valid;
	int			backend;
	int			frameNumber;
	std::uint32_t	generation;
	std::uint32_t	latencyFrames;
	std::uint64_t	elapsedMicroseconds;
	std::uint64_t	resolvedSamples;
	std::uint64_t	unavailableSamples;
	std::uint64_t	droppedSamples;
	std::uint64_t	resetCount;
} gpuFrameTimingCoreState_t;

inline void GpuFrameTimingCore_Initialize( gpuFrameTimingCoreState_t &state ) {
	state.supported = false;
	state.valid = false;
	state.backend = 0;
	state.frameNumber = -1;
	state.generation = 0;
	state.latencyFrames = 0;
	state.elapsedMicroseconds = 0;
	state.resolvedSamples = 0;
	state.unavailableSamples = 0;
	state.droppedSamples = 0;
	state.resetCount = 0;
}

inline void GpuFrameTimingCore_Reset( gpuFrameTimingCoreState_t &state ) {
	state.valid = false;
	state.frameNumber = -1;
	state.latencyFrames = 0;
	state.elapsedMicroseconds = 0;
	state.generation++;
	state.resetCount++;
}

inline void GpuFrameTimingCore_SetBackend( gpuFrameTimingCoreState_t &state,
		int backend, bool supported ) {
	if ( state.backend != backend || state.supported != supported ) {
		state.backend = backend;
		state.supported = supported;
		GpuFrameTimingCore_Reset( state );
	}
}

inline void GpuFrameTimingCore_RecordResolved( gpuFrameTimingCoreState_t &state,
		int backend, int frameNumber, std::uint32_t generation,
		std::uint64_t elapsedMicroseconds, std::uint32_t latencyFrames ) {
	if ( !state.supported || state.backend != backend || state.generation != generation
			|| elapsedMicroseconds == 0 ) {
		state.droppedSamples++;
		return;
	}
	state.valid = true;
	state.frameNumber = frameNumber;
	state.latencyFrames = latencyFrames;
	state.elapsedMicroseconds = elapsedMicroseconds;
	state.resolvedSamples++;
}

inline std::uint64_t GpuFrameTimingCore_TimestampDelta( std::uint64_t begin,
		std::uint64_t end, std::uint32_t validBits ) {
	if ( validBits == 0 ) {
		return 0;
	}
	if ( validBits >= 64 ) {
		return end - begin;
	}
	const std::uint64_t mask = ( std::uint64_t( 1 ) << validBits ) - 1;
	return ( end - begin ) & mask;
}

inline std::uint64_t GpuFrameTimingCore_TicksToMicroseconds( std::uint64_t ticks,
		double nanosecondsPerTick ) {
	if ( nanosecondsPerTick <= 0.0 ) {
		return 0;
	}
	const long double microseconds =
		static_cast<long double>( ticks ) * static_cast<long double>( nanosecondsPerTick ) / 1000.0L;
	if ( microseconds >= static_cast<long double>( ( std::numeric_limits<std::uint64_t>::max )() ) ) {
		return ( std::numeric_limits<std::uint64_t>::max )();
	}
	return static_cast<std::uint64_t>( microseconds + 0.5L );
}

inline std::uint32_t GpuFrameTimingCore_FrameLatency( int sampleFrame, int currentFrame ) {
	if ( sampleFrame == -1 || currentFrame == sampleFrame ) {
		return 0;
	}
	std::int64_t signedLatency = static_cast<std::int64_t>( currentFrame )
		- static_cast<std::int64_t>( sampleFrame );
	if ( signedLatency < 0 ) {
		// Renderer frame numbers are exposed as signed ints for legacy ABI
		// compatibility. Interpret a sign-boundary crossing as one 32-bit wrap.
		signedLatency += ( std::int64_t( 1 ) << 32 );
	}
	const std::uint64_t latency = static_cast<std::uint64_t>( signedLatency );
	return latency > ( std::numeric_limits<std::uint32_t>::max )()
		? ( std::numeric_limits<std::uint32_t>::max )()
		: static_cast<std::uint32_t>( latency );
}

#endif /* !__GPU_FRAME_TIMING_CORE_H__ */
