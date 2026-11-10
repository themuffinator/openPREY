// Copyright (C) 2026 DarkMatter Productions
//

#ifndef __RENDERER_CONTRACTS_H__
#define __RENDERER_CONTRACTS_H__

#include <cstddef>
#include <cstdint>

/*
===============================================================================

	Backend-neutral renderer contracts.

	This header deliberately contains no idlib, OpenGL, or Vulkan types.  The
	front end can therefore describe material work, clip-space conversion,
	vertex input, and buffer slices once while each backend retains ownership of
	its native objects.

===============================================================================
*/

const std::uint32_t RENDERER_CONTRACT_MAX_MATERIAL_PASSES = 256;
const std::uint32_t RENDERER_CONTRACT_MAX_VERTEX_BINDINGS = 3;
const std::uint32_t RENDERER_CONTRACT_MAX_VERTEX_ATTRIBUTES = 10;

enum rendererRegisterSource_t : int {
	RENDERER_REGISTER_UNUSED = 0,
	RENDERER_REGISTER_INDEX,
	RENDERER_REGISTER_CONSTANT
};

typedef struct rendererRegisterRef_s {
	rendererRegisterSource_t	source;
	std::int32_t				index;
	float					constantValue;
} rendererRegisterRef_t;

rendererRegisterRef_t RendererContracts_UnusedRegister( void );
rendererRegisterRef_t RendererContracts_Register( std::int32_t index );
rendererRegisterRef_t RendererContracts_Constant( float value );

enum rendererMaterialPassKind_t : int {
	RENDERER_MATERIAL_PASS_SURFACE = 0,
	RENDERER_MATERIAL_PASS_DEPTH,
	RENDERER_MATERIAL_PASS_INTERACTION,
	RENDERER_MATERIAL_PASS_SHADOW,
	RENDERER_MATERIAL_PASS_GUI,
	RENDERER_MATERIAL_PASS_POST_PROCESS
};

enum rendererMaterialTextureSemantic_t : int {
	RENDERER_TEXTURE_NONE = 0,
	RENDERER_TEXTURE_DIFFUSE,
	RENDERER_TEXTURE_NORMAL,
	RENDERER_TEXTURE_SPECULAR,
	RENDERER_TEXTURE_HEIGHT,
	RENDERER_TEXTURE_EMISSIVE,
	RENDERER_TEXTURE_LIGHT,
	RENDERER_TEXTURE_FALLOFF,
	RENDERER_TEXTURE_CURRENT_RENDER,
	RENDERER_TEXTURE_CURRENT_DEPTH,
	RENDERER_TEXTURE_CUBE,
	RENDERER_TEXTURE_CUSTOM
};

enum rendererBlendFactor_t : int {
	RENDERER_BLEND_ZERO = 0,
	RENDERER_BLEND_ONE,
	RENDERER_BLEND_SRC_COLOR,
	RENDERER_BLEND_ONE_MINUS_SRC_COLOR,
	RENDERER_BLEND_DST_COLOR,
	RENDERER_BLEND_ONE_MINUS_DST_COLOR,
	RENDERER_BLEND_SRC_ALPHA,
	RENDERER_BLEND_ONE_MINUS_SRC_ALPHA,
	RENDERER_BLEND_DST_ALPHA,
	RENDERER_BLEND_ONE_MINUS_DST_ALPHA,
	RENDERER_BLEND_SRC_ALPHA_SATURATE
};

enum rendererBlendOp_t : int {
	RENDERER_BLEND_OP_ADD = 0,
	RENDERER_BLEND_OP_SUBTRACT,
	RENDERER_BLEND_OP_REVERSE_SUBTRACT,
	RENDERER_BLEND_OP_MIN,
	RENDERER_BLEND_OP_MAX
};

typedef struct rendererBlendState_s {
	bool				enabled;
	rendererBlendFactor_t	sourceColor;
	rendererBlendFactor_t	destinationColor;
	rendererBlendOp_t	colorOperation;
	rendererBlendFactor_t	sourceAlpha;
	rendererBlendFactor_t	destinationAlpha;
	rendererBlendOp_t	alphaOperation;
} rendererBlendState_t;

