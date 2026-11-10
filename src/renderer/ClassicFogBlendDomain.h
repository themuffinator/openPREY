// Copyright (C) 2026 DarkMatter Productions
//

#ifndef __CLASSIC_FOG_BLEND_DOMAIN_H__
#define __CLASSIC_FOG_BLEND_DOMAIN_H__

#include "ClassicDeformDomain.h"
#include "MaterialResourceTable.h"

/*
===============================================================================

	Shared whole-view ownership contract for the classic fog/blend phase.

	Preparation is transactional per ordinary root 3D view. A ready view owns
	the complete source-ordered fog/blend light stream: authoritative GLOBAL then
	LOCAL receiver chains, every authored blend stage (including inactive
	stages), and the fog frustum cap after its receivers. Every stage register,
	texture, render state, transform and texgen plane is sealed here. Retained
	draw-surface and triangle pointers are geometry submission bridges only.

	Any unsupported view, surface, stage, geometry or resource rewinds all ranges
	for that view so an unchanged classic backend can execute the complete phase
	exactly once. Fog and blend are never split between shared and classic owners.

===============================================================================
*/

const int CLASSIC_FOG_BLEND_DOMAIN_MAX_VIEWS = SCENE_PACKET_MAX_SCENES;
const int CLASSIC_FOG_BLEND_DOMAIN_MAX_LIGHTS = SCENE_PACKET_MAX_DRAWS;
const int CLASSIC_FOG_BLEND_DOMAIN_MAX_SURFACES = SCENE_PACKET_MAX_DRAWS;
const int CLASSIC_FOG_BLEND_DOMAIN_MAX_LIGHT_STAGES =
	SCENE_PACKET_MAX_DRAWS * 2;
const int CLASSIC_FOG_BLEND_DOMAIN_MAX_PRIMITIVES =
	SCENE_PACKET_MAX_DRAWS * 4;
const int CLASSIC_FOG_BLEND_DOMAIN_MAX_TEXTURES =
	SCENE_PACKET_MAX_DRAWS * 2;

enum classicFogBlendDomainLightKind_t {
	CLASSIC_FOG_BLEND_LIGHT_FOG = 0,
	CLASSIC_FOG_BLEND_LIGHT_BLEND,
	CLASSIC_FOG_BLEND_LIGHT_KIND_COUNT
};

enum classicFogBlendDomainReceiver_t {
	CLASSIC_FOG_BLEND_RECEIVER_GLOBAL = 0,
	CLASSIC_FOG_BLEND_RECEIVER_LOCAL,
	CLASSIC_FOG_BLEND_RECEIVER_FRUSTUM,
	CLASSIC_FOG_BLEND_RECEIVER_COUNT
};

enum classicFogBlendDomainLightDisposition_t {
	CLASSIC_FOG_BLEND_LIGHT_DRAW = 0,
	CLASSIC_FOG_BLEND_LIGHT_NOOP_SKIP_BLEND,
	CLASSIC_FOG_BLEND_LIGHT_NOOP_MISSING_GLOBAL_CHAIN,
	CLASSIC_FOG_BLEND_LIGHT_DISPOSITION_COUNT
};

enum classicFogBlendDomainLightStageDisposition_t {
	CLASSIC_FOG_BLEND_STAGE_DRAW = 0,
	CLASSIC_FOG_BLEND_STAGE_NOOP_INACTIVE_CONDITION,
	CLASSIC_FOG_BLEND_STAGE_NOOP_SKIP_BLEND,
	CLASSIC_FOG_BLEND_STAGE_NOOP_MISSING_GLOBAL_CHAIN,
	CLASSIC_FOG_BLEND_STAGE_DISPOSITION_COUNT
};

enum classicFogBlendDomainPrimitiveKind_t {
	CLASSIC_FOG_BLEND_PRIMITIVE_FOG_RECEIVER = 0,
	CLASSIC_FOG_BLEND_PRIMITIVE_FOG_FRUSTUM_CAP,
	CLASSIC_FOG_BLEND_PRIMITIVE_BLEND_RECEIVER,
	CLASSIC_FOG_BLEND_PRIMITIVE_KIND_COUNT
};

enum classicFogBlendDomainPrimitiveDisposition_t {
	CLASSIC_FOG_BLEND_PRIMITIVE_DRAW = 0,
	CLASSIC_FOG_BLEND_PRIMITIVE_NOOP_INACTIVE_STAGE,
	CLASSIC_FOG_BLEND_PRIMITIVE_NOOP_SKIP_BLEND,
	CLASSIC_FOG_BLEND_PRIMITIVE_NOOP_MISSING_GLOBAL_CHAIN,
	CLASSIC_FOG_BLEND_PRIMITIVE_DISPOSITION_COUNT
};

