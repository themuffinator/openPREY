#!/usr/bin/env python3
"""Regression checks for the macOS renderer and backend support policy."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def reject(haystack: str, needle: str, context: str) -> None:
    if needle in haystack:
        raise AssertionError(f"Unexpected {needle!r} in {context}")


def validate_policy_doc() -> None:
    policy = read("docs/dev/macos-renderer-backend-policy.md")

    for token in (
        "# macOS Renderer And Backend Policy",
        "`platform_backend=sdl3`",
        "`macos_graphics_bridge=opengl`",
        "`macos_graphics_bridge=metal`",
        "stock-compatible openQ4 OpenGL renderer",
        "not a native Metal renderer",
        "Release-facing package names and docs must use `OpenGL` and `Metal bridge`",
        "`renderer-smoke`, `renderer-mp-smoke`, and `renderer-matrix`",
        "Apple OpenGL remains the limiting macOS rendering dependency",
        "No native Metal renderer is selected for the current release line",
        "Stock Quake 4 material, shader, interaction, and lighting parity",
        "BSE effect rendering and lifetime behavior",
        "The legacy macOS native backend selected by `-Dplatform_backend=native` is",
        "comparison-only diagnostic infrastructure",
        "It is not a supported macOS release backend",
        "Carbon and NSOpenGL remain isolated to the native fallback boundary",
        "`macos_graphics_bridge=metal` must require `platform_backend=sdl3`",
    ):
        require(policy, token, "macOS renderer/backend policy doc")


def validate_docs() -> None:
    platform = read("docs/dev/platform-support.md")
    building = read("BUILDING.md")
    migration = read("docs/dev/archive/2026-10-18/sdl3-linux-macos-migration.md")
    workflow = read("docs/dev/macos-vm-testing-workflow.md")
    evidence = read("docs/dev/macos-signoff-evidence.md")
    getting_started = read("docs/user/getting-started.md")
    package_readme = read("assets/release/README.html")
    readme = read("README.md")
    release_completion = read("docs/dev/release-completion.md")

    for source, context in (
        (platform, "platform support docs"),
        (building, "build docs"),
        (release_completion, "release completion gate"),
        (evidence, "macOS evidence index"),
    ):
        require(source, "docs/dev/macos-renderer-backend-policy.md", context)

    for source, context in (
        (platform, "platform support docs"),
        (building, "build docs"),
        (migration, "SDL3 migration docs"),
        (workflow, "macOS workflow docs"),
        (getting_started, "getting started docs"),
        (package_readme, "packaged README"),
    ):
        require(source, "Metal bridge", context)
        require(source, "not a native Metal", context)

    for source, context in (
        (platform, "platform support native backend policy"),
        (building, "build native backend policy"),
        (migration, "SDL3 migration native backend policy"),
        (workflow, "workflow native backend policy"),
    ):
        require(source, "comparison-only", context)
        require(source, "not a supported release backend", context)

    require(readme, "OpenGL/Metal bridge packages", "README macOS bridge wording")
    require(
        release_completion,
        "do not imply native Metal or native Cocoa/OpenGL backend support",
        "release completion renderer/backend note gate",
    )


def validate_meson_policy() -> None:
    meson = read("meson.build")
    options = read("meson_options.txt")

    require(
        meson,
        "macos_graphics_bridge=metal requires platform_backend=sdl3 so the bridge stays on the shared SDL3 path",
        "Meson Metal bridge backend guard",
    )
    require(
        meson,
        "platform_backend=native on macOS is comparison-only diagnostic infrastructure",
        "Meson native backend warning",
    )
    require(
        meson,
        "Release packages use platform_backend=sdl3",
        "Meson native backend release warning",
    )
    require(
        options,
        "The macOS native backend is comparison-only; release packages use sdl3",
        "Meson option native backend description",
    )


def validate_workflow_scope() -> None:
    manual = read(".github/workflows/manual-release.yml")
    commit = read(".github/workflows/commit-validation.yml")
    push = read(".github/workflows/push-verification.yml")

    for source, context in (
        (manual, "manual release workflow"),
        (commit, "commit validation workflow"),
        (push, "push verification workflow"),
    ):
        reject(source, "-Dplatform_backend=native", context)

    for token in (
        '"platform_backend": "sdl3"',
        '"macos_graphics_bridge": "opengl"',
        '"macos_graphics_bridge": "metal"',
    ):
        require(manual, token, "manual release macOS SDL3 bridge matrix")

    for source, context in ((commit, "commit validation macOS matrix"), (push, "push verification macOS matrix")):
        require(source, "macos_graphics_bridge: opengl", context)
        require(source, "macos_graphics_bridge: metal", context)
        require(source, "-Dmacos_graphics_bridge", context)


def validate_ci_and_local_wiring() -> None:
    local_runner = read("tools/validation/openq4_validate.py")
    commit = read(".github/workflows/commit-validation.yml")
    push = read(".github/workflows/push-verification.yml")

    for source, context in (
        (local_runner, "local validation runner"),
        (commit, "commit validation workflow"),
        (push, "push verification workflow"),
    ):
        require(source, "macos_renderer_backend_policy.py", context)

    for source, context in ((commit, "commit validation workflow"), (push, "push verification workflow")):
        require(source, "python tools/tests/macos_renderer_backend_policy.py", context)


def validate_phase5_plan_status() -> None:
    plan = read("docs/dev/archive/2026-10-18/plan/2026-06-30-macos-compatibility-support.md")

    for token in (
        "Phase 5: Renderer and backend future",
        "- [x] Keep OpenGL/Metal bridge support honest and validated.",
        "- [x] Create a separate design plan if native Metal becomes a target.",
        "- [x] Decide the maintenance status of the native macOS fallback backend.",
        "Phase 5 implementation status",
        "`docs/dev/macos-renderer-backend-policy.md`",
        "`tools/tests/macos_renderer_backend_policy.py`",
        "native Cocoa/OpenGL backend is comparison-only",
    ):
        require(plan, token, "macOS compatibility/support plan Phase 5 status")


def main() -> None:
    validate_policy_doc()
    validate_docs()
    validate_meson_policy()
    validate_workflow_scope()
    validate_ci_and_local_wiring()
    validate_phase5_plan_status()
    print("macos_renderer_backend_policy: ok")


if __name__ == "__main__":
    main()
