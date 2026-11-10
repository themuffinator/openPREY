#!/usr/bin/env python3
"""Regression contract for Vulkan GUI image residency during level loads."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEST_PATH = "tools/tests/renderer_vulkan_gui_residency.py"


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
            raise AssertionError(f"Expected ordered contracts in {context}: {needles!r}")
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


def validate_level_load_residency_scenario() -> None:
    session = read("src/framework/Session.cpp")
    execute_map_change = braced_body(
        session,
        "void idSessionLocal::ExecuteMapChange(",
        "map-change loading presentation",
    )
    require_order(
        execute_map_change,
        (
            "renderSystem->BeginLevelLoad();",
            "LoadLoadingGui( mapString );",
            "insideExecuteMapChange = true;",
            "ShowLoadingGui();",
            "renderSystem->EndLevelLoad();",
        ),
        "loading GUI lifetime around renderer level-load residency",
    )

    images = read("src/renderer/ImageManager.cpp")
    begin_level_load = braced_body(
        images,
        "void idImageManager::BeginLevelLoad()",
        "image level-load purge",
    )
    require_order(
        begin_level_load,
        (
            "insideLevelLoad = true;",
            "if ( !image->referencedOutsideLevelLoad && image->IsLoaded() )",
            "image->PurgeImage();",
        ),
        "non-persistent image purge before loading GUI drawing",
    )


def validate_vulkan_lazy_residency_contract() -> None:
    executor = read("src/renderer/Vulkan/vk_GuiExecutor.cpp")
    resident_descriptor = braced_body(
        executor,
        "static VkDescriptorSet VK_GuiExecutor_GetResidentImageDescriptor(",
        "Vulkan resident image descriptor",
    )
    require_order(
        resident_descriptor,
        (
            "if ( image == NULL )",
            "if ( !image->IsLoaded() )",
            "image->ActuallyLoadImage( true );",
            "if ( !image->IsLoaded() )",
            "VK_GuiExecutor_GetImageDescriptor( image->GetDeviceHandle() )",
        ),
        "Vulkan lazy image residency before descriptor lookup",
    )

    ambient_stages = braced_body(
        executor,
        "static void VK_Exec_DrawAmbientStages(",
        "Vulkan GUI and ambient stage drawing",
    )
    require_order(
        ambient_stages,
        (
            # native emission replaces the authored glow image before residency
            ": pStage->texture.image;",
            "VK_GuiExecutor_GetResidentImageDescriptor( stageImage )",
            "vkCmdBindDescriptorSets(",
            "vkCmdDrawIndexed(",
        ),
        "resident image binding for GUI stages",
    )

    draw_2d = braced_body(
        executor,
        "void VK_GuiExecutor_Draw2DView(",
        "Vulkan 2D view",
    )
    require(
        draw_2d,
        "VK_Exec_DrawAmbientStages( viewDef, drawSurf, tri, mvp, false );",
        "loading GUI route through resident ambient-stage binding",
    )


def validate_ci_registration() -> None:
    validator = read("tools/validation/openq4_validate.py")
    commit = read(".github/workflows/commit-validation.yml")
    push = read(".github/workflows/push-verification.yml")

    if validator.count("renderer_vulkan_gui_residency.py") != 1:
        raise AssertionError(
            "Local validation must register the Vulkan GUI residency test exactly once"
        )
    for workflow, context in (
        (commit, "commit validation workflow"),
        (push, "push verification workflow"),
    ):
        if workflow.count(TEST_PATH) != 2:
            raise AssertionError(f"{context} must compile and directly run {TEST_PATH}")
        require(workflow, f"python {TEST_PATH}", context)


def main() -> None:
    validate_level_load_residency_scenario()
    validate_vulkan_lazy_residency_contract()
    validate_ci_registration()
    print("renderer_vulkan_gui_residency: ok")


if __name__ == "__main__":
    main()
