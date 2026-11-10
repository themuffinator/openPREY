// Copyright (C) 2026 DarkMatter Productions
// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef __ARB_COLOR_ZERO_FLOOR_H__
#define __ARB_COLOR_ZERO_FLOOR_H__

#include <cstddef>
#include <cstring>

/*
===============================================================================

	Zero floor for ARB fragment program colour.

	Retail Quake 4 drew into an RGBA8 framebuffer, which clamps every fragment
	colour to [0,1], and the stock light interaction programs depend on that:
	interaction.vfp, SimpleInteraction.vfp and test.vfp never saturate N.L, so a
	light behind the surface writes a negative colour that the fixed-point buffer
	turns into zero. openQ4 draws the view into an RGBA16F target whenever a post
	effect is on (SSAO, bloom, tone mapping, TAA and the rest). A float target
	keeps the sign, and the additive interaction blend then subtracts that light
	instead of adding nothing. noShadows surfaces show it worst, because their
	light-backfacing triangles are lit on purpose: q4xctf6's green cryo liquid
	came out magenta, the background with the green light taken away.

	RewriteWithZeroFloor sends each result.color write through a temporary and
	writes MAX( temporary, 0.0 ) straight after it. That restores the lower bound
	of the old clamp and nothing else, so values above 1 still reach the HDR
	target, and on an RGBA8 target the output does not change.

	It uses no idlib types, so tools/tests/native/ARBColorZeroFloorTest.cpp
	drives this same code.

===============================================================================
*/

namespace oq4arbfloor {

// Every colour write is redirected through this temporary.
inline constexpr char TEMP_NAME[] = "oq4ColorBeforeZeroFloor";

enum rewriteResult_t {
	REWRITE_DONE,			// out holds the rewritten program
	REWRITE_NO_COLOR_WRITE,	// the program never writes result.color
	REWRITE_UNSUPPORTED,	// a colour write this rewrite cannot follow
	REWRITE_NO_ROOM			// out is smaller than RewriteBufferSize() asked for
};

namespace detail {

inline constexpr char RESULT_COLOR[] = "result.color";
inline constexpr std::size_t RESULT_COLOR_LENGTH = sizeof( RESULT_COLOR ) - 1;

inline bool IsSpace( char c ) {
	return c == ' ' || c == '\t' || c == '\r' || c == '\n' || c == '\f' || c == '\v';
}

inline bool IsIdentifierChar( char c ) {
	return ( c >= 'a' && c <= 'z' ) || ( c >= 'A' && c <= 'Z' ) || ( c >= '0' && c <= '9' ) || c == '_';
}

// idlib's Str.h turns strncmp into a compile error inside the engine.
inline bool StartsWith( const char *text, const char *prefix ) {
	for ( ; *prefix != '\0'; ++text, ++prefix ) {
		if ( *text != *prefix ) {
			return false;
		}
	}
	return true;
}

// Skips whitespace and '#' comments, which run to the end of the line.
inline const char *SkipBlank( const char *p ) {
	for ( ;; ) {
		while ( IsSpace( *p ) ) {
			++p;
		}
		if ( *p != '#' ) {
			return p;
		}
		while ( *p != '\0' && *p != '\n' ) {
			++p;
		}
	}
}

// The ';' ending the statement that starts at p, or nullptr once only END is
// left. A comment can hold a ';' without ending anything.
inline const char *StatementEnd( const char *p ) {
	for ( ; *p != '\0'; ++p ) {
		if ( *p == '#' ) {
			while ( p[1] != '\0' && p[1] != '\n' ) {
				++p;
			}
		} else if ( *p == ';' ) {
			return p;
		}
	}
	return nullptr;
}

// An empty mask writes all four components; otherwise one to four of xyzw, or
// of rgba, in order, as the ARB grammar spells a destination mask.
inline bool IsWriteMask( const char *suffix ) {
	if ( suffix[0] == '\0' ) {
		return true;
	}
	if ( suffix[0] != '.' || suffix[1] == '\0' ) {
		return false;
	}
	static const char *const componentSets[2] = { "xyzw", "rgba" };
	for ( const char *components : componentSets ) {
		int previous = -1;
		const char *scan = suffix + 1;
		for ( ; *scan != '\0'; ++scan ) {
			const char *found = std::strchr( components, *scan );
			if ( found == nullptr || static_cast<int>( found - components ) <= previous ) {
				break;
			}
			previous = static_cast<int>( found - components );
		}
		if ( *scan == '\0' ) {
			return true;
		}
	}
	return false;
}

// True when [p, end) mentions result.color outside a comment.
inline bool MentionsColor( const char *p, const char *end ) {
	while ( p < end ) {
		if ( *p == '#' ) {
			while ( p < end && *p != '\n' ) {
				++p;
			}
			continue;
		}
		if ( static_cast<std::size_t>( end - p ) >= RESULT_COLOR_LENGTH && StartsWith( p, RESULT_COLOR ) ) {
			return true;
		}
		++p;
	}
	return false;
}

class Writer {
public:
	Writer( char *target, std::size_t targetSize ) : out( target ), outSize( targetSize ) {}

	void Append( const char *text, std::size_t length ) {
		if ( overflowed || length >= outSize - used ) {
			overflowed = true;
			return;
		}
		std::memcpy( out + used, text, length );
		used += length;
		out[used] = '\0';
	}

	void Append( const char *text ) {
		Append( text, std::strlen( text ) );
	}

