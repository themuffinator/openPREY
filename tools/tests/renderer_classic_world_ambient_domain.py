#!/usr/bin/env python3
"""Static regression contract for shared classic world ambient ownership."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEST_PATH = "tools/tests/renderer_classic_world_ambient_domain.py"


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def reject(haystack: str, needle: str, context: str) -> None:
    if needle in haystack:
        raise AssertionError(f"Unexpected {needle!r} in {context}")


def require_order(haystack: str, needles: tuple[str, ...], context: str) -> None:
    previous = -1
    for needle in needles:
        position = haystack.find(needle, previous + 1)
        if position == -1:
            raise AssertionError(f"Missing {needle!r} in {context}")
        if position <= previous:
            raise AssertionError(
                f"Expected ordered contracts in {context}: {needles!r}"
            )
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
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Could not find closing brace for {marker!r} in {context}")


def validate_world_material_table() -> None:
    header = read("src/renderer/MaterialResourceTable.h")
    source = read("src/renderer/MaterialResourceTable.cpp")
    for token in (
        "MATERIAL_RESOURCE_TABLE_MAX_WORLD_PASSES",
        "firstWorldPass",
        "worldPassCount",
        "worldDomainReferenced",
        "worldPassEligible",
        "worldPassFailure",
        "worldPassFailureStage",
        "worldDomainReferencedRecords",
        "worldPassEligibleRecords",
        "worldPassFallbackRecords",
        "worldPassPoolOverflows",
        "R_MaterialResourceTable_WorldPassEligible",
        "R_MaterialResourceTable_WorldPasses",
        "R_MaterialResourceTable_CopyWorldPassList",
        "MaterialResourceWorldPassFailure_Name",
    ):
        require(header, token, "distinct ordered world material-pass contract")

    for token in (
        "rendererMaterialPass_t\t\t\tworldPasses[",
        "rendererMaterialPass_t\t\t\tguiPasses[",
    ):
        require(source, token, "separate GUI and world pass pools")
    reject(
        source,
        "record.firstWorldPass = record.firstGuiPass",
        "distinct world material-pass span",
    )

    prepare = braced_body(
        source,
        "void R_MaterialResourceTable_PrepareFrame(",
        "world packet-derived material-table preparation",
    )
    require_order(
        prepare,
        (
            "drawPacket.passCategory == RENDER_PASS_AMBIENT",
            "worldDomainReferenced[drawPacket.materialRecordIndex] = true;",
            "R_MaterialResourceTable_AddRecordFromSource(",
        ),
        "packet-derived world material admission",
    )

    compiler = braced_body(
        source,
        "static bool R_MaterialResourceTable_CompileOrderedPasses(",
        "ordered GUI/world material compiler",
    )
    for token in (
        "pass.kind = worldDomain",
        "RENDERER_MATERIAL_PASS_SURFACE",
        "R_MaterialResourceTable_MapWorldDepthState(",
        "pass.programFamily = worldDomain",
        "RENDERER_PROGRAM_FIXED",
        "record.firstWorldPass = rg_materialResourceTable.worldPassCount;",
        "rg_materialResourceTable.worldPasses[record.firstWorldPass]",
    ):
        require(compiler, token, "sealed world surface-pass compilation")

    depth = braced_body(
        source,
        "static bool R_MaterialResourceTable_MapWorldDepthState(",
        "world depth-state translation",
    )
    for token in (
        "depth.testEnabled = true;",
        "depth.writeEnabled = ( drawStateBits & GLS_DEPTHMASK ) == 0;",
        "RENDERER_COMPARE_LESS_OR_EQUAL",
        "RENDERER_COMPARE_EQUAL",
        "RENDERER_COMPARE_ALWAYS",
    ):
        require(depth, token, "depth-enabled world material pass")


def validate_transactional_domain() -> None:
    header = read("src/renderer/ClassicWorldAmbientDomain.h")
    source = read("src/renderer/ClassicWorldAmbientDomain.cpp")
    for token in (
        "CLASSIC_WORLD_AMBIENT_PHASE_PRE_FOG",
        "CLASSIC_WORLD_AMBIENT_PHASE_POST_FOG",
        "CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_DRAWABLE",
        "CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_IN_WORLD_GUI",
        "CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_SUBVIEW",
        "CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_SPECIAL_SURFACE",
        "CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_DEFORM",
        "CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_DEPTH_HACK",
        "CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_DECAL",
        "CLASSIC_WORLD_AMBIENT_SOURCE_SURFACE_FALLBACK_POST_PROCESS",
        "CLASSIC_WORLD_AMBIENT_FAILURE_INVALID_AMBIENT_PASS",
        "CLASSIC_WORLD_AMBIENT_FAILURE_FORBIDDEN_PASS",
        "CLASSIC_WORLD_AMBIENT_FAILURE_DEPTH_PREREQUISITE_MISSING",
        "CLASSIC_WORLD_AMBIENT_FAILURE_BACKEND_COVERAGE_MISMATCH",
        "classicWorldAmbientDomainBackendCoverage_t",
        "R_ClassicWorldAmbientDomain_RecordOwned",
        "R_ClassicWorldAmbientDomain_RecordBackendFallback",
    ):
        require(header, token, "whole-view world ambient domain API")

    prepare = braced_body(
        source,
        "void R_ClassicWorldAmbientDomain_PrepareFrame(",
        "whole-view world ambient domain preparation",
    )
    require_order(
        prepare,
        (
            "R_ClassicWorldAmbientDomain_ResetFrame();",
            "R_ClassicWorldAmbientDomain_PrepareView(",
            "domain.stats.frameValid",
        ),
        "per-view transactional world preparation",
    )

    prepare_view = braced_body(
        source,
        "static bool R_ClassicWorldAmbientDomain_PrepareView(",
        "per-view world ambient transaction",
    )
    require_order(
        prepare_view,
        (
            "CLASSIC_WORLD_AMBIENT_FAILURE_FORBIDDEN_PASS",
            "const int drawCheckpoint = domain.drawCount;",
            "const int passCheckpoint = domain.passCount;",
            "draw.phase = phase;",
            "ValidateDepthPrerequisite(",
            "R_MaterialResourceTable_CopyWorldPassList(",
            "RendererContracts_EvaluateMaterialPassList(",
            "pass.kind != RENDERER_MATERIAL_PASS_SURFACE",
            "!pass.depth.testEnabled",
            "R_MaterialResourceTable_ResolveTextureResource(",
            "view.firstDraw = drawCheckpoint;",
            "domain.drawCount += view.drawCount;",
            "domain.passCount += view.evaluatedPassCount;",
            "view.ready = true;",
        ),
        "validate and stage the complete view before atomic publication",
    )

    failure = braced_body(
        source,
        "static bool FailView(",
        "transactional world-view rollback",
    )
    for token in (
        "view.ready = false;",
        "view.firstDraw = -1;",
        "view.drawCount = 0;",
        "view.firstEvaluatedPass = -1;",
        "view.evaluatedPassCount = 0;",
        "domain.stats.fallbackViews++;",
    ):
        require(failure, token, "failed view publishes no partial span")

    phase = braced_body(
        source,
        "static classicWorldAmbientPhase_t PhaseForSurface(",
        "classic fog split classification",
    )
    require_order(
        phase,
        (
            "material->GetSort() >= SS_MEDIUM",
            "CLASSIC_WORLD_AMBIENT_PHASE_POST_FOG",
            "CLASSIC_WORLD_AMBIENT_PHASE_PRE_FOG",
        ),
        "pre-fog/post-fog source ordering",
    )

    depth = braced_body(
        source,
        "static bool ValidateDepthPrerequisite(",
        "opaque/perforated depth prerequisite",
    )
    for token in (
        "drawSurf->material->Coverage() == MC_TRANSLUCENT",
        "packet.passCategory != RENDER_PASS_DEPTH",
        "packet.materialRecordIndex != ambientPacket.materialRecordIndex",
        "packet.geometryRecordIndex != ambientPacket.geometryRecordIndex",
        "packet.instanceRecordIndex != ambientPacket.instanceRecordIndex",
        "depthPacketIndex = packetIndex;",
    ):
        require(depth, token, "matching depth-packet prerequisite")

    blockers = braced_body(
        source,
        "static bool ForbiddenPassCategory(",
        "explicit non-owned pass blockers",
    )
    for token in (
        "RENDER_PASS_STENCIL_SHADOW",
        "RENDER_PASS_SHADOW_MAP",
        "RENDER_PASS_ARB2_INTERACTION",
        "RENDER_PASS_LIGHT_GRID",
        "RENDER_PASS_FOG_BLEND",
        "RENDER_PASS_AUTHORED_POST",
        "RENDER_PASS_SPECIAL_EFFECTS",
        "RENDER_PASS_GUI",
    ):
        require(blockers, token, "whole-view non-owned domain blocker")
    require(
        source,
        "RendererClassicWorldAmbientDomain_RunSelfTest",
        "whole-view rollback and coverage self-test",
    )


def validate_gl_consumer() -> None:
    backend = read("src/renderer/tr_backend.cpp")
    draw = read("src/renderer/draw_common.cpp")
    handoff = braced_body(
        backend,
        "void RB_ExecuteBackEndCommands(",
        "OpenGL command handoff",
    )
    require_order(
        handoff,
        (
            "R_ClassicWorldAmbientDomain_ResetFrame();",
            "cmds->commandId == RC_NOP && !cmds->next",
            "R_MaterialResourceTable_PrepareFrame(",
            "R_ClassicWorldAmbientDomain_PrepareFrame(",
        ),
        "OpenGL world-domain frame preparation",
    )

    preflight = braced_body(
        draw,
        "static bool RB_SharedWorldAmbientGLPreflight(",
        "complete OpenGL world ambient preflight",
    )
    require_order(
        preflight,
        (
            "R_ClassicWorldAmbientDomain_ViewDraw(",
            "RB_EnsurePackedClassicDrawCaches(",
            "R_ClassicWorldAmbientDomain_DrawPass(",
            "R_ClassicWorldAmbientDomain_DrawPassTexture(",
            "RB_SharedWorldAmbientGLBuildState(",
            "RB_SharedGuiGLTextureBindingValid(",
            "prepared.ready = true;",
        ),
        "all-view OpenGL preflight before commit",
    )
    reject(preflight, "RB_DrawElementsWithCounters(", "fallible OpenGL preflight")

    prepare = braced_body(
        draw,
        "static bool RB_PrepareSharedWorldAmbientView(",
        "OpenGL whole-view shared ownership handoff",
    )
    require_order(
        prepare,
        (
            "R_ClassicWorldAmbientDomain_FindView(",
            "RB_SharedWorldAmbientGLPreflight(",
            "return true;",
        ),
        "OpenGL preflight completes before ownership",
    )

    consumer = braced_body(
        draw,
        "static void RB_DrawSharedWorldAmbientPhase(",
        "OpenGL shared world ambient consumer",
    )
    require_order(
        consumer,
        (
            "prepared.committed = true;",
            "RB_DrawElementsWithCounters( tri );",
            "R_ClassicWorldAmbientDomain_RecordOwned(",
        ),
        "OpenGL commit, execution, and coverage ordering",
    )
    for body, context in (
        (preflight, "OpenGL sealed world preflight"),
        (prepare, "OpenGL sealed world handoff"),
        (consumer, "OpenGL sealed world consumer"),
    ):
        reject(body, "shaderRegisters", context)
        reject(body, "GetStage(", context)

    draw_view = braced_body(
        draw,
        "void\tRB_STD_DrawView(",
        "OpenGL classic 3D view phase handoff",
    )
    require_order(
        draw_view,
        (
            "RB_PrepareSharedWorldAmbientView(",
            "RB_DrawSharedWorldAmbientPhase(",
            "CLASSIC_WORLD_AMBIENT_PHASE_PRE_FOG",
            "RB_STD_FogAllLights();",
            "RB_DrawSharedWorldAmbientPhase(",
            "CLASSIC_WORLD_AMBIENT_PHASE_POST_FOG",
        ),
        "OpenGL pre-fog/fog/post-fog split",
    )
    require(
        draw_view,
        "RB_STD_DrawShaderPasses( drawSurfs, processed, RB_DrawSurfIsPreFogMaterialPass );",
        "untouched OpenGL pre-fog classic fallback",
    )
    require(
        draw_view,
        "RB_STD_DrawShaderPasses( drawSurfs, processed, RB_DrawSurfIsPostFogMaterialPass );",
        "untouched OpenGL post-fog classic fallback",
    )


def validate_vulkan_consumer() -> None:
    backend = read("src/renderer/Vulkan/vk_Backend.cpp")
    executor = read("src/renderer/Vulkan/vk_GuiExecutor.cpp")
    handoff = braced_body(
        backend,
        "void RB_ExecuteBackEndCommands(",
        "Vulkan command handoff",
    )
    require_order(
        handoff,
        (
            "R_ClassicWorldAmbientDomain_ResetFrame();",
            "R_MaterialResourceTable_PrepareFrame(",
            "R_ClassicWorldAmbientDomain_PrepareFrame(",
        ),
        "Vulkan world-domain frame preparation",
    )

    preflight = braced_body(
        executor,
        "static bool VK_ClassicWorldAmbient_Preflight(",
        "complete Vulkan world ambient preflight",
    )
    require_order(
        preflight,
        (
            "R_ClassicWorldAmbientDomain_FindView(",
            "R_ClassicWorldAmbientDomain_ViewDraw(",
            "R_ClassicWorldAmbientDomain_DrawPass(",
            "R_ClassicWorldAmbientDomain_DrawPassTexture(",
            "VK_ClassicWorldAmbient_MapState(",
            "R_MaterialResourceTable_ResolveTextureResource(",
            "VK_GuiExecutor_GetImageDescriptor(",
            "VK_GuiExecutor_GetPipelineStrict(",
            "VK_Exec_SharedGeometryCheckpoint()",
            "VK_Exec_PrepareTriGeometryOffsets(",
            "VK_Exec_SharedGeometryCommit();",
            "prepared.ready = true;",
        ),
        "all-view Vulkan preflight before commit",
    )
    require(
        preflight,
        "VK_Exec_SharedGeometryRestore();",
        "Vulkan failed-preflight geometry rollback",
    )
    for command in ("vkCmdDraw(", "vkCmdDrawIndexed(", "vkCmdClearAttachments("):
        reject(preflight, command, "Vulkan attachment write during world preflight")

    consumer = braced_body(
        executor,
        "static void VK_ClassicWorldAmbient_DrawPhase(",
        "Vulkan shared world ambient consumer",
    )
    require_order(
        consumer,
        (
            "prepared.committed = true;",
            "vkCmdDrawIndexed(",
            "R_ClassicWorldAmbientDomain_RecordOwned(",
        ),
        "Vulkan commit, execution, and coverage ordering",
    )
    for body, context in (
        (preflight, "Vulkan sealed world preflight"),
        (consumer, "Vulkan sealed world consumer"),
    ):
        reject(body, "shaderRegisters", context)
        reject(body, "GetStage(", context)

    draw_view = braced_body(
        executor,
        "void VK_GuiExecutor_Draw3DView(",
        "Vulkan classic 3D view phase handoff",
    )
    require_order(
        draw_view,
        (
            "VK_ClassicWorldAmbient_Preflight( viewDef )",
            "for ( int pass = 0; pass < 3; pass++ )",
            "if ( pass == 1 )",
            "VK_Fog_DrawAllLights( viewDef );",
            "if ( sharedWorldAmbientOwned && pass < 2 )",
            "VK_ClassicWorldAmbient_DrawPhase(",
            "pass == 0",
            "CLASSIC_WORLD_AMBIENT_PHASE_PRE_FOG",
            "CLASSIC_WORLD_AMBIENT_PHASE_POST_FOG",
            "continue;",
        ),
        "Vulkan preflight/pre-fog/fog/post-fog split",
    )
    require(
        draw_view,
        "VK_Exec_DrawAmbientStages( viewDef, drawSurf, tri, mvp, true );",
        "untouched Vulkan classic ambient fallback",
    )


def validate_control_and_evidence() -> None:
    init = read("src/renderer/RenderSystem_init.cpp")
    bootstrap = read("src/renderer/RendererBootstrap.cpp")
    benchmark = read("tools/tests/renderer_gameplay_benchmark.py")
    baseline = read("tools/validation/stock_asset_baseline.py")
    validation_matrix = read("tools/tests/renderer_validation_matrix.py")
    require(
        init,
        'idCVar r_rendererSharedWorldAmbient( "r_rendererSharedWorldAmbient", "0"',
        "default-off shared world ambient control",
    )
    require(
        bootstrap,
        '{ "r_rendererSharedWorldAmbient", &r_rendererSharedWorldAmbient, 0 }',
        "renderer bootstrap safety expectation",
    )
    require(bootstrap, "sharedWorldAmbient=%d", "renderer bootstrap safety report")
    require(
        benchmark,
        'append_set(args, "r_rendererSharedWorldAmbient", "0")',
        "benchmark launch isolation",
    )
    require(
        benchmark,
        '"r_rendererSharedWorldAmbient 0"',
        "benchmark capture-script isolation",
    )
    require(benchmark, '"sp-mv2-ambient":', "stock world-ambient gameplay case")
    world_ambient_profile = braced_body(
        benchmark,
        '"world-ambient":',
        "world-ambient gameplay profile",
    )
    for token, context in (
        ('("ui_showGun", "0")', "view-model isolation"),
        ('("g_showHud", "0")', "root-HUD isolation"),
        ('("r_multiSamples", "0")', "direct swapchain ownership isolation"),
        ('("g_renderFastNoPost", "1")', "fast no-post selection"),
        ('("g_renderFastNoPostDirect", "1")', "direct no-post selection"),
        ('("r_postAA", "0")', "post-AA isolation"),
        ('("r_singleLight", "2147483647")', "interaction-light isolation"),
        ('("r_skipSubviews", "1")', "subview isolation"),
        ('("r_useLightGrid", "0")', "light-grid isolation"),
        ('("r_skipPlayerVisibilityEffects", "1")', "player-overlay isolation"),
        ('("r_portalsDistanceCull", "0")', "portal-fade isolation"),
        ('("r_forceAmbient", "0")', "forced-ambient isolation"),
        ('("r_celShading", "0")', "cel-shading isolation"),
        ('("r_celShadingWorld", "0")', "world cel-shading isolation"),
        ('("r_showOverDraw", "0")', "overdraw diagnostic isolation"),
        ('("r_singleTriangle", "0")', "single-triangle diagnostic isolation"),
        ('("r_skipAmbient", "0")', "ambient ownership retention"),
        ('("r_skipNewAmbient", "0")', "new-ambient ownership retention"),
        ('("r_skipDeforms", "0")', "deform rollback retention"),
        ('("r_skipRender", "0")', "normal rendering retention"),
        ('"noclip"', "fixed world-ambient camera lock"),
        ('"setviewpos 0 0 256 80 0 0"', "fixed world-ambient camera pose"),
    ):
        require(world_ambient_profile, token, context)
    for token in (
        'g_stopTime',
        'r_skipGuiShaders',
        'r_skipPostProcess',
    ):
        reject(world_ambient_profile, token, "world-ambient gameplay profile")
    require(
        baseline,
        'add_set(args, "r_rendererSharedWorldAmbient", 0)',
        "stock baseline launch isolation",
    )
    require(
        baseline,
        '"r_rendererSharedWorldAmbient 0"',
        "stock baseline capture-script isolation",
    )
    require(
        init,
        "RendererClassicWorldAmbientDomain_RunSelfTest()",
        "registered world ambient domain self-test",
    )
    require(
        init,
        'cmdSystem->AddCommand( "rendererClassicWorldAmbientDomainSelfTest"',
        "world ambient self-test command",
    )
    require(
        init,
        "R_ClassicWorldAmbientDomain_Stats()",
        "gfx-info world ambient diagnostics",
    )
    require(
        init,
        "Renderer shared world ambient: requested=%d prepared=%d valid=%d",
        "world ambient gfx-info marker",
    )
    require(
        validation_matrix,
        '"+rendererClassicWorldAmbientDomainSelfTest"',
        "runtime self-test validation matrix",
    )
    require(
        validation_matrix,
        '"RendererClassicWorldAmbientDomain self-test passed"',
        "runtime self-test success marker",
    )


def validate_ci_registration() -> None:
    validator = read("tools/validation/openq4_validate.py")
    commit = read(".github/workflows/commit-validation.yml")
    push = read(".github/workflows/push-verification.yml")
    if validator.count("renderer_classic_world_ambient_domain.py") != 1:
        raise AssertionError("Local validation must register this test exactly once")
    for workflow, context in (
        (commit, "commit validation workflow"),
        (push, "push verification workflow"),
    ):
        if workflow.count(TEST_PATH) != 2:
            raise AssertionError(f"{context} must compile and directly run {TEST_PATH}")
        require(workflow, f"python {TEST_PATH}", context)


def main() -> None:
    validate_world_material_table()
    validate_transactional_domain()
    validate_gl_consumer()
    validate_vulkan_consumer()
    validate_control_and_evidence()
    validate_ci_registration()
    print("renderer_classic_world_ambient_domain: ok")


if __name__ == "__main__":
    main()
