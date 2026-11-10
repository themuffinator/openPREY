// Copyright (C) 2026 openQ4 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENQ4_SOUND_MEMORY_TRIM_H
#define OPENQ4_SOUND_MEMORY_TRIM_H

// What an operating-system low-memory notice may take from a loaded sample.
// Nothing a channel references goes, in any world, audible or not: shakes,
// flicker, subtitles and resumed playback still read it. A freed sample keeps
// its shader references and reloads when a sound starts it again.
enum class SoundTrimAction { Keep, ReleaseCopy, Free };

struct SoundTrimSample {
	bool active = false;			// a channel in some world plays it or will
	bool neverPurge = false;		// menus, HUD and samples first used outside a level load
	bool levelReferenced = false;	// the current level loaded it
	bool streamed = false;			// only metadata and an envelope are resident
	bool cpuCopy = false;			// CPU PCM retained beside OpenAL's own complete copy
	bool played = false;			// started at least once since it loaded
	int idleMsec = 0;				// since it last started, when played
};

// idleLimitMsec < 0 keeps the current level's samples. insideLevelLoad keeps
// every loaded sample: the load in progress may reference any of them next.
inline SoundTrimAction SoundTrimDecide( const SoundTrimSample& sample, int idleLimitMsec, bool insideLevelLoad )
{
	if( sample.active )
	{
		return SoundTrimAction::Keep;
	}
	if( !insideLevelLoad && !sample.neverPurge )
	{
		// An earlier level's cache: EndLevelLoad would free it at the next change.
		if( !sample.levelReferenced )
		{
			return SoundTrimAction::Free;
		}
		// Streamed tracks hold almost nothing, and rebuilding their envelope
		// decodes the whole file again.
		if( !sample.streamed && idleLimitMsec >= 0 && ( !sample.played || sample.idleMsec >= idleLimitMsec ) )
		{
			return SoundTrimAction::Free;
		}
	}
	return sample.cpuCopy ? SoundTrimAction::ReleaseCopy : SoundTrimAction::Keep;
}

#endif
