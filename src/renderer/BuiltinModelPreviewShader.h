// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once

// Render-world lighting does not supply coverage alpha. Resolve opaque model
// coverage from depth and retain alpha supplied by translucent/effect stages.
// These internal sources ship in the renderer; no override PK4 is required.
inline constexpr const char* RetainedModelVertexSource = R"GLSL(
varying vec2 modelTexCoord;
void main(void) {
    modelTexCoord = gl_MultiTexCoord0.xy;
    gl_Position = ftransform();
}
)GLSL";
inline constexpr const char* RetainedModelFragmentSource = R"GLSL(
uniform sampler2D Colour;
uniform sampler2D Depth;
varying vec2 modelTexCoord;
void main(void) {
    vec4 colour = texture2D(Colour, modelTexCoord);
    float coverage = texture2D(Depth, modelTexCoord).r < 1.0 ? 1.0 : 0.0;
    gl_FragColor = vec4(colour.rgb, max(coverage, clamp(colour.a, 0.0, 1.0)));
}
)GLSL";
