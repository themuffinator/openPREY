/*
===========================================================================

openQ4 ARB colour zero floor native tests

Copyright (C) 2026 DarkMatter Productions
SPDX-License-Identifier: GPL-3.0-or-later

Drives src/renderer/ARBColorZeroFloor.h, the rewrite R_LoadARBProgram applies
to the light interaction fragment programs. A small evaluator for the ARB
instructions those programs use runs each program before and after the
rewrite, so the tests check what the rewrite computes rather than how it
reads: a light behind the surface writes negative colour before it and zero
after it, and every other value comes through unchanged.

===========================================================================
*/

#include "src/renderer/ARBColorZeroFloor.h"

#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
#include <vector>

namespace floor0 = oq4arbfloor;

static int failures = 0;

static void Expect( const bool condition, const std::string &label ) {
	if ( !condition ) {
		std::fprintf( stderr, "ARB colour zero floor failed: %s\n", label.c_str() );
		failures++;
	}
}

/*
===============================================================================

	Evaluator for the ARB fragment program subset the tests use: TEMP, PARAM
	constants, OPTION, and MOV ADD SUB MUL MAD MAX MIN DP3 DP4 RSQ TEX TXP, with
	_SAT, swizzles, negation, write masks and scalar constants. Temporaries
	start as NaN, so reading a component nothing wrote shows up in the result.

===============================================================================
*/

struct Vec4 {
	float v[4];
};

static Vec4 MakeVec4( float x, float y, float z, float w ) {
	Vec4 result = { { x, y, z, w } };
	return result;
}

struct FragmentInputs {
	Vec4 texcoord[8];
	Vec4 color;
	Vec4 env[4];
	Vec4 texture[8];	// what every fetch from each unit returns
};

struct FragmentOutput {
	Vec4 color;
	bool written[4];
	bool ok;
};

static std::string Trim( const std::string &text ) {
	std::size_t first = 0;
	std::size_t last = text.size();
	while ( first < last && std::strchr( " \t\r\n", text[first] ) != nullptr ) {
		++first;
	}
	while ( last > first && std::strchr( " \t\r\n", text[last - 1] ) != nullptr ) {
		--last;
	}
	return text.substr( first, last - first );
}

static std::vector<std::string> Split( const std::string &text, char separator ) {
	std::vector<std::string> parts;
	std::string current;
	for ( char c : text ) {
		if ( c == separator ) {
			parts.push_back( Trim( current ) );
			current.clear();
		} else {
			current += c;
		}
	}
	parts.push_back( Trim( current ) );
	return parts;
}

static int ComponentIndex( char c ) {
	switch ( c ) {
	case 'x': case 'r': return 0;
	case 'y': case 'g': return 1;
	case 'z': case 'b': return 2;
	case 'w': case 'a': return 3;
	default: return -1;
	}
}

class Evaluator {
public:
	FragmentOutput Run( const std::string &program, const FragmentInputs &inputs ) {
		in = inputs;
		temps.clear();
		params.clear();
		out.color = MakeVec4( NAN, NAN, NAN, NAN );
		for ( bool &written : out.written ) {
			written = false;
		}
		out.ok = true;

		if ( program.compare( 0, 10, "!!ARBfp1.0" ) != 0 ) {
			return Fail( "missing !!ARBfp1.0 header" );
		}
		std::string body;
		bool comment = false;
		for ( std::size_t i = 10; i < program.size(); ++i ) {
			const char c = program[i];
			if ( c == '#' ) {
				comment = true;
			} else if ( c == '\n' ) {
				comment = false;
			}
			if ( !comment ) {
				body += c;
			}
		}
		const std::vector<std::string> statements = Split( body, ';' );
		if ( statements.empty() || statements.back() != "END" ) {
			return Fail( "program does not end with END" );
		}
		for ( std::size_t i = 0; i + 1 < statements.size() && out.ok; ++i ) {
			Execute( statements[i] );
		}
		return out;
	}

private:
	FragmentInputs in;
	std::map<std::string, Vec4> temps;
	std::map<std::string, Vec4> params;
	FragmentOutput out;

