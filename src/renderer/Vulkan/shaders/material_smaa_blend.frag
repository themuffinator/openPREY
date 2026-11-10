#version 450
#extension GL_GOOGLE_include_directive : require

// Vulkan port of openQ4's live smaa_blend.fs material program.

layout(set = 0, binding = 0) uniform sampler2D ColorTex;
layout(set = 1, binding = 0) uniform sampler2D BlendTex;

layout(set = 6, binding = 0, std140) uniform MaterialShaderParms {
    vec4 shaderParms[16];
} material;

#include "material_image_coords.glsl"

layout(location = 0) in vec2 vTexCoord;
layout(location = 0) out vec4 outColor;

void main() {
    vec2 invTexSize = material.shaderParms[0].xy;
    vec2 texcoord = vTexCoord;

    vec4 a;
    a.x = texture(BlendTex, MaterialImageCoord(texcoord + vec2(invTexSize.x, 0.0), 1u)).a;
    a.y = texture(BlendTex, MaterialImageCoord(texcoord + vec2(0.0, invTexSize.y), 1u)).g;
    a.wz = texture(BlendTex, MaterialImageCoord(texcoord, 1u)).xz;

    if (dot(a, vec4(1.0)) < 0.00001) {
        outColor = texture(ColorTex, MaterialImageCoord(texcoord, 0u));
        return;
    }

    bool horizontal = max(a.x, a.z) > max(a.y, a.w);
    vec4 blendingOffset = vec4(0.0, a.y, 0.0, a.w);
    vec2 blendingWeight = a.yw;
    if (horizontal) {
        blendingOffset = vec4(a.x, 0.0, a.z, 0.0);
        blendingWeight = a.xz;
    }

    blendingWeight /= max(dot(blendingWeight, vec2(1.0)), 0.00001);
    vec4 blendingCoord =
        blendingOffset * vec4(invTexSize, -invTexSize) + texcoord.xyxy;
    vec4 color =
        blendingWeight.x * texture(ColorTex, MaterialImageCoord(blendingCoord.xy, 0u));
    color += blendingWeight.y * texture(ColorTex, MaterialImageCoord(blendingCoord.zw, 0u));
    outColor = color;
}
