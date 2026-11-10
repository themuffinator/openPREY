#version 450

// Native Vulkan port of openQ4's live glprogs/blur.fs depth-aware
// postprocess. This is intentionally a separate family from the retail
// glsl/Blur.glsl contract.
//
// Semantic sampler sets:
//   set 0: Scene
//   set 1: DepthTex
//
// Canonical shaderParms slots:
//   0 invTexSize (xy)
//   1 range
//   2 focus
//   3 approachColor (rgba)
//   4 approachPercent
//   5 specialDepthZNear (controller distance scale is consumed at the C++ boundary)

layout(set = 0, binding = 0) uniform sampler2D Scene;
layout(set = 1, binding = 0) uniform sampler2D DepthTex;

layout(set = 6, binding = 0, std140) uniform MaterialShaderParms {
    vec4 shaderParms[16];
} material;

layout(location = 0) in vec2 vTexCoord;
layout(location = 0) out vec4 outColor;

float LinearizeDepth(float depth, float zNear) {
    float ndcDepth = depth * 2.0 - 1.0;
    float denom = max(0.999 - ndcDepth, 0.001);
    return (2.0 * zNear) / denom;
}

float ViewDistanceFromDepth(float depth, float zNear) {
    return depth < 0.99999 ? LinearizeDepth(depth, zNear) : 4096.0;
}

float CircleOfConfusion(
        float viewDistance,
        float focusDistance,
        float blurRange,
        float blurStrength) {
    float blurFactor = clamp(
        abs(viewDistance - focusDistance) / blurRange, 0.0, 1.0);
    return smoothstep(0.0, 1.0, blurFactor) * blurStrength;
}

void GatherDepthAwareSample(
        vec2 uv,
        vec2 minUv,
        vec2 maxUv,
        vec2 kernelScale,
        vec2 kernelPoint,
        float radialWeight,
        float centerDistance,
        float zNear,
        inout vec4 colorSum,
        inout float weightSum) {
    vec2 sampleUv = clamp(uv + kernelPoint * kernelScale, minUv, maxUv);
    float sampleDepth = texture(DepthTex, sampleUv).x;
    float sampleDistance = ViewDistanceFromDepth(sampleDepth, zNear);
    float depthDelta = abs(sampleDistance - centerDistance);
    float depthTolerance =
        max(3.0, min(centerDistance, sampleDistance) * 0.04);
    float sameSurface = 1.0 - smoothstep(
        depthTolerance, depthTolerance * 4.0, depthDelta);
    float sampleWeight = radialWeight * mix(0.02, 1.0, sameSurface);

    colorSum += texture(Scene, sampleUv) * sampleWeight;
    weightSum += sampleWeight;
}