	FragmentOutput Fail( const std::string &why ) {
		std::fprintf( stderr, "evaluator: %s\n", why.c_str() );
		out.ok = false;
		return out;
	}

	void Execute( const std::string &statement ) {
		std::size_t split = 0;
		while ( split < statement.size() && std::strchr( " \t\r\n", statement[split] ) == nullptr ) {
			++split;
		}
		std::string opcode = statement.substr( 0, split );
		const std::string rest = Trim( statement.substr( split ) );

		if ( opcode == "OPTION" ) {
			return;
		}
		if ( opcode == "TEMP" ) {
			for ( const std::string &name : Split( rest, ',' ) ) {
				if ( temps.count( name ) != 0 ) {
					Fail( "temporary declared twice: " + name );
					return;
				}
				temps[name] = MakeVec4( NAN, NAN, NAN, NAN );
			}
			return;
		}
		if ( opcode == "PARAM" ) {
			// name = { a, b, c, d }
			const std::size_t equals = rest.find( '=' );
			const std::size_t open = rest.find( '{' );
			const std::size_t close = rest.find( '}' );
			if ( equals == std::string::npos || open == std::string::npos || close == std::string::npos ) {
				Fail( "unsupported PARAM: " + rest );
				return;
			}
			Vec4 value = MakeVec4( 0.0f, 0.0f, 0.0f, 1.0f );
			const std::vector<std::string> items = Split( rest.substr( open + 1, close - open - 1 ), ',' );
			for ( std::size_t i = 0; i < items.size() && i < 4; ++i ) {
				value.v[i] = std::strtof( items[i].c_str(), nullptr );
			}
			params[Trim( rest.substr( 0, equals ) )] = value;
			return;
		}

		bool saturate = false;
		if ( opcode.size() > 4 && opcode.compare( opcode.size() - 4, 4, "_SAT" ) == 0 ) {
			saturate = true;
			opcode.resize( opcode.size() - 4 );
		}
		const std::vector<std::string> operands = Split( rest, ',' );
		if ( operands.size() < 2 ) {
			Fail( "instruction without sources: " + statement );
			return;
		}
		std::vector<Vec4> sources;
		const bool fetch = opcode == "TEX" || opcode == "TXP";
		if ( fetch ) {
			// TEX dst, coord, texture[n], 2D: the tests only need the unit.
			const std::string &unit = operands.size() > 2 ? operands[2] : std::string();
			if ( unit.compare( 0, 8, "texture[" ) != 0 ) {
				Fail( "unsupported texture operand: " + statement );
				return;
			}
			sources.push_back( in.texture[std::atoi( unit.c_str() + 8 ) & 7] );
		} else {
			for ( std::size_t i = 1; i < operands.size(); ++i ) {
				Vec4 value;
				if ( !Source( operands[i], value ) ) {
					Fail( "unsupported source: " + operands[i] );
					return;
				}
				sources.push_back( value );
			}
		}

		Vec4 result;
		if ( !Compute( opcode, sources, result ) ) {
			Fail( "unsupported instruction: " + statement );
			return;
		}
		if ( saturate ) {
			for ( float &component : result.v ) {
				component = component < 0.0f ? 0.0f : ( component > 1.0f ? 1.0f : component );
			}
		}
		Write( operands[0], result );
	}

