// Copyright (C) 2026 DarkMatter Productions
//

#include "src/renderer/RendererContracts.h"

#include <cmath>
#include <cstdio>
#include <cstring>
#include <limits>

static int failures = 0;

static void Check( bool condition, const char *message ) {
	if ( condition ) {
		return;
	}
	std::fprintf( stderr, "RendererContractsTest: %s\n", message );
	failures++;
}

static bool NearlyEqual( float a, float b ) {
	return std::fabs( a - b ) <= 0.00001f;
}

static void ExerciseMaterialPassContract( void ) {
	rendererMaterialPassList_t list;
	RendererContracts_ResetMaterialPassList( list );

	rendererMaterialPass_t first = RendererContracts_DefaultMaterialPass();
	Check( first.blend.sourceColor == RENDERER_BLEND_ONE
			&& first.blend.destinationColor == RENDERER_BLEND_ZERO
			&& first.alphaTestCompareOperation == RENDERER_COMPARE_GREATER,
		"default material pass blend and alpha-test comparison changed" );
	first.sourceStageIndex = 3;
	first.kind = RENDERER_MATERIAL_PASS_SURFACE;
	first.textureSemantic = RENDERER_TEXTURE_DIFFUSE;
	first.textureResourceId = 0x101u;
	first.condition = RendererContracts_Register( 7 );
	for ( int i = 0; i < 4; ++i ) {
		first.color[ i ] = RendererContracts_Register( 10 + i );
	}
	for ( int i = 0; i < 6; ++i ) {
		first.textureMatrix[ i ] = RendererContracts_Register( 20 + i );
	}
	first.blend.enabled = true;
	first.blend.sourceColor = RENDERER_BLEND_SRC_ALPHA;
	first.blend.destinationColor = RENDERER_BLEND_ONE_MINUS_SRC_ALPHA;
	first.blend.sourceAlpha = RENDERER_BLEND_SRC_ALPHA_SATURATE;
	first.depth.testEnabled = true;
	first.depth.writeEnabled = false;
	first.depth.compareOperation = RENDERER_COMPARE_EQUAL;
	first.cull = RENDERER_CULL_FRONT;
	first.colorWriteMask = RENDERER_COLOR_WRITE_RED | RENDERER_COLOR_WRITE_GREEN;
	first.alphaTestEnabled = true;
	first.alphaTestCompareOperation = RENDERER_COMPARE_GREATER_OR_EQUAL;
	first.alphaTest = RendererContracts_Register( 31 );
	first.texgen = RENDERER_TEXGEN_SCREEN;
	first.vertexColor = RENDERER_VERTEX_COLOR_MODULATE;
	first.polygonOffsetEnabled = true;
	first.polygonOffsetFactor = RendererContracts_Register( 32 );
	first.polygonOffsetUnits = RendererContracts_Constant( 2.0f );
	first.programFamily = RENDERER_PROGRAM_CUSTOM;
	first.programKey = 0x33445566u;

	rendererMaterialPass_t second = RendererContracts_DefaultMaterialPass();
	second.sourceStageIndex = 9;
	second.textureSemantic = RENDERER_TEXTURE_DIFFUSE;
	second.textureResourceId = 0x202u;
	second.condition = RendererContracts_Register( 41 );

	Check( RendererContracts_AppendMaterialPass( list, first ),
		"first material pass must append" );
	Check( RendererContracts_AppendMaterialPass( list, second ),
		"repeated texture semantic must append" );
	Check( list.count == 2 && list.passes[ 0 ].order == 0 && list.passes[ 1 ].order == 1,
		"material pass insertion order must be stable" );
	Check( list.passes[ 0 ].textureSemantic == RENDERER_TEXTURE_DIFFUSE
			&& list.passes[ 1 ].textureSemantic == RENDERER_TEXTURE_DIFFUSE
			&& list.passes[ 0 ].textureResourceId == 0x101u
			&& list.passes[ 1 ].textureResourceId == 0x202u,
		"repeated semantics must remain distinct" );
	Check( list.passes[ 0 ].condition.index == 7
			&& list.passes[ 0 ].color[ 3 ].index == 13
			&& list.passes[ 0 ].textureMatrix[ 5 ].index == 25
			&& list.passes[ 0 ].alphaTest.index == 31
			&& list.passes[ 0 ].polygonOffsetFactor.index == 32,
		"material register references must survive append" );
	Check( list.passes[ 0 ].blend.enabled && !list.passes[ 0 ].depth.writeEnabled
			&& list.passes[ 0 ].blend.sourceAlpha == RENDERER_BLEND_SRC_ALPHA_SATURATE
			&& list.passes[ 0 ].cull == RENDERER_CULL_FRONT
			&& list.passes[ 0 ].colorWriteMask == 3u
			&& list.passes[ 0 ].texgen == RENDERER_TEXGEN_SCREEN
			&& list.passes[ 0 ].vertexColor == RENDERER_VERTEX_COLOR_MODULATE
			&& list.passes[ 0 ].polygonOffsetEnabled
			&& list.passes[ 0 ].alphaTestCompareOperation == RENDERER_COMPARE_GREATER_OR_EQUAL
			&& list.passes[ 0 ].programFamily == RENDERER_PROGRAM_CUSTOM,
		"material pass render state must survive append" );

	const std::uint32_t validCount = list.count;
	rendererMaterialPass_t malformed = RendererContracts_DefaultMaterialPass();
	malformed.sourceStageIndex = 0;
	malformed.alphaTestCompareOperation = static_cast<rendererCompareOp_t>( 99 );
	Check( !RendererContracts_ValidateMaterialPass( malformed )
			&& !RendererContracts_AppendMaterialPass( list, malformed )
			&& list.count == validCount,
		"malformed alpha-test comparison enum must fail validation without appending" );
	malformed = RendererContracts_DefaultMaterialPass();
	malformed.sourceStageIndex = 0;
	malformed.blend.sourceColor = static_cast<rendererBlendFactor_t>( 99 );
	Check( !RendererContracts_ValidateMaterialPass( malformed )
			&& !RendererContracts_AppendMaterialPass( list, malformed )
			&& list.count == validCount,
		"malformed blend-factor enum must fail validation without appending" );

	RendererContracts_ResetMaterialPassList( list );
	rendererMaterialPass_t bounded = RendererContracts_DefaultMaterialPass();
	bounded.sourceStageIndex = 0;
	for ( std::uint32_t i = 0; i < RENDERER_CONTRACT_MAX_MATERIAL_PASSES; ++i ) {
		Check( RendererContracts_AppendMaterialPass( list, bounded ),
			"bounded material list rejected an in-range pass" );
	}
	Check( !RendererContracts_AppendMaterialPass( list, bounded ) && list.overflowed
			&& list.count == RENDERER_CONTRACT_MAX_MATERIAL_PASSES,
		"bounded material list must fail closed at capacity" );
}

