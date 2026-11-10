#version 450

// Compatibility reconstruction for Quake 4's source-less monochrome.vfp.
// Preserve sampled alpha so authored blending remains authoritative.

layout(set = 0, binding = 0) uniform sampler2D Image;

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
    vec4 sampled = texture(Image, vTexCoord);
    float luminance = dot(sampled.rgb, vec3(0.33));
    vec4 color = vec4(vec3(luminance), sampled.a) * pc.stageColor;
    if (AlphaTestFails(color.a)) {
        discard;
    }
    outColor = color;
}
