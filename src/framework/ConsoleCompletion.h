// Copyright (C) 2026 DarkMatter Productions
// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef __CONSOLE_COMPLETION_H__
#define __CONSOLE_COMPLETION_H__

#include <cstddef>
#include <cstring>

/*
===============================================================================

	Console completion matching.

	Argument completion offers whole command lines, such as "com_maxfps 120",
	and the console popup keeps the argument under the cursor from each. These
	rules decide which lines survive the typed text, how the popup stores the
	survivors, and when a token that matched nothing may be offered typo
	suggestions instead. They use no idlib types, so
	tools/tests/native/ConsoleCompletionTest.cpp drives this same code with the
	candidate streams the engine produces.

===============================================================================
*/

namespace oq4completion {

// Prefix matches the popup keeps. Candidates reach the popup only after the
// typed text has narrowed them, so the cap bites only on huge argument domains
// such as <0,60000>. It is sized so a whole name family still lists every
// member: r_ alone is ~480 names, and tools/tests/console_completion_contract.py
// fails when it outgrows the cap.
constexpr int MAX_MATCHES = 1024;

// Fuzzy suggestions are ranked best first, so a short list is enough.
constexpr int MAX_FUZZY_MATCHES = 64;

// ASCII case folding, as idStr::Icmp and idStr::Icmpn apply it.
inline int FoldCase( int ch ) {
	ch &= 0xff;
	return ( ch >= 'A' && ch <= 'Z' ) ? ch + ( 'a' - 'A' ) : ch;
}

/*
====================
BuildArgumentLinePrefix

Writes the text every argument candidate line has to start with, given the
command segment up to the cursor with any leading '/' already removed.

Candidate lines are "<command> <value>" with one space between, so each run of
whitespace collapses to a single space. A trailing run is kept as one space
because it means the next argument has begun: "com_maxfps " keeps every value.
Everything else is copied verbatim. Re-joining lexer tokens instead would turn
"gl-module" into "gl - module", which no candidate starts with.
====================
*/
inline void BuildArgumentLinePrefix( const char *segment, char *out, std::size_t outSize ) {
	std::size_t length = 0;
	bool pendingSpace = false;

	if ( out == nullptr || outSize == 0 ) {
		return;
	}

	for ( const char *scan = ( segment != nullptr ) ? segment : ""; *scan != '\0'; ++scan ) {
		if ( static_cast<unsigned char>( *scan ) <= ' ' ) {
			pendingSpace = ( length > 0 );
			continue;
		}
		if ( length + ( pendingSpace ? 2 : 1 ) >= outSize ) {
			break;
		}
		if ( pendingSpace ) {
			out[length++] = ' ';
			pendingSpace = false;
		}
		out[length++] = *scan;
	}
	if ( pendingSpace && length + 1 < outSize ) {
		out[length++] = ' ';
	}
	out[length] = '\0';
}

// True for a token that reads as a number: an optional sign, an optional
// leading point, then a digit. "5000", "-1", ".5" and "1e3" all qualify.
inline bool LooksNumeric( const char *token ) {
	if ( token == nullptr ) {
		return false;
	}
	if ( *token == '+' || *token == '-' ) {
		++token;
	}
	if ( *token == '.' ) {
		++token;
	}
	return *token >= '0' && *token <= '9';
}

/*
====================
AllowsFuzzyFallback

Whether a token that no candidate starts with may be offered fuzzy suggestions
instead. Names may: com_maxpfs is a slip for com_maxfps, and a misspelled map
or decl argument is the same kind of slip. Numeric argument values may not:
5000 and 500 are one edit apart and a factor of ten apart, and Enter on the
popup would swap the typed value for one nobody typed.
====================
*/
inline bool AllowsFuzzyFallback( int argIndex, const char *token ) {
	if ( token == nullptr || token[0] == '\0' || token[1] == '\0' ) {
		return false;
	}
	return argIndex <= 0 || !LooksNumeric( token );
}

/*
====================
CandidateIndex

Case-insensitive de-duplication for the popup's fixed array of candidates. One
value can arrive more than once: a command and a CVar can share a name, and
different lines can share the token being completed. A linear scan per insert
made collecting a whole family such as r_ quadratic, so the index is an open
addressed table twice the capacity, which keeps each insert constant time on
average.
====================
*/
constexpr int CandidateTableSize( int capacity ) {
	int size = 1;
	while ( size < capacity * 2 ) {
		size <<= 1;
	}
	return size;
}

template<int Capacity>
class CandidateIndex {
public:
	void Clear( void ) {
		std::memset( slots, 0, sizeof( slots ) );
	}

	// Appends token to entries[count] unless an equal token is already there,
	// cutting it to Width - 1 characters. Returns false only when a new token
	// arrives with all Capacity entries in use, which tells the caller to stop
	// collecting.
	template<std::size_t Width>
	bool Add( char ( *entries )[Width], int &count, const char *token ) {
		const std::size_t length = BoundedLength( token, Width - 1 );
		unsigned int slot = Hash( token, length ) & ( TableSize - 1 );

		while ( slots[slot] != 0 ) {
			const char *entry = entries[slots[slot] - 1];
			if ( EqualPrefix( entry, token, length ) && entry[length] == '\0' ) {
				return true;
			}
			slot = ( slot + 1 ) & ( TableSize - 1 );
		}

		if ( count >= Capacity ) {
			return false;
		}

		std::memcpy( entries[count], token, length );
		entries[count][length] = '\0';
		++count;
		slots[slot] = count;
		return true;
	}

private:
	static std::size_t BoundedLength( const char *text, std::size_t limit ) {
		std::size_t length = 0;
		while ( length < limit && text[length] != '\0' ) {
			++length;
		}
		return length;
	}

	static unsigned int Hash( const char *text, std::size_t length ) {
		unsigned int hash = 2166136261u;
		for ( std::size_t i = 0; i < length; ++i ) {
			hash ^= static_cast<unsigned int>( FoldCase( text[i] ) );
			hash *= 16777619u;
		}
		return hash;
	}

	static bool EqualPrefix( const char *entry, const char *token, std::size_t length ) {
		for ( std::size_t i = 0; i < length; ++i ) {
			if ( FoldCase( entry[i] ) != FoldCase( token[i] ) ) {
				return false;
			}
		}
		return true;
	}

	static constexpr int TableSize = CandidateTableSize( Capacity );

	int slots[TableSize];	// entry index + 1, 0 for an empty slot
};

}	// namespace oq4completion

#endif /* !__CONSOLE_COMPLETION_H__ */
