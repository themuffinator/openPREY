/*
===========================================================================

Doom 3 GPL Source Code
Copyright (C) 1999-2011 id Software LLC, a ZeniMax Media company. 

This file is part of the Doom 3 GPL Source Code (?Doom 3 Source Code?).  

Doom 3 Source Code is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Doom 3 Source Code is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Doom 3 Source Code.  If not, see <http://www.gnu.org/licenses/>.

In addition, the Doom 3 Source Code is also subject to certain additional terms. You should have received a copy of these additional terms immediately following the terms and conditions of the GNU General Public License which accompanied the Doom 3 Source Code.  If not, please request a copy in writing from id Software at the address below.

If you have questions concerning this license or the applicable additional terms, you may contact in writing id Software LLC, c/o ZeniMax Media Inc., Suite 120, Rockville, Maryland 20850 USA.

===========================================================================
*/




#include "tr_local.h"
#include "../sound/sound.h"
#include "../framework/declEntityDef.h"

static ID_INLINE idSoundEmitter *R_GetPortalShaderSoundEmitter( idSoundEmitter *referenceSound, int soundEmitterHandle ) {
	if ( referenceSound != NULL ) {
		return referenceSound;
	}

	if ( soundEmitterHandle == 0 || soundSystem == NULL ) {
		return NULL;
	}

	return soundSystem->EmitterForIndex( SOUNDWORLD_GAME, soundEmitterHandle );
}

/*


All that is done in these functions is the creation of viewLights
and viewEntitys for the lightDefs and entityDefs that are visible
in the portal areas that can be seen from the current viewpoint.

*/


// if we hit this many planes, we will just stop cropping the
// view down, which is still correct, just conservative
const int MAX_PORTAL_PLANES	= 20;

typedef struct portalStack_s {
	portal_t	*p;
	const struct portalStack_s *next;

	idScreenRect	rect;

	int			numPortalPlanes;
	idPlane		portalPlanes[MAX_PORTAL_PLANES+1];
	// positive side is outside the visible frustum
} portalStack_t;


// RenderPortalFades runs in the backend, after later subview floods and
// entity updates have advanced tr.viewCount past this view's area stamps,
// so the flooded areas are snapshotted per view at frontend time
typedef struct portalFadeView_s {
	const viewDef_t *	viewDef;
	const bool *		areaVisible;	// in frame temporary memory, numPortalAreas entries
} portalFadeView_t;

const int MAX_PORTAL_FADE_VIEWS = 64;

static portalFadeView_t	portalFadeViews[MAX_PORTAL_FADE_VIEWS];
static int				numPortalFadeViews;
static int				portalFadeViewFrameCount = -1;


//====================================================================


/*
===================
idRenderWorldLocal::ScreenRectForWinding
===================
*/
idScreenRect idRenderWorldLocal::ScreenRectFromWinding( const idWinding *w, viewEntity_t *space ) {
	idScreenRect	r;
	int				i;
	idVec3			v;
	idVec3			ndc;
	float			windowX, windowY;

	r.Clear();
	const int windingPointCount = w->GetNumPoints();
	for ( i = 0 ; i < windingPointCount ; i++ ) {
		R_LocalPointToGlobal( space->modelMatrix, (*w)[i].ToVec3(), v );
		R_GlobalToNormalizedDeviceCoordinates( v, ndc );

		windowX = 0.5f * ( 1.0f + ndc[0] ) * ( tr.viewDef->viewport.x2 - tr.viewDef->viewport.x1 );
		windowY = 0.5f * ( 1.0f + ndc[1] ) * ( tr.viewDef->viewport.y2 - tr.viewDef->viewport.y1 );

		r.AddPoint( windowX, windowY );
	}

	r.Expand();

	return r;
}

/*
===================
PortalIsFoggedOut
===================
*/
bool idRenderWorldLocal::PortalIsFoggedOut( const portal_t *p ) {
	idRenderLightLocal	*ldef;
	const idWinding	*w;
	int			i;
	idPlane		forward;

	ldef = p->doublePortal->fogLight;
	if ( !ldef ) {
		return false;
	}

	// find the current density of the fog
	const idMaterial	*lightShader = ldef->lightShader;
	int		size = sizeof( float ) *lightShader->GetNumRegisters();
	float	*regs =(float *)_alloca( size );
	idSoundEmitter *soundEmitter = R_GetPortalShaderSoundEmitter( ldef->parms.referenceSound, ldef->parms.referenceSoundHandle );

	lightShader->EvaluateRegisters( regs, ldef->parms.shaderParms, tr.viewDef, soundEmitter );

	const shaderStage_t	*stage = lightShader->GetStage(0);

	float alpha = regs[ stage->color.registers[3] ];


	// if they left the default value on, set a fog distance of 500
	float	a;

	if ( alpha <= 1.0f ) {
		a = -0.5f / DEFAULT_FOG_DISTANCE;
	} else {
		// otherwise, distance = alpha color
		a = -0.5f / alpha;
	}

	forward[0] = a * tr.viewDef->worldSpace.modelViewMatrix[2];
	forward[1] = a * tr.viewDef->worldSpace.modelViewMatrix[6];
	forward[2] = a * tr.viewDef->worldSpace.modelViewMatrix[10];
	forward[3] = a * tr.viewDef->worldSpace.modelViewMatrix[14];

	w = p->w;
	const int windingPointCount = w->GetNumPoints();
	for ( i = 0 ; i < windingPointCount ; i++ ) {
		float	d;

		d = forward.Distance( (*w)[i].ToVec3() );
		if ( d < 0.5f ) {
			return false;		// a point not clipped off
		}
	}

	return true;
}

