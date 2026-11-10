// Compile the production dmap vertex-sharing implementation with a counted,
// fallible geometry allocator. No renderer or proprietary map assets required.
#include <array>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <functional>
#include <limits>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#ifdef INT_MAX
#undef INT_MAX
#endif

struct idMath {
	static constexpr int INT_MAX = std::numeric_limits<int>::max();
	static float Fabs( float value ) { return std::fabs( value ); }
};
using idVec3 = std::array<float, 3>;
static float DotProduct( const idVec3 &a, const idVec3 &b ) {
	return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}
struct idDrawVert {
	idVec3 xyz{}, normal{};
	std::array<float, 2> st{};
	float unused[8]{};
	void Clear() { *this = {}; }
};
static_assert( sizeof( idDrawVert ) == 64, "match the production vertex allocation size" );
struct mapTri_t {
	mapTri_t *next = nullptr;
	idDrawVert v[3];
};
struct srfTriangles_t {
	idDrawVert *verts = nullptr;
	int *indexes = nullptr;
	int numVerts = 0, numIndexes = 0;
};
struct TestCommon {
	[[noreturn]] void Error( const char *format, ... ) {
		char message[256];
		va_list args;
		va_start( args, format );
		std::vsnprintf( message, sizeof( message ), format, args );
		va_end( args );
		throw std::runtime_error( message );
	}
} testCommon;
static TestCommon *common = &testCommon;
static size_t vertexLimit = 16 * 1024 * 1024, indexLimit = 16 * 1024 * 1024;
static size_t vertexRequest = 0;
static int liveSurfaces = 0, liveBuffers = 0, forcedCount = -1;
static srfTriangles_t *R_AllocStaticTriSurf() {
	liveSurfaces++;
	return new srfTriangles_t;
}
static void R_AllocStaticTriSurfVerts( srfTriangles_t *tri, int count ) {
	vertexRequest = size_t( count ) * sizeof( idDrawVert );
	if ( count > 0 && vertexRequest <= vertexLimit ) {
		tri->verts = new idDrawVert[count];
		liveBuffers++;
	}
}
static void R_AllocStaticTriSurfIndexes( srfTriangles_t *tri, int count ) {
	if ( count > 0 && size_t( count ) * sizeof( int ) <= indexLimit ) {
		tri->indexes = new int[count];
		liveBuffers++;
	}
}
static void R_FreeStaticTriSurf( srfTriangles_t *tri ) {
	liveBuffers -= ( tri->verts != nullptr ) + ( tri->indexes != nullptr );
	delete[] tri->verts;
	delete[] tri->indexes;
	delete tri;
	liveSurfaces--;
}
static int CountTriList( const mapTri_t *tri ) {
	if ( forcedCount >= 0 ) {
		return forcedCount;
	}
	int count = 0;
	for ( ; tri; tri = tri->next ) { count++; }
	return count;
}

// @PRODUCTION@

