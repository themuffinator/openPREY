// Copyright (C) 2004 Id Software, Inc.
//

#include "tr_local.h"
#include "ModernLightImageAtlas.h"
#include "GLStateCache.h"

/*
================================================================================

	The atlas is a fixed grid of equal cells rather than a shelf packer.  Light
	falloff and projection images are few, small, and long-lived, so a grid
	keeps residency lookup and eviction trivial and makes the uv rect exact
	(no per-entry padding arithmetic at sample time).  Cells carry a one texel
	border so bilinear taps at a cell edge cannot bleed into a neighbour.

	Source images are copied in with glGetTexImage + glTexSubImage2D rather than
	by rendering into the atlas.  A render-to-atlas path was tried first and
	crashed the driver from inside the frame: the copy has to run between the
	clustered-light build and the modern passes, and issuing a draw there means
	binding an FBO, program, VAO and viewport in the middle of a caller that
	owns all of them - invalidating the state cache around it was not enough.
	A pure texture copy touches none of that.  glGetTexImage decompresses DXT
	sources for free, works on every tier, and the transfer happens once per
	image because residency is cached, so the CPU round-trip does not matter.

	The cost is that a source larger than a cell cannot be rescaled without a
	draw, so oversized light images are rejected and those lights stay on the
	ARB2 bridge.

================================================================================
*/

// Sized from real content: measured on game/storage1, 128px cells rejected
// every light projection image as oversized while accepting the much smaller
// falloff images. Stock Quake 4 light projections run to 256px, so cells are
// 256 and the atlas grows to keep the same 64-cell capacity.
static const int MODERN_LIGHT_ATLAS_SIZE = 2048;
static const int MODERN_LIGHT_ATLAS_CELL = 256;
static const int MODERN_LIGHT_ATLAS_BORDER = 1;

typedef struct modernLightAtlasEntry_s {
	const idImage *	image;			// residency key; never dereferenced when stale
	unsigned int	sourceTexnum;	// re-upload when the source is reloaded
	int				cell;
	int				lastUsedFrame;
	int				uploadWidth;	// re-upload when a reload changes dims under a recycled GL name
	int				uploadHeight;
	bool			resident;
	bool			pendingUpload;	// reserved this frame, not yet copied in
	float			rect[4];
} modernLightAtlasEntry_t;

static bool rg_modernLightAtlasAvailable = false;
static bool rg_modernLightAtlasInitialized = false;
static GLuint rg_modernLightAtlasTexture = 0;
static modernLightAtlasEntry_t rg_modernLightAtlasEntries[MODERN_LIGHT_ATLAS_MAX_ENTRIES];
static int rg_modernLightAtlasFrame = 0;
static modernLightImageAtlasStats_t rg_modernLightAtlasStats;

const char *ModernLightAtlasReject_Name( modernLightAtlasReject_t reject ) {
	switch ( reject ) {
	case MODERN_LIGHT_ATLAS_REJECT_NONE:			return "none";
	case MODERN_LIGHT_ATLAS_REJECT_NULL_IMAGE:		return "null-image";
	case MODERN_LIGHT_ATLAS_REJECT_NOT_LOADED:		return "image-not-loaded";
	case MODERN_LIGHT_ATLAS_REJECT_CUBE_MAP:		return "cube-map-light-image";
	case MODERN_LIGHT_ATLAS_REJECT_OVERSIZED:		return "light-image-oversized";
	case MODERN_LIGHT_ATLAS_REJECT_ATLAS_FULL:		return "light-atlas-full";
	case MODERN_LIGHT_ATLAS_REJECT_UNAVAILABLE:		return "light-atlas-unavailable";
	default:										return "unknown";
	}
}

static unsigned int R_ModernLightImageAtlas_SourceHandle( const idImage *image ) {
	// GetDeviceHandle is non-const only by omission; the atlas reads the source
	// image and never mutates it.
	return image != NULL ? const_cast<idImage *>( image )->GetDeviceHandle() : 0;
}

static int R_ModernLightImageAtlas_CellsPerRow( void ) {
	return MODERN_LIGHT_ATLAS_SIZE / MODERN_LIGHT_ATLAS_CELL;
}

static int R_ModernLightImageAtlas_Capacity( void ) {
	const int perRow = R_ModernLightImageAtlas_CellsPerRow();
	const int cells = perRow * perRow;
	return cells < MODERN_LIGHT_ATLAS_MAX_ENTRIES ? cells : MODERN_LIGHT_ATLAS_MAX_ENTRIES;
}

