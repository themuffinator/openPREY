// Copyright (C) 2026 DarkMatter Productions
//

#ifndef __CLASSIC_GUI_DOMAIN_H__
#define __CLASSIC_GUI_DOMAIN_H__

#include "ClassicDeformDomain.h"
#include "MaterialResourceTable.h"

/*
===============================================================================

	Shared ownership contract for classic fixed-function GUI work. Root 2D
	command views remain whole-view transactions; GUI quads emitted onto 3D
	surfaces are an independently sealed, provenance-tagged subset.

	Preparation is transactional per view.  A view is ready only when every
	source surface has been classified, every expected scene packet matches in
	original order, every material pass has evaluated, and every opaque texture
	resource has resolved.  Failed views retain diagnostics but expose no partial
	draw or pass range.

===============================================================================
*/

const int CLASSIC_GUI_DOMAIN_MAX_VIEWS = SCENE_PACKET_MAX_SCENES;
const int CLASSIC_GUI_DOMAIN_MAX_DRAWS = SCENE_PACKET_MAX_DRAWS;
const int CLASSIC_GUI_DOMAIN_MAX_EVALUATED_PASSES = SCENE_PACKET_MAX_DRAWS * 2;

enum classicGuiDomainScope_t {
	CLASSIC_GUI_DOMAIN_SCOPE_ROOT_2D = 0,
	CLASSIC_GUI_DOMAIN_SCOPE_IN_WORLD,
	CLASSIC_GUI_DOMAIN_SCOPE_COUNT
};

enum classicGuiDomainSourceSurface_t {
	CLASSIC_GUI_DOMAIN_SOURCE_SURFACE_DRAWABLE = 0,
	CLASSIC_GUI_DOMAIN_SOURCE_SURFACE_NOOP_NULL_SURFACE,
	CLASSIC_GUI_DOMAIN_SOURCE_SURFACE_NOOP_MISSING_MATERIAL,
	CLASSIC_GUI_DOMAIN_SOURCE_SURFACE_NOOP_NO_AMBIENT,
	CLASSIC_GUI_DOMAIN_SOURCE_SURFACE_NOOP_PORTAL_SKY,
	CLASSIC_GUI_DOMAIN_SOURCE_SURFACE_NOOP_EMPTY_GEOMETRY,
	CLASSIC_GUI_DOMAIN_SOURCE_SURFACE_FALLBACK_SUPPRESSED_IN_SUBVIEW,
	CLASSIC_GUI_DOMAIN_SOURCE_SURFACE_FALLBACK_MISSING_SPACE,
	CLASSIC_GUI_DOMAIN_SOURCE_SURFACE_FALLBACK_DEPTH_HACK,
	CLASSIC_GUI_DOMAIN_SOURCE_SURFACE_FALLBACK_DECAL_COLOR_STREAM,
	CLASSIC_GUI_DOMAIN_SOURCE_SURFACE_FALLBACK_NEGATIVE_SCALE,
	CLASSIC_GUI_DOMAIN_SOURCE_SURFACE_FALLBACK_POST_PROCESS,
	CLASSIC_GUI_DOMAIN_SOURCE_SURFACE_COUNT
};

