#version 450

// Separable bloom blur. A port of content/baseoq4/pak0/glprogs/bloom_blur.fs
// (RB_STD_Bloom).

layout(set = 0, binding = 0) uniform sampler2D Scene;

layout(std140, set = 6, binding = 0) uniform BloomBlurBlock {
    vec4 params;			// xy: invTexSize, zw: blur axis
    vec4 radius;			// x: blur radius
} block;

#define invTexSize			block.params.xy
#define blurAxis			block.params.zw
#define blurRadius			block.radius.x

layout(location = 0) in vec2 fragUV;
layout(location = 0) out vec4 outColor;

void main() {
	vec2 uv = fragUV;
	vec2 stepSize = blurAxis * invTexSize * max( blurRadius, 0.1 );
	vec3 color = texture( Scene, uv ).rgb * 0.19648255;

	color += texture( Scene, uv + stepSize * 1.4117647 ).rgb * 0.29690696;
	color += texture( Scene, uv - stepSize * 1.4117647 ).rgb * 0.29690696;
	color += texture( Scene, uv + stepSize * 3.2941176 ).rgb * 0.0944704;
	color += texture( Scene, uv - stepSize * 3.2941176 ).rgb * 0.0944704;
	color += texture( Scene, uv + stepSize * 5.1764706 ).rgb * 0.01038136;
	color += texture( Scene, uv - stepSize * 5.1764706 ).rgb * 0.01038136;

	outColor = vec4( max( color, vec3( 0.0 ) ), 1.0 );
}
