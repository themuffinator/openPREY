// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once

#include <cmath>

namespace openq4 {

// Draw-only late-look policy shared by the input sampler and both game modules.
// Nothing here is serialized, transmitted or written back into a usercmd: it
// only decides how far the drawn camera may turn ahead of the last
// authoritative view, toward input the game has not applied yet. Traces,
// damage, projectile spawns, network events and RNG keep reading the
// authoritative view.

// Signed shortest difference a - b in degrees, within [-180, 180).
inline float PresentationAngleDelta(float a, float b) {
	const double d = std::fmod(double(a) - double(b), 360.0);
	const double wrapped = d >= 180.0 ? d - 360.0 : (d < -180.0 ? d + 360.0 : d);
	return float(wrapped);
}

// Rate sources a usercmd integrates once per tick (held look keys, stick
// deflection) reach the drawn view as the share of the coming tick that has
// already elapsed. The next usercmd then applies the whole tick, so a steady
// rate draws as a straight line instead of a 60 Hz staircase.
inline float PresentationRateShare(float degreesPerSecond, double elapsedSeconds, double tickSeconds) {
	if (!(tickSeconds > 0.0) || !std::isfinite(elapsedSeconds) || !std::isfinite(degreesPerSecond)) {
		return 0.0f;
	}
	const double share = elapsedSeconds < 0.0 ? 0.0 : (elapsedSeconds > tickSeconds ? tickSeconds : elapsedSeconds);
	return float(double(degreesPerSecond) * share);
}

// True when the authoritative view followed its usercmds between two camera
// samples. Modes that hold or override the view (wheel cursors, scripted
// locks, Arena freezes, influence effects, teleports) fail it, and late look
// stands down rather than turning the camera ahead of a view that will not
// follow. Yaw alone decides: pitch legitimately stops at its clamp.
inline bool PresentationLookCoupled(float previousViewYaw, float currentViewYaw,
	float previousCommandYaw, float currentCommandYaw, float tolerance = 0.05f) {
	const float viewStep = PresentationAngleDelta(currentViewYaw, previousViewYaw);
	const float commandStep = PresentationAngleDelta(currentCommandYaw, previousCommandYaw);
	return std::fabs(PresentationAngleDelta(viewStep, commandStep)) <= tolerance;
}

struct PresentationLookSample {
	// Authoritative view angles at the camera's previous and current samples.
	float previousYaw = 0.0f, previousPitch = 0.0f;
	float currentYaw = 0.0f, currentPitch = 0.0f;
	// Angles of the usercmd the game last applied, and the generator's angles
	// including everything it has not handed to the game yet.
	float appliedYaw = 0.0f, appliedPitch = 0.0f;
	float inputYaw = 0.0f, inputPitch = 0.0f;
	// The camera's previous-to-current blend; 1 when it is not interpolating.
	float fraction = 1.0f;
	float minPitch = -89.0f, maxPitch = 89.0f;
};

struct PresentationLookCorrection {
	float yaw = 0.0f, pitch = 0.0f;
	bool valid = false;
};

// The camera is drawn at lerp(previous, current, fraction) plus its view
// offsets (bob, kick, shake). Late look replaces only the input-driven part
// with current + unapplied input, so the view turns on the next draw instead of
// up to a tick later. More than maxUnapplied degrees of unapplied input is a
// discontinuity (map change, angle reset), not motion.
inline PresentationLookCorrection ComputePresentationLook(const PresentationLookSample &s, float maxUnapplied = 90.0f) {
	PresentationLookCorrection out;
	const float values[] = { s.previousYaw, s.previousPitch, s.currentYaw, s.currentPitch,
		s.appliedYaw, s.appliedPitch, s.inputYaw, s.inputPitch, s.fraction, s.minPitch, s.maxPitch };
	for (float value : values) {
		if (!std::isfinite(value)) {
			return out;
		}
	}
	const float pendingYaw = PresentationAngleDelta(s.inputYaw, s.appliedYaw);
	const float pendingPitch = PresentationAngleDelta(s.inputPitch, s.appliedPitch);
	if (std::fabs(pendingYaw) > maxUnapplied || std::fabs(pendingPitch) > maxUnapplied || s.minPitch > s.maxPitch) {
		return out;
	}
	const float f = s.fraction < 0.0f ? 0.0f : (s.fraction > 1.0f ? 1.0f : s.fraction);
	const float drawnYaw = s.previousYaw + PresentationAngleDelta(s.currentYaw, s.previousYaw) * f;
	const float drawnPitch = s.previousPitch + PresentationAngleDelta(s.currentPitch, s.previousPitch) * f;
	float targetPitch = s.currentPitch + pendingPitch;
	targetPitch = targetPitch < s.minPitch ? s.minPitch : (targetPitch > s.maxPitch ? s.maxPitch : targetPitch);
	out.yaw = PresentationAngleDelta(s.currentYaw + pendingYaw, drawnYaw);
	out.pitch = targetPitch - drawnPitch;
	out.valid = true;
	return out;
}

} // namespace openq4
