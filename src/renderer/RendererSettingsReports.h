// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#ifndef __RENDERERSETTINGSREPORTS_H__
#define __RENDERERSETTINGSREPORTS_H__

#include <stdint.h>

// What the renderer tells the SYSTEM settings service (render API 20). Plain
// data, copied across the module boundary; the engine stamps its own serials.

// How the renderer resolved r_renderer when it selected a back end.
enum renderSelectionFallback_t {
	RENDER_SELECTION_REQUESTED		= 0,	// "best", or a named back end that is available here
	RENDER_SELECTION_UNAVAILABLE	= 1,	// the named back end is unavailable; the automatic pick runs
	RENDER_SELECTION_LEGACY			= 2		// a retired back-end name; the automatic pick runs
};

typedef struct renderRendererSelection_s {
	char			requested[ 32 ];			// r_renderer as the renderer read it, cut to fit
	int				selected;					// backEndName_t
	int				automatic;					// the back end "best" picks on this device
	int				fallback;					// renderSelectionFallback_t
	bool			promotionActive;			// the development auto-promotion of the modern path
	// OpenGL upload storage as the selection found it; Vulkan reports none.
	bool			uploadObserved;
	unsigned int	uploadPath;					// 1 subdata, 2 map-range, 3 persistent
	bool			uploadPersistentFallback;	// persistent mapping fell back to streaming
} renderRendererSelection_t;

// What one level load did with its light grids.
enum renderLightGridLoadOutcome_t {
	RENDER_LIGHTGRID_NO_ASSETS				= 1,	// the map has no baked light grids
	RENDER_LIGHTGRID_RENDERER_STOPPED		= 2,	// no device, so nothing was made resident
	RENDER_LIGHTGRID_STREAMED				= 3,	// areas stream in on first use
	RENDER_LIGHTGRID_PRELOADED				= 4,	// every usable area is resident
	RENDER_LIGHTGRID_PRELOAD_INCOMPLETE		= 5		// some usable areas failed to load
};

typedef struct renderLightGridLoadReceipt_s {
	uint64_t		token;			// the settings policy token the load used; 0 means r_lightGridPreload
	bool			preload;		// the policy the load used
	int				outcome;		// renderLightGridLoadOutcome_t
	int				areasUsable;
	int				areasResident;
} renderLightGridLoadReceipt_t;

#endif /* !__RENDERERSETTINGSREPORTS_H__ */
