// Copyright (C) 2026 DarkMatter Productions
//

#ifndef __GPU_SKINNING_H__
#define __GPU_SKINNING_H__

#include "RendererCaps.h"

class idDrawVert;
struct srfTriangles_s;

static const int GPU_SKINNING_INFLUENCES = 4;
static const int GPU_SKINNING_JOINT_FLOATS = 12;
static const int GPU_SKINNING_MAX_JOINTS = 65536;

enum gpuSkinningFallbackReason_t {
	GPU_SKINNING_FALLBACK_NONE = 0,
	GPU_SKINNING_FALLBACK_DISABLED,
	GPU_SKINNING_FALLBACK_BACKEND_UNAVAILABLE,
	GPU_SKINNING_FALLBACK_MISSING_BIND_POSE,
	GPU_SKINNING_FALLBACK_MISSING_SKIN_VERTICES,
	GPU_SKINNING_FALLBACK_VERTEX_COUNT,
	GPU_SKINNING_FALLBACK_RESIDUAL_WEIGHTS,
	GPU_SKINNING_FALLBACK_JOINT_COUNT,
	GPU_SKINNING_FALLBACK_JOINT_INDEX,
	GPU_SKINNING_FALLBACK_MALFORMED_WEIGHTS,
	GPU_SKINNING_FALLBACK_SKIN_SCALE,
	GPU_SKINNING_FALLBACK_UNSUPPORTED_MATERIAL,
	GPU_SKINNING_FALLBACK_UNSUPPORTED_PASS,
	GPU_SKINNING_FALLBACK_STENCIL_VOLUME,
	GPU_SKINNING_FALLBACK_DECAL_OVERLAY,
	GPU_SKINNING_FALLBACK_PALETTE_ALLOCATION,
	GPU_SKINNING_FALLBACK_STALE_PALETTE,
	GPU_SKINNING_FALLBACK_COUNT
};

typedef struct gpuSkinningVertex_s {
	uint32	jointIndices[ GPU_SKINNING_INFLUENCES ];
	float	jointWeights[ GPU_SKINNING_INFLUENCES ];
} gpuSkinningVertex_t;

typedef struct gpuSkinningInfluence_s {
	uint32	jointIndex;
	float	weight;
} gpuSkinningInfluence_t;

typedef struct gpuSkinningPackResult_s {
	gpuSkinningFallbackReason_t	reason;
	int		meaningfulInfluences;
	uint32	maxJointIndex;
	float	totalAbsoluteWeight;
	float	residualAbsoluteWeight;
} gpuSkinningPackResult_t;

// Backend objects are intentionally opaque to the shared front end. A zero
// generation is always invalid; context/device recreation advances generation.
typedef struct gpuSkinningBufferHandle_s {
	uint32		generation;
	uint32		frameSlot;
	uint32		offsetBytes;
	uint32		sizeBytes;
	uint64		backendObject;
} gpuSkinningBufferHandle_t;

typedef struct gpuSkinningJointPalette_s {
	const float *	matrices;
	int			numJoints;
	int			matrixStrideFloats;
	uint32			generation;
	gpuSkinningBufferHandle_t buffer;
} gpuSkinningJointPalette_t;

typedef struct gpuSkinningSurface_s {
	const idDrawVert *		bindPoseVerts;
	const gpuSkinningVertex_t *skinVerts;
	int					numVerts;
	gpuSkinningJointPalette_t palette;
	gpuSkinningFallbackReason_t fallbackReason;
	bool					signedWeights;
	// Joint bound the source model validated every packed influence against
	// when it built the immutable sidecar; 0 validates every vertex per use.
	int					prevalidatedJoints;
} gpuSkinningSurface_t;

