#version 450
#extension GL_GOOGLE_include_directive : require
#include "framebuffer_coords.glsl"

// Compatible Vulkan implementation of Quake 4's missing glsl/AL.glsl
// fragment program.
//
// Semantic sampler sets:
//   set 0: RT
//   set 1: LightImage
//
// Canonical shaderParms slots:
//   0 distanceScale
//   1 textureScale (xy)
//   2 LightLoc (xyz)
//   3 LightColor (rgba)
//   4 LightSize
//   5 LightBehind
//   6 LightMinDistance
//   7 nativeDepthInput (internal Vulkan controller marker)
//
// LightLoc and LightBehind remain ABI-visible in their stock slots.  The
// recovered retail runtime updates LightLoc but does not expose an authored
// LightBehind update; compatible occlusion is consequently driven by the
// explicitly updated LightMinDistance, as in the in-tree rvspecial shader.

layout(set = 0, binding = 0) uniform sampler2D RT;
layout(set = 1, binding = 0) uniform sampler2D LightImage;

layout(set = 6, binding = 0, std140) uniform MaterialShaderParms {
    vec4 shaderParms[16];
} material;

layout(push_constant) uniform StagePushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    vec4 params;
} pc;

layout(location = 0) in vec2 vLightTexCoord;

layout(location = 0) out vec4 outColor;

bool AlphaTestFails(float alpha) {
    if (pc.params.y > 1.5) {
        return abs(alpha - pc.params.z) > (0.5 / 255.0);
    }
    if (pc.params.y > 0.5) {
        return alpha <= pc.params.z;
    }
    if (pc.params.y < -0.5) {
        return alpha >= pc.params.z;
    }
    return false;
}

void main() {
    // The retail controller supplies independent screen and sprite UV
    // streams. Derive the former from fragment position so the standard
    // idDrawVert ST remains available for the projected light sprite.
    vec2 viewportOrigin = material.shaderParms[13].xy;
    vec2 viewportSize = max(material.shaderParms[14].xy, vec2(1.0));
    float framebufferHeight = max(material.shaderParms[12].x, viewportSize.y);
    vec2 glPixel = vec2(gl_FragCoord.x, CanonicalWindowY(framebufferHeight));
    vec2 screenTexCoord =
        ((glPixel - viewportOrigin) / viewportSize)
        * material.shaderParms[1].xy;

    float distanceScale = max(material.shaderParms[0].x, 1.0);
    float sceneDepth = texture(RT, screenTexCoord).r;
    if (material.shaderParms[7].x > 0.5) {
        // The Vulkan RC_DRAW_SPECIAL_EFFECTS path samples the resolved depth
        // attachment directly. Authored hs/ALSetup stages sample Raven's
        // already-normalized DepthTexture and leave this marker at zero.
        const float zNear = 0.25;
        float ndcDepth = sceneDepth * 2.0 - 1.0;
        float linearDepth =
            (2.0 * zNear) / max(0.999 - ndcDepth, 0.001);
        sceneDepth = clamp(linearDepth / distanceScale, 0.0, 1.0);
    } else if (sceneDepth <= 0.001) {
        sceneDepth = 1.0;
    }

    vec4 lightColor = material.shaderParms[3];
    float lightSize = material.shaderParms[4].x;
    float lightMinDistance = material.shaderParms[6].x;

    float sprite = texture(LightImage, vLightTexCoord).a;
    float normalizedLightDepth = clamp(
        lightMinDistance / distanceScale,
        0.0,
        1.0);
    float normalizedLightRadius = max(
        lightSize / distanceScale,
        0.0005);
    float occlusion = smoothstep(
        normalizedLightDepth - normalizedLightRadius * 0.25,
        normalizedLightDepth + normalizedLightRadius,
        sceneDepth);
    float intensity = sprite * occlusion * 0.35;
    vec4 color = vec4(
        lightColor.rgb * intensity,
        lightColor.a * intensity);

    if (AlphaTestFails(color.a)) {
        discard;
    }
    outColor = color;
}
