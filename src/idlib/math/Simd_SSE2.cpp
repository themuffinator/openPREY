
#include "Simd_SSE2.h"

#ifdef ID_SIMD_SSE2_AVAILABLE

#include <emmintrin.h>

//===============================================================
//
//	SSE2 implementation of idSIMDProcessor
//
//===============================================================

/*
============
idSIMD_SSE2::GetName
============
*/
const char * VPCALL idSIMD_SSE2::GetName( void ) const {
	return "SSE2";
}

/*
============
SSE2_StoreVec3

	stores the low three lanes without touching the 4th float of memory,
	which idDrawVert packs with color bytes / adjacent fields
============
*/
ID_INLINE static void SSE2_StoreVec3( float *dst, __m128 v ) {
	float lanes[4];
	_mm_storeu_ps( lanes, v );
	dst[0] = lanes[0];
	dst[1] = lanes[1];
	dst[2] = lanes[2];
}

/*
============
SSE2_JointMatMulVec4

	returns ( row0 . v, row1 . v, row2 . v, junk ) for a row-major 3x4
	joint matrix; the sum order matches idJointMat::operator*( idVec4 )
============
*/
ID_INLINE static __m128 SSE2_JointMatMulVec4( const float *mat, __m128 v ) {
	__m128 r0 = _mm_mul_ps( _mm_loadu_ps( mat + 0 ), v );
	__m128 r1 = _mm_mul_ps( _mm_loadu_ps( mat + 4 ), v );
	__m128 r2 = _mm_mul_ps( _mm_loadu_ps( mat + 8 ), v );
	__m128 r3 = _mm_setzero_ps();
	_MM_TRANSPOSE4_PS( r0, r1, r2, r3 );
	return _mm_add_ps( _mm_add_ps( _mm_add_ps( r0, r1 ), r2 ), r3 );
}

/*
============
SSE2_TransformColumns

	result = c0 * v.x + c1 * v.y + c2 * v.z + c3 * v.w, with the same
	left-to-right sum order as idJointMat::operator*( idVec4 )
============
*/
ID_INLINE static __m128 SSE2_TransformColumns( __m128 c0, __m128 c1, __m128 c2, __m128 c3, __m128 v ) {
	__m128 r = _mm_mul_ps( c0, _mm_shuffle_ps( v, v, _MM_SHUFFLE( 0, 0, 0, 0 ) ) );
	r = _mm_add_ps( r, _mm_mul_ps( c1, _mm_shuffle_ps( v, v, _MM_SHUFFLE( 1, 1, 1, 1 ) ) ) );
	r = _mm_add_ps( r, _mm_mul_ps( c2, _mm_shuffle_ps( v, v, _MM_SHUFFLE( 2, 2, 2, 2 ) ) ) );
	r = _mm_add_ps( r, _mm_mul_ps( c3, _mm_shuffle_ps( v, v, _MM_SHUFFLE( 3, 3, 3, 3 ) ) ) );
	return r;
}

/*
============
idSIMD_SSE2::Dot

	dst[i] = constant * src[i].Normal() + src[i][3];
============
*/
void VPCALL idSIMD_SSE2::Dot( float * RESTRICT dst, const idVec3 &constant, const idPlane * RESTRICT src, const int count ) {
	const __m128 cx = _mm_set1_ps( constant.x );
	const __m128 cy = _mm_set1_ps( constant.y );
	const __m128 cz = _mm_set1_ps( constant.z );

	int i = 0;
	for ( ; i + 4 <= count; i += 4 ) {
		__m128 p0 = _mm_loadu_ps( src[i+0].ToFloatPtr() );
		__m128 p1 = _mm_loadu_ps( src[i+1].ToFloatPtr() );
		__m128 p2 = _mm_loadu_ps( src[i+2].ToFloatPtr() );
		__m128 p3 = _mm_loadu_ps( src[i+3].ToFloatPtr() );
		_MM_TRANSPOSE4_PS( p0, p1, p2, p3 );
		__m128 r = _mm_add_ps( _mm_add_ps( _mm_add_ps(
			_mm_mul_ps( cx, p0 ), _mm_mul_ps( cy, p1 ) ), _mm_mul_ps( cz, p2 ) ), p3 );
		_mm_storeu_ps( dst + i, r );
	}
	for ( ; i < count; i++ ) {
		dst[i] = constant * src[i].Normal() + src[i][3];
	}
}

