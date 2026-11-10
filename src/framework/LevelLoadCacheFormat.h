/*
===========================================================================

openQ4 hardened level-load cache and preload-manifest format

Copyright (C) 2026 openQ4 contributors

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This is an original openQ4 format and implementation.  It deliberately uses
only fixed-width values and C++ standard-library types so cache validation can
be tested independently of engine and platform ABIs.

===========================================================================
*/

#ifndef __LEVEL_LOAD_CACHE_FORMAT_H__
#define __LEVEL_LOAD_CACHE_FORMAT_H__

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace idLevelLoadCache {

static constexpr std::uint32_t CACHE_FORMAT_VERSION = 1;
static constexpr std::uint32_t MANIFEST_FORMAT_VERSION = 2;
static constexpr std::size_t HASH_BYTES = 32;

static constexpr std::size_t DEFAULT_MAX_PATH_BYTES = 1024;
static constexpr std::size_t DEFAULT_MAX_MAP_KEY_BYTES = 512;
static constexpr std::size_t DEFAULT_MAX_ENTRY_NAME_BYTES = 1024;
static constexpr std::size_t DEFAULT_MAX_ENTRY_OPTIONS_BYTES = 4096;
static constexpr std::size_t DEFAULT_MAX_PAYLOAD_BYTES = 512u * 1024u * 1024u;
static constexpr std::size_t DEFAULT_MAX_DECODED_PAYLOAD_BYTES = 1024u * 1024u * 1024u;
static constexpr std::size_t DEFAULT_MAX_MANIFEST_ENTRIES = 65536;
static constexpr std::size_t DEFAULT_MAX_AGGREGATE_STRING_BYTES = 16u * 1024u * 1024u;
static constexpr std::size_t DEFAULT_MAX_ENVELOPE_BYTES = DEFAULT_MAX_PAYLOAD_BYTES + 16384u;
static constexpr std::size_t DEFAULT_MAX_MANIFEST_BYTES = 64u * 1024u * 1024u;

using Hash = std::array<std::uint8_t, HASH_BYTES>;

enum class Status {
	OK = 0,
	INVALID_ARGUMENT,
	SIZE_LIMIT_EXCEEDED,
	INTEGER_OVERFLOW,
	TRUNCATED,
	INVALID_MAGIC,
	UNSUPPORTED_VERSION,
	INVALID_END_MARKER,
	INVALID_ENUM_VALUE,
	INVALID_STRING,
	PATH_NOT_NORMALIZED,
	INVALID_FIELD,
	PAYLOAD_HASH_MISMATCH,
	INTEGRITY_MISMATCH,
	TRAILING_DATA,
	DUPLICATE_ENTRY,
	NON_CANONICAL_ORDER,
	KIND_MISMATCH,
	PARSER_VERSION_MISMATCH,
	SOURCE_MISMATCH,
	CONTENT_SIGNATURE_MISMATCH,
	SETTINGS_SIGNATURE_MISMATCH,
	MAP_KEY_MISMATCH,
	GAME_MODE_MISMATCH,
	ENTITY_FILTER_MISMATCH,
	PRODUCER_VERSION_MISMATCH
};

struct Result {
	Status			status = Status::OK;
	std::size_t		offset = 0;
	std::string		diagnostic;

	bool Ok() const {
		return status == Status::OK;
	}

	explicit operator bool() const {
		return Ok();
	}
};

struct DecodeLimits {
	std::size_t	maxPathBytes = DEFAULT_MAX_PATH_BYTES;
	std::size_t	maxMapKeyBytes = DEFAULT_MAX_MAP_KEY_BYTES;
	std::size_t	maxEntryNameBytes = DEFAULT_MAX_ENTRY_NAME_BYTES;
	std::size_t	maxEntryOptionsBytes = DEFAULT_MAX_ENTRY_OPTIONS_BYTES;
	std::size_t	maxPayloadBytes = DEFAULT_MAX_PAYLOAD_BYTES;
	std::size_t	maxDecodedPayloadBytes = DEFAULT_MAX_DECODED_PAYLOAD_BYTES;
	std::size_t	maxManifestEntries = DEFAULT_MAX_MANIFEST_ENTRIES;
	std::size_t	maxAggregateStringBytes = DEFAULT_MAX_AGGREGATE_STRING_BYTES;
	std::size_t	maxEnvelopeBytes = DEFAULT_MAX_ENVELOPE_BYTES;
	std::size_t	maxManifestBytes = DEFAULT_MAX_MANIFEST_BYTES;
};

enum class SourceContainerKind : std::uint32_t {
	LOOSE_FILE = 0,
	PK4_ARCHIVE = 1
};

struct SourceIdentity {
	std::string			normalizedPath;
	std::uint64_t		size = 0;
	std::uint64_t		timestamp = 0;
	SourceContainerKind	containerKind = SourceContainerKind::LOOSE_FILE;
	std::uint32_t		containerPk4Checksum = 0;

	bool operator==( const SourceIdentity &other ) const = default;
};

enum class CacheKind : std::uint32_t {
	RENDER_MODEL = 1,
	RENDER_WORLD = 2,
	COLLISION_MODEL = 3
};

enum class CompressionCodec : std::uint32_t {
	NONE = 0,
	DEFLATE = 1
};

struct CacheEnvelope {
	CacheKind		kind = CacheKind::RENDER_MODEL;
	std::uint32_t		parserVersion = 0;
	CompressionCodec	codec = CompressionCodec::NONE;
	SourceIdentity		source;
	Hash			contentSignature{};
	Hash			settingsSignature{};
	std::uint64_t		decodedPayloadBytes = 0;
	Hash			decodedPayloadHash{};
	std::vector<std::uint8_t> payload;

	bool operator==( const CacheEnvelope &other ) const = default;
};

struct EnvelopeExpectation {
	CacheKind		kind = CacheKind::RENDER_MODEL;
	std::uint32_t		parserVersion = 0;
	SourceIdentity		source;
	Hash			contentSignature{};
	Hash			settingsSignature{};
};

enum class ManifestEntryType : std::uint32_t {
	RENDER_MODEL = 1,
	IMAGE = 2,
	ANIMATION = 3,
	SOUND_SAMPLE = 4,
	COLLISION_MODEL = 5,
	RENDER_WORLD = 6,
	MATERIAL = 7,
	GUI = 8,
	EFFECT = 9,
	SKIN = 10,
	DECL = 11,
	RAW_FILE = 12
};

enum class ManifestPriority : std::uint32_t {
	LOW = 0,
	NORMAL = 1,
	HIGH = 2,
	CRITICAL = 3
};

struct ManifestEntry {
	ManifestEntryType		type = ManifestEntryType::RAW_FILE;
	ManifestPriority		priority = ManifestPriority::NORMAL;
	std::uint64_t			firstUseOrder = 0;
	std::uint32_t			useCount = 1;
	std::uint32_t			flags = 0;
	std::string			normalizedName;
	SourceIdentity			source;
	std::vector<std::uint8_t>	options;

	bool operator==( const ManifestEntry &other ) const = default;
};

struct Manifest {
	std::uint32_t		producerVersion = 0;
	std::string		mapKey;
	// Exact SHA-256 tokens are stored on disk.  Truncated digests would allow
	// distinct mod-controlled filters or runtime roles to share a manifest.
	Hash				gameMode{};
	Hash				entityFilter{};
	Hash			contentSignature{};
	Hash			settingsSignature{};
	std::vector<ManifestEntry> entries;

	bool operator==( const Manifest &other ) const = default;
};

struct ManifestExpectation {
	std::uint32_t	producerVersion = 0;
	std::string	mapKey;
	Hash			gameMode{};
	Hash			entityFilter{};
	Hash		contentSignature{};
	Hash		settingsSignature{};
};

// Virtual paths are lowercase, slash-separated, relative paths without empty,
// dot, or parent segments.  The result is unchanged when the input is already
// canonical.  Normalization never consults the host filesystem.
Result NormalizeVirtualPath( std::string_view input, std::string &output,
	std::size_t maximumBytes = DEFAULT_MAX_PATH_BYTES );

Hash ComputeHash( const void *data, std::size_t bytes );
const char *StatusName( Status status );

Result EncodeEnvelope( const CacheEnvelope &envelope, std::vector<std::uint8_t> &encoded,
	const DecodeLimits &limits = DecodeLimits() );
Result DecodeEnvelope( const void *data, std::size_t bytes, CacheEnvelope &envelope,
	const DecodeLimits &limits = DecodeLimits() );
Result DecodeEnvelope( const std::vector<std::uint8_t> &encoded, CacheEnvelope &envelope,
	const DecodeLimits &limits = DecodeLimits() );
Result ValidateEnvelopeKey( const CacheEnvelope &envelope, const EnvelopeExpectation &expected );
Result DecodeEnvelopeForKey( const void *data, std::size_t bytes,
	const EnvelopeExpectation &expected, CacheEnvelope &envelope,
	const DecodeLimits &limits = DecodeLimits() );
Result DecodeEnvelopeForKey( const std::vector<std::uint8_t> &encoded,
	const EnvelopeExpectation &expected, CacheEnvelope &envelope,
	const DecodeLimits &limits = DecodeLimits() );
Result ValidateDecodedPayload( const CacheEnvelope &envelope,
	const void *decodedPayload, std::size_t decodedBytes );

// Canonicalization sorts entries by replay priority and first-use order, then
// by stable entry identity.  Exact duplicate observations are merged by taking
// their earliest order, highest priority, and checked sum of use counts.
Result CanonicalizeManifest( Manifest &manifest,
	const DecodeLimits &limits = DecodeLimits() );
Result EncodeManifest( const Manifest &manifest, std::vector<std::uint8_t> &encoded,
	const DecodeLimits &limits = DecodeLimits() );
Result DecodeManifest( const void *data, std::size_t bytes, Manifest &manifest,
	const DecodeLimits &limits = DecodeLimits() );
Result DecodeManifest( const std::vector<std::uint8_t> &encoded, Manifest &manifest,
	const DecodeLimits &limits = DecodeLimits() );
Result ValidateManifestKey( const Manifest &manifest, const ManifestExpectation &expected );
Result DecodeManifestForKey( const void *data, std::size_t bytes,
	const ManifestExpectation &expected, Manifest &manifest,
	const DecodeLimits &limits = DecodeLimits() );
Result DecodeManifestForKey( const std::vector<std::uint8_t> &encoded,
	const ManifestExpectation &expected, Manifest &manifest,
	const DecodeLimits &limits = DecodeLimits() );

} // namespace idLevelLoadCache

#endif /* !__LEVEL_LOAD_CACHE_FORMAT_H__ */
