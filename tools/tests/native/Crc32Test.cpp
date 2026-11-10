// CRC wire compatibility: independent polynomial oracle, unaligned data and
// incremental chunks crossing the optimized eight- and sixteen-byte boundaries.
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>
typedef unsigned char byte;
#define __PRECOMPILED_H__
#include "../../../src/idlib/hashing/CRC32.cpp"

static uint32_t Reference( const byte *data, int length ) {
	uint32_t crc = 0xffffffffu;
	for ( int i = 0; i < length; ++i ) {
		crc ^= data[i];
		for ( int bit = 0; bit < 8; ++bit ) {
			crc = ( crc >> 1 ) ^ ( ( crc & 1 ) ? 0xedb88320u : 0 );
		}
	}
	return crc ^ 0xffffffffu;
}

int main() {
	if ( CRC32_BlockChecksum( "123456789", 9 ) != 0xcbf43926u ||
		CRC32_BlockChecksum( nullptr, 0 ) != 0 ) return 1;
	std::vector<byte> bytes( 65536 + 16 );
	uint32_t random = 0x12345678u;
	for ( byte &value : bytes ) {
		random ^= random << 13; random ^= random >> 17; random ^= random << 5;
		value = static_cast<byte>( random );
	}
	for ( int offset = 0; offset < 16; ++offset ) {
		for ( int length : { 0, 1, 7, 8, 9, 15, 16, 17, 31, 32, 33, 255, 256, 257, 4096, 65536 } ) {
			const byte *data = bytes.data() + offset;
			const uint32_t expected = Reference( data, length );
			if ( CRC32_BlockChecksum( data, length ) != expected ) return 2;
			for ( int chunk : { 1, 7, 8, 9, 15, 16, 17, 127, 4096 } ) {
				uint32_t crc;
				CRC32_InitChecksum( crc );
				for ( int i = 0; i < length; i += chunk ) {
					CRC32_UpdateChecksum( crc, data + i, length-i < chunk ? length-i : chunk );
				}
				CRC32_FinishChecksum( crc );
				if ( crc != expected ) return 3;
			}
		}
	}
	std::puts( "CRC32 wire compatibility passed" );
	return 0;
}
