#version 450

// Native Vulkan port of Quake 4's shipped arbVP_glasswarp.txt stage.
//
// The stage texture coordinate addresses the warp map while the fragment
// program receives clip-space X, Y, and W for the projected scratch-image
// lookup.  The 128-byte block matches the renderer-wide stage ABI.

layout(location = 0) in vec3 inPosition;
layout(location = 5) in vec2 inTexCoord;

layout(push_constant) uniform StagePushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    // w: texture-matrix enable
    vec4 params;
} pc;

layout(location = 0) out vec2 vWarpTexCoord;
layout(location = 1) out vec3 vClipCoord;

void main() {
    gl_Position = pc.mvp * vec4(inPosition, 1.0);

    vec2 stageTexCoord = inTexCoord;
    if (pc.params.w > 0.5) {
        vec4 st = vec4(inTexCoord, 0.0, 1.0);
        stageTexCoord = vec2(
            dot(st, pc.texMatrixS),
            dot(st, pc.texMatrixT));
    }

    vWarpTexCoord = stageTexCoord;
    vClipCoord = vec3(gl_Position.xy, gl_Position.w);
}
