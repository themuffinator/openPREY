// Copyright (C) 2026 DarkMatter Productions
#ifdef OPENQ4_RENDERER_VK_MODULE
#include "../../idlib/precompiled.h"
#pragma hdrstop
#include "../tr_local.h"
#include "VulkanDevice.h"
#include "vk_Image.h"
#include "vk_ExecutorHooks.h"
#include "vk_HDRScene.h"
#include "shaders/hdr_domain_spv.h"
#include "shaders/hdr_scene_spv.h"

// Separate numeric domains through the existing light/shadow walk. Both
// attachments use identical blending; no independentBlend or sample shading
// feature is required. The original depth/stencil attachment remains shared.
static struct vkHDRSceneState_t {
	idImage *classic;
	idImage *pbr;
	idRenderTexture *accumulation;
	idRenderTexture *destination;
	idImage *previewColor;
	idRenderTexture *previewTarget;
	VkPipeline previewPipeline;
	VkDescriptorSet previewSet;
	bool preview;
	VkPipeline seedPipeline;
	VkPipeline combinePipeline;
	VkDescriptorSet sourceSet;
	VkDescriptorSet accumulationSets[2];
	int samples;
} hdrScene;

enum vkHDRCompositeModule_t {
	HDR_VERTEX, HDR_SEED, HDR_SEED_MS, HDR_COMBINE, HDR_COMBINE_MS,
	HDR_TEST, HDR_TEST_SEED, HDR_PREVIEW, HDR_PREVIEW_MS, HDR_MODULE_COUNT
};
static VkShaderModule domainModules[VK_HDR_SCENE_SHADER_COUNT];
static VkShaderModule compositeModules[HDR_MODULE_COUNT];
static const viewDef_t *hdrView;
static bool hdrLinearActive;
static bool hdrOutputCommitted;
static const char *hdrRejection = "disabled";
static unsigned int hdrCompletedViews;
static bool previewRequested;
static bool previewCommitted;
static const char *previewRejection = "disabled";
static unsigned int previewCompletedViews;
// Every view's admission outcome since the map (render world) changed, so the
// reported reason is not only whichever 3D view of the frame happened to run
// last. Reasons are static strings; a small fixed table bounds the counts.
struct hdrOutcomeCount_t {
	const char *reason;
	bool preview;
	unsigned int views;
};
static const int HDR_OUTCOME_SLOTS = 48;
static hdrOutcomeCount_t hdrOutcomes[ HDR_OUTCOME_SLOTS ];
static int hdrOutcomeCount;
static unsigned int hdrOutcomeOverflow;
static const void *hdrOutcomeWorld;
static const char *hdrMainViewReason = "none";

static void VK_HDR_CountOutcome( const viewDef_t *view, bool preview, const char *reason ) {
	if ( reason == NULL ) { return; }
	if ( view != NULL && view->renderWorld != hdrOutcomeWorld ) {
		hdrOutcomeWorld = view->renderWorld;
		hdrOutcomeCount = 0;
		hdrOutcomeOverflow = 0;
	}
	// FinishOutput passes no view: it only ever settles the main scene view.
	if ( view == NULL || ( !view->isSubview && view->superView == NULL ) ) { hdrMainViewReason = reason; }
	for ( int i = 0; i < hdrOutcomeCount; ++i ) {
		if ( hdrOutcomes[i].preview == preview && idStr::Cmp( hdrOutcomes[i].reason, reason ) == 0 ) {
			++hdrOutcomes[i].views;
			return;
		}
	}
	if ( hdrOutcomeCount >= HDR_OUTCOME_SLOTS ) { ++hdrOutcomeOverflow; return; }
	hdrOutcomes[hdrOutcomeCount].reason = reason;
	hdrOutcomes[hdrOutcomeCount].preview = preview;
	hdrOutcomes[hdrOutcomeCount].views = 1;
	++hdrOutcomeCount;
}

// The linear scene and the floating-point preview are laboratory modes
// (r_pbrLinearScene): the linear scene presents classic surfaces through the
// PBR filmic curve. Production PBR composites each draw into the classic
// display-referred framebuffer instead, so stock frames never change.
bool VK_HDRScene_Requested() {
	return r_rendererModernQuality.GetBool() && r_pbrMaterials.GetBool() && r_pbrLinearScene.GetBool()
		&& r_hdrToneMap.GetBool() && VK_PostProcess_HDRSceneRequested();
}