static void BuildEvaluationPassList( rendererMaterialPassList_t &list ) {
	RendererContracts_ResetMaterialPassList( list );

	rendererMaterialPass_t first = RendererContracts_DefaultMaterialPass();
	first.sourceStageIndex = 3;
	first.kind = RENDERER_MATERIAL_PASS_INTERACTION;
	first.textureSemantic = RENDERER_TEXTURE_DIFFUSE;
	first.textureResourceId = 0x101u;
	first.condition = RendererContracts_Register( 0 );
	for ( int i = 0; i < 4; ++i ) {
		first.color[ i ] = RendererContracts_Register( 1 + i );
	}
	for ( int i = 0; i < 6; ++i ) {
		first.textureMatrix[ i ] = RendererContracts_Register( 5 + i );
	}
	first.blend.enabled = true;
	first.blend.sourceColor = RENDERER_BLEND_SRC_ALPHA;
	first.blend.destinationColor = RENDERER_BLEND_ONE_MINUS_SRC_ALPHA;
	first.blend.colorOperation = RENDERER_BLEND_OP_REVERSE_SUBTRACT;
	first.blend.sourceAlpha = RENDERER_BLEND_SRC_ALPHA_SATURATE;
	first.blend.destinationAlpha = RENDERER_BLEND_ZERO;
	first.blend.alphaOperation = RENDERER_BLEND_OP_MAX;
	first.depth.testEnabled = true;
	first.depth.writeEnabled = false;
	first.depth.compareOperation = RENDERER_COMPARE_EQUAL;
	first.cull = RENDERER_CULL_FRONT;
	first.colorWriteMask = RENDERER_COLOR_WRITE_RED | RENDERER_COLOR_WRITE_ALPHA;
	first.alphaTestEnabled = true;
	first.alphaTestCompareOperation = RENDERER_COMPARE_GREATER_OR_EQUAL;
	first.alphaTest = RendererContracts_Register( 11 );
	first.texgen = RENDERER_TEXGEN_SCREEN;
	first.vertexColor = RENDERER_VERTEX_COLOR_MODULATE;
	first.polygonOffsetEnabled = true;
	first.polygonOffsetFactor = RendererContracts_Register( 12 );
	first.polygonOffsetUnits = RendererContracts_Register( 13 );
	first.programFamily = RENDERER_PROGRAM_INTERACTION;
	first.programKey = 0x33445566u;

	rendererMaterialPass_t second = RendererContracts_DefaultMaterialPass();
	second.sourceStageIndex = 9;
	second.kind = RENDERER_MATERIAL_PASS_SURFACE;
	second.textureSemantic = RENDERER_TEXTURE_DIFFUSE;
	second.textureResourceId = 0x202u;
	second.condition = RendererContracts_Register( 14 );
	second.color[ 0 ] = RendererContracts_Constant( 0.25f );
	second.programFamily = RENDERER_PROGRAM_AMBIENT;
	second.programKey = 0x77889900u;

	Check( RendererContracts_AppendMaterialPass( list, first )
			&& RendererContracts_AppendMaterialPass( list, second ),
		"evaluation pass list setup failed" );
}

