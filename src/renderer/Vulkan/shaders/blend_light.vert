#version 450

// openQ4 Vulkan blend light — vertex stage (Phase G2,
// docs/dev/archive/2026-10-18/plans/2026-07-20-vulkan-phase-g.md).
//
// Port of the RB_T_BlendLight texgen contract (draw_common.cpp:7470-7484):
// tex0 projects S/T/Q from the model-local lightProject[0..2] planes (the
// stage texture matrix is folded into S/T CPU-side via
// RB_BakeTextureMatrixIntoTexgen, replacing GL's texture matrix); tex1
// takes S from lightProject[3] (falloff) with T pinned at 0.5
// (glTexCoord2f(0, 0.5)) — a strict subset of interaction.vert's
// projection math. The per-draw planes + stage color stream through a
// dynamic uniform ring slice on set 2 (5 vec4 overflows the spare push
// space); the push block keeps the shared 128B shape for the MVP.

layout(location = 0) in vec3 inPosition;

layout(push_constant) uniform BlendLightPushConstants {
    mat4 mvp;
    vec4 a;
    vec4 b;
    vec4 c;
    vec4 d;
} pc;

layout(set = 2, binding = 0, std140) uniform BlendLightBlock {
    vec4 lightProjectS;
    vec4 lightProjectT;
    vec4 lightProjectQ;
    vec4 lightFalloffS;
    vec4 color;
} blend;

layout(location = 0) out vec4 vProjTexCoord;
layout(location = 1) out vec2 vFalloffTexCoord;

void main() {
    vec4 position = vec4(inPosition, 1.0);
    vProjTexCoord = vec4(
        dot(position, blend.lightProjectS),
        dot(position, blend.lightProjectT),
        0.0,
        dot(position, blend.lightProjectQ));
    vFalloffTexCoord = vec2(dot(position, blend.lightFalloffS), 0.5);
    gl_Position = pc.mvp * position;
}
