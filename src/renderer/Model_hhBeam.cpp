/*
===========================================================================

Doom 3 GPL Source Code
Copyright (C) 1999-2011 id Software LLC, a ZeniMax Media company.

===========================================================================
*/

#include "tr_local.h"
#include "Model_local.h"

static void R_InitPreyBeamVert( idDrawVert &vert, float s, float t ) {
	vert.Clear();
	vert.st.Set( s, t );
	vert.color[0] = vert.color[1] = vert.color[2] = vert.color[3] = 255;
}

void hhRenderModelBeam::InitFromFile( const char *fileName ) {
	name = fileName;
	declBeam = static_cast<const hhDeclBeam *>( declManager->FindType( DECL_BEAM, fileName ) );
}

void hhRenderModelBeam::LoadModel( void ) {
	idRenderModelStatic::LoadModel();
}

dynamicModel_t hhRenderModelBeam::IsDynamicModel( void ) const {
	return DM_CONTINUOUS;
}

idRenderModel *hhRenderModelBeam::InstantiateDynamicModel( const renderEntity_s *renderEntity, const viewDef_s *view, idRenderModel *cachedModel ) {
	delete cachedModel;
	if ( renderEntity == NULL || view == NULL || declBeam == NULL || renderEntity->beamNodes == NULL || declBeam->numNodes < 2 ) {
		return NULL;
	}

	idRenderModelStatic *staticModel = new idRenderModelStatic;
	staticModel->InitEmpty( "_PreyBeam_Snapshot_" );
	modelSurface_t surface = {};
	int surfaceId = 0;

	// Retail's beam template (PREY.exe 1.4): three rows of numNodes vertices,
	// row 1 on the nodes and rows 0 and 2 beside them, joined by two strips of
	// quads; t is 0, 0.5 and 1 across the rows. UpdateSurface places the rows.
	for ( int beamIndex = 0; beamIndex < declBeam->numBeams; ++beamIndex ) {
		const int nodeCount = declBeam->numNodes;
		const int segmentCount = nodeCount - 1;
		srfTriangles_t *tri = R_AllocStaticTriSurf();
		R_AllocStaticTriSurfVerts( tri, 3 * nodeCount );
		R_AllocStaticTriSurfIndexes( tri, 12 * segmentCount );
		for ( int row = 0; row < 3; ++row ) {
			for ( int node = 0; node < nodeCount; ++node ) {
				R_InitPreyBeamVert( tri->verts[row * nodeCount + node], 0.0f, 0.5f * row );
			}
		}
		for ( int segment = 0; segment < segmentCount; ++segment ) {
			glIndex_t *indexes = &tri->indexes[12 * segment];
			for ( int strip = 0; strip < 2; ++strip ) {
				const glIndex_t inner = strip * nodeCount + segment;
				const glIndex_t outer = inner + nodeCount;
				indexes[6 * strip + 0] = inner;
				indexes[6 * strip + 1] = inner + 1;
				indexes[6 * strip + 2] = outer;
				indexes[6 * strip + 3] = outer;
				indexes[6 * strip + 4] = inner + 1;
				indexes[6 * strip + 5] = outer + 1;
			}
		}
		tri->numVerts = 3 * nodeCount;
		tri->numIndexes = 12 * segmentCount;
		surface.id = surfaceId++;
		surface.shader = declBeam->shader[beamIndex];
		surface.geometry = tri;
		staticModel->AddSurface( surface );
	}

	for ( int beamIndex = 0; beamIndex < declBeam->numBeams; ++beamIndex ) {
		for ( int endpoint = 0; endpoint < 2; ++endpoint ) {
			if ( declBeam->quadShader[beamIndex][endpoint] == NULL ) {
				continue;
			}
			srfTriangles_t *tri = R_AllocStaticTriSurf();
			R_AllocStaticTriSurfVerts( tri, 4 );
			R_AllocStaticTriSurfIndexes( tri, 6 );
			R_InitPreyBeamVert( tri->verts[0], 0.0f, 0.0f );
			R_InitPreyBeamVert( tri->verts[1], 0.0f, 1.0f );
			R_InitPreyBeamVert( tri->verts[2], 1.0f, 0.0f );
			R_InitPreyBeamVert( tri->verts[3], 1.0f, 1.0f );
			const glIndex_t indexes[6] = { 0, 2, 1, 2, 3, 1 };
			memcpy( tri->indexes, indexes, sizeof( indexes ) );
			tri->numVerts = 4;
			tri->numIndexes = 6;
			surface.id = surfaceId++;
			surface.shader = declBeam->quadShader[beamIndex][endpoint];
			surface.geometry = tri;
			staticModel->AddSurface( surface );
		}
	}

	int surfaceIndex = 0;
	for ( int beamIndex = 0; beamIndex < declBeam->numBeams; ++beamIndex ) {
		UpdateSurface( renderEntity, view, beamIndex, &renderEntity->beamNodes[beamIndex],
			const_cast<modelSurface_t *>( staticModel->Surface( surfaceIndex++ ) ) );
	}
	for ( int beamIndex = 0; beamIndex < declBeam->numBeams; ++beamIndex ) {
		for ( int endpoint = 0; endpoint < 2; ++endpoint ) {
			if ( declBeam->quadShader[beamIndex][endpoint] != NULL ) {
				UpdateQuadSurface( renderEntity, view, beamIndex, endpoint, &renderEntity->beamNodes[beamIndex],
					const_cast<modelSurface_t *>( staticModel->Surface( surfaceIndex++ ) ) );
			}
		}
	}

	staticModel->bounds = Bounds( renderEntity );
	return staticModel;
}

