// Copyright (C) 2026 DarkMatter Productions
//

#ifndef __CLASSIC_WORLD_AMBIENT_DOMAIN_H__
#define __CLASSIC_WORLD_AMBIENT_DOMAIN_H__

#include "ClassicDeformDomain.h"
#include "MaterialResourceTable.h"

/*
===============================================================================

	Shared whole-view ownership contract for classic fixed-function world
	ambient/material work.

	Preparation is transactional per 3D view. A view is ready only when every
	source surface is classified, the complete ambient packet span matches in
	source order, every required opaque/perforated depth prerequisite is present,
	every authored pass evaluates once, and every generation-scoped texture
	resource resolves. Failed views expose diagnostics but no partial draw/pass
	range. Interaction, shadow, light-grid, fog, deform, subview, GUI, special,
	and post-process islands remain explicit whole-view rollback boundaries.

===============================================================================
*/

const int CLASSIC_WORLD_AMBIENT_DOMAIN_MAX_VIEWS = SCENE_PACKET_MAX_SCENES;
const int CLASSIC_WORLD_AMBIENT_DOMAIN_MAX_DRAWS = SCENE_PACKET_MAX_DRAWS;
const int CLASSIC_WORLD_AMBIENT_DOMAIN_MAX_EVALUATED_PASSES = SCENE_PACKET_MAX_DRAWS * 2;

enum classicWorldAmbientPhase_t {
	CLASSIC_WORLD_AMBIENT_PHASE_PRE_FOG = 0,
	CLASSIC_WORLD_AMBIENT_PHASE_POST_FOG,
	CLASSIC_WORLD_AMBIENT_PHASE_COUNT
};

enum classicWorldAmbientDomainSourceSurface_t {
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_DRAWABLE = 0,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_NOOP_NULL_SURFACE,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_NOOP_MISSING_MATERIAL,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_NOOP_NO_AMBIENT,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_NOOP_EMPTY_GEOMETRY,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_NOT_DRAWN,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_PORTAL_SKY,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_SUPPRESSED_IN_SUBVIEW,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_IN_WORLD_GUI,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_SUBVIEW,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_MISSING_SPACE,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_SYNTHETIC_GUI_SPACE,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_SPECIAL_SURFACE,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_DEFORM,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_SKINNING,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_DEPTH_HACK,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_NEGATIVE_SCALE,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_DECAL,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_POST_PROCESS,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_PLAYER_VISIBILITY,
	CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_COUNT
};

