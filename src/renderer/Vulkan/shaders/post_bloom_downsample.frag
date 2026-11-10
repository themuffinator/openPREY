#version 450

// Bloom pyramid downsample. A port of
// content/baseoq4/pak0/glprogs/bloom_downsample.fs (RB_STD_Bloom).

layout(set = 0, binding = 0) uniform sampler2D Scene;

layout(std140, set = 6, binding = 0) uniform BloomDownsampleBlock {
    vec4 params;			// xy: invTexSize
} block;

#define invTexSize			block.params.xy

layout(location = 0) in vec2 fragUV;
layout(location = 0) out vec4 outColor;

vec3 FilteredScene( vec2 uv ) {
	vec2 texel = invTexSize;
	vec3 color = texture( Scene, uv ).rgb * 0.25;

	color += texture( Scene, uv + vec2( texel.x, 0.0 ) ).rgb * 0.125;
	color += texture( Scene, uv - vec2( texel.x, 0.0 ) ).rgb * 0.125;
	color += texture( Scene, uv + vec2( 0.0, texel.y ) ).rgb * 0.125;
	color += texture( Scene, uv - vec2( 0.0, texel.y ) ).rgb * 0.125;

	color += texture( Scene, uv + vec2( texel.x, texel.y ) ).rgb * 0.0625;
	color += texture( Scene, uv + vec2( -texel.x, texel.y ) ).rgb * 0.0625;
	color += texture( Scene, uv + vec2( texel.x, -texel.y ) ).rgb * 0.0625;
	color += texture( Scene, uv - vec2( texel.x, texel.y ) ).rgb * 0.0625;

	return color;
}

void main() {
	outColor = vec4( max( FilteredScene( fragUV ), vec3( 0.0 ) ), 1.0 );
}
