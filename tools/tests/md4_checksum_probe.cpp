// Preserved from openQ4-game; Quake 4 SDK EULA. See docs/dev/game-test-coverage.md.
#include <cstdint>
#include <cstdio>
#include <cstring>

#define __PRECOMPILED_H__
#include "../../src/idlib/hashing/MD4.cpp"

struct checksumVector_t {
	const char *text;
	uint32_t expected;
};

int main() {
#if !defined( __linux__ )
#error This checksum probe must be compiled on Linux.
#endif

	static_assert( sizeof( UINT4 ) == 4, "MD4 words must stay 32-bit on LP64 targets" );

	const checksumVector_t vectors[] = {
		{ "", 0xc6f640b7UL },
		{ "abc", 0x5da10e2eUL },
		{ "message digest", 0x24dc0744UL },
	};

	for ( const checksumVector_t &vector : vectors ) {
		const int length = static_cast<int>( std::strlen( vector.text ) );
		for ( int iteration = 0; iteration < 64; ++iteration ) {
			if ( MD4_BlockChecksum( vector.text, length ) != vector.expected ) {
				return 1;
			}
		}
	}

	return 0;
}
