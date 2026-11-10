# Native Vulkan Renderer Plan

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Date: 2026-07-16
Status: stock rendering implemented; remaining compatibility and release qualification tracked below. OpenGL remains the shipping default.

Status update (2026-09-20): the stock light-grid, gamma/brightness, classic post-processing, alpha-to-coverage, soft-particle, and debug-view paths have landed alongside Phases A-G and the render-texture/capture/MSAA work. Floating-point scene rendering and automatic exposure remain open. Missing modules, failed device probes and window/surface/swapchain/mandatory-resource startup failures recover to OpenGL in the same launch; a later full vid_restart device failure still uses next-launch recovery. The remaining implementation and evidence requirements are tracked in [Vulkan gap closure](2026-09-20-vulkan-gap-closure.md). Vulkan remains experimental; the capability matrix and player-facing gap list in `docs/user/display-settings.md` describe the current scope. Historical phase descriptions below are design intent, not a current missing-feature checklist.

## Scope and architectural conclusion

openQ4 gains a fully native Vulkan renderer as a user-selectable alternative to OpenGL. Renderers become dynamic modules loaded next to the executable, selected by a new `r_renderApi` cvar, with a fail-closed fallback ladder that always lands on the proven GL path. The Vulkan backend must ultimately reach full functional parity with the OpenGL renderer across every user-visible rendering feature, and it is designed from the start around modern low-overhead Vulkan (1.3 core: dynamic rendering, synchronization2, timeline semaphores; VMA memory management; bindless descriptors; persisted pipeline cache) rather than a port of GL idioms.

The architectural cut is the **full renderer behind the module boundary**, not a backend-only or executor-only plug-in:

- The engine outside `src/renderer` binds to exactly one narrow surface: the virtual `idRenderSystem` interface, the backend-neutral `glConfig` data block (vid dimensions, UI viewport, caps booleans), and the `glIndex_t` typedef. There are zero GL calls in `src/framework` or `src/ui`; real GL usage outside the renderer is confined to the platform layer in `src/sys` and the self-contained `src/tools` editors.
- A backend-only cut fails on data coupling: `idVertexCache::Position()` returns API offsets, `idImage` carries a GL texture name consumed across renderer files, and `backEnd.glState` is GL-typed. Abstracting each of those in place is a larger refactor than moving the whole renderer.
- An executor-level plug-in fails on coverage: the modern ScenePackets → RenderGraph track is opt-in and pass-granular today, interleaved with the legacy ARB2 path per view. A GL-free Vulkan module cannot inherit legacy-GL fallbacks per pass.
- The loading infrastructure is proven: the `GetGameAPI` handshake, `Sys_DLL_Load`/`Sys_DLL_GetProcAddress`, per-OS export control (`.def`, version scripts, `@loader_path`), and arch-tagged module naming all exist for game modules. `renderSystem` is already a swappable pointer global.

Target module layout:

```
openQ4-client / openQ4-ded            (engine, graphics-API-free at the end state)
  └─ loads renderer-gl_<arch> OR renderer-vk_<arch>   (r_renderApi-selected)
       each links openq4_renderer_core (static: frontend, ScenePackets,
         RenderGraph, planners, BinaryImage, ring-buffer bookkeeping)
       + its API backend (GL: GLEW/context ladder/ARB2+modern executor;
         VK: volk/VMA/swapchain/pipeline library/graph executor)
```

The legacy ARB2 path moves wholesale into `renderer-gl` and is never ported to Vulkan. The Vulkan module implements only the packet/graph track, end to end, for every pass. `src/tools` editors keep their own fixed-function GL and are out of scope. Window creation, input, and display/mode policy stay engine-side (SDL3 or platform backend); renderer modules request window flags (`SDL_WINDOW_OPENGL` vs `SDL_WINDOW_VULKAN`) and receive native handles through the import surface.

## Module ABI

Single versioned `extern "C"` export, mirroring the game-module convention (same-compiler C++ interfaces carried in the structs):

