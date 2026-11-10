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

#include "Rcon2Protocol.h"

#include <cstring>

namespace idRcon2 {

void HashRequest( const char *command,
		std::uint8_t digest[ REQUEST_DIGEST_BYTES ] ) {
	if ( command == nullptr ) {
		idCrypto::SHA256( nullptr, 0, digest );
		return;
	}
	idCrypto::SHA256( command, std::strlen( command ), digest );
}

bool DeriveVerifier( const char *password,
		const std::uint8_t salt[ SALT_BYTES ],
		std::uint8_t verifier[ VERIFIER_BYTES ] ) {
	if ( password == nullptr || salt == nullptr || verifier == nullptr ) {
		return false;
	}
	const std::size_t passwordBytes = std::strlen( password );
	if ( passwordBytes < MIN_PASSWORD_BYTES ) {
		return false;
	}
	return idCrypto::PBKDF2HMACSHA256( password, passwordBytes,
		salt, SALT_BYTES, PBKDF2_ITERATIONS, verifier, VERIFIER_BYTES );
}

void ComputeProof( const std::uint8_t verifier[ VERIFIER_BYTES ],
		const std::uint8_t clientNonce[ NONCE_BYTES ],
		const std::uint8_t serverNonce[ NONCE_BYTES ],
		const std::uint8_t endpointBinding[ ENDPOINT_BINDING_BYTES ],
		const std::uint8_t requestDigest[ REQUEST_DIGEST_BYTES ],
		std::uint8_t proof[ PROOF_BYTES ] ) {
	static constexpr char PROOF_DOMAIN[] = "openQ4-rcon2-proof-v1";
	static constexpr std::size_t PROOF_DOMAIN_BYTES = sizeof( PROOF_DOMAIN ) - 1;
	std::uint8_t message[ PROOF_DOMAIN_BYTES + 1 + NONCE_BYTES + NONCE_BYTES +
		ENDPOINT_BINDING_BYTES + REQUEST_DIGEST_BYTES ];
	std::size_t offset = 0;
	std::memcpy( message + offset, PROOF_DOMAIN, PROOF_DOMAIN_BYTES );
	offset += PROOF_DOMAIN_BYTES;
	message[ offset++ ] = PROTOCOL_VERSION;
	std::memcpy( message + offset, clientNonce, NONCE_BYTES );
	offset += NONCE_BYTES;
	std::memcpy( message + offset, serverNonce, NONCE_BYTES );
	offset += NONCE_BYTES;
	std::memcpy( message + offset, endpointBinding, ENDPOINT_BINDING_BYTES );
	offset += ENDPOINT_BINDING_BYTES;
	std::memcpy( message + offset, requestDigest, REQUEST_DIGEST_BYTES );
	idCrypto::HMACSHA256( verifier, VERIFIER_BYTES, message, sizeof( message ), proof );
	idCrypto::SecureZero( message, sizeof( message ) );
}

} // namespace idRcon2
