// Copyright (C) 2026 openQ4 contributors. SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENQ4_VOICE_TRANSPORT_H
#define OPENQ4_VOICE_TRANSPORT_H
#include <cstdint>
#include <cstring>

namespace oq4voice {
constexpr int MaxWireFrame = 384;
constexpr int MaxTalkers = 3;
constexpr int MaxBatch = 1 + MaxTalkers * ( MaxWireFrame + 2 );

// A single server frame's exact-recipient mailbox. Keep the latest frame per
// speaker, flush after snapshots, and discard it regardless of send success.
// There is no retransmission or second-frame backlog behind reliable messages.
struct Mailbox {
	uint8_t data[MaxTalkers][MaxWireFrame];
	int size[MaxTalkers] = {};
	uint32_t time[MaxTalkers] = {};
	int count = 0;
	void Clear() { count = 0; }
	bool Push( const uint8_t* frame, int bytes, uint32_t now ) {
		if ( !frame || bytes < 1 || bytes > MaxWireFrame || frame[0] >= 32 ) return false;
		int slot = 0;
		while ( slot < count && data[slot][0] != frame[0] ) ++slot;
		if ( slot == MaxTalkers ) return false;
		if ( slot == count ) ++count;
		std::memcpy( data[slot], frame, bytes );
		size[slot] = bytes;
		time[slot] = now;
		return true;
	}
	int Take( uint8_t* output, uint32_t now ) {
		int length = 1;
		output[0] = 0;
		for ( int i = 0; i < count; ++i ) {
			if ( now - time[i] > 100 ) continue;
			output[length++] = uint8_t( size[i] );
			output[length++] = uint8_t( size[i] >> 8 );
			std::memcpy( output + length, data[i], size[i] );
			length += size[i];
			++output[0];
		}
		Clear();
		return output[0] ? length : 0;
	}
};

// Validate the entire envelope before exposing any contained frame to the game.
inline bool ValidBatch( const uint8_t* data, int size ) {
	if ( !data || size < 1 || size > MaxBatch || !data[0] || data[0] > MaxTalkers ) return false;
	int offset = 1;
	for ( int i = 0; i < data[0]; ++i ) {
		if ( size - offset < 2 ) return false;
		const int length = data[offset] | ( int( data[offset + 1] ) << 8 );
		offset += 2;
		if ( length < 1 || length > MaxWireFrame || size - offset < length || data[offset] >= 32 ) return false;
		offset += length;
	}
	return offset == size;
}
}
#endif