bool VK_HDRScene_PreviewRequested( const viewDef_t *view ) {
	if ( view == NULL || !r_rendererModernQuality.GetBool() || !r_pbrMaterials.GetBool()
			|| !r_pbrLinearScene.GetBool() || r_hdrToneMap.GetBool()
			|| r_hdrDebugView.GetInteger() > 0 ) { return false; }
	// Stock-only views retain their original targets and blending. A PBR view
	// still has to pass complete-view admission before any framebuffer write.
	for ( int i = 0; i < view->numDrawSurfs; ++i ) {
		const drawSurf_t *surf = view->drawSurfs[i];
		if ( surf != NULL && surf->material != NULL && surf->material->HasPBR() ) { return true; }
	}
	return false;
}

bool VK_HDRScene_PreviewAccumulating() {
	return hdrScene.preview && VK_HDRScene_Accumulating();
}

void VK_HDRScene_ResetView() {
	hdrView = NULL;
	hdrLinearActive = hdrOutputCommitted = false;
	hdrRejection = "disabled";
	previewRequested = previewCommitted = false;
	previewRejection = "disabled";
}

bool VK_HDRScene_LinearActive() { return hdrLinearActive; }

// Only the linear scene, its accumulation and its linear target, holds
// radiance. The HDR-off preview stores the framebuffer's display-referred
// values, merely in floating point, so its PBR draws encode like any other.
bool VK_HDRScene_DisplayReferredTarget() {
	return !hdrLinearActive && ( !VK_HDRScene_Accumulating() || VK_HDRScene_PreviewAccumulating() );
}

void VK_HDRScene_PrintInfo() {
	common->Printf( "Vulkan HDR scene ownership: requested=%d committed=%d linearActive=%d reason=%s completedViews=%u samples=%d\n",
		int( VK_HDRScene_Requested() ), int( hdrOutputCommitted ), int( hdrLinearActive ),
		hdrRejection, hdrCompletedViews, hdrScene.samples );
	common->Printf( "Vulkan PBR preview: requested=%d committed=%d reason=%s completedViews=%u samples=%d\n",
		int( previewRequested ), int( previewCommitted ), previewRejection, previewCompletedViews, hdrScene.samples );
	common->Printf( "Vulkan HDR scene views on this map: main view reason=%s%s\n", hdrMainViewReason,
		hdrOutcomeCount == 0 ? " (none counted)" : "" );
	for ( int i = 0; i < hdrOutcomeCount; ++i ) {
		common->Printf( "  %s %s: %u\n", hdrOutcomes[i].preview ? "preview" : "linear", hdrOutcomes[i].reason,
			hdrOutcomes[i].views );
	}
	if ( hdrOutcomeOverflow > 0 ) {
		common->Printf( "  %u further outcomes not counted\n", hdrOutcomeOverflow );
	}
}

static VkShaderModule VK_HDR_CreateModule( VkShaderModule &module, const unsigned char *code, unsigned int bytes ) {
	if ( module == VK_NULL_HANDLE && vkCtx.device != VK_NULL_HANDLE ) {
		VkShaderModuleCreateInfo info = {};
		info.sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO;
		info.codeSize = bytes;
		info.pCode = reinterpret_cast<const uint32_t *>( code );
		if ( vkCreateShaderModule( vkCtx.device, &info, NULL, &module ) != VK_SUCCESS ) {
			return VK_NULL_HANDLE;
		}
	}
	return module;
}

VkShaderModule VK_HDRScene_Shader( vkHDRSceneShader_t shader ) {
#define HDR_DOMAIN_CASE(kind, name) case kind: return VK_HDR_CreateModule( domainModules[kind], vk_hdr_##name##_spv, vk_hdr_##name##_spv_size )
	switch ( shader ) {
		HDR_DOMAIN_CASE( VK_HDR_GUI, gui_frag );
		HDR_DOMAIN_CASE( VK_HDR_INTERACTION, interaction_frag );
		HDR_DOMAIN_CASE( VK_HDR_SHADOW_INTERACTION, interaction_shadow_frag );
		HDR_DOMAIN_CASE( VK_HDR_POINT_INTERACTION, interaction_shadow_point_frag );
		HDR_DOMAIN_CASE( VK_HDR_PROBE_ENVIRONMENT, pbr_probe_environment_frag );
		HDR_DOMAIN_CASE( VK_HDR_BAKED_ENVIRONMENT, pbr_baked_environment_frag );
		HDR_DOMAIN_CASE( VK_HDR_BAKED_PROBE_ENVIRONMENT, pbr_baked_probe_environment_frag );
		default: return VK_NULL_HANDLE;
	}
#undef HDR_DOMAIN_CASE
}

