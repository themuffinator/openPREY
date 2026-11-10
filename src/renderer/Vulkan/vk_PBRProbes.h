// Copyright (C) 2026 DarkMatter Productions
#ifndef __VK_PBR_PROBES_H__
#define __VK_PBR_PROBES_H__

#include "volk.h"
class idImage;
class idScenePacketFrame;
typedef struct viewDef_s viewDef_t;

idImage *VK_PBRProbes_Atlas();
VkDescriptorSetLayout VK_PBRProbes_CreateLayout();
// Called only after this slot's frame fence has completed.
void VK_PBRProbes_BeginFrame( int slot );
void VK_PBRProbes_PrepareFrame( const idScenePacketFrame &frame );
// A null set means analytic fallback; false means resource admission failed.
bool VK_PBRProbes_ForView( const viewDef_t *view, VkDescriptorSet &set );
void VK_PBRProbes_Shutdown();
void VK_PBRProbes_PrintGfxInfo();

#endif
