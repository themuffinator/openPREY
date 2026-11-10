#version 450

// openQ4 Vulkan fog light — fragment stage (Phase G2).
//
// The RB_FogPass fixed-function modulate chain (draw_common.cpp:7670-7715):
// primary color (the light's stage-0 fog color, alpha pinned 1 by
// glColor3fv) × _fog (GL_MODULATE) × _fogEnter (GL_MODULATE). Both
// intrinsic images are RGBA with white RGB and the fog fraction in alpha
// (Image_intrinsic.cpp:268-270, 376-379), so the product lands
// vec4(fogColor.rgb, texFog.a * texEnter.a) under the pass's fixed
// SRC_ALPHA / ONE_MINUS_SRC_ALPHA blend.

layout(set = 0, binding = 0) uniform sampler2D fogMap;        // _fog
layout(set = 1, binding = 0) uniform sampler2D fogEnterMap;   // _fogEnter

layout(push_constant) uniform FogPushConstants {
    mat4 mvp;
    vec4 a;
    vec4 b;
    vec4 c;
    vec4 d;    // fog color
} pc;

layout(location = 0) in vec2 vFogTexCoord;
layout(location = 1) in vec2 vEnterTexCoord;

layout(location = 0) out vec4 outColor;

void main() {
    outColor = vec4(pc.d.rgb, 1.0) * texture(fogMap, vFogTexCoord) * texture(fogEnterMap, vEnterTexCoord);
}
