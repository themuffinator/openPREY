/*
===========================================================================

openQ4 hardened level-load cache format native tests

Copyright (C) 2026 openQ4 contributors

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

===========================================================================
*/

#include "src/framework/LevelLoadCacheFormat.h"

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <string>
#include <vector>

namespace cache = idLevelLoadCache;

static int failures = 0;

static void Expect( const bool condition, const char *label ) {
	if ( !condition ) {
		std::fprintf( stderr, "level-load cache format failed: %s\n", label );
		failures++;
	}
}

static void ExpectStatus( const cache::Result &result, const cache::Status expected,
		const char *label ) {
	if ( result.status != expected ) {
		std::fprintf( stderr,
			"level-load cache format failed: %s expected %s, got %s at %zu (%s)\n",
			label, cache::StatusName( expected ), cache::StatusName( result.status ),
			result.offset, result.diagnostic.c_str() );
		failures++;
	}
	if ( expected != cache::Status::OK && result.diagnostic.empty() ) {
		std::fprintf( stderr, "level-load cache format failed: %s had no diagnostic\n", label );
		failures++;
	}
}

static cache::Hash HashText( const char *text ) {
	return cache::ComputeHash( text, std::strlen( text ) );
}

static std::string HashHex( const cache::Hash &hash ) {
	static constexpr char digits[] = "0123456789abcdef";
	std::string text;
	text.reserve( hash.size() * 2 );
	for ( const std::uint8_t value : hash ) {
		text.push_back( digits[value >> 4] );
		text.push_back( digits[value & 15] );
	}
	return text;
}

static void WriteU32( std::vector<std::uint8_t> &bytes, const std::size_t offset,
		const std::uint32_t value ) {
	Expect( offset <= bytes.size() && bytes.size() - offset >= 4, "test WriteU32 bounds" );
	if ( offset > bytes.size() || bytes.size() - offset < 4 ) {
		return;
	}
	for ( unsigned int index = 0; index < 4; ++index ) {
		bytes[offset + index] = static_cast<std::uint8_t>( value >> ( index * 8u ) );
	}
}

static void WriteU64( std::vector<std::uint8_t> &bytes, const std::size_t offset,
		const std::uint64_t value ) {
	Expect( offset <= bytes.size() && bytes.size() - offset >= 8, "test WriteU64 bounds" );
	if ( offset > bytes.size() || bytes.size() - offset < 8 ) {
		return;
	}
	for ( unsigned int index = 0; index < 8; ++index ) {
		bytes[offset + index] = static_cast<std::uint8_t>( value >> ( index * 8u ) );
	}
}

static void RewriteIntegrityHash( std::vector<std::uint8_t> &encoded ) {
	Expect( encoded.size() >= cache::HASH_BYTES + 4, "test integrity trailer bounds" );
	if ( encoded.size() < cache::HASH_BYTES + 4 ) {
		return;
	}
	const std::size_t protectedBytes = encoded.size() - cache::HASH_BYTES - 4;
	const cache::Hash hash = cache::ComputeHash( encoded.data(), protectedBytes );
	std::memcpy( encoded.data() + protectedBytes, hash.data(), hash.size() );
}

static cache::SourceIdentity ArchiveSource( const char *path, const std::uint64_t size = 987654,
		const std::uint64_t timestamp = 123456789, const std::uint32_t checksum = 0x91a2b3c4u ) {
	cache::SourceIdentity source;
	source.normalizedPath = path;
	source.size = size;
	source.timestamp = timestamp;
	source.containerKind = cache::SourceContainerKind::PK4_ARCHIVE;
	source.containerPk4Checksum = checksum;
	return source;
}

