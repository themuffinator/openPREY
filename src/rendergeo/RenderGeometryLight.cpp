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




#include "RenderGeometry.h"
#include "../imagetools/ImageTools.h"

void R_AxisToModelMatrix( const idMat3 &axis, const idVec3 &origin, float modelMatrix[16] ) {
	modelMatrix[0] = axis[0][0];
	modelMatrix[4] = axis[1][0];
	modelMatrix[8] = axis[2][0];
	modelMatrix[12] = origin[0];

	modelMatrix[1] = axis[0][1];
	modelMatrix[5] = axis[1][1];
	modelMatrix[9] = axis[2][1];
	modelMatrix[13] = origin[1];

	modelMatrix[2] = axis[0][2];
	modelMatrix[6] = axis[1][2];
	modelMatrix[10] = axis[2][2];
	modelMatrix[14] = origin[2];

	modelMatrix[3] = 0;
	modelMatrix[7] = 0;
	modelMatrix[11] = 0;
	modelMatrix[15] = 1;
}

void R_LocalPointToGlobal( const float modelMatrix[16], const idVec3 &in, idVec3 &out ) {
#if defined(MACOS_X) && defined(__i386__)
	__m128 m0, m1, m2, m3;
	__m128 in0, in1, in2;
	float i0,i1,i2;
	i0 = in[0];
	i1 = in[1];
	i2 = in[2];
	
	m0 = _mm_loadu_ps(&modelMatrix[0]);
	m1 = _mm_loadu_ps(&modelMatrix[4]);
	m2 = _mm_loadu_ps(&modelMatrix[8]);
	m3 = _mm_loadu_ps(&modelMatrix[12]);
	
	in0 = _mm_load1_ps(&i0);
	in1 = _mm_load1_ps(&i1);
	in2 = _mm_load1_ps(&i2);
	
	m0 = _mm_mul_ps(m0, in0);
	m1 = _mm_mul_ps(m1, in1);
	m2 = _mm_mul_ps(m2, in2);

	m0 = _mm_add_ps(m0, m1);
	m0 = _mm_add_ps(m0, m2);
	m0 = _mm_add_ps(m0, m3);
	
	_mm_store_ss(&out[0], m0);
	m1 = (__m128) _mm_shuffle_epi32((__m128i)m0, 0x55);
	_mm_store_ss(&out[1], m1);
	m2 = _mm_movehl_ps(m2, m0);
	_mm_store_ss(&out[2], m2);
#else	
	out[0] = in[0] * modelMatrix[0] + in[1] * modelMatrix[4]
		+ in[2] * modelMatrix[8] + modelMatrix[12];
	out[1] = in[0] * modelMatrix[1] + in[1] * modelMatrix[5]
		+ in[2] * modelMatrix[9] + modelMatrix[13];
	out[2] = in[0] * modelMatrix[2] + in[1] * modelMatrix[6]
		+ in[2] * modelMatrix[10] + modelMatrix[14];
#endif
}

void R_PointTimesMatrix( const float modelMatrix[16], const idVec4 &in, idVec4 &out ) {
	out[0] = in[0] * modelMatrix[0] + in[1] * modelMatrix[4]
		+ in[2] * modelMatrix[8] + modelMatrix[12];
	out[1] = in[0] * modelMatrix[1] + in[1] * modelMatrix[5]
		+ in[2] * modelMatrix[9] + modelMatrix[13];
	out[2] = in[0] * modelMatrix[2] + in[1] * modelMatrix[6]
		+ in[2] * modelMatrix[10] + modelMatrix[14];
	out[3] = in[0] * modelMatrix[3] + in[1] * modelMatrix[7]
		+ in[2] * modelMatrix[11] + modelMatrix[15];
}

void R_GlobalPointToLocal( const float modelMatrix[16], const idVec3 &in, idVec3 &out ) {
	idVec3	temp;

	VectorSubtract( in, &modelMatrix[12], temp );

	out[0] = DotProduct( temp, &modelMatrix[0] );
	out[1] = DotProduct( temp, &modelMatrix[4] );
	out[2] = DotProduct( temp, &modelMatrix[8] );
}

void R_LocalVectorToGlobal( const float modelMatrix[16], const idVec3 &in, idVec3 &out ) {
	out[0] = in[0] * modelMatrix[0] + in[1] * modelMatrix[4]
		+ in[2] * modelMatrix[8];
	out[1] = in[0] * modelMatrix[1] + in[1] * modelMatrix[5]
		+ in[2] * modelMatrix[9];
	out[2] = in[0] * modelMatrix[2] + in[1] * modelMatrix[6]
		+ in[2] * modelMatrix[10];
}