/*
============
idSIMD_SSE2::Dot

	dst[i] = constant * src[i].xyz;
============
*/
void VPCALL idSIMD_SSE2::Dot( float * RESTRICT dst, const idVec3 &constant, const idDrawVert * RESTRICT src, const int count ) {
	const __m128 cx = _mm_set1_ps( constant.x );
	const __m128 cy = _mm_set1_ps( constant.y );
	const __m128 cz = _mm_set1_ps( constant.z );

	int i = 0;
	for ( ; i + 4 <= count; i += 4 ) {
		// the 16 byte load stays inside the 64 byte idDrawVert
		__m128 v0 = _mm_loadu_ps( src[i+0].xyz.ToFloatPtr() );
		__m128 v1 = _mm_loadu_ps( src[i+1].xyz.ToFloatPtr() );
		__m128 v2 = _mm_loadu_ps( src[i+2].xyz.ToFloatPtr() );
		__m128 v3 = _mm_loadu_ps( src[i+3].xyz.ToFloatPtr() );
		_MM_TRANSPOSE4_PS( v0, v1, v2, v3 );
		__m128 r = _mm_add_ps( _mm_add_ps(
			_mm_mul_ps( cx, v0 ), _mm_mul_ps( cy, v1 ) ), _mm_mul_ps( cz, v2 ) );
		_mm_storeu_ps( dst + i, r );
	}
	for ( ; i < count; i++ ) {
		dst[i] = constant * src[i].xyz;
	}
}

/*
============
idSIMD_SSE2::Dot

	dst[i] = constant.Normal() * src[i] + constant[3];
============
*/
void VPCALL idSIMD_SSE2::Dot( float * RESTRICT dst, const idPlane &constant, const idVec3 * RESTRICT src, const int count ) {
	const __m128 cx = _mm_set1_ps( constant[0] );
	const __m128 cy = _mm_set1_ps( constant[1] );
	const __m128 cz = _mm_set1_ps( constant[2] );
	const __m128 cd = _mm_set1_ps( constant[3] );

	int i = 0;
	// idVec3 is 12 bytes, so a 16 byte load on an element is only safe when
	// another element follows it; always leave the final element to the tail
	for ( ; i + 5 <= count; i += 4 ) {
		__m128 v0 = _mm_loadu_ps( src[i+0].ToFloatPtr() );
		__m128 v1 = _mm_loadu_ps( src[i+1].ToFloatPtr() );
		__m128 v2 = _mm_loadu_ps( src[i+2].ToFloatPtr() );
		__m128 v3 = _mm_loadu_ps( src[i+3].ToFloatPtr() );
		_MM_TRANSPOSE4_PS( v0, v1, v2, v3 );
		__m128 r = _mm_add_ps( _mm_add_ps( _mm_add_ps(
			_mm_mul_ps( cx, v0 ), _mm_mul_ps( cy, v1 ) ), _mm_mul_ps( cz, v2 ) ), cd );
		_mm_storeu_ps( dst + i, r );
	}
	for ( ; i < count; i++ ) {
		dst[i] = constant.Normal() * src[i] + constant[3];
	}
}

/*
============
idSIMD_SSE2::Dot

	dst[i] = constant.Normal() * src[i].xyz + constant[3];
============
*/
void VPCALL idSIMD_SSE2::Dot( float * RESTRICT dst, const idPlane &constant, const idDrawVert * RESTRICT src, const int count ) {
	const __m128 cx = _mm_set1_ps( constant[0] );
	const __m128 cy = _mm_set1_ps( constant[1] );
	const __m128 cz = _mm_set1_ps( constant[2] );
	const __m128 cd = _mm_set1_ps( constant[3] );

	int i = 0;
	for ( ; i + 4 <= count; i += 4 ) {
		__m128 v0 = _mm_loadu_ps( src[i+0].xyz.ToFloatPtr() );
		__m128 v1 = _mm_loadu_ps( src[i+1].xyz.ToFloatPtr() );
		__m128 v2 = _mm_loadu_ps( src[i+2].xyz.ToFloatPtr() );
		__m128 v3 = _mm_loadu_ps( src[i+3].xyz.ToFloatPtr() );
		_MM_TRANSPOSE4_PS( v0, v1, v2, v3 );
		__m128 r = _mm_add_ps( _mm_add_ps( _mm_add_ps(
			_mm_mul_ps( cx, v0 ), _mm_mul_ps( cy, v1 ) ), _mm_mul_ps( cz, v2 ) ), cd );
		_mm_storeu_ps( dst + i, r );
	}
	for ( ; i < count; i++ ) {
		dst[i] = constant.Normal() * src[i].xyz + constant[3];
	}
}

