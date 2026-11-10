#version 450

// Motion vectors for posed (skinned) surfaces: post_motionvectors.vert with
// a second stream holding each vertex's model-space position as drawn on the
// previous frame (drawSurf->previousPositionCache), so animation itself
// produces exact vectors. Shares post_motionvectors.frag.

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec3 inPreviousPosition;

layout(push_constant) uniform MotionVectorPush {
    mat4 currentMvp;
    mat4 previousMvp;
} push;

layout(location = 0) out vec4 currentClipPosition;
layout(location = 1) out vec4 previousClipPosition;

void main() {
	currentClipPosition = push.currentMvp * vec4( inPosition, 1.0 );
	previousClipPosition = push.previousMvp * vec4( inPreviousPosition, 1.0 );
	gl_Position = currentClipPosition;
}
