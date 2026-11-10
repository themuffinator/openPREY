// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once

#include <cmath>

namespace openq4 {

// HF-07 frame-pacing policy shared by the engine's frame limiter, its pacing
// statistics and their native test (tools/tests/native/PresentationPacingTest.cpp).
// Nothing here touches simulation: it decides how the presentation loop waits
// for its next frame, how fast a window that shows nothing may present, and
// how frame intervals are reported.

// ---- frame-interval statistics ----

// Intervals are binned at 50 us. Whole-millisecond bins could not judge the
// 240 Hz budget (p95 4.6 ms, p99 6.3 ms): a steady 4.17 ms cadence landed in
// the 4 and 5 ms bins and read p95 5 ms.
constexpr int FRAME_PACING_BIN_USEC = 50;
constexpr int FRAME_PACING_BINS = 1321;		// 0 to 66 ms, then one overflow bin
constexpr int FRAME_PACING_OVERFLOW_BIN = FRAME_PACING_BINS - 1;

inline int FramePacingBin(double intervalMsec) {
	if (!(intervalMsec > 0.0)) {
		return 0;
	}
	const double bin = std::floor(intervalMsec * 1000.0 / FRAME_PACING_BIN_USEC);
	return bin >= double(FRAME_PACING_OVERFLOW_BIN) ? FRAME_PACING_OVERFLOW_BIN : int(bin);
}

// The nearest-rank percentile's interval: the upper edge of the bin that
// holds it, never above the longest interval seen, so a report errs long by
// less than one bin and never short. Overflowed samples report the longest.
inline float FramePacingPercentileMsec(const int *bins, int sampleCount, int percentile, float maxMsec) {
	if (bins == nullptr || sampleCount <= 0) {
		return 0.0f;
	}
	long long target = (static_cast<long long>(sampleCount) * percentile + 99) / 100;
	if (target < 1) {
		target = 1;
	}
	long long accumulated = 0;
	for (int i = 0; i < FRAME_PACING_BINS; ++i) {
		accumulated += bins[i];
		if (accumulated < target) {
			continue;
		}
		if (i == FRAME_PACING_OVERFLOW_BIN) {
			return maxMsec;
		}
		const float edge = float(i + 1) * float(FRAME_PACING_BIN_USEC) / 1000.0f;
		return edge < maxMsec ? edge : maxMsec;
	}
	return maxMsec;
}

// The declared 240 Hz target (presentation-owners.md): frame interval p95 and
// p99 budgets on the reference machine in a visible foreground window. Other
// caps are reported only. presentation_look_runtime.py judges the same values.
constexpr int SUPPORTED_PRESENTATION_CAP = 240;
constexpr float SUPPORTED_CAP_P95_BUDGET_MSEC = 4.6f;
constexpr float SUPPORTED_CAP_P99_BUDGET_MSEC = 6.3f;

enum class FramePacingBudget { NotDeclared, Met, Missed };

inline FramePacingBudget JudgeFramePacingBudget(int presentationCap, float p95Msec, float p99Msec) {
	if (presentationCap != SUPPORTED_PRESENTATION_CAP) {
		return FramePacingBudget::NotDeclared;
	}
	return p95Msec <= SUPPORTED_CAP_P95_BUDGET_MSEC && p99Msec <= SUPPORTED_CAP_P99_BUDGET_MSEC
		? FramePacingBudget::Met : FramePacingBudget::Missed;
}

// ---- windows that show nothing ----

// A hidden or minimized window shows nothing, so it never presents faster than
// this, uncapped included, on every platform. Game ticks are unaffected.
constexpr int HIDDEN_WINDOW_PRESENTATION_CAP = 60;

inline int PresentationCapForWindow(int cap, bool windowShown) {
	if (cap < 0) {
		cap = 0;
	}
	if (!windowShown && (cap == 0 || cap > HIDDEN_WINDOW_PRESENTATION_CAP)) {
		return HIDDEN_WINDOW_PRESENTATION_CAP;
	}
	return cap;
}

// ---- the frame limiter's wait ----

// The limiter sleeps most of a frame on the platform's high-resolution timer
// (SDL_DelayNS: a high-resolution waitable timer on Windows, nanosleep
// elsewhere), then spins the rest against a fixed cadence. The spin only has
// to cover how late a sleep wakes, so it follows the measured oversleep: the
// 95th percentile of the last 64 sleeps, plus a margin. That covers the
// timer's own jitter but not preemption (a thread descheduled for
// milliseconds), which no spin can hide and which would otherwise keep the
// spin wide, burning a core, for as long as it stayed in the window.
constexpr double LIMITER_MIN_SPIN_MSEC = 0.25;
constexpr double LIMITER_MAX_SPIN_MSEC = 2.0;
constexpr double LIMITER_SPIN_MARGIN_MSEC = 0.1;
constexpr double LIMITER_INITIAL_OVERSLEEP_MSEC = 0.5;

struct LimiterOversleepWindow {
	static constexpr int SIZE = 64;
	float samples[SIZE] = {};
	int count = 0;
	int next = 0;

