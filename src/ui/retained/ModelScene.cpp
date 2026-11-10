// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#include "ModelScene.h"
#include "Document.h"
#include "State.h"
#include <atomic>
#include <cmath>
#include <limits>

namespace openq4::ui {
namespace {
template<std::size_t N>
bool Bounded(const std::array<double,N>& value, double minimum, double maximum) {
    for (double component : value)
        if (!std::isfinite(component) || component < minimum || component > maximum) return false;
    return true;
}
bool ModelName(const std::string& value) { return value.size() <= 256 && ValidImageSource(value); }
}

bool ValidModelScene(const ModelScene& scene, std::string& error) {
    error.clear();
    if (scene.parts.empty() || scene.parts.size() > 3 || scene.lights.size() > 5) {
        error = "A model scene needs one to three parts and at most five lights"; return false;
    }
    for (std::size_t index = 0; index < scene.parts.size(); ++index) {
        const auto& part = scene.parts[index];
        if (!ModelName(part.model) || !ModelName(part.skin) || !ModelName(part.animation) ||
            !ModelName(part.animationClass) || !ModelName(part.joint) || (!index && !part.joint.empty())) {
            error = "Model assets must be bounded relative VFS names; the root has no attachment joint"; return false;
        }
    }
    if (!Bounded(scene.origin,-32768,32768) || !Bounded(scene.rotation,-360000,360000) ||
        !Bounded(scene.camera,-32768,32768) || !Bounded(scene.outline,0,16) ||
        !Bounded(scene.rimlight,0,16) || !Bounded(scene.brightSkin,0,16) ||
        !std::isfinite(scene.fov) || scene.fov < 1 || scene.fov > 179 ||
        !std::isfinite(scene.outlineWidth) || scene.outlineWidth < 0 || scene.outlineWidth > 6) {
        error = "Model camera, transform or surface effects are outside their finite bounds"; return false;
    }
    for (const auto& light : scene.lights)
        if (!Bounded(light.origin,-32768,32768) || !Bounded(light.colour,0,16)) {
            error = "Model lights are outside their finite position/colour bounds"; return false;
        }
    return true;
}

std::uint64_t NewModelSceneLease() noexcept {
    static std::atomic<std::uint64_t> next{1};
    auto value = next.load(std::memory_order_relaxed);
    while (value && value != std::numeric_limits<std::uint64_t>::max()) {
        if (next.compare_exchange_weak(value,value+1,std::memory_order_relaxed)) return value;
    }
    return 0;
}

bool ResolveModelScene(const ModelSceneSpec& spec, const StateValues& state, ModelScene& out, std::string& error) {
    ModelScene candidate;
    const auto number = [&](const Expression& expression, double& value) {
        StateValue evaluated;
        if (!EvaluateStateExpression(expression,state,evaluated,error)) return false;
        if (!std::holds_alternative<double>(evaluated)) { error = "A model numeric expression changed type"; return false; }
        value = std::get<double>(evaluated); return true;
    };
    const auto text = [&](const Expression& expression, std::string& value) {
        StateValue evaluated;
        if (!EvaluateStateExpression(expression,state,evaluated,error)) return false;
        if (!std::holds_alternative<std::string>(evaluated)) { error = "A model asset expression changed type"; return false; }
        value = std::get<std::string>(std::move(evaluated)); return true;
    };
    const auto vector = [&](const auto& expressions, auto& values) {
        for (std::size_t index = 0; index < values.size(); ++index)
            if (!number(expressions[index],values[index])) return false;
        return true;
    };
    for (const auto& part : spec.parts) {
        ModelPart resolved; resolved.joint = part.joint;
        if (!text(part.model,resolved.model) || !text(part.skin,resolved.skin) ||
            !text(part.animation,resolved.animation) || !text(part.animationClass,resolved.animationClass)) return false;
        candidate.parts.push_back(std::move(resolved));
    }
    for (const auto& light : spec.lights) {
        ModelLight resolved;
        if (!vector(light.origin,resolved.origin) || !vector(light.colour,resolved.colour)) return false;
        candidate.lights.push_back(std::move(resolved));
    }
    if (!vector(spec.origin,candidate.origin) || !vector(spec.rotation,candidate.rotation) ||
        !vector(spec.camera,candidate.camera) || !vector(spec.outline,candidate.outline) ||
        !vector(spec.rimlight,candidate.rimlight) || !vector(spec.brightSkin,candidate.brightSkin) ||
        !number(spec.fov,candidate.fov) || !number(spec.outlineWidth,candidate.outlineWidth) ||
        !ValidModelScene(candidate,error)) return false;
    out = std::move(candidate); return true;
}

}
