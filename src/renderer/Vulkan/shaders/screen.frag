#version 450

// Quake 4 TG_SCREEN/TG_SCREEN2 stage.
//
// _currentRender is captured with bottom-up row orientation, matching the
// OpenGL texture convention.  Consequently the projective T coordinate is
// sampled directly and must not be flipped here.

layout(binding = 0) uniform sampler2D texSampler;

layout(location = 0) in vec3 fragTexCoord;
layout(location = 1) in vec4 fragColor;

layout(push_constant) uniform GuiPushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    // x: vertex color mode, y: alpha-test mode, z: reference, w: matrix
    vec4 params;
} pc;

layout(location = 0) out vec4 outColor;

void main() {
    vec2 uv = fragTexCoord.xy / fragTexCoord.z;
    vec4 color = texture(texSampler, uv) * fragColor;

    if (pc.params.y > 1.5) {
        if (abs(color.a - pc.params.z) > (0.5 / 255.0)) {
            discard;
        }
    } else if (pc.params.y > 0.5) {
        if (color.a <= pc.params.z) {
            discard;
        }
    } else if (pc.params.y < -0.5) {
        if (color.a >= pc.params.z) {
            discard;
        }
    }

    outColor = color;
}
