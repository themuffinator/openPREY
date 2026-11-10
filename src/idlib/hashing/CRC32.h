
#ifndef __CRC32_H__
#define __CRC32_H__

#include <stdint.h>

/*
===============================================================================

	Calculates a checksum for a block of data
	using the CRC-32.

===============================================================================
*/

void CRC32_InitChecksum( uint32_t &crcvalue );
void CRC32_UpdateChecksum( uint32_t &crcvalue, const void *data, int length );
void CRC32_FinishChecksum( uint32_t &crcvalue );
uint32_t CRC32_BlockChecksum( const void *data, int length );

#endif /* !__CRC32_H__ */
