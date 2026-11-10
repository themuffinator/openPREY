// Copyright (C) 2026 DarkMatter Productions
// Exact shared CPU top-two selection, with native per-view std430 storage.
struct PBRProbeRecord {
    vec4 positionRadius;
    vec4 tintIntensity;
    vec4 axisXPriority;
    vec4 axisYBlend;
    vec4 axisZSlot;
    vec4 identity;
    vec4 boxExtents; // xyz half extents, w 1 for box parallax
};
layout(set = 7, binding = 0, std430) readonly buffer PBRProbeBlock {
    vec4 grid;
    vec4 depth;
    vec4 viewOrigin;
    vec4 worldToViewX;
    vec4 worldToViewY;
    vec4 worldToViewZ;
    vec4 projection;
    PBRProbeRecord records[32];
    uint indices[];
} probes;

vec3 PBRProbeToView(vec3 direction) {
    return vec3(dot(probes.worldToViewX.xyz, direction),
        dot(probes.worldToViewY.xyz, direction), dot(probes.worldToViewZ.xyz, direction));
}

bool PBRProbeExact(float value, float low, float high) {
    return !isnan(value) && !isinf(value) && value >= low && value <= high && floor(value) == value;
}

bool PBRProbeFinite(vec3 value) { return !any(isnan(value)) && !any(isinf(value)); }

bool PBRProbeValid(PBRProbeRecord probe) {
    if (!PBRProbeExact(probes.depth.w, 1.0, 16777215.0)
            || !PBRProbeExact(probe.identity.x, 0.0, 16777215.0)
            || !PBRProbeExact(probe.identity.y, 1.0, 16777215.0)
            || !PBRProbeExact(probe.identity.z, 1.0, 16777215.0)
            || probe.identity.w != probes.depth.w) return false;
    if (!PBRProbeFinite(probe.positionRadius.xyz) || isnan(probe.positionRadius.w)
            || isinf(probe.positionRadius.w) || probe.positionRadius.w <= 0.0) return false;
    if (!PBRProbeFinite(probe.tintIntensity.rgb) || any(lessThan(probe.tintIntensity.rgb, vec3(0.0)))
            || any(greaterThan(probe.tintIntensity.rgb, vec3(64.0)))
            || isnan(probe.tintIntensity.w) || isinf(probe.tintIntensity.w)
            || probe.tintIntensity.w <= 0.0 || probe.tintIntensity.w > 64.0) return false;
    if (!PBRProbeFinite(probe.axisXPriority.xyz) || !PBRProbeFinite(probe.axisYBlend.xyz)
            || !PBRProbeFinite(probe.axisZSlot.xyz)
            || !PBRProbeExact(probe.axisXPriority.w, 0.0, 255.0)
            || isnan(probe.axisYBlend.w) || isinf(probe.axisYBlend.w)
            || probe.axisYBlend.w <= 0.0 || probe.axisYBlend.w > 1.0
            || !PBRProbeExact(probe.axisZSlot.w, 0.0, 7.0)) return false;
    if ((probe.boxExtents.w != 0.0 && probe.boxExtents.w != 1.0)
            || (probe.boxExtents.w == 1.0 && (!PBRProbeFinite(probe.boxExtents.xyz)
                || any(lessThanEqual(probe.boxExtents.xyz, vec3(0.0)))))) return false;
    float x = dot(probe.axisXPriority.xyz, probe.axisXPriority.xyz);
    float y = dot(probe.axisYBlend.xyz, probe.axisYBlend.xyz);
    float z = dot(probe.axisZSlot.xyz, probe.axisZSlot.xyz);
    if (min(x, min(y, z)) <= 0.000001) return false;
    vec3 axisX = probe.axisXPriority.xyz * inversesqrt(x);
    vec3 axisY = probe.axisYBlend.xyz * inversesqrt(y);
    vec3 axisZ = probe.axisZSlot.xyz * inversesqrt(z);
    return abs(dot(axisX, axisY)) < 0.01 && abs(dot(axisX, axisZ)) < 0.01
        && abs(dot(axisY, axisZ)) < 0.01 && abs(dot(cross(axisX, axisY), axisZ)) > 0.99;
}

