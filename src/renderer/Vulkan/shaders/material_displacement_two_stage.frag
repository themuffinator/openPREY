#version 450

// Restored glsl/DisplacementTwoStage.glsl semantics.  See the vertex module
// for the source-availability note.
//
// Semantic sampler sets:
//   set 0: Image
//   set 1: DisplacementMap
//   set 2: DisplacementMap2
//
// Canonical shaderParms slots:
//   0 scrollX,  1 scrollY,  2 sizeX,  3 sizeY,  4 texCoordSize,
//   5 scrollX2, 6 scrollY2, 7 sizeX2, 8 sizeY2, 9 texCoordSize2.

layout(set = 0, binding = 0) uniform sampler2D Image;
layout(set = 1, binding = 0) uniform sampler2D DisplacementMap;
layout(set = 2, binding = 0) uniform sampler2D DisplacementMap2;

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

vec2 TransformDisplacementCoord(
    vec2 texCoord,
    float scrollX,
    float scrollY,
    float sizeX,
    float sizeY) {
    vec2 newSize = vec2(sizeX, sizeY) * 0.5 + vec2(1.5);
    vec2 newScroll = vec2(scrollX, scrollY) * 0.2;
    return (texCoord - vec2(0.5)) * newSize + newScroll + vec2(0.5);
}

void main() {
    vec2 firstCoord = TransformDisplacementCoord(
        vTexCoord,
        material.shaderParms[0].x,
        material.shaderParms[1].x,
        material.shaderParms[2].x,
        material.shaderParms[3].x);
    vec2 secondCoord = TransformDisplacementCoord(
        vTexCoord,
        material.shaderParms[5].x,
        material.shaderParms[6].x,
        material.shaderParms[7].x,
        material.shaderParms[8].x);

    // Match the shipped one-stage family by keeping both maps unsigned.
    // Each layer owns its authored amplitude before the offsets are summed.
    vec2 offset =
        texture(DisplacementMap, firstCoord).xy
            * material.shaderParms[4].x +
        texture(DisplacementMap2, secondCoord).xy
            * material.shaderParms[9].x;

    vec4 color = texture(Image, vTexCoord + offset) * vColor;
    if (AlphaTestFails(color.a)) {
        discard;
    }
    outColor = color;
}