```c
#define RENDER_API_VERSION 1

typedef struct renderImport_s {
    int                        version;        // RENDER_API_VERSION
    idSys *                    sys;
    idCommon *                 common;
    idCVarSystem *             cvarSystem;
    idCmdSystem *              cmdSystem;
    idFileSystem *             fileSystem;
    idDeclManager *            declManager;
    idSoundSystem *            soundSystem;
    const rendererWindowServices_t * window;   // native handles, mode apply, display enumeration
} renderImport_t;

typedef struct renderExport_s {
    int                        version;        // RENDER_API_VERSION
    const char *               backendName;    // "gl" / "vulkan" -> r_actualRenderApi
    idRenderSystem *           renderSystem;   // full interface; may be NULL during bring-up
    const renderModuleDiagnostics_t * diagnostics; // probe/self-test surface, valid before renderSystem
} renderExport_t;

extern "C" renderExport_t *GetRenderAPI( renderImport_t *import );
```

Rules copied from the game-module precedent: no `__declspec` macros (Windows uses `vs_module_defs`, Linux a version script plus hidden visibility, macOS `shared_library` with `@loader_path` install name); modules register their own `r_*` cvars and self-test commands through the imported systems so `CVAR_RENDERER` restart flush machinery keeps working; memory routes through the shared idlib conventions the game modules already follow.

`glConfig` remains the engine-owned handoff block (it is load-bearing across framework/ui/sys); the module populates dimensions, caps, and init state. GL-only members remain meaningful only inside `renderer-gl`; the Vulkan module leaves them defaulted and adds its own caps record surfaced through `gfxInfo`.

Renderer modules are located **next to the executable** via `Sys_EXEPath()` — never through `fileSystem->FindDLL`, which is game-module/pure-mode territory. Dedicated server loads no renderer module (stub renderer stays built in).

## Bootstrap and selection

- **`r_renderApi`** — `{ "best", "gl", "vulkan" }`, default **`gl`**, `CVAR_RENDERER | CVAR_ARCHIVE` (takes effect on `vid_restart`; `CVAR_INIT` is unsuitable because it rejects the archived config value), arg-completed. `best` resolves to `gl` until Vulkan promotion evidence lands (see gating below), after which it may resolve per-platform.
- **`r_actualRenderApi`** — `CVAR_ROM`, set from the loaded module's `backendName` (or `gl-builtin` while the GL renderer remains statically linked during Phase A/B).
- Existing cvars keep their meaning *inside* `renderer-gl`: `r_renderer` (ARB2 hardware paths) and `r_glTier` (GL tier ladder) are GL-module concepts; the Vulkan module ignores them and gets its own device-selection cvars (`r_vkDevice`, `r_vkValidation`, `r_vkPresentMode` follow-ons).
- **Fail-closed ladder:** requested module missing → load failure → `GetRenderAPI` version mismatch → module init (instance/device/swapchain) failure — each step warns, unloads, and falls back to GL; the GL path retains its existing safe-mode retry loop. A failed Vulkan selection must never leave the user without a picture.
- `gfxInfo` prints requested API, actual API, module path, and load/fallback disposition. The default-safety audit is generalized so `r_renderApi gl` reads as conservative default and `vulkan` as explicit opt-in.

## Vulkan technical design

Baseline: Vulkan 1.3 (dynamic rendering, sync2, timeline semaphores core), volk loader (runtime dlopen of the ICD loader — no import-table dependency on `vulkan-1`, so the module loads cleanly on machines without Vulkan and the ladder falls back), VMA for all allocations, **2 frames in flight** to match the engine's `NUM_VERTEX_FRAMES=2` pipelining assumption (widening evaluated only in the optimization phase, with evidence).

