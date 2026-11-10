#version 450

// Vulkan port of Quake 4's shipped
// glprogs/glsl/sniperstretch2.glslvp.
//
// Canonical shaderParms slots (the runner packs by case-insensitive name):
//   0 textureScale (xy)
//   1 textureHalfScale (xy)
//   2 backgroundColor (rgba)
//   12 framebuffer height (x, renderer built-in)
//   13 viewport origin in GL window coordinates (xy, renderer built-in)
//   14 viewport size (xy, renderer built-in)
//   15 current-render texture scale (xy, renderer built-in)

layout(location = 0) in vec3 inPosition;
layout(location = 5) in vec2 inTexCoord;

layout(set = 6, binding = 0, std140) uniform MaterialShaderParms {
    vec4 shaderParms[16];
} material;

layout(push_constant) uniform StagePushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    // x: vertex-color mode (unused by the retail program)
    // y: alpha-test mode (-1 less, 0 off, 1 greater, 2 equal)
    // z: alpha-test reference
    vec4 params;
} pc;

layout(location = 0) out vec2 vTexCoord;
layout(location = 1) out vec2 vScopeTexCoord;

void main() {
    gl_Position = pc.mvp * vec4(inPosition, 1.0);

    // These are the two varyings authored by the retail vertex program.
    // scopeTexCoord simplifies to the unscaled source coordinate, but keeping
    // the scale operation explicit documents the original contract.
    vec2 textureScale = material.shaderParms[0].xy;
    vTexCoord = inTexCoord * textureScale;
    vScopeTexCoord = inTexCoord;
}