static cache::CacheEnvelope ExampleEnvelope() {
	cache::CacheEnvelope envelope;
	envelope.kind = cache::CacheKind::RENDER_MODEL;
	envelope.parserVersion = 0x01020304u;
	envelope.codec = cache::CompressionCodec::NONE;
	envelope.source = ArchiveSource( "models/mapobjects/storage/crate.lwo" );
	envelope.contentSignature = HashText( "ordered stock PK4 inventory" );
	envelope.settingsSignature = HashText( "renderer cache settings" );
	envelope.payload = { 0x00, 0x01, 0x7f, 0x80, 0xfe, 0xff, 0x55, 0xaa };
	return envelope;
}

static cache::EnvelopeExpectation ExpectationFor( const cache::CacheEnvelope &envelope ) {
	cache::EnvelopeExpectation expected;
	expected.kind = envelope.kind;
	expected.parserVersion = envelope.parserVersion;
	expected.source = envelope.source;
	expected.contentSignature = envelope.contentSignature;
	expected.settingsSignature = envelope.settingsSignature;
	return expected;
}

static cache::ManifestEntry ExampleEntry( const cache::ManifestEntryType type,
		const char *name, const char *sourcePath, const cache::ManifestPriority priority,
		const std::uint64_t order, const std::uint32_t useCount ) {
	cache::ManifestEntry entry;
	entry.type = type;
	entry.priority = priority;
	entry.firstUseOrder = order;
	entry.useCount = useCount;
	entry.flags = 0x10203040u + static_cast<std::uint32_t>( type );
	entry.normalizedName = name;
	entry.source = ArchiveSource( sourcePath, 4000 + static_cast<std::uint32_t>( type ),
		5000 + static_cast<std::uint32_t>( type ) );
	entry.options = { static_cast<std::uint8_t>( type ), 0x22, 0x00, 0xff };
	return entry;
}

static cache::Manifest ExampleManifest() {
	cache::Manifest manifest;
	manifest.producerVersion = 7;
	manifest.mapKey = "game/storage1";
	manifest.gameMode = HashText( "single-player" );
	manifest.entityFilter = HashText( "storage1/default" );
	manifest.contentSignature = HashText( "ordered stock PK4 inventory" );
	manifest.settingsSignature = HashText( "renderer preload settings" );
	manifest.entries.push_back( ExampleEntry( cache::ManifestEntryType::IMAGE,
		"textures/base_wall/metal", "textures/base_wall/metal.tga",
		cache::ManifestPriority::NORMAL, 18, 2 ) );
	manifest.entries.push_back( ExampleEntry( cache::ManifestEntryType::RENDER_MODEL,
		"models/mapobjects/crate.lwo", "models/mapobjects/crate.lwo",
		cache::ManifestPriority::CRITICAL, 2, 5 ) );
	manifest.entries.push_back( ExampleEntry( cache::ManifestEntryType::SOUND_SAMPLE,
		"sound/ambience/machine.wav", "sound/ambience/machine.wav",
		cache::ManifestPriority::HIGH, 9, 3 ) );
	return manifest;
}

static cache::ManifestExpectation ExpectationFor( const cache::Manifest &manifest ) {
	cache::ManifestExpectation expected;
	expected.producerVersion = manifest.producerVersion;
	expected.mapKey = manifest.mapKey;
	expected.gameMode = manifest.gameMode;
	expected.entityFilter = manifest.entityFilter;
	expected.contentSignature = manifest.contentSignature;
	expected.settingsSignature = manifest.settingsSignature;
	return expected;
}

static void ExerciseHashAndPathPrimitives() {
	Expect( HashHex( HashText( "abc" ) ) ==
		"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
		"SHA-256 known vector" );
	Expect( HashHex( cache::ComputeHash( nullptr, 0 ) ) ==
		"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
		"SHA-256 empty vector" );

	std::string normalized;
	ExpectStatus( cache::NormalizeVirtualPath( "Models\\Weapons//./Gun.LWO", normalized ),
		cache::Status::OK, "normalize mixed virtual path" );
	Expect( normalized == "models/weapons/gun.lwo", "normalized virtual path bytes" );
	ExpectStatus( cache::NormalizeVirtualPath( "models/../secret", normalized ),
		cache::Status::INVALID_STRING, "reject parent virtual path" );
	ExpectStatus( cache::NormalizeVirtualPath( "/absolute/path", normalized ),
		cache::Status::INVALID_STRING, "reject absolute virtual path" );
	ExpectStatus( cache::NormalizeVirtualPath( "c:/drive/path", normalized ),
		cache::Status::INVALID_STRING, "reject drive virtual path" );
	ExpectStatus( cache::NormalizeVirtualPath( "models/long", normalized, 4 ),
		cache::Status::SIZE_LIMIT_EXCEEDED, "virtual path bound" );
}

