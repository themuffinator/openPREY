// Copyright (C) 2026 DarkMatter Productions
// Match the modern PBR vertex frame before interpolation. Averaged mesh
// tangents are not necessarily perpendicular to the authored normal; leaving
// that component in the frame can flip N.V at grazing angles after mapping.
vec3 PBRVertexNormalize(vec3 value, vec3 fallback) {
    float lengthSquared = dot(value, value);
    return lengthSquared > 1.0e-8 ? value * inversesqrt(lengthSquared) : fallback;
}

void PBRVertexFrame(vec3 sourceNormal, vec3 sourceTangent, vec3 sourceBitangent,
        out vec3 normal, out vec3 tangent, out vec3 bitangent) {
    normal = PBRVertexNormalize(sourceNormal, vec3(0.0, 0.0, 1.0));
    tangent = PBRVertexNormalize(sourceTangent, vec3(1.0, 0.0, 0.0));
    vec3 rawBitangent = PBRVertexNormalize(sourceBitangent, vec3(0.0, 1.0, 0.0));
    tangent = PBRVertexNormalize(tangent - normal * dot(normal, tangent), vec3(1.0, 0.0, 0.0));
    float handedness = dot(cross(normal, tangent), rawBitangent) < 0.0 ? -1.0 : 1.0;
    bitangent = PBRVertexNormalize(cross(normal, tangent) * handedness, rawBitangent);
}
