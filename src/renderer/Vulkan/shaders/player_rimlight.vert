#version 450

// Multiplayer player rimlight. A port of
// content/baseoq4/pak0/glprogs/player_rimlight.vs
// (RB_PlayerVisibilityDrawRimlightSurface).

layout(location = 0) in vec3 inPosition;
layout(location = 2) in vec3 inNormal;

layout(push_constant) uniform RimlightPush {
    mat4 mvp;
} pc;

layout(std140, set = 6, binding = 0) uniform RimlightBlock {
    vec4 modelRow0;
    vec4 modelRow1;
    vec4 modelRow2;
    vec4 viewOrigin;
    vec4 color;
    vec4 rimParams;
} block;

layout(location = 0) out vec3 vWorldNormal;
layout(location = 1) out vec3 vWorldPosition;

vec3 TransformVectorToWorld( vec3 localVector ) {
	return vec3(
		dot( localVector, block.modelRow0.xyz ),
		dot( localVector, block.modelRow1.xyz ),
		dot( localVector, block.modelRow2.xyz ) );
}

void main() {
	vec4 position = vec4( inPosition, 1.0 );
	vWorldNormal = normalize( TransformVectorToWorld( inNormal ) );
	vWorldPosition = vec3(
		dot( position, block.modelRow0 ),
		dot( position, block.modelRow1 ),
		dot( position, block.modelRow2 ) );

	gl_Position = pc.mvp * position;
}