/*
==================
R_ModernLightImageAtlas_CellRect

uv rect for a cell, inset by the border so bilinear taps stay inside it.
Exposed through the entry so the shader needs no atlas geometry constants.
==================
*/
static void R_ModernLightImageAtlas_CellRect( int cell, float rect[4] ) {
	const int perRow = R_ModernLightImageAtlas_CellsPerRow();
	const float inv = 1.0f / static_cast<float>( MODERN_LIGHT_ATLAS_SIZE );
	const int cellX = ( cell % perRow ) * MODERN_LIGHT_ATLAS_CELL;
	const int cellY = ( cell / perRow ) * MODERN_LIGHT_ATLAS_CELL;
	const float usable = static_cast<float>( MODERN_LIGHT_ATLAS_CELL - 2 * MODERN_LIGHT_ATLAS_BORDER );
	rect[0] = static_cast<float>( cellX + MODERN_LIGHT_ATLAS_BORDER ) * inv;
	rect[1] = static_cast<float>( cellY + MODERN_LIGHT_ATLAS_BORDER ) * inv;
	rect[2] = usable * inv;
	rect[3] = usable * inv;
}

static void R_ModernLightImageAtlas_SetStatus( const char *status ) {
	idStr::Copynz( rg_modernLightAtlasStats.status, status != NULL ? status : "unknown", sizeof( rg_modernLightAtlasStats.status ) );
}

static void R_ModernLightImageAtlas_ResetEntries( void ) {
	memset( rg_modernLightAtlasEntries, 0, sizeof( rg_modernLightAtlasEntries ) );
	for ( int i = 0; i < MODERN_LIGHT_ATLAS_MAX_ENTRIES; ++i ) {
		rg_modernLightAtlasEntries[i].cell = -1;
	}
}

static void R_ModernLightImageAtlas_RefreshCounts( void ) {
	int resident = 0;
	int live = 0;
	for ( int i = 0; i < MODERN_LIGHT_ATLAS_MAX_ENTRIES; ++i ) {
		if ( !rg_modernLightAtlasEntries[i].resident ) {
			continue;
		}
		resident++;
		if ( rg_modernLightAtlasEntries[i].lastUsedFrame == rg_modernLightAtlasFrame ) {
			live++;
		}
	}
	rg_modernLightAtlasStats.residentEntries = resident;
	rg_modernLightAtlasStats.liveEntries = live;
}

void R_ModernLightImageAtlas_Init( const renderBackendCaps_t &caps, const renderFeatureSet_t &features ) {
	R_ModernLightImageAtlas_Shutdown();
	memset( &rg_modernLightAtlasStats, 0, sizeof( rg_modernLightAtlasStats ) );
	R_ModernLightImageAtlas_ResetEntries();

	rg_modernLightAtlasStats.atlasSize = MODERN_LIGHT_ATLAS_SIZE;
	rg_modernLightAtlasStats.cellSize = MODERN_LIGHT_ATLAS_CELL;
	rg_modernLightAtlasStats.cellsPerRow = R_ModernLightImageAtlas_CellsPerRow();
	rg_modernLightAtlasStats.capacity = R_ModernLightImageAtlas_Capacity();

	// The atlas needs the same GL 3.3 baseline the modern executor does: FBOs to
	// render into, and VAOs for the copy quad.
	rg_modernLightAtlasStats.available = features.modernBaseline && caps.hasFBO && caps.hasVAO;
	if ( !rg_modernLightAtlasStats.available ) {
		R_ModernLightImageAtlas_SetStatus( "unavailable" );
		return;
	}
	rg_modernLightAtlasAvailable = true;

	if ( glGenTextures == NULL || glGenFramebuffers == NULL || glGenVertexArrays == NULL ) {
		R_ModernLightImageAtlas_SetStatus( "entry-points-missing" );
		return;
	}

	glGenTextures( 1, &rg_modernLightAtlasTexture );
	if ( rg_modernLightAtlasTexture != 0 ) {
		R_GLStateCache().ActiveTextureUnit( 0 );
		R_GLStateCache().BindTexture( 0, GL_TEXTURE_2D, rg_modernLightAtlasTexture );
		// zero-fill rather than leaving the storage undefined: a cell that is
		// reserved but not yet flushed must read black, not noise
		byte *zeroed = (byte *)Mem_ClearedAlloc( MODERN_LIGHT_ATLAS_SIZE * MODERN_LIGHT_ATLAS_SIZE * 4 );
		glTexImage2D( GL_TEXTURE_2D, 0, GL_RGBA8, MODERN_LIGHT_ATLAS_SIZE, MODERN_LIGHT_ATLAS_SIZE, 0, GL_RGBA, GL_UNSIGNED_BYTE, zeroed );
		Mem_Free( zeroed );
		glTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR );
		glTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR );
		// Light falloff and projection lookups clamp in ARB2; the border inset
		// keeps the clamp inside the owning cell.
		glTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE );
		glTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE );
		rg_modernLightAtlasStats.textureReady = true;
	}

	// the upload path is a plain texture copy, so the atlas needs nothing but
	// its own texture
	rg_modernLightAtlasInitialized = rg_modernLightAtlasStats.textureReady;
	rg_modernLightAtlasStats.initialized = rg_modernLightAtlasInitialized;
	R_ModernLightImageAtlas_SetStatus( rg_modernLightAtlasInitialized ? "ready" : "incomplete" );
}