static void ExerciseEnvelopeRoundTrip( std::vector<std::uint8_t> &encodedOut ) {
	const cache::CacheEnvelope source = ExampleEnvelope();
	std::vector<std::uint8_t> encoded;
	ExpectStatus( cache::EncodeEnvelope( source, encoded ), cache::Status::OK,
		"encode cache envelope" );
	Expect( encoded.size() > 128, "cache envelope has fixed metadata" );
	Expect( encoded.size() >= 16 && encoded[0] == 'O' && encoded[1] == 'Q' &&
		encoded[2] == '4' && encoded[3] == 'C', "cache magic wire bytes" );
	Expect( encoded.size() >= 16 && encoded[12] == 0x04 && encoded[13] == 0x03 &&
		encoded[14] == 0x02 && encoded[15] == 0x01, "cache parser version is little endian" );

	cache::CacheEnvelope decoded;
	ExpectStatus( cache::DecodeEnvelopeForKey( encoded, ExpectationFor( source ), decoded ),
		cache::Status::OK, "decode cache envelope round trip" );
	cache::CacheEnvelope canonical = source;
	canonical.decodedPayloadBytes = source.payload.size();
	canonical.decodedPayloadHash = cache::ComputeHash( source.payload.data(), source.payload.size() );
	Expect( decoded == canonical, "cache envelope round-trip fields" );
	ExpectStatus( cache::ValidateDecodedPayload( decoded, decoded.payload.data(), decoded.payload.size() ),
		cache::Status::OK, "validate uncompressed decoded payload" );

	std::vector<std::uint8_t> second;
	ExpectStatus( cache::EncodeEnvelope( source, second ), cache::Status::OK,
		"encode deterministic cache envelope" );
	Expect( encoded == second, "deterministic cache envelope bytes" );
	encodedOut = std::move( encoded );
}

