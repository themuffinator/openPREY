// Copyright (C) 2026 openQ4 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENQ4_SOUND_OUTPUT_RECOVERY_H
#define OPENQ4_SOUND_OUTPUT_RECOVERY_H

// The output a voice plays on can go away (a disconnected endpoint stops every
// source), be replaced (a reopen onto another endpoint) or change layout (an
// in-place reset, or a new endpoint with other speakers). The hardware counts
// those events in an output serial; each voice keeps the serial it started on.
//
// A voice that must recover hands itself back to its channel, which restarts
// the sound at the scene clock on the current output, exactly as after a
// bounded-queue underrun. A stopped static voice is otherwise a finished sound.
enum class SoundOutputVoiceAction { Keep, Adopt, Recover };

inline SoundOutputVoiceAction SoundOutputVoiceCheck( unsigned int voiceSerial, unsigned int outputSerial,
	bool outputConnected, bool sourceStopped, bool routed, bool wantsRouting )
{
	// A lost endpoint stops every source: that is not the end of the sound.
	if( sourceStopped && !outputConnected )
	{
		return SoundOutputVoiceAction::Recover;
	}
	if( voiceSerial == outputSerial )
	{
		return SoundOutputVoiceAction::Keep;
	}
	// The source was stopped while its output was replaced, or it is routed for
	// a layout the output no longer has (or no longer routed for one it has).
	if( sourceStopped || routed != wantsRouting )
	{
		return SoundOutputVoiceAction::Recover;
	}
	// The replacement kept this source playing on an equivalent layout.
	return SoundOutputVoiceAction::Adopt;
}

// A paused source that lost its OpenAL voice restarts from its first sample when
// it is played again, so a voice paused across an output change is restarted at
// the scene clock instead of being resumed.
inline bool SoundOutputResumePaused( unsigned int voiceSerial, unsigned int outputSerial, bool outputConnected )
{
	return outputConnected && voiceSerial == outputSerial;
}

#endif
