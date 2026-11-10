// Copyright (C) 2026 DarkMatter Productions
#version 450
layout(location = 0) out vec4 outColor;
void main() {
	// Every column has a known number of populated samples, including zero
	// and full coverage. No geometry edge or sample-shading feature is needed.
	gl_SampleMask[0] = (1 << int(gl_FragCoord.x)) - 1;
	outColor = vec4(30.0, 200.0, 255.0, 73.0) / 255.0;
}