static void ExerciseEnvelopeFailures( const std::vector<std::uint8_t> &valid ) {
	cache::CacheEnvelope decoded;
	for ( std::size_t bytes = 0; bytes < valid.size(); ++bytes ) {
		const cache::Result result = cache::DecodeEnvelope( valid.data(), bytes, decoded );
		if ( result.Ok() ) {
			std::fprintf( stderr, "level-load cache format failed: cache truncation accepted at %zu/%zu\n",
				bytes, valid.size() );
			failures++;
			break;
		}
	}

	std::vector<std::uint8_t> damaged = valid;
	damaged[0] ^= 0xffu;
	ExpectStatus( cache::DecodeEnvelope( damaged, decoded ), cache::Status::INVALID_MAGIC,
		"reject corrupt cache magic" );
	damaged = valid;
	WriteU32( damaged, 4, cache::CACHE_FORMAT_VERSION + 1 );
	ExpectStatus( cache::DecodeEnvelope( damaged, decoded ), cache::Status::UNSUPPORTED_VERSION,
		"reject unsupported cache version" );
	damaged = valid;
	damaged[damaged.size() - cache::HASH_BYTES - 4] ^= 0x80u;
	ExpectStatus( cache::DecodeEnvelope( damaged, decoded ), cache::Status::INTEGRITY_MISMATCH,
		"reject corrupt cache integrity hash" );
	damaged = valid;
	const cache::CacheEnvelope source = ExampleEnvelope();
	const std::size_t pathLengthOffset = 20;
	const std::size_t storedPayloadLengthOffset = 112 + source.source.normalizedPath.size();
	const std::size_t payloadOffset = storedPayloadLengthOffset + 48;
	damaged[payloadOffset] ^= 0x20u;
	ExpectStatus( cache::DecodeEnvelope( damaged, decoded ), cache::Status::INTEGRITY_MISMATCH,
		"reject corrupt stored cache payload" );
	damaged = valid;
	damaged[damaged.size() - 1] ^= 1u;
	ExpectStatus( cache::DecodeEnvelope( damaged, decoded ), cache::Status::INVALID_END_MARKER,
		"reject corrupt cache end marker" );
	damaged = valid;
	damaged.push_back( 0x7e );
	ExpectStatus( cache::DecodeEnvelope( damaged, decoded ), cache::Status::TRAILING_DATA,
		"reject trailing cache garbage" );

	damaged = valid;
	WriteU32( damaged, pathLengthOffset, std::numeric_limits<std::uint32_t>::max() );
	ExpectStatus( cache::DecodeEnvelope( damaged, decoded ), cache::Status::SIZE_LIMIT_EXCEEDED,
		"reject oversized cache source path length" );
	damaged = valid;
	WriteU64( damaged, storedPayloadLengthOffset, std::numeric_limits<std::uint64_t>::max() );
	const cache::Result oversizedPayload = cache::DecodeEnvelope( damaged, decoded );
	Expect( oversizedPayload.status == cache::Status::SIZE_LIMIT_EXCEEDED ||
		oversizedPayload.status == cache::Status::INTEGER_OVERFLOW,
		"reject oversized cache payload length" );

	cache::DecodeLimits limits;
	limits.maxPayloadBytes = source.payload.size() - 1;
	ExpectStatus( cache::DecodeEnvelope( valid, decoded, limits ), cache::Status::SIZE_LIMIT_EXCEEDED,
		"caller cache payload limit" );
	limits = cache::DecodeLimits();
	limits.maxDecodedPayloadBytes = source.payload.size() - 1;
	ExpectStatus( cache::DecodeEnvelope( valid, decoded, limits ), cache::Status::SIZE_LIMIT_EXCEEDED,
		"caller decoded cache limit" );

	// Alter the decoded hash but repair the whole-envelope hash.  This proves the
	// independent decoded-payload hash is checked after envelope integrity.
	damaged = valid;
	const std::size_t decodedHashOffset = storedPayloadLengthOffset + 16;
	damaged[decodedHashOffset] ^= 0x40u;
	RewriteIntegrityHash( damaged );
	ExpectStatus( cache::DecodeEnvelope( damaged, decoded ), cache::Status::PAYLOAD_HASH_MISMATCH,
		"reject cache decoded-payload hash mismatch" );

	cache::CacheEnvelope sentinel;
	sentinel.parserVersion = 777;
	sentinel.payload = { 9, 9, 9 };
	damaged = valid;
	damaged[0] ^= 1;
	Expect( !cache::DecodeEnvelope( damaged, sentinel ).Ok(), "failed cache decode reports failure" );
	Expect( sentinel.parserVersion == 777 && sentinel.payload == std::vector<std::uint8_t>( { 9, 9, 9 } ),
		"failed cache decode leaves output unchanged" );
}