static VkShaderModule VK_HDR_CompositeModule( vkHDRCompositeModule_t shader ) {
#define HDR_MODULE_CASE(kind, name) case kind: return VK_HDR_CreateModule( compositeModules[kind], vk_##name##_spv, vk_##name##_spv_size )
	switch ( shader ) {
		HDR_MODULE_CASE( HDR_VERTEX, hdr_scene_vert );
		HDR_MODULE_CASE( HDR_SEED, hdr_scene_seed_frag );
		HDR_MODULE_CASE( HDR_SEED_MS, hdr_scene_seed_ms_frag );
		HDR_MODULE_CASE( HDR_COMBINE, hdr_scene_combine_frag );
		HDR_MODULE_CASE( HDR_COMBINE_MS, hdr_scene_combine_ms_frag );
		HDR_MODULE_CASE( HDR_TEST, hdr_scene_test_frag );
		HDR_MODULE_CASE( HDR_TEST_SEED, hdr_scene_test_seed_frag );
		HDR_MODULE_CASE( HDR_PREVIEW, hdr_scene_preview_frag );
		HDR_MODULE_CASE( HDR_PREVIEW_MS, hdr_scene_preview_ms_frag );
		default: return VK_NULL_HANDLE;
	}
#undef HDR_MODULE_CASE
}

bool VK_HDRScene_Accumulating() {
	return hdrScene.accumulation != NULL && VK_Exec_ActiveRenderTexture() == hdrScene.accumulation;
}

static VkPipeline VK_HDR_Pipeline( vkHDRCompositeModule_t module, int blend ) {
	// Kinds 20-28 in the post range are reserved for this boundary.
	return VK_Exec_PostPipeline( 20 + int( module ), VK_HDR_CompositeModule( HDR_VERTEX ),
		VK_HDR_CompositeModule( module ), blend );
}

static bool VK_HDR_EnsureImage( idImage *&image, const char *name, const idImageOpts &opts ) {
	if ( image == NULL ) {
		idImageOpts createOpts = opts;
		image = globalImages->ScratchImage( name, &createOpts, TF_NEAREST, TR_CLAMP, TD_DEFAULT );
	}
	if ( image == NULL ) { return false; }
	const idImageOpts &old = image->GetOpts();
	if ( old.width != opts.width || old.height != opts.height || old.format != opts.format
			|| old.numMSAASamples != opts.numMSAASamples || image->GetDeviceHandle() == 0 ) {
		image->AllocImage( opts, TF_NEAREST, TR_CLAMP );
	}
	vkImageEntry_t *entry = VK_Image_GetEntry( image->GetDeviceHandle() );
	const VkFormat format = opts.format == FMT_RGBA16F ? VK_FORMAT_R16G16B16A16_SFLOAT : VK_FORMAT_R8G8B8A8_UNORM;
	return entry != NULL && entry->format == format
		&& entry->width == opts.width && entry->height == opts.height
		&& int( entry->samples ) == Max( 1, opts.numMSAASamples );
}