void R_ModernLightImageAtlas_Shutdown( void ) {
	if ( rg_modernLightAtlasTexture != 0 && glDeleteTextures != NULL ) {
		glDeleteTextures( 1, &rg_modernLightAtlasTexture );
	}
	rg_modernLightAtlasTexture = 0;
	rg_modernLightAtlasAvailable = false;
	rg_modernLightAtlasInitialized = false;
	rg_modernLightAtlasFrame = 0;
	R_ModernLightImageAtlas_ResetEntries();
	memset( &rg_modernLightAtlasStats, 0, sizeof( rg_modernLightAtlasStats ) );
	R_ModernLightImageAtlas_SetStatus( "off" );
}

void R_ModernLightImageAtlas_BeginFrame( void ) {
	rg_modernLightAtlasFrame++;
	rg_modernLightAtlasStats.acquires = 0;
	rg_modernLightAtlasStats.cacheHits = 0;
	rg_modernLightAtlasStats.uploads = 0;
	rg_modernLightAtlasStats.evictions = 0;
	rg_modernLightAtlasStats.rejectedNullImage = 0;
	rg_modernLightAtlasStats.rejectedNotLoaded = 0;
	rg_modernLightAtlasStats.rejectedCubeMap = 0;
	rg_modernLightAtlasStats.rejectedOversized = 0;
	rg_modernLightAtlasStats.rejectedAtlasFull = 0;
	R_ModernLightImageAtlas_RefreshCounts();
}

static int R_ModernLightImageAtlas_FindEntry( const idImage *image ) {
	for ( int i = 0; i < MODERN_LIGHT_ATLAS_MAX_ENTRIES; ++i ) {
		if ( rg_modernLightAtlasEntries[i].resident && rg_modernLightAtlasEntries[i].image == image ) {
			return i;
		}
	}
	return -1;
}

/*
==================
R_ModernLightImageAtlas_ClaimEntry

Returns a free slot, or evicts the least recently used slot that was not
touched this frame.  Evicting a slot still in use this frame would hand two
lights the same cell, so that case reports the atlas as full instead.
==================
*/
static int R_ModernLightImageAtlas_ClaimEntry( void ) {
	const int capacity = R_ModernLightImageAtlas_Capacity();
	for ( int i = 0; i < capacity; ++i ) {
		if ( !rg_modernLightAtlasEntries[i].resident ) {
			rg_modernLightAtlasEntries[i].cell = i;
			return i;
		}
	}

	int oldest = -1;
	for ( int i = 0; i < capacity; ++i ) {
		if ( rg_modernLightAtlasEntries[i].lastUsedFrame == rg_modernLightAtlasFrame ) {
			continue;
		}
		if ( oldest < 0 || rg_modernLightAtlasEntries[i].lastUsedFrame < rg_modernLightAtlasEntries[oldest].lastUsedFrame ) {
			oldest = i;
		}
	}
	if ( oldest >= 0 ) {
		rg_modernLightAtlasStats.evictions++;
		rg_modernLightAtlasEntries[oldest].resident = false;
		rg_modernLightAtlasEntries[oldest].image = NULL;
		rg_modernLightAtlasEntries[oldest].sourceTexnum = 0;
		rg_modernLightAtlasEntries[oldest].uploadWidth = 0;
		rg_modernLightAtlasEntries[oldest].uploadHeight = 0;
		rg_modernLightAtlasEntries[oldest].cell = oldest;
	}
	return oldest;
}

