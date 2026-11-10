#!/usr/bin/env python3
"""Static regression contract for atomic shared classic fog/blend ownership."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEST_PATH = "tools/tests/renderer_classic_fog_blend_domain.py"


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def reject(haystack: str, needle: str, context: str) -> None:
    if needle in haystack:
        raise AssertionError(f"Unexpected {needle!r} in {context}")


def require_any(haystack: str, needles: tuple[str, ...], context: str) -> None:
    if not any(needle in haystack for needle in needles):
        raise AssertionError(f"Missing one of {needles!r} in {context}")


def braced_body(source: str, marker: str, context: str) -> str:
    start = source.find(marker)
    if start == -1:
        raise AssertionError(f"Missing {marker!r} in {context}")
    opening = source.find("{", start + len(marker))
    if opening == -1:
        raise AssertionError(f"Missing opening brace after {marker!r} in {context}")
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Could not find closing brace for {marker!r} in {context}")


def preflight_bodies(source: str, context: str) -> list[str]:
    markers = re.findall(
        r"(?:static\s+)?bool\s+([A-Za-z0-9_]*FogBlend[A-Za-z0-9_]*Preflight[A-Za-z0-9_]*)\s*\(",
        source,
    )
    return [braced_body(source, f"{name}(", context) for name in markers]


def validate_domain_contract() -> None:
    header = read("src/renderer/ClassicFogBlendDomain.h")
    source = read("src/renderer/ClassicFogBlendDomain.cpp")
    combined = header + source

    for token in (
        "CLASSIC_FOG_BLEND_LIGHT_FOG",
        "CLASSIC_FOG_BLEND_LIGHT_BLEND",
        "CLASSIC_FOG_BLEND_RECEIVER_GLOBAL",
        "CLASSIC_FOG_BLEND_RECEIVER_LOCAL",
        "CLASSIC_FOG_BLEND_PRIMITIVE_FOG_RECEIVER",
        "CLASSIC_FOG_BLEND_BACKEND_GL",
        "CLASSIC_FOG_BLEND_BACKEND_VULKAN",
        "R_ClassicFogBlendDomain_ResetFrame",
        "R_ClassicFogBlendDomain_PrepareFrame",
        "R_ClassicFogBlendDomain_Stats",
        "R_ClassicFogBlendDomain_NumViews",
        "R_ClassicFogBlendDomain_ViewByIndex",
        "R_ClassicFogBlendDomain_ViewForScenePacket",
        "R_ClassicFogBlendDomain_FindView",
        "R_ClassicFogBlendDomain_ViewLight",
        "R_ClassicFogBlendDomain_LightStage",
        "R_ClassicFogBlendDomain_ViewPrimitive",
        "R_ClassicFogBlendDomain_ResolveTexture",
        "R_ClassicFogBlendDomain_RecordOwned",
        "R_ClassicFogBlendDomain_RecordBackendFallback",
        "R_ClassicFogBlendDomain_BackendCoverage",
        "ClassicFogBlendDomainLightKind_Name",
        "ClassicFogBlendDomainReceiver_Name",
        "ClassicFogBlendDomainPrimitiveKind_Name",
        "ClassicFogBlendDomainFailure_Name",
        "ClassicFogBlendDomainBackend_Name",
    ):
        require(combined, token, "shared fog/blend domain API")
    require_any(
        header,
        (
            "CLASSIC_FOG_BLEND_PRIMITIVE_FOG_FRUSTUM_CAP",
            "CLASSIC_FOG_BLEND_PRIMITIVE_FOG_CAP",
        ),
        "sealed fog frustum-cap primitive",
    )
    require_any(
        header,
        (
            "CLASSIC_FOG_BLEND_PRIMITIVE_BLEND_RECEIVER",
            "CLASSIC_FOG_BLEND_PRIMITIVE_BLEND_DRAW",
        ),
        "sealed blend receiver primitive",
    )

    prepare = braced_body(
        source,
        "R_ClassicFogBlendDomain_PrepareFrame(",
        "atomic fog/blend frame preparation",
    )
    for token in (
        "R_ClassicFogBlendDomain_ResetFrame();",
        "PrepareView(",
        "frameValid",
    ):
        require(prepare, token, "atomic fog/blend frame preparation")

    for token in (
        "IsFogLight()",
        "IsBlendLight()",
        "globalInteractions",
        "localInteractions",
        "frustumTris",
        "conditionRegister",
        "drawStateBits",
        "falloff",
        "texture",
        "ready = true",
        "ready = false",
        "fallbackViews",
        "CLASSIC_FOG_BLEND_LIGHT_NOOP_MISSING_GLOBAL_CHAIN",
        "CLASSIC_FOG_BLEND_LIGHT_NOOP_SKIP_BLEND",
        "ValidateDrawPacketIdentity",
        "noopBlend",
    ):
        require(source, token, "sealed ordered fog/blend semantic snapshot")
    require_any(source, ("semanticHash", "SemanticHash", "Hash"), "semantic hash")
    require_any(
        source,
        ("DEFAULT_FOG_DISTANCE", "defaultFogDistance", "fogDistance"),
        "fog distance semantics",
    )
    require_any(
        source,
        ("FOG_ENTER", "fogEnter", "viewInsideLight"),
        "fog-entry/cap semantics",
    )


def validate_scene_packet_identity() -> None:
    header = read("src/renderer/ScenePackets.h")
    source = read("src/renderer/ScenePackets.cpp")
    for token in (
        "sceneFogBlendReceiverClass_t",
        "SCENE_FOG_BLEND_RECEIVER_GLOBAL",
        "SCENE_FOG_BLEND_RECEIVER_LOCAL",
        "fogBlendLight",
        "fogBlendLightOrdinal",
        "fogBlendReceiverOrdinal",
        "fogBlendSourceOrdinal",
        "fogBlendReceiverClass",
        "AddFogBlendDrawPacket",
    ):
        require(header, token, "authoritative fog/blend packet identity")
    append = braced_body(
        source,
        "R_ScenePackets_AppendFogBlendChain(",
        "ordered fog/blend packet chain",
    )
    require(append, "AddFogBlendDrawPacket(", "dedicated fog/blend packet append")
    fog_pass = braced_body(
        source,
        "R_ScenePackets_AddFogBlendPass(",
        "global-to-local fog/blend source order",
    )
    global_at = fog_pass.find("globalInteractions")
    local_at = fog_pass.find("localInteractions")
    if global_at == -1 or local_at <= global_at:
        raise AssertionError("Fog/blend packets must preserve global-to-local order")
    classifier = braced_body(
        source,
        "R_ScenePackets_ViewLightIsFogOrBlend(",
        "unfiltered fog/blend packet identity",
    )
    reject(classifier, "r_skipFogLights", "unfiltered fog/blend packet identity")
    reject(classifier, "r_skipBlendLights", "unfiltered fog/blend packet identity")


def validate_backend_transactions() -> None:
    gl = read("src/renderer/draw_common.cpp") + read("src/renderer/tr_backend.cpp")
    vk = (
        read("src/renderer/Vulkan/vk_Backend.cpp")
        + read("src/renderer/Vulkan/vk_GuiExecutor.cpp")
        + read("src/renderer/Vulkan/vk_Interactions.cpp")
    )
    for source, backend, draw_token in (
        (gl, "GL", "RB_DrawElementsWithCounters"),
        (vk, "Vulkan", "vkCmdDrawIndexed"),
    ):
        for token in (
            "R_ClassicFogBlendDomain_FindView",
            "R_ClassicFogBlendDomain_RecordOwned",
            "R_ClassicFogBlendDomain_RecordBackendFallback",
        ):
            require(source, token, f"{backend} fog/blend ownership transaction")
        bodies = preflight_bodies(source, f"{backend} fog/blend preflight")
        if not bodies:
            raise AssertionError(f"Missing fog/blend preflight in {backend} backend")
        for body in bodies:
            reject(body, draw_token, f"draw-free {backend} fog/blend preflight")
            reject(body, "RecordOwned", f"uncommitted {backend} preflight")

    for token in ("RB_STD_FogAllLights", "RB_FogPass", "RB_BlendLight"):
        require(gl, token, "GL legacy rollback and fog/blend semantics")
    for token in ("VK_Fog_DrawAllLights", "VK_Fog_DrawFogLight", "VK_Fog_DrawBlendLight"):
        require(vk, token, "Vulkan legacy rollback and fog/blend semantics")

    handoff = read("src/renderer/tr_backend.cpp")
    require(
        handoff,
        "R_ClassicFogBlendDomain_ResetFrame();",
        "backend-frame reset",
    )
    require(
        handoff,
        "R_ClassicFogBlendDomain_PrepareFrame( *scenePackets );",
        "packet-derived backend handoff",
    )


def validate_controls_diagnostics_and_build() -> None:
    init = read("src/renderer/RenderSystem_init.cpp")
    local = read("src/renderer/tr_local.h")
    meson = read("meson.build")
    source_discovery = read("tools/build/meson_sources.py")
    for token in (
        'r_rendererSharedWorldFogBlend( "r_rendererSharedWorldFogBlend", "0"',
        '"rendererClassicFogBlendDomainSelfTest"',
        "RendererClassicFogBlendDomain self-test passed",
        "classicFogBlendDomain requested=",
        "classicFogBlendDomain backend=",
        "noopLights=%d",
        "ownedNoopStages=%d",
        "ownedNoopLights=%d",
    ):
        require(init, token, "default-off control, self-test, and diagnostics")
    require(local, "extern idCVar r_rendererSharedWorldFogBlend;", "renderer cvar API")
    require(meson, "meson_sources.py", "renderer Meson source discovery")
    require(
        source_discovery,
        '"renderer/*.cpp"',
        "renderer source glob includes ClassicFogBlendDomain.cpp",
    )

    bootstrap = read("src/renderer/RendererBootstrap.cpp")
    require(bootstrap, "sharedWorldFogBlend", "bootstrap default-off diagnostics")


def validate_tooling_registration() -> None:
    benchmark = read("tools/tests/renderer_gameplay_benchmark.py")
    baseline = read("tools/validation/stock_asset_baseline.py")
    baseline_test = read("tools/tests/stock_asset_baseline.py")
    matrix = read("tools/tests/renderer_validation_matrix.py")
    registry = read("tools/validation/openq4_validate.py")
    for token in (
        '"fog-blend"',
        '"sp-mv2-fog-blend"',
        '"r_rendererSharedWorldFogBlend", "1"',
        "lights/fog_generic",
        "lights/fog_ambient",
        "classicFogBlendDomain requested=",
        "classicFogBlendDomain backend=",
        '"owned-skip-blend"',
        'spec.fog_blend_expectation in ("owned", "owned-skip-blend")',
        '"sharedFogBlendViews"',
    ):
        require(benchmark, token, "controlled stock fog/blend profile")
    for source, context in (
        (benchmark, "benchmark default isolation"),
        (baseline, "stock baseline default isolation"),
        (baseline_test, "stock baseline unit contract"),
    ):
        require(source, "r_rendererSharedWorldFogBlend", context)
    for token in (
        "rendererClassicFogBlendDomainSelfTest",
        "RendererClassicFogBlendDomain self-test passed",
        "sharedWorldFogBlend=0",
    ):
        require(matrix, token, "renderer validation matrix")
    require(
        registry,
        '"renderer_classic_fog_blend_domain.py"',
        "validation registry",
    )

    for workflow_path in (
        ".github/workflows/commit-validation.yml",
        ".github/workflows/push-verification.yml",
    ):
        workflow = read(workflow_path)
        if workflow.count(TEST_PATH) != 2:
            raise AssertionError(
                f"Expected compile and execution registration in {workflow_path}"
            )


def main() -> int:
    validate_scene_packet_identity()
    validate_domain_contract()
    validate_backend_transactions()
    validate_controls_diagnostics_and_build()
    validate_tooling_registration()
    print("renderer_classic_fog_blend_domain: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