enum classicGuiDomainFailure_t {
	CLASSIC_GUI_DOMAIN_FAILURE_NONE = 0,
	CLASSIC_GUI_DOMAIN_FAILURE_UNAVAILABLE,
	CLASSIC_GUI_DOMAIN_FAILURE_SCENE_PACKET_OVERFLOW,
	CLASSIC_GUI_DOMAIN_FAILURE_MATERIAL_TABLE_NOT_PREPARED,
	CLASSIC_GUI_DOMAIN_FAILURE_MATERIAL_TABLE_OVERFLOW,
	CLASSIC_GUI_DOMAIN_FAILURE_VIEW_POOL_OVERFLOW,
	CLASSIC_GUI_DOMAIN_FAILURE_DRAW_POOL_OVERFLOW,
	CLASSIC_GUI_DOMAIN_FAILURE_EVALUATED_PASS_POOL_OVERFLOW,
	CLASSIC_GUI_DOMAIN_FAILURE_UNSUPPORTED_VIEW,
	CLASSIC_GUI_DOMAIN_FAILURE_INVALID_SCENE_RANGE,
	CLASSIC_GUI_DOMAIN_FAILURE_INVALID_GUI_PASS,
	CLASSIC_GUI_DOMAIN_FAILURE_INVALID_DRAW_RANGE,
	CLASSIC_GUI_DOMAIN_FAILURE_SOURCE_SURFACE_FALLBACK,
	CLASSIC_GUI_DOMAIN_FAILURE_SOURCE_PACKET_MISMATCH,
	CLASSIC_GUI_DOMAIN_FAILURE_INVALID_DRAW_PACKET,
	CLASSIC_GUI_DOMAIN_FAILURE_DEFORM_CONTRACT,
	CLASSIC_GUI_DOMAIN_FAILURE_MISSING_GEOMETRY_RECORD,
	CLASSIC_GUI_DOMAIN_FAILURE_MISSING_INSTANCE_RECORD,
	CLASSIC_GUI_DOMAIN_FAILURE_MISSING_MATERIAL_RECORD,
	CLASSIC_GUI_DOMAIN_FAILURE_STALE_MATERIAL_RECORD,
	CLASSIC_GUI_DOMAIN_FAILURE_MATERIAL_PASS_INELIGIBLE,
	CLASSIC_GUI_DOMAIN_FAILURE_MATERIAL_PASS_COPY_FAILED,
	CLASSIC_GUI_DOMAIN_FAILURE_MATERIAL_PASS_EVALUATION_FAILED,
	CLASSIC_GUI_DOMAIN_FAILURE_TEXTURE_RESOURCE_UNAVAILABLE,
	CLASSIC_GUI_DOMAIN_FAILURE_INVALID_DISPOSITION,
	CLASSIC_GUI_DOMAIN_FAILURE_BACKEND_NOT_READY,
	CLASSIC_GUI_DOMAIN_FAILURE_BACKEND_COVERAGE_MISMATCH,
	CLASSIC_GUI_DOMAIN_FAILURE_BACKEND_REJECTED,
	CLASSIC_GUI_DOMAIN_FAILURE_COUNT
};

enum classicGuiDomainBackend_t {
	CLASSIC_GUI_DOMAIN_BACKEND_GL = 0,
	CLASSIC_GUI_DOMAIN_BACKEND_VULKAN,
	CLASSIC_GUI_DOMAIN_BACKEND_COUNT
};

enum classicGuiDomainBackendOutcome_t {
	CLASSIC_GUI_DOMAIN_BACKEND_UNRECORDED = 0,
	CLASSIC_GUI_DOMAIN_BACKEND_OWNED,
	CLASSIC_GUI_DOMAIN_BACKEND_FALLBACK
};

typedef struct classicGuiDomainBackendCoverage_s {
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
	int			coverageMismatches;
	int			duplicateReports;
	int			untrackedFallbacks;
} classicGuiDomainBackendCoverage_t;

typedef struct classicGuiDomainDraw_s {
	int					sourceSurfaceIndex;
	classicGuiDomainSourceSurface_t	sourceSurface;
	// This is the sole legacy bridge retained by the domain.  Consumers may use
	// it for geometry submission only; material stages and shader registers are
	// sealed into the evaluated pass range during preparation.
	const drawSurf_t			*legacyDrawSurf;
	int					drawPacketIndex;
	int					materialTableRecordIndex;
	int					materialId;
	std::uint32_t				tableGeneration;
	int					firstGuiPass;
	int					guiPassCount;
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
	bool					hasIndexCache;
	bool					hasAmbientCache;
	classicDeformRole_t			deformRole;
	classicDeformOutcome_t		deformOutcome;
	std::uint64_t				deformContractHash;
	std::uint64_t				hash;
} classicGuiDomainDraw_t;

