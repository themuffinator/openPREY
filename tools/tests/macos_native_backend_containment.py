#!/usr/bin/env python3
"""Static containment checks for legacy and future macOS backend paths."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "src"

SDL3_FORBIDDEN_TOKENS = (
    "#import <Carbon",
    "#include <Carbon",
    "Carbon/Carbon.h",
    "Carbon.framework",
    "NSOpenGL",
    "NSOpenGLContext",
    "NSOpenGLPixelFormat",
    "CGLContextObj",
    # CGL context/present call surface; CGLQueryRendererInfo/CGLDescribeRenderer
    # stay allowed for the SDL3-path VRAM probe in macos_compat.mm.
    "CGLCreateContext",
    "CGLSetCurrentContext",
    "CGLGetCurrentContext",
    "CGLFlushDrawable",
    "CGLSetFullScreen",
    "CGLDestroyContext",
    "aglCreateContext",
)

# Headers that are allowed to hold native NSOpenGL/CGL tokens; imported only by
# the native comparison backend (macos_glimp.mm).
NATIVE_ONLY_OSX_HEADERS = (
    "src/sys/macos/macos_native_gl.h",
)

NATIVE_METAL_IMPLEMENTATION_TOKENS = (
    "#import <Metal/",
    "#include <Metal/",
    "#import <MetalKit/",
    "#include <MetalKit/",
    "#import <QuartzCore/CAMetalLayer",
    "#include <QuartzCore/CAMetalLayer",
    "MTLCreateSystemDefaultDevice",
    "id<MTL",
    "CAMetalLayer",
    "MTKView",
    "MTLCommandQueue",
    "MTLRenderPipeline",
    "MTLDevice",
)

FORBIDDEN_RELEASE_NOTE_PATTERNS = (
    re.compile(r"\bnative macos backend support\b", re.IGNORECASE),
    re.compile(r"\bnative cocoa/opengl support\b", re.IGNORECASE),
    re.compile(r"\bsupported native backend\b", re.IGNORECASE),
    re.compile(r"\bnative backend is supported\b", re.IGNORECASE),
    re.compile(r"\bnative metal renderer support\b", re.IGNORECASE),
    re.compile(r"\bopengl-free renderer\b", re.IGNORECASE),
)


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def read_source(relative_path: str) -> str:
    return (SOURCE_ROOT / relative_path).read_text(encoding="utf-8", errors="ignore")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def reject(haystack: str, needle: str, context: str) -> None:
    if needle in haystack:
        raise AssertionError(f"Unexpected {needle!r} in {context}")


def require_before(haystack: str, first: str, second: str, context: str) -> None:
    first_index = haystack.find(first)
    second_index = haystack.find(second)
    if first_index == -1 or second_index == -1 or first_index >= second_index:
        raise AssertionError(f"Expected {first!r} before {second!r} in {context}")


def load_meson_sources_module():
    module_path = ROOT / "tools" / "build" / "meson_sources.py"
    spec = importlib.util.spec_from_file_location("openq4_meson_sources", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not load Meson source manifest module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def active_darwin_sources() -> tuple[set[str], set[str]]:
    module = load_meson_sources_module()
    return set(module.SDL3_DARWIN_SOURCES), set(module.DARWIN_PLATFORM_SOURCES)


def active_sources_containing(token: str, sources: set[str]) -> list[str]:
    hits: list[str] = []
    for relative_path in sorted(sources):
        if token in read_source(relative_path):
            hits.append(relative_path)
    return hits


def implementation_sources() -> list[Path]:
    paths: set[Path] = set()
    for root in (
        SOURCE_ROOT / "renderer",
        SOURCE_ROOT / "sys" / "macos",
        SOURCE_ROOT / "sys" / "posix",
        SOURCE_ROOT / "sys" / "sdl3",
    ):
        for path in root.rglob("*"):
            if path.suffix in {".c", ".cpp", ".h", ".m", ".mm"}:
                paths.add(path)
    return sorted(paths)


def validate_source_manifest_boundary() -> None:
    sdl3, native = active_darwin_sources()

    for required in (
        "sys/macos/macos_sdl3.cpp",
        "sys/macos/macos_sdl3_main.cpp",
        "sys/macos/macos_compat.mm",
        "sys/macos/macos_misc.mm",
    ):
        if required not in sdl3:
            raise AssertionError(f"Missing {required!r} from SDL3_DARWIN_SOURCES")

    for native_only in ("sys/macos/macos_event.mm", "sys/macos/macos_glimp.mm"):
        if native_only not in native:
            raise AssertionError(f"Missing {native_only!r} from DARWIN_PLATFORM_SOURCES")
        if native_only in sdl3:
            raise AssertionError(f"{native_only!r} leaked into SDL3_DARWIN_SOURCES")

    active = sdl3 | native
    carbon_hits = active_sources_containing("Carbon", active)
    if carbon_hits != ["sys/macos/macos_event.mm"]:
        raise AssertionError(f"Carbon escaped the native event boundary: {carbon_hits!r}")

    nsopengl_hits = active_sources_containing("NSOpenGL", active)
    if nsopengl_hits != ["sys/macos/macos_glimp.mm"]:
        raise AssertionError(f"NSOpenGL escaped the native GL boundary: {nsopengl_hits!r}")

    cgl_hits = active_sources_containing("CGLContextObj", active)
    if cgl_hits != ["sys/macos/macos_glimp.mm"]:
        raise AssertionError(f"CGL context APIs escaped the native GL boundary: {cgl_hits!r}")


def validate_sdl3_sources_are_carbon_free() -> None:
    sdl3, _native = active_darwin_sources()
    for relative_path in sorted(sdl3):
        source = read_source(relative_path)
        for token in SDL3_FORBIDDEN_TOKENS:
            if token in source:
                raise AssertionError(
                    f"SDL3 Darwin source {relative_path} contains forbidden native token {token!r}"
                )


def validate_osx_headers_are_native_token_free() -> None:
    for allowed in NATIVE_ONLY_OSX_HEADERS:
        if not (ROOT / allowed).is_file():
            raise AssertionError(f"Missing allowlisted native-only header {allowed!r}")
    for path in sorted((SOURCE_ROOT / "sys" / "macos").rglob("*.h")):
        relative = path.relative_to(ROOT).as_posix()
        if relative in NATIVE_ONLY_OSX_HEADERS:
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        for token in SDL3_FORBIDDEN_TOKENS:
            if token in source:
                raise AssertionError(
                    f"macOS header {relative} contains forbidden native token {token!r}"
                )


def validate_meson_framework_boundary() -> None:
    meson = read("meson.build")

    require(
        meson,
        "macos_framework_modules = ['Cocoa', 'OpenGL', 'ApplicationServices']",
        "macOS SDL3 framework list",
    )
    require(
        meson,
        "if not use_sdl3_backend\n      macos_framework_modules += ['Carbon']",
        "macOS native-only Carbon framework gate",
    )
    reject(
        meson,
        "macos_framework_modules = ['Cocoa', 'OpenGL', 'ApplicationServices', 'Carbon']",
        "macOS unconditional Carbon framework list",
    )
    require_before(
        meson,
        "if use_macos_metal_bridge",
        "modules: ['Metal', 'QuartzCore']",
        "macOS Metal bridge framework gate",
    )
    require(
        meson,
        "macos_graphics_bridge=metal requires platform_backend=sdl3 so the bridge stays on the shared SDL3 path",
        "macOS Metal bridge SDL3 guard",
    )


def validate_native_metal_not_implemented() -> None:
    for path in implementation_sources():
        source = path.read_text(encoding="utf-8", errors="ignore")
        for token in NATIVE_METAL_IMPLEMENTATION_TOKENS:
            if token in source:
                relative = path.relative_to(ROOT).as_posix()
                raise AssertionError(f"Native Metal implementation token {token!r} found in {relative}")


def validate_policy_docs() -> None:
    containment = read("docs/dev/macos-native-backend-containment-policy.md")
    renderer = read("docs/dev/macos-renderer-backend-policy.md")
    platform = read("docs/dev/platform-support.md")
    building = read("BUILDING.md")
    release_completion = read("docs/dev/release-completion.md")

    for token in (
        "# macOS Native Backend Containment Policy",
        "`platform_backend=sdl3`",
        "`platform_backend=native` Cocoa/OpenGL backend is retained only as",
        "comparison-only diagnostic infrastructure",
        "The native backend is not kept indefinitely by default",
        "separate native-backend removal plan",
        "`src/sys/macos/macos_event.mm` is the native Carbon event/input boundary",
        "`src/sys/macos/macos_glimp.mm` is the native NSOpenGL/CGL context boundary",
        "SDL3 macOS sources must not import Carbon, link Carbon, or use NSOpenGL/CGL",
        "Curated release notes may say that the native backend is comparison-only",
        "native macOS backend support, native Cocoa/OpenGL",
        "No native Metal renderer is selected for the current release line",
        "Stock Quake 4 material, shader, interaction, and lighting parity",
        "BSE effect rendering and lifetime behavior",
        "Screenshot, readback, video, and diagnostic capture behavior",
        "Fallback and rollback behavior",
        "Package names, release notes, and signoff evidence",
        "`tools/tests/macos_native_backend_containment.py`",
        "static guard only and does not claim macOS runtime or Finder coverage",
    ):
        require(containment, token, "macOS native backend containment policy")

    for source, context in (
        (renderer, "renderer/backend policy"),
        (platform, "platform support docs"),
        (building, "build docs"),
        (release_completion, "release completion notes"),
    ):
        require(source, "docs/dev/macos-native-backend-containment-policy.md", context)


def validate_release_note_wording() -> None:
    for release_path in sorted((ROOT / "docs" / "dev" / "releases").glob("v*.md")):
        source = release_path.read_text(encoding="utf-8")
        context = release_path.relative_to(ROOT).as_posix()
        require(source, "Metal bridge around the OpenGL renderer, not a native Metal renderer", context)
        require(source, "comparison-only diagnostic infrastructure, not a release backend", context)
        for pattern in FORBIDDEN_RELEASE_NOTE_PATTERNS:
            if pattern.search(source):
                raise AssertionError(f"Forbidden native-backend support wording in {context}: {pattern.pattern}")


def validate_phase7_plan_status() -> None:
    plan = read("docs/dev/archive/2026-10-18/plans/2026-06-30-apple-support-no-macos-access.md")
    for token in (
        "## Phase 7: Contain Legacy And Future Renderer Paths",
        "- [x] Keep Carbon and NSOpenGL isolated to the native comparison backend.",
        "- [x] Add a static guard that SDL3 macOS sources never import or link Carbon.",
        "- [x] Keep native Cocoa/OpenGL backend support wording out of release notes.",
        "removal plan after SDL3 coverage is mature.",
        "- [x] Keep native Metal out of implementation work until a separate design plan",
        "Phase 7 implementation status",
        "`docs/dev/macos-native-backend-containment-policy.md`",
        "`tools/tests/macos_native_backend_containment.py`",
        "No macOS platform testing is required or claimed for Phase 7.",
    ):
        require(plan, token, "Apple support plan Phase 7 status")


def validate_ci_and_local_wiring() -> None:
    script = "tools/tests/macos_native_backend_containment.py"
    validator = read("tools/validation/openq4_validate.py")
    commit = read(".github/workflows/commit-validation.yml")
    push = read(".github/workflows/push-verification.yml")
    macos_debug = read(".github/workflows/macos-debug.yml")

    require(validator, "macos_native_backend_containment.py", "local validation runner")
    for source, context in (
        (commit, "commit validation workflow"),
        (push, "push verification workflow"),
        (macos_debug, "macOS debug workflow"),
    ):
        require(source, script, context)

    for source, context in (
        (commit, "commit validation workflow"),
        (push, "push verification workflow"),
        (macos_debug, "macOS debug workflow"),
    ):
        require(source, f"python {script}", context)


def main() -> None:
    validate_source_manifest_boundary()
    validate_sdl3_sources_are_carbon_free()
    validate_osx_headers_are_native_token_free()
    validate_meson_framework_boundary()
    validate_native_metal_not_implemented()
    validate_policy_docs()
    validate_release_note_wording()
    validate_phase7_plan_status()
    validate_ci_and_local_wiring()
    print("macos_native_backend_containment: ok")


if __name__ == "__main__":
    main()