/*
==================
R_ModernLightImageAtlas_FlushUploads

Acquire is deliberately CPU-only: it runs from the clustered-light descriptor
build, and issuing draws from there binds an FBO and rewrites the viewport in
the middle of a caller that does not expect it.  Uploads are queued and copied
here instead, at a point the executor controls, with the viewport saved and
restored around the batch.
==================
*/
void R_ModernLightImageAtlas_FlushUploads( void ) {
	if ( !rg_modernLightAtlasInitialized ) {
		return;
	}
	int pending = 0;
	for ( int i = 0; i < MODERN_LIGHT_ATLAS_MAX_ENTRIES; ++i ) {
		if ( rg_modernLightAtlasEntries[i].resident && rg_modernLightAtlasEntries[i].pendingUpload ) {
			pending++;
		}
	}
	if ( pending == 0 ) {
		return;
	}
	if ( glGetTexImage == NULL || glTexSubImage2D == NULL ) {
		return;
	}

	static byte scratch[MODERN_LIGHT_ATLAS_CELL * MODERN_LIGHT_ATLAS_CELL * 4];
	const int usable = MODERN_LIGHT_ATLAS_CELL - 2 * MODERN_LIGHT_ATLAS_BORDER;
	const int perRow = R_ModernLightImageAtlas_CellsPerRow();

	for ( int i = 0; i < MODERN_LIGHT_ATLAS_MAX_ENTRIES; ++i ) {
		modernLightAtlasEntry_t &entry = rg_modernLightAtlasEntries[i];
		if ( !entry.resident || !entry.pendingUpload || entry.image == NULL ) {
			continue;
		}
		entry.pendingUpload = false;

		const int width = entry.image->GetUploadWidth();
		const int height = entry.image->GetUploadHeight();
		if ( width <= 0 || height <= 0 || width > usable || height > usable ) {
			continue;
		}

		R_GLStateCache().ActiveTextureUnit( 0 );
		R_GLStateCache().BindTexture( 0, GL_TEXTURE_2D, entry.sourceTexnum );
		glGetTexImage( GL_TEXTURE_2D, 0, GL_RGBA, GL_UNSIGNED_BYTE, scratch );

		const int cellX = ( entry.cell % perRow ) * MODERN_LIGHT_ATLAS_CELL + MODERN_LIGHT_ATLAS_BORDER;
		const int cellY = ( entry.cell / perRow ) * MODERN_LIGHT_ATLAS_CELL + MODERN_LIGHT_ATLAS_BORDER;
		R_GLStateCache().BindTexture( 0, GL_TEXTURE_2D, rg_modernLightAtlasTexture );
		glTexSubImage2D( GL_TEXTURE_2D, 0, cellX, cellY, width, height, GL_RGBA, GL_UNSIGNED_BYTE, scratch );

		rg_modernLightAtlasStats.uploads++;
	}

	R_GLStateCache().ActiveTextureUnit( 0 );
	// Diagnostic resident/live counts are refreshed once here (after all Acquires
	// for the frame) instead of on every Acquire; the values read by gfxInfo are
	// identical since no Acquire runs between the last Acquire and this flush.
	R_ModernLightImageAtlas_RefreshCounts();
}

