#version 450

// Baked light-grid indirect diffuse. A port of
// content/baseoq4/pak0/glprogs/lightgrid_indirect.vs, which
// RB_STD_LightGridIndirect draws on the OpenGL backend. The uniforms are split
// between the push range (projection and texture matrices) and the 256-byte
// LightGridBlock shared with lightgrid_indirect.frag; see that file for the
// packing.

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec4 inColor;
layout(location = 2) in vec3 inNormal;
layout(location = 3) in vec3 inTangent0;
layout(location = 4) in vec3 inTangent1;
layout(location = 5) in vec2 inTexCoord;

layout(push_constant) uniform LightGridPush {
    mat4 mvp;
    vec4 bumpMatrixS;
    vec4 bumpMatrixT;
    vec4 diffuseMatrixS;
    vec4 diffuseMatrixT;
} pc;

layout(std140, set = 6, binding = 0) uniform LightGridBlock {
    vec4 modelRow0;
    vec4 modelRow1;
    vec4 modelRow2;
    vec4 gridOrigin;		// xyz: grid origin, w: r_lightGridDebug
    vec4 gridSize;			// xyz: cell size, w: probe relocation distance
    vec4 gridBounds;		// xyz: cell counts, w: probe atlas bound
    vec4 atlasInfo;
    vec4 visibilityInfo;
    vec4 blendInfo;			// xyz: intensity, portal side, portal distance; w: irradiance gamma
    vec4 portalPlane;
    vec4 portalBoundsMin;	// xyz: bounds, w: max contribution
    vec4 portalBoundsMax;	// xyz: bounds, w: vertex colour scale
    vec4 depthInfo;
    vec4 depthViewport;		// xy: view origin (OpenGL window space), z: vertex colour bias, w: framebuffer height
    vec4 diffuseColor;
    vec4 flatDiffuseParams;
} block;

layout(location = 0) out vec2 vBumpTexCoord;
layout(location = 1) out vec2 vDiffuseTexCoord;
layout(location = 2) out vec3 vWorldTangent;
layout(location = 3) out vec3 vWorldBitangent;
layout(location = 4) out vec3 vWorldNormal;
layout(location = 5) out vec3 vWorldPosition;
layout(location = 6) out vec3 vVertexColor;
layout(location = 7) out float vLocalZ;

vec3 TransformVectorToWorld( vec3 localVector ) {
	return vec3(
		dot( localVector, block.modelRow0.xyz ),
		dot( localVector, block.modelRow1.xyz ),
		dot( localVector, block.modelRow2.xyz ) );
}

void main() {
	vec4 baseTexCoord = vec4( inTexCoord, 0.0, 1.0 );
	vec4 position = vec4( inPosition, 1.0 );

	vBumpTexCoord = vec2( dot( baseTexCoord, pc.bumpMatrixS ), dot( baseTexCoord, pc.bumpMatrixT ) );
	vDiffuseTexCoord = vec2( dot( baseTexCoord, pc.diffuseMatrixS ), dot( baseTexCoord, pc.diffuseMatrixT ) );

	vWorldTangent = normalize( TransformVectorToWorld( inTangent0 ) );
	vWorldBitangent = normalize( TransformVectorToWorld( inTangent1 ) );
	vWorldNormal = normalize( TransformVectorToWorld( inNormal ) );

	vWorldPosition = vec3(
		dot( position, block.modelRow0 ),
		dot( position, block.modelRow1 ),
		dot( position, block.modelRow2 ) );

	vVertexColor = inColor.rgb * block.portalBoundsMax.w + vec3( block.depthViewport.z );
	vLocalZ = inPosition.z;

	gl_Position = pc.mvp * position;
}
