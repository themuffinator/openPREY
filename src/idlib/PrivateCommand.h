/*
===========================================================================

openQ4 private command matching helpers
Copyright (C) 2026 DarkMatter Productions

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

===========================================================================
*/

#ifndef __PRIVATECOMMAND_H__
#define __PRIVATECOMMAND_H__

#include <cstddef>
#include <cstring>

namespace idPrivateCommand {

static inline bool IsNameCharacter( const unsigned char value ) {
	return ( value >= 'a' && value <= 'z' ) ||
		( value >= 'A' && value <= 'Z' ) ||
		( value >= '0' && value <= '9' ) || value == '_' || value == '.';
}

static inline unsigned char FoldASCII( const unsigned char value ) {
	return value >= 'A' && value <= 'Z' ?
		static_cast<unsigned char>( value + ( 'a' - 'A' ) ) : value;
}

// Matches a complete CVar-name token anywhere in a command line. Lengths are
// established before the scan so a command ending in a prefix of name never
// causes the comparison or right-boundary check to read beyond its NUL byte.
static inline bool ContainsBoundedCaseInsensitiveToken( const char *commandText,
		const char *name ) {
	if ( commandText == NULL || name == NULL || commandText[ 0 ] == '\0' || name[ 0 ] == '\0' ) {
		return false;
	}

	const std::size_t commandBytes = std::strlen( commandText );
	const std::size_t nameBytes = std::strlen( name );
	if ( nameBytes > commandBytes ) {
		return false;
	}

	for ( std::size_t offset = 0; offset <= commandBytes - nameBytes; ++offset ) {
		bool equal = true;
		for ( std::size_t index = 0; index < nameBytes; ++index ) {
			if ( FoldASCII( static_cast<unsigned char>( commandText[ offset + index ] ) ) !=
				FoldASCII( static_cast<unsigned char>( name[ index ] ) ) ) {
				equal = false;
				break;
			}
		}
		if ( !equal ) {
			continue;
		}

		const bool leftBounded = offset == 0 ||
			!IsNameCharacter( static_cast<unsigned char>( commandText[ offset - 1 ] ) );
		const std::size_t rightOffset = offset + nameBytes;
		const bool rightBounded = rightOffset == commandBytes ||
			!IsNameCharacter( static_cast<unsigned char>( commandText[ rightOffset ] ) );
		if ( leftBounded && rightBounded ) {
			return true;
		}
	}
	return false;
}

} // namespace idPrivateCommand

#endif /* !__PRIVATECOMMAND_H__ */
