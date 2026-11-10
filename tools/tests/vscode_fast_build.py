#!/usr/bin/env python3
"""Regression checks for the VS Code fast default build path, launch configurations and the Codex actions that run them."""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CODEX_RUNNER = ".codex/scripts/run-vscode-entry.ps1"
# How the Codex setup script and every action run a VS Code entry. Inside the
# double quotes, $ and ` would expand in PowerShell and % in cmd.
CODEX_COMMAND = re.compile(
    r'powershell -NoProfile -ExecutionPolicy Bypass -File \.codex\\scripts\\run-vscode-entry\.ps1 (task|launch) "([^"$`%]+)"'
)


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def reject(haystack: str, needle: str, context: str) -> None:
    if needle in haystack:
        raise AssertionError(f"Unexpected {needle!r} in {context}")


def find_task(tasks: list[dict[str, object]], label: str) -> dict[str, object]:
    for task in tasks:
        if task.get("label") == label:
            return task
    raise AssertionError(f"Missing VS Code task {label!r}")


def validate_tasks() -> None:
    tasks = json.loads(read(".vscode/tasks.json"))["tasks"]
    default_tasks = [
        task
        for task in tasks
        if isinstance(task.get("group"), dict) and task["group"].get("kind") == "build" and task["group"].get("isDefault") is True
    ]
    if len(default_tasks) != 1:
        raise AssertionError(f"Expected exactly one default build task, found {len(default_tasks)}")

    fast_build = find_task(tasks, "Build openPREY (Meson Debug)")
    if fast_build is not default_tasks[0]:
        raise AssertionError("Build openPREY (Meson Debug) must be the default VS Code build task")
    if fast_build.get("dependsOn"):
        raise AssertionError("Fast default build must not depend on configure or full install tasks")
    if "fastbuild" not in fast_build.get("args", []):
        raise AssertionError("Fast default build must invoke meson-task.ps1 fastbuild")

    full_build = find_task(tasks, "Full Build and Stage openPREY (Meson Debug)")
    if full_build.get("dependsOrder") != "sequence":
        raise AssertionError("Full build task must keep ordered configure, compile, install steps")
    for label in (
        "Configure openPREY (Meson Debug)",
        "Compile openPREY (Meson Debug)",
        "Stage openPREY Install Tree (Meson Debug)",
    ):
        if label not in full_build.get("dependsOn", []):
            raise AssertionError(f"Full build task is missing dependency {label!r}")

    for task in tasks:
        if "fs_basepath" in task.get("args", []):
            raise AssertionError(f"VS Code task {task.get('label')!r} must leave fs_basepath to the engine's install discovery")


def validate_wrapper() -> None:
    wrapper = read(".vscode/meson-task.ps1")
    require(wrapper, "[ValidateSet('setup', 'compile', 'install', 'fastbuild')]", "VS Code Meson wrapper actions")
    require(wrapper, "stage_fast_install.py", "VS Code fast build staging script")
    # openPREY's standard local tree is builddir configured as a debug build;
    # compile reconfigures an existing build directory that drifted from it.
    require(wrapper, "$buildDir = Join-Path $workspaceRoot 'builddir'", "VS Code build uses the standard builddir")
    require(wrapper, "'buildtype' = 'debug'", "VS Code build must configure the debug buildtype")
    require(wrapper, "Get-StaleBuildOptions $buildDir", "VS Code compile reconfigures stale build options")
    require(wrapper, "check_staged_content_edits.py", "VS Code fast build staged content guard")
    require(wrapper, "'compile',", "VS Code fast build compiles through Meson")
    require(wrapper, "'--install-dir',", "VS Code fast build stages .install incrementally")

    stager = read("tools/build/stage_fast_install.py")
    require(stager, "copy_file_if_changed", "fast install copy-if-changed behavior")
    require(
        stager,
        "from windows_runtime import cleanup_windows_stage_target, is_windows_host",
        "shared Windows stage hygiene helper",
    )
    require(
        stager,
        "cleanup_windows_stage_target(install_dir)",
        "fast-build Windows stale-runtime cleanup",
    )
    require(stager, '"renderer-gl_*.dll"', "fast install renderer staging")
    require(stager, '"--temporary-runtime"', "isolated compatibility runtime staging")
    require(stager, 'source_root / ".tmp" / "stock-runtime"', "temporary runtime containment")
    require(stager, "*OPENQ4_PACK_NAMES,", "fast install stages every table pack")
    reject(stager, '"*.lib",\n    "pak0.pk4"', "fast install must not copy linker artifacts as runtime content")

    windows_runtime = read("tools/build/windows_runtime.py")
    require(
        windows_runtime,
        "WINDOWS_STALE_STAGE_FILE_MANIFEST",
        "narrow Windows stale-runtime cleanup manifest",
    )
    require(
        windows_runtime,
        '"basepr/skins"',
        "known empty Windows stage directory manifest",
    )
    require(
        windows_runtime,
        "cleanup_results[str(target)] = cleanup_windows_stage_target(target)",
        "full-install Windows stale-runtime cleanup",
    )


def set_values(args: list[object], key: str) -> list[str]:
    return [
        str(args[index + 2])
        for index, token in enumerate(args[:-2])
        if token in ("+set", "+seta") and args[index + 1] == key
    ]


