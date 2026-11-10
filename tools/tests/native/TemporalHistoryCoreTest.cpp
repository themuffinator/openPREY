// Copyright (C) 2026 DarkMatter Productions
//

#include "src/renderer/TemporalHistoryCore.h"

#include <cstdio>

static int failures = 0;

static void Check( bool condition, const char *message ) {
	if ( condition ) {
		return;
	}
	std::fprintf( stderr, "TemporalHistoryCoreTest: %s\n", message );
	failures++;
}

static temporalCameraState_t Camera( int frameNumber ) {
	temporalCameraState_t state = {};
	state.valid = true;
	state.viewIdentity = UINT64_C( 0x1234 );
	state.historyGeneration = 7;
	state.frameNumber = frameNumber;
	state.renderTimeMsec = frameNumber * 16;
	state.outputWidth = 1920;
	state.outputHeight = 1080;
	state.sceneWidth = 1440;
	state.sceneHeight = 808;
	state.viewAxis[0] = 1.0f;
	state.viewAxis[4] = 1.0f;
	state.viewAxis[8] = 1.0f;
	state.fovX = 90.0f;
	state.fovY = 60.0f;
	return state;
}

int main() {
	const temporalJitterSample_t jitter0 = TemporalHistoryCore_Jitter( 0 );
	const temporalJitterSample_t jitter8 = TemporalHistoryCore_Jitter( 8 );
	Check( jitter0.x == jitter8.x && jitter0.y == jitter8.y,
		"the jitter sequence must repeat exactly after eight frames" );
	for ( std::uint32_t i = 0; i < 8; ++i ) {
		const temporalJitterSample_t sample = TemporalHistoryCore_Jitter( i );
		Check( sample.x >= -0.5f && sample.x <= 0.5f
				&& sample.y >= -0.5f && sample.y <= 0.5f,
			"jitter must remain inside one pixel" );
	}

	const temporalCameraPolicy_t policy = TemporalHistoryCore_DefaultCameraPolicy();
	temporalCameraState_t previous = Camera( 10 );
	temporalCameraState_t current = Camera( 11 );
	Check( TemporalHistoryCore_ValidateCameraHistory( current, previous, policy )
			== TEMPORAL_HISTORY_RESET_NONE,
		"ordinary adjacent camera samples must retain history" );
	current.renderTimeMsec = previous.renderTimeMsec;
	Check( TemporalHistoryCore_ValidateCameraHistory( current, previous, policy )
			== TEMPORAL_HISTORY_RESET_NONE,
		"high-refresh presentation frames may share one simulation time" );

	previous.valid = false;
	Check( TemporalHistoryCore_ValidateCameraHistory( current, previous, policy )
			== TEMPORAL_HISTORY_RESET_FIRST_SAMPLE,
		"the first camera sample must reject uninitialized history" );
	previous = Camera( 10 );
	current.historyGeneration++;
	Check( TemporalHistoryCore_ValidateCameraHistory( current, previous, policy )
			== TEMPORAL_HISTORY_RESET_GENERATION,
		"a generation change must reject stale image history" );
	current = Camera( 11 );
	current.sceneWidth = 1280;
	Check( TemporalHistoryCore_ValidateCameraHistory( current, previous, policy )
			== TEMPORAL_HISTORY_RESET_NONE,
		"a scene-extent transition must retain native-resolution history" );
	current = Camera( 11 );
	current.outputWidth = 2560;
	Check( TemporalHistoryCore_ValidateCameraHistory( current, previous, policy )
			== TEMPORAL_HISTORY_RESET_OUTPUT_EXTENT,
		"a native output-extent transition must reject image history" );
	current = Camera( 11 );
	current.viewOrigin[0] = 513.0f;
	Check( TemporalHistoryCore_ValidateCameraHistory( current, previous, policy )
			== TEMPORAL_HISTORY_RESET_CAMERA_TRANSLATION,
		"a teleport must reset history" );
	current = Camera( 11 );
	current.viewAxis[0] = 0.0f;
	current.viewAxis[1] = 1.0f;
	Check( TemporalHistoryCore_ValidateCameraHistory( current, previous, policy )
			== TEMPORAL_HISTORY_RESET_CAMERA_ROTATION,
		"a hard camera cut must reset history" );
	current = Camera( 11 );
	current.fovX += 1.0f;
	Check( TemporalHistoryCore_ValidateCameraHistory( current, previous, policy )
			== TEMPORAL_HISTORY_RESET_PROJECTION,
		"an authored projection discontinuity must reset history" );

	temporalMotionInput_t input = {};
	temporalMotionOwnership_t ownership = TemporalHistoryCore_ClassifyMotion( input );
	Check( ownership.domain == TEMPORAL_MOTION_DOMAIN_STATIC_WORLD
			&& ownership.source == TEMPORAL_MOTION_SOURCE_CAMERA_DEPTH,
		"static world motion must be reconstructed from depth" );

	input = {};
	input.hasEntity = true;
	input.hasPreviousTransform = true;
	ownership = TemporalHistoryCore_ClassifyMotion( input );
	Check( ownership.domain == TEMPORAL_MOTION_DOMAIN_RIGID
			&& ownership.source == TEMPORAL_MOTION_SOURCE_RIGID_TRANSFORM
			&& ( ownership.flags & TEMPORAL_MOTION_OWNERSHIP_HAS_PREVIOUS_TRANSFORM ) != 0,
		"rigid motion must own a stable previous transform" );

	input = {};
	input.skinned = true;
	ownership = TemporalHistoryCore_ClassifyMotion( input );
	Check( ownership.domain == TEMPORAL_MOTION_DOMAIN_SKINNED
			&& ownership.source == TEMPORAL_MOTION_SOURCE_CAMERA_DEPTH
			&& ( ownership.flags & TEMPORAL_MOTION_OWNERSHIP_REACTIVE ) != 0,
		"skinned geometry without a prior palette must fail safe to reactive history" );
	input.hasPreviousSkinningPalette = true;
	ownership = TemporalHistoryCore_ClassifyMotion( input );
	Check( ownership.source == TEMPORAL_MOTION_SOURCE_SKINNED_PALETTE
			&& ( ownership.flags & TEMPORAL_MOTION_OWNERSHIP_REACTIVE ) == 0,
		"skinned geometry with prior joints must own palette motion" );

	input = {};
	input.particle = true;
	ownership = TemporalHistoryCore_ClassifyMotion( input );
	Check( ownership.domain == TEMPORAL_MOTION_DOMAIN_PARTICLE
			&& ( ownership.flags & TEMPORAL_MOTION_OWNERSHIP_REACTIVE ) != 0,
		"particles must explicitly reject stale history" );
	input = {};
	input.deform = true;
	ownership = TemporalHistoryCore_ClassifyMotion( input );
	Check( ownership.domain == TEMPORAL_MOTION_DOMAIN_DEFORM
			&& ( ownership.flags & TEMPORAL_MOTION_OWNERSHIP_REACTIVE ) != 0,
		"deforms without prior vertices must explicitly reject stale history" );
	input = {};
	input.subview = true;
	ownership = TemporalHistoryCore_ClassifyMotion( input );
	Check( ownership.domain == TEMPORAL_MOTION_DOMAIN_SUBVIEW
			&& ownership.source == TEMPORAL_MOTION_SOURCE_INDEPENDENT_VIEW
			&& ( ownership.flags & TEMPORAL_MOTION_OWNERSHIP_SEPARATE_HISTORY ) != 0,
		"subviews must never borrow their parent history" );
	input = {};
	input.inWorldGui = true;
	ownership = TemporalHistoryCore_ClassifyMotion( input );
	Check( ownership.domain == TEMPORAL_MOTION_DOMAIN_IN_WORLD_GUI
			&& ( ownership.flags & TEMPORAL_MOTION_OWNERSHIP_REACTIVE ) != 0,
		"in-world GUI must remain reactive" );
	input = {};
	input.viewModel = true;
	input.hasPreviousTransform = true;
	ownership = TemporalHistoryCore_ClassifyMotion( input );
	Check( ownership.domain == TEMPORAL_MOTION_DOMAIN_VIEW_MODEL
			&& ( ownership.flags & TEMPORAL_MOTION_OWNERSHIP_DEPTH_HACK ) != 0,
		"view models must preserve their depth-hack ownership" );

	temporalViewMotionPolicy_t motionPolicy =
		TemporalHistoryCore_BeginViewMotionPolicy();
	input = {};
	input.hasEntity = true;
	input.hasPreviousTransform = true;
	ownership = TemporalHistoryCore_ClassifyMotion( input );
	const unsigned int rigidDomain = TemporalHistoryCore_MotionDomainBit(
		TEMPORAL_MOTION_DOMAIN_RIGID );
	TemporalHistoryCore_AddMotionOwnership( motionPolicy, ownership,
		rigidDomain, 0.10f, 0.10f, 0.20f, 0.20f );
	Check( motionPolicy.exactMotionDomainMask == rigidDomain
			&& motionPolicy.reactiveRegionCount == 0,
		"a backend with exact rigid vectors must retain history outside explicit reactive flags" );

	motionPolicy = TemporalHistoryCore_BeginViewMotionPolicy();
	TemporalHistoryCore_AddMotionOwnership( motionPolicy, ownership, 0u,
		0.10f, 0.10f, 0.20f, 0.20f );
	Check( motionPolicy.reactiveDomainMask == rigidDomain
			&& motionPolicy.reactiveRegionCount == 1,
		"a backend without rigid vectors must reject history over the rigid packet scissor" );

	input = {};
	input.skinned = true;
	ownership = TemporalHistoryCore_ClassifyMotion( input );
	TemporalHistoryCore_AddMotionOwnership( motionPolicy, ownership, 0u,
		0.70f, 0.70f, 0.80f, 0.80f );
	input = {};
	input.particle = true;
	ownership = TemporalHistoryCore_ClassifyMotion( input );
	TemporalHistoryCore_AddMotionOwnership( motionPolicy, ownership, 0u,
		0.40f, 0.40f, 0.50f, 0.50f );
	Check( motionPolicy.reactiveRegionCount == 2
			&& motionPolicy.reactiveRegionsMerged,
		"more than two reactive islands must merge conservatively into the fixed policy budget" );
	const unsigned int expectedReactiveDomains = rigidDomain
		| TemporalHistoryCore_MotionDomainBit( TEMPORAL_MOTION_DOMAIN_SKINNED )
		| TemporalHistoryCore_MotionDomainBit( TEMPORAL_MOTION_DOMAIN_PARTICLE );
	Check( motionPolicy.reactiveDomainMask == expectedReactiveDomains,
		"every accumulated unsupported motion domain must remain visible to the backend" );

	motionPolicy = TemporalHistoryCore_BeginViewMotionPolicy();
	TemporalHistoryCore_AddMotionOwnership( motionPolicy, ownership, 0u,
		0.5f, 0.5f, 0.5f, 0.5f );
	Check( motionPolicy.reactiveRegionCount == 1
			&& motionPolicy.reactiveRegions[0].x1 == 0.0f
			&& motionPolicy.reactiveRegions[0].y1 == 0.0f
			&& motionPolicy.reactiveRegions[0].x2 == 1.0f
			&& motionPolicy.reactiveRegions[0].y2 == 1.0f,
		"a missing packet scissor must fail safe to full-frame history rejection" );

	std::uint64_t identityA = TemporalHistoryCore_BeginIdentity();
	identityA = TemporalHistoryCore_MixIdentity( identityA, 1 );
	identityA = TemporalHistoryCore_MixIdentity( identityA, 2 );
	std::uint64_t identityB = TemporalHistoryCore_BeginIdentity();
	identityB = TemporalHistoryCore_MixIdentity( identityB, 1 );
	identityB = TemporalHistoryCore_MixIdentity( identityB, 2 );
	Check( identityA != 0 && identityA == identityB,
		"view identity hashing must be deterministic" );

	if ( failures != 0 ) {
		return 1;
	}
	std::printf( "TemporalHistoryCoreTest: PASS\n" );
	return 0;
}
