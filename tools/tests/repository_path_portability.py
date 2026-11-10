#!/usr/bin/env python3
"""Regression checks that tracked paths check out identically everywhere and follow the source layout."""

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

# Leaves room for a checkout or worktree root under the Windows 260-character MAX_PATH.
MAX_RELATIVE_PATH = 160
PORTABLE_COMPONENT = re.compile(r"[A-Za-z0-9._+-]+")
WINDOWS_RESERVED_STEMS = {"con", "prn", "aux", "nul"} | {f"com{n}" for n in range(1, 10)} | {f"lpt{n}" for n in range(1, 10)}


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def tracked_paths() -> list[str]:
    output = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        check=True,
        capture_output=True,
    ).stdout
    paths = [entry.decode("utf-8") for entry in output.split(b"\0") if entry]
    if not paths:
        raise AssertionError("git ls-files returned no tracked paths")
    return paths


def path_prefixes(paths: list[str]) -> set[str]:
    prefixes = set(paths)
    for path in paths:
        parts = path.split("/")
        for index in range(1, len(parts)):
            prefixes.add("/".join(parts[:index]))
    return prefixes


def validate_no_case_collisions(paths: list[str]) -> None:
    # Windows and macOS keep one entry per case-folded name, so the second
    # spelling silently aliases the first and shows up as a phantom change.
    seen: dict[str, str] = {}
    collisions = []
    for path in sorted(path_prefixes(paths)):
        folded = path.casefold()
        if folded in seen and seen[folded] != path:
            collisions.append(f"{seen[folded]} <-> {path}")
        else:
            seen[folded] = path
    if collisions:
        raise AssertionError("Tracked paths differ only by case:\n  " + "\n  ".join(collisions))


def validate_portable_components(paths: list[str]) -> None:
    problems = []
    for path in paths:
        if len(path) > MAX_RELATIVE_PATH:
            problems.append(f"{path}: longer than {MAX_RELATIVE_PATH} characters")
        for component in path.split("/"):
            if not PORTABLE_COMPONENT.fullmatch(component):
                problems.append(f"{path}: component {component!r} uses characters outside [A-Za-z0-9._+-]")
            elif component.endswith("."):
                problems.append(f"{path}: component {component!r} ends with a dot")
            elif component.split(".", 1)[0].casefold() in WINDOWS_RESERVED_STEMS:
                problems.append(f"{path}: component {component!r} is a reserved Windows device name")
    if problems:
        raise AssertionError("Non-portable tracked paths:\n  " + "\n  ".join(problems))


def validate_lowercase_extensions(paths: list[str]) -> None:
    uppercase = []
    for path in paths:
        name = path.rsplit("/", 1)[-1]
        stem, dot, extension = name.lstrip(".").rpartition(".")
        if dot and stem and extension != extension.lower():
            uppercase.append(path)
    if uppercase:
        raise AssertionError("Tracked files with uppercase extensions:\n  " + "\n  ".join(uppercase))


def validate_source_root_directories(paths: list[str]) -> None:
    # First-level source directories are single lowercase words, as in
    # imagetools, rendergeo and mayaimport; see docs/dev/source-layout.md.
    names = {path.split("/")[1] for path in paths if path.startswith("src/") and path.count("/") >= 2}
    outliers = sorted(name for name in names if not re.fullmatch(r"[a-z0-9]+", name))
    if outliers:
        raise AssertionError("Source directories must be lowercase words without separators: " + ", ".join(outliers))


def validate_validation_coverage() -> None:
    validator = read("tools/validation/openq4_validate.py")
    push = read(".github/workflows/push-verification.yml")
    commit = read(".github/workflows/commit-validation.yml")

    for haystack, context in (
        (validator, "validation runner"),
        (push, "push verification workflow"),
        (commit, "commit validation workflow"),
    ):
        require(haystack, "repository_path_portability.py", context)


def main() -> None:
    paths = tracked_paths()
    validate_no_case_collisions(paths)
    validate_portable_components(paths)
    validate_lowercase_extensions(paths)
    validate_source_root_directories(paths)
    validate_validation_coverage()
    print(f"repository_path_portability: ok ({len(paths)} tracked paths)")


if __name__ == "__main__":
    main()
