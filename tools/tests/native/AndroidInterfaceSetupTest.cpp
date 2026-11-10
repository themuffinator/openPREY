// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
// The Android interface setup record crosses JNI as text. Only a complete,
// in-range record with a new transaction identity may change live settings.
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

// The engine includes the header after idlib's Str.h, which replaces the C
// string comparisons with poison names; keep the header free of them.
#define strcmp use_idStr_Cmp
#define strncmp use_idStr_Cmpn
#define stricmp use_idStr_Icmp
#define strcasecmp use_idStr_Icmp
#include "src/sys/android/android_interface_settings.h"
#undef strcmp
#undef strncmp
#undef stricmp
#undef strcasecmp

using openq4::android::InterfaceSetup;
using openq4::android::PendingInterfaceSetup;

static void Check( bool condition, const char *message ) {
	if ( !condition ) {
		std::fprintf( stderr, "FAIL: %s\n", message );
		std::exit( 1 );
	}
}

static const char *const kRevision = "0123456789abcdef0123456789abcdef";
static const char *const kOther = "fedcba9876543210fedcba9876543210";

static std::string Record( const char *revision, int profile, int ui, int text ) {
	char buffer[96];
	std::snprintf( buffer, sizeof( buffer ), "1:%s:%d:%d:%d", revision, profile, ui, text );
	return buffer;
}

// A rejected record must leave the caller's settings exactly as they were.
static void Rejected( const std::string &record, const char *applied, const char *message ) {
	InterfaceSetup out;
	std::memcpy( out.revision, "sentinel", sizeof( "sentinel" ) );
	out.profile = 9; out.scale = 3; out.textScale = 4;
	Check( !PendingInterfaceSetup( record.c_str(), applied, out ), message );
	Check( !std::strcmp( out.revision, "sentinel" ) && out.profile == 9 && out.scale == 3 && out.textScale == 4,
		"rejected record partially changed the output" );
}

int main() {
	int accepted = 0;
	for ( int profile = 1; profile <= 5; ++profile ) {
		for ( int ui = 75; ui <= 200; ui += 5 ) {
			for ( int text = 100; text <= 200; text += 5 ) {
				InterfaceSetup out;
				const std::string record = Record( kRevision, profile, ui, text );
				Check( PendingInterfaceSetup( record.c_str(), "", out ), "valid record rejected" );
				Check( !std::strcmp( out.revision, kRevision ) && out.profile == profile, "identity or profile lost" );
				Check( std::fabs( out.scale - ui / 100.0f ) < 1e-6f && std::fabs( out.textScale - text / 100.0f ) < 1e-6f,
					"scale percentages not converted to cvar multipliers" );
				++accepted;
			}
		}
	}
	// Both scales may be set to any whole percentage the engine cvars accept.
	InterfaceSetup odd;
	Check( PendingInterfaceSetup( Record( kRevision, 4, 133, 101 ).c_str(), NULL, odd ) &&
		std::fabs( odd.scale - 1.33f ) < 1e-6f && std::fabs( odd.textScale - 1.01f ) < 1e-6f, "unaligned percentage rejected" );

	// The same transaction applies once; a different applied identity does not block it.
	Rejected( Record( kRevision, 4, 100, 100 ), kRevision, "already-applied transaction applied again" );
	InterfaceSetup next;
	Check( PendingInterfaceSetup( Record( kRevision, 2, 150, 125 ).c_str(), kOther, next ), "new transaction blocked by older identity" );

	// Missing, truncated, oversized and out-of-range payloads.
	InterfaceSetup none;
	Check( !PendingInterfaceSetup( NULL, "", none ) && none.revision[0] == '\0', "null record accepted" );
	const std::string valid = Record( kRevision, 4, 100, 100 );
	for ( size_t length = 0; length < valid.size(); ++length ) {
		Rejected( valid.substr( 0, length ), "", "truncated record accepted" );
	}
	Rejected( valid + "0", "", "trailing digit accepted" );
	Rejected( valid + ":", "", "trailing separator accepted" );
	Rejected( valid + "\n", "", "trailing newline accepted" );
	Rejected( "2" + valid.substr( 1 ), "", "unknown record version accepted" );
	Rejected( Record( "0123456789ABCDEF0123456789abcdef", 4, 100, 100 ), "", "uppercase identity accepted" );
	Rejected( Record( "0123456789abcdef0123456789abcde", 4, 100, 100 ), "", "short identity accepted" );
	Rejected( Record( "0123456789abcdef0123456789abcdef0", 4, 100, 100 ), "", "long identity accepted" );
	Rejected( Record( "0123456789abcdeg0123456789abcdef", 4, 100, 100 ), "", "non-hex identity accepted" );
	for ( int profile : { 0, 6, 9 } ) {
		Rejected( Record( kRevision, profile, 100, 100 ), "", "unresolved or unknown profile accepted" );
	}
	for ( int ui : { 0, 70, 74, 201, 999 } ) {
		Rejected( Record( kRevision, 4, ui, 100 ), "", "UI scale outside the ui_retainedScale range accepted" );
	}
	for ( int text : { 0, 99, 201, 500 } ) {
		Rejected( Record( kRevision, 4, 100, text ), "", "text scale outside the ui_retainedTextScale range accepted" );
	}
	Rejected( std::string( "1:" ) + kRevision + ":4:0100:100", "", "four-digit scale accepted" );
	Rejected( std::string( "1:" ) + kRevision + ":4:-100:100", "", "negative scale accepted" );
	Rejected( std::string( "1:" ) + kRevision + ":4::100", "", "empty scale accepted" );
	Rejected( std::string( "1:" ) + kRevision + ":4:100", "", "missing text scale accepted" );
	Rejected( std::string( "1:" ) + kRevision + "-4:100:100", "", "wrong separator accepted" );
	Rejected( std::string( "1:" ) + kRevision + ":4:100:100" + std::string( 8, ' ' ), "", "padded record accepted" );
	std::string embedded = valid; embedded[10] = '\0';
	Rejected( std::string( embedded.c_str() ), "", "record cut at an embedded NUL accepted" );

	std::printf( "PASS: %d interface setup records, applied-once identity, truncation, range and format rejection\n", accepted );
	return 0;
}
