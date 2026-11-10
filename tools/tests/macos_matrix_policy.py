#!/usr/bin/env python3
"""Regression checks for the macOS architecture and OS-version support matrix."""

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


def validate_matrix_policy_doc() -> None:
    policy = read("docs/dev/macos-support-matrix-policy.md")

    for token in (
        "# macOS Support Matrix Policy",
        "Current macOS release artifacts are preview Apple Silicon/arm64 only",
        "The current user-facing release policy is `arm64 only`",
        "Intel Mac / `x86_64` packages",
        "universal2 packages",
        "Rosetta as a supported compatibility layer",
        "The current packaged compatibility floor is `macOS 11`",
        "latest public macOS release",
        "Architecture policy and actual CPU architecture",
        "OS matrix role",
        "Xcode and macOS SDK version",
        "OpenGL and Metal bridge signoff on the oldest supported macOS floor",
        "OpenGL and Metal bridge signoff on the latest public macOS release",
    ):
        require(policy, token, "macOS support matrix policy")


def validate_release_facing_docs() -> None:
    platform = read("docs/dev/platform-support.md")
    building = read("BUILDING.md")
    getting_started = read("docs/user/getting-started.md")
    package_readme = read("assets/release/README.html")
    release_completion = read("docs/dev/release-completion.md")
    compat = read("src/sys/macos/macos_compat.mm")

    for source, context in (
        (platform, "platform support documentation"),
        (building, "build documentation"),
    ):
        require(source, "docs/dev/macos-support-matrix-policy.md", context)
        require(source, "arm64 only", context)
        require(source, "macOS 11", context)
        require(source, "latest public macOS", context)
        require(source, "Intel Mac", context)
        require(source, "universal2", context)
        require(source, "Rosetta", context)

    require(
        platform,
        "Hosted `macos-15` CI builds prove configure, build, package, signing, notarization, and static validation paths",
        "platform support hosted CI caveat",
    )
    require(
        building,
        "oldest-floor plus latest-public-macOS signoff evidence",
        "build documentation floor/latest evidence wording",
    )
    require(
        getting_started,
        "Apple Silicon/arm64 Macs on macOS 11 or later",
        "getting started macOS floor and architecture",
    )
    require(
        getting_started,
        "Our GitHub releases do not yet publish Intel Mac or universal2 packages",
        "getting started Intel/universal2 wording",
    )
    require(getting_started, "Rosetta is not a supported release target", "getting started Rosetta wording")
    require(
        package_readme,
        "Apple Silicon/arm64 Macs on macOS 11 or later",
        "packaged README macOS floor and architecture",
    )
    require(package_readme, "Intel Mac and universal2 packages are not published yet", "packaged README Intel/universal2 wording")
    require(package_readme, "Rosetta is not a supported release target", "packaged README Rosetta wording")
    require(
        release_completion,
        "docs/dev/macos-support-matrix-policy.md",
        "release completion support matrix policy gate",
    )
    require(
        release_completion,
        "macOS floor-version evidence is recorded for the documented `macOS 11` floor",
        "release completion floor evidence gate",
    )
    require(compat, "Sys_IsTranslatedUnderRosetta", "macOS Rosetta runtime CPU summary")
    require(compat, "sysctl.proc_translated", "macOS Rosetta runtime CPU summary")
    require(compat, "Rosetta translated", "macOS Rosetta runtime CPU summary")


def validate_workflow_matrix_scope() -> None:
    manual = read(".github/workflows/manual-release.yml")
    commit = read(".github/workflows/commit-validation.yml")
    push = read(".github/workflows/push-verification.yml")

    for token in (
        "macos-arm64-opengl.dmg",
        "macos-arm64-metal.dmg",
        "macos-arm64-opengl-unsigned.tar.gz",
        "macos-arm64-metal-unsigned.tar.gz",
        '"label": f"macOS ARM64 OpenGL',
        '"label": f"macOS ARM64 Metal',
        '"binary_arch": "arm64"',
    ):
        require(manual, token, "manual release macOS arm64 matrix")

    for token in ("macos-x64", "macos-universal2", "macOS x64", "macOS universal2"):
        reject(manual, token, "manual release macOS matrix")

    for token in ("macos-universal2", "macOS universal2"):
        reject(push, token, "push verification macOS matrix")

    # Pull requests validate only the published arm64 slice. Intel builds one
    # bridge on pushes to main; the manual candidate lane assembles universal2.
    require(commit, "macos-arm64:", "commit validation macOS arm64 job")
    for token in ("macos-x64:", "macos-universal2:", "runs-on: macos-15-intel", "commit-macos-x64-"):
        reject(commit, token, "commit validation macOS matrix")
    require(push, "macos-15", "push verification hosted macOS runner")
    require(push, "macOS Intel x64 OpenGL Push Verification", "push verification Intel OpenGL job")
    reject(push, "macOS Intel x64 Metal Push Verification", "push verification Intel matrix")
    candidate = read(".github/workflows/macos-universal2-candidate.yml")
    require(candidate, "workflow_dispatch:", "manual universal2 candidate lane")
    require(candidate, '"runner": "macos-15-intel"', "manual universal2 candidate Intel thin build")


