#version 450

// Prey's glow overlay (RB_STD_GlowOverlay, draw_common.cpp). OpenGL blurs the
// glow-only view by redrawing it as a stack of offset quads: the source at
// full weight, then each tap pair at +-step texels with an alpha that starts
// at r_glowAlpha and is multiplied by r_glowAlphaChange per step, added into
// an 8-bit target that clamps. One pass per axis; the vertical one here also
// adds the result to the scene at r_glowStrength, as OpenGL's composite does.
// A quad shifted off the view contributes nothing, so taps outside it are
// black rather than clamped to the edge.

layout(set = 0, binding = 0) uniform sampler2D Source;
layout(set = 1, binding = 0) uniform sampler2D Scene;

layout(std140, set = 6, binding = 0) uniform GlowBlock {
    vec4 params;			// xy: one blur step in UV along the axis, z: steps, w: 1 = composite
    vec4 weights;			// x: start alpha, y: alpha change, z: glow strength
} block;

layout(location = 0) in vec2 fragUV;
layout(location = 0) out vec4 outColor;

vec3 Tap( vec2 uv ) {
	if ( any( lessThan( uv, vec2( 0.0 ) ) ) || any( greaterThan( uv, vec2( 1.0 ) ) ) ) {
		return vec3( 0.0 );
	}
	return texture( Source, uv ).rgb;
}

void main() {
	vec3 sum = texture( Source, fragUV ).rgb;
	float alpha = block.weights.x;
	const int steps = int( block.params.z );
	for ( int step = 1; step < steps && alpha > 0.001; ++step ) {
		const vec2 offset = block.params.xy * float( step );
		sum += alpha * ( Tap( fragUV + offset ) + Tap( fragUV - offset ) );
		alpha *= block.weights.y;
	}
	sum = clamp( sum, vec3( 0.0 ), vec3( 1.0 ) );

	if ( block.params.w > 0.5 ) {
		const vec4 scene = texture( Scene, fragUV );
		outColor = vec4( scene.rgb + sum * block.weights.z, scene.a );
	} else {
		outColor = vec4( sum, 1.0 );
	}
}