enum classicFogBlendDomainFailure_t {
	CLASSIC_FOG_BLEND_FAILURE_NONE = 0,
	CLASSIC_FOG_BLEND_FAILURE_UNAVAILABLE,
	CLASSIC_FOG_BLEND_FAILURE_SCENE_PACKET_OVERFLOW,
	CLASSIC_FOG_BLEND_FAILURE_VIEW_POOL_OVERFLOW,
	CLASSIC_FOG_BLEND_FAILURE_LIGHT_POOL_OVERFLOW,
	CLASSIC_FOG_BLEND_FAILURE_SURFACE_POOL_OVERFLOW,
	CLASSIC_FOG_BLEND_FAILURE_LIGHT_STAGE_POOL_OVERFLOW,
	CLASSIC_FOG_BLEND_FAILURE_PRIMITIVE_POOL_OVERFLOW,
	CLASSIC_FOG_BLEND_FAILURE_TEXTURE_POOL_OVERFLOW,
	CLASSIC_FOG_BLEND_FAILURE_UNSUPPORTED_VIEW,
	CLASSIC_FOG_BLEND_FAILURE_UNSUPPORTED_STATE,
	CLASSIC_FOG_BLEND_FAILURE_INVALID_SCENE_RANGE,
	CLASSIC_FOG_BLEND_FAILURE_INVALID_FOG_BLEND_PASS,
	CLASSIC_FOG_BLEND_FAILURE_INVALID_DRAW_RANGE,
	CLASSIC_FOG_BLEND_FAILURE_SOURCE_PACKET_MISMATCH,
	CLASSIC_FOG_BLEND_FAILURE_INVALID_DRAW_PACKET,
	CLASSIC_FOG_BLEND_FAILURE_MISSING_GEOMETRY_RECORD,
	CLASSIC_FOG_BLEND_FAILURE_MISSING_INSTANCE_RECORD,
	CLASSIC_FOG_BLEND_FAILURE_MISSING_LIGHT_SHADER,
	CLASSIC_FOG_BLEND_FAILURE_MISSING_SHADER_REGISTERS,
	CLASSIC_FOG_BLEND_FAILURE_MISSING_LIGHT_STAGE,
	CLASSIC_FOG_BLEND_FAILURE_REGISTER_OUT_OF_RANGE,
	CLASSIC_FOG_BLEND_FAILURE_NONFINITE_VALUE,
	CLASSIC_FOG_BLEND_FAILURE_FOG_FRUSTUM_GEOMETRY,
	CLASSIC_FOG_BLEND_FAILURE_DEFORM,
	CLASSIC_FOG_BLEND_FAILURE_DEFORM_CONTRACT,
	CLASSIC_FOG_BLEND_FAILURE_SKINNING,
	CLASSIC_FOG_BLEND_FAILURE_SPECIAL_SURFACE,
	CLASSIC_FOG_BLEND_FAILURE_DEPTH_HACK,
	CLASSIC_FOG_BLEND_FAILURE_NEGATIVE_SCALE,
	CLASSIC_FOG_BLEND_FAILURE_UNSUPPORTED_MATERIAL,
	CLASSIC_FOG_BLEND_FAILURE_UNSUPPORTED_RENDER_STATE,
	CLASSIC_FOG_BLEND_FAILURE_DYNAMIC_RESOURCE,
	CLASSIC_FOG_BLEND_FAILURE_MISSING_RESOURCE,
	CLASSIC_FOG_BLEND_FAILURE_DEFAULTED_RESOURCE,
	CLASSIC_FOG_BLEND_FAILURE_UNLOADED_RESOURCE,
	CLASSIC_FOG_BLEND_FAILURE_BACKEND_NOT_READY,
	CLASSIC_FOG_BLEND_FAILURE_BACKEND_COVERAGE_MISMATCH,
	CLASSIC_FOG_BLEND_FAILURE_BACKEND_REJECTED,
	CLASSIC_FOG_BLEND_FAILURE_COUNT
};

enum classicFogBlendDomainBackend_t {
	CLASSIC_FOG_BLEND_BACKEND_GL = 0,
	CLASSIC_FOG_BLEND_BACKEND_VULKAN,
	CLASSIC_FOG_BLEND_BACKEND_COUNT
};