static bool EvaluateConstantMaterialPass( rendererMaterialPassList_t &list,
		rendererEvaluatedMaterialPassList_t &evaluated,
		const rendererMaterialPass_t &pass ) {
	RendererContracts_ResetMaterialPassList( list );
	return RendererContracts_AppendMaterialPass( list, pass )
		&& RendererContracts_EvaluateMaterialPassList(
			evaluated, list, NULL, 0 ) == RENDERER_MATERIAL_PASS_EVALUATION_SUCCESS;
}

static void ExerciseMaterialPassDispositionContract( void ) {
	rendererMaterialPassList_t list;
	rendererEvaluatedMaterialPassList_t evaluated;
	rendererMaterialPass_t pass = RendererContracts_DefaultMaterialPass();
	pass.sourceStageIndex = 0;
	Check( EvaluateConstantMaterialPass( list, evaluated, pass )
			&& evaluated.count == 1 && evaluated.activeCount == 1
			&& evaluated.passes[ 0 ].active
			&& evaluated.passes[ 0 ].disposition == RENDERER_MATERIAL_PASS_DRAW,
		"an enabled default pass must have draw disposition" );

	pass.condition = RendererContracts_Constant( 0.0f );
	pass.blend.enabled = true;
	pass.blend.sourceColor = RENDERER_BLEND_ZERO;
	pass.blend.destinationColor = RENDERER_BLEND_ONE;
	Check( EvaluateConstantMaterialPass( list, evaluated, pass )
			&& evaluated.count == 1 && evaluated.activeCount == 0
			&& !evaluated.passes[ 0 ].active
			&& evaluated.passes[ 0 ].disposition == RENDERER_MATERIAL_PASS_INACTIVE_CONDITION,
		"an exactly zero condition must take precedence and mark the pass inactive" );

	pass = RendererContracts_DefaultMaterialPass();
	pass.sourceStageIndex = 0;
	pass.condition = RendererContracts_Constant( -0.0f );
	Check( EvaluateConstantMaterialPass( list, evaluated, pass )
			&& !evaluated.passes[ 0 ].active
			&& evaluated.passes[ 0 ].disposition == RENDERER_MATERIAL_PASS_INACTIVE_CONDITION,
		"negative zero must be treated as the exact inactive condition" );
	pass.condition = RendererContracts_Constant( -0.00001f );
	Check( EvaluateConstantMaterialPass( list, evaluated, pass )
			&& evaluated.passes[ 0 ].active
			&& evaluated.passes[ 0 ].disposition == RENDERER_MATERIAL_PASS_DRAW,
		"a finite nonzero condition must remain active regardless of sign" );

	pass = RendererContracts_DefaultMaterialPass();
	pass.sourceStageIndex = 0;
	pass.blend.enabled = true;
	pass.blend.sourceColor = RENDERER_BLEND_ZERO;
	pass.blend.destinationColor = RENDERER_BLEND_ONE;
	Check( EvaluateConstantMaterialPass( list, evaluated, pass )
			&& evaluated.activeCount == 1 && evaluated.passes[ 0 ].active
			&& evaluated.passes[ 0 ].disposition == RENDERER_MATERIAL_PASS_NOOP_ZERO_ONE_BLEND,
		"zero/one framebuffer-preserving blend must have no-op disposition" );

	pass = RendererContracts_DefaultMaterialPass();
	pass.sourceStageIndex = 0;
	pass.blend.enabled = true;
	pass.blend.sourceColor = RENDERER_BLEND_ONE;
	pass.blend.destinationColor = RENDERER_BLEND_ONE;
	pass.color[ 0 ] = RendererContracts_Constant( 0.0f );
	pass.color[ 1 ] = RendererContracts_Constant( -0.25f );
	pass.color[ 2 ] = RendererContracts_Constant( 0.0f );
	Check( EvaluateConstantMaterialPass( list, evaluated, pass )
			&& evaluated.activeCount == 1 && evaluated.passes[ 0 ].active
			&& evaluated.passes[ 0 ].disposition == RENDERER_MATERIAL_PASS_NOOP_BLACK_ADDITIVE,
		"non-positive black additive color must have no-op disposition" );

	pass = RendererContracts_DefaultMaterialPass();
	pass.sourceStageIndex = 0;
	pass.blend.enabled = true;
	pass.blend.sourceColor = RENDERER_BLEND_SRC_ALPHA;
	pass.blend.destinationColor = RENDERER_BLEND_ONE_MINUS_SRC_ALPHA;
	pass.color[ 3 ] = RendererContracts_Constant( 0.0f );
	Check( EvaluateConstantMaterialPass( list, evaluated, pass )
			&& evaluated.activeCount == 1 && evaluated.passes[ 0 ].active
			&& evaluated.passes[ 0 ].disposition == RENDERER_MATERIAL_PASS_NOOP_TRANSPARENT_ALPHA,
		"transparent source-alpha blend must have no-op disposition" );

	pass = RendererContracts_DefaultMaterialPass();
	pass.sourceStageIndex = 0;
	pass.blend.enabled = true;
	pass.blend.sourceColor = RENDERER_BLEND_SRC_ALPHA_SATURATE;
	Check( EvaluateConstantMaterialPass( list, evaluated, pass )
			&& evaluated.passes[ 0 ].blend.sourceColor == RENDERER_BLEND_SRC_ALPHA_SATURATE
			&& evaluated.passes[ 0 ].disposition == RENDERER_MATERIAL_PASS_DRAW,
		"source-alpha-saturate must validate, survive evaluation, and remain drawable" );
}

