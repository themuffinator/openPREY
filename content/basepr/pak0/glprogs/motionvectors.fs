uniform sampler2D DepthBuffer;
uniform vec2 viewportSize;
// x: 0 = rigid, 1 = previous positions, 2 = reactive coverage; y: reactive strength
uniform vec4 motionMode;

varying vec4 currentClipPosition;
varying vec4 previousClipPosition;

void main() {
	if ( currentClipPosition.w <= 0.00001 ) {
		discard;
	}

	vec2 currentUV = currentClipPosition.xy / currentClipPosition.w * 0.5 + 0.5;
	if ( currentUV.x < 0.0 || currentUV.y < 0.0 || currentUV.x > 1.0 || currentUV.y > 1.0 ) {
		discard;
	}

	float sceneDepth = texture2D( DepthBuffer, currentUV ).x;
	float depthTolerance = max( 0.00008, sceneDepth * 0.00005 );

	if ( motionMode.x > 1.5 ) {
		// Reactive coverage: any fragment not hidden behind the finished opaque
		// depth (particles and glass in front of it, or the visible surface
		// itself) marks its pixel; only the blue channel is written.
		if ( gl_FragCoord.z > sceneDepth + depthTolerance ) {
			discard;
		}
		gl_FragColor = vec4( 0.0, 0.0, motionMode.y, 0.0 );
		return;
	}

	if ( sceneDepth >= 0.99999 ) {
		discard;
	}
	if ( abs( sceneDepth - gl_FragCoord.z ) > depthTolerance ) {
		discard;
	}
	if ( previousClipPosition.w <= 0.00001 ) {
		// visible, but with no previous clip position: reject its history
		gl_FragColor = vec4( 0.0, 0.0, 1.0, 0.0 );
		return;
	}

	vec2 previousUV = previousClipPosition.xy / previousClipPosition.w * 0.5 + 0.5;
	vec2 velocityPixels = ( currentUV - previousUV ) * viewportSize;
	gl_FragColor = vec4( velocityPixels, 0.0, 1.0 );
}