/*
===================
idRenderWorldLocal::RenderPortalFades
===================
*/
void idRenderWorldLocal::RenderPortalFades( void ) {
	// use the visibility snapshot captured for this view at frontend time
	const bool *areaVisible = NULL;
	for ( int i = 0; i < numPortalFadeViews; i++ ) {
		if ( portalFadeViews[i].viewDef == backEnd.viewDef ) {
			areaVisible = portalFadeViews[i].areaVisible;
			break;
		}
	}
	if ( areaVisible == NULL ) {
		return;
	}

	backEnd.currentSpace = &backEnd.viewDef->worldSpace;
	glLoadMatrixf( backEnd.viewDef->worldSpace.modelViewMatrix );

	backEnd.currentScissor = backEnd.viewDef->scissor;
	glScissor( backEnd.viewDef->viewport.x1 + backEnd.currentScissor.x1,
		backEnd.viewDef->viewport.y1 + backEnd.currentScissor.y1,
		backEnd.currentScissor.x2 + 1 - backEnd.currentScissor.x1,
		backEnd.currentScissor.y2 + 1 - backEnd.currentScissor.y1 );

	GL_State( GLS_DEPTHMASK | GLS_SRCBLEND_SRC_ALPHA | GLS_DSTBLEND_ONE_MINUS_SRC_ALPHA );
	GL_Cull( CT_FRONT_SIDED );
	GL_SelectTexture( 0 );

	for ( int areaIndex = 0; areaIndex < numPortalAreas; areaIndex++ ) {
		portalArea_t *area = &portalAreas[areaIndex];
		if ( !areaVisible[areaIndex] ) {
			continue;
		}

		for ( portal_t *portal = area->portals; portal; portal = portal->next ) {
			const idWinding *w = portal->w;
			if ( w == NULL || w->GetNumPoints() < 2 || portal->image == NULL ) {
				continue;
			}

			const float d = portal->plane.Distance( backEnd.viewDef->renderView.vieworg );
			if ( d <= portal->cullNear ) {
				continue;
			}

			float alpha = 1.0f;
			if ( d < portal->cullFar && portal->cullFar > portal->cullNear ) {
				alpha = 1.0f - ( portal->cullFar - d ) / ( portal->cullFar - portal->cullNear );
			}
			alpha = idMath::ClampFloat( 0.0f, 1.0f, alpha );

			const idVec3 &origin = ( *w )[0].ToVec3();
			const idVec3 edge = ( *w )[1].ToVec3() - origin;
			if ( edge.LengthSqr() <= idMath::FLOAT_EPSILON ) {
				continue;
			}
			const idVec3 vAxis = portal->plane.Normal().Cross( edge );
			if ( vAxis.LengthSqr() <= idMath::FLOAT_EPSILON ) {
				continue;
			}

			float minU = idMath::INFINITY;
			float maxU = -idMath::INFINITY;
			float minV = idMath::INFINITY;
			float maxV = -idMath::INFINITY;

			const int windingPointCount = w->GetNumPoints();
			for ( int pointIndex = 0; pointIndex < windingPointCount; pointIndex++ ) {
				const idVec3 delta = ( *w )[pointIndex].ToVec3() - origin;
				const float u = delta * edge;
				const float v = delta * vAxis;

				minU = Min( minU, u );
				maxU = Max( maxU, u );
				minV = Min( minV, v );
				maxV = Max( maxV, v );
			}

			const float uRange = maxU - minU;
			const float vRange = maxV - minV;
			if ( uRange <= idMath::FLOAT_EPSILON || vRange <= idMath::FLOAT_EPSILON ) {
				continue;
			}

			glColor4f( 1.0f, 1.0f, 1.0f, alpha );
			portal->image->Bind();

			glBegin( GL_POLYGON );
			for ( int pointIndex = 0; pointIndex < windingPointCount; pointIndex++ ) {
				const idVec3 &point = ( *w )[pointIndex].ToVec3();
				const idVec3 delta = point - origin;
				const float u = ( ( delta * edge ) - minU ) / uRange;
				const float v = 1.0f - ( ( delta * vAxis ) - minV ) / vRange;

				glTexCoord2f( u, v );
				glVertex3fv( point.ToFloatPtr() );
			}
			glEnd();
		}
	}

	glColor4f( 1.0f, 1.0f, 1.0f, 1.0f );
	globalImages->BindNull();
}

/*
===================
FloodViewThroughArea_r
===================
*/
void idRenderWorldLocal::FloodViewThroughArea_r( const idVec3 origin, int areaNum, 
								 const struct portalStack_s *ps ) {
	portal_t*		p;
	float			d;
	portalArea_t *	area;
	const portalStack_t	*check;
	portalStack_t	newStack;
	int				i, j;
	idVec3			v1, v2;
	int				addPlanes;
	idFixedWinding	w;		// we won't overflow because MAX_PORTAL_PLANES = 20

	area = &portalAreas[ areaNum ];

	// cull models and lights to the current collection of planes
	AddAreaRefs( areaNum, ps );

	if ( areaScreenRect[areaNum].IsEmpty() ) {
		areaScreenRect[areaNum] = ps->rect;
	} else {
		areaScreenRect[areaNum].Union( ps->rect );
	}

	// go through all the portals
	for ( p = area->portals; p; p = p->next ) {
		// an enclosing door may have sealed the portal off
		if ( p->doublePortal->blockingBits & PS_BLOCK_VIEW ) {
			continue;
		}

		// make sure this portal is facing away from the view
		d = p->plane.Distance( origin );
		if ( d < -0.1f ) {
			continue;
		}

		// make sure the portal isn't in our stack trace,
		// which would cause an infinite loop
		for ( check = ps; check; check = check->next ) {
			if ( check->p == p ) {
				break;		// don't recursively enter a stack
			}
		}
		if ( check ) {
			continue;	// already in stack
		}

		// if we are very close to the portal surface, don't bother clipping
		// it, which tends to give epsilon problems that make the area vanish
		if ( d < 1.0f ) {

			// go through this portal
			newStack = *ps;
			newStack.p = p;
			newStack.next = ps;
			FloodViewThroughArea_r( origin, p->intoArea, &newStack );
			continue;
		}

		// clip the portal winding to all of the planes
		w = *p->w;
		for ( j = 0; j < ps->numPortalPlanes; j++ ) {
			if ( !w.ClipInPlace( -ps->portalPlanes[j], 0 ) ) {
				break;
			}
		}
		if ( !w.GetNumPoints() ) {
			continue;	// portal not visible
		}

		// see if it is fogged out
		if ( PortalIsFoggedOut( p ) || ( r_portalsDistanceCull.GetBool() && d > p->cullFar ) ) {
			continue;
		}

		// go through this portal
		newStack.p = p;
		newStack.next = ps;

		// find the screen pixel bounding box of the remaining portal
		// so we can scissor things outside it
		newStack.rect = ScreenRectFromWinding( &w, &tr.identitySpace );
		
		// slop might have spread it a pixel outside, so trim it back
		newStack.rect.Intersect( ps->rect );

		// generate a set of clipping planes that will further restrict
		// the visible view beyond just the scissor rect

		addPlanes = w.GetNumPoints();
		if ( addPlanes > MAX_PORTAL_PLANES ) {
			addPlanes = MAX_PORTAL_PLANES;
		}

		newStack.numPortalPlanes = 0;
		for ( i = 0; i < addPlanes; i++ ) {
			j = i+1;
			if ( j == w.GetNumPoints() ) {
				j = 0;
			}

			v1 = origin - w[i].ToVec3();
			v2 = origin - w[j].ToVec3();

			newStack.portalPlanes[newStack.numPortalPlanes].Normal().Cross( v2, v1 );

			// if it is degenerate, skip the plane
			if ( newStack.portalPlanes[newStack.numPortalPlanes].Normalize() < 0.01f ) {
				continue;
			}
			newStack.portalPlanes[newStack.numPortalPlanes].FitThroughPoint( origin );

			newStack.numPortalPlanes++;
		}

		// the last stack plane is the portal plane
		newStack.portalPlanes[newStack.numPortalPlanes] = p->plane;
		newStack.numPortalPlanes++;

		FloodViewThroughArea_r( origin, p->intoArea, &newStack );
	}
}