static void ExerciseMaterialPassEvaluationContract( void ) {
	rendererMaterialPassList_t list;
	BuildEvaluationPassList( list );
	float registers[ 15 ] = {
		1.0f,
		0.10f, 0.20f, 0.30f, 0.40f,
		1.0f, 0.0f, 0.125f, 0.0f, 1.0f, 0.25f,
		0.60f, 1.50f, 2.50f,
		0.0f
	};

	rendererEvaluatedMaterialPassList_t evaluated;
	Check( RendererContracts_EvaluateMaterialPassList(
			evaluated, list, registers, 15 ) == RENDERER_MATERIAL_PASS_EVALUATION_SUCCESS,
		"valid per-draw material passes must evaluate" );
	Check( evaluated.count == 2 && evaluated.activeCount == 1,
		"inactive conditions must be retained without counting as active" );
	Check( evaluated.passes[ 0 ].order == 0 && evaluated.passes[ 1 ].order == 1
			&& evaluated.passes[ 0 ].sourceStageIndex == 3
			&& evaluated.passes[ 1 ].sourceStageIndex == 9
			&& evaluated.passes[ 0 ].textureSemantic == RENDERER_TEXTURE_DIFFUSE
			&& evaluated.passes[ 1 ].textureSemantic == RENDERER_TEXTURE_DIFFUSE
			&& evaluated.passes[ 0 ].textureResourceId == 0x101u
			&& evaluated.passes[ 1 ].textureResourceId == 0x202u,
		"evaluation must preserve repeated semantics, source stages, and order" );
	Check( evaluated.passes[ 0 ].active && NearlyEqual( evaluated.passes[ 0 ].condition, 1.0f )
			&& evaluated.passes[ 0 ].disposition == RENDERER_MATERIAL_PASS_DRAW
			&& !evaluated.passes[ 1 ].active && NearlyEqual( evaluated.passes[ 1 ].condition, 0.0f )
			&& evaluated.passes[ 1 ].disposition == RENDERER_MATERIAL_PASS_INACTIVE_CONDITION,
		"zero condition must mark a pass inactive without failing evaluation" );
	Check( NearlyEqual( evaluated.passes[ 0 ].color[ 0 ], 0.10f )
			&& NearlyEqual( evaluated.passes[ 0 ].color[ 3 ], 0.40f )
			&& NearlyEqual( evaluated.passes[ 1 ].color[ 0 ], 0.25f ),
		"stage color registers and constants must resolve exactly" );
	Check( NearlyEqual( evaluated.passes[ 0 ].textureMatrix[ 0 ], 1.0f )
			&& NearlyEqual( evaluated.passes[ 0 ].textureMatrix[ 2 ], 0.125f )
			&& NearlyEqual( evaluated.passes[ 0 ].textureMatrix[ 5 ], 0.25f ),
		"texture-matrix registers must resolve exactly" );
	Check( evaluated.passes[ 0 ].kind == RENDERER_MATERIAL_PASS_INTERACTION
			&& evaluated.passes[ 0 ].blend.enabled
			&& evaluated.passes[ 0 ].blend.sourceColor == RENDERER_BLEND_SRC_ALPHA
			&& evaluated.passes[ 0 ].blend.destinationColor == RENDERER_BLEND_ONE_MINUS_SRC_ALPHA
			&& evaluated.passes[ 0 ].blend.colorOperation == RENDERER_BLEND_OP_REVERSE_SUBTRACT
			&& evaluated.passes[ 0 ].blend.sourceAlpha == RENDERER_BLEND_SRC_ALPHA_SATURATE
			&& evaluated.passes[ 0 ].blend.alphaOperation == RENDERER_BLEND_OP_MAX
			&& evaluated.passes[ 0 ].depth.testEnabled
			&& !evaluated.passes[ 0 ].depth.writeEnabled
			&& evaluated.passes[ 0 ].depth.compareOperation == RENDERER_COMPARE_EQUAL
			&& evaluated.passes[ 0 ].cull == RENDERER_CULL_FRONT
			&& evaluated.passes[ 0 ].colorWriteMask == ( RENDERER_COLOR_WRITE_RED | RENDERER_COLOR_WRITE_ALPHA ),
		"evaluation must preserve pass kind and fixed render state" );
	Check( evaluated.passes[ 0 ].alphaTestEnabled
			&& evaluated.passes[ 0 ].alphaTestCompareOperation == RENDERER_COMPARE_GREATER_OR_EQUAL
			&& NearlyEqual( evaluated.passes[ 0 ].alphaTest, 0.60f )
			&& evaluated.passes[ 0 ].texgen == RENDERER_TEXGEN_SCREEN
			&& evaluated.passes[ 0 ].vertexColor == RENDERER_VERTEX_COLOR_MODULATE
			&& evaluated.passes[ 0 ].polygonOffsetEnabled
			&& NearlyEqual( evaluated.passes[ 0 ].polygonOffsetFactor, 1.50f )
			&& NearlyEqual( evaluated.passes[ 0 ].polygonOffsetUnits, 2.50f )
			&& evaluated.passes[ 0 ].programFamily == RENDERER_PROGRAM_INTERACTION
			&& evaluated.passes[ 0 ].programKey == 0x33445566u,
		"evaluation must resolve optional values and preserve program state" );

	RendererContracts_ResetMaterialPassList( list );
	rendererMaterialPass_t constantPass = RendererContracts_DefaultMaterialPass();
	constantPass.sourceStageIndex = 0;
	constantPass.condition = RendererContracts_UnusedRegister();
	for ( int i = 0; i < 4; ++i ) {
		constantPass.color[ i ] = RendererContracts_UnusedRegister();
	}
	for ( int i = 0; i < 6; ++i ) {
		constantPass.textureMatrix[ i ] = RendererContracts_UnusedRegister();
	}
	constantPass.alphaTest = RendererContracts_UnusedRegister();
	constantPass.polygonOffsetFactor = RendererContracts_UnusedRegister();
	constantPass.polygonOffsetUnits = RendererContracts_UnusedRegister();
	Check( RendererContracts_AppendMaterialPass( list, constantPass ),
		"constant-only pass setup failed" );
	Check( RendererContracts_EvaluateMaterialPassList(
			evaluated, list, NULL, 0 ) == RENDERER_MATERIAL_PASS_EVALUATION_SUCCESS
			&& evaluated.count == 1 && evaluated.activeCount == 1
			&& NearlyEqual( evaluated.passes[ 0 ].color[ 0 ], 1.0f )
			&& NearlyEqual( evaluated.passes[ 0 ].textureMatrix[ 0 ], 1.0f )
			&& NearlyEqual( evaluated.passes[ 0 ].textureMatrix[ 4 ], 1.0f ),
		"unused references must resolve to neutral state without a register array" );

	RendererContracts_ResetMaterialPassList( list );
	Check( RendererContracts_EvaluateMaterialPassList(
			evaluated, list, NULL, 0 ) == RENDERER_MATERIAL_PASS_EVALUATION_SUCCESS
			&& evaluated.count == 0 && evaluated.activeCount == 0,
		"an empty list must evaluate safely without registers" );

	BuildEvaluationPassList( list );
	Check( RendererContracts_EvaluateMaterialPassList(
			evaluated, list, NULL, 0 ) == RENDERER_MATERIAL_PASS_EVALUATION_REGISTERS_UNAVAILABLE
			&& evaluated.count == 0 && evaluated.activeCount == 0,
		"indexed passes must reject a missing register array atomically" );
	Check( RendererContracts_EvaluateMaterialPassList(
			evaluated, list, NULL, 15 ) == RENDERER_MATERIAL_PASS_EVALUATION_REGISTERS_UNAVAILABLE
			&& evaluated.count == 0,
		"a nonzero bound with a null register pointer must fail closed" );
	Check( RendererContracts_EvaluateMaterialPassList(
			evaluated, list, registers, 14 ) == RENDERER_MATERIAL_PASS_EVALUATION_REGISTER_OUT_OF_RANGE
			&& evaluated.count == 0,
		"out-of-range register references must reject the complete list" );

	BuildEvaluationPassList( list );
	list.passes[ 0 ].color[ 2 ] = RendererContracts_Register( -1 );
	Check( RendererContracts_EvaluateMaterialPassList(
			evaluated, list, registers, 15 ) == RENDERER_MATERIAL_PASS_EVALUATION_INVALID_PASS
			&& evaluated.count == 0,
		"negative register references must fail closed" );
	BuildEvaluationPassList( list );
	list.passes[ 0 ].condition.source = static_cast<rendererRegisterSource_t>( 99 );
	Check( RendererContracts_EvaluateMaterialPassList(
			evaluated, list, registers, 15 ) == RENDERER_MATERIAL_PASS_EVALUATION_INVALID_PASS
			&& evaluated.count == 0,
		"unknown register reference sources must fail closed" );
	BuildEvaluationPassList( list );
	list.passes[ 0 ].alphaTestCompareOperation = static_cast<rendererCompareOp_t>( 99 );
	Check( RendererContracts_EvaluateMaterialPassList(
			evaluated, list, registers, 15 ) == RENDERER_MATERIAL_PASS_EVALUATION_INVALID_PASS
			&& evaluated.count == 0,
		"malformed alpha-test comparison must reject evaluation atomically" );

	BuildEvaluationPassList( list );
	registers[ 3 ] = std::numeric_limits<float>::quiet_NaN();
	Check( RendererContracts_EvaluateMaterialPassList(
			evaluated, list, registers, 15 ) == RENDERER_MATERIAL_PASS_EVALUATION_NONFINITE_VALUE
			&& evaluated.count == 0,
		"non-finite register values must reject the complete list" );
	registers[ 3 ] = 0.30f;
	list.passes[ 1 ].color[ 2 ] = RendererContracts_Constant(
		( std::numeric_limits<float>::infinity )() );
	Check( RendererContracts_EvaluateMaterialPassList(
			evaluated, list, registers, 15 ) == RENDERER_MATERIAL_PASS_EVALUATION_NONFINITE_VALUE
			&& evaluated.count == 0,
		"non-finite constants must reject the complete list" );

	BuildEvaluationPassList( list );
	list.overflowed = true;
	Check( RendererContracts_EvaluateMaterialPassList(
			evaluated, list, registers, 15 ) == RENDERER_MATERIAL_PASS_EVALUATION_SOURCE_OVERFLOW
			&& evaluated.count == 0,
		"an overflowed source list must fail closed" );
	BuildEvaluationPassList( list );
	list.count = RENDERER_CONTRACT_MAX_MATERIAL_PASSES + 1;
	Check( RendererContracts_EvaluateMaterialPassList(
			evaluated, list, registers, 15 ) == RENDERER_MATERIAL_PASS_EVALUATION_SOURCE_OVERFLOW
			&& evaluated.count == 0,
		"an out-of-bounds source count must fail before reading passes" );
}

