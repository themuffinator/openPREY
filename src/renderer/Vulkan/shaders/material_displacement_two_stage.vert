#version 450

// Native Vulkan restoration for the stock material-program name
// glsl/DisplacementTwoStage.glsl.  Quake 4 ships material declarations for
// this family but no corresponding .glslvp/.glslfp files in any base PK4.
// Its interface and behavior therefore extend the shipped Displacement
// program directly with a second independently transformed displacement map.

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec4 inColor;
layout(location = 5) in vec2 inTexCoord;

layout(push_constant) uniform StagePushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    // x: vertex-color mode (0 ignore, 1 modulate, 2 inverse modulate)
    // y: alpha-test mode (-1 less, 0 off, 1 greater, 2 equal)
    // z: alpha-test reference
    vec4 params;
} pc;

layout(location = 0) out vec2 vTexCoord;
layout(location = 1) out vec4 vColor;

vec4 ResolveStageColor() {
    vec4 vertexColor = inColor;
    if (pc.params.x < 0.5) {
        vertexColor = vec4(1.0);
    } else if (pc.params.x > 1.5) {
        vertexColor = vec4(vec3(1.0) - inColor.rgb, inColor.a);
    }
    return vertexColor * pc.stageColor;
}

void main() {
    gl_Position = pc.mvp * vec4(inPosition, 1.0);
    vTexCoord = inTexCoord;
    vColor = ResolveStageColor();
}
