// Copyright (C) 2026 DarkMatter Productions
#ifndef OPENQ4_SAVE_DICTIONARY_ENCODING_H
#define OPENQ4_SAVE_DICTIONARY_ENCODING_H

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <initializer_list>

// The established length-prefixed dictionary payload, excluding its pair count.
// Both the save writer and bounded cache population use this encoder. Returning
// false from emit cancels work before another chunk; invalidLength distinguishes
// an invalid string from deliberate cancellation. No allocation or timing here.
template<class Dictionary, class Emit>
bool EncodeSaveDictionaryPayload( const Dictionary &dict, size_t maxStringBytes,
		Emit emit, size_t &invalidLength ) {
	invalidLength = 0;
	unsigned char encoded[16384];
	size_t used = 0;
	const int count = dict.GetNumKeyVals();
	for ( int i = 0; i < count; ++i ) {
		const auto *pair = dict.GetKeyVal( i );
		for ( const auto *string : { &pair->GetKey(), &pair->GetValue() } ) {
			const size_t length = std::strlen( string->c_str() );
			if ( length >= maxStringBytes || length > sizeof( encoded ) - 4 ) {
				invalidLength = length;
				return false;
			}
			if ( used + 4 + length > sizeof( encoded ) ) {
				if ( !emit( encoded, used ) ) return false;
				used = 0;
			}
			for ( int b = 0; b < 4; ++b ) encoded[used++] = static_cast<unsigned char>( static_cast<uint32_t>( length ) >> (b * 8) );
			std::memcpy( encoded + used, string->c_str(), length );
			used += length;
		}
	}
	return emit( encoded, used );
}
#endif
