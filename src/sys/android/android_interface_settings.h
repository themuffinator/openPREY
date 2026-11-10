// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

// Engine-free: included after idlib's precompiled.h, whose Str.h replaces the
// C string comparisons, and by standalone native tests.
#include <cstddef>

namespace openq4 { namespace android {
struct InterfaceSetup {
    char revision[33] = {};
    int profile = 0;
    float scale = 1, textScale = 1;
};

// The Activity's resolved record: "1:<32 hex revision>:<profile 1-5>:<UI %>:<text %>",
// with the UI and text percentages in the ui_retainedScale (75-200) and
// ui_retainedTextScale (100-200) ranges. Keep invalid/truncated records and
// already-delivered transactions from changing live settings: a player's later
// in-game edits must survive resume.
inline bool PendingInterfaceSetup(const char* record, const char* applied, InterfaceSetup& out) {
    if (!record || record[0] != '1' || record[1] != ':') return false;
    for (std::size_t length = 0; record[length]; ++length) {
        if (length >= 48) return false;
    }
    const char* cursor = record + 2;
    InterfaceSetup candidate;
    for (int i = 0; i < 32; ++i) {
        const char c = *cursor++;
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
        candidate.revision[i] = c;
    }
    if (*cursor++ != ':') return false;
    const int profile = *cursor++ - '0';
    if (profile < 1 || profile > 5 || *cursor++ != ':') return false;
    int percentages[2] = {};
    for (int i = 0; i < 2; ++i) {
        int digits = 0;
        while (*cursor >= '0' && *cursor <= '9') {
            if (++digits > 3) return false;
            percentages[i] = percentages[i] * 10 + (*cursor++ - '0');
        }
        if (!digits || percentages[i] < (i ? 100 : 75) || percentages[i] > 200) return false;
        if (i == 0 && *cursor++ != ':') return false;
    }
    if (*cursor) return false;
    if (applied) {
        int same = 0;
        while (same < 32 && applied[same] == candidate.revision[same]) ++same;
        if (same == 32 && applied[32] == '\0') return false;
    }
    candidate.profile = profile;
    candidate.scale = percentages[0] / 100.0f;
    candidate.textScale = percentages[1] / 100.0f;
    out = candidate;
    return true;
}
}}
