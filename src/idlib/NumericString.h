/*
===============================================================================

	Small, allocation-free helpers for validating numeric strings at input
	boundaries.  These stay independent of the rest of idlib so native safety
	tests can exercise the exact production implementation.

===============================================================================
*/

#ifndef __NUMERICSTRING_H__
#define __NUMERICSTRING_H__

namespace idNumericString {

inline bool IsDecimal( const char *text ) {
	if ( text == nullptr || text[ 0 ] == '\0' ) {
		return false;
	}

	if ( text[ 0 ] == '-' ) {
		text++;
		if ( text[ 0 ] == '\0' ) {
			return false;
		}
	}

	bool sawDigit = false;
	bool sawDot = false;
	for ( ; text[ 0 ] != '\0'; text++ ) {
		if ( text[ 0 ] >= '0' && text[ 0 ] <= '9' ) {
			sawDigit = true;
			continue;
		}
		if ( text[ 0 ] == '.' && !sawDot ) {
			sawDot = true;
			continue;
		}
		return false;
	}

	return sawDigit;
}

inline bool ParseUnsignedBounded( const char *text, const int maximum, int &value ) {
	if ( text == nullptr || text[ 0 ] == '\0' || maximum < 0 ) {
		return false;
	}

	int parsed = 0;
	for ( ; text[ 0 ] != '\0'; text++ ) {
		if ( text[ 0 ] < '0' || text[ 0 ] > '9' ) {
			return false;
		}

		const int digit = text[ 0 ] - '0';
		if ( parsed > maximum / 10 ||
			 ( parsed == maximum / 10 && digit > maximum % 10 ) ) {
			return false;
		}
		parsed = parsed * 10 + digit;
	}

	value = parsed;
	return true;
}

} // namespace idNumericString

#endif /* !__NUMERICSTRING_H__ */
