// Copyright (C) 2026 DarkMatter Productions
//

#ifndef __CLASSIC_SUBVIEW_DOMAIN_H__
#define __CLASSIC_SUBVIEW_DOMAIN_H__

#include "ImageOpts.h"
#include "ScenePackets.h"

/*
===============================================================================

	Shared special-subview transaction.

	A view is published only after its parent source surface, child scene packet,
	and exact RC_COPY_RENDER destination agree.  Direct SS_SUBVIEW mirrors seal
	their complete camera/clip/scissor semantics and have no capture command;
	dynamic remote, mirror, reflection, refraction, and x-ray surfaces retain an
	exact color, cubemap-face, or depth-capture edge. A nested child also seals
	its direct parent domain record, root transaction, depth, and depth-first
	command order. Every capture target seals its image type, depth/color aspect,
	and exact cube face before either backend uses its established transfer
	implementation. Nested transaction ownership is published only after the
	outermost special view completes every admitted descendant.

===============================================================================
*/

const int CLASSIC_SUBVIEW_DOMAIN_MAX_VIEWS = SCENE_PACKET_MAX_SUBVIEW_CAPTURES;

enum classicSubviewDomainKind_t {
	CLASSIC_SUBVIEW_DOMAIN_KIND_NONE = 0,
	CLASSIC_SUBVIEW_DOMAIN_KIND_DIRECT_MIRROR,
	CLASSIC_SUBVIEW_DOMAIN_KIND_REMOTE_CAMERA,
	CLASSIC_SUBVIEW_DOMAIN_KIND_MIRROR,
	CLASSIC_SUBVIEW_DOMAIN_KIND_REFLECTION,
	CLASSIC_SUBVIEW_DOMAIN_KIND_REFRACTION,
	CLASSIC_SUBVIEW_DOMAIN_KIND_XRAY,
	CLASSIC_SUBVIEW_DOMAIN_KIND_COUNT
};

enum classicSubviewDomainCaptureType_t {
	CLASSIC_SUBVIEW_DOMAIN_CAPTURE_NONE = 0,
	CLASSIC_SUBVIEW_DOMAIN_CAPTURE_COLOR_2D,
	CLASSIC_SUBVIEW_DOMAIN_CAPTURE_COLOR_CUBEMAP,
	CLASSIC_SUBVIEW_DOMAIN_CAPTURE_DEPTH_2D,
	CLASSIC_SUBVIEW_DOMAIN_CAPTURE_DEPTH_CUBEMAP,
	CLASSIC_SUBVIEW_DOMAIN_CAPTURE_COUNT
};

enum classicSubviewDomainFailure_t {
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_NONE = 0,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_UNAVAILABLE,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_SCENE_PACKET_OVERFLOW,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_CAPTURE_POOL_OVERFLOW,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_UNSUPPORTED_VIEW,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_MISSING_PARENT_SCENE,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_MISSING_PARENT_SURFACE,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_UNSUPPORTED_PARENT_MATERIAL,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_MISSING_CAPTURE,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_DUPLICATE_CAPTURE,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_INVALID_CAPTURE,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_CAPTURE_SURFACE_MISMATCH,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_CAPTURE_VIEWPORT_MISMATCH,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_UNSUPPORTED_CAPTURE_TARGET,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_UNEXPECTED_CAPTURE,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_UNSUPPORTED_SPECIAL_SEMANTICS,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_VIEW_SEMANTICS_MISMATCH,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_MISSING_NESTED_PARENT,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_NESTED_COMMAND_ORDER,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_NESTED_PARENT_FALLBACK,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_NESTED_CHILD_FALLBACK,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_NESTED_CINEMATIC_POST_FALLBACK,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_NOT_READY,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_REJECTED,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_CAPTURE_MISMATCH,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_NESTING_INCOMPLETE,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_NESTED_CINEMATIC_POST_INCOMPLETE,
	CLASSIC_SUBVIEW_DOMAIN_FAILURE_COUNT
};

enum classicSubviewDomainBackend_t {
	CLASSIC_SUBVIEW_DOMAIN_BACKEND_GL = 0,
	CLASSIC_SUBVIEW_DOMAIN_BACKEND_VULKAN,
	CLASSIC_SUBVIEW_DOMAIN_BACKEND_COUNT
};

enum classicSubviewDomainBackendOutcome_t {
	CLASSIC_SUBVIEW_DOMAIN_BACKEND_UNRECORDED = 0,
	CLASSIC_SUBVIEW_DOMAIN_BACKEND_OWNED,
	CLASSIC_SUBVIEW_DOMAIN_BACKEND_FALLBACK
};

typedef struct classicSubviewDomainBackendCoverage_s {
	std::uint64_t	ownedViewMask;
	std::uint64_t	fallbackViewMask;
	int				ownedViews;
	int				fallbackViews;
	int				ownedDirectMirrorViews;
	int				ownedRemoteCameraViews;
	int				ownedMirrorViews;
	int				ownedReflectionViews;
	int				ownedRefractionViews;
	int				ownedXrayViews;
	int				ownedColorCubemapCaptures;
	int				ownedDepth2DCaptures;
	int				ownedDepthCubemapCaptures;
	int				ownedNestedViews;
	int				ownedNestedTransactions;
	int				fallbackNestedViews;
	int				fallbackNestedTransactions;
	int				coverageMismatches;
	int				duplicateReports;
	int				untrackedFallbacks;
} classicSubviewDomainBackendCoverage_t;

