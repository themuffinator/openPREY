#version 450

// Native Vulkan restoration for the stock material-program name
// glsl/AL.glsl.  Raven's paired source is absent from the retail archives;
// this uses the compatible in-tree Alpha Labs light-overlay contract.
//
// Canonical shaderParms slots:
//   0 distanceScale
//   1 textureScale (xy)
//   2 LightLoc (xyz)
//   3 LightColor (rgba)
//   4 LightSize
//   5 LightBehind
//   6 LightMinDistance

layout(location = 0) in vec3 inPosition;
layout(location = 5) in vec2 inTexCoord;

layout(push_constant) uniform StagePushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    vec4 params;
} pc;

layout(location = 0) out vec2 vLightTexCoord;

void main() {
    gl_Position = pc.mvp * vec4(inPosition, 1.0);
    vLightTexCoord = inTexCoord;
}
