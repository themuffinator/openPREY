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




#include "Model_local.h"
#include "tr_local.h"

namespace {

void R_FreeOverlayMaterial( overlayMaterial_t *material ) {
	if ( material == NULL ) {
		return;
	}

	for ( int i = 0; i < material->surfaces.Num(); i++ ) {
		overlaySurface_t *surface = material->surfaces[i];
		if ( surface == NULL ) {
			continue;
		}

		if ( surface->verts != NULL ) {
			Mem_Free( surface->verts );
		}
		if ( surface->indexes != NULL ) {
			Mem_Free( surface->indexes );
		}
		Mem_Free( surface );
	}

	material->surfaces.Clear();
	delete material;
}

void R_ClearOverlayMaterials( idList<overlayMaterial_t *> &materials ) {
	for ( int k = 0; k < materials.Num(); k++ ) {
		R_FreeOverlayMaterial( materials[k] );
	}

	materials.Clear();
}

bool R_RejectOverlayDemo( idDemoFile *f, const char *reason ) {
	common->Warning( "Malformed render demo overlay: %s; playback stopped safely", reason );
	if ( f != NULL ) {
		f->Close();
	}
	return false;
}

bool R_MaterializePrimBatchOverlayTriangles( const srfTriangles_t &sourceTri, srfTriangles_t &tempTri, idDrawVert *tempVerts, glIndex_t *tempIndexes ) {
	memset( &tempTri, 0, sizeof( tempTri ) );
	tempTri.bounds = sourceTri.bounds;
	tempTri.numVerts = sourceTri.numVerts;
	tempTri.verts = tempVerts;
	tempTri.numIndexes = sourceTri.numIndexes;
	tempTri.indexes = tempIndexes;

	if ( sourceTri.numVerts <= 0 || sourceTri.numIndexes <= 0 || tempVerts == NULL || tempIndexes == NULL ) {
		return false;
	}

	if ( sourceTri.verts != NULL && sourceTri.indexes != NULL ) {
		memcpy( tempVerts, sourceTri.verts, sourceTri.numVerts * sizeof( tempVerts[0] ) );
		memcpy( tempIndexes, sourceTri.indexes, sourceTri.numIndexes * sizeof( tempIndexes[0] ) );
		return true;
	}

#if defined( _MD5R_SUPPORT ) || defined( Q4SDK_MD5R )
	if ( !R_TriHasPrimBatchMesh( &sourceTri ) ) {
		return false;
	}

	return R_MD5R_CopyPrimBatchTriangles(
		tempVerts,
		tempIndexes,
		reinterpret_cast<const rvMesh *>( sourceTri.primBatchMesh ),
		reinterpret_cast<const rvSilTraceVertT *>( sourceTri.silTraceVerts ) );
#else
	return false;
#endif
}

void R_CreateClassicOverlayTriangles( const srfTriangles_t *stri, const idPlane localTextureAxis[2], overlayVertex_t *overlayVerts, glIndex_t *overlayIndexes, int &numVerts, int &numIndexes ) {
	numVerts = 0;
	numIndexes = 0;

	if ( stri == NULL || stri->verts == NULL || stri->indexes == NULL || stri->numVerts <= 0 || stri->numIndexes <= 0 ) {
		return;
	}

	byte *cullBits = (byte *)_alloca16( stri->numVerts * sizeof( cullBits[0] ) );
	idVec2 *texCoords = (idVec2 *)_alloca16( stri->numVerts * sizeof( texCoords[0] ) );

	SIMDProcessor->OverlayPointCull( cullBits, texCoords, localTextureAxis, stri->verts, stri->numVerts );

	glIndex_t *vertexRemap = (glIndex_t *)_alloca16( sizeof( vertexRemap[0] ) * stri->numVerts );
	SIMDProcessor->Memset( vertexRemap, -1, sizeof( vertexRemap[0] ) * stri->numVerts );

	// Find triangles that need the overlay.
	for ( int index = 0; index < stri->numIndexes; index += 3 ) {
		int v1 = stri->indexes[index + 0];
		int	v2 = stri->indexes[index + 1];
		int v3 = stri->indexes[index + 2];

		// Skip triangles completely off one side.
		if ( cullBits[v1] & cullBits[v2] & cullBits[v3] ) {
			continue;
		}

		// Keep this triangle.
		for ( int vnum = 0; vnum < 3; vnum++ ) {
			int ind = stri->indexes[index + vnum];
			if ( vertexRemap[ind] == (glIndex_t)-1 ) {
				vertexRemap[ind] = numVerts;

				overlayVerts[numVerts].vertexNum = ind;
				overlayVerts[numVerts].st[0] = texCoords[ind][0];
				overlayVerts[numVerts].st[1] = texCoords[ind][1];

				numVerts++;
			}
			overlayIndexes[numIndexes++] = vertexRemap[ind];
		}
	}
}

bool R_CopyOverlayVertexPosition( idDrawVert &dst, const srfTriangles_t *baseTri, int vertexNum ) {
	if ( baseTri == NULL || vertexNum < 0 || vertexNum >= baseTri->numVerts ) {
		return false;
	}

#if defined( _MD5R_SUPPORT ) || defined( Q4SDK_MD5R )
	if ( baseTri->silTraceVerts != NULL ) {
		const rvSilTraceVertT *silTraceVerts = reinterpret_cast<const rvSilTraceVertT *>( baseTri->silTraceVerts );
		dst.xyz = silTraceVerts[vertexNum].xyzw.ToVec3();
		return true;
	}
#endif

	if ( baseTri->verts == NULL ) {
		return false;
	}

	dst.xyz = baseTri->verts[vertexNum].xyz;
	return true;
}

}