typedef struct gpuSkinningStats_s {
	uint64	packedVertices;
	uint64	exactVertices;
	uint64	surfaceAttempts;
	uint64	surfacesAdmitted;
	uint64	backendPrepared;
	uint64	preparedVertices;
	uint64	paletteUploads;
	uint64	paletteJoints;
	uint64	paletteBytes;
	uint64	cpuSkinVertices;
	uint64	cpuSkinMicroseconds;
	uint64	cpuPositionOnlyVertices;
	uint64	cpuPositionOnlyMicroseconds;
	uint64	fallbacks[ GPU_SKINNING_FALLBACK_COUNT ];
} gpuSkinningStats_t;

extern idCVar r_gpuSkinning;

const char *R_GpuSkinning_FallbackName( gpuSkinningFallbackReason_t reason );
uint32 R_GpuSkinning_ContractGeneration( void );
uint64 R_GpuSkinning_ReadMicroseconds( void );

bool R_GpuSkinning_PackVertexExact( const gpuSkinningInfluence_t *influences,
	int numInfluences, int numJoints, bool allowSignedWeights,
	gpuSkinningVertex_t &packed, gpuSkinningPackResult_t &result );

bool R_GpuSkinning_DeformVertexCPU( const idDrawVert &bindPose,
	const gpuSkinningVertex_t &skinVertex, const gpuSkinningJointPalette_t &palette,
	idDrawVert &deformed );
bool R_GpuSkinning_CompareVertexCPU( const idDrawVert &expected,
	const idDrawVert &actual, float positionEpsilon, float basisEpsilon );

void R_GpuSkinning_ClearSurfaceContract( srfTriangles_s *tri,
	gpuSkinningFallbackReason_t reason );
bool R_GpuSkinning_AttachSurfaceContract( srfTriangles_s *tri,
	const idDrawVert *bindPoseVerts, const gpuSkinningVertex_t *skinVerts,
	int numVerts, const float *jointMatrices, int numJoints,
	int sourceMatrixStrideFloats, bool signedWeights,
	gpuSkinningFallbackReason_t sourceFallback = GPU_SKINNING_FALLBACK_NONE,
	int sidecarJointBound = 0 );
void R_GpuSkinning_ReferenceSurfaceContract( srfTriangles_s *tri,
	const srfTriangles_s *reference );
bool R_GpuSkinning_GetSurface( const srfTriangles_s *tri,
	gpuSkinningSurface_t &surface );
bool R_GpuSkinning_IsCandidate( const srfTriangles_s *tri );
gpuSkinningFallbackReason_t R_GpuSkinning_ValidateSurface(
	const gpuSkinningSurface_t &surface );

void R_GpuSkinning_RecordCpuSkinning( uint64 elapsedMicroseconds,
	int numVerts, bool positionsOnly );
void R_GpuSkinning_RecordFallback( gpuSkinningFallbackReason_t reason );
void R_GpuSkinning_RecordBackendPrepared( int numVerts );
void R_GpuSkinning_RecordBackendPrepared( int numVerts, int numJoints,
	uint64 paletteBytes );
const gpuSkinningStats_t &R_GpuSkinning_GetStats( void );

void R_GpuSkinning_ContractInit( const renderBackendCaps_t &caps );
void R_GpuSkinning_ContractShutdown( void );
bool R_GpuSkinning_PrepareAmbientCache( srfTriangles_s *tri, bool needsLighting );
void R_GpuSkinning_PrintGfxInfo( void );
bool R_GpuSkinning_RunSelfTest( void );

// Implemented once by each backend module. The shared gate validates the
// surface before it reaches this seam; false requests the existing CPU cache.
// A backend that skins the surface later in the frame instead (Vulkan) sets
// tri->gpuSkinningDeferred before returning false: the front end then builds
// that CPU cache from current positions without deriving normals/tangents,
// and the backend must complete it on the CPU before any draw reads it if its
// dispatch is refused.
void R_BackendGpuSkinning_Init( const renderBackendCaps_t &caps );
void R_BackendGpuSkinning_Shutdown( void );
bool R_BackendGpuSkinning_PrepareAmbientCache( srfTriangles_s *tri, bool needsLighting );
void R_BackendGpuSkinning_PrintGfxInfo( void );

#endif
