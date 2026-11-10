// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once

#include <array>
#include <string>

namespace openq4 {

struct SaveGameTransactionFile {
	std::string temporary, final, backup;
	bool backedUp = false, published = false;
};

struct SaveGameTransactionResult {
	bool committed = false;
	bool recoveryNeeded = false;
	bool cleanupComplete = true;
	std::string error;
};

// All paths are resolved before dispatch, and the application serializes access
// to the slot until completion. Files are description, preview, then payload.
// Staged bytes have already passed persistence/readback and format validation.
// Ops exposes checked Exists/Move/Remove on exact regular-file paths only.
template<class Ops>
SaveGameTransactionResult CommitSaveGame( std::array<SaveGameTransactionFile, 3>& files,
	Ops& ops, bool removePreview ) {
	SaveGameTransactionResult result;
	std::array<bool, 3> existed{};
	for ( std::size_t i = 0; i < files.size(); ++i ) {
		bool temporary = false, backup = false;
		if ( !ops.Exists( files[i].temporary, temporary, result.error ) || !temporary ||
			 !ops.Exists( files[i].final, existed[i], result.error ) ||
			 !ops.Exists( files[i].backup, backup, result.error ) ) {
			if ( result.error.empty() ) result.error = "staged save component is missing";
			return result;
		}
		if ( backup ) {
			result.error = "save backup still requires recovery";
			result.recoveryNeeded = true;
			return result;
		}
	}

	const auto rollback = [&]() {
		std::string error;
		// Put published components back under their temporary names before
		// consuming any backups. This retains the existing recovery protocol's
		// evidence of which components were published if rollback is interrupted.
		for ( std::size_t n = files.size(); n > 0; --n ) {
			auto& file = files[n - 1];
			if ( file.published ) {
				if ( !ops.Move( file.final, file.temporary, error ) ) {
					result.recoveryNeeded = true;
					return;
				}
				file.published = false;
			}
		}
		for ( auto& file : files ) if ( file.backedUp ) {
			if ( !ops.Move( file.backup, file.final, error ) ) {
				result.recoveryNeeded = true;
				return;
			}
			file.backedUp = false;
		}
		// Clear the payload sentinel first. If its removal fails, retain every
		// component's temporary so recovery never mistakes restored old sidecars
		// for newly published files without backups.
		if ( !ops.Remove( files[2].temporary, error ) ) {
			result.recoveryNeeded = true;
			return;
		}
		for ( std::size_t i = 0; i < 2; ++i ) {
			if ( !ops.Remove( files[i].temporary, error ) ) result.cleanupComplete = false;
		}
	};

	for ( std::size_t i = 0; i < files.size(); ++i ) if ( existed[i] ) {
		if ( !ops.Move( files[i].final, files[i].backup, result.error ) ) {
			rollback();
			return result;
		}
		files[i].backedUp = true;
	}
	for ( auto& file : files ) {
		if ( !ops.Move( file.temporary, file.final, result.error ) ) {
			rollback();
			return result;
		}
		file.published = true;
	}
	// The final payload rename publishes the complete slot. Cleanup failure
	// leaves a valid committed save plus recovery evidence, never a false abort.
	result.committed = true;
	for ( auto& file : files ) if ( file.backedUp ) {
		if ( !ops.Remove( file.backup, result.error ) ) result.cleanupComplete = false;
		else file.backedUp = false;
	}
	if ( removePreview && !ops.Remove( files[1].final, result.error ) ) result.cleanupComplete = false;
	return result;
}

} // namespace openq4
