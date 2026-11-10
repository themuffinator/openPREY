#!/usr/bin/env python3
"""rendererVkProbe must not reload the Vulkan module while it is the active renderer.

The console command loads renderer-vk, calls its GetRenderAPI, runs the
bring-up probe, then calls the module's Shutdown and unloads it. While Vulkan is
the active renderer that load returns the live module instance -- LoadLibrary
and dlopen only raise its reference count -- so the sequence would re-run
idLib::Init under the running renderer, then free its SIMD processor and clear
its dict string pools while the renderer still uses both, and let the probe's
throwaway instance and device repoint volk's function pointers away from the
live device. The loader has to refuse before it loads anything.
"""

from __future__ import annotations

from pathlib import Path
from copy import deepcopy
from unittest.mock import Mock, patch

import renderer_validation_matrix as matrix
import renderer_vulkan_hdr_gameplay as hdr_gameplay
import renderer_hdr_highlights as hdr_highlights


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def braced_block(source: str, marker: str) -> str:
    """The marker through the end of the first brace-balanced block after it."""
    start = source.find(marker)
    if start == -1:
        raise AssertionError(f"Missing {marker!r}")

    depth = 0
    for index in range(source.index("{", start), len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]

    raise AssertionError(f"Could not find the end of the block after {marker!r}")


def validate_probe_refuses_active_vulkan() -> None:
    loader = read("src/renderer/RendererModule.cpp")
    context = "R_RendererModule_RunVulkanProbe"
    probe = braced_block(loader, "bool R_RendererModule_RunVulkanProbe( bool verbose ) {")

    guard = braced_block(
        probe,
        "if ( rm_state.interfacesPublished && rm_state.status.activeApi == RENDER_MODULE_API_VULKAN ) {",
    )
    require(guard, "rendererVkProbe: the Vulkan renderer is active", f"{context} active-Vulkan refusal")
    require(guard, "return false;", f"{context} active-Vulkan refusal")

    # The load itself hands back the live instance, and GetRenderAPI and
    # Shutdown then run against it, so every one of them has to sit behind
    # the refusal.
    guard_end = probe.index(guard) + len(guard)
    for token in (
        "Sys_DLL_Load( modulePath )",
        "GetRenderAPI( &moduleImport )",
        "moduleExport->Shutdown();",
        "RM_UnloadModuleBinary( handle, completions );",
    ):
        position = probe.find(token)
        if position == -1:
            raise AssertionError(f"Missing {token!r} in {context}")
        if position < guard_end:
            raise AssertionError(f"{token!r} runs before the active-Vulkan refusal in {context}")