/*
============
idSIMD_SSE2::MinMax
============
*/
void VPCALL idSIMD_SSE2::MinMax( idVec3 &min, idVec3 &max, const idDrawVert * RESTRICT src, const int count ) {
	__m128 minAcc = _mm_set1_ps( idMath::INFINITY );
	__m128 maxAcc = _mm_set1_ps( -idMath::INFINITY );

	// new value as the first operand: MINPS/MAXPS return the second operand
	// when either is NaN, which matches the NaN-ignoring "if ( v < min )"
	// semantics of the generic version
	for ( int i = 0; i < count; i++ ) {
		__m128 v = _mm_loadu_ps( src[i].xyz.ToFloatPtr() );
		minAcc = _mm_min_ps( v, minAcc );
		maxAcc = _mm_max_ps( v, maxAcc );
	}

	SSE2_StoreVec3( min.ToFloatPtr(), minAcc );
	SSE2_StoreVec3( max.ToFloatPtr(), maxAcc );
}

/*
============
idSIMD_SSE2::MinMax
============
*/
void VPCALL idSIMD_SSE2::MinMax( idVec3 &min, idVec3 &max, const idDrawVert * RESTRICT src, const int *indexes, const int count ) {
	__m128 minAcc = _mm_set1_ps( idMath::INFINITY );
	__m128 maxAcc = _mm_set1_ps( -idMath::INFINITY );

	for ( int i = 0; i < count; i++ ) {
		__m128 v = _mm_loadu_ps( src[indexes[i]].xyz.ToFloatPtr() );
		minAcc = _mm_min_ps( v, minAcc );
		maxAcc = _mm_max_ps( v, maxAcc );
	}

	SSE2_StoreVec3( min.ToFloatPtr(), minAcc );
	SSE2_StoreVec3( max.ToFloatPtr(), maxAcc );
}

/*
============
SSE2_RSqrt

	vectorizes idMath::RSqrt's 0x5f3759df bit trick + one Newton-Raphson step
	with the exact generic operation order, so each lane is bit-identical to
	the scalar version - including the huge-finite (not inf/NaN) result for
	x == 0 that degenerate triangles in skinned meshes rely on
============
*/
ID_INLINE static __m128 SSE2_RSqrt( __m128 x ) {
	__m128 y = _mm_mul_ps( x, _mm_set1_ps( 0.5f ) );
	__m128i i = _mm_sub_epi32( _mm_set1_epi32( 0x5f3759df ), _mm_srli_epi32( _mm_castps_si128( x ), 1 ) );
	__m128 r = _mm_castsi128_ps( i );
	r = _mm_mul_ps( r, _mm_sub_ps( _mm_set1_ps( 1.5f ), _mm_mul_ps( _mm_mul_ps( r, r ), y ) ) );
	return r;
}

