#version 450

// Vulkan port of Quake 4's shipped
// glprogs/glsl/displacementcube.glslfp.
//
// Semantic sampler sets:
//   set 0: Image
//   set 1: DisplacementMap
//   set 2: CubeImage
//
// Canonical shaderParms slots:
//   0 scrollX, 1 scrollY, 2 sizeX, 3 sizeY, 4 texCoordSize,
//   5 EyeVector (xyz).

layout(set = 0, binding = 0) uniform sampler2D Image;
layout(set = 1, binding = 0) uniform sampler2D DisplacementMap;
layout(set = 2, binding = 0) uniform samplerCube CubeImage;

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
layout(location = 1) in vec2 vDisplacementTexCoord;
layout(location = 2) in vec4 vColor;
layout(location = 3) in vec3 vNormal;
layout(location = 4) in vec3 vViewVector;

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
    vec2 offset = texture(DisplacementMap, vDisplacementTexCoord).xy
        * material.shaderParms[4].x;

    // Keep Raven's original object-space reflection and its intentionally
    // unnormalised view vector.  Cubemap lookup normalises direction
    // implicitly, while the large displacement term perturbs that direction.
    vec3 normal = normalize(vNormal);
    vec3 reflectionVector = reflect(-vViewVector, normal);
    vec3 cubeOffset =
        vec3(offset.x + offset.y, offset.x, offset.y) * 128.0;
    vec4 reflected = texture(CubeImage, reflectionVector + cubeOffset);
    vec4 straight = texture(Image, vTexCoord + offset);

    vec4 color = vec4(reflected.rgb + straight.rgb, 1.0) * vColor;
    if (AlphaTestFails(color.a)) {
        discard;
    }
    outColor = color;
}