static void ExerciseEnvelopeKeyAndCompression( const std::vector<std::uint8_t> &valid ) {
	const cache::CacheEnvelope source = ExampleEnvelope();
	cache::EnvelopeExpectation expected = ExpectationFor( source );
	cache::CacheEnvelope decoded;
	expected.kind = cache::CacheKind::RENDER_WORLD;
	ExpectStatus( cache::DecodeEnvelopeForKey( valid, expected, decoded ), cache::Status::KIND_MISMATCH,
		"cache kind key mismatch" );
	expected = ExpectationFor( source );
	expected.parserVersion++;
	ExpectStatus( cache::DecodeEnvelopeForKey( valid, expected, decoded ),
		cache::Status::PARSER_VERSION_MISMATCH, "cache parser key mismatch" );
	expected = ExpectationFor( source );
	expected.source.timestamp++;
	ExpectStatus( cache::DecodeEnvelopeForKey( valid, expected, decoded ), cache::Status::SOURCE_MISMATCH,
		"cache source key mismatch" );
	expected = ExpectationFor( source );
	expected.contentSignature[0] ^= 1;
	ExpectStatus( cache::DecodeEnvelopeForKey( valid, expected, decoded ),
		cache::Status::CONTENT_SIGNATURE_MISMATCH, "cache content key mismatch" );
	expected = ExpectationFor( source );
	expected.settingsSignature[0] ^= 1;
	ExpectStatus( cache::DecodeEnvelopeForKey( valid, expected, decoded ),
		cache::Status::SETTINGS_SIGNATURE_MISMATCH, "cache settings key mismatch" );

	const std::vector<std::uint8_t> decodedBytes = { 'd', 'e', 'c', 'o', 'd', 'e', 'd' };
	cache::CacheEnvelope compressed = source;
	compressed.codec = cache::CompressionCodec::DEFLATE;
	compressed.payload = { 0x78, 0x9c, 0x03, 0x00 };
	compressed.decodedPayloadBytes = decodedBytes.size();
	compressed.decodedPayloadHash = cache::ComputeHash( decodedBytes.data(), decodedBytes.size() );
	std::vector<std::uint8_t> encoded;
	ExpectStatus( cache::EncodeEnvelope( compressed, encoded ), cache::Status::OK,
		"encode externally compressed envelope" );
	ExpectStatus( cache::DecodeEnvelope( encoded, decoded ), cache::Status::OK,
		"decode externally compressed envelope" );
	ExpectStatus( cache::ValidateDecodedPayload( decoded, decodedBytes.data(), decodedBytes.size() ),
		cache::Status::OK, "validate decompressed payload" );
	std::vector<std::uint8_t> wrong = decodedBytes;
	wrong[0] ^= 1;
	ExpectStatus( cache::ValidateDecodedPayload( decoded, wrong.data(), wrong.size() ),
		cache::Status::PAYLOAD_HASH_MISMATCH, "reject wrong decompressed payload" );
}

static void ExerciseManifestRoundTrip( std::vector<std::uint8_t> &encodedOut,
		cache::Manifest &canonicalOut ) {
	const cache::Manifest source = ExampleManifest();
	cache::Manifest canonical = source;
	ExpectStatus( cache::CanonicalizeManifest( canonical ), cache::Status::OK,
		"canonicalize manifest" );
	std::vector<std::uint8_t> encoded;
	ExpectStatus( cache::EncodeManifest( source, encoded ), cache::Status::OK, "encode manifest" );
	Expect( encoded.size() >= 8 && encoded[0] == 'O' && encoded[1] == 'Q' &&
		encoded[2] == '4' && encoded[3] == 'M', "manifest magic wire bytes" );

	cache::Manifest decoded;
	ExpectStatus( cache::DecodeManifestForKey( encoded, ExpectationFor( source ), decoded ),
		cache::Status::OK, "decode manifest round trip" );
	Expect( decoded == canonical, "manifest round-trip fields" );

	std::vector<std::uint8_t> second;
	ExpectStatus( cache::EncodeManifest( source, second ), cache::Status::OK,
		"encode deterministic manifest" );
	Expect( encoded == second, "deterministic manifest bytes" );
	encodedOut = std::move( encoded );
	canonicalOut = std::move( canonical );
}

