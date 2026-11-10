#version 450
#extension GL_GOOGLE_include_directive : require
#include "framebuffer_coords.glsl"

// Native reconstruction of the source-less Quake 4 Water guide program.
// The implementation preserves the authored two-normal, reflection,
// refraction, Fresnel, tint, and fog ABI without requiring replacement
// material or shader assets.
//
// Semantic sampler sets:
//   set 0: NoiseNormalTexture
//   set 1: NoiseNormalTexture2
//   set 2: ReflectTexture (_reflectionRender)
//   set 3: RefractTexture (_currentRender)

layout(set = 0, binding = 0) uniform sampler2D NoiseNormalTexture;
layout(set = 1, binding = 0) uniform sampler2D NoiseNormalTexture2;
layout(set = 2, binding = 0) uniform sampler2D ReflectTexture;
layout(set = 3, binding = 0) uniform sampler2D RefractTexture;

layout(set = 6, binding = 0, std140) uniform MaterialShaderParms {
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

layout(location = 0) in vec2 vNormalTexCoord0;
layout(location = 1) in vec2 vNormalTexCoord1;
layout(location = 2) in vec3 vLocalPosition;
layout(location = 3) in vec3 vLocalNormal;
layout(location = 4) in vec3 vLocalTangent;
layout(location = 5) in vec3 vLocalBitangent;

layout(location = 0) out vec4 outColor;

vec3 SafeNormalize(vec3 value) {
    return value * inversesqrt(max(dot(value, value), 1.0e-8));
}

vec3 DecodeNormal(vec4 sampleValue) {
    // Quake 4 normal maps use RXGB/DXT5 layout: X in alpha, Y in green,
    // Z in blue.
    return SafeNormalize(vec3(
        sampleValue.a, sampleValue.g, sampleValue.b) * 2.0 - 1.0);
}

vec2 CurrentRenderCoord() {
    float framebufferHeight = max(material.shaderParms[12].x, 1.0);
    vec2 viewportOrigin = material.shaderParms[13].xy;
    vec2 viewportSize = max(material.shaderParms[14].xy, vec2(1.0));
    vec2 textureScale = max(material.shaderParms[15].xy, vec2(1.0e-6));

    // Captured render maps retain OpenGL's bottom-up texture convention.
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
    vec3 normal0 = DecodeNormal(
        texture(NoiseNormalTexture, vNormalTexCoord0));
    vec3 normal1 = DecodeNormal(
        texture(NoiseNormalTexture2, vNormalTexCoord1));

    vec4 distortionScale = material.shaderParms[7];
    vec3 tangentNormal = SafeNormalize(vec3(
        normal0.xy * distortionScale.z
            + normal1.xy * distortionScale.w,
        max(0.08, normal0.z * distortionScale.z
            + normal1.z * distortionScale.w)));

    vec3 objectNormal = SafeNormalize(
        tangentNormal.x * vLocalTangent
        + tangentNormal.y * vLocalBitangent
        + tangentNormal.z * vLocalNormal);
    vec3 toEye = SafeNormalize(
        material.shaderParms[8].xyz - vLocalPosition);

    float ior = max(material.shaderParms[0].x, 1.0001);
    float fresnelPower = max(material.shaderParms[0].y, 0.001);
    float f0 = (ior - 1.0) / (ior + 1.0);
    f0 *= f0;
    float fresnel = f0 + (1.0 - f0)
        * pow(1.0 - clamp(dot(toEye, objectNormal), 0.0, 1.0),
              fresnelPower);

    vec2 viewportSize = max(material.shaderParms[14].xy, vec2(1.0));
    vec2 textureScale = max(material.shaderParms[15].xy, vec2(1.0e-6));
    vec2 baseCoord = CurrentRenderCoord();
    vec2 refractionOffset =
        tangentNormal.xy * distortionScale.x / viewportSize * textureScale;
    vec2 reflectionOffset =
        tangentNormal.xy * distortionScale.y / viewportSize * textureScale;

    // POTCorrection is the authored render-map clamp. It is 1 on native
    // non-padded images and below 1 when the source occupies a POT backing.
    vec2 potCorrection = material.shaderParms[3].xy;
    if (any(lessThanEqual(potCorrection, vec2(0.0)))) {
        potCorrection = vec2(1.0);
    }
    vec2 maxCoord = min(textureScale, potCorrection);
    vec2 refractCoord =
        clamp(baseCoord + refractionOffset, vec2(0.0), maxCoord);
    vec2 reflectCoord =
        clamp(baseCoord - reflectionOffset, vec2(0.0), maxCoord);

    vec3 refracted = texture(RefractTexture, refractCoord).rgb;
    vec3 reflected = texture(ReflectTexture, reflectCoord).rgb;

    vec3 lightColor = material.shaderParms[1].rgb;
    vec3 darkColor = material.shaderParms[2].rgb;
    float facing = clamp(abs(objectNormal.z), 0.0, 1.0);
    vec3 waterTint = mix(darkColor, lightColor, facing);

    vec3 color = mix(refracted * waterTint, reflected, fresnel);
    vec4 fog = material.shaderParms[6];
    color = mix(color, fog.rgb, clamp(fog.a * (1.0 - facing), 0.0, 1.0));

    vec4 result = vec4(color, 1.0) * pc.stageColor;
    if (AlphaTestFails(result.a)) {
        discard;
    }
    outColor = result;
}
