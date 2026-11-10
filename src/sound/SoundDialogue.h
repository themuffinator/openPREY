// SPDX-License-Identifier: GPL-3.0-or-later
// Spoken-dialogue classification is independent of mixer priority and routing.
#ifndef OPENQ4_SOUND_DIALOGUE_H
#define OPENQ4_SOUND_DIALOGUE_H

#include <string_view>

inline bool SoundDialogueSamplePath( std::string_view path ) {
	// The loader keeps canonical sound/vo names, but tools and mods may refer
	// directly to localized assets. Match a complete directory, not "voicegun".
	constexpr std::string_view prefix = "sound/vo";
	if ( path.size() <= prefix.size() ) return false;
	for ( size_t i = 0; i < prefix.size(); ++i ) {
		char c = path[i];
		if ( c == '\\' ) c = '/';
		if ( c >= 'A' && c <= 'Z' ) c += 'a' - 'A';
		if ( c != prefix[i] ) return false;
	}
	if ( path[8] == '/' || path[8] == '\\' ) return true;
	if ( path[8] != '_' ) return false;
	const auto end = path.find_first_of( "/\\", 9 );
	return end != std::string_view::npos && end > 9 && end + 1 < path.size();
}

inline bool SoundIsDialogue( bool music, bool authoredSpeech, std::string_view samplePath ) {
	// SSF_VO also labels UI effects, and SND_CHANNEL_VOICE is used by weapons.
	// Neither on its own is evidence that the selected sample is spoken dialogue.
	return !music && ( authoredSpeech || SoundDialogueSamplePath( samplePath ) );
}

// Why a playing sample shows a subtitle or not under the mapping policy: it has
// text; no lipSync declares it; the declaration has no transcript; its text key
// does not resolve; or only its random-variant shader declares one.
enum class SoundTranscript { Text, Undeclared, NoText, Unresolved, Variant };

inline const char* SoundTranscriptName( SoundTranscript transcript ) {
	switch ( transcript ) {
		case SoundTranscript::Text: return "text";
		case SoundTranscript::Undeclared: return "undeclared";
		case SoundTranscript::NoText: return "notext";
		case SoundTranscript::Unresolved: return "unresolved";
		case SoundTranscript::Variant: return "variant";
	}
	return "unknown";
}

#endif
