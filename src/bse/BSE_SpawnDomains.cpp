// Copyright (C) 2007 Id Software, Inc.
//

#include "../idlib/precompiled.h"
#if defined(_MSC_VER)
#pragma hdrstop
#endif

#include "BSE_Envelope.h"
#include "BSE_Particle.h"
#include "BSE_SpawnDomains.h"
#include "BSE.h"

#include <math.h>
#include <string.h>

/*
Every sampler here follows the retail Quake 4 1.4.2 implementation, including the
shape of its random distributions: stock effects were authored against them, so a
statistically "nicer" sampler visibly changes how smoke, sparks and explosions sit.
*/

namespace {

// Surface-box faces in sampling order; a centred spawn takes its normal from here.
const idVec3 bseCubeNormals[6] = {
	idVec3(-1.0f, 0.0f, 0.0f),
	idVec3(0.0f, -1.0f, 0.0f),
	idVec3(0.0f, 0.0f, -1.0f),
	idVec3(1.0f, 0.0f, 0.0f),
	idVec3(0.0f, 1.0f, 0.0f),
	idVec3(0.0f, 0.0f, 1.0f)
};

// Model space is z-up while effects emit along +x: model z becomes effect x, x becomes y
// and y becomes z.
const idMat3 bseModelToEffect(
	0.0f, 1.0f, 0.0f,
	0.0f, 0.0f, 1.0f,
	1.0f, 0.0f, 0.0f);

ID_INLINE void SpawnNormalize(idVec3& v) {
	const float lengthSqr = v.LengthSqr();
	if (lengthSqr != 0.0f) {
		v *= 1.0f / idMath::Sqrt(lengthSqr);
	}
}

// The normal of a volume sample points away from the centre it was given, or away from
// the origin when there is none.
void SpawnGetNormal(idVec3* normal, const idVec3& result, const idVec3* centre) {
	if (!normal) {
		return;
	}
	*normal = centre ? result - *centre : result;
	SpawnNormalize(*normal);
}

// Directions are a random point in the [-1,1] cube pushed onto the unit sphere (or
// circle), so they lean toward the cube's diagonals rather than being uniform.
ID_INLINE idVec3 SpawnRandomDirection3(void) {
	idVec3 dir;
	dir.x = rvRandom::flrand(-1.0f, 1.0f);
	dir.y = rvRandom::flrand(-1.0f, 1.0f);
	dir.z = rvRandom::flrand(-1.0f, 1.0f);
	SpawnNormalize(dir);
	return dir;
}

ID_INLINE idVec2 SpawnRandomDirection2(void) {
	idVec2 dir;
	dir.x = rvRandom::flrand(-1.0f, 1.0f);
	dir.y = rvRandom::flrand(-1.0f, 1.0f);
	const float lengthSqr = dir.LengthSqr();
	if (lengthSqr != 0.0f) {
		dir *= 1.0f / idMath::Sqrt(lengthSqr);
	}
	return dir;
}

ID_INLINE idVec3& SpawnResult3(float* result) {
	return *reinterpret_cast<idVec3*>(result);
}

ID_INLINE float SpawnLinearFraction(const rvParticleParms& parms, float seed) {
	return (parms.mFlags & PPFLAG_LINEARSPACING) ? seed : rvRandom::flrand(0.0f, 1.0f);
}

// A spiral's x is either random along its length or, with linearSpacing, the caller's
// fraction; its cross-section then turns once per mRange units of x.  A zero range
// means no twist at all.
ID_INLINE float SpawnSpiralX(const rvParticleParms& parms, float seed) {
	if (parms.mFlags & PPFLAG_LINEARSPACING) {
		return parms.mMins.x + (parms.mMaxs.x - parms.mMins.x) * seed;
	}
	return rvRandom::flrand(parms.mMins.x, parms.mMaxs.x);
}

/*
The front half shared by both cylinder samplers: a radial direction, the distance
along the x axis and the radius scale there.  A cone narrows linearly from a point at
mins.x to the full radius at maxs.x.
*/
ID_INLINE float SpawnCylinderAxis(const rvParticleParms& parms, idVec2& dir, float& taper) {
	dir = SpawnRandomDirection2();
	const float length = parms.mMaxs.x - parms.mMins.x;
	const float along = rvRandom::flrand(0.0f, length);
	taper = 1.0f;
	if (length != 0.0f && (parms.mFlags & PPFLAG_CONE)) {
		taper = along / length;
	}
	return along;
}
}

