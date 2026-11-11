#!/usr/bin/env python3
"""Check the 64-bit script VM against the 32-bit behaviour retail Prey scripts rely on.

Retail Prey ran its script VM on 32-bit x86; openPREY widens the VM's scalar
slots to pointer size. This runner loads a retail map with the development
fixture content/basepr/dev/script/openprey_vm_conformance.script staged as that
map's loose map script inside an isolated fs_savepath, so the fixture compiles
on top of the full retail program (prey_main.script and every map script). The
fixture prints one VMTEST line per check; the runner fails on any FAIL line,
a script compile or runtime error, or a missing DONE line.

Example:
  python tools/tests/script_vm_conformance.py
  python tools/tests/script_vm_conformance.py --map game/feedingtowera --fs-game basepr

The engine always runs windowed (r_fullscreen 0). Writable data stays under
.tmp/script-vm-conformance/<timestamp>/.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "validation"))

from prey_map_load_condump_audit import default_executable, detect_basepath  # noqa: E402

FIXTURE = ROOT / "content" / "basepr" / "dev" / "script" / "openprey_vm_conformance.script"
RESULT_RE = re.compile(r"VMTEST (PASS|FAIL|DONE)\b(.*)")
ERROR_RE = re.compile(
    r"(?i)(script error|error:.*\.script|compile error|exceeded|stack overflow|"
    r"Entity not found for event|not supported on entity.*openprey|unknown event|ERROR:)"
)
CONSOLE_CODE_RE = re.compile(r"\^[0-9A-Za-z]")


def build_args(args: argparse.Namespace, savepath: Path, log_name: str) -> list[str]:
    sets = [
        ("win_allowMultipleInstances" if platform.system().lower() == "windows" else "sys_allowMultipleInstances", "1"),
        ("logFile", "2"),
        ("logFileName", f"logs/{log_name}"),
        ("developer", "1"),
        ("r_fullscreen", "0"),
        ("s_deviceName", "default"),
        ("com_skipLoadingContinue", "1"),
        ("com_loadingContinueAutoAdvance", "1"),
        ("g_autoScreenshot", "0"),
        ("fs_savepath", str(savepath)),
        ("fs_devpath", str(args.install_root)),
        ("fs_game", args.fs_game),
        ("si_gameType", "singleplayer"),
    ]
    if args.basepath:
        sets.append(("fs_basepath", args.basepath))
    launch: list[str] = []
    for key, value in sets:
        launch += ["+set", key, value]
    launch += ["+map", args.map]
    return launch


def read_log(path: Path) -> list[str]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    return [CONSOLE_CODE_RE.sub("", line).replace("\x00", "").rstrip() for line in text.splitlines()]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--map", default="game/roadhouse", help="retail map to host the fixture (default: game/roadhouse)")
    parser.add_argument("--install-root", type=Path, default=ROOT / ".install")
    parser.add_argument("--executable", type=Path, default=None)
    parser.add_argument("--basepath", default=None, help="retail Prey root (default: auto-detect)")
    parser.add_argument(
        "--fs-game",
        default="basepr",
        help="game directory whose module runs the test; a mod directory next to the executable "
        "can carry a freshly built game module while .install/basepr is in use",
    )
    parser.add_argument("--timeout", type=float, default=240.0, help="seconds to wait for the DONE line")
    parser.add_argument("--run-root", type=Path, default=None)
    args = parser.parse_args(argv)

    args.install_root = args.install_root.resolve()
    executable = (args.executable or default_executable(args.install_root)).resolve()
    if args.basepath is None:
        args.basepath = detect_basepath()
    if not executable.is_file():
        print(f"error: missing executable {executable}", file=sys.stderr)
        return 2
    if not FIXTURE.is_file():
        print(f"error: missing fixture {FIXTURE}", file=sys.stderr)
        return 2

    run_root = (args.run_root or ROOT / ".tmp" / "script-vm-conformance" / time.strftime("%Y%m%d-%H%M%S")).resolve()
    savepath = run_root / "save"
    map_script = savepath / args.fs_game / "maps" / Path(args.map + ".script")
    map_script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURE, map_script)

    log_name = "script_vm_conformance.log"
    log_path = savepath / args.fs_game / "logs" / log_name
    launch = build_args(args, savepath, log_name)
    (run_root / "launch.txt").write_text(" ".join([str(executable), *launch]) + "\n", encoding="utf-8")

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if platform.system().lower() == "windows" else 0
    started = time.monotonic()
    done = False
    with (run_root / "stdout.txt").open("w", encoding="utf-8", errors="replace") as out, (
        run_root / "stderr.txt"
    ).open("w", encoding="utf-8", errors="replace") as err:
        proc = subprocess.Popen(
            [str(executable), *launch], cwd=str(args.install_root), stdout=out, stderr=err, creationflags=creationflags
        )
        try:
            while time.monotonic() - started < args.timeout:
                if proc.poll() is not None:
                    break
                if any(line.startswith("VMTEST DONE") or " VMTEST DONE" in line for line in read_log(log_path)):
                    done = True
                    break
                time.sleep(1.0)
        finally:
            if proc.poll() is None:
                proc.kill()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    pass

    lines = read_log(log_path)
    passed: list[str] = []
    failed: list[str] = []
    errors: list[str] = []
    summary = ""
    for line in lines:
        match = RESULT_RE.search(line)
        if match:
            kind, rest = match.group(1), match.group(2).strip()
            if kind == "PASS":
                passed.append(rest)
            elif kind == "FAIL":
                failed.append(rest)
            else:
                summary = rest
            continue
        if ERROR_RE.search(line):
            errors.append(line)

    print(f"log: {log_path}")
    print(f"checks passed: {len(passed)}; failed: {len(failed)}; {summary or 'no DONE line'}")
    for item in failed:
        print(f"  FAIL {item}")
    for item in errors[:40]:
        print(f"  ERROR {item}")
    if not done:
        print("  fixture did not reach its DONE line" + (f" (engine exited {proc.returncode})" if proc.returncode is not None else ""))
    return 0 if done and not failed and not errors and passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
