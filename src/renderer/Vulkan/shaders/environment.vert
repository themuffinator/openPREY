#version 450

// Quake 4 TG_REFLECT_CUBE / environment.vfp vertex semantics.

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec3 inNormal;
layout(location = 2) in vec4 inColor;

layout(push_constant) uniform GuiPushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;    // xyz: model-local view origin
    vec4 texMatrixT;
    // x: vertex color mode, y: alpha-test mode, z: alpha-test reference
    vec4 params;
} pc;

layout(location = 0) out vec3 fragNormal;
layout(location = 1) out vec3 fragToEye;
layout(location = 2) out vec4 fragColor;

void main() {
    gl_Position = pc.mvp * vec4(inPosition, 1.0);
    fragNormal = inNormal;
    fragToEye = pc.texMatrixS.xyz - inPosition;
    if (pc.params.x < 0.5) {
        fragColor = pc.stageColor;
    } else {
        // The ARB environment fragment program bypasses GL texture unit 1,
        // so both vertexColor modes observe the raw color array.
        fragColor = inColor;
    }
}
