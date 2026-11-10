// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#ifndef OPENQ4_TOUCH_INPUT_H
#define OPENQ4_TOUCH_INPUT_H

#include <algorithm>
#include <cmath>

namespace openq4 {
namespace touch {

struct Motion {
	float side = 0, forward = 0;
	float yaw = 0, pitch = 0;		// degrees, before zoom scaling
	bool active = false;
	unsigned buttons = 0;
	unsigned canceledButtons = 0;
	int nextWeapon = 0, reload = 0;	// queued taps, emitted one per usercmd
	int impulse = -1;				// Take() result only
};

// The SDL thread posts levels/deltas; the usercmd thread consumes them under
// the engine's input critical section. This channel has no mouse/controller
// preferences, filters or device enable switch. A handoff requires a neutral
// sample before accepting another gesture.
class MotionState {
public:
	void Submit( const Motion &motion ) {
		if ( !std::isfinite( motion.side ) || !std::isfinite( motion.forward )
				|| !std::isfinite( motion.yaw ) || !std::isfinite( motion.pitch ) ) {
			Block();
			return;
		}
		if ( blocked ) {
			if ( !motion.active ) blocked = false;
			return;
		}
		if ( motion.nextWeapon < 0 || motion.reload < 0 || motion.nextWeapon > 32 || motion.reload > 32
				|| motion.nextWeapon + motion.reload > 32 - impulseCount ) {
			Block();
			return;
		}
		for ( int i = 0; i < motion.nextWeapon; ++i ) impulses[( impulseHead + impulseCount++ ) % 32] = 14;
		for ( int i = 0; i < motion.reload; ++i ) impulses[( impulseHead + impulseCount++ ) % 32] = 13;
		pending.active = motion.active;
		pressed = ( pressed | ( motion.buttons & ~pending.buttons ) ) & ~motion.canceledButtons;
		pending.buttons = motion.buttons & ~motion.canceledButtons;
		pending.side = std::clamp( motion.side, -1.0f, 1.0f );
		pending.forward = std::clamp( motion.forward, -1.0f, 1.0f );
		pending.yaw = std::clamp( pending.yaw + motion.yaw, -360.0f, 360.0f );
		pending.pitch = std::clamp( pending.pitch + motion.pitch, -90.0f, 90.0f );
	}
	Motion Take() {
		Motion result = pending;
		result.buttons |= pressed;
		pressed = 0;
		if ( impulseCount ) {
			result.impulse = impulses[impulseHead];
			impulseHead = ( impulseHead + 1 ) % 32;
			--impulseCount;
		}
		pending.yaw = pending.pitch = 0;
		return result;
	}
	void Clear() { pending = {}; pressed = 0; impulseHead = impulseCount = 0; blocked = false; }
	void Block() { Clear(); blocked = true; }
private:
	Motion pending;
	bool blocked = false;
	unsigned pressed = 0;
	int impulses[32] = {};
	int impulseHead = 0, impulseCount = 0;
};

} // namespace touch
} // namespace openq4
#endif
