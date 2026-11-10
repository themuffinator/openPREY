#version 450

// Full-screen triangle for the native-output temporal presentation pass.
// This pass deliberately uses a positive Vulkan viewport: fragUV therefore
// follows image-memory coordinates (0,0 is the top-left texel) even though
// the rest of the renderer preserves idTech's bottom-left view convention
// with negative-height viewports.

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
