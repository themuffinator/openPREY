// Copyright (C) 2026 DarkMatter Productions
//

#ifndef __VULKANBRINGUP_H__
#define __VULKANBRINGUP_H__

/*
===============================================================================

	Vulkan renderer module bring-up diagnostics (roadmap Phase A).

	Instance/device/queue/memory validation with no window or surface work,
	safe to run while the OpenGL renderer owns the screen. Later phases grow
	this module toward the full idRenderSystem implementation described in
	docs/dev/archive/2026-10-18/plans/2026-07-16-vulkan-renderer.md.

	This translation unit is standalone: no idlib, engine services arrive
	through the renderModuleServices_t table.

===============================================================================
*/

struct renderModuleServices_s;
struct renderDeviceCatalog_t;
// No logical device, allocation or presentation. Only for an inactive module;
// a live Vulkan renderer queries its existing instance instead.
bool VK_Bringup_QueryCatalog(renderDeviceCatalog_t* catalog);

void	VK_Bringup_SetServices( const struct renderModuleServices_s *services );

// how the probe resolves the Vulkan library. The module glue installs the
// device back end's resolver so the probe tests the library the renderer will
// load: on macOS volk alone never looks inside the app bundle for MoltenVK.
// Without one the probe falls back to volkInitialize().
typedef bool ( *vkBringupLoaderInit_t )( void );
void	VK_Bringup_SetLoaderInit( vkBringupLoaderInit_t initLoader );

// full bring-up pass: loader -> instance (+ optional validation) -> device
// enumeration/selection -> logical device + queues -> VMA allocations ->
// timeline semaphore -> teardown; reports through services->Printf
bool	VK_Bringup_RunProbe( bool verbose );

// quiet pass/fail wrapper; the engine's loader runs it before activating the
// module. A pass keeps its instance alive, so the Vulkan drivers stay loaded
// for the renderer's own instance, until VK_Bringup_ReleaseHeldInstance
bool	VK_Bringup_RunDeviceSelfTest( char *outSummary, int summaryLength );

// destroys the instance a passed VK_Bringup_RunDeviceSelfTest kept; called
// once the renderer has created its own, and from VK_Bringup_Shutdown
void	VK_Bringup_ReleaseHeldInstance( void );

// releases any cached module state; called before the engine unloads the module
void	VK_Bringup_Shutdown( void );

#endif /* !__VULKANBRINGUP_H__ */