// All fallible allocation/pipeline/descriptor work precedes any accumulation
// write. Merely creating a second target does not confer linear ownership.
static bool VK_HDR_Prepare( idRenderTexture *destination, bool preview = false ) {
	if ( destination == NULL || destination->GetNumColorImages() != 1 || VK_Exec_ActiveCubeFace() != 0 ) {
		return false;
	}
	idImage *source = destination->GetColorImage( 0 );
	const idImageOpts &opts = source->GetOpts();
	if ( ( opts.format != FMT_RGBA16F && ( !preview || opts.format != FMT_RGBA8 ) ) || opts.textureType != TT_2D
			|| opts.numMSAASamples > 32 ) { return false; }
	hdrScene.preview = preview;
	idImageOpts radianceOpts = opts;
	radianceOpts.format = FMT_RGBA16F;
	if ( !VK_HDR_EnsureImage( hdrScene.classic, "_vkHDRClassicAccum", opts )
			|| !VK_HDR_EnsureImage( hdrScene.pbr, "_vkHDRPBRAccum", radianceOpts ) ) { return false; }
	if ( hdrScene.accumulation != NULL && hdrScene.accumulation->GetDepthImage() != destination->GetDepthImage() ) {
		delete hdrScene.accumulation;
		hdrScene.accumulation = NULL;
	}
	if ( hdrScene.accumulation == NULL ) {
		hdrScene.accumulation = new idRenderTexture( hdrScene.classic, destination->GetDepthImage() );
		hdrScene.accumulation->AddRenderImage( hdrScene.pbr );
		hdrScene.accumulation->SetDebugLabel( "Vulkan classic/PBR accumulation" );
	}
	hdrScene.destination = destination;
	hdrScene.samples = Max( 1, opts.numMSAASamples );
	idRenderTexture *compositeTarget = destination;
	if ( preview ) {
		if ( !VK_HDR_EnsureImage( hdrScene.previewColor, "_vkPBRPreviewColor", radianceOpts ) ) { return false; }
		if ( hdrScene.previewTarget != NULL && hdrScene.previewTarget->GetDepthImage() != destination->GetDepthImage() ) {
			delete hdrScene.previewTarget;
			hdrScene.previewTarget = NULL;
		}
		if ( hdrScene.previewTarget == NULL ) {
			hdrScene.previewTarget = new idRenderTexture( hdrScene.previewColor, destination->GetDepthImage() );
			hdrScene.previewTarget->SetDebugLabel( "Vulkan PBR preview radiance" );
		}
		hdrScene.previewSet = VK_Exec_ImageDescriptor( hdrScene.previewColor->GetDeviceHandle(), true );
		if ( hdrScene.previewSet == VK_NULL_HANDLE || !VK_Exec_SetRenderTarget( destination ) ) { return false; }
		hdrScene.previewPipeline = VK_HDR_Pipeline( hdrScene.samples > 1 ? HDR_PREVIEW_MS : HDR_PREVIEW,
			GLS_SRCBLEND_ONE | GLS_DSTBLEND_ZERO );
		if ( hdrScene.previewPipeline == VK_NULL_HANDLE ) { return false; }
		compositeTarget = hdrScene.previewTarget;
	}
	hdrScene.sourceSet = VK_Exec_ImageDescriptor( source->GetDeviceHandle(), true );
	hdrScene.accumulationSets[0] = VK_Exec_ImageDescriptor( hdrScene.classic->GetDeviceHandle(), true );
	hdrScene.accumulationSets[1] = VK_Exec_ImageDescriptor( hdrScene.pbr->GetDeviceHandle(), true );
	if ( hdrScene.sourceSet == VK_NULL_HANDLE || hdrScene.accumulationSets[0] == VK_NULL_HANDLE
			|| hdrScene.accumulationSets[1] == VK_NULL_HANDLE ) { return false; }
	if ( !VK_Exec_SetRenderTarget( compositeTarget ) ) { return false; }
	hdrScene.combinePipeline = VK_HDR_Pipeline( hdrScene.samples > 1 ? HDR_COMBINE_MS : HDR_COMBINE,
		GLS_SRCBLEND_ONE | GLS_DSTBLEND_ZERO );
	bool ready = hdrScene.combinePipeline != VK_NULL_HANDLE && VK_Exec_SetRenderTarget( hdrScene.accumulation );
	if ( ready ) {
		hdrScene.seedPipeline = VK_HDR_Pipeline( hdrScene.samples > 1 ? HDR_SEED_MS : HDR_SEED,
			GLS_SRCBLEND_ONE | GLS_DSTBLEND_ZERO );
		ready = hdrScene.seedPipeline != VK_NULL_HANDLE;
	}
	return VK_Exec_SetRenderTarget( destination ) && ready;
}

static void VK_HDR_DrawState( const viewDef_t *view ) {
	VK_Exec_MarkCanonicalWrites();
	VkCommandBuffer cmd = VK_Exec_ActiveCmd();
	VkViewport viewport = {};
	viewport.width = float( VK_Exec_ActiveFramebufferWidth() );
	viewport.height = float( VK_Exec_ActiveFramebufferHeight() );
	viewport.maxDepth = 1.0f;
	vkCmdSetViewport( cmd, 0, 1, &viewport );
	VK_Exec_SetViewScissor( cmd, view, int( viewport.height ) );
	vkCmdSetDepthTestEnable( cmd, VK_FALSE );
	vkCmdSetDepthWriteEnable( cmd, VK_FALSE );
	vkCmdSetDepthCompareOp( cmd, VK_COMPARE_OP_ALWAYS );
	vkCmdSetCullMode( cmd, VK_CULL_MODE_NONE );
	vkCmdSetFrontFace( cmd, VK_Exec_CanonicalFrontFace() );
	vkCmdSetDepthBiasEnable( cmd, VK_FALSE );
	vkCmdSetStencilTestEnable( cmd, VK_FALSE );
	if ( vkCtx.depthBoundsSupported ) { vkCmdSetDepthBoundsTestEnable( cmd, VK_FALSE ); }
}

static bool VK_HDR_DrawSamples( const viewDef_t *view, VkPipeline pipeline,
		const VkDescriptorSet *sets, int count ) {
	if ( pipeline == VK_NULL_HANDLE || !VK_Exec_MainRenderingScopeOpen() ) { return false; }
	VK_HDR_DrawState( view );
	VkCommandBuffer cmd = VK_Exec_ActiveCmd();
	VkPipelineLayout layout = VK_Exec_InteractionPipelineLayout();
	vkCmdBindPipeline( cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, pipeline );
	vkCmdBindDescriptorSets( cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, layout, 0, count, sets, 0, NULL );
	for ( int sample = 0; sample < hdrScene.samples; ++sample ) {
		const int params[4] = { sample, int( hdrScene.preview ), 0, 0 };
		vkCmdPushConstants( cmd, layout, VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT, 0, sizeof( params ), params );
		vkCmdDraw( cmd, 3, 1, 0, 0 );
	}
	return true;
}

