#!/usr/bin/env python3
"""Regression checks for macOS crash-report intake and support artifact collection."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = "docs/dev/archive/2026-10-18/plans/2026-06-30-apple-support-no-macos-access.md"


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def reject(haystack: str, needle: str, context: str) -> None:
    if needle in haystack:
        raise AssertionError(f"Unexpected {needle!r} in {context}")


def require_segment(haystack: str, start: str, end: str, context: str) -> str:
    try:
        start_index = haystack.index(start)
        end_index = haystack.index(end, start_index)
    except ValueError as exc:
        raise AssertionError(f"Could not find {context} segment") from exc
    return haystack[start_index:end_index]


def validate_issue_template() -> None:
    template = read(".github/ISSUE_TEMPLATE/macos-crash-report.yml")

    for token in (
        "macOS crash report",
        "issue #73",
        "macOS support is a preview",
        "full terminal output as text, not only a screenshot",
        "openQ4 version",
        "Package artifact name",
        "OpenGL",
        "Metal bridge",
        "openQ4.app",
        "openQ4-client_arm64 from Terminal",
        "openQ4-ded_arm64 from Terminal",
        "macOS version and build",
        "Hardware model",
        "Full terminal output",
        "Saved openq4.log",
        "~/Library/Application Support/openQ4/baseoq4/logs/openq4.log",
        "macOS crash report",
        "~/Library/Logs/DiagnosticReports",
        "I tested `openQ4.app` after dragging it independently",
        "collect_macos_support_info.sh",
        "openq4-macos-support-*.tar.gz",
        "system/rosetta.txt",
        "logs/renderer-summary.txt",
        "logs/renderer-config.txt",
        "package/binary-architecture.txt",
        "package/dylib-dependencies.txt",
        "package/signing.txt",
        "package/quarantine.txt",
    ):
        require(template, token, "macOS crash issue template")


def validate_support_collector() -> None:
    script = read("tools/macos/collect_macos_support_info.sh")

    for token in (
        "#!/bin/sh",
        "umask 077",
        "OPENQ4_PACKAGE_ROOT",
        "openq4-macos-support-${STAMP}",
        "ARCHIVE_TMP",
        "MAX_SUPPORT_TEXT_BYTES",
        "MAX_CRASH_REPORT_BYTES",
        "MAX_SUPPORT_ARCHIVE_BYTES",
        "sanitize_text()",
        "limit_stream_tail()",
        "Support report output is limited to the final",
        "write_bounded_report()",
        "redact_text()",
        "/Users/[^/[:space:]]+",
        "<email>",
        "sw_vers",
        "uname -a",
        "system_profiler SPHardwareDataType",
        "system_profiler SPDisplaysDataType",
        "xcodebuild -version",
        "xcrun --sdk macosx --show-sdk-version",
        "system/rosetta.txt",
        "Rosetta is not a supported openQ4 release target",
        "sysctl.proc_translated",
        "contains_control_chars()",
        "HOME_DIR=${HOME:-}",
        "prepare_package_root()",
        "Support package root must not contain control characters",
        "Support package root must not be a symlink",
        "Support package root must be an existing directory",
        "Support output directory must not be empty",
        "Support output directory must not contain control characters",
        "Support archive target already exists",
        "Unable to create support archive temporary target",
        "Support archive temporary target must be a regular file",
        ".XXXXXX.tar.gz.tmp",
        "Support archive target appeared while collecting data",
        "Source file was larger than",
        'tail -c "${max_bytes}"',
        "truncated copy failed; source was not copied",
        "codesign",
        "spctl --assess --type execute --verbose=4",
        "xcrun stapler validate",
        "xattr",
        "file",
        "lipo -archs",
        "otool -L",
        "otool -D",
        "com.apple.quarantine",
        "openQ4.app",
        "baseoq4",
        "openQ4-client_arm64",
        "openQ4-ded_arm64",
        "collect_macos_support_info.sh",
        "openq4.log",
        "logs/renderer-summary.txt",
        "logs/renderer-config.txt",
        "R_InitOpenGL",
        "Renderer driver quirks",
        "ARB2 interaction driver bypass",
        "material_interaction",
        "GLSL material interaction",
        "idRenderTexture",
        "GL_FRAMEBUFFER_",
        "Forward render target MSAA:",
        "MSAA requested",
        "_forwardRender",
        "Filesystem paths:",
        "Selected game module:",
        "Game module search failed:",
        "Game module load failed:",
        "dlopen .* failed:",
        "fatal signal SIGSEGV",
        "package/binary-architecture.txt",
        "Architecture checks do not launch openQ4.",
        "package/dylib-dependencies.txt",
        "Dependency and install-name checks do not launch openQ4.",
        "package/signing.txt",
        "Signing and Gatekeeper checks do not launch openQ4.",
        "stapler validation failed; continuing support collection",
        "package/quarantine.txt",
        "Only extended-attribute names are listed; values are not copied.",
        "write_openq4_log_candidate_paths()",
        "write_openq4_renderer_config_candidate_paths()",
        "${HOME_DIR}/Library/Application Support/openQ4/baseoq4/logs/openq4.log",
        "${HOME_DIR}/Library/Application Support/openQ4/baseoq4/openQ4Config.cfg",
        "Only renderer and performance settings are copied",
        "r_[[:alnum:]_]+",
        "com_(machineSpec|performancePreset)",
        "Bindings, player/account, network, audio-device, and arbitrary config settings are excluded.",
        "HOME was not set; home-scoped openq4.log paths were skipped.",
        "HOME was not set; saved openQ4Config.cfg paths were skipped.",
        "HOME was not set; home-scoped openq4.log files were skipped.",
        "HOME was not set; the macOS DiagnosticReports directory could not be located.",
        "path_exists_for_inspection()",
        "Skipped symlinked source:",
        "copy_crash_report_if_safe()",
        "The support collector only copies DiagnosticReports files with archive-safe names.",
        "support collector does not follow symlinks",
        "The collector does not follow symlinked package, log, or crash-report inputs",
        "~/Library/Logs/DiagnosticReports",
        "-name 'openQ4*.ips'",
        "-name 'openQ4*.crash'",
        "-name 'openQ4-client*.ips'",
        "-name 'openQ4-client*.crash'",
        "-name 'openQ4-ded*.ips'",
        "-name 'openQ4-ded*.crash'",
        "tail -n 10",
        "openQ4, openQ4-client, and openQ4-ded DiagnosticReports",
        "tar -czf",
        "tar -tzf",
        "Support archive is empty or unreadable before publish",
        "Support archive validation failed before publish",
        "Support archive is too large before publish",
        'ln "${ARCHIVE_TMP}" "${ARCHIVE_PATH}"',
        'chmod 600 "${ARCHIVE_TMP}"',
        "does not dump the environment",
        "does not launch openQ4",
        "does not copy retail q4base PK4 assets",
    ):
        require(script, token, "macOS support collector")

    for token in (
        "printenv",
        "env >",
        "set >",
        "openQ4-client_arm64 >",
        "openQ4-client_arm64 2>",
        "openQ4-client_x64 >",
        "openQ4-client_x64 2>",
        "openQ4-client_x86 >",
        "openQ4-client_x86 2>",
        "openQ4-ded_arm64 >",
        "openQ4-ded_arm64 2>",
        "openQ4-ded_x64 >",
        "openQ4-ded_x64 2>",
        "openQ4-ded_x86 >",
        "openQ4-ded_x86 2>",
        "xattr -l",
        "xattr -p",
        "xattr -w",
        "|| cat",
        'tail -c "${max_bytes}" < "${source_path}" 2>/dev/null || cat',
    ):
        reject(script, token, "macOS support collector privacy/no-launch guard")

    reject(
        script,
        'copy_text_if_present "${HOME_DIR}/Library/Application Support/openQ4/baseoq4/openQ4Config.cfg"',
        "macOS support collector renderer-config privacy guard",
    )

    signing_segment = require_segment(
        script,
        "Signing and Gatekeeper checks do not launch openQ4.",
        '} | write_bounded_report "package/signing.txt"',
        "macOS support collector signing",
    )
    quarantine_segment = require_segment(
        script,
        "Only extended-attribute names are listed; values are not copied.",
        '} | write_bounded_report "package/quarantine.txt"',
        "macOS support collector quarantine",
    )

    for segment, context in (
        (signing_segment, "macOS support collector signing"),
        (quarantine_segment, "macOS support collector quarantine"),
    ):
        for token in (
            "openQ4-client_arm64",
            "openQ4-client_x64",
            "openQ4-client_x86",
            "openQ4-ded_arm64",
            "openQ4-ded_x64",
            "openQ4-ded_x86",
        ):
            require(segment, token, context)


def validate_user_docs() -> None:
    support_doc = read("docs/user/macos-support-data.md")
    readme = read("README.md")
    getting_started = read("docs/user/getting-started.md")
    package_readme = read("assets/release/README.html")
    release_notes = read("docs/dev/releases/v0.6.5.md")

    for token in (
        "# macOS Support Data",
        "GitHub issue #73",
        "Full terminal output as text, not only a screenshot",
        "openQ4-ded_arm64` from Terminal",
        "./openQ4-ded_arm64 +set dedicated 1",
        "~/Library/Application Support/openQ4/baseoq4/logs/openq4.log",
        "~/Library/Logs/DiagnosticReports",
        "~/Library/Logs/DiagnosticReports/openQ4-ded*.ips",
        "~/Library/Logs/DiagnosticReports/openQ4-ded*.crash",
        "collect_macos_support_info.sh",
        "openq4-macos-support-YYYYMMDD-HHMMSSZ.tar.gz",
        "system/rosetta.txt",
        "logs/renderer-summary.txt",
        "logs/renderer-config.txt",
        "package/binary-architecture.txt",
        "package/dylib-dependencies.txt",
        "package/signing.txt",
        "package/quarantine.txt",
        "com.apple.quarantine",
        "does not dump the environment",
        "does not launch openQ4",
        "does not copy retail `q4base` PK4 assets",
        "does not follow symlinked package, log, or crash-report inputs",
        "DiagnosticReports filename contains unusual characters",
        "only `openQ4.app` to `/Applications` is supported.",
    ):
        require(support_doc, token, "macOS support-data guide")

    require(readme, "docs/user/macos-support-data.md", "README macOS support-data link")
    require(getting_started, "macos-support-data.md", "getting started macOS support-data link")
    require(package_readme, "docs/docs/user/macos-support-data.html", "packaged README macOS support-data link")
    require(package_readme, "collect_macos_support_info.sh", "packaged README macOS collector mention")
    require(release_notes, "collect_macos_support_info.sh", "curated release notes macOS collector request")
    require(release_notes, "system/rosetta.txt", "curated release notes Rosetta diagnostics mention")
    require(release_notes, "logs/renderer-summary.txt", "curated release notes renderer-summary mention")
    require(release_notes, "logs/renderer-config.txt", "curated release notes renderer-config mention")
    require(release_notes, "package/binary-architecture.txt", "curated release notes binary-architecture diagnostics mention")
    require(release_notes, "package/dylib-dependencies.txt", "curated release notes dylib-dependencies diagnostics mention")
    require(release_notes, "package/signing.txt", "curated release notes signing diagnostics mention")
    require(release_notes, "package/quarantine.txt", "curated release notes quarantine diagnostics mention")
    require(release_notes, "../../user/macos-support-data.md", "curated release notes macOS support-data link")


def validate_packaging_contract() -> None:
    packaging = read("tools/build/package_nightly.py")
    validator = read("tools/validation/openq4_validate.py")
    meson = read("meson.build")

    for token in (
        'MACOS_SUPPORT_INFO_SCRIPT_PATH = Path("tools") / "macos" / "collect_macos_support_info.sh"',
        'MACOS_SUPPORT_INFO_SCRIPT_NAME = "collect_macos_support_info.sh"',
        "MACOS_SUPPORT_INFO_REQUIRED_TOKENS",
        "MACOS_SUPPORT_INFO_FORBIDDEN_TOKENS",
        "MAX_MACOS_SUPPORT_INFO_SCRIPT_BYTES",
        "validate_macos_support_info_script_bytes",
        "forbidden privacy/no-launch pattern",
        "sanitize_text()",
        "limit_stream_tail()",
        "Support report output is limited to the final",
        "contains_control_chars()",
        "Support package root must not contain control characters",
        "Support output directory must not contain control characters",
        ".XXXXXX.tar.gz.tmp",
        "openQ4-client_x64 >",
        "openQ4-ded_x64 >",
        "|| cat",
        'tail -c "${max_bytes}" < "${source_path}" 2>/dev/null || cat',
        "def copy_release_collateral(source_root: Path, package_root: Path, platform: str) -> None:",
        'if platform == "macos":',
        "source_root / MACOS_SUPPORT_INFO_SCRIPT_PATH",
        "package_root / MACOS_SUPPORT_INFO_SCRIPT_NAME",
        "ensure_posix_executable(destination)",
        "Path(MACOS_SUPPORT_INFO_SCRIPT_NAME)",
        'f"{package_prefix}{MACOS_SUPPORT_INFO_SCRIPT_NAME}"',
        "copy_release_collateral(source_root, package_root, args.platform)",
    ):
        require(packaging, token, "macOS collector packaging contract")

    for token in (
        "MACOS_SUPPORT_INFO_FORBIDDEN_TOKENS",
        "forbidden privacy/no-launch pattern",
        "sanitize_text()",
        "limit_stream_tail()",
        "Support report output is limited to the final",
        "contains_control_chars()",
        "Support package root must not contain control characters",
        "Support output directory must not contain control characters",
        ".XXXXXX.tar.gz.tmp",
        "openQ4-client_x64 >",
        "openQ4-ded_x64 >",
        "|| cat",
        'tail -c "${max_bytes}" < "${source_path}" 2>/dev/null || cat',
    ):
        require(validator, token, "macOS collector staged validation contract")

    for token in (
        "host_system == 'darwin'",
        "'tools/macos/collect_macos_support_info.sh'",
        "install_mode: 'rwxr-xr-x'",
    ):
        require(meson, token, "macOS collector Meson staging contract")


def validate_phase1_plan_status() -> None:
    plan = read(PLAN_PATH)

    for token in (
        "## Phase 1: Improve Issue #73 Triage Without Running macOS",
        "- [x] Add a macOS issue/support template requesting:",
        "- [x] Add a short packaged `collect_macos_support_info.sh` helper that gathers",
        "- [x] Make the helper redact obvious user secrets from paths or environment",
        "- [x] Add a docs page explaining how users can provide crash data without",
        "- [x] Link the support-data request from issue #73 and future macOS release",
        "Phase 1 implementation status",
        ".github/ISSUE_TEMPLATE/macos-crash-report.yml",
        "docs/user/macos-support-data.md",
        "tools/macos/collect_macos_support_info.sh",
        "tools/tests/macos_support_intake.py",
        "system/rosetta.txt",
        "logs/renderer-summary.txt",
        "logs/renderer-config.txt",
        "package/binary-architecture.txt",
        "package/dylib-dependencies.txt",
        "package/signing.txt",
        "package/quarantine.txt",
    ):
        require(plan, token, "Phase 1 Apple support plan")


def validate_ci_and_local_wiring() -> None:
    local_runner = read("tools/validation/openq4_validate.py")
    commit = read(".github/workflows/commit-validation.yml")
    push = read(".github/workflows/push-verification.yml")
    macos_debug = read(".github/workflows/macos-debug.yml")

    for source, context in (
        (local_runner, "local validation runner"),
        (commit, "commit validation workflow"),
        (push, "push verification workflow"),
        (macos_debug, "macOS debug workflow"),
    ):
        require(source, "macos_support_intake.py", context)

    for source, context in (
        (commit, "commit validation workflow"),
        (push, "push verification workflow"),
        (macos_debug, "macOS debug workflow"),
    ):
        require(source, "python tools/tests/macos_support_intake.py", context)


def main() -> None:
    validate_issue_template()
    validate_support_collector()
    validate_user_docs()
    validate_packaging_contract()
    validate_phase1_plan_status()
    validate_ci_and_local_wiring()
    print("macos_support_intake: ok")


if __name__ == "__main__":
    main()