/*
=======================
FlowViewThroughPortals

Finds viewLights and viewEntities by flowing from an origin through the visible portals.
origin point can see into.  The planes array defines a volume (positive
sides facing in) that should contain the origin, such as a view frustum or a point light box.
Zero planes assumes an unbounded volume.
=======================
*/
void idRenderWorldLocal::FlowViewThroughPortals( const idVec3 origin, int numPlanes, const idPlane *planes ) {
	portalStack_t	ps;
	int				i;

	ps.next = NULL;
	ps.p = NULL;

	for ( i = 0 ; i < numPlanes ; i++ ) {
		ps.portalPlanes[i] = planes[i];
	}

	ps.numPortalPlanes = numPlanes;
	ps.rect = tr.viewDef->scissor;

	if ( tr.viewDef->areaNum < 0 ){

		for ( i = 0; i < numPortalAreas; i++ ) {
			areaScreenRect[i] = tr.viewDef->scissor;
		}

		// if outside the world, mark everything
		for ( i = 0 ; i < numPortalAreas ; i++ ) {
			AddAreaRefs( i, &ps );
		}
	} else {

		for ( i = 0; i < numPortalAreas; i++ ) {
			areaScreenRect[i].Clear();
		}

		// flood out through portals, setting area viewCount
		FloodViewThroughArea_r( origin, tr.viewDef->areaNum, &ps );
	}
}

//==================================================================================================

/*
===================
FindVisibleAreas_r

Coarse topological portal flood used by game-side portal-sky PVS setup. This
intentionally avoids render-time scissor, fog, and distance culling because the
caller only needs to know whether any currently reachable visible area contains
skybox surfaces.
===================
*/
void idRenderWorldLocal::FindVisibleAreas_r( const idVec3 origin, int areaNum, bool *visibleAreas ) {
	(void)origin;

	if ( areaNum < 0 || areaNum >= numPortalAreas || visibleAreas == NULL ) {
		return;
	}
	if ( visibleAreas[ areaNum ] ) {
		return;
	}

	visibleAreas[ areaNum ] = true;
	portalArea_t *area = &portalAreas[ areaNum ];
	for ( portal_t *portal = area->portals; portal != NULL; portal = portal->next ) {
		if ( portal->doublePortal != NULL && ( portal->doublePortal->blockingBits & PS_BLOCK_VIEW ) ) {
			continue;
		}
		if ( portal->intoArea < 0 || portal->intoArea >= numPortalAreas ) {
			continue;
		}
		if ( visibleAreas[ portal->intoArea ] ) {
			continue;
		}

		FindVisibleAreas_r( origin, portal->intoArea, visibleAreas );
	}
}

/*
===================
FindVisibleAreas
===================
*/
void idRenderWorldLocal::FindVisibleAreas( idVec3 origin, int areaNum, bool *visibleAreas ) {
	if ( visibleAreas == NULL ) {
		return;
	}
	if ( areaNum < 0 || areaNum >= numPortalAreas ) {
		for ( int i = 0; i < numPortalAreas; i++ ) {
			visibleAreas[ i ] = true;
		}
		return;
	}

	FindVisibleAreas_r( origin, areaNum, visibleAreas );
}


/*
===================
FloodLightThroughArea_r
===================
*/
void idRenderWorldLocal::FloodLightThroughArea_r( idRenderLightLocal *light, int areaNum, 
								 const struct portalStack_s *ps ) {
	portal_t*		p;
	float			d;
	portalArea_t *	area;
	const portalStack_t	*check, *firstPortalStack;
	portalStack_t	newStack;
	int				i, j;
	idVec3			v1, v2;
	int				addPlanes;
	idFixedWinding	w;		// we won't overflow because MAX_PORTAL_PLANES = 20

	area = &portalAreas[ areaNum ];

	// add an areaRef
	AddLightRefToArea( light, area );	

	// go through all the portals
	for ( p = area->portals; p; p = p->next ) {
		// make sure this portal is facing away from the view
		d = p->plane.Distance( light->globalLightOrigin );
		if ( d < -0.1f ) {
			continue;
		}

		// make sure the portal isn't in our stack trace,
		// which would cause an infinite loop
		for ( check = ps; check; check = check->next ) {
			firstPortalStack = check;
			if ( check->p == p ) {
				break;		// don't recursively enter a stack
			}
		}
		if ( check ) {
			continue;	// already in stack
		}

		// if we are very close to the portal surface, don't bother clipping
		// it, which tends to give epsilon problems that make the area vanish
		if ( d < 1.0f ) {
			// go through this portal
			newStack = *ps;
			newStack.p = p;
			newStack.next = ps;
			FloodLightThroughArea_r( light, p->intoArea, &newStack );
			continue;
		}

		// clip the portal winding to all of the planes
		w = *p->w;
		for ( j = 0; j < ps->numPortalPlanes; j++ ) {
			if ( !w.ClipInPlace( -ps->portalPlanes[j], 0 ) ) {
				break;
			}
		}
		if ( !w.GetNumPoints() ) {
			continue;	// portal not visible
		}
		// also always clip to the original light planes, because they aren't
		// necessarily extending to infinitiy like a view frustum
		for ( j = 0; j < firstPortalStack->numPortalPlanes; j++ ) {
			if ( !w.ClipInPlace( -firstPortalStack->portalPlanes[j], 0 ) ) {
				break;
			}
		}
		if ( !w.GetNumPoints() ) {
			continue;	// portal not visible
		}

		// go through this portal
		newStack.p = p;
		newStack.next = ps;

		// generate a set of clipping planes that will further restrict
		// the visible view beyond just the scissor rect

		addPlanes = w.GetNumPoints();
		if ( addPlanes > MAX_PORTAL_PLANES ) {
			addPlanes = MAX_PORTAL_PLANES;
		}

		newStack.numPortalPlanes = 0;
		for ( i = 0; i < addPlanes; i++ ) {
			j = i+1;
			if ( j == w.GetNumPoints() ) {
				j = 0;
			}

			v1 = light->globalLightOrigin - w[i].ToVec3();
			v2 = light->globalLightOrigin - w[j].ToVec3();

			newStack.portalPlanes[newStack.numPortalPlanes].Normal().Cross( v2, v1 );

			// if it is degenerate, skip the plane
			if ( newStack.portalPlanes[newStack.numPortalPlanes].Normalize() < 0.01f ) {
				continue;
			}
			newStack.portalPlanes[newStack.numPortalPlanes].FitThroughPoint( light->globalLightOrigin );

			newStack.numPortalPlanes++;
		}

		FloodLightThroughArea_r( light, p->intoArea, &newStack );
	}
}