	static bool Compute( const std::string &opcode, const std::vector<Vec4> &s, Vec4 &r ) {
		const std::size_t count = s.size();
		for ( int i = 0; i < 4; ++i ) {
			if ( opcode == "MOV" && count == 1 ) {
				r.v[i] = s[0].v[i];
			} else if ( ( opcode == "TEX" || opcode == "TXP" ) && count == 1 ) {
				r.v[i] = s[0].v[i];
			} else if ( opcode == "ADD" && count == 2 ) {
				r.v[i] = s[0].v[i] + s[1].v[i];
			} else if ( opcode == "SUB" && count == 2 ) {
				r.v[i] = s[0].v[i] - s[1].v[i];
			} else if ( opcode == "MUL" && count == 2 ) {
				r.v[i] = s[0].v[i] * s[1].v[i];
			} else if ( opcode == "MAD" && count == 3 ) {
				r.v[i] = s[0].v[i] * s[1].v[i] + s[2].v[i];
			} else if ( opcode == "MAX" && count == 2 ) {
				r.v[i] = s[0].v[i] > s[1].v[i] ? s[0].v[i] : s[1].v[i];
			} else if ( opcode == "MIN" && count == 2 ) {
				r.v[i] = s[0].v[i] < s[1].v[i] ? s[0].v[i] : s[1].v[i];
			} else if ( opcode == "DP3" && count == 2 ) {
				r.v[i] = s[0].v[0] * s[1].v[0] + s[0].v[1] * s[1].v[1] + s[0].v[2] * s[1].v[2];
			} else if ( opcode == "DP4" && count == 2 ) {
				r.v[i] = s[0].v[0] * s[1].v[0] + s[0].v[1] * s[1].v[1] + s[0].v[2] * s[1].v[2] + s[0].v[3] * s[1].v[3];
			} else if ( opcode == "RSQ" && count == 1 ) {
				r.v[i] = 1.0f / std::sqrt( std::fabs( s[0].v[0] ) );
			} else {
				return false;
			}
		}
		return true;
	}

	bool Source( const std::string &operand, Vec4 &value ) {
		std::string text = operand;
		bool negate = false;
		if ( !text.empty() && ( text[0] == '-' || text[0] == '+' ) ) {
			negate = text[0] == '-';
			text = Trim( text.substr( 1 ) );
		}
		if ( !text.empty() && ( std::isdigit( static_cast<unsigned char>( text[0] ) ) || text[0] == '.' ) ) {
			const float scalar = std::strtof( text.c_str(), nullptr );
			value = MakeVec4( scalar, scalar, scalar, scalar );
		} else {
			// Split a trailing swizzle off the register name.
			std::string name = text;
			std::string swizzle;
			const std::size_t bracket = text.rfind( ']' );
			const std::size_t dot = text.rfind( '.' );
			if ( dot != std::string::npos && ( bracket == std::string::npos || dot > bracket ) ) {
				const std::string tail = text.substr( dot + 1 );
				bool isSwizzle = !tail.empty() && tail.size() <= 4;
				for ( char c : tail ) {
					isSwizzle = isSwizzle && ComponentIndex( c ) >= 0;
				}
				if ( isSwizzle ) {
					name = text.substr( 0, dot );
					swizzle = tail;
				}
			}
			if ( !Register( name, value ) ) {
				return false;
			}
			if ( swizzle.size() == 1 ) {
				const float scalar = value.v[ComponentIndex( swizzle[0] )];
				value = MakeVec4( scalar, scalar, scalar, scalar );
			} else if ( swizzle.size() == 4 ) {
				const Vec4 unswizzled = value;
				for ( int i = 0; i < 4; ++i ) {
					value.v[i] = unswizzled.v[ComponentIndex( swizzle[i] )];
				}
			} else if ( !swizzle.empty() ) {
				return false;
			}
		}
		if ( negate ) {
			for ( float &component : value.v ) {
				component = -component;
			}
		}
		return true;
	}