static bool VK_HDR_Seed( const viewDef_t *view ) {
	// SetRenderTarget transitions the previous color attachment to sampled and
	// retains the same depth/stencil contents on the new target.
	return VK_Exec_SetRenderTarget( hdrScene.accumulation )
		&& VK_HDR_DrawSamples( view, hdrScene.seedPipeline, &hdrScene.sourceSet, 1 );
}

static bool VK_HDR_Combine( const viewDef_t *view ) {
	return VK_Exec_SetRenderTarget( hdrScene.preview ? hdrScene.previewTarget : hdrScene.destination )
		&& VK_HDR_DrawSamples( view, hdrScene.combinePipeline, hdrScene.accumulationSets, 2 );
}

bool VK_HDRScene_BeginView( const viewDef_t *view, const char *rejection ) {
	previewRequested = VK_HDRScene_PreviewRequested( view );
	if ( !VK_HDRScene_Requested() && !previewRequested ) { return false; }
	const bool preview = previewRequested;
	const char *&reason = preview ? previewRejection : hdrRejection;
	reason = rejection;
	if ( rejection != NULL ) { VK_HDR_CountOutcome( view, preview, reason ); return false; }
	if ( !preview ) {
		reason = VK_PostProcess_PrepareLinearOutput( view );
		if ( reason != NULL ) { VK_HDR_CountOutcome( view, preview, reason ); return false; }
	}
	idRenderTexture *destination = VK_Exec_ActiveRenderTexture();
	if ( !VK_HDR_Prepare( destination, preview ) ) {
		(void)VK_Exec_SetRenderTarget( destination );
		VK_PostProcess_DiscardLinearOutput();
		reason = "accumulation-resources";
		VK_HDR_CountOutcome( view, preview, reason );
		return false;
	}
	bool ready = VK_Exec_SetRenderTarget( hdrScene.accumulation ) && VK_Exec_HDRScenePipelinesReady( view );
	ready = VK_Exec_SetRenderTarget( destination ) && ready;
	if ( !ready ) {
		VK_PostProcess_DiscardLinearOutput();
		reason = "material-pipelines";
		VK_HDR_CountOutcome( view, preview, reason );
		return false;
	}
	if ( preview ) {
		// Ordered transparency runs after the opaque combine, on the float
		// preview target. Its original LDR pipelines cannot be replayed there.
		ready = VK_Exec_SetRenderTarget( hdrScene.previewTarget ) && VK_PBR_RetargetTransparentView( view );
		ready = VK_Exec_SetRenderTarget( destination ) && ready;
		if ( !ready ) {
			(void)VK_PBR_RetargetTransparentView( view );
			reason = "transparent-pipelines";
			VK_HDR_CountOutcome( view, preview, reason );
			return false;
		}
	}
	if ( !VK_HDR_Seed( view ) ) {
		(void)VK_Exec_SetRenderTarget( destination );
		if ( preview ) { (void)VK_PBR_RetargetTransparentView( view ); }
		VK_PostProcess_DiscardLinearOutput();
		reason = "seed";
		VK_HDR_CountOutcome( view, preview, reason );
		return false;
	}
	hdrView = view;
	reason = "accumulating";
	VK_HDR_CountOutcome( view, preview, reason );
	return true;
}

bool VK_HDRScene_EndOpaque( const viewDef_t *view ) {
	if ( hdrView != view ) { return true; }
	const char *&reason = hdrScene.preview ? previewRejection : hdrRejection;
	if ( !VK_HDR_Combine( view ) ) {
		reason = "combine";
		VK_HDR_CountOutcome( view, hdrScene.preview, reason );
		// The caller abandons the rest of this view, so its opaque content is
		// lost, but the accumulation must not stay bound for the GUI and later
		// views. Return to the view's own target and release the output.
		(void)VK_Exec_SetRenderTarget( hdrScene.destination );
		if ( hdrScene.preview ) {
			(void)VK_PBR_RetargetTransparentView( view );
		} else {
			VK_PostProcess_DiscardLinearOutput();
		}
		hdrView = NULL;
		return false;
	}
	hdrLinearActive = !hdrScene.preview;
	reason = hdrScene.preview ? "radiance" : "linear";
	return true;
}