TSpawnFunc rvParticleParms::spawnFunctions[SPF_COUNT] = {
	/*00*/ &SpawnStub,
	/*01*/ &SpawnNone1,
	/*02*/ &SpawnNone2,
	/*03*/ &SpawnNone3,
	/*04*/ &SpawnStub,
	/*05*/ &SpawnOne1,
	/*06*/ &SpawnOne2,
	/*07*/ &SpawnOne3,
	/*08*/ &SpawnStub,
	/*09*/ &SpawnPoint1,
	/*10*/ &SpawnPoint2,
	/*11*/ &SpawnPoint3,
	/*12*/ &SpawnStub,
	/*13*/ &SpawnLinear1,
	/*14*/ &SpawnLinear2,
	/*15*/ &SpawnLinear3,
	/*16*/ &SpawnStub,
	/*17*/ &SpawnBox1,
	/*18*/ &SpawnBox2,
	/*19*/ &SpawnBox3,
	/*20*/ &SpawnStub,
	/*21*/ &SpawnSurfaceBox1,
	/*22*/ &SpawnSurfaceBox2,
	/*23*/ &SpawnSurfaceBox3,
	/*24*/ &SpawnStub,
	/*25*/ &SpawnBox1,
	/*26*/ &SpawnSphere2,
	/*27*/ &SpawnSphere3,
	/*28*/ &SpawnStub,
	/*29*/ &SpawnSurfaceBox1,
	/*30*/ &SpawnSurfaceSphere2,
	/*31*/ &SpawnSurfaceSphere3,
	/*32*/ &SpawnStub,
	/*33*/ &SpawnBox1,
	/*34*/ &SpawnSphere2,
	/*35*/ &SpawnCylinder3,
	/*36*/ &SpawnStub,
	/*37*/ &SpawnSurfaceBox1,
	/*38*/ &SpawnSurfaceSphere2,
	/*39*/ &SpawnSurfaceCylinder3,
	/*40*/ &SpawnStub,
	/*41*/ &SpawnStub,
	/*42*/ &SpawnSpiral2,
	/*43*/ &SpawnSpiral3,
	/*44*/ &SpawnStub,
	/*45*/ &SpawnStub,
	/*46*/ &SpawnStub,
	/*47*/ &SpawnModel3,
};

bool rvParticleParms::Compare(const rvParticleParms& comp) const {
	if (mSpawnType != comp.mSpawnType || mFlags != comp.mFlags || mModel != comp.mModel) {
		return false;
	}

	const float eps = 0.001f;
	if (!mMins.Compare(comp.mMins, eps) || !mMaxs.Compare(comp.mMaxs, eps)) {
		return false;
	}

	return idMath::Fabs(mRange - comp.mRange) <= eps;
}

void rvParticleParms::HandleRelativeParms(float* death, float* init, int count) {
	if ((mFlags & PPFLAG_RELATIVE) == 0 || death == NULL || init == NULL) {
		return;
	}

	for (int i = 0; i < count; ++i) {
		death[i] += init[i];
	}
}

void rvParticleParms::GetMinsMaxs(idVec3& mins, idVec3& maxs) {
	// Only the domain's own dimensions are filled; the rest stay zero, as does all
	// of a zero domain.
	mins.Zero();
	maxs.Zero();
	if (mSpawnType < SPF_ONE_1 || mSpawnType >= SPF_COUNT) {
		return;
	}

	const int shape = mSpawnType & ~0x3;
	for (int i = 0; i < (mSpawnType & 0x3); ++i) {
		if (shape == SPF_ONE_0) {
			mins[i] = maxs[i] = 1.0f;
		}
		else if (shape == SPF_POINT_0) {
			mins[i] = maxs[i] = mMins[i];
		}
		else {
			mins[i] = mMins[i];
			maxs[i] = mMaxs[i];
		}
	}
}

