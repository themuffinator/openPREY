// Copyright (C) 2026 DarkMatter Productions
#version 450
layout(set = 0, binding = 0) uniform sampler2DMS sourceImage;
layout(location = 0) out vec4 outColor;
void main() {
    // Average stored color without filtering or changing the image's row order.
    // Native normalized resolves can round intermediate values differently.
    ivec2 texel = ivec2(gl_FragCoord.xy);
    int count = textureSamples(sourceImage);
    vec4 sum = vec4(0.0);
    for (int sampleIndex = 0; sampleIndex < count; ++sampleIndex) {
        sum += texelFetch(sourceImage, texel, sampleIndex);
    }
    outColor = sum / float(count);
}
