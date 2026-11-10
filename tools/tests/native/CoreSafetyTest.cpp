#include "src/idlib/NumericString.h"
#include "src/idlib/StrAllocation.h"
#include "src/idlib/CryptoHash.h"
#include "src/idlib/PrivateCommand.h"
#include "src/framework/GameDirPolicy.h"
#include "src/framework/RemoteCVarPolicy.h"
#include "src/framework/async/Rcon2Protocol.h"
#include "src/sys/NetworkEndpoint.h"
#include "src/sys/URLPolicy.h"
#include "tools/tests/native/NetworkImpairmentCases.h"

#include <climits>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>

static int failures = 0;

static void ExpectDecimal( const char *text, const bool expected, const char *label ) {
	const bool actual = idNumericString::IsDecimal( text );
	if ( actual != expected ) {
		std::fprintf( stderr, "IsDecimal failed for %s: expected %d, got %d\n", label, expected, actual );
		failures++;
	}
}

static void ExpectBounded( const char *text, const int maximum, const bool expected,
		const int expectedValue, const char *label ) {
	int value = -7331;
	const bool actual = idNumericString::ParseUnsignedBounded( text, maximum, value );
	if ( actual != expected ) {
		std::fprintf( stderr, "ParseUnsignedBounded failed for %s: expected %d, got %d\n", label, expected, actual );
		failures++;
		return;
	}
	if ( actual && value != expectedValue ) {
		std::fprintf( stderr, "ParseUnsignedBounded value failed for %s: expected %d, got %d\n", label, expectedValue, value );
		failures++;
	}
	if ( !actual && value != -7331 ) {
		std::fprintf( stderr, "ParseUnsignedBounded modified output on failure for %s\n", label );
		failures++;
	}
}

static void ExpectAllocation( const bool condition, const char *label ) {
	if ( !condition ) {
		std::fprintf( stderr, "String allocation arithmetic failed for %s\n", label );
		failures++;
	}
}

static void ExpectPrivateToken( const char *command, const char *name,
		const bool expected, const char *label ) {
	const bool actual = idPrivateCommand::ContainsBoundedCaseInsensitiveToken( command, name );
	if ( actual != expected ) {
		std::fprintf( stderr, "Private command-token match failed for %s: expected %d, got %d\n",
			label, expected, actual );
		failures++;
	}
}

static int HexNibble( const char value ) {
	if ( value >= '0' && value <= '9' ) {
		return value - '0';
	}
	if ( value >= 'a' && value <= 'f' ) {
		return value - 'a' + 10;
	}
	if ( value >= 'A' && value <= 'F' ) {
		return value - 'A' + 10;
	}
	return -1;
}

static void ExpectCryptoBytes( const std::uint8_t *actual, const std::size_t bytes,
		const char *expectedHex, const char *label ) {
	if ( std::strlen( expectedHex ) != bytes * 2 ) {
		std::fprintf( stderr, "Invalid expected crypto vector for %s\n", label );
		failures++;
		return;
	}
	for ( std::size_t index = 0; index < bytes; ++index ) {
		const int high = HexNibble( expectedHex[ index * 2 ] );
		const int low = HexNibble( expectedHex[ index * 2 + 1 ] );
		if ( high < 0 || low < 0 || actual[ index ] != static_cast<std::uint8_t>( ( high << 4 ) | low ) ) {
			std::fprintf( stderr, "Crypto vector failed for %s at byte %zu\n", label, index );
			failures++;
			return;
		}
	}
}

