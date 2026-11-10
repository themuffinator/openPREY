/*
===========================================================================

Doom 3 GPL Source Code
Copyright (C) 1999-2011 id Software LLC, a ZeniMax Media company.

This file is part of the Doom 3 GPL Source Code. See docs/legal for details.

===========================================================================
*/

#include "../../idlib/precompiled.h"
#include "../../renderer/tr_local.h"

#include <ApplicationServices/ApplicationServices.h>

#define OPENQ4_SDL3_DARWIN_HOST 1
#include "../sdl3/sdl3_backend.cpp"

bool QGL_Init(const char *dllname) {
	(void)dllname;
	return true;
}

void QGL_Shutdown(void) {
}

bool Sys_GetDesktopResolution(int *width, int *height) {
	return SDL3_QueryDesktopResolution(width, height, "SDL3 macOS");
}

CGDirectDisplayID Sys_DisplayToUse(void) {
	CGDirectDisplayID displays[32];
	CGDisplayCount displayCount = 0;
	const CGError err = CGGetActiveDisplayList(static_cast<CGDisplayCount>(sizeof(displays) / sizeof(displays[0])), displays, &displayCount);

	const int requestedScreen = r_screen.GetInteger();
	if (requestedScreen >= 0) {
		if (err == kCGErrorSuccess && requestedScreen < static_cast<int>(displayCount)) {
			return displays[requestedScreen];
		}
	}

	const CGDirectDisplayID mainDisplay = CGMainDisplayID();
	if (mainDisplay != 0) {
		return mainDisplay;
	}
	if (err == kCGErrorSuccess && displayCount > 0) {
		return displays[0];
	}
	return 0;
}
