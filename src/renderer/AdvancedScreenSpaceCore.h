// Copyright (C) 2026 DarkMatter Productions
//


#ifndef __ADVANCED_SCREEN_SPACE_CORE_H__
#define __ADVANCED_SCREEN_SPACE_CORE_H__

#include <cmath>

/*
===============================================================================

	Bounded, device-independent admission for the optional screen-space
	advanced-lighting tail.  The packed eight-float contract deliberately fits
	the established OpenGL uniform path and the unused w components of Vulkan's
	256-byte temporal resolve block.

	All leaves are additionally controlled by the Milestone-F master.  Invalid
	or non-finite tuning input is clamped to a conservative value, and disabling
	the master publishes an exact zero-feature packet.

===============================================================================
*/

const int ADVANCED_SCREEN_SPACE_FROXEL_MAX_SLICES = 16;
const int ADVANCED_SCREEN_SPACE_SSR_MAX_STEPS = 16;
const int ADVANCED_SCREEN_SPACE_SSGI_TAPS = 8;

typedef enum advancedScreenSpaceEffectBits_e {
	ADVANCED_SCREEN_SPACE_EFFECT_NONE = 0,
	ADVANCED_SCREEN_SPACE_EFFECT_FROXEL = 1 << 0,
	ADVANCED_SCREEN_SPACE_EFFECT_SSR = 1 << 1,
	ADVANCED_SCREEN_SPACE_EFFECT_SSGI = 1 << 2
} advancedScreenSpaceEffectBits_t;

typedef struct advancedScreenSpaceConfig_s {
	unsigned int	effectMask;
	float		froxelDensity;
	float		froxelMaxDistance;
	int		froxelSlices;
	float		ssrIntensity;
	float		ssrMaxDistance;
	int		ssrSteps;
	float		ssgiIntensity;
} advancedScreenSpaceConfig_t;

inline float AdvancedScreenSpaceCore_ClampFinite( float value,
		float minimum, float maximum, float fallback ) {
	if ( !std::isfinite( value ) ) {
		value = fallback;
	}
	return value < minimum ? minimum : ( value > maximum ? maximum : value );
}

inline int AdvancedScreenSpaceCore_ClampInt( int value,
		int minimum, int maximum ) {
	return value < minimum ? minimum : ( value > maximum ? maximum : value );
}

inline advancedScreenSpaceConfig_t AdvancedScreenSpaceCore_Build(
		bool masterEnabled, bool froxelEnabled, bool ssrEnabled,
		bool ssgiEnabled, float froxelDensity, float froxelMaxDistance,
		int froxelSlices, float ssrIntensity, float ssrMaxDistance,
		int ssrSteps, float ssgiIntensity ) {
	advancedScreenSpaceConfig_t config = {};
	if ( !masterEnabled ) {
		return config;
	}
	if ( froxelEnabled ) {
		config.effectMask |= ADVANCED_SCREEN_SPACE_EFFECT_FROXEL;
		config.froxelDensity = AdvancedScreenSpaceCore_ClampFinite(
			froxelDensity, 0.00001f, 0.01f, 0.00012f );
		config.froxelMaxDistance = AdvancedScreenSpaceCore_ClampFinite(
			froxelMaxDistance, 64.0f, 8192.0f, 2048.0f );
		config.froxelSlices = AdvancedScreenSpaceCore_ClampInt(
			froxelSlices, 4, ADVANCED_SCREEN_SPACE_FROXEL_MAX_SLICES );
	}
	if ( ssrEnabled ) {
		config.effectMask |= ADVANCED_SCREEN_SPACE_EFFECT_SSR;
		config.ssrIntensity = AdvancedScreenSpaceCore_ClampFinite(
			ssrIntensity, 0.0f, 1.0f, 0.35f );
		config.ssrMaxDistance = AdvancedScreenSpaceCore_ClampFinite(
			ssrMaxDistance, 32.0f, 2048.0f, 512.0f );
		config.ssrSteps = AdvancedScreenSpaceCore_ClampInt(
			ssrSteps, 4, ADVANCED_SCREEN_SPACE_SSR_MAX_STEPS );
	}
	if ( ssgiEnabled ) {
		config.effectMask |= ADVANCED_SCREEN_SPACE_EFFECT_SSGI;
		config.ssgiIntensity = AdvancedScreenSpaceCore_ClampFinite(
			ssgiIntensity, 0.0f, 1.0f, 0.25f );
	}
	return config;
}

inline bool AdvancedScreenSpaceCore_Requested(
		const advancedScreenSpaceConfig_t &config ) {
	return config.effectMask != ADVANCED_SCREEN_SPACE_EFFECT_NONE;
}

// Layout: mask, froxel density/distance/slices, SSR intensity/distance/steps,
// SSGI intensity.  Keep this stable across both native backends.
inline void AdvancedScreenSpaceCore_Pack(
		const advancedScreenSpaceConfig_t &config, float packed[8] ) {
	packed[0] = static_cast<float>( config.effectMask );
	packed[1] = config.froxelDensity;
	packed[2] = config.froxelMaxDistance;
	packed[3] = static_cast<float>( config.froxelSlices );
	packed[4] = config.ssrIntensity;
	packed[5] = config.ssrMaxDistance;
	packed[6] = static_cast<float>( config.ssrSteps );
	packed[7] = config.ssgiIntensity;
}

#endif /* !__ADVANCED_SCREEN_SPACE_CORE_H__ */
