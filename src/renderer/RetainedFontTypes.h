// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once

// Physical-pixel metrics shared across the renderer module boundary. These
// contain no allocator-owned objects. Atlas identities stay valid until the
// retained view coordinator releases every context at its resource barrier.
struct renderFontMetrics_t {
	float ascent = 0, descent = 0, lineSpacing = 0, xHeight = 0;
};
struct renderFontGlyph_t {
	float advance = 0, left = 0, top = 0, width = 0, height = 0;
	float u0 = 0, v0 = 0, u1 = 0, v1 = 0;
	char image[64] = {};
};
