// Copyright (C) 2004 Id Software, Inc.
//

#include "tr_local.h"
#include "CelShading.h"

/*
===============================================================================

	Cel shading policy.

	See CelShading.h for the shape of the feature. This translation unit owns
	every rule that decides whether a surface is cel shaded and what its
	outline looks like, so the backend passes never have to re-derive it.

===============================================================================
*/

// The outline colour parser lives below the gates that need its alpha.
static void	R_CelParsedOutlineColor( idVec4 &color );

/*
==================
R_CelBandCount
==================
*/
int R_CelBandCount( void ) {
	return idMath::ClampInt( CEL_MIN_BANDS, CEL_MAX_BANDS, r_celShadingSteps.GetInteger() );
}

/*
==================
R_CelBandSoftness
==================
*/
float R_CelBandSoftness( void ) {
	return idMath::ClampFloat( CEL_MIN_BAND_SOFTNESS, CEL_MAX_BAND_SOFTNESS, r_celShadingSoftness.GetFloat() );
}

/*
==================
R_CelSmoothStep

GLSL's smoothstep, spelled out so the CPU ladder and the shader ladder agree
to the bit on where a softened band boundary sits.
==================
*/
static float R_CelSmoothStep( float edge0, float edge1, float value ) {
	if ( edge1 <= edge0 ) {
		return ( value < edge0 ) ? 0.0f : 1.0f;
	}

	const float t = idMath::ClampFloat( 0.0f, 1.0f, ( value - edge0 ) / ( edge1 - edge0 ) );

	return t * t * ( 3.0f - 2.0f * t );
}

/*
==================
R_CelQuantizeUnitValue

Snaps an intensity onto the band ladder. Both endpoints are preserved exactly
so unlit surfaces stay black and fully lit ones keep their peak value; only the
ramp between them is stepped.

r_celShadingSoftness widens each boundary into a smoothstep centred on the same
place the hard step would have landed. The plateaus survive - a boundary only
ever eats into the band on either side of it - but the transition itself stops
being a single texel wide, which is what kept the terminator crawling across a
curved surface as the camera moved. At 0 the result is bit-identical to the
hard step.
==================
*/
float R_CelQuantizeUnitValue( float value ) {
	if ( value <= 0.0f ) {
		return 0.0f;
	}
	if ( value >= 1.0f ) {
		return value;
	}

	const float steps = (float)R_CelBandCount() - 1.0f;
	if ( steps <= 0.0f ) {
		return value;
	}

	const float scaled = value * steps;
	const float softness = R_CelBandSoftness();
	if ( softness <= 0.0f ) {
		const float band = idMath::ClampFloat( 0.0f, steps, idMath::Floor( scaled + 0.5f ) );
		return band / steps;
	}

	// floor( scaled ) names the band below the pixel and the boundary above it
	// sits half a band away, so the blend window is centred on 0.5.
	const float lower = idMath::Floor( scaled );
	const float halfWidth = softness * 0.5f;
	const float blend = R_CelSmoothStep( 0.5f - halfWidth, 0.5f + halfWidth, scaled - lower );

	return idMath::ClampFloat( 0.0f, 1.0f, ( lower + blend ) / steps );
}

/*
==================
R_CelShadingEnabled
==================
*/
bool R_CelShadingEnabled( void ) {
	return r_celShading.GetBool();
}

/*
==================
R_CelShadingWorldEnabled
==================
*/
bool R_CelShadingWorldEnabled( void ) {
	return r_celShadingWorld.GetBool();
}

/*
==================
R_CelShadingAnyEnabled
==================
*/
bool R_CelShadingAnyEnabled( void ) {
	return R_CelShadingEnabled() || R_CelShadingWorldEnabled();
}

/*
==================
R_CelInkAlpha

The opacity r_celOutlineColor carries on its own, before any per-surface
multiplier. Zero here means every outline in the frame is invisible whatever
the other knobs say, and both outline passes reserve real resources - a stencil
bit for the shells, a depth prepass and a fullscreen pass for the world - long
before they discover a surface draws nothing. Asking up front is what keeps a
transparent ink as cheap as a disabled one.
==================
*/
static float R_CelInkAlpha( void ) {
	idVec4 color;
	R_CelParsedOutlineColor( color );

	return color.w;
}

