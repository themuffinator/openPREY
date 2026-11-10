// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
// Late-look policy (HF-03): the production header driven by a deterministic
// model of the usercmd pipeline. It proves the drawn view reaches unapplied
// input without latency, stays continuous across tics, honours the pitch
// clamp and angle wrap, and collapses safely on discontinuities. It is a
// policy test, not a replay of the whole game; the engine sampler's read-only
// boundary is pinned by presentation_look_contract.py.
#include "src/framework/PresentationLook.h"
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>

#define CHECK(value) do { if (!(value)) { std::fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #value); std::exit(1); } } while (0)

static bool Near(double a, double b, double epsilon = 0.0001) { return std::fabs(a - b) < epsilon; }

// usercmd angles travel as 16-bit shorts, as ANGLE2SHORT/SHORT2ANGLE do
static float Quantize(double degrees) {
	const long s = std::lround(degrees * 65536.0 / 360.0) & 65535;
	return float(s * (360.0 / 65536.0));
}

static float Normalize180(double degrees) {
	return float(std::remainder(degrees, 360.0));
}

static void AngleArithmetic() {
	CHECK(Near(openq4::PresentationAngleDelta(179.0f, -179.0f), -2.0));
	CHECK(Near(openq4::PresentationAngleDelta(-179.0f, 179.0f), 2.0));
	CHECK(Near(openq4::PresentationAngleDelta(10.0f, 370.0f), 0.0));
	CHECK(Near(openq4::PresentationAngleDelta(720.5f, 0.0f), 0.5));
	CHECK(Near(openq4::PresentationAngleDelta(180.0f, 0.0f), -180.0));
	CHECK(Near(openq4::PresentationAngleDelta(100000.25f, 99999.75f), 0.5, 0.01));

	CHECK(openq4::PresentationRateShare(120.0f, -0.004, 1.0 / 60.0) == 0.0f);
	CHECK(Near(openq4::PresentationRateShare(120.0f, 0.005, 1.0 / 60.0), 0.6));
	CHECK(Near(openq4::PresentationRateShare(120.0f, 0.5, 1.0 / 60.0), 2.0));
	CHECK(openq4::PresentationRateShare(120.0f, std::nan(""), 1.0 / 60.0) == 0.0f);
	CHECK(openq4::PresentationRateShare(120.0f, 0.005, 0.0) == 0.0f);

	// The view followed its commands (including across the wrap), or it was
	// held while the commands moved on (radial selector, scripted lock).
	CHECK(openq4::PresentationLookCoupled(10.0f, 15.0f, 100.0f, 105.0f));
	CHECK(openq4::PresentationLookCoupled(178.0f, -178.0f, -2.0f, 2.0f));
	CHECK(openq4::PresentationLookCoupled(20.0f, 20.0f, 33.0f, 33.0f));
	CHECK(!openq4::PresentationLookCoupled(20.0f, 20.0f, 33.0f, 38.0f));
	CHECK(!openq4::PresentationLookCoupled(20.0f, 50.0f, 33.0f, 33.0f)); // teleport/SetViewAngles
}

static void Correction() {
	openq4::PresentationLookSample s;
	s.previousYaw = 10.0f; s.currentYaw = 20.0f;
	s.appliedYaw = 200.0f; s.inputYaw = 205.0f; // the game's view keeps its own delta
	s.fraction = 0.5f;
	openq4::PresentationLookCorrection c = openq4::ComputePresentationLook(s);
	CHECK(c.valid && Near(c.yaw, 10.0) && Near(c.pitch, 0.0)); // 15 drawn -> 25 wanted

	// not interpolating: only unapplied input turns the view
	s.fraction = 1.0f;
	c = openq4::ComputePresentationLook(s);
	CHECK(c.valid && Near(c.yaw, 5.0));

	// pitch stops at the clamp the game will apply, from either side
	s.previousPitch = 80.0f; s.currentPitch = 88.0f; s.appliedPitch = 10.0f; s.inputPitch = 20.0f;
	s.fraction = 0.25f;
	c = openq4::ComputePresentationLook(s);
	CHECK(c.valid && Near(82.0 + c.pitch, 89.0));
	s.currentPitch = -88.5f; s.previousPitch = -88.5f; s.inputPitch = 0.0f;
	c = openq4::ComputePresentationLook(s);
	CHECK(c.valid && Near(-88.5 + c.pitch, -89.0));

	// discontinuities and malformed samples keep the authoritative view
	s.inputPitch = s.appliedPitch;
	s.inputYaw = s.appliedYaw + 120.0f;
	CHECK(!openq4::ComputePresentationLook(s).valid);
	s.inputYaw = std::nanf("");
	CHECK(!openq4::ComputePresentationLook(s).valid);
	s.inputYaw = s.appliedYaw;
	s.minPitch = 10.0f; s.maxPitch = -10.0f;
	CHECK(!openq4::ComputePresentationLook(s).valid);
}

