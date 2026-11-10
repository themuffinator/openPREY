// Copyright (C) 2026 DarkMatter Productions
//

#ifndef __CLASSIC_CINEMATIC_POST_DOMAIN_H__
#define __CLASSIC_CINEMATIC_POST_DOMAIN_H__

#include "ScenePackets.h"

/*
==============================================================================

	Shared transaction boundary for the two dynamic classic-frame islands that
	cannot use the static fixed-material pass pools:

	* root 2D command views containing one or more videoMap/soundMap stages;
	* the ordered SS_POST_PROCESS range in an ordinary root 3D view.

	Cinematics retain the established decoder, scratch-image upload, and exact
	audio/video clock. Authored post stages retain their established feedback
	capture and program-stage dispatch. The domain instead seals the complete
	source range, packet correspondence, view identity, timing, and ordering
	before either backend enters that mature dynamic-stage adapter. A rejected
	transaction is wholly classic; a committed transaction never mixes a partial
	shared range with the ordinary walker.

==============================================================================
*/

const int CLASSIC_CINEMATIC_POST_DOMAIN_MAX_VIEWS = SCENE_PACKET_MAX_SCENES;

enum classicCinematicPostDomainScope_t {
	CLASSIC_CINEMATIC_POST_SCOPE_ROOT_CINEMATIC = 0,
	CLASSIC_CINEMATIC_POST_SCOPE_AUTHORED_POST,
	CLASSIC_CINEMATIC_POST_SCOPE_COUNT
};

enum classicCinematicPostDomainFailure_t {
	CLASSIC_CINEMATIC_POST_FAILURE_NONE = 0,
	CLASSIC_CINEMATIC_POST_FAILURE_UNAVAILABLE,
	CLASSIC_CINEMATIC_POST_FAILURE_SCENE_PACKET_OVERFLOW,
	CLASSIC_CINEMATIC_POST_FAILURE_VIEW_POOL_OVERFLOW,
	CLASSIC_CINEMATIC_POST_FAILURE_UNSUPPORTED_VIEW,
	CLASSIC_CINEMATIC_POST_FAILURE_INVALID_SCENE_RANGE,
	CLASSIC_CINEMATIC_POST_FAILURE_INVALID_PASS_RANGE,
	CLASSIC_CINEMATIC_POST_FAILURE_SOURCE_PACKET_MISMATCH,
	CLASSIC_CINEMATIC_POST_FAILURE_INVALID_SOURCE_SURFACE,
	CLASSIC_CINEMATIC_POST_FAILURE_CINEMATIC_CLOCK,
	CLASSIC_CINEMATIC_POST_FAILURE_MISSING_SPECIAL_VIEW,
	CLASSIC_CINEMATIC_POST_FAILURE_SPECIAL_VIEW_TRANSACTION_REJECTED,
	CLASSIC_CINEMATIC_POST_FAILURE_BACKEND_SPECIAL_VIEW_INCOMPLETE,
	CLASSIC_CINEMATIC_POST_FAILURE_BACKEND_NOT_READY,
	CLASSIC_CINEMATIC_POST_FAILURE_BACKEND_REJECTED,
	CLASSIC_CINEMATIC_POST_FAILURE_BACKEND_COVERAGE_MISMATCH,
	CLASSIC_CINEMATIC_POST_FAILURE_COUNT
};

enum classicCinematicPostDomainBackend_t {
	CLASSIC_CINEMATIC_POST_BACKEND_GL = 0,
	CLASSIC_CINEMATIC_POST_BACKEND_VULKAN,
	CLASSIC_CINEMATIC_POST_BACKEND_COUNT
};

enum classicCinematicPostDomainBackendOutcome_t {
	CLASSIC_CINEMATIC_POST_BACKEND_UNRECORDED = 0,
	CLASSIC_CINEMATIC_POST_BACKEND_OWNED,
	CLASSIC_CINEMATIC_POST_BACKEND_FALLBACK
};