| Engine concept | Vulkan design |
|---|---|
| `idImage` | `VkImage + VkImageView + VmaAllocation` behind an opaque device handle; single `textureFormat_t → VkFormat` table (BC1/BC3/BC7, RGBA16F, D24S8/D32S8 by caps); legacy ALPHA/LUM/L8A8 swizzles as `VkComponentMapping`; sampler-object cache keyed by filter/repeat/aniso/compare; generation counters map to device/swapchain generations. |
| Image upload | Persistent host-visible staging ring + `vkCmdCopyBufferToImage`, dedicated transfer queue where available, timeline-signaled; `idBinaryImage` CPU blobs reused byte-for-byte. |
| `idVertexCache` | Static tier: DEVICE_LOCAL buffers via staging. Frame tier: per-frame-in-flight HOST_VISIBLE ring reusing the existing ring-buffer bookkeeping; GL fences replaced by the frame timeline semaphore; frame-fenced deferred deletion queues. |
| Render targets / FBOs | **Dynamic rendering** — no VkRenderPass/VkFramebuffer objects; attachment infos built from the same `idRenderTexture` attachments; MSAA resolve via resolve attachments; clears via loadOp. Public `idRenderSystem::CreateRenderTexture/...` unchanged. |
| RenderGraph resources | New VK resource owner consuming the same graph lifetimes/alias groups for VMA transient placement (aliased allocations); graph READ/WRITE/RESOLVE/PRESENT edges drive `vkCmdPipelineBarrier2` generation automatically. |
| ScenePackets / draw + submit plans | Reused verbatim (already API-free) after neutralizing the plan structs' opaque handle fields (program index → pipeline index; buffer names → buffer+offset pairs; texture handles/uniform locations → descriptor indices/push-constant offsets). |
| Shaders | Offline GLSL → SPIR-V (glslang at build time, shipped `.spv`), keyed by the same shader-kind × permutation key the modern GL shader library uses; ARB2 semantics arrive via the shared reference-GLSL translation, validated against RenderDoc captures. |
| Pipelines | `VkPipeline` keyed by `{shader kind+permutation, vertex layout, attachment formats+samples, GLS_* state bits}`; viewport/scissor/depth-bias/depth-bounds/stencil-ref as dynamic state so per-surface scissors and depth hacks don't multiply pipelines; `VkPipelineCache` persisted across runs with level-load warm-up. |
| Descriptors | Bindless-biased hybrid: set 0 = global variable-count sampled-image + sampler arrays (update-after-bind, partially bound), stable per-image indices assigned at allocation; set 1 = per-frame view UBO + light/cluster/shadow SSBOs (std140 layouts already exist); per-draw data via push constants + frame instance SSBO offsets. No per-material sets, no per-draw allocation. |
| State system | GL_State bits and the GL state cache disappear as runtime concepts; GLS bits fold into pipeline keys; submit order already minimizes binds. Exactly one state model. |
| Present | Module-owned swapchain; `r_swapInterval` → present mode (MAILBOX/IMMEDIATE/FIFO honoring the loading-screen bypass); acquire/present binary semaphores at the swapchain edge only; per-slot timeline semaphore for CPU throttle; OUT_OF_DATE/resize recreate reuses the generation-invalidation pattern. |
| Scene feedback captures | `_currentRender`/`_currentDepth`, SSAO depth, subview RTT, envshot, tiled screenshots as explicit copy/blit operations at the same pass-order points (ordering is load-bearing for authored content); readbacks via HOST_VISIBLE buffers with frame-deferred maps. |
| Timers / debug | `vkCmdWriteTimestamp2` pools per frame slot behind the existing metrics interface; `VK_EXT_debug_utils` labels/scopes behind the same RAII debug-scope API; validation layers behind `r_vkValidation` with matrix-recognized error signatures. |
| GPU-driven path | `vkCmdDrawIndexedIndirectCount` + compute culling + Hi-Z mirroring the GL executor's advanced tiers, in the optimization phase. |

## Phased roadmap

Every phase ends with the standing gate: Windows Meson wrapper build clean; `python tools/tests/renderer_validation_matrix.py` safe set N/N; macOS policy sweep (`tools/tests/macos_*.py`) green; new behavior covered by a registered `renderer*SelfTest` command; SP gameplay (not menu-only) exercised when the phase touches the visible path. GL default behavior must be unchanged in every phase until the final, separately-gated default decision.

### Phase A — module ABI, selection cvar, loader, Vulkan probe (foundation)

