#version 450

// Reactive coverage (see post_motionvectors_reactive.vert). Any fragment not
// hidden behind the finished opaque depth marks its pixel; the pipeline
// writes only the blue channel, so exact vectors underneath survive.

layout(set = 0, binding = 0) uniform sampler2D DepthBuffer;

layout(std140, set = 6, binding = 0) uniform MotionVectorBlock {
    vec4 params;			// xy: viewportSize; z: scene-depth Y flip for TAA
} block;

layout(push_constant) uniform ReactivePush {
    mat4 currentMvp;
    vec4 params;			// x: reactive strength
} push;

layout(location = 0) in vec4 currentClipPosition;
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
	float depthTolerance = max( 0.00008, sceneDepth * 0.00005 );
	if ( gl_FragCoord.z > sceneDepth + depthTolerance ) {
		discard;
	}
	outColor = vec4( 0.0, 0.0, push.params.x, 0.0 );
}
