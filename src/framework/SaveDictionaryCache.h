// Copyright (C) 2026 DarkMatter Productions
#ifndef OPENQ4_SAVE_DICTIONARY_CACHE_H
#define OPENQ4_SAVE_DICTIONARY_CACHE_H

#include <array>
#include <cstdint>
#include <cstring>
#include <utility>
#include <vector>

#include "../idlib/ContentIdentity.h"
#include "SaveDictionaryEncoding.h"

// Bounded capture of the shared encoder. Oversized dictionaries continue on
// the ordinary save path and are never retained by the cache.
class SaveDictionaryRecord {
public:
	explicit SaveDictionaryRecord( bool enabled ) : enabled( enabled ) {}
	bool Append( const unsigned char *source, size_t count ) {
		if ( !enabled || count == 0 ) return enabled;
		if ( count > Limit - bytes.size() ) {
			enabled = false;
			std::vector<unsigned char>().swap( bytes );
			return false;
		}
		const size_t required = bytes.size() + count;
		if ( required > bytes.capacity() ) {
			size_t capacity = 256;
			while ( capacity < required ) capacity *= 2;
			bytes.reserve( capacity );
		}
		bytes.insert( bytes.end(), source, source + count );
		return true;
	}
	std::vector<unsigned char> &Bytes() { return bytes; }
	bool Valid() const { return enabled; }
private:
	static constexpr size_t Limit = 64 * 1024;
	bool enabled;
	std::vector<unsigned char> bytes;
};

// Main-thread save cache. A dictionary mutation or destruction detaches the
// observer before its bytes can be reused. Addresses only select a bucket.
template<class Dictionary, size_t Slots = 4096>
class SaveDictionaryCache {
public:
	static constexpr size_t MaxPayloadBytes = 64 * 1024;
	static constexpr size_t DefaultBudget = 16 * 1024 * 1024;
	static_assert( Slots >= 4 && ( Slots & ( Slots - 1 ) ) == 0, "power-of-two four-way cache" );

	explicit SaveDictionaryCache( size_t budget = DefaultBudget ) : budget( budget ) {}
	SaveDictionaryCache( const SaveDictionaryCache& ) = delete;
	SaveDictionaryCache& operator=( const SaveDictionaryCache& ) = delete;

	const std::vector<unsigned char> *Find( const Dictionary &dict ) {
		const uintptr_t key = reinterpret_cast<uintptr_t>( &dict );
		const size_t base = Bucket( key );
		for ( size_t i = base; i < base + 4; ++i ) {
			Entry &entry = entries[i];
			if ( !entry.valid || entry.key != key ) continue;
			if ( entry.pairs != dict.GetNumKeyVals() || !entry.observer.Matches( dict.ContentIdentity() ) ) {
				Erase( entry );
				return nullptr;
			}
			entry.touched = ++clock;
			return entry.pending ? nullptr : &entry.bytes;
		}
		return nullptr;
	}

	// A miss registers only the source's lifetime/content identity. Encoding
	// and allocation happen on later game frames, never in the save writer.
	void Queue( const Dictionary &dict ) {
		if ( sizeof( *this ) > budget || dict.GetNumKeyVals() <= 0 || (size_t)dict.GetNumKeyVals() > MaxPayloadBytes / 8 ) return;
		const uintptr_t key = reinterpret_cast<uintptr_t>( &dict );
		Entry *slot = SelectSlot( key );
		if ( slot->valid && slot->key == key && slot->observer.Matches( dict.ContentIdentity() ) ) return;
		Erase( *slot );
		slot->key = key;
		slot->pairs = dict.GetNumKeyVals();
		slot->touched = ++clock;
		slot->source = &dict;
		slot->observer.Attach( dict.ContentIdentity() );
		slot->valid = slot->pending = true;
		++count;
		++pending;
		deferOnePass = true;
	}

