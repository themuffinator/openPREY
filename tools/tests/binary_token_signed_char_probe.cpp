// Preserved from openQ4-game; Quake 4 SDK EULA. See docs/dev/game-test-coverage.md.
#include <cstdint>
#include <cstring>
#include <type_traits>

template <typename T>
static T ReadValue( const unsigned char raw ) {
	T value;
	static_assert( sizeof( value ) == sizeof( raw ), "binary-token byte values must occupy one byte" );
	std::memcpy( &value, &raw, sizeof( value ) );
	return value;
}

static bool FitsSignedByte( const int value ) {
	const signed char byteValue = static_cast<signed char>( value );
	return byteValue == value;
}

static int DecodeSignedByte( const unsigned char raw ) {
	const unsigned int tokenStorage = ReadValue<signed char>( raw );
	return static_cast<int>( tokenStorage );
}

int main() {
	static_assert( sizeof( signed char ) == 1, "binary tokens require eight-bit signed bytes" );
	static_assert( sizeof( unsigned int ) == 4, "binary token integer storage must remain 32-bit" );

#if defined( OPENQ4_EXPECT_UNSIGNED_PLAIN_CHAR )
	static_assert( !std::is_signed<char>::value,
		"the unsigned-plain-char regression mode must emulate Linux AArch64" );
#endif

	if ( FitsSignedByte( -129 ) || !FitsSignedByte( -128 ) || !FitsSignedByte( -1 ) ||
			!FitsSignedByte( 0 ) || !FitsSignedByte( 127 ) || FitsSignedByte( 128 ) ) {
		return 1;
	}

	if ( DecodeSignedByte( 0x80u ) != -128 || DecodeSignedByte( 0xffu ) != -1 ||
			DecodeSignedByte( 0x00u ) != 0 || DecodeSignedByte( 0x7fu ) != 127 ) {
		return 2;
	}

	return 0;
}
