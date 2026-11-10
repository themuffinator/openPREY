#version 450
#extension GL_GOOGLE_include_directive : require
#include "framebuffer_coords.glsl"

// Vulkan port of Quake 4's shipped
// glprogs/glsl/sniperstretch2.glslfp.
//
// Semantic sampler sets:
//   set 0: BackgroundImage
//   set 1: Scope
//
// Canonical shaderParms slots:
//   0 textureScale (xy)
//   1 textureHalfScale (xy)
//   2 backgroundColor (rgba)
//   12 framebuffer height (x, renderer built-in)
//   13 viewport origin in GL window coordinates (xy, renderer built-in)
//   14 viewport size (xy, renderer built-in)
//   15 current-render texture scale (xy, renderer built-in)

layout(set = 0, binding = 0) uniform sampler2D BackgroundImage;
layout(set = 1, binding = 0) uniform sampler2D Scope;

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
layout(location = 1) in vec2 vScopeTexCoord;

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

bool HasViewportBuiltins() {
    return material.shaderParms[12].x > 0.0
        && all(greaterThan(material.shaderParms[14].xy, vec2(0.0)))
        && all(greaterThan(material.shaderParms[15].xy, vec2(0.0)));
}

vec2 CurrentRenderCoord(out vec2 halfTextureScale) {
    if (!HasViewportBuiltins()) {
        halfTextureScale = material.shaderParms[1].xy;
        return vTexCoord;
    }

    float framebufferHeight = material.shaderParms[12].x;
    vec2 viewportOrigin = material.shaderParms[13].xy;
    vec2 viewportSize = max(material.shaderParms[14].xy, vec2(1.0));
    vec2 currentRenderScale = material.shaderParms[15].xy;

    // Vulkan fragment coordinates are upper-left oriented.  Convert to the
    // bottom-left GL window space used by the retail program and by the
    // current-render capture, then localize the coordinate to this viewport.
    vec2 windowGL = vec2(gl_FragCoord.x, CanonicalWindowY(framebufferHeight));
    vec2 viewportCoord = (windowGL - viewportOrigin) / viewportSize;
    halfTextureScale = currentRenderScale * 0.5;
    return clamp(viewportCoord * currentRenderScale, vec2(0.0), currentRenderScale);
}

void main() {
    vec4 scopeArea = texture(Scope, vScopeTexCoord);

    vec2 halfTextureScale;
    vec2 start = CurrentRenderCoord(halfTextureScale);
    vec2 blurDir = start - halfTextureScale;
    float blurDirLength = length(blurDir);
    if (blurDirLength > 0.0) {
        blurDir /= blurDirLength;
    } else {
        blurDir = vec2(0.0);
    }

    vec4 sceneColor = texture(BackgroundImage, start);
    vec4 color;
    if (scopeArea.r == 0.0) {
        color = sceneColor;
    } else {
        // Preserve the retail six-tap radial offsets and weighting outside
        // the feathered aperture rim.
        float len = scopeArea.r;
        vec2 amount = blurDir * len * 0.25;
        vec4 blurColor =
            texture(BackgroundImage, start - amount * 1.5)
            + texture(BackgroundImage, start - amount * 1.4)
            + texture(BackgroundImage, start - amount * 1.3)
            + texture(BackgroundImage, start - amount * 1.2)
            + texture(BackgroundImage, start - amount * 1.1)
            + texture(BackgroundImage, start - amount * 1.0);
        blurColor /= 6.0;
        color = (blurColor + material.shaderParms[2]) * 0.5;
    }

    // Match the GL shader: compressed mask noise must not switch on the
    // half-strength tint abruptly along a staircase of texture blocks.
    float blurCoverage = smoothstep(0.0, 8.0 / 255.0, scopeArea.r);
    color = mix(sceneColor, color, blurCoverage);

    if (AlphaTestFails(color.a)) {
        discard;
    }
    outColor = color;
}