void R_GlobalVectorToLocal( const float modelMatrix[16], const idVec3 &in, idVec3 &out ) {
	out[0] = DotProduct( in, &modelMatrix[0] );
	out[1] = DotProduct( in, &modelMatrix[4] );
	out[2] = DotProduct( in, &modelMatrix[8] );
}

void R_GlobalPlaneToLocal( const float modelMatrix[16], const idPlane &in, idPlane &out ) {
	out[0] = DotProduct( in, &modelMatrix[0] );
	out[1] = DotProduct( in, &modelMatrix[4] );
	out[2] = DotProduct( in, &modelMatrix[8] );
	out[3] = in[3] + modelMatrix[12] * in[0] + modelMatrix[13] * in[1] + modelMatrix[14] * in[2];
}

void R_LocalPlaneToGlobal( const float modelMatrix[16], const idPlane &in, idPlane &out ) {
	float	offset;

	R_LocalVectorToGlobal( modelMatrix, in.Normal(), out.Normal() );

	offset = modelMatrix[12] * out[0] + modelMatrix[13] * out[1] + modelMatrix[14] * out[2];
	out[3] = in[3] - offset;
}

/*
=====================
R_SetLightProject

All values are reletive to the origin
Assumes that right and up are not normalized
This is also called by dmap during map processing.
=====================
*/
void R_SetLightProject( idPlane lightProject[4], const idVec3 origin, const idVec3 target,
					   const idVec3 rightVector, const idVec3 upVector, const idVec3 start, const idVec3 stop ) {
	float		dist;
	float		scale;
	float		rLen, uLen;
	idVec3		normal;
	float		ofs;
	idVec3		right, up;
	idVec3		startGlobal;
	idVec4		targetGlobal;

	right = rightVector;
	rLen = right.Normalize();
	up = upVector;
	uLen = up.Normalize();
	normal = up.Cross( right );
//normal = right.Cross( up );
	normal.Normalize();

	dist = target * normal; //  - ( origin * normal );
	if ( dist < 0 ) {
		dist = -dist;
		normal = -normal;
	}

	scale = ( 0.5f * dist ) / rLen;
	right *= scale;
	scale = -( 0.5f * dist ) / uLen;
	up *= scale;

	lightProject[2] = normal;
	lightProject[2][3] = -( origin * lightProject[2].Normal() );

	lightProject[0] = right;
	lightProject[0][3] = -( origin * lightProject[0].Normal() );

	lightProject[1] = up;
	lightProject[1][3] = -( origin * lightProject[1].Normal() );

	// now offset to center
	targetGlobal.ToVec3() = target + origin;
	targetGlobal[3] = 1;
	ofs = 0.5f - ( targetGlobal * lightProject[0].ToVec4() ) / ( targetGlobal * lightProject[2].ToVec4() );
	lightProject[0].ToVec4() += ofs * lightProject[2].ToVec4();
	ofs = 0.5f - ( targetGlobal * lightProject[1].ToVec4() ) / ( targetGlobal * lightProject[2].ToVec4() );
	lightProject[1].ToVec4() += ofs * lightProject[2].ToVec4();

	// set the falloff vector
	normal = stop - start;
	dist = normal.Normalize();
	if ( dist <= 0 ) {
		dist = 1;
	}
	lightProject[3] = normal * ( 1.0f / dist );
	startGlobal = start + origin;
	lightProject[3][3] = -( startGlobal * lightProject[3].Normal() );
}

/*
===================
R_SetLightFrustum

Creates plane equations from the light projection, positive sides
face out of the light
===================
*/
void R_SetLightFrustum( const idPlane lightProject[4], idPlane frustum[6] ) {
	int		i;

	// we want the planes of s=0, s=q, t=0, and t=q
	frustum[0] = lightProject[0];
	frustum[1] = lightProject[1];
	frustum[2] = lightProject[2] - lightProject[0];
	frustum[3] = lightProject[2] - lightProject[1];

	// we want the planes of s=0 and s=1 for front and rear clipping planes
	frustum[4] = lightProject[3];

	frustum[5] = lightProject[3];
	frustum[5][3] -= 1.0f;
	frustum[5] = -frustum[5];

	for ( i = 0 ; i < 6 ; i++ ) {
		float	l;

		frustum[i] = -frustum[i];
		l = frustum[i].Normalize();
		frustum[i][3] /= l;
	}
}

