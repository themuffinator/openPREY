/*
===========================================================================

openQ4
Copyright (C) 2026 DarkMatter Productions

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

===========================================================================
*/

#if !defined( __linux__ ) || !defined( ID_DEDICATED )
	#error "stub_openal.cpp is only for Linux dedicated-server builds"
#endif

#define AL_ALEXT_PROTOTYPES
#include <AL/alext.h>

// Older OpenAL headers do not annotate the API with noexcept. Match whichever
// declaration the selected headers provide.
#ifndef AL_API_NOEXCEPT
	#define AL_API_NOEXCEPT
#endif
#ifndef ALC_API_NOEXCEPT
	#define ALC_API_NOEXCEPT
#endif

namespace {

const ALchar openalEmptyString[] = "";
const ALCchar openalEmptyList[] = { '\0', '\0' };

template< typename T >
void ZeroValues( T* values, const int count ) {
	if( values == NULL ) {
		return;
	}
	for( int i = 0; i < count; ++i ) {
		values[i] = 0;
	}
}

} // namespace

extern "C" {

void AL_APIENTRY alBufferData( ALuint, ALenum, const ALvoid*, ALsizei, ALsizei ) AL_API_NOEXCEPT {
}

void AL_APIENTRY alBufferSamplesSOFT( ALuint, ALuint, ALenum, ALsizei, ALenum, ALenum, const ALvoid* ) AL_API_NOEXCEPT {
}

void AL_APIENTRY alDeleteBuffers( ALsizei, const ALuint* ) AL_API_NOEXCEPT {
}

void AL_APIENTRY alDeleteSources( ALsizei, const ALuint* ) AL_API_NOEXCEPT {
}

void AL_APIENTRY alDopplerFactor( ALfloat ) AL_API_NOEXCEPT {
}

void AL_APIENTRY alGenBuffers( const ALsizei count, ALuint* buffers ) AL_API_NOEXCEPT {
	ZeroValues( buffers, count );
}

void AL_APIENTRY alGenSources( const ALsizei count, ALuint* sources ) AL_API_NOEXCEPT {
	ZeroValues( sources, count );
}

ALenum AL_APIENTRY alGetEnumValue( const ALchar* ) AL_API_NOEXCEPT {
	return AL_NONE;
}

ALenum AL_APIENTRY alGetError( void ) AL_API_NOEXCEPT {
	return AL_NO_ERROR;
}

ALint AL_APIENTRY alGetInteger( ALenum ) AL_API_NOEXCEPT {
	return 0;
}

void AL_APIENTRY alGetListenerf( ALenum, ALfloat* value ) AL_API_NOEXCEPT {
	ZeroValues( value, 1 );
}

void* AL_APIENTRY alGetProcAddress( const ALchar* ) AL_API_NOEXCEPT {
	return NULL;
}

void AL_APIENTRY alGetSourcef( ALuint, ALenum, ALfloat* value ) AL_API_NOEXCEPT {
	ZeroValues( value, 1 );
}

void AL_APIENTRY alGetSourcefv( ALuint, const ALenum param, ALfloat* values ) AL_API_NOEXCEPT {
	const bool vector = param == AL_POSITION || param == AL_VELOCITY || param == AL_DIRECTION;
	ZeroValues( values, vector ? 3 : 1 );
}

void AL_APIENTRY alGetSourcei( ALuint, ALenum, ALint* value ) AL_API_NOEXCEPT {
	ZeroValues( value, 1 );
}

void AL_APIENTRY alGetBufferi( ALuint, ALenum, ALint* value ) AL_API_NOEXCEPT {
	ZeroValues( value, 1 );
}

const ALchar* AL_APIENTRY alGetString( ALenum ) AL_API_NOEXCEPT {
	return openalEmptyString;
}

ALboolean AL_APIENTRY alIsBuffer( ALuint ) AL_API_NOEXCEPT {
	return AL_FALSE;
}

ALboolean AL_APIENTRY alIsBufferFormatSupportedSOFT( ALenum ) AL_API_NOEXCEPT {
	return AL_FALSE;
}

ALboolean AL_APIENTRY alIsExtensionPresent( const ALchar* ) AL_API_NOEXCEPT {
	return AL_FALSE;
}

ALboolean AL_APIENTRY alIsSource( ALuint ) AL_API_NOEXCEPT {
	return AL_FALSE;
}

void AL_APIENTRY alListenerf( ALenum, ALfloat ) AL_API_NOEXCEPT {
}

void AL_APIENTRY alSource3f( ALuint, ALenum, ALfloat, ALfloat, ALfloat ) AL_API_NOEXCEPT {
}

void AL_APIENTRY alSource3i( ALuint, ALenum, ALint, ALint, ALint ) AL_API_NOEXCEPT {
}

void AL_APIENTRY alSourcef( ALuint, ALenum, ALfloat ) AL_API_NOEXCEPT {
}

void AL_APIENTRY alSourcei( ALuint, ALenum, ALint ) AL_API_NOEXCEPT {
}

void AL_APIENTRY alSourcePause( ALuint ) AL_API_NOEXCEPT {
}

void AL_APIENTRY alSourcePlay( ALuint ) AL_API_NOEXCEPT {
}

void AL_APIENTRY alSourceQueueBuffers( ALuint, ALsizei, const ALuint* ) AL_API_NOEXCEPT {
}

void AL_APIENTRY alSourceStop( ALuint ) AL_API_NOEXCEPT {
}

void AL_APIENTRY alSourceRewind( ALuint ) AL_API_NOEXCEPT {
}

void AL_APIENTRY alSpeedOfSound( ALfloat ) AL_API_NOEXCEPT {
}

void AL_APIENTRY alSourceUnqueueBuffers( ALuint, const ALsizei count, ALuint* buffers ) AL_API_NOEXCEPT {
	ZeroValues( buffers, count );
}

ALCboolean ALC_APIENTRY alcCloseDevice( ALCdevice* ) ALC_API_NOEXCEPT {
	return ALC_FALSE;
}

ALCcontext* ALC_APIENTRY alcCreateContext( ALCdevice*, const ALCint* ) ALC_API_NOEXCEPT {
	return NULL;
}

void ALC_APIENTRY alcDestroyContext( ALCcontext* ) ALC_API_NOEXCEPT {
}

ALCcontext* ALC_APIENTRY alcGetCurrentContext( void ) ALC_API_NOEXCEPT {
	return NULL;
}

ALCenum ALC_APIENTRY alcGetError( ALCdevice* ) ALC_API_NOEXCEPT {
	return ALC_NO_ERROR;
}

void ALC_APIENTRY alcGetIntegerv( ALCdevice*, ALCenum, const ALCsizei count, ALCint* values ) ALC_API_NOEXCEPT {
	ZeroValues( values, count );
}

ALCvoid* ALC_APIENTRY alcGetProcAddress( ALCdevice*, const ALCchar* ) ALC_API_NOEXCEPT {
	return NULL;
}

const ALCchar* ALC_APIENTRY alcGetString( ALCdevice*, ALCenum ) ALC_API_NOEXCEPT {
	return openalEmptyList;
}

ALCboolean ALC_APIENTRY alcIsExtensionPresent( ALCdevice*, const ALCchar* ) ALC_API_NOEXCEPT {
	return ALC_FALSE;
}

ALCboolean ALC_APIENTRY alcMakeContextCurrent( ALCcontext* context ) ALC_API_NOEXCEPT {
	return context == NULL ? ALC_TRUE : ALC_FALSE;
}

ALCdevice* ALC_APIENTRY alcOpenDevice( const ALCchar* ) ALC_API_NOEXCEPT {
	return NULL;
}

} // extern "C"
