/*
===========================================================================

openQ4 console completion native tests

Copyright (C) 2026 DarkMatter Productions
SPDX-License-Identifier: GPL-3.0-or-later

Drives src/framework/ConsoleCompletion.h with the candidate streams the command
and CVar systems produce. The popup pipeline around it is modelled here:
idEditField::QueryCompletionMatches offers each candidate line that starts with
the typed prefix, idConsoleLocal::CollectCompletionMatch keeps the token being
completed, and Enter runs the line once the highlighted entry already is the
typed token. tools/tests/console_completion_contract.py pins that the engine
wires those steps to the functions tested here.

===========================================================================
*/

#include "src/framework/ConsoleCompletion.h"

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <memory>
#include <string>
#include <vector>

namespace completion = oq4completion;

static const std::size_t EDIT_LINE = 256;	// MAX_EDIT_LINE

static int failures = 0;

static void Expect( const bool condition, const std::string &label ) {
	if ( !condition ) {
		std::fprintf( stderr, "console completion failed: %s\n", label.c_str() );
		failures++;
	}
}

using Lines = std::vector<std::string>;

// idCmdSystem::ArgCompletion_Integer<min,max>: every value, ascending.
static Lines IntegerLines( const char *command, int minimum, int maximum ) {
	Lines lines;
	lines.reserve( static_cast<std::size_t>( maximum - minimum + 1 ) );
	for ( int value = minimum; value <= maximum; ++value ) {
		lines.push_back( std::string( command ) + " " + std::to_string( value ) );
	}
	return lines;
}

// ArgCompletion_String, a folder listing, or CVar names offered as arguments.
static Lines ValueLines( const char *command, const std::vector<std::string> &values ) {
	Lines lines;
	for ( const std::string &value : values ) {
		lines.push_back( std::string( command ) + " " + value );
	}
	return lines;
}

static std::string Prefix( const char *segment, std::size_t outSize = EDIT_LINE ) {
	std::vector<char> out( outSize + 1, '#' );
	completion::BuildArgumentLinePrefix( segment, out.data(), outSize );
	Expect( out[outSize] == '#', std::string( "prefix of \"" ) + ( segment ? segment : "(null)" ) + "\" stays inside its buffer" );
	return std::string( out.data() );
}

static bool HasPrefix( const std::string &text, const std::string &prefix ) {
	if ( prefix.size() > text.size() ) {
		return false;
	}
	for ( std::size_t i = 0; i < prefix.size(); ++i ) {
		if ( completion::FoldCase( text[i] ) != completion::FoldCase( prefix[i] ) ) {
			return false;
		}
	}
	return true;
}

static bool Equal( const std::string &a, const std::string &b ) {
	return a.size() == b.size() && HasPrefix( a, b );
}

static std::vector<std::string> Split( const std::string &text ) {
	std::vector<std::string> fields;
	std::string field;
	for ( const char ch : text ) {
		if ( static_cast<unsigned char>( ch ) <= ' ' ) {
			if ( !field.empty() ) {
				fields.push_back( field );
				field.clear();
			}
		} else {
			field += ch;
		}
	}
	if ( !field.empty() ) {
		fields.push_back( field );
	}
	return fields;
}

struct Popup {
	char matches[completion::MAX_MATCHES][EDIT_LINE];
	int count = 0;
	completion::CandidateIndex<completion::MAX_MATCHES> index;
};

struct Outcome {
	std::vector<std::string> shown;		// sorted, as the popup lists them
	bool popup = false;					// the list is visible
	bool enterRuns = false;				// Enter runs the typed line
	bool fuzzy = false;					// nothing matched; typo suggestions allowed
};

