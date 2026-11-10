#version 450

// Rigid-object motion vectors. A port of
// content/baseoq4/pak0/glprogs/motionvectors.fs. The vector target is drawn
// with a positive-height viewport, so its rows are stored bottom-up like the
// OpenGL target and the blur pass samples it with OpenGL texture coordinates.

layout(set = 0, binding = 0) uniform sampler2D DepthBuffer;

layout(std140, set = 6, binding = 0) uniform MotionVectorBlock {
    vec4 params;			// xy: viewportSize; z: scene-depth Y flip for TAA
} block;

#define viewportSize		block.params.xy

layout(location = 0) in vec4 currentClipPosition;
layout(location = 1) in vec4 previousClipPosition;
layout(location = 0) out vec4 outColor;

void main() {
	if ( currentClipPosition.w <= 0.00001 ) {
		discard;
	}

	vec2 currentUV = currentClipPosition.xy / currentClipPosition.w * 0.5 + 0.5;
	if ( currentUV.x < 0.0 || currentUV.y < 0.0 || currentUV.x > 1.0 || currentUV.y > 1.0 ) {
		discard;
	}

	vec2 depthUV = vec2( currentUV.x, mix( currentUV.y, 1.0 - currentUV.y, block.params.z ) );
	float sceneDepth = texture( DepthBuffer, depthUV ).x;
	if ( sceneDepth >= 0.99999 ) {
		discard;
	}

	float depthTolerance = max( 0.00008, sceneDepth * 0.00005 );
	if ( abs( sceneDepth - gl_FragCoord.z ) > depthTolerance ) {
		discard;
	}
	if ( previousClipPosition.w <= 0.00001 ) {
		// Only visible fragments without a previous clip position reject history.
		outColor = vec4( 0.0, 0.0, 1.0, 0.0 );
		return;
	}

	vec2 previousUV = previousClipPosition.xy / previousClipPosition.w * 0.5 + 0.5;
	vec2 velocityPixels = ( currentUV - previousUV ) * viewportSize;
	outColor = vec4( velocityPixels, 0.0, 1.0 );
}
