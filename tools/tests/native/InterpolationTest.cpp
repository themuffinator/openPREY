#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#define ID_INLINE inline
using byte = unsigned char;
using dword = std::uint32_t;
class idVec2;
class idVec3;
class idVec4;
#include "src/idlib/math/Math.h"

const float idMath::HALF_PI = 1.57079632679489661923f;
const float idMath::SQRT_1OVER2 = 0.70710678118654752440f;
const float idMath::M_DEG2RAD = 0.01745329251994329577f;

// The scalar suites below exercise the production templates directly. The
// quaternion declaration only satisfies the unused spherical specialization.
struct idQuat {
	idQuat operator+( const idQuat & ) const { std::abort(); }
	idQuat operator-( const idQuat & ) const { std::abort(); }
	idQuat operator*( float ) const { std::abort(); }
	void Slerp( const idQuat &, const idQuat &, float ) { std::abort(); }
};
#include "src/idlib/math/Extrapolate.h"
#include "src/idlib/math/Interpolate.h"

static int failures = 0;
static void Near( float actual, float expected, const char *label ) {
	if ( !std::isfinite( actual ) || std::fabs( actual - expected ) > 0.0002f ) {
		std::fprintf( stderr, "%s: expected %g, got %g\n", label, expected, actual );
		++failures;
	}
}

template<class Interpolation>
static void CheckPhases() {
	Interpolation value;
	value.Init( 100, 200, 200, 1000, 0.0f, 10.0f );
	Near( value.GetCurrentValue( 600 ), 5, "symmetric midpoint" );
	value.SetEndValue( 20 );
	Near( value.GetCurrentValue( 600 ), 10, "new endpoint must recompute speed" );
	value.SetStartValue( 10 );
	Near( value.GetCurrentValue( 600 ), 15, "new start must recompute speed" );
	value.SetStartTime( 200 );
	Near( value.GetCurrentValue( 700 ), 15, "phase timing after retime" );
	value.Init( 100, 200, 200, 0, 30.0f, 40.0f );
	Near( value.GetDuration(), 0, "zero-duration reinitialization clears old phases" );
	Near( value.GetCurrentValue( 99 ), 30, "zero-duration before start" );
	Near( value.GetCurrentValue( 100 ), 40, "zero-duration at start" );
	Near( value.GetCurrentValue( 101 ), 40, "zero-duration after start" );
	Near( value.GetCurrentSpeed( 101 ), 0, "zero-duration has no old speed" );
	value.Init( 100, 200, 200, -1, 50.0f, 60.0f );
	Near( value.GetDuration(), 0, "negative duration is instantaneous" );
	Near( value.GetCurrentValue( 100 ), 60, "negative-duration replacement" );
	value.Init( 100, -200, -200, 1000, 0.0f, 10.0f );
	Near( value.GetCurrentValue( 600 ), 5, "negative acceleration and deceleration clamp to zero" );
	Near( value.GetCurrentValue( 1100 ), 10, "clamped phases reach endpoint" );
}

int main() {
	idInterpolate<float> linear;
	linear.Init( 0, 100, 0, 10 );
	Near( linear.GetCurrentValue( 50 ), 5, "linear midpoint" );
	linear.SetEndValue( 20 );
	Near( linear.GetCurrentValue( 50 ), 10, "same-time endpoint update" );
	linear.SetStartValue( 10 );
	Near( linear.GetCurrentValue( 50 ), 15, "same-time start update" );
	linear.SetDuration( 200 );
	Near( linear.GetCurrentValue( 50 ), 12.5f, "same-time duration update" );
	linear.SetStartTime( 50 );
	Near( linear.GetCurrentValue( 50 ), 10, "same-time retime" );
	linear.Init( -100, 200, 0, 20 );
	Near( linear.GetCurrentValue( -1 ), 9.9f, "negative times are valid sample times" );

	idExtrapolate<float> motion;
	motion.Init( 100, 1000, 3, 0, 20, EXTRAPOLATION_LINEAR );
	Near( motion.GetCurrentValue( 600 ), 13, "extrapolation midpoint" );
	Near( motion.GetCurrentValue( 50 ), 3, "rewind before start" );
	Near( motion.GetCurrentValue( 50 ), 3, "cached rewind before start" );
	motion.Init( -100, 1000, 3, 0, 20, EXTRAPOLATION_LINEAR );
	Near( motion.GetCurrentValue( -1 ), 4.98f, "extrapolation cannot reserve -1 as cache sentinel" );
	CheckPhases<idInterpolateAccelDecelLinear<float>>();
	CheckPhases<idInterpolateAccelDecelSine<float>>();
	if ( !failures ) { std::puts( "interpolation mutation, rewind and phase-reset tests passed" ); }
	return failures ? 1 : 0;
}