/*
=======================
FlowLightThroughPortals

Adds an arearef in each area that the light center flows into.
This can only be used for shadow casting lights that have a generated
prelight, because shadows are cast from back side which may not be in visible areas.
=======================
*/
void idRenderWorldLocal::FlowLightThroughPortals( idRenderLightLocal *light ) {
	portalStack_t	ps;
	int				i;
	const idVec3 origin = light->globalLightOrigin;

	// if the light origin areaNum is not in a valid area,
	// the light won't have any area refs
	if ( light->areaNum == -1 ) {
		return;
	}

	memset( &ps, 0, sizeof( ps ) );

	ps.numPortalPlanes = 6;
	for ( i = 0 ; i < 6 ; i++ ) {
		ps.portalPlanes[i] = light->frustum[i];
	}

	FloodLightThroughArea_r( light, light->areaNum, &ps );
}

//======================================================================================================

/*
===================
idRenderWorldLocal::FloodFrustumAreas_r
===================
*/
areaNumRef_t *idRenderWorldLocal::FloodFrustumAreas_r( const idFrustum &frustum, const int areaNum, const idBounds &bounds, areaNumRef_t *areas ) {
	portal_t *p;
	portalArea_t *portalArea;
	idBounds newBounds;
	areaNumRef_t *a;

	portalArea = &portalAreas[ areaNum ];

	// go through all the portals
	for ( p = portalArea->portals; p; p = p->next ) {

		// check if we already visited the area the portal leads to
		for ( a = areas; a; a = a->next ) {
			if ( a->areaNum == p->intoArea ) {
				break;
			}
		}
		if ( a ) {
			continue;
		}

		// the frustum origin must be at the front of the portal plane
		if ( p->plane.Side( frustum.GetOrigin(), 0.1f ) == SIDE_BACK ) {
			continue;
		}

		// the frustum must cross the portal plane
		if ( frustum.PlaneSide( p->plane, 0.0f ) != PLANESIDE_CROSS ) {
			continue;
		}

		// get the bounds for the portal winding projected in the frustum
		frustum.ProjectionBounds( *p->w, newBounds );

		newBounds.IntersectSelf( bounds );

		if ( newBounds[0][0] > newBounds[1][0] || newBounds[0][1] > newBounds[1][1] || newBounds[0][2] > newBounds[1][2] ) {
			continue;
		}

		newBounds[1][0] = frustum.GetFarDistance();

		a = areaNumRefAllocator.Alloc();
		a->areaNum = p->intoArea;
		a->next = areas;
		areas = a;

		areas = FloodFrustumAreas_r( frustum, p->intoArea, newBounds, areas );
	}

	return areas;
}

/*
===================
idRenderWorldLocal::FloodFrustumAreas

  Retrieves all the portal areas the frustum floods into where the frustum starts in the given areas.
  All portals are assumed to be open.
===================
*/
areaNumRef_t *idRenderWorldLocal::FloodFrustumAreas( const idFrustum &frustum, areaNumRef_t *areas ) {
	idBounds bounds;
	areaNumRef_t *a;

	// bounds that cover the whole frustum
	bounds[0].Set( frustum.GetNearDistance(), -1.0f, -1.0f );
	bounds[1].Set( frustum.GetFarDistance(), 1.0f, 1.0f );

	for ( a = areas; a; a = a->next ) {
		areas = FloodFrustumAreas_r( frustum, a->areaNum, bounds, areas );
	}

	return areas;
}


/*
=======================================================================

R_FindViewLightsAndEntities

=======================================================================
*/

/*
================
CullEntityByPortals

Return true if the entity reference bounds do not intersect the current portal chain.
================
*/
bool idRenderWorldLocal::CullEntityByPortals( const idRenderEntityLocal *entity, const portalStack_t *ps ) {
	if ( R_ShouldDisableEntityCullingForLevelshot() ) {
		return false;
	}

	if ( !r_useEntityCulling.GetBool() ) {
		return false;
	}

	// try to cull the entire thing using the reference bounds.
	// we do not yet do callbacks or dynamic model creation,
	// because we want to do all touching of the model after
	// we have determined all the lights that may effect it,
	// which optimizes cache usage
	if ( R_CullLocalBox( entity->referenceBounds, entity->modelMatrix,
							ps->numPortalPlanes, ps->portalPlanes ) ) {
		return true;
	}

	return false;
}

/*
===================
AddAreaEntityRefs

Any models that are visible through the current portalStack will
have their scissor 
===================
*/
void idRenderWorldLocal::AddAreaEntityRefs( int areaNum, const portalStack_t *ps ) {
	areaReference_t		*ref;
	idRenderEntityLocal	*entity;
	portalArea_t		*area;
	viewEntity_t		*vEnt;
	idBounds			b;

	area = &portalAreas[ areaNum ];

	for ( ref = area->entityRefs.areaNext ; ref != &area->entityRefs ; ref = ref->areaNext ) {
		entity = ref->entity;

		// debug tool to allow viewing of only one entity at a time
		if ( r_singleEntity.GetInteger() >= 0 && r_singleEntity.GetInteger() != entity->index ) {
			continue;
		}
		if ( r_skipEntities.GetBool() &&
			 ( entity->parms.hModel == NULL || !entity->parms.hModel->IsStaticWorldModel() ) ) {
			continue;
		}

		// remove decals that are completely faded away
		R_FreeEntityDefFadedDecals( entity, tr.viewDef->renderView.time );

		if ( tr.viewDef->renderView.viewSpiritEntities ) {
			if ( entity->parms.onlyInvisibleInSpirit ) {
				continue;
			}
		} else if ( entity->parms.onlyVisibleInSpirit ) {
			continue;
		}

		const int effectiveViewID = R_EffectiveViewIDForSubview();
		if ( R_ShouldSuppressViewModelForLevelshot( effectiveViewID, entity->parms.allowSurfaceInViewID, entity->parms.weaponDepthHackInViewID ) ) {
			continue;
		}

		// check for completely suppressing the model
		if ( !r_skipSuppress.GetBool() ) {
			if ( entity->parms.suppressSurfaceInViewID
					&& entity->parms.suppressSurfaceInViewID == effectiveViewID ) {
				continue;
			}
			if ( entity->parms.allowSurfaceInViewID 
					&& entity->parms.allowSurfaceInViewID != effectiveViewID ) {
				continue;
			}
		}

		// cull reference bounds
		if ( CullEntityByPortals( entity, ps ) ) {
			// we are culled out through this portal chain, but it might
			// still be visible through others
			continue;
		}

		vEnt = R_SetEntityDefViewEntity( entity );

		// possibly expand the scissor rect
		vEnt->scissorRect.Union( ps->rect );
	}
}

