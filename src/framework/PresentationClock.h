// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>

namespace openq4 {

// Draw-only clock policy shared by SP and MP. None of this state is serialized,
// transmitted, or used to schedule simulation. The input clock is monotonic ms
// with fractional precision, NOT Sys_Milliseconds or an OpenXR XrTime.
class PresentationClock {
public:
	void Reset() { valid = false; }
	double SampleTimeMilliseconds() const { return lastObserved; }

	float Phase(int gameTime, int gameStep, int hz, double now, bool frozen) {
		if (hz <= 0 || gameStep <= 0 || !std::isfinite(now)) {
			Reset();
			return 1.0f;
		}
		const double period = 1000.0 / hz;
		// Widen before subtracting: a map reset or signed game-clock wrap must
		// reseed transient presentation without overflowing authoritative time.
		const std::int64_t delta = std::int64_t(gameTime) - anchorGame;
		if (!valid || frozen || hz != rate || gameStep != step || delta < 0 ||
			delta > std::int64_t(gameStep) * 4 || now < lastObserved ||
			(delta > 0 && now - anchorReal > period * 4)) {
			anchorReal = now;
			lastMaterial = gameTime;
			valid = true;
		} else if (delta > 0) {
			// Predict the boundary, rather than stamping the late draw time onto
			// every tick. Early observations correct immediately; late ones creep.
			anchorReal += (double(delta) / gameStep) * period;
			anchorReal += (std::min)(now - anchorReal, 1.0);
		}
		anchorGame = gameTime;
		lastObserved = now;
		rate = hz;
		step = gameStep;
		// An unchanged tick saturates, even after a long stall. Re-anchoring it
		// periodically would make paused movers cycle between their two poses.
		return frozen ? 1.0f : float((std::max)(0.0, (std::min)(1.0, (now - anchorReal) / period)));
	}

	int MaterialTime(int gameTime, int gameStep, float phase) {
		const int offset = int((std::max)(0.0, (std::min)(double(gameStep), double(phase) * gameStep)));
		const std::int64_t candidate = std::int64_t(gameTime) + offset;
		const int bounded = int((std::min)(candidate, std::int64_t((std::numeric_limits<int>::max)())));
		lastMaterial = (std::max)(lastMaterial, bounded);
		return lastMaterial;
	}

private:
	bool valid = false;
	int anchorGame = 0, lastMaterial = 0, rate = 0, step = 0;
	double anchorReal = 0.0, lastObserved = 0.0;
};

// Host-clock frame delta for smooth turning. Predicted XR display time stays
// in the runtime's domain and is used only for locating/submitting poses.
class PresentationFrameDelta {
public:
	void Reset() { valid = false; }
	float Sample(double ticks, double frequency) {
		if (!(frequency > 0.0) || !std::isfinite(frequency) || !std::isfinite(ticks)) {
			Reset();
			return 0.0f;
		}
		const double seconds = valid && frequency == rate ? (ticks - previous) / frequency : 0.0;
		previous = ticks;
		rate = frequency;
		valid = true;
		return float((std::max)(0.0, (std::min)(0.1, seconds)));
	}
private:
	bool valid = false;
	double previous = 0.0, rate = 0.0;
};

} // namespace openq4
