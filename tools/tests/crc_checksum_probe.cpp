// Preserved from openQ4-game; Quake 4 SDK EULA. See docs/dev/game-test-coverage.md.
#include <climits>
#include <cstdint>
#include <cstring>

typedef unsigned char byte;

#define __PRECOMPILED_H__

namespace crc8_impl {
#include "../../src/idlib/hashing/CRC8.cpp"
}

namespace crc16_impl {
#include "../../src/idlib/hashing/CRC16.cpp"
}

namespace crc32_impl {
#include "../../src/idlib/hashing/CRC32.cpp"
}

namespace honeyman_impl {
#include "../../src/idlib/hashing/Honeyman.cpp"
}

struct checksumVector_t {
	const char *text;
	uint32_t crc32;
	uint32_t honeyman;
};

int main() {
#if !defined( __linux__ )
#error This checksum probe must be compiled on Linux.
#endif

	static_assert( sizeof( unsigned long ) == 8, "Linux x64/arm64 must use LP64 for this probe" );
	static_assert( sizeof( decltype( crc8_impl::CRC8_BlockChecksum( nullptr, 0 ) ) ) == 1, "CRC-8 state must stay 8-bit" );
	static_assert( sizeof( decltype( crc16_impl::CRC16_BlockChecksum( nullptr, 0 ) ) ) == 2, "CRC-16 state must stay 16-bit" );
	static_assert( sizeof( crc32_impl::crc32Word_t ) == 4, "CRC-32 state must stay 32-bit" );
	static_assert( sizeof( honeyman_impl::honeymanWord_t ) == 4, "Honeyman state must stay 32-bit" );

	const checksumVector_t vectors[] = {
		{ "", 0x00000000UL, 0x00000000UL },
		{ "a", 0xe8b7be43UL, 0x4b600000UL },
		{ "abc", 0x352441c2UL, 0x6f2fed80UL },
		{ "123456789", 0xcbf43926UL, 0x4dbabd04UL },
		{ "message digest", 0x20159d7fUL, 0x77423c07UL },
		{ "The quick brown fox jumps over the lazy dog", 0x414fa339UL, 0x346a4297UL },
	};

	for ( const checksumVector_t &vector : vectors ) {
		const int length = static_cast<int>( std::strlen( vector.text ) );
		if ( crc32_impl::CRC32_BlockChecksum( vector.text, length ) != vector.crc32 ) {
			return 1;
		}
		if ( honeyman_impl::Honeyman_BlockChecksum( vector.text, length ) != vector.honeyman ) {
			return 2;
		}

		uint32_t crc32 = 0;
		crc32_impl::CRC32_InitChecksum( crc32 );
		for ( int i = 0; i < length; ++i ) {
			crc32_impl::CRC32_Update( crc32, static_cast<byte>( vector.text[i] ) );
		}
		crc32_impl::CRC32_FinishChecksum( crc32 );
		if ( crc32 != vector.crc32 ) {
			return 3;
		}

		uint32_t honeyman = 0;
		honeyman_impl::Honeyman_InitChecksum( honeyman );
		for ( int i = 0; i < length; ++i ) {
			honeyman_impl::Honeyman_Update( honeyman, static_cast<byte>( vector.text[i] ) );
		}
		honeyman_impl::Honeyman_FinishChecksum( honeyman );
		if ( honeyman != vector.honeyman ) {
			return 4;
		}
	}

	static const char canonical[] = "123456789";
	if ( crc8_impl::CRC8_BlockChecksum( canonical, 9 ) != 0xf4u ) {
		return 5;
	}
	if ( crc16_impl::CRC16_BlockChecksum( canonical, 9 ) != 0x29b1u ) {
		return 6;
	}

	return 0;
}