def validate_runtime_gate() -> None:
    """Required Vulkan coverage cannot pass by omission or disabled layers."""
    cases = matrix.build_safe_cases(("auto",))
    for case in matrix.build_safe_cases(("auto", "gl33", "gl43", "gl45")):
        args = case["args"]
        expected = "vulkan" if case["id"].startswith("renderer-vk-") else "gl"
        selections = [args[i + 1] for i, arg in enumerate(args[:-1]) if arg == "r_renderApi"]
        if selections != [expected]:
            raise AssertionError(f"{case['id']} depends on an automatic or inherited backend: {selections}")
    startup = next(case for case in cases if case["id"] == "renderer-vk-clear-startup")
    fallback = next(case for case in cases if case["id"] == "renderer-vk-device-fallback-drill")
    runtime = ROOT / ".tmp" / "unused-vulkan-probe-test"
    suffix = ".exe" if matrix.os.name == "nt" else ""
    expected_client = runtime / f"openQ4-client_{matrix.host_arch()}{suffix}"
    with patch.object(Path, "exists", autospec=True, side_effect=lambda path: path == expected_client):
        if matrix.find_client_executable(runtime) != expected_client:
            raise AssertionError("runtime override selected a client from another package")
    savepath = ROOT / ".tmp" / "unused-vulkan-probe-evidence"
    args = matrix.common_args(runtime, "probe", "", savepath, True)
    if args[args.index("fs_devpath") + 1] != str(savepath):
        raise AssertionError("runtime checks write generated files into the tested package")
    module = Mock()
    with patch.object(matrix, "vk_module_path", return_value=module):
        module.is_file.return_value = True
        with patch.object(matrix.sys, "platform", "linux"):
            if matrix.filter_vulkan_module_cases([startup, fallback], runtime) != [startup, fallback]:
                raise AssertionError("Linux Vulkan cases were silently excluded")
            matrix.validate_case_prerequisites([startup, fallback], runtime)
        module.is_file.return_value = False
        try:
            matrix.validate_case_prerequisites([startup], runtime)
        except ValueError as exc:
            if "required Vulkan module is missing" not in str(exc):
                raise
        else:
            raise AssertionError("a required missing Vulkan module did not fail the gate")

    try:
        matrix.validate_case_prerequisites([], runtime)
    except ValueError:
        pass
    else:
        raise AssertionError("an empty runtime suite passed")

    complete_log = "\n".join(alternatives[0] for alternatives in startup["checks"])
    if not matrix.evaluate_checks(complete_log, startup["checks"], {})[0]:
        raise AssertionError("complete Vulkan startup evidence was rejected")
    validated = "Vulkan: validation enabled (VK_LAYER_KHRONOS_validation, debug messenger active)"
    without_layers = complete_log.replace(validated, "Vulkan: requested validation is not active")
    if matrix.evaluate_checks(without_layers, startup["checks"], {})[0]:
        raise AssertionError("startup without active validation passed as validated")
    mrt_marker = "Vulkan MRT self-test passed (draws, mixed formats, blend masks, load, cube faces, MSAA resolves, resize and rejection)"
    if [mrt_marker] not in startup["checks"]:
        raise AssertionError("Vulkan startup no longer requires the GPU MRT exercise")
    if matrix.evaluate_checks(complete_log.replace(mrt_marker, ""), startup["checks"], {})[0]:
        raise AssertionError("startup without MRT evidence passed")

    probe_source_marker = "Vulkan probe source self-test passed (GPU cube readback, face orientation, sRGB/HDR, upload/reload generations and rejection)"
    if [probe_source_marker] not in startup["checks"]:
        raise AssertionError("Vulkan startup no longer requires real GPU probe source reads")
    if matrix.evaluate_checks(complete_log.replace(probe_source_marker, ""), startup["checks"], {})[0]:
        raise AssertionError("startup without probe source evidence passed")

    source_case = next(case for case in cases if case["id"] == "renderer-vk-probe-source-lifecycle")
    source_markers = source_case["orderedLogChecks"]
    if matrix.evaluate_ordered_log_checks("\n".join(source_markers), source_markers):
        raise AssertionError("complete probe source lifecycle evidence rejected")
    for index in range(len(source_markers)):
        incomplete = "\n".join(source_markers[:index] + source_markers[index + 1:])
        if not matrix.evaluate_ordered_log_checks(incomplete, source_markers):
            raise AssertionError("incomplete probe source lifecycle evidence accepted")
    if "vid_restart partial failed" not in source_case["absent"]:
        raise AssertionError("partial restart falling back to full could masquerade as partial coverage")
    for workflow in ("push-verification.yml", "commit-validation.yml"):
        require(read(f".github/workflows/{workflow}"), source_case["id"], f"{workflow} required probe source coverage")

    hdr = next(case for case in cases if case["id"] == "renderer-vk-hdr-selftest")
    hdr_log = "\n".join(alternatives[0] for alternatives in hdr["checks"])
    if not matrix.evaluate_checks(hdr_log, hdr["checks"], {})[0]:
        raise AssertionError("complete HDR runtime evidence was rejected")
    for marker in (validated, hdr["checks"][-1][0]):
        if matrix.evaluate_checks(hdr_log.replace(marker, ""), hdr["checks"], {})[0]:
            raise AssertionError("HDR without real GPU fixture/validation evidence passed")
    for workflow in ("push-verification.yml", "commit-validation.yml"):
        require(read(f".github/workflows/{workflow}"), hdr["id"], f"{workflow} required HDR coverage")
    restarted = "\n".join(hdr["orderedLogChecks"])
    if matrix.evaluate_ordered_log_checks(restarted, hdr["orderedLogChecks"]):
        raise AssertionError("complete HDR device-restart sequence rejected")
    if not matrix.evaluate_ordered_log_checks(hdr["orderedLogChecks"][0], hdr["orderedLogChecks"]):
        raise AssertionError("HDR without post-restart GPU evidence passed")

    motion = next(case for case in cases if case["id"] == "renderer-vk-temporal-motion-selftest")
    motion_log = "\n".join(alternatives[0] for alternatives in motion["checks"])
    if not matrix.evaluate_checks(motion_log, motion["checks"], {})[0]:
        raise AssertionError("complete rigid motion GPU evidence rejected")
    for marker in (validated, motion["checks"][-1][0]):
        if matrix.evaluate_checks(motion_log.replace(marker, ""), motion["checks"], {})[0]:
            raise AssertionError("rigid motion without GPU/validation evidence passed")
    if matrix.evaluate_ordered_log_checks("\n".join(motion["orderedLogChecks"]), motion["orderedLogChecks"]):
        raise AssertionError("complete rigid motion restart sequence rejected")
    if not matrix.evaluate_ordered_log_checks(motion["orderedLogChecks"][0], motion["orderedLogChecks"]):
        raise AssertionError("rigid motion without a post-restart exercise passed")
    for workflow in ("push-verification.yml", "commit-validation.yml"):
        require(read(f".github/workflows/{workflow}"), motion["id"], f"{workflow} required rigid motion coverage")


