/*
===========================================================================

Doom 3 BFG Edition GPL Source Code
Copyright (C) 1993-2012 id Software LLC, a ZeniMax Media company.
Copyright (C) 2013 Robert Beckebans

This file is part of the Doom 3 BFG Edition GPL Source Code ("Doom 3 BFG Edition Source Code").

Doom 3 BFG Edition Source Code is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Doom 3 BFG Edition Source Code is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Doom 3 BFG Edition Source Code.  If not, see <http://www.gnu.org/licenses/>.

In addition, the Doom 3 BFG Edition Source Code is also subject to certain additional terms. You should have received a copy of these additional terms immediately following the terms and conditions of the GNU General Public License which accompanied the Doom 3 BFG Edition Source Code.  If not, please request a copy in writing from id Software at the address below.

If you have questions concerning this license or the applicable additional terms, you may contact in writing id Software LLC, c/o ZeniMax Media Inc., Suite 120, Rockville, Maryland 20850 USA.

===========================================================================
*/
#ifndef __SOUNDVOICE_H__
#define __SOUNDVOICE_H__

/*
================================================
idSoundVoice_Base
================================================
*/

class idSoundVoice_Base
{
public:
	idSoundVoice_Base();

	static void InitSurround( int outputChannels, int channelMask );

	void		CalculateSurround( int srcChannels, float pLevelMatrix[ MAX_CHANNELS_PER_VOICE * MAX_CHANNELS_PER_VOICE ], float scale );

	// RB begin
	virtual void	SetPosition( const idVec3& p )
	{
		if( FLOAT_IS_NAN( p.x ) || FLOAT_IS_NAN( p.y ) || FLOAT_IS_NAN( p.z ) )
		{
			position.Zero();
		}
		else
		{
			position = p;
		}
	}

	virtual void	SetVelocity( const idVec3& v )
	{
		if( FLOAT_IS_NAN( v.x ) || FLOAT_IS_NAN( v.y ) || FLOAT_IS_NAN( v.z ) )
		{
			velocity.Zero();
		}
		else
		{
			velocity = v;
		}
	}

	virtual void	SetGain( float g )
	{
		gain = ( FLOAT_IS_NAN( g ) || g <= 0.0f ) ? 0.0f : idMath::ClampFloat( 0.0f, 16.0f, g );
	}

	virtual void	SetPitch( float p )
	{
		pitch = ( FLOAT_IS_NAN( p ) || p <= 0.0f ) ? 1.0f : idMath::ClampFloat( 0.01f, 64.0f, p );
	}

	virtual void	SetWetLevel( float wet )
	{
		wetLevel = FLOAT_IS_NAN( wet ) ? 0.0f : idMath::ClampFloat( 0.0f, 1.0f, wet );
	}

	virtual void	SetDryLevel( float dry )
	{
		dryLevel = FLOAT_IS_NAN( dry ) ? 1.0f : idMath::ClampFloat( 0.0f, 1.0f, dry );
	}
	// RB end

	void		SetCenterChannel( float c )
	{
		centerChannel = FLOAT_IS_NAN( c ) ? 0.0f : idMath::ClampFloat( 0.0f, 1.0f, c );
	}

	virtual void	SetInnerRadius( float r )
	{
		innerRadius = ( FLOAT_IS_NAN( r ) || r <= 0.0f ) ? 0.0f : r;
	}

	// Sends the gain, filter and reverb state gathered by this frame's setters
	// to the hardware in one pass.
	virtual void	CommitMix() {}
	void		SetChannelMask( uint32 mask )
	{
		channelMask = mask;
	}

	const idSoundSample* GetCurrentSample();

	// Controls portal/wall obstruction, where 0.0f = clear, 1.0f = fully obstructed
	virtual void	SetOcclusion( float f )
	{
		occlusion = FLOAT_IS_NAN( f ) ? 0.0f : idMath::ClampFloat( 0.0f, 1.0f, f );
	}

	// Controls listener/world muffling effects such as enviro-suit filtering
	virtual void	SetEnvironmentMuffle( float f )
	{
		environmentMuffle = FLOAT_IS_NAN( f ) ? 0.0f : idMath::ClampFloat( 0.0f, 1.0f, f );
	}

