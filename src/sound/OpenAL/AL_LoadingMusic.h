// Copyright (C) 2026 openPREY contributors
// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENPREY_AL_LOADING_MUSIC_H
#define OPENPREY_AL_LOADING_MUSIC_H

// Map-load music (a mapDef's snd_loadmusic) plays while ExecuteMapChange blocks
// the main thread. A world voice refills its queue once per main-thread frame,
// and a blocking load stalls that frame for well over the queue's second of
// audio, so the voice underran and restarted ahead in the track again and again.
// Retail mixed sound on an asynchronous timer, which a load could not starve.
//
// This plays one streamed Ogg on an OpenAL source of its own, decoded from an
// in-memory copy of the file by a thread of its own. Nothing it touches is
// shared with the sound worlds or the voice pool; OpenAL itself is thread-safe.
// The thread makes no call that can raise an AL error, so it never consumes an
// error the main thread's CheckALErrors is waiting for.

// Main thread only. Reads the file, prefills and starts the source, then hands
// refilling to the thread. False when the file cannot be read or decoded.
bool	SoundLoadingMusic_Start( const char* oggName, float gain, bool looping, float startFraction, ALint directChannelsMode );
// Main thread only. Joins the thread and frees the source; safe when idle.
void	SoundLoadingMusic_Stop();
bool	SoundLoadingMusic_IsActive();
// Main thread only. Applies volume changes made while loading.
void	SoundLoadingMusic_SetGain( float gain );

#endif