static void ExerciseCryptoVectors() {
	std::uint8_t digest[idCrypto::SHA256_DIGEST_BYTES];
	idCrypto::SHA256( nullptr, 0, digest );
	ExpectCryptoBytes( digest, sizeof( digest ),
		"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "SHA-256 empty" );
	idCrypto::SHA256( "abc", 3, digest );
	ExpectCryptoBytes( digest, sizeof( digest ),
		"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", "SHA-256 abc" );
	const char *twoBlocks = "abcdefghbcdefghicdefghijdefghijkefghijklfghijklmghijklmnhijklmno"
		"ijklmnopjklmnopqklmnopqrlmnopqrsmnopqrstnopqrstu";
	idCrypto::SHA256( twoBlocks, 112, digest );
	ExpectCryptoBytes( digest, sizeof( digest ),
		"cf5b16a778af8380036ce59e7b0492370b249b11e8f07a51afac45037afee9d1", "SHA-256 896-bit" );

	// SHA256 runs the processor's SHA instructions where it has them. Every
	// length across several blocks, at every word alignment, must agree with
	// the portable compression.
	std::printf( "SHA-256 implementation: %s\n", idCrypto::SHA256Implementation() );
	std::uint8_t pattern[ 1100 + 4 ];
	std::uint32_t seed = 0x9e3779b9u;
	for ( std::uint8_t &value : pattern ) {
		seed = seed * 1664525u + 1013904223u;
		value = static_cast<std::uint8_t>( seed >> 24 );
	}
	for ( std::size_t length = 0; length <= 1100; ++length ) {
		for ( std::size_t offset = 0; offset < 4; ++offset ) {
			std::uint8_t portable[idCrypto::SHA256_DIGEST_BYTES];
			idCrypto::SHA256( pattern + offset, length, digest );
			idCrypto::SHA256Portable( pattern + offset, length, portable );
			if ( std::memcmp( digest, portable, sizeof( digest ) ) != 0 ) {
				std::fprintf( stderr, "SHA-256 %s disagrees with portable at length %zu offset %zu\n",
					idCrypto::SHA256Implementation(), length, offset );
				failures++;
				length = 1100;
				break;
			}
		}
	}

	std::uint8_t hmacKey[20];
	std::memset( hmacKey, 0x0b, sizeof( hmacKey ) );
	idCrypto::HMACSHA256( hmacKey, sizeof( hmacKey ), "Hi There", 8, digest );
	ExpectCryptoBytes( digest, sizeof( digest ),
		"b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7", "RFC 4231 HMAC-SHA-256" );

	const char password[] = "password";
	const char salt[] = "salt";
	if ( !idCrypto::PBKDF2HMACSHA256( password, 8, salt, 4, 1, digest, sizeof( digest ) ) ) {
		std::fprintf( stderr, "PBKDF2 iteration-1 vector rejected\n" );
		failures++;
	} else {
		ExpectCryptoBytes( digest, sizeof( digest ),
			"120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b", "PBKDF2-HMAC-SHA-256 c=1" );
	}
	if ( !idCrypto::PBKDF2HMACSHA256( password, 8, salt, 4, 2, digest, sizeof( digest ) ) ) {
		std::fprintf( stderr, "PBKDF2 iteration-2 vector rejected\n" );
		failures++;
	} else {
		ExpectCryptoBytes( digest, sizeof( digest ),
			"ae4d0c95af6b46d32d0adff928f06dd02a303f8ef3c251dfd6e2d85a95474c43", "PBKDF2-HMAC-SHA-256 c=2" );
	}
	if ( !idCrypto::PBKDF2HMACSHA256( password, 8, salt, 4, 4096, digest, sizeof( digest ) ) ) {
		std::fprintf( stderr, "PBKDF2 iteration-4096 vector rejected\n" );
		failures++;
	} else {
		ExpectCryptoBytes( digest, sizeof( digest ),
			"c5e478d59288c841aa530db6845c4c8d962893a001ce4e11a4963873aa98134a", "PBKDF2-HMAC-SHA-256 c=4096" );
	}
	if ( idCrypto::PBKDF2HMACSHA256( password, 8, salt, 4, 0, digest, sizeof( digest ) ) ) {
		std::fprintf( stderr, "PBKDF2 accepted zero iterations\n" );
		failures++;
	}

	std::uint8_t verifier[idRcon2::VERIFIER_BYTES];
	std::uint8_t clientNonce[idRcon2::NONCE_BYTES];
	std::uint8_t serverNonce[idRcon2::NONCE_BYTES];
	std::uint8_t endpointBinding[idRcon2::ENDPOINT_BINDING_BYTES];
	std::uint8_t requestDigest[idRcon2::REQUEST_DIGEST_BYTES];
	std::uint8_t proof[idRcon2::PROOF_BYTES];
	for ( std::size_t index = 0; index < sizeof( verifier ); ++index ) {
		verifier[index] = static_cast<std::uint8_t>( index );
	}
	for ( std::size_t index = 0; index < sizeof( clientNonce ); ++index ) {
		clientNonce[index] = static_cast<std::uint8_t>( index );
		serverNonce[index] = static_cast<std::uint8_t>( index + 16 );
		endpointBinding[index] = static_cast<std::uint8_t>( index + 32 );
	}
	for ( std::size_t index = 0; index < sizeof( requestDigest ); ++index ) {
		requestDigest[index] = static_cast<std::uint8_t>( index + 48 );
	}
	idRcon2::ComputeProof( verifier, clientNonce, serverNonce, endpointBinding, requestDigest, proof );
	ExpectCryptoBytes( proof, sizeof( proof ),
		"b5a5953f5327179b21f82fb5fe6a158896c82df1126feb48b0c8ce96a2f65c20", "rcon2 proof domain" );
	idRcon2::HashRequest( "status", requestDigest );
	ExpectCryptoBytes( requestDigest, sizeof( requestDigest ),
		"073c1634c496cdb649d1afe0a312bbb4b7e1741b271542e4a436c3b8824b1761", "rcon2 request digest" );

	std::uint8_t different[idCrypto::SHA256_DIGEST_BYTES];
	std::memcpy( different, digest, sizeof( different ) );
	different[31] ^= 1;
	if ( !idCrypto::ConstantTimeEquals( digest, digest, sizeof( digest ) ) ||
		idCrypto::ConstantTimeEquals( digest, different, sizeof( digest ) ) ) {
		std::fprintf( stderr, "Constant-time equality result mismatch\n" );
		failures++;
	}
	idCrypto::SecureZero( different, sizeof( different ) );
	for ( std::uint8_t value : different ) {
		if ( value != 0 ) {
			std::fprintf( stderr, "SecureZero left data behind\n" );
			failures++;
			break;
		}
	}
}

static void ExpectOpenURLPolicy( const char *url, const bool expected, const char *label ) {
	const bool actual = idURLPolicy::IsAllowedHTTPURL( url );
	if ( actual != expected ) {
		std::fprintf( stderr, "Open URL policy failed for %s: expected %d, got %d\n", label, expected, actual );
		failures++;
	}
}

static void ExpectRemoteCVarPolicy( const int variableFlags, const int requiredFlag,
		const bool expected, const char *label ) {
	const int userInfo = 1 << 0;
	const int serverInfo = 1 << 1;
	const int networkSync = 1 << 2;
	const int privateFlag = 1 << 3;
	const int allowed = userInfo | serverInfo | networkSync;
	const bool actual = idRemoteCVarPolicy::CanApply(
		variableFlags, requiredFlag, allowed, privateFlag );
	if ( actual != expected ) {
		std::fprintf( stderr, "Remote CVar policy failed for %s: expected %d, got %d\n",
			label, expected, actual );
		failures++;
	}
}

static void ExpectGameDirSegment( const char *segment, const bool expected, const char *label ) {
	const bool actual = idGameDirPolicy::IsPortableSegment( segment );
	if ( actual != expected ) {
		std::fprintf( stderr, "Game-directory policy failed for %s: expected %d, got %d\n",
			label, expected, actual );
		failures++;
	}
}

static void ExpectEndpoint( const char *text, const bool expected, const char *expectedHost,
		const bool expectedHasPort, const unsigned short expectedPort, const char *label ) {
	char host[256] = "untouched";
	idNetworkEndpoint::endpointParts_t parts;
	const bool actual = idNetworkEndpoint::Split( text, host, sizeof( host ), parts );
	if ( actual != expected ) {
		std::fprintf( stderr, "Network endpoint split failed for %s: expected %d, got %d\n", label, expected, actual );
		failures++;
		return;
	}
	if ( !actual ) {
		if ( host[0] != '\0' || parts.hasPort || parts.port != 0 ) {
			std::fprintf( stderr, "Network endpoint split left output on failure for %s\n", label );
			failures++;
		}
		return;
	}
	if ( std::strcmp( host, expectedHost ) != 0 || parts.hasPort != expectedHasPort || parts.port != expectedPort ) {
		std::fprintf(
			stderr,
			"Network endpoint split value failed for %s: got host='%s', hasPort=%d, port=%u\n",
			label,
			host,
			parts.hasPort,
			static_cast<unsigned int>( parts.port )
		);
		failures++;
	}
}

static void ParseIPv6Hex( const char *hex, unsigned char out[16] ) {
	for ( int i = 0; i < 16; i++ ) {
		int value = 0;
		for ( int nibble = 0; nibble < 2; nibble++ ) {
			const char digit = hex[i * 2 + nibble];
			int parsed = 0;
			if ( digit >= '0' && digit <= '9' ) {
				parsed = digit - '0';
			} else if ( digit >= 'a' && digit <= 'f' ) {
				parsed = digit - 'a' + 10;
			} else if ( digit >= 'A' && digit <= 'F' ) {
				parsed = digit - 'A' + 10;
			}
			value = ( value << 4 ) | parsed;
		}
		out[i] = static_cast<unsigned char>( value );
	}
}

static void ExpectIPv6Text( const char *hex, const char *expected, const char *label ) {
	unsigned char ip6[16];
	ParseIPv6Hex( hex, ip6 );
	char text[idNetworkEndpoint::IPV6_TEXT_SIZE];
	if ( !idNetworkEndpoint::FormatIPv6( ip6, text, sizeof( text ) ) ) {
		std::fprintf( stderr, "IPv6 formatting failed for %s\n", label );
		failures++;
		return;
	}
	if ( std::strcmp( text, expected ) != 0 ) {
		std::fprintf( stderr, "IPv6 formatting value failed for %s: expected '%s', got '%s'\n", label, expected, text );
		failures++;
	}
}

static void ExpectIPv6Endpoint( const char *hex, const unsigned int scopeId, const unsigned short port,
		const char *expected, const char *label ) {
	unsigned char ip6[16];
	ParseIPv6Hex( hex, ip6 );
	char text[idNetworkEndpoint::IPV6_ENDPOINT_TEXT_SIZE];
	if ( !idNetworkEndpoint::FormatIPv6Endpoint( ip6, scopeId, port, text, sizeof( text ) ) ) {
		std::fprintf( stderr, "IPv6 endpoint formatting failed for %s\n", label );
		failures++;
		return;
	}
	if ( std::strcmp( text, expected ) != 0 ) {
		std::fprintf( stderr, "IPv6 endpoint value failed for %s: expected '%s', got '%s'\n", label, expected, text );
		failures++;
	}
}

static void ExpectLocalServerEndpoint( const char *netIP, const int netPort, const bool expected,
		const char *expectedText, const char *label ) {
	// Sized for interface text, which may be a host name, not for an address
	// literal - the same distinction the callers have to make.
	char text[idNetworkEndpoint::LOCAL_ENDPOINT_TEXT_SIZE] = "untouched";
	const bool actual = idNetworkEndpoint::FormatLocalServerEndpoint( netIP, netPort, text, sizeof( text ) );
	if ( actual != expected ) {
		std::fprintf( stderr, "Local server endpoint failed for %s: expected %d, got %d\n", label, expected, actual );
		failures++;
		return;
	}
	if ( !actual ) {
		if ( text[0] != '\0' ) {
			std::fprintf( stderr, "Local server endpoint left output on failure for %s\n", label );
			failures++;
		}
		return;
	}
	if ( std::strcmp( text, expectedText ) != 0 ) {
		std::fprintf( stderr, "Local server endpoint value failed for %s: expected '%s', got '%s'\n", label, expectedText, text );
		failures++;
	}
}

static void ExpectBindPlan( const char *ipv4Text, const char *ipv6Text, const bool enableIPv4, const bool enableIPv6,
		const bool expectIPv4, const bool expectIPv6, const char *expectedIPv6Interface, const char *label ) {
	idNetworkEndpoint::bindPlan_t plan;
	idNetworkEndpoint::PlanBind( ipv4Text, ipv6Text, enableIPv4, enableIPv6, plan );
	if ( plan.bindIPv4 != expectIPv4 || plan.bindIPv6 != expectIPv6 ) {
		std::fprintf( stderr, "Bind plan families failed for %s: got v4=%d v6=%d\n", label, plan.bindIPv4, plan.bindIPv6 );
		failures++;
		return;
	}
	const char *actualIPv6 = plan.ipv6Interface != nullptr ? plan.ipv6Interface : "";
	if ( std::strcmp( actualIPv6, expectedIPv6Interface ) != 0 ) {
		std::fprintf( stderr, "Bind plan IPv6 interface failed for %s: expected '%s', got '%s'\n",
			label, expectedIPv6Interface, actualIPv6 );
		failures++;
	}
}

// Families are given as a string of '4'/'6' in resolver order; the expected
// order is the resolver indices, one decimal digit each.
static void ExpectCandidateOrder( const char *families, const bool preferIPv4, const int maxOrder,
		const char *expectedOrder, const char *label ) {
	int familyList[idNetworkEndpoint::MAX_RESOLVER_RESULTS];
	int count = 0;
	for ( const char *cursor = families; *cursor != '\0' && count < idNetworkEndpoint::MAX_RESOLVER_RESULTS; ++cursor ) {
		familyList[count++] = ( *cursor == '4' ) ? idNetworkEndpoint::ADDRESS_FAMILY_IPV4 : idNetworkEndpoint::ADDRESS_FAMILY_IPV6;
	}
	int order[idNetworkEndpoint::MAX_RESOLVER_RESULTS];
	const int written = idNetworkEndpoint::OrderCandidates( familyList, count, preferIPv4, order, maxOrder );
	char actual[idNetworkEndpoint::MAX_RESOLVER_RESULTS + 1];
	for ( int i = 0; i < written; i++ ) {
		actual[i] = static_cast<char>( '0' + order[i] );
	}
	actual[written] = '\0';
	if ( std::strcmp( actual, expectedOrder ) != 0 ) {
		std::fprintf( stderr, "Candidate order failed for %s: expected '%s', got '%s'\n", label, expectedOrder, actual );
		failures++;
	}
}

static void ExerciseConnectFailover() {
	// The first entry is always what the single-address resolvers chose.
	ExpectCandidateOrder( "4", true, 8, "0", "single A record" );
	ExpectCandidateOrder( "6", true, 8, "0", "single AAAA record" );
	ExpectCandidateOrder( "64", true, 8, "10", "A record goes first for an unspecified family" );
	ExpectCandidateOrder( "64", false, 8, "01", "explicit family keeps resolver order" );
	ExpectCandidateOrder( "6644", true, 8, "2031", "families alternate after the first" );
	ExpectCandidateOrder( "4466", true, 8, "0213", "dual-stack records interleave" );
	ExpectCandidateOrder( "444", true, 8, "012", "one family keeps resolver order" );
	ExpectCandidateOrder( "66664", true, 8, "40123", "late A record still leads" );
	ExpectCandidateOrder( "4466", true, 2, "02", "output is capped" );
	ExpectCandidateOrder( "", true, 8, "", "no records" );
	{
		int families[1] = { idNetworkEndpoint::ADDRESS_FAMILY_IPV4 };
		int order[1] = { -1 };
		if ( idNetworkEndpoint::OrderCandidates( families, 1, true, order, 0 ) != 0 || order[0] != -1 ||
				idNetworkEndpoint::OrderCandidates( nullptr, 1, true, order, 1 ) != 0 ||
				idNetworkEndpoint::OrderCandidates( families, 1, true, nullptr, 1 ) != 0 ) {
			std::fprintf( stderr, "Candidate order accepted an empty or missing buffer\n" );
			failures++;
		}
	}

	// One candidate is challenged forever, exactly as before failover existed.
	idNetworkEndpoint::connectFailover_t single;
	idNetworkEndpoint::FailoverReset( single, 1 );
	for ( int challenge = 0; challenge < 20; challenge++ ) {
		if ( idNetworkEndpoint::FailoverBeforeChallenge( single ) || single.index != 0 ) {
			std::fprintf( stderr, "Single-address connection moved off its only address\n" );
			failures++;
			break;
		}
	}

	// Three candidates: three challenges each, then the next, wrapping around.
	idNetworkEndpoint::connectFailover_t state;
	idNetworkEndpoint::FailoverReset( state, 3 );
	const int per = idNetworkEndpoint::CONNECT_CHALLENGES_PER_CANDIDATE;
	for ( int challenge = 0; challenge < per * 7; challenge++ ) {
		const bool moved = idNetworkEndpoint::FailoverBeforeChallenge( state );
		const int expectedIndex = ( challenge / per ) % 3;
		const bool expectedMove = challenge > 0 && ( challenge % per ) == 0;
		if ( state.index != expectedIndex || moved != expectedMove ) {
			std::fprintf( stderr, "Failover challenge %d: expected candidate %d (move %d), got %d (move %d)\n",
				challenge, expectedIndex, expectedMove, state.index, moved );
			failures++;
			break;
		}
	}

	// A zero or negative count still behaves as one candidate.
	idNetworkEndpoint::connectFailover_t empty;
	idNetworkEndpoint::FailoverReset( empty, 0 );
	if ( empty.count != 1 || idNetworkEndpoint::FailoverBeforeChallenge( empty ) || empty.index != 0 ) {
		std::fprintf( stderr, "Failover with no candidates did not stay on the first\n" );
		failures++;
	}
}

int main() {
	ExerciseCryptoVectors();
	ExerciseConnectFailover();
	failures += ExerciseNetworkImpairment();
	const int remoteUserInfo = 1 << 0;
	const int remoteServerInfo = 1 << 1;
	const int remoteNetworkSync = 1 << 2;
	const int remotePrivate = 1 << 3;
	const int localInit = 1 << 4;
	ExpectRemoteCVarPolicy( remoteUserInfo, remoteUserInfo, true, "matching userinfo authority" );
	ExpectRemoteCVarPolicy( remoteServerInfo, remoteServerInfo, true, "matching serverinfo authority" );
	ExpectRemoteCVarPolicy( remoteNetworkSync, remoteNetworkSync, true, "matching networksync authority" );
	ExpectRemoteCVarPolicy( remoteUserInfo, remoteNetworkSync, false, "cross-class authority" );
	ExpectRemoteCVarPolicy( localInit, remoteUserInfo, false, "local-only CVar" );
	ExpectRemoteCVarPolicy( remoteUserInfo | remotePrivate, remoteUserInfo, false, "private CVar" );
	ExpectRemoteCVarPolicy( remoteUserInfo, 0, false, "empty authority" );
	ExpectRemoteCVarPolicy( remoteUserInfo | remoteNetworkSync,
		remoteUserInfo | remoteNetworkSync, false, "combined authority" );
	ExpectRemoteCVarPolicy( localInit, localInit, false, "unknown authority" );
	ExpectPrivateToken( "set net_serverRemoteConsolePassword secret",
		"net_serverRemoteConsolePassword", true, "ordinary assignment" );
	ExpectPrivateToken( "status; SET NET_SERVERREMOTECONSOLEPASSWORD secret",
		"net_serverRemoteConsolePassword", true, "case-insensitive semicolon assignment" );
	ExpectPrivateToken( "net_serverRemoteConsolePasswor",
		"net_serverRemoteConsolePassword", false, "command ends in private-name prefix" );
	ExpectPrivateToken( "net_serverRemoteConsolePasswordSuffix",
		"net_serverRemoteConsolePassword", false, "private name is a longer token prefix" );
	ExpectPrivateToken( "xnet_serverRemoteConsolePassword",
		"net_serverRemoteConsolePassword", false, "private name lacks left boundary" );
	ExpectPrivateToken( "echo net_serverRemoteConsolePassword",
		"net_serverRemoteConsolePassword", true, "private name at command end" );
	ExpectPrivateToken( nullptr, "net_private", false, "null command" );
	ExpectPrivateToken( "set net_private x", "", false, "empty private name" );
	const char *validDecimals[] = {
		"0", "-0", "123", "-123", "1.0", ".5", "-.5", "5."
	};
	for ( const char *value : validDecimals ) {
		ExpectDecimal( value, true, value );
	}

	const char *invalidDecimals[] = {
		"", "-", ".", "-.", "+1", "1..0", "1e3", " 1", "1 ", "--1", "one"
	};
	ExpectDecimal( nullptr, false, "null" );
	for ( const char *value : invalidDecimals ) {
		ExpectDecimal( value, false, value[ 0 ] == '\0' ? "empty" : value );
	}

	ExpectBounded( "0", 127, true, 0, "zero" );
	ExpectBounded( "127", 127, true, 127, "maximum" );
	ExpectBounded( "000127", 127, true, 127, "leading zeroes" );
	ExpectBounded( "128", 127, false, 0, "one above maximum" );
	ExpectBounded( "999999999999999999999999999999", 127, false, 0, "overflow-sized input" );
	ExpectBounded( "", 127, false, 0, "empty" );
	ExpectBounded( nullptr, 127, false, 0, "null" );
	ExpectBounded( "-1", 127, false, 0, "negative" );
	ExpectBounded( "12x", 127, false, 0, "non-digit" );
	ExpectBounded( "0", -1, false, 0, "negative maximum" );

	ExpectGameDirSegment( "baseoq4", true, "ordinary game directory" );
	ExpectGameDirSegment( "my-mod_2", true, "portable punctuation" );
	ExpectGameDirSegment( ".hidden-mod", true, "non-dot hidden directory" );
	ExpectGameDirSegment( nullptr, false, "null game directory" );
	ExpectGameDirSegment( "", false, "empty game directory" );
	ExpectGameDirSegment( ".", false, "dot game directory" );
	ExpectGameDirSegment( "..", false, "parent game directory" );
	ExpectGameDirSegment( "../escape", false, "parent path escape" );
	ExpectGameDirSegment( "mod/child", false, "forward-slash path" );
	ExpectGameDirSegment( "mod\\child", false, "backslash path" );
	ExpectGameDirSegment( "C:mod", false, "volume-relative path" );
	ExpectGameDirSegment( " leading", false, "leading space" );
	ExpectGameDirSegment( "trailing. ", false, "normalized trailing characters" );
	ExpectGameDirSegment( "bad*mod", false, "reserved punctuation" );
	ExpectGameDirSegment( "CON", false, "Windows device directory" );
	ExpectGameDirSegment( "com1.mod", false, "numbered Windows device directory" );
	ExpectGameDirSegment( "lpt\xC2\xB3", false, "UTF-8 superscript Windows device directory" );
	{
		char maximumSegment[idGameDirPolicy::MAX_SEGMENT_BYTES + 1];
		for ( int index = 0; index < idGameDirPolicy::MAX_SEGMENT_BYTES; ++index ) {
			maximumSegment[index] = 'm';
		}
		maximumSegment[idGameDirPolicy::MAX_SEGMENT_BYTES] = '\0';
		ExpectGameDirSegment( maximumSegment, true, "maximum game-directory segment" );

		char oversizedSegment[idGameDirPolicy::MAX_SEGMENT_BYTES + 2];
		for ( int index = 0; index <= idGameDirPolicy::MAX_SEGMENT_BYTES; ++index ) {
			oversizedSegment[index] = 'm';
		}
		oversizedSegment[idGameDirPolicy::MAX_SEGMENT_BYTES + 1] = '\0';
		ExpectGameDirSegment( oversizedSegment, false, "oversized game-directory segment" );
	}

	using namespace idStrAllocationDetail;
	const size_t sizeMaximum = ( std::numeric_limits<size_t>::max )();
	ExpectAllocation( SaturatingAdd( 17, 25 ) == 42, "ordinary addition" );
	ExpectAllocation( SaturatingAdd( sizeMaximum, 1 ) == sizeMaximum, "saturating addition" );
	ExpectAllocation( SaturatingMultiply( 6, 7 ) == 42, "ordinary multiplication" );
	ExpectAllocation( SaturatingMultiply( sizeMaximum, 2 ) == sizeMaximum, "saturating multiplication" );

	int roundedAmount = 0;
	const size_t maximumRoundedAllocation = static_cast<size_t>( INT_MAX ) / 32 * 32;
	ExpectAllocation( TryRoundUpToInt( 1, 32, roundedAmount ) && roundedAmount == 32, "small round-up" );
	ExpectAllocation(
		TryRoundUpToInt( maximumRoundedAllocation, 32, roundedAmount ) &&
			roundedAmount == static_cast<int>( maximumRoundedAllocation ),
		"largest representable rounded allocation"
	);
	ExpectAllocation( !TryRoundUpToInt( maximumRoundedAllocation + 1, 32, roundedAmount ), "first unrepresentable round-up" );
	ExpectAllocation( !TryRoundUpToInt( static_cast<size_t>( INT_MAX ), 32, roundedAmount ), "INT_MAX round-up" );
	ExpectAllocation( !TryRoundUpToInt( sizeMaximum, 32, roundedAmount ), "SIZE_MAX round-up" );
	ExpectAllocation( !TryRoundUpToInt( 1, 0, roundedAmount ), "zero granularity" );

	ExpectOpenURLPolicy( "http://example.com", true, "ordinary HTTP URL" );
	ExpectOpenURLPolicy( "HTTPS://example.com:443/releases?q=openq4#download", true, "ordinary HTTPS URL" );
	ExpectOpenURLPolicy( "https://localhost", true, "localhost HTTPS URL" );
	ExpectOpenURLPolicy( "http://127.0.0.1:8080/path", true, "IPv4 HTTP URL" );
	ExpectOpenURLPolicy( "https://[2001:db8::1]:65535/path", true, "IPv6 HTTPS URL" );
	ExpectOpenURLPolicy( "https://example.com/path@name?redirect=%2Fsafe", true, "reserved path characters" );
	ExpectOpenURLPolicy( nullptr, false, "null URL" );
	ExpectOpenURLPolicy( "", false, "empty URL" );
	ExpectOpenURLPolicy( "ftp://example.com/file", false, "FTP scheme" );
	ExpectOpenURLPolicy( "file:///tmp/update", false, "file scheme" );
	ExpectOpenURLPolicy( "javascript:alert(1)", false, "script scheme" );
	ExpectOpenURLPolicy( "https:example.com", false, "HTTPS URL without authority delimiter" );
	ExpectOpenURLPolicy( "https:///missing-host", false, "empty authority" );
	ExpectOpenURLPolicy( "https://:443/path", false, "empty host with port" );
	ExpectOpenURLPolicy( "https://user@example.com/path", false, "userinfo authority" );
	ExpectOpenURLPolicy( "https://example.com%40attacker.invalid/path", false, "encoded authority ambiguity" );
	ExpectOpenURLPolicy( "https://example.com:65536/path", false, "out-of-range URL port" );
	ExpectOpenURLPolicy( "https://example.com:/path", false, "empty URL port" );
	ExpectOpenURLPolicy( "https://example.com:443:444/path", false, "ambiguous URL port" );
	ExpectOpenURLPolicy( "https://2001:db8::1/path", false, "unbracketed IPv6 URL" );
	ExpectOpenURLPolicy( "https://[::1]suffix/path", false, "text after bracketed URL host" );
	ExpectOpenURLPolicy( "https://!/path", false, "invalid hostname character" );
	ExpectOpenURLPolicy( "https://./path", false, "empty DNS labels" );
	ExpectOpenURLPolicy( "https://-example.com/path", false, "leading hostname hyphen" );
	ExpectOpenURLPolicy( "https://example-.com/path", false, "trailing hostname hyphen" );
	ExpectOpenURLPolicy( "https://999.1.2.3/path", false, "invalid IPv4 octet" );
	ExpectOpenURLPolicy( "https://127.1/path", false, "ambiguous abbreviated IPv4" );
	ExpectOpenURLPolicy( "https://[not-an-ip]/path", false, "invalid bracketed IP literal" );
	ExpectOpenURLPolicy( "https://[::::]/path", false, "invalid IPv6 compression" );
	ExpectOpenURLPolicy( "https://example.com/line\nbreak", false, "URL newline" );
	ExpectOpenURLPolicy( "https://example.com/space here", false, "URL space" );
	ExpectOpenURLPolicy( "https://example.com\\attacker.invalid", false, "URL backslash" );
	ExpectOpenURLPolicy( "https://example.com/\x7f", false, "URL delete control" );

	{
		char maximumLengthURL[idURLPolicy::MAX_URL_BYTES];
		const char prefix[] = "https://example.com/";
		for ( size_t index = 0; index < sizeof( prefix ) - 1; index++ ) {
			maximumLengthURL[index] = prefix[index];
		}
		for ( size_t index = sizeof( prefix ) - 1; index < idURLPolicy::MAX_URL_BYTES - 1; index++ ) {
			maximumLengthURL[index] = 'a';
		}
		maximumLengthURL[idURLPolicy::MAX_URL_BYTES - 1] = '\0';
		ExpectOpenURLPolicy( maximumLengthURL, true, "maximum bounded URL" );

		char oversizedURL[idURLPolicy::MAX_URL_BYTES + 1];
		for ( size_t index = 0; index < idURLPolicy::MAX_URL_BYTES; index++ ) {
			oversizedURL[index] = maximumLengthURL[index];
		}
		oversizedURL[idURLPolicy::MAX_URL_BYTES - 1] = 'a';
		oversizedURL[idURLPolicy::MAX_URL_BYTES] = '\0';
		ExpectOpenURLPolicy( oversizedURL, false, "oversized URL" );
	}

	ExpectEndpoint( "127.0.0.1", true, "127.0.0.1", false, 0, "numeric IPv4" );
	ExpectEndpoint( "127.0.0.1:65535", true, "127.0.0.1", true, 65535, "maximum IPv4 port" );
	ExpectEndpoint( "4.example.com:27960", true, "4.example.com", true, 27960, "digit-leading hostname" );
	ExpectEndpoint( "255.255.255.255", true, "255.255.255.255", false, 0, "IPv4 broadcast literal" );
	ExpectEndpoint( "hostname:0", true, "hostname", true, 0, "explicit zero port" );
	ExpectEndpoint( "::1", true, "::1", false, 0, "unbracketed IPv6 literal" );
	ExpectEndpoint( "[::1]:27960", true, "::1", true, 27960, "bracketed IPv6 endpoint" );
	ExpectEndpoint( "[fe80::1%3]", true, "fe80::1%3", false, 0, "scoped IPv6 literal" );
	ExpectEndpoint( "fe80::1%eth0", true, "fe80::1%eth0", false, 0, "unbracketed named zone" );
	ExpectEndpoint( "[fe80::1%eth0]:27650", true, "fe80::1%eth0", true, 27650, "bracketed named zone" );
	ExpectEndpoint( "::ffff:1.2.3.4", true, "::ffff:1.2.3.4", false, 0, "IPv4-mapped literal" );
	ExpectEndpoint( "2001:db8::1", true, "2001:db8::1", false, 0, "unbracketed global unicast" );
	ExpectEndpoint( "[2001:db8::1]", true, "2001:db8::1", false, 0, "bracketed literal without a port" );
	ExpectEndpoint( "::", true, "::", false, 0, "unspecified address" );
	// Two or more colons and no brackets means the whole string is a host, so an
	// unbracketed scoped literal with a port is a host name the resolver will
	// reject rather than a silently mis-split endpoint.
	ExpectEndpoint( "fe80::1%eth0:27650", true, "fe80::1%eth0:27650", false, 0, "unbracketed scoped literal with a port" );

	ExpectIPv6Text( "00000000000000000000000000000000", "::", "unspecified" );
	ExpectIPv6Text( "00000000000000000000000000000001", "::1", "loopback" );
	ExpectIPv6Text( "20010db8000000000000000000000001", "2001:db8::1", "global unicast" );
	ExpectIPv6Text( "00010002000300040005000600070008", "1:2:3:4:5:6:7:8", "no zero groups" );
	ExpectIPv6Text( "fe800000000000000000000000000000", "fe80::", "trailing zero run" );
	// A single zero group is never compressed.
	ExpectIPv6Text( "20010000000100010001000100010001", "2001:0:1:1:1:1:1:1", "single zero group" );
	// The leftmost of two equally long runs wins.
	ExpectIPv6Text( "00010000000000020000000000030004", "1::2:0:0:3:4", "leftmost equal-length run" );
	// The longest run wins even when a shorter one comes first.
	ExpectIPv6Text( "00010000000000020000000000000003", "1:0:0:2::3", "longest run" );
	ExpectIPv6Text( "00000000000000000000ffff01020304", "::ffff:1.2.3.4", "IPv4-mapped dotted tail" );
	ExpectIPv6Text( "00000000000000000000ffffffffffff", "::ffff:255.255.255.255", "IPv4-mapped maximum" );
	// Only ::ffff:0:0/96 earns the dotted tail.
	ExpectIPv6Text( "ffffffffffffffffffffffff01020304", "ffff:ffff:ffff:ffff:ffff:ffff:102:304", "non-mapped tail" );
	ExpectIPv6Text( "ffffffffffffffffffffffffffffffff", "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff", "longest literal" );

	ExpectIPv6Endpoint( "00000000000000000000000000000001", 0, 0, "::1", "loopback without a port" );
	ExpectIPv6Endpoint( "00000000000000000000000000000001", 0, 27650, "[::1]:27650", "loopback with a port" );
	ExpectIPv6Endpoint( "fe800000000000000000000000000001", 12, 27650, "[fe80::1%12]:27650", "scoped endpoint" );
	ExpectIPv6Endpoint( "fe800000000000000000000000000001", 12, 0, "fe80::1%12", "scoped without a port" );
	ExpectIPv6Endpoint(
		"ffffffffffffffffffffffffffffffff", 4294967295u, 65535,
		"[ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff%4294967295]:65535", "longest endpoint" );

	{
		// A truncated address would alias two distinct servers onto one browser
		// key and one ban-list entry, so an undersized buffer must fail closed.
		unsigned char widest[16];
		ParseIPv6Hex( "ffffffffffffffffffffffffffffffff", widest );
		char tooSmall[8] = "keepme";
		if ( idNetworkEndpoint::FormatIPv6( widest, tooSmall, sizeof( tooSmall ) ) || tooSmall[0] != '\0' ) {
			std::fprintf( stderr, "IPv6 formatting accepted an undersized buffer\n" );
			failures++;
		}
		if ( idNetworkEndpoint::FormatIPv6( nullptr, tooSmall, sizeof( tooSmall ) ) ) {
			std::fprintf( stderr, "IPv6 formatting accepted a null address\n" );
			failures++;
		}
	}

	ExpectLocalServerEndpoint( "", 27650, true, "127.0.0.1:27650", "wildcard interface" );
	ExpectLocalServerEndpoint( nullptr, 0, false, "", "no interface and no port" );
	ExpectLocalServerEndpoint( "0.0.0.0", 27650, true, "127.0.0.1:27650", "IPv4 wildcard literal" );
	ExpectLocalServerEndpoint( "192.168.1.5", 27650, true, "192.168.1.5:27650", "explicit IPv4 interface" );
	ExpectLocalServerEndpoint( "::", 27650, true, "[::1]:27650", "IPv6 wildcard literal" );
	ExpectLocalServerEndpoint( "2001:db8::5", 27650, true, "[2001:db8::5]:27650", "bare IPv6 interface" );
	ExpectLocalServerEndpoint( "[2001:db8::5]", 27650, true, "[2001:db8::5]:27650", "bracketed IPv6 interface" );
	// "localhost" is the shipped net_ip default and names every interface, so
	// the endpoint shown is the loopback a player can actually dial.
	ExpectLocalServerEndpoint( "localhost", 27650, true, "127.0.0.1:27650", "default interface name" );
	// net_port 0 means "choose automatically"; the chosen port is not known
	// here, so naming it would point players at a port nothing listens on.
	ExpectLocalServerEndpoint( "localhost", 0, false, "", "default interface and automatic port" );
	ExpectLocalServerEndpoint( "192.168.1.5", 0, true, "192.168.1.5", "explicit interface, automatic port" );
	{
		// An interface may be a host name far longer than any address literal.
		const char *longHost = "gameserver-01.eu-west-2.datacenter.example-hosting-provider.com";
		char expected[idNetworkEndpoint::LOCAL_ENDPOINT_TEXT_SIZE];
		std::snprintf( expected, sizeof( expected ), "%s:28004", longHost );
		ExpectLocalServerEndpoint( longHost, 28004, true, expected, "long hostname interface" );
	}

	ExpectBindPlan( "localhost", "", true, true, true, true, "", "default dual-stack plan" );
	ExpectBindPlan( "192.168.1.5", "", true, true, true, true, "", "explicit IPv4 interface" );
	ExpectBindPlan( "192.168.1.5:27650", "", true, true, true, true, "", "IPv4 interface carrying a port" );
	ExpectBindPlan( "localhost", "2001:db8::5", true, true, true, true, "2001:db8::5", "explicit IPv6 interface" );
	ExpectBindPlan( "localhost", "", false, true, false, true, "", "IPv6-only host" );
	ExpectBindPlan( "localhost", "", true, false, true, false, "", "IPv4-only host" );
	// An IPv6 literal in net_ip is a pre-net_ip6 configuration, and has to keep
	// producing the single IPv6 socket it always did.
	ExpectBindPlan( "2001:db8::5", "", true, true, false, true, "2001:db8::5", "legacy IPv6 net_ip" );
	ExpectBindPlan( "2001:db8::5", "2001:db8::6", true, true, false, true, "2001:db8::6", "net_ip6 wins over legacy net_ip" );

	ExpectEndpoint( nullptr, false, "", false, 0, "null endpoint" );
	ExpectEndpoint( "", false, "", false, 0, "empty endpoint" );
	ExpectEndpoint( ":27960", false, "", false, 0, "missing host" );
	ExpectEndpoint( "host:", false, "", false, 0, "missing port" );
	ExpectEndpoint( "host:-1", false, "", false, 0, "negative port" );
	ExpectEndpoint( "host:65536", false, "", false, 0, "out-of-range port" );
	ExpectEndpoint( "host:184467440737095516160", false, "", false, 0, "overflowing decimal port" );
	ExpectEndpoint( "host:12x", false, "", false, 0, "non-numeric port" );
	ExpectEndpoint( "[::1", false, "", false, 0, "missing close bracket" );
	ExpectEndpoint( "[]:27960", false, "", false, 0, "empty bracketed host" );
	ExpectEndpoint( "[::1]junk", false, "", false, 0, "text after close bracket" );

	if ( failures != 0 ) {
		std::fprintf( stderr, "core safety native test: %d failure(s)\n", failures );
		return 1;
	}

	std::printf( "core safety native test: ok\n" );
	return 0;
}
