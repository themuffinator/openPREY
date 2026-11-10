#!/usr/bin/env python3
"""Locate Meson wrap sources for native test harnesses, fetching them if absent.

Several harnesses compile upstream sources (jsoncpp, libtess2) that the build
obtains through subprojects/*.wrap. A fresh checkout carries only the wrap
files; Meson downloads, verifies and patches the sources during `meson setup`,
and CI runs the Python checks before that. A missing tree is provisioned with
`meson subprojects download`, the build's own mechanism, so a harness compiles
exactly the sources and patches that the build will.

Meson extracts a tree once. When the wrap file later changes, for example to
add a diff_files patch, Meson only warns that the extraction may be out of
date. A tree whose recorded wrap hash no longer matches is therefore
re-extracted with `meson subprojects update --reset`.
"""
from __future__ import annotations

import configparser
import hashlib
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def meson_command() -> list[str]:
    """Meson as tools/build/meson_setup.sh finds it: this Python's, else PATH's."""
    if importlib.util.find_spec("mesonbuild") is not None:
        return [sys.executable, "-m", "mesonbuild.mesonmain"]
    found = shutil.which("meson")
    if found:
        return [found]
    raise RuntimeError("Meson is required to provision wrap sources for native test harnesses; "
                       "install it with 'python -m pip install meson'")


def wrap_hash(wrap_path: Path) -> str:
    """The digest Meson records for a wrap file: SHA-256 of its text with universal newlines."""
    return hashlib.sha256(wrap_path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def wrap_source(name: str, root: Path = ROOT) -> Path:
    """Return the source tree of wrap-file subproject `name`, provisioning it if absent or stale."""
    wrap_path = root / "subprojects" / f"{name}.wrap"
    wrap = configparser.ConfigParser(interpolation=None)
    if not wrap.read(wrap_path, encoding="utf-8") or not wrap.has_option("wrap-file", "directory"):
        raise RuntimeError(f"Not a wrap-file subproject: {wrap_path}")
    source = root / "subprojects" / wrap["wrap-file"]["directory"]
    recorded = source / ".meson-subproject-wrap-hash.txt"
    stale = recorded.is_file() and recorded.read_text(encoding="utf-8").strip() != wrap_hash(wrap_path)
    if stale or not source.is_dir():
        action = ["update", "--reset"] if stale else ["download"]
        command = [*meson_command(), "subprojects", *action, name]
        result = subprocess.run(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", check=False)
        if result.returncode or not source.is_dir():
            raise RuntimeError(f"Cannot provision wrap {name!r} with {' '.join(command)}:\n{result.stdout}")
        print(f"Provisioned {source.relative_to(root).as_posix()} with meson subprojects {' '.join(action)}",
              file=sys.stderr, flush=True)
    return source
