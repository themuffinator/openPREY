#version 450

// Debug tool geometry with a bound image (testImage, testVideo, r_testGamma),
// modulated by the vertex colour like GL_MODULATE.

layout(set = 0, binding = 0) uniform sampler2D debugImage;

layout(location = 0) in vec4 fragColor;
layout(location = 1) in vec2 fragTexCoord;
layout(location = 0) out vec4 outColor;

void main() {
	outColor = texture( debugImage, fragTexCoord ) * fragColor;
}