typedef struct classicSubviewDomainView_s {
	const viewDef_t			*viewDef;
	const viewDef_t			*parentViewDef;
	const drawSurf_t		*parentSurface;
	idImage					*captureImage;
	int					scenePacketIndex;
	int					parentScenePacketIndex;
	int					parentViewIndex;
	int					rootViewIndex;
	int					nestingDepth;
	int					subtreeViewCount;
	int					capturePacketIndex;
	int					firstPassPacket;
	int					passPacketCount;
	int					firstDrawPacket;
	int					drawPacketCount;
	int					captureX;
	int					captureY;
	int					captureWidth;
	int					captureHeight;
	int					captureCubeFace;
	textureType_t			captureTextureType;
	textureFormat_t			captureTextureFormat;
	bool					captureCopyDepth;
	int					semanticViewID;
	int					semanticRenderTime;
	float					semanticFloatTime;
	idVec3					semanticViewOrigin;
	idMat3					semanticViewAxis;
	idVec3					semanticInitialViewAreaOrigin;
	idScreenRect				semanticViewport;
	idScreenRect				semanticScissor;
	idPlane					semanticClipPlanes[MAX_CLIP_PLANES];
	int					semanticClipPlaneCount;
	bool					semanticIsMirror;
	bool					semanticIsXraySubview;
	classicSubviewDomainKind_t	kind;
	classicSubviewDomainCaptureType_t	captureType;
	bool					ready;
	classicSubviewDomainFailure_t	failure;
	int					failureDetail;
	std::uint64_t			hash;
	classicSubviewDomainBackendOutcome_t backendOutcome[
		CLASSIC_SUBVIEW_DOMAIN_BACKEND_COUNT];
	classicSubviewDomainFailure_t backendFailure[
		CLASSIC_SUBVIEW_DOMAIN_BACKEND_COUNT];
	int					backendFailureDetail[
		CLASSIC_SUBVIEW_DOMAIN_BACKEND_COUNT];
	bool					backendCompleted[
		CLASSIC_SUBVIEW_DOMAIN_BACKEND_COUNT];
} classicSubviewDomainView_t;

typedef struct classicSubviewDomainStats_s {
	bool					prepared;
	bool					frameValid;
	bool					overflow;
	int					sourceScenes;
	int					subviewScenes;
	int					capturePackets;
	int					readyViews;
	int					fallbackViews;
	int					directMirrorViews;
	int					remoteCameraViews;
	int					mirrorViews;
	int					reflectionViews;
	int					refractionViews;
	int					xrayViews;
	int					colorCubemapCaptures;
	int					depth2DCaptures;
	int					depthCubemapCaptures;
	int					nestedViews;
	int					nestedTransactions;
	int					maxNestingDepth;
	int					failureCounts[CLASSIC_SUBVIEW_DOMAIN_FAILURE_COUNT];
	std::uint64_t			hash;
	classicSubviewDomainBackendCoverage_t backend[
		CLASSIC_SUBVIEW_DOMAIN_BACKEND_COUNT];
	char					status[96];
} classicSubviewDomainStats_t;

void R_ClassicSubviewDomain_ResetFrame( void );
void R_ClassicSubviewDomain_PrepareFrame( const idScenePacketFrame &packetFrame );
const classicSubviewDomainStats_t &R_ClassicSubviewDomain_Stats( void );
int R_ClassicSubviewDomain_NumViews( void );
const classicSubviewDomainView_t *R_ClassicSubviewDomain_ViewByIndex( int index );
const classicSubviewDomainView_t *R_ClassicSubviewDomain_FindView(
	const viewDef_t *viewDef );
bool R_ClassicSubviewDomain_CaptureMatches(
	const classicSubviewDomainView_t &view, const idImage *image,
	int x, int y, int width, int height, int cubeFace, bool copyDepth );
bool R_ClassicSubviewDomain_IsCaptureBacked(
	const classicSubviewDomainView_t &view );
bool R_ClassicSubviewDomain_IsDirect(
	const classicSubviewDomainView_t &view );
bool R_ClassicSubviewDomain_ViewSemanticsMatch(
	const classicSubviewDomainView_t &view );
bool R_ClassicSubviewDomain_ReadyForBackend(
	const classicSubviewDomainView_t &view,
	classicSubviewDomainBackend_t backend );
bool R_ClassicSubviewDomain_RecordOwned( const viewDef_t *viewDef,
	classicSubviewDomainBackend_t backend, const idImage *image,
	int x, int y, int width, int height, int cubeFace, bool copyDepth );
bool R_ClassicSubviewDomain_RecordDirectOwned( const viewDef_t *viewDef,
	classicSubviewDomainBackend_t backend );
void R_ClassicSubviewDomain_RecordBackendFallback( const viewDef_t *viewDef,
	classicSubviewDomainBackend_t backend, classicSubviewDomainFailure_t failure,
	int detail );
const classicSubviewDomainBackendCoverage_t &
	R_ClassicSubviewDomain_BackendCoverage( classicSubviewDomainBackend_t backend );
const char *ClassicSubviewDomainKind_Name( classicSubviewDomainKind_t kind );
const char *ClassicSubviewDomainCaptureType_Name(
	classicSubviewDomainCaptureType_t type );
const char *ClassicSubviewDomainFailure_Name( classicSubviewDomainFailure_t failure );
const char *ClassicSubviewDomainBackend_Name( classicSubviewDomainBackend_t backend );
bool RendererClassicSubviewDomain_RunSelfTest( void );

#endif /* !__CLASSIC_SUBVIEW_DOMAIN_H__ */