enum rendererCompareOp_t : int {
	RENDERER_COMPARE_NEVER = 0,
	RENDERER_COMPARE_LESS,
	RENDERER_COMPARE_EQUAL,
	RENDERER_COMPARE_LESS_OR_EQUAL,
	RENDERER_COMPARE_GREATER,
	RENDERER_COMPARE_NOT_EQUAL,
	RENDERER_COMPARE_GREATER_OR_EQUAL,
	RENDERER_COMPARE_ALWAYS
};

typedef struct rendererDepthState_s {
	bool				testEnabled;
	bool				writeEnabled;
	rendererCompareOp_t	compareOperation;
} rendererDepthState_t;

enum rendererCullMode_t : int {
	RENDERER_CULL_NONE = 0,
	RENDERER_CULL_FRONT,
	RENDERER_CULL_BACK
};

enum rendererColorWriteMask_t : int {
	RENDERER_COLOR_WRITE_RED = 1u << 0,
	RENDERER_COLOR_WRITE_GREEN = 1u << 1,
	RENDERER_COLOR_WRITE_BLUE = 1u << 2,
	RENDERER_COLOR_WRITE_ALPHA = 1u << 3,
	RENDERER_COLOR_WRITE_RGBA = RENDERER_COLOR_WRITE_RED
		| RENDERER_COLOR_WRITE_GREEN
		| RENDERER_COLOR_WRITE_BLUE
		| RENDERER_COLOR_WRITE_ALPHA
};

enum rendererTexGen_t : int {
	RENDERER_TEXGEN_EXPLICIT = 0,
	RENDERER_TEXGEN_SCREEN,
	RENDERER_TEXGEN_SKYBOX_CUBE,
	RENDERER_TEXGEN_WOBBLESKY_CUBE,
	RENDERER_TEXGEN_DIFFUSE_CUBE,
	RENDERER_TEXGEN_REFLECT_CUBE,
	RENDERER_TEXGEN_GLASS_WARP
};

enum rendererVertexColorMode_t : int {
	RENDERER_VERTEX_COLOR_IGNORE = 0,
	RENDERER_VERTEX_COLOR_MODULATE,
	RENDERER_VERTEX_COLOR_INVERSE_MODULATE
};

enum rendererMaterialProgramFamily_t : int {
	RENDERER_PROGRAM_FIXED = 0,
	RENDERER_PROGRAM_DEPTH,
	RENDERER_PROGRAM_AMBIENT,
	RENDERER_PROGRAM_INTERACTION,
	RENDERER_PROGRAM_SHADOW,
	RENDERER_PROGRAM_GUI,
	RENDERER_PROGRAM_HEAT_HAZE,
	RENDERER_PROGRAM_MONOCHROME,
	RENDERER_PROGRAM_REFRACTIVE,
	RENDERER_PROGRAM_CUSTOM
};

enum rendererMaterialPassDisposition_t : int {
	RENDERER_MATERIAL_PASS_DRAW = 0,
	RENDERER_MATERIAL_PASS_INACTIVE_CONDITION,
	RENDERER_MATERIAL_PASS_NOOP_ZERO_ONE_BLEND,
	RENDERER_MATERIAL_PASS_NOOP_BLACK_ADDITIVE,
	RENDERER_MATERIAL_PASS_NOOP_TRANSPARENT_ALPHA
};

typedef struct rendererMaterialPass_s {
	std::uint32_t				order;
	std::int32_t				sourceStageIndex;
	rendererMaterialPassKind_t		kind;
	rendererMaterialTextureSemantic_t	textureSemantic;
	std::uint64_t				textureResourceId;
	rendererRegisterRef_t			condition;
	rendererRegisterRef_t			color[ 4 ];
	rendererRegisterRef_t			textureMatrix[ 6 ];
	rendererBlendState_t			blend;
	rendererDepthState_t			depth;
	rendererCullMode_t			cull;
	std::uint32_t				colorWriteMask;
	bool					alphaTestEnabled;
	rendererCompareOp_t			alphaTestCompareOperation;
	rendererRegisterRef_t			alphaTest;
	rendererTexGen_t			texgen;
	rendererVertexColorMode_t		vertexColor;
	bool					polygonOffsetEnabled;
	rendererRegisterRef_t			polygonOffsetFactor;
	rendererRegisterRef_t			polygonOffsetUnits;
	rendererMaterialProgramFamily_t	programFamily;
	std::uint32_t				programKey;
} rendererMaterialPass_t;

