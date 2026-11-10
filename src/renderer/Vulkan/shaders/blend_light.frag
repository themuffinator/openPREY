#version 450

// openQ4 Vulkan blend light — fragment stage (Phase G2).
//
// The RB_BlendLight fixed-function result (draw_common.cpp:7508-7564):
// projected stage texture (S/Q, T/Q) × falloff (S, 0.5) × the light
// stage's RGBA color, blended into the framebuffer by the stage's blend
// keyword (the pipeline's per-stage GLS blend bits).

layout(set = 0, binding = 0) uniform sampler2D lightProjectionMap;
layout(set = 1, binding = 0) uniform sampler2D lightFalloffMap;

layout(set = 2, binding = 0, std140) uniform BlendLightBlock {
    vec4 lightProjectS;
    vec4 lightProjectT;
    vec4 lightProjectQ;
    vec4 lightFalloffS;
    vec4 color;
} blend;

layout(location = 0) in vec4 vProjTexCoord;
layout(location = 1) in vec2 vFalloffTexCoord;

layout(location = 0) out vec4 outColor;

void main() {
    outColor = textureProj(lightProjectionMap, vProjTexCoord)
            * texture(lightFalloffMap, vFalloffTexCoord)
            * blend.color;
}
