#!/usr/bin/env python3
"""List C++ sources for a source subtree, excluding explicit relative paths."""

from __future__ import annotations

import sys
from pathlib import Path

from openq4_pak import is_relative_to


def normalize(path: str) -> str:
    return path.replace("\\", "/").strip()


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(
            f"usage: {argv[0]} <source-root> <subdir> [exclude-relative-path ...]",
            file=sys.stderr,
        )
        return 2

    raw_source_root = Path(argv[1])
    if raw_source_root.is_symlink():
        print(f"error: source root must not be a symlink: {raw_source_root}", file=sys.stderr)
        return 1
    source_root = raw_source_root.resolve()
    subdir = normalize(argv[2]).strip("/")
    raw_target_root = source_root / subdir
    if raw_target_root.is_symlink():
        print(f"error: source subtree must not be a symlink: {raw_target_root}", file=sys.stderr)
        return 1
    target_root = raw_target_root.resolve()

    if not target_root.is_dir():
        print(f"error: source subtree not found: {target_root}", file=sys.stderr)
        return 1
    if not is_relative_to(target_root, source_root):
        print(f"error: source subtree must stay under {source_root}: {target_root}", file=sys.stderr)
        return 1

    excludes = {normalize(entry) for entry in argv[3:]}
    sources: list[str] = []

    for path in target_root.rglob("*.cpp"):
        if path.is_symlink():
            print(f"error: refusing to list symlinked source file: {path}", file=sys.stderr)
            return 1
        if not path.is_file():
            continue
        rel = path.relative_to(source_root).as_posix()
        if rel in excludes:
            continue
        sources.append(rel)

    for rel in sorted(sources):
        print(rel)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