/*
Completes `line`, typed up to the cursor, against `producer`. `wholeToken` is
the whole token under the cursor, which differs from the typed text only when
the cursor sits inside it. Command names use the name itself as the prefix;
arguments use the whole typed line, as QueryCompletionInternal does.

Tokens split at whitespace here, where the engine uses idCmdArgs. The two agree
for the numbers, names and paths completed below; the lexer also splits at
punctuation, so hyphenated values are only checked at the prefix level.
*/
static Outcome Complete( const std::string &line, const Lines &producer, const std::string *wholeToken = nullptr ) {
	static std::unique_ptr<Popup> popup( new Popup );
	Outcome outcome;

	const std::vector<std::string> fields = Split( line );
	const bool trailingSpace = !line.empty() && static_cast<unsigned char>( line.back() ) <= ' ';
	const bool completingArguments = fields.size() > 1 || trailingSpace;
	const int argIndex = static_cast<int>( fields.size() ) - ( trailingSpace ? 0 : 1 );
	const std::string typed = trailingSpace || fields.empty() ? std::string() : fields.back();
	const std::string token = wholeToken != nullptr ? *wholeToken : typed;
	const std::string prefix = completingArguments ? Prefix( line.c_str() ) : typed;

	popup->count = 0;
	popup->index.Clear();
	for ( const std::string &candidate : producer ) {
		if ( !HasPrefix( candidate, prefix ) ) {
			continue;
		}
		const std::vector<std::string> candidateFields = Split( candidate );
		if ( argIndex >= static_cast<int>( candidateFields.size() ) ) {
			continue;
		}
		if ( !popup->index.Add( popup->matches, popup->count, candidateFields[static_cast<std::size_t>( argIndex )].c_str() ) ) {
			break;	// FindMatches stops calling back once the collector is full
		}
	}

	if ( popup->count < 1 ) {
		outcome.fuzzy = completion::AllowsFuzzyFallback( argIndex, token.c_str() );
		outcome.enterRuns = !outcome.fuzzy;
		return outcome;
	}

	for ( int i = 0; i < popup->count; ++i ) {
		outcome.shown.push_back( popup->matches[i] );
	}
	std::sort( outcome.shown.begin(), outcome.shown.end(), []( const std::string &a, const std::string &b ) {
		const std::size_t length = std::min( a.size(), b.size() );
		for ( std::size_t i = 0; i < length; ++i ) {
			const int ca = completion::FoldCase( a[i] );
			const int cb = completion::FoldCase( b[i] );
			if ( ca != cb ) {
				return ca < cb;
			}
		}
		return a.size() < b.size();
	} );

	int exact = -1;
	bool extended = false;
	for ( int i = 0; i < static_cast<int>( outcome.shown.size() ); ++i ) {
		const std::string &match = outcome.shown[static_cast<std::size_t>( i )];
		if ( Equal( match, token ) ) {
			exact = i;
		} else if ( match.size() > token.size() && HasPrefix( match, token ) ) {
			extended = true;
		}
	}

	const bool cursorAtTokenEnd = ( wholeToken == nullptr );
	const bool hidden = cursorAtTokenEnd && !token.empty() && exact >= 0 && !extended;
	const int selection = exact >= 0 ? exact : 0;
	outcome.popup = !hidden;
	outcome.enterRuns = hidden || Equal( outcome.shown[static_cast<std::size_t>( selection )], token );
	return outcome;
}

static bool AllStartWith( const Outcome &outcome, const std::string &prefix ) {
	for ( const std::string &match : outcome.shown ) {
		if ( !HasPrefix( match, prefix ) ) {
			return false;
		}
	}
	return true;
}

static bool Shows( const Outcome &outcome, const std::string &value ) {
	return std::find( outcome.shown.begin(), outcome.shown.end(), value ) != outcome.shown.end();
}

static void TestPrefixBuilder() {
	Expect( Prefix( "com_maxfps 12" ) == "com_maxfps 12", "a typed argument is kept" );
	Expect( Prefix( "com_maxfps \t  12" ) == "com_maxfps 12", "whitespace runs collapse to one space" );
	Expect( Prefix( "com_maxfps " ) == "com_maxfps ", "a started argument keeps its space" );
	Expect( Prefix( "com_maxfps    " ) == "com_maxfps ", "a trailing run keeps one space" );
	Expect( Prefix( "  com_maxfps 12  " ) == "com_maxfps 12 ", "leading whitespace is dropped" );
	Expect( Prefix( "r_renderApi gl-mod" ) == "r_renderApi gl-mod", "punctuation inside an argument is kept" );
	Expect( Prefix( "map game/air" ) == "map game/air", "paths are kept" );
	Expect( Prefix( "say caf\xc3\xa9" ) == "say caf\xc3\xa9", "UTF-8 bytes are not whitespace" );
	Expect( Prefix( "com_maxfps 12", 8 ) == "com_max", "a short buffer truncates the prefix" );
	Expect( Prefix( "com_maxfps 12", 11 ) == "com_maxfps", "truncation never leaves a dangling space" );
	Expect( Prefix( "com_maxfps 12", 1 ).empty(), "a one-byte buffer holds only the terminator" );
	Expect( Prefix( nullptr ).empty(), "a missing segment yields an empty prefix" );
}

