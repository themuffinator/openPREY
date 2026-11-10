// Copyright (C) 2026 DarkMatter Productions
//

#ifndef __VULKAN_SHADOW_TIMING_H__
#define __VULKAN_SHADOW_TIMING_H__

#include "VulkanDevice.h"

/*
===============================================================================

	Shadow-pass GPU timing (r_shadowMapGpuTimerQueries /
	r_shadowMapGpuSyncTimings).

	The whole-frame facility above measures one span per frame. Shadow
	diagnostics need the shadow pass broken into the phases OpenGL reports,
	and the pass emits several disjoint spans per view, so this keeps its own
	ring of timestamp pairs.

	OpenGL brackets its phases with glFinish under r_shadowMapGpuSyncTimings.
	Vulkan cannot: the pass is being RECORDED, so there is nothing submitted
	to wait for. The equivalent is applied at readback instead -- a
	synchronized resolve waits for results rather than dropping the ones that
	are not ready yet, which is the same accuracy-for-a-stall trade.

===============================================================================
*/

typedef enum vkShadowTimingPhase_e {
	VK_SHADOW_TIMING_MAP_RENDER = 0,	// fresh atlas, compose, cube faces
	VK_SHADOW_TIMING_CACHE_REUSE,		// resident publish/restore transfers
	VK_SHADOW_TIMING_PHASE_COUNT
} vkShadowTimingPhase_t;

typedef struct vkShadowGpuTimingReport_s {
	bool		available;		// the device can timestamp this queue
	bool		enabled;		// a timing cvar asked for samples
	bool		synchronized;	// results were waited for, not polled
	double		totalMilliseconds;
	int			samples;
	int			pending;		// recorded, not resolved yet
	int			dropped;		// lost to ring pressure or a failed read
	double		phaseMilliseconds[ VK_SHADOW_TIMING_PHASE_COUNT ];
	int			phaseSamples[ VK_SHADOW_TIMING_PHASE_COUNT ];
} vkShadowGpuTimingReport_t;

// True when timestamps should be written for this view at all.
bool VK_ShadowGpuTiming_Enabled( void );
// Resolves whatever the GPU has finished since the last view and starts a
// fresh report, mirroring the per-view reset of the OpenGL shadow stats.
void VK_ShadowGpuTiming_BeginView( int frameSlot );
// Each span must begin OUTSIDE a dynamic-rendering scope: the reset of its
// query pair is illegal inside one. Writing the timestamps is not.
void VK_ShadowGpuTiming_BeginPhase( VkCommandBuffer commandBuffer,
	vkShadowTimingPhase_t phase );
void VK_ShadowGpuTiming_EndPhase( VkCommandBuffer commandBuffer,
	vkShadowTimingPhase_t phase );
// A view that recorded spans it will never submit must release them.
void VK_ShadowGpuTiming_AbandonView( void );
const vkShadowGpuTimingReport_t &VK_ShadowGpuTiming_Report( void );
const char *VK_ShadowGpuTiming_PhaseName( vkShadowTimingPhase_t phase );
void VK_ShadowGpuTiming_Shutdown( void );

#endif /* !__VULKAN_SHADOW_TIMING_H__ */