static void ExerciseClipSpaceContract( void ) {
	const rendererClipSpaceConvention_t gl = RendererContracts_GLClipSpace();
	const rendererClipSpaceConvention_t vk = RendererContracts_VulkanClipSpace();
	float identity[ 16 ];
	std::memset( identity, 0, sizeof( identity ) );
	identity[ 0 ] = identity[ 5 ] = identity[ 10 ] = identity[ 15 ] = 1.0f;

	float converted[ 16 ];
	Check( RendererContracts_ConvertClipMatrix( converted, identity, gl, vk ),
		"GL to Vulkan clip conversion failed" );
	Check( NearlyEqual( converted[ 10 ], 0.5f ) && NearlyEqual( converted[ 14 ], 0.5f )
			&& NearlyEqual( converted[ 0 ], 1.0f ) && NearlyEqual( converted[ 15 ], 1.0f ),
		"GL to Vulkan depth conversion must map z from [-w,w] to [0,w]" );
	Check( RendererContracts_ConvertClipMatrix( converted, converted, vk, gl ),
		"in-place Vulkan to GL clip conversion failed" );
	for ( int i = 0; i < 16; ++i ) {
		Check( NearlyEqual( converted[ i ], identity[ i ] ),
			"round-trip clip conversion changed the matrix" );
	}
	Check( RendererContracts_ConvertClipMatrix( converted, identity, gl, gl )
			&& std::memcmp( converted, identity, sizeof( identity ) ) == 0,
		"same-convention clip conversion must be an exact no-op" );

	rendererCanonicalViewport_t source = { 12.0f, 34.0f, 640.0f, 360.0f, 0.1f, 0.9f };
	rendererBackendViewport_t viewport;
	Check( RendererContracts_BuildViewport( viewport, source, 1080.0f, gl )
			&& NearlyEqual( viewport.y, 34.0f ) && NearlyEqual( viewport.height, 360.0f ),
		"GL viewport must preserve lower-left coordinates" );
	Check( RendererContracts_BuildViewport( viewport, source, 1080.0f, vk )
			&& NearlyEqual( viewport.y, 1046.0f ) && NearlyEqual( viewport.height, -360.0f )
			&& NearlyEqual( viewport.minDepth, 0.1f ) && NearlyEqual( viewport.maxDepth, 0.9f ),
		"Vulkan viewport must use the shared upper-left negative-height convention" );
}