	bool Register( const std::string &name, Vec4 &value ) {
		if ( temps.count( name ) != 0 ) {
			value = temps[name];
			return true;
		}
		if ( params.count( name ) != 0 ) {
			value = params[name];
			return true;
		}
		if ( name == "fragment.color" ) {
			value = in.color;
			return true;
		}
		if ( name.compare( 0, 18, "fragment.texcoord[" ) == 0 ) {
			value = in.texcoord[std::atoi( name.c_str() + 18 ) & 7];
			return true;
		}
		if ( name.compare( 0, 12, "program.env[" ) == 0 ) {
			value = in.env[std::atoi( name.c_str() + 12 ) & 3];
			return true;
		}
		return false;
	}

	void Write( const std::string &destination, const Vec4 &value ) {
		std::string name = destination;
		std::string mask = "xyzw";
		const std::size_t dot = destination.rfind( '.' );
		if ( dot != std::string::npos && destination.compare( 0, dot, "result" ) != 0 ) {
			name = destination.substr( 0, dot );
			mask = destination.substr( dot + 1 );
		}
		Vec4 *target = nullptr;
		if ( name == "result.color" ) {
			target = &out.color;
		} else if ( temps.count( name ) != 0 ) {
			target = &temps[name];
		} else {
			Fail( "unknown destination: " + destination );
			return;
		}
		for ( char c : mask ) {
			const int index = ComponentIndex( c );
			if ( index < 0 ) {
				Fail( "bad write mask: " + destination );
				return;
			}
			target->v[index] = value.v[index];
			if ( target == &out.color ) {
				out.written[index] = true;
			}
		}
	}
};

/*
===============================================================================

	Helpers

===============================================================================
*/

static floor0::rewriteResult_t Rewrite( const char *program, std::string &rewritten ) {
	const std::size_t size = floor0::RewriteBufferSize( program );
	std::vector<char> out( size + 16, '@' );
	const floor0::rewriteResult_t result = floor0::RewriteWithZeroFloor( program, out.data(), size );
	bool sentinelIntact = true;
	for ( std::size_t i = size; i < out.size(); ++i ) {
		sentinelIntact = sentinelIntact && out[i] == '@';
	}
	Expect( sentinelIntact, "the rewrite stays inside the buffer RewriteBufferSize asked for" );
	rewritten = out.data();
	if ( result != floor0::REWRITE_DONE ) {
		Expect( rewritten.empty(), "a program that is not rewritten leaves the output empty" );
	}
	return result;
}

static std::size_t Count( const std::string &text, const std::string &needle ) {
	std::size_t count = 0;
	for ( std::size_t at = text.find( needle ); at != std::string::npos; at = text.find( needle, at + needle.size() ) ) {
		++count;
	}
	return count;
}

static bool Near( float a, float b ) {
	return std::fabs( a - b ) <= 1.0e-5f;
}

static std::string Label( const char *what, int component ) {
	return std::string( what ) + " (component " + std::to_string( component ) + ")";
}

// A flat normal map texel: (0.5, 0.5, 1) decodes to (0, 0, 1).
static FragmentInputs LitSurface( float lightZ ) {
	FragmentInputs inputs;
	std::memset( &inputs, 0, sizeof( inputs ) );
	inputs.texcoord[0] = MakeVec4( 0.0f, 0.0f, lightZ, 1.0f );	// tangent-space light vector
	inputs.color = MakeVec4( 1.0f, 1.0f, 1.0f, 1.0f );
	inputs.env[0] = MakeVec4( 1.06f, 2.0f, 1.04f, 1.0f );		// a green light at r_lightScale 2
	inputs.env[1] = MakeVec4( 0.0f, 0.0f, 0.0f, 0.0f );
	inputs.texture[1] = MakeVec4( 0.5f, 0.5f, 1.0f, 1.0f );
	inputs.texture[4] = MakeVec4( 0.08f, 0.25f, 0.08f, 1.0f );	// fluid01_green's average
	inputs.texture[5] = MakeVec4( 0.2f, 0.2f, 0.2f, 1.0f );
	return inputs;
}