/*
==================
R_CelOutlineEnabled
==================
*/
bool R_CelOutlineEnabled( void ) {
	return R_CelShadingEnabled() && r_celOutline.GetBool() && R_CelInkAlpha() > 0.0f;
}

/*
==================
R_CelWorldOutlineEnabled
==================
*/
bool R_CelWorldOutlineEnabled( void ) {
	return R_CelShadingWorldEnabled() && R_CelWorldOutlineAlpha() > 0.0f && R_CelInkAlpha() > 0.0f;
}

/*
==================
R_CelSurfaceIsWorld

BSP geometry arrives either through the synthetic world space (no entityDef at
all) or through the entity that owns the static world model.
==================
*/
bool R_CelSurfaceIsWorld( const drawSurf_t *surf ) {
	if ( surf == NULL || surf->space == NULL ) {
		return false;
	}

	const idRenderEntityLocal *entityDef = surf->space->entityDef;
	if ( entityDef == NULL || entityDef->parms.hModel == NULL ) {
		return true;
	}

	return entityDef->parms.hModel->IsStaticWorldModel();
}

/*
==================
R_CelSurfaceIsViewWeapon

The first-person weapon and the arms that carry it are the surfaces squashed
into the near depth range or restricted to the local player's view.
==================
*/
bool R_CelSurfaceIsViewWeapon( const drawSurf_t *surf ) {
	if ( surf == NULL || surf->space == NULL ) {
		return false;
	}
	if ( surf->space->weaponDepthHack ) {
		return true;
	}

	const idRenderEntityLocal *entityDef = surf->space->entityDef;
	if ( entityDef == NULL ) {
		return false;
	}

	const renderEntity_t &renderEntity = entityDef->parms;
	return renderEntity.weaponDepthHackInViewID != 0 || renderEntity.allowSurfaceInViewID != 0;
}

/*
==================
R_CelSurfaceParticipates

Shared front half of the per-surface gates: is this drawable geometry that the
cel treatment is allowed to touch at all, and is its class enabled?
==================
*/
static bool R_CelSurfaceParticipates( const drawSurf_t *surf ) {
	if ( surf == NULL || surf->space == NULL || surf->geo == NULL || surf->material == NULL ) {
		return false;
	}
	if ( ( surf->dsFlags & DSF_BSE_EFFECT ) != 0 ) {
		return false;
	}

	if ( R_CelSurfaceIsWorld( surf ) ) {
		return R_CelShadingWorldEnabled();
	}
	if ( R_CelSurfaceIsViewWeapon( surf ) ) {
		return R_CelShadingEnabled() && r_celViewWeapon.GetBool();
	}

	return R_CelShadingEnabled();
}

/*
==================
R_CelShadingSurfaceActive
==================
*/
bool R_CelShadingSurfaceActive( const drawSurf_t *surf ) {
	if ( !r_celShadingBands.GetBool() || !R_CelSurfaceParticipates( surf ) ) {
		return false;
	}

	// Banding is a lighting effect; surfaces that never take a light pass, and
	// translucent ones whose ramp is carrying the blend, are left alone.
	const idMaterial *material = surf->material;
	if ( !material->IsDrawn() || material->Coverage() == MC_TRANSLUCENT ) {
		return false;
	}

	return true;
}

/*
==================
R_CelOutlineSurfaceActive

Outline shells are a model-entity effect. World geometry is inked by the
screen-space pass instead, which is why world surfaces are rejected here even
when r_celShadingWorld is on.
==================
*/
bool R_CelOutlineSurfaceActive( const drawSurf_t *surf ) {
	if ( !R_CelOutlineEnabled() || surf == NULL ) {
		return false;
	}
	if ( R_CelSurfaceIsWorld( surf ) ) {
		return false;
	}
	if ( !R_CelSurfaceParticipates( surf ) ) {
		return false;
	}
	if ( R_CelOutlineAlphaForSurface( surf ) <= 0.0f ) {
		return false;
	}

	const idMaterial *material = surf->material;
	if ( !material->IsDrawn() || material->Coverage() == MC_TRANSLUCENT ) {
		return false;
	}
	if ( material->GetSort() >= SS_POST_PROCESS || material->GetSort() == SS_SUBVIEW ) {
		return false;
	}
	if ( material->HasGui() || material->SuppressInSubview() ) {
		return false;
	}

	return surf->geo->numIndexes > 0;
}

