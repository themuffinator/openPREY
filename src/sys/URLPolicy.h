/*
===========================================================================

openQ4 external URL validation helpers.
Copyright (C) 2026 DarkMatter Productions

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

===========================================================================
*/

#ifndef __URL_POLICY_H__
#define __URL_POLICY_H__

#include <cstddef>

namespace idURLPolicy {

// These helpers intentionally have no engine dependencies so every platform
// launcher and the native safety tests use the same fail-closed policy.

// Includes the terminating NUL. Accepted URLs therefore contain at most 4095
// bytes, matching the former macOS bound without allowing an unbounded scan.
const size_t MAX_URL_BYTES = 4096;

inline char ASCIILower( const char value ) {
	return ( value >= 'A' && value <= 'Z' ) ? static_cast<char>( value + ( 'a' - 'A' ) ) : value;
}

inline bool ASCIIStartsWith( const char *text, const char *prefix ) {
	if ( text == NULL || prefix == NULL ) {
		return false;
	}
	while ( *prefix != '\0' ) {
		if ( *text == '\0' || ASCIILower( *text ) != ASCIILower( *prefix ) ) {
			return false;
		}
		text++;
		prefix++;
	}
	return true;
}

inline bool ParsePort( const char *begin, const char *end ) {
	if ( begin == NULL || end == NULL || begin == end || end < begin ) {
		return false;
	}

	unsigned int port = 0;
	for ( const char *cursor = begin; cursor != end; cursor++ ) {
		if ( *cursor < '0' || *cursor > '9' ) {
			return false;
		}
		const unsigned int digit = static_cast<unsigned int>( *cursor - '0' );
		if ( port > 6553 || ( port == 6553 && digit > 5 ) ) {
			return false;
		}
		port = port * 10 + digit;
	}
	return true;
}

inline bool IsASCIIAlphaNumeric( const char value ) {
	return ( value >= 'a' && value <= 'z' ) || ( value >= 'A' && value <= 'Z' ) ||
		( value >= '0' && value <= '9' );
}

inline bool IsASCIIHexDigit( const char value ) {
	return ( value >= '0' && value <= '9' ) || ( value >= 'a' && value <= 'f' ) ||
		( value >= 'A' && value <= 'F' );
}

inline bool IsIPv4Literal( const char *begin, const char *end ) {
	int components = 0;
	const char *cursor = begin;
	while ( cursor != end ) {
		if ( components == 4 ) {
			return false;
		}
		unsigned int value = 0;
		int digits = 0;
		while ( cursor != end && *cursor != '.' ) {
			if ( *cursor < '0' || *cursor > '9' || digits == 3 ) {
				return false;
			}
			value = value * 10 + static_cast<unsigned int>( *cursor - '0' );
			digits++;
			cursor++;
		}
		if ( digits == 0 || value > 255 ) {
			return false;
		}
		components++;
		if ( cursor != end ) {
			cursor++;
			if ( cursor == end ) {
				return false;
			}
		}
	}
	return components == 4;
}

inline bool IsIPv6Literal( const char *begin, const char *end ) {
	if ( begin == end ) {
		return false;
	}

	int groups = 0;
	bool compressed = false;
	const char *cursor = begin;
	if ( *cursor == ':' ) {
		if ( cursor + 1 == end || cursor[ 1 ] != ':' ) {
			return false;
		}
		compressed = true;
		cursor += 2;
		if ( cursor == end ) {
			return true;
		}
	}

	while ( cursor != end ) {
		const char *groupBegin = cursor;
		bool dotted = false;
		while ( cursor != end && *cursor != ':' ) {
			dotted = dotted || *cursor == '.';
			cursor++;
		}
		if ( dotted ) {
			if ( cursor != end || !IsIPv4Literal( groupBegin, cursor ) ) {
				return false;
			}
			groups += 2;
			break;
		}
		const size_t groupLength = static_cast<size_t>( cursor - groupBegin );
		if ( groupLength == 0 || groupLength > 4 ) {
			return false;
		}
		for ( const char *digit = groupBegin; digit != cursor; digit++ ) {
			if ( !IsASCIIHexDigit( *digit ) ) {
				return false;
			}
		}
		if ( ++groups > 8 ) {
			return false;
		}
		if ( cursor == end ) {
			break;
		}
		cursor++;
		if ( cursor == end ) {
			return false;
		}
		if ( *cursor == ':' ) {
			if ( compressed ) {
				return false;
			}
			compressed = true;
			cursor++;
			if ( cursor == end ) {
				break;
			}
		}
	}
	return compressed ? groups < 8 : groups == 8;
}

inline bool IsDNSOrIPv4Host( const char *begin, const char *end ) {
	const size_t hostLength = static_cast<size_t>( end - begin );
	if ( hostLength == 0 || hostLength > 253 ) {
		return false;
	}

	bool numericAndDotsOnly = true;
	bool sawDot = false;
	const char *labelBegin = begin;
	for ( const char *cursor = begin; ; cursor++ ) {
		if ( cursor == end || *cursor == '.' ) {
			const size_t labelLength = static_cast<size_t>( cursor - labelBegin );
			if ( labelLength == 0 || labelLength > 63 ||
				 !IsASCIIAlphaNumeric( *labelBegin ) || !IsASCIIAlphaNumeric( cursor[ -1 ] ) ) {
				return false;
			}
			if ( cursor == end ) {
				break;
			}
			sawDot = true;
			labelBegin = cursor + 1;
			continue;
		}
		if ( !IsASCIIAlphaNumeric( *cursor ) && *cursor != '-' ) {
			return false;
		}
		if ( *cursor < '0' || *cursor > '9' ) {
			numericAndDotsOnly = false;
		}
	}
	return !numericAndDotsOnly || ( sawDot && IsIPv4Literal( begin, end ) );
}

inline bool AuthorityHasHost( const char *begin, const char *end ) {
	if ( begin == NULL || end == NULL || begin == end || end < begin ) {
		return false;
	}

	// User information and percent-encoded authority components create URL
	// display/parser ambiguity. Neither is needed by an engine-owned web link.
	for ( const char *cursor = begin; cursor != end; cursor++ ) {
		if ( *cursor == '@' || *cursor == '%' ) {
			return false;
		}
	}

	if ( *begin == '[' ) {
		const char *closeBracket = begin + 1;
		while ( closeBracket != end && *closeBracket != ']' ) {
			closeBracket++;
		}
		if ( closeBracket == end || !IsIPv6Literal( begin + 1, closeBracket ) ) {
			return false;
		}
		if ( closeBracket + 1 == end ) {
			return true;
		}
		return closeBracket[ 1 ] == ':' && ParsePort( closeBracket + 2, end );
	}

	const char *portSeparator = NULL;
	for ( const char *cursor = begin; cursor != end; cursor++ ) {
		if ( *cursor == '[' || *cursor == ']' ) {
			return false;
		}
		if ( *cursor == ':' ) {
			if ( portSeparator != NULL ) {
				// IPv6 literals must use brackets so the authority is unambiguous.
				return false;
			}
			portSeparator = cursor;
		}
	}

	const char *hostEnd = portSeparator != NULL ? portSeparator : end;
	if ( hostEnd == begin ) {
		return false;
	}
	if ( !IsDNSOrIPv4Host( begin, hostEnd ) ) {
		return false;
	}
	return portSeparator == NULL || ParsePort( portSeparator + 1, end );
}

inline bool IsAllowedHTTPURL( const char *url ) {
	if ( url == NULL ) {
		return false;
	}

	size_t length = 0;
	for ( ; length < MAX_URL_BYTES && url[ length ] != '\0'; length++ ) {
		const unsigned char value = static_cast<unsigned char>( url[ length ] );
		if ( value <= 32 || value == 127 || value == '"' || value == '<' || value == '>' ||
			 value == '\\' || value == '^' || value == '`' || value == '{' || value == '|' || value == '}' ) {
			return false;
		}
	}
	if ( length == 0 || length == MAX_URL_BYTES ) {
		return false;
	}

	const char *authority = NULL;
	if ( ASCIIStartsWith( url, "https://" ) ) {
		authority = url + 8;
	} else if ( ASCIIStartsWith( url, "http://" ) ) {
		authority = url + 7;
	} else {
		return false;
	}

	const char *authorityEnd = authority;
	while ( *authorityEnd != '\0' && *authorityEnd != '/' && *authorityEnd != '?' && *authorityEnd != '#' ) {
		authorityEnd++;
	}
	return AuthorityHasHost( authority, authorityEnd );
}

} // namespace idURLPolicy

#endif /* !__URL_POLICY_H__ */