// Shaped like the stock interaction programs: the Lambert term is never
// saturated, and only xyz of result.color is written.
static const char *const INTERACTION_SHAPED =
	"!!ARBfp1.0\n"
	"OPTION ARB_precision_hint_fastest;\n"
	"\n"
	"# texture 1 is the bump map; result.color is written once; at the end\n"
	"TEMP\tlight, color, normal;\n"
	"PARAM\tscaleTwo = { 2, 2, 2, 2 };\n"
	"\n"
	"TEX\tnormal, fragment.texcoord[1], texture[1], 2D;\n"
	"MAD\tnormal.xyz, normal, scaleTwo, -1.0;\n"
	"DP3\tlight.w, fragment.texcoord[0], normal;\n"
	"TEX\tcolor, fragment.texcoord[4], texture[4], 2D;\n"
	"MUL\tcolor.xyz, color, program.env[0];\n"
	"MUL\tcolor.xyz, color, light.w;\n"
	"\n"
	"# modify by the vertex color\n"
	"MUL result.color.xyz, color, fragment.color;\n"
	"\n"
	"END\n";

/*
===============================================================================

	Tests

===============================================================================
*/

static void TestLightBehindSurfaceAddsNothing() {
	std::string rewritten;
	Expect( Rewrite( INTERACTION_SHAPED, rewritten ) == floor0::REWRITE_DONE, "an interaction-shaped program is rewritten" );

	Evaluator evaluator;
	const FragmentInputs facing = LitSurface( 1.0f );
	const FragmentInputs behind = LitSurface( -1.0f );
	const FragmentOutput facingBefore = evaluator.Run( INTERACTION_SHAPED, facing );
	const FragmentOutput facingAfter = evaluator.Run( rewritten, facing );
	const FragmentOutput behindBefore = evaluator.Run( INTERACTION_SHAPED, behind );
	const FragmentOutput behindAfter = evaluator.Run( rewritten, behind );
	Expect( facingBefore.ok && facingAfter.ok && behindBefore.ok && behindAfter.ok, "every run evaluates" );

	for ( int i = 0; i < 3; ++i ) {
		Expect( behindBefore.color.v[i] < 0.0f, Label( "unclamped, a light behind the surface writes negative colour", i ) );
		Expect( behindAfter.written[i] && behindAfter.color.v[i] == 0.0f, Label( "after the rewrite it writes zero", i ) );
		Expect( facingAfter.written[i] && Near( facingAfter.color.v[i], facingBefore.color.v[i] ), Label( "a facing light is unchanged", i ) );
	}
	// 0.25 green texel times 2.0 green light: HDR headroom must survive.
	Expect( Near( facingAfter.color.v[1], 0.5f ), "the facing green channel keeps its value" );
	Expect( !facingBefore.written[3] && !facingAfter.written[3] && !behindAfter.written[3],
		"alpha stays unwritten, as the shipped program leaves it" );
}

static void TestHDRHeadroomSurvives() {
	std::string rewritten;
	Rewrite( INTERACTION_SHAPED, rewritten );
	FragmentInputs bright = LitSurface( 1.0f );
	bright.texture[4] = MakeVec4( 0.9f, 0.9f, 0.9f, 1.0f );
	Evaluator evaluator;
	const FragmentOutput output = evaluator.Run( rewritten, bright );
	Expect( output.ok && output.color.v[1] > 1.0f, "colour above 1 is not clamped: only the lower bound is restored" );
}

