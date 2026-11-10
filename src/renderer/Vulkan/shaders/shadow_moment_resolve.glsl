// Translucent shadow-moment resolve shared by the projected and point
// receivers: GL ResolveTranslucentShadowMoments (shadow_interaction.fs and
// shadow_point_interaction.fs). The moments hold the total optical depth and
// its first three depth moments; a normal distribution over the stored mean
// and variance estimates the fraction in front of the receiver.
//
// params: x density, y minimum variance, z light-bleed reduction.

float MomentApproxErf(float x) {
    float s = sign(x);
    float ax = abs(x);
    float t = 1.0 / (1.0 + 0.3275911 * ax);
    float y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t
        - 0.284496736) * t + 0.254829592) * t * exp(-ax * ax);
    return s * y;
}

float MomentNormalCdf(float x) {
    return 0.5 * (1.0 + MomentApproxErf(x * 0.70710678));
}

float ResolveTranslucentShadowMoments(vec4 moments, float depth, vec4 params) {
    float totalTau = max(moments.x, 0.0);
    if (totalTau <= 1.0e-4) {
        return 1.0;
    }

    float mean = moments.y / totalTau;
    float variance = max(moments.z / totalTau - mean * mean, max(params.y, 1.0e-6));
    float sigma = sqrt(variance);
    float fraction = clamp(MomentNormalCdf((depth - mean) / sigma), 0.0, 1.0);
    float bleed = clamp(params.z, 0.0, 0.95);
    fraction = clamp((fraction - bleed) / max(1.0 - bleed, 1.0e-4), 0.0, 1.0);
    float tau = totalTau * fraction;
    return exp(-min(tau * max(params.x, 0.0), 16.0));
}