/*
================
CullLightByPortals

Return true if the light frustum does not intersect the current portal chain.
The last stack plane is not used because lights are not near clipped.
================
*/
bool idRenderWorldLocal::CullLightByPortals( const idRenderLightLocal *light, const portalStack_t *ps ) {
	int				i, j;
	const srfTriangles_t	*tri;
	float			d;
	idFixedWinding	w;		// we won't overflow because MAX_PORTAL_PLANES = 20

	if ( r_useLightCulling.GetInteger() == 0 ) {
		return false;
	}

	if ( r_useLightCulling.GetInteger() >= 2 ) {
		// exact clip of light faces against all planes
		for ( i = 0; i < 6; i++ ) {
			// the light frustum planes face out from the light,
			// so the planes that have the view origin on the negative
			// side will be the "back" faces of the light, which must have
			// some fragment inside the portalStack to be visible
			if ( light->frustum[i].Distance( tr.viewDef->renderView.vieworg ) >= 0 ) {
				continue;
			}

			// get the exact winding for this side
			const idWinding *ow = light->frustumWindings[i];

			// projected lights may have one of the frustums degenerated
			if ( !ow ) {
				continue;
			}

			w = *ow;

			// now check the winding against each of the portalStack planes
			for ( j = 0; j < ps->numPortalPlanes - 1; j++ ) {
				if ( !w.ClipInPlace( -ps->portalPlanes[j] ) ) {
					break;
				}
			}

			if ( w.GetNumPoints() ) {
				// part of the winding is visible through the portalStack,
				// so the light is not culled
				return false;
			}
		}
		// none of the light surfaces were visible
		return true;

	} else {

		// simple point check against each plane
		tri = light->frustumTris;

		// check against frustum planes
		for ( i = 0; i < ps->numPortalPlanes - 1; i++ ) {
			for ( j = 0; j < tri->numVerts; j++ ) {
				d = ps->portalPlanes[i].Distance( tri->verts[j].xyz );
				if ( d < 0.0f ) {
					break;	// point is inside this plane
				}
			}
			if ( j == tri->numVerts ) {
				// all points were outside one of the planes
				tr.pc.c_box_cull_out++;
				return true;
			}
		}
	}

	return false;
}

/*
===================
AddAreaLightRefs

This is the only point where lights get added to the viewLights list
===================
*/
void idRenderWorldLocal::AddAreaLightRefs( int areaNum, const portalStack_t *ps ) {
	areaReference_t		*lref;
	portalArea_t		*area;
	idRenderLightLocal			*light;
	viewLight_t			*vLight;

	area = &portalAreas[ areaNum ];

	for ( lref = area->lightRefs.areaNext ; lref != &area->lightRefs ; lref = lref->areaNext ) {
		light = lref->light;

		// debug tool to allow viewing of only one light at a time
		if ( r_singleLight.GetInteger() >= 0 && r_singleLight.GetInteger() != light->index ) {
			continue;
		}

		if ( light->parms.detailLevel < r_lightDetailLevel.GetFloat() ) {
			continue;
		}

		// check for being closed off behind a door
		// a light that doesn't cast shadows will still light even if it is behind a door
		if ( r_useLightCulling.GetInteger() >= 3 &&
				!light->parms.noShadows && light->lightShader->LightCastsShadows()
					&& light->areaNum != -1 && !tr.viewDef->connectedAreas[ light->areaNum ] ) {
			continue;
		}

		// cull frustum
		if ( !light->parms.globalLight && CullLightByPortals( light, ps ) ) {
			// we are culled out through this portal chain, but it might
			// still be visible through others
			continue;
		}

		vLight = R_SetLightDefViewLight( light );

		// expand the scissor rect
		vLight->scissorRect.Union( ps->rect );
	}
}

/*
===================
AddAreaRefs

This may be entered multiple times with different planes
if more than one portal sees into the area
===================
*/
void idRenderWorldLocal::AddAreaRefs( int areaNum, const portalStack_t *ps ) {
	// mark the viewCount, so r_showPortals can display the
	// considered portals
	portalAreas[ areaNum ].viewCount = tr.viewCount;

	// add the models and lights, using more precise culling to the planes
	AddAreaEntityRefs( areaNum, ps );
	AddAreaLightRefs( areaNum, ps );
}

/*
===================
BuildConnectedAreas_r
===================
*/
void idRenderWorldLocal::BuildConnectedAreas_r( int areaNum ) {
	portalArea_t	*area;
	portal_t		*portal;

	if ( tr.viewDef->connectedAreas[areaNum] ) {
		return;
	}

	tr.viewDef->connectedAreas[areaNum] = true;

	// flood through all non-blocked portals
	area = &portalAreas[ areaNum ];
	for ( portal = area->portals ; portal ; portal = portal->next ) {
		if ( !(portal->doublePortal->blockingBits & PS_BLOCK_VIEW) ) {
			BuildConnectedAreas_r( portal->intoArea );
		}
	}
}

/*
===================
BuildConnectedAreas

This is only valid for a given view, not all views in a frame
===================
*/
void idRenderWorldLocal::BuildConnectedAreas( void ) {
	int		i;

	tr.viewDef->connectedAreas = (bool *)R_FrameAlloc( numPortalAreas
		* sizeof( tr.viewDef->connectedAreas[0] ) );

	// if we are outside the world, we can see all areas
	if ( tr.viewDef->areaNum == -1 ) {
		for ( i = 0 ; i < numPortalAreas ; i++ ) {
			tr.viewDef->connectedAreas[i] = true;
		}
		return;
	}

	// start with none visible, and flood fill from the current area
	memset( tr.viewDef->connectedAreas, 0, numPortalAreas * sizeof( tr.viewDef->connectedAreas[0] ) );
	BuildConnectedAreas_r( tr.viewDef->areaNum );
}

