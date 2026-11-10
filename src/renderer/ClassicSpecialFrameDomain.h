// Copyright (C) 2026 DarkMatter Productions
//

#ifndef __CLASSIC_SPECIAL_FRAME_DOMAIN_H__
#define __CLASSIC_SPECIAL_FRAME_DOMAIN_H__

#include "ScenePackets.h"

/*
==============================================================================

	Render-demo playback and Raven's special-frame controller cannot be
	classified solely from normal material passes. A demo is an immutable
	session stream that can use an ordinary positive view id, while the Raven
	controller is an RC_DRAW_SPECIAL_EFFECTS command whose depth/color work is
	completed later in the matching world, resolve, and UI paths.

	This domain seals those two command/view islands before either backend uses
	the existing complete executor. It never rewrites a decoder, recorded
	world, special-effect resource, or resolved-target path. A failed record is
	therefore wholly classic; a successful record reports only after the same
	complete executor has finished its source range.

==============================================================================
*/

const int CLASSIC_SPECIAL_FRAME_DOMAIN_MAX_VIEWS = SCENE_PACKET_MAX_SCENES;

enum classicSpecialFrameDomainScope_t {
	CLASSIC_SPECIAL_FRAME_SCOPE_RENDER_DEMO = 0,
	CLASSIC_SPECIAL_FRAME_SCOPE_RAVEN_EFFECTS,
	CLASSIC_SPECIAL_FRAME_SCOPE_COUNT
};

enum classicSpecialFrameDomainFailure_t {
	CLASSIC_SPECIAL_FRAME_FAILURE_NONE = 0,
	CLASSIC_SPECIAL_FRAME_FAILURE_UNAVAILABLE,
	CLASSIC_SPECIAL_FRAME_FAILURE_SCENE_PACKET_OVERFLOW,
	CLASSIC_SPECIAL_FRAME_FAILURE_VIEW_POOL_OVERFLOW,
	CLASSIC_SPECIAL_FRAME_FAILURE_UNSUPPORTED_VIEW,
	CLASSIC_SPECIAL_FRAME_FAILURE_INVALID_SCENE_RANGE,
	CLASSIC_SPECIAL_FRAME_FAILURE_INVALID_PASS_RANGE,
	CLASSIC_SPECIAL_FRAME_FAILURE_SOURCE_PACKET_MISMATCH,
	CLASSIC_SPECIAL_FRAME_FAILURE_RENDER_DEMO_STATE,
	CLASSIC_SPECIAL_FRAME_FAILURE_SPECIAL_EFFECT_STATE,
	CLASSIC_SPECIAL_FRAME_FAILURE_BACKEND_NOT_READY,
	CLASSIC_SPECIAL_FRAME_FAILURE_BACKEND_REJECTED,
	CLASSIC_SPECIAL_FRAME_FAILURE_BACKEND_COVERAGE_MISMATCH,
	CLASSIC_SPECIAL_FRAME_FAILURE_COUNT
};

enum classicSpecialFrameDomainBackend_t {
	CLASSIC_SPECIAL_FRAME_BACKEND_GL = 0,
	CLASSIC_SPECIAL_FRAME_BACKEND_VULKAN,
	CLASSIC_SPECIAL_FRAME_BACKEND_COUNT
};

enum classicSpecialFrameDomainBackendOutcome_t {
	CLASSIC_SPECIAL_FRAME_BACKEND_UNRECORDED = 0,
	CLASSIC_SPECIAL_FRAME_BACKEND_OWNED,
	CLASSIC_SPECIAL_FRAME_BACKEND_FALLBACK
};

typedef struct classicSpecialFrameDomainView_s {
	const viewDef_t					*viewDef;
	classicSpecialFrameDomainScope_t	scope;
	int							scenePacketIndex;
	int							passPacketIndex;
	int							sourceSurfaceCount;
	int							packetDrawCount;
	int							passPacketCount;
	int							renderDemoVersion;
	int							specialEffectsMask;
	bool							ready;
	classicSpecialFrameDomainFailure_t	failure;
	int							failureDetail;
	std::uint64_t					hash;
	classicSpecialFrameDomainBackendOutcome_t	backendOutcome[
		CLASSIC_SPECIAL_FRAME_BACKEND_COUNT ];
	classicSpecialFrameDomainFailure_t	backendFailure[
		CLASSIC_SPECIAL_FRAME_BACKEND_COUNT ];
	int							backendFailureDetail[
		CLASSIC_SPECIAL_FRAME_BACKEND_COUNT ];
	int							backendCoverage[
		CLASSIC_SPECIAL_FRAME_BACKEND_COUNT ];
} classicSpecialFrameDomainView_t;

typedef struct classicSpecialFrameDomainBackendCoverage_s {
	int	ownedViews;
	int	fallbackViews;
	int	ownedSurfaces;
	int	fallbackSurfaces;
	int	coverageMismatches;
	int	duplicateReports;
} classicSpecialFrameDomainBackendCoverage_t;

typedef struct classicSpecialFrameDomainStats_s {
	bool	prepared;
	bool	frameValid;
	bool	overflow;
	int	sourceScenes;
	int	views;
	int	renderDemoViews;
	int	ravenEffectsViews;
	int	readyViews;
	int	fallbackViews;
	int	specialEffectsMask;
	int	failureCounts[ CLASSIC_SPECIAL_FRAME_FAILURE_COUNT ];
	std::uint64_t	hash;
	classicSpecialFrameDomainBackendCoverage_t backend[
		CLASSIC_SPECIAL_FRAME_BACKEND_COUNT ];
	char	status[ 96 ];
} classicSpecialFrameDomainStats_t;

void R_ClassicSpecialFrameDomain_ResetFrame( void );
void R_ClassicSpecialFrameDomain_PrepareFrame( const idScenePacketFrame &packetFrame );
const classicSpecialFrameDomainStats_t &R_ClassicSpecialFrameDomain_Stats( void );
const classicSpecialFrameDomainView_t *R_ClassicSpecialFrameDomain_FindRenderDemoView(
	const viewDef_t *viewDef );
const classicSpecialFrameDomainView_t *R_ClassicSpecialFrameDomain_FindRavenEffectsView(
	const viewDef_t *viewDef );
bool R_ClassicSpecialFrameDomain_ReadyForBackend( const viewDef_t *viewDef,
	classicSpecialFrameDomainScope_t scope,
	classicSpecialFrameDomainBackend_t backend );
bool R_ClassicSpecialFrameDomain_RecordOwned( const viewDef_t *viewDef,
	classicSpecialFrameDomainScope_t scope,
	classicSpecialFrameDomainBackend_t backend, int coverage );
void R_ClassicSpecialFrameDomain_RecordBackendFallback( const viewDef_t *viewDef,
	classicSpecialFrameDomainScope_t scope,
	classicSpecialFrameDomainBackend_t backend,
	classicSpecialFrameDomainFailure_t failure, int detail );
void R_ClassicSpecialFrameDomain_FinalizeBackendFrame(
	classicSpecialFrameDomainBackend_t backend );
const char *ClassicSpecialFrameDomainFailure_Name(
	classicSpecialFrameDomainFailure_t failure );
bool RendererClassicSpecialFrameDomain_RunSelfTest( void );

#endif /* !__CLASSIC_SPECIAL_FRAME_DOMAIN_H__ */