static void TestWideIntegerDomain() {
	// com_loadingContinueAutoAdvance, ArgCompletion_Integer<0,60000>.
	const Lines lines = IntegerLines( "com_loadingContinueAutoAdvance", 0, 60000 );

	Outcome typed = Complete( "com_loadingContinueAutoAdvance 30000", lines );
	Expect( typed.shown.size() == 1 && typed.shown[0] == "30000", "a typed value outside the first 1024 is found" );
	Expect( !typed.popup && typed.enterRuns, "an exact value closes the popup and Enter runs the line" );

	// The regression: an empty prefix offered every value, the collector filled
	// with the first ones, and the typed value was never among them.
	Popup *unfiltered = new Popup;
	unfiltered->index.Clear();
	for ( const std::string &candidate : lines ) {
		if ( !unfiltered->index.Add( unfiltered->matches, unfiltered->count, Split( candidate )[1].c_str() ) ) {
			break;
		}
	}
	bool unfilteredHasValue = false;
	for ( int i = 0; i < unfiltered->count; ++i ) {
		unfilteredHasValue |= std::strcmp( unfiltered->matches[i], "30000" ) == 0;
	}
	Expect( unfiltered->count == completion::MAX_MATCHES && !unfilteredHasValue,
		"an unfiltered stream fills the cap before reaching the typed value" );
	delete unfiltered;

	Outcome digit = Complete( "com_loadingContinueAutoAdvance 3", lines );
	Expect( static_cast<int>( digit.shown.size() ) == completion::MAX_MATCHES, "a barely narrowed domain fills the cap" );
	Expect( AllStartWith( digit, "3" ), "every kept value starts with the typed digit" );
	Expect( Shows( digit, "3" ) && digit.popup && digit.enterRuns, "the typed value itself is kept and Enter still runs" );

	Outcome started = Complete( "com_loadingContinueAutoAdvance ", lines );
	Expect( static_cast<int>( started.shown.size() ) == completion::MAX_MATCHES && Shows( started, "0" ) && Shows( started, "1023" ),
		"a started argument lists the first values" );
	Expect( started.popup && !started.enterRuns, "with nothing typed, Enter takes the highlighted value" );

	const std::string wholeToken = "120";
	Outcome inside = Complete( "com_loadingContinueAutoAdvance 1", lines, &wholeToken );
	Expect( Shows( inside, "120" ) && inside.popup && inside.enterRuns,
		"with the cursor inside a typed value, Enter runs the line" );

	Outcome outOfRange = Complete( "com_loadingContinueAutoAdvance 60001", lines );
	Expect( outOfRange.shown.empty() && !outOfRange.fuzzy && outOfRange.enterRuns,
		"an out-of-range value gets no suggestions and Enter runs it" );

	Outcome padded = Complete( "com_loadingContinueAutoAdvance 007", lines );
	Expect( padded.shown.empty() && !padded.fuzzy, "a zero-padded value is not fuzzy-corrected" );
}

static void TestFrameCap() {
	// com_maxfps, ArgCompletion_Integer<0,1000>.
	const Lines lines = IntegerLines( "com_maxfps", 0, 1000 );

	Outcome sixty = Complete( "com_maxfps 60", lines );
	Expect( sixty.shown.size() == 11 && sixty.shown.front() == "60" && sixty.shown.back() == "609",
		"60 lists itself and 600-609" );
	Expect( sixty.popup && sixty.enterRuns, "Enter runs 60 although longer values are listed" );

	Outcome oneTwenty = Complete( "com_maxfps 120", lines );
	Expect( oneTwenty.shown.size() == 1 && !oneTwenty.popup && oneTwenty.enterRuns, "120 is exact and closes the popup" );

	Outcome thousand = Complete( "com_maxfps 1000", lines );
	Expect( thousand.shown.size() == 1 && thousand.enterRuns, "the top of the range is exact" );

	Outcome zero = Complete( "com_maxfps 0", lines );
	Expect( zero.shown.size() == 1 && zero.shown[0] == "0" && !zero.popup, "0 lists only itself" );

	Outcome spaced = Complete( "com_maxfps     12", lines );
	Expect( spaced.shown.size() == 11 && AllStartWith( spaced, "12" ), "extra spaces before the value do not matter" );

	Outcome tooHigh = Complete( "com_maxfps 5000", lines );
	Expect( tooHigh.shown.empty() && !tooHigh.fuzzy && tooHigh.enterRuns,
		"5000 is not replaced by a near miss such as 500" );

	Outcome secondArgument = Complete( "com_maxfps 60 ", lines );
	Expect( secondArgument.shown.empty() && secondArgument.enterRuns, "no candidates are offered for a second argument" );
}

