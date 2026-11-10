// Copyright (C) 2026 DarkMatter Productions
#version 450
#extension GL_GOOGLE_include_directive : require
#include "framebuffer_coords.glsl"
layout(push_constant) uniform HDRFixturePush {
    ivec4 params;
    vec4 classicColor;
    vec4 pbrColor;
} pc;
layout(location = 0) out vec4 outColor;
// Author the same top-down test pattern in either attachment layout.
void main() {
    int row = framebufferLowerOrigin ? pc.params.z - 1 - int(gl_FragCoord.y) : int(gl_FragCoord.y);
    gl_SampleMask[0] = int(1u << uint(pc.params.x));
    float pattern = float((int(gl_FragCoord.x) + 2 * row) & 3) / 16.0;
    outColor = pc.classicColor + vec4(vec3(pattern), 0.0);
}