1. `RenderModuleAPI.h`: versioned `GetRenderAPI` contract (import/export structs, window services, diagnostics surface).
2. Engine-side module loader: `r_renderApi`/`r_actualRenderApi` cvars, exe-relative module resolution, load/handshake/version-check, fail-closed fallback ladder, `gfxInfo` reporting, `rendererModuleSelfTest` (name resolution, ladder order, version rejection — no device required).
3. Meson: `build_renderer_vk` option; vendored Vulkan C headers + Volk + VMA under `src/external` (glew precedent); `renderer-vk_<arch>` shared module with `.def`/version-script export; staged next to the executables in `builddir/` and `.install/`.
4. `renderer-vk` bring-up module: volk init, instance (+`r_vkValidation` debug utils), physical-device enumeration/selection, device/queues, VMA init, caps report through the diagnostics surface; `rendererVkProbe` console command loads the module on demand, prints the report, unloads. `GetRenderAPI` returns `renderSystem = NULL` at this stage, so selecting `vulkan` exercises the production fallback ladder end to end.

Acceptance: default (`r_renderApi gl`) bit-identical behavior; `rendererVkProbe` reports instance/device/queue/caps on Vulkan-capable machines and fails gracefully (no crash, clear message) without a Vulkan loader; `r_renderApi vulkan` falls back to GL with the documented warning chain; self-tests pass on the safe matrix; module builds on Windows/Linux.

### Phase B — GL renderer behind the module seam (no Vulkan rendering yet)

Staged in detail (with the audit-derived blocker index and file dispositions) in [2026-07-16-vulkan-renderer-phase-b.md](2026-07-16-vulkan-renderer-phase-b.md); stages B1–B3(partial) have landed.

1. Extract `openq4_renderer_core` static library (frontend, packets/graph/planners, BinaryImage, ring bookkeeping) from engine source lists.
2. Build `renderer-gl_<arch>` from the GL backend + core; move GLEW, GL link deps, and the context-ladder/window half behind the window-services import; engine executables become GL-link-free.
3. Keep the statically-linked GL renderer available behind a build option during the transition; flip the default load path to the module only when pixel-identical.

Acceptance: pixel-identical A/B screenshots (benchmark preset scenes) module vs static; full validation matrix + SP/MP gameplay clean from the DLL; `gfxInfo` prints module path and `r_actualRenderApi gl`; dedicated server unaffected. This phase is shippable alone and de-risks everything after it.

### Phase C — Vulkan clear + present

Swapchain, frame loop, per-slot timeline sync, debug utils, validation cvar; `r_renderApi vulkan` boots the real game loop to an animated clear at correct resolution/vsync/fullscreen across `r_screen`/mode changes; deliberate module-break drill proves the fallback ladder. Self-tests: `rendererVkDeviceSelfTest`, `rendererVkSwapchainSelfTest` in the safe matrix; Vulkan validation-layer error signatures added to the matrix runner so warnings=0 is meaningful from the first visible frame.

### Phase D — images, vertex cache, 2D/GUI parity

idImage VK path (formats, swizzles, staging, bindless table), VK vertex-cache tiers, GUI pipeline consuming the existing GUI packet stream, fonts, ROQ cinematic streaming upload. Milestone: full main menu, console, and video playback on Vulkan; assetless-startup probes pass.

### Phase E — world geometry: depth prepass + ambient/flat materials

VK render-graph resource owner, pipeline library bring-up (depth/flat/GUI kinds), submit loop with dynamic-state scissor/depth-hack, skybox. Milestone: map loads, fully-bright walkthrough with correct geometry/materials/portals culling.

### Phase F — interaction lighting + shadow maps

SPIR-V interaction shaders validated against ARB2 captures on fixed scenes; clustered light binning (CPU records + std140 uploads reused); shadow-map path via the shared shadow planner (atlas, point cube, CSM, PCF). Milestone: lit SP gameplay with `r_useShadowMap 1` matching GL A/B captures.

### Phase G — stencil shadows + fog/blend lights + light-grid indirect

