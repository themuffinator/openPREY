# macOS Native Backend Containment Policy

Current work and future design/removal decisions belong in the
[development roadmap](roadmap.md#desktop-platforms-and-packaging). References
below to a separate design or removal plan mean a scoped roadmap decision with
supporting technical documentation, not another active delivery plan.

Updated: 2026-06-30

This policy keeps the legacy macOS Cocoa/OpenGL backend useful for comparison
without allowing it to become an implied support surface.

## Current Decision

The release backend is `platform_backend=sdl3`. The legacy
`platform_backend=native` Cocoa/OpenGL backend is retained only as
comparison-only diagnostic infrastructure while SDL3 macOS coverage matures.

The native backend is not kept indefinitely by default. After SDL3 coverage is
mature enough for the current macOS floor and latest public macOS, create a
separate native-backend removal plan before deleting or changing the legacy path.
That plan must cover Meson option changes, documentation updates, rollback
strategy, release-note wording, and any temporary comparison evidence still
needed for open macOS renderer issues.

## Source Boundary

The native backend owns the remaining legacy macOS platform APIs:

- `src/sys/macos/macos_event.mm` is the native Carbon event/input boundary.
- `src/sys/macos/macos_glimp.mm` is the native NSOpenGL/CGL context boundary.

SDL3 macOS sources must not import Carbon, link Carbon, or use NSOpenGL/CGL
context APIs. `tools/build/meson_sources.py` must keep `macos_event.mm` and
`macos_glimp.mm` out of `SDL3_DARWIN_SOURCES`.

`meson.build` may link Carbon only when `platform_backend=native` is selected.
The SDL3 macOS backend links Cocoa/OpenGL/ApplicationServices, and the Metal
bridge variant adds Metal/QuartzCore only for `macos_graphics_bridge=metal`.

## Release Wording

Curated release notes may say that the native backend is comparison-only
diagnostic infrastructure and not a release backend. They must not describe the
legacy Cocoa/OpenGL backend as native macOS backend support, native Cocoa/OpenGL
support, a supported native backend, or release support evidence.

## Native Metal Boundary

No native Metal renderer is selected for the current release line. Native Metal
implementation work stays out of scope until a separate design plan covers:

- Stock Quake 4 material, shader, interaction, and lighting parity.
- BSE effect rendering and lifetime behavior.
- Shader translation or replacement strategy.
- Screenshot, readback, video, and diagnostic capture behavior.
- RenderDoc or Xcode GPU capture workflow.
- Performance counters, renderer metrics, and failure diagnostics.
- Fallback and rollback behavior.
- Package names, release notes, and signoff evidence for a new renderer path.

Until that plan exists, release packages remain `OpenGL` and `Metal bridge`,
and the `Metal bridge` label must not imply a native Metal renderer or
OpenGL-free renderer.

## MoltenVK Boundary

Added: 2026-07-25.

openQ4's Vulkan renderer module now builds and ships for macOS, where it runs
through MoltenVK, a Vulkan-on-Metal translation layer. The decision plan is
[macos-moltenvk-decision.md](archive/2026-10-18/macos-moltenvk-decision.md).

That does not move the native Metal boundary above. Nothing in
`src/renderer`, `src/sys/macos`, `src/sys/posix`, or `src/sys/sdl3` imports Metal,
MetalKit, QuartzCore `CAMetalLayer`, or any `MTL*` type for the Vulkan path;
presentation-surface creation goes through `SDL_Vulkan_CreateSurface` only, and
the Metal work is entirely internal to the third-party translation layer.

The wording rules are the same ones the boundary already enforces. The
translation layer must not be described as native Metal, a Metal renderer, a
Metal backend, a native Vulkan driver, or an OpenGL-free renderer, and the
macOS packages remain the two
existing `OpenGL` and `Metal bridge` variants with OpenGL as the default
renderer in both. `tools/tests/macos_moltenvk_policy.py` rejects
native-backend wording for MoltenVK in the release-facing documents.

## Static Guard

`tools/tests/macos_native_backend_containment.py` enforces this policy by
checking the source manifests, Meson framework gating, release-note wording, and
absence of native Metal implementation tokens in active renderer/macOS sources.
It is a static guard only and does not claim macOS runtime or Finder coverage.