/*
=============
FindViewLightsAndEntites

All the modelrefs and lightrefs that are in visible areas
will have viewEntitys and viewLights created for them.

The scissorRects on the viewEntitys and viewLights may be empty if
they were considered, but not actually visible.
=============
*/
void idRenderWorldLocal::FindViewLightsAndEntities( void ) {
	// clear the visible lightDef and entityDef lists
	tr.viewDef->viewLights = NULL;
	tr.viewDef->viewEntitys = NULL;

	// find the area to start the portal flooding in
	if ( !r_usePortals.GetBool() ) {
		// debug tool to force no portal culling
		tr.viewDef->areaNum = -1;
	} else {
		tr.viewDef->areaNum = PointInArea( tr.viewDef->initialViewAreaOrigin );
	}

	// determine all possible connected areas for
	// light-behind-door culling
	BuildConnectedAreas();

	// bump the view count, invalidating all
	// visible areas
	tr.viewCount++;

	// flow through all the portals and add models / lights
	if ( r_singleArea.GetBool() ) {
		// if debugging, only mark this area
		// if we are outside the world, don't draw anything
		if ( tr.viewDef->areaNum >= 0 ) {
			portalStack_t	ps;
			int				i;
			static int lastPrintedAreaNum;

			if ( tr.viewDef->areaNum != lastPrintedAreaNum ) {
				lastPrintedAreaNum = tr.viewDef->areaNum;
				common->Printf( "entering portal area %i\n", tr.viewDef->areaNum );
			}

			for ( i = 0 ; i < 5 ; i++ ) {
				ps.portalPlanes[i] = tr.viewDef->frustum[i];
			}
			ps.numPortalPlanes = 5;
			ps.rect = tr.viewDef->scissor;

			AddAreaRefs( tr.viewDef->areaNum, &ps );
		}
	} else {
		// note that the center of projection for flowing through portals may
		// be a different point than initialViewAreaOrigin for subviews that
		// may have the viewOrigin in a solid/invalid area
		FlowViewThroughPortals( tr.viewDef->renderView.vieworg, 5, tr.viewDef->frustum );
	}

	if ( R_ShouldDisableEntityCullingForLevelshot() ) {
		portalStack_t ps;

		memset( &ps, 0, sizeof( ps ) );
		ps.rect = tr.viewDef->scissor;

		// A levelshot tile keeps every entity of each area the portal flow
		// reached, unclipped by the portal chain, so nothing drops out at a
		// tile seam. Areas the flow did not reach stay hidden, as in play: an
		// unreached area can hold a set the player never sees (The Awakening's
		// m09 parks a black starfield box in front of its skyline).
		for ( int i = 0; i < numPortalAreas; i++ ) {
			if ( portalAreas[i].viewCount != tr.viewCount ) {
				continue;
			}
			AddAreaEntityRefs( i, &ps );
		}
	}

	// snapshot the flooded areas for RenderPortalFades, which runs in the
	// backend after later subview floods and entity updates have advanced
	// tr.viewCount past the stamps made above
	if ( portalFadeViewFrameCount != tr.frameCount ) {
		portalFadeViewFrameCount = tr.frameCount;
		numPortalFadeViews = 0;
	}
	if ( numPortalFadeViews < MAX_PORTAL_FADE_VIEWS && numPortalAreas > 0 ) {
		bool *areaVisible = (bool *)R_FrameAlloc( numPortalAreas * sizeof( areaVisible[0] ) );
		for ( int i = 0; i < numPortalAreas; i++ ) {
			areaVisible[i] = ( portalAreas[i].viewCount == tr.viewCount );
		}
		portalFadeViews[numPortalFadeViews].viewDef = tr.viewDef;
		portalFadeViews[numPortalFadeViews].areaVisible = areaVisible;
		numPortalFadeViews++;
	}
}

/*
==============
NumPortals
==============
*/
int idRenderWorldLocal::NumPortals( void ) const {
	return numInterAreaPortals + gamePortals.Num();
}

/*
==============
FindPortal

Game code uses this to identify which portals are inside doors.
Returns 0 if no portal contacts the bounds
==============
*/
qhandle_t idRenderWorldLocal::FindPortal( const idBounds &b ) const {
	int				i, j;
	idBounds		wb;
	doublePortal_t	*portal;
	idWinding		*w;

	for ( i = 0 ; i < numInterAreaPortals ; i++ ) {
		portal = &doublePortals[i];
		w = portal->portals[0]->w;

		wb.Clear();
		const int windingPointCount = w->GetNumPoints();
		for ( j = 0 ; j < windingPointCount ; j++ ) {
			wb.AddPoint( (*w)[j].ToVec3() );
		}
		if ( wb.IntersectsBounds( b ) ) {
			return i + 1;
		}
	}

	return 0;
}

/*
=============
FloodConnectedAreas
=============
*/
void	idRenderWorldLocal::FloodConnectedAreas( portalArea_t *area, int portalAttributeIndex ) {
	if ( area->connectedAreaNum[portalAttributeIndex] == connectedAreaNum ) {
		return;
	}
	area->connectedAreaNum[portalAttributeIndex] = connectedAreaNum;

	for ( portal_t *p = area->portals ; p ; p = p->next ) {
		if ( !(p->doublePortal->blockingBits & (1<<portalAttributeIndex) ) ) {
			FloodConnectedAreas( &portalAreas[p->intoArea], portalAttributeIndex );
		}
	}
}

/*
==============
AreasAreConnected

==============
*/
bool	idRenderWorldLocal::AreasAreConnected( int areaNum1, int areaNum2, portalConnection_t connection ) {
	if ( areaNum1 == -1 || areaNum2 == -1 ) {
		return false;
	}
	if ( areaNum1 >= numPortalAreas || areaNum2 >= numPortalAreas || areaNum1 < 0 || areaNum2 < 0 ) {
		common->Error( "idRenderWorldLocal::AreAreasConnected: bad parms: %i, %i", areaNum1, areaNum2 );
	}

	int	attribute = 0;

	int	intConnection = (int)connection;

	while ( intConnection > 1 ) {
		attribute++;
		intConnection >>= 1;
	}
	if ( attribute >= NUM_PORTAL_ATTRIBUTES || ( 1 << attribute ) != (int)connection ) {
		common->Error( "idRenderWorldLocal::AreasAreConnected: bad connection number: %i\n", (int)connection );
	}

	return portalAreas[areaNum1].connectedAreaNum[attribute] == portalAreas[areaNum2].connectedAreaNum[attribute];
}