	// Retail EAX source state: the reverb slot of the sound's own portal area
	// (-1 when no slot holds it), EAXSOURCE_ROOM and EAXSOURCE_OCCLUSION in
	// millibels. As on retail's EAX path only mono voices reach the reverb.
	// Returns true when the routing changed.
	virtual bool	SetReverbSource( int areaSlot, int roomMB, int occlusionMB, bool mono )
	{
		soundReverbSourceSends_t sends;
		SoundReverb_SourceSends( roomMB, occlusionMB, sends );
		if( !mono )
		{
			areaSlot = -1;
			sends.directGain = sends.directGainHF = 1.0f;
			sends.primaryGain = sends.areaGain = 0.0f;
		}
		const bool changed = areaSlot != reverbAreaSlot ||
			sends.directGain != eaxDirectGain || sends.directGainHF != eaxDirectGainHF ||
			sends.primaryGain != eaxPrimaryGain || sends.primaryGainHF != eaxPrimaryGainHF ||
			sends.areaGain != eaxAreaGain || sends.areaGainHF != eaxAreaGainHF;
		reverbAreaSlot = areaSlot;
		eaxDirectGain = sends.directGain;
		eaxDirectGainHF = sends.directGainHF;
		eaxPrimaryGain = sends.primaryGain;
		eaxPrimaryGainHF = sends.primaryGainHF;
		eaxAreaGain = sends.areaGain;
		eaxAreaGainHF = sends.areaGainHF;
		return changed;
	}

	float		GetGain()
	{
		return gain;
	}
	float		GetPitch()
	{
		return pitch;
	}
	float		GetWetLevel() const
	{
		return wetLevel;
	}
	float		GetDryLevel() const
	{
		return dryLevel;
	}
	virtual bool	GetPlaybackLatencyMS( float& offsetMS, float& latencyMS ) const
	{
		offsetMS = 0.0f;
		latencyMS = 0.0f;
		return false;
	}

protected:
	idVec3		position;			// Position of the sound relative to listener
	idVec3		velocity;			// Velocity of the sound relative to listener
	float		gain;				// Volume (0-1)
	float		centerChannel;		// Value (0-1) which indicates how much of this voice goes to the center channel
	float		pitch;				// Pitch multiplier
	float		wetLevel;			// Aux send level (0-1)
	float		dryLevel;			// Direct path level (0-1)
	float		innerRadius;		// Anything closer than this is omni
	float		occlusion;			// How much of this sound is occluded (0-1)
	float		environmentMuffle;	// Listener/world muffling amount (0-1)
	int			reverbAreaSlot;		// Reverb slot of the sound's own area, -1 for none
	float		eaxDirectGain;		// Retail EAX source filters (SoundReverb_SourceSends)
	float		eaxDirectGainHF;
	float		eaxPrimaryGain;		// Send into the listener's (primary) reverb slot
	float		eaxPrimaryGainHF;
	float		eaxAreaGain;		// Send into the sound's own area slot
	float		eaxAreaGainHF;
	uint32		channelMask;		// Set to override the default channel mask

	// These are some setting used to do SSF_DISTANCE_BASED_STERO blending
	float		innerSampleRangeSqr;
	float		outerSampleRangeSqr;

	idList< idSoundSample*> samples;

	// These are constants which are initialized with InitSurround
	//-------------------------------------------------------------

	static idVec2 speakerPositions[idWaveFile::CHANNEL_INDEX_MAX];

	// This is to figure out which speakers are "next to" this one
	static int speakerLeft[idWaveFile::CHANNEL_INDEX_MAX];
	static int speakerRight[idWaveFile::CHANNEL_INDEX_MAX];

	// Number of channels in the output hardware
	static int dstChannels;

	// Mask indicating which speakers exist in the hardware configuration
	static int dstMask;

	// dstMap maps a destination channel to a speaker
	// invMap maps a speaker to a destination channel
	static int dstCenter;
	static int dstLFE;
	static int dstMap[MAX_CHANNELS_PER_VOICE];
	static int invMap[idWaveFile::CHANNEL_INDEX_MAX];

	// specifies what volume to specify for each channel when a speaker is omni
	static float omniLevel;
};

#endif
