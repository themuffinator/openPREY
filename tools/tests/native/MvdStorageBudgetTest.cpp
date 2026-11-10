#include "src/framework/async/MvdStorageBudget.h"
#include <cstdio>
#include <cstdlib>
#include <fstream>

static void Check( bool value ) { if ( !value ) { std::abort(); } }

int main( int argc, char **argv ) {
	Check( argc == 3 );
	const auto root = std::filesystem::u8path( argv[1] );
	openq4_mvd::LibraryUsage usage;
	Check( !std::filesystem::exists( root ) );
	Check( openq4_mvd::ScanLibrary( root, usage ) && usage.bytes == 0 && usage.recordings == 0 );
	std::filesystem::create_directories( root / "matches" );
	const auto write = [&]( const std::filesystem::path &name, const char *text ) {
		std::ofstream file( root / name, std::ios::binary ); file << text; Check( file.good() );
	};
	write( "one.mvd", "12345" );
	write( "matches/two.MVD.PART", "1234567" );
	write( std::filesystem::u8path( "recording-\xe2\x98\x83.MVD" ), "123" );
	write( "unrelated.part", "not a recording" );
	write( "one.mvd.backup", "not a recording" );
	Check( openq4_mvd::ScanLibrary( root, usage ) && usage.bytes == 15 && usage.recordings == 3 );
	Check( !openq4_mvd::ScanLibrary( root / "one.mvd", usage ) );
	const auto linked = std::filesystem::u8path( argv[2] );
	if ( std::filesystem::exists( linked ) ) {
		Check( !openq4_mvd::ScanLibrary( linked, usage ) );
	}
	using openq4_mvd::WouldExceedLibraryBudget;
	Check( !WouldExceedLibraryBudget( 800, 100, 0, 1000 ) );
	Check( WouldExceedLibraryBudget( 801, 100, 0, 1000 ) );
	Check( !WouldExceedLibraryBudget( 800, 40, 5, 1000 ) );
	Check( WouldExceedLibraryBudget( 801, 40, 5, 1000 ) );
	Check( WouldExceedLibraryBudget( 1001, 0, 0, 1000 ) );
	Check( WouldExceedLibraryBudget( -1, 0, 0, 1000 ) );
	Check( WouldExceedLibraryBudget( 0, -1, 0, 1000 ) );
	Check( WouldExceedLibraryBudget( 0, 0, -1, 1000 ) );
	Check( !WouldExceedLibraryBudget( 5000, 1000, 9999, 0 ) );
	const auto maximum = ( std::numeric_limits<std::int64_t>::max )();
	Check( WouldExceedLibraryBudget( maximum - 50, 40, 0, maximum ) );
	Check( !WouldExceedLibraryBudget( maximum - 100, 0, 0, maximum ) );
	std::puts( "MVD storage budget: PASS (nested/partial/Unicode files, links, exact footer reserve, overflow and disabled quota)" );
}