static void TestRewriteShape() {
	std::string rewritten;
	Rewrite( INTERACTION_SHAPED, rewritten );
	const std::string temp = floor0::TEMP_NAME;
	const std::size_t declaration = rewritten.find( "TEMP " + temp + ";" );
	const std::size_t redirected = rewritten.find( "MUL " + temp + ".xyz, color, fragment.color;" );
	const std::size_t floored = rewritten.find( "MAX result.color.xyz, " + temp + ", 0.0;" );
	Expect( declaration != std::string::npos && redirected != std::string::npos && floored != std::string::npos,
		"the write is redirected, floored and its temporary declared" );
	Expect( declaration < redirected && redirected < floored, "declaration, write and floor come in that order" );
	Expect( Count( rewritten, "TEMP " + temp ) == 1, "the temporary is declared once" );
	Expect( rewritten.find( "# texture 1 is the bump map; result.color is written once; at the end\n" ) != std::string::npos,
		"comments are copied, even ones naming result.color or holding ';'" );
	Expect( rewritten.size() >= 4 && rewritten.compare( rewritten.size() - 4, 4, "END\n" ) == 0, "the program still ends with END" );
	Expect( rewritten.compare( 0, 11, "!!ARBfp1.0\n" ) == 0, "the header is kept" );
}

static void TestFullWriteAndTwoWrites() {
	// test.vfp writes all of result.color at once.
	const char *const fullWrite =
		"!!ARBfp1.0\r\n"
		"TEMP color;\r\n"
		"MUL color, fragment.texcoord[0], program.env[0];\r\n"
		"MUL_SAT result.color, color, fragment.color;\r\n"
		"END\r\n";
	std::string rewritten;
	Expect( Rewrite( fullWrite, rewritten ) == floor0::REWRITE_DONE, "a full-mask write is rewritten" );
	Expect( rewritten.find( std::string( "MAX result.color, " ) + floor0::TEMP_NAME + ", 0.0;" ) != std::string::npos,
		"a full-mask write is floored on every component" );
	FragmentInputs inputs = LitSurface( 1.0f );
	inputs.texcoord[0] = MakeVec4( -1.0f, 0.5f, 2.0f, -3.0f );
	Evaluator evaluator;
	const FragmentOutput before = evaluator.Run( fullWrite, inputs );
	const FragmentOutput after = evaluator.Run( rewritten, inputs );
	for ( int i = 0; i < 4; ++i ) {
		Expect( before.ok && after.ok && after.written[i] && Near( after.color.v[i], before.color.v[i] ),
			Label( "an already saturated write is unchanged", i ) );
	}

	// Colour and alpha written by separate instructions.
	const char *const twoWrites =
		"!!ARBfp1.0\n"
		"TEMP a;\n"
		"MUL a, fragment.texcoord[0], program.env[0];\n"
		"MOV result.color.rgb, a;\n"
		"MOV result.color.a, -2.0;\n"
		"END";
	Expect( Rewrite( twoWrites, rewritten ) == floor0::REWRITE_DONE, "two colour writes are rewritten" );
	Expect( Count( rewritten, std::string( "TEMP " ) + floor0::TEMP_NAME ) == 1, "two writes share one temporary" );
	Expect( Count( rewritten, "MAX result.color" ) == 2, "each write gets its own floor" );
	const FragmentOutput split = evaluator.Run( rewritten, inputs );
	Expect( split.ok && split.color.v[0] == 0.0f && Near( split.color.v[1], 1.0f ) && Near( split.color.v[2], 2.08f ),
		"rgb is floored per component" );
	Expect( split.color.v[3] == 0.0f && split.written[3], "alpha is floored too" );
}

static void TestTextureWriteAndComments() {
	const char *const program =
		"!!ARBfp1.0 OPTION ARB_precision_hint_nicest;\n"
		"TEX result.color.xyz, # the sample; straight out\n"
		"    fragment.texcoord[0], texture[4], 2D;\n"
		"END";
	std::string rewritten;
	Expect( Rewrite( program, rewritten ) == floor0::REWRITE_DONE, "a texture fetch into result.color is rewritten" );
	Evaluator evaluator;
	const FragmentOutput output = evaluator.Run( rewritten, LitSurface( 1.0f ) );
	Expect( output.ok && Near( output.color.v[1], 0.25f ), "a comment inside an instruction does not split it" );
}

