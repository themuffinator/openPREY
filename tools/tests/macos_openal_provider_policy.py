#!/usr/bin/env python3
"""Static checks for the macOS OpenAL Soft release/package policy."""

from __future__ import annotations

import re
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


def reject_regex(haystack: str, pattern: str, context: str) -> None:
    if re.search(pattern, haystack, flags=re.IGNORECASE | re.DOTALL):
        raise AssertionError(f"Unexpected pattern {pattern!r} in {context}")


def validate_meson_provider_switch() -> None:
    options = read("meson_options.txt")
    meson = read("meson.build")
    for token in (
        "'macos_openal_provider'",
        "choices: ['apple_framework', 'system']",
        "value: 'apple_framework'",
        "Release workflows use system with the pinned, bundled OpenAL Soft runtime",
        "OpenAL Soft-style AL/... headers",
    ):
        require(options, token, "macOS OpenAL provider Meson option")

    for token in (
        "dependency('appleframeworks', modules: ['OpenAL'], required: true)",
        "dependency('openal', required: true, method: 'pkg-config')",
        "if macos_openal_provider == 'system'",
        "-DUSE_OPENAL_SOFT_INCLUDES=1",
        "@loader_path/Frameworks:@loader_path/../Frameworks:@loader_path/openQ4.app/Contents/Frameworks",
        "install_rpath: macos_openal_install_rpath",
        "'macOS OpenAL provider': macos_openal_provider",
    ):
        require(meson, token, "macOS OpenAL provider Meson wiring")


def validate_pinned_builder_and_licensing() -> None:
    script = read("tools/build/prepare_macos_openal_soft.sh")
    source_notice = read("src/external/openal-soft/SOURCE.md")
    copying = read("src/external/openal-soft/COPYING")
    for token in (
        'OPENAL_SOFT_VERSION="1.25.2"',
        'OPENAL_SOFT_ARCHIVE_SHA256="fb27e5839aa11f0e5b9d33756965291fad5d6909ab928ea1f796f4a1a6877894"',
        '[[ ! "${OPENAL_SOFT_ARCHIVE_SHA256}" =~ ^[0-9a-f]{64}$ ]]',
        "https://github.com/kcat/openal-soft/archive/refs/tags/",
        "-DCMAKE_OSX_DEPLOYMENT_TARGET=",
        "-DLIBTYPE=SHARED",
        "-DALSOFT_BACKEND_COREAUDIO=ON",
        "-DALSOFT_REQUIRE_COREAUDIO=ON",
        "-DALSOFT_OSX_FRAMEWORK=OFF",
        'OPENAL_SOFT_INSTALL_NAME="@rpath/${OPENAL_SOFT_DYLIB_NAME}"',
        'prefix=${pcfiledir}/../..',
        'exec_prefix=${prefix}',
        'libdir=${exec_prefix}/lib',
        'includedir=${prefix}/include',
        'chmod 0755 "${installed_runtime}"',
        '"${stage_install_dir}/Frameworks"',
        '"${stage_install_dir}/licenses/openal-soft"',
        "openal-soft-${OPENAL_SOFT_VERSION}.tar.gz",
        "src/external/openal-soft/COPYING",
        "src/external/openal-soft/SOURCE.md",
        '"${source_root}/LICENSE-pffft"',
        '"${source_root}/fmt-11.2.0/LICENSE"',
        '"${source_root}/gsl/LICENSE"',
    ):
        require(script, token, "pinned macOS OpenAL Soft builder")
    for token in (
        "[OpenAL Soft](https://openal-soft.org/)",
        "version 1.25.2",
        "openal-soft-1.25.2.tar.gz",
        "fb27e5839aa11f0e5b9d33756965291fad5d6909ab928ea1f796f4a1a6877894",
        "prepare_macos_openal_soft.sh",
        "LICENSE-pffft",
        "LICENSE-fmt",
        "LICENSE-gsl",
    ):
        require(source_notice, token, "OpenAL Soft source notice")
    require(copying, "GNU LIBRARY GENERAL PUBLIC LICENSE", "OpenAL Soft license")


