#version 450

// Reactive coverage for the temporal velocity target: surfaces whose image
// changes on its own (particles, effects, GUIs, subviews, translucent or
// unposed moving geometry) mark the pixels they cover. Port of the reactive
// mode of content/baseoq4/pak0/glprogs/motionvectors.vs.

layout(location = 0) in vec3 inPosition;

layout(push_constant) uniform ReactivePush {
    mat4 currentMvp;
    vec4 params;			// x: reactive strength
} push;

layout(location = 0) out vec4 currentClipPosition;

void main() {
	currentClipPosition = push.currentMvp * vec4( inPosition, 1.0 );
	gl_Position = currentClipPosition;
}