/*
============
idSIMD_SSE2::DeriveTriPlanes

	four triangles per iteration: gathered vertex loads + transpose, 4-wide
	cross product, bit-exact RSqrt normalization, and a transpose back to
	four idPlane rows; sum orders match the generic version exactly
============
*/
void VPCALL idSIMD_SSE2::DeriveTriPlanes( idPlane * RESTRICT planes, const idDrawVert * RESTRICT verts, const int numVerts, const int * RESTRICT indexes, const int numIndexes ) {
	const __m128 signMask = _mm_castsi128_ps( _mm_set1_epi32( 0x80000000 ) );
	const int numTris = numIndexes / 3;

	int t = 0;
	for ( ; t + 4 <= numTris; t += 4 ) {
		const int * RESTRICT ix = indexes + t * 3;

		// the 16 byte loads stay inside the 64 byte idDrawVert
		__m128 a0 = _mm_loadu_ps( verts[ix[ 0]].xyz.ToFloatPtr() );
		__m128 a1 = _mm_loadu_ps( verts[ix[ 3]].xyz.ToFloatPtr() );
		__m128 a2 = _mm_loadu_ps( verts[ix[ 6]].xyz.ToFloatPtr() );
		__m128 a3 = _mm_loadu_ps( verts[ix[ 9]].xyz.ToFloatPtr() );
		_MM_TRANSPOSE4_PS( a0, a1, a2, a3 );	// a0 = ax, a1 = ay, a2 = az

		__m128 b0 = _mm_loadu_ps( verts[ix[ 1]].xyz.ToFloatPtr() );
		__m128 b1 = _mm_loadu_ps( verts[ix[ 4]].xyz.ToFloatPtr() );
		__m128 b2 = _mm_loadu_ps( verts[ix[ 7]].xyz.ToFloatPtr() );
		__m128 b3 = _mm_loadu_ps( verts[ix[10]].xyz.ToFloatPtr() );
		_MM_TRANSPOSE4_PS( b0, b1, b2, b3 );

		__m128 c0 = _mm_loadu_ps( verts[ix[ 2]].xyz.ToFloatPtr() );
		__m128 c1 = _mm_loadu_ps( verts[ix[ 5]].xyz.ToFloatPtr() );
		__m128 c2 = _mm_loadu_ps( verts[ix[ 8]].xyz.ToFloatPtr() );
		__m128 c3 = _mm_loadu_ps( verts[ix[11]].xyz.ToFloatPtr() );
		_MM_TRANSPOSE4_PS( c0, c1, c2, c3 );

		__m128 d0x = _mm_sub_ps( b0, a0 );
		__m128 d0y = _mm_sub_ps( b1, a1 );
		__m128 d0z = _mm_sub_ps( b2, a2 );
		__m128 d1x = _mm_sub_ps( c0, a0 );
		__m128 d1y = _mm_sub_ps( c1, a1 );
		__m128 d1z = _mm_sub_ps( c2, a2 );

		__m128 nx = _mm_sub_ps( _mm_mul_ps( d1y, d0z ), _mm_mul_ps( d1z, d0y ) );
		__m128 ny = _mm_sub_ps( _mm_mul_ps( d1z, d0x ), _mm_mul_ps( d1x, d0z ) );
		__m128 nz = _mm_sub_ps( _mm_mul_ps( d1x, d0y ), _mm_mul_ps( d1y, d0x ) );

		// generic sum order: n.x * n.x + n.y * n.y + n.z * n.z
		__m128 f = SSE2_RSqrt( _mm_add_ps( _mm_add_ps(
			_mm_mul_ps( nx, nx ), _mm_mul_ps( ny, ny ) ), _mm_mul_ps( nz, nz ) ) );

		nx = _mm_mul_ps( nx, f );
		ny = _mm_mul_ps( ny, f );
		nz = _mm_mul_ps( nz, f );

		// FitThroughPoint: d = -( normal * point ), idVec3 dot sum order
		__m128 dist = _mm_xor_ps( signMask, _mm_add_ps( _mm_add_ps(
			_mm_mul_ps( nx, a0 ), _mm_mul_ps( ny, a1 ) ), _mm_mul_ps( nz, a2 ) ) );

		_MM_TRANSPOSE4_PS( nx, ny, nz, dist );
		_mm_storeu_ps( planes[t + 0].ToFloatPtr(), nx );
		_mm_storeu_ps( planes[t + 1].ToFloatPtr(), ny );
		_mm_storeu_ps( planes[t + 2].ToFloatPtr(), nz );
		_mm_storeu_ps( planes[t + 3].ToFloatPtr(), dist );
	}

	// hand any remainder to the generic loop, including a trailing partial
	// triangle when numIndexes is not a multiple of 3 (the generic version
	// processes it, so the tail condition must use numIndexes, not numTris)
	if ( t * 3 < numIndexes ) {
		idSIMD_Generic::DeriveTriPlanes( planes + t, verts, numVerts, indexes + t * 3, numIndexes - t * 3 );
	}
}

/*
============
SSE2 float-vs-constant compares

	exact replacements: the ordered SSE compares return false for NaN exactly
	like the scalar relational operators do. Four 4-wide float masks are
	packed to sixteen 0x00/0xFF bytes, then masked to 0/1 stores or OR'd into
	the destination bit. These feed shadow facing / cull-bit classification,
	which runs per (caster x light) every frame in combat scenes.
============
*/
ID_INLINE static __m128i SSE2_PackCmpMasks( __m128 m0, __m128 m1, __m128 m2, __m128 m3 ) {
	return _mm_packs_epi16(
		_mm_packs_epi32( _mm_castps_si128( m0 ), _mm_castps_si128( m1 ) ),
		_mm_packs_epi32( _mm_castps_si128( m2 ), _mm_castps_si128( m3 ) ) );
}

#define SSE2_CMP_CONSTANT_PLAIN( CMP_PS, SCALAR_OP ) \
	const __m128 c = _mm_set1_ps( constant ); \
	const __m128i one = _mm_set1_epi8( 1 ); \
	int i = 0; \
	for ( ; i + 16 <= count; i += 16 ) { \
		const __m128i packed = SSE2_PackCmpMasks( \
			CMP_PS( _mm_loadu_ps( src0 + i + 0 ), c ), \
			CMP_PS( _mm_loadu_ps( src0 + i + 4 ), c ), \
			CMP_PS( _mm_loadu_ps( src0 + i + 8 ), c ), \
			CMP_PS( _mm_loadu_ps( src0 + i + 12 ), c ) ); \
		_mm_storeu_si128( (__m128i *)( dst + i ), _mm_and_si128( packed, one ) ); \
	} \
	for ( ; i < count; i++ ) { \
		dst[i] = src0[i] SCALAR_OP constant; \
	}

