// Copyright (C) 2004 Id Software, Inc.
//

#ifndef __MODERN_LIGHT_IMAGE_ATLAS_H__
#define __MODERN_LIGHT_IMAGE_ATLAS_H__

#include "RendererCaps.h"

class idImage;

/*
===============================================================================

	Shared falloff/projection atlas for the modern clustered light path.

	A Quake 4 light is textured: its shape and colour come from a light
	projection image and its distance response from a falloff image.  The
	clustered path samples many lights per pixel, so it cannot bind a texture
	pair per light the way the ARB2 interaction pass does.

	This packs those per-light 2D images into one atlas and hands back uv
	rects, so a light record can reference its own images by rect instead of by
	binding.  Bindless handles would also solve this, but only on GL 4.5+;
	the atlas keeps the GL 3.3/4.1 baseline tiers viable.

	Cube-map light images are intentionally out of scope: they cannot be packed
	into a 2D atlas, and lights that use one stay on the ARB2 bridge with an
	explicit blocker rather than being silently approximated.

===============================================================================
*/

static const int MODERN_LIGHT_ATLAS_MAX_ENTRIES = 128;

enum modernLightAtlasReject_t {
	MODERN_LIGHT_ATLAS_REJECT_NONE = 0,
	MODERN_LIGHT_ATLAS_REJECT_NULL_IMAGE,
	MODERN_LIGHT_ATLAS_REJECT_NOT_LOADED,
	MODERN_LIGHT_ATLAS_REJECT_CUBE_MAP,
	MODERN_LIGHT_ATLAS_REJECT_OVERSIZED,
	MODERN_LIGHT_ATLAS_REJECT_ATLAS_FULL,
	MODERN_LIGHT_ATLAS_REJECT_UNAVAILABLE
};

typedef struct modernLightImageAtlasStats_s {
	bool	available;
	bool	initialized;
	bool	textureReady;
	bool	framebufferReady;
	bool	programReady;
	int		atlasSize;
	int		cellSize;
	int		cellsPerRow;
	int		capacity;
	int		residentEntries;
	int		liveEntries;
	int		acquires;
	int		cacheHits;
	int		uploads;
	int		evictions;
	int		rejectedNullImage;
	int		rejectedNotLoaded;
	int		rejectedCubeMap;
	int		rejectedOversized;
	int		rejectedAtlasFull;
	char	status[96];
} modernLightImageAtlasStats_t;

void R_ModernLightImageAtlas_Init( const renderBackendCaps_t &caps, const renderFeatureSet_t &features );
void R_ModernLightImageAtlas_Shutdown( void );
void R_ModernLightImageAtlas_BeginFrame( void );

// Packs image into the atlas if it is not already resident and fills rect with
// { uOffset, vOffset, uScale, vScale }. Returns MODERN_LIGHT_ATLAS_REJECT_NONE
// on success; rect is zeroed on every rejection so a caller that ignores the
// return value cannot sample a stale cell.
modernLightAtlasReject_t R_ModernLightImageAtlas_Acquire( const idImage *image, float rect[4] );

// Copies every cell reserved since the last flush. Acquire is CPU-only so it
// can be called from the clustered-light build; this must run at a point the
// caller controls, after that build and before anything samples the atlas.
void R_ModernLightImageAtlas_FlushUploads( void );

const char *ModernLightAtlasReject_Name( modernLightAtlasReject_t reject );
unsigned int R_ModernLightImageAtlas_Texture( void );
bool R_ModernLightImageAtlas_Ready( void );
const modernLightImageAtlasStats_t &R_ModernLightImageAtlas_Stats( void );
void R_ModernLightImageAtlas_PrintGfxInfo( void );
bool RendererLightImageAtlas_RunSelfTest( void );

#endif /* !__MODERN_LIGHT_IMAGE_ATLAS_H__ */