// Unused slots (a dimensionless domain, a 1D spiral, a 1D/2D model) leave the
// destination untouched.
void SpawnStub(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
}

void SpawnNone1(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	result[0] = 0.0f;
}

void SpawnNone2(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	result[0] = 0.0f;
	result[1] = 0.0f;
}

void SpawnNone3(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	idVec3& out = SpawnResult3(result);
	out.Zero();
	SpawnGetNormal(normal, out, centre);
}

void SpawnOne1(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	result[0] = 1.0f;
}

void SpawnOne2(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	result[0] = 1.0f;
	result[1] = 1.0f;
}

void SpawnOne3(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	idVec3& out = SpawnResult3(result);
	out.Set(1.0f, 1.0f, 1.0f);
	SpawnGetNormal(normal, out, centre);
}

void SpawnPoint1(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	result[0] = parms.mMins.x;
}

void SpawnPoint2(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	result[0] = parms.mMins.x;
	result[1] = parms.mMins.y;
}

void SpawnPoint3(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	idVec3& out = SpawnResult3(result);
	out = parms.mMins;
	SpawnGetNormal(normal, out, centre);
}

void SpawnLinear1(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	result[0] = parms.mMins.x + (parms.mMaxs.x - parms.mMins.x) * rvRandom::flrand(0.0f, 1.0f);
}

void SpawnLinear2(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	const float t = SpawnLinearFraction(parms, result[0]);
	result[0] = parms.mMins.x + (parms.mMaxs.x - parms.mMins.x) * t;
	result[1] = parms.mMins.y + (parms.mMaxs.y - parms.mMins.y) * t;
}

void SpawnLinear3(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	idVec3& out = SpawnResult3(result);
	const float t = SpawnLinearFraction(parms, out.x);
	out = parms.mMins + (parms.mMaxs - parms.mMins) * t;
	SpawnGetNormal(normal, out, centre);
}

void SpawnBox1(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	result[0] = rvRandom::flrand(parms.mMins.x, parms.mMaxs.x);
}

void SpawnBox2(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	result[0] = rvRandom::flrand(parms.mMins.x, parms.mMaxs.x);
	result[1] = rvRandom::flrand(parms.mMins.y, parms.mMaxs.y);
}

void SpawnBox3(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	idVec3& out = SpawnResult3(result);
	out.x = rvRandom::flrand(parms.mMins.x, parms.mMaxs.x);
	out.y = rvRandom::flrand(parms.mMins.y, parms.mMaxs.y);
	out.z = rvRandom::flrand(parms.mMins.z, parms.mMaxs.z);
	SpawnGetNormal(normal, out, centre);
}

// Retail indexes mMins rather than choosing between mins and maxs, so a 1D surface box
// yields mins.x or mins.y; kept for parity with shipped content.
void SpawnSurfaceBox1(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	result[0] = parms.mMins[rvRandom::irand(0, 1)];
}

// A 2D surface box is the rectangle's outline: pick an edge, then a point along it.
void SpawnSurfaceBox2(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	switch (rvRandom::irand(0, 3)) {
	case 0:
		result[0] = parms.mMins.x;
		result[1] = rvRandom::flrand(parms.mMins.y, parms.mMaxs.y);
		break;
	case 1:
		result[0] = rvRandom::flrand(parms.mMins.x, parms.mMaxs.x);
		result[1] = parms.mMins.y;
		break;
	case 2:
		result[0] = parms.mMaxs.x;
		result[1] = rvRandom::flrand(parms.mMins.y, parms.mMaxs.y);
		break;
	default:
		result[0] = rvRandom::flrand(parms.mMins.x, parms.mMaxs.x);
		result[1] = parms.mMaxs.y;
		break;
	}
}

void SpawnSurfaceBox3(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	idVec3& out = SpawnResult3(result);
	const int face = rvRandom::irand(0, 5);
	const int faceAxis = face % 3;
	for (int i = 0; i < 3; i++) {
		if (i == faceAxis) {
			out[i] = (face < 3) ? parms.mMins[i] : parms.mMaxs[i];
		} else {
			out[i] = rvRandom::flrand(parms.mMins[i], parms.mMaxs[i]);
		}
	}

	if (normal && centre) {
		*normal = bseCubeNormals[face];
	} else {
		SpawnGetNormal(normal, out, NULL);
	}
}