	void Add(double oversleepMsec) {
		if (!std::isfinite(oversleepMsec) || oversleepMsec < 0.0) {
			oversleepMsec = 0.0;
		}
		samples[next] = float(oversleepMsec > LIMITER_MAX_SPIN_MSEC ? LIMITER_MAX_SPIN_MSEC : oversleepMsec);
		next = (next + 1) % SIZE;
		if (count < SIZE) {
			++count;
		}
	}

	// the nearest-rank 95th percentile of the window: its fourth-longest when full
	double Covered() const {
		if (count <= 0) {
			return LIMITER_INITIAL_OVERSLEEP_MSEC;
		}
		const int rank = count - (count * 95 + 99) / 100;	// samples longer than the percentile
		float longest[SIZE / 16 + 1] = {};
		const int keep = rank + 1;
		for (int i = 0; i < count; ++i) {
			float value = samples[i];
			for (int k = 0; k < keep; ++k) {
				if (value > longest[k]) {
					const float displaced = longest[k];
					longest[k] = value;
					value = displaced;
				}
			}
		}
		return longest[rank];
	}
};

inline double LimiterSpinMsec(const LimiterOversleepWindow &window) {
	double spin = window.Covered() + LIMITER_SPIN_MARGIN_MSEC;
	if (spin < LIMITER_MIN_SPIN_MSEC) {
		spin = LIMITER_MIN_SPIN_MSEC;
	}
	return spin > LIMITER_MAX_SPIN_MSEC ? LIMITER_MAX_SPIN_MSEC : spin;
}

// The legacy wait (com_preciseFrameWait 0): whole-millisecond sleeps, then a
// fixed spin of an eighth of the frame, at least 0.5 ms and at most 1.5 ms.
inline double LegacyLimiterSpinMsec(double frameMsec) {
	const double spin = frameMsec * 0.125;
	return spin < 0.5 ? 0.5 : (spin > 1.5 ? 1.5 : spin);
}

// ---- what holds the frame rate ----

enum class FramePacingBound {
	Unknown,
	Simulation,			// frames wait for game tics (demos, capture, coupled play)
	Vsync,				// frames wait for the display's refresh
	PresentationCap,	// the frame cap holds
	FrameWork			// nothing waits: the frame's own work sets the rate
};

struct FramePacingBoundInput {
	float avgFrameMsec = 0.0f;
	int presentationCap = 0;		// after the window policy, 0 = uncapped
	int swapInterval = 0;			// r_swapInterval: 0 off, 1 vsync, -1 adaptive
	float refreshHz = 0.0f;			// the window's display, 0 when unknown
	float ticMsec = 1000.0f / 60.0f;
	float avgTicsPerFrame = 0.0f;
	float avgGameTicsPerFrame = 0.0f;
	bool waitedForTic = false;
};

// The cap holds when frames arrive within -5%/+8% of its interval; vsync holds
// when frames come no faster than the refresh (vsync rounds a slower frame up
// to the next refresh, so any slower average mixes whole refresh intervals).
// Without a known refresh, vsync is assumed only below the tick rate, as before.
inline FramePacingBound ClassifyFramePacing(const FramePacingBoundInput &in) {
	if (!(in.avgFrameMsec > 0.0f)) {
		return FramePacingBound::Unknown;
	}
	if (in.presentationCap > 0) {
		const float capMsec = 1000.0f / float(in.presentationCap);
		if (in.avgFrameMsec >= capMsec * 0.95f && in.avgFrameMsec <= capMsec * 1.08f) {
			return FramePacingBound::PresentationCap;
		}
	}
	if (in.swapInterval != 0) {
		if (in.refreshHz > 0.0f) {
			if (in.avgFrameMsec >= (1000.0f / in.refreshHz) * 0.95f) {
				return FramePacingBound::Vsync;
			}
		} else if (in.avgFrameMsec > in.ticMsec * 1.10f) {
			return FramePacingBound::Vsync;
		}
	}
	if (in.waitedForTic || in.avgTicsPerFrame >= 0.90f || in.avgGameTicsPerFrame >= 0.90f) {
		return FramePacingBound::Simulation;
	}
	return FramePacingBound::FrameWork;
}

}	// namespace openq4
