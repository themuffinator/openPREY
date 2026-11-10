
#ifndef __MATH_SIMD_SSE2_H__
#define __MATH_SIMD_SSE2_H__

/*
===============================================================================

	SSE2 implementation of idSIMDProcessor

	Intrinsics based, so it compiles on MSVC x64 (where the original inline
	assembly SIMD implementations could not). Only the renderer and animation
	hot paths are specialized; every other routine falls through to
	idSIMD_Generic. The specialized routines preserve the generic versions'
	floating point evaluation order wherever results feed gameplay-visible
	logic, and only relax it (exact min/max instead of the midpoint-trick
	bounds) where the result is a conservative bound.

===============================================================================
*/

#include "Simd_generic.h"

#if !defined( _XENON ) && ( defined( _M_X64 ) || defined( __x86_64__ ) || defined( _M_IX86 ) || defined( __i386__ ) )

#define ID_SIMD_SSE2_AVAILABLE 1

class idSIMD_SSE2 : public idSIMD_Generic {
public:
	virtual const char * VPCALL GetName( void ) const;

	using idSIMD_Generic::Dot;
	using idSIMD_Generic::MinMax;
	using idSIMD_Generic::DeriveTriPlanes;

	virtual void VPCALL Dot( float * RESTRICT dst, const idVec3 &constant, const idPlane * RESTRICT src, const int count );
	virtual void VPCALL Dot( float * RESTRICT dst, const idVec3 &constant, const idDrawVert * RESTRICT src, const int count );
	virtual void VPCALL Dot( float * RESTRICT dst, const idPlane &constant, const idVec3 * RESTRICT src, const int count );
	virtual void VPCALL Dot( float * RESTRICT dst, const idPlane &constant, const idDrawVert * RESTRICT src, const int count );

	virtual void VPCALL MinMax( idVec3 &min, idVec3 &max, const idDrawVert * RESTRICT src, const int count );
	virtual void VPCALL MinMax( idVec3 &min, idVec3 &max, const idDrawVert * RESTRICT src, const int *indexes, const int count );

	virtual void VPCALL DeriveTriPlanes( idPlane * RESTRICT planes, const idDrawVert * RESTRICT verts, const int numVerts, const int * RESTRICT indexes, const int numIndexes );

	virtual void VPCALL CmpGT( byte *dst, const float *src0, const float constant, const int count );
	virtual void VPCALL CmpGT( byte *dst, const byte bitNum, const float *src0, const float constant, const int count );
	virtual void VPCALL CmpGE( byte *dst, const float *src0, const float constant, const int count );
	virtual void VPCALL CmpGE( byte *dst, const byte bitNum, const float *src0, const float constant, const int count );
	virtual void VPCALL CmpLT( byte *dst, const float *src0, const float constant, const int count );
	virtual void VPCALL CmpLT( byte *dst, const byte bitNum, const float *src0, const float constant, const int count );
	virtual void VPCALL CmpLE( byte *dst, const float *src0, const float constant, const int count );
	virtual void VPCALL CmpLE( byte *dst, const byte bitNum, const float *src0, const float constant, const int count );

	virtual void VPCALL ConvertJointQuatsToJointMats( idJointMat * RESTRICT jointMats, const idJointQuat * RESTRICT jointQuats, const int numJoints );
	virtual void VPCALL TransformJoints( idJointMat * RESTRICT jointMats, const int * RESTRICT parents, const int firstJoint, const int lastJoint );
	virtual void VPCALL MultiplyJoints( idJointMat * RESTRICT result, const idJointMat * RESTRICT joints1, const idJointMat * RESTRICT joints2, const int numJoints );

	virtual void VPCALL TransformVerts( idDrawVert *verts, const int numVerts, const idJointMat *joints, const idVec4 *weights, const int *index, const int numWeights );
	virtual void VPCALL TransformVertsNew( idDrawVert * RESTRICT verts, const int numVerts, idBounds &bounds, const idJointMat * RESTRICT joints, const idVec4 * RESTRICT base, const jointWeight_t * RESTRICT weights, const int numWeights );
	virtual void VPCALL TransformVertsAndTangents( idDrawVert * RESTRICT verts, const int numVerts, idBounds &bounds, const idJointMat * RESTRICT joints, const idVec4 * RESTRICT base, const jointWeight_t * RESTRICT weights, const int numWeights );
	virtual void VPCALL TransformVertsAndTangentsFast( idDrawVert * RESTRICT verts, const int numVerts, idBounds &bounds, const idJointMat * RESTRICT joints, const idVec4 * RESTRICT base, const jointWeight_t * RESTRICT weights, const int numWeights );

	virtual int  VPCALL CreateShadowCache( idVec4 * RESTRICT vertexCache, int * RESTRICT vertRemap, const idVec3 &lightOrigin, const idDrawVert * RESTRICT verts, const int numVerts );
	virtual int  VPCALL CreateVertexProgramShadowCache( idVec4 * RESTRICT vertexCache, const idDrawVert * RESTRICT verts, const int numVerts );
};

#endif /* x86 / x64 */

#endif /* !__MATH_SIMD_SSE2_H__ */
