#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <vector>

#define ID_INLINE inline
using byte = unsigned char;
using dword = std::uint32_t;
class idVec2;
class idVec3;
struct idVec4;
#include "src/idlib/math/Math.h"
const int idMath::INT_MAX = std::numeric_limits<int>::max();
template<int N> struct VectorStub {
	float values[N];
	int GetDimension() const { return N; }
	float &operator[]( int i ) { return values[i]; }
	float operator[]( int i ) const { return values[i]; }
};
class idVec3 : public VectorStub<3> {};
struct idVec4 : VectorStub<4> {};
struct idQuat : VectorStub<4> {};
struct idMat3 {
	idVec3 values[3];
	int GetDimension() const { return 9; }
	int GetVec3Dimension() const { return 3; }
	idVec3 &operator[]( int i ) { return values[i]; }
	const idVec3 &operator[]( int i ) const { return values[i]; }
};
struct netadr_t;
class idDict;
struct idStr {
	static int Length( const char *s ) { return static_cast<int>( std::strlen( s ) ); }
};
struct TestCommon {
	[[noreturn]] void FatalError( const char *, ... ) { throw std::runtime_error( "message error" ); }
	[[noreturn]] void Error( const char *, ... ) { throw std::runtime_error( "message error" ); }
	void Printf( const char *, ... ) {}
	void Warning( const char *, ... ) {}
};
namespace idLib { TestCommon instance; TestCommon *common = &instance; }
#include "BitMsgUnderTest.inc"

static int failures = 0;
static void Check( bool condition, const char *label ) {
	if ( !condition ) { std::fprintf( stderr, "%s\n", label ); ++failures; }
}

static void CheckDeltaBlock( int size, bool different, bool truncatedBase ) {
	std::vector<byte> original( size, 0x47 ), replacement( size, different ? 0x82 : 0x47 );
	std::vector<byte> packet( size + 16 ), output( size, 0xcc ), rebuilt( size + 16 );
	idBitMsg base, delta, newBase;
	const int baseSize = truncatedBase ? size / 2 : size;
	base.Init( baseSize ? original.data() : nullptr, baseSize );
	base.SetSize( baseSize );
	base.BeginReading();
	delta.Init( packet.data(), static_cast<int>( packet.size() ) );
	delta.BeginWriting();
	idBitMsgDelta writer;
	writer.InitWriting( &base, nullptr, &delta );
	writer.WriteData( replacement.data(), size );
	Check( writer.HasChanged() == ( different || truncatedBase ), "delta change detection" );
	Check( delta.GetSize() == ( different || truncatedBase ? size + 1 : 1 ), "delta wire size" );
	base.BeginReading();
	delta.BeginReading();
	newBase.Init( rebuilt.data(), static_cast<int>( rebuilt.size() ) );
	newBase.BeginWriting();
	idBitMsgDelta reader;
	reader.InitReading( &base, &newBase, &delta );
	reader.ReadData( output.data(), size );
	Check( !reader.IsReadOverflowed() && output == replacement, "delta block round trip" );
	Check( newBase.GetSize() == size && std::equal( replacement.begin(), replacement.end(), rebuilt.begin() ), "rebuilt delta base" );
}

int main( int argc, char ** ) {
	byte storage[64] = {};
	idBitMsg msg;
	msg.Init( storage, sizeof( storage ) );
	msg.BeginWriting();
	msg.WriteString( "discard this" );
	msg.WriteByte( 37 );
	msg.BeginReading();
	char guard = 'x';
	Check( msg.ReadString( &guard, 0 ) == 0 && guard == 'x', "zero-capacity string read wrote outside the buffer" );
	Check( msg.ReadByte() == 37, "discarded string left the cursor misaligned" );
	msg.BeginReading();
	char shortText[3];
	msg.ReadString( shortText, sizeof( shortText ) );
	Check( std::strcmp( shortText, "di" ) == 0 && msg.ReadByte() == 37, "truncated string alignment" );
	msg.ReadLong();
	byte unread[4] = { 1, 2, 3, 4 };
	msg.ReadData( unread, sizeof( unread ) );
	Check( unread[0] == 0 && unread[3] == 0, "an exhausted read left stale destination data" );
	int count, bit;
	msg.SaveReadState( count, bit );
	msg.BeginReading();
	msg.RestoreReadState( count, bit );
	Check( msg.IsReadOverflowed(), "restoring read state lost overflow" );
	if ( argc > 1 ) { return failures ? 1 : 0; }

	msg.BeginWriting();
	msg.WriteBits( 5, 3 ); msg.WriteData( nullptr, 0 ); msg.WriteBits( 1, 1 );
	msg.BeginReading();
	Check( msg.ReadBits( 3 ) == 5, "prefix before empty data block" );
	msg.ReadData( nullptr, 0 );
	Check( msg.ReadBits( 1 ) == 1, "empty data blocks must retain byte alignment" );

	msg.BeginWriting();
	msg.WriteString( "zero", 0 );
	Check( msg.GetSize() == 1 && storage[0] == 0, "zero string limit must encode an empty string" );
	msg.WriteData( nullptr, 0 );
	msg.BeginReading();
	msg.ReadString( nullptr, 0 );
	Check( msg.GetReadCount() == 1 && !msg.IsReadOverflowed(), "null destination string discard" );
	for ( int length : { -1, std::numeric_limits<int>::min(), std::numeric_limits<int>::max() } ) {
		try { msg.WriteData( storage, length ); Check( false, "invalid write length accepted" ); }
		catch ( const std::runtime_error & ) {}
	}
	for ( int size : { 0, 1, 1023, 1024, 1025, 8192 } ) {
		CheckDeltaBlock( size, false, false );
		if ( size ) { CheckDeltaBlock( size, true, false ); CheckDeltaBlock( size, false, true ); }
	}
	// An unchanged field cannot be reconstructed from a truncated base.
	byte baseBytes[2] = { 9, 8 }, deltaBytes[1] = { 0 }, output[4] = {};
	idBitMsg base, delta;
	base.Init( baseBytes, 2 ); base.SetSize( 2 ); base.BeginReading();
	delta.Init( deltaBytes, 1 ); delta.SetSize( 1 ); delta.BeginReading();
	idBitMsgDelta reader;
	reader.InitReading( &base, nullptr, &delta ); reader.ReadData( output, 4 );
	Check( reader.IsReadOverflowed() && output[0] == 9 && output[1] == 8 && output[2] == 0 && output[3] == 0, "truncated base rejection and initialized output" );
	if ( !failures ) { std::puts( "bit-message bounds, cursor and large delta-block tests passed" ); }
	return failures ? 1 : 0;
}
