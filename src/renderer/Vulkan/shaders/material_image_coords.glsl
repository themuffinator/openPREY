// Included after MaterialShaderParms. Slot 12.y carries one orientation bit
// per texture descriptor. Apply this after authored offsets: changing the
// varying itself would reverse SMAA's directional searches and blend weights.
vec2 MaterialImageCoord(vec2 uv, uint textureSet) {
    uint flipMask = uint(material.shaderParms[12].y);
    if ((flipMask & (1u << textureSet)) != 0u) {
        uv.y = 1.0 - uv.y;
    }
    return uv;
}