def validate_recovery_gate() -> None:
    cases = {case["id"]: case for case in matrix.build_safe_cases(("auto",))}
    for stage in ("window", "surface", "swapchain", "resources"):
        case_id = f"renderer-vk-{stage}-recovery"
        case = cases[case_id]
        markers = case["orderedLogChecks"]
        complete = "\n".join(markers)
        if matrix.evaluate_ordered_log_checks(complete, markers):
            raise AssertionError(f"complete recovery sequence rejected: {case_id}")
        for missing in markers:
            if not matrix.evaluate_ordered_log_checks(complete.replace(missing, ""), markers):
                raise AssertionError(f"missing recovery evidence accepted: {case_id}: {missing}")
        premature_gl = markers.copy()
        premature_gl[1], premature_gl[4] = premature_gl[4], premature_gl[1]
        if not matrix.evaluate_ordered_log_checks("\n".join(premature_gl), markers):
            raise AssertionError(f"OpenGL before teardown accepted: {case_id}")
        if not case["requiresVulkanModule"] or not case["preservesConfig"]:
            raise AssertionError(f"recovery drill lost isolation/prerequisites: {case_id}")
        for workflow in ("push-verification.yml", "commit-validation.yml"):
            source = read(f".github/workflows/{workflow}")
            require(source, case_id, f"{workflow} required recovery coverage")


def validate_hdr_gameplay_gate() -> None:
    # Regression cases from real runs: requested MP MSAA stayed single-sample,
    # a cheat-protected readback toggle never took effect, and hidden restarts
    # silently used the desktop extent. A clean exit cannot qualify these.
    states = {}
    for name, fmt, extent, generation in (
        ("initial", "RGBA16F", "1280x720", 1),
        ("after_capture", "RGBA16F", "1280x720", 1),
        ("ldr", "LDR", "1280x720", 2),
        ("scaled", "RGBA16F", "960x540", 3),
        ("synchronous", "RGBA16F", "960x540", 3),
        ("resized", "RGBA16F", "1024x640", 1),
        ("partial", "RGBA16F", "960x600", 2),
        ("manual", "RGBA16F", "960x600", 3),
        ("disabled", "LDR", "960x600", 4),
    ):
        active = name not in ("manual", "disabled")
        states[name] = {"sceneFormat": fmt, "extent": extent, "samples": "4",
                        "generation": str(generation), "async": "0" if name == "synchronous" else "1",
                        "autoExposure": str(int(active)), "initialized": str(int(active)),
                        "average": "0.125", "target": "1.44", "exposure": "1.4",
                        "queued": "30", "completed": "29", "skyPreserved": str(int(name != "disabled"))}
    if hdr_gameplay.validate_states(states, 4, "sp"):
        raise AssertionError("complete HDR gameplay sequence rejected")
    for checkpoint, field, value in (
        ("initial", "samples", "0"),
        ("scaled", "skyPreserved", "0"),
        ("disabled", "samples", "0"),
        ("synchronous", "async", "1"),
        ("resized", "extent", "2560x1440"),
        ("partial", "generation", "1"),
        ("after_capture", "exposure", "1.5"),
        ("initial", "average", "nan"),
        ("scaled", "completed", "0"),
    ):
        broken = deepcopy(states)
        broken[checkpoint][field] = value
        if not hdr_gameplay.validate_states(broken, 4, "sp"):
            raise AssertionError(f"invalid HDR gameplay evidence accepted: {checkpoint}.{field}={value}")
    del states["manual"]
    if not hdr_gameplay.validate_states(states, 4):
        raise AssertionError("missing HDR gameplay checkpoint accepted")

    motion_log = "\n".join(f"HDR_MOTION_START_{name}\nVulkan temporal motion: frame=240 generation=1 "
                           "eligible=10 drawn=10 complete=1 completedViews=30\n"
                           f"HDR_CHECK_{name}\nTemporal presentation: taaRequested=1 frame=300 historyGeneration=2\n"
                           "Vulkan temporal motion: frame=300 generation=2 "
                           "eligible=10 drawn=10 complete=1 completedViews=90"
                           for name in ("scaled", "resized", "partial"))
    if hdr_gameplay.validate_temporal_motion(motion_log)[1]:
        raise AssertionError("complete rigid motion gameplay rejected")
    # Correctly rejected current history does not erase successful interval draws.
    cut_log = motion_log.replace("eligible=10 drawn=10 complete=1", "eligible=0 drawn=0 complete=0")
    if hdr_gameplay.validate_temporal_motion(cut_log)[1]:
        raise AssertionError("safe history rejection after completed interval draws was rejected")
    for old, new in (("eligible=10", "eligible=0"), ("drawn=10", "drawn=9"),
                     ("complete=1", "complete=2"), ("completedViews=90", "completedViews=30"),
                     ("taaRequested=1", "taaRequested=0"), ("historyGeneration=2", "historyGeneration=1"),
                     ("frame=300", "frame=-1"), ("generation=2", "generation=0"),
                     ("HDR_MOTION_START_scaled", "HDR_MOTION_START_missing"),
                     ("HDR_CHECK_partial", "HDR_CHECK_missing")):
        if not hdr_gameplay.validate_temporal_motion(motion_log.replace(old, new))[1]:
            raise AssertionError(f"missing/invalid rigid motion gameplay accepted: {new}")


