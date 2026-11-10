#version 450

// Native Vulkan port of Quake 4's shipped arbFP_glasswarp.txt stage.
//
// The retail program writes the texture-unit 1 lookup to result.color before
// executing an abandoned color-mixing tail.  Preserve that visible result:
// unit 0 supplies the distortion, unit 1 (_scratch2) supplies the output, and
// unit 2 (_scratch) participates only in the intentionally dead tail below.

layout(set = 0, binding = 0) uniform sampler2D warpMap;
layout(set = 1, binding = 0) uniform sampler2D scratchImage2;
layout(set = 2, binding = 0) uniform sampler2D scratchImage;

layout(push_constant) uniform StagePushConstants {
    mat4 mvp;
    vec4 stageColor;
    vec4 texMatrixS;
    vec4 texMatrixT;
    // y: alpha-test mode (-1 less, 0 off, 1 greater, 2 equal)
    // z: alpha-test reference
    vec4 params;
} pc;

layout(location = 0) in vec2 vWarpTexCoord;
layout(location = 1) in vec3 vClipCoord;

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
    vec2 warpTexCoord = (vWarpTexCoord - vec2(0.5)) * 2.0;
    vec4 warp = texture(warpMap, warpTexCoord);
    vec2 preturb = vec2(1.0) - 0.2 * warp.rg;

    // Quake 4's glass-warp stage feeds the raw MVP X/Y/W object planes and
    // divides by W here. Unlike TG_SCREEN, the shipped ARB program does not
    // perform an NDC-to-[0,1] remap before perturbing around 0.5.
    vec2 screenTexCoord = vClipCoord.xy / vClipCoord.z;
    screenTexCoord =
        (screenTexCoord - vec2(0.5)) * preturb + vec2(0.5);

    vec4 color = texture(scratchImage2, screenTexCoord);
    if (AlphaTestFails(color.a)) {
        discard;
    }
    outColor = color;

    // This is the shipped program's deliberately abandoned tail.  Its final
    // result.color write is commented out in the asset, so an optimizing
    // compiler may remove all of this work while retaining the exact output
    // above.
    vec4 color2 = texture(scratchImage, screenTexCoord) * vec4(0.1, 0.1, 0.1, 1.0);
    vec4 greyScale = color.xxxx * vec4(0.6, 0.6, 1.0, 1.0);
    vec4 temp = greyScale * warp.x;
    vec4 mixedColor = color * (1.0 - warp.x) + temp + color2;
}
