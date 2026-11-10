#!/usr/bin/env python3
"""Opt-in stock-map gameplay after same-process Vulkan startup recovery.

This records recovery evidence, not performance or renderer-promotion evidence.
All launches use isolated save paths, hidden windowed rendering, disabled input,
and the engine's screenshot command. The runtime package is hashed before/after.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import renderer_gameplay_benchmark as gameplay
import renderer_validation_matrix as matrix

ROOT = Path(__file__).resolve().parents[2]
STAGES = {1: "window", 2: "surface", 3: "swapchain", 4: "resources"}


def run_case(runtime: Path, output: Path, basepath: Path, stage: int, mode: str, timeout: int) -> dict:
    case_id = f"{STAGES[stage]}-{mode}"
    evidence = output / case_id
    evidence.mkdir()
    savepath = evidence / "savepath"
    gamepath = savepath / "baseoq4"
    gamepath.mkdir(parents=True)
    screenshot_name = "screenshots/recovery.tga"
    (gamepath / "screenshots").mkdir()
    cfg_name = "vulkan-recovery.cfg"
    (gamepath / cfg_name).write_text(
        "r_mode -1\nwait 120\nviewpos\nframePacingReset\nwait 180\n"
        f'framePacingSnapshot\ngfxInfo\nscreenshot "{screenshot_name}"\nwait 5\nquit\n',
        encoding="utf-8",
    )
    args = matrix.common_args(runtime, case_id, str(basepath), savepath, False)
    for name, value in {
        "r_renderApi": "vulkan", "r_vkValidation": "1", "r_vkStartupFailure": str(stage),
        "r_hiddenWindow": "1", "in_mouse": "0", "in_joystick": "0", "s_noSound": "1",
        "r_mode": "-1", "r_windowWidth": "1280", "r_windowHeight": "720",
        "r_customWidth": "1280", "r_customHeight": "720", "r_swapInterval": "0",
        "com_maxFps": "240", "com_skipLoadingContinue": "1", "g_autoSkipCinematics": "1",
        "g_autoExecAfterMapLoad": cfg_name, "g_autoExecAfterMapLoadDelayMs": "1000",
        "si_gameType": "singleplayer" if mode == "sp" else "DM",
        "net_serverDedicated": "0", "ui_autoJoin": "1", "net_port": "28766",
    }.items():
        args += ["+set", name, value]
    map_name = "game/airdefense1" if mode == "sp" else "mp/q4dm1"
    args += ["+rendererModuleSelfTest", "+map" if mode == "sp" else "+spawnServer", map_name]
    if sum(arg.startswith("+") for arg in args) > matrix.ENGINE_MAX_STARTUP_COMMANDS:
        raise ValueError("recovery gameplay exceeds the engine startup command limit")
    stdout, stderr = evidence / "stdout.txt", evidence / "stderr.txt"
    exit_code, timed_out, elapsed = gameplay.launch_and_wait(
        matrix.find_client_executable(runtime), args, runtime, stdout, stderr, timeout,
    )
    log = matrix.find_log(savepath, f"openq4_validation_{case_id}.log")
    log_text = log.read_text(encoding="utf-8", errors="replace") if log else ""
    diagnostic_text = "\n".join([log_text, stdout.read_text(encoding="utf-8", errors="replace"),
                                 stderr.read_text(encoding="utf-8", errors="replace")])
    startup = next(case for case in matrix.build_safe_cases(("auto",))
                   if case["id"] == f"renderer-vk-{STAGES[stage]}-recovery")
    checks = startup["checks"] + [
        [f"maps/{map_name}.map"],
        [f"AutoExecAfterMapLoad: executed {cfg_name}"],
        [f"Frame pacing snapshot ({mode.upper()}):"],
        [f"Wrote {screenshot_name}"],
        ["Shutting down OpenGL subsystem"],
    ]
    warnings = matrix.count_warning_signatures(diagnostic_text)
    _, failures = matrix.evaluate_checks(diagnostic_text, checks, warnings, startup["absent"])
    failures += matrix.evaluate_ordered_log_checks(log_text, startup["orderedLogChecks"] + [
        f"AutoExecAfterMapLoad: executed {cfg_name}",
        f"Frame pacing snapshot ({mode.upper()}):", f"Wrote {screenshot_name}",
        "Shutting down OpenGL subsystem",
    ])
    samples = re.search(rf"Frame pacing snapshot \({mode.upper()}\):[^\n]*samples=(\d+)", log_text)
    if not samples or int(samples[1]) < 120:
        failures.append("fewer than 120 measured gameplay frames")
    if exit_code != 0 or timed_out:
        failures.append(f"process exit={exit_code}, timedOut={timed_out}")
    shot = gamepath / screenshot_name
    screenshot = {"path": str(shot)}
    try:
        width, height, rgb = gameplay.load_tga_rgb(shot)
        screenshot.update(width=width, height=height, sha256=hashlib.sha256(shot.read_bytes()).hexdigest())
        if (width, height) != (1280, 720) or max(rgb) == min(rgb):
            failures.append("engine capture is blank or has incorrect dimensions")
    except (OSError, ValueError) as exc:
        failures.append(f"invalid engine screenshot: {exc}")
    result = {
        "id": case_id, "map": map_name, "stage": stage, "requestedBackend": "vulkan",
        "expectedActiveBackend": "opengl", "status": "fail" if failures else "pass",
        "exitCode": exit_code, "timedOut": timed_out, "elapsedSeconds": round(elapsed, 2),
        "launchArgs": args, "log": str(log) if log else "", "screenshot": screenshot,
        "failures": failures, "warningSignatures": warnings,
    }
    (evidence / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"{case_id}: {result['status']} ({elapsed:.1f}s)", flush=True)
    for failure in failures:
        print(f"  {failure}", flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, default=ROOT / ".install")
    parser.add_argument("--output-dir", type=Path, required=True, help="New evidence directory; existing directories are rejected.")
    parser.add_argument("--basepath", type=Path, required=True)
    parser.add_argument("--stages", type=int, nargs="+", choices=tuple(STAGES), default=[4])
    parser.add_argument("--modes", nargs="+", choices=("sp", "mp"), default=["sp", "mp"])
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    runtime = gameplay.validate_runtime_dir(args.runtime_dir, ROOT)
    output, basepath = args.output_dir.resolve(), args.basepath.resolve()
    if not (basepath / "q4base").is_dir():
        parser.error("--basepath must contain installed Quake 4 q4base assets")
    if not matrix.vk_module_path(runtime).is_file():
        parser.error("the tested package has no Vulkan renderer module")
    if output == runtime or runtime in output.parents:
        parser.error("evidence must be outside the tested runtime package")
    output.mkdir(parents=True, exist_ok=False)
    before = gameplay.collect_runtime_files(runtime)
    results = [run_case(runtime, output, basepath, stage, mode, args.timeout)
               for stage in dict.fromkeys(args.stages) for mode in dict.fromkeys(args.modes)]
    after = gameplay.collect_runtime_files(runtime)
    unchanged = before == after
    report = {
        "kind": "vulkan-startup-recovery-gameplay", "runtime": str(runtime), "basepath": str(basepath),
        "runtimeFilesBefore": before, "runtimeFilesAfter": after, "runtimeUnchanged": unchanged,
        "results": results, "status": "pass" if unchanged and all(r["status"] == "pass" for r in results) else "fail",
    }
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Recovery gameplay: {report['status']}; runtime unchanged={unchanged}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