/*
==================
R_CelOutlineWidthForSurface
==================
*/
float R_CelOutlineWidthForSurface( const drawSurf_t *surf ) {
	const idCVar &width = R_CelSurfaceIsViewWeapon( surf ) ? r_celViewWeaponOutlineWidth : r_celOutlineWidth;

	return idMath::ClampFloat( CEL_MIN_OUTLINE_WIDTH, CEL_MAX_OUTLINE_WIDTH, width.GetFloat() );
}

/*
==================
R_CelOutlineAlphaForSurface
==================
*/
float R_CelOutlineAlphaForSurface( const drawSurf_t *surf ) {
	const idCVar &alpha = R_CelSurfaceIsViewWeapon( surf ) ? r_celViewWeaponOutlineAlpha : r_celOutlineAlpha;

	return idMath::ClampFloat( 0.0f, 1.0f, alpha.GetFloat() );
}

/*
==================
R_CelParsedOutlineColor

Parses r_celOutlineColor ("r g b a", 0-255) into normalized components. The
result is cached against the raw string so the common case costs a compare
rather than a parse, without disturbing the cvar's modified flag for anyone
else watching it.
==================
*/
static void R_CelParsedOutlineColor( idVec4 &color ) {
	static idStr	cachedSource;
	static idVec4	cachedColor( 0.0f, 0.0f, 0.0f, 1.0f );
	static bool		cachedValid = false;

	const char *source = r_celOutlineColor.GetString();
	if ( source == NULL ) {
		source = "";
	}

	if ( cachedValid && cachedSource.Cmp( source ) == 0 ) {
		color = cachedColor;
		return;
	}

	// An unparsable value keeps the classic ink colour rather than blanking
	// the outline, so a typo in a config never silently disables the effect.
	idVec4 parsed( 0.0f, 0.0f, 0.0f, 255.0f );
	const int parsedCount = sscanf( source, "%f %f %f %f", &parsed.x, &parsed.y, &parsed.z, &parsed.w );
	if ( parsedCount < 3 ) {
		parsed.Set( 0.0f, 0.0f, 0.0f, 255.0f );
	} else if ( parsedCount < 4 ) {
		parsed.w = 255.0f;
	}

	for ( int i = 0; i < 4; i++ ) {
		parsed[i] = idMath::ClampFloat( 0.0f, 255.0f, parsed[i] ) * ( 1.0f / 255.0f );
	}

	cachedSource = source;
	cachedColor = parsed;
	cachedValid = true;
	color = cachedColor;
}

/*
==================
R_CelOutlineColorForSurface
==================
*/
void R_CelOutlineColorForSurface( const drawSurf_t *surf, idVec4 &color ) {
	R_CelParsedOutlineColor( color );
	color.w *= R_CelOutlineAlphaForSurface( surf );
}

/*
==================
R_CelWorldOutlineColor

The world edge shares the ink colour with the model shells but takes its opacity
from r_celShadingWorldAlpha alone, so the two outline kinds can be balanced
against each other.
==================
*/
void R_CelWorldOutlineColor( idVec4 &color ) {
	R_CelParsedOutlineColor( color );
	color.w *= R_CelWorldOutlineAlpha();
}

/*
==================
R_CelWorldOutlineWidth
==================
*/
float R_CelWorldOutlineWidth( void ) {
	return idMath::ClampFloat( CEL_MIN_WORLD_OUTLINE_WIDTH, CEL_MAX_WORLD_OUTLINE_WIDTH,
		r_celShadingWorldWidth.GetFloat() );
}

/*
==================
R_CelWorldOutlineAlpha
==================
*/
float R_CelWorldOutlineAlpha( void ) {
	return idMath::ClampFloat( 0.0f, 1.0f, r_celShadingWorldAlpha.GetFloat() );
}

/*
==================
R_CelWorldOutlineDepthThreshold

Expressed as a fraction of view distance, so a crease reads the same whether it
is at the player's feet or across the room.
==================
*/
float R_CelWorldOutlineDepthThreshold( void ) {
	return idMath::ClampFloat( 0.0001f, 0.02f, r_celShadingWorldDepthThreshold.GetFloat() );
}

/*
==================
R_CelWorldOutlineNormalThreshold
==================
*/
float R_CelWorldOutlineNormalThreshold( void ) {
	return idMath::ClampFloat( 0.0f, 1.0f, r_celShadingWorldNormalThreshold.GetFloat() );
}
