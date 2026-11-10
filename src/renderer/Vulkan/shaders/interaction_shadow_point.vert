#version 450
#extension GL_GOOGLE_include_directive : require
#include "pbr_vertex.glsl"
#include "point_shadow_math.glsl"

// openQ4 Vulkan point-shadow-receiving interaction — vertex stage (Phase
// F2b, docs/dev/archive/2026-10-18/plans/2026-07-19-vulkan-phase-f.md).
//
// interaction.vert plus the point-light cube shadow vector of the GL
// shadow_point_interaction.vs contract: worldPos comes from the model
// matrix rows, the shadow vector is worldPos - globalLightOrigin, and
// normal-offset shadows push the sampled point along the world-space
// geometric normal by (per-distance texel factor × distance × sinθ) before
// the cube lookup, fixing self-shadow acne structurally where pure depth
// bias would detach contact shadows.

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec4 inColor;
layout(location = 2) in vec3 inNormal;
layout(location = 3) in vec3 inTangent0;
layout(location = 4) in vec3 inTangent1;
layout(location = 5) in vec2 inTexCoord;

layout(push_constant) uniform InteractionPushConstants {
    mat4 mvp;
    vec4 a;
    vec4 b;
    vec4 c;
    vec4 d;
} pc;

layout(set = 6, binding = 0, std140) uniform InteractionBlock {
    vec4 localLightOrigin;
    vec4 localViewOrigin;
    vec4 lightProjectionS;
    vec4 lightProjectionT;
    vec4 lightProjectionQ;
    vec4 lightFalloffS;
    vec4 bumpMatrixS;
    vec4 bumpMatrixT;
    vec4 diffuseMatrixS;
    vec4 diffuseMatrixT;
    vec4 specularMatrixS;
    vec4 specularMatrixT;
    vec4 diffuseColor;
    vec4 specularColor;
    vec4 flatDiffuseParams;
    // cel banding (RB_SetCelInteractionUniform): x enabled, y band count,
    // z hard specular, w softness; zero when the surface is not banded
    vec4 celParams;
} inter;

layout(set = 7, binding = 1, std140) uniform ShadowBlock {
    vec4 modelRow0;      // model -> world matrix rows
    vec4 modelRow1;
    vec4 modelRow2;
    vec4 lightOriginFar; // xyz: world-space light origin, w: far envelope
    vec4 biasParams;     // x: constant bias, y: normal bias, z: texel depth bias, w: per-distance normal-offset factor
    vec4 filterParams;   // x: radius, y: taps, z: mode, w: cube texel scale
    vec4 samplingParams; // x: hardware compare enabled
} shadow;

layout(location = 0) out vec2 vBumpTexCoord;
layout(location = 1) out vec2 vDiffuseTexCoord;
layout(location = 2) out vec2 vSpecularTexCoord;
layout(location = 3) out vec4 vLightFalloffTexCoord;
layout(location = 4) out vec4 vLightProjectionTexCoord;
layout(location = 5) out vec3 vLightVector;
layout(location = 6) out vec3 vHalfAngleVector;
layout(location = 7) out vec3 vVertexColor;
layout(location = 8) out vec3 vPointShadowVector;
layout(location = 9) out float vShadowLightCos;
layout(location = 10) out vec3 vViewVector;

// Pack the basis into unused components so the projected receiver remains
// within Vulkan's minimum 16 varying locations (0..15).
layout(location = 12, component = 1) out vec3 vPBRTangent0;
layout(location = 14, component = 1) out vec3 vPBRTangent1;
layout(location = 15) out vec3 vPBRNormal;

vec3 TangentSpaceVector(vec3 objectVector) {
    return vec3(
        dot(inTangent0, objectVector),
        dot(inTangent1, objectVector),
        dot(inNormal, objectVector));
}

void main() {
    vec4 position = vec4(inPosition, 1.0);
    vec4 texCoord = vec4(inTexCoord, 0.0, 1.0);

    vec3 toLight = inter.localLightOrigin.xyz - position.xyz;
    vec3 toView = inter.localViewOrigin.xyz - position.xyz;

    vLightVector = pc.d.x > 0.5 ? toLight : TangentSpaceVector(toLight);
    vHalfAngleVector = TangentSpaceVector(normalize(toLight) + normalize(toView));
    // PBR dot products use the interpolated object-space material normal.
    vViewVector = pc.d.x > 0.5 ? toView : TangentSpaceVector(toView);
    vPBRTangent0 = inTangent0;
    vPBRTangent1 = inTangent1;
    vPBRNormal = inNormal;
    if (pc.d.x > 0.5) {
        PBRVertexFrame(inNormal, inTangent0, inTangent1, vPBRNormal, vPBRTangent0, vPBRTangent1);
    }

    vBumpTexCoord = vec2(dot(texCoord, inter.bumpMatrixS), dot(texCoord, inter.bumpMatrixT));
    vDiffuseTexCoord = vec2(dot(texCoord, inter.diffuseMatrixS), dot(texCoord, inter.diffuseMatrixT));
    vSpecularTexCoord = vec2(dot(texCoord, inter.specularMatrixS), dot(texCoord, inter.specularMatrixT));

    // z is unused by textureProj for this 2D sampler; carry model-local Z.
    vLightFalloffTexCoord = vec4(dot(position, inter.lightFalloffS), 0.5, position.z, 1.0);
    vLightProjectionTexCoord = vec4(
        dot(position, inter.lightProjectionS),
        dot(position, inter.lightProjectionT),
        0.0,
        dot(position, inter.lightProjectionQ));

    vec3 worldPos = vec3(
        dot(position, shadow.modelRow0),
        dot(position, shadow.modelRow1),
        dot(position, shadow.modelRow2));
    vec3 pointShadowVector = worldPos - shadow.lightOriginFar.xyz;
    vec3 worldNormal = normalize(vec3(
        dot(vec4(inNormal, 0.0), shadow.modelRow0),
        dot(vec4(inNormal, 0.0), shadow.modelRow1),
        dot(vec4(inNormal, 0.0), shadow.modelRow2)));
    float shadowLightCos = max(dot(normalize(inNormal), normalize(toLight)), 0.0);
    float shadowSinTheta = sqrt(max(1.0 - shadowLightCos * shadowLightCos, 0.0));
    float normalOffset = shadow.biasParams.w * PointShadowRadialLength(pointShadowVector) * shadowSinTheta;
    vPointShadowVector = pointShadowVector + worldNormal * normalOffset;
    vShadowLightCos = shadowLightCos;

    vVertexColor = inColor.rgb * pc.a.x + vec3(pc.a.y);

    gl_Position = pc.mvp * position;
}
