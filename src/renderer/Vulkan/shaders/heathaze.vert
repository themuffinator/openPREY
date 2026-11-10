#version 450

// Native Vulkan port of the vertex program shared by Quake 4's
// heatHaze.vfp and heatHazeWithMask.vfp.
//
// The 128-byte push block deliberately matches the renderer-wide stage ABI.
// Only the MVP is consumed here; program locals and fixed-function matrix
// rows live in the dynamic StageParms slice at set 6.

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec2 inTexCoord;

layout(push_constant) uniform StagePushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    vec4 params;
} pc;

// parms[0] = local[0], texture scroll
// parms[1] = local[1], deform magnitude
// parms[2] = model-view row 2
// parms[3] = projection row 0
// parms[4] = projection row 3
// parms[5] = env[0], current-render non-power-of-two scale
// parms[6] = env[1].xy followed by framebuffer height
layout(set = 6, binding = 0, std140) uniform StageParms {
    vec4 parms[8];
} sp;

layout(location = 0) out vec2 vMaskTexCoord;
layout(location = 1) out vec2 vScrollTexCoord;
layout(location = 2) out vec4 vDeformScale;

void main() {
    gl_Position = pc.mvp * vec4(inPosition, 1.0);

    vMaskTexCoord = inTexCoord;
    vScrollTexCoord = inTexCoord + sp.parms[0].xy;

    // Preserve the retail ARB program's distance-scaled deformation:
    // R0 = (1, 0, eyeZ, 1), R1 = R0 dot projection row 0,
    // R2 = max(R0 dot projection row 3, 1).
    vec4 projectionPosition = vec4(
        1.0,
        0.0,
        dot(vec4(inPosition, 1.0), sp.parms[2]),
        1.0);
    float projectedDistance = dot(projectionPosition, sp.parms[3]);
    float projectedW = max(dot(projectionPosition, sp.parms[4]), 1.0);
    float distanceScale = min(projectedDistance / projectedW, 0.02);
    vDeformScale = vec4(distanceScale) * sp.parms[1];
}
