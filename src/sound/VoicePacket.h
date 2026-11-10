// Copyright (C) 2026 openQ4 contributors. SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENQ4_VOICE_PACKET_H
#define OPENQ4_VOICE_PACKET_H

#include <algorithm>
#include <cstddef>
#include <cstdint>

// Versioned, independently decodable 20 ms frames. Mu-law companding at 8 kHz
// keeps the whole frame below the game's old 382-byte voice limit, without an
// allocator or an inter-packet codec dependency (64 kbit/s of narrowband audio).
// This is an openQ4 packet envelope, not RTP. Never treat audio as routing authority.
namespace oq4voice {
constexpr int Rate = 8000;
constexpr int FrameMsec = 20;
constexpr int Samples = Rate * FrameMsec / 1000;
constexpr int HeaderBytes = 9;
constexpr int PacketBytes = HeaderBytes + Samples;
constexpr int MaxQueuedFrames = 4;
constexpr int MaxAgeMsec = 120;
constexpr int Version = 1;

inline uint32_t Read32( const uint8_t* data ) {
	return uint32_t( data[0] ) | ( uint32_t( data[1] ) << 8 ) |
		( uint32_t( data[2] ) << 16 ) | ( uint32_t( data[3] ) << 24 );
}
inline void Write32( uint8_t* data, uint32_t value ) {
	for ( int i = 0; i < 4; ++i ) data[i] = uint8_t( value >> ( i * 8 ) );
}
inline bool Valid( const uint8_t* data, int size ) {
	return data && size == PacketBytes && data[0] == Version;
}
inline uint8_t Compress( int16_t input ) {
	const int sign = input < 0 ? 0x80 : 0;
	int magnitude = (std::min)( input < 0 ? -int( input ) : int( input ), 32635 ) + 132;
	int exponent = 0;
	for ( int threshold = 256; magnitude >= threshold && exponent < 7; threshold <<= 1 ) ++exponent;
	return uint8_t( ~( sign | ( exponent << 4 ) | ( ( magnitude >> ( exponent + 3 ) ) & 15 ) ) );
}
inline int16_t Expand( uint8_t input ) {
	const int code = uint8_t( ~input );
	const int magnitude = ( ( ( code & 15 ) * 8 + 132 ) << ( ( code >> 4 ) & 7 ) ) - 132;
	return int16_t( code & 0x80 ? -magnitude : magnitude );
}
inline void Encode( const int16_t* pcm, uint32_t sequence, uint32_t time, uint8_t* packet ) {
	packet[0] = Version;
	Write32( packet + 1, sequence );
	Write32( packet + 5, time );
	for ( int i = 0; i < Samples; ++i ) packet[HeaderBytes + i] = Compress( pcm[i] );
}
inline bool Decode( const uint8_t* packet, int size, int16_t* pcm ) {
	if ( !Valid( packet, size ) ) return false;
	for ( int i = 0; i < Samples; ++i ) pcm[i] = Expand( packet[HeaderBytes + i] );
	return true;
}

// Per authenticated sender, reset on connection/entity generation changes. A
// three-frame burst permits ordinary scheduling jitter, never a second of speech
// released all at once. The offset measures added delay, not absolute clock skew.
struct Admission {
	bool initialized = false;
	uint32_t sequence = 0, lastArrival = 0, lastAccepted = 0, clockOffset = 0;
	int creditMsec = 3 * FrameMsec;
	uint32_t driftRemainder = 0;

	bool Accept( const uint8_t* packet, int size, uint32_t now ) {
		if ( !Valid( packet, size ) ) return false;
		const uint32_t next = Read32( packet + 1 );
		const uint32_t offset = now - Read32( packet + 5 );
		if ( initialized ) {
			const uint32_t advance = next - sequence;
			if ( advance == 0 || advance >= 0x80000000u ) return false;
			const uint32_t elapsed = now - lastArrival;
			creditMsec = (std::min)( 3 * FrameMsec, creditMsec + int( (std::min)( elapsed, 1000u ) ) );
			lastArrival = now;
			// Keep the latency baseline across PTT gaps. Relearning it after an
			// idle second would admit a delayed backlog as a fresh utterance.
			if ( offset - clockOffset >= 0x80000000u ) clockOffset = offset;
			if ( offset - clockOffset > MaxAgeMsec || creditMsec < FrameMsec ) return false;
			// Independent monotonic clocks drift. Slew the baseline upward by
			// at most 2 ms per second of accepted, active traffic; otherwise a
			// slower sender eventually exceeds MaxAgeMsec forever. Do not bank
			// silent/stalled time or learn from rejected delayed frames. A lower
			// observed delay still resets the baseline immediately above.
			const uint32_t activeElapsed = now - lastAccepted;
			if ( activeElapsed <= MaxAgeMsec ) {
				driftRemainder += activeElapsed;
				clockOffset += (std::min)( offset - clockOffset, driftRemainder / 500u );
				driftRemainder %= 500u;
			} else {
				driftRemainder = 0;
			}
		} else {
			clockOffset = offset;
			lastArrival = now;
		}
		initialized = true;
		lastAccepted = now;
		sequence = next;
		creditMsec -= FrameMsec;
		return true;
	}
};

// Observation only; never feeds admission. Reports how far above the learned
// baseline an accepted frame arrived (the bounded added delay) and how far the
// baseline itself has moved since the sender's first frame (observed drift).
// The interval maximum is reset by whoever reports it.
struct AdmissionStats {
	uint32_t accepted = 0, rejected = 0, firstOffset = 0;
	uint32_t lastAdded = 0, maxAdded = 0, intervalMaxAdded = 0;
	bool haveFirst = false;

	void Record( const Admission& admission, const uint8_t* packet, int size, uint32_t now, bool ok ) {
		if ( !ok || !Valid( packet, size ) ) { ++rejected; return; }
		++accepted;
		if ( !haveFirst ) { firstOffset = admission.clockOffset; haveFirst = true; }
		lastAdded = ( now - Read32( packet + 5 ) ) - admission.clockOffset;
		maxAdded = (std::max)( maxAdded, lastAdded );
		intervalMaxAdded = (std::max)( intervalMaxAdded, lastAdded );
	}
	int32_t BaselineShift( const Admission& admission ) const {
		return haveFirst ? int32_t( admission.clockOffset - firstOffset ) : 0;
	}
};

struct Frame {
	int16_t pcm[Samples] = {};
	uint32_t time = 0;
};

// The capture callback owns no unbounded container. The stream lock serializes
// callback Push and main-thread Pop; a stalled game overwrites its oldest audio.
struct CaptureQueue {
	Frame frames[MaxQueuedFrames];
	int begin = 0, count = 0;
	uint32_t dropped = 0;
	void Push( const Frame& frame ) {
		if ( count == MaxQueuedFrames ) {
			begin = ( begin + 1 ) % MaxQueuedFrames;
			--count;
			++dropped;
		}
		frames[( begin + count++ ) % MaxQueuedFrames] = frame;
	}
	bool Pop( Frame& frame, uint32_t now ) {
		while ( count ) {
			frame = frames[begin];
			begin = ( begin + 1 ) % MaxQueuedFrames;
			--count;
			if ( now - frame.time <= MaxAgeMsec ) return true;
			++dropped;
		}
		return false;
	}
};
}
#endif
