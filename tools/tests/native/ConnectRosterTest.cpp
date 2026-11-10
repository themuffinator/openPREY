// The connect response's roster block: what a joining client's loading
// screen lists before the map loads. The block arrives from a server the
// client has not trusted yet, so every malformed form must decode to nothing.
#include "src/framework/async/ConnectRoster.h"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

using namespace idConnectRoster;

static int checks = 0, failures = 0;

static void Check( bool condition, const char *label ) {
	++checks;
	if ( !condition ) {
		std::fprintf( stderr, "connect roster: %s\n", label );
		failures++;
	}
}

static roster_t Sample() {
	roster_t roster;
	std::memset( &roster, 0, sizeof( roster ) );
	roster.connecting = 2;
	const struct { std::uint8_t slot, flags, team; const char *name; } players[] = {
		{ 0, 0, 0, "^1Kane" }, { 3, FLAG_BOT, 1, "Makron" }, { 7, FLAG_SPECTATOR, 0, "Watcher" }, { 31, FLAG_BOT, 1, "" } };
	for ( const auto &player : players ) {
		entry_t &entry = roster.entries[ roster.count++ ];
		entry.slot = player.slot;
		entry.flags = player.flags;
		entry.team = player.team;
		std::memcpy( entry.name, player.name, std::strlen( player.name ) + 1 );
	}
	return roster;
}

static std::vector<std::uint8_t> Encoded( const roster_t &roster ) {
	std::vector<std::uint8_t> block( MAX_BYTES );
	block.resize( Encode( roster, block.data(), block.size() ) );
	return block;
}

static bool Empty( const roster_t &roster ) {
	return roster.count == 0 && roster.connecting == 0;
}

int main() {
	// A round trip keeps every field and the order.
	const roster_t sample = Sample();
	const std::vector<std::uint8_t> block = Encoded( sample );
	Check( block.size() == 3 + 4 * 3 + ( 7 + 7 + 8 + 1 ), "the block is the header, the fields and the terminated names" );
	Check( block[ 0 ] == VERSION && block[ 1 ] == 2 && block[ 2 ] == 4, "the header carries the version and the counts" );
	roster_t decoded;
	Check( Decode( block.data(), block.size(), decoded ), "a whole block decodes" );
	Check( decoded.connecting == 2 && decoded.count == 4, "the counts survive" );
	for ( int i = 0; i < sample.count; i++ ) {
		const entry_t &a = sample.entries[ i ], &b = decoded.entries[ i ];
		Check( a.slot == b.slot && a.flags == b.flags && a.team == b.team && !std::strcmp( a.name, b.name ), "each entry survives" );
	}
	// Every truncation decodes to nothing, never a partial roster.
	for ( std::size_t size = 0; size < block.size(); size++ ) {
		roster_t partial = Sample();
		Check( !Decode( block.data(), size, partial ) && Empty( partial ), "a truncated block decodes to nothing" );
	}
	// Bytes left over, another version, and counts or fields out of range.
	std::vector<std::uint8_t> bad = block;
	bad.push_back( 0 );
	Check( !Decode( bad.data(), bad.size(), decoded ) && Empty( decoded ), "trailing bytes are refused" );
	bad = block; bad[ 0 ] = VERSION + 1;
	Check( !Decode( bad.data(), bad.size(), decoded ), "another version is refused" );
	bad = block; bad[ 1 ] = MAX_ENTRIES + 1;
	Check( !Decode( bad.data(), bad.size(), decoded ), "too many connecting is refused" );
	bad = block; bad[ 2 ] = MAX_ENTRIES + 1;
	Check( !Decode( bad.data(), bad.size(), decoded ), "too many entries is refused" );
	bad = block; bad[ 3 ] = MAX_ENTRIES;
	Check( !Decode( bad.data(), bad.size(), decoded ), "a slot past the clients is refused" );
	bad = block; bad[ 4 ] = 4;
	Check( !Decode( bad.data(), bad.size(), decoded ), "an unknown flag is refused" );
	bad = block; bad[ 5 ] = 2;
	Check( !Decode( bad.data(), bad.size(), decoded ), "a third team is refused" );
	bad = block; bad.pop_back();
	Check( !Decode( bad.data(), bad.size(), decoded ), "an unterminated name is refused" );
	Check( !Decode( nullptr, 3, decoded ), "no data decodes to nothing" );
	// Names: the longest fits, one byte more is refused both ways.
	roster_t names;
	std::memset( &names, 0, sizeof( names ) );
	names.count = 1;
	std::memset( names.entries[ 0 ].name, 'x', MAX_NAME_BYTES );
	std::vector<std::uint8_t> longest = Encoded( names );
	Check( longest.size() == 3 + 3 + MAX_NAME_BYTES + 1 && Decode( longest.data(), longest.size(), decoded ) &&
		std::strlen( decoded.entries[ 0 ].name ) == static_cast<std::size_t>( MAX_NAME_BYTES ), "the longest name round-trips" );
	std::vector<std::uint8_t> longer = longest;
	longer.insert( longer.begin() + 6, 'x' );
	Check( !Decode( longer.data(), longer.size(), decoded ), "a name past the limit is refused" );
	std::memset( names.entries[ 0 ].name, 'x', sizeof( names.entries[ 0 ].name ) );
	std::uint8_t out[ MAX_BYTES ];
	Check( Encode( names, out, sizeof( out ) ) == 0, "an unterminated name does not encode" );
	// A full roster fits the largest block, and nothing encodes past capacity.
	roster_t full;
	std::memset( &full, 0, sizeof( full ) );
	full.count = MAX_ENTRIES;
	for ( int i = 0; i < MAX_ENTRIES; i++ ) {
		full.entries[ i ].slot = static_cast<std::uint8_t>( i );
		std::memset( full.entries[ i ].name, 'n', MAX_NAME_BYTES );
	}
	const std::size_t fullBytes = Encode( full, out, sizeof( out ) );
	Check( fullBytes == MAX_BYTES && Decode( out, fullBytes, decoded ) && decoded.count == MAX_ENTRIES, "a full roster fills the largest block" );
	Check( Encode( full, out, sizeof( out ) - 1 ) == 0 && Encode( sample, out, 2 ) == 0, "a block past capacity does not encode" );
	full.count = MAX_ENTRIES + 1;
	Check( Encode( full, out, sizeof( out ) ) == 0, "too many entries do not encode" );
	roster_t none;
	std::memset( &none, 0, sizeof( none ) );
	const std::vector<std::uint8_t> empty = Encoded( none );
	Check( empty.size() == 3 && Decode( empty.data(), empty.size(), decoded ) && Empty( decoded ), "an empty game encodes its header" );
	if ( failures ) {
		std::fprintf( stderr, "connect roster: %d of %d checks failed\n", failures, checks );
		return 1;
	}
	std::printf( "connect roster: %d checks passed\n", checks );
	return 0;
}
