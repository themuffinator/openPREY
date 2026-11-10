// Preserved from openQ4-game; Quake 4 SDK EULA. See docs/dev/game-test-coverage.md.
#include <alloca.h>
#include <cassert>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>

using ID_TIME_T = long;

#include "../../src/sys/sys_public.h"

ALIGN16( static unsigned char globalAlignmentProbe[1] );

int main() {
#if !defined( __linux__ )
#error This portability probe must be compiled on Linux.
#endif

	static_assert( BUILD_OS_ID == 2, "unexpected Linux build OS identifier" );
	static_assert( __alignof__( globalAlignmentProbe ) >= 16, "ALIGN16 did not align static storage" );
	if ( ( reinterpret_cast<uintptr_t>( globalAlignmentProbe ) & 15U ) != 0U ) {
		return 3;
	}

#if defined( __aarch64__ ) || defined( __arm64__ )
	if ( std::strcmp( BUILD_STRING, "linux-arm64" ) != 0 || std::strcmp( CPUSTRING, "arm64" ) != 0 ) {
		return 1;
	}
#elif defined( __x86_64__ )
	if ( std::strcmp( BUILD_STRING, "linux-x64" ) != 0 || std::strcmp( CPUSTRING, "x64" ) != 0 ) {
		return 2;
	}
#else
#error This portability probe currently covers Linux x64 and arm64.
#endif

	ALIGN16( unsigned char localAlignmentProbe[1] );
	ALIGN16( unsigned char declarationWithEmbeddedSemicolon[1]; )
	void *stackAllocation = _alloca16( 31 );
	if ( ( reinterpret_cast<uintptr_t>( localAlignmentProbe ) & 15U ) != 0U ) {
		return 4;
	}
	if ( ( reinterpret_cast<uintptr_t>( stackAllocation ) & 15U ) != 0U ) {
		return 5;
	}
	if ( ( reinterpret_cast<uintptr_t>( declarationWithEmbeddedSemicolon ) & 15U ) != 0U ) {
		return 6;
	}

	return 0;
}
