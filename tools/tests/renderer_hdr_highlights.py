#!/usr/bin/env python3
"""Opt-in, windowed stock HDR highlight and portal-sky regression captures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics

import renderer_gameplay_benchmark as gameplay
import renderer_validation_matrix as matrix

ROOT = Path(__file__).resolve().parents[2]
CONTROLS = (
    ("ldr", {"r_hdrToneMap": 0}),
    ("manual1", {"r_hdrToneMap": 1, "r_hdrExposure": 1}),
    ("manual3", {"r_hdrExposure": 3}),
    ("manual8", {"r_hdrExposure": 8}),
    ("auto", {"r_hdrExposure": 1, "r_hdrAutoExposure": 1}),
    ("pbr_enabled", {"r_pbrMaterials": 1}),
    ("pbr_restored", {"r_pbrMaterials": 0}),
    ("restored", {"r_hdrAutoExposure": 0, "r_hdrExposure": 1}),
)


def extract_patch(rgb: bytes, width: int, height: int, descriptor: int, rect: tuple) -> bytes:
    """The shared TGA loader retains storage order; this rectangle is top-left."""
    x0, y0, x1, y1 = rect
    return bytes(rgb[(((y if descriptor & 32 else height - 1 - y) * width
                      + (width - 1 - x if descriptor & 16 else x)) * 3) + c]
                 for y in range(y0, y1) for x in range(x0, x1) for c in range(3))


def validate_controls(captures: dict, sky: dict) -> list[str]:
    failures = []
    if any(name not in captures for name, _ in CONTROLS):
        return ["missing HDR control capture"]
    for other in ("pbr_enabled", "pbr_restored"):
        if captures[other]["sha256"] != captures["auto"]["sha256"]:
            failures.append(f"stock PBR toggle changed the frozen frame: {other}")
    if captures["manual1"]["sha256"] != captures["restored"]["sha256"]:
        failures.append("manual exposure restoration changed the frozen frame")
    if len({captures[name]["sha256"] for name in ("manual1", "manual3", "manual8")}) != 3:
        failures.append("manual exposure controls did not visibly affect the foreground")
    if sky.get("changedChannels", -1) != 0:
        failures.append("exposure changed the already composed portal-sky backdrop")
    if sky.get("greenStdDev", 0) < 2 or sky.get("nearWhiteFraction", 1) >= 0.01:
        failures.append("portal-sky texture detail is missing or washed out")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, default=ROOT / ".install")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--basepath", type=Path, required=True)
    parser.add_argument("--backend", choices=("gl", "vulkan"), default="vulkan")
    args = parser.parse_args()
    runtime = gameplay.validate_runtime_dir(args.runtime_dir, ROOT)
    output, basepath = args.output_dir.resolve(), args.basepath.resolve()
    if not (basepath / "q4base").is_dir() or output == runtime or runtime in output.parents:
        parser.error("installed Quake 4 assets and an evidence directory outside the runtime are required")
    output.mkdir(parents=True, exist_ok=False)
    save = output / "savepath"
    game = save / "baseoq4"
    (game / "screenshots").mkdir(parents=True)
    case_id = "hdr-highlights-" + args.backend
    settings = {
        "r_renderApi": args.backend, "r_vkValidation": "1",
        "r_hiddenWindow": "1", "in_mouse": "0", "in_joystick": "0", "s_noSound": "1",
        "r_mode": "-1", "r_windowWidth": "1280", "r_windowHeight": "720",
        "r_customWidth": "1280", "r_customHeight": "720", "r_multiSamples": "0",
        "r_swapInterval": "0", "com_maxFps": "60", "ui_autoJoin": "1",
        "r_hdrToneMap": "1", "r_hdrSceneTarget": "1", "r_hdrAutoExposure": "0",
        "r_pbrMaterials": "0", "r_pbrInferFromLegacyMaterials": "0", "r_rendererModernQuality": "1",
        "r_temporalAA": "0", "r_screenFraction": "100", "r_postAA": "0",
        "com_skipLoadingContinue": "1", "g_autoSkipCinematics": "1",
        "g_autoExecAfterMapLoad": "highlights.cfg", "g_autoExecAfterMapLoadDelayMs": "1000",
        "si_gameType": "singleplayer",
    }
    launch = matrix.common_args(runtime, case_id, str(basepath), save, False)
    for name, value in settings.items():
        launch += ["+set", name, value]
    launch += ["+map", "game/airdefense1"]
    if sum(s.startswith("+") for s in launch) > matrix.ENGINE_MAX_STARTUP_COMMANDS:
        raise ValueError("HDR highlights exceed the engine startup command limit")
    commands = ["wait 30", "god", "notarget", "g_stopTime 1", "viewpos"]
    for name, changes in CONTROLS:
        commands += [f"set {key} {value}" for key, value in changes.items()]
        commands += ["wait 90", "echo HDR_COMPARE_" + name, "viewpos", "gfxInfo"]
        if args.backend == "vulkan":
            commands += ["rendererVulkanHDRInfo"]
        commands += [f'screenshot "screenshots/{name}.tga"']
    commands += ["quit"]
    (game / "highlights.cfg").write_text("\n".join(commands) + "\n", encoding="utf-8")
    before = gameplay.collect_runtime_files(runtime)
    exit_code, timeout, elapsed = gameplay.launch_and_wait(matrix.find_client_executable(runtime), launch,
        runtime, output / "stdout.txt", output / "stderr.txt", 360)
    log_path = matrix.find_log(save, "openq4_validation_" + case_id + ".log")
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path else ""
    diagnostics = "\n".join([log, (output / "stdout.txt").read_text(encoding="utf-8", errors="replace"),
        (output / "stderr.txt").read_text(encoding="utf-8", errors="replace")])
    warnings = matrix.count_warning_signatures(diagnostics)
    checks = [[f"Renderer API: requested={args.backend} active={args.backend} disposition=module"],
              ["maps/game/airdefense1.map"], ["AutoExecAfterMapLoad: executed highlights.cfg"],
              ["idRenderSystem::Shutdown()"]]
    if args.backend == "vulkan":
        checks += [["Vulkan: validation enabled (VK_LAYER_KHRONOS_validation, debug messenger active)"],
                   ["skyPreserved=1"]]
    _, failures = matrix.evaluate_checks(diagnostics, checks, warnings)
    captures, patches = {}, {}
    for name, _ in CONTROLS:
        path = game / "screenshots" / (name + ".tga")
        try:
            width, height, rgb = gameplay.load_tga_rgb(path)
            if (width, height) != (1280, 720) or max(rgb) == min(rgb):
                raise ValueError("incorrect extent or blank frame")
            captures[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "path": str(path)}
            # Static sky patch, outside the moving walker and smoke columns.
            patches[name] = extract_patch(rgb, width, height, path.read_bytes()[17], (900, 10, 1100, 100))
        except (OSError, ValueError) as exc:
            failures.append(f"{name}: invalid engine capture: {exc}")
    sky = {}
    if "manual1" in patches and "manual8" in patches:
        a, b = patches["manual1"], patches["manual8"]
        sky = {"rect": [900, 10, 1100, 100], "changedChannels": sum(x != y for x, y in zip(a, b)),
               "greenStdDev": statistics.pstdev(b[1::3]), "nearWhiteFraction": sum(v >= 250 for v in b) / len(b)}
    failures += validate_controls(captures, sky)
    after = gameplay.collect_runtime_files(runtime)
    if before != after or exit_code != 0 or timeout:
        failures.append(f"runtime/process failure: unchanged={before == after} exit={exit_code} timeout={timeout}")
    report = {"status": "fail" if failures else "pass", "exitCode": exit_code, "timedOut": timeout,
        "elapsedSeconds": elapsed, "launchArgs": launch, "runtime": str(runtime),
        "harnessSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "runtimeFilesBefore": before, "runtimeFilesAfter": after, "runtimeUnchanged": before == after,
        "warnings": warnings, "log": str(log_path), "captures": captures, "sky": sky, "failures": failures,
        "scope": "Classic stock scene; GL automatic exposure requires modern handoff and is not qualified by this control."}
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"HDR highlights {args.backend}: {report['status']} ({elapsed:.1f}s)", flush=True)
    for failure in failures:
        print("  " + failure, flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
