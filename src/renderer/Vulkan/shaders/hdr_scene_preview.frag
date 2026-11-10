// Copyright (C) 2026 DarkMatter Productions
#version 450
layout(set = 0, binding = 0) uniform sampler2D scene;
layout(location = 0) out vec4 outColor;
void main() {
    // The float scene is already resolved. Broadcast it to every destination
    // sample so an LDR target clamps after, rather than before, MSAA resolve.
    outColor = texelFetch(scene, ivec2(gl_FragCoord.xy), 0);
}