/*
==============
SetPortalState

doors explicitly close off portals when shut
==============
*/
void		idRenderWorldLocal::SetPortalState( qhandle_t portal, int blockTypes ) {
	if ( portal == 0 ) {
		return;
	}

	// A game portal only gates the game's PVS: no render-side connectivity
	// changes with it (retail sub_4d13b0 floods nothing).
	gamePortal_t *gamePortal = GamePortalForHandle( portal );
	if ( gamePortal != NULL ) {
		if ( gamePortal->blockingBits == blockTypes ) {
			return;
		}
		gamePortal->blockingBits = blockTypes;
		if ( session->writeDemo ) {
			session->writeDemo->WriteInt( DS_RENDER );
			session->writeDemo->WriteInt( DC_SET_PORTAL_STATE );
			session->writeDemo->WriteInt( portal );
			session->writeDemo->WriteInt( blockTypes );
		}
		return;
	}
	// Above the real portals is the game's range. A demo replays the world
	// without the game, so its recorded game-portal states have nothing to set.
	if ( portal > numInterAreaPortals && gamePortals.Num() == 0 ) {
		return;
	}

	if ( portal < 1 || portal > numInterAreaPortals ) {
		common->Error( "SetPortalState: bad portal number %i", portal );
	}
	int	old = doublePortals[portal-1].blockingBits;
	if ( old == blockTypes ) {
		return;
	}
	doublePortals[portal-1].blockingBits = blockTypes;

	// leave the connectedAreaGroup the same on one side,
	// then flood fill from the other side with a new number for each changed attribute
	for ( int i = 0 ; i < NUM_PORTAL_ATTRIBUTES ; i++ ) {
		if ( ( old ^ blockTypes ) & ( 1 << i ) ) {
			connectedAreaNum++;
			FloodConnectedAreas( &portalAreas[doublePortals[portal-1].portals[1]->intoArea], i );
		}
	}

	if ( session->writeDemo ) {
		session->writeDemo->WriteInt( DS_RENDER );
		session->writeDemo->WriteInt( DC_SET_PORTAL_STATE );
		session->writeDemo->WriteInt( portal );
		session->writeDemo->WriteInt( blockTypes );
	}
}

/*
==============
GetPortalState
==============
*/
int		idRenderWorldLocal::GetPortalState( qhandle_t portal ) {
	if ( portal == 0 ) {
		return 0;
	}

	const gamePortal_t *gamePortal = GamePortalForHandle( portal );
	if ( gamePortal != NULL ) {
		return gamePortal->blockingBits;
	}

	if ( portal < 1 || portal > numInterAreaPortals ) {
		common->Error( "GetPortalState: bad portal number %i", portal );
	}

	return doublePortals[portal-1].blockingBits;
}

/*
==============================================================================

Prey game portals

==============================================================================
*/

/*
==============
idRenderWorldLocal::GamePortalForHandle
==============
*/
gamePortal_t *idRenderWorldLocal::GamePortalForHandle( qhandle_t handle ) const {
	const int index = handle - numInterAreaPortals - 1;
	if ( index < 0 || index >= gamePortals.Num() ) {
		return NULL;
	}
	return gamePortals[index];
}

/*
==============
idRenderWorldLocal::FreeGamePortals
==============
*/
void idRenderWorldLocal::FreeGamePortals( void ) {
	gamePortals.DeleteContents( true );
}

/*
==============
R_GamePortalEntityDict

An entity's keys over its entityDef's, as the game will spawn it.
==============
*/
static void R_GamePortalEntityDict( const idMapEntity *mapEnt, idDict &dict ) {
	dict.Clear();
	const char *classname = mapEnt->epairs.GetString( "classname" );
	if ( classname[0] != '\0' ) {
		const idDecl *decl = declManager->FindType( DECL_ENTITYDEF, classname, false );
		if ( decl != NULL && decl->GetState() != DS_DEFAULTED ) {
			dict = static_cast<const idDeclEntityDef *>( decl )->dict;
		}
	}
	dict.Copy( mapEnt->epairs );
}

/*
==============
R_GamePortalAxis
==============
*/
static idMat3 R_GamePortalAxis( const idDict &dict ) {
	if ( dict.FindKey( "rotation" ) != NULL ) {
		return dict.GetMatrix( "rotation", "1 0 0 0 1 0 0 0 1" );
	}
	return idAngles( dict.GetFloat( "pitch" ), dict.GetFloat( "angle" ), dict.GetFloat( "roll" ) ).ToMat3();
}

/*
==============
R_GamePortalTarget

The entity a map entity links its area to, or NULL (retail sub_4d2650): a
spawned entity, not opted out with noportal, naming a cameraTarget, or a
portal monster's portal_buddy, or an info_portalflow's portalTarget.
==============
*/
static const char *R_GamePortalTarget( const idDict &dict, idMapFile *mapFile ) {
	if ( dict.GetInt( "noportal" ) != 0 || dict.GetString( "spawnclass" )[0] == '\0' ) {
		return NULL;
	}
	const char *target = dict.GetString( "cameraTarget" );
	if ( dict.GetInt( "portal" ) != 0 && dict.FindKey( "portal_buddy" ) != NULL ) {
		target = dict.GetString( "portal_buddy" );
	}
	if ( dict.FindKey( "portalTarget" ) != NULL ) {
		target = dict.GetString( "portalTarget" );
	}
	if ( target[0] == '\0' || mapFile->FindEntity( target ) == NULL ) {
		return NULL;
	}
	return target;
}

/*
==============
R_GamePortalWinding

A 64 unit square through origin across axis[1] and axis[2].
==============
*/
static void R_GamePortalWinding( const idVec3 &origin, const idMat3 &axis, idWinding &w ) {
	const idVec3 right = axis[1] * 32.0f;
	const idVec3 up = axis[2] * 32.0f;
	w.SetNumPoints( 4 );
	w[0] = idVec5( origin + right + up, idVec2( 0.0f, 0.0f ) );
	w[1] = idVec5( origin + right - up, idVec2( 0.0f, 0.0f ) );
	w[2] = idVec5( origin - right - up, idVec2( 0.0f, 0.0f ) );
	w[3] = idVec5( origin - right + up, idVec2( 0.0f, 0.0f ) );
}