enum classicWorldAmbientDomainFailure_t {
	CLASSIC_WORLD_AMBIENT_FAILURE_NONE = 0,
	CLASSIC_WORLD_AMBIENT_FAILURE_UNAVAILABLE,
	CLASSIC_WORLD_AMBIENT_FAILURE_SCENE_PACKET_OVERFLOW,
	CLASSIC_WORLD_AMBIENT_FAILURE_MATERIAL_TABLE_NOT_PREPARED,
	CLASSIC_WORLD_AMBIENT_FAILURE_MATERIAL_TABLE_OVERFLOW,
	CLASSIC_WORLD_AMBIENT_FAILURE_VIEW_POOL_OVERFLOW,
	CLASSIC_WORLD_AMBIENT_FAILURE_DRAW_POOL_OVERFLOW,
	CLASSIC_WORLD_AMBIENT_FAILURE_EVALUATED_PASS_POOL_OVERFLOW,
	CLASSIC_WORLD_AMBIENT_FAILURE_UNSUPPORTED_VIEW,
	CLASSIC_WORLD_AMBIENT_FAILURE_UNPACKETIZED_VIEW_EFFECT,
	CLASSIC_WORLD_AMBIENT_FAILURE_INVALID_SCENE_RANGE,
	CLASSIC_WORLD_AMBIENT_FAILURE_INVALID_AMBIENT_PASS,
	CLASSIC_WORLD_AMBIENT_FAILURE_FORBIDDEN_PASS,
	CLASSIC_WORLD_AMBIENT_FAILURE_INVALID_DRAW_RANGE,
	CLASSIC_WORLD_AMBIENT_FAILURE_SOURCE_SURFACE_FALLBACK,
	CLASSIC_WORLD_AMBIENT_FAILURE_SOURCE_PACKET_MISMATCH,
	CLASSIC_WORLD_AMBIENT_FAILURE_INVALID_DRAW_PACKET,
	CLASSIC_WORLD_AMBIENT_FAILURE_DEFORM_CONTRACT,
	CLASSIC_WORLD_AMBIENT_FAILURE_MISSING_GEOMETRY_RECORD,
	CLASSIC_WORLD_AMBIENT_FAILURE_MISSING_INSTANCE_RECORD,
	CLASSIC_WORLD_AMBIENT_FAILURE_MISSING_MATERIAL_RECORD,
	CLASSIC_WORLD_AMBIENT_FAILURE_STALE_MATERIAL_RECORD,
	CLASSIC_WORLD_AMBIENT_FAILURE_DEPTH_PREREQUISITE_MISSING,
	CLASSIC_WORLD_AMBIENT_FAILURE_MATERIAL_PASS_INELIGIBLE,
	CLASSIC_WORLD_AMBIENT_FAILURE_MATERIAL_PASS_COPY_FAILED,
	CLASSIC_WORLD_AMBIENT_FAILURE_MATERIAL_PASS_EVALUATION_FAILED,
	CLASSIC_WORLD_AMBIENT_FAILURE_TEXTURE_RESOURCE_UNAVAILABLE,
	CLASSIC_WORLD_AMBIENT_FAILURE_INVALID_DISPOSITION,
	CLASSIC_WORLD_AMBIENT_FAILURE_BACKEND_NOT_READY,
	CLASSIC_WORLD_AMBIENT_FAILURE_BACKEND_COVERAGE_MISMATCH,
	CLASSIC_WORLD_AMBIENT_FAILURE_BACKEND_REJECTED,
	CLASSIC_WORLD_AMBIENT_FAILURE_COUNT
};

enum classicWorldAmbientDomainBackend_t {
	CLASSIC_WORLD_AMBIENT_BACKEND_GL = 0,
	CLASSIC_WORLD_AMBIENT_BACKEND_VULKAN,
	CLASSIC_WORLD_AMBIENT_BACKEND_COUNT
};

enum classicWorldAmbientDomainBackendOutcome_t {
	CLASSIC_WORLD_AMBIENT_BACKEND_UNRECORDED = 0,
	CLASSIC_WORLD_AMBIENT_BACKEND_OWNED,
	CLASSIC_WORLD_AMBIENT_BACKEND_FALLBACK
};

typedef struct classicWorldAmbientDomainBackendCoverage_s {
	std::uint64_t	ownedViewMask;
	std::uint64_t	fallbackViewMask;
	int			ownedViews;
	int			fallbackViews;
	int			ownedSourceSurfaces;
	int			fallbackSourceSurfaces;
	int			ownedDrawablePasses;
	int			fallbackDrawablePasses;
	int			ownedNoopPasses;
	int			fallbackNoopPasses;
	int			ownedPhaseDrawablePasses[ CLASSIC_WORLD_AMBIENT_PHASE_COUNT ];
	int			fallbackPhaseDrawablePasses[ CLASSIC_WORLD_AMBIENT_PHASE_COUNT ];
	int			coverageMismatches;
	int			duplicateReports;
	int			untrackedFallbacks;
} classicWorldAmbientDomainBackendCoverage_t;

