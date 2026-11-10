#version 450

// openQ4 Vulkan shadow-map debug overlay — solid fills and glyphs
// (r_shadowMapDebugOverlay).
//
// Declares no sampler at all, which is the whole point: the frame, the
// backdrop, and the stats readout must still draw when no shadow map exists
// this view (the OpenGL overlay's "NO MAP" state), and a shader with a
// statically used sampler would need a descriptor set there is nothing to
// fill. The two panel variants own every sampled pixel; this one owns
// everything else, so the 5x7 font lives in exactly one shader.
//
// params.x is a compact font slot rather than an ASCII code — the CPU
// already knows the character, so mapping it there keeps this table dense
// and indexable. Slot order: space, 0-9, A-Z, '/', '-', '.', ':', '?',
// '%', '+'. Slot 0 (blank) also absorbs every unmapped character.

layout(push_constant) uniform ShadowOverlayPush {
    vec4 rect;
    vec4 uvRect;
    vec4 color;
    vec4 params;
    vec4 screen;
} pc;

layout(location = 0) in vec2 fragLocal;

layout(location = 0) out vec4 outColor;

// Each glyph is 5 columns x 7 rows, MSB-left. x packs rows 0-3 (4x5 bits),
// y packs rows 4-6 (3x5 bits).
const uvec2 kFont[44] = uvec2[44](
    uvec2(0x00000u, 0x0000u), uvec2(0x74675u, 0x662eu),
    uvec2(0x23084u, 0x108eu), uvec2(0x74422u, 0x111fu),
    uvec2(0xf042eu, 0x043eu), uvec2(0x11952u, 0x7c42u),
    uvec2(0xfc3c1u, 0x062eu), uvec2(0x3a21eu, 0x462eu),
    uvec2(0xf8444u, 0x2108u), uvec2(0x7462eu, 0x462eu),
    uvec2(0x7462fu, 0x045cu), uvec2(0x7463fu, 0x4631u),
    uvec2(0xf463eu, 0x463eu), uvec2(0x74610u, 0x422eu),
    uvec2(0xe4a31u, 0x465cu), uvec2(0xfc21eu, 0x421fu),
    uvec2(0xfc21eu, 0x4210u), uvec2(0x74617u, 0x462eu),
    uvec2(0x8c63fu, 0x4631u), uvec2(0x71084u, 0x108eu),
    uvec2(0x08421u, 0x462eu), uvec2(0x8ca98u, 0x5251u),
    uvec2(0x84210u, 0x421fu), uvec2(0x8eeb1u, 0x4631u),
    uvec2(0x8e6b3u, 0x4631u), uvec2(0x74631u, 0x462eu),
    uvec2(0xf463eu, 0x4210u), uvec2(0x74631u, 0x564du),
    uvec2(0xf463eu, 0x5251u), uvec2(0x7c20eu, 0x043eu),
    uvec2(0xf9084u, 0x1084u), uvec2(0x8c631u, 0x462eu),
    uvec2(0x8c631u, 0x4544u), uvec2(0x8c635u, 0x5771u),
    uvec2(0x8c544u, 0x2a31u), uvec2(0x8c544u, 0x1084u),
    uvec2(0xf8444u, 0x221fu), uvec2(0x08844u, 0x2110u),
    uvec2(0x0000eu, 0x0000u), uvec2(0x00000u, 0x018cu),
    uvec2(0x03180u, 0x3180u), uvec2(0x74422u, 0x1004u),
    uvec2(0xc6444u, 0x2263u), uvec2(0x0109fu, 0x1080u)
);

float GlyphAlpha(vec2 uv, int slot) {
    // Inset the 5x7 cell so adjacent glyphs keep a gap at any scale.
    vec2 local = (uv - vec2(0.10, 0.08)) / vec2(0.80, 0.84);
    if (local.x < 0.0 || local.x > 1.0 || local.y < 0.0 || local.y > 1.0) {
        return 0.0;
    }

    uint col = uint(clamp(floor(local.x * 5.0), 0.0, 4.0));
    uint row = uint(clamp(floor(local.y * 7.0), 0.0, 6.0));

    uvec2 glyph = kFont[slot];
    uint packed = row < 4u ? glyph.x : glyph.y;
    uint shift = row < 4u ? (3u - row) * 5u : (6u - row) * 5u;
    uint bits = (packed >> shift) & 31u;

    return ((bits >> (4u - col)) & 1u) != 0u ? 1.0 : 0.0;
}

void main() {
    if (pc.params.x < 0.0) {
        outColor = pc.color;
        return;
    }

    int slot = clamp(int(pc.params.x + 0.5), 0, 43);
    outColor = vec4(pc.color.rgb, pc.color.a * GlyphAlpha(fragLocal, slot));
}