/*
====================
idRenderModelOverlay::idRenderModelOverlay
====================
*/
idRenderModelOverlay::idRenderModelOverlay() {
}

/*
====================
idRenderModelOverlay::~idRenderModelOverlay
====================
*/
idRenderModelOverlay::~idRenderModelOverlay() {
	R_ClearOverlayMaterials( materials );
}

/*
====================
idRenderModelOverlay::Alloc
====================
*/
idRenderModelOverlay *idRenderModelOverlay::Alloc( void ) {
	return new idRenderModelOverlay;
}

/*
====================
idRenderModelOverlay::Free
====================
*/
void idRenderModelOverlay::Free( idRenderModelOverlay *overlay ) {
	delete overlay;
}

/*
====================
idRenderModelOverlay::FreeSurface
====================
*/
void idRenderModelOverlay::FreeSurface( overlaySurface_t *surface ) {
	if ( surface->verts ) {
		Mem_Free( surface->verts );
	}
	if ( surface->indexes ) {
		Mem_Free( surface->indexes );
	}
	Mem_Free( surface );
}

/*
=====================
idRenderModelOverlay::CreateOverlay

This projects on both front and back sides to avoid seams
The material should be clamped, because entire triangles are added, some of which
may extend well past the 0.0 to 1.0 texture range
=====================
*/
void idRenderModelOverlay::CreateOverlay( const idRenderModel *model, const idPlane localTextureAxis[2], const idMaterial *mtr ) {
	int i, maxVerts, maxIndexes, surfNum;

	// count up the maximum possible vertices and indexes per surface
	maxVerts = 0;
	maxIndexes = 0;
	const int surfaceCount = model->NumSurfaces();
	for ( surfNum = 0; surfNum < surfaceCount; surfNum++ ) {
		const modelSurface_t *surf = model->Surface( surfNum );
		if ( surf == NULL || surf->geometry == NULL ) {
			continue;
		}

		if ( surf->geometry->numVerts > maxVerts ) {
			maxVerts = surf->geometry->numVerts;
		}
		if ( surf->geometry->numIndexes > maxIndexes ) {
			maxIndexes = surf->geometry->numIndexes;
		}
	}

	if ( maxVerts <= 0 || maxIndexes <= 0 ) {
		return;
	}

	// make temporary buffers for the building process
	overlayVertex_t	*overlayVerts = (overlayVertex_t *)_alloca( maxVerts * sizeof( *overlayVerts ) );
	glIndex_t *overlayIndexes = (glIndex_t *)_alloca16( maxIndexes * sizeof( *overlayIndexes ) );

	// pull out the triangles we need from the base surfaces
	const int baseSurfaceCount = model->NumBaseSurfaces();
	for ( surfNum = 0; surfNum < baseSurfaceCount; surfNum++ ) {
		const modelSurface_t *surf = model->Surface( surfNum );
		float d;

		if ( !surf->geometry || !surf->shader ) {
			continue;
		}

		// some surfaces can explicitly disallow overlays
		if ( !surf->shader->AllowOverlays() ) {
			continue;
		}

		const srfTriangles_t *stri = surf->geometry;

		// try to cull the whole surface along the first texture axis
		d = stri->bounds.PlaneDistance( localTextureAxis[0] );
		if ( d < 0.0f || d > 1.0f ) {
			continue;
		}

		// try to cull the whole surface along the second texture axis
		d = stri->bounds.PlaneDistance( localTextureAxis[1] );
		if ( d < 0.0f || d > 1.0f ) {
			continue;
		}

		int numVerts = 0;
		int numIndexes = 0;
		const srfTriangles_t *overlayTri = stri;
		srfTriangles_t materializedTri;

		if ( R_TriHasPrimBatchMesh( stri ) && ( stri->verts == NULL || stri->indexes == NULL ) ) {
			idDrawVert *tempVerts = (idDrawVert *)_alloca16( stri->numVerts * sizeof( tempVerts[0] ) );
			glIndex_t *tempIndexes = (glIndex_t *)_alloca16( stri->numIndexes * sizeof( tempIndexes[0] ) );
			if ( !R_MaterializePrimBatchOverlayTriangles( *stri, materializedTri, tempVerts, tempIndexes ) ) {
				continue;
			}

			overlayTri = &materializedTri;
		}

		R_CreateClassicOverlayTriangles( overlayTri, localTextureAxis, overlayVerts, overlayIndexes, numVerts, numIndexes );

		if ( !numIndexes ) {
			continue;
		}

		overlaySurface_t *s = (overlaySurface_t *) Mem_Alloc( sizeof( overlaySurface_t ) );
		s->surfaceNum = surfNum;
		s->surfaceId = surf->id;
		s->verts = (overlayVertex_t *)Mem_Alloc( numVerts * sizeof( s->verts[0] ) );
		memcpy( s->verts, overlayVerts, numVerts * sizeof( s->verts[0] ) );
		s->numVerts = numVerts;
		s->indexes = (glIndex_t *)Mem_Alloc( numIndexes * sizeof( s->indexes[0] ) );
		memcpy( s->indexes, overlayIndexes, numIndexes * sizeof( s->indexes[0] ) );
		s->numIndexes = numIndexes;

		for ( i = 0; i < materials.Num(); i++ ) {
			if ( materials[i]->material == mtr ) {
				break;
			}
		}
		if ( i < materials.Num() ) {
            materials[i]->surfaces.Append( s );
		} else {
			overlayMaterial_t *mat = new overlayMaterial_t;
			mat->material = mtr;
			mat->surfaces.Append( s );
			materials.Append( mat );
		}
	}

	// remove the oldest overlay surfaces if there are too many per material
	for ( i = 0; i < materials.Num(); i++ ) {
		while( materials[i]->surfaces.Num() > MAX_OVERLAY_SURFACES ) {
			FreeSurface( materials[i]->surfaces[0] );
			materials[i]->surfaces.RemoveIndex( 0 );
		}
	}
}

