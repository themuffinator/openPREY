#version 450
#extension GL_GOOGLE_include_directive : require

// Vulkan port of openQ4's live smaa_edge.fs material program.

layout(set = 0, binding = 0) uniform sampler2D ColorTex;

layout(set = 6, binding = 0, std140) uniform MaterialShaderParms {
    vec4 shaderParms[16];
} material;

#include "material_image_coords.glsl"

layout(location = 0) in vec2 vTexCoord;
layout(location = 0) out vec4 outColor;

const vec3 kLumaWeights = vec3(0.2126, 0.7152, 0.0722);
const float kSourceColorSpaceLegacyPerceptualLDR = 0.0;
const float kSourceColorSpaceLinearLDR = 1.0;
const float kEdgeModeColor = 1.0;

float EdgeThreshold() {
    return max(material.shaderParms[2].y, 0.0001);
}

float LocalContrastAdaptationFactor() {
    return max(material.shaderParms[2].w, 0.0);
}

vec3 ToSMAAPerceptualColor(vec3 color) {
    color = clamp(color, vec3(0.0), vec3(1.0));
    vec4 sourceColorSpace = material.shaderParms[1];
    if (abs(sourceColorSpace.x - kSourceColorSpaceLegacyPerceptualLDR) < 0.5) {
        return color;
    }
    if (abs(sourceColorSpace.x - kSourceColorSpaceLinearLDR) < 0.5) {
        float gamma = max(sourceColorSpace.y, 0.0001);
        return pow(color, vec3(1.0 / gamma));
    }
    return color;
}

vec3 SamplePerceptualColor(vec2 uv) {
    return ToSMAAPerceptualColor(texture(ColorTex, MaterialImageCoord(uv, 0u)).rgb);
}

float ColorDelta(vec3 a, vec3 b) {
    vec3 delta = abs(a - b);
    return max(max(delta.r, delta.g), delta.b);
}

void main() {
    vec2 invTexSize = material.shaderParms[0].xy;
    vec4 quality = material.shaderParms[2];
    vec2 texcoord = vTexCoord;
    vec4 offset0 =
        invTexSize.xyxy * vec4(-1.0, 0.0, 0.0, -1.0) + texcoord.xyxy;
    vec4 offset1 =
        invTexSize.xyxy * vec4(1.0, 0.0, 0.0, 1.0) + texcoord.xyxy;
    vec4 offset2 =
        invTexSize.xyxy * vec4(-2.0, 0.0, 0.0, -2.0) + texcoord.xyxy;
    float threshold = EdgeThreshold();
    float localContrastAdaptationFactor = LocalContrastAdaptationFactor();

    vec3 color = SamplePerceptualColor(texcoord);
    vec3 colorLeft = SamplePerceptualColor(offset0.xy);
    vec3 colorTop = SamplePerceptualColor(offset0.zw);

    vec4 delta;
    if (abs(quality.x - kEdgeModeColor) < 0.5) {
        delta.xy = vec2(
            ColorDelta(color, colorLeft),
            ColorDelta(color, colorTop));
    } else {
        float luma = dot(color, kLumaWeights);
        delta.xy = abs(luma - vec2(
            dot(colorLeft, kLumaWeights),
            dot(colorTop, kLumaWeights)));
    }

    vec2 edges = step(vec2(threshold), delta.xy);
    if (dot(edges, vec2(1.0)) == 0.0) {
        discard;
    }

    vec3 colorRight = SamplePerceptualColor(offset1.xy);
    vec3 colorBottom = SamplePerceptualColor(offset1.zw);
    if (abs(quality.x - kEdgeModeColor) < 0.5) {
        delta.zw = vec2(
            ColorDelta(color, colorRight),
            ColorDelta(color, colorBottom));
    } else {
        float luma = dot(color, kLumaWeights);
        delta.zw = abs(luma - vec2(
            dot(colorRight, kLumaWeights),
            dot(colorBottom, kLumaWeights)));
    }

    vec2 maxDelta = max(delta.xy, delta.zw);
    vec3 colorLeftLeft = SamplePerceptualColor(offset2.xy);
    vec3 colorTopTop = SamplePerceptualColor(offset2.zw);
    if (abs(quality.x - kEdgeModeColor) < 0.5) {
        delta.zw = vec2(
            ColorDelta(colorLeft, colorLeftLeft),
            ColorDelta(colorTop, colorTopTop));
    } else {
        delta.zw = abs(vec2(
            dot(colorLeft, kLumaWeights),
            dot(colorTop, kLumaWeights)) - vec2(
            dot(colorLeftLeft, kLumaWeights),
            dot(colorTopTop, kLumaWeights)));
    }

    maxDelta = max(maxDelta, delta.zw);
    float finalDelta = max(maxDelta.x, maxDelta.y);
    edges *= step(vec2(finalDelta),
        vec2(localContrastAdaptationFactor) * delta.xy);
    outColor = vec4(edges, 0.0, 0.0);
}