bool VK_HDRScene_FinishPreview( const viewDef_t *view, bool *composited ) {
	if ( composited != NULL ) { *composited = false; }
	if ( hdrView != view || !hdrScene.preview ) { return true; }
	// Fog/blend lights and ordered transparent PBR finish in floating point.
	// Average the stored samples in the copy shader, then broadcast the result
	// to every destination sample. This keeps the averaging explicit, avoids an
	// intermediate resolve image and clamps only the finished scene.
	const bool ready = VK_Exec_SetRenderTarget( hdrScene.destination );
	if ( !ready ) { previewRejection = "resolve"; return false; }
	VK_HDR_DrawState( view );
	VkCommandBuffer cmd = VK_Exec_ActiveCmd();
	vkCmdBindPipeline( cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, hdrScene.previewPipeline );
	vkCmdBindDescriptorSets( cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, VK_Exec_InteractionPipelineLayout(),
		0, 1, &hdrScene.previewSet, 0, NULL );
	vkCmdDraw( cmd, 3, 1, 0, 0 );
	previewCommitted = true;
	previewRejection = "complete";
	++previewCompletedViews;
	hdrView = NULL;
	if ( composited != NULL ) { *composited = true; }
	return true;
}

void VK_HDRScene_FinishOutput( bool submitted ) {
	if ( !hdrLinearActive ) { return; }
	hdrOutputCommitted = submitted;
	hdrLinearActive = false;
	hdrRejection = submitted ? "complete" : "output";
	if ( submitted ) { ++hdrCompletedViews; }
	VK_HDR_CountOutcome( NULL, false, hdrRejection );
}

void VK_HDRScene_Shutdown() {
	VK_HDRScene_ResetView();
	hdrCompletedViews = 0;
	previewCompletedViews = 0;
	hdrOutcomeCount = 0;
	hdrOutcomeOverflow = 0;
	hdrOutcomeWorld = NULL;
	hdrMainViewReason = "none";
	delete hdrScene.accumulation;
	delete hdrScene.previewTarget;
	memset( &hdrScene, 0, sizeof( hdrScene ) );
	for ( int i = 0; i < VK_HDR_SCENE_SHADER_COUNT; ++i ) {
		if ( domainModules[i] != VK_NULL_HANDLE ) { vkDestroyShaderModule( vkCtx.device, domainModules[i], NULL ); }
		domainModules[i] = VK_NULL_HANDLE;
	}
	for ( int i = 0; i < HDR_MODULE_COUNT; ++i ) {
		if ( compositeModules[i] != VK_NULL_HANDLE ) { vkDestroyShaderModule( vkCtx.device, compositeModules[i], NULL ); }
		compositeModules[i] = VK_NULL_HANDLE;
	}
}

// The diagnostic supplies independently chosen per-sample radiance and checks
// the production seed/combine, including alpha, orientation, additive classic
// lights and values above one. A resolve-before-decode implementation fails.
static bool VK_HDR_TestDraw( const viewDef_t &view, int sample, const float classic[4],
		const float pbr[4], bool seed, bool additive, int blendOverride = -1 ) {
	const VkPipeline pipeline = VK_HDR_Pipeline( seed ? HDR_TEST_SEED : HDR_TEST,
		blendOverride >= 0 ? blendOverride : GLS_SRCBLEND_ONE | ( additive ? GLS_DSTBLEND_ONE : GLS_DSTBLEND_ZERO ) );
	if ( pipeline == VK_NULL_HANDLE ) { return false; }
	VK_HDR_DrawState( &view );
	struct { int params[4]; float classic[4]; float pbr[4]; } push = {};
	push.params[0] = sample;
	push.params[2] = view.viewport.y2 - view.viewport.y1 + 1;
	memcpy( push.classic, classic, sizeof( push.classic ) );
	memcpy( push.pbr, pbr, sizeof( push.pbr ) );
	VkCommandBuffer cmd = VK_Exec_ActiveCmd();
	vkCmdBindPipeline( cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, pipeline );
	vkCmdPushConstants( cmd, VK_Exec_InteractionPipelineLayout(), VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT,
		0, sizeof( push ), &push );
	vkCmdDraw( cmd, 3, 1, 0, 0 );
	return true;
}

static double VK_HDR_TestDecode( double value ) {
	return value <= 0.0 ? 0.0 : value <= 0.04045 ? value / 12.92 : pow( ( value + .055 ) / 1.055, 2.4 );
}

static double VK_HDR_TestUNorm( double value ) {
	return floor( Max( 0.0, Min( 1.0, value ) ) * 255.0 + .5 ) / 255.0;
}

