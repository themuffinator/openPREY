// Copyright (C) 2026 openQ4 contributors. GPL-3.0-or-later.
#pragma once
#include <atomic>
#include <cassert>
#include <cstdint>

// Allocation admission is on the sound/main thread; decode workers can release
// compressed input. Reservations stay charged until their actual owner releases.
class SoundMemoryBudget {
public:
	bool Acquire(std::uint64_t bytes, std::uint64_t limit) {
		auto current = used.load(std::memory_order_relaxed);
		for (;;) {
			if (current > limit || bytes > limit - current) return false;
			if (used.compare_exchange_weak(current, current + bytes, std::memory_order_relaxed)) break;
		}
		auto high = peak.load(std::memory_order_relaxed);
		while (high < current + bytes && !peak.compare_exchange_weak(high, current + bytes, std::memory_order_relaxed)) {}
		return true;
	}
	void Release(std::uint64_t bytes) {
		const auto previous = used.fetch_sub(bytes, std::memory_order_relaxed);
		assert(previous >= bytes);
		(void)previous;
	}
	std::uint64_t Used() const { return used.load(std::memory_order_relaxed); }
	std::uint64_t Peak() const { return peak.load(std::memory_order_relaxed); }
private:
	std::atomic<std::uint64_t> used{0}, peak{0};
};
