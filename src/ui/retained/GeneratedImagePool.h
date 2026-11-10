// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace openq4::ui {

// Shared by every context using a host. Retired images still consume the budget
// until the host has consumed their last submission frame and shrunk the image.
// Slot names are bounded too: closing/reopening documents cannot grow the engine
// image/decl registries. Call only on the host's rendering thread.
class GeneratedImagePool {
public:
    static constexpr unsigned Capacity = 64;
    static constexpr int MaximumDimension = 4096;
    static constexpr std::size_t ByteBudget = 64u * 1024u * 1024u;

    static bool ValidSize(int width, int height, std::size_t bytes) noexcept {
        return width > 0 && height > 0 && width <= MaximumDimension && height <= MaximumDimension &&
            bytes == std::size_t(width) * std::size_t(height) * 4;
    }
    unsigned Reserve(int width, int height, std::size_t bytes) noexcept {
        if (!ValidSize(width,height,bytes) || bytes > ByteBudget - residentBytes) return 0;
        for (unsigned i = 0; i < Capacity; ++i) if (slots[i].state == State::Free) {
            slots[i] = {State::Reserved,bytes,0}; residentBytes += bytes; return i + 1;
        }
        return 0;
    }
    bool Publish(unsigned id) noexcept {
        if (!id || id > Capacity || slots[id-1].state != State::Reserved) return false;
        slots[id-1].state = State::Live; return true;
    }
    bool Retire(unsigned id, std::uint64_t frame) noexcept {
        if (!id || id > Capacity) return false;
        auto& slot = slots[id-1];
        if (slot.state != State::Live && slot.state != State::Reserved) return false;
        slot.state = State::Retired; slot.frame = frame; return true;
    }
    template<class Release> void Collect(std::uint64_t frame, Release release) {
        for (unsigned i = 0; i < Capacity; ++i) {
            auto& slot = slots[i];
            if (slot.state == State::Retired && slot.frame != frame && release(i+1)) {
                residentBytes -= slot.bytes; slot = {};
            }
        }
    }
    // Resource-generation teardown already guarantees no outstanding draws.
    template<class Release> void Reset(Release release) {
        for (unsigned i = 0; i < Capacity; ++i) if (slots[i].state != State::Free) {
            auto& slot = slots[i];
            if (release(i+1)) { residentBytes -= slot.bytes; slot = {}; }
            else { slot.state = State::Retired; slot.frame = 0; }
        }
    }
    bool IsLive(unsigned id) const noexcept { return id && id <= Capacity && slots[id-1].state == State::Live; }
    std::size_t ResidentBytes() const noexcept { return residentBytes; }
private:
    enum class State { Free, Reserved, Live, Retired };
    struct Slot { State state = State::Free; std::size_t bytes = 0; std::uint64_t frame = 0; };
    std::array<Slot,Capacity> slots{};
    std::size_t residentBytes = 0;
};

} // namespace openq4::ui
