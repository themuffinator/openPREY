#version 450

// Silhouette shell for the multiplayer player outline and the cel outline. A
// port of content/baseoq4/pak0/glprogs/player_outline.vs, which
// RB_PlayerVisibilityDrawOutlineSurface and RB_CelDrawOutlineSurface draw on
// the OpenGL backend. The same program, with a width of 0, draws the
// silhouette mask and the brightskin wash.
//
// OpenGL projects the eye-space normal (gl_NormalMatrix * gl_Normal) with the
// projection; for the rigid transforms entities use, that is the model-view-
// projection applied to the normal as a direction. The Vulkan clip-z fixup
// in mvp leaves x, y and w alone, and the negative-height viewport flips the
// result, so the pixel-space extrusion is OpenGL's.

layout(location = 0) in vec3 inPosition;
layout(location = 2) in vec3 inNormal;

layout(push_constant) uniform OutlinePush {
    mat4 mvp;
    vec4 color;
    // x: outline width in viewport pixels
    // y: clip-space units per horizontal pixel ( 2 / viewport width )
    // z: clip-space units per vertical pixel ( 2 / viewport height )
    // w: unused
    vec4 outlineParams;
} pc;

void main() {
	vec4 clipPosition = pc.mvp * vec4( inPosition, 1.0 );
	vec2 clipNormal = ( pc.mvp * vec4( inNormal, 0.0 ) ).xy;

	// Pick the direction in pixel space, not in clip space; see
	// player_outline.vs for why that keeps the ring even on wide viewports.
	vec2 pixelsPerClip = vec2( 1.0 / pc.outlineParams.y, 1.0 / pc.outlineParams.z );
	vec2 pixelNormal = clipNormal * pixelsPerClip;
	float pixelLength = length( pixelNormal );
	if ( pixelLength > 0.0001 ) {
		// Scaling by w cancels the perspective divide, so the offset stays a
		// constant pixel count at any distance from the camera.
		vec2 offset = ( pixelNormal / pixelLength ) * vec2( pc.outlineParams.y, pc.outlineParams.z );
		clipPosition.xy += offset * pc.outlineParams.x * max( clipPosition.w, 0.001 );
	}

	gl_Position = clipPosition;
}
