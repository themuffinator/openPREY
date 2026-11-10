#version 450

// Native Vulkan reconstruction of Quake 4's shipped glsl/Water.glsl guide
// ABI. The retail PK4s contain the guide and its parameter declarations but
// not the shader sources.
//
// Canonical shaderParm slots:
//   0 fRefractionIndexAndPower
//   1 vColorLight
//   2 vColorDark
//   3 POTCorrection
//   4 TextureTranslateScale
//   5 TextureTranslateScale2
//   6 vFogColor
//   7 vDistortionScale
//   8 localEyePos

layout(location = 0) in vec3 inPosition;
layout(location = 2) in vec3 inNormal;
layout(location = 3) in vec3 inTangent0;
layout(location = 4) in vec3 inTangent1;
layout(location = 5) in vec2 inTexCoord;

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

layout(location = 0) out vec2 vNormalTexCoord0;
layout(location = 1) out vec2 vNormalTexCoord1;
layout(location = 2) out vec3 vLocalPosition;
layout(location = 3) out vec3 vLocalNormal;
layout(location = 4) out vec3 vLocalTangent;
layout(location = 5) out vec3 vLocalBitangent;

void main() {
    gl_Position = pc.mvp * vec4(inPosition, 1.0);

    vec4 translateScale0 = material.shaderParms[4];
    vec4 translateScale1 = material.shaderParms[5];
    vNormalTexCoord0 =
        inTexCoord * translateScale0.zw + translateScale0.xy;
    vNormalTexCoord1 =
        inTexCoord * translateScale1.zw + translateScale1.xy;

    vLocalPosition = inPosition;
    vLocalNormal = inNormal;
    vLocalTangent = inTangent0;
    vLocalBitangent = inTangent1;
}