// Input model: degrees turned by time t (seconds).
struct Motion {
	double rate, wobble, frequency;
	double Yaw(double t) const { return rate * t + wobble * std::sin(6.283185307179586 * frequency * t); }
	double YawSpeed() const { return std::fabs(rate) + 6.283185307179586 * frequency * std::fabs(wobble); }
	// sweeps past both pitch clamps and back
	double Pitch(double t) const { return 140.0 * std::sin(6.283185307179586 * 0.3 * t); }
};

struct RunResult { double maxLateError, minInterpLag, maxInterpLag, maxStep, maxPitch, minPitch; };

// One run of the pipeline: exact 60 Hz usercmds, buffered `bufferTics` deep
// before the game applies them (0 = built as the game runs, the default
// com_asyncInput 0; 1 = built by the async thread a tic ahead), and draws at
// `drawHz` with deterministic scheduling jitter. The game's view is its
// command plus a delta, clamped in pitch and re-based the way
// idPlayer::UpdateViewAngles and UpdateDeltaViewAngles do.
static RunResult Run(const Motion &motion, double drawHz, int bufferTics, bool lateLook, double seconds) {
	const double tick = 1.0 / 60.0;
	RunResult r = { 0.0, 1.0e9, 0.0, 0.0, -1000.0, 1000.0 };
	std::vector<float> builtYaw, builtPitch;
	int built = 0, applied = -1;
	float yawDelta = 37.5f, pitchDelta = 0.0f;
	float prevYaw = 0, curYaw = 0, prevPitch = 0, curPitch = 0, appliedYaw = 0, appliedPitch = 0;
	double previousDrawn = 0.0, previousTime = 0.0;
	bool haveDrawn = false;
	unsigned jitter = 12345u;
	const int draws = int(seconds * drawHz);
	for (int i = 1; i <= draws; ++i) {
		jitter = jitter * 1103515245u + 12345u;
		const double t = i / drawHz + ((jitter >> 16) % 1000) * 1.0e-7; // up to 0.1 ms late
		while (built * tick <= t) {
			// MakeCurrent: the command carries the input integrated to its tic
			builtYaw.push_back(float(motion.Yaw(built * tick)));
			builtPitch.push_back(float(motion.Pitch(built * tick)));
			++built;
		}
		while (applied + 1 < built - bufferTics) {
			++applied;
			appliedYaw = Quantize(builtYaw[applied]);
			appliedPitch = Quantize(builtPitch[applied]);
			prevYaw = curYaw; prevPitch = curPitch;
			curYaw = Normalize180(double(appliedYaw) + yawDelta);
			float pitch = Normalize180(double(appliedPitch) + pitchDelta);
			pitch = pitch > 89.0f ? 89.0f : (pitch < -89.0f ? -89.0f : pitch);
			curPitch = pitch;
			yawDelta = float(openq4::PresentationAngleDelta(curYaw, appliedYaw));
			pitchDelta = float(openq4::PresentationAngleDelta(curPitch, appliedPitch));
			if (applied == 0) { prevYaw = curYaw; prevPitch = curPitch; }
		}
		if (applied < 1) {
			continue;
		}
		// the game observed tic `applied` when its command reached it
		const double phase = (t - (applied + bufferTics) * tick) / tick;
		const float fraction = float(phase < 0.0 ? 0.0 : (phase > 1.0 ? 1.0 : phase));
		const double interpYaw = prevYaw + openq4::PresentationAngleDelta(curYaw, prevYaw) * fraction;
		const double interpPitch = prevPitch + (curPitch - prevPitch) * fraction;
		double drawnYaw = interpYaw, drawnPitch = interpPitch;
		if (lateLook) {
			openq4::PresentationLookSample s;
			s.previousYaw = prevYaw; s.currentYaw = curYaw;
			s.previousPitch = prevPitch; s.currentPitch = curPitch;
			s.appliedYaw = appliedYaw; s.appliedPitch = appliedPitch;
			// GetPresentationViewAngles: the next command's angles if built now
			s.inputYaw = float(motion.Yaw(t)); s.inputPitch = float(motion.Pitch(t));
			s.fraction = fraction;
			const openq4::PresentationLookCorrection c = openq4::ComputePresentationLook(s);
			CHECK(c.valid);
			drawnYaw += c.yaw;
			drawnPitch += c.pitch;
		}
		// the view the next command would give if it were built now
		const double wantedYaw = motion.Yaw(t) + yawDelta;
		double wantedPitch = Normalize180(motion.Pitch(t) + pitchDelta);
		wantedPitch = wantedPitch > 89.0 ? 89.0 : (wantedPitch < -89.0 ? -89.0 : wantedPitch);
		const double yawError = std::fabs(openq4::PresentationAngleDelta(float(drawnYaw), float(wantedYaw)));
		if (lateLook) {
			r.maxLateError = std::fmax(r.maxLateError, std::fmax(yawError, std::fabs(drawnPitch - wantedPitch)));
		} else {
			r.minInterpLag = std::fmin(r.minInterpLag, yawError);
			r.maxInterpLag = std::fmax(r.maxInterpLag, yawError);
		}
		if (haveDrawn) {
			// how far a draw turned beyond the input's own motion since the last draw
			const double step = std::fabs(openq4::PresentationAngleDelta(float(drawnYaw), float(previousDrawn)));
			r.maxStep = std::fmax(r.maxStep, step - motion.YawSpeed() * (t - previousTime) * 1.01);
		}
		previousDrawn = drawnYaw;
		previousTime = t;
		haveDrawn = true;
		r.maxPitch = std::fmax(r.maxPitch, drawnPitch);
		r.minPitch = std::fmin(r.minPitch, drawnPitch);
	}
	return r;
}