static void ExerciseVertexLayoutContract( void ) {
	const rendererVertexLayoutDesc_t &legacy = RendererContracts_LegacyDrawVertLayout();
	Check( RendererContracts_ValidateVertexLayout( legacy ),
		"legacy idDrawVert layout must validate" );
	Check( legacy.bindingCount == 1 && legacy.bindings[ 0 ].stride == 64
			&& legacy.attributeCount == 6,
		"legacy idDrawVert descriptor shape mismatch" );
	const rendererVertexAttributeDesc_t *texcoord = RendererContracts_FindVertexAttribute(
		legacy, RENDERER_VERTEX_SEMANTIC_TEXCOORD0 );
	Check( texcoord != NULL && texcoord->format == RENDERER_VERTEX_FORMAT_FLOAT32X2
			&& texcoord->offset == 56,
		"legacy idDrawVert texcoord descriptor mismatch" );

	const rendererVertexLayoutDesc_t &skinned = RendererContracts_SkinnedDrawVertLayout();
	Check( RendererContracts_ValidateVertexLayout( skinned )
			&& skinned.bindingCount == 2 && skinned.bindings[ 1 ].stride == 32,
		"skinned vertex layout must expose its dedicated 32-byte binding" );
	const rendererVertexAttributeDesc_t *joints = RendererContracts_FindVertexAttribute(
		skinned, RENDERER_VERTEX_SEMANTIC_JOINT_INDICES );
	const rendererVertexAttributeDesc_t *weights = RendererContracts_FindVertexAttribute(
		skinned, RENDERER_VERTEX_SEMANTIC_JOINT_WEIGHTS );
	Check( joints != NULL && joints->binding == 1 && joints->offset == 0
			&& joints->format == RENDERER_VERTEX_FORMAT_UINT32X4,
		"skin joint indices must be full uint32x4 values" );
	Check( weights != NULL && weights->binding == 1 && weights->offset == 16
			&& weights->format == RENDERER_VERTEX_FORMAT_FLOAT32X4,
		"skin weights must be full float32x4 values" );

	rendererVertexLayoutDesc_t invalid = legacy;
	invalid.attributes[ 1 ].semantic = invalid.attributes[ 0 ].semantic;
	Check( !RendererContracts_ValidateVertexLayout( invalid ),
		"duplicate vertex semantics must fail validation" );
	invalid = legacy;
	invalid.attributes[ 5 ].offset = 60;
	Check( !RendererContracts_ValidateVertexLayout( invalid ),
		"out-of-bounds vertex attributes must fail validation" );
	invalid = legacy;
	invalid.attributes[ 2 ].offset = 8;
	Check( !RendererContracts_ValidateVertexLayout( invalid ),
		"overlapping vertex attributes must fail validation" );
}