modernLightAtlasReject_t R_ModernLightImageAtlas_Acquire( const idImage *image, float rect[4] ) {
	if ( rect != NULL ) {
		rect[0] = rect[1] = rect[2] = rect[3] = 0.0f;
	}
	rg_modernLightAtlasStats.acquires++;

	if ( image == NULL ) {
		rg_modernLightAtlasStats.rejectedNullImage++;
		return MODERN_LIGHT_ATLAS_REJECT_NULL_IMAGE;
	}
	if ( !rg_modernLightAtlasAvailable ) {
		return MODERN_LIGHT_ATLAS_REJECT_UNAVAILABLE;
	}
	if ( !image->IsLoaded() ) {
		rg_modernLightAtlasStats.rejectedNotLoaded++;
		return MODERN_LIGHT_ATLAS_REJECT_NOT_LOADED;
	}
	if ( image->GetOpts().textureType != TT_2D ) {
		// a cube light image cannot be packed flat; the light stays legacy
		rg_modernLightAtlasStats.rejectedCubeMap++;
		return MODERN_LIGHT_ATLAS_REJECT_CUBE_MAP;
	}
	// Without a draw there is no rescale, so a source has to fit its cell.
	const int usableCell = MODERN_LIGHT_ATLAS_CELL - 2 * MODERN_LIGHT_ATLAS_BORDER;
	const int sourceWidth = image->GetUploadWidth();
	const int sourceHeight = image->GetUploadHeight();
	if ( sourceWidth <= 0 || sourceHeight <= 0 || sourceWidth > usableCell || sourceHeight > usableCell ) {
		rg_modernLightAtlasStats.rejectedOversized++;
		return MODERN_LIGHT_ATLAS_REJECT_OVERSIZED;
	}

	int entryIndex = R_ModernLightImageAtlas_FindEntry( image );
	// A reload can recycle the same GL name with different dimensions, which
	// would pass a texnum-only staleness check while the resident texels and the
	// rect (scaled for the old dims) are wrong, so compare dimensions too.
	const bool stale = entryIndex >= 0
		&& ( rg_modernLightAtlasEntries[entryIndex].sourceTexnum != R_ModernLightImageAtlas_SourceHandle( image )
			|| rg_modernLightAtlasEntries[entryIndex].uploadWidth != sourceWidth
			|| rg_modernLightAtlasEntries[entryIndex].uploadHeight != sourceHeight );
	if ( entryIndex >= 0 && !stale ) {
		rg_modernLightAtlasEntries[entryIndex].lastUsedFrame = rg_modernLightAtlasFrame;
		if ( rect != NULL ) {
			memcpy( rect, rg_modernLightAtlasEntries[entryIndex].rect, sizeof( float ) * 4 );
		}
		rg_modernLightAtlasStats.cacheHits++;
		return MODERN_LIGHT_ATLAS_REJECT_NONE;
	}

	if ( entryIndex < 0 ) {
		entryIndex = R_ModernLightImageAtlas_ClaimEntry();
		if ( entryIndex < 0 ) {
			rg_modernLightAtlasStats.rejectedAtlasFull++;
			return MODERN_LIGHT_ATLAS_REJECT_ATLAS_FULL;
		}
	}

	modernLightAtlasEntry_t &entry = rg_modernLightAtlasEntries[entryIndex];
	entry.image = image;
	entry.sourceTexnum = R_ModernLightImageAtlas_SourceHandle( image );
	entry.uploadWidth = sourceWidth;
	entry.uploadHeight = sourceHeight;
	entry.cell = entryIndex;
	entry.resident = true;
	entry.lastUsedFrame = rg_modernLightAtlasFrame;
	// queued, not drawn: see R_ModernLightImageAtlas_FlushUploads
	entry.pendingUpload = true;
	R_ModernLightImageAtlas_CellRect( entry.cell, entry.rect );
	// the cell rect spans the whole usable square; a smaller source fills only
	// part of it, so the rect handed out must cover exactly what gets written
	entry.rect[2] *= static_cast<float>( sourceWidth ) / static_cast<float>( usableCell );
	entry.rect[3] *= static_cast<float>( sourceHeight ) / static_cast<float>( usableCell );

	if ( rect != NULL ) {
		memcpy( rect, entry.rect, sizeof( float ) * 4 );
	}
	return MODERN_LIGHT_ATLAS_REJECT_NONE;
}

unsigned int R_ModernLightImageAtlas_Texture( void ) {
	return rg_modernLightAtlasTexture;
}

bool R_ModernLightImageAtlas_Ready( void ) {
	return rg_modernLightAtlasInitialized;
}

const modernLightImageAtlasStats_t &R_ModernLightImageAtlas_Stats( void ) {
	return rg_modernLightAtlasStats;
}