vec3 PBRProbeDiffuse(int slot, vec3 direction) {
    vec3 n = direction / max(abs(direction.x) + abs(direction.y) + abs(direction.z), 1.0e-6);
    vec2 oct = n.xy;
    if (n.z < 0.0) oct = (1.0 - abs(n.yx)) * vec2(n.x >= 0.0 ? 1.0 : -1.0, n.y >= 0.0 ? 1.0 : -1.0);
    return PBREnvironmentTile(54 + slot, oct * 0.5 + 0.5, 32.0);
}

void PBRProbeBlend(vec3 worldPosition, vec3 worldReflection, vec3 worldNormal, float roughness,
        inout vec3 prefiltered, inout vec3 irradiance) {
    if (!PBRProbeExact(probes.grid.w, 1.0, 32.0)
            || !all(equal(textureSize(lightFalloffMap, 0), ivec2(2048)))) return;
    vec3 position = PBRProbeToView(worldPosition - probes.viewOrigin.xyz);
    if (!PBRProbeFinite(position) || position.z <= 0.0) return;
    // Shared cluster rows count from the bottom. Reconstruct pre-flip NDC
    // from the interpolated world position, independent of target origin,
    // Vulkan's upper-left fragment coordinates and MSAA sample positions.
    vec2 ndc = vec2(-position.x * probes.projection.x, position.y * probes.projection.y)
        / position.z - probes.projection.zw;
    ivec3 grid = ivec3(max(probes.grid.xyz, vec3(1.0)));
    ivec2 tile = clamp(ivec2(floor((ndc * 0.5 + 0.5) * vec2(grid.xy))), ivec2(0), grid.xy - 1);
    float z = clamp(position.z, probes.depth.x, probes.depth.y);
    int slice = clamp(int(floor(log(z / probes.depth.x) / probes.depth.z * float(grid.z))), 0, grid.z - 1);
    int pair = ((slice * grid.y + tile.y) * grid.x + tile.x) * 2;
    if (pair < 0 || pair + 1 >= probes.indices.length()) return;
    vec3 reflection = PBRProbeToView(worldReflection);
    vec3 normal = PBRProbeToView(worldNormal);
    vec3 radiance = vec3(0.0), diffuse = vec3(0.0);
    float weightSum = 0.0;
    uint first = probes.indices[pair];
    for (int i = 0; i < 2; ++i) {
        uint index = probes.indices[pair + i];
        if (index >= uint(probes.grid.w) || index >= 32u || (i == 1 && index == first)) continue;
        PBRProbeRecord probe = probes.records[index];
        if (!PBRProbeValid(probe)) continue;
        mat3 orientation = transpose(mat3(normalize(probe.axisXPriority.xyz),
            normalize(probe.axisYBlend.xyz), normalize(probe.axisZSlot.xyz)));
        vec3 localPosition = orientation * (position - probe.positionRadius.xyz);
        vec4 box = probe.boxExtents;
        float weight = box.w > 0.5
            ? PBRBoxInfluence(localPosition.x, localPosition.y, localPosition.z, box.x, box.y, box.z, probe.axisYBlend.w)
            : clamp((probe.positionRadius.w - length(position - probe.positionRadius.xyz))
                / max(probe.positionRadius.w * probe.axisYBlend.w, 1.0e-6), 0.0, 1.0);
        if (weight <= 0.0) continue;
        vec3 localReflection = orientation * reflection;
        // Box-projected parallax: look up where the reflection leaves the room.
        if (box.w > 0.5) {
            float exitDistance = PBRBoxParallaxDistance(localPosition.x, localPosition.y, localPosition.z,
                localReflection.x, localReflection.y, localReflection.z, box.x, box.y, box.z);
            if (exitDistance > 0.0) localReflection = localPosition + localReflection * exitDistance;
        }
        float lod = roughness * 6.0;
        int low = int(floor(lod)), slot = int(probe.axisZSlot.w);
        vec3 tint = probe.tintIntensity.rgb * probe.tintIntensity.w;
        radiance += mix(PBREnvironmentLevel(slot, localReflection, low),
            PBREnvironmentLevel(slot, localReflection, min(low + 1, 6)), fract(lod)) * tint * weight;
        diffuse += PBRProbeDiffuse(slot, orientation * normal) * tint * weight;
        weightSum += weight;
    }
    if (weightSum <= 1.0e-6) return;
    float coverage = clamp(weightSum, 0.0, 1.0);
    prefiltered = mix(prefiltered, radiance / weightSum, coverage);
    irradiance = mix(irradiance, diffuse / weightSum, coverage);
}