def validate_highlight_capture_gate() -> None:
    captures = {name: {"sha256": str(i)} for i, (name, _) in enumerate(hdr_highlights.CONTROLS)}
    for name in ("pbr_enabled", "pbr_restored"):
        captures[name] = captures["auto"].copy()
    captures["restored"] = captures["manual1"].copy()
    sky = {"changedChannels": 0, "greenStdDev": 12, "nearWhiteFraction": 0}
    if hdr_highlights.validate_controls(captures, sky):
        raise AssertionError("complete HDR highlight evidence rejected")
    for key, value in (("changedChannels", 100), ("greenStdDev", 0), ("nearWhiteFraction", 1)):
        if not hdr_highlights.validate_controls(captures, {**sky, key: value}):
            raise AssertionError(f"invalid portal-sky comparison accepted: {key}")
    for name in ("pbr_enabled", "pbr_restored", "restored"):
        broken = deepcopy(captures)
        broken[name]["sha256"] = "changed"
        if not hdr_highlights.validate_controls(broken, sky):
            raise AssertionError(f"broken HDR/PBR restoration accepted: {name}")
    # Distinct rows AND columns expose both TGA origin flags independently.
    pixels = (bytes([1,2,3]), bytes([4,5,6]), bytes([7,8,9]), bytes([10,11,12]))
    for descriptor, order in ((32,(0,1,2,3)), (0,(2,3,0,1)), (48,(1,0,3,2)), (16,(3,2,1,0))):
        raw = b"".join(pixels[i] for i in order)
        if hdr_highlights.extract_patch(raw, 2, 2, descriptor, (0,0,1,1)) != pixels[0]:
            raise AssertionError(f"TGA origin {descriptor} changed the selected sky patch")


def validate_probe_admission_wiring() -> None:
    source = read("src/renderer/Vulkan/VulkanBringup.cpp")
    probe = braced_block(source, "static bool VK_Bringup_RunProbeInternal(")
    selection = probe.index("result = VK_SelectProbeDevice(")
    creation = probe.index("result = vkCreateDevice(")
    failure = braced_block(probe[selection:creation], "if ( result != VK_SUCCESS )")
    require(failure, "break;", "failed probe must stop before logical device creation")
    require(probe, "probeApi.getMemoryProperties = vkGetPhysicalDeviceMemoryProperties;", "probe dispatch wiring")
    require(probe, "if ( selected.hasPortabilitySubset )", "probe uses its complete extension inventory")
    require(probe, "const int overrideIndex = VK_CVarGetInteger( \"r_vkDevice\" );", "explicit probe selection")
    for obsolete in ("physicalDevices[ 16 ]", "deviceInfos[ 16 ]", "using automatic selection", "VK_Bringup_DeviceExtensionSupported"):
        if obsolete in source:
            raise AssertionError(f"Obsolete probe enumeration/override path remains: {obsolete}")
    portability = braced_block(source, "static void VK_Bringup_ReportPortability(")
    guard13 = braced_block(portability, "if ( info.props.apiVersion >= VK_API_VERSION_1_3 )")
    guard12 = braced_block(portability, "if ( info.props.apiVersion >= VK_API_VERSION_1_2 )")
    require(guard13, "vkGetPhysicalDeviceFormatProperties2(", "version-aware format diagnostics")
    require(guard12, "vkGetPhysicalDeviceProperties2(", "version-aware resolve diagnostics")
    selector = read("src/renderer/Vulkan/VulkanDeviceSelection.cpp")
    for marker in ("VkResult CheckCandidate(", "VkResult QueryProbeDevice("):
        require(braced_block(selector, marker), "CheckDeviceLimits(", "shared renderer/probe capability floor")


def main() -> None:
    validate_probe_admission_wiring()
    validate_probe_refuses_active_vulkan()
    validate_runtime_gate()
    validate_recovery_gate()
    validate_hdr_gameplay_gate()
    validate_highlight_capture_gate()
    print("renderer_vulkan_probe_safety: ok")


if __name__ == "__main__":
    main()
