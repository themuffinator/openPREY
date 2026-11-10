#version 450

// openQ4 Vulkan shadow-map debug overlay — projected mini-map panel
// (r_shadowMapDebugOverlay).
//
// Reads the selected light's atlas block through set 0 binding 2, the RAW
// (compare-disabled, NEAREST) shadow sampler, so the panel shows stored
// depth rather than a comparison result. The set layout is the shadow
// receiver layout the interaction pipelines already use, so the atlas set
// vk_ShadowMap.cpp publishes binds here unchanged; binding 0 (the compare
// sampler) and binding 1 (the shadow block) are deliberately unused.
//
// fragLocal is panel-local [0,1], never the atlas coordinate: the cascade
// grid must line up with the panel's own edges no matter where in the atlas
// the light's block was allocated. The sampled coordinate is derived from
// uvRect separately.

layout(set = 0, binding = 2) uniform sampler2D shadowRawMap;

layout(push_constant) uniform ShadowOverlayPush {
    vec4 rect;
    vec4 uvRect;
    vec4 color;
    vec4 params;
    vec4 screen;
} pc;

layout(location = 0) in vec2 fragLocal;

layout(location = 0) out vec4 outColor;

void main() {
    vec2 sampleUv = mix(pc.uvRect.xy, pc.uvRect.zw, fragLocal);
    float depth = texture(shadowRawMap, sampleUv).r;
    float shade = clamp(pow(max(1.0 - depth, 0.0), 0.55), 0.0, 1.0);
    vec3 base = mix(vec3(0.04, 0.04, 0.05), vec3(0.92), shade);

    // Cascades occupy the first params.z cells of an atlasDiv x atlasDiv
    // block; dim the cells this light does not own.
    float divisions = max(pc.params.y, 1.0);
    float tileIndex = floor(fragLocal.x * divisions)
            + floor(fragLocal.y * divisions) * divisions;
    float activeTile = step(tileIndex + 0.5, pc.params.z);
    base *= mix(0.22, 1.0, activeTile);

    vec2 gridUv = fract(fragLocal * divisions);
    float border = max(step(gridUv.x, 0.025),
            max(step(gridUv.y, 0.025),
                max(step(0.975, gridUv.x), step(0.975, gridUv.y))));
    base = mix(base, pc.color.rgb, border * 0.85);

    outColor = vec4(base, 0.95);
}
