#!/usr/bin/env python3
"""Static checks for the no-macOS-runtime local validation track."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLAN = "docs/dev/archive/2026-10-18/plans/2026-06-30-apple-support-no-macos-access.md"
DOC = "docs/dev/macos-local-validation-track.md"


def read(relative_path: str) -> str:
    path = ROOT / relative_path
    if not path.is_file():
        raise AssertionError(f"Required file not found: {path}")
    return path.read_text(encoding="utf-8")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def validate_runner_profile() -> None:
    runner = read("tools/validation/openq4_validate.py")

    for token in (
        '"macos-static"',
        "MACOS_STATIC_PROFILE",
        "MACOS_STATIC_SHELL_SYNTAX_FILES",
        "validate_macos_static.sh",
        "openq4-macos-bootstrap.sh",
        "openq4-macos-install-quake4-assets.sh",
        "openq4-macos-sync-build-test.sh",
        "MACOS_STATIC_DRY_RUN_PROFILES",
        "run_macos_static_shell_syntax_checks",
        "run_macos_static_dry_run_profiles",
        "run_macos_static_validation_track",
        '"--skip-python-tests"',
        '"--skip-build"',
        '"--no-install"',
        '"--dry-run"',
        "if args.runtime and host_is_macos()",
        "must not run openQ4 on macOS",
        "Run renderer self-test binaries only on available non-macOS hosts",
        'args.profile == MACOS_STATIC_PROFILE',
    ):
        require(runner, token, "macos-static validation profile")

    for token in (
        "macos_apple_gl21_arb2_corridor.py",
        "macos_metal_bridge.py",
        "macos_package_robustness.py",
        "macos_signoff_archive.py",
        "macos_gamelibs_alignment.py",
        "macos_local_validation_track.py",
    ):
        require(runner, token, "macos-static Python static/policy test set")


def validate_wrappers_and_docs() -> None:
    ps1 = read("tools/validation/validate_macos_static.ps1")
    sh = read("tools/validation/validate_macos_static.sh")
    building = read("BUILDING.md")
    doc = read(DOC)

    for source, context in (
        (ps1, "PowerShell macos-static wrapper"),
        (sh, "POSIX macos-static wrapper"),
    ):
        require(source, "macos-static", context)
        require(source, "openq4_validate.py", context)

    for source, context in (
        (building, "building guide"),
        (doc, "macOS local validation track doc"),
    ):
        require(source, "tools/validation/validate_macos_static.ps1", context)
        require(source, "tools/validation/validate_macos_static.sh", context)
        require(source, "python tools/validation/openq4_validate.py macos-static", context)
        require(source, "does not run openQ4 on macOS", context)
        require(source, "renderer-default-safety-selftest", context)
        require(source, "non-macOS", context)

    for token in (
        "macos_apple_gl21_arb2_corridor.py",
        "macos_signoff_archive.py",
        "macos_metal_bridge.py",
        "macos_package_robustness.py",
        "validate_push.sh --dry-run",
        "validate_pr.sh --dry-run",
        "Synthetic Apple GL 2.1",
        "Synthetic macOS package/archive fixtures",
    ):
        require(doc, token, "macOS local validation track doc coverage")


def validate_phase9_plan_and_release_notes() -> None:
    plan = read(PLAN)
    release_completion = read("docs/dev/release-completion.md")
    release_notes = read("docs/dev/releases/v0.6.5.md")

    for token in (
        "## Phase 9: Local Validation Track",
        "- [x] Run Python static/policy tests on Windows or Linux after plan work changes",
        "- [x] Run renderer self-test binaries only on available non-macOS hosts when the",
        "- [x] Use synthetic driver/capability tests to model Apple GL 2.1 behavior.",
        "- [x] Use archive/package fixture tests with synthetic macOS payloads.",
        "- [x] Use CI/workflow linting and dry-run validation for release matrix changes.",
        "- [x] Do not mark a checkbox complete merely because hosted macOS compiled; this",
        "Phase 9 implementation status",
        "tools/validation/validate_macos_static.ps1",
        "tools/tests/macos_local_validation_track.py",
        "No macOS platform testing is required or claimed for Phase 9.",
        "- [x] No checklist item in this document requires the maintainer to run or test",
    ):
        require(plan, token, "Phase 9 checklist and definition of done")

    for source, context in (
        (release_completion, "release completion notes"),
        (release_notes, "curated release notes"),
    ):
        require(source, "macOS no-runtime validation track", context)
        require(source, "macos-static", context)
        require(source, "synthetic Apple GL 2.1", context)
        require(source, "synthetic macOS package/archive", context)


def validate_workflow_wiring() -> None:
    commit = read(".github/workflows/commit-validation.yml")
    push = read(".github/workflows/push-verification.yml")
    macos_debug = read(".github/workflows/macos-debug.yml")

    for workflow, context in (
        (commit, "commit validation workflow"),
        (push, "push verification workflow"),
    ):
        require(workflow, "tools/tests/macos_local_validation_track.py", context)
        require(workflow, "python tools/tests/macos_local_validation_track.py", context)
        require(workflow, "bash -n tools/validation/validate_macos_static.sh", context)

    require(macos_debug, "python tools/tests/macos_local_validation_track.py", "macOS debug static guards")
    require(macos_debug, "bash -n tools/validation/validate_macos_static.sh", "macOS debug static guards")


def main() -> None:
    validate_runner_profile()
    validate_wrappers_and_docs()
    validate_phase9_plan_and_release_notes()
    validate_workflow_wiring()
    print("macos_local_validation_track: ok")


if __name__ == "__main__":
    main()