typedef struct rendererMaterialPassList_s {
	std::uint32_t		count;
	bool			overflowed;
	rendererMaterialPass_t	passes[ RENDERER_CONTRACT_MAX_MATERIAL_PASSES ];
} rendererMaterialPassList_t;

rendererMaterialPass_t RendererContracts_DefaultMaterialPass( void );
void RendererContracts_ResetMaterialPassList( rendererMaterialPassList_t &list );
bool RendererContracts_ValidateMaterialPass( const rendererMaterialPass_t &pass );
bool RendererContracts_AppendMaterialPass( rendererMaterialPassList_t &list,
	const rendererMaterialPass_t &pass );

/*
 * Per-draw material state after register references have been resolved.  This
 * deliberately retains the source identity and immutable render state from the
 * authored pass while replacing register references with compact scalar data.
 * Inactive and recognized no-op passes remain in the ordered list so backends
 * cannot disagree about which source stage occupied a given position.  The
 * active flag reflects only the authored condition; disposition determines
 * whether an active pass can affect the framebuffer.
 */
typedef struct rendererEvaluatedMaterialPass_s {
	std::uint32_t				order;
	std::int32_t				sourceStageIndex;
	rendererMaterialPassKind_t		kind;
	rendererMaterialTextureSemantic_t	textureSemantic;
	std::uint64_t				textureResourceId;
	float					condition;
	bool					active;
	rendererMaterialPassDisposition_t	disposition;
	float					color[ 4 ];
	float					textureMatrix[ 6 ];
	rendererBlendState_t			blend;
	rendererDepthState_t			depth;
	rendererCullMode_t			cull;
	std::uint32_t				colorWriteMask;
	bool					alphaTestEnabled;
	rendererCompareOp_t			alphaTestCompareOperation;
	float					alphaTest;
	rendererTexGen_t			texgen;
	rendererVertexColorMode_t		vertexColor;
	bool					polygonOffsetEnabled;
	float					polygonOffsetFactor;
	float					polygonOffsetUnits;
	rendererMaterialProgramFamily_t	programFamily;
	std::uint32_t				programKey;
} rendererEvaluatedMaterialPass_t;

typedef struct rendererEvaluatedMaterialPassList_s {
	std::uint32_t			count;
	std::uint32_t			activeCount;
	rendererEvaluatedMaterialPass_t	passes[ RENDERER_CONTRACT_MAX_MATERIAL_PASSES ];
} rendererEvaluatedMaterialPassList_t;

enum rendererMaterialPassEvaluationStatus_t : int {
	RENDERER_MATERIAL_PASS_EVALUATION_SUCCESS = 0,
	RENDERER_MATERIAL_PASS_EVALUATION_SOURCE_OVERFLOW,
	RENDERER_MATERIAL_PASS_EVALUATION_INVALID_PASS,
	RENDERER_MATERIAL_PASS_EVALUATION_REGISTERS_UNAVAILABLE,
	RENDERER_MATERIAL_PASS_EVALUATION_REGISTER_OUT_OF_RANGE,
	RENDERER_MATERIAL_PASS_EVALUATION_NONFINITE_VALUE
};

void RendererContracts_ResetEvaluatedMaterialPassList(
	rendererEvaluatedMaterialPassList_t &list );

/*
 * Resolves one ordered material list against a bounded per-draw register array.
 * An exactly zero condition produces a valid inactive pass, while recognized
 * classic blend/color no-ops receive an explicit disposition.  Any malformed
 * pass, unavailable/out-of-range register, non-finite value, or overflow
 * rejects the complete list and resets destination, so consumers never see
 * partial state.  Constant-only and empty lists may be evaluated with no
 * register array.
 */
