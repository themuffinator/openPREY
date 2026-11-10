#version 450

// openQ4 Vulkan cube-texgen pipeline — vertex stage (Phase E,
// TG_SKYBOX_CUBE / TG_WOBBLESKY_CUBE / TG_DIFFUSE_CUBE).
//
// Binding 0 carries the idDrawVert position; location 1 carries the
// per-vertex cube direction — either the front-end texgen's tightly packed
// vec3 stream (skybox/wobblesky, RB_BindStageTexture's dynamicTexCoords
// contract) or the idDrawVert normal (diffuse cube). The push-constant
// block matches the GUI pipeline so one pipeline layout serves both;
// texMatrix and params stay unused here.

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec3 inTexDir;

layout(push_constant) uniform GuiPushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    vec4 params;
} pc;

layout(location = 0) out vec3 fragTexDir;

void main() {
    gl_Position = pc.mvp * vec4(inPosition, 1.0);
    fragTexDir = inTexDir;
}