/*
====================
idRenderModelOverlay::AddOverlaySurfacesToModel
====================
*/
void idRenderModelOverlay::AddOverlaySurfacesToModel( idRenderModel *baseModel ) {
	int i, j, k, numVerts, numIndexes, surfaceNum;
	const modelSurface_t *baseSurf;
	idRenderModelStatic *staticModel;
	overlaySurface_t *surf;
	srfTriangles_t *newTri;
	modelSurface_t *newSurf;

	if ( baseModel == NULL || baseModel->IsDefaultModel() ) {
		return;
	}

	// md5 models won't have any surfaces when r_showSkel is set
	if ( !baseModel->NumSurfaces() ) {
		return;
	}

	if ( baseModel->IsDynamicModel() != DM_STATIC ) {
		common->Error( "idRenderModelOverlay::AddOverlaySurfacesToModel: baseModel is not a static model" );
	}

	assert( dynamic_cast<idRenderModelStatic *>(baseModel) != NULL );
	staticModel = static_cast<idRenderModelStatic *>(baseModel);

	staticModel->overlaysAdded = 0;

	if ( !materials.Num() ) {
		staticModel->DeleteSurfacesWithNegativeId();
		return;
	}

	for ( k = 0; k < materials.Num(); k++ ) {

		numVerts = numIndexes = 0;
		for ( i = 0; i < materials[k]->surfaces.Num(); i++ ) {
			numVerts += materials[k]->surfaces[i]->numVerts;
			numIndexes += materials[k]->surfaces[i]->numIndexes;
		}

		if ( staticModel->FindSurfaceWithId( -1 - k, surfaceNum ) ) {
			newSurf = &staticModel->surfaces[surfaceNum];
		} else {
			newSurf = &staticModel->surfaces.Alloc();
			newSurf->geometry = NULL;
			newSurf->shader = materials[k]->material;
			newSurf->id = -1 - k;
			newSurf->mOriginalSurfaceName = NULL;
		}

		if ( newSurf->geometry == NULL || newSurf->geometry->numVerts < numVerts || newSurf->geometry->numIndexes < numIndexes ) {
			R_FreeStaticTriSurf( newSurf->geometry );
			newSurf->geometry = R_AllocStaticTriSurf();
			R_AllocStaticTriSurfVerts( newSurf->geometry, numVerts );
			R_AllocStaticTriSurfIndexes( newSurf->geometry, numIndexes );
			SIMDProcessor->Memset( newSurf->geometry->verts, 0, numVerts * sizeof( newTri->verts[0] ) );
		} else {
			R_FreeStaticTriSurfVertexCaches( newSurf->geometry );
		}

		newTri = newSurf->geometry;
		R_GpuSkinning_ClearSurfaceContract( newTri, GPU_SKINNING_FALLBACK_NONE );
		numVerts = numIndexes = 0;

		for ( i = 0; i < materials[k]->surfaces.Num(); i++ ) {
			surf = materials[k]->surfaces[i];

			// get the model surface for this overlay surface
			if ( surf->surfaceNum < staticModel->NumSurfaces() ) {
				baseSurf = staticModel->Surface( surf->surfaceNum );
			} else {
				baseSurf = NULL;
			}

			// if the surface ids no longer match
			if ( !baseSurf || baseSurf->id != surf->surfaceId ) {
				// find the surface with the correct id
				if ( staticModel->FindSurfaceWithId( surf->surfaceId, surf->surfaceNum ) ) {
					baseSurf = staticModel->Surface( surf->surfaceNum );
				} else {
					// the surface with this id no longer exists
					FreeSurface( surf );
					materials[k]->surfaces.RemoveIndex( i );
					i--;
					continue;
				}
			}

			// copy indexes;
			for ( j = 0; j < surf->numIndexes; j++ ) {
				newTri->indexes[numIndexes + j] = numVerts + surf->indexes[j];
			}
			numIndexes += surf->numIndexes;

			// copy vertices
			for ( j = 0; j < surf->numVerts; j++ ) {
				overlayVertex_t *overlayVert = &surf->verts[j];

				newTri->verts[numVerts].st[0] = overlayVert->st[0];
				newTri->verts[numVerts].st[1] = overlayVert->st[1];

				if ( !R_CopyOverlayVertexPosition( newTri->verts[numVerts], baseSurf->geometry, overlayVert->vertexNum ) ) {
					// This can happen when playing a demofile and a model has been changed since it was recorded, so just issue a warning and go on.
					common->Warning( "idRenderModelOverlay::AddOverlaySurfacesToModel: overlay vertex out of range.  Model has probably changed since generating the overlay." );
					FreeSurface( surf );
					materials[k]->surfaces.RemoveIndex( i );
					staticModel->DeleteSurfaceWithId( newSurf->id );
					return;
				}
				numVerts++;
			}
		}

		newTri->numVerts = numVerts;
		newTri->numIndexes = numIndexes;
		R_BoundTriSurf( newTri );

		staticModel->overlaysAdded++;	// so we don't create an overlay on an overlay surface
	}
}

