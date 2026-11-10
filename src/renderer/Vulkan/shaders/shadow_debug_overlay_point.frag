#version 450

// openQ4 Vulkan shadow-map debug overlay — point-light cube panel
// (r_shadowMapDebugOverlay).
//
// Identical to the projected panel except that set 0 binding 2 is a
// samplerCube: the descriptor set layout is view-type agnostic, so this
// variant binds one of the point cube sets vk_ShadowMap.cpp already builds
// for every frame slot. The panel is a 3x2 unwrap of the six faces sampled
// through the standard cube-face directions, which is what the receivers
// see regardless of the orientation each face was rendered with.
//
// Vulkan point cubes always store native depth (r_shadowMapPointHighPrecision
// is OpenGL-only), so unlike the OpenGL overlay there is no packed
// two-channel depth to decode here.

layout(set = 0, binding = 2) uniform samplerCube shadowRawMap;

layout(push_constant) uniform ShadowOverlayPush {
    vec4 rect;
    vec4 uvRect;
    vec4 color;
    vec4 params;
    vec4 screen;
} pc;

layout(location = 0) in vec2 fragLocal;

layout(location = 0) out vec4 outColor;

vec3 PointFaceDirection(float faceIndex, vec2 uv) {
    vec2 st = uv * 2.0 - 1.0;

    if (faceIndex < 0.5) {
        return normalize(vec3(1.0, -st.y, -st.x));
    }
    if (faceIndex < 1.5) {
        return normalize(vec3(-1.0, -st.y, st.x));
    }
    if (faceIndex < 2.5) {
        return normalize(vec3(st.x, 1.0, st.y));
    }
    if (faceIndex < 3.5) {
        return normalize(vec3(st.x, -1.0, -st.y));
    }
    if (faceIndex < 4.5) {
        return normalize(vec3(st.x, -st.y, 1.0));
    }
    return normalize(vec3(-st.x, -st.y, -1.0));
}

void main() {
    vec2 tiled = vec2(fragLocal.x * 3.0, fragLocal.y * 2.0);
    vec2 faceUv = fract(tiled);
    float faceIndex = floor(tiled.x) + floor(tiled.y) * 3.0;

    if (faceIndex < 0.0 || faceIndex > 5.0) {
        outColor = vec4(0.02, 0.02, 0.03, 0.92);
        return;
    }

    vec3 direction = PointFaceDirection(faceIndex, faceUv);
    float depth = texture(shadowRawMap, direction).r;
    float shade = clamp(pow(max(1.0 - depth, 0.0), 0.55), 0.0, 1.0);
    vec3 base = mix(vec3(0.04, 0.04, 0.05), vec3(0.92), shade);

    float border = max(step(faceUv.x, 0.025),
            max(step(faceUv.y, 0.025),
                max(step(0.975, faceUv.x), step(0.975, faceUv.y))));
    base = mix(base, pc.color.rgb, border * 0.85);

    outColor = vec4(base, 0.95);
}
