// Preserved from openQ4-game; Quake 4 SDK EULA. See docs/dev/game-test-coverage.md.
#include <climits>
#include <cstddef>
#include <cstdio>
#include <limits>

#include "../../src/idlib/StrAllocation.h"

namespace {

bool Check( bool condition, const char *message ) {
	if ( !condition ) {
		std::fprintf( stderr, "string_allocation_probe: %s\n", message );
	}
	return condition;
}

} // namespace

int main() {
	using namespace idStrAllocationDetail;

	bool ok = true;
	ok &= Check( SaturatingAdd( 17, 25 ) == 42, "ordinary addition changed" );
	ok &= Check(
		SaturatingAdd( std::numeric_limits<size_t>::max(), 1 ) == std::numeric_limits<size_t>::max(),
		"overflowing addition did not saturate"
	);
	ok &= Check( SaturatingMultiply( 6, 7 ) == 42, "ordinary multiplication changed" );
	ok &= Check(
		SaturatingMultiply( std::numeric_limits<size_t>::max(), 2 ) == std::numeric_limits<size_t>::max(),
		"overflowing multiplication did not saturate"
	);

	int roundedAmount = 0;
	ok &= Check( TryRoundUpToInt( 1, 32, roundedAmount ) && roundedAmount == 32, "small allocation did not round to 32" );
	ok &= Check( TryRoundUpToInt( 32, 32, roundedAmount ) && roundedAmount == 32, "aligned allocation changed" );

	const size_t maximumRoundedAllocation = static_cast<size_t>( INT_MAX ) / 32 * 32;
	ok &= Check(
		TryRoundUpToInt( maximumRoundedAllocation, 32, roundedAmount ) &&
			roundedAmount == static_cast<int>( maximumRoundedAllocation ),
		"largest representable rounded allocation was rejected"
	);
	ok &= Check(
		!TryRoundUpToInt( maximumRoundedAllocation + 1, 32, roundedAmount ),
		"allocation whose round-up exceeds INT_MAX was accepted"
	);
	ok &= Check( !TryRoundUpToInt( static_cast<size_t>( INT_MAX ), 32, roundedAmount ), "INT_MAX allocation was accepted" );
	ok &= Check(
		!TryRoundUpToInt( std::numeric_limits<size_t>::max(), 32, roundedAmount ),
		"SIZE_MAX allocation was accepted"
	);
	ok &= Check( !TryRoundUpToInt( 1, 0, roundedAmount ), "zero granularity was accepted" );

	if ( !ok ) {
		return 1;
	}

	std::puts( "string_allocation_probe: ok" );
	return 0;
}
