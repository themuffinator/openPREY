#ifndef OPENQ4_MVD_STORAGE_BUDGET_H
#define OPENQ4_MVD_STORAGE_BUDGET_H

#include <cstdint>
#include <filesystem>
#include <limits>
#include <system_error>

namespace openq4_mvd {

struct LibraryUsage {
	std::int64_t bytes = 0;
	unsigned int recordings = 0;
};

inline bool IsRecordingName( const std::filesystem::path &path ) {
	const auto name = path.filename().native();
	const auto endsWith = [&]( const char *suffix, std::size_t length ) {
		if ( name.size() < length ) { return false; }
		for ( std::size_t i = 0; i < length; ++i ) {
			auto c = name[name.size() - length + i];
			if ( c >= 'A' && c <= 'Z' ) { c += 'a' - 'A'; }
			if ( c != suffix[i] ) { return false; }
		}
		return true;
	};
	return endsWith( ".mvd", 4 ) || endsWith( ".mvd.part", 9 );
}

// Measure only the writable library, including nested competition recordings
// and interrupted streams. Never prune files or follow a linked directory.
// Refuse incomplete observations rather than admitting an undercounted quota.
inline bool ScanLibrary( const std::filesystem::path &root, LibraryUsage &usage ) {
	usage = {};
	std::error_code error;
	const auto status = std::filesystem::symlink_status( root, error );
	if ( error == std::errc::no_such_file_or_directory ) { return true; }
	if ( error || std::filesystem::is_symlink( status ) ) { return false; }
	if ( !std::filesystem::exists( status ) ) { return true; }
	if ( !std::filesystem::is_directory( status ) ) { return false; }
	unsigned int entries = 0;
	std::filesystem::recursive_directory_iterator entry( root, error ), end;
	if ( error ) { return false; }
	for ( ; entry != end; entry.increment( error ) ) {
		if ( error || ++entries > 16384 ) { return false; }
		const auto fileStatus = entry->symlink_status( error );
		if ( error || std::filesystem::is_symlink( fileStatus ) ) { return false; }
		if ( !std::filesystem::is_regular_file( fileStatus ) || !IsRecordingName( entry->path() ) ) { continue; }
		const auto bytes = entry->file_size( error );
		if ( error || bytes > static_cast<std::uintmax_t>( ( std::numeric_limits<std::int64_t>::max )() - usage.bytes ) ) {
			return false;
		}
		usage.bytes += static_cast<std::int64_t>( bytes );
		++usage.recordings;
	}
	return !error;
}

inline bool WouldExceedLibraryBudget( std::int64_t current, int additional,
		int indexEntries, std::int64_t budget ) {
	if ( budget <= 0 ) { return false; }
	if ( current < 0 || additional < 0 || indexEntries < 0 || current > budget ) { return true; }
	// Index header/payload, clean end, and room for the next and final index
	// entries. Backpatching the existing file header requires no extra bytes.
	const std::int64_t reserve = 2 * 24 + 8 + 20 +
		( static_cast<std::int64_t>( indexEntries ) + 2 ) * 12;
	const std::int64_t available = budget - current;
	return additional > available || reserve > available - additional;
}

} // namespace openq4_mvd

#endif