static void ExerciseBufferHandleContract( void ) {
	const rendererBufferHandle_t handle = RendererContracts_MakeBufferHandle(
		RENDERER_BUFFER_KIND_VERTEX, RENDERER_BUFFER_LIFETIME_FRAME, 12, 7 );
	rendererBufferRecord_t record = { handle, 4096, 99 };
	rendererBufferSlice_t slice = { handle, 128, 512 };
	Check( RendererContracts_ValidateBufferSlice( slice, record,
			RENDERER_BUFFER_KIND_VERTEX, 99 ) == RENDERER_BUFFER_SLICE_VALID,
		"valid typed buffer slice was rejected" );

	slice.handle = RendererContracts_MakeBufferHandle(
		RENDERER_BUFFER_KIND_VERTEX, RENDERER_BUFFER_LIFETIME_FRAME, 12, 8 );
	Check( RendererContracts_ValidateBufferSlice( slice, record,
			RENDERER_BUFFER_KIND_VERTEX, 99 ) == RENDERER_BUFFER_SLICE_STALE_GENERATION,
		"stale buffer generation must fail validation" );

	slice.handle = RendererContracts_MakeBufferHandle(
		RENDERER_BUFFER_KIND_INDEX, RENDERER_BUFFER_LIFETIME_FRAME, 12, 7 );
	Check( RendererContracts_ValidateBufferSlice( slice, record,
			RENDERER_BUFFER_KIND_VERTEX, 99 ) == RENDERER_BUFFER_SLICE_WRONG_KIND,
		"wrong buffer kind must fail validation" );

	slice.handle = handle;
	Check( RendererContracts_ValidateBufferSlice( slice, record,
			RENDERER_BUFFER_KIND_VERTEX, 100 ) == RENDERER_BUFFER_SLICE_EXPIRED,
		"frame buffer slice must expire with its frame serial" );

	record.capacityBytes = ( std::numeric_limits<std::uint64_t>::max )();
	slice.offsetBytes = record.capacityBytes - 2;
	slice.sizeBytes = 8;
	Check( RendererContracts_ValidateBufferSlice( slice, record,
			RENDERER_BUFFER_KIND_VERTEX, 99 ) == RENDERER_BUFFER_SLICE_RANGE_OVERFLOW,
		"overflowing buffer slice range must fail without wrapping" );
}

int main() {
	Check( RendererContracts_RunSelfTest(),
		"shared runtime self-test must pass without a graphics device" );
	ExerciseMaterialPassContract();
	ExerciseMaterialPassDispositionContract();
	ExerciseMaterialPassEvaluationContract();
	ExerciseClipSpaceContract();
	ExerciseVertexLayoutContract();
	ExerciseBufferHandleContract();
	if ( failures != 0 ) {
		std::fprintf( stderr, "RendererContractsTest: %d failure(s)\n", failures );
		return 1;
	}
	std::printf( "RendererContractsTest: PASS\n" );
	return 0;
}