enum classicFogBlendDomainBackendOutcome_t {
	CLASSIC_FOG_BLEND_BACKEND_UNRECORDED = 0,
	CLASSIC_FOG_BLEND_BACKEND_OWNED,
	CLASSIC_FOG_BLEND_BACKEND_FALLBACK
};

typedef struct classicFogBlendDomainTexture_s {
	std::uint64_t	textureResourceId;
	const idImage		*image;
	std::uint64_t	storageGeneration;
	std::uint64_t	nameHash;
	unsigned int	textureHandle;
	textureFilter_t	filter;
	textureRepeat_t	repeat;
	bool			loaded;
	bool			defaulted;
	bool			mutableImage;
} classicFogBlendDomainTexture_t;

typedef struct classicFogBlendDomainSurface_s {
	// Geometry submission bridges only. Consumers must not follow either bridge
	// to material stages, shader registers, or mutable front-end state.
	const drawSurf_t		*legacyDrawSurf;
	const srfTriangles_t	*legacyGeometry;
	int			drawPacketIndex;
	int			lightIndex;
	int			sourceOrdinal;
	int			receiverOrdinal;
	classicFogBlendDomainReceiver_t receiver;
	int			geometryRecordIndex;
	int			instanceRecordIndex;
	int			vertexCount;
	int			firstIndex;
	int			indexCount;
	int			vertexOffset;
	int			scissorX1;
	int			scissorY1;
	int			scissorX2;
	int			scissorY2;
	float			modelMatrix[ 16 ];
	float			modelViewMatrix[ 16 ];
	bool			hasAmbientCache;
	bool			hasIndexCache;
	classicDeformRole_t	deformRole;
	classicDeformOutcome_t	deformOutcome;
	std::uint64_t	deformContractHash;
	std::uint64_t	hash;
} classicFogBlendDomainSurface_t;

typedef struct classicFogBlendDomainLightStage_s {
	int			lightIndex;
	int			sourceStageIndex;
	classicFogBlendDomainLightStageDisposition_t disposition;
	int			firstPrimitive;
	int			primitiveCount;
	int			drawablePrimitiveCount;
	int			noopPrimitiveCount;
	float			condition;
	float			color[ 4 ];
	float			textureMatrix[ 2 ][ 4 ];
	std::uint64_t	projectionTextureResourceId;
	std::uint64_t	falloffTextureResourceId;
	std::uint64_t	fogTextureResourceId;
	std::uint64_t	fogEnterTextureResourceId;
	rendererBlendState_t blend;
	rendererDepthState_t depth;
	rendererCullMode_t	cull;
	std::uint32_t	colorWriteMask;
	bool			alphaTestEnabled;
	rendererCompareOp_t	alphaTestCompareOperation;
	float			alphaTestValue;
	bool			hasTextureMatrix;
	bool			conditionIgnored;
	std::uint64_t	hash;
} classicFogBlendDomainLightStage_t;

typedef struct classicFogBlendDomainLight_s {
	int			sourceOrdinal;
	classicFogBlendDomainLightKind_t kind;
	classicFogBlendDomainLightDisposition_t disposition;
	int			firstSurface;
	int			surfaceCount;
	int			receiverSurfaceCount[ CLASSIC_FOG_BLEND_RECEIVER_COUNT ];
	int			firstLightStage;
	int			lightStageCount;
	int			activeLightStageCount;
	int			inactiveLightStageCount;
	int			noopLightStageCount;
	int			firstPrimitive;
	int			primitiveCount;
	int			drawablePrimitiveCount;
	int			noopPrimitiveCount;
	int			fogReceiverPrimitiveCount;
	int			fogFrustumPrimitiveCount;
	int			blendPrimitiveCount;
	int			scissorX1;
	int			scissorY1;
	int			scissorX2;
	int			scissorY2;
	float			lightProject[ 4 ][ 4 ];
	float			fogPlane[ 4 ];
	float			fogGlobalTexgen[ 2 ][ 2 ][ 4 ];
	float			fogColor[ 4 ];
	float			fogDensity;
	float			fogDistanceScale;
	std::uint64_t	falloffTextureResourceId;
	std::uint64_t	fogTextureResourceId;
	std::uint64_t	fogEnterTextureResourceId;
	bool			globalChainPresent;
	int			materialDeformReceiverCount;
	std::uint64_t	deformContractHash;
	std::uint64_t	hash;
} classicFogBlendDomainLight_t;

