// SPDX-License-Identifier: GPL-3.0-or-later
#include "src/sound/SoundDialogue.h"
#include <cstdio>
#include <cstdlib>
#include <initializer_list>

static void Check( bool ok, const char* message ) {
	if ( !ok ) { std::fprintf( stderr, "%s\n", message ); std::exit( 1 ); }
}

int main() {
	for ( const char* path : { "sound/vo/airdefense/line", "sound/vo_english/ai/line.ogg",
		"sound/vo_french/radio.wav", "SOUND\\VO_GERMAN\\line.wav", "sound/vo/awakening/line" } ) {
		Check( SoundIsDialogue( false, false, path ), path );
		Check( !SoundIsDialogue( true, false, path ), "Music bus has precedence" );
	}
	for ( const char* path : { "", "sound/vo", "sound/vo_/bad", "sound/vo_english", "sound/voicegun/fire",
		"sound/guis/menu.wav", "sound/weapons/darkmatter/rings", "sound/marine/player/pain",
		"sound/musical/score", "sound/ambience/room", "other/sound/vo/line" } ) {
		Check( !SoundIsDialogue( false, false, path ), path );
		Check( SoundIsDialogue( false, true, path ), "Explicit lip-sync/VO-for-player speech" );
	}
	std::puts( "Sound dialogue classification passed" );
}
