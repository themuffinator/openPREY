#version 450

// openQ4 Vulkan GUI/2D pipeline — vertex stage (Phase D,
// docs/dev/archive/2026-10-18/plans/2026-07-18-vulkan-phase-d.md).
//
// Consumes idDrawVert (64-byte stride): position, byte-normalized color,
// texcoord. The 2D ortho projection arrives fully formed from the engine
// front-end (GuiModel EmitFullScreen); stage state arrives as push
// constants so the pipeline needs no descriptor churn per stage.

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec4 inColor;
layout(location = 2) in vec2 inTexCoord;

layout(push_constant) uniform GuiPushConstants {
    mat4 mvp;
    vec4 stageColor;
    // 2x3 texture matrix as two row vectors: s' = dot((s,t,0,1), texMatrixS)
    vec4 texMatrixS;
    vec4 texMatrixT;
    // x: color mode (0 ignore, 1 modulate, 2 inverse, 3 native emission)
    // y: alpha test (3 filtered / 4 hard PBR), z: reference, w: texture matrix enable
    vec4 params;
} pc;

layout(location = 0) out vec2 fragTexCoord;
layout(location = 1) out vec4 fragColor;

void main() {
    gl_Position = pc.mvp * vec4(inPosition, 1.0);

    vec2 st = inTexCoord;
    if (pc.params.w > 0.5) {
        vec4 stv = vec4(inTexCoord, 0.0, 1.0);
        st = vec2(dot(stv, pc.texMatrixS), dot(stv, pc.texMatrixT));
    }
    fragTexCoord = st;

    vec4 vertexColor = inColor;
    if (pc.params.x < 0.5 || pc.params.x > 2.5) {
        vertexColor = vec4(1.0);
    } else if (pc.params.x > 1.5) {
        // GL's inverse-modulate combiner inverts only the RGB operand;
        // primary alpha continues to modulate texture alpha unchanged.
        vertexColor = vec4(vec3(1.0) - inColor.rgb, inColor.a);
    }
    fragColor = vertexColor * pc.stageColor;
}
