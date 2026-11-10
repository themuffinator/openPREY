#!/usr/bin/env python3
"""Exercise the experimental editor service, then play its saved stock SP map.

Uses the staged executable and mode-specific SP launch options. No keyboard or
mouse injection: commands arrive through an isolated cfg, and the engine's own
screenshot command records the played map. All writes stay beneath --output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

from renderer_gameplay_benchmark import collect_runtime_files

ROOT = Path(__file__).resolve().parents[2]
SOURCE_MAP = "maps/game/airdefense1.map"


def stock_map( assets: Path) -> bytes:
    result = None
    for package in sorted((assets / "q4base").glob("*.pk4")):
        with zipfile.ZipFile(package) as archive:
            if SOURCE_MAP in archive.namelist():
                result = archive.read(SOURCE_MAP)
    if result is None:
        raise RuntimeError(f"no {SOURCE_MAP} in {assets}")
    return result


def run(args: argparse.Namespace) -> dict:
    output = args.output.resolve()
    output.relative_to(ROOT / ".tmp")
    output.mkdir(parents=True, exist_ok=False)
    runtime = ROOT / ".install"
    executable = runtime / ("openQ4-client_x64.exe" if os.name == "nt" else "openQ4-client_x64")
    if not executable.is_file():
        raise RuntimeError(f"stage the current build first: {executable}")
    before = collect_runtime_files(runtime)
    (output / "runtime-before.json").write_text(json.dumps(before, indent=2) + "\n", encoding="utf-8")
    game = output / "baseoq4"
    (game / "maps/tools").mkdir(parents=True)
    # An installation may contain unrelated loose authoring overrides. Seed
    # this isolated source from the retail PK4 so the byte comparison is known.
    original = stock_map(args.assets)
    (game / SOURCE_MAP).parent.mkdir(parents=True, exist_ok=True)
    (game / SOURCE_MAP).write_bytes(original)
    (game / "maps/tools/editor_invalid.map").write_text("Version 3\n{ broken }\n", encoding="ascii")
    commands = [
        "editorExperimental open game/airdefense1",
        'editorExperimental set "1x" _openq4_editor_test invalid',  # a partial numeric handle must not target entity 1
        "editorExperimental savecopy tools/editor_roundtrip",
        "editorExperimental set 1 _openq4_editor_test first",
        "editorExperimental autosave",
        "editorExperimental close",  # must refuse to discard dirty work
        "editorExperimental savecopy tools/editor_dirtycopy",
        "editorExperimental undo",
        "editorExperimental savecopy tools/editor_undo",
        "editorExperimental redo",
        "editorExperimental save",
        "editorExperimental undo",
        "editorExperimental redo",
        "editorExperimental set 1 _openq4_editor_test second",
        "editorExperimental autosave",
        "editorExperimental close discard",
        "editorExperimental recover game/airdefense1",
        "editorExperimental save tools/editor_recovered",
        "editorExperimental close",
        "editorExperimental open game/airdefense1",
        "editorExperimental open tools/editor_invalid",  # old document must survive
        "mapEdit status",  # document-service alias must address the same experiment
        "editorExperimental close",
        "devmap game/airdefense1",
    ]
    after_map = [
        'set g_autoExecAfterMapLoad ""',
        "waitMsec 3000",
        'screenshot "screenshots/editor-authoring.tga"',
        "wait 2",
        "echo EDITOR_RUNTIME_COMPLETE",
        "quit",
    ]
    (game / "editor_runtime.cfg").write_text("\n".join(commands) + "\n", encoding="ascii")
    (game / "editor_after_map.cfg").write_text("\n".join(after_map) + "\n", encoding="ascii")
    launch = [str(executable)]
    settings = {
        "fs_basepath": str(args.assets.resolve()), "fs_savepath": str(output),
        "fs_devpath": str(output), "fs_game": "baseoq4", "si_gameType": "singleplayer",
        "r_fullscreen": "0", "r_hiddenWindow": "1", "r_renderApi": "vulkan" if args.renderer == "vk" else "gl",
        "r_mode": "-1", "r_customWidth": "960", "r_customHeight": "540",
        "in_mouse": "0", "in_joystick": "0", "s_noSound": "1",
        "logFile": "2", "logFileName": "logs/openq4.log", "developer": "1",
        "com_allowConsole": "1", "win_allowMultipleInstances" if os.name == "nt" else "sys_allowMultipleInstances": "1",
        "com_skipLoadingContinue": "1", "com_loadingContinueAutoAdvance": "1", "g_autoSkipCinematics": "1",
        "editorExperimental_autoSaveSeconds": "0", "r_useLightGrid": "0",
        "g_autoExecAfterMapLoad": "editor_after_map.cfg", "g_autoExecAfterMapLoadDelayMs": "1000",
    }
    for key, value in settings.items():
        launch += ["+set", key, value]
    launch += ["+exec", "editor_runtime.cfg"]
    (output / "launch.json").write_text(json.dumps(launch, indent=2) + "\n", encoding="utf-8")
    with (output / "process.log").open("wb") as stream:
        process = subprocess.run(launch, cwd=runtime, stdout=stream, stderr=subprocess.STDOUT, timeout=180)
    after = collect_runtime_files(runtime)
    check(before == after, "shared runtime changed during qualification")
    log_path = game / "logs/openq4.log"
    log = log_path.read_text(encoding="utf-8", errors="replace")
    require = check
    require(process.returncode == 0, f"engine exited with {process.returncode}")
    require("EDITOR_RUNTIME_COMPLETE" in log, "completion marker missing")
    require("Unknown command 'editorExperimental'" not in log, "editor not registered")
    backend = "vulkan" if args.renderer == "vk" else "gl"
    require(f"Loading renderer module: api='{backend}'" in log, "requested renderer was not loaded")
    if args.renderer == "vk":
        require("Vulkan renderer initialized:" in log, "Vulkan did not initialize")
        require("Loading renderer module: api='gl'" not in log, "Vulkan fell back to OpenGL")
    require(log.count("editor rejected:") == 3, "unexpected editor rejection count")
    require("unknown entity handle" in log, "malformed-handle guard was not exercised")
    require("document has unsaved changes" in log, "dirty-close guard was not exercised")
    require("expected a quoted entity key" in log, "failed-open guard was not exercised")
    require((game / "maps/tools/editor_roundtrip.map").read_bytes() == original, "stock roundtrip altered bytes")
    require((game / "maps/tools/editor_undo.map").read_bytes() == original, "undo altered original bytes")
    require((game / (SOURCE_MAP + ".bak")).read_bytes() == original, "backup differs from original")
    edited = (game / SOURCE_MAP).read_bytes()
    require(b'"_openq4_editor_test" "first"' in edited, "published edit is missing")
    require((game / "maps/tools/editor_dirtycopy.map").read_bytes() == edited, "save-copy differs from edited map")
    recovery = (game / "editor_experimental/recovery" / SOURCE_MAP).read_bytes()
    require(b'"_openq4_editor_test" "second"' in recovery, "recovery lost latest edit")
    require((game / "maps/tools/editor_recovered.map").read_bytes() == recovery, "recovered source differs")
    require(not list(game.rglob("*.editor-tmp")), "unpublished staging files remain")
    capture = game / "screenshots/editor-authoring.tga"
    require(capture.is_file() and capture.stat().st_size > 18, "engine gameplay capture missing")
    require("Game Map Init" in log and "airdefense1" in log, "SP gameplay was not entered")
    require("editor shutdown recovery failed" not in log, "shutdown recovery failed")
    warnings = [line for line in log.splitlines() if "WARNING:" in line or "ERROR:" in line]
    require(not warnings, "unexpected engine diagnostics: " + "\n".join(warnings[:10]))
    artifacts = sorted((game / "maps").rglob("*")) + sorted((game / "editor_experimental/recovery").rglob("*"))
    report = {
        "result": "PASS", "renderer": args.renderer, "runtimeUnchanged": before == after, "runtimeFiles": before,
        "source_bytes": len(original), "source_sha256": hashlib.sha256(original).hexdigest(),
        "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "log": str(log_path), "engine_capture": str(capture), "diagnostics": warnings,
        "visual_review": "required; this harness checks authoring and gameplay entry, not image parity",
        "artifact_sha256": {str(path.relative_to(game)): hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in artifacts if path.is_file()},
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / ".tmp/editor-modernization/runtime")
    parser.add_argument("--renderer", choices=("gl", "vk"), default="gl")
    print(json.dumps(run(parser.parse_args()), indent=2))