/*
====================
idRenderModelOverlay::RemoveOverlaySurfacesFromModel
====================
*/
void idRenderModelOverlay::RemoveOverlaySurfacesFromModel( idRenderModel *baseModel ) {
	idRenderModelStatic *staticModel;

	assert( dynamic_cast<idRenderModelStatic *>(baseModel) != NULL );
	staticModel = static_cast<idRenderModelStatic *>(baseModel);

	staticModel->DeleteSurfacesWithNegativeId();
	staticModel->overlaysAdded = 0;
}

/*
====================
idRenderModelOverlay::ReadFromDemoFile
====================
*/
bool idRenderModelOverlay::ReadFromDemoFile( idDemoFile *f ) {
	int numMaterials = 0;

	R_ClearOverlayMaterials( materials );

	if ( f == NULL || f->ReadInt( numMaterials ) != sizeof( numMaterials ) ) {
		return R_RejectOverlayDemo( f, "truncated material count" );
	}
	if ( numMaterials < 0 || numMaterials > 1024 ) {
		return R_RejectOverlayDemo( f, va( "material count %d is out of range", numMaterials ) );
	}

	for ( int materialIndex = 0; materialIndex < numMaterials; materialIndex++ ) {
		overlayMaterial_t *material = new overlayMaterial_t;
		const char *materialName = f->ReadHashString();
		int numSurfaces;

		if ( !f->IsOpen() ) {
			R_FreeOverlayMaterial( material );
			return false;
		}
		material->material = ( materialName[0] != '\0' ) ? declManager->FindMaterial( materialName ) : NULL;

		if ( f->ReadInt( numSurfaces ) != sizeof( numSurfaces ) ) {
			R_FreeOverlayMaterial( material );
			return R_RejectOverlayDemo( f, "truncated surface count" );
		}
		if ( numSurfaces < 0 || numSurfaces > MAX_OVERLAY_SURFACES ) {
			R_FreeOverlayMaterial( material );
			return R_RejectOverlayDemo( f, va( "surface count %d is out of range", numSurfaces ) );
		}

		material->surfaces.SetNum( numSurfaces );
		for ( int surfaceIndex = 0; surfaceIndex < numSurfaces; surfaceIndex++ ) {
			material->surfaces[surfaceIndex] = NULL;
		}
		for ( int surfaceIndex = 0; surfaceIndex < numSurfaces; surfaceIndex++ ) {
			overlaySurface_t *surface = (overlaySurface_t *)Mem_Alloc( sizeof( *surface ) );
			int numVerts;
			int numIndexes;

			memset( surface, 0, sizeof( *surface ) );

			if ( f->ReadInt( surface->surfaceNum ) != sizeof( surface->surfaceNum ) ||
				 f->ReadInt( surface->surfaceId ) != sizeof( surface->surfaceId ) ||
				 f->ReadInt( numVerts ) != sizeof( numVerts ) ||
				 f->ReadInt( numIndexes ) != sizeof( numIndexes ) ) {
				Mem_Free( surface );
				R_FreeOverlayMaterial( material );
				return R_RejectOverlayDemo( f, "truncated surface header" );
			}

			if ( numVerts < 0 || numVerts > 1 << 20 || numIndexes < 0 || numIndexes > 1 << 21 || ( numIndexes % 3 ) != 0 ) {
				Mem_Free( surface );
				R_FreeOverlayMaterial( material );
				return R_RejectOverlayDemo(
					f,
					va( "surface payload has invalid counts (vertices %d, indices %d)", numVerts, numIndexes )
				);
			}

			surface->numVerts = numVerts;
			surface->numIndexes = numIndexes;

			if ( surface->numVerts > 0 ) {
				surface->verts = (overlayVertex_t *)Mem_Alloc( surface->numVerts * sizeof( surface->verts[0] ) );
				for ( int vertIndex = 0; vertIndex < surface->numVerts; vertIndex++ ) {
					if ( f->ReadInt( surface->verts[vertIndex].vertexNum ) != sizeof( surface->verts[vertIndex].vertexNum ) ||
						 f->ReadFloat( surface->verts[vertIndex].st[0] ) != sizeof( surface->verts[vertIndex].st[0] ) ||
						 f->ReadFloat( surface->verts[vertIndex].st[1] ) != sizeof( surface->verts[vertIndex].st[1] ) ) {
						FreeSurface( surface );
						R_FreeOverlayMaterial( material );
						return R_RejectOverlayDemo( f, "truncated vertex payload" );
					}
				}
			}

			if ( surface->numIndexes > 0 ) {
				surface->indexes = (glIndex_t *)Mem_Alloc( surface->numIndexes * sizeof( surface->indexes[0] ) );
				for ( int index = 0; index < surface->numIndexes; index++ ) {
					int storedIndex;

					if ( f->ReadInt( storedIndex ) != sizeof( storedIndex ) ) {
						FreeSurface( surface );
						R_FreeOverlayMaterial( material );
						return R_RejectOverlayDemo( f, "truncated vertex index" );
					}
					if ( storedIndex < 0 || storedIndex >= surface->numVerts ) {
						FreeSurface( surface );
						R_FreeOverlayMaterial( material );
						return R_RejectOverlayDemo( f, va( "vertex index %d is out of range", storedIndex ) );
					}
					surface->indexes[index] = storedIndex;
				}
			}

			material->surfaces[surfaceIndex] = surface;
		}

		materials.Append( material );
	}
	return true;
}