def validate_release_workflows() -> None:
    manual = read(".github/workflows/manual-release.yml")
    commit = read(".github/workflows/commit-validation.yml")
    push = read(".github/workflows/push-verification.yml")
    universal = read(".github/workflows/macos-universal2-candidate.yml")
    sanitizer = read(".github/workflows/macos-sanitizer.yml")
    debug = read(".github/workflows/macos-debug.yml")

    require(manual, '"platform": "macos"', "manual release macOS matrix")
    require(manual, '"macos_openal_provider": "system"', "manual release OpenAL Soft pin")
    for token in (
        'openal_runtime="${module_dir}/libopenal.1.dylib"',
        "@rpath/libopenal.1.dylib)",
        'if [ ! -f "${openal_runtime}" ]; then',
        '"${renderer_module}" "${openal_runtime}"',
        'check_macos_install_name "${openal_runtime}" "@rpath/libopenal.1.dylib"',
    ):
        require(manual, token, "manual release bundled OpenAL dependency audit")
    for source, context in (
        (manual, "manual release workflow"),
        (commit, "commit validation workflow"),
        (push, "push verification workflow"),
        (universal, "universal2 candidate workflow"),
        (sanitizer, "macOS sanitizer workflow"),
        (debug, "macOS debug workflow"),
    ):
        require(source, "prepare_macos_openal_soft.sh", context)
    require(commit, "macos_openal_provider: system", "commit validation OpenAL Soft pin")
    require(push, "macos_openal_provider: system", "push validation OpenAL Soft pin")
    for source, context in (
        (universal, "universal2 candidate workflow"),
        (sanitizer, "macOS sanitizer workflow"),
        (debug, "macOS debug workflow"),
    ):
        require(source, "macos_openal_provider=system", context)
    for source, context in (
        (manual, "manual release workflow"),
        (commit, "commit validation workflow"),
        (push, "push verification workflow"),
        (universal, "universal2 candidate workflow"),
        (sanitizer, "macOS sanitizer workflow"),
        (debug, "macOS debug workflow"),
    ):
        require(source, "--stage-install-dir .install", context)
    require(universal, "--openal-provider system", "universal2 provenance")
    require(debug, "macOS Apple OpenAL Compatibility Corridor", "Apple OpenAL diagnostic lane")
    require(debug, "-Dmacos_openal_provider=apple_framework", "Apple OpenAL diagnostic lane")
    reject_regex(
        manual,
        r'"platform":\s*"macos".{0,400}"macos_openal_provider":\s*"apple_framework"',
        "manual release macOS matrix",
    )


def validate_package_contract() -> None:
    package = read("tools/build/package_nightly.py")
    assembler = read("tools/build/assemble_macos_universal2.py")
    validator = read("tools/validation/openq4_validate.py")
    for token in (
        'MACOS_OPENAL_SOFT_DYLIB_NAME = "libopenal.1.dylib"',
        'MACOS_OPENAL_SOFT_INSTALL_NAME = f"@rpath/{MACOS_OPENAL_SOFT_DYLIB_NAME}"',
        'MACOS_APP_OPENAL_LICENSE_DIR = MACOS_APP_RESOURCES_DIR / "licenses" / "openal-soft"',
        "macos_embedded_openal_soft_path",
        "copy_macos_openal_soft_licenses",
        "MACOS_OPENAL_SOFT_LICENSE_FILES",
        "openal-soft-1.25.2.tar.gz",
        "macOS client does not use exactly one bundled OpenAL Soft dependency",
        "misplaced OpenAL Soft runtime copies",
        "macos_embedded_library_paths",
    ):
        require(package, token, "macOS package OpenAL Soft contract")
    for token in (
        'OPENAL_PROVIDERS = ("apple_framework", "system")',
        'OPENAL_SOFT_RELATIVE_PATH = Path("Frameworks") / OPENAL_SOFT_DYLIB_NAME',
        '"openal-soft": OPENAL_SOFT_RELATIVE_PATH',
        "OPENAL_SOFT_INSTALL_NAME",
        '"licenses/openal-soft/COPYING"',
        '"licenses/openal-soft/LICENSE-pffft"',
        '"licenses/openal-soft/LICENSE-fmt"',
        '"licenses/openal-soft/LICENSE-gsl"',
        '"licenses/openal-soft/SOURCE.md"',
        '"licenses/openal-soft/openal-soft-1.25.2.tar.gz"',
    ):
        require(assembler, token, "macOS universal2 OpenAL Soft contract")
    for token in (
        'MACOS_OPENAL_SOFT_DYLIB_NAME = "libopenal.1.dylib"',
        "MACOS_OPENAL_SOFT_LICENSE_FILES",
        "selected_macos_openal_provider",
        'intro-buildoptions.json',
        'if openal_provider == "system":',
        'install_root / "Frameworks" / MACOS_OPENAL_SOFT_DYLIB_NAME',
        "missing OpenAL Soft license/source payload",
    ):
        require(validator, token, "staged macOS OpenAL Soft validation")


