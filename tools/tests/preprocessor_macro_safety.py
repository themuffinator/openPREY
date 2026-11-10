#!/usr/bin/env python3
"""Validate platform preprocessor guards used by shared engine code."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

SCAN_ROOTS = (
    ROOT / "src" / "framework",
    ROOT / "src" / "idlib",
    ROOT / "src" / "renderer",
    ROOT / "src" / "sys" / "macos",
    ROOT / "src" / "sys" / "posix",
)

UNSAFE_GUARDS = (
	(re.compile(r"^\s*#\s*(if|elif)\s+!?\s*MACOS_X\b"), "use defined( MACOS_X ) for macOS guards"),
	(re.compile(r"^\s*#\s*(if|elif)\s+!?\s*__MWERKS__\b"), "use defined( __MWERKS__ ) for compiler guards"),
	(re.compile(r"^\s*#\s*(if|elif)\s+!?\s*__MACH__\b"), "use defined( __MACH__ ) for Mach guards"),
)

BUILD_DEFINE_BOOLEAN_DEFAULTS = (
	"ID_NOLANADDRESS",
	"ID_PURE_ALLOWDDS",
	"ID_ALLOW_CHEATS",
	"ID_ENABLE_CURL",
	"ID_ALLOW_D3XP",
	"ID_CONSOLE_LOCK",
	"ID_FAKE_PURE",
	"ID_CLIENTINFO_TAGS",
)


def iter_source_files() -> list[Path]:
    files: list[Path] = []
    for scan_root in SCAN_ROOTS:
        for path in scan_root.rglob("*"):
            if path.suffix.lower() in {".c", ".cc", ".cpp", ".h", ".hpp", ".m", ".mm"}:
                files.append(path)
    return sorted(files)


def validate_guard_forms() -> None:
    violations: list[str] = []
    for path in iter_source_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern, message in UNSAFE_GUARDS:
                if pattern.search(line):
                    violations.append(f"{path.relative_to(ROOT)}:{line_number}: {message}: {line.strip()}")

    if violations:
        formatted = "\n".join(f"  - {violation}" for violation in violations)
        raise SystemExit(f"Unsafe macOS/compiler preprocessor guards found:\n{formatted}")


def validate_canonical_macos_define() -> None:
	precompiled = (ROOT / "src" / "idlib" / "precompiled.h").read_text(encoding="utf-8", errors="ignore")
	required = "#if defined( __APPLE__ ) && !defined( MACOS_X )\n#define MACOS_X 1\n#endif"
	if required not in precompiled:
		raise SystemExit("src/idlib/precompiled.h must canonicalize __APPLE__ to MACOS_X for non-Meson Apple builds.")


def validate_build_define_defaults() -> None:
	build_defines = (ROOT / "src" / "framework" / "BuildDefines.h").read_text(encoding="utf-8", errors="ignore")
	violations: list[str] = []
	for macro in BUILD_DEFINE_BOOLEAN_DEFAULTS:
		default_pattern = re.compile(
			rf"#ifndef\s+{re.escape(macro)}\b\s*"
			rf"\n\s*#\s*define\s+{re.escape(macro)}\s+[01]\b",
			re.MULTILINE,
		)
		if not default_pattern.search(build_defines):
			violations.append(macro)

	if violations:
		formatted = ", ".join(violations)
		raise SystemExit(f"BuildDefines.h must provide guarded 0/1 defaults for: {formatted}")


def main() -> None:
	validate_guard_forms()
	validate_canonical_macos_define()
	validate_build_define_defaults()
	print("preprocessor macro safety checks passed")


if __name__ == "__main__":
    main()
