// Copyright (C) 2026 DarkMatter Productions
#ifdef VK_HDR_MULTISAMPLE
layout(set = 0, binding = 0) uniform sampler2DMS classicScene;
layout(set = 1, binding = 0) uniform sampler2DMS pbrScene;
#else
layout(set = 0, binding = 0) uniform sampler2D classicScene;
layout(set = 1, binding = 0) uniform sampler2D pbrScene;
#endif

layout(push_constant) uniform HDRScenePush { ivec4 params; } pc;
layout(location = 0) out vec4 outColor;
#ifdef VK_HDR_SEED
layout(location = 1) out vec4 outPBRColor;
#endif

void main() {
    ivec2 texel = ivec2(gl_FragCoord.xy);
#ifdef VK_HDR_MULTISAMPLE
    int sampleIndex = pc.params.x;
    gl_SampleMask[0] = int(1u << uint(sampleIndex));
    vec4 classic = texelFetch(classicScene, texel, sampleIndex);
#else
    vec4 classic = texelFetch(classicScene, texel, 0);
#endif
#ifdef VK_HDR_SEED
    outColor = classic;
    outPBRColor = vec4(0.0);
#else
#ifdef VK_HDR_MULTISAMPLE
    vec3 pbr = texelFetch(pbrScene, texel, sampleIndex).rgb;
#else
    vec3 pbr = texelFetch(pbrScene, texel, 0).rgb;
#endif
    // Convert completed classic lighting, not each additive light and not an
    // already resolved mixture of covered/uncovered or classic/PBR samples.
    vec3 c = max(classic.rgb, vec3(0.0));
    vec3 linear = mix(pow((c + 0.055) / 1.055, vec3(2.4)), c / 12.92,
                      lessThanEqual(c, vec3(0.04045)));
    // HDR-off previews retain the classic encoded numeric domain, and their PBR
    // draws were encoded one light at a time like the classic lights beside
    // them; only the storage is floating point until the scene is resolved.
    vec3 base = pc.params.y != 0 ? c : linear;
    outColor = vec4(min(base + max(pbr, vec3(0.0)), vec3(65504.0)), classic.a);
#endif
}
