// SPDX-License-Identifier: GPL-3.0-or-later
// Every combination of the output-change decision a voice makes in CheckOutput
// and UnPause (src/sound/SoundOutputRecovery.h).
#include "src/sound/SoundOutputRecovery.h"
#include <cstdio>
#include <cstdlib>
#include <initializer_list>

static int checks = 0;
static void Check( bool ok, const char* message ) {
	++checks;
	if ( !ok ) { std::fprintf( stderr, "%s\n", message ); std::exit( 1 ); }
}

int main() {
	using Action = SoundOutputVoiceAction;
	for ( unsigned int voice : { 1u, 7u, 0xffffffffu } ) {
		for ( unsigned int output : { 1u, 7u, 8u, 0u } ) {
			for ( int bits = 0; bits < 16; ++bits ) {
				const bool connected = bits & 1, stopped = bits & 2, routed = bits & 4, wants = bits & 8;
				const Action action = SoundOutputVoiceCheck( voice, output, connected, stopped, routed, wants );
				if ( stopped && !connected ) {
					Check( action == Action::Recover, "a source stopped by a lost endpoint is not a finished sound" );
				} else if ( voice == output ) {
					// Same output: a stopped source with the endpoint present ended.
					Check( action == Action::Keep, "an unchanged output keeps the voice, whatever its routing" );
				} else if ( stopped ) {
					Check( action == Action::Recover, "a source stopped across a reopen restarts at the scene clock" );
				} else if ( routed != wants ) {
					Check( action == Action::Recover, "a voice routed for the old layout re-routes" );
				} else {
					Check( action == Action::Adopt, "a voice still playing on an equivalent layout carries on" );
				}
			}
		}
	}
	// The serial wraps; only equality matters.
	Check( SoundOutputVoiceCheck( 0xffffffffu, 0u, true, false, false, false ) == Action::Adopt, "wrapped serial is a change" );
	for ( int bits = 0; bits < 8; ++bits ) {
		const bool connected = bits & 1;
		const unsigned int voice = 3, output = ( bits & 2 ) ? 3u : 4u;
		Check( SoundOutputResumePaused( voice, output, connected ) == ( connected && voice == output ),
			"only a paused voice whose output never changed resumes in place" );
	}
	std::printf( "Sound output recovery: %d checks passed\n", checks );
}
