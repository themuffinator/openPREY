#version 450

// Restored glsl/Displacement2.glsl CTF flag semantics.  See the vertex
// module for the source-availability note.
//
// Semantic sampler sets:
//   set 0: Image
//   set 1: DisplacementMap
//   set 2: EffectA
//   set 3: EffectB
//   set 4: Mask
//
// Canonical shaderParms slots:
//   0 OffsetScrollSpeed, 1 EffectAScrollSpeed, 2 EffectBScrollSpeed,
//   3 OffsetScale,       4 EffectAScale,       5 EffectBScale,
//   6 BaseFlicker,       7 EffectAFlicker,     8 EffectBFlicker.

layout(set = 0, binding = 0) uniform sampler2D Image;
layout(set = 1, binding = 0) uniform sampler2D DisplacementMap;
layout(set = 2, binding = 0) uniform sampler2D EffectA;
layout(set = 3, binding = 0) uniform sampler2D EffectB;
layout(set = 4, binding = 0) uniform sampler2D Mask;

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
    // The offset layer scrolls vertically and uses the same unsigned
    // displacement convention as Raven's shipped Displacement program.
    vec2 offsetCoord =
        vTexCoord + vec2(0.0, material.shaderParms[0].x);
    vec2 offset = texture(DisplacementMap, offsetCoord).xy
        * material.shaderParms[3].x;
    vec2 displacedCoord = vTexCoord + offset;

    vec4 base =
        texture(Image, displacedCoord) * material.shaderParms[6].x;

    // The non-GLSL fallback authored beside this stage scrolls and scales
    // the two energy layers independently.  Preserve the horizontal flag
    // coordinate while applying those controls to the scrolling axis.
    vec2 effectACoord = vec2(
        displacedCoord.x,
        displacedCoord.y * material.shaderParms[4].x
            + material.shaderParms[1].x);
    vec2 effectBCoord = vec2(
        displacedCoord.x,
        displacedCoord.y * material.shaderParms[5].x
            + material.shaderParms[2].x);
    vec4 effectA =
        texture(EffectA, effectACoord) * material.shaderParms[7].x;
    vec4 effectB =
        texture(EffectB, effectBCoord) * material.shaderParms[8].x;

    // The mask remains in undistorted flag space so the animated layers
    // cannot leak beyond the rect-sprite silhouette.
    float mask = texture(Mask, vTexCoord).r;
    vec4 color = (base + effectA + effectB) * mask * vColor;

    if (AlphaTestFails(color.a)) {
        discard;
    }
    outColor = color;
}