def validate_evidence_contract() -> None:
    evidence = read("docs/dev/macos-signoff-evidence.md")
    workflow_doc = read("docs/dev/macos-vm-testing-workflow.md")
    host = read("tools/macos/Invoke-openQ4MacOSWorkflow.ps1")
    guest = read("tools/macos/guest/openq4-macos-sync-build-test.sh")
    validator = read("tools/macos/validate_signoff_archive.py")
    recorder = read("tools/macos/record_signoff_evidence.py")

    for token in (
        "Architecture policy:",
        "CPU architecture:",
        "OS matrix role:",
        "macOS floor evidence:",
        "Latest public macOS evidence:",
        "Xcode version:",
        "macOS SDK version:",
    ):
        require(evidence, token, "macOS evidence index matrix fields")

    for token in (
        "Architecture policy",
        "CPU architecture",
        "OS matrix role",
        "macOS floor evidence",
        "Latest public macOS evidence",
        "Xcode version",
        "macOS SDK version",
    ):
        require(recorder, token, "macOS evidence recorder matrix fields")

    for token in (
        "MacOSOSMatrixRole",
        "floor-candidate",
        "latest-public-macos",
        "OPENQ4_MACOS_OS_MATRIX_ROLE",
    ):
        require(host, token, "macOS host workflow OS matrix role")

    for token in (
        "os_matrix_role",
        "Architecture policy: arm64-only preview release matrix",
        "OS matrix role:",
        "Xcode And SDK",
        "xcodebuild -version",
        "xcrun --sdk macosx --show-sdk-version",
    ):
        require(guest, token, "macOS guest signoff matrix metadata")

    for token in (
        "## Xcode And SDK",
        "Architecture policy:",
        "OS matrix role:",
        "missing architecture policy metadata",
        "missing OS matrix role metadata",
    ):
        require(validator, token, "macOS signoff archive matrix validation")

    for token in (
        "parse_xcode_version",
        "parse_macos_sdk_version",
        "matrix_evidence_status",
        "Latest public macOS evidence",
    ):
        require(recorder, token, "macOS evidence recorder matrix parsing")

    for token in (
        "-MacOSOSMatrixRole floor-candidate",
        "-MacOSOSMatrixRole latest-public-macos",
        "Xcode/macOS SDK",
        "floor/latest runtime signoff",
    ):
        require(workflow_doc, token, "macOS VM workflow matrix evidence docs")


def validate_ci_and_local_wiring() -> None:
    local_runner = read("tools/validation/openq4_validate.py")
    commit = read(".github/workflows/commit-validation.yml")
    push = read(".github/workflows/push-verification.yml")
    evidence_plumbing = read("tools/tests/macos_evidence_plumbing.py")

    for source, context in (
        (local_runner, "local validation runner"),
        (commit, "commit validation workflow"),
        (push, "push verification workflow"),
        (evidence_plumbing, "macOS evidence plumbing test"),
    ):
        require(source, "macos_matrix_policy.py", context)

    for source, context in (
        (commit, "commit validation workflow"),
        (push, "push verification workflow"),
    ):
        require(source, "python tools/tests/macos_matrix_policy.py", context)


def validate_phase4_plan_status() -> None:
    plan = read("docs/dev/archive/2026-10-18/plan/2026-06-30-macos-compatibility-support.md")

    for token in (
        "Phase 4: Matrix expansion",
        "- [x] Decide architecture policy for Intel/universal2.",
        "- [x] Decide OS-version validation policy for the macOS 11 floor and latest public macOS.",
        "- [x] Add guardrails for the current arm64-only matrix and floor/latest evidence fields.",
        "- [x] Add runners, build lanes, and validation only for support claims the project is ready to make.",
        "Phase 4 implementation status",
        "`docs/dev/macos-support-matrix-policy.md`",
        "`tools/tests/macos_matrix_policy.py`",
        "Intel release expansion remains deferred",
    ):
        require(plan, token, "macOS compatibility/support plan Phase 4 status")


def main() -> None:
    validate_matrix_policy_doc()
    validate_release_facing_docs()
    validate_workflow_matrix_scope()
    validate_evidence_contract()
    validate_ci_and_local_wiring()
    validate_phase4_plan_status()
    print("macos_matrix_policy: ok")


if __name__ == "__main__":
    main()
