#version 450

// openQ4 Vulkan shadow-map caster — vertex stage (Phase F2a,
// docs/dev/archive/2026-10-18/plans/2026-07-19-vulkan-phase-f.md).
//
// Depth-only caster into the projected-light shadow atlas, mirroring the GL
// shadow_proj_caster.vs contract: gl_Position comes from the light's clip
// matrix (R_ShadowMapClipPlanesToGLMatrix over the world clip planes, times
// the model matrix, with the Vulkan clip-z fixup), while the DEPTH the map
// stores is written by the fragment stage from vShadowDepth = dot(position,
// depthRow) — the model-local shadow depth plane (clip plane 2), exactly the
// value the receiver compares against.
//
// The push block keeps the shared 128B envelope. Because the alpha texture
// matrix rows only ever dot against (s, t, 0, 1), their z components are
// free; they carry the two caster depth-offset scalars (slope factor in
// alphaS.z, pre-scaled constant offset in alphaT.z).

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec2 inTexCoord;

layout(push_constant) uniform CasterPushConstants {
    mat4 mvp;
    vec4 depthRow;   // model-local shadow depth plane (clip plane 2)
    vec4 alphaS;     // alpha-test texture matrix S row; z = slope-scale depth factor
    vec4 alphaT;     // alpha-test texture matrix T row; z = constant depth offset
    vec4 params;     // x: alpha mode, y: alphaRef, z: alphaScale, w: alpha-hash mode/seed
} pc;

layout(location = 0) out vec2 vAlphaTexCoord;
layout(location = 1) out float vShadowDepth;
layout(location = 2) out vec3 vAlphaHashCoord;

void main() {
    vec4 position = vec4(inPosition, 1.0);
    vec4 texCoord = vec4(inTexCoord, 0.0, 1.0);
    // texCoord.z is 0, so the depth-offset scalars packed into the matrix
    // rows' z components never contribute to the texture coordinate
    vAlphaTexCoord = vec2(dot(texCoord, pc.alphaS), dot(texCoord, pc.alphaT));
    vShadowDepth = dot(position, pc.depthRow);
    // The portable 128-byte push block cannot also carry three model rows.
    // Model-local coordinates plus the world-translation phase in params.w
    // retain a stable hash. This matches identity/world geometry; arbitrary
    // rotated or scaled entities use the documented stable approximation.
    vAlphaHashCoord = inPosition;
    gl_Position = pc.mvp * position;
}
