#version 450

// One covering triangle for the full-screen post passes in vk_PostProcess.cpp.
// These passes draw with a positive-height viewport, so fragUV follows
// image-memory order: (0,0) is the top-left texel of the target. The
// executor's colour captures (VK_Exec_CopyRender) store rows bottom-up like
// OpenGL textures, so a pass that samples one flips V.

layout(location = 0) out vec2 fragUV;

void main() {
    const vec2 positions[3] = vec2[3](
        vec2(-1.0, -1.0),
        vec2( 3.0, -1.0),
        vec2(-1.0,  3.0)
    );
    vec2 position = positions[gl_VertexIndex];
    gl_Position = vec4(position, 0.0, 1.0);
    fragUV = position * 0.5 + 0.5;
}
