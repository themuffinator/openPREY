// Copyright (C) 2004 Id Software, Inc.
//

#ifndef __CELSHADING_H__
#define __CELSHADING_H__

/*
===============================================================================

	Cel shading policy.

	openQ4's cel look is assembled from three cooperating pieces:

	  1. banded lighting, applied inside the interaction shaders so every
	     additive light contributes a quantized ramp instead of a smooth one;
	  2. silhouette outline shells drawn around cel-shaded model entities;
	  3. a screen-space depth/normal edge pass that inks world geometry, which
	     has no shell of its own to expand.

	Everything here is pure policy and math: which surfaces participate, how
	many bands they get, how wide their outline is and what colour it uses.
	No GL state is touched, so the backend passes stay readable and the rules
	stay in one testable place.

===============================================================================
*/

typedef struct drawSurf_s drawSurf_t;

// Band ladder shared by every cel consumer.
static const int CEL_MIN_BANDS = 2;
static const int CEL_MAX_BANDS = 8;

// How much of a band width each boundary is allowed to blend across. 0 is the
// classic hard step; 1 spreads the transition over a whole band, which is
// nearly smooth again but keeps the band count's tonal spacing.
static const float CEL_MIN_BAND_SOFTNESS = 0.0f;
static const float CEL_MAX_BAND_SOFTNESS = 1.0f;

// Outline widths are authored in pixels and converted to a model expansion
// scale per surface, so a silhouette stays the same thickness at any range.
static const float CEL_MIN_OUTLINE_WIDTH = 0.5f;
static const float CEL_MAX_OUTLINE_WIDTH = 8.0f;

// Screen-space world edge detection radius, also in pixels.
static const float CEL_MIN_WORLD_OUTLINE_WIDTH = 1.0f;
static const float CEL_MAX_WORLD_OUTLINE_WIDTH = 8.0f;

// Number of quantization steps requested by r_celShadingSteps, clamped.
int			R_CelBandCount( void );

// Band edge softness requested by r_celShadingSoftness, clamped.
float		R_CelBandSoftness( void );

// Quantize a 0..1 intensity onto the band ladder. Values outside the open
// interval pass through untouched so full black and full white stay exact.
float		R_CelQuantizeUnitValue( float value );

// Master gates. Cheap enough to call per surface; they only read cvars.
bool		R_CelShadingEnabled( void );			// models participate
bool		R_CelShadingWorldEnabled( void );		// world participates
bool		R_CelShadingAnyEnabled( void );			// either of the above
bool		R_CelOutlineEnabled( void );			// model outline shells
bool		R_CelWorldOutlineEnabled( void );		// screen-space world edges

// Surface classification.
bool		R_CelSurfaceIsWorld( const drawSurf_t *surf );
bool		R_CelSurfaceIsViewWeapon( const drawSurf_t *surf );

// True when this surface's lighting should be quantized into cel bands.
bool		R_CelShadingSurfaceActive( const drawSurf_t *surf );

// True when this surface should receive an outline shell.
bool		R_CelOutlineSurfaceActive( const drawSurf_t *surf );

// Outline appearance for a surface, honouring the separate view-weapon knobs.
float		R_CelOutlineWidthForSurface( const drawSurf_t *surf );
float		R_CelOutlineAlphaForSurface( const drawSurf_t *surf );

// Parsed "r g b a" outline colour with the surface alpha multiplier applied.
// Components are returned in 0..1.
void		R_CelOutlineColorForSurface( const drawSurf_t *surf, idVec4 &color );

// Screen-space world edge colour: the shared ink colour at the world alpha.
void		R_CelWorldOutlineColor( idVec4 &color );

// Screen-space world edge tuning, pre-clamped.
float		R_CelWorldOutlineWidth( void );
float		R_CelWorldOutlineAlpha( void );
float		R_CelWorldOutlineDepthThreshold( void );
float		R_CelWorldOutlineNormalThreshold( void );

#endif /* !__CELSHADING_H__ */