typedef struct classicFogBlendDomainPrimitive_s {
	// Geometry submission bridges only. All render semantics are available from
	// this record, its LightStage, and its owning View.
	const drawSurf_t		*legacyDrawSurf;
	const srfTriangles_t	*legacyGeometry;
	int			lightIndex;
	int			lightStageIndex;
	int			surfaceIndex;
	classicFogBlendDomainPrimitiveKind_t kind;
	classicFogBlendDomainReceiver_t receiver;
	classicFogBlendDomainPrimitiveDisposition_t disposition;
	int			geometryRecordIndex;
	int			instanceRecordIndex;
	int			vertexCount;
	int			firstIndex;
	int			indexCount;
	int			vertexOffset;
	int			scissorX1;
	int			scissorY1;
	int			scissorX2;
	int			scissorY2;
	// Depth/cull are repeated per primitive because the fog frustum cap changes
	// from receiver EQUAL/front culling to LESS_OR_EQUAL/back culling while
	// retaining its light stage's blend/color state.
	rendererDepthState_t depth;
	rendererCullMode_t	cull;
	float			modelMatrix[ 16 ];
	float			modelViewMatrix[ 16 ];
	float			localLightProject[ 4 ][ 4 ];
	float			fogTexgen[ 2 ][ 2 ][ 4 ];
	std::uint64_t	hash;
} classicFogBlendDomainPrimitive_t;

typedef struct classicFogBlendDomainBackendCoverage_s {
	std::uint64_t	ownedViewMask;
	std::uint64_t	fallbackViewMask;
	int		ownedViews;
	int		fallbackViews;
	int		ownedLights;
	int		fallbackLights;
	int		ownedSurfaces;
	int		fallbackSurfaces;
	int		ownedFogReceiverPrimitives;
	int		fallbackFogReceiverPrimitives;
	int		ownedFogFrustumPrimitives;
	int		fallbackFogFrustumPrimitives;
	int		ownedBlendPrimitives;
	int		fallbackBlendPrimitives;
	int		ownedNoopPrimitives;
	int		fallbackNoopPrimitives;
	int		ownedNoopLightStages;
	int		fallbackNoopLightStages;
	int		ownedNoopLights;
	int		fallbackNoopLights;
	int		coverageMismatches;
	int		duplicateReports;
	int		untrackedFallbacks;
} classicFogBlendDomainBackendCoverage_t;

typedef struct classicFogBlendDomainView_s {
	const viewDef_t		*viewDef;
	int			scenePacketIndex;
	int			fogBlendPassPacketIndex;
	int			firstLight;
	int			lightCount;
	int			fogLightCount;
	int			blendLightCount;
	int			noopLightCount;
	int			firstSurface;
	int			surfaceCount;
	int			receiverSurfaceCount[ CLASSIC_FOG_BLEND_RECEIVER_COUNT ];
	int			firstLightStage;
	int			lightStageCount;
	int			activeLightStageCount;
	int			inactiveLightStageCount;
	int			noopLightStageCount;
	int			firstPrimitive;
	int			primitiveCount;
	int			drawablePrimitiveCount;
	int			noopPrimitiveCount;
	int			fogReceiverPrimitiveCount;
	int			fogFrustumPrimitiveCount;
	int			blendPrimitiveCount;
	int			packetDrawCount;
	int			materialDeformReceiverCount;
	int			viewportX1;
	int			viewportY1;
	int			viewportX2;
	int			viewportY2;
	int			scissorX1;
	int			scissorY1;
	int			scissorX2;
	int			scissorY2;
	float			projectionMatrix[ 16 ];
	bool			useScissor;
	bool			skipBlendLights;
	bool			ready;
	classicFogBlendDomainFailure_t failure;
	int			failureDetail;
	int			failurePassPacketIndex;
	int			failureDrawPacketIndex;
	int			failureLightOrdinal;
	int			failureReceiverOrdinal;
	int			failureStageIndex;
	std::uint64_t	hash;
	classicFogBlendDomainBackendOutcome_t backendOutcome[
		CLASSIC_FOG_BLEND_BACKEND_COUNT ];
	classicFogBlendDomainFailure_t backendFailure[
		CLASSIC_FOG_BLEND_BACKEND_COUNT ];
	int			backendFailureDetail[
		CLASSIC_FOG_BLEND_BACKEND_COUNT ];
	int			backendFogReceiverPrimitives[
		CLASSIC_FOG_BLEND_BACKEND_COUNT ];
	int			backendFogFrustumPrimitives[
		CLASSIC_FOG_BLEND_BACKEND_COUNT ];
	int			backendBlendPrimitives[
		CLASSIC_FOG_BLEND_BACKEND_COUNT ];
	int			backendNoopPrimitives[
		CLASSIC_FOG_BLEND_BACKEND_COUNT ];
	int			backendNoopLightStages[
		CLASSIC_FOG_BLEND_BACKEND_COUNT ];
	int			backendNoopLights[
		CLASSIC_FOG_BLEND_BACKEND_COUNT ];
} classicFogBlendDomainView_t;

