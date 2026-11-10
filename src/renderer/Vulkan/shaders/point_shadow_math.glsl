// Keep radial comparisons in world-axis order. A built-in dot/length may
// reassociate the first two squares; a one-ULP reference difference can change
// a hardware shadow comparison. Explicit x, then y, then z fused additions
// match the OpenGL path measured on the qualification GPU.
float PointShadowRadialLength(vec3 value) {
    precise float squareLength = value.x * value.x;
    squareLength = fma(value.y, value.y, squareLength);
    squareLength = fma(value.z, value.z, squareLength);
    return sqrt(squareLength);
}

float PointShadowRadialDepth(vec3 value, float farDistance) {
    precise float inverseFar = 1.0 / farDistance;
    precise float depth = PointShadowRadialLength(value) * inverseFar;
    return depth;
}
