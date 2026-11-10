#version 450

// Quake 4 bumpyEnvironment.vfp vertex semantics.
//
// Consumes the full idDrawVert input used by the interaction pipelines.  The
// stock ARB program transforms the object-space eye vector and tangent frame
// into global space with program.env[6..8]; those values arrive here through
// a compact dynamic uniform block.

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec4 inColor;
layout(location = 2) in vec3 inNormal;
layout(location = 3) in vec3 inTangent0;
layout(location = 4) in vec3 inTangent1;
layout(location = 5) in vec2 inTexCoord;

layout(push_constant) uniform GuiPushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    // x: vertex color mode (0 = ignore, 1 = modulate, 2 = inverse modulate)
    // y: alpha-test mode (-1 = less, 0 = off, 1 = greater, 2 = equal)
    // z: alpha-test reference
    vec4 params;
} pc;

layout(set = 6, binding = 0, std140) uniform BumpyEnvironmentBlock {
    vec4 localViewOrigin;
    vec4 modelRow0;
    vec4 modelRow1;
    vec4 modelRow2;
} env;

layout(location = 0) out vec2 vNormalTexCoord;
layout(location = 1) out vec3 vGlobalToEye;
layout(location = 2) out vec3 vGlobalTangent;
layout(location = 3) out vec3 vGlobalBitangent;
layout(location = 4) out vec3 vGlobalNormal;

vec3 TransformDirectionToGlobal(vec3 direction) {
    return vec3(
        dot(direction, env.modelRow0.xyz),
        dot(direction, env.modelRow1.xyz),
        dot(direction, env.modelRow2.xyz));
}

void main() {
    gl_Position = pc.mvp * vec4(inPosition, 1.0);

    // The original program deliberately passes the normal-map coordinates
    // through unmodified.
    vNormalTexCoord = inTexCoord;

    vGlobalToEye = TransformDirectionToGlobal(
        env.localViewOrigin.xyz - inPosition);
    vGlobalTangent = TransformDirectionToGlobal(inTangent0);
    vGlobalBitangent = TransformDirectionToGlobal(inTangent1);
    vGlobalNormal = TransformDirectionToGlobal(inNormal);
}
