// Copyright (C) 2026 DarkMatter Productions
//

#include "src/renderer/ModernSpecularProbeAtlas.h"

#include <cstdio>

static int failures = 0;

static void Check( bool condition, const char *message ) {
	if ( condition ) {
		return;
	}
	std::fprintf( stderr,
		"ModernSpecularProbeAtlasPackingTest: %s\n", message );
	failures++;
}

int main() {
	modernSpecularProbeAtlasPlacement_t placements[
		MODERN_SPECULAR_PROBE_ATLAS_MAX_ENTRIES];
	for ( int slot = 0; slot < MODERN_SPECULAR_PROBE_ATLAS_MAX_ENTRIES; ++slot ) {
		Check( ModernSpecularProbeAtlas_BuildPlacement( slot,
			MODERN_SPECULAR_PROBE_ATLAS_FACE_SIZE, placements[slot] ),
			"every bounded slot must pack" );
		Check( placements[slot].valid && placements[slot].slot == slot,
			"a packed placement must publish its stable slot" );
		for ( int face = 0; face < MODERN_SPECULAR_PROBE_ATLAS_FACE_COUNT; ++face ) {
			const int expectedCell =
				slot * MODERN_SPECULAR_PROBE_ATLAS_FACE_COUNT + face;
			Check( placements[slot].faceCells[face] == expectedCell,
				"faces must occupy consecutive cells in +X,-X,+Y,-Y,+Z,-Z order" );
			const float *rect = placements[slot].faceRects[face];
			Check( rect[0] >= 0.0f && rect[1] >= 0.0f
				&& rect[0] + rect[2] <= 1.0f
				&& rect[1] + rect[3] <= 1.0f,
				"face rectangles must stay inside the atlas" );
		}
	}

	for ( int slot = 0; slot < MODERN_SPECULAR_PROBE_ATLAS_MAX_ENTRIES; ++slot ) {
		for ( int face = 0; face < MODERN_SPECULAR_PROBE_ATLAS_FACE_COUNT; ++face ) {
			const float *rect = placements[slot].faceRects[face];
			const int flat = slot * MODERN_SPECULAR_PROBE_ATLAS_FACE_COUNT + face;
			for ( int prior = 0; prior < flat; ++prior ) {
				const int priorSlot = prior / MODERN_SPECULAR_PROBE_ATLAS_FACE_COUNT;
				const int priorFace = prior % MODERN_SPECULAR_PROBE_ATLAS_FACE_COUNT;
				const float *other = placements[priorSlot].faceRects[priorFace];
				Check( rect[0] + rect[2] < other[0]
						|| other[0] + other[2] < rect[0]
						|| rect[1] + rect[3] < other[1]
						|| other[1] + other[3] < rect[1],
					"face rectangles must be disjoint" );
			}
		}
	}

	modernSpecularProbeAtlasPlacement_t smaller;
	Check( ModernSpecularProbeAtlas_BuildPlacement( 0, 64, smaller )
		&& smaller.faceRects[0][2]
			== 255.0f / static_cast<float>( MODERN_SPECULAR_PROBE_ATLAS_SIZE ),
		"smaller source cubes must occupy complete filtered atlas cells" );

	modernSpecularProbeAtlasPlacement_t rejected;
	rejected.valid = true;
	Check( !ModernSpecularProbeAtlas_BuildPlacement( -1,
		MODERN_SPECULAR_PROBE_ATLAS_FACE_SIZE, rejected )
		&& !rejected.valid && rejected.slot == -1
		&& rejected.faceCells[0] == -1
		&& rejected.faceRects[0][0] == 0.0f,
		"invalid slots must fail closed and clear output" );
	Check( !ModernSpecularProbeAtlas_BuildPlacement( 0,
		MODERN_SPECULAR_PROBE_ATLAS_FACE_SIZE + 1, rejected )
		&& !rejected.valid,
		"oversized faces must not produce a placement" );

	if ( failures != 0 ) {
		return 1;
	}
	std::printf( "ModernSpecularProbeAtlasPackingTest: PASS\n" );
	return 0;
}
