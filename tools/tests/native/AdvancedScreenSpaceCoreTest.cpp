// Copyright (C) 2026 DarkMatter Productions
//

#include "src/renderer/AdvancedScreenSpaceCore.h"

#include <cstdio>
#include <limits>

static int failures = 0;

static void Check( bool condition, const char *message ) {
	if ( condition ) {
		return;
	}
	std::fprintf( stderr, "AdvancedScreenSpaceCoreTest: %s\n", message );
	failures++;
}

int main() {
	advancedScreenSpaceConfig_t config = AdvancedScreenSpaceCore_Build(
		true, true, true, true, 0.0005f, 4096.0f, 12,
		0.4f, 768.0f, 10, 0.3f );
	Check( config.effectMask == 7u,
		"independent leaves must publish one combined bounded mask" );
	Check( config.froxelSlices == 12 && config.ssrSteps == 10,
		"valid work bounds must be retained" );
	Check( AdvancedScreenSpaceCore_Requested( config ),
		"a non-empty feature mask must request the shared presentation tail" );

	float packed[8] = {};
	AdvancedScreenSpaceCore_Pack( config, packed );
	Check( packed[0] == 7.0f && packed[1] == 0.0005f
		&& packed[2] == 4096.0f && packed[3] == 12.0f
		&& packed[4] == 0.4f && packed[5] == 768.0f
		&& packed[6] == 10.0f && packed[7] == 0.3f,
		"the GL/Vulkan eight-float packet must be stable" );

	config = AdvancedScreenSpaceCore_Build(
		true, true, true, true,
		std::numeric_limits<float>::quiet_NaN(), 1.0e9f, 999,
		std::numeric_limits<float>::infinity(), -4.0f, -1,
		std::numeric_limits<float>::quiet_NaN() );
	Check( config.froxelDensity == 0.00012f
		&& config.froxelMaxDistance == 8192.0f
		&& config.froxelSlices == ADVANCED_SCREEN_SPACE_FROXEL_MAX_SLICES,
		"froxel tuning must reject non-finite input and remain bounded" );
	Check( config.ssrIntensity == 0.35f && config.ssrMaxDistance == 32.0f
		&& config.ssrSteps == 4
		&& config.ssrSteps <= ADVANCED_SCREEN_SPACE_SSR_MAX_STEPS
		&& config.ssgiIntensity == 0.25f,
		"SSR and SSGI tuning must reject malformed input and remain bounded" );

	config = AdvancedScreenSpaceCore_Build(
		false, true, true, true, 0.01f, 8192.0f, 16,
		1.0f, 2048.0f, 16, 1.0f );
	AdvancedScreenSpaceCore_Pack( config, packed );
	Check( config.effectMask == 0u && !AdvancedScreenSpaceCore_Requested( config ),
		"the master rollback must publish no screen-space work" );
	Check( packed[0] == 0.0f && packed[1] == 0.0f && packed[7] == 0.0f,
		"the master rollback packet must be exactly zero-initialized" );

	config = AdvancedScreenSpaceCore_Build(
		true, false, false, false, 0.01f, 8192.0f, 16,
		1.0f, 2048.0f, 16, 1.0f );
	AdvancedScreenSpaceCore_Pack( config, packed );
	bool allZero = true;
	for ( int i = 0; i < 8; ++i ) {
		allZero = allZero && packed[i] == 0.0f;
	}
	Check( allZero,
		"disabled leaves must ignore dormant tuning and publish a canonical zero packet" );

	if ( failures != 0 ) {
		return 1;
	}
	std::printf( "AdvancedScreenSpaceCoreTest: PASS\n" );
	return 0;
}