	bool Overflowed( void ) const {
		return overflowed;
	}

private:
	char *out;
	std::size_t outSize;
	std::size_t used = 0;
	bool overflowed = false;
};

} // namespace detail

/*
====================
RewriteBufferSize

Bytes RewriteWithZeroFloor may need for this program, terminator included.
Every mention of result.color counts as a write, which only overestimates.
====================
*/
inline std::size_t RewriteBufferSize( const char *program ) {
	if ( program == nullptr ) {
		return 1;
	}
	std::size_t mentions = 0;
	for ( const char *scan = std::strstr( program, detail::RESULT_COLOR ); scan != nullptr;
		scan = std::strstr( scan + detail::RESULT_COLOR_LENGTH, detail::RESULT_COLOR ) ) {
		++mentions;
	}
	// A write grows by the longer destination and one MAX statement, and the
	// first also declares the temporary.
	const std::size_t perWrite = 2 * sizeof( TEMP_NAME ) + 48;
	return std::strlen( program ) + ( mentions + 1 ) * perWrite + 1;
}

/*
====================
RewriteWithZeroFloor

program is one fragment program, "!!ARBfp1.0" through END. On REWRITE_DONE, out
holds it with every "OP result.color<mask>, ..." turned into

	OP <TEMP_NAME><mask>, ...;
	MAX result.color<mask>, <TEMP_NAME>, 0.0;

and the temporary declared just before its first use. Anything else leaves out
empty, and the caller submits the program unchanged. That covers colour it
cannot follow: an OUTPUT binding of result.color, an indexed result.color[n]
from ARB_draw_buffers, a destination that is not a plain write mask (an NV
condition code, say), and a program that already uses TEMP_NAME.
====================
*/
inline rewriteResult_t RewriteWithZeroFloor( const char *program, char *out, std::size_t outSize ) {
	if ( out == nullptr || outSize == 0 ) {
		return REWRITE_NO_ROOM;
	}
	out[0] = '\0';
	if ( program == nullptr || !detail::StartsWith( program, "!!ARBfp" ) ) {
		return REWRITE_UNSUPPORTED;
	}
	if ( std::strstr( program, TEMP_NAME ) != nullptr ) {
		return REWRITE_UNSUPPORTED;
	}

	detail::Writer writer( out, outSize );

	// The "!!ARBfp1.0" header is not a statement.
	const char *p = program;
	while ( *p != '\0' && !detail::IsSpace( *p ) ) {
		++p;
	}
	writer.Append( program, static_cast<std::size_t>( p - program ) );

	int writes = 0;
	for ( const char *end = detail::StatementEnd( p ); end != nullptr; end = detail::StatementEnd( p ) ) {
		const char *opcode = detail::SkipBlank( p );
		const char *opcodeEnd = opcode;
		while ( detail::IsIdentifierChar( *opcodeEnd ) ) {
			++opcodeEnd;
		}

		if ( opcodeEnd - opcode == 6 && detail::StartsWith( opcode, "OUTPUT" ) ) {
			// An alias would carry the colour writes under another name.
			if ( detail::MentionsColor( opcodeEnd, end ) ) {
				out[0] = '\0';
				return REWRITE_UNSUPPORTED;
			}
			writer.Append( p, static_cast<std::size_t>( end + 1 - p ) );
			p = end + 1;
			continue;
		}

		// The first operand, blanks dropped: an instruction's destination.
		const char *destination = detail::SkipBlank( opcodeEnd );
		const char *destinationEnd = destination;
		char operand[64];
		std::size_t operandLength = 0;
		bool operandTruncated = false;
		while ( destinationEnd < end && *destinationEnd != ',' ) {
			if ( *destinationEnd == '#' ) {
				while ( destinationEnd < end && *destinationEnd != '\n' ) {
					++destinationEnd;
				}
				continue;
			}
			if ( !detail::IsSpace( *destinationEnd ) ) {
				if ( operandLength + 1 < sizeof( operand ) ) {
					operand[operandLength++] = *destinationEnd;
				} else {
					operandTruncated = true;
				}
			}
			++destinationEnd;
		}
		operand[operandLength] = '\0';

		if ( !detail::StartsWith( operand, detail::RESULT_COLOR ) ) {
			writer.Append( p, static_cast<std::size_t>( end + 1 - p ) );
			p = end + 1;
			continue;
		}

		const char *mask = operand + detail::RESULT_COLOR_LENGTH;
		if ( operandTruncated || !detail::IsWriteMask( mask ) ) {
			out[0] = '\0';
			return REWRITE_UNSUPPORTED;
		}

		if ( writes == 0 ) {
			writer.Append( p, static_cast<std::size_t>( opcode - p ) );
			writer.Append( "TEMP " );
			writer.Append( TEMP_NAME );
			writer.Append( ";\n" );
			writer.Append( opcode, static_cast<std::size_t>( destination - opcode ) );
		} else {
			writer.Append( p, static_cast<std::size_t>( destination - p ) );
		}
		writer.Append( TEMP_NAME );
		writer.Append( mask );
		writer.Append( destinationEnd, static_cast<std::size_t>( end - destinationEnd ) );
		writer.Append( ";\nMAX " );
		writer.Append( detail::RESULT_COLOR );
		writer.Append( mask );
		writer.Append( ", " );
		writer.Append( TEMP_NAME );
		writer.Append( ", 0.0;" );
		++writes;
		p = end + 1;
	}
	writer.Append( p );

	if ( writer.Overflowed() ) {
		out[0] = '\0';
		return REWRITE_NO_ROOM;
	}
	if ( writes == 0 ) {
		out[0] = '\0';
		return REWRITE_NO_COLOR_WRITE;
	}
	return REWRITE_DONE;
}

} // namespace oq4arbfloor

#endif /* !__ARB_COLOR_ZERO_FLOOR_H__ */
