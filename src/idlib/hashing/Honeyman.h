
#ifndef __HONEYMAN_H__
#define __HONEYMAN_H__

#include <stdint.h>

/*
===============================================================================

	Calculates a checksum for a block of data
	using the simplified version of the pathalias hashing
	function by Steve Belovin and Peter Honeyman.

===============================================================================
*/

void Honeyman_InitChecksum( uint32_t &crcvalue );
void Honeyman_UpdateChecksum( uint32_t &crcvalue, const void *data, int length );
void Honeyman_FinishChecksum( uint32_t &crcvalue );
uint32_t Honeyman_BlockChecksum( const void *data, int length );

#endif /* !__HONEYMAN_H__ */