typedef struct classicWorldAmbientDomainDraw_s {
	int					sourceSurfaceIndex;
	classicWorldAmbientDomainSourceSurface_t sourceSurface;
	classicWorldAmbientPhase_t		phase;
	// The sole legacy bridge retained by the domain. Consumers may use it only
	// for sealed geometry submission; stage data/registers are never reread.
	const drawSurf_t			*legacyDrawSurf;
	int					drawPacketIndex;
	int					depthDrawPacketIndex;
	int					materialTableRecordIndex;
	int					materialId;
	std::uint32_t				tableGeneration;
	int					firstWorldPass;
	int					worldPassCount;
	int					firstEvaluatedPass;
	int					evaluatedPassCount;
	int					activePassCount;
	int					drawablePassCount;
	int					inactivePassCount;
	int					activeNoopPassCount;
	int					noopPassCount;
	int					vertexCount;
	int					firstIndex;
	int					indexCount;
	int					vertexOffset;
	int					scissorX1;
	int					scissorY1;
	int					scissorX2;
	int					scissorY2;
	float					modelViewMatrix[ 16 ];
	bool					packetBacked;
	bool					depthPrerequisite;
	bool					hasIndexCache;
	bool					hasAmbientCache;
	classicDeformRole_t			deformRole;
	classicDeformOutcome_t		deformOutcome;
	std::uint64_t				deformContractHash;
	std::uint64_t				hash;
} classicWorldAmbientDomainDraw_t;

typedef struct classicWorldAmbientDomainView_s {
	const viewDef_t				*viewDef;
	int					scenePacketIndex;
	int					ambientPassPacketIndex;
	int					depthPassPacketIndex;
	std::uint32_t				tableGeneration;
	int					firstDraw;
	int					drawCount;
	int					sourceSurfaceCount;
	int					drawableSurfaceCount;
	int					noopSurfaceCount;
	int					packetDrawCount;
	int					depthPacketDrawCount;
	int					firstEvaluatedPass;
	int					evaluatedPassCount;
	int					activePassCount;
	int					drawablePassCount;
	int					inactivePassCount;
	int					activeNoopPassCount;
	int					noopPassCount;
	int					materialDeformSurfaceCount;
	int					completedDeformSurfaceCount;
	int					emptyDeformSurfaceCount;
	int					phaseSurfaceCount[ CLASSIC_WORLD_AMBIENT_PHASE_COUNT ];
	int					phaseDrawableSurfaceCount[ CLASSIC_WORLD_AMBIENT_PHASE_COUNT ];
	int					phaseDrawablePassCount[ CLASSIC_WORLD_AMBIENT_PHASE_COUNT ];
	int					phaseNoopPassCount[ CLASSIC_WORLD_AMBIENT_PHASE_COUNT ];
	int					viewportX1;
	int					viewportY1;
	int					viewportX2;
	int					viewportY2;
	int					scissorX1;
	int					scissorY1;
	int					scissorX2;
	int					scissorY2;
	float					projectionMatrix[ 16 ];
	bool					ready;
	classicWorldAmbientDomainFailure_t failure;
	int					failureDetail;
	materialResourceWorldPassFailure_t worldPassFailure;
	rendererMaterialPassEvaluationStatus_t evaluationStatus;
	int					failurePassPacketIndex;
	int					failureDrawPacketIndex;
	int					failureSourceSurfaceIndex;
	int					failureSourceStageIndex;
	std::uint64_t				hash;
	classicWorldAmbientDomainBackendOutcome_t backendOutcome[ CLASSIC_WORLD_AMBIENT_BACKEND_COUNT ];
	classicWorldAmbientDomainFailure_t backendFailure[ CLASSIC_WORLD_AMBIENT_BACKEND_COUNT ];
	int					backendFailureDetail[ CLASSIC_WORLD_AMBIENT_BACKEND_COUNT ];
	int					backendDrawnPasses[ CLASSIC_WORLD_AMBIENT_BACKEND_COUNT ][ CLASSIC_WORLD_AMBIENT_PHASE_COUNT ];
	int					backendNoopPasses[ CLASSIC_WORLD_AMBIENT_BACKEND_COUNT ];
} classicWorldAmbientDomainView_t;