static void ExerciseManifestDeterminism() {
	cache::Manifest first = ExampleManifest();
	cache::ManifestEntry target = first.entries[1];
	first.entries[1].useCount = 5;

	cache::Manifest second = first;
	second.entries.erase( second.entries.begin() + 1 );
	cache::ManifestEntry early = target;
	early.useCount = 3;
	early.priority = cache::ManifestPriority::CRITICAL;
	early.firstUseOrder = 2;
	cache::ManifestEntry late = target;
	late.useCount = 2;
	late.priority = cache::ManifestPriority::NORMAL;
	late.firstUseOrder = 99;
	second.entries.push_back( late );
	second.entries.push_back( early );
	std::reverse( second.entries.begin(), second.entries.end() );

	std::vector<std::uint8_t> firstBytes;
	std::vector<std::uint8_t> secondBytes;
	ExpectStatus( cache::EncodeManifest( first, firstBytes ), cache::Status::OK,
		"encode canonical deterministic manifest" );
	ExpectStatus( cache::EncodeManifest( second, secondBytes ), cache::Status::OK,
		"encode reordered duplicate manifest" );
	Expect( firstBytes == secondBytes, "manifest duplicate merge and deterministic ordering" );

	cache::Manifest overflow = ExampleManifest();
	cache::ManifestEntry duplicate = overflow.entries.front();
	overflow.entries.front().useCount = std::numeric_limits<std::uint32_t>::max();
	duplicate.useCount = 1;
	overflow.entries.push_back( duplicate );
	ExpectStatus( cache::CanonicalizeManifest( overflow ), cache::Status::INTEGER_OVERFLOW,
		"manifest duplicate use-count overflow" );
}

