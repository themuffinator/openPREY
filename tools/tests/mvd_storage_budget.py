#!/usr/bin/env python3
"""Run the production MVD quota policy in an isolated project-local filesystem."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", nargs="?", type=Path)
    args = parser.parse_args()
    task_tmp = ROOT / ".tmp"
    task_tmp.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="mvd-storage-budget-", dir=task_tmp)).absolute()
    try:
        executable = args.executable.resolve() if args.executable else directory / ("fixture.exe" if os.name == "nt" else "fixture")
        if args.executable is None:
            compiler = os.environ.get("CXX") or shutil.which("clang++") or shutil.which("g++")
            if not compiler:
                raise RuntimeError("a C++ compiler is required")
            subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", f"-I{ROOT}",
                            str(ROOT / "tools/tests/native/MvdStorageBudgetTest.cpp"), "-o", str(executable)],
                           cwd=directory, check=True)
        target, linked = directory / "target", directory / "linked"
        target.mkdir()
        link_created = False
        try:
            if os.name == "nt":
                import _winapi
                _winapi.CreateJunction(str(target), str(linked))
            else:
                linked.symlink_to(target, target_is_directory=True)
            link_created = True
            subprocess.run([str(executable), str(directory / "library"), str(linked)], cwd=directory, check=True)
        finally:
            if link_created:
                if os.name == "nt":
                    os.rmdir(linked)  # Remove the verified junction entry, without traversing it.
                else:
                    linked.unlink()
    finally:
        if directory.resolve().parent != task_tmp.resolve():
            raise RuntimeError(f"temporary cleanup target escaped the project: {directory}")
        pending = [directory]
        while pending:
            path = pending.pop()
            status = path.lstat()
            if stat.S_ISLNK(status.st_mode) or bool(getattr(status, "st_file_attributes", 0) & 0x400):
                raise RuntimeError(f"unexpected link in temporary fixture; preserving {directory}")
            if path.is_dir():
                pending.extend(path.iterdir())
        shutil.rmtree(directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
