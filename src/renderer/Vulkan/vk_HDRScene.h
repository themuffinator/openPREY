// Copyright (C) 2026 DarkMatter Productions
#ifndef __VK_HDR_SCENE_H__
#define __VK_HDR_SCENE_H__

enum vkHDRSceneShader_t {
	VK_HDR_GUI,
	VK_HDR_INTERACTION,
	VK_HDR_SHADOW_INTERACTION,
	VK_HDR_POINT_INTERACTION,
	VK_HDR_PROBE_ENVIRONMENT,
	VK_HDR_BAKED_ENVIRONMENT,
	VK_HDR_BAKED_PROBE_ENVIRONMENT,
	VK_HDR_SCENE_SHADER_COUNT
};

bool VK_HDRScene_Accumulating();
VkShaderModule VK_HDRScene_Shader( vkHDRSceneShader_t shader );
bool VK_HDRScene_Requested();
bool VK_HDRScene_PreviewRequested( const viewDef_t *view );
bool VK_HDRScene_PreviewAccumulating();
void VK_HDRScene_ResetView();
bool VK_HDRScene_BeginView( const viewDef_t *view, const char *rejection );
bool VK_HDRScene_EndOpaque( const viewDef_t *view );
bool VK_HDRScene_FinishPreview( const viewDef_t *view, bool *composited = NULL );
bool VK_HDRScene_LinearActive();
// True when PBR draws write Quake 4's display-referred framebuffer and must
// encode their linear radiance, one draw at a time like classic lights: every
// target except the laboratory linear scene (r_pbrLinearScene with HDR).
bool VK_HDRScene_DisplayReferredTarget();
void VK_HDRScene_FinishOutput( bool submitted );
void VK_HDRScene_PrintInfo();
bool VK_Exec_HDRScenePipelinesReady( const viewDef_t *view );
const char *VK_PostProcess_PrepareLinearOutput( const viewDef_t *view );
void VK_PostProcess_DiscardLinearOutput();
const char *VK_SceneEffects_HDRRejection( const viewDef_t *view );
void VK_HDRScene_Shutdown();
bool VK_HDRScene_Test();

#endif
