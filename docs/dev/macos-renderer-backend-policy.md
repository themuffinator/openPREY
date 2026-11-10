# macOS Renderer And Backend Policy

Current work and future design/removal decisions belong in the
[development roadmap](roadmap.md#desktop-platforms-and-packaging). References
below to a separate design or removal plan mean a scoped roadmap decision with
supporting technical documentation, not another active delivery plan.

Updated: 2026-07-11

This document defines the current macOS renderer and platform-backend support
policy. It exists so the OpenGL package, Metal bridge package, and legacy native
Cocoa/OpenGL backend do not imply support promises beyond what openQ4 actually
builds, validates, and releases.

The legacy backend source-containment and removal-decision policy is tracked in
`docs/dev/macos-native-backend-containment-policy.md`.

## Current Release Path

The current macOS release path is:

- `platform_backend=sdl3`.
- `macos_graphics_bridge=opengl` for the OpenGL package.
- `macos_graphics_bridge=metal` for the Metal bridge package.
- The stock-compatible openQ4 OpenGL renderer in both package variants.

The Metal bridge package is not a native Metal renderer. It keeps the renderer
on the OpenGL compatibility path while using the SDL3/Cocoa host integration and
Metal/QuartzCore bridge plumbing needed for translation-layer bring-up and
diagnostics.

Release-facing package names and docs must use `OpenGL` and `Metal bridge`.
They must not describe the current `-metal` package as native Metal, a Metal
renderer, or an OpenGL-free renderer.

## Validation Contract

Every accepted macOS renderer signoff must keep the two bridge variants
separate:

- OpenGL package signoff for `macos_graphics_bridge=opengl`.
- Metal bridge package signoff for `macos_graphics_bridge=metal`.
- `renderer-smoke`, `renderer-mp-smoke`, and `renderer-matrix` evidence for
  both variants.
- SP and MP in-game checks on real Apple hardware or a compliant Apple-hardware
  VM before any first-class support claim.

Hosted CI now performs an assetless renderer launch for both bridge variants,
and release packaging launches the app executable from an unrelated working
directory to exercise app-bundle path resolution. These are required smoke
checks, but they are not a replacement for SP/MP gameplay evidence on the
documented macOS floor and latest public macOS release.

## Apple OpenGL Risk

Apple OpenGL remains the limiting macOS rendering dependency. The current policy
accepts this for the preview release line because stock Quake 4 asset
compatibility and renderer parity are higher priorities than changing graphics
APIs prematurely.

Known policy consequences:

- macOS remains capped by Apple OpenGL behavior, including the OpenGL 4.1 core
  ceiling and fragile compatibility-context behavior.
- Apple compatibility launches currently select a 2.1 compatibility context
  because the visible renderer still needs fixed-function/ARB-era state. The
  automatic interaction policy avoids the previously crashing ARB program on
  ordinary stock surfaces by using the existing GLSL 1.10
  `material_interaction` program with neutral values; generated or otherwise
  ineligible surfaces use a CPU-pointer-safe `SimpleInteraction.vfp` fallback.
- `r_appleARB2Interactions 3` retains the old ambient-only interaction bypass
  strictly as an emergency recovery mode. It is not acceptable visual-parity
  evidence. Modes `1` and `2` force the simple/full ARB paths for diagnosis.
- Window/default-framebuffer MSAA support is not treated as proof that Apple
  accepts the same sample count for offscreen RGBA8 + packed depth/stencil
  targets. Game targets retry lower samples and fail into direct rendering
  instead of terminating on an incomplete FBO.
- Renderer compatibility work should continue to harden the OpenGL path, not
  hide OpenGL dependency behind Metal wording.
- Release notes must call out any renderer limitation found during signoff.

## Native Metal Decision Gate

No native Metal renderer is selected for the current release line.

If native Metal becomes a target, create a separate renderer design plan before
implementation. That plan must cover:

- Stock Quake 4 material, shader, interaction, and lighting parity.
- BSE effect rendering and lifetime behavior.
- Shader translation or replacement strategy.
- Screenshot, readback, video, and diagnostic capture behavior.
- RenderDoc or Xcode GPU capture workflow.
- Performance counters, renderer metrics, and failure diagnostics.
- Fallback and rollback behavior when native Metal cannot initialize.
- Package naming, release notes, and signoff evidence for native Metal as a new
  renderer path.

Until that plan exists and has matching tests, docs must continue to call the
current package `Metal bridge`.

## MoltenVK-Backed Vulkan Renderer

Added: 2026-07-25.

The gate above has been cleared for exactly one non-GL macOS renderer path: the
existing openQ4 Vulkan renderer module running through MoltenVK, a
Vulkan-on-Metal translation layer. The design plan is
[macos-moltenvk-decision.md](archive/2026-10-18/macos-moltenvk-decision.md) and the staged record
is [plans/2026-07-25-macos-moltenvk.md](archive/2026-10-18/plans/2026-07-25-macos-moltenvk.md).

Clearing that gate did not change the default renderer, the package set, or the
macOS support claim:

- The user-requested 28 October 2026 hardware policy makes fresh desktop
  `best` configurations try Vulkan with OpenGL fallback. Existing explicit
  OpenGL selections remain OpenGL in both package variants.
- The retained System menu saves backend and stable device preferences and
  offers a main-menu engine restart. Vulkan remains experimental on macOS;
  this selection policy does not close its physical hardware gates.
- No third package variant and no new `macos_graphics_bridge` value are
  introduced. The `renderer-vk_<arch>.dylib` module and the bundled
  `libMoltenVK.dylib` ship inside the existing `OpenGL` and `Metal bridge`
  packages, in `openQ4.app/Contents/Frameworks`.
- macOS support is a preview for Apple Silicon/arm64. macOS Vulkan is an
  experimental renderer on that preview platform, and no first-class or
  supported-renderer claim follows from this decision.
- A missing renderer module, a missing MoltenVK, or a GPU that cannot start
  Vulkan falls back to the OpenGL renderer through the existing fail-closed
  ladder, which probes the Vulkan device before it activates the module. A
  window or surface failure after activation stops openQ4 with an error, after
  setting `r_renderApi` back to `gl` so the next launch uses OpenGL (issue #96
  recorded the old behavior, where every device failure stopped every launch).

The gate remains closed for a native Metal renderer, for making Vulkan the macOS
default or resolving `best` to `vulkan` on macOS, and for any additional macOS
package variant. Each needs its own plan, its own tests, and real
Apple-hardware evidence.

MoltenVK is a translation layer. It must never be described as native Metal, a
Metal renderer, a native Vulkan driver, or an OpenGL-free renderer. The
provider, pinning, and signing policy is recorded in
[macos-moltenvk-provider-policy.md](macos-moltenvk-provider-policy.md), and
`tools/tests/macos_moltenvk_policy.py` enforces the runtime and wording
contracts that no Windows or Linux build can observe.

## Native Cocoa/OpenGL Backend Policy

The legacy macOS native backend selected by `-Dplatform_backend=native` is
comparison-only diagnostic infrastructure.

It is retained to:

- Compare SDL3 regressions against the older Cocoa/OpenGL path.
- Preserve isolated fallback code while SDL3 macOS support matures.
- Keep crash-resistant guards around legacy Cocoa, NSOpenGL, and Carbon
  boundaries.

It is not a supported macOS release backend. Release packages, release
workflows, first-class support claims, and user-facing install docs must use the
SDL3 backend unless the project makes a new explicit support decision.

Native backend maintenance rules:

- Carbon and NSOpenGL remain isolated to the native fallback boundary.
- `macos_graphics_bridge=metal` must require `platform_backend=sdl3`.
- CI policy tests must continue to block Carbon/NSOpenGL leakage into the SDL3
  release path.
- Native backend results are diagnostic unless a future plan adds dedicated
  build, package, and runtime signoff coverage.
- The native backend is not kept indefinitely by default. Once SDL3 OpenGL and
  Metal bridge coverage is mature across the documented macOS floor and latest
  public macOS, create a separate native-backend removal plan before deleting or
  expanding the legacy path.

## Release-Gate Summary

Before macOS support can move beyond the current preview wording to first-class:

- OpenGL and Metal bridge package evidence must be current for the supported OS
  matrix.
- Release notes must state that the Metal package is a bridge, not native Metal.
- Release notes must not imply that `platform_backend=native` is supported for
  release packages.
- Any future native Metal or native backend support claim must have a separate
  design plan, CI/build lane, package validation, and real Apple-hardware
  runtime evidence.
