#!/usr/bin/env python3
"""Static regression contract for shared cinematic and authored-post ownership."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEST_PATH = "tools/tests/renderer_classic_cinematic_post_domain.py"


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def require_before(haystack: str, first: str, second: str, context: str) -> None:
    first_at = haystack.find(first)
    second_at = haystack.find(second)
    if first_at < 0 or second_at < 0 or first_at >= second_at:
        raise AssertionError(f"Expected {first!r} before {second!r} in {context}")


def function_body(source: str, signature: str, context: str) -> str:
    start = source.find(signature)
    if start < 0:
        raise AssertionError(f"Missing {signature!r} in {context}")
    opening = source.find("{", start + len(signature))
    if opening < 0:
        raise AssertionError(f"Missing opening brace for {signature!r} in {context}")
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    raise AssertionError(f"Unterminated {signature!r} in {context}")


def validate_sealed_domain() -> None:
    header = read("src/renderer/ClassicCinematicPostDomain.h")
    source = read("src/renderer/ClassicCinematicPostDomain.cpp")
    packets = read("src/renderer/ScenePackets.cpp")

    for token in (
        "CLASSIC_CINEMATIC_POST_SCOPE_ROOT_CINEMATIC",
        "CLASSIC_CINEMATIC_POST_SCOPE_AUTHORED_POST",
        "CLASSIC_CINEMATIC_POST_FAILURE_SOURCE_PACKET_MISMATCH",
        "CLASSIC_CINEMATIC_POST_FAILURE_CINEMATIC_CLOCK",
        "CLASSIC_CINEMATIC_POST_FAILURE_MISSING_SPECIAL_VIEW",
        "CLASSIC_CINEMATIC_POST_FAILURE_SPECIAL_VIEW_TRANSACTION_REJECTED",
        "CLASSIC_CINEMATIC_POST_FAILURE_BACKEND_COVERAGE_MISMATCH",
        "classicCinematicPostDomainView_t",
        "specialRootViewDef",
        "specialRootScenePacketIndex",
        "specialNestingDepth",
        "nestedInSpecialView",
        "backendCompleted",
        "cinematicTimeMilliseconds",
        "currentRenderStageCount",
        "currentDepthStageCount",
        "R_ClassicCinematicPostDomain_PrepareFrame",
        "R_ClassicCinematicPostDomain_RecordOwned",
        "R_ClassicCinematicPostDomain_RecordBackendFallback",
        "R_ClassicCinematicPostDomain_SubviewTransactionReady",
        "R_ClassicCinematicPostDomain_SubviewTransactionCompleted",
        "R_ClassicCinematicPostDomain_PublishSubviewTransactionOwned",
        "R_ClassicCinematicPostDomain_RecordSubviewTransactionFallback",
        "RendererClassicCinematicPostDomain_RunSelfTest",
    ):
        require(header, token, "cinematic/post domain interface")

    for token in (
        "R_ClassicCinematicPostDomain_IsRootGUIPacketEligible",
        "stage->texture.cinematic",
        "MF_NEED_CURRENT_RENDER",
        "RENDER_PASS_GUI",
        "RENDER_PASS_AUTHORED_POST",
        "SCENE_PACKET_CATEGORY_POST_PROCESS",
        "packet.legacyDrawSurf != drawSurf",
        "viewDef->floatTime",
        "cinematicClock",
        "specialRootViewDef",
        "nestedInSpecialView",
        "!stats.prepared || !stats.frameValid || stats.overflow",
        "R_ClassicSubviewDomain_RecordBackendFallback",
        "RecordBackendFallback",
        "R_ClassicCinematicPostDomain_RangeFits",
        "R_ClassicCinematicPostDomain_RangeContains",
        "packetFrame.NumDrawPackets()",
        "classic cinematic/post and subview GL backend ordinals must match",
        "classic cinematic/post and subview Vulkan backend ordinals must match",
        "classic cinematic/post and subview backend counts must match",
    ):
        require(source, token, "sealed source, timing, and fallback handling")
    completed = function_body(
        source,
        "bool R_ClassicCinematicPostDomain_SubviewTransactionCompleted(",
        "atomic nested cinematic completion",
    )
    for token in (
        "CLASSIC_CINEMATIC_POST_BACKEND_UNRECORDED",
        "backendCompleted[ backend ]",
        "backendDrawnSurfaces[ backend ] != view.sourceSurfaceCount",
    ):
        require(completed, token, "atomic nested cinematic completion")
    require_before(
        source,
        "int packetCursor = pass.firstDrawPacket;",
        "R_ClassicCinematicPostDomain_CommitView( view );",
        "root packet reconciliation before commit",
    )
    require(
        packets,
        "R_ScenePackets_AddFilteredDrawSurfPass( packetFrame, viewDef, RENDER_PASS_AUTHORED_POST",
        "authored post packet production",
    )


def validate_backend_handoffs() -> None:
    gl = read("src/renderer/draw_common.cpp")
    gl_backend = read("src/renderer/tr_backend.cpp")
    vk = read("src/renderer/Vulkan/vk_GuiExecutor.cpp")
    vk_backend = read("src/renderer/Vulkan/vk_Backend.cpp")
    subview = read("src/renderer/ClassicSubviewDomain.cpp")

    for token in (
        "RB_DrawSharedCinematicRootView",
        "RB_DrawSharedAuthoredPostView",
        "RB_STD_DrawShaderPasses",
        "R_ClassicCinematicPostDomain_RecordOwned",
        "R_ClassicCinematicPostDomain_RecordBackendFallback",
    ):
        require(gl, token, "OpenGL dynamic-stage adapter")
    root = function_body(gl, "bool RB_DrawSharedCinematicRootView(", "OpenGL root adapter")
    require(root, "RB_BeginDrawingView();", "OpenGL root view setup")
    require(root, "RB_STD_DrawShaderPasses", "OpenGL root dynamic-stage execution")
    post = function_body(gl, "bool RB_DrawSharedAuthoredPostView(", "OpenGL post adapter")
    require(post, "drawSurfs + firstSourceSurface", "OpenGL exact authored post tail")
    gl_world = function_body(gl, "RB_STD_DrawView( void )", "OpenGL world adapter")
    require_before(
        gl_world,
        "sharedAuthoredPostView->backendOutcome[",
        "RB_DrawSharedAuthoredPostView(",
        "OpenGL already-rolled-back member bypass",
    )
    require(
        gl_world,
        "CLASSIC_CINEMATIC_POST_BACKEND_UNRECORDED",
        "OpenGL already-rolled-back member bypass",
    )

    for source, backend, direct_signature in (
        (gl_backend, "OpenGL", "static void RB_DrawSharedDirectSubview("),
        (vk_backend, "Vulkan", "static void VK_DrawSharedDirectSubview("),
    ):
        require(source, "R_ClassicCinematicPostDomain_ResetFrame();", f"{backend} reset")
        require(source, "R_ClassicCinematicPostDomain_PrepareFrame( *scenePackets );", f"{backend} packet preparation")
        require_before(
            source,
            "R_ClassicSubviewDomain_PrepareFrame( *scenePackets );",
            "R_ClassicCinematicPostDomain_PrepareFrame( *scenePackets );",
            f"{backend} special topology before nested dynamic ranges",
        )
        copy_case = function_body(
            source, "case RC_COPY_RENDER:", f"{backend} copy transaction"
        )
        if copy_case.count("== CLASSIC_SUBVIEW_DOMAIN_BACKEND_UNRECORDED") < 2:
            raise AssertionError(
                f"Expected sealed-match and late-outcome guards in {backend} copy transaction"
            )
        direct = function_body(source, direct_signature, f"{backend} direct transaction")
        require_before(
            direct,
            "!= CLASSIC_SUBVIEW_DOMAIN_BACKEND_UNRECORDED",
            "R_ClassicSubviewDomain_RecordDirectOwned",
            f"{backend} late nested rollback before direct publication",
        )
    require(gl_backend, "RB_DrawSharedCinematicRootView( drawView )", "OpenGL root dispatch")

    for token in (
        "sharedCinematicRoot",
        "sharedAuthoredPostCandidate",
        "VK_Exec_DrawAmbientStages",
        "R_ClassicCinematicPostDomain_RecordOwned",
        "R_ClassicCinematicPostDomain_RecordBackendFallback",
    ):
        require(vk, token, "Vulkan dynamic-stage adapter")
    fallback = function_body(
        vk,
        "static void VK_RecordCinematicPostFallbackIfPending(",
        "Vulkan pending-outcome fallback",
    )
    for token in (
        "CLASSIC_CINEMATIC_POST_BACKEND_UNRECORDED",
        "backendCompleted[CLASSIC_CINEMATIC_POST_BACKEND_VULKAN]",
        "R_ClassicCinematicPostDomain_RecordBackendFallback",
    ):
        require(fallback, token, "Vulkan pending-outcome fallback")
    vk_root = function_body(vk, "void VK_GuiExecutor_Draw2DView(", "Vulkan root adapter")
    for token in (
        "VK_RecordCinematicPostFallbackIfPending",
        "VK_CLASSIC_CINEMATIC_POST_REJECT_VIEWPORT",
    ):
        require(vk_root, token, "Vulkan root early-return accounting")
    vk_world = function_body(vk, "void VK_GuiExecutor_Draw3DView(", "Vulkan world adapter")
    for token in (
        "VK_CLASSIC_CINEMATIC_POST_REJECT_SKIP_OR_EMPTY",
        "VK_CLASSIC_CINEMATIC_POST_REJECT_BEGIN_FRAME",
        "VK_CLASSIC_CINEMATIC_POST_REJECT_GPU_SKINNING",
        "VK_CLASSIC_CINEMATIC_POST_REJECT_VIEWPORT",
        "VK_CLASSIC_CINEMATIC_POST_REJECT_NO_POST_WALK",
        "!sharedAuthoredPostView->backendCompleted[",
    ):
        require(vk_world, token, "Vulkan authored-post outcome closure")
    if vk_world.count("VK_RecordCinematicPostFallbackIfPending") < 5:
        raise AssertionError(
            "Expected every Vulkan authored-post early/terminal exit to record fallback"
        )
    require_before(
        vk_world,
        "sharedAuthoredPostView->backendOutcome[",
        "sharedAuthoredPostReady",
        "Vulkan already-rolled-back member bypass",
    )
    require(
        vk_world,
        "CLASSIC_CINEMATIC_POST_BACKEND_UNRECORDED",
        "Vulkan already-rolled-back member bypass",
    )
    require_before(
        vk_world,
        "sharedAuthoredPostCandidate",
        "R_ClassicCinematicPostDomain_RecordOwned( viewDef,",
        "Vulkan post ownership after the complete dynamic walk",
    )
    for token in (
        "R_ClassicCinematicPostDomain_SubviewTransactionCompleted",
        "R_ClassicCinematicPostDomain_PublishSubviewTransactionOwned",
        "R_ClassicCinematicPostDomain_RecordSubviewTransactionFallback",
        "CLASSIC_SUBVIEW_DOMAIN_FAILURE_BACKEND_NESTED_CINEMATIC_POST_INCOMPLETE",
    ):
        require(subview, token, "atomic special-view/cinematic transaction coupling")


def validate_controls_and_evidence() -> None:
    init = read("src/renderer/RenderSystem_init.cpp")
    local = read("src/renderer/tr_local.h")
    bootstrap = read("src/renderer/RendererBootstrap.cpp")
    matrix = read("tools/tests/renderer_validation_matrix.py")
    benchmark = read("tools/tests/renderer_gameplay_benchmark.py")
    baseline = read("tools/validation/stock_asset_baseline.py")
    registry = read("tools/validation/openq4_validate.py")
    roadmap = read("docs/dev/archive/2026-10-18/idtech5-modernization-roadmap.md")
    domain_doc = read("docs/dev/classic-cinematic-post-domain-modernization.md")
    fixture = read("tools/tests/renderer_milestone_d_fixture.py")
    acceptance = read("tools/tests/renderer_milestone_d_acceptance.py")
    hardening = read("tools/tests/validation_hardening.py")
    workflows = (
        read(".github/workflows/commit-validation.yml"),
        read(".github/workflows/push-verification.yml"),
    )

    require(init, 'r_rendererSharedCinematicPost( "r_rendererSharedCinematicPost", "0"', "default-off cvar")
    require(init, 'cmdSystem->AddCommand( "rendererClassicCinematicPostDomainSelfTest"', "native self-test")
    require(init, "Renderer shared cinematic/post:", "gfxInfo diagnostics")
    require(init, "coverageMismatches", "cinematic/post mismatch diagnostics")
    require(init, "duplicateReports", "cinematic/post duplicate diagnostics")
    require(local, "extern idCVar r_rendererSharedCinematicPost;", "renderer cvar API")
    require(bootstrap, '{ "r_rendererSharedCinematicPost", &r_rendererSharedCinematicPost, 0 }', "default safety")
    for source, context in (
        (matrix, "safe renderer matrix"),
        (benchmark, "benchmark isolation"),
        (baseline, "stock-baseline isolation"),
    ):
        require(source, "r_rendererSharedCinematicPost", context)
    require(matrix, "+rendererClassicCinematicPostDomainSelfTest", "safe native self-test")
    require(registry, '"renderer_classic_cinematic_post_domain.py"', "validation registry")
    require(roadmap, "Milestone D scoped implementation is complete", "Milestone D completion boundary")
    for token in (
        "maps/tools/mv2.map",
        "video/idlogo.roq",
        "412fc796e569660c92dca5d55359e5c4eb3d572754bd1cdff8ce994b0b802fe2",
        "375c9641c96359c2e0d49cdd3905cc2cdc66a7b067c9a8910d80bf36fb06c8f4",
        "milestone_d_nested_dynamic.map",
        "milestoneD/nestedCinematicPost",
        "shaderDemos/transparentMirror",
        "Temporary Milestone D validation material; never shipped.",
        '"shippingContent": False',
        '"r_fullscreen", "0"',
        '"in_mouse", "0"',
        '"+dmap"',
        '"--temporary-runtime"',
        'ROOT / ".tmp/stock-runtime"',
        "is_link_or_junction",
        'for suffix in (".proc", ".cm")',
        "def stock_dependency_inventory(basepath: Path)",
        '"stockDependencies": stock_dependencies_before',
        "stock_dependencies_after = stock_dependency_inventory(basepath)",
        "if stock_dependencies_after != stock_dependencies_before:",
        "def validate_runtime_components(runtime_dir: Path)",
        '"runtimeComponents": runtime_components',
        "prepare_macos_moltenvk.sh",
        "libMoltenVK.dylib",
        "validation_map_payload(retrieved_map)",
        "timeout=timeout_seconds",
        "allow_nan=False",
    ):
        require(fixture, token, "temporary stock-derived Milestone D fixture")
    for case_block in (
        '"classic-normal",\n        "classic subview and cinematic/post paths, normal post processing",\n        0,\n        0,\n        0,',
        '"subview-only-normal",\n        "shared subview only, with cinematic/post domain disabled",\n        1,\n        0,\n        0,',
        '"cinematic-only-normal",\n        "shared cinematic/post only; nested authored post remains vacuous",\n        0,\n        1,\n        0,',
        '"both-normal",\n        "shared subview plus nested cinematic/post ownership",\n        1,\n        1,\n        0,',
        '"classic-skip",\n        "classic paths with r_skipPostProcess forced",\n        0,\n        0,\n        1,',
        '"both-skip",\n        "shared domains requested with deterministic nested post fallback",\n        1,\n        1,\n        1,',
    ):
        require(acceptance, case_block, "Milestone D six-case CVar matrix")
    for token in (
        'return ("gl", "vk") if value == "all"',
        '"milestone-d-nested-dynamic"',
        '"-B"',
        '"--pacing-only"',
        '"--no-gpu-timers"',
        '"windowed"',
        "CINEMATIC_PATTERN",
        "SUBVIEW_PATTERN",
        "SUBVIEW_BACKEND_PATTERN",
        '"classic-normal-vs-subview-only-normal"',
        '"classic-normal-vs-cinematic-only-normal"',
        '"classic-normal-vs-both-normal"',
        '"classic-skip-vs-both-skip"',
        '"classic-normal-vs-classic-skip"',
        '"both-normal-vs-both-skip"',
        "runtime_before = benchmark.collect_runtime_files(runtime_dir)",
        "runtime_after = benchmark.collect_runtime_files(runtime_dir)",
        '"--fixture-manifest"',
        "def validate_fixture_manifest(",
        "fixture_builder.stock_dependency_inventory(basepath)",
        'manifest.get("stockDependencies") != stock_dependencies',
        "fixture_builder.validate_runtime_components(runtime_dir)",
        'manifest.get("runtimeComponents") != runtime_components',
        '"manifestArtifact": {',
        "prefix_count = sum(",
        "backend_prefix_count = sum(",
        'inactive_outcome = f"{inactive_label}=0/none/0"',
        "math.isfinite(args.difference_min_rms)",
        "benchmark.evaluate_display_evidence(",
        'failures.extend(f"actual display evidence: {failure}"',
        'f"{prefix}_mismatch"',
        'f"{prefix}_duplicate"',
        "fixture_after = validate_fixture_manifest(",
        "_reject_link_ancestry",
        "allow_nan=False",
        '"screenshotSource": "engine screenshot command"',
        "REPORT_JSON_NAME",
        "REPORT_MD_NAME",
    ):
        require(acceptance, token, "Milestone D acceptance contract")
    for runtime_driver in (
        "tools/tests/renderer_milestone_d_acceptance.py",
        "tools/tests/renderer_milestone_d_fixture.py",
    ):
        require(hardening, Path(runtime_driver).name, "runtime-driver validation allowlist")
        for workflow in workflows:
            if workflow.count(runtime_driver) != 1:
                raise AssertionError(
                    f"Expected exactly one compile-only {runtime_driver!r} workflow entry"
                )
    require(benchmark, '"milestone-d-nested-dynamic"', "nested runtime benchmark profile")
    require(
        benchmark,
        '("r_rendererSharedSubview", "1")',
        "nested runtime benchmark shared subview default",
    )
    require(
        benchmark,
        '("r_rendererSharedCinematicPost", "1")',
        "nested runtime benchmark shared cinematic/post default",
    )
    for token in (
        "videoMap",
        "soundMap",
        "_currentRender",
        "r_rendererSharedCinematicPost 1",
        "classic fallback",
        "engine-written",
        "nested",
        "atomic",
    ):
        require(domain_doc, token, "domain documentation")


def main() -> int:
    validate_sealed_domain()
    validate_backend_handoffs()
    validate_controls_and_evidence()
    print("renderer_classic_cinematic_post_domain: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
