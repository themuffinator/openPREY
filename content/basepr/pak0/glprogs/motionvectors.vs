uniform mat4 previousModelViewProjection;
uniform vec2 viewportSize;
// x: 0 = rigid (previous transform), 1 = previous positions in texcoord 1,
//    2 = reactive coverage; y: reactive strength
uniform vec4 motionMode;

varying vec4 currentClipPosition;
varying vec4 previousClipPosition;

void main() {
	vec4 position = gl_Vertex;
	vec4 previousPosition = position;
	if ( motionMode.x > 0.5 && motionMode.x < 1.5 ) {
		previousPosition = vec4( gl_MultiTexCoord1.xyz, 1.0 );
	}
	currentClipPosition = ftransform();
	previousClipPosition = previousModelViewProjection * previousPosition;
	gl_Position = currentClipPosition;
}
