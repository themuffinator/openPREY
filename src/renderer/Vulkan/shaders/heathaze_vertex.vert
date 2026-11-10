#version 450

// Vertex-color heat-haze variant used by heatHazeWithMaskAndVertex.vfp.
// Locations 0 and 1 retain the compact position/ST input contract of
// heathaze.vert; location 2 adds idDrawVert::color for this variant only.

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec2 inTexCoord;
layout(location = 2) in vec4 inColor;

layout(push_constant) uniform StagePushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    vec4 params;
} pc;

layout(set = 6, binding = 0, std140) uniform StageParms {
    vec4 parms[8];
} sp;

layout(location = 0) out vec2 vMaskTexCoord;
layout(location = 1) out vec2 vScrollTexCoord;
layout(location = 2) out vec4 vDeformScale;
layout(location = 3) out vec4 vVertexColor;

void main() {
    gl_Position = pc.mvp * vec4(inPosition, 1.0);

    vMaskTexCoord = inTexCoord;
    vScrollTexCoord = inTexCoord + sp.parms[0].xy;

    vec4 projectionPosition = vec4(
        1.0,
        0.0,
        dot(vec4(inPosition, 1.0), sp.parms[2]),
        1.0);
    float projectedDistance = dot(projectionPosition, sp.parms[3]);
    float projectedW = max(dot(projectionPosition, sp.parms[4]), 1.0);
    float distanceScale = min(projectedDistance / projectedW, 0.02);
    vDeformScale = vec4(distanceScale) * sp.parms[1];

    // The retail ARB variant copies primary color without stage-color
    // modulation and multiplies its XY components into the mask.
    vVertexColor = inColor;
}
