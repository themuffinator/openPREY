// SPDX-License-Identifier: GPL-3.0-or-later
// Every combination of what a low-memory notice may take from a loaded sample
// (src/sound/SoundMemoryTrim.h).
#include "src/sound/SoundMemoryTrim.h"
#include <cstdio>
#include <cstdlib>
#include <initializer_list>

static int checks = 0;
static void Check( bool ok, const char* message ) {
	++checks;
	if ( !ok ) { std::fprintf( stderr, "%s\n", message ); std::exit( 1 ); }
}

int main() {
	using Action = SoundTrimAction;
	for ( int bits = 0; bits < 128; ++bits ) {
		SoundTrimSample sample;
		sample.active = bits & 1;
		sample.neverPurge = bits & 2;
		sample.levelReferenced = bits & 4;
		sample.streamed = bits & 8;
		sample.cpuCopy = bits & 16;
		sample.played = bits & 32;
		const bool loading = bits & 64;
		for ( int idle : { 0, 29999, 30000, 600000 } ) {
			sample.idleMsec = idle;
			for ( int limit : { -1, 0, 30000 } ) {
				const Action action = SoundTrimDecide( sample, limit, loading );
				const Action spare = sample.cpuCopy ? Action::ReleaseCopy : Action::Keep;
				if ( sample.active ) {
					Check( action == Action::Keep, "a sample a channel references is never touched, not even its copy" );
				} else if ( loading || sample.neverPurge ) {
					Check( action == spare, "level loads and menu/HUD samples only lose a retained copy" );
				} else if ( !sample.levelReferenced ) {
					Check( action == Action::Free, "an earlier level's cache is freed" );
				} else if ( sample.streamed || limit < 0 ) {
					Check( action == spare, "streamed tracks and a negative idle limit keep the level's samples" );
				} else if ( !sample.played || idle >= limit ) {
					Check( action == Action::Free, "a level sample idle for the limit is freed" );
				} else {
					Check( action == spare, "a recently started level sample is kept" );
				}
			}
		}
	}
	std::printf( "Sound memory trim: %d checks passed\n", checks );
}
