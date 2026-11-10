// Preserved from openQ4-game; Quake 4 SDK EULA. See docs/dev/game-test-coverage.md.
#include <cstdint>
#include <cstring>

#define ID_INLINE inline

static unsigned int idMath_FloatBits( const float value ) {
	unsigned int bits;
	std::memcpy( &bits, &value, sizeof( bits ) );
	return bits;
}

static float idMath_FloatFromBits( const unsigned int bits ) {
	float value;
	std::memcpy( &value, &bits, sizeof( value ) );
	return value;
}

class idMath {
public:
	static int BitsForInteger( int value ) {
		int bits = 1;
		while ( value >>= 1 ) {
			++bits;
		}
		return bits;
	}
};

#include "../../src/idlib/math/Random.h"

int main() {
#if !defined( __linux__ )
#error This LP64 semantics probe must be compiled on Linux.
#endif

	static_assert( sizeof( unsigned long ) == 8, "Linux x64/arm64 must use the LP64 data model" );
	static_assert( sizeof( unsigned int ) == 4, "serialized engine words must be 32-bit" );
	static_assert( sizeof( idRandom ) == 4, "idRandom state must stay one 32-bit word" );
	static_assert( sizeof( idRandom2 ) == 4, "idRandom2 state must stay one 32-bit word" );

	idRandom legacyRandom( 0 );
	if ( legacyRandom.RandomInt() != 1 || legacyRandom.GetSeed() != 1 ) {
		return 1;
	}
	if ( legacyRandom.RandomInt() != 3534 || legacyRandom.GetSeed() != 69070 ) {
		return 2;
	}
	if ( legacyRandom.RandomInt() != 1015 || legacyRandom.GetSeed() != 475628535 ) {
		return 3;
	}
	if ( legacyRandom.RandomInt() != 14284 || legacyRandom.GetSeed() != -1017563188 ) {
		return 4;
	}

	idRandom legacyWraparound( -1 );
	if ( legacyWraparound.RandomInt() != 29236 || legacyWraparound.GetSeed() != -69068 ) {
		return 5;
	}

	idRandom2 random( 0u );
	if ( random.RandomInt() != 29535 || random.GetSeed() != 0x3c6ef35fu ) {
		return 11;
	}
	if ( idMath_FloatBits( random.RandomFloat() ) != 0x3f205264u || random.GetSeed() != 0x47502932u ) {
		return 12;
	}
	if ( idMath_FloatBits( random.CRandomFloat() ) != 0x3e4f6e90u || random.GetSeed() != 0xd1ccf6e9u ) {
		return 13;
	}

	idRandom2 wraparound( 0xffffffffu );
	if ( wraparound.RandomInt() != 3410 || wraparound.GetSeed() != 0x3c558d52u ) {
		return 14;
	}

	return 0;
}