/*
====================
idRenderModelOverlay::WriteToDemoFile
====================
*/
void idRenderModelOverlay::WriteToDemoFile( idDemoFile *f ) const {
	f->WriteInt( materials.Num() );

	for ( int materialIndex = 0; materialIndex < materials.Num(); materialIndex++ ) {
		const overlayMaterial_t *material = materials[materialIndex];
		const char *materialName = ( material != NULL && material->material != NULL ) ? material->material->GetName() : "";
		const int numSurfaces = ( material != NULL ) ? material->surfaces.Num() : 0;

		f->WriteHashString( materialName );
		f->WriteInt( numSurfaces );

		for ( int surfaceIndex = 0; surfaceIndex < numSurfaces; surfaceIndex++ ) {
			const overlaySurface_t *surface = material->surfaces[surfaceIndex];

			f->WriteInt( surface->surfaceNum );
			f->WriteInt( surface->surfaceId );
			f->WriteInt( surface->numVerts );
			f->WriteInt( surface->numIndexes );

			for ( int vertIndex = 0; vertIndex < surface->numVerts; vertIndex++ ) {
				f->WriteInt( surface->verts[vertIndex].vertexNum );
				f->WriteFloat( surface->verts[vertIndex].st[0] );
				f->WriteFloat( surface->verts[vertIndex].st[1] );
			}

			for ( int index = 0; index < surface->numIndexes; index++ ) {
				f->WriteInt( surface->indexes[index] );
			}
		}
	}
}