// Volume spheres scale each axis of the direction by its own random radius, which packs
// samples toward the centre and the axis planes.
void SpawnSphere2(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	const idVec3 mid = (parms.mMins + parms.mMaxs) * 0.5f;
	const idVec3 radius = (parms.mMaxs - parms.mMins) * 0.5f;
	const idVec2 dir = SpawnRandomDirection2();
	result[0] = mid.x + rvRandom::flrand(0.0f, radius.x) * dir.x;
	result[1] = mid.y + rvRandom::flrand(0.0f, radius.y) * dir.y;
}

void SpawnSphere3(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	idVec3& out = SpawnResult3(result);
	const idVec3 mid = (parms.mMins + parms.mMaxs) * 0.5f;
	const idVec3 radius = (parms.mMaxs - parms.mMins) * 0.5f;
	const idVec3 dir = SpawnRandomDirection3();
	out.x = mid.x + rvRandom::flrand(0.0f, radius.x) * dir.x;
	out.y = mid.y + rvRandom::flrand(0.0f, radius.y) * dir.y;
	out.z = mid.z + rvRandom::flrand(0.0f, radius.z) * dir.z;
	SpawnGetNormal(normal, out, centre);
}

void SpawnSurfaceSphere2(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	const idVec3 mid = (parms.mMins + parms.mMaxs) * 0.5f;
	const idVec3 radius = (parms.mMaxs - parms.mMins) * 0.5f;
	const idVec2 dir = SpawnRandomDirection2();
	result[0] = mid.x + radius.x * dir.x;
	result[1] = mid.y + radius.y * dir.y;
}

void SpawnSurfaceSphere3(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	idVec3& out = SpawnResult3(result);
	const idVec3 mid = (parms.mMins + parms.mMaxs) * 0.5f;
	const idVec3 radius = (parms.mMaxs - parms.mMins) * 0.5f;
	const idVec3 dir = SpawnRandomDirection3();
	out.x = mid.x + radius.x * dir.x;
	out.y = mid.y + radius.y * dir.y;
	out.z = mid.z + radius.z * dir.z;
	SpawnGetNormal(normal, out, centre);
}

// Cylinders run along x; y/z give the elliptical cross-section.
void SpawnCylinder3(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	idVec3& out = SpawnResult3(result);
	const idVec3 mid = (parms.mMins + parms.mMaxs) * 0.5f;
	const idVec3 radius = (parms.mMaxs - parms.mMins) * 0.5f;
	idVec2 dir;
	float taper;
	out.x = parms.mMins.x + SpawnCylinderAxis(parms, dir, taper);
	out.y = mid.y + rvRandom::flrand(0.0f, radius.y * taper) * dir.x;
	out.z = mid.z + rvRandom::flrand(0.0f, radius.z * taper) * dir.y;
	SpawnGetNormal(normal, out, centre);
}

void SpawnSurfaceCylinder3(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	idVec3& out = SpawnResult3(result);
	const idVec3 mid = (parms.mMins + parms.mMaxs) * 0.5f;
	const idVec3 radius = (parms.mMaxs - parms.mMins) * 0.5f;
	idVec2 dir;
	float taper;
	out.x = parms.mMins.x + SpawnCylinderAxis(parms, dir, taper);
	const float edgeY = radius.y * dir.x;
	const float edgeZ = radius.z * dir.y;
	out.y = mid.y + edgeY * taper;
	out.z = mid.z + edgeZ * taper;

	if (!normal) {
		return;
	}
	if (!centre) {
		SpawnGetNormal(normal, out, NULL);
		return;
	}
	if (taper == 1.0f) {
		// The side of a cylinder faces straight out from its axis.
		normal->Set(0.0f, dir.x, dir.y);
		return;
	}
	// The side of a cone leans back toward its apex.
	const float length = parms.mMaxs.x - parms.mMins.x;
	normal->Set(-(edgeY * edgeY + edgeZ * edgeZ), edgeY * length, edgeZ * length);
	SpawnNormalize(*normal);
}

