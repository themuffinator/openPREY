// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#include "src/renderer/RetainedFontCache.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <set>

using namespace openq4::fonts;
static unsigned checks = 0;
static void Check(bool ok, const char* message) {
	++checks; if (!ok) { std::fprintf(stderr,"FAIL: %s\n",message); std::exit(1); }
}
struct Font : Source {
	int metricsCalls = 0, rasters = 0, resolves = 0, lastSize = 0;
	bool huge = false, blank = false, invalid = false;
	bool Metrics(const std::string&, int size, renderFontMetrics_t& out) override {
		++metricsCalls; out = {size*.8f,size*.2f,float(size),size*.5f};
		if (invalid) out.ascent = std::numeric_limits<float>::quiet_NaN();
		return true;
	}
	bool Resolve(const std::string&, std::uint32_t scalar, int& glyph) override {
		++resolves; glyph = scalar == 0x10fffd || scalar == 0x10fffe ? '?' : static_cast<int>(scalar); return true;
	}
	bool Rasterize(const std::string&, int size, int glyph, Raster& out) override {
		++rasters; lastSize = size; out.advance = size*.6f;
		if (blank || glyph == ' ') return true;
		out.left = -2; out.top = -size;
		out.width = huge ? Cache::PageSize-2 : std::max(1,size/2);
		out.height = huge ? Cache::PageSize-2 : size;
		out.coverage.assign(static_cast<size_t>(out.width)*out.height,static_cast<unsigned char>(1+glyph%254));
		if (invalid) out.coverage.pop_back();
		return true;
	}
};
struct Graphics : Device {
	struct Rect { unsigned page; int x,y,w,h; unsigned long long sum; };
	std::vector<Rect> rects, restored;
	unsigned created = 0, uploads = 0, resets = 0;
	bool failCreate = false, failUpload = false, restoring = false;
	bool CreatePage(unsigned page, int dimension, const char* name) override {
		if (failCreate) return false;
		Check(page == created && dimension == Cache::PageSize,"bounded sequential page creation");
		Check(std::string(name) == "_ttfatlasr_"+std::to_string(page),"deterministic reusable image identity");
		++created; return true;
	}
	bool Upload(unsigned page, int x, int y, int w, int h, const unsigned char* data) override {
		if (failUpload) return false;
		Check(page < created && x >= 0 && y >= 0 && x+w <= Cache::PageSize && y+h <= Cache::PageSize,"subimage within allocated page");
		if (!restoring) for (const auto& r : rects) Check(r.page != page || x+w <= r.x || r.x+r.w <= x || y+h <= r.y || r.y+r.h <= y,"published glyph rectangles never overlap");
		unsigned long long sum = 0;
		for (int row = 0; row < h; ++row) for (int col = 0; col < w; ++col) {
			const auto* pixel = data+(static_cast<size_t>(row)*w+col)*4;
			Check(pixel[0] == 255 && pixel[1] == 255 && pixel[2] == 255,"straight white font coverage");
			Check((pixel[3] == 0) == (row == 0 || col == 0 || row == h-1 || col == w-1),"transparent gutter separates neighboring glyphs");
			sum = sum*131+pixel[3];
		}
		if (restoring) {
			// A restore rewrites a published rectangle with the texels it held.
			Check(std::any_of(rects.begin(),rects.end(),[&](const Rect& r) {
				return r.page == page && r.x == x && r.y == y && r.w == w && r.h == h && r.sum == sum; }),"restore reuploads a published glyph unchanged");
			restored.push_back({page,x,y,w,h,sum}); return true;
		}
		rects.push_back({page,x,y,w,h,sum}); ++uploads; return true;
	}
	void Reset() override { ++resets; created = uploads = 0; rects.clear(); }
};
int main() {
	Font source; Graphics device; Cache cache(source,device);
	renderFontMetrics_t metrics;
	renderFontGlyph_t glyph, saved;
	for (int size : {1,12,24,48,49,96,144,256,512}) {
		Check(cache.Metrics("marine",size,metrics) && metrics.lineSpacing == size,"metrics in physical output pixels");
		Check(cache.Glyph("marine",size,'A',glyph) && source.lastSize == size,"rasterizer receives exact requested size");
		Check(glyph.width == std::max(1,size/2) && glyph.height == size && glyph.left == -2 && glyph.top == -size,"physical raster bounds retained without legacy scaling");
		Check(std::abs((glyph.u1-glyph.u0)*Cache::PageSize-glyph.width) < .001f,"one raster texel per output pixel");
		const int before = source.rasters; saved = glyph;
		Check(cache.Glyph("marine",size,'A',glyph) && source.rasters == before && !std::memcmp(&glyph,&saved,sizeof(glyph)),"repeat/shared-view query reuses stable glyph");
	}
	const int rasterCount = source.rasters;
	Check(cache.Glyph("lowpixel",48,'A',glyph) && source.rasters == rasterCount+1,"family participates in glyph identity");
	Check(cache.Glyph("marine",48,0x1f680,glyph),"non-BMP scalar reaches font source");
	Check(cache.Glyph("marine",48,0x10fffd,glyph),"first absent scalar resolves fallback");
	saved = glyph; const int fallbackCount = source.rasters;
	Check(cache.Glyph("marine",48,0x10fffe,glyph) && source.rasters == fallbackCount && !std::memcmp(&saved,&glyph,sizeof(glyph)),"absent scalars share resolved glyph art");
	const unsigned uploads = device.uploads;
	Check(cache.Glyph("marine",48,' ',glyph) && glyph.advance > 0 && !glyph.image[0] && device.uploads == uploads,"space keeps its advance without an atlas allocation");
	glyph = saved;
	for (unsigned cp : {0xd800u,0xdfffu,0x110000u,0xffffffffu}) Check(!cache.Glyph("marine",48,cp,glyph) && !std::memcmp(&saved,&glyph,sizeof(glyph)),"invalid scalar preserves caller output");
	for (int size : {-1,0,513,std::numeric_limits<int>::max()}) Check(!cache.Metrics("marine",size,metrics) && !cache.Glyph("marine",size,'A',glyph),"invalid output size rejected");
	source.invalid = true;
	Check(!cache.Metrics("invalid",16,metrics) && !cache.Glyph("invalid",16,'A',glyph),"invalid source metrics/coverage not published");
	source.invalid = false;
	cache.Reset(); Check(!cache.PageCount() && !cache.GlyphCount() && device.resets == 1,"resource barrier releases all cache/device ownership");
	device.failCreate = true;
	Check(!cache.Glyph("marine",16,'A',glyph) && !cache.GlyphCount() && !cache.PageCount(),"device creation failure does not publish a glyph or page");
	device.failCreate = false; device.failUpload = true;
	Check(!cache.Glyph("marine",16,'A',glyph) && !cache.GlyphCount(),"upload refusal does not publish incomplete art");
	device.failUpload = false;
	Check(cache.Glyph("marine",16,'A',glyph),"failed upload can be retried without poisoned glyph identity");
	cache.Reset(); source.huge = true;
	for (unsigned i = 0; i < Cache::MaxPages; ++i) Check(cache.Glyph("large",512,0x100+i,glyph),"maximum page budget remains usable");
	saved = glyph;
	Check(!cache.Glyph("large",512,0x1000,glyph) && !std::memcmp(&saved,&glyph,sizeof(glyph)),"page budget fails explicitly without replacing published art");
	const int before = source.rasters;
	Check(cache.Glyph("large",512,0x100,glyph) && source.rasters == before,"earliest view remains usable at budget exhaustion");
	cache.Reset(); source.huge = false; source.blank = true;
	for (unsigned i = 0; i < Cache::MaxGlyphs; ++i) Check(cache.Glyph("blank",16,0x100+i,glyph),"bounded metadata admits unique blank glyphs");
	Check(!cache.Glyph("blank",16,0x6000,glyph) && !cache.PageCount(),"metadata budget bounds no-ink glyphs independently of GPU pages");
	cache.Reset();
	for (unsigned i = 0; i < Cache::MaxFaces; ++i) Check(cache.Metrics("face"+std::to_string(i),16,metrics),"bounded metric identity");
	Check(!cache.Metrics("overflow",16,metrics) && cache.Metrics("face0",16,metrics),"metric limit preserves existing handles");
	// reloadImages reallocates a page empty. Every glyph on it is uploaded again
	// into the rectangle its published UVs already name; nothing else changes.
	cache.Reset(); source.blank = false;
	std::vector<std::pair<int,unsigned>> requests;
	for (unsigned cp = 'A'; cp <= 'E'; ++cp) requests.push_back({512,cp}); // three on page 0, two on page 1
	for (unsigned cp = 'a'; cp <= 'c'; ++cp) requests.push_back({96,cp});  // beside the first three
	std::vector<renderFontGlyph_t> published;
	for (const auto& [size,cp] : requests) { Check(cache.Glyph("marine",size,cp,glyph),"restore fixture glyph"); published.push_back(glyph); }
	Check(cache.Glyph("marine",96,' ',glyph) && cache.PageCount() == 2,"restore fixture spans two pages");
	const unsigned pageCount = cache.PageCount(), glyphCount = cache.GlyphCount();
	for (unsigned page = 0; page < pageCount; ++page) {
		const auto placed = std::count_if(device.rects.begin(),device.rects.end(),[&](const auto& r) { return r.page == page; });
		const int rasters = source.rasters;
		device.restoring = true; device.restored.clear();
		Check(cache.RestorePage(page),"every glyph on a reallocated page is restored");
		device.restoring = false;
		Check(static_cast<long>(device.restored.size()) == placed && source.rasters-rasters == placed,"restore uploads only that page's glyphs, once each");
	}
	Check(cache.PageCount() == pageCount && cache.GlyphCount() == glyphCount && device.created == pageCount,"restore neither opens pages nor publishes glyphs");
	const int restoredRasters = source.rasters;
	for (size_t i = 0; i < requests.size(); ++i)
		Check(cache.Glyph("marine",requests[i].first,requests[i].second,glyph) && !std::memcmp(&glyph,&published[i],sizeof(glyph)),"published UVs stay valid after a restore");
	Check(source.rasters == restoredRasters && !cache.RestorePage(pageCount),"restored glyphs stay cached; an unopened page has nothing to restore");
	source.invalid = true; device.restoring = true; device.restored.clear();
	Check(!cache.RestorePage(0) && device.restored.empty() && cache.GlyphCount() == glyphCount,"an unrasterizable glyph is reported and never moved");
	source.invalid = false; device.restoring = false;
	std::printf("Retained output font cache: %u checks passed\n",checks);
}
