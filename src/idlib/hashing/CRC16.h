
#ifndef __CRC16_H__
#define __CRC16_H__

#include <stdint.h>

/*
===============================================================================

	Calculates a checksum for a block of data
	using the CCITT standard CRC-16.

===============================================================================
*/

void CRC16_InitChecksum( uint16_t &crcvalue );
void CRC16_UpdateChecksum( uint16_t &crcvalue, const void *data, int length );
void CRC16_FinishChecksum( uint16_t &crcvalue );
uint16_t CRC16_BlockChecksum( const void *data, int length );

#endif /* !__CRC16_H__ */
