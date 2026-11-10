#version 450

// Match the renderer's HDR luminance pyramid, including edge clamping and
// logarithmic averaging. Each pass halves the dimensions, rounding up.
layout(set = 0, binding = 0) uniform sampler2D Scene;
layout(std140, set = 6, binding = 0) uniform HDRLuminanceBlock {
    vec4 source; // xy: inverse source extent; z: source contains scene color
} block;
layout(location = 0) in vec2 fragUV;
layout(location = 0) out vec4 outColor;

float SampleValue(vec2 uv) {
    vec3 value = texture(Scene, uv).rgb;
    if (block.source.z > 0.5) {
        return log(max(dot(max(value, vec3(0.0)), vec3(0.2126, 0.7152, 0.0722)), 0.0001));
    }
    return value.r;
}

void main() {
    vec2 halfTexel = block.source.xy * 0.5;
    float value = SampleValue(fragUV + vec2(-halfTexel.x, -halfTexel.y));
    value += SampleValue(fragUV + vec2(halfTexel.x, -halfTexel.y));
    value += SampleValue(fragUV + vec2(-halfTexel.x, halfTexel.y));
    value += SampleValue(fragUV + vec2(halfTexel.x, halfTexel.y));
    outColor = vec4(vec3(value * 0.25), 1.0);
}
