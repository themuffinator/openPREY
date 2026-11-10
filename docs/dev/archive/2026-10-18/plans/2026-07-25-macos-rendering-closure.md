# macOS Rendering Closure Plan

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Updated: 2026-07-29

## Landed Status (2026-07-29)

| gap | state | where |
| --- | --- | --- |
| G2 | landed | per-flavour `openq4_game_idlib` / `openq4_game_idlib_mp`; `tools/build/darwin_game_module.exp` plus hidden visibility on both darwin modules; the companion repo's x86-64 SIMD exclusion and its `_DEBUG` divergence from the engine both removed |
| G3 | landed | `si_gameType` defaults to `singleplayer`; `openQ4_IsMultiplayerGameType` is an allowlist mirrored from `si_gameTypeArgs`; dedicated keeps the old reading; `Com_ReloadGameModule_f` guards the swap and names the failing phase |
| G4 | landed | `material_interaction.fs` normalizes the half-angle unconditionally |
| G5 | landed | `RB_SurfaceUsesGPUPosedGeometry` replaces the `deformedSurface` proxy; the receiver self-test now models a real CPU-skinned MD5 surface |
| G6 | landed | `Apple GL 2.1 interaction routes:` per-run counters with the fallback reason breakdown |
| G7 | landed | the interaction program load cache keys on the attempt, not on the resulting object |
| G9 | landed | the corridor is selected by context shape on darwin hosts; off-darwin it needs the vendor string or `r_forceAppleGL21InteractionCorridor`; the verbatim `GL_VENDOR` is logged when the shape matches but the host test rejects it |
| G10 | landed | `SDL3: reported OpenGL framebuffer attributes:` with `depthBits`/`stencilBits`/`hasStencilBuffer` and a warning when the visual has no stencil |
| G20 | landed | unconditional `Quality profile:` line carrying `com_machineSpec`, `com_videoRam`, `com_performancePreset` |
| G21 | landed | both `shadow.vp` binds report failure instead of falling silently to fixed function |
| G22 | landed | `-Didlib_asserts=true` reaches `src/idlib/Lib.h` on Clang; the macOS sanitizer lane sets it |
| G23 | landed | `r_forceAppleGL21InteractionCorridor` plus `r_appleARB2Interactions` authority over the archived `r_useSimpleInteraction` |
| G24 | landed | `r_forceAmbient` is echoed in the `Quality profile:` line |
| G19 | partial | the S3TC/BPTC AND was already correct; the Apple 4.1 ceiling is now documented in `docs/user/texture-replacements.md`. macOS CI runs no GL client, so `BC7/BPTC=0` cannot be asserted there |
| G11, G12, G13 | open | fullscreen letterbox, Retina mode list and archived-cvar rewrites are untouched; they need Apple hardware to verify |
| G8, G14-G18, G25-G30 | open | unchanged |

A new `game module phase` breadcrumb (`src/framework/GameModuleDiagnostics.h`)
is printed by the POSIX fatal-signal handler. Issue #90 could not distinguish a
bad static initializer from `GetGameAPI` from `idGameLocal::Init`; the next
report on that machine names the step.

Original plan follows.

Updated: 2026-07-25

This plan closes the macOS rendering gaps behind issue #73 (Apple Silicon
"picture is better, but still not ok"), issue #90 (Intel `SIGABRT` on launch),
and issue #82 (BC7 not working). It supersedes the renderer half of
`docs/dev/archive/2026-10-18/plans/2026-07-11-macos-runtime-renderer-closure.md`, whose mode-0
interaction claims the field evidence disproves.

## Evidence Reviewed