static void ExerciseManifestFailures( const std::vector<std::uint8_t> &valid,
		const cache::Manifest &canonical ) {
	cache::Manifest decoded;
	for ( std::size_t bytes = 0; bytes < valid.size(); ++bytes ) {
		const cache::Result result = cache::DecodeManifest( valid.data(), bytes, decoded );
		if ( result.Ok() ) {
			std::fprintf( stderr, "level-load cache format failed: manifest truncation accepted at %zu/%zu\n",
				bytes, valid.size() );
			failures++;
			break;
		}
	}

	std::vector<std::uint8_t> damaged = valid;
	damaged[0] ^= 0xffu;
	ExpectStatus( cache::DecodeManifest( damaged, decoded ), cache::Status::INVALID_MAGIC,
		"reject corrupt manifest magic" );
	damaged = valid;
	WriteU32( damaged, 4, cache::MANIFEST_FORMAT_VERSION + 1 );
	ExpectStatus( cache::DecodeManifest( damaged, decoded ), cache::Status::UNSUPPORTED_VERSION,
		"reject unsupported manifest version" );
	damaged = valid;
	damaged[damaged.size() - cache::HASH_BYTES - 4] ^= 0x01u;
	ExpectStatus( cache::DecodeManifest( damaged, decoded ), cache::Status::INTEGRITY_MISMATCH,
		"reject corrupt manifest integrity hash" );
	damaged = valid;
	damaged[damaged.size() - 1] ^= 0x01u;
	ExpectStatus( cache::DecodeManifest( damaged, decoded ), cache::Status::INVALID_END_MARKER,
		"reject corrupt manifest end marker" );
	damaged = valid;
	damaged.push_back( 0x99 );
	ExpectStatus( cache::DecodeManifest( damaged, decoded ), cache::Status::TRAILING_DATA,
		"reject trailing manifest garbage" );

	const std::size_t mapLengthOffset = 140;
	const std::size_t entryCountOffset = 144 + canonical.mapKey.size();
	const std::size_t firstEntryOffset = entryCountOffset + 4;
	const cache::ManifestEntry &firstEntry = canonical.entries.front();
	const std::size_t firstNameLengthOffset = firstEntryOffset + 24;
	const std::size_t firstSourceLengthOffset = firstNameLengthOffset + 4 +
		firstEntry.normalizedName.size();
	const std::size_t firstOptionsLengthOffset = firstEntryOffset + 56 +
		firstEntry.normalizedName.size() + firstEntry.source.normalizedPath.size();
	damaged = valid;
	WriteU32( damaged, mapLengthOffset, std::numeric_limits<std::uint32_t>::max() );
	ExpectStatus( cache::DecodeManifest( damaged, decoded ), cache::Status::SIZE_LIMIT_EXCEEDED,
		"reject oversized manifest map-key length" );
	damaged = valid;
	WriteU32( damaged, entryCountOffset, std::numeric_limits<std::uint32_t>::max() );
	ExpectStatus( cache::DecodeManifest( damaged, decoded ), cache::Status::SIZE_LIMIT_EXCEEDED,
		"reject oversized manifest entry count" );
	damaged = valid;
	WriteU32( damaged, firstNameLengthOffset, std::numeric_limits<std::uint32_t>::max() );
	ExpectStatus( cache::DecodeManifest( damaged, decoded ), cache::Status::SIZE_LIMIT_EXCEEDED,
		"reject oversized manifest entry-name length" );
	damaged = valid;
	WriteU32( damaged, firstSourceLengthOffset, std::numeric_limits<std::uint32_t>::max() );
	ExpectStatus( cache::DecodeManifest( damaged, decoded ), cache::Status::SIZE_LIMIT_EXCEEDED,
		"reject oversized manifest source-path length" );
	damaged = valid;
	WriteU32( damaged, firstOptionsLengthOffset, std::numeric_limits<std::uint32_t>::max() );
	ExpectStatus( cache::DecodeManifest( damaged, decoded ), cache::Status::SIZE_LIMIT_EXCEEDED,
		"reject oversized manifest options length" );
	damaged = valid;
	WriteU32( damaged, firstEntryOffset, std::numeric_limits<std::uint32_t>::max() );
	RewriteIntegrityHash( damaged );
	ExpectStatus( cache::DecodeManifest( damaged, decoded ), cache::Status::INVALID_ENUM_VALUE,
		"reject unknown manifest entry type" );

	cache::DecodeLimits limits;
	limits.maxManifestEntries = canonical.entries.size() - 1;
	ExpectStatus( cache::DecodeManifest( valid, decoded, limits ), cache::Status::SIZE_LIMIT_EXCEEDED,
		"caller manifest entry-count limit" );
	limits = cache::DecodeLimits();
	limits.maxEntryOptionsBytes = 1;
	ExpectStatus( cache::DecodeManifest( valid, decoded, limits ), cache::Status::SIZE_LIMIT_EXCEEDED,
		"caller manifest options limit" );
	limits = cache::DecodeLimits();
	limits.maxAggregateStringBytes = canonical.mapKey.size();
	ExpectStatus( cache::DecodeManifest( valid, decoded, limits ), cache::Status::SIZE_LIMIT_EXCEEDED,
		"caller manifest aggregate-byte limit" );

	const cache::Manifest source = ExampleManifest();
	cache::ManifestExpectation expected = ExpectationFor( source );
	expected.mapKey = "game/medlabs";
	ExpectStatus( cache::DecodeManifestForKey( valid, expected, decoded ),
		cache::Status::MAP_KEY_MISMATCH, "manifest map key mismatch" );
	expected = ExpectationFor( source );
	expected.gameMode[0] ^= 1;
	ExpectStatus( cache::DecodeManifestForKey( valid, expected, decoded ),
		cache::Status::GAME_MODE_MISMATCH, "manifest full game-mode key mismatch" );
	expected = ExpectationFor( source );
	expected.entityFilter[31] ^= 1;
	ExpectStatus( cache::DecodeManifestForKey( valid, expected, decoded ),
		cache::Status::ENTITY_FILTER_MISMATCH, "manifest full entity-filter key mismatch" );
	expected = ExpectationFor( source );
	expected.contentSignature[0] ^= 1;
	ExpectStatus( cache::DecodeManifestForKey( valid, expected, decoded ),
		cache::Status::CONTENT_SIGNATURE_MISMATCH, "manifest content key mismatch" );
	expected = ExpectationFor( source );
	expected.settingsSignature[0] ^= 1;
	ExpectStatus( cache::DecodeManifestForKey( valid, expected, decoded ),
		cache::Status::SETTINGS_SIGNATURE_MISMATCH, "manifest settings key mismatch" );
}

