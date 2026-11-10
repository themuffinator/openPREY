#version 450

// A port of content/baseoq4/pak0/glprogs/player_outline.fs: one flat colour.
// The brightskin wash uses it too, with the colour OpenGL sets through
// glColor on its fixed-function path.

layout(push_constant) uniform OutlinePush {
    mat4 mvp;
    vec4 color;
    vec4 outlineParams;
} pc;

layout(location = 0) out vec4 outColor;

void main() {
	outColor = pc.color;
}
