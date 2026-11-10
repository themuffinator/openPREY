#version 450

// openQ4 Vulkan stencil shadow volume — vertex stage (Phase G1,
// docs/dev/archive/2026-10-18/plans/2026-07-20-vulkan-phase-g.md).
//
// Port of the retail VPROG_STENCIL_SHADOW contract ("shadow.vp" is a pak
// asset, not in-repo; the semantics are pinned by the shadowCache_t data
// and the PP_LIGHT_ORIGIN upload at draw_common.cpp:7211-7222): verts with
// w == 1 stay at their model-space position (prelight volumes and the
// near copies of turbo volumes); verts with w == 0 are silhouette copies
// that project away from the local light origin to infinity — the output
// is the homogeneous direction (xyz - lightOrigin, 0), which the engine's
// unconditional infinite-far projection (tr_main.cpp R_SetupProjection)
// rasterizes just inside the far clip after the clip-z fixup.
//
// pc.a carries the local light origin with w == 0 exactly like env[4];
// the caller pushes a ZERO origin for CPU-projected caches
// (r_useShadowVertexProgram 0), whose w == 0 verts are already
// light-relative directions, making this shader the fixed-function
// pass-through. Formulated as v - (1-w)*lightOrigin so both vertex
// classes flow through one expression.

layout(location = 0) in vec4 inPosition;

layout(push_constant) uniform ShadowVolumePushConstants {
    mat4 mvp;
    vec4 a;    // xyz: local light origin (w uploaded 0)
    vec4 b;
    vec4 c;
    vec4 d;
} pc;

void main() {
    vec4 position = vec4(inPosition.xyz - pc.a.xyz * (1.0 - inPosition.w), inPosition.w);
    gl_Position = pc.mvp * position;
}
