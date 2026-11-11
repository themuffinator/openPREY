// Copyright (C) 2026 openPREY contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "../snd_local.h"
#include "AL_LoadingMusic.h"

#include <vorbis/vorbisfile.h>
#include <atomic>
#include <chrono>
#include <thread>

extern idCVar s_debugHardware;

namespace
{

// Four buffers of 8192 frames: 1.5 s queued at 22 kHz, 0.74 s at 44.1 kHz. The
// thread tops them up every few milliseconds, so the depth only has to ride out
// scheduling delays while job workers saturate the CPU during a load.
const int LOADING_MUSIC_BUFFERS = 4;
const int LOADING_MUSIC_BUFFER_FRAMES = 8192;
const int LOADING_MUSIC_SERVICE_MSEC = 5;
// A source that stops with audio queued has lost its output (a source that ran
// dry is refilled first). Retry at this pace rather than decoding ahead of a
// source that will not play.
const int LOADING_MUSIC_RESTART_MSEC = 250;
// libvorbisfile resumes after a damaged page (OV_HOLE); retail Prey ships a few.
const int LOADING_MUSIC_MAX_HOLE_RETRIES = 16;

struct loadingMusicMemory_t
{
	const byte*	data;
	size_t		length;
	size_t		offset;
};

size_t LoadingMusic_Read( void* output, size_t itemSize, size_t itemCount, void* dataSource )
{
	loadingMusicMemory_t* stream = static_cast<loadingMusicMemory_t*>( dataSource );
	if( stream == NULL || output == NULL || itemSize == 0 || stream->offset >= stream->length )
	{
		return 0;
	}
	const size_t items = Min( itemCount, ( stream->length - stream->offset ) / itemSize );
	memcpy( output, stream->data + stream->offset, items * itemSize );
	stream->offset += items * itemSize;
	return items;
}

int LoadingMusic_Seek( void* dataSource, ogg_int64_t offset, int origin )
{
	loadingMusicMemory_t* stream = static_cast<loadingMusicMemory_t*>( dataSource );
	if( stream == NULL )
	{
		return -1;
	}
	ogg_int64_t base = 0;
	switch( origin )
	{
		case SEEK_SET:
			base = 0;
			break;
		case SEEK_CUR:
			base = static_cast<ogg_int64_t>( stream->offset );
			break;
		case SEEK_END:
			base = static_cast<ogg_int64_t>( stream->length );
			break;
		default:
			return -1;
	}
	const ogg_int64_t target = base + offset;
	if( target < 0 || target > static_cast<ogg_int64_t>( stream->length ) )
	{
		return -1;
	}
	stream->offset = static_cast<size_t>( target );
	return 0;
}

long LoadingMusic_Tell( void* dataSource )
{
	const loadingMusicMemory_t* stream = static_cast<const loadingMusicMemory_t*>( dataSource );
	return stream != NULL ? static_cast<long>( stream->offset ) : -1;
}

int LoadingMusic_Close( void* )
{
	return 0;
}

class idLoadingMusicStream
{
public:
	bool				Start( const char* oggName, float gain, bool looping, float startFraction, ALint directChannelsMode );
	void				Stop();
	bool				IsActive() const
	{
		return active;
	}
	void				SetGain( float gain );

private:
	void				Run();
	// Unqueues played buffers, decodes into them and keeps the source playing.
	// Called on the main thread to prefill, then only on the streaming thread.
	void				Service();
	int					Decode( short* pcm, int capacityFrames );

	bool				active = false;
	bool				vorbisOpen = false;
	bool				looping = false;
	bool				finished = false;
	std::atomic<bool>	stopRequested{ false };
	// Counted here, reported by Stop on the main thread (s_debugHardware).
	std::atomic<int>	underruns{ 0 };
	int					startMsec = 0;
	std::thread			thread;

	void*				fileData = NULL;
	loadingMusicMemory_t memory = {};
	OggVorbis_File		vorbisFile = {};
	int					channels = 0;
	int					rate = 0;
	ALenum				format = AL_NONE;

	ALuint				source = 0;
	ALuint				buffers[LOADING_MUSIC_BUFFERS] = {};
	ALuint				freeBuffers[LOADING_MUSIC_BUFFERS] = {};
	int					numFreeBuffers = 0;
	int					lastPlayMsec = 0;
	float				currentGain = -1.0f;

