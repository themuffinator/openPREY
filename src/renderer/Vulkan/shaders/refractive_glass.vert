#version 450

// Native Vulkan reconstruction of the source-less arbFP1_Glass.cg /
// nvFP20_Glass.cg pair referenced by Quake 4's refractiveGlass guide.
//
// Material parameter slots supplied by the executor:
//   0 vertexParm 0: POT correction (xy)
//   1 vertexParm 1: index of refraction, Fresnel power (xy)
//   2 local view origin
//   3..5 local-to-world direction rows
//   12..15 framebuffer/current-render facts

layout(location = 0) in vec3 inPosition;
layout(location = 2) in vec3 inNormal;
layout(location = 3) in vec3 inTangent0;
layout(location = 4) in vec3 inTangent1;
layout(location = 5) in vec2 inTexCoord;

layout(set = 6, binding = 0, std140) uniform GlassProgramParms {
    vec4 shaderParms[16];
} material;

layout(push_constant) uniform StagePushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    vec4 params;
} pc;

layout(location = 0) out vec2 vOffsetTexCoord;
layout(location = 1) out vec3 vLocalPosition;
layout(location = 2) out vec3 vLocalNormal;
layout(location = 3) out vec3 vLocalTangent;
layout(location = 4) out vec3 vLocalBitangent;

void main() {
    gl_Position = pc.mvp * vec4(inPosition, 1.0);
    vOffsetTexCoord = inTexCoord;
    vLocalPosition = inPosition;
    vLocalNormal = inNormal;
    vLocalTangent = inTangent0;
    vLocalBitangent = inTangent1;
}
