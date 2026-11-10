#version 450

// Compatible Vulkan implementation of Quake 4's missing glsl/Blur.glsl
// fragment program.
//
// Semantic sampler sets:
//   set 0: Image
//
// Canonical shaderParms slots:
//   0 textureScale (xy)
//   1 sampleDist

layout(set = 0, binding = 0) uniform sampler2D Image;

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
    vec2 uv = vTexCoord * material.shaderParms[0].xy;
    vec2 offset = vec2(material.shaderParms[1].x);

    // Preserve the established rvspecial kernel and weights.
    vec4 color = texture(Image, uv) * 0.227027;
    color += texture(Image, uv + vec2(offset.x, 0.0)) * 0.1945946;
    color += texture(Image, uv - vec2(offset.x, 0.0)) * 0.1945946;
    color += texture(Image, uv + vec2(0.0, offset.y)) * 0.1945946;
    color += texture(Image, uv - vec2(0.0, offset.y)) * 0.1945946;
    color += texture(Image, uv + offset) * 0.0945946;
    color += texture(Image, uv - offset) * 0.0945946;
    color.a = 1.0;

    if (AlphaTestFails(color.a)) {
        discard;
    }
    outColor = color;
}
