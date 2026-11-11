// Retail Prey's stock specular model for the classic interaction shaders, the
// Vulkan side of R_InteractionSpecularParms (tr_local.h). A stock classic
// draw (neither r_enhancedMaterials nor native PBR) pushes:
//   pc.d.y = the specular stage's specularExp exponent (retail default 22)
//   pc.d.z = its specularExp brightness (retail default 1.4)
//   pc.d.w = flags: 1 r_correctspecular, 2 r_normalizebumpmap
// Include after SafeNormalize, enhanced_material.glsl and the
// specularTableMap binding.

int StockSpecularFlags() {
    return int(pc.d.w + 0.5);
}

vec3 StockLocalNormal(vec4 bumpSample) {
    vec3 localNormal = vec3(bumpSample.a, bumpSample.g, bumpSample.b) * 2.0 - 1.0;
    return (StockSpecularFlags() & 2) != 0 ? SafeNormalize(localNormal) : localNormal;
}

// The _specularTable ramp of N.H, or with r_correctspecular retail's
// interactionNormBumpH.vfp term pow( N.H, exponent ) * brightness, whose half
// angle is rebuilt per pixel from the light direction and the normalized
// vector to the viewer. Callers apply the stock x2 of the specular map.
float StockSpecularTerm(vec3 halfAngle, vec3 lightDir, vec3 viewDir, vec3 localNormal) {
    if ((StockSpecularFlags() & 1) != 0) {
        float ndoth = max(clamp(dot(SafeNormalize(lightDir + viewDir), localNormal), 0.0, 1.0), 1.0e-6);
        return pow(ndoth, pc.d.y) * pc.d.z;
    }
    float specularDot = clamp(dot(halfAngle, localNormal), 0.0, 1.0);
    return texture(specularTableMap, vec2(specularDot, 0.5)).r;
}
