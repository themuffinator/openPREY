#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#define ID_INLINE inline
using byte = unsigned char;
#include "src/idlib/containers/List.h"
#include "src/idlib/containers/Queue.h"

constexpr int MAX_FEATURE_LIST = 20, MAX_AREAS_TOUCHED = 450;
constexpr int TFL_WALK = 1, AREA_REACHABLE_WALK = 1;
constexpr float MAX_DISTANCE = 650.0f;
struct idVec3 {
	float x = 0;
	float Dist( const idVec3 &other ) const { return std::fabs( x - other.x ); }
};
struct idReachability { int toAreaNum = 0, travelType = TFL_WALK; idVec3 end; idReachability *next = nullptr; };
struct aasFeature_t { int id = 0; byte weight = 0; idVec3 origin; idVec3 Origin() const { return origin; } };
using TFeaturePtr = aasFeature_t *;
struct aasArea_t { int firstFeature = 0, numFeatures = 0; idReachability *reach = nullptr; };
struct idAASFile {
	std::vector<aasArea_t> areas;
	std::vector<aasFeature_t> features;
	int GetNumAreas() const { return static_cast<int>( areas.size() ); }
	int GetNumFeatures() const { return static_cast<int>( features.size() ); }
	const aasArea_t &GetArea( int area ) const { return areas.at( area ); }
	aasFeature_t &GetFeature( int feature ) { return features.at( feature ); }
	int GetFeatureIndex( int feature ) const { return feature; }
};
struct idAAS {
	idAASFile file;
	int ownerArea = 1;
	idAASFile *GetFile() { return &file; }
	int PointReachableAreaNum( const idVec3 &, int, int ) const { return ownerArea; }
	bool WalkPathValid( int, const idVec3 &, int, const idVec3 &, int, idVec3 &, int & ) const { return true; }
};
struct Physics { int GetBounds() const { return 0; } };
struct Entity { Physics physics; Physics *GetPhysics() { return &physics; } const char *GetName() const { return "fixture"; } };
struct AI : Entity { idAAS *aas = nullptr; int PointReachableAreaNum( const idVec3 & ) { return aas->ownerArea; } };
struct { idAAS *aas = nullptr; idAAS *GetAAS( int ) { return aas; } int GetTime() const { return 0; } } gameLocal;
struct { int GetInteger() const { return 0; } } ai_showTacticalFeatures;
struct Common { void Printf( const char *, ... ) {} } commonValue, *common = &commonValue;
struct TestSet { idVec3 mOrigin; struct { float mMin = 0; } mDistance; };
class rvAASTacticalSensorLocal {
public:
	Entity *mOwner = nullptr;
	AI *mOwnerAI = nullptr;
	idList<TFeaturePtr> mFeatures;
	bool mAssignmentValid = false;
	struct { void Reset() {} } mAssignment;
	TestSet mFromOwner;
	int mFeaturesSearchMax = 32;
	std::string mSearchName;
	std::vector<int> seen;
	float SearchComputeWeightRange( float & ) { return 0; }
	float SearchComputeWeight() { return 0; }
	bool TestValid( aasFeature_t *feature, float ) { seen.push_back( feature->id ); return true; }
	void Search();
};
#ifndef AAS_TACTICAL_TEST_INCLUDE
#define AAS_TACTICAL_TEST_INCLUDE "AasTacticalUnderTest.inc"
#endif
#include AAS_TACTICAL_TEST_INCLUDE

static int failures = 0;
static void Check( bool condition, const char *label ) {
	if ( !condition ) { std::fprintf( stderr, "%s\n", label ); ++failures; }
}
int main( int argc, char ** ) {
	idAAS aas;
	gameLocal.aas = &aas;
	aas.file.areas.resize( 7 );
	aas.file.features.resize( 5 );
	idReachability reaches[5];
	const float distances[] = { 6, 1, 4, 2, 3 };
	for ( int i = 0; i < 5; ++i ) {
		reaches[i].toAreaNum = i + 2; reaches[i].end.x = distances[i];
		reaches[i].next = i + 1 < 5 ? &reaches[i + 1] : nullptr;
		aas.file.areas[i + 2].firstFeature = i; aas.file.areas[i + 2].numFeatures = 1;
		aas.file.features[i].id = i + 2; aas.file.features[i].origin.x = distances[i];
	}
	aas.file.areas[1].reach = reaches;
	Entity owner;
	rvAASTacticalSensorLocal sensor;
	sensor.mOwner = &owner; sensor.mFeaturesSearchMax = 4;
	sensor.Search();
	Check( sensor.seen == std::vector<int>({3, 5, 6, 4}), "tactical search did not visit nearest areas first" );
	const int capacity = sensor.mFeatures.NumAllocated();
	sensor.seen.clear(); sensor.Search();
	Check( sensor.seen == std::vector<int>({3, 5, 6, 4}), "repeat search retained stale visit marks" );
	Check( sensor.mFeatures.NumAllocated() == capacity, "repeat search changed result capacity" );
	TFeaturePtr first = &aas.file.features[0];
	Check( rvSortFeature( &first, &first ) == 0, "feature comparison must report equality" );
	sensor.mOwner = nullptr; sensor.Search();
	Check( sensor.mFeatures.Num() == 0, "search without an owner retained stale features" );
	if ( argc > 1 ) { return failures ? 1 : 0; }

	// Real area numbers can exceed the former 32000-bit fixed bitmap.
	sensor.mOwner = &owner; aas.ownerArea = 40000;
	aas.file.areas.clear(); aas.file.areas.resize( 40002 );
	aas.file.areas[40000].reach = &reaches[0];
	reaches[0].toAreaNum = 40001; reaches[0].next = &reaches[1];
	reaches[1].toAreaNum = -1; reaches[1].next = &reaches[2];
	reaches[2].toAreaNum = 40002; reaches[2].next = nullptr;
	aas.file.areas[40001].numFeatures = 1;
	sensor.seen.clear(); sensor.Search();
	Check( sensor.seen == std::vector<int>({2}), "large-map feature search or invalid-edge handling" );
	for ( int invalid : { 0, -1, 40002 } ) {
		aas.ownerArea = invalid; sensor.seen.clear(); sensor.Search();
		Check( sensor.mFeatures.Num() == 0 && sensor.seen.empty(), "invalid owner area must not be searched" );
	}
	// Reusing the static workspace for a smaller map must reset its bounds.
	aas.file.areas.resize( 2 ); aas.ownerArea = 1;
	aas.file.areas[1].reach = nullptr; aas.file.areas[1].numFeatures = 1;
	sensor.seen.clear(); sensor.Search();
	Check( sensor.seen == std::vector<int>({2}), "map shrink retained old search bounds" );
	if ( !failures ) { std::puts( "tactical search ordering, reuse and large-map bounds passed" ); }
	return failures ? 1 : 0;
}
