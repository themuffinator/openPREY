#version 450

// Debug tool geometry (vk_DebugTools.cpp): the immediate-mode vertices the
// fixed-function emulation records from tr_rendertools.cpp. mvp is the GL
// projection times modelview with the Vulkan clip-z fixup applied, or the
// identity for polygon edges that arrive in clip space already, carrying
// their GL_POLYGON_OFFSET_LINE offset. The position keeps its w: shadow
// volume vertices (r_showShadowCount) put their far caps at infinity with
// w = 0.

layout(location = 0) in vec4 inPosition;
layout(location = 1) in vec4 inColor;
layout(location = 2) in vec2 inTexCoord;

layout(push_constant) uniform DebugDrawPush {
    mat4 mvp;
    vec4 params;			// x: point size
} pc;

layout(location = 0) out vec4 fragColor;
layout(location = 1) out vec2 fragTexCoord;

void main() {
	gl_Position = pc.mvp * inPosition;
	gl_PointSize = max( pc.params.x, 1.0 );
	fragColor = inColor;
	fragTexCoord = inTexCoord;
}
