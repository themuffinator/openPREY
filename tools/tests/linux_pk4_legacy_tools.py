#!/usr/bin/env python3
"""Regression checks for legacy Linux PK4 maintenance helpers."""

from __future__ import annotations

import importlib.util
import contextlib
import io
import os
import shutil
import sys
import uuid
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
WORK_BASE = ROOT / ".tmp" / "linux-pk4-legacy-tools"
WORK = WORK_BASE / f"{os.getpid()}-{uuid.uuid4().hex}"
ID_UTILS_PATH = ROOT / "src" / "sys" / "linux" / "pk4" / "id_utils.py"
UPDATEPAKS_PATH = ROOT / "src" / "sys" / "linux" / "pk4" / "updatepaks.sh"


def load_id_utils():
    spec = importlib.util.spec_from_file_location("openq4_legacy_id_utils_test", ID_UTILS_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load id_utils.py from {ID_UTILS_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_file(path: Path, data: bytes = b"data\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def make_symlink(target: Path, link: Path) -> bool:
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        return False
    return True


def assert_raises(callback, text: str, label: str) -> None:
    try:
        callback()
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        if text not in str(exc):
            raise AssertionError(f"{label} raised {exc!r}, expected text {text!r}") from exc
        return
    raise AssertionError(f"{label} unexpectedly succeeded")


def quiet(callback) -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        callback()


def main() -> None:
    shutil.rmtree(WORK, ignore_errors=True)
    try:
        id_utils = load_id_utils()
        pak_dir = WORK / "paks"
        pak_dir.mkdir(parents=True, exist_ok=True)
        write_file(pak_dir / "pak0.pk4")
        write_file(pak_dir / "pak2.pk4")
        write_file(pak_dir / "notes.txt")
        if id_utils.list_paks(str(pak_dir)) != ["pak2.pk4", "pak0.pk4"]:
            raise AssertionError("list_paks did not return reverse PK4 search order without mutating the listing")

        source = WORK / "source"
        write_file(source / "materials" / "safe.mtr", b"material\n")
        built_pak = WORK / "built.pk4"
        quiet(lambda: id_utils.build_pak(str(built_pak), str(source), ["materials/safe.mtr"]))
        with ZipFile(built_pak, "r") as archive:
            if archive.namelist() != ["materials/safe.mtr"]:
                raise AssertionError(f"unexpected built PK4 entries: {archive.namelist()!r}")

        assert_raises(
            lambda: quiet(lambda: id_utils.build_pak(str(WORK / "escape.pk4"), str(source), ["../escape.txt"])),
            "unsafe pak archive path",
            "escaped PK4 source path",
        )

        outside = WORK / "outside.txt"
        link = source / "materials" / "linked.mtr"
        write_file(outside)
        if make_symlink(outside, link):
            assert_raises(
                lambda: quiet(lambda: id_utils.build_pak(str(WORK / "linked.pk4"), str(source), ["materials/linked.mtr"])),
                "symlinked source file",
                "symlinked PK4 source path",
            )

        cased = WORK / "cased"
        write_file(cased / "Materials" / "MixedCase.MTR")
        found, cased_name = id_utils.ifind(str(cased), "materials/mixedcase.mtr")
        if not found or Path(cased_name).as_posix() != "Materials/MixedCase.MTR":
            raise AssertionError(f"ifind did not recover filesystem casing: {(found, cased_name)!r}")

        update_script = UPDATEPAKS_PATH.read_text(encoding="utf-8")
        for token in (
            "set -eu",
            "mktemp -d \"${TMPDIR:-/tmp}/openq4-updatepaks.XXXXXX\"",
            "trap cleanup EXIT HUP INT TERM",
            "OPENQ4_UPDATEPAKS_ASSUME_YES",
            "unzip -Z1",
            "zip -b \"$tmpdir\" \"$new_pak\" -@",
        ):
            if token not in update_script:
                raise AssertionError(f"updatepaks.sh is missing safety token {token!r}")
    finally:
        shutil.rmtree(WORK, ignore_errors=True)
    print("linux_pk4_legacy_tools: ok")


if __name__ == "__main__":
    main()
