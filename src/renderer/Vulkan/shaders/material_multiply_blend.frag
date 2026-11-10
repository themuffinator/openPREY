#version 450

// Vulkan port of Quake 4's shipped glprogs/glsl/multiplyblend.glslfp.
//
// Semantic sampler sets:
//   set 0: Image
//
// This family has no authored shaderParm values.

layout(set = 0, binding = 0) uniform sampler2D Image;

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
    // Retail semantics use only primary alpha.  At full decal opacity this
    // emits Image; as the decal fades it approaches neutral 0.5, allowing
    // the material's GL_DST_COLOR,GL_SRC_COLOR blend to disappear cleanly.
    vec4 color =
        texture(Image, vTexCoord) * vColor.a +
        vec4(0.5) * (1.0 - vColor.a);
    if (AlphaTestFails(color.a)) {
        discard;
    }
    outColor = color;
}
