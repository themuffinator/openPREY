// Copyright (C) 2026 DarkMatter Productions
#include "../../../src/renderer/HDRExposureCore.h"
#include <cstdio>
#include <limits>
#include <cstdlib>

static void Check( bool condition, const char *message ) {
	if ( !condition ) {
		std::fprintf( stderr, "HDR exposure: %s\n", message );
		std::exit( 1 );
	}
}

static bool Near( float a, float b, float tolerance = 0.0001f ) {
	return std::fabs( a - b ) <= tolerance;
}

int main() {
	hdrExposureState_t state;
	HDRExposure_Reset( state );
	hdrExposureSettings_t settings = { 0.18f, 0.25f, 8.0f, 3.0f, 1.5f };
	Check( !state.initialized && state.exposure == 1.0f, "neutral reset" );
	Check( HDRExposure_Update( state, std::log( 0.18f ), 0.0f, settings ) && Near( state.exposure, 1.0f ), "middle gray" );
	const float initial = state.exposure;
	Check( HDRExposure_Update( state, std::log( 4.0f ), 0.25f, settings ), "bright sample accepted" );
	Check( state.targetExposure == 0.25f && state.exposure > 0.25f && state.exposure < initial, "bounded darkening" );
	const float darkened = state.exposure;
	Check( HDRExposure_Update( state, std::log( 0.0001f ), 0.5f, settings ), "dark sample accepted" );
	Check( state.targetExposure == 8.0f && state.exposure > darkened && state.exposure < 8.0f, "bounded brightening" );
	const float oldExposure = state.exposure;
	Check( !HDRExposure_Update( state, std::numeric_limits<float>::quiet_NaN(), 0.6f, settings )
		&& state.exposure == oldExposure, "invalid sample preserves history" );
	Check( !HDRExposure_Update( state, std::numeric_limits<float>::infinity(), 0.6f, settings ), "infinite sample rejected" );
	Check( HDRExposure_Update( state, std::log( 0.18f ), -1.0f, settings ) && Near( state.exposure, 1.0f ), "time rewind resets adaptation" );
	Check( HDRExposure_Update( state, std::log( 0.045f ), 5.0f, settings ) && Near( state.exposure, 4.0f ), "long interruption resets adaptation" );
	settings.minExposure = 8.0f;
	settings.maxExposure = 0.25f;
	Check( HDRExposure_Update( state, -1000.0f, 10.0f, settings ) && state.exposure == 8.0f, "reversed limits and deep dark" );
	Check( HDRExposure_Update( state, 1000.0f, 12.0f, settings ) && state.exposure == 0.25f, "extreme highlight remains finite" );
	settings.minExposure = 0.25f;
	settings.maxExposure = 8.0f;
	float endpoints[ 3 ];
	const int rates[ 3 ] = { 30, 60, 144 };
	for ( int i = 0; i < 3; ++i ) {
		HDRExposure_Reset( state );
		HDRExposure_Update( state, std::log( 0.18f ), 0.0f, settings );
		float previous = state.exposure;
		for ( int frame = 1; frame <= rates[ i ]; ++frame ) {
			Check( HDRExposure_Update( state, std::log( 0.045f ), static_cast<float>( frame ) / rates[ i ], settings ), "frame sample" );
			Check( state.exposure >= previous && state.exposure <= 4.0f, "monotonic adaptation without overshoot" );
			previous = state.exposure;
		}
		endpoints[ i ] = state.exposure;
	}
	Check( Near( endpoints[ 0 ], endpoints[ 1 ] ) && Near( endpoints[ 1 ], endpoints[ 2 ] ), "frame-rate independent adaptation" );
	settings.maxExposure = 2.0f;
	settings.brightenSpeed = settings.darkenSpeed = 0.0f;
	Check( HDRExposure_Update( state, std::log( 0.045f ), state.lastTime, settings )
		&& state.exposure == 2.0f, "live maximum applies with adaptation paused" );
	settings.minExposure = 3.0f;
	settings.maxExposure = 8.0f;
	Check( HDRExposure_Update( state, std::log( 0.18f ), state.lastTime, settings )
		&& state.exposure == 3.0f, "live minimum applies with adaptation paused" );
	float value = 0.0f;
	Check( HDRExposure_DecodeHalf( 0x3c00, value ) && value == 1.0f, "half one" );
	Check( HDRExposure_DecodeHalf( 0xc400, value ) && value == -4.0f, "negative log luminance" );
	Check( HDRExposure_DecodeHalf( 0x0001, value ) && value == std::ldexp( 1.0f, -24 ), "half subnormal" );
	Check( HDRExposure_DecodeHalf( 0x7bff, value ) && value == 65504.0f, "half maximum" );
	Check( !HDRExposure_DecodeHalf( 0x7c00, value ) && !HDRExposure_DecodeHalf( 0x7e00, value ), "half nonfinite rejected" );
	std::puts( "HDRExposureCore: passed" );
	return 0;
}