static bool VK_HDR_TestPreview() {
	const int previousFrame = backEnd.frameCount;
	viewDef_t view = {};
	idImageOpts opts;
	opts.textureType = TT_2D;
	opts.format = FMT_RGBA8;
	opts.width = 8;
	opts.height = 6;
	opts.numLevels = 1;
	opts.numMSAASamples = 0;
	opts.isPersistant = true;
	idImage *image = globalImages->ScratchImage( "_vkPBRPreviewTest", &opts, TF_NEAREST, TR_CLAMP, TD_DEFAULT );
	idImageOpts readOpts = opts;
	readOpts.format = FMT_RGBA16F;
	idImage *readback = globalImages->ScratchImage( "_vkPBRPreviewReadback", &readOpts, TF_NEAREST, TR_CLAMP, TD_DEFAULT );
	bool passed = image != NULL && readback != NULL;
	int cases = 0;
	for ( int ms = 0; ms < 2 && passed; ++ms ) {
		opts.numMSAASamples = ms == 0 ? 0 : 4;
		image->AllocImage( opts, TF_NEAREST, TR_CLAMP );
		passed = image->GetOpts().numMSAASamples == opts.numMSAASamples;
		idRenderTexture target( image, NULL );
		for ( int fixture = 0; fixture < 12 && passed; ++fixture ) {
			++backEnd.frameCount;
			view.viewport.x2 = view.scissor.x2 = opts.width - 1;
			view.viewport.y2 = view.scissor.y2 = opts.height - 1;
			const int samples = Max( 1, opts.numMSAASamples );
			const int covered = fixture % samples + 1;
			const float radiance = .25f * float( fixture + 1 );
			passed = VK_GuiExecutor_BeginFrame() && target.MakeCurrent();
			for ( int sample = 0; sample < samples && passed; ++sample ) {
				const float seed[4] = { 0, 0, 0, .5f };
				const float zero[4] = {};
				passed = VK_HDR_TestDraw( view, sample, seed, zero, true, false );
			}
			passed = passed && VK_HDR_Prepare( &target, true ) && VK_HDR_Seed( &view );
			for ( int light = 0; light < 2 && passed; ++light ) {
				for ( int sample = 0; sample < samples && passed; ++sample ) {
					// Overshoot then modulate: changing classic storage to FP16
					// would leave red above one instead of halving its LDR value.
					const float classic[4] = { 2.0f, .25f, 0, 0 };
					const float pbr[4] = { 0, sample < covered ? 2 * radiance : 0.0f,
						sample < covered ? 4.0f : 0.0f, 0 };
					const float modulation[4] = { .5f, .5f, .5f, 1 };
					passed = light == 0 ? VK_HDR_TestDraw( view, sample, classic, pbr, false, true )
						: VK_HDR_TestDraw( view, sample, modulation, modulation, false, false,
							GLS_SRCBLEND_ZERO | GLS_DSTBLEND_SRC_COLOR );
				}
			}
			hdrView = &view;
			passed = passed && VK_HDRScene_EndOpaque( &view ) && VK_HDRScene_FinishPreview( &view )
				&& VK_Exec_CopyRender( readback, 0, 0, opts.width, opts.height, 0, false );
			idList<float> pixels;
			passed = passed && VK_Exec_TestReadFloatImage( readback, pixels ) && pixels.Num() == opts.width * opts.height * 4;
			for ( int y = 0; y < opts.height && passed; ++y ) {
				for ( int x = 0; x < opts.width && passed; ++x ) {
					const double seed = VK_HDR_TestUNorm( double( ( x + 2 * ( opts.height - 1 - y ) ) & 3 ) / 16 );
					const double expected[4] = {
						VK_HDR_TestUNorm( .5 ),
						VK_HDR_TestUNorm( VK_HDR_TestUNorm( VK_HDR_TestUNorm( seed + .25 ) * .5 ) + radiance * covered / samples ),
						VK_HDR_TestUNorm( VK_HDR_TestUNorm( seed * .5 ) + 2.0 * covered / samples ),
						VK_HDR_TestUNorm( .5 ) };
					for ( int c = 0; c < 4 && passed; ++c ) {
						const float got = pixels[( y * opts.width + x ) * 4 + c];
						passed = std::isfinite( got ) && fabs( got - expected[c] ) <= 1.0 / 255.0 + .0005;
						if ( !passed ) { common->Warning( "Vulkan PBR preview fixture=%d samples=%d xy=%d,%d channel=%d got=%g expected=%g",
							fixture, samples, x, y, c, got, expected[c] ); }
					}
				}
			}
			if ( passed ) { ++cases; }
		}
		(void)VK_Exec_SetRenderTarget( NULL );
	}
	backEnd.frameCount = previousFrame;
	VK_HDRScene_ResetView();
	common->Printf( "Vulkan PBR preview self-test %s (%d clamp/resolve fixtures, actual 0x/4x MSAA)\n",
		passed && cases == 24 ? "passed" : "FAILED", cases );
	return passed && cases == 24;
}

