#version 450

// openQ4 Vulkan shadow-map debug overlay — vertex stage
// (r_shadowMapDebugOverlay, docs/dev/archive/2026-10-18/plans/2026-09-02-vulkan-shadow-gl-parity.md).
//
// The overlay is a handful of axis-aligned rectangles, so the quad is
// generated from gl_VertexIndex and positioned entirely by push constants:
// no vertex buffer, no ring allocation, and no descriptor churn between the
// panel, its frame, and every glyph cell.
//
// rect is in framebuffer pixels with a TOP-LEFT origin, which Vulkan clip
// space already agrees with (NDC y = -1 is the top row), so unlike the
// OpenGL overlay's vertex program no y flip is applied here. The overlay
// draw issues its own positive-height full-framebuffer viewport for exactly
// that reason; the interaction pass's negative-height viewport would
// otherwise invert the panel.

layout(push_constant) uniform ShadowOverlayPush {
    // x, y, w, h in framebuffer pixels (top-left origin)
    vec4 rect;
    // u0, v0, u1, v1 of the sampled region, image (top-left) orientation
    vec4 uvRect;
    // solid/glyph/border color
    vec4 color;
    // x: glyph slot (< 0 = solid fill), y: panel grid divisions,
    // z: active tile count, w: unused
    vec4 params;
    // x: framebuffer width, y: framebuffer height
    vec4 screen;
} pc;

layout(location = 0) out vec2 fragLocal;

void main() {
    const vec2 kCorners[6] = vec2[6](
        vec2(0.0, 0.0), vec2(1.0, 0.0), vec2(1.0, 1.0),
        vec2(0.0, 0.0), vec2(1.0, 1.0), vec2(0.0, 1.0));

    vec2 local = kCorners[gl_VertexIndex];
    vec2 pixel = pc.rect.xy + local * pc.rect.zw;
    vec2 extent = max(pc.screen.xy, vec2(1.0));
    vec2 clip = pixel / extent * 2.0 - 1.0;

    gl_Position = vec4(clip, 0.0, 1.0);
    fragLocal = local;
}
