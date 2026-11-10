// Copyright (C) 2026 DarkMatter Productions
// Same atlas interpolation/visibility contract as ModernLightGridGLSL.h.
// This pass receives world coordinates directly from the interaction vertex.
layout(set = 7, binding = 1) uniform sampler2D uBakedIrradiance;
layout(set = 7, binding = 2) uniform sampler2D uBakedVisibility;
layout(set = 7, binding = 3) uniform sampler2D uBakedRelocation;
layout(set = 7, binding = 4, std140) uniform BakedGridBlock { vec4 uBakedGrid[7]; };
vec3 ModernClassicSceneColor(vec3 color) {
    vec3 c = max(color, vec3(0.0));
    return mix(c / 12.92, pow((c + vec3(0.055)) / 1.055, vec3(2.4)), step(vec3(0.04045), c));
}
vec2 ModernBakedOct(vec3 direction) {
    vec3 n = direction / max(dot(abs(direction), vec3(1.0)), 0.0001);
    vec2 signs = vec2(n.x >= 0.0 ? 1.0 : -1.0, n.y >= 0.0 ? 1.0 : -1.0);
    return ((n.z < 0.0 ? (1.0 - abs(n.yx)) * signs : n.xy) + 1.0) * 0.5;
}
vec2 ModernBakedAtlasUV(vec3 cell, vec2 oct) {
    float index = cell.x + cell.z * uBakedGrid[2].x;
    vec2 origin = vec2(index, cell.y) * uBakedGrid[3].z;
    return (origin + uBakedGrid[3].w * 0.5 + oct * (uBakedGrid[3].z - uBakedGrid[3].w)) * uBakedGrid[3].xy;
}
float ModernBakedVisibility(vec3 cell, vec3 worldPosition, vec3 normal) {
    vec2 cells = vec2(uBakedGrid[2].x * uBakedGrid[2].z, uBakedGrid[2].y);
    vec2 relocationUV = (vec2(cell.x + cell.z * uBakedGrid[2].x, cell.y) + 0.5) / cells;
    vec3 relocation = (texture(uBakedRelocation, relocationUV).rgb * 255.0 - 128.0) * (uBakedGrid[5].x / 127.0);
    vec3 offset = worldPosition - (uBakedGrid[0].xyz + cell * uBakedGrid[1].xyz + relocation);
    float distance = length(offset);
    vec3 direction = distance > 0.001 ? offset / distance : normal;
    vec3 moments = texture(uBakedVisibility, ModernBakedAtlasUV(cell, ModernBakedOct(direction))).rgb;
    if (moments.b <= 0.001) return 1.0;
    float maxDistance = uBakedGrid[4].x;
    float mean = moments.r * maxDistance;
    float bias = uBakedGrid[4].y * (0.25 + 0.75 * max(dot(normal, -direction), 0.0));
    float delta = max(distance - bias, 0.0) - mean;
    if (delta <= 0.0) return 1.0;
    float variance = max(moments.g * maxDistance * maxDistance - mean * mean, maxDistance * maxDistance * 0.000025);
    return clamp(pow(variance / (variance + delta * delta), uBakedGrid[4].w), uBakedGrid[4].z, 1.0);
}
vec4 ModernBakedIrradiance(vec3 position, vec3 normal, bool pbr) {
    if (uBakedGrid[0].w < 0.5) return vec4(-1.0, -1.0, -1.0, 0.0);
    vec3 worldPosition = position;
    vec3 worldNormal = normalize(normal);
    vec3 coordinate = clamp((worldPosition - uBakedGrid[0].xyz) / max(uBakedGrid[1].xyz, vec3(0.001)), vec3(0.0), uBakedGrid[2].xyz - 1.0);
    vec3 cell = floor(coordinate), fraction = fract(coordinate);
    vec2 oct = ModernBakedOct(worldNormal);
    vec3 irradiance = vec3(0.0);
    float validWeight = 0.0;
    for (int i = 0; i < 8; ++i) {
        vec3 corner = vec3(i & 1, (i >> 1) & 1, (i >> 2) & 1);
        vec3 weights = mix(1.0 - fraction, fraction, corner);
        float weight = weights.x * weights.y * weights.z;
        if (weight <= 0.0) continue;
        vec3 sampleCell = cell + corner;
        vec3 sampleColor = pow(max(texture(uBakedIrradiance, ModernBakedAtlasUV(sampleCell, oct)).rgb, vec3(0.0)), vec3(uBakedGrid[1].w));
        if (dot(sampleColor, vec3(1.0)) < 0.0001) continue;
        // Legacy atlas texels are display-encoded. Decode each contributing
        // probe before interpolation for linear PBR transport. Black/invalid
        // handling and visibility weights retain the existing bake contract.
        if (pbr) sampleColor = ModernClassicSceneColor(sampleColor);
        irradiance += sampleColor * weight * ModernBakedVisibility(sampleCell, worldPosition, worldNormal);
        validWeight += weight;
    }
    if (validWeight > 0.0 && validWeight < 0.9999) irradiance /= validWeight;
    return vec4(irradiance * uBakedGrid[2].w, uBakedGrid[6].w);
}
vec3 ModernBakedClamp(vec3 value, float cap) {
    return max(cap > 0.0 ? min(value, vec3(cap)) : value, vec3(0.0));
}
