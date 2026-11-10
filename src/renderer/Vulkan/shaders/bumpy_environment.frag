#version 450

// Quake 4 bumpyEnvironment.vfp fragment semantics.

layout(set = 0, binding = 0) uniform samplerCube environmentMap;
layout(set = 1, binding = 0) uniform sampler2D normalMap;

layout(push_constant) uniform GuiPushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    vec4 params;
} pc;

layout(location = 0) in vec2 vNormalTexCoord;
layout(location = 1) in vec3 vGlobalToEye;
layout(location = 2) in vec3 vGlobalTangent;
layout(location = 3) in vec3 vGlobalBitangent;
layout(location = 4) in vec3 vGlobalNormal;

layout(location = 0) out vec4 outColor;

vec3 SafeNormalize(vec3 value) {
    return value * inversesqrt(max(dot(value, value), 1.0e-8));
}

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
    vec4 bumpSample = texture(normalMap, vNormalTexCoord);

    // Quake 4's RXGB/DXT5 normal compression stores X in alpha, with Y and Z
    // in green and blue respectively.
    vec3 localNormal = vec3(bumpSample.a, bumpSample.g, bumpSample.b) * 2.0 - 1.0;
    localNormal = SafeNormalize(localNormal);

    // Preserve the ARB program's interpolated tangent-frame transform.  The
    // frame is not renormalized after interpolation in the original shader.
    vec3 globalNormal =
        localNormal.x * vGlobalTangent +
        localNormal.y * vGlobalBitangent +
        localNormal.z * vGlobalNormal;
    vec3 globalEye = SafeNormalize(vGlobalToEye);

    vec3 reflectionVector =
        2.0 * dot(globalEye, globalNormal) * globalNormal - globalEye;
    // The retail ARB program intentionally uses MOV rather than its
    // commented-out vertex-color multiply. Preserve that behavior; stage
    // registers still participate in the renderer's normal skip rules.
    vec4 environmentSample = texture(environmentMap, reflectionVector);
    vec4 color = vec4(environmentSample.rgb, 1.0);

    if (AlphaTestFails(color.a)) {
        discard;
    }
    outColor = color;
}