void main() {
    vec2 invTexSize = material.shaderParms[0].xy;
    float effectRange = material.shaderParms[1].x;
    float focus = material.shaderParms[2].x;
    vec4 approachColor = material.shaderParms[3];
    float approachPercent = material.shaderParms[4].x;
    // The material ABI retains its historical slot; the C++ boundary now
    // writes the special-depth near plane here after consuming distanceScale.
    float distanceScale = material.shaderParms[5].x;

    vec2 uv = vTexCoord;
    vec4 scene = texture(Scene, uv);
    float blurStrength = clamp(approachPercent, 0.0, 1.0);
    float zNear = max(distanceScale, 0.25);
    float focusDistance = max(focus, 0.0);
    if (focusDistance <= 0.0) {
        float focusDepth = texture(DepthTex, vec2(0.5)).x;
        focusDistance = focusDepth < 0.99999
            ? LinearizeDepth(focusDepth, zNear)
            : 16.0;
    }

    float blurRange = max(effectRange, 0.0);
    if (blurRange <= 0.0) {
        blurRange = max(64.0, focusDistance * 0.25);
    }

    float depth = texture(DepthTex, uv).x;
    float viewDistance = ViewDistanceFromDepth(depth, zNear);
    float blurAmount = CircleOfConfusion(
        viewDistance, focusDistance, blurRange, blurStrength);
    if (blurAmount <= 0.001) {
        outColor = scene;
        return;
    }

    vec2 kernelScale = invTexSize * (24.0 * blurAmount);
    vec2 minUv = invTexSize * 0.5;
    vec2 maxUv = vec2(1.0) - minUv;
    vec4 blur = scene;
    float blurWeight = 1.0;

    GatherDepthAwareSample(uv, minUv, maxUv, kernelScale,
        vec2( 0.197990,  0.197990), 0.86,
        viewDistance, zNear, blur, blurWeight);
    GatherDepthAwareSample(uv, minUv, maxUv, kernelScale,
        vec2(-0.197990,  0.197990), 0.86,
        viewDistance, zNear, blur, blurWeight);
    GatherDepthAwareSample(uv, minUv, maxUv, kernelScale,
        vec2(-0.197990, -0.197990), 0.86,
        viewDistance, zNear, blur, blurWeight);
    GatherDepthAwareSample(uv, minUv, maxUv, kernelScale,
        vec2( 0.197990, -0.197990), 0.86,
        viewDistance, zNear, blur, blurWeight);

    GatherDepthAwareSample(uv, minUv, maxUv, kernelScale,
        vec2( 0.620000,  0.000000), 0.46,
        viewDistance, zNear, blur, blurWeight);
    GatherDepthAwareSample(uv, minUv, maxUv, kernelScale,
        vec2( 0.310000,  0.536936), 0.46,
        viewDistance, zNear, blur, blurWeight);
    GatherDepthAwareSample(uv, minUv, maxUv, kernelScale,
        vec2(-0.310000,  0.536936), 0.46,
        viewDistance, zNear, blur, blurWeight);
    GatherDepthAwareSample(uv, minUv, maxUv, kernelScale,
        vec2(-0.620000,  0.000000), 0.46,
        viewDistance, zNear, blur, blurWeight);
    GatherDepthAwareSample(uv, minUv, maxUv, kernelScale,
        vec2(-0.310000, -0.536936), 0.46,
        viewDistance, zNear, blur, blurWeight);
    GatherDepthAwareSample(uv, minUv, maxUv, kernelScale,
        vec2( 0.310000, -0.536936), 0.46,
        viewDistance, zNear, blur, blurWeight);

    GatherDepthAwareSample(uv, minUv, maxUv, kernelScale,
        vec2( 0.923880,  0.382683), 0.14,
        viewDistance, zNear, blur, blurWeight);
    GatherDepthAwareSample(uv, minUv, maxUv, kernelScale,
        vec2( 0.382683,  0.923880), 0.14,
        viewDistance, zNear, blur, blurWeight);
    GatherDepthAwareSample(uv, minUv, maxUv, kernelScale,
        vec2(-0.382683,  0.923880), 0.14,
        viewDistance, zNear, blur, blurWeight);
    GatherDepthAwareSample(uv, minUv, maxUv, kernelScale,
        vec2(-0.923880,  0.382683), 0.14,
        viewDistance, zNear, blur, blurWeight);
    GatherDepthAwareSample(uv, minUv, maxUv, kernelScale,
        vec2(-0.923880, -0.382683), 0.14,
        viewDistance, zNear, blur, blurWeight);
    GatherDepthAwareSample(uv, minUv, maxUv, kernelScale,
        vec2(-0.382683, -0.923880), 0.14,
        viewDistance, zNear, blur, blurWeight);
    GatherDepthAwareSample(uv, minUv, maxUv, kernelScale,
        vec2( 0.382683, -0.923880), 0.14,
        viewDistance, zNear, blur, blurWeight);
    GatherDepthAwareSample(uv, minUv, maxUv, kernelScale,
        vec2( 0.923880, -0.382683), 0.14,
        viewDistance, zNear, blur, blurWeight);

    blur /= max(blurWeight, 0.0001);
    vec4 mixed = mix(scene, blur, blurAmount);
    float tintAmount =
        blurAmount * clamp(approachColor.a, 0.0, 1.0) * 0.04;
    mixed.rgb = mix(mixed.rgb, approachColor.rgb, tintAmount);
    mixed.a = scene.a;
    outColor = mixed;
}
