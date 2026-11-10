// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#ifndef OPENQ4_BSE_PARTICLE_ORDER_H
#define OPENQ4_BSE_PARTICLE_ORDER_H

#include <algorithm>
#include <cmath>
#include <cstddef>

namespace openq4::bse {
template<class Particle> struct DrawParticle {
	Particle* particle;
	float distance;
	std::size_t sequence;
};

// Preserve the used-list order at equal depths, including when the caller
// subsequently reverses the result. Cache distance before sorting: evaluating
// it inside insertion-sort's inner loop made dense effects quadratic.
template<class Entry> void SortParticleDepth(Entry* entries, std::size_t count) {
	if (count < 2) return;
	std::sort(entries, entries + count, [](const Entry& a, const Entry& b) {
		// Malformed positions must not violate std::sort's strict ordering.
		const bool aNan = std::isnan(a.distance), bNan = std::isnan(b.distance);
		if (aNan != bNan) return !aNan;
		if (a.distance > b.distance) return true;
		if (a.distance < b.distance) return false;
		return a.sequence < b.sequence;
	});
}
}
#endif