	short				pcm[LOADING_MUSIC_BUFFER_FRAMES * 2];
};

idLoadingMusicStream loadingMusicStream;

int idLoadingMusicStream::Decode( short* output, int capacityFrames )
{
	const int frameBytes = channels * static_cast<int>( sizeof( short ) );
	const int capacityBytes = capacityFrames * frameBytes;
	int filled = 0;
	int holes = 0;
	bool rewound = false;
	while( filled < capacityBytes )
	{
		int bitstream = 0;
		const long got = ov_read( &vorbisFile, reinterpret_cast<char*>( output ) + filled, capacityBytes - filled, 0, 2, 1, &bitstream );
		if( got > 0 )
		{
			filled += static_cast<int>( got );
			rewound = false;
			continue;
		}
		if( got == OV_HOLE && ++holes <= LOADING_MUSIC_MAX_HOLE_RETRIES )
		{
			continue;
		}
		// The end of the track, or a stream that cannot be decoded further.
		// A loop that decodes nothing after rewinding would spin; end it instead.
		if( !looping || rewound || ov_pcm_seek( &vorbisFile, 0 ) != 0 )
		{
			break;
		}
		rewound = true;
	}
	return filled / frameBytes;
}

void idLoadingMusicStream::Service()
{
	ALint processed = 0;
	alGetSourcei( source, AL_BUFFERS_PROCESSED, &processed );
	ALint state = AL_INITIAL;
	alGetSourcei( source, AL_SOURCE_STATE, &state );

	const int now = Sys_Milliseconds();
	if( state == AL_STOPPED && lastPlayMsec != 0 && now - lastPlayMsec < LOADING_MUSIC_RESTART_MSEC )
	{
		return;
	}
	if( state == AL_STOPPED && !finished )
	{
		underruns.fetch_add( 1, std::memory_order_relaxed );
	}

	while( processed > 0 && numFreeBuffers < LOADING_MUSIC_BUFFERS )
	{
		ALuint buffer = 0;
		alSourceUnqueueBuffers( source, 1, &buffer );
		freeBuffers[numFreeBuffers++] = buffer;
		processed--;
	}

	while( numFreeBuffers > 0 && !finished )
	{
		const int frames = Decode( pcm, LOADING_MUSIC_BUFFER_FRAMES );
		if( frames <= 0 )
		{
			finished = true;
			break;
		}
		const ALuint buffer = freeBuffers[--numFreeBuffers];
		alBufferData( buffer, format, pcm, frames * channels * static_cast<int>( sizeof( short ) ), rate );
		alSourceQueueBuffers( source, 1, &buffer );
	}

	ALint queued = 0;
	alGetSourcei( source, AL_BUFFERS_QUEUED, &queued );
	if( queued > 0 && state != AL_PLAYING && state != AL_PAUSED )
	{
		alSourcePlay( source );
		lastPlayMsec = Max( 1, now );
	}
}

void idLoadingMusicStream::Run()
{
	while( !stopRequested.load( std::memory_order_acquire ) )
	{
		Service();
		if( finished )
		{
			ALint queued = 0;
			alGetSourcei( source, AL_BUFFERS_QUEUED, &queued );
			ALint processed = 0;
			alGetSourcei( source, AL_BUFFERS_PROCESSED, &processed );
			if( queued <= processed )
			{
				// A one-shot track has played out.
				break;
			}
		}
		std::this_thread::sleep_for( std::chrono::milliseconds( LOADING_MUSIC_SERVICE_MSEC ) );
	}
}

bool idLoadingMusicStream::Start( const char* oggName, float gain, bool loop, float startFraction, ALint directChannelsMode )
{
	Stop();
	if( oggName == NULL || oggName[0] == '\0' || alcGetCurrentContext() == NULL )
	{
		return false;
	}

	const int fileLength = fileSystem->ReadFile( oggName, &fileData, NULL );
	if( fileLength <= 0 || fileData == NULL )
	{
		Stop();
		return false;
	}
	memory.data = static_cast<const byte*>( fileData );
	memory.length = static_cast<size_t>( fileLength );
	memory.offset = 0;

	const ov_callbacks callbacks = { LoadingMusic_Read, LoadingMusic_Seek, LoadingMusic_Close, LoadingMusic_Tell };
	if( ov_open_callbacks( &memory, &vorbisFile, NULL, 0, callbacks ) != 0 )
	{
		Stop();
		return false;
	}
	vorbisOpen = true;
	const vorbis_info* info = ov_info( &vorbisFile, -1 );
	if( info == NULL || info->channels < 1 || info->channels > 2 || info->rate < 8000 || info->rate > 192000 )
	{
		Stop();
		return false;
	}
	channels = info->channels;
	rate = static_cast<int>( info->rate );
	format = channels == 2 ? AL_FORMAT_STEREO16 : AL_FORMAT_MONO16;
	looping = loop;
	finished = false;

	if( startFraction > 0.0f && startFraction < 1.0f )
	{
		const ogg_int64_t total = ov_pcm_total( &vorbisFile, -1 );
		if( total > 0 )
		{
			ov_pcm_seek( &vorbisFile, static_cast<ogg_int64_t>( total * startFraction ) );
		}
	}

	alGetError();
	alGenSources( 1, &source );
	if( alGetError() != AL_NO_ERROR )
	{
		source = 0;
		Stop();
		return false;
	}
	alGenBuffers( LOADING_MUSIC_BUFFERS, buffers );
	if( alGetError() != AL_NO_ERROR )
	{
		memset( buffers, 0, sizeof( buffers ) );
		Stop();
		return false;
	}
	for( int i = 0; i < LOADING_MUSIC_BUFFERS; i++ )
	{
		freeBuffers[i] = buffers[i];
	}
	numFreeBuffers = LOADING_MUSIC_BUFFERS;

	// Head-relative and unattenuated, as a global menu-world sound plays.
	alSourcei( source, AL_SOURCE_RELATIVE, AL_TRUE );
	alSource3f( source, AL_POSITION, 0.0f, 0.0f, 0.0f );
	alSourcef( source, AL_ROLLOFF_FACTOR, 0.0f );
	alSourcei( source, AL_LOOPING, AL_FALSE );
#if defined( AL_DIRECT_CHANNELS_SOFT )
	if( channels > 1 && directChannelsMode >= 0 )
	{
		alSourcei( source, AL_DIRECT_CHANNELS_SOFT, directChannelsMode );
	}
#endif
	currentGain = -1.0f;
	SetGain( gain );
	active = true;

	// Prefill here so the music is audible the moment the load begins.
	Service();
	if( alGetError() != AL_NO_ERROR || finished )
	{
		Stop();
		return false;
	}

	stopRequested.store( false, std::memory_order_release );
	underruns.store( 0, std::memory_order_relaxed );
	startMsec = Sys_Milliseconds();
	try
	{
		thread = std::thread( &idLoadingMusicStream::Run, this );
	}
	catch( ... )
	{
		Stop();
		return false;
	}
	if( s_debugHardware.GetBool() )
	{
		idLib::Printf( "Loading music: %s, %d Hz, %d channels, start %.0f%%\n", oggName, rate, channels, startFraction * 100.0f );
	}
	return true;
}

void idLoadingMusicStream::Stop()
{
	stopRequested.store( true, std::memory_order_release );
	if( thread.joinable() )
	{
		thread.join();
	}
	const bool hadOpenALObjects = source != 0 || buffers[0] != 0;
	if( active && s_debugHardware.GetBool() )
	{
		idLib::Printf( "Loading music stopped after %d ms, %d underruns\n", Sys_Milliseconds() - startMsec, underruns.load( std::memory_order_relaxed ) );
	}
	if( source != 0 )
	{
		alSourceStop( source );
		alSourcei( source, AL_BUFFER, 0 );
		alDeleteSources( 1, &source );
		source = 0;
	}
	if( buffers[0] != 0 )
	{
		alDeleteBuffers( LOADING_MUSIC_BUFFERS, buffers );
		memset( buffers, 0, sizeof( buffers ) );
	}
	if( hadOpenALObjects )
	{
		// Main thread, thread joined: nothing else can be relying on this error.
		alGetError();
	}
	numFreeBuffers = 0;
	if( vorbisOpen )
	{
		ov_clear( &vorbisFile );
		vorbisOpen = false;
	}
	if( fileData != NULL )
	{
		fileSystem->FreeFile( fileData );
		fileData = NULL;
	}
	memory = {};
	active = false;
	finished = false;
	lastPlayMsec = 0;
	currentGain = -1.0f;
}

void idLoadingMusicStream::SetGain( float gain )
{
	if( source == 0 )
	{
		return;
	}
	gain = idMath::ClampFloat( 0.0f, 16.0f, FLOAT_IS_NAN( gain ) ? 0.0f : gain );
	if( gain != currentGain )
	{
		alSourcef( source, AL_GAIN, gain );
		currentGain = gain;
	}
}

}	// namespace

bool SoundLoadingMusic_Start( const char* oggName, float gain, bool looping, float startFraction, ALint directChannelsMode )
{
	return loadingMusicStream.Start( oggName, gain, looping, startFraction, directChannelsMode );
}

void SoundLoadingMusic_Stop()
{
	loadingMusicStream.Stop();
}

bool SoundLoadingMusic_IsActive()
{
	return loadingMusicStream.IsActive();
}

void SoundLoadingMusic_SetGain( float gain )
{
	loadingMusicStream.SetGain( gain );
}
