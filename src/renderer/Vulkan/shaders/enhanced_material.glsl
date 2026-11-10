// r_enhancedMaterials for the classic interaction shaders: the
// DecodeLocalNormal / EnhancedSpecularTerm math of OpenGL's
// material_interaction.fs and shadow_interaction.fs. Classic draws push
// pc.c.w = 1 to enable it, with pc.d.y specular boost, pc.d.z Fresnel and
// pc.d.w normal scale (those components belong to native PBR draws otherwise).
// Include after SafeNormalize.

bool EnhancedMaterialActive() {
    return pc.d.x < 0.5 && pc.c.w > 0.5;
}

vec3 EnhancedLocalNormal(vec4 bumpSample) {
    vec2 localNormalXY = vec2(bumpSample.a, bumpSample.g) * 2.0 - 1.0;
    localNormalXY *= max(pc.d.w, 0.0);
    float xyLengthSq = dot(localNormalXY, localNormalXY);
    if (xyLengthSq > 1.0) {
        localNormalXY *= inversesqrt(xyLengthSq);
        xyLengthSq = 1.0;
    }
    float encodedZ = max(bumpSample.b * 2.0 - 1.0, 0.0);
    float reconstructedZ = sqrt(max(1.0 - xyLengthSq, 0.0));
    return SafeNormalize(vec3(localNormalXY, mix(encodedZ, reconstructedZ, 0.75)));
}

float EnhancedSpecularTerm(vec3 halfAngle, vec3 viewDir, vec3 localNormal, vec3 specularSample) {
    float ndoth = max(dot(halfAngle, localNormal), 0.0);
    float ndotv = max(dot(viewDir, localNormal), 0.0);
    float gloss = clamp(max(max(specularSample.r, specularSample.g), specularSample.b), 0.0, 1.0);
    float specularPower = mix(10.0, 40.0, gloss);
    float fresnel = 1.0 + (pow(1.0 - ndotv, 5.0) * 2.0 * clamp(pc.d.z, 0.0, 1.0));
    return pow(ndoth, specularPower) * max(pc.d.y, 0.0) * fresnel;
}
