#version 450

// openQ4 Vulkan fog light — vertex stage (Phase G2,
// docs/dev/archive/2026-10-18/plans/2026-07-20-vulkan-phase-g.md).
//
// Port of the RB_T_BasicFog texgen contract (draw_common.cpp:7593-7616;
// the MD5R fog vprog env-param twin at draw_arb2.cpp:1573-1588 is the
// exact vertex-shader formulation): three model-local planes evaluate to
// the two fog texcoords —
//   tex0 (_fog):      S = eye-depth density ramp (the view-space Z plane
//                     scaled by the fog distance, +0.5 folded CPU-side),
//                     T = the constant 0.5 row (FOG_DISTANCE_BIAS).
//   tex1 (_fogEnter): S = the viewer's constant scaled distance to the
//                     fog plane (zero-normal plane), T = the fragment's
//                     scaled distance to the fog plane (+FOG_ENTER folded).
//
// The push block keeps the shared 128B shape {mat4; vec4 a,b,c,d}:
//   a = local FOG_DISTANCE_PLANE_S (+0.5), b = local FOG_ENTER_PLANE_T
//   (+FOG_ENTER), c = FOG_ENTER_PLANE_S, d = the fog color (rgb, a = 1).

layout(location = 0) in vec3 inPosition;

layout(push_constant) uniform FogPushConstants {
    mat4 mvp;
    vec4 a;    // tex0 S: local fog distance plane
    vec4 b;    // tex1 T: local fog enter plane
    vec4 c;    // tex1 S: constant viewer-distance plane
    vec4 d;    // fog color
} pc;

layout(location = 0) out vec2 vFogTexCoord;
layout(location = 1) out vec2 vEnterTexCoord;

void main() {
    vec4 position = vec4(inPosition, 1.0);
    vFogTexCoord = vec2(dot(position, pc.a), 0.5);
    vEnterTexCoord = vec2(dot(position, pc.c), dot(position, pc.b));
    gl_Position = pc.mvp * position;
}
