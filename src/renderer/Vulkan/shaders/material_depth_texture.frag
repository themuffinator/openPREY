#version 450

// Compatible Vulkan implementation of Quake 4's missing
// glsl/DepthTexture.glsl fragment program.
//
// Semantic sampler sets:
//   set 0: Image
//
// Canonical shaderParms slots:
//   0 distanceScale

layout(set = 0, binding = 0) uniform sampler2D Image;

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

float LinearizeDepth(float depth) {
    const float zNear = 0.25;
    float ndcDepth = depth * 2.0 - 1.0;
    float denom = max(0.999 - ndcDepth, 0.001);
    return (2.0 * zNear) / denom;
}

void main() {
    float alpha = texture(Image, vTexCoord).a;
    float linearDepth = LinearizeDepth(gl_FragCoord.z);
    float normalizedDepth = clamp(
        linearDepth / max(material.shaderParms[0].x, 1.0),
        0.0,
        1.0);
    vec4 color = vec4(vec3(normalizedDepth), alpha);

    if (AlphaTestFails(color.a)) {
        discard;
    }
    outColor = color;
}
