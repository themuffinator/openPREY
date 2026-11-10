#version 450

// Compatibility reconstruction for the source-less Quake 4
// monochrome.vfp test program. The shipped material supplies only position,
// base ST, and fragmentMap 0.

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec2 inTexCoord;

layout(push_constant) uniform StagePushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    // y: alpha-test mode (-1 less, 0 off, 1 greater, 2 equal)
    // z: alpha-test reference
    vec4 params;
} pc;

layout(location = 0) out vec2 vTexCoord;

void main() {
    gl_Position = pc.mvp * vec4(inPosition, 1.0);
    vTexCoord = inTexCoord;
}