	struct Population {
		size_t records = 0, discarded = 0, bytes = 0, inspected = 0;
	};
	// At most 24 records, 128 KiB of attempted payload and 128 slots per call.
	// The caller also supplies a time deadline. One record can overrun the byte
	// or time limit; it is itself bounded to 64 KiB plus one 16 KiB chunk.
	template<class MayContinue>
	Population Populate( size_t maxStringBytes, MayContinue mayContinue ) {
		Population result;
		if ( deferOnePass ) { deferOnePass = false; return result; }
		while ( pending && result.inspected < 128 && result.records < 24
				&& result.bytes < 128 * 1024 && mayContinue() ) {
			Entry &entry = entries[populationCursor++ & (Slots - 1)];
			++result.inspected;
			if ( !entry.valid || !entry.pending ) continue;
			if ( !entry.observer.IsAttached() ) {
				Erase( entry );
				++result.discarded;
				continue;
			}
			// IsAttached is checked before the source is dereferenced. The
			// source and observer can only change on this same game thread.
			const Dictionary &dict = *entry.source;
			SaveDictionaryRecord record( true );
			size_t invalidLength = 0;
			const bool complete = EncodeSaveDictionaryPayload( dict, maxStringBytes,
				[&]( const unsigned char *data, size_t size ) {
					result.bytes += size;
					return record.Append( data, size );
				}, invalidLength );
			++result.records;
			if ( complete && record.Valid() ) {
				Store( dict, std::move( record.Bytes() ) );
			} else {
				Erase( entry );
				++result.discarded;
			}
		}
		return result;
	}

	void Store( const Dictionary &dict, std::vector<unsigned char> &&bytes ) {
		if ( dict.GetNumKeyVals() <= 0 || bytes.empty() || bytes.size() > MaxPayloadBytes
				|| bytes.capacity() > MaxPayloadBytes || !ValidPayload( bytes, dict.GetNumKeyVals() ) ) return;
		const uintptr_t key = reinterpret_cast<uintptr_t>( &dict );
		Entry *slot = SelectSlot( key );
		Erase( *slot );
		// One bounded record can exist while entries are evicted.
		slot->bytes = std::move( bytes );
		slot->charge = slot->bytes.capacity();
		if ( sizeof( *this ) > budget || slot->charge > budget - sizeof( *this ) ) {
			std::vector<unsigned char>().swap( slot->bytes );
			slot->charge = 0;
			return;
		}
		while ( resident + slot->charge > budget - sizeof( *this ) ) {
			Entry *oldest = nullptr;
			for ( Entry &entry : entries ) {
				if ( entry.valid && ( oldest == nullptr || entry.touched < oldest->touched ) ) oldest = &entry;
			}
			if ( oldest == nullptr ) break;
			Erase( *oldest );
		}
		slot->key = key;
		slot->pairs = dict.GetNumKeyVals();
		slot->touched = ++clock;
		slot->observer.Attach( dict.ContentIdentity() );
		slot->valid = true;
		resident += slot->charge;
		++count;
	}

	size_t ResidentBytes() const { return sizeof( *this ) + resident; }
	size_t Count() const { return count; }
	size_t Pending() const { return pending; }

private:
	struct Entry {
		idContentObserver observer;
		const Dictionary *source = nullptr;
		std::vector<unsigned char> bytes;
		uintptr_t key = 0;
		uint64_t touched = 0;
		size_t charge = 0;
		int pairs = 0;
		bool valid = false;
		bool pending = false;
	};
	Entry *SelectSlot( uintptr_t key ) {
		const size_t base = Bucket( key );
		Entry *slot = &entries[base];
		for ( size_t i = base; i < base + 4; ++i ) {
			Entry &candidate = entries[i];
			// Search all four entries before using an empty one, so an
			// earlier eviction cannot hide an existing pending registration.
			if ( candidate.valid && candidate.key == key ) return &candidate;
			if ( !candidate.valid || (slot->valid && candidate.touched < slot->touched) ) slot = &candidate;
		}
		return slot;
	}
	static bool ValidPayload( const std::vector<unsigned char> &bytes, int pairs ) {
		if ( (size_t)pairs > bytes.size() / 8 ) return false;
		size_t offset = 0;
		for ( int i = 0; i < pairs * 2; ++i ) {
			if ( bytes.size() - offset < 4 ) return false;
			uint32_t length = 0;
			for ( int b = 0; b < 4; ++b ) length |= (uint32_t)bytes[offset++] << (b * 8);
			if ( length > bytes.size() - offset ) return false;
			offset += length;
		}
		return offset == bytes.size();
	}
	static size_t Bucket( uintptr_t key ) {
		key ^= key >> 17;
		key ^= key >> 9;
		return ( ( key >> 4 ) & ( Slots / 4 - 1 ) ) * 4;
	}
	void Erase( Entry &entry ) {
		if ( !entry.valid ) return;
		resident -= entry.charge;
		--count;
		if ( entry.pending ) --pending;
		std::vector<unsigned char>().swap( entry.bytes );
		entry.observer.Clear();
		entry.valid = false;
		entry.pending = false;
		entry.source = nullptr;
		entry.charge = 0;
	}
	std::array<Entry, Slots> entries;
	size_t budget, resident = 0, count = 0, pending = 0, populationCursor = 0;
	uint64_t clock = 0;
	bool deferOnePass = false;
};

#endif