void SpawnSpiral2(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	result[0] = SpawnSpiralX(parms, result[0]);
	result[1] = rvRandom::flrand(parms.mMins.y, parms.mMaxs.y);
	if (parms.mRange != 0.0f) {
		result[1] *= idMath::Cos(idMath::TWO_PI * result[0] / parms.mRange);
	}
}

void SpawnSpiral3(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	idVec3& out = SpawnResult3(result);
	out.x = SpawnSpiralX(parms, out.x);
	const float radiusY = rvRandom::flrand(parms.mMins.y, parms.mMaxs.y);
	const float radiusZ = rvRandom::flrand(parms.mMins.z, parms.mMaxs.z);
	if (parms.mRange != 0.0f) {
		float s, c;
		idMath::SinCos(idMath::TWO_PI * out.x / parms.mRange, s, c);
		out.y = c * radiusY - s * radiusZ;
		out.z = c * radiusZ + s * radiusY;
	} else {
		out.y = radiusY;
		out.z = radiusZ;
	}

	if (normal) {
		normal->Set(centre ? 0.0f : out.x, out.y, out.z);
		SpawnNormalize(*normal);
	}
}

/*
Sample a random triangle of a random surface, then fit that surface's bounds onto the
authored box.  The corner weights are a random vector normalised by length rather than
barycentric coordinates, so samples bulge out from the model origin by up to sqrt(3);
the fit keeps retail's (scale * point + boxCentre - surfaceCentre) form.
*/
void SpawnModel3(float* result, const rvParticleParms& parms, idVec3* normal, const idVec3* centre) {
	idVec3& out = SpawnResult3(result);
	const idRenderModel* model = parms.mModel;
	const srfTriangles_t* tri = NULL;
	if (model && model->NumSurfaces() > 0) {
		const modelSurface_t* surface = model->Surface(rvRandom::irand(0, model->NumSurfaces() - 1));
		tri = surface ? surface->geometry : NULL;
	}
	if (!tri || !tri->verts || !tri->indexes || tri->numIndexes < 3) {
		out = (parms.mMins + parms.mMaxs) * 0.5f;
		SpawnGetNormal(normal, out, centre);
		return;
	}

	const glIndex_t* corner = tri->indexes + rvRandom::irand(0, tri->numIndexes / 3 - 1) * 3;
	const idVec3& a = tri->verts[corner[0]].xyz;
	const idVec3& b = tri->verts[corner[1]].xyz;
	const idVec3& c = tri->verts[corner[2]].xyz;
	idVec3 weights;
	weights.x = rvRandom::flrand(0.0f, 1.0f);
	weights.y = rvRandom::flrand(0.0f, 1.0f);
	weights.z = rvRandom::flrand(0.0f, 1.0f);
	SpawnNormalize(weights);
	const idVec3 point = a * weights.x + b * weights.y + c * weights.z;

	if (normal) {
		if (centre) {
			// the triangle's face plane normal, wound like R_DeriveFacePlanes
			*normal = (c - a).Cross(b - a);
		} else {
			*normal = point;
		}
		SpawnNormalize(*normal);
		*normal = bseModelToEffect * *normal;
	}

	const idVec3 sample = bseModelToEffect * point;
	const idVec3 boundsMins = bseModelToEffect * tri->bounds[0];
	const idVec3 boundsMaxs = bseModelToEffect * tri->bounds[1];
	for (int i = 0; i < 3; i++) {
		const float boxCentre = (parms.mMins[i] + parms.mMaxs[i]) * 0.5f;
		const float extent = boundsMaxs[i] - boundsMins[i];
		if (extent == 0.0f) {
			// retail divides by zero for a surface that is flat along this axis
			out[i] = boxCentre;
			continue;
		}
		out[i] = (parms.mMaxs[i] - parms.mMins[i]) / extent * sample[i] + boxCentre - (boundsMins[i] + boundsMaxs[i]) * 0.5f;
	}
}
