// Copyright (C) 2026 openQ4 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENQ4_SOUND_QUEUE_H
#define OPENQ4_SOUND_QUEUE_H

// A bounded voice queue (streamed Ogg, CPU-resident PCM without an uploaded
// buffer, centre-routed mono) owns three OpenAL buffers and is refilled once
// per main-thread frame. Each buffer is limited to the bytes the fixed and
// per-stream audio reservations already account for: one 4096-frame 5.1
// block. Inside that limit a buffer holds a third of a second, so the three
// cover about one second of main-thread stall instead of the 279 ms a flat
// 4096 frames gave 44.1 kHz audio.
static const int SOUND_QUEUE_BUFFER_BYTES = 4096 * 6 * 2;
static const int SOUND_QUEUE_MIN_FRAMES = 4096;
static const int SOUND_QUEUE_MAX_FRAMES = 16384;
// The bounded Vorbis decoder returns at most this many frames per call
// (SoundVorbisStream::ChunkFrames); larger buffers are filled in several calls.
static const int SOUND_QUEUE_DECODE_FRAMES = 4096;
static_assert( SOUND_QUEUE_BUFFER_BYTES == 4096 * 6 * sizeof( short ),
	"the audio reservations count one 4096-frame 5.1 block per queue buffer" );

// Centre routing uploads mono as 5.1, twelve bytes per frame, which fits only
// 4096 frames in that block. A fixed pool of routed voices gets buffers large
// enough for the same one-second depth; the fixed audio reservation counts
// the pool's extra bytes and its routing scratch. Routed voices beyond the
// pool keep 4096 frames per buffer.
static const int SOUND_QUEUE_DEEP_ROUTED_VOICES = 8;
static const int SOUND_QUEUE_ROUTED_FRAME_BYTES = 6 * 2;
static const int SOUND_QUEUE_DEEP_ROUTED_BUFFER_BYTES = SOUND_QUEUE_MAX_FRAMES * SOUND_QUEUE_ROUTED_FRAME_BYTES;

// Frames per queue buffer for audio uploaded with outputFrameBytes per frame
// (two per channel for 16-bit PCM, twelve once mono is routed to 5.1) into a
// buffer of at most bufferBytes.
inline int SoundQueueFrames( int sampleRate, int outputFrameBytes, int bufferBytes )
{
	if( outputFrameBytes < 1 )
	{
		outputFrameBytes = 1;
	}
	int limit = bufferBytes / outputFrameBytes;
	if( limit < 1 )
	{
		limit = 1;
	}
	int frames = sampleRate > 0 && sampleRate <= 384000 ? ( sampleRate + 2 ) / 3 : 0;
	frames = ( frames + 511 ) & ~511;
	if( frames < SOUND_QUEUE_MIN_FRAMES )
	{
		frames = SOUND_QUEUE_MIN_FRAMES;
	}
	return frames < limit ? frames : limit;
}

inline int SoundQueueChunkFrames( int sampleRate, int outputFrameBytes )
{
	return SoundQueueFrames( sampleRate, outputFrameBytes, SOUND_QUEUE_BUFFER_BYTES );
}
#endif
