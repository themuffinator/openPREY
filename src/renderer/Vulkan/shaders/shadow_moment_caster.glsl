// Translucent shadow-moment accumulation shared by the projected and point
// caster fragment stages: GL shadow_proj_translucent_caster.fs and
// shadow_point_translucent_caster.fs. Every caster stage adds its optical
// depth tau and tau*d, tau*d^2, tau*d^3 per color channel with ONE/ONE
// blending; the receivers estimate how much of that depth lies in front of
// them (shadow_moment_resolve.glsl).

layout(set = 0, binding = 0) uniform sampler2D alphaMap;
layout(set = 1, binding = 0) uniform sampler2D coverageMap;

layout(location = 0) in vec2 vAlphaTexCoord;
layout(location = 1) in vec2 vCoverageTexCoord;
layout(location = 2) in vec3 vVertexColorRgb;
layout(location = 3) in float vVertexAlpha;
layout(location = 4) in float vCoverageVertexAlpha;

layout(location = 0) out vec4 outMomentR;
layout(location = 1) out vec4 outMomentG;
layout(location = 2) out vec4 outMomentB;

float OpticalDepth(float alpha) {
    return -log(max(1.0 - clamp(alpha, 0.0, 0.999), 1.0e-4));
}

vec3 VertexColorRgb(float mode) {
    if (mode > 1.5) {
        return 1.0 - vVertexColorRgb;
    }
    if (mode > 0.5) {
        return vVertexColorRgb;
    }
    return vec3(1.0);
}

bool CoverageAlphaTestPass(float alpha) {
    if (stage.coverageTest.y < -0.5) {
        return alpha < stage.coverageTest.x;
    }
    if (abs(stage.coverageTest.y) <= 0.5) {
        return abs(alpha - stage.coverageTest.x) <= (0.5 / 255.0);
    }
    return alpha > stage.coverageTest.x;
}

// Both textures are fetched before any discard, so implicit-LOD derivatives
// see the complete quad; the GL source fetches between its discards, which
// gives the same results. The branches only test uniform modes.
void WriteTranslucentMoments(float depth, bool outsideDepthRange) {
    vec4 coverageSample = stage.modes.z >= 0.5
        ? texture(coverageMap, vCoverageTexCoord) : vec4(1.0);
    vec4 alphaSample = stage.modes.x <= 1.5
        ? texture(alphaMap, vAlphaTexCoord) : vec4(1.0);
    if (outsideDepthRange) {
        discard;
    }

    float coverage = 1.0;
    if (stage.modes.z >= 0.5) {
        vec3 coverageTint = clamp(coverageSample.rgb * stage.coverageStageColor.rgb
            * VertexColorRgb(stage.modes.w), 0.0, 1.0);
        float coverageAlpha = coverageSample.a * stage.coverageStageColor.a
            * vCoverageVertexAlpha;
        if (stage.coverageTest.z > 0.5 && !CoverageAlphaTestPass(coverageAlpha)) {
            discard;
        }
        if (stage.modes.z > 1.5) {
            coverageAlpha = max(coverageAlpha,
                dot(coverageTint, vec3(0.2126, 0.7152, 0.0722)) * vCoverageVertexAlpha);
        }
        coverage = clamp(coverageAlpha, 0.0, 1.0);
    }

    // Opacity source 2 (cube-map additive) derives absorption from the stage
    // color alone; the others filter it through the stage texture.
    vec3 transmission = stage.modes.x > 1.5
        ? clamp(stage.stageColor.rgb * VertexColorRgb(stage.modes.y), 0.0, 1.0)
        : clamp(alphaSample.rgb * stage.stageColor.rgb * VertexColorRgb(stage.modes.y), 0.0, 1.0);
    vec3 absorption = clamp((1.0 - transmission) * coverage * vVertexAlpha, 0.0, 0.999);
    float maxAbsorption = max(absorption.r, max(absorption.g, absorption.b));
    if (maxAbsorption <= stage.coverageTest.w) {
        discard;
    }

    vec3 tau = vec3(OpticalDepth(absorption.r), OpticalDepth(absorption.g),
        OpticalDepth(absorption.b));
    float d = clamp(depth, 0.0, 1.0);
    float d2 = d * d;
    outMomentR = vec4(tau.r, tau.r * d, tau.r * d2, tau.r * d2 * d);
    outMomentG = vec4(tau.g, tau.g * d, tau.g * d2, tau.g * d2 * d);
    outMomentB = vec4(tau.b, tau.b * d, tau.b * d2, tau.b * d2 * d);
}
