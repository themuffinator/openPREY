// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once
#include "Runtime.h"
#include <algorithm>
#include <cmath>

namespace openq4::ui {
struct CoverageBitmap {
	int x=0, y=0, width=0, height=0;
	std::vector<unsigned char> pixels;
};
// Analytic path coverage emits whole-pixel, constant-colour rectangles. Store
// precisely those cells once instead of resubmitting all their triangles.
// Gradients, overlapping cells, subpixel motion and oversized artwork keep
// their original geometry. No resampling or additional edge approximation.
inline bool RasterizeCoverage(const std::vector<Vertex>& vertices, const std::vector<int>& indices,
	CoverageBitmap& result, int maximumExtent=510, bool multiply=false) {
	if (vertices.empty() || vertices.size()%4 || indices.size()!=vertices.size()/4*6) return false;
	int left=1000000, top=1000000, right=-1000000, bottom=-1000000;
	std::uint64_t work=0;
	const auto integer=[](float v) { return std::isfinite(v) && std::abs(v)<=1000000 && v==std::floor(v); };
	for (size_t base=0; base<vertices.size(); base+=4) {
		const auto& a=vertices[base]; const auto& b=vertices[base+1];
		const auto& c=vertices[base+2]; const auto& d=vertices[base+3];
		if (!integer(a.x) || !integer(a.y) || !integer(c.x) || !integer(c.y) ||
			a.x>=c.x || a.y>=c.y || b.x!=c.x || b.y!=a.y || d.x!=a.x || d.y!=c.y) return false;
		work+=std::uint64_t(c.x-a.x)*std::uint64_t(c.y-a.y);
		if (work>4*1024*1024) return false; // Bound overlapping-cell work as well as image storage.
		const int order[6]={0,1,2,0,2,3};
		for (int i=0;i<6;++i) if (indices[base/4*6+i]!=int(base)+order[i]) return false;
		for (size_t i=base;i<base+4;++i) {
			const auto& v=vertices[i];
			if (v.r!=a.r || v.g!=a.g || v.b!=a.b || v.a!=a.a ||
				!std::isfinite(v.r) || !std::isfinite(v.g) || !std::isfinite(v.b) || !std::isfinite(v.a) ||
				v.r<0 || v.r>1 || v.g<0 || v.g>1 || v.b<0 || v.b>1 || v.a<0 || v.a>1) return false;
		}
		left=(std::min)(left,int(a.x)); top=(std::min)(top,int(a.y));
		right=(std::max)(right,int(c.x)); bottom=(std::max)(bottom,int(c.y));
	}
	if (right-left>maximumExtent || bottom-top>maximumExtent ||
		std::uint64_t(right-left)*std::uint64_t(bottom-top)>4*1024*1024) return false;
	CoverageBitmap bitmap{left,top,right-left,bottom-top,{}};
	bitmap.pixels.resize(size_t(bitmap.width)*bitmap.height*4,multiply ? 255 : 0);
	std::vector<unsigned char> occupied(size_t(bitmap.width)*bitmap.height);
	for (size_t base=0; base<vertices.size(); base+=4) {
		const auto& a=vertices[base]; const auto& c=vertices[base+2];
		const unsigned channels[4]={unsigned(a.r*255+.5f),unsigned(a.g*255+.5f),unsigned(a.b*255+.5f),unsigned(a.a*255+.5f)};
		for (int y=int(a.y)-top;y<int(c.y)-top;++y) for (int x=int(a.x)-left;x<int(c.x)-left;++x) {
			const size_t offset=size_t(y)*bitmap.width+x;
			// Combining translucent layers before GPU blending changes rounding
			// against the destination. Keep those layers as authored geometry.
			if (occupied[offset]) return false;
			occupied[offset]=1;
			auto* pixel=bitmap.pixels.data()+offset*4;
			for (int ch=0;ch<4;++ch) pixel[ch]=static_cast<unsigned char>(channels[ch]);
		}
	}
	result=std::move(bitmap); return true;
}
} // namespace openq4::ui
