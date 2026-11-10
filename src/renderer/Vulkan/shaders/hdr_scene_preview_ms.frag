// Copyright (C) 2026 DarkMatter Productions
#version 450
layout(set = 0, binding = 0) uniform sampler2DMS scene;
layout(location = 0) out vec4 outColor;
void main() {
    // Average the stored radiance at this exact texel before the destination
    // clamps it. Native resolves may use different weights/precision, which
    // can darken bright silhouettes and change a later SMAA edge decision.
    ivec2 texel = ivec2(gl_FragCoord.xy);
    int count = textureSamples(scene);
    vec4 sum = vec4(0.0);
    for (int sampleIndex = 0; sampleIndex < count; ++sampleIndex) {
        sum += texelFetch(scene, texel, sampleIndex);
    }
    outColor = sum / float(count);
}
