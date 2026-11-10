// Preserved from openQ4-game; Quake 4 SDK EULA. See docs/dev/game-test-coverage.md.
#include <cstdint>
#include <cstdio>
#include <cstring>

// openQ4's supported Linux x64 and arm64 targets are little-endian.  Supply
// the two endian helpers normally provided by the engine precompiled header so
// this probe exercises the production MD5 implementation in isolation.
static void LittleRevBytes( void *, int, int ) {
}

static unsigned int LittleLong( unsigned int value ) {
	return value;
}

#define __PRECOMPILED_H__
#include "../../src/idlib/hashing/MD5.cpp"

struct checksumVector_t {
	const char *text;
	uint32_t expected;
};

int main() {
#if !defined( __linux__ )
#error This checksum probe must be compiled on Linux.
#endif

	const checksumVector_t vectors[] = {
		{ "", 0x3b75655eUL },
		{ "abc", 0x275fa452UL },
		{ "openQ4", 0x8a8bae9bUL },
	};

	for ( const checksumVector_t &vector : vectors ) {
		const int length = static_cast<int>( std::strlen( vector.text ) );
		for ( int iteration = 0; iteration < 64; ++iteration ) {
			if ( MD5_BlockChecksum( vector.text, length ) != vector.expected ) {
				return 1;
			}
		}
	}

	return 0;
}
