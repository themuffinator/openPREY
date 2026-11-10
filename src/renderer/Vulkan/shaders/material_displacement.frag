#version 450

// Vulkan port of Quake 4's shipped glprogs/glsl/displacement.glslfp.
//
// Semantic sampler sets:
//   set 0: Image
//   set 1: DisplacementMap
//
// Canonical shaderParms slots (the runner packs by case-insensitive name):
//   0 scrollX, 1 scrollY, 2 sizeX, 3 sizeY, 4 texCoordSize.

layout(set = 0, binding = 0) uniform sampler2D Image;
layout(set = 1, binding = 0) uniform sampler2D DisplacementMap;

layout(set = 6, binding = 0, std140) uniform MaterialShaderParms {
    vec4 shaderParms[16];
} material;

layout(push_constant) uniform StagePushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    vec4 params;
} pc;

layout(location = 0) in vec2 vTexCoord;
layout(location = 1) in vec4 vColor;

layout(location = 0) out vec4 outColor;

bool AlphaTestFails(float alpha) {
    if (pc.params.y > 1.5) {
        return abs(alpha - pc.params.z) > (0.5 / 255.0);
    }
    if (pc.params.y > 0.5) {
        return alpha <= pc.params.z;
    }
    if (pc.params.y < -0.5) {
        return alpha >= pc.params.z;
    }
    return false;
}

void main() {
    vec2 newSize = vec2(
        material.shaderParms[2].x,
        material.shaderParms[3].x) * 0.5 + vec2(1.5);
    vec2 newScroll = vec2(
        material.shaderParms[0].x,
        material.shaderParms[1].x) * 0.2;

    vec2 displacementCoord =
        (vTexCoord - vec2(0.5)) * newSize + newScroll + vec2(0.5);
    vec2 offset = texture(DisplacementMap, displacementCoord).xy
        * material.shaderParms[4].x;

    // The retail shader deliberately treats the displacement map as
    // unsigned data; do not remap it from [0,1] to [-1,1].
    vec4 color = texture(Image, vTexCoord + offset) * vColor;
    if (AlphaTestFails(color.a)) {
        discard;
    }
    outColor = color;
}
