#version 450
#extension GL_GOOGLE_include_directive : require
#include "framebuffer_coords.glsl"

// ABI-faithful reconstruction of Quake 4's unshipped refractive-glass CG
// programs: offset normal + projected scene refraction + environment cube,
// blended by the guide's index-of-refraction and Fresnel-power controls.

layout(set = 0, binding = 0) uniform sampler2D OffsetImage;
layout(set = 1, binding = 0) uniform sampler2D CurrentRender;
layout(set = 2, binding = 0) uniform samplerCube EnvironmentImage;

layout(set = 6, binding = 0, std140) uniform GlassProgramParms {
    vec4 shaderParms[16];
} material;

layout(push_constant) uniform StagePushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    // y: alpha-test mode, z: alpha-test reference
    vec4 params;
} pc;

layout(location = 0) in vec2 vOffsetTexCoord;
layout(location = 1) in vec3 vLocalPosition;
layout(location = 2) in vec3 vLocalNormal;
layout(location = 3) in vec3 vLocalTangent;
layout(location = 4) in vec3 vLocalBitangent;

layout(location = 0) out vec4 outColor;

vec3 SafeNormalize(vec3 value) {
    return value * inversesqrt(max(dot(value, value), 1.0e-8));
}

vec3 DecodeNormal(vec4 sampleValue) {
    return SafeNormalize(vec3(
        sampleValue.a, sampleValue.g, sampleValue.b) * 2.0 - 1.0);
}

vec3 LocalDirectionToWorld(vec3 direction) {
    return vec3(
        dot(direction, material.shaderParms[3].xyz),
        dot(direction, material.shaderParms[4].xyz),
        dot(direction, material.shaderParms[5].xyz));
}

vec2 CurrentRenderCoord() {
    float framebufferHeight = max(material.shaderParms[12].x, 1.0);
    vec2 viewportOrigin = material.shaderParms[13].xy;
    vec2 viewportSize = max(material.shaderParms[14].xy, vec2(1.0));
    vec2 textureScale = max(material.shaderParms[15].xy, vec2(1.0e-6));
    vec2 windowGL = vec2(gl_FragCoord.x, CanonicalWindowY(framebufferHeight));
    vec2 viewportCoord = (windowGL - viewportOrigin) / viewportSize;
    return clamp(viewportCoord * textureScale, vec2(0.0), textureScale);
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
    vec3 tangentNormal = DecodeNormal(
        texture(OffsetImage, vOffsetTexCoord));
    vec3 localNormal = SafeNormalize(
        tangentNormal.x * vLocalTangent
        + tangentNormal.y * vLocalBitangent
        + tangentNormal.z * vLocalNormal);
    vec3 toEye = SafeNormalize(
        material.shaderParms[2].xyz - vLocalPosition);

    float ior = max(material.shaderParms[1].x, 1.0001);
    float fresnelPower = max(material.shaderParms[1].y, 0.001);
    float f0 = (ior - 1.0) / (ior + 1.0);
    f0 *= f0;
    float fresnel = f0 + (1.0 - f0)
        * pow(1.0 - clamp(dot(toEye, localNormal), 0.0, 1.0),
              fresnelPower);

    vec2 textureScale = max(material.shaderParms[15].xy, vec2(1.0e-6));
    vec2 viewportSize = max(material.shaderParms[14].xy, vec2(1.0));
    vec2 potCorrection = material.shaderParms[0].xy;
    if (any(lessThanEqual(potCorrection, vec2(0.0)))) {
        potCorrection = vec2(1.0);
    }

    // Refraction grows with the difference between air and the material.
    // OffsetImage supplies a tangent-space normal, matching the guide's
    // high-quality `_n` branch and its older DSDT fallback.
    float refractionAmount = (1.0 - 1.0 / ior) * 32.0;
    vec2 offset =
        tangentNormal.xy * refractionAmount / viewportSize * textureScale;
    vec2 sceneCoord = clamp(
        CurrentRenderCoord() + offset,
        vec2(0.0), min(textureScale, potCorrection));
    vec3 refracted = texture(CurrentRender, sceneCoord).rgb;

    vec3 reflectedLocal = reflect(-toEye, localNormal);
    vec3 reflectedWorld =
        SafeNormalize(LocalDirectionToWorld(reflectedLocal));
    vec3 reflected = texture(EnvironmentImage, reflectedWorld).rgb;

    vec4 result =
        vec4(mix(refracted, reflected, fresnel), 1.0) * pc.stageColor;
    if (AlphaTestFails(result.a)) {
        discard;
    }
    outColor = result;
}
