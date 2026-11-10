#version 450

// Quake 4 TG_SCREEN/TG_SCREEN2 stage.
//
// The OpenGL path generates S, T, and Q from rows 0, 1, and 3 of the
// model-view-projection matrix, producing clip-space x, y, and w.  Passing
// those values as a projective coordinate preserves the fixed-function
// object-plane texgen behavior.  The Vulkan clip-z fixup changes only row 2,
// so gl_Position.x/y/w remain the same values used by the OpenGL path.

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec4 inColor;

layout(push_constant) uniform GuiPushConstants {
    mat4 mvp;
    vec4 stageColor;
    // Texture-matrix rows.  For projective coordinates the translation
    // component multiplies Q, matching GL's matrix over (S, T, 0, Q).
    vec4 texMatrixS;
    vec4 texMatrixT;
    // x: vertex color mode (0 = ignore, 1 = modulate, 2 = inverse modulate)
    // y: alpha-test mode (-1 = less, 0 = off, 1 = greater, 2 = equal)
    // z: alpha-test reference, w: texture-matrix enable
    vec4 params;
} pc;

layout(location = 0) out vec3 fragTexCoord;
layout(location = 1) out vec4 fragColor;

void main() {
    gl_Position = pc.mvp * vec4(inPosition, 1.0);

    vec3 stq = vec3(gl_Position.x, gl_Position.y, gl_Position.w);
    if (pc.params.w > 0.5) {
        vec4 projectiveCoord = vec4(stq.xy, 0.0, stq.z);
        stq.xy = vec2(dot(projectiveCoord, pc.texMatrixS),
                      dot(projectiveCoord, pc.texMatrixT));
    }
    fragTexCoord = stq;

    vec4 vertexColor = inColor;
    if (pc.params.x < 0.5) {
        vertexColor = vec4(1.0);
    } else if (pc.params.x > 1.5) {
        // GL inverse-modulate inverts RGB while alpha continues to modulate.
        vertexColor = vec4(vec3(1.0) - inColor.rgb, inColor.a);
    }
    fragColor = vertexColor * pc.stageColor;
}