def validate_nonfatal_allocation_policy() -> None:
    sample_header = read("src/sound/OpenAL/AL_SoundSample.h")
    sample_source = read("src/sound/OpenAL/AL_SoundSample.cpp")
    voice_source = read("src/sound/OpenAL/AL_SoundVoice.cpp")
    require(sample_header, "openalBufferUploadFailed", "OpenAL sample state")
    for token in (
        "openQ4_openALBufferAllocationWarningIssued",
        "continuing with streaming fallback where resources permit",
        "Further allocation failures are suppressed",
        "openalBufferUploadFailed = true",
        "CreateOpenALBuffer();",
    ):
        require(sample_source, token, "non-fatal OpenAL sample upload")
    reject(
        sample_source,
        'common->Error( "idSoundSample_OpenAL::CreateOpenALBuffer: error generating OpenAL hardware buffer"',
        "OpenAL allocation failure policy",
    )
    reject(
        sample_source,
        'common->Error( "idSoundSample_OpenAL::MakeDefault: error generating OpenAL hardware buffer"',
        "default-sample allocation failure policy",
    )
    require(voice_source, "EnsureStreamingBuffers()", "OpenAL voice streaming fallback")


def validate_docs_and_attribution() -> None:
    policy = read("docs/dev/macos-openal-provider-policy.md")
    building = read("BUILDING.md")
    platform = read("docs/dev/platform-support.md")
    workflow = read("docs/dev/macos-vm-testing-workflow.md")
    readme = read("README.md")
    getting_started = read("docs/user/getting-started.md")
    package_readme = read("assets/release/README.html")
    release_completion = read("docs/dev/release-completion.md")
    for token in (
        "-Dmacos_openal_provider=system",
        "checksum-pinned OpenAL Soft 1.25.2",
        "openQ4.app/Contents/Frameworks/libopenal.1.dylib",
        "@rpath/libopenal.1.dylib",
        "Codesigning and notarization",
        "COPYING",
        "PFFFT/fmt/Microsoft GSL notices",
        "SOURCE.md",
        "openal-soft-1.25.2.tar.gz",
        "Allocation-failure behavior",
        "logs/openal-summary.txt",
        "must not launch openQ4",
    ):
        require(policy, token, "macOS OpenAL provider policy")
    for source, context in (
        (building, "build documentation"),
        (platform, "platform support documentation"),
        (workflow, "macOS workflow documentation"),
    ):
        require(source, "OpenAL Soft", context)
        require(source, "docs/dev/macos-openal-provider-policy.md", context)
    require(readme, "[OpenAL Soft](https://openal-soft.org/)", "README attribution")
    require(getting_started, "no Homebrew or separate audio install is required", "player setup guide")
    require(package_readme, "no Homebrew or separate audio install is required", "packaged README")
    require(release_completion, "This resolves GitHub issue #122", "candidate release notes")
    reject(platform, "current macOS packages do not bundle OpenAL Soft", "current platform documentation")
    reject(building, "current macOS packages do not bundle OpenAL Soft", "current build documentation")


def validate_support_and_wiring() -> None:
    template = read(".github/ISSUE_TEMPLATE/macos-crash-report.yml")
    collector = read("tools/macos/collect_macos_support_info.sh")
    support_doc = read("docs/user/macos-support-data.md")
    local_runner = read("tools/validation/openq4_validate.py")
    for token in (
        "OpenAL vendor:",
        "OpenAL renderer:",
        "OpenAL active device:",
        "OpenAL EFX",
        "logs/openal-summary.txt",
    ):
        require(template + collector + support_doc, token, "macOS OpenAL support intake")
    require(local_runner, "macos_openal_provider_policy.py", "local validation runner")


def main() -> None:
    validate_meson_provider_switch()
    validate_pinned_builder_and_licensing()
    validate_release_workflows()
    validate_package_contract()
    validate_nonfatal_allocation_policy()
    validate_docs_and_attribution()
    validate_support_and_wiring()
    print("macos_openal_provider_policy: ok")


if __name__ == "__main__":
    main()
