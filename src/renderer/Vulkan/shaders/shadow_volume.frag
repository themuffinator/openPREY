#version 450

// openQ4 Vulkan stencil shadow volume — fragment stage (Phase G1).
//
// The volume pipeline masks every color write (colorWriteMask 0) and only
// the depth test + stencil ops matter. The r_showShadows visualization
// pipelines share these stages with color writes enabled; they push the
// volume's debug color in pc.b (RB_T_Shadow's glColor3f).

layout(push_constant) uniform ShadowVolumePushConstants {
    mat4 mvp;
    vec4 a;
    vec4 b;    // r_showShadows color
    vec4 c;
    vec4 d;
} pc;

layout(location = 0) out vec4 outColor;

void main() {
    outColor = pc.b;
}