#define SSE2_CMP_CONSTANT_BITNUM( CMP_PS, SCALAR_OP ) \
	const __m128 c = _mm_set1_ps( constant ); \
	const __m128i bit = _mm_set1_epi8( (char)( 1 << bitNum ) ); \
	int i = 0; \
	for ( ; i + 16 <= count; i += 16 ) { \
		const __m128i packed = SSE2_PackCmpMasks( \
			CMP_PS( _mm_loadu_ps( src0 + i + 0 ), c ), \
			CMP_PS( _mm_loadu_ps( src0 + i + 4 ), c ), \
			CMP_PS( _mm_loadu_ps( src0 + i + 8 ), c ), \
			CMP_PS( _mm_loadu_ps( src0 + i + 12 ), c ) ); \
		const __m128i prev = _mm_loadu_si128( (const __m128i *)( dst + i ) ); \
		_mm_storeu_si128( (__m128i *)( dst + i ), _mm_or_si128( prev, _mm_and_si128( packed, bit ) ) ); \
	} \
	for ( ; i < count; i++ ) { \
		dst[i] |= ( src0[i] SCALAR_OP constant ) << bitNum; \
	}

void VPCALL idSIMD_SSE2::CmpGT( byte *dst, const float *src0, const float constant, const int count ) {
	SSE2_CMP_CONSTANT_PLAIN( _mm_cmpgt_ps, > )
}

void VPCALL idSIMD_SSE2::CmpGT( byte *dst, const byte bitNum, const float *src0, const float constant, const int count ) {
	SSE2_CMP_CONSTANT_BITNUM( _mm_cmpgt_ps, > )
}

void VPCALL idSIMD_SSE2::CmpGE( byte *dst, const float *src0, const float constant, const int count ) {
	SSE2_CMP_CONSTANT_PLAIN( _mm_cmpge_ps, >= )
}

void VPCALL idSIMD_SSE2::CmpGE( byte *dst, const byte bitNum, const float *src0, const float constant, const int count ) {
	SSE2_CMP_CONSTANT_BITNUM( _mm_cmpge_ps, >= )
}

void VPCALL idSIMD_SSE2::CmpLT( byte *dst, const float *src0, const float constant, const int count ) {
	SSE2_CMP_CONSTANT_PLAIN( _mm_cmplt_ps, < )
}

void VPCALL idSIMD_SSE2::CmpLT( byte *dst, const byte bitNum, const float *src0, const float constant, const int count ) {
	SSE2_CMP_CONSTANT_BITNUM( _mm_cmplt_ps, < )
}

void VPCALL idSIMD_SSE2::CmpLE( byte *dst, const float *src0, const float constant, const int count ) {
	SSE2_CMP_CONSTANT_PLAIN( _mm_cmple_ps, <= )
}

void VPCALL idSIMD_SSE2::CmpLE( byte *dst, const byte bitNum, const float *src0, const float constant, const int count ) {
	SSE2_CMP_CONSTANT_BITNUM( _mm_cmple_ps, <= )
}

#undef SSE2_CMP_CONSTANT_PLAIN
#undef SSE2_CMP_CONSTANT_BITNUM

/*
============
idSIMD_SSE2::ConvertJointQuatsToJointMats

	scalar, but with the idMat3 round trip of the generic version removed;
	the expressions mirror idQuat::ToMat3 followed by idJointMat::SetRotation
	(which transposes) and SetTranslation, so the results are bit identical
============
*/
void VPCALL idSIMD_SSE2::ConvertJointQuatsToJointMats( idJointMat * RESTRICT jointMats, const idJointQuat * RESTRICT jointQuats, const int numJoints ) {
	for ( int i = 0; i < numJoints; i++ ) {
		const idJointQuat &jq = jointQuats[i];
		float *m = jointMats[i].ToFloatPtr();

		const float x = jq.q.x;
		const float y = jq.q.y;
		const float z = jq.q.z;
		const float w = jq.q.w;

		const float x2 = x + x;
		const float y2 = y + y;
		const float z2 = z + z;

		const float xx = x * x2;
		const float xy = x * y2;
		const float xz = x * z2;

		const float yy = y * y2;
		const float yz = y * z2;
		const float zz = z * z2;

		const float wx = w * x2;
		const float wy = w * y2;
		const float wz = w * z2;

		m[0 * 4 + 0] = 1.0f - ( yy + zz );
		m[0 * 4 + 1] = xy + wz;
		m[0 * 4 + 2] = xz - wy;
		m[0 * 4 + 3] = jq.t[0];

		m[1 * 4 + 0] = xy - wz;
		m[1 * 4 + 1] = 1.0f - ( xx + zz );
		m[1 * 4 + 2] = yz + wx;
		m[1 * 4 + 3] = jq.t[1];

		m[2 * 4 + 0] = xz + wy;
		m[2 * 4 + 1] = yz - wx;
		m[2 * 4 + 2] = 1.0f - ( xx + yy );
		m[2 * 4 + 3] = jq.t[2];
	}
}