Two-sided stencil pipelines, depth-bounds dynamic state (feature-gated exactly as GL), turboshadow paths, texgen fog/blend lights, light-grid indirect diffuse, force-ambient. Milestone: `r_useShadowMap 0` parity; per-light shadow-technique dispatch matches GL.

Stock shadow-path closure landed on 2026-07-24. Vulkan now preserves
LOCAL/GLOBAL ownership independently across stencil, projected, point, and
one-to-four-cascade maps; covers static, animated, packed MD5R, two-sided,
and perforated/hashed-alpha casters; supports hardware or manual depth
comparison plus fixed, rotated, and PCSS-lite filtering; and reuses exact
static maps without consuming the per-view update budget. If a mapped
ownership cannot be submitted, its complete retained stencil set is used in
the same frame (including a proven empty set after view culling); map-only
ownerships fail closed rather than receiving falsely unshadowed light.
Mapped Vulkan lights retain successfully generated and linked per-surface
stencil volumes and build dedicated LOCAL/GLOBAL supplement chains containing
only casters absent from a partial map. Combined optimized-prelight volumes
are never stamped as partial-map supplements. Update-budget and subview
fallback policies apply only when a complete stencil result exists;
ownerships containing map-only casters schedule their required map beyond the
nominal update budget and fail closed only on a genuine map submission
failure. Correctness-required ownerships are admitted before maps that can
fall back to stencil, and a subview target without a usable stencil path
renders required maps regardless of the normal cache-only subview policy.

### Phase H — post-process chain + feedback captures + MSAA

`_currentRender`/`_currentDepth` capture points in graph order; SSAO → motion blur → bloom → HDR tonemap/auto-exposure → authored post materials → SMAA → CRT → resolution scale → gamma; soft particles; MSAA with alpha-to-coverage and depth resolve. Milestone: full visual-stack parity screenshots across the benchmark scenes.

### Phase I — long tail to full parity

Subviews (mirrors, remote screens, xray), screenshots/envshot/tiled readback, crop/capture-to-image, debug rendertools (`r_show*` suite as buffered-line implementations), optional native packed-MD5R GPU submission, demo/timedemo capture. Milestone: gameplay benchmark profiles pass on Vulkan; every renderer cvar triaged implemented / documented-no-op-with-warning.

MD5/MD5R functional closure landed on 2026-07-24. The Vulkan module deliberately consumes MD5R through the renderer's complete classic surface contract, giving authored MD5 plus converted, ASCII-prebuilt, and compiled-prebuilt MD5R the same coverage across Vulkan passes. A future direct packed-buffer submission path is an optimization opportunity rather than a remaining compatibility requirement.

### Phase J — optimization + promotion evidence

GPU-driven indirect + compute culling + Hi-Z parity with the top GL tiers; multi-threaded command recording over the partitionable sorted submit stream; transfer-queue overlap; pipeline warm-up coverage; descriptor/barrier audits with validation perf warnings clean. Measurement per house policy: ≥5-run p50/p95/p99 A/B vs GL per scene/preset, CPU frame time and GPU pass times, VRAM budgets. Vulkan default consideration requires its own promotion-evidence token and explicit sign-off cvar modeled on the modern-GL promotion machinery; `r_renderApi best` resolution changes only then.

## Risks and mitigations

