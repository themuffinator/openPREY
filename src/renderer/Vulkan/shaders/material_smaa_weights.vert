#version 450

// Vulkan material-stage wrapper for openQ4's SMAA fullscreen vertex shader.

layout(location = 0) in vec3 inPosition;
layout(location = 5) in vec2 inTexCoord;

layout(push_constant) uniform StagePushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    vec4 params;
} pc;

layout(location = 0) out vec2 vTexCoord;

void main() {
    gl_Position = pc.mvp * vec4(inPosition, 1.0);
    vTexCoord = inTexCoord;
}