/*
============
SSE2_ComposeJointMat

	dst = a * t for row-major 3x4 affine joint matrices, with the same sum
	order as idJointMat::operator*= / idJointMat::Multiply
============
*/
ID_INLINE static void SSE2_ComposeJointMat( float *dst, const float *a, __m128 t0, __m128 t1, __m128 t2 ) {
	for ( int row = 0; row < 3; row++ ) {
		__m128 n = _mm_mul_ps( _mm_set1_ps( a[row * 4 + 0] ), t0 );
		n = _mm_add_ps( n, _mm_mul_ps( _mm_set1_ps( a[row * 4 + 1] ), t1 ) );
		n = _mm_add_ps( n, _mm_mul_ps( _mm_set1_ps( a[row * 4 + 2] ), t2 ) );
		n = _mm_add_ps( n, _mm_set_ps( a[row * 4 + 3], 0.0f, 0.0f, 0.0f ) );
		_mm_storeu_ps( dst + row * 4, n );
	}
}

/*
============
idSIMD_SSE2::TransformJoints
============
*/
void VPCALL idSIMD_SSE2::TransformJoints( idJointMat * RESTRICT jointMats, const int * RESTRICT parents, const int firstJoint, const int lastJoint ) {
	for ( int i = firstJoint; i <= lastJoint; i++ ) {
		assert( parents[i] < i );
		float *m = jointMats[i].ToFloatPtr();
		const float *p = jointMats[parents[i]].ToFloatPtr();

		__m128 t0 = _mm_loadu_ps( m + 0 );
		__m128 t1 = _mm_loadu_ps( m + 4 );
		__m128 t2 = _mm_loadu_ps( m + 8 );

		SSE2_ComposeJointMat( m, p, t0, t1, t2 );
	}
}

/*
============
idSIMD_SSE2::MultiplyJoints
============
*/
void VPCALL idSIMD_SSE2::MultiplyJoints( idJointMat * RESTRICT result, const idJointMat * RESTRICT joints1, const idJointMat * RESTRICT joints2, const int numJoints ) {
	for ( int i = 0; i < numJoints; i++ ) {
		const float *m2 = joints2[i].ToFloatPtr();

		__m128 t0 = _mm_loadu_ps( m2 + 0 );
		__m128 t1 = _mm_loadu_ps( m2 + 4 );
		__m128 t2 = _mm_loadu_ps( m2 + 8 );

		SSE2_ComposeJointMat( result[i].ToFloatPtr(), joints1[i].ToFloatPtr(), t0, t1, t2 );
	}
}

/*
============
idSIMD_SSE2::TransformVerts
============
*/
void VPCALL idSIMD_SSE2::TransformVerts( idDrawVert *verts, const int numVerts, const idJointMat *joints, const idVec4 *weights, const int *index, const int numWeights ) {
	const byte *jointsPtr = (const byte *)joints;

	for ( int j = 0, i = 0; i < numVerts; i++ ) {
		__m128 v = SSE2_JointMatMulVec4(
			(const float *)( jointsPtr + index[j * 2 + 0] ), _mm_loadu_ps( weights[j].ToFloatPtr() ) );
		while ( index[j * 2 + 1] == 0 ) {
			j++;
			v = _mm_add_ps( v, SSE2_JointMatMulVec4(
				(const float *)( jointsPtr + index[j * 2 + 0] ), _mm_loadu_ps( weights[j].ToFloatPtr() ) ) );
		}
		j++;

		SSE2_StoreVec3( verts[i].xyz.ToFloatPtr(), v );
	}
}

/*
============
idSIMD_SSE2::TransformVertsNew
============
*/
void VPCALL idSIMD_SSE2::TransformVertsNew( idDrawVert * RESTRICT verts, const int numVerts, idBounds &bounds, const idJointMat * RESTRICT joints, const idVec4 * RESTRICT base, const jointWeight_t * RESTRICT weights, const int numWeights ) {
	const byte * RESTRICT jointsPtr = (const byte * RESTRICT)joints;

	// mirrors the bounds.Zero() starting state of the generic version,
	// which always keeps the origin inside the bounds
	__m128 minAcc = _mm_setzero_ps();
	__m128 maxAcc = _mm_setzero_ps();

	for ( int j = 0, i = 0; i < numVerts; i++, j++ ) {
		__m128 v = SSE2_JointMatMulVec4(
			(const float *)( jointsPtr + weights[j].jointMatOffset ), _mm_loadu_ps( base[j].ToFloatPtr() ) );
		while ( weights[j].nextVertexOffset != JOINTWEIGHT_SIZE ) {
			j++;
			v = _mm_add_ps( v, SSE2_JointMatMulVec4(
				(const float *)( jointsPtr + weights[j].jointMatOffset ), _mm_loadu_ps( base[j].ToFloatPtr() ) ) );
		}

		SSE2_StoreVec3( verts[i].xyz.ToFloatPtr(), v );

		minAcc = _mm_min_ps( minAcc, v );
		maxAcc = _mm_max_ps( maxAcc, v );
	}

	SSE2_StoreVec3( bounds[0].ToFloatPtr(), minAcc );
	SSE2_StoreVec3( bounds[1].ToFloatPtr(), maxAcc );
}