rendererMaterialPassEvaluationStatus_t RendererContracts_EvaluateMaterialPassList(
	rendererEvaluatedMaterialPassList_t &destination,
	const rendererMaterialPassList_t &source,
	const float *registers, std::uint32_t registerCount );

enum rendererClipDepthRange_t : int {
	RENDERER_CLIP_DEPTH_NEGATIVE_ONE_TO_ONE = 0,
	RENDERER_CLIP_DEPTH_ZERO_TO_ONE
};

enum rendererFramebufferOrigin_t : int {
	RENDERER_FRAMEBUFFER_ORIGIN_LOWER_LEFT = 0,
	RENDERER_FRAMEBUFFER_ORIGIN_UPPER_LEFT
};

enum rendererViewportYAxis_t : int {
	RENDERER_VIEWPORT_Y_POSITIVE = 0,
	RENDERER_VIEWPORT_Y_NEGATIVE
};

enum rendererFrontFace_t : int {
	RENDERER_FRONT_FACE_COUNTER_CLOCKWISE = 0,
	RENDERER_FRONT_FACE_CLOCKWISE
};

typedef struct rendererClipSpaceConvention_s {
	rendererClipDepthRange_t	depthRange;
	rendererFramebufferOrigin_t	framebufferOrigin;
	rendererViewportYAxis_t	viewportYAxis;
	rendererFrontFace_t		frontFace;
} rendererClipSpaceConvention_t;

typedef struct rendererCanonicalViewport_s {
	float	x;
	float	y;
	float	width;
	float	height;
	float	minDepth;
	float	maxDepth;
} rendererCanonicalViewport_t;

typedef struct rendererBackendViewport_s {
	float	x;
	float	y;
	float	width;
	float	height;
	float	minDepth;
	float	maxDepth;
} rendererBackendViewport_t;

rendererClipSpaceConvention_t RendererContracts_GLClipSpace( void );
rendererClipSpaceConvention_t RendererContracts_VulkanClipSpace( void );
bool RendererContracts_ConvertClipMatrix( float destination[ 16 ],
	const float source[ 16 ], const rendererClipSpaceConvention_t &sourceConvention,
	const rendererClipSpaceConvention_t &destinationConvention );
bool RendererContracts_BuildViewport( rendererBackendViewport_t &destination,
	const rendererCanonicalViewport_t &source, float framebufferHeight,
	const rendererClipSpaceConvention_t &destinationConvention );

enum rendererVertexSemantic_t : int {
	RENDERER_VERTEX_SEMANTIC_POSITION = 0,
	RENDERER_VERTEX_SEMANTIC_COLOR0,
	RENDERER_VERTEX_SEMANTIC_NORMAL,
	RENDERER_VERTEX_SEMANTIC_TANGENT0,
	RENDERER_VERTEX_SEMANTIC_TANGENT1,
	RENDERER_VERTEX_SEMANTIC_TEXCOORD0,
	RENDERER_VERTEX_SEMANTIC_JOINT_INDICES,
	RENDERER_VERTEX_SEMANTIC_JOINT_WEIGHTS
};

enum rendererVertexFormat_t : int {
	RENDERER_VERTEX_FORMAT_FLOAT32X2 = 0,
	RENDERER_VERTEX_FORMAT_FLOAT32X3,
	RENDERER_VERTEX_FORMAT_FLOAT32X4,
	RENDERER_VERTEX_FORMAT_UNORM8X4,
	RENDERER_VERTEX_FORMAT_UINT32X4
};

enum rendererVertexInputRate_t : int {
	RENDERER_VERTEX_RATE_PER_VERTEX = 0,
	RENDERER_VERTEX_RATE_PER_INSTANCE
};

typedef struct rendererVertexBindingDesc_s {
	std::uint32_t			binding;
	std::uint32_t			stride;
	rendererVertexInputRate_t	inputRate;
} rendererVertexBindingDesc_t;