/*
====================
R_FreeLightDefFrustum
====================
*/
void R_FreeLightDefFrustum( idRenderLightLocal *ldef ) {
	int i;

	// free the frustum tris
	if ( ldef->frustumTris ) {
		R_FreeStaticTriSurf( ldef->frustumTris );
		ldef->frustumTris = NULL;
	}
	// free frustum windings
	for ( i = 0; i < 6; i++ ) {
		if ( ldef->frustumWindings[i] ) {
			delete ldef->frustumWindings[i];
			ldef->frustumWindings[i] = NULL;
		}
	}
}

/*
=================
R_DeriveLightData

Fills everything in based on light->parms
=================
*/
void R_DeriveLightData( idRenderLightLocal *light ) {
	int i;

	// decide which light shader we are going to use
	if ( light->parms.shader ) {
		light->lightShader = light->parms.shader;
	}
	if ( !light->lightShader ) {
		if ( light->parms.pointLight ) {
			light->lightShader = declManager->FindMaterial( "lights/defaultPointLight" );
		} else {
			light->lightShader = declManager->FindMaterial( "lights/defaultProjectedLight" );
		}
	}

	// get the falloff image
	light->falloffImage = light->lightShader->LightFalloffImage();
	if ( !light->falloffImage ) {
		// use the falloff from the default shader of the correct type
		const idMaterial	*defaultShader;

		if ( light->parms.pointLight ) {
			defaultShader = declManager->FindMaterial( "lights/defaultPointLight" );
			light->falloffImage = defaultShader->LightFalloffImage();
		} else {
			// projected lights by default don't diminish with distance
			defaultShader = declManager->FindMaterial( "lights/defaultProjectedLight" );
			light->falloffImage = defaultShader->LightFalloffImage();
		}
	}

	// set the projection
	if ( !light->parms.pointLight ) {
		// projected light

		R_SetLightProject( light->lightProject, vec3_origin /* light->parms.origin */, light->parms.target, 
			light->parms.right, light->parms.up, light->parms.start, light->parms.end);
	} else {
		// point light
		memset( light->lightProject, 0, sizeof( light->lightProject ) );
		light->lightProject[0][0] = 0.5f / light->parms.lightRadius[0];
		light->lightProject[1][1] = 0.5f / light->parms.lightRadius[1];
		light->lightProject[3][2] = 0.5f / light->parms.lightRadius[2];
		light->lightProject[0][3] = 0.5f;
		light->lightProject[1][3] = 0.5f;
		light->lightProject[2][3] = 1.0f;
		light->lightProject[3][3] = 0.5f;
	}

	// set the frustum planes
	R_SetLightFrustum( light->lightProject, light->frustum );

	// rotate the light planes and projections by the axis
	R_AxisToModelMatrix( light->parms.axis, light->parms.origin, light->modelMatrix );

	for ( i = 0 ; i < 6 ; i++ ) {
		idPlane		temp;
		temp = light->frustum[i];
		R_LocalPlaneToGlobal( light->modelMatrix, temp, light->frustum[i] );
	}
	for ( i = 0 ; i < 4 ; i++ ) {
		idPlane		temp;
		temp = light->lightProject[i];
		R_LocalPlaneToGlobal( light->modelMatrix, temp, light->lightProject[i] );
	}

	// adjust global light origin for off center projections and parallel projections
	// we are just faking parallel by making it a very far off center for now
	if ( light->parms.parallel ) {
		idVec3	dir;

		dir = light->parms.lightCenter;
		if ( !dir.Normalize() ) {
			// make point straight up if not specified
			dir[2] = 1;
		}
		light->globalLightOrigin = light->parms.origin + dir * 100000;
	} else {
		light->globalLightOrigin = light->parms.origin + light->parms.axis * light->parms.lightCenter;
	}

	R_FreeLightDefFrustum( light );

	light->frustumTris = R_PolytopeSurface( 6, light->frustum, light->frustumWindings );

	// a projected light will have one shadowFrustum, a point light will have
	// six unless the light center is outside the box
	R_MakeShadowFrustums( light );
}

/*
===============
R_RenderLightFrustum

Called by the editor and dmap to operate on light volumes
===============
*/
void R_RenderLightFrustum( const renderLight_t &renderLight, idPlane lightFrustum[6] ) {
	idRenderLightLocal	fakeLight;

	memset( &fakeLight, 0, sizeof( fakeLight ) );
	fakeLight.parms = renderLight;

	R_DeriveLightData( &fakeLight );

	R_FreeLightDefFrustum( &fakeLight );

	for ( int i = 0 ; i < 6 ; i++ ) {
		lightFrustum[i] = fakeLight.frustum[i];
	}
}
