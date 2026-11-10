// Copyright (C) 2026 openQ4 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef OPENQ4_SOUND_SURROUND_H
#define OPENQ4_SOUND_SURROUND_H
#include <algorithm>
#include <cmath>

// Mono radio/global VO can use the physical centre speaker. Positional NPC
// speech retains its authored direction unless the shader explicitly requests
// SSF_CENTER. Stereo/HRTF output keeps the original OpenAL mono path.
inline bool SoundUseCenterChannel(bool outputHasCenter, bool mono, bool explicitCenter,
	float fraction, float positionSquared) {
	return outputHasCenter && mono && std::isfinite(fraction) && fraction > 0.0f &&
		(explicitCenter || (std::isfinite(positionSquared) && positionSquared < 0.0001f));
}

// OpenAL's mono panner has no exclusive physical-centre mode. A direct 5.1
// buffer does. Preserve unit power while moving the authored mono signal from
// four surrounding speakers into the centre; the LFE receives no dialogue.
inline void SoundRouteMonoToCenter(const short* input, int frames, float fraction, short* output) {
	fraction = std::isfinite(fraction) ? (std::max)(0.0f, (std::min)(1.0f, fraction)) : 0.0f;
	const float surround = std::sqrt((std::max)(0.0f, 1.0f - fraction * fraction)) * 0.5f;
	for (int i = 0; i < frames; ++i) {
		const short side = static_cast<short>(std::lround(input[i] * surround));
		output[i * 6 + 0] = side;
		output[i * 6 + 1] = side;
		output[i * 6 + 2] = static_cast<short>(std::lround(input[i] * fraction));
		output[i * 6 + 3] = 0;
		output[i * 6 + 4] = side;
		output[i * 6 + 5] = side;
	}
}
#endif