bool VK_HDRScene_Test() {
	const int previousFrame = backEnd.frameCount;
	viewDef_t view = {};
	idImageOpts opts;
	opts.textureType = TT_2D;
	opts.format = FMT_RGBA16F;
	opts.width = 8;
	opts.height = 6;
	opts.numLevels = 1;
	opts.numMSAASamples = 0;
	opts.isPersistant = true;
	idImage *image = globalImages->ScratchImage( "_vkHDRBoundaryTest", &opts, TF_NEAREST, TR_CLAMP, TD_DEFAULT );
	idImage *resolved = globalImages->ScratchImage( "_vkHDRBoundaryResolved", &opts, TF_NEAREST, TR_CLAMP, TD_DEFAULT );
	bool passed = image != NULL && resolved != NULL;
	int cases = 0;
	for ( int ms = 0; ms < 2 && passed; ++ms ) {
		opts.numMSAASamples = ms == 0 ? 0 : 4;
		image->AllocImage( opts, TF_NEAREST, TR_CLAMP );
		passed = image->GetOpts().numMSAASamples == opts.numMSAASamples;
		idRenderTexture target( image, NULL );
		for ( int fixture = 0; fixture < 12 && passed; ++fixture ) {
			++backEnd.frameCount;
			view.viewport.x1 = view.viewport.y1 = view.scissor.x1 = view.scissor.y1 = 0;
			view.viewport.x2 = view.scissor.x2 = opts.width - 1;
			view.viewport.y2 = view.scissor.y2 = opts.height - 1;
			const int samples = Max( 1, opts.numMSAASamples );
			const float alpha = float( fixture % 4 ) / 8.0f;
			passed = VK_GuiExecutor_BeginFrame() && target.MakeCurrent();
			for ( int sample = 0; sample < samples && passed; ++sample ) {
				const float seed[4] = { float( sample ) / 8, float( fixture % 3 ) / 8, .0625f, alpha };
				const float zero[4] = {};
				passed = VK_HDR_TestDraw( view, sample, seed, zero, true, false );
			}
			passed = passed && VK_HDR_Prepare( &target ) && VK_HDR_Seed( &view );
			for ( int light = 0; light < 2 && passed; ++light ) {
				for ( int sample = 0; sample < samples && passed; ++sample ) {
					const float classic[4] = { float( fixture ) / 8, .125f, -.0625f, 0 };
					const float pbr[4] = { float( sample % 2 ), .25f * float( fixture ), .5f, 0 };
					passed = VK_HDR_TestDraw( view, sample, classic, pbr, false, true );
				}
			}
			passed = passed && VK_HDR_Combine( &view )
				&& VK_Exec_CopyRender( resolved, 0, 0, opts.width, opts.height, 0, false );
			idList<float> pixels;
			passed = passed && VK_Exec_TestReadFloatImage( resolved, pixels ) && pixels.Num() == opts.width * opts.height * 4;
			for ( int y = 0; y < opts.height && passed; ++y ) {
				for ( int x = 0; x < opts.width && passed; ++x ) {
					// CopyRender stores GL-oriented (bottom-up) rows.
					const double pattern = double( ( x + 2 * ( opts.height - 1 - y ) ) & 3 ) / 16;
					double expected[4] = { 0, 0, 0, alpha };
					for ( int sample = 0; sample < samples; ++sample ) {
						expected[0] += ( VK_HDR_TestDecode( double( sample ) / 8 + double( fixture ) / 4 + pattern ) + 2 * ( sample % 2 ) ) / samples;
						expected[1] += ( VK_HDR_TestDecode( double( fixture % 3 ) / 8 + .25 + pattern ) + .5 * fixture ) / samples;
						expected[2] += ( VK_HDR_TestDecode( -.0625 + pattern ) + 1 ) / samples;
					}
					for ( int c = 0; c < 4 && passed; ++c ) {
						const float got = pixels[( y * opts.width + x ) * 4 + c];
						passed = std::isfinite( got ) && ( c == 3 ? got == expected[c]
							: fabs( got - expected[c] ) < Max( .002, expected[c] * .0015 ) );
						if ( !passed ) { common->Warning( "Vulkan HDR boundary fixture=%d samples=%d xy=%d,%d channel=%d got=%g expected=%g",
							fixture, samples, x, y, c, got, expected[c] ); }
					}
				}
			}
			if ( passed ) { ++cases; }
		}
		(void)VK_Exec_SetRenderTarget( NULL );
	}
	backEnd.frameCount = previousFrame;
	common->Printf( "Vulkan HDR scene-boundary self-test %s (%d per-sample composition fixtures, actual 0x/4x MSAA)\n",
		passed && cases == 24 ? "passed" : "FAILED", cases );
	return passed && cases == 24 && VK_HDR_TestPreview();
}
#endif
