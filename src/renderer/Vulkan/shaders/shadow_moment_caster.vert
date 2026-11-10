#version 450
#extension GL_GOOGLE_include_directive : require

// openQ4 Vulkan translucent shadow-moment caster for projected lights —
// vertex stage, mirroring GL shadow_proj_translucent_caster.vs. It draws
// into the moment atlas tile that mirrors the light's depth-atlas block:
// gl_Position comes from the cascade's light clip matrix over the model
// matrix (with the Vulkan clip-z fixup) and the moment depth is the same
// model-local shadow depth plane the opaque caster stores.

#include "shadow_moment_stage.glsl"

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec2 inTexCoord;
layout(location = 2) in vec4 inColor;

layout(push_constant) uniform MomentCasterPushConstants {
    mat4 mvp;
    vec4 depthRow;   // model-local shadow depth plane (clip plane 2)
} pc;

layout(location = 0) out vec2 vAlphaTexCoord;
layout(location = 1) out vec2 vCoverageTexCoord;
layout(location = 2) out vec3 vVertexColorRgb;
layout(location = 3) out float vVertexAlpha;
layout(location = 4) out float vCoverageVertexAlpha;
layout(location = 5) out float vShadowDepth;

void main() {
    vec4 position = vec4(inPosition, 1.0);
    vec4 texCoord = vec4(inTexCoord, 0.0, 1.0);
    vAlphaTexCoord = vec2(dot(texCoord, stage.alphaS), dot(texCoord, stage.alphaT));
    vCoverageTexCoord = vec2(dot(texCoord, stage.coverageS), dot(texCoord, stage.coverageT));
    vVertexColorRgb = inColor.rgb;
    vVertexAlpha = clamp(inColor.a * stage.vertexAlpha.x + stage.vertexAlpha.y, 0.0, 1.0);
    vCoverageVertexAlpha = clamp(inColor.a * stage.vertexAlpha.z + stage.vertexAlpha.w, 0.0, 1.0);
    vShadowDepth = dot(position, pc.depthRow);
    gl_Position = pc.mvp * position;
}