/*
============
idSIMD_SSE2::TransformVertsAndTangents
============
*/
void VPCALL idSIMD_SSE2::TransformVertsAndTangents( idDrawVert * RESTRICT verts, const int numVerts, idBounds &bounds, const idJointMat * RESTRICT joints, const idVec4 * RESTRICT base, const jointWeight_t * RESTRICT weights, const int numWeights ) {
	const byte * RESTRICT jointsPtr = (const byte * RESTRICT)joints;

	__m128 minAcc = _mm_setzero_ps();
	__m128 maxAcc = _mm_setzero_ps();

	for ( int j = 0, i = 0; i < numVerts; i++, j++ ) {
		// blend the joint matrices for this vertex
		{
			const float *m = (const float *)( jointsPtr + weights[j].jointMatOffset );
			__m128 ws = _mm_set1_ps( weights[j].weight );
			__m128 m0 = _mm_mul_ps( ws, _mm_loadu_ps( m + 0 ) );
			__m128 m1 = _mm_mul_ps( ws, _mm_loadu_ps( m + 4 ) );
			__m128 m2 = _mm_mul_ps( ws, _mm_loadu_ps( m + 8 ) );
			while ( weights[j].nextVertexOffset != JOINTWEIGHT_SIZE ) {
				j++;
				m = (const float *)( jointsPtr + weights[j].jointMatOffset );
				ws = _mm_set1_ps( weights[j].weight );
				m0 = _mm_add_ps( m0, _mm_mul_ps( ws, _mm_loadu_ps( m + 0 ) ) );
				m1 = _mm_add_ps( m1, _mm_mul_ps( ws, _mm_loadu_ps( m + 4 ) ) );
				m2 = _mm_add_ps( m2, _mm_mul_ps( ws, _mm_loadu_ps( m + 8 ) ) );
			}

			// transpose the blended matrix to columns and run all four base
			// vectors of the vertex through it
			__m128 c0 = m0, c1 = m1, c2 = m2, c3 = _mm_setzero_ps();
			_MM_TRANSPOSE4_PS( c0, c1, c2, c3 );

			const float *bp = base[i * 4].ToFloatPtr();

			__m128 pos = SSE2_TransformColumns( c0, c1, c2, c3, _mm_loadu_ps( bp + 0 ) );
			__m128 nrm = SSE2_TransformColumns( c0, c1, c2, c3, _mm_loadu_ps( bp + 4 ) );
			__m128 tan0 = SSE2_TransformColumns( c0, c1, c2, c3, _mm_loadu_ps( bp + 8 ) );
			__m128 tan1 = SSE2_TransformColumns( c0, c1, c2, c3, _mm_loadu_ps( bp + 12 ) );

			SSE2_StoreVec3( verts[i].xyz.ToFloatPtr(), pos );
			SSE2_StoreVec3( verts[i].normal.ToFloatPtr(), nrm );
			SSE2_StoreVec3( verts[i].tangents[0].ToFloatPtr(), tan0 );
			SSE2_StoreVec3( verts[i].tangents[1].ToFloatPtr(), tan1 );

			minAcc = _mm_min_ps( minAcc, pos );
			maxAcc = _mm_max_ps( maxAcc, pos );
		}
	}

	SSE2_StoreVec3( bounds[0].ToFloatPtr(), minAcc );
	SSE2_StoreVec3( bounds[1].ToFloatPtr(), maxAcc );
}

