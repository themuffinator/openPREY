#version 450

// Compatible Vulkan implementation of Quake 4's missing glsl/MedLabs.glsl
// fragment program.
//
// Semantic sampler sets:
//   set 0: Depth
//   set 1: Blur1
//   set 2: Variance
//
// Canonical shaderParms slots:
//   0 range
//   1 focus
//   2 Scroll
//   3 ApproachColor (rgba)
//   4 ApproachPercent

layout(set = 0, binding = 0) uniform sampler2D Depth;
layout(set = 1, binding = 0) uniform sampler2D Blur1;
layout(set = 2, binding = 0) uniform sampler2D Variance;

layout(set = 6, binding = 0, std140) uniform MaterialShaderParms {
    vec4 shaderParms[16];
} material;

layout(push_constant) uniform StagePushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    vec4 params;
} pc;

layout(location = 0) in vec2 vTexCoord;

layout(location = 0) out vec4 outColor;

bool AlphaTestFails(float alpha) {
    if (pc.params.y > 1.5) {
        return abs(alpha - pc.params.z) > (0.5 / 255.0);
    }
    if (pc.params.y > 0.5) {
        return alpha <= pc.params.z;
    }
    if (pc.params.y < -0.5) {
        return alpha >= pc.params.z;
    }
    return false;
}

void main() {
    vec2 uv = vTexCoord;
    float depth = texture(Depth, uv).r;
    vec3 blurredScene = texture(Blur1, uv).rgb;

    float effectRange = material.shaderParms[0].x;
    float focus = material.shaderParms[1].x;
    float scroll = material.shaderParms[2].x;
    vec4 approachColor = material.shaderParms[3];
    float approachPercent = material.shaderParms[4].x;

    float safeRange = max(effectRange, 0.01);
    float clearBand = max(0.015, 1.0 / (safeRange * 6.0));
    float blurFactor = smoothstep(
        clearBand,
        clearBand * (1.5 + safeRange * 0.5),
        abs(depth - focus));
    float tintAmount = clamp(approachPercent, 0.0, 1.0);

    // The white Variance map authored by stock content preserves the
    // established procedural behavior.  Replacement maps can modulate that
    // cycle through the semantic sampler the original material declares.
    vec2 varianceCoord = fract(uv + vec2(scroll, scroll * 0.61803399));
    float varianceMap = texture(Variance, varianceCoord).r;
    float proceduralVariance =
        sin((uv.x + uv.y + scroll) * 6.28318531) * 0.5 + 0.5;
    float variance = proceduralVariance * varianceMap;

    vec3 overlayColor = mix(
        blurredScene,
        approachColor.rgb,
        tintAmount * variance);
    float alpha = blurFactor
        * clamp(0.6 + tintAmount * 0.4, 0.0, 1.0);
    vec4 color = vec4(overlayColor, alpha);

    if (AlphaTestFails(color.a)) {
        discard;
    }
    outColor = color;
}
