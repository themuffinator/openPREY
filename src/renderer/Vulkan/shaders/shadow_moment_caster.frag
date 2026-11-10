#version 450
#extension GL_GOOGLE_include_directive : require

// openQ4 Vulkan translucent shadow-moment caster for projected lights —
// fragment stage (GL shadow_proj_translucent_caster.fs). Geometry outside the
// light's depth range contributes nothing.

#include "shadow_moment_stage.glsl"
#include "shadow_moment_caster.glsl"

layout(location = 5) in float vShadowDepth;

void main() {
    WriteTranslucentMoments(vShadowDepth, vShadowDepth <= 0.0 || vShadowDepth >= 1.0);
}
