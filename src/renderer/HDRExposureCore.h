// Copyright (C) 2026 DarkMatter Productions
#ifndef __HDR_EXPOSURE_CORE_H__
#define __HDR_EXPOSURE_CORE_H__

#include <cmath>

// Dependency-light exposure math. GPU readback ownership/generation checks
// belong to the backend; only a completed, current-generation sample enters here.
struct hdrExposureSettings_t {
	float keyValue;
	float minExposure;
	float maxExposure;
	float brightenSpeed;
	float darkenSpeed;
};

struct hdrExposureState_t {
	bool initialized;
	float exposure;
	float averageLuminance;
	float targetExposure;
	float lastTime;
};

inline void HDRExposure_Reset( hdrExposureState_t &state ) {
	state.initialized = false;
	state.exposure = state.averageLuminance = state.targetExposure = 1.0f;
	state.lastTime = 0.0f;
}

inline float HDRExposure_Clamp( float value, float low, float high ) {
	return value < low ? low : value > high ? high : value;
}

inline bool HDRExposure_Update( hdrExposureState_t &state, float logLuminance,
		float now, const hdrExposureSettings_t &settings ) {
	if ( !std::isfinite( logLuminance ) || !std::isfinite( now )
			|| !std::isfinite( settings.keyValue ) || settings.keyValue <= 0.0f
			|| !std::isfinite( settings.minExposure ) || settings.minExposure <= 0.0f
			|| !std::isfinite( settings.maxExposure ) || settings.maxExposure <= 0.0f
			|| !std::isfinite( settings.brightenSpeed ) || settings.brightenSpeed < 0.0f
			|| !std::isfinite( settings.darkenSpeed ) || settings.darkenSpeed < 0.0f ) {
		return false;
	}
	const float minimum = settings.minExposure < settings.maxExposure ? settings.minExposure : settings.maxExposure;
	const float maximum = settings.minExposure > settings.maxExposure ? settings.minExposure : settings.maxExposure;
	const float luminance = std::exp( HDRExposure_Clamp( logLuminance, -16.0f, 16.0f ) );
	const float target = HDRExposure_Clamp( settings.keyValue / ( luminance > 0.0001f ? luminance : 0.0001f ), minimum, maximum );
	if ( !state.initialized || now < state.lastTime || now - state.lastTime > 1.0f ) {
		state.exposure = target;
		state.initialized = true;
	} else {
		const float speed = target > state.exposure ? settings.brightenSpeed : settings.darkenSpeed;
		const float blend = HDRExposure_Clamp( 1.0f - std::exp( -speed * ( now - state.lastTime ) ), 0.0f, 1.0f );
		state.exposure += ( target - state.exposure ) * blend;
	}
	// Live limit changes must take effect even while adaptation is slow or paused.
	state.exposure = HDRExposure_Clamp( state.exposure, minimum, maximum );
	state.averageLuminance = luminance > 0.0001f ? luminance : 0.0001f;
	state.targetExposure = target;
	state.lastTime = now;
	return true;
}

// Vulkan's compact luminance target is RGBA16F. Decode the first component
// without platform intrinsics; reject infinities and NaNs before adaptation.
inline bool HDRExposure_DecodeHalf( unsigned short bits, float &value ) {
	const int exponent = ( bits >> 10 ) & 31;
	if ( exponent == 31 ) {
		return false;
	}
	const int mantissa = bits & 1023;
	value = exponent == 0 ? std::ldexp( static_cast<float>( mantissa ), -24 )
		: std::ldexp( static_cast<float>( mantissa + 1024 ), exponent - 25 );
	if ( ( bits & 0x8000 ) != 0 ) {
		value = -value;
	}
	return true;
}

#endif
