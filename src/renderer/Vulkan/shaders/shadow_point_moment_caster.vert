#version 450
#extension GL_GOOGLE_include_directive : require

// openQ4 Vulkan translucent shadow-moment caster for point lights — vertex
// stage, mirroring GL shadow_point_translucent_caster.vs. Each cube face is a
// tile of the moment atlas, drawn with the same face view, analytic
// projection and positive-height viewport as the depth cube face
// (shadow_point_caster.vert), so a face tile's texels line up with the cube
// face's. The moment depth is the normalized radial distance.

#include "shadow_moment_stage.glsl"

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec2 inTexCoord;
layout(location = 2) in vec4 inColor;

layout(push_constant) uniform MomentCasterPushConstants {
    mat4 mvp;        // model -> cube-face view space
    vec4 depthRow;   // x: zA, y: zB, z: far envelope, w: cube face
} pc;

layout(location = 0) out vec2 vAlphaTexCoord;
layout(location = 1) out vec2 vCoverageTexCoord;
layout(location = 2) out vec3 vVertexColorRgb;
layout(location = 3) out float vVertexAlpha;
layout(location = 4) out float vCoverageVertexAlpha;
layout(location = 5) out vec3 vPointShadowVector;

void main() {
    vec4 position = vec4(inPosition, 1.0);
    vec4 texCoord = vec4(inTexCoord, 0.0, 1.0);
    vAlphaTexCoord = vec2(dot(texCoord, stage.alphaS), dot(texCoord, stage.alphaT));
    vCoverageTexCoord = vec2(dot(texCoord, stage.coverageS), dot(texCoord, stage.coverageT));
    vVertexColorRgb = inColor.rgb;
    vVertexAlpha = clamp(inColor.a * stage.vertexAlpha.x + stage.vertexAlpha.y, 0.0, 1.0);
    vCoverageVertexAlpha = clamp(inColor.a * stage.vertexAlpha.z + stage.vertexAlpha.w, 0.0, 1.0);
    vec4 viewPos = pc.mvp * position;
    // World-axis order, exactly as shadow_point_caster.vert recovers it.
    int face = int(pc.depthRow.w);
    if (face == 0) vPointShadowVector = vec3(-viewPos.z, -viewPos.y, -viewPos.x);
    else if (face == 1) vPointShadowVector = vec3(viewPos.z, -viewPos.y, viewPos.x);
    else if (face == 2) vPointShadowVector = vec3(viewPos.x, -viewPos.z, viewPos.y);
    else if (face == 3) vPointShadowVector = vec3(viewPos.x, viewPos.z, -viewPos.y);
    else if (face == 4) vPointShadowVector = vec3(viewPos.x, -viewPos.y, -viewPos.z);
    else vPointShadowVector = vec3(-viewPos.x, -viewPos.y, viewPos.z);
    gl_Position = vec4(viewPos.xy, pc.depthRow.x * viewPos.z + pc.depthRow.y * viewPos.w, -viewPos.z);
}
