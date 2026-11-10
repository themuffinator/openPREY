#version 450
#extension GL_GOOGLE_include_directive : require
#include "../../PBRMath.h"

// openQ4 Vulkan GUI/2D pipeline â€” fragment stage (Phase D,
// docs/dev/archive/2026-10-18/plans/2026-07-18-vulkan-phase-d.md).
//
// One combined image sampler; component swizzles (fonts' green-alpha,
// R8-backed alpha/intensity formats) live on the VkImageView, so the
// sample here is already in canonical RGBA space.

layout(binding = 0) uniform sampler2D texSampler;

layout(location = 0) in vec2 fragTexCoord;
layout(location = 1) in vec4 fragColor;

layout(push_constant) uniform GuiPushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    vec4 params;
} pc;

layout(location = 0) out vec4 outColor;

#ifdef VK_HDR_DOMAIN_MRT
layout(location = 1) out vec4 outPBRColor;
#define main HDRMaterialMain
#endif

void main() {
    vec4 texel = texture(texSampler, fragTexCoord);
    vec4 color = texel * fragColor;
    if (pc.params.y > 2.5) {
        // Native PBR coverage uses constant stage alpha. Perspective
        // interpolation can perturb even a constant varying by one ULP,
        // introducing false gradients at filtered cutout edges.
        color.a = texel.a * pc.stageColor.a;
    }
    if (pc.params.x > 2.5) {
        // Bound the evaluated radiance, never the authored intensity before
        // texture modulation: a faint channel can remain in range at high gain.
        color.rgb = mix(clamp(color.rgb, vec3(0.0), vec3(65504.0)),
                        vec3(0.0), isnan(color.rgb));
        if (pc.params.x > 3.5) {
            // Production composition writes the display-referred framebuffer,
            // so linear emission takes the same encoding as classic colors.
            color.rgb = vec3(PBRLinearToSRGBExtended(color.r),
                PBRLinearToSRGBExtended(color.g), PBRLinearToSRGBExtended(color.b));
        }
    }
    if (pc.params.y > 3.5) {
        // Modern PBR hard cutouts include the threshold, like GL's step().
        // Keep the classic material test's strict greater-than rule below.
        color.a = step(max(pc.params.z, 0.001), color.a);
        if (color.a <= 0.0) discard;
    } else if (pc.params.y > 2.5) {
        // Admitted PBR cutouts use the same footprint coverage as the GL
        // modern depth/forward passes. Later EQUAL draws inherit this mask.
        color.a = clamp((color.a - max(pc.params.z, 0.001))
            / max(fwidth(color.a), 0.0001) + 0.5, 0.0, 1.0);
        if (color.a <= 0.0) discard;
    } else if (pc.params.y > 0.5) {
        if (pc.params.y > 1.5) {
            // Match fixed-function GL_EQUAL exactly. A tolerance admits
            // linearly filtered values that the classic alpha test rejects.
            if (color.a != pc.params.z) {
                discard;
            }
        } else if (color.a <= pc.params.z) {
            discard;
        }
    } else if (pc.params.y < -0.5 && color.a >= pc.params.z) {
        discard;
    }
    outColor = color;
}

#ifdef VK_HDR_DOMAIN_MRT
#undef main
void main() {
    HDRMaterialMain();
    // Both attachments use the same blend state. Preserve source alpha in
    // both outputs for coverage/blending; the primary stores scene alpha.
    bool nativePBR = pc.params.x > 2.5;
    outPBRColor = vec4(nativePBR ? outColor.rgb : vec3(0.0), outColor.a);
    if (nativePBR) outColor.rgb = vec3(0.0);
}
#endif
