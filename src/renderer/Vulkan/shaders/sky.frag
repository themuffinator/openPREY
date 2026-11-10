#version 450

// openQ4 Vulkan cube-texgen pipeline — fragment stage (Phase E).
//
// Samples the stage's cube map along the interpolated direction. The GL
// reference feeds the same 3-float texcoords to a GL_TEXTURE_CUBE_MAP and
// cube faces upload in the same +X..-Z layer order, so stageColor
// modulation is the only color math (sky stages carry no vertex color or
// alpha test).

layout(binding = 0) uniform samplerCube texSampler;

layout(location = 0) in vec3 fragTexDir;

layout(push_constant) uniform GuiPushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    vec4 params;
} pc;

layout(location = 0) out vec4 outColor;

void main() {
    outColor = texture(texSampler, fragTexDir) * pc.stageColor;
}