typedef struct rendererVertexAttributeDesc_s {
	rendererVertexSemantic_t	semantic;
	rendererVertexFormat_t		format;
	std::uint32_t			binding;
	std::uint32_t			offset;
} rendererVertexAttributeDesc_t;

typedef struct rendererVertexLayoutDesc_s {
	std::uint32_t			bindingCount;
	std::uint32_t			attributeCount;
	rendererVertexBindingDesc_t	bindings[ RENDERER_CONTRACT_MAX_VERTEX_BINDINGS ];
	rendererVertexAttributeDesc_t	attributes[ RENDERER_CONTRACT_MAX_VERTEX_ATTRIBUTES ];
} rendererVertexLayoutDesc_t;

const rendererVertexLayoutDesc_t &RendererContracts_LegacyDrawVertLayout( void );
const rendererVertexLayoutDesc_t &RendererContracts_SkinnedDrawVertLayout( void );
std::uint32_t RendererContracts_VertexFormatSize( rendererVertexFormat_t format );
bool RendererContracts_ValidateVertexLayout( const rendererVertexLayoutDesc_t &layout );
const rendererVertexAttributeDesc_t *RendererContracts_FindVertexAttribute(
	const rendererVertexLayoutDesc_t &layout, rendererVertexSemantic_t semantic );

enum rendererBufferKind_t : int {
	RENDERER_BUFFER_KIND_VERTEX = 1,
	RENDERER_BUFFER_KIND_INDEX,
	RENDERER_BUFFER_KIND_UNIFORM,
	RENDERER_BUFFER_KIND_STORAGE,
	RENDERER_BUFFER_KIND_JOINT_PALETTE
};

enum rendererBufferLifetime_t : int {
	RENDERER_BUFFER_LIFETIME_STATIC = 1,
	RENDERER_BUFFER_LIFETIME_FRAME
};

typedef struct rendererBufferHandle_s {
	std::uint64_t value;
} rendererBufferHandle_t;

typedef struct rendererBufferRecord_s {
	rendererBufferHandle_t	handle;
	std::uint64_t		capacityBytes;
	std::uint64_t		frameSerial;
} rendererBufferRecord_t;

typedef struct rendererBufferSlice_s {
	rendererBufferHandle_t	handle;
	std::uint64_t		offsetBytes;
	std::uint64_t		sizeBytes;
} rendererBufferSlice_t;

enum rendererBufferSliceValidation_t : int {
	RENDERER_BUFFER_SLICE_VALID = 0,
	RENDERER_BUFFER_SLICE_INVALID_HANDLE,
	RENDERER_BUFFER_SLICE_WRONG_SLOT,
	RENDERER_BUFFER_SLICE_STALE_GENERATION,
	RENDERER_BUFFER_SLICE_WRONG_KIND,
	RENDERER_BUFFER_SLICE_WRONG_LIFETIME,
	RENDERER_BUFFER_SLICE_EXPIRED,
	RENDERER_BUFFER_SLICE_EMPTY,
	RENDERER_BUFFER_SLICE_RANGE_OVERFLOW
};

rendererBufferHandle_t RendererContracts_InvalidBufferHandle( void );
rendererBufferHandle_t RendererContracts_MakeBufferHandle( rendererBufferKind_t kind,
	rendererBufferLifetime_t lifetime, std::uint32_t slot, std::uint32_t generation );
bool RendererContracts_DecodeBufferHandle( rendererBufferHandle_t handle,
	rendererBufferKind_t &kind, rendererBufferLifetime_t &lifetime,
	std::uint32_t &slot, std::uint32_t &generation );
rendererBufferSliceValidation_t RendererContracts_ValidateBufferSlice(
	const rendererBufferSlice_t &slice, const rendererBufferRecord_t &record,
	rendererBufferKind_t expectedKind, std::uint64_t currentFrameSerial );
bool RendererContracts_RunSelfTest( void );

#endif /* !__RENDERER_CONTRACTS_H__ */
