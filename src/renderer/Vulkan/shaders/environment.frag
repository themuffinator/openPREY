#version 450

// Quake 4 TG_REFLECT_CUBE / environment.vfp fragment semantics.

layout(binding = 0) uniform samplerCube texSampler;

layout(location = 0) in vec3 fragNormal;
layout(location = 1) in vec3 fragToEye;
layout(location = 2) in vec4 fragColor;

layout(push_constant) uniform GuiPushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    vec4 params;
} pc;

layout(location = 0) out vec4 outColor;

bool alphaTestFails(float alpha) {
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
    vec3 n = normalize(fragNormal);
    vec3 toEye = normalize(fragToEye);
    vec3 r = 2.0 * dot(toEye, n) * n - toEye;
    vec4 color = texture(texSampler, r) * fragColor;
    if (alphaTestFails(color.a)) {
        discard;
    }
    outColor = color;
}
