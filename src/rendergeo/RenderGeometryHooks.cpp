// Copyright (C) 2026 DarkMatter Productions
//

#include "RenderGeometry.h"

/*
===============================================================================

	Hook state for the shared render-geometry library. The zeroed defaults
	are the dmap-correct behavior; NULL checks at the call sites supply the
	documented default values.

===============================================================================
*/

static renderGeoHooks_t rg_hooks;

void RenderGeo_SetHooks( const renderGeoHooks_t &hooks ) {
	// preserve an already-bound offline optimizer (dmap may have registered
	// before or after the renderer installs its live hooks)
	optimizedShadow_t ( *superOptimize )( idVec4 *, glIndex_t *, int, idPlane, idVec3 ) = rg_hooks.superOptimize;
	void ( *cleanup )( srfTriangles_t * ) = rg_hooks.cleanupOptimizedShadowTris;

	rg_hooks = hooks;

	if ( rg_hooks.superOptimize == NULL ) {
		rg_hooks.superOptimize = superOptimize;
	}
	if ( rg_hooks.cleanupOptimizedShadowTris == NULL ) {
		rg_hooks.cleanupOptimizedShadowTris = cleanup;
	}
}

void RenderGeo_SetShadowOptimizer( optimizedShadow_t ( *superOptimize )( idVec4 *, glIndex_t *, int, idPlane, idVec3 ),
								   void ( *cleanupOptimizedShadowTris )( srfTriangles_t * ) ) {
	rg_hooks.superOptimize = superOptimize;
	rg_hooks.cleanupOptimizedShadowTris = cleanupOptimizedShadowTris;
}

const renderGeoHooks_t &RenderGeo_GetHooks( void ) {
	return rg_hooks;
}