typedef struct classicWorldAmbientDomainStats_s {
	bool		prepared;
	bool		frameValid;
	bool		overflow;
	int		sourceScenes;
	int		worldViews;
	int		readyViews;
	int		fallbackViews;
	int		sourceSurfaces;
	int		drawableSurfaces;
	int		noopSurfaces;
	int		draws;
	int		evaluatedPasses;
	int		activePasses;
	int		drawablePasses;
	int		inactivePasses;
	int		activeNoopPasses;
	int		noopPasses;
	int		materialDeformSurfaces;
	int		completedDeformSurfaces;
	int		emptyDeformSurfaces;
	int		phaseDrawablePasses[ CLASSIC_WORLD_AMBIENT_PHASE_COUNT ];
	int		phaseNoopPasses[ CLASSIC_WORLD_AMBIENT_PHASE_COUNT ];
	int		failureCounts[ CLASSIC_WORLD_AMBIENT_FAILURE_COUNT ];
	std::uint64_t	hash;
	classicWorldAmbientDomainBackendCoverage_t backend[ CLASSIC_WORLD_AMBIENT_BACKEND_COUNT ];
	char		status[ 96 ];
} classicWorldAmbientDomainStats_t;

void R_ClassicWorldAmbientDomain_ResetFrame( void );
void R_ClassicWorldAmbientDomain_PrepareFrame( const idScenePacketFrame &packetFrame );
const classicWorldAmbientDomainStats_t &R_ClassicWorldAmbientDomain_Stats( void );
int R_ClassicWorldAmbientDomain_NumViews( void );
const classicWorldAmbientDomainView_t *R_ClassicWorldAmbientDomain_ViewByIndex( int index );
const classicWorldAmbientDomainView_t *R_ClassicWorldAmbientDomain_ViewForScenePacket( int scenePacketIndex );
const classicWorldAmbientDomainView_t *R_ClassicWorldAmbientDomain_FindView( const viewDef_t *viewDef );
const classicWorldAmbientDomainDraw_t *R_ClassicWorldAmbientDomain_ViewDraw(
	const classicWorldAmbientDomainView_t &view, int drawIndex );
const rendererEvaluatedMaterialPass_t *R_ClassicWorldAmbientDomain_DrawPass(
	const classicWorldAmbientDomainDraw_t &draw, int passIndex );
const materialResourceTextureBinding_t *R_ClassicWorldAmbientDomain_DrawPassTexture(
	const classicWorldAmbientDomainDraw_t &draw, int passIndex );
bool R_ClassicWorldAmbientDomain_RecordOwned( const viewDef_t *viewDef,
	classicWorldAmbientDomainBackend_t backend, int preFogDrawnPasses,
	int postFogDrawnPasses, int noopPasses );
void R_ClassicWorldAmbientDomain_RecordBackendFallback( const viewDef_t *viewDef,
	classicWorldAmbientDomainBackend_t backend,
	classicWorldAmbientDomainFailure_t failure, int detail );
const classicWorldAmbientDomainBackendCoverage_t &R_ClassicWorldAmbientDomain_BackendCoverage(
	classicWorldAmbientDomainBackend_t backend );
const char *ClassicWorldAmbientPhase_Name( classicWorldAmbientPhase_t phase );
const char *ClassicWorldAmbientDomainSourceSurface_Name(
	classicWorldAmbientDomainSourceSurface_t sourceSurface );
const char *ClassicWorldAmbientDomainFailure_Name(
	classicWorldAmbientDomainFailure_t failure );
const char *ClassicWorldAmbientDomainBackend_Name(
	classicWorldAmbientDomainBackend_t backend );
bool RendererClassicWorldAmbientDomain_RunSelfTest( void );

#endif /* !__CLASSIC_WORLD_AMBIENT_DOMAIN_H__ */