static void Require( bool condition, const char *message ) {
	if ( !condition ) { throw std::runtime_error( message ); }
}
static idDrawVert Vertex( float x, float y = 0, float z = 0 ) {
	idDrawVert vert;
	vert.xyz = { x, y, z };
	vert.normal = { 0, 0, 1 };
	return vert;
}
static std::vector<mapTri_t> Triangles( std::vector<idDrawVert> vertices ) {
	while ( vertices.size() % 3 ) { vertices.push_back( vertices.back() ); }
	std::vector<mapTri_t> tris( vertices.size() / 3 );
	for ( size_t i = 0; i < tris.size(); i++ ) {
		tris[i].next = i + 1 < tris.size() ? &tris[i + 1] : nullptr;
		for ( int j = 0; j < 3; j++ ) { tris[i].v[j] = vertices[i * 3 + j]; }
	}
	return tris;
}
static void CompareWithLinearSearch( const std::vector<idDrawVert> &input ) {
	auto tris = Triangles( input );
	std::vector<idDrawVert> expectedVerts;
	std::vector<int> expectedIndexes;
	for ( const auto &tri : tris ) {
		for ( const auto &vert : tri.v ) {
			size_t match = 0;
			while ( match < expectedVerts.size() && !MatchVert( &expectedVerts[match], &vert ) ) { match++; }
			if ( match == expectedVerts.size() ) { expectedVerts.push_back( vert ); }
			expectedIndexes.push_back( int( match ) );
		}
	}
	srfTriangles_t *result = ShareMapTriVerts( tris.empty() ? nullptr : tris.data() );
	Require( result->numVerts == int( expectedVerts.size() ), "shared vertex count differs from linear search" );
	Require( result->numIndexes == int( expectedIndexes.size() ), "index count changed" );
	for ( int i = 0; i < result->numVerts; i++ ) {
		Require( result->verts[i].xyz == expectedVerts[i].xyz &&
			result->verts[i].st == expectedVerts[i].st &&
			result->verts[i].normal == expectedVerts[i].normal, "first matching vertex changed" );
	}
	for ( int i = 0; i < result->numIndexes; i++ ) {
		Require( result->indexes[i] == expectedIndexes[i], "index order or epsilon matching changed" );
	}
	R_FreeStaticTriSurf( result );
}
static void ExpectFailure( mapTri_t *tri, const char *message ) {
	bool failed = false;
	try {
		srfTriangles_t *result = ShareMapTriVerts( tri );
		R_FreeStaticTriSurf( result );
	} catch ( const std::runtime_error &error ) {
		failed = std::string( error.what() ).find( message ) != std::string::npos;
	}
	Require( failed, "missing useful compile error" );
	Require( liveSurfaces == 0 && liveBuffers == 0, "failed compile leaked geometry" );
}
int main() {
	try {
		CompareWithLinearSearch( {} );
		// Epsilon matches across positive/negative bucket boundaries on every
		// axis, ambiguous matches, UV seams, hard normals and smoothed normals.
		std::vector<idDrawVert> vertices;
		for ( int axis = 0; axis < 3; axis++ ) {
			for ( float base : { -10.0f, -1.0f, 0.0f, 1.0f, 10.0f, 65536.0f } ) {
				for ( float offset : { -0.009f, 0.009f, 0.0f, -0.01f, 0.01f, 0.02f } ) {
					auto vertex = Vertex( 3, 4, 5 );
					vertex.xyz[axis] = base + offset;
					vertices.push_back( vertex );
				}
			}
		}
		for ( float uv : { 0.0f, 0.0009f, 0.0011f, 1.0f } ) {
			for ( idVec3 normal : { idVec3{ 0, 0, 0 }, idVec3{ 0, 0, 1 }, idVec3{ 0, 1, 0 }, idVec3{ 0, 0, -1 } } ) {
				auto vertex = Vertex( 1 ); vertex.st[0] = uv; vertex.normal = normal; vertices.push_back( vertex );
			}
		}
		// Deterministic varied geometry and nearby copies exercise hash collisions
		// without making the test depend on unordered_map's iteration order.
		for ( int i = 0; i < 2000; i++ ) {
			auto vertex = Vertex( float( i % 41 ) - 20, float( i % 37 ) - 18, float( i % 31 ) - 15 );
			vertices.push_back( vertex ); vertex.xyz[i % 3] += 0.005f; vertices.push_back( vertex );
		}
		CompareWithLinearSearch( vertices );

		// A small allocator cap reproduces #181 without a multi-gigabyte fixture:
		// the old three-vertices-per-triangle reservation is rejected, but the
		// actual three shared vertices and all indexes fit comfortably.
		std::vector<mapTri_t> repeated( 14000 );
		for ( size_t i = 0; i < repeated.size(); i++ ) {
			repeated[i].next = i + 1 < repeated.size() ? &repeated[i + 1] : nullptr;
			repeated[i].v[0] = Vertex( 0 ); repeated[i].v[1] = Vertex( 1 ); repeated[i].v[2] = Vertex( 0, 1 );
		}
		vertexLimit = indexLimit = 256 * 1024;
		srfTriangles_t *result = ShareMapTriVerts( repeated.data() );
		Require( result->numVerts == 3 && result->numIndexes == 42000, "large repeated surface was truncated" );
		Require( vertexRequest == 3 * sizeof( idDrawVert ), "vertex allocation uses unshared triangle count" );
		for ( int i = 0; i < result->numIndexes; i++ ) { Require( result->indexes[i] == i % 3, "repeated surface index changed" ); }
		R_FreeStaticTriSurf( result );
		indexLimit = 1;
		ExpectFailure( repeated.data(), "indexes" );
		indexLimit = 256 * 1024; vertexLimit = 1;
		ExpectFailure( repeated.data(), "shared vertices" );
		vertexLimit = 256 * 1024;
		forcedCount = idMath::INT_MAX / 3 + 1;
		ExpectFailure( repeated.data(), "too many triangles" );
		forcedCount = -1;
		repeated[0].v[0].xyz[0] = std::numeric_limits<float>::infinity();
		ExpectFailure( repeated.data(), "non-finite" );
		Require( liveSurfaces == 0 && liveBuffers == 0, "geometry leaked" );
		std::puts( "dmap_vertex_sharing: passed (legacy equivalence, bounded allocation, failure cleanup)" );
		return 0;
	} catch ( const std::exception &error ) {
		std::fprintf( stderr, "FAIL: %s\n", error.what() );
		return 1;
	}
}