typedef struct classicGuiDomainView_s {
	const viewDef_t				*viewDef;
	classicGuiDomainScope_t		scope;
	int					scenePacketIndex;
	int					guiPassPacketIndex;
	std::uint32_t				tableGeneration;
	int					firstDraw;
	int					drawCount;
	int					sourceSurfaceCount;
	int					drawableSurfaceCount;
	int					noopSurfaceCount;
	int					packetDrawCount;
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
	classicGuiDomainFailure_t	failure;
	int					failureDetail;
	materialResourceGuiPassFailure_t	guiPassFailure;
	rendererMaterialPassEvaluationStatus_t evaluationStatus;
	int					failurePassPacketIndex;
	int					failureDrawPacketIndex;
	int					failureSourceSurfaceIndex;
	int					failureSourceStageIndex;
	std::uint64_t				hash;
	classicGuiDomainBackendOutcome_t	backendOutcome[ CLASSIC_GUI_DOMAIN_BACKEND_COUNT ];
	classicGuiDomainFailure_t	backendFailure[ CLASSIC_GUI_DOMAIN_BACKEND_COUNT ];
	int					backendFailureDetail[ CLASSIC_GUI_DOMAIN_BACKEND_COUNT ];
	int					backendDrawnPasses[ CLASSIC_GUI_DOMAIN_BACKEND_COUNT ];
	int					backendNoopPasses[ CLASSIC_GUI_DOMAIN_BACKEND_COUNT ];
} classicGuiDomainView_t;

typedef struct classicGuiDomainStats_s {
	bool			prepared;
	bool			frameValid;
	bool			overflow;
	int			sourceScenes;
	int			guiViews;
	int			rootViews;
	int			inWorldViews;
	int			readyViews;
	int			fallbackViews;
	int			sourceSurfaces;
	int			drawableSurfaces;
	int			noopSurfaces;
	int			draws;
	int			evaluatedPasses;
	int			activePasses;
	int			drawablePasses;
	int			inactivePasses;
	int			activeNoopPasses;
	int			noopPasses;
	int			materialDeformSurfaces;
	int			completedDeformSurfaces;
	int			emptyDeformSurfaces;
	int			failureCounts[ CLASSIC_GUI_DOMAIN_FAILURE_COUNT ];
	std::uint64_t	hash;
	classicGuiDomainBackendCoverage_t backend[ CLASSIC_GUI_DOMAIN_BACKEND_COUNT ];
	char			status[ 96 ];
} classicGuiDomainStats_t;

void R_ClassicGuiDomain_ResetFrame( void );
void R_ClassicGuiDomain_PrepareFrame( const idScenePacketFrame &packetFrame );
const classicGuiDomainStats_t &R_ClassicGuiDomain_Stats( void );
int R_ClassicGuiDomain_NumViews( void );
const classicGuiDomainView_t *R_ClassicGuiDomain_ViewByIndex( int index );
const classicGuiDomainView_t *R_ClassicGuiDomain_ViewForScenePacket( int scenePacketIndex );
const classicGuiDomainView_t *R_ClassicGuiDomain_FindView( const viewDef_t *viewDef );
const classicGuiDomainView_t *R_ClassicGuiDomain_FindRootView( const viewDef_t *viewDef );
const classicGuiDomainView_t *R_ClassicGuiDomain_FindInWorldView( const viewDef_t *viewDef );
const classicGuiDomainDraw_t *R_ClassicGuiDomain_ViewDraw(
	const classicGuiDomainView_t &view, int drawIndex );
const rendererEvaluatedMaterialPass_t *R_ClassicGuiDomain_DrawPass(
	const classicGuiDomainDraw_t &draw, int passIndex );
const materialResourceTextureBinding_t *R_ClassicGuiDomain_DrawPassTexture(
	const classicGuiDomainDraw_t &draw, int passIndex );
bool R_ClassicGuiDomain_RecordOwned( const viewDef_t *viewDef,
	classicGuiDomainBackend_t backend, int drawnPasses, int noopPasses );
void R_ClassicGuiDomain_RecordBackendFallback( const viewDef_t *viewDef,
	classicGuiDomainBackend_t backend, classicGuiDomainFailure_t failure, int detail );
const classicGuiDomainBackendCoverage_t &R_ClassicGuiDomain_BackendCoverage(
	classicGuiDomainBackend_t backend );
bool R_ClassicGuiDomain_IsLegacyInWorldDrawOwned( const viewDef_t *viewDef,
	classicGuiDomainBackend_t backend, const drawSurf_t *drawSurf );
const char *ClassicGuiDomainSourceSurface_Name(
	classicGuiDomainSourceSurface_t sourceSurface );
const char *ClassicGuiDomainFailure_Name( classicGuiDomainFailure_t failure );
const char *ClassicGuiDomainBackend_Name( classicGuiDomainBackend_t backend );
bool RendererClassicGuiDomain_RunSelfTest( void );

#endif /* !__CLASSIC_GUI_DOMAIN_H__ */
