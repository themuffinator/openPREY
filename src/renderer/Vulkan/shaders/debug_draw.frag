#version 450

// Debug tool geometry: the vertex colour, as fixed-function GL draws it with
// no texture bound.

layout(location = 0) in vec4 fragColor;
layout(location = 1) in vec2 fragTexCoord;
layout(location = 0) out vec4 outColor;

void main() {
	outColor = fragColor;
}
