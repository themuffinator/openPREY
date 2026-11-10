// Copyright (C) 2004 Id Software, Inc.
//

#ifndef __MODERN_GL_SUBMIT_PLAN_H__
#define __MODERN_GL_SUBMIT_PLAN_H__

#include "ModernGLDrawPlan.h"

const int MODERN_GL_SUBMIT_PLAN_MAX_COMMANDS = MODERN_GL_DRAW_PLAN_MAX_ENTRIES;
const int MODERN_GL_SUBMIT_MATERIAL_TEXTURE_MAIN = 0;
const int MODERN_GL_SUBMIT_MATERIAL_TEXTURE_NORMAL = 1;
const int MODERN_GL_SUBMIT_MATERIAL_TEXTURE_SPECULAR = 2;
const int MODERN_GL_SUBMIT_MATERIAL_TEXTURE_EMISSIVE = 3;
// PBR's separate metallic/roughness/AO layout uses these direct samplers.
// They stay below the texture-array/shadow range, so this fits the GL 3.3
// floor without overlapping a cubemap shadow sampler.
const int MODERN_GL_SUBMIT_MATERIAL_TEXTURE_METALLIC = 4;
const int MODERN_GL_SUBMIT_MATERIAL_TEXTURE_ROUGHNESS = 5;
const int MODERN_GL_SUBMIT_MATERIAL_TEXTURE_AO = 6;
const int MODERN_GL_SUBMIT_MATERIAL_TEXTURE_COUNT = 7;

typedef struct modernGLSubmitCommand_s {
	const modernGLDrawPlanEntry_t *drawPlanEntry;
	const materialResourceTableRecord_t *materialRecord;
	const viewDef_t			*viewDef;
	renderPassCategory_t		passCategory;
	modernGLDrawPlanPipeline_t	pipeline;
	modernGLShaderProgramKind_t	shaderKind;
	unsigned int				program;
	unsigned int				vertexBuffer;
	unsigned int				indexBuffer;
	const void					*clientIndexData;
	int							ambientCacheOffset;
	int							indexCacheOffset;
	int							clientIndexBytes;
	int							modelViewProjectionLocation;
	int							modelViewMatrixLocation;
	int							debugColorLocation;
	int							localParamsLocation;
	int							pbrIBLLocation;
	int							bakedGridLocation;
	int							mainTextureLocation;
	int							normalTextureLocation;
	int							specularTextureLocation;
	int							emissiveTextureLocation;
	int							metallicTextureLocation;
	int							roughnessTextureLocation;
	int							aoTextureLocation;
	int							textureIndicesLocation;
	int							textureTableModeLocation;
	int							materialFlagsLocation;
	int							materialEnhancementLocation;
	int							drawRecordModeLocation;
	int							drawRecordCountLocation;
	int							vertexStride;
	int							indexType;
	int							indexCount;
	int							vertexCount;
	int							materialRecordIndex;
	int							materialTableIndex;
	int							geometryRecordIndex;
	int							instanceRecordIndex;
	unsigned int				materialTextureHandles[MODERN_GL_SUBMIT_MATERIAL_TEXTURE_COUNT];
	int							materialTextureTableIndices[MODERN_GL_SUBMIT_MATERIAL_TEXTURE_COUNT];
	unsigned int				materialLoadedTextureSemanticMask;
	materialResourceBlendMode_t	blendMode;
	int							cullType;
	int							materialAlphaTestRegister;
	int							originalSubmitOrder;
	int							sortBucket;
	int							cullSortKey;
	unsigned int				materialStableId;
	float						modelViewMatrix[16];
	float						modelViewProjectionMatrix[16];
	float						modelDepthHack;
	int							scissorX1;
	int							scissorY1;
	int							scissorX2;
	int							scissorY2;
	int							visibilityScreenX1;
	int							visibilityScreenY1;
	int							visibilityScreenX2;
	int							visibilityScreenY2;
	float						visibilityDepthMin;
	float						visibilityDepthMax;
	bool						indexed;
	bool						uploadIndexBuffer;
	bool						twoSided;
	bool						shouldCreateBackSides;
	bool						weaponDepthHack;
	bool						negativeScale;
	bool						visibilityBoundsValid;
	bool						visibilityFrustumEligible;
	bool						visibilityFrustumRejected;
	bool						visibilityScreenRectValid;
	bool						visibilityNearPlaneClipped;
	bool						visibilityHiZCandidate;
	bool						visibilityDynamic;
	bool						visibilityShadowCaster;
	bool						sortEligible;
	bool						forwardPlusDecal;
	bool						alphaTestMaterial;
	bool						alphaTestOrPerforatedMaterial;
} modernGLSubmitCommand_t;

typedef struct modernGLSubmitPlanStats_s {
	bool	available;
	bool	valid;
	bool	overflow;
	int		sourcePlanDraws;
	int		readyDraws;
	int		fallbackDraws;
	int		depthReadyDraws;
	int		materialReadyDraws;
	int		indexedReadyDraws;
	int		vertexOnlyReadyDraws;
	int		missingDrawPacketDraws;
	int		missingGeometryDraws;
	int		missingAmbientCacheDraws;
	int		missingIndexCacheDraws;
	int		clientVertexFallbackDraws;
	int		indexCacheReadyDraws;
	int		indexUploadDraws;
	int		programBatches;
	int		vertexBufferBatches;
	int		indexBufferBatches;
	int		scissorBatches;
	int		materialBatches;
	int		sortEligibleDraws;
	int		sortLockedDraws;
	int		sortSpans;
	int		sortBuckets;
	int		sortReorderedDraws;
	int		unsortedStateBuckets;
	int		sortedStateBuckets;
	int		sortStateBucketSavings;
	int		sortProgramBatchSavings;
	int		sortMaterialBatchSavings;
	int		sortVertexBufferBatchSavings;
	int		uniformUpdates;
	int		frameUBOBinds;
	int		highestGLSLVersion;
	char	status[96];
} modernGLSubmitPlanStats_t;

class idModernGLSubmitPlan {
public:
	idModernGLSubmitPlan();
	void Clear( void );
	bool Build( const idModernGLDrawPlan &drawPlan );

	int NumCommands( void ) const;
	const modernGLSubmitCommand_t &Command( int index ) const;
	const modernGLSubmitPlanStats_t &Stats( void ) const;

private:
	bool AddCommand( const modernGLDrawPlanEntry_t &entry );

	modernGLSubmitCommand_t commands[MODERN_GL_SUBMIT_PLAN_MAX_COMMANDS];
	modernGLSubmitPlanStats_t stats;
	int numCommands;
};

// builds command.modelViewProjectionMatrix from the command's view projection,
// model-view matrix, and depth-hack state; safe to call once at plan-build time
void R_ModernGLSubmitCommand_BuildModelViewProjection( modernGLSubmitCommand_t &command );

bool RendererModernGLSubmitPlan_RunSelfTest( void );

#endif /* !__MODERN_GL_SUBMIT_PLAN_H__ */