/*
============
idSIMD_SSE2::TransformVertsAndTangentsFast
============
*/
void VPCALL idSIMD_SSE2::TransformVertsAndTangentsFast( idDrawVert * RESTRICT verts, const int numVerts, idBounds &bounds, const idJointMat * RESTRICT joints, const idVec4 * RESTRICT base, const jointWeight_t * RESTRICT weights, const int numWeights ) {
	const byte * RESTRICT jointsPtr = (const byte * RESTRICT)joints;
	const byte * RESTRICT weightsPtr = (const byte * RESTRICT)weights;

	__m128 minAcc = _mm_setzero_ps();
	__m128 maxAcc = _mm_setzero_ps();

	for ( int i = 0; i < numVerts; i++ ) {
		const jointWeight_t *weight = (const jointWeight_t *)weightsPtr;
		const float *m = (const float *)( jointsPtr + weight->jointMatOffset );

		weightsPtr += weight->nextVertexOffset;

		__m128 c0 = _mm_loadu_ps( m + 0 );
		__m128 c1 = _mm_loadu_ps( m + 4 );
		__m128 c2 = _mm_loadu_ps( m + 8 );
		__m128 c3 = _mm_setzero_ps();
		_MM_TRANSPOSE4_PS( c0, c1, c2, c3 );

		const float *bp = base[i * 4].ToFloatPtr();

		__m128 pos = SSE2_TransformColumns( c0, c1, c2, c3, _mm_loadu_ps( bp + 0 ) );
		__m128 nrm = SSE2_TransformColumns( c0, c1, c2, c3, _mm_loadu_ps( bp + 4 ) );
		__m128 tan0 = SSE2_TransformColumns( c0, c1, c2, c3, _mm_loadu_ps( bp + 8 ) );
		__m128 tan1 = SSE2_TransformColumns( c0, c1, c2, c3, _mm_loadu_ps( bp + 12 ) );

		SSE2_StoreVec3( verts[i].xyz.ToFloatPtr(), pos );
		SSE2_StoreVec3( verts[i].normal.ToFloatPtr(), nrm );
		SSE2_StoreVec3( verts[i].tangents[0].ToFloatPtr(), tan0 );
		SSE2_StoreVec3( verts[i].tangents[1].ToFloatPtr(), tan1 );

		minAcc = _mm_min_ps( minAcc, pos );
		maxAcc = _mm_max_ps( maxAcc, pos );
	}

	SSE2_StoreVec3( bounds[0].ToFloatPtr(), minAcc );
	SSE2_StoreVec3( bounds[1].ToFloatPtr(), maxAcc );
}

/*
============
idSIMD_SSE2::CreateShadowCache
============
*/
int VPCALL idSIMD_SSE2::CreateShadowCache( idVec4 * RESTRICT vertexCache, int * RESTRICT vertRemap, const idVec3 &lightOrigin, const idDrawVert * RESTRICT verts, const int numVerts ) {
	const __m128 xyzMask = _mm_castsi128_ps( _mm_set_epi32( 0, -1, -1, -1 ) );
	const __m128 oneW = _mm_set_ps( 1.0f, 0.0f, 0.0f, 0.0f );
	const __m128 lo = _mm_set_ps( 0.0f, lightOrigin.z, lightOrigin.y, lightOrigin.x );

	int outVerts = 0;
	for ( int i = 0; i < numVerts; i++ ) {
		if ( vertRemap[i] ) {
			continue;
		}
		__m128 v = _mm_and_ps( _mm_loadu_ps( verts[i].xyz.ToFloatPtr() ), xyzMask );
		_mm_storeu_ps( vertexCache[outVerts+0].ToFloatPtr(), _mm_or_ps( v, oneW ) );

		// R_SetupProjection() builds the projection matrix with a slight crunch
		// for depth, which keeps this w=0 division from rasterizing right at the
		// wrap around point and causing depth fighting with the rear caps
		_mm_storeu_ps( vertexCache[outVerts+1].ToFloatPtr(), _mm_sub_ps( v, lo ) );
		vertRemap[i] = outVerts;
		outVerts += 2;
	}
	return outVerts;
}

/*
============
idSIMD_SSE2::CreateVertexProgramShadowCache
============
*/
int VPCALL idSIMD_SSE2::CreateVertexProgramShadowCache( idVec4 * RESTRICT vertexCache, const idDrawVert * RESTRICT verts, const int numVerts ) {
	const __m128 xyzMask = _mm_castsi128_ps( _mm_set_epi32( 0, -1, -1, -1 ) );
	const __m128 oneW = _mm_set_ps( 1.0f, 0.0f, 0.0f, 0.0f );

	for ( int i = 0; i < numVerts; i++ ) {
		__m128 v = _mm_and_ps( _mm_loadu_ps( verts[i].xyz.ToFloatPtr() ), xyzMask );
		_mm_storeu_ps( vertexCache[i*2+0].ToFloatPtr(), _mm_or_ps( v, oneW ) );
		_mm_storeu_ps( vertexCache[i*2+1].ToFloatPtr(), v );
	}
	return numVerts * 2;
}

#endif /* ID_SIMD_SSE2_AVAILABLE */
