// Copyright (C) 2026 DarkMatter Productions
//

#include "src/renderer/AdvancedLightingCore.h"

#include <cstdio>
#include <limits>

static int failures = 0;

static void Check( bool condition, const char *message ) {
	if ( condition ) {
		return;
	}
	std::fprintf( stderr, "AdvancedLightingCoreTest: %s\n", message );
	failures++;
}

static advancedLightingVolume_t Volume( std::uint32_t generation, int stableId ) {
	advancedLightingVolume_t volume = {};
	volume.origin[0] = 1.0f;
	volume.origin[1] = 2.0f;
	volume.origin[2] = 3.0f;
	volume.extents[0] = 64.0f;
	volume.extents[1] = 32.0f;
	volume.extents[2] = 16.0f;
	volume.generation = generation;
	volume.stableId = stableId;
	return volume;
}

int main() {
	advancedLightingTransaction_t transaction;
	AdvancedLightingCore_Begin( transaction, true, 7, 2, 1, 4 );
	Check( AdvancedLightingCore_Admit( transaction,
		ADVANCED_LIGHTING_RECORD_PROBE, Volume( 7, 11 ) ),
		"a current finite probe must be admitted" );
	Check( AdvancedLightingCore_Admit( transaction,
		ADVANCED_LIGHTING_RECORD_DECAL, Volume( 7, 21 ) ),
		"a current finite decal must be admitted" );
	Check( AdvancedLightingCore_AddReference( transaction,
		ADVANCED_LIGHTING_RECORD_PROBE )
		&& AdvancedLightingCore_AddReference( transaction,
			ADVANCED_LIGHTING_RECORD_DECAL ),
		"bounded probe/decal references must be admitted" );
	Check( AdvancedLightingCore_Seal( transaction, true )
		&& transaction.complete && transaction.sealed,
		"a lossless resource-complete transaction must seal" );
	Check( !AdvancedLightingCore_Admit( transaction,
		ADVANCED_LIGHTING_RECORD_PROBE, Volume( 7, 12 ) ),
		"sealed transactions must be immutable" );

	AdvancedLightingCore_Begin( transaction, true, 9, 1, 1, 1 );
	Check( !AdvancedLightingCore_Admit( transaction,
		ADVANCED_LIGHTING_RECORD_PROBE, Volume( 8, 1 ) )
		&& transaction.firstReject == ADVANCED_LIGHTING_REJECT_INVALID_GENERATION,
		"a stale generation must poison the complete transaction" );
	advancedLightingVolume_t malformed = Volume( 9, 2 );
	malformed.extents[1] = std::numeric_limits<float>::quiet_NaN();
	Check( !AdvancedLightingCore_Admit( transaction,
		ADVANCED_LIGHTING_RECORD_DECAL, malformed ),
		"non-finite volumes must fail closed" );
	Check( !AdvancedLightingCore_Seal( transaction, true )
		&& !transaction.complete,
		"a rejected record must prevent partial publication" );

	AdvancedLightingCore_Begin( transaction, true, 10, 1, 1, 1 );
	Check( !AdvancedLightingCore_Admit( transaction,
		static_cast<advancedLightingRecordKind_t>( 99 ), Volume( 10, 1 ) )
		&& transaction.firstReject == ADVANCED_LIGHTING_REJECT_INVALID_KIND,
		"an unknown record kind must fail closed" );

	AdvancedLightingCore_Begin( transaction, true, 3, 1, 1, 1 );
	Check( AdvancedLightingCore_Admit( transaction,
		ADVANCED_LIGHTING_RECORD_PROBE, Volume( 3, 1 ) )
		&& !AdvancedLightingCore_Admit( transaction,
			ADVANCED_LIGHTING_RECORD_PROBE, Volume( 3, 2 ) )
		&& transaction.firstReject == ADVANCED_LIGHTING_REJECT_CAPACITY,
		"record overflow must be explicit and atomic" );
	Check( AdvancedLightingCore_AddReference( transaction,
		ADVANCED_LIGHTING_RECORD_PROBE )
		&& !AdvancedLightingCore_AddReference( transaction,
			ADVANCED_LIGHTING_RECORD_DECAL ),
		"reference overflow must be bounded" );

	advancedLightingProbeCandidate_t selected[ADVANCED_LIGHTING_PROBES_PER_CLUSTER] = {};
	for ( int i = 0; i < ADVANCED_LIGHTING_PROBES_PER_CLUSTER; ++i ) {
		selected[i].probeIndex = -1;
		selected[i].stableId = -1;
	}
	const advancedLightingProbeCandidate_t candidates[] = {
		{ 0, 2, 20, 0.8f },
		{ 1, 3, 40, 0.2f },
		{ 2, 3, 10, 0.9f },
		{ 3, 3, 5, 0.9f }
	};
	for ( unsigned int i = 0; i < sizeof( candidates ) / sizeof( candidates[0] ); ++i ) {
		AdvancedLightingCore_SelectProbe( selected, candidates[i] );
	}
	Check( selected[0].probeIndex == 3 && selected[1].probeIndex == 2,
		"priority, weight, and stable identity must order probe selection deterministically" );

	for ( int i = 0; i < ADVANCED_LIGHTING_PROBES_PER_CLUSTER; ++i ) {
		selected[i].probeIndex = -1;
		selected[i].stableId = -1;
	}
	const advancedLightingProbeCandidate_t conservativeEdge = { 4, -1, 1, 0.000256f };
	const advancedLightingProbeCandidate_t positiveLowPriority = { 5, 0, 2, 0.1f };
	const advancedLightingProbeCandidate_t positiveSecond = { 6, 0, 3, 0.05f };
	AdvancedLightingCore_SelectProbe( selected, conservativeEdge );
	AdvancedLightingCore_SelectProbe( selected, positiveLowPriority );
	AdvancedLightingCore_SelectProbe( selected, positiveSecond );
	Check( selected[0].probeIndex == 5 && selected[1].probeIndex == 6,
		"conservative edge references must not crowd positive probe contributors" );

	const advancedLightingVolume_t volume = Volume( 1, 1 );
	const float center[3] = { 1.0f, 2.0f, 3.0f };
	const float edge[3] = { 65.0f, 2.0f, 3.0f };
	const float blend[3] = { 49.0f, 2.0f, 3.0f };
	Check( AdvancedLightingCore_ProbeWeight( volume, center, 16.0f ) == 1.0f,
		"probe center must have full weight" );
	Check( AdvancedLightingCore_ProbeWeight( volume, edge, 16.0f ) == 0.0f,
		"probe boundary must have zero weight" );
	Check( AdvancedLightingCore_ProbeWeight( volume, blend, 32.0f ) > 0.0f
		&& AdvancedLightingCore_ProbeWeight( volume, blend, 32.0f ) < 1.0f,
		"probe blend band must be continuous" );

	const float sphereOrigin[3] = { 0.0f, 0.0f, 0.0f };
	const float sphereCenter[3] = { 0.0f, 0.0f, 0.0f };
	const float sphereBlend[3] = { 7.0f, 0.0f, 0.0f };
	const float sphereEdge[3] = { 8.0f, 0.0f, 0.0f };
	Check( AdvancedLightingCore_SphericalProbeWeight(
		sphereOrigin, 8.0f, sphereCenter, 2.0f ) == 1.0f,
		"spherical probe center must have full weight" );
	Check( AdvancedLightingCore_SphericalProbeWeight(
		sphereOrigin, 8.0f, sphereBlend, 2.0f ) == 0.5f,
		"spherical probe shell must preserve its authored blend width" );
	Check( AdvancedLightingCore_SphericalProbeWeight(
		sphereOrigin, 8.0f, sphereEdge, 2.0f ) == 0.0f,
		"spherical probe boundary must fail closed" );
	Check( AdvancedLightingCore_SphericalProbeWeight(
		sphereOrigin, 8.0f, sphereCenter,
		std::numeric_limits<float>::quiet_NaN() ) == 0.0f,
		"malformed spherical blend distance must fail closed" );

	AdvancedLightingCore_Begin( transaction, false, 1, 1, 1, 1 );
	Check( !AdvancedLightingCore_Seal( transaction, true )
		&& transaction.firstReject == ADVANCED_LIGHTING_REJECT_DISABLED,
		"the default-off master gate must publish no records" );

	if ( failures != 0 ) {
		return 1;
	}
	std::printf( "AdvancedLightingCoreTest: PASS\n" );
	return 0;
}