- [Issue #73 comment 5077163795](https://github.com/themuffinator/openQ4/issues/73#issuecomment-5077163795)
  (2026-07-25, Apple Silicon M4 Max, macOS 26.5.2, `0.9.0-macos-arm64-metal-unsigned`):
  full console log, a support archive, and a gameplay screenshot. The screenshot
  shows flat ambient-looking lighting with no visible bump or specular detail on
  characters, no visible shadows, and black bars at the top and bottom of an
  otherwise fullscreen image.
- The same log contains `Loaded GLSL program 'glprogs/material_interaction'`
  followed by `first ARB2 interaction handoff`. The automatic Apple GL 2.1
  interaction corridor is therefore **running**, not falling back wholesale.
  Any theory that begins "the GLSL program failed to load" is disproved by the
  reporter's own log.
- [Issue #90](https://github.com/themuffinator/openQ4/issues/90) (Intel iMac
  2020, macOS 15.7.7, self-built): `malloc: *** error for object …: pointer
  being freed was not allocated` immediately after
  `Selected game module: logical='game_mp'`, before `Initializing Game`. That
  machine gets **no** `Renderer driver quirks` line at all, keeps `VBO:1`, and
  compiles the **full** ARB interaction family.
- Both reporters boot `game_mp` on a plain client launch, and both saw identical
  behaviour on the `-gl` and `-metal` packages.

## Root-Cause Summary

Three separate problems were being read as one:

1. **Lighting quality** is a shader defect plus a surface-eligibility defect,
   both inside the Apple GL 2.1 corridor. Neither needs a new graphics API.
2. **"New Game" bouncing to the menu** is not a renderer failure at all. It is a
   game-module hot-swap that tears down the whole renderer mid-click, with no
   exception guard, triggered on every single-player start because the shipped
   `default.cfg` selects a multiplayer game type.
3. **The Intel abort** is a cross-platform engine/game ABI problem that macOS's
   two-level namespace and separate dylib heaps turn into an immediate abort.

A fourth, cross-cutting problem made all three expensive to diagnose: the
corridor emits no evidence a reporter can send back.

## Decisions Taken

| Decision | Choice | Rationale |
| --- | --- | --- |
| Pursue OpenGL 4.1 core on macOS | **No** | Four sequential hard gates, ~61 authored GLSL assets to port, ~800 `GLhandleARB` call sites, ~1000 fixed-function sites, and the modern executor cannot own a lit frame on *any* platform today. It fixes none of the reported symptoms and cannot fix #82 (BPTC needs GL 4.2). The cheap ladder/caps groundwork is done anyway because it is also a live Windows/Linux correctness fix. |
| `si_gameType` default | **Flip to `singleplayer`**, land the exception guard first | Removes a full renderer teardown from every single-player session start. The guard is the safety net and ships as its own commit so the next failure is self-diagnosing regardless. |
| `-metal` release package | **Stop publishing as a release variant** | Verified gameplay no-op: `OPENQ4_MACOS_METAL_BRIDGE` reaches only the splash `SDL_CreateRenderer`, four `SDL_Renderer`/`SDL_GPU` hints, and a summary printer. The game window is `SDL_WINDOW_OPENGL` either way. The build option and one CI leg are retained. |
| Retina points/pixels rework | **Conservative half** | Fix the fullscreen viewport intersection and the misreported desktop resolution, add a high-pixel-density opt-out cvar, and defer the window-creation conversion that would change HiDPI Windows behaviour. |
| `disableVBO` retirement | **Ship the cvar defaulting to current behaviour** | The evidence that the workaround is obsolete is strong but circumstantial. Flip the default only after a reporter log with the new `frameStalls` line. |

## Gap Register

Severity: **B**locker, **M**ajor, **m**inor, **T**ech-debt.

| id | sev | gap | resolution phase |
| --- | --- | --- | --- |
| G1 | B | Six macOS guard tests red on `main`; the corridor guard aborts before its own doc checks | 0 |
| G2 | B | Intel `SIGABRT`: darwin game modules export every weak inline (no hidden visibility, no export list); one `idlib` archive built with **SP** game headers is linked into **both** modules; that archive is `c++17` while the engine's copy is `c++20` | 4 |
| G3 | B | `default.cfg` selects `dm`, so every client boots `game_mp`; `StartNewGame` then queues a module swap that re-inits the renderer with no exception guard | 4 |
| G4 | M | Stock GLSL interaction branch passes an **unnormalized** half-angle (magnitude up to 2) into `clamp(dot*4-3,0,1)^2*2`, saturating specular across most of the lit hemisphere | 2 |
| G5 | M | `RB_SurfaceUsesGeneratedCharacterGeometry` treats any `deformedSurface` as GPU-posed, which is true for every CPU-skinned MD5 surface, so all characters and the viewmodel fall to diffuse-only `SimpleInteraction.vfp`; its self-test models a case no MD5 model can produce and passes vacuously | 2 |
| G6 | M | The `material_interaction` marker the support doc asks reporters for cannot appear in a default-configured log; no per-surface route counters exist; `family=simple` describes only fallback arming and misleads | 1 |
| G7 | M | A failed GLSL interaction load is never cached, so it recompiles per surface per light per frame | 2 |
| G8 | M | `disableVBO` was superseded by the same commit that introduced it, and `r_useVertexBuffers` cannot re-enable it | 6 |
| G9 | M | The Apple quirk is gated on `GL_VENDOR == "Apple"` exactly; Apple's GL reports the GPU vendor on Intel/AMD/NVIDIA Macs, so those machines get zero workarounds and no log line | 1, 6 |
| G10 | M | A stencil-less framebuffer is silently rewritten to 8 bits; depth/stencil sizes are never logged, so "no shadows" is undiagnosable | 1 |
| G11 | M | Cocoa derives the UI viewport from a point-space window/display intersection even in fullscreen; the full-drawable path exists but is reserved for Wayland. No macOS window-geometry log | 3 |
| G12 | M | Desktop resolution is queried in points, so native resolution is reported and offered at half size | 3 (partial) |
| G13 | M | One failed context attempt permanently rewrites five archived cvars; the MSAA ladder writes the achieved count into the archived preference | 3 |
| G14 | M | macOS CI runs the client on every push and asserts no renderer fact, though the decisive lines are already printed | 5 |
| G15 | M | No `r_glTier` value can reach a core context on macOS, and the warning blames the context rather than the renderer | 5 |
| G16 | M | `-metal` is a gameplay no-op that doubles the release and evidence surface | 5 |
| G17 | M | The documented drag-install flow leaves no reachable `q4base`, and Finder launches show no error dialog | 5 |
| G18 | M | Four docs assert mode-0 outcomes the field disproves, one as a ticked release gate | 5 |
| G19 | M | BC7/BPTC is unreachable on **every** Apple tier (4.1 < 4.2), undocumented, and its capability is wrongly ANDed with S3TC | 5, 6 |
| G20 | M | Quality tier, VRAM and the achieved GL context are never logged, so config provenance is unanswerable | 1 |
| G21 | m | If `shadow.vp` fails to bind, the back end draws `w=0` volumes through fixed function, silently | 2 |
| G22 | m | Every idlib ownership assert is compiled out on all clang builds because the gate is `#ifdef _DEBUG` | 4 |
| G23 | m | `r_appleARB2Interactions 2` is defeated by archived `r_useSimpleInteraction` (OR-gate); no way to reproduce the corridor off-Apple | 2 |
| G24 | m | `r_forceAmbient 0.275` independently crushes shadow contrast and is never echoed in logs | 1 |
| G25 | m | `r_renderApi vulkan` and `gl-module` are silent no-ops on macOS; the release notes tell users to try Vulkan | 5 |
| G26 | m | Vulkan lacks portability enumeration/subset and hardcodes BPTC (matters on Windows/Linux) | 6 |
| G27 | T | The quirk system looks data-driven but the load-bearing rule is hand-coded; the self-test's flags check is a subset test and is vacuous for the `NONE` row | 6 |
| G28 | T | Capability-probe and hygiene batch (anisotropy guard, `FMT_ALPHA` swizzle, NPOT probe, uninitialised vertex/mip buffers, placeholder image) | 6 |
| G29 | T | `r_glTier auto` emits no core candidates on **any** platform, so modern auto-promotion is dead code everywhere | 5 |
| G30 | T | No CI exercises the module swap (`+devmap` bypasses it) or the resolution-scale corridor | 4, 5 |

## Explicitly Refuted

Recorded so they are not chased again. Each was proposed during the audit and
killed by reading the code.

- *Texture swizzle breaks every bump map.* Precompressed DXT5/RXGB bumps set
  `CFM_NORMAL_DXT5`, which skips the swizzle; RXGB already stores X in alpha.
- *Vulkan's hardcoded BC7 explains the new-game bounce.* `build_renderer_vk` is
  forced `false` on darwin, so no Vulkan code ran in either session.
- *A failed `material_interaction` load leaves surfaces unlit.* It falls through
  to `RB_ARB2_CreateDrawInteractions`. The path fails safe; the real cost is the
  uncached recompile (G7).
- *MSAA is a macOS path difference between the two reporters.* It is
  configuration: one had `r_multiSamples 0` archived, the other had no config.
- *Relaxing the vendor `Icmp` to a substring fixes Intel Macs.* Apple's GL
  reports `Intel Inc.` / `ATI Technologies Inc.` / `NVIDIA Corporation` there;
  neither form matches. Only a stack-shaped predicate helps.
- *Swapping the two ladder lines reaches a core context.* It breaks two in-tree
  ladder self-tests and changes forced-tier ordering on Windows and Linux. A fix
  must reorder **and** filter, cocoa-only.
- *`precompiled.h`'s `NDEBUG` is why idlib asserts are dead.* `src/idlib/Lib.h`
  `#ifdef _DEBUG` → `#else #undef assert` is the killer; both edits are needed.

## Phases

Each phase is independently shippable and leaves macOS no worse than before.

### Phase 0 — Unblock the static gate

No behaviour change. Repoint the three stale token pins at the code that moved,
add the mandatory macOS boilerplate to the v0.9.0 release notes, re-sync the
`openQ4-game` engine-interface header mirror, and run the full sweep in the
macOS-dispatched lane instead of a twelve-guard subset.

Validation: `python tools/validation/openq4_validate.py macos-static`.

### Phase 1 — Observability

No behaviour change. The goal is that the next reporter log answers the
questions this plan had to guess at.

Adds: per-view interaction route counters with the dominant fallback reason;
real `depthBits`/`stencilBits` plus a `hasStencilBuffer` warning; achieved GL
context separated from the requested one; the context ladder and winning
candidate; a driver-agnostic window-geometry and viewport dump; an unconditional
`com_machineSpec`/`com_videoRam`/`com_performancePreset` line; the verbatim
`GL_VENDOR` when the GL 2.1 compatibility shape is seen but the vendor test
rejects it; `frameStalls`; `GL_MAX_VARYING_FLOATS`. Documents the shadow intake
triad, which the macOS support doc never mentioned.

### Phase 2 — The two targeted rendering fixes

`material_interaction.fs` normalizes the half-angle unconditionally (G4). An
explicit GPU-posed predicate replaces the `deformedSurface` proxy at both the
interaction and shadow-receiver call sites, and the vacuous self-test is
rebuilt to model CPU-skinned geometry the way the engine actually produces it
(G5). Failed GLSL loads are cached (G7). `shadow.vp` binds with `required=true`
(G21). A non-archived `r_forceAppleGL21InteractionCorridor` makes the corridor
reproducible on Windows, and the policy mode becomes authoritative over the
archived `r_useSimpleInteraction` (G23).

### Phase 3 — Letterbox, Retina and configuration integrity

Fullscreen uses the full drawable instead of a point-space intersection (G11).
The desktop resolution query and the menu mode list speak pixels (G12, partial).
A high-pixel-density opt-out cvar is added. The notch safe-area key is set in
both the source and generated `Info.plist`. A failed first context attempt no
longer permanently rewrites five archived cvars, and the achieved MSAA count
goes to a non-archived mirror (G13).

### Phase 4 — Intel abort and the New Game bounce

idlib ownership asserts are re-enabled on clang (G22) so the rest is
diagnosable. Darwin game modules get hidden visibility plus an exported-symbol
list, the shared SP-headered idlib archive is split per game flavour, and
`cpp_std` is unified (G2). `GetGameAPI` is NULL-checked and module-load
breadcrumbs are added. The module swap gets an exception guard, then
`si_gameType` defaults to `singleplayer` with an allowlist so unknown values
fall back to single-player (G3). `macos-15-intel` is wired into the sanitizer
lane — the only mechanism that can reproduce #90.

### Phase 5 — CI teeth, docs honesty, scope reduction

Assert the renderer facts macOS CI already prints, including
`BC7/BPTC=0`, which converts #82 from an open investigation into an asserted
contract. Downgrade the four disproven mode-0 doc claims, including the ticked
gate in `release-completion.md`. Stop publishing `-metal`. Refuse non-static
renderer APIs on darwin with an accurate message, and refuse forced modern tiers
with a message that names the real constraint instead of blaming the context.

### Phase 6 — Performance and hygiene

Split the Apple quirk so `disableVBO` is independently gated by
`r_appleGL21VertexBuffers` (default: current behaviour). Fix the BC7-vs-S3TC AND
and the `.dds`-BC7 no-fallback placeholder. Land the G28 hygiene batch. Make
machine-spec detection pure and table-tested — the precondition for ever
touching a tier threshold.

## What Cannot Be Validated Without A Mac

| Unknown | Evidence requested instead |
| --- | --- |
| Whether the fullscreen window rect differs from display bounds on a notched panel | Phase-1 window-geometry line |
| Whether a stencil buffer actually exists | Phase-1 `stencilBits` line and `gfxInfo` PIXELFORMAT |
| How many surfaces take the GLSL corridor | Phase-1 route-counter line |
| Whether the specular fix looks right | Two screenshots at one viewpoint, before and after |
| Whether re-enabling VBOs is safe on Apple GL 2.1 | Reporter log with `r_appleGL21VertexBuffers 1` plus `frameStalls` |
| Gatekeeper, Finder, input, controller, audio-device, display-mode behaviour | Apple-hardware signoff workflow |
| Real gameplay parity on retail assets | Apple-hardware signoff; blocked until G3 is fixed |

Real Apple completion remains evidence-gated. Nothing in this plan promotes
macOS beyond experimental, and no signoff claim may be recorded from a Windows
checkout.

## Deliberately Unchanged Scope

- No native Metal renderer. The decision gate in
  `docs/dev/macos-renderer-backend-policy.md` still applies.
- No OpenGL 4.1 core visible renderer, per the decision above.
- The comparison-only native Cocoa/OpenGL backend is not promoted.
- The full `ShutdownGame`/`InitGame` split is deferred to a follow-up; the
  exception guard plus the single-player default reduce the swap to genuine
  SP/MP transitions, which is enough to unblock macOS gameplay validation.
