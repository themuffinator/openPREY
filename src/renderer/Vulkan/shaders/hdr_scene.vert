// Copyright (C) 2026 DarkMatter Productions
#version 450

// No interpolated coordinates: fetches use framebuffer texel coordinates so
// seed and composition preserve rows and individual samples without a resolve.
void main() {
    vec2 position = vec2((gl_VertexIndex << 1) & 2, gl_VertexIndex & 2);
    gl_Position = vec4(position * 2.0 - 1.0, 0.0, 1.0);
}
