// Copyright (C) 2026 DarkMatter Productions
#version 450
layout(push_constant) uniform Test { vec4 params; } test;
layout(location = 0) out vec4 colors[2];
void main() {
	for (int i = 0; i < 2; ++i) {
		uint bits = uint(test.params.x) + uint(i);
		colors[i] = vec4(float(bits & 1u) * 2.0,
			float((bits >> 1u) & 1u) * 2.0, float((bits >> 2u) & 1u) * 2.0, 1.0);
	}
}
