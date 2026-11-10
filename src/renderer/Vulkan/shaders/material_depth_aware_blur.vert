#version 450

// Native Vulkan port of openQ4's live glprogs/blur.vs postprocess stage.

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
