#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#define ID_INLINE inline
#include "src/idlib/containers/List.h"

static int failures = 0;

static void Check( bool condition, const char *label ) {
	if ( !condition ) {
		std::fprintf( stderr, "%s\n", label );
		++failures;
	}
}

static void CheckHeap( const std::vector<int> &values ) {
	idList<int> heap;
	for ( int value : values ) {
		heap.HeapAdd( value );
	}
	std::vector<int> expected = values;
	std::sort( expected.rbegin(), expected.rend() );
	for ( int value : expected ) {
		if ( heap[0] != value ) {
			Check( false, "HeapPop did not preserve priority order" );
			return;
		}
		heap.HeapPop();
	}
	Check( heap.Num() == 0, "drained heap must be empty" );
}

struct Counted {
	static int assignments;
	int value = 0;
	Counted &operator=( const Counted &other ) {
		value = other.value;
		++assignments;
		return *this;
	}
};
int Counted::assignments = 0;

int main( int argc, char **argv ) {
	// Keep the heap reproduction separate from the alias tests so an ASan
	// failure in the latter does not hide the priority-order regression.
	CheckHeap( { 9, 5, 8, 1, 2, 7, 6 } );
	std::vector<int> permutation = { 0, 1, 2, 3, 4, 5, 6 };
	do {
		CheckHeap( permutation );
		if ( failures ) { break; }
	} while ( std::next_permutation( permutation.begin(), permutation.end() ) );
	CheckHeap( { 4, 4, -1, 2, -1, 4, 0, 2 } );
	if ( argc > 1 && std::strcmp( argv[1], "heap" ) == 0 ) {
		return failures ? 1 : 0;
	}

	idList<std::string> strings( 1 );
	strings.Append( std::string( 128, 'a' ) );
	strings.Append( strings[0] );
	Check( strings.Num() == 2 && strings[1] == std::string( 128, 'a' ), "Append lost an aliased element on growth" );
	strings.Insert( strings[1], 0 );
	Check( strings.Num() == 3 && strings[0] == strings[2], "Insert lost an aliased element on growth" );
	strings.Resize( 16 );
	strings[0] = "first";
	strings[1] = "second";
	strings[2] = "third";
	strings.Insert( strings[2], 0 );
	Check( strings[0] == "third" && strings[1] == "first" && strings[3] == "third", "Insert overwrote its source while shifting" );
	strings.Append( strings );
	Check( strings.Num() == 8, "self-append must double the list" );
	for ( int i = 0; i < 4; ++i ) {
		Check( strings[i] == strings[i + 4], "self-append changed values" );
	}
	strings.Condense();
	strings.Append( strings );
	Check( strings.Num() == 16, "self-append with growth must double the list" );
	for ( int i = 0; i < 8; ++i ) {
		Check( strings[i] == strings[i + 8], "self-append with growth changed values" );
	}

	idList<Counted> source;
	source.SetNum( 4096 );
	for ( int i = 0; i < source.Num(); ++i ) { source[i].value = i; }
	idList<Counted> destination;
	Counted::assignments = 0;
	destination.Append( source );
	Check( destination.Num() == source.Num(), "bulk append has the wrong length" );
	Check( Counted::assignments <= 2 * source.Num(), "bulk append repeatedly copied its growing prefix" );
	for ( int i = 0; i < source.Num(); ++i ) {
		Check( destination[i].value == i, "bulk append changed order" );
	}
	if ( !failures ) { std::puts( "idList priority, aliasing and linear bulk-copy tests passed" ); }
	return failures ? 1 : 0;
}