def validate_launch_configs() -> None:
    launch = json.loads(read(".vscode/launch.json"))
    mp_configs = []
    for config in launch.get("configurations", []):
        name = str(config.get("name", ""))
        args = config.get("args", [])
        if "preLaunchTask" in config:
            raise AssertionError(f"Launch config {name!r} must not define preLaunchTask")
        if not isinstance(args, list) or not any(
            args[index : index + 3] == ["+set", "r_fullscreen", "0"]
            for index in range(max(0, len(args) - 2))
        ):
            raise AssertionError(f"Launch config {name!r} must force windowed mode")
        if "basepr" not in args:
            raise AssertionError(f"Launch config {name!r} must select basepr")
        if set_values(args, "fs_basepath"):
            raise AssertionError(f"Launch config {name!r} must leave fs_basepath to the engine's install discovery")
        if "(MP)" in name:
            mp_configs.append(config)
    if not mp_configs:
        raise AssertionError("Expected at least one VS Code MP launch configuration")


def validate_codex_actions() -> None:
    # The actions once ran entries by position, and regrouping launch.json moved
    # them all onto other entries. Each now names its entry, which has to exist.
    entries = {
        "task": [task.get("label") for task in json.loads(read(".vscode/tasks.json"))["tasks"]],
        "launch": [config.get("name") for config in json.loads(read(".vscode/launch.json"))["configurations"]],
    }

    def resolve(command: object, context: str) -> tuple[str, str]:
        match = CODEX_COMMAND.fullmatch(command) if isinstance(command, str) else None
        if match is None:
            raise AssertionError(f"{context} must run one quoted entry through {CODEX_RUNNER}, not {command!r}")
        kind, entry = match.groups()
        if entry.isdigit():
            raise AssertionError(f"{context} must name its {kind} rather than give its position")
        if entries[kind].count(entry) != 1:
            raise AssertionError(f"{context} runs {kind} {entry!r}, which .vscode does not define exactly once")
        return kind, entry

    environment = tomllib.loads(read(".codex/environments/openq4.toml"))
    if resolve(environment["setup"]["win32"]["script"], "Codex setup script")[0] != "task":
        raise AssertionError("Codex setup script must run a task")
    names = []
    for action in environment.get("actions", []):
        name = action.get("name")
        context = f"Codex action {name!r}"
        if resolve(action.get("command"), context)[1] != name:
            raise AssertionError(f"{context} must run the entry it is named after")
        # The commands are Windows command lines. The Codex app reads platform and
        # drops any other key, such as platforms, then offers the action on every OS.
        if action.get("platform") != "win32":
            raise AssertionError(f'{context} must set platform = "win32"')
        names.append(name)
    if not names or len(set(names)) != len(names):
        raise AssertionError("Codex actions must exist and have distinct names")

    # Windows PowerShell reads a file without a byte order mark as ANSI, so the
    # runner has to stay ASCII and read launch.json as UTF-8 for an em dash to match.
    runner = read(CODEX_RUNNER)
    if not runner.isascii():
        raise AssertionError(f"{CODEX_RUNNER} must stay ASCII")
    require(runner, "Get-Content -LiteralPath $Path -Raw -Encoding UTF8", "Codex runner JSON reads")


def validate_mp_autojoin_policy() -> None:
    listen_script = read("tools/debug/start_listen_server_client.ps1")
    if listen_script.count('"+set", "ui_autoJoin", "1"') != 2:
        raise AssertionError("MP listen-server helper must enable auto-join for host and client")

    renderdoc_script = read("tools/debug/renderdoc_capture.ps1")
    if renderdoc_script.count('"+set", "ui_autoJoin", "1"') != 1:
        raise AssertionError("MP RenderDoc helper must enable auto-join for its listen host")

    benchmark = read("tools/tests/renderer_gameplay_benchmark.py")
    for target in ("server_args", "client_args"):
        require(
            benchmark,
            f'append_set({target}, "ui_autoJoin", "1")',
            f"MP renderer benchmark {target}",
        )

    baseline = read("tools/validation/stock_asset_baseline.py")
    require(
        baseline,
        'args[restart_index:restart_index] = ("+set", "ui_autoJoin", "1")',
        "stock baseline MP roles",
    )
    require(
        baseline,
        'launch_contract["ui_autoJoin"] = "1"',
        "recorded stock baseline MP contract",
    )

    guide = read("AGENTS.md")
    require(
        guide,
        "keep an explicit `+set ui_autoJoin 1`",
        "agent MP test policy",
    )
    require(
        guide,
        "pass `+set ui_autoJoin 0`",
        "interactive join-screen launch policy",
    )


def validate_validation_coverage() -> None:
    validator = read("tools/validation/openq4_validate.py")
    push = read(".github/workflows/push-verification.yml")
    commit = read(".github/workflows/commit-validation.yml")
    for haystack, context in (
        (validator, "validation runner"),
        (push, "push verification workflow"),
        (commit, "commit validation workflow"),
    ):
        require(haystack, "vscode_fast_build.py", context)


def main() -> None:
    validate_tasks()
    validate_wrapper()
    validate_launch_configs()
    validate_codex_actions()
    validate_mp_autojoin_policy()
    validate_validation_coverage()
    print("vscode_fast_build: ok")


if __name__ == "__main__":
    main()