typedef struct classicFogBlendDomainStats_s {
	bool		prepared;
	bool		frameValid;
	bool		overflow;
	int		sourceScenes;
	int		fogBlendViews;
	int		readyViews;
	int		fallbackViews;
	int		lights;
	int		fogLights;
	int		blendLights;
	int		noopLights;
	int		surfaces;
	int		receiverSurfaces[ CLASSIC_FOG_BLEND_RECEIVER_COUNT ];
	int		lightStages;
	int		activeLightStages;
	int		inactiveLightStages;
	int		noopLightStages;
	int		primitives;
	int		drawablePrimitives;
	int		noopPrimitives;
	int		fogReceiverPrimitives;
	int		fogFrustumPrimitives;
	int		blendPrimitives;
	int		textures;
	int		materialDeformReceivers;
	int		failureCounts[ CLASSIC_FOG_BLEND_FAILURE_COUNT ];
	std::uint64_t	hash;
	classicFogBlendDomainBackendCoverage_t backend[
		CLASSIC_FOG_BLEND_BACKEND_COUNT ];
	char		status[ 96 ];
} classicFogBlendDomainStats_t;

void R_ClassicFogBlendDomain_ResetFrame( void );
void R_ClassicFogBlendDomain_PrepareFrame( const idScenePacketFrame &packetFrame );
const classicFogBlendDomainStats_t &R_ClassicFogBlendDomain_Stats( void );
int R_ClassicFogBlendDomain_NumViews( void );
const classicFogBlendDomainView_t *R_ClassicFogBlendDomain_ViewByIndex( int index );
const classicFogBlendDomainView_t *R_ClassicFogBlendDomain_ViewForScenePacket(
	int scenePacketIndex );
const classicFogBlendDomainView_t *R_ClassicFogBlendDomain_FindView(
	const viewDef_t *viewDef );
const classicFogBlendDomainLight_t *R_ClassicFogBlendDomain_ViewLight(
	const classicFogBlendDomainView_t &view, int lightIndex );
const classicFogBlendDomainLightStage_t *R_ClassicFogBlendDomain_LightStage(
	const classicFogBlendDomainLight_t &light, int stageIndex );
const classicFogBlendDomainPrimitive_t *R_ClassicFogBlendDomain_ViewPrimitive(
	const classicFogBlendDomainView_t &view, int primitiveIndex );
const classicFogBlendDomainTexture_t *R_ClassicFogBlendDomain_ResolveTexture(
	std::uint64_t textureResourceId );
bool R_ClassicFogBlendDomain_RecordOwned( const viewDef_t *viewDef,
	classicFogBlendDomainBackend_t backend, int fogReceiverPrimitives,
	int fogFrustumPrimitives, int blendPrimitives, int noopPrimitives,
	int noopLightStages, int noopLights );
void R_ClassicFogBlendDomain_RecordBackendFallback( const viewDef_t *viewDef,
	classicFogBlendDomainBackend_t backend,
	classicFogBlendDomainFailure_t failure, int detail );
const classicFogBlendDomainBackendCoverage_t &
	R_ClassicFogBlendDomain_BackendCoverage(
		classicFogBlendDomainBackend_t backend );
const char *ClassicFogBlendDomainLightKind_Name(
	classicFogBlendDomainLightKind_t kind );
const char *ClassicFogBlendDomainReceiver_Name(
	classicFogBlendDomainReceiver_t receiver );
const char *ClassicFogBlendDomainLightDisposition_Name(
	classicFogBlendDomainLightDisposition_t disposition );
const char *ClassicFogBlendDomainLightStageDisposition_Name(
	classicFogBlendDomainLightStageDisposition_t disposition );
const char *ClassicFogBlendDomainPrimitiveKind_Name(
	classicFogBlendDomainPrimitiveKind_t kind );
const char *ClassicFogBlendDomainPrimitiveDisposition_Name(
	classicFogBlendDomainPrimitiveDisposition_t disposition );
const char *ClassicFogBlendDomainFailure_Name(
	classicFogBlendDomainFailure_t failure );
const char *ClassicFogBlendDomainBackend_Name(
	classicFogBlendDomainBackend_t backend );
bool RendererClassicFogBlendDomain_RunSelfTest( void );

#endif /* !__CLASSIC_FOG_BLEND_DOMAIN_H__ */
