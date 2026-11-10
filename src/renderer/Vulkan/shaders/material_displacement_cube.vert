#version 450

// Vulkan port of Quake 4's shipped
// glprogs/glsl/displacementcube.glslvp.
//
// This family consumes position, color, normal, and base texcoord from the
// standard full-idDrawVert locations.
//
// Canonical shaderParms slots (the runner packs by case-insensitive name):
//   0 scrollX, 1 scrollY, 2 sizeX, 3 sizeY, 4 texCoordSize,
//   5 EyeVector (xyz).

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec4 inColor;
layout(location = 2) in vec3 inNormal;
layout(location = 5) in vec2 inTexCoord;

layout(set = 6, binding = 0, std140) uniform MaterialShaderParms {
    vec4 shaderParms[16];
} material;

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
layout(location = 1) out vec2 vDisplacementTexCoord;
layout(location = 2) out vec4 vColor;
layout(location = 3) out vec3 vNormal;
layout(location = 4) out vec3 vViewVector;

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

    // Preserve the retail shader's vertex-linear displacement transform.
    vec2 newSize = vec2(
        material.shaderParms[2].x,
        material.shaderParms[3].x) * 0.5 + vec2(1.5);
    vec2 newScroll = vec2(
        material.shaderParms[0].x,
        material.shaderParms[1].x) * 0.2;
    vDisplacementTexCoord =
        (inTexCoord - vec2(0.5)) * newSize + newScroll + vec2(0.5);

    vColor = ResolveStageColor();
    vNormal = inNormal;
    vViewVector = material.shaderParms[5].xyz - inPosition;
}
