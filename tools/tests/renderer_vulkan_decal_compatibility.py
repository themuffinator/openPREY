#!/usr/bin/env python3
"""Regression contract for Vulkan decal rendering parity."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEST_PATH = "tools/tests/renderer_vulkan_decal_compatibility.py"


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def require_order(haystack: str, needles: tuple[str, ...], context: str) -> None:
    previous = -1
    for needle in needles:
        position = haystack.find(needle, previous + 1)
        if position == -1:
            raise AssertionError(f"Missing {needle!r} in {context}")
        if position <= previous:
            raise AssertionError(f"Expected ordered snippets in {context}: {needles!r}")
        previous = position


def braced_body(source: str, marker: str, context: str) -> str:
    start = source.find(marker)
    if start == -1:
        raise AssertionError(f"Missing {marker!r} in {context}")

    opening_brace = source.find("{", start + len(marker))
    if opening_brace == -1:
        raise AssertionError(f"Missing opening brace after {marker!r} in {context}")

    depth = 0
    for index in range(opening_brace, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]

    raise AssertionError(f"Could not find closing brace for {marker!r} in {context}")


def validate_projected_decal_payload() -> None:
    model_decal = read("src/renderer/ModelDecal.cpp")
    add_draw_surf = braced_body(
        model_decal,
        "void idRenderModelDecal::AddDecalDrawSurf(",
        "projected decal draw-surface submission",
    )

    require_order(
        add_draw_surf,
        (
            "r_skipDecals.GetBool()",
            "const int decalColorStride = tri.numVerts * 4",
            "R_DeriveTangents( &tri, false )",
            "material->EvaluateStageRegisters( stage, regs, shaderParms, tr.frameShaderTime )",
            "vertDepthFade[triVertIndex0] * 255.0f",
            "vertexCache.AllocFrameTemp( vertexAndColorData, totalAmbientBytes )",
            "R_AddDrawSurf(",
            "drawSurf->decalColorCache",
            "drawSurf->decalColorStageCount = numStages",
        ),
        "projected decal draw-surface submission",
    )

    draw_surf = read("src/renderer/tr_local.h")
    for field in (
        "decalColorCache",
        "decalColorOffset",
        "decalColorStride",
        "decalColorStageCount",
    ):
        require(draw_surf, field, "drawSurf_t decal metadata")


def validate_stage_color_streams() -> None:
    executor = read("src/renderer/Vulkan/vk_GuiExecutor.cpp")

    color_bind = braced_body(
        executor,
        "static bool VK_Exec_BindGLSLStageColor(",
        "Vulkan GLSL decal color binding",
    )
    require_order(
        color_bind,
        (
            "stage->vertexColor == SVC_IGNORE",
            "drawSurf->decalColorCache == NULL",
            "stageNum >= drawSurf->decalColorStageCount",
            "drawSurf->decalColorOffset",
            "stageNum * drawSurf->decalColorStride",
            "vkCmdBindVertexBuffers( vkExec.cmd, 1, 1",
        ),
        "Vulkan GLSL decal color binding",
    )

    glsl_stage = braced_body(
        executor,
        "static bool VK_Exec_DrawGLSLProgramStage(",
        "Vulkan GLSL material-stage drawing",
    )
    require_order(
        glsl_stage,
        (
            "VK_Exec_GLSLFamilyUsesVertexColor( family )",
            "VK_Exec_BindGLSLStageColor( drawSurf, tri, stage, stageNum )",
            "VK_Exec_GetGLSLMaterialPipeline(",
            "if ( separateColor )",
            "push.stageColor[ 0 ] = 1.0f",
            "vkCmdDrawIndexed(",
        ),
        "Vulkan GLSL material-stage drawing",
    )

    ambient = braced_body(
        executor,
        "static void VK_Exec_DrawAmbientStages(",
        "Vulkan ambient material-stage drawing",
    )
    require(
        ambient,
        "drawSurf->decalColorOffset + stageNum * drawSurf->decalColorStride",
        "classic Vulkan decal stage-color upload",
    )
    require(
        ambient,
        "VK_GuiExecutor_GetPipeline( pStage->drawStateBits, bakedDecalStageColor )",
        "classic Vulkan decal pipeline selection",
    )
    if ambient.count("const bool stagePolygonOffset") != 2:
        raise AssertionError(
            "Ambient drawing must apply private polygon offset to both program and classic stages"
        )

    program_stage = braced_body(
        ambient,
        "if ( pStage->newStage != NULL )",
        "Vulkan program-stage polygon offset",
    )
    require_order(
        program_stage,
        (
            "pStage->privatePolygonOffset",
            "vkCmdSetDepthBiasEnable( cmd, VK_TRUE )",
            "vkCmdSetDepthBias( cmd",
            "VK_Exec_DrawProgramStage(",
            "shader->TestMaterialFlag( MF_POLYGONOFFSET )",
            "shader->GetPolygonOffset()",
            "vkCmdSetDepthBiasEnable( cmd, VK_FALSE )",
        ),
        "Vulkan program-stage polygon offset",
    )


def validate_multiply_blend_fade() -> None:
    fragment = read("src/renderer/Vulkan/shaders/material_multiply_blend.frag")
    require_order(
        fragment,
        (
            "texture(Image, vTexCoord) * vColor.a",
            "vec4(0.5) * (1.0 - vColor.a)",
            "outColor = color",
        ),
        "Vulkan multiply-blend decal shader",
    )


def validate_draw_order_and_state() -> None:
    executor = read("src/renderer/Vulkan/vk_GuiExecutor.cpp")
    draw_view = braced_body(
        executor,
        "void VK_GuiExecutor_Draw3DView(",
        "Vulkan 3D view",
    )
    require_order(
        draw_view,
        (
            "VK_Interactions_DrawLights( viewDef )",
            "for ( int pass = 0; pass < 3; pass++ )",
            "if ( pass == 1 )",
            "VK_Fog_DrawAllLights( viewDef )",
        ),
        "Vulkan direct-light/decal/fog ordering",
    )
    for snippet in (
        "drawSurf->decalColorCache != NULL",
        "shader->GetSort() >= SS_DECAL",
        "isDecal ? !r_skipDecals.GetBool()",
        "shader->GetCullType()",
        "shader->TestMaterialFlag( MF_POLYGONOFFSET )",
        "shader->GetPolygonOffset()",
    ):
        require(draw_view, snippet, "Vulkan decal draw classification and state")

    interactions = read("src/renderer/Vulkan/vk_Interactions.cpp")
    create_interactions = braced_body(
        interactions,
        "static void VK_CreateSingleDrawInteractions(",
        "Vulkan interaction drawing",
    )
    require_order(
        create_interactions,
        (
            "surfaceShader->GetCullType()",
            "surfaceShader->TestMaterialFlag( MF_POLYGONOFFSET )",
            "surfaceShader->GetPolygonOffset()",
            "VK_SubmitInteraction( &inter, pbrOwnerEligible )",
            "vkCmdSetDepthBiasEnable( interPass.cmd, VK_FALSE )",
        ),
        "Vulkan lit decal interaction state",
    )


def validate_ci_registration() -> None:
    validator = read("tools/validation/openq4_validate.py")
    commit = read(".github/workflows/commit-validation.yml")
    push = read(".github/workflows/push-verification.yml")

    if validator.count("renderer_vulkan_decal_compatibility.py") != 1:
        raise AssertionError(
            "Local validation runner must register the Vulkan decal compatibility test exactly once"
        )

    for workflow, context in (
        (commit, "commit validation workflow"),
        (push, "push verification workflow"),
    ):
        if workflow.count(TEST_PATH) != 2:
            raise AssertionError(f"{context} must compile and directly run {TEST_PATH}")
        require(workflow, f"python {TEST_PATH}", context)


def main() -> None:
    validate_projected_decal_payload()
    validate_stage_color_streams()
    validate_multiply_blend_fade()
    validate_draw_order_and_state()
    validate_ci_registration()
    print("renderer_vulkan_decal_compatibility: ok")


if __name__ == "__main__":
    main()