static void ExerciseManifestCanonicalRejection() {
	cache::Manifest manifest;
	manifest.producerVersion = 11;
	manifest.mapKey = "game/testmap";
	manifest.gameMode = HashText( "single-player" );
	manifest.entityFilter = HashText( "default" );
	manifest.contentSignature = HashText( "content" );
	manifest.settingsSignature = HashText( "settings" );
	manifest.entries.push_back( ExampleEntry( cache::ManifestEntryType::RAW_FILE,
		"files/a", "source/a", cache::ManifestPriority::NORMAL, 1, 1 ) );
	manifest.entries.push_back( ExampleEntry( cache::ManifestEntryType::RAW_FILE,
		"files/b", "source/b", cache::ManifestPriority::NORMAL, 2, 1 ) );
	Expect( manifest.entries[0].normalizedName.size() == manifest.entries[1].normalizedName.size() &&
		manifest.entries[0].source.normalizedPath.size() == manifest.entries[1].source.normalizedPath.size(),
		"canonical rejection fixture has equal entry sizes" );

	std::vector<std::uint8_t> encoded;
	ExpectStatus( cache::EncodeManifest( manifest, encoded ), cache::Status::OK,
		"encode canonical-rejection fixture" );
	const std::size_t entryStart = 148 + manifest.mapKey.size();
	const std::size_t entryBytes = 60 + manifest.entries[0].normalizedName.size() +
		manifest.entries[0].source.normalizedPath.size() + manifest.entries[0].options.size();
	Expect( entryStart + entryBytes * 2 + cache::HASH_BYTES + 4 == encoded.size(),
		"canonical rejection fixture wire-size calculation" );
	if ( entryStart + entryBytes * 2 + cache::HASH_BYTES + 4 != encoded.size() ) {
		return;
	}

	std::vector<std::uint8_t> duplicate = encoded;
	std::memcpy( duplicate.data() + entryStart + entryBytes,
		duplicate.data() + entryStart, entryBytes );
	RewriteIntegrityHash( duplicate );
	cache::Manifest decoded;
	ExpectStatus( cache::DecodeManifest( duplicate, decoded ), cache::Status::DUPLICATE_ENTRY,
		"reject duplicate manifest entry on disk" );

	std::vector<std::uint8_t> reversed = encoded;
	std::vector<std::uint8_t> firstEntry( entryBytes );
	std::memcpy( firstEntry.data(), reversed.data() + entryStart, entryBytes );
	std::memcpy( reversed.data() + entryStart,
		reversed.data() + entryStart + entryBytes, entryBytes );
	std::memcpy( reversed.data() + entryStart + entryBytes, firstEntry.data(), entryBytes );
	RewriteIntegrityHash( reversed );
	ExpectStatus( cache::DecodeManifest( reversed, decoded ), cache::Status::NON_CANONICAL_ORDER,
		"reject non-canonical manifest entry order" );
}

int main() {
	ExerciseHashAndPathPrimitives();

	std::vector<std::uint8_t> envelopeBytes;
	ExerciseEnvelopeRoundTrip( envelopeBytes );
	if ( !envelopeBytes.empty() ) {
		ExerciseEnvelopeFailures( envelopeBytes );
		ExerciseEnvelopeKeyAndCompression( envelopeBytes );
	}

	std::vector<std::uint8_t> manifestBytes;
	cache::Manifest canonicalManifest;
	ExerciseManifestRoundTrip( manifestBytes, canonicalManifest );
	ExerciseManifestDeterminism();
	if ( !manifestBytes.empty() ) {
		ExerciseManifestFailures( manifestBytes, canonicalManifest );
	}
	ExerciseManifestCanonicalRejection();

	if ( failures != 0 ) {
		std::fprintf( stderr, "level-load cache format native test: %d failure(s)\n", failures );
		return 1;
	}
	std::printf( "level-load cache format native test: ok\n" );
	return 0;
}
