/*
===========================================================================

openQ4 GPL Source Code
Copyright (C) 2026 the openQ4 contributors.

This file is part of the openQ4 Source Code. See docs/legal for details.

===========================================================================
*/

#ifndef __GAMEDIRPOLICY_H__
#define __GAMEDIRPOLICY_H__

// fs_game values cross network, package and host-filesystem boundaries. Keep
// them to one filename segment that has the same meaning on every supported
// host; in particular, never let a separator or Windows alias reach a path
// join performed under a trusted package root.
namespace idGameDirPolicy {

static const int MAX_SEGMENT_BYTES = 255;

inline unsigned char LowerASCII( unsigned char value ) {
	return value >= 'A' && value <= 'Z' ? static_cast<unsigned char>( value + ( 'a' - 'A' ) ) : value;
}

inline bool HasASCIIStem( const char *segment, int stemLength, const char *expected, int expectedLength ) {
	if ( stemLength != expectedLength ) {
		return false;
	}
	for ( int index = 0; index < expectedLength; ++index ) {
		if ( LowerASCII( static_cast<unsigned char>( segment[ index ] ) ) !=
			 static_cast<unsigned char>( expected[ index ] ) ) {
			return false;
		}
	}
	return true;
}

inline bool HasASCIIPrefix( const char *segment, const char *expected, int expectedLength ) {
	for ( int index = 0; index < expectedLength; ++index ) {
		if ( LowerASCII( static_cast<unsigned char>( segment[ index ] ) ) !=
			 static_cast<unsigned char>( expected[ index ] ) ) {
			return false;
		}
	}
	return true;
}

inline bool IsWindowsDeviceName( const char *segment, int segmentLength ) {
	int stemLength = 0;
	while ( stemLength < segmentLength && segment[ stemLength ] != '.' ) {
		stemLength++;
	}

	if ( HasASCIIStem( segment, stemLength, "con", 3 ) ||
		 HasASCIIStem( segment, stemLength, "prn", 3 ) ||
		 HasASCIIStem( segment, stemLength, "aux", 3 ) ||
		 HasASCIIStem( segment, stemLength, "nul", 3 ) ) {
		return true;
	}

	if ( stemLength < 4 ) {
		return false;
	}
	const bool portPrefix = HasASCIIPrefix( segment, "com", 3 ) || HasASCIIPrefix( segment, "lpt", 3 );
	if ( !portPrefix ) {
		return false;
	}

	const unsigned char digit = static_cast<unsigned char>( segment[ 3 ] );
	if ( stemLength == 4 ) {
		return ( digit >= '1' && digit <= '9' ) || digit == 0xB9 || digit == 0xB2 || digit == 0xB3;
	}

	return stemLength == 5 && digit == 0xC2 &&
		( static_cast<unsigned char>( segment[ 4 ] ) == 0xB9 ||
		  static_cast<unsigned char>( segment[ 4 ] ) == 0xB2 ||
		  static_cast<unsigned char>( segment[ 4 ] ) == 0xB3 );
}

inline bool IsPortableSegment( const char *segment ) {
	if ( segment == nullptr || segment[ 0 ] == '\0' ) {
		return false;
	}

	int segmentLength = 0;
	for ( const unsigned char *scan = reinterpret_cast<const unsigned char *>( segment ); *scan != '\0'; ++scan ) {
		if ( ++segmentLength > MAX_SEGMENT_BYTES || *scan < 32 || *scan == '/' || *scan == '\\' ||
			 *scan == ':' || *scan == '<' || *scan == '>' || *scan == '"' || *scan == '|' ||
			 *scan == '?' || *scan == '*' ) {
			return false;
		}
	}

	if ( ( segmentLength == 1 && segment[ 0 ] == '.' ) ||
		 ( segmentLength == 2 && segment[ 0 ] == '.' && segment[ 1 ] == '.' ) ||
		 segment[ 0 ] == ' ' || segment[ segmentLength - 1 ] == '.' ||
		 segment[ segmentLength - 1 ] == ' ' ) {
		return false;
	}

	return !IsWindowsDeviceName( segment, segmentLength );
}

} // namespace idGameDirPolicy

#endif /* !__GAMEDIRPOLICY_H__ */
