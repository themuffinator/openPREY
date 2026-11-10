// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#include "RetainedFontCache.h"
#include <cmath>
#include <charconv>
#include <cstring>

namespace openq4::fonts {
namespace {
bool ValidFace(const std::string& face, int pixels) {
	return !face.empty() && face.size() <= 128 && pixels > 0 && pixels <= Cache::MaxPixelSize;
}
void PageName(unsigned page, char (&name)[64]) {
	constexpr char prefix[] = "_ttfatlasr_";
	std::memcpy(name,prefix,sizeof(prefix)-1);
	*std::to_chars(name+sizeof(prefix)-1,name+sizeof(name)-1,page).ptr = '\0';
}
bool ValidRaster(const Raster& raster) {
	return std::isfinite(raster.advance) && raster.advance >= 0 && raster.width >= 0 && raster.height >= 0 &&
		raster.width <= Cache::PageSize-2 && raster.height <= Cache::PageSize-2 &&
		raster.coverage.size() == static_cast<size_t>(raster.width)*raster.height;
}
// One transparent gutter outside the rasterizer's own edge coverage.
std::vector<unsigned char> GlyphTexels(const Raster& raster) {
	const int width = raster.width+2, height = raster.height+2;
	std::vector<unsigned char> rgba(static_cast<size_t>(width)*height*4,255);
	for (size_t i = 3; i < rgba.size(); i += 4) rgba[i] = 0;
	for (int row = 0; row < raster.height; ++row) for (int col = 0; col < raster.width; ++col)
		rgba[(static_cast<size_t>(row+1)*width+col+1)*4+3] = raster.coverage[static_cast<size_t>(row)*raster.width+col];
	return rgba;
}
}
bool Cache::Metrics(const std::string& face, int pixels, renderFontMetrics_t& out) {
	if (!ValidFace(face,pixels)) return false;
	const auto key = std::make_pair(face,pixels);
	const auto found = faces.find(key);
	if (found != faces.end()) { out = found->second; return true; }
	if (faces.size() >= MaxFaces) return false;
	renderFontMetrics_t metrics;
	if (!source.Metrics(face,pixels,metrics) || !std::isfinite(metrics.ascent) || !std::isfinite(metrics.descent) ||
		!std::isfinite(metrics.lineSpacing) || !std::isfinite(metrics.xHeight) || metrics.lineSpacing <= 0 ||
		metrics.ascent < 0 || metrics.descent < 0 || metrics.xHeight < 0) return false;
	faces.emplace(key,metrics);
	out = metrics;
	return true;
}
bool Cache::Place(int width, int height, unsigned& page, int& x, int& y) {
	if (width <= 0 || height <= 0 || width > PageSize || height > PageSize) return false;
	for (unsigned i = 0; i < pages.size(); ++i) {
		auto& current = pages[i];
		for (auto& shelf : current.shelves) if (height <= shelf.height && shelf.used <= PageSize-width) {
			page = i; x = shelf.used; y = shelf.y; shelf.used += width; return true;
		}
		if (current.usedHeight <= PageSize-height) {
			page = i; x = 0; y = current.usedHeight;
			current.shelves.push_back({y,height,width}); current.usedHeight += height; return true;
		}
	}
	if (pages.size() >= MaxPages) return false;
	page = static_cast<unsigned>(pages.size());
	char name[64]; PageName(page,name);
	if (!device.CreatePage(page,PageSize,name)) return false;
	Page next;
	next.shelves.push_back({0,height,width}); next.usedHeight = height;
	pages.push_back(std::move(next)); x = y = 0;
	return true;
}
bool Cache::Glyph(const std::string& face, int pixels, std::uint32_t scalar, renderFontGlyph_t& out) {
	if (!ValidFace(face,pixels) || scalar > 0x10ffff || (scalar >= 0xd800 && scalar <= 0xdfff)) return false;
	int index = 0;
	if (!source.Resolve(face,scalar,index) || index < 0) return false;
	const auto key = std::make_tuple(face,pixels,index);
	const auto found = glyphs.find(key);
	if (found != glyphs.end()) { out = found->second.glyph; return true; }
	if (glyphs.size() >= MaxGlyphs) return false;
	Raster raster;
	if (!source.Rasterize(face,pixels,index,raster) || !ValidRaster(raster)) return false;
	Placed placed;
	renderFontGlyph_t& result = placed.glyph;
	result.advance = raster.advance;
	if (raster.width && raster.height) {
		const int width = raster.width+2, height = raster.height+2;
		if (!Place(width,height,placed.page,placed.x,placed.y) ||
			!device.Upload(placed.page,placed.x,placed.y,width,height,GlyphTexels(raster).data())) return false;
		result.left = static_cast<float>(raster.left); result.top = static_cast<float>(raster.top);
		result.width = static_cast<float>(raster.width); result.height = static_cast<float>(raster.height);
		result.u0 = float(placed.x+1)/PageSize; result.v0 = float(placed.y+1)/PageSize;
		result.u1 = float(placed.x+1+raster.width)/PageSize; result.v1 = float(placed.y+1+raster.height)/PageSize;
		PageName(placed.page,result.image);
	}
	glyphs.emplace(key,placed);
	out = result;
	return true;
}
bool Cache::RestorePage(unsigned page) {
	if (page >= pages.size()) return false;
	bool restored = true;
	for (const auto& [key,placed] : glyphs) {
		if (!placed.glyph.image[0] || placed.page != page) continue;
		// The source is deterministic: the same face, size and glyph rasterize
		// to the bounds the published UVs were cut for.
		Raster raster;
		if (!source.Rasterize(std::get<0>(key),std::get<1>(key),std::get<2>(key),raster) || !ValidRaster(raster) ||
			raster.width != static_cast<int>(placed.glyph.width) || raster.height != static_cast<int>(placed.glyph.height) ||
			!device.Upload(page,placed.x,placed.y,raster.width+2,raster.height+2,GlyphTexels(raster).data())) restored = false;
	}
	return restored;
}
void Cache::Reset() {
	glyphs.clear(); faces.clear(); pages.clear(); device.Reset();
}
}
