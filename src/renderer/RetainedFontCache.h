// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once
#include "RetainedFontTypes.h"
#include <cstdint>
#include <map>
#include <string>
#include <tuple>
#include <vector>

namespace openq4::fonts {

struct Raster {
	float advance = 0;
	int left = 0, top = 0, width = 0, height = 0;
	std::vector<unsigned char> coverage;
};
class Source {
public:
	virtual ~Source() = default;
	virtual bool Metrics(const std::string& face, int pixels, renderFontMetrics_t& out) = 0;
	// Resolve missing scalars to the same glyph identity, so fallback requests
	// neither duplicate atlas art nor exhaust the metadata budget.
	virtual bool Resolve(const std::string& face, std::uint32_t scalar, int& glyph) = 0;
	virtual bool Rasterize(const std::string& face, int pixels, int glyph, Raster& out) = 0;
};
class Device {
public:
	virtual ~Device() = default;
	virtual bool CreatePage(unsigned page, int dimension, const char* name) = 0;
	virtual bool Upload(unsigned page, int x, int y, int width, int height, const unsigned char* rgba) = 0;
	// Called only with no live geometry or pending retained draws.
	virtual void Reset() = 0;
};

// Append-only pages: no eviction, rectangle reuse or UV mutation while another
// view/queued draw can still reference a glyph. At the budget boundary callers
// receive an explicit failure and can use their documented legacy fallback.
// GPU storage is bounded to 128 MiB; CPU coverage exists only during a miss
// or while RestorePage rebuilds a page.
class Cache {
public:
	static constexpr int PageSize = 1024, MaxPixelSize = 512;
	static constexpr unsigned MaxPages = 32, MaxGlyphs = 16384, MaxFaces = 4096;
	Cache(Source& source, Device& device) : source(source), device(device) {}
	bool Metrics(const std::string& face, int pixels, renderFontMetrics_t& out);
	bool Glyph(const std::string& face, int pixels, std::uint32_t scalar, renderFontGlyph_t& out);
	// Rasterizes every glyph placed on a page into its original rectangle again,
	// after the device reallocated the page's storage empty (reloadImages). The
	// published UVs stay valid, so no view has to rebuild its text. False when a
	// glyph cannot be restored; it stays blank rather than moving.
	bool RestorePage(unsigned page);
	void Reset();
	unsigned PageCount() const { return static_cast<unsigned>(pages.size()); }
	unsigned GlyphCount() const { return static_cast<unsigned>(glyphs.size()); }
private:
	struct Shelf { int y, height, used; };
	struct Page { std::vector<Shelf> shelves; int usedHeight = 0; };
	// Glyphs with art also keep the rectangle they were uploaded to.
	struct Placed { renderFontGlyph_t glyph; unsigned page = 0; int x = 0, y = 0; };
	bool Place(int width, int height, unsigned& page, int& x, int& y);
	Source& source;
	Device& device;
	std::map<std::pair<std::string,int>, renderFontMetrics_t> faces;
	std::map<std::tuple<std::string,int,int>, Placed> glyphs;
	std::vector<Page> pages;
};
}