static void TestNameFamilies() {
	std::vector<std::string> names;
	for ( int i = 0; i < 480; ++i ) {
		char name[32];
		std::snprintf( name, sizeof( name ), "r_family%03d", i );
		names.push_back( name );
	}
	names.push_back( "r_renderer" );
	for ( int i = 0; i < 46; ++i ) {
		char name[32];
		std::snprintf( name, sizeof( name ), "r_renderer%02d", i );
		names.push_back( name );
	}
	for ( int i = 0; i < 190; ++i ) {
		char name[32];
		std::snprintf( name, sizeof( name ), "g_family%03d", i );
		names.push_back( name );
	}
	names.push_back( "com_maxfps" );
	names.push_back( "COM_MAXFPS" );	// a command and a CVar sharing a name

	Outcome family = Complete( "r_", names );
	Expect( family.shown.size() == 527, "every r_ name is listed" );
	Expect( family.popup, "a family prefix shows the popup" );

	Outcome exact = Complete( "R_RENDERER", names );
	Expect( exact.shown.size() == 47 && exact.popup && exact.enterRuns,
		"an exact name that heads a family runs on Enter" );

	Outcome partial = Complete( "r_rendere", names );
	Expect( partial.popup && !partial.enterRuns, "a partial name takes the highlighted completion" );

	Outcome shared = Complete( "com_max", names );
	Expect( shared.shown.size() == 1, "names that differ only in case are listed once" );

	Outcome typo = Complete( "com_maxpfs", names );
	Expect( typo.shown.empty() && typo.fuzzy, "a misspelled name still gets fuzzy suggestions" );

	Outcome digits = Complete( "12", names );
	Expect( digits.fuzzy, "command names keep their fuzzy fallback whatever they look like" );

	// set, seta, toggle and reset complete CVar names as their argument.
	Outcome set = Complete( "set r_", ValueLines( "set", names ) );
	Expect( set.shown.size() == 527, "CVar-name arguments list the whole family too" );
}

static void TestFolderCompletion() {
	// ArgCompletion_MapName strips maps/ and lists one folder level at a time.
	const Lines root = ValueLines( "map", { "game/", "mp/", "testmaps/", "sandbox.map" } );
	const Lines game = ValueLines( "map", { "game/airdefense1.map", "game/airdefense2.map", "game/hangar1.map" } );

	Outcome started = Complete( "map ", root );
	Expect( started.shown.size() == 4, "a started map argument lists the root" );

	Outcome folder = Complete( "map ga", root );
	Expect( folder.shown.size() == 1 && folder.shown[0] == "game/" && !folder.enterRuns,
		"a folder completes from its first letters" );

	Outcome files = Complete( "map game/air", game );
	Expect( files.shown.size() == 2 && AllStartWith( files, "game/air" ), "files narrow inside a folder" );

	Outcome all = Complete( "map game/", game );
	Expect( all.shown.size() == 3, "an opened folder lists every entry" );

	Outcome chosen = Complete( "map game/airdefense1.map", game );
	Expect( !chosen.popup && chosen.enterRuns, "a complete file name runs on Enter" );

	Outcome typo = Complete( "map game/airdefens1", game );
	Expect( typo.shown.empty() && typo.fuzzy, "a misspelled map name keeps its fuzzy fallback" );

	// ArgCompletion_ModelName keeps its models/ folder in each candidate.
	Outcome unrooted = Complete( "testmodel mon", ValueLines( "testmodel", { "models/monsters/", "models/weapons/" } ) );
	Expect( unrooted.shown.empty() && unrooted.fuzzy, "a path missing its root folder falls back to fuzzy suggestions" );
}

static void TestHyphenatedValues() {
	// r_renderApi, ArgCompletion_String<r_renderApiArgs>.
	const Lines lines = ValueLines( "r_renderApi", { "best", "gl", "vulkan", "gl-module" } );
	const std::string prefix = Prefix( "r_renderApi gl-mod" );

	int survivors = 0;
	for ( const std::string &candidate : lines ) {
		survivors += HasPrefix( candidate, prefix ) ? 1 : 0;
	}
	Expect( survivors == 1, "a hyphenated value survives its own prefix" );

	// Re-joining lexer tokens would put spaces around the hyphen.
	Expect( !HasPrefix( "r_renderApi gl-module", "r_renderApi gl - mod" ), "a re-joined token list would match nothing" );

	const std::string glPrefix = Prefix( "r_renderApi gl" );
	survivors = 0;
	for ( const std::string &candidate : lines ) {
		survivors += HasPrefix( candidate, glPrefix ) ? 1 : 0;
	}
	Expect( survivors == 2, "gl keeps both gl and gl-module" );
}

