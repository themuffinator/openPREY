// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#include "src/bse/ParticleOrder.h"
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <random>
#include <vector>

#define CHECK(x) do { if (!(x)) { std::fprintf(stderr,"line %d: %s\n",__LINE__,#x); std::exit(1); } } while (0)
using Entry = openq4::bse::DrawParticle<int>;

int main() {
	std::mt19937 random(42);
	// Compare against the former stable insertion order, including large
	// effects, repeated depths, and the inverse-draw-order traversal.
	for (const int count : {0, 1, 2, 8, 64, 1000, 8192}) {
		std::vector<Entry> actual;
		for (int i=0; i<count; ++i) actual.push_back({nullptr,float(random()%31),std::size_t(i)});
		auto expected=actual;
		for (int i=1; i<count; ++i) {
			const auto key=expected[i]; int j=i-1;
			while (j>=0 && expected[j].distance<key.distance) { expected[j+1]=expected[j]; --j; }
			expected[j+1]=key;
		}
		openq4::bse::SortParticleDepth(actual.data(),actual.size());
		for (int i=0; i<count; ++i) {
			CHECK(actual[i].sequence==expected[i].sequence);
			CHECK(actual[count-1-i].sequence==expected[count-1-i].sequence);
		}
	}
	const float nan=std::numeric_limits<float>::quiet_NaN(), inf=std::numeric_limits<float>::infinity();
	std::vector<Entry> invalid{{nullptr,nan,0},{nullptr,2,1},{nullptr,inf,2},{nullptr,nan,3},{nullptr,2,4}};
	openq4::bse::SortParticleDepth(invalid.data(),invalid.size());
	const std::size_t order[]{2,1,4,0,3};
	for (int i=0; i<5; ++i) CHECK(invalid[i].sequence==order[i]);
	std::puts("BSE particle order: stable depth, inverse traversal, empty and malformed cases passed");
}