/*
==============
idRenderWorldLocal::RegisterGamePortals

Called by the game as each map loads, after the world and before its PVS is
built (retail sub_4d4a90). Without these links an entity standing in a
remote camera's area is outside the player's PVS and stays dormant: in
game/feedingtowerb the hunter that the mini asteroid's sky shows (the area
of biosky) never walked and never drew.
==============
*/
void idRenderWorldLocal::RegisterGamePortals( idMapFile *mapFile ) {
	FreeGamePortals();
	if ( mapFile == NULL || numPortalAreas <= 0 ) {
		return;
	}

	idDict dict, targetDict;
	for ( int i = 0 ; i < mapFile->GetNumEntities() ; i++ ) {
		const idMapEntity *mapEnt = mapFile->GetEntity( i );
		R_GamePortalEntityDict( mapEnt, dict );
		const char *targetName = R_GamePortalTarget( dict, mapFile );
		if ( targetName == NULL ) {
			continue;
		}
		const idStr target = targetName;
		R_GamePortalEntityDict( mapFile->FindEntity( target ), targetDict );

		idVec3 src = dict.GetVector( "origin" );
		const idMat3 srcAxis = R_GamePortalAxis( dict );
		const idVec3 dst = targetDict.GetVector( "origin" );
		const idMat3 dstAxis = R_GamePortalAxis( targetDict );

		// a portal pair links both ways and starts closed until it opens
		const bool pair = target.Icmp( dict.GetString( "portal_buddy" ) ) == 0;
		if ( pair ) {
			src += srcAxis[2] * dict.GetFloat( "offset_portal" );
		}

		const int srcArea = PointInArea( src );
		const int dstArea = PointInArea( dst );
		if ( srcArea < 0 ) {
			common->Warning( "Entity '%s' has bad portal source (%s)", dict.GetString( "name" ), src.ToString() );
			continue;
		}
		if ( dstArea < 0 ) {
			common->Warning( "Entity '%s' has bad portal target '%s' (%s)", dict.GetString( "name" ), target.c_str(), dst.ToString() );
			continue;
		}

		const int directions = pair && dict.GetInt( "portal_noTeleport" ) == 0 ? 2 : 1;
		for ( int direction = 0 ; direction < directions ; direction++ ) {
			gamePortal_t *gamePortal = new gamePortal_t;
			gamePortal->src = direction == 0 ? src : dst;
			gamePortal->dst = direction == 0 ? dst : src;
			gamePortal->areas[0] = direction == 0 ? srcArea : dstArea;
			gamePortal->areas[1] = direction == 0 ? dstArea : srcArea;
			gamePortal->blockingBits = pair ? PS_BLOCK_ALL : PS_BLOCK_NONE;
			R_GamePortalWinding( gamePortal->src, direction == 0 ? srcAxis : dstAxis, gamePortal->srcWinding );
			R_GamePortalWinding( gamePortal->dst, direction == 0 ? dstAxis : srcAxis, gamePortal->dstWinding );
			gamePortal->name = direction == 0 ? dict.GetString( "name" ) : targetDict.GetString( "name" );
			gamePortals.Append( gamePortal );
		}
	}

	common->Printf( "%d game portals\n", gamePortals.Num() );
	if ( com_developer.GetBool() ) {
		for ( int i = 0 ; i < gamePortals.Num() ; i++ ) {
			common->Printf( "  GamePortal: area %d -> %d (%s)\n", gamePortals[i]->areas[0], gamePortals[i]->areas[1], gamePortals[i]->name.c_str() );
		}
	}
}

/*
==============
idRenderWorldLocal::FindGamePortal
==============
*/
qhandle_t idRenderWorldLocal::FindGamePortal( const char *name ) {
	if ( name == NULL ) {
		return 0;
	}
	for ( int i = 0 ; i < gamePortals.Num() ; i++ ) {
		if ( gamePortals[i]->name.Icmp( name ) == 0 ) {
			return numInterAreaPortals + 1 + i;
		}
	}
	return 0;
}

/*
==============
idRenderWorldLocal::IsGamePortal
==============
*/
bool idRenderWorldLocal::IsGamePortal( qhandle_t handle ) {
	return GamePortalForHandle( handle ) != NULL;
}

/*
==============
idRenderWorldLocal::GetGamePortalSrc / GetGamePortalDst
==============
*/
idVec3 idRenderWorldLocal::GetGamePortalSrc( qhandle_t handle ) {
	const gamePortal_t *gamePortal = GamePortalForHandle( handle );
	return gamePortal != NULL ? gamePortal->src : vec3_origin;
}

idVec3 idRenderWorldLocal::GetGamePortalDst( qhandle_t handle ) {
	const gamePortal_t *gamePortal = GamePortalForHandle( handle );
	return gamePortal != NULL ? gamePortal->dst : vec3_origin;
}

/*
==============
idRenderWorldLocal::DrawGamePortals

g_showGamePortals: each portal's source square, an arrow to its target while
it is open, and its areas. A negative mode draws them all, mode n only the
n-th.
==============
*/
void idRenderWorldLocal::DrawGamePortals( int mode, const idMat3 &viewAxis ) {
	for ( int i = 0 ; i < gamePortals.Num() ; i++ ) {
		if ( mode > 0 && i != mode - 1 ) {
			continue;
		}
		const gamePortal_t *gamePortal = gamePortals[i];
		const bool open = ( gamePortal->blockingBits & PS_BLOCK_VIEW ) == 0;
		const idVec4 &color = open ? colorGreen : colorRed;
		DebugWinding( color, gamePortal->srcWinding, vec3_origin, mat3_identity );
		if ( open ) {
			DebugArrow( color, gamePortal->src, gamePortal->dst, 16 );
		}
		DrawText( va( "%d -> %d %s", gamePortal->areas[0], gamePortal->areas[1], gamePortal->name.c_str() ),
			gamePortal->src + viewAxis[2] * 40.0f, 0.25f, color, viewAxis );
	}
}

/*
=====================
idRenderWorldLocal::ShowPortals

Debugging tool, won't work correctly with SMP or when mirrors are present
=====================
*/
void idRenderWorldLocal::ShowPortals() {
	int			i, j;
	portalArea_t	*area;
	portal_t	*p;
	idWinding	*w;

	// flood out through portals, setting area viewCount
	for ( i = 0 ; i < numPortalAreas ; i++ ) {
		area = &portalAreas[i];
		if ( area->viewCount != tr.viewCount ) {
			continue;
		}
		for ( p = area->portals ; p ; p = p->next ) {
			w = p->w;
			if ( !w ) {
				continue;
			}

			if ( portalAreas[ p->intoArea ].viewCount != tr.viewCount ) {
				// red = can't see
				glColor3f( 1, 0, 0 );
			} else {
				// green = see through
				glColor3f( 0, 1, 0 );
			}

			glBegin( GL_LINE_LOOP );
			const int windingPointCount = w->GetNumPoints();
			for ( j = 0 ; j < windingPointCount ; j++ ) {
				glVertex3fv( (*w)[j].ToFloatPtr() );
			}
			glEnd();
		}
	}
}
