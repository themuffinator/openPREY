// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
// Test-only floating-point mode control. Engines can run with subnormal inputs
// and outputs flushed to zero, and the settings tests prove that exact value
// handling does not depend on that. x86-64 sets the SSE MXCSR FTZ and DAZ bits;
// AArch64 sets FPCR.FZ, which flushes both inputs and outputs. Each mode also
// selects round-to-nearest, and the destructor restores the caller's mode.
#ifndef OPENQ4_TESTS_NATIVE_FLOATFLUSHMODE_H
#define OPENQ4_TESTS_NATIVE_FLOATFLUSHMODE_H

#include <cstdint>

#if defined(__SSE__) || defined(_M_X64)
#include <xmmintrin.h>
#define OPENQ4_TEST_FLUSH_SSE 1
#elif defined(__aarch64__) && (defined(__GNUC__) || defined(__clang__))
#define OPENQ4_TEST_FLUSH_FPCR 1
#elif defined(_M_ARM64)
#include <float.h>
#define OPENQ4_TEST_FLUSH_CONTROLFP 1
#endif

namespace openq4::test {

// Whether FloatFlushMode changes anything on this target.
#if defined(OPENQ4_TEST_FLUSH_SSE) || defined(OPENQ4_TEST_FLUSH_FPCR) || defined(OPENQ4_TEST_FLUSH_CONTROLFP)
inline constexpr bool kFloatFlushAvailable = true;
#else
inline constexpr bool kFloatFlushAvailable = false;
#endif

class FloatFlushMode {
public:
	explicit FloatFlushMode(bool flush) : saved(Bits()) { Set(flush); }
	~FloatFlushMode() { Restore(saved); }
	FloatFlushMode(const FloatFlushMode&) = delete;
	FloatFlushMode& operator=(const FloatFlushMode&) = delete;

	// Flush subnormals to zero, or treat them as IEEE 754 does.
	void Set(bool flush) {
#if defined(OPENQ4_TEST_FLUSH_SSE)
		_mm_setcsr(static_cast<unsigned>((saved & ~std::uint64_t(0xe040u)) | (flush ? 0x8040u : 0u)));
#elif defined(OPENQ4_TEST_FLUSH_FPCR)
		constexpr std::uint64_t fz = std::uint64_t(1) << 24, rounding = std::uint64_t(3) << 22;
		const std::uint64_t mode = (saved & ~(fz | rounding)) | (flush ? fz : 0);
		__asm__ volatile("msr fpcr, %0" : : "r"(mode));
#elif defined(OPENQ4_TEST_FLUSH_CONTROLFP)
		unsigned int current = 0;
		_controlfp_s(&current, (flush ? _DN_FLUSH : _DN_SAVE) | _RC_NEAR, _MCW_DN | _MCW_RC);
#else
		(void)flush;
#endif
	}

	// The control state the mode sets: MXCSR, FPCR or the CRT control word.
	static std::uint64_t Bits() {
#if defined(OPENQ4_TEST_FLUSH_SSE)
		return _mm_getcsr();
#elif defined(OPENQ4_TEST_FLUSH_FPCR)
		std::uint64_t value = 0;
		__asm__ volatile("mrs %0, fpcr" : "=r"(value));
		return value;
#elif defined(OPENQ4_TEST_FLUSH_CONTROLFP)
		unsigned int current = 0;
		_controlfp_s(&current, 0, 0);
		return current;
#else
		return 0;
#endif
	}

private:
	static void Restore(std::uint64_t value) {
#if defined(OPENQ4_TEST_FLUSH_SSE)
		_mm_setcsr(static_cast<unsigned>(value));
#elif defined(OPENQ4_TEST_FLUSH_FPCR)
		__asm__ volatile("msr fpcr, %0" : : "r"(value));
#elif defined(OPENQ4_TEST_FLUSH_CONTROLFP)
		unsigned int current = 0;
		_controlfp_s(&current, static_cast<unsigned int>(value), _MCW_DN | _MCW_RC);
#else
		(void)value;
#endif
	}

	std::uint64_t saved;
};

} // namespace openq4::test

#endif // OPENQ4_TESTS_NATIVE_FLOATFLUSHMODE_H
