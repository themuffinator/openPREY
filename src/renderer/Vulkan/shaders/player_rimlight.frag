#version 450

// Multiplayer player rimlight. A port of
// content/baseoq4/pak0/glprogs/player_rimlight.fs; see that file for the
// shaping parameters.

layout(std140, set = 6, binding = 0) uniform RimlightBlock {
    vec4 modelRow0;
    vec4 modelRow1;
    vec4 modelRow2;
    vec4 viewOrigin;
    vec4 color;
    // x: falloff exponent, y: intensity scale, z: floor, w: unused
    vec4 rimParams;
} block;

layout(location = 0) in vec3 vWorldNormal;
layout(location = 1) in vec3 vWorldPosition;
layout(location = 0) out vec4 outColor;

void main() {
	vec3 normal = normalize( vWorldNormal );
	vec3 viewDir = normalize( block.viewOrigin.xyz - vWorldPosition );
	float rim = 1.0 - max( dot( normal, viewDir ), 0.0 );
	rim = pow( max( rim, 0.0 ), max( block.rimParams.x, 0.001 ) );

	// The floor lifts the rim term itself rather than the final colour, so it
	// still scales with the entity's requested strength.
	rim = clamp( rim + block.rimParams.z, 0.0, 1.0 );

	float contribution = clamp( block.color.a * rim * block.rimParams.y, 0.0, 1.0 );
	outColor = vec4( block.color.rgb * contribution, contribution );
}
