// Per-stage state of one translucent shadow-moment caster draw, streamed
// through the frame's uniform ring (set 2, the fog/blend layout's UBO). The
// fields are the GL shadow_proj_translucent_caster uniforms; the stage
// analysis that fills them is RB_TranslucentShadowStage* in draw_arb2.cpp.
layout(set = 2, binding = 0, std140) uniform MomentStageBlock {
    vec4 alphaS;             // stage texture matrix S row
    vec4 alphaT;             // stage texture matrix T row
    vec4 coverageS;          // coverage stage texture matrix S row
    vec4 coverageT;          // coverage stage texture matrix T row
    vec4 stageColor;
    vec4 coverageStageColor;
    vec4 modes;              // x: opacity source, y: vertex color, z: coverage source, w: coverage vertex color
    vec4 coverageTest;       // x: alpha ref, y: alpha test mode (-1 less, 0 equal, 1 greater), z: enabled, w: min alpha
    vec4 vertexAlpha;        // xy: stage vertex alpha scale/bias, zw: coverage vertex alpha scale/bias
} stage;