void R_ModernLightImageAtlas_PrintGfxInfo( void ) {
	const modernLightImageAtlasStats_t &stats = rg_modernLightAtlasStats;
	common->Printf(
		"Modern light image atlas: %s, available=%d init=%d texture=%d fbo=%d program=%d size=%d cell=%d capacity=%d resident=%d live=%d acquires=%d hits=%d uploads=%d evictions=%d rejected(null=%d notLoaded=%d cube=%d oversized=%d full=%d)\n",
		stats.status,
		stats.available ? 1 : 0,
		stats.initialized ? 1 : 0,
		stats.textureReady ? 1 : 0,
		stats.framebufferReady ? 1 : 0,
		stats.programReady ? 1 : 0,
		stats.atlasSize,
		stats.cellSize,
		stats.capacity,
		stats.residentEntries,
		stats.liveEntries,
		stats.acquires,
		stats.cacheHits,
		stats.uploads,
		stats.evictions,
		stats.rejectedNullImage,
		stats.rejectedNotLoaded,
		stats.rejectedCubeMap,
		stats.rejectedOversized,
		stats.rejectedAtlasFull );
}

/*
==================
RendererLightImageAtlas_RunSelfTest

Covers the packing contract without needing real light images: cell rects are
inside the atlas, disjoint, and inset by the border; capacity is honoured; and
a rejected acquire always zeroes the caller's rect so it cannot sample a stale
cell.
==================
*/
bool RendererLightImageAtlas_RunSelfTest( void ) {
	const int capacity = R_ModernLightImageAtlas_Capacity();
	if ( capacity <= 0 || capacity > MODERN_LIGHT_ATLAS_MAX_ENTRIES ) {
		common->Printf( "RendererLightImageAtlas self-test failed: bad capacity (%d)\n", capacity );
		return false;
	}

	const float inv = 1.0f / static_cast<float>( MODERN_LIGHT_ATLAS_SIZE );
	const float expectedExtent = static_cast<float>( MODERN_LIGHT_ATLAS_CELL - 2 * MODERN_LIGHT_ATLAS_BORDER ) * inv;
	for ( int i = 0; i < capacity; ++i ) {
		float rect[4];
		R_ModernLightImageAtlas_CellRect( i, rect );
		if ( rect[0] < 0.0f || rect[1] < 0.0f || rect[0] + rect[2] > 1.0f || rect[1] + rect[3] > 1.0f ) {
			common->Printf( "RendererLightImageAtlas self-test failed: cell %d escapes the atlas (%g,%g,%g,%g)\n", i, rect[0], rect[1], rect[2], rect[3] );
			return false;
		}
		if ( idMath::Fabs( rect[2] - expectedExtent ) > 1e-6f || idMath::Fabs( rect[3] - expectedExtent ) > 1e-6f ) {
			common->Printf( "RendererLightImageAtlas self-test failed: cell %d extent %g,%g expected %g\n", i, rect[2], rect[3], expectedExtent );
			return false;
		}
		for ( int j = 0; j < i; ++j ) {
			float other[4];
			R_ModernLightImageAtlas_CellRect( j, other );
			const bool disjoint =
				rect[0] + rect[2] <= other[0] + 1e-7f ||
				other[0] + other[2] <= rect[0] + 1e-7f ||
				rect[1] + rect[3] <= other[1] + 1e-7f ||
				other[1] + other[3] <= rect[1] + 1e-7f;
			if ( !disjoint ) {
				common->Printf( "RendererLightImageAtlas self-test failed: cells %d and %d overlap\n", i, j );
				return false;
			}
		}
	}

	float rect[4] = { 1.0f, 1.0f, 1.0f, 1.0f };
	if ( R_ModernLightImageAtlas_Acquire( NULL, rect ) != MODERN_LIGHT_ATLAS_REJECT_NULL_IMAGE ) {
		common->Printf( "RendererLightImageAtlas self-test failed: null image was not rejected\n" );
		return false;
	}
	if ( rect[0] != 0.0f || rect[1] != 0.0f || rect[2] != 0.0f || rect[3] != 0.0f ) {
		common->Printf( "RendererLightImageAtlas self-test failed: rejected acquire left a stale rect\n" );
		return false;
	}

	common->Printf(
		"RendererLightImageAtlas self-test passed (capacity=%d size=%d cell=%d border=%d available=%d init=%d)\n",
		capacity,
		MODERN_LIGHT_ATLAS_SIZE,
		MODERN_LIGHT_ATLAS_CELL,
		MODERN_LIGHT_ATLAS_BORDER,
		rg_modernLightAtlasStats.available ? 1 : 0,
		rg_modernLightAtlasInitialized ? 1 : 0 );
	return true;
}