typedef struct classicCinematicPostDomainView_s {
	const viewDef_t					*viewDef;
	const viewDef_t *specialRootViewDef;
	int specialRootScenePacketIndex;
	int specialNestingDepth;
	classicCinematicPostDomainScope_t	scope;
	int								scenePacketIndex;
	int									passPacketIndex;
	int									firstSourceSurface;
	int									sourceSurfaceCount;
	int									packetDrawCount;
	int									cinematicStageCount;
	int									currentRenderStageCount;
	int									currentDepthStageCount;
	int									cinematicTimeMilliseconds;
	bool									ready;
	classicCinematicPostDomainFailure_t	failure;
	bool nestedInSpecialView;
	int									failureDetail;
	std::uint64_t						hash;
	classicCinematicPostDomainBackendOutcome_t	backendOutcome[
		CLASSIC_CINEMATIC_POST_BACKEND_COUNT ];
	classicCinematicPostDomainFailure_t	backendFailure[
		CLASSIC_CINEMATIC_POST_BACKEND_COUNT ];
	int									backendFailureDetail[
		CLASSIC_CINEMATIC_POST_BACKEND_COUNT ];
	int									backendDrawnSurfaces[
		CLASSIC_CINEMATIC_POST_BACKEND_COUNT ];
	bool backendCompleted[ CLASSIC_CINEMATIC_POST_BACKEND_COUNT ];
} classicCinematicPostDomainView_t;

typedef struct classicCinematicPostDomainBackendCoverage_s {
	int	ownedViews;
	int	fallbackViews;
	int	ownedSurfaces;
	int	fallbackSurfaces;
	int	coverageMismatches;
	int	duplicateReports;
} classicCinematicPostDomainBackendCoverage_t;

typedef struct classicCinematicPostDomainStats_s {
	bool	prepared;
	bool	frameValid;
	bool	overflow;
	int	sourceScenes;
	int	views;
	int	rootCinematicViews;
	int	authoredPostViews;
	int	nestedSpecialViews;
	int	nestedSpecialTransactions;
	int	nestedCinematicStages;
	int	readyViews;
	int	fallbackViews;
	int	cinematicStages;
	int	currentRenderStages;
	int	currentDepthStages;
	int	failureCounts[ CLASSIC_CINEMATIC_POST_FAILURE_COUNT ];
	std::uint64_t	hash;
	classicCinematicPostDomainBackendCoverage_t backend[
		CLASSIC_CINEMATIC_POST_BACKEND_COUNT ];
	char	status[ 96 ];
} classicCinematicPostDomainStats_t;

void R_ClassicCinematicPostDomain_ResetFrame( void );
void R_ClassicCinematicPostDomain_PrepareFrame( const idScenePacketFrame &packetFrame );
const classicCinematicPostDomainStats_t &R_ClassicCinematicPostDomain_Stats( void );
const classicCinematicPostDomainView_t *R_ClassicCinematicPostDomain_FindRootCinematicView(
	const viewDef_t *viewDef );
const classicCinematicPostDomainView_t *R_ClassicCinematicPostDomain_FindAuthoredPostView(
	const viewDef_t *viewDef );
bool R_ClassicCinematicPostDomain_RecordOwned( const viewDef_t *viewDef,
	classicCinematicPostDomainScope_t scope,
	classicCinematicPostDomainBackend_t backend, int drawnSurfaces );
void R_ClassicCinematicPostDomain_RecordBackendFallback( const viewDef_t *viewDef,
	classicCinematicPostDomainScope_t scope,
	classicCinematicPostDomainBackend_t backend,
	classicCinematicPostDomainFailure_t failure, int detail );
bool R_ClassicCinematicPostDomain_ReadyForBackend( const viewDef_t *viewDef,
	classicCinematicPostDomainScope_t scope,
	classicCinematicPostDomainBackend_t backend );
bool R_ClassicCinematicPostDomain_SubviewTransactionReady(
	const viewDef_t *memberViewDef,
	classicCinematicPostDomainBackend_t backend );
bool R_ClassicCinematicPostDomain_SubviewTransactionCompleted(
	const viewDef_t *memberViewDef,
	classicCinematicPostDomainBackend_t backend );
bool R_ClassicCinematicPostDomain_PublishSubviewTransactionOwned(
	const viewDef_t *memberViewDef,
	classicCinematicPostDomainBackend_t backend );
void R_ClassicCinematicPostDomain_RecordSubviewTransactionFallback(
	const viewDef_t *memberViewDef,
	classicCinematicPostDomainBackend_t backend,
	classicCinematicPostDomainFailure_t failure, int detail );
const char *ClassicCinematicPostDomainFailure_Name(
	classicCinematicPostDomainFailure_t failure );
bool RendererClassicCinematicPostDomain_RunSelfTest( void );

#endif /* !__CLASSIC_CINEMATIC_POST_DOMAIN_H__ */
