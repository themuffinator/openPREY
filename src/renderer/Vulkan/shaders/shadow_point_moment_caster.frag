#version 450
#extension GL_GOOGLE_include_directive : require

// openQ4 Vulkan translucent shadow-moment caster for point lights —
// fragment stage (GL shadow_point_translucent_caster.fs). The depth is the
// radial distance over the far envelope; anything outside (0, 1) adds
// nothing.

#include "point_shadow_math.glsl"
#include "shadow_moment_stage.glsl"
#include "shadow_moment_caster.glsl"

layout(push_constant) uniform MomentCasterPushConstants {
    mat4 mvp;        // model -> cube-face view space
    vec4 depthRow;   // x: zA, y: zB, z: far envelope, w: cube face
} pc;

layout(location = 5) in vec3 vPointShadowVector;

void main() {
    float farDistance = pc.depthRow.z;
    float rawDepth = farDistance > 0.0
        ? PointShadowRadialDepth(vPointShadowVector, farDistance) : 0.0;
    WriteTranslucentMoments(rawDepth, farDistance <= 0.0 || rawDepth <= 0.0 || rawDepth >= 1.0);
}
