
#ifndef __CRC8_H__
#define __CRC8_H__

#include <stdint.h>

/*
===============================================================================

	Calculates a checksum for a block of data
	using the CRC-8.

===============================================================================
*/

void CRC8_InitChecksum( uint8_t &crcvalue );
void CRC8_UpdateChecksum( uint8_t &crcvalue, const void *data, int length );
void CRC8_FinishChecksum( uint8_t &crcvalue );
uint8_t CRC8_BlockChecksum( const void *data, int length );

#endif /* !__CRC8_H__ */