1. **ARB2 material stage programs.** Authored ARB assembly in mods cannot execute on Vulkan. Stock content routes through the shared reference-GLSL translations validated per-program against ARB2 captures; arbitrary custom ARBfp is a documented limitation with per-material fallback flagging.
2. **Packet coverage gaps.** Legacy passes not yet represented in packets (some subview/effect/debug/crop paths) get packet coverage engine-core-side (benefiting GL too), each with a packet self-test — never VK-only side channels.
3. **Feedback-capture ordering.** Encoded as explicit graph passes with access edges so barriers derive from data; validation case renders a known post-process material.
4. **macOS policy.** Per `docs/dev/macos-renderer-backend-policy.md`, a non-GL macOS renderer requires its own decision-gate plan, and MoltenVK is a translation layer that must not be marketed native. This plan originally scoped Vulkan to Windows/Linux and held `build_renderer_vk` off for macOS packages until a separate macOS plan cleared the gate. **Resolved 2026-07-25:** [../macos-moltenvk-decision.md](../macos-moltenvk-decision.md) is that plan, staged in [2026-07-25-macos-moltenvk.md](2026-07-25-macos-moltenvk.md). The darwin carve-out on `build_renderer_vk` is removed and `renderer-vk_<arch>.dylib` now ships in both existing macOS packages together with a pinned, bundled `libMoltenVK.dylib`, running through MoltenVK as a Vulkan-on-Metal translation layer. The decision is defaults-neutral: OpenGL stays the macOS default renderer in both package variants, `r_renderApi best` still resolves to `gl` on macOS, Vulkan is opt-in through `r_renderApi vulkan`, and no third package variant is created. The translation layer must still never be described as native Metal, a Metal renderer, a native Vulkan driver, or an OpenGL-free renderer. The macOS token sweep runs after every build-system change here, and `tools/tests/macos_moltenvk_policy.py` additionally pins the portability negotiation, the SDL/volk loader agreement, the module export contract, and the MSL-hostile shader constructs that no Windows or Linux build can observe.
5. **Seam blast radius (Phase B).** GL-in-a-DLL must be provably pixel-identical before any Vulkan rendering work builds on the seam; engine-side includes of renderer-internal headers are grep-audited as a phase exit criterion.
6. **Driver variance.** Validation layers in dev loops, conservative feature gating mirroring GL caps booleans, and the fail-closed ladder keep users renderable on every failure class.

## Build plan (Meson)

- Vendored under `src/external`: `vulkan/` C headers (+`vk_video/`), `volk/`, `vma/` — pinned versions recorded in headers; no C++ binding headers.
- `renderer-vk_<arch>` follows the game-module target pattern (`shared_module`, `name_prefix: ''`, `.def` on Windows, version script + hidden visibility on Linux); installs to `.install/` beside executables with a matching direct-run stage into `builddir/`.
- No link against `vulkan-1`/`libvulkan` — volk resolves the loader at runtime.
- `build_renderer_vk` option (default true; the only remaining gate is the SDL3 platform backend). macOS was originally excluded pending policy and was admitted on 2026-07-25 by [../macos-moltenvk-decision.md](../macos-moltenvk-decision.md); on darwin the target is a `shared_library` producing `renderer-vk_<arch>.dylib` with `@loader_path` install name, hidden visibility, dead stripping, and an exported-symbols list limited to `GetRenderAPI`.
- Phase B adds `openq4_renderer_core` and `renderer-gl_<arch>` targets and moves GL deps off the engine executables.
- SPIR-V: glslang as a build-time tool (`find_program('glslangValidator')` with SDK/env fallback) compiling shared shader sources via `custom_target`; shipped `.spv` staged with the module (Phase D onward).

## Validation matrix for this plan

| Gate | Command/workload | Required evidence |
|---|---|---|
| Default unchanged | SP launch task, `r_renderApi gl` | Clean `openq4.log`; no new warnings; gameplay unchanged |
| Module fallback | `r_renderApi vulkan` with module absent/broken | Warning chain in log; GL renders; `r_actualRenderApi` reports fallback |
| Vulkan probe | `rendererVkProbe` on VK-capable and VK-less hosts | Device/caps report; graceful no-loader message |
| Self-tests | `rendererModuleSelfTest`, later `rendererVk*SelfTest` | Exit clean in safe matrix |
| Build health | `tools/build/meson_setup.ps1 compile` (Windows), CI Linux | Zero new warnings in renderer module targets |
| Policy sweep | `python tools/tests/macos_*.py` suite | All green after build-system changes |
| Parity (per phase C+) | A/B screenshot + RenderDoc capture diffs on benchmark scenes | Phase-specific parity artifacts |
| Performance (Phase J) | `renderer_gameplay_benchmark.py` ≥5 runs | p50/p95/p99 gl-or-better per scene before any promotion claim |
