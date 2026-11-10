#version 450

// Rigid-object motion vectors. A port of
// content/baseoq4/pak0/glprogs/motionvectors.vs (RB_RenderMotionVectorBuffer).
// currentMvp is this frame's projection * modelview with the Vulkan clip-z
// fixup; previousMvp is last frame's OpenGL projection * view * model. Only
// the xy/w of either clip position is used for the vector, and the fixup
// leaves those unchanged.

layout(location = 0) in vec3 inPosition;

layout(push_constant) uniform MotionVectorPush {
    mat4 currentMvp;
    mat4 previousMvp;
} push;

layout(location = 0) out vec4 currentClipPosition;
layout(location = 1) out vec4 previousClipPosition;

void main() {
	vec4 position = vec4( inPosition, 1.0 );
	currentClipPosition = push.currentMvp * position;
	previousClipPosition = push.previousMvp * position;
	gl_Position = currentClipPosition;
}