static void Pipeline() {
	const double rates[] = { 30.0, 60.0, 144.0, 165.0, 240.0, 360.0, 997.0 };
	const Motion steady = { 90.0, 0.0, 0.0 };
	const Motion rapid = { 1000.0, 60.0, 2.0 }; // flick-speed turns, many times through the wrap
	for (const Motion &motion : { steady, rapid }) {
		for (int buffer = 0; buffer <= 1; ++buffer) {
			for (double hz : rates) {
				const RunResult late = Run(motion, hz, buffer, true, 10.0);
				const RunResult interp = Run(motion, hz, buffer, false, 10.0);
				// Late look shows the input the moment it is sampled, up to the
				// 16-bit command quantization (0.0055 degrees) and float rounding at
				// these magnitudes; interpolation always trails by at least a tic.
				CHECK(late.maxLateError < 0.02);
				if (motion.wobble == 0.0) {
					CHECK(interp.minInterpLag > std::fabs(motion.rate) / 60.0 * 0.9);
				}
				CHECK(interp.maxInterpLag > std::fabs(motion.rate) / 60.0 * 0.9);
				// No staircase: a draw never turns further than the input did since
				// the previous draw, plus quantization.
				CHECK(late.maxStep <= 0.02);
				// Pitch never leaves the authoritative clamp.
				CHECK(late.maxPitch <= 89.0001 && late.minPitch >= -89.0001);
			}
		}
	}
}

// Held look keys and sticks are integrated once per command at a fixed rate;
// the sampler shows the elapsed share of the coming tick.
static void HeldRates() {
	const double tick = 1.0 / 60.0;
	const float rate = 140.0f; // in_yawspeed
	double previousDrawn = 0.0;
	double maxStep = 0.0;
	for (int i = 0; i <= 2400; ++i) {
		const double t = i / 240.0;
		const int commands = int(t / tick + 1e-9);
		const double builtAt = commands * tick;
		const float builtYaw = float(commands * rate * tick);
		const float drawn = builtYaw + openq4::PresentationRateShare(rate, t - builtAt, tick);
		CHECK(Near(drawn, rate * t, 0.001));
		if (i > 0) {
			maxStep = std::fmax(maxStep, drawn - previousDrawn);
		}
		previousDrawn = drawn;
	}
	CHECK(maxStep <= rate / 240.0 + 0.001);
	// A late command build (a stalled main thread) never extrapolates past one tick.
	CHECK(Near(openq4::PresentationRateShare(rate, 0.25, tick), rate * tick));
}

int main() {
	AngleArithmetic();
	Correction();
	Pipeline();
	HeldRates();
	std::puts("presentation look: zero-latency drawn input, continuity, clamps, wrap and discontinuity policy passed");
	return 0;
}