static void TestCandidateIndex() {
	Popup *popup = new Popup;
	popup->index.Clear();

	char name[32];
	for ( int i = 0; i < completion::MAX_MATCHES; ++i ) {
		std::snprintf( name, sizeof( name ), "cvar%04d", i );
		Expect( popup->index.Add( popup->matches, popup->count, name ), "a new name is accepted below the cap" );
	}
	Expect( popup->count == completion::MAX_MATCHES, "the array fills to the cap" );
	Expect( !popup->index.Add( popup->matches, popup->count, "one_more" ), "a new name at the cap stops collection" );
	Expect( popup->index.Add( popup->matches, popup->count, "CVAR0512" ), "a duplicate at the cap does not stop collection" );
	Expect( popup->count == completion::MAX_MATCHES, "neither changes the count" );

	bool allFound = true;
	for ( int i = 0; i < completion::MAX_MATCHES; ++i ) {
		std::snprintf( name, sizeof( name ), "Cvar%04d", i );
		const int before = popup->count;
		allFound &= popup->index.Add( popup->matches, popup->count, name ) && popup->count == before;
	}
	Expect( allFound, "every stored name is found again, case folded" );
	Expect( std::strcmp( popup->matches[512], "cvar0512" ) == 0, "the first spelling is kept" );

	popup->index.Clear();
	popup->count = 0;
	Expect( popup->index.Add( popup->matches, popup->count, "cvar0000" ) && popup->count == 1, "a cleared index starts over" );

	const std::string longToken( 300, 'x' );
	Expect( popup->index.Add( popup->matches, popup->count, longToken.c_str() ), "a long token is accepted" );
	Expect( popup->index.Add( popup->matches, popup->count, longToken.c_str() ) && popup->count == 2,
		"a long token is de-duplicated after truncation" );
	Expect( std::strlen( popup->matches[1] ) == EDIT_LINE - 1, "a long token is cut to the row width" );
	delete popup;
}

static void TestFuzzyGate() {
	Expect( completion::AllowsFuzzyFallback( 0, "com_maxpfs" ), "names may be fuzzy matched" );
	Expect( completion::AllowsFuzzyFallback( 0, "5000" ), "the name position ignores digits" );
	Expect( completion::AllowsFuzzyFallback( 1, "airdefens1" ), "name-like arguments may be fuzzy matched" );
	Expect( !completion::AllowsFuzzyFallback( 1, "5000" ), "integers are never fuzzy matched" );
	Expect( !completion::AllowsFuzzyFallback( 2, "-5" ), "negative values are never fuzzy matched" );
	Expect( !completion::AllowsFuzzyFallback( 1, ".5" ), "fractions are never fuzzy matched" );
	Expect( !completion::AllowsFuzzyFallback( 1, "+3.25" ), "signed decimals are never fuzzy matched" );
	Expect( !completion::AllowsFuzzyFallback( 1, "1e3" ), "exponents are never fuzzy matched" );
	Expect( !completion::AllowsFuzzyFallback( 1, "a" ), "one character is too short to correct" );
	Expect( !completion::AllowsFuzzyFallback( 0, "" ), "an empty token has nothing to correct" );
	Expect( !completion::AllowsFuzzyFallback( 1, nullptr ), "a missing token has nothing to correct" );
	Expect( completion::LooksNumeric( "-.5" ) && !completion::LooksNumeric( "-" ) && !completion::LooksNumeric( "x1" ),
		"numbers are recognised by their leading digit" );
}

int main() {
	TestPrefixBuilder();
	TestWideIntegerDomain();
	TestFrameCap();
	TestNameFamilies();
	TestFolderCompletion();
	TestHyphenatedValues();
	TestCandidateIndex();
	TestFuzzyGate();

	if ( failures != 0 ) {
		std::fprintf( stderr, "console completion: %d failure(s)\n", failures );
		return 1;
	}
	std::printf( "Console completion: argument narrowing, cap, de-duplication, Enter and fuzzy gating passed\n" );
	return 0;
}