idBounds hhRenderModelBeam::Bounds( const renderEntity_s *renderEntity ) const {
	idBounds result;
	result.Clear();
	if ( renderEntity == NULL || renderEntity->beamNodes == NULL || declBeam == NULL ) {
		return idBounds( vec3_origin ).Expand( 8.0f );
	}
	for ( int beamIndex = 0; beamIndex < declBeam->numBeams; ++beamIndex ) {
		const hhBeamNodes_t &beam = renderEntity->beamNodes[beamIndex];
		for ( int node = 0; node < declBeam->numNodes; ++node ) {
			result.AddPoint( beam.nodes[node] );
		}
		result.ExpandSelf( declBeam->thickness[beamIndex] * 0.5f );
		for ( int endpoint = 0; endpoint < 2; ++endpoint ) {
			if ( declBeam->quadShader[beamIndex][endpoint] != NULL ) {
				result.AddBounds( idBounds( endpoint == 0 ? beam.nodes[0] : beam.nodes[declBeam->numNodes - 1] ).Expand( declBeam->quadSize[beamIndex][endpoint] * 0.5f ) );
			}
		}
	}
	return result;
}

/*
Retail places the template in model space without looking at the view: the
game turns the entity so local X runs from the beam's origin to its target
and gives the nodes in that space, and the side rows sit at +-half thickness
on local Y (a flat beam) or at (+-half, -half) on Y and Z, a shallow V. The
beam materials' "deform beam" then turns Y to face the viewer (R_BeamDeform,
which takes the beam's axis from row 1). Built facing the view here instead,
the deform turned the strip edge-on and the beam vanished. s runs once over
the whole beam, a thousandth per unit of its length; "taperEnds" closes the
side rows on the end nodes.
*/
void hhRenderModelBeam::UpdateSurface( const renderEntity_s *renderEntity, const viewDef_s *view, int beamIndex, const hhBeamNodes_t *beam, modelSurface_t *surface ) {
	(void)renderEntity;
	(void)view;
	srfTriangles_t *tri = surface->geometry;
	const int nodeCount = declBeam->numNodes;
	const idVec3 *nodes = beam->nodes;
	const float half = declBeam->thickness[beamIndex] * 0.5f;
	const idVec3 side0( 0.0f, half, declBeam->bFlat[beamIndex] ? 0.0f : -half );
	const idVec3 side2( 0.0f, -half, declBeam->bFlat[beamIndex] ? 0.0f : -half );
	const float sScale = ( nodes[nodeCount - 1] - nodes[0] ).Length() * 0.001f / (float)( nodeCount - 1 );
	for ( int node = 0; node < nodeCount; ++node ) {
		const float s = (float)node * sScale;
		tri->verts[node].xyz = nodes[node] + side0;
		tri->verts[nodeCount + node].xyz = nodes[node];
		tri->verts[2 * nodeCount + node].xyz = nodes[node] + side2;
		for ( int row = 0; row < 3; ++row ) {
			tri->verts[row * nodeCount + node].st[0] = s;
		}
	}
	if ( declBeam->bTaperEndPoints[beamIndex] ) {
		tri->verts[0].xyz = nodes[0];
		tri->verts[2 * nodeCount].xyz = nodes[0];
		tri->verts[nodeCount - 1].xyz = nodes[nodeCount - 1];
		tri->verts[3 * nodeCount - 1].xyz = nodes[nodeCount - 1];
	}
	R_BoundTriSurf( tri );
}

void hhRenderModelBeam::UpdateQuadSurface( const renderEntity_s *renderEntity, const viewDef_s *view, int beamIndex, int endpoint, const hhBeamNodes_t *beam, modelSurface_t *surface ) {
	idVec3 up;
	idVec3 right;
	renderEntity->axis.ProjectVector( view->renderView.viewaxis[2], up );
	renderEntity->axis.ProjectVector( view->renderView.viewaxis[1], right );
	const float halfSize = declBeam->quadSize[beamIndex][endpoint] * 0.5f;
	up *= halfSize;
	right *= halfSize;
	const idVec3 center = endpoint == 0 ? beam->nodes[0] : beam->nodes[declBeam->numNodes - 1];
	srfTriangles_t *tri = surface->geometry;
	tri->verts[0].xyz = center - right - up;
	tri->verts[1].xyz = center - right + up;
	tri->verts[2].xyz = center + right - up;
	tri->verts[3].xyz = center + right + up;
	R_BoundTriSurf( tri );
}
