// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#include "src/framework/PresentationClock.h"
#include <cstdio>
#include <cstdlib>
#include <vector>

#define CHECK(value) do { if (!(value)) { std::fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #value); std::exit(1); } } while (0)

static bool Near(double a, double b, double epsilon = 0.00001) { return std::abs(a - b) < epsilon; }

static void Boundaries() {
	openq4::PresentationClock clock;
	CHECK(clock.Phase(0, 16, 60, 0.0, false) == 0.0f);
	CHECK(Near(clock.Phase(0, 16, 60, 0.125, false), 0.0075));
	CHECK(Near(clock.Phase(0, 16, 60, 0.250, false), 0.015));
	CHECK(Near(clock.Phase(0, 16, 60, 16.0, false), 0.96));
	CHECK(clock.Phase(0, 16, 60, 16.6666666667, false) == 1.0f);
	CHECK(clock.Phase(16, 16, 60, 16.6666666667, false) < 0.00001f);
	CHECK(Near(clock.Phase(16, 16, 60, 25.0, false), 0.5));
	// Missed draws/catch-up advance the predicted boundary by game steps.
	CHECK(clock.Phase(64, 16, 60, 1000.0 / 15, false) < 0.00001f);
	CHECK(Near(clock.Phase(64, 16, 60, 75.0, false), 0.5));
	CHECK(clock.Phase(64, 16, 60, 100000.0, false) == 1.0f);
	CHECK(clock.Phase(64, 16, 60, 100001.0, false) == 1.0f);
	CHECK(clock.Phase(80, 16, 60, 100002.0, false) == 0.0f);
	// A slow-time step/rate change and backwards host clock reseed safely.
	CHECK(clock.Phase(88, 8, 60, 100010.0, false) == 0.0f);
	CHECK(Near(clock.Phase(88, 8, 60, 100018.3333333, false), 0.5));
	CHECK(clock.Phase(96, 8, 120, 100020.0, false) == 0.0f);
	CHECK(clock.Phase(96, 8, 120, 10.0, false) == 0.0f);
	CHECK(clock.Phase(96, 8, 120, 12.0, true) == 1.0f);
	CHECK(clock.Phase(96, 8, 120, 200.0, true) == 1.0f);
	CHECK(clock.Phase(104, 8, 120, 208.3333333, false) < 0.00001f);
	CHECK(clock.Phase(0, 16, 60, 220.0, false) == 0.0f); // restore/map
	clock.Reset();
	CHECK(clock.Phase(0, 16, 60, 230.0, false) == 0.0f);
	CHECK(clock.Phase(0, 16, 0, 230.0, false) == 1.0f);
	CHECK(clock.Phase(0, 0, 60, 230.0, false) == 1.0f);
	CHECK(clock.Phase(0, 16, 60, std::numeric_limits<double>::quiet_NaN(), false) == 1.0f);
}

static void WrapAndMapping() {
	openq4::PresentationClock clock;
	const int maximum = (std::numeric_limits<int>::max)();
	const int minimum = (std::numeric_limits<int>::min)();
	const double now = 4294967296.0; // beyond a wrapping 32-bit ms clock
	CHECK(clock.Phase(maximum - 7, 16, 60, now, false) == 0.0f);
	CHECK(Near(clock.Phase(maximum - 7, 16, 60, now + 8.3333333, false), 0.5));
	CHECK(clock.MaterialTime(maximum - 7, 16, 1.0f) == maximum);
	CHECK(clock.Phase(minimum + 8, 16, 60, now + 16.6666667, false) == 0.0f);
	CHECK(clock.MaterialTime(minimum + 8, 16, 0.5f) == minimum + 16);
	CHECK(Near(clock.Phase(minimum + 8, 16, 60, now + 25.0, false), 0.5));
	clock.Reset();
	clock.Phase(100, 16, 60, 0, false);
	CHECK(clock.MaterialTime(100, 16, 0.5f) == 108);
	CHECK(clock.MaterialTime(100, 16, 0.1f) == 108); // no backwards effects
	CHECK(clock.MaterialTime(100, 16, 1.0f) == 116);
	clock.Phase(0, 16, 60, 10, false);
	CHECK(clock.MaterialTime(0, 16, 0) == 0);
}

static void LongRunAndCaps() {
	openq4::PresentationClock clock;
	for (int tick = 0; tick < 1000000; ++tick) {
		const double boundary = tick * (1000.0 / 60);
		CHECK(clock.Phase(tick * 16, 16, 60, boundary, false) < 0.00001f);
		CHECK(Near(clock.Phase(tick * 16, 16, 60, boundary + 4.1666666667, false), 0.25));
		// Exact scheduler timestamps alternate 16/17; network/game stays 16.
		const std::int64_t scheduled = std::int64_t(tick) * 1000 / 60;
		const std::int64_t next = std::int64_t(tick + 1) * 1000 / 60;
		CHECK(next - scheduled == 16 || next - scheduled == 17);
	}
	for (int cap : {30, 60, 120, 144, 165, 240, 360, 997}) {
		clock.Reset();
		int previousTick = -1;
		float previousPhase = 0;
		// A deterministic authoritative command/event ledger is produced only
		// by ticks. Arbitrarily many presentation samples may read that state.
		std::vector<int> events;
		for (int frame = 0; frame <= cap * 30; ++frame) {
			const double jitter = frame % 7 == 0 ? 0.17 : 0.0;
			const double now = frame * 1000.0 / cap + jitter;
			const int tick = int(std::floor(now * 60.0 / 1000.0 + 1e-9));
			for (int next = previousTick + 1; next <= tick; ++next) events.push_back(next * 16);
			const int authoritative = tick * 16;
			const float phase = clock.Phase(authoritative, 16, 60, now, false);
			CHECK(phase >= 0 && phase <= 1);
			if (tick == previousTick) CHECK(phase >= previousPhase);
			CHECK(clock.MaterialTime(authoritative, 16, phase) <= authoritative + 16);
			CHECK(authoritative == tick * 16);
			previousTick = tick;
			previousPhase = phase;
		}
		CHECK(events.size() == 1801);
		for (int i = 0; i < int(events.size()); ++i) CHECK(events[i] == i * 16);
	}
}

static void XRDelta() {
	openq4::PresentationFrameDelta delta;
	CHECK(delta.Sample(1000000, 1000000) == 0);
	CHECK(Near(delta.Sample(1000125, 1000000), 0.000125));
	CHECK(Near(delta.Sample(3000000, 1000000), 0.1));
	CHECK(delta.Sample(1, 1000000) == 0); // reset/wrap
	CHECK(delta.Sample(2, 0) == 0);
	CHECK(delta.Sample(2, 1000000) == 0);
	delta.Reset();
	CHECK(delta.Sample(10000, 1000000) == 0);
	CHECK(delta.Sample(10001, 1000) == 0); // frequency discontinuity
}

int main() {
	Boundaries(); WrapAndMapping(); LongRunAndCaps(); XRDelta();
	std::puts("presentation clock: fractional phase, clocks, caps, jitter, catch-up, pause, reset, wrap and XR deltas passed");
}
