/*
===========================================================================

openQ4 authenticated remote-console protocol
Copyright (C) 2026 DarkMatter Productions

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

===========================================================================
*/

#ifndef __RCON2PROTOCOL_H__
#define __RCON2PROTOCOL_H__

#include "../../idlib/CryptoHash.h"

#include <cstddef>
#include <cstdint>

namespace idRcon2 {

static constexpr std::uint8_t PROTOCOL_VERSION = 1;
static constexpr std::size_t NONCE_BYTES = 16;
static constexpr std::size_t SALT_BYTES = 16;
static constexpr std::size_t ENDPOINT_BINDING_BYTES = 16;
static constexpr std::size_t REQUEST_DIGEST_BYTES = idCrypto::SHA256_DIGEST_BYTES;
static constexpr std::size_t PROOF_BYTES = idCrypto::SHA256_DIGEST_BYTES;
static constexpr std::size_t VERIFIER_BYTES = idCrypto::SHA256_DIGEST_BYTES;
static constexpr std::uint32_t PBKDF2_ITERATIONS = 200000;
static constexpr std::size_t MIN_PASSWORD_BYTES = 12;

void HashRequest( const char *command,
	std::uint8_t digest[ REQUEST_DIGEST_BYTES ] );

bool DeriveVerifier( const char *password,
	const std::uint8_t salt[ SALT_BYTES ],
	std::uint8_t verifier[ VERIFIER_BYTES ] );

void ComputeProof( const std::uint8_t verifier[ VERIFIER_BYTES ],
	const std::uint8_t clientNonce[ NONCE_BYTES ],
	const std::uint8_t serverNonce[ NONCE_BYTES ],
	const std::uint8_t endpointBinding[ ENDPOINT_BINDING_BYTES ],
	const std::uint8_t requestDigest[ REQUEST_DIGEST_BYTES ],
	std::uint8_t proof[ PROOF_BYTES ] );

} // namespace idRcon2

#endif /* !__RCON2PROTOCOL_H__ */
