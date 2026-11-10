#ifndef __STR_ALLOCATION_H__
#define __STR_ALLOCATION_H__

#include <stddef.h>

namespace idStrAllocationDetail {

inline size_t SaturatingAdd( size_t left, size_t right ) {
	const size_t maximum = static_cast<size_t>( -1 );
	return right > maximum - left ? maximum : left + right;
}

inline size_t SaturatingMultiply( size_t left, size_t right ) {
	const size_t maximum = static_cast<size_t>( -1 );
	return left != 0 && right > maximum / left ? maximum : left * right;
}

inline bool TryRoundUpToInt( size_t amount, size_t granularity, int &roundedAmount ) {
	if ( amount == 0 || granularity == 0 ) {
		return false;
	}

	const size_t remainder = amount % granularity;
	const size_t padding = remainder == 0 ? 0 : granularity - remainder;
	const size_t maximum = static_cast<size_t>( static_cast<unsigned int>( -1 ) >> 1 );
	if ( amount > maximum || padding > maximum - amount ) {
		return false;
	}

	roundedAmount = static_cast<int>( amount + padding );
	return true;
}

} // namespace idStrAllocationDetail

#endif
