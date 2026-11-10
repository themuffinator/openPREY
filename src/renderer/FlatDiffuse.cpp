// Copyright (C) 2026 DarkMatter Productions
//

#include "tr_local.h"

/*
=================
RB_FlatDiffuseSurfaceActive

Flat diffuse is presentation-only renderer state.  The weapon depth hack is a
hard safety boundary so a tagged entity can never alter the first-person
weapon, regardless of the game-side configuration.
=================
*/
bool RB_FlatDiffuseSurfaceActive( const drawSurf_t *surf ) {
	return surf != NULL
		&& surf->space != NULL
		&& !surf->space->weaponDepthHack
		&& ( surf->space->flatDiffuseFlags & REF_FLAT_DIFFUSE ) != 0;
}

bool RB_FlatDiffuseSweepActive( const drawSurf_t *surf ) {
	return RB_FlatDiffuseSurfaceActive( surf )
		&& ( surf->space->flatDiffuseFlags & REF_FLAT_DIFFUSE_SWEEP ) != 0
		&& surf->space->flatDiffuseInvHeight > 0.0f;
}

/*
=================
RB_GetFlatDiffuseParams

The shader receives a compact fixed-style contract:
  x = lightness-band strength, y = model-local minimum Z,
  z = inverse model-local height, w = upward cyclic phase.
Zero strength is the branch-free disabled state used by held world weapons.
=================
*/
void RB_GetFlatDiffuseParams( const drawSurf_t *surf, idVec4 &params ) {
	params.Zero();
	if ( !RB_FlatDiffuseSweepActive( surf ) || backEnd.viewDef == NULL ) {
		return;
	}

	static const float FLAT_DIFFUSE_SWEEP_STRENGTH = 0.30f;
	static const float FLAT_DIFFUSE_SWEEP_CYCLES_PER_SECOND = 0.28f;
	float phase = backEnd.viewDef->floatTime * FLAT_DIFFUSE_SWEEP_CYCLES_PER_SECOND;
	phase -= idMath::Floor( phase );

	params.Set(
		FLAT_DIFFUSE_SWEEP_STRENGTH,
		surf->space->flatDiffuseMinZ,
		surf->space->flatDiffuseInvHeight,
		phase );
}

/*
=================
RB_ApplyFlatDiffuseStage

Replace only the lit diffuse image RGB.  Alpha testing/depth coverage and
ambient/translucent stages continue to use the authored material image in
their own passes; bump and specular are untouched.
=================
*/
void RB_ApplyFlatDiffuseStage( const drawSurf_t *surf, idImage **diffuseImage, float diffuseColor[4], idVec4 &params ) {
	params.Zero();
	if ( !RB_FlatDiffuseSurfaceActive( surf )
		|| diffuseImage == NULL
		|| *diffuseImage == NULL
		|| *diffuseImage == globalImages->blackImage
		|| diffuseColor == NULL ) {
		return;
	}

	*diffuseImage = globalImages->whiteImage;
	for ( int component = 0; component < 3; component++ ) {
		const float flatColor = idMath::ClampFloat( 0.0f, 1.0f, surf->space->flatDiffuseColor[component] );
		diffuseColor[component] *= flatColor;
	}
	RB_GetFlatDiffuseParams( surf, params );
}