static void TestLeftAlone() {
	std::string rewritten;
	Expect( Rewrite( "!!ARBfp1.0\nOUTPUT oColor = result.color;\nMOV oColor, fragment.color;\nEND", rewritten )
		== floor0::REWRITE_UNSUPPORTED, "an OUTPUT alias of result.color is left alone" );
	Expect( Rewrite( "!!ARBfp1.0\nOUTPUT oDepth = result.depth;\nMOV oDepth.z, fragment.color;\nMOV result.color, fragment.color;\nEND", rewritten )
		== floor0::REWRITE_DONE, "an OUTPUT of depth does not block the colour floor" );
	Expect( Rewrite( "!!ARBfp1.0\nOPTION ARB_draw_buffers;\nMOV result.color[1], fragment.color;\nEND", rewritten )
		== floor0::REWRITE_UNSUPPORTED, "an indexed colour output is left alone" );
	Expect( Rewrite( "!!ARBfp1.0\nMOV result.color.xx, fragment.color;\nEND", rewritten )
		== floor0::REWRITE_UNSUPPORTED, "a malformed write mask is left alone" );
	Expect( Rewrite( "!!ARBfp1.0\nOPTION NV_fragment_program;\nMOV result.color (GT.x), fragment.color;\nEND", rewritten )
		== floor0::REWRITE_UNSUPPORTED, "a condition-coded write is left alone" );
	Expect( Rewrite( "!!ARBfp1.0\nMOV result.depth.z, fragment.color;\nEND", rewritten )
		== floor0::REWRITE_NO_COLOR_WRITE, "a program without a colour write needs nothing" );
	Expect( Rewrite( ( std::string( "!!ARBfp1.0\nTEMP " ) + floor0::TEMP_NAME + ";\nMOV result.color, fragment.color;\nEND" ).c_str(), rewritten )
		== floor0::REWRITE_UNSUPPORTED, "a program already using the temporary's name is left alone" );
	Expect( Rewrite( "!!ARBvp1.0\nMOV result.color, vertex.color;\nEND", rewritten )
		== floor0::REWRITE_UNSUPPORTED, "a vertex program is left alone" );
	Expect( Rewrite( nullptr, rewritten ) == floor0::REWRITE_UNSUPPORTED, "no program is left alone" );
}

static void TestBufferLimits() {
	char small[32];
	std::memset( small, '@', sizeof( small ) );
	Expect( floor0::RewriteWithZeroFloor( INTERACTION_SHAPED, small, sizeof( small ) ) == floor0::REWRITE_NO_ROOM,
		"a buffer that is too small is refused" );
	Expect( small[0] == '\0', "a refused rewrite leaves the buffer empty" );
	Expect( floor0::RewriteWithZeroFloor( INTERACTION_SHAPED, nullptr, 64 ) == floor0::REWRITE_NO_ROOM, "no buffer is refused" );

	// Many writes, each needing the longest growth, still fit the estimate.
	std::string many = "!!ARBfp1.0\n";
	for ( int i = 0; i < 40; ++i ) {
		many += "MOV result.color.xyzw,fragment.color;";
	}
	many += "END";
	std::string rewritten;
	Expect( Rewrite( many.c_str(), rewritten ) == floor0::REWRITE_DONE, "forty writes fit RewriteBufferSize" );
	Expect( Count( rewritten, "MAX result.color.xyzw" ) == 40, "every one of forty writes is floored" );
}

int main() {
	TestLightBehindSurfaceAddsNothing();
	TestHDRHeadroomSurvives();
	TestRewriteShape();
	TestFullWriteAndTwoWrites();
	TestTextureWriteAndComments();
	TestLeftAlone();
	TestBufferLimits();

	if ( failures != 0 ) {
		std::fprintf( stderr, "ARB colour zero floor: %d failure(s)\n", failures );
		return 1;
	}
	std::printf( "ARB colour zero floor: back-lit interactions add nothing, HDR headroom kept, unsupported programs left alone\n" );
	return 0;
}
