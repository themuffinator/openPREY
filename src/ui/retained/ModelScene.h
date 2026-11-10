// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace openq4::ui {

// The engine's renderDef contract: one animated root, two joint attachments
// and five lights. No engine pointers, entity spawning or GUI scripts cross
// the retained host boundary.
struct ModelPart {
    std::string model, skin, animation, animationClass, joint;
    bool operator==(const ModelPart&) const = default;
};
struct ModelLight {
    std::array<double,3> origin{-128,0,0}, colour{1,1,1};
    bool operator==(const ModelLight&) const = default;
};
struct ModelScene {
    std::vector<ModelPart> parts;
    std::vector<ModelLight> lights;
    std::array<double,3> origin{}, rotation{}, camera{-128,0,0};
    std::array<double,4> outline{}, rimlight{}, brightSkin{};
    double fov = 90, outlineWidth = 2;
    bool operator==(const ModelScene&) const = default;
};

bool ValidModelScene(const ModelScene&, std::string& error);
// Process-local, never reused, including across live documents and editors.
// Exhaustion returns zero rather than wrapping onto an existing owner.
std::uint64_t NewModelSceneLease() noexcept;

}
