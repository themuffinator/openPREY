#!/usr/bin/env python3
"""Remove obsolete openQ4 layer outputs after staging the unified modules.

Only known build artifacts are removed. Loose content, PK4s, saves and user
configuration in q4xbase are preserved. Links are never followed or removed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ARTIFACTS = {"mod.json"} | {
    f"game-{mode}_{arch}.{extension}"
    for mode in ("sp", "mp")
    for arch in ("x86", "x64", "arm64", "universal2")
    for extension in ("dll", "so", "dylib", "pdb", "lib", "exp")
}


def retire(root: Path) -> list[str]:
    target = root.absolute() / "q4xbase"
    for path in (target, *target.parents):
        if path.is_symlink() or (path.exists() and getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400):
            raise ValueError(f"refusing layer cleanup through a link: {path}")
    if not target.exists():
        return []
    if not target.is_dir():
        raise ValueError(f"obsolete layer path is not a directory: {target}")
    removed = []
    for name in sorted(ARTIFACTS):
        path = target / name
        if path.is_symlink() or (path.exists() and getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400):
            raise ValueError(f"refusing layer cleanup of a link: {path}")
        if path.is_file():
            path.unlink()
            removed.append(str(path))
    if not any(target.iterdir()):
        target.rmdir()
    return removed


def main() -> None:
    # Meson supplies the absolute runtime directory; apply DESTDIR if set. This helper
    # is only an install hook, never a recursive cleanup of an asset source.
    value = sys.argv[1] if len(sys.argv) == 2 else ""
    if not value or not Path(value).is_absolute():
        raise ValueError("Meson must supply the absolute runtime staging directory")
    root = Path(value)
    if os.environ.get("DESTDIR"):
        root = Path(os.environ["DESTDIR"]) / root.relative_to(root.anchor)
    for path in retire(root):
        print(f"Removed obsolete layer output: {path}")


if __name__ == "__main__":
    main()
