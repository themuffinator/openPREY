# Vulkan gap closure

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Status: in progress. Objective: resolve all remaining Vulkan implementation,
compatibility, recovery, and qualification gaps. This does not change the
default renderer or declare Vulkan release-supported before the evidence exists.

2026-10-04: the implementation gaps are closed (see the work record), and the
user signed off Vulkan as a **stable, supported opt-in renderer on Windows
x64** on the NVIDIA and Intel real-hardware evidence below. It stays
experimental on Linux and macOS, OpenGL stays the default, and `best` still
resolves to `gl`.

The current source and `engine-capability-matrix.md` take precedence over the
older Phase A-J progress notes. Gamma/brightness, classic post processing,
light grids, soft particles, alpha-to-coverage, player outlines, cel shading,
underwater effects, and debug views have already landed.

## Completion requirements

| Area | Remaining work | Evidence required for closure |
|---|---|---|
| Continuous runtime validation | Implemented: Linux x64/ARM64 push and ARM64 PR jobs run the lavapipe startup, probe, HDR, temporal, fallback and four recovery cases with active validation layers, and pass (run 37124801663). | Keep the hosted cases green. Software Vulkan is regression evidence, not physical GPU qualification. |
| Startup and runtime recovery | Startup: implemented and locally verified for window, surface, swapchain and mandatory renderer resources; full owner teardown precedes module unload and OpenGL starts in the same process. Runtime (2026-10-03): a latched device queues an automatic renderer restart (budget `r_vkPresentationRecoveries`), surface loss rebuilds the surface in place, and the drill `r_vkPresentationFailureTest` exercises both. | All four deterministic failure cases pass repeatedly with clean shutdown, intact ordered logs, and unchanged Vulkan startup. Resource-failure SP/MP stock gameplay also passes. Hosted/platform coverage remains part of the separate qualification requirement. |
| Custom material programs | Implemented for authored GLSL (v50-v53) and authored ARB assembly (2026-10-03, translated to GLSL), with explicit diagnostics for unsupported state. Remaining: broader GLSL language/state coverage and real mod content. | Compiled shader fixtures and rendered comparisons against OpenGL for real custom programs, including parameter bindings, textures, vertex outputs, and custom lighting. |
| HDR scene and exposure | Bounded linear scene composition, bloom/exposure, scaled GL comparisons, HDR-off preview fog/blend parity and native linear screenshots are implemented. Extend admission to declined material, baked-lighting, portal/capture and post-effect combinations; complete remaining presentation comparisons. | Complete-scope render-target/radiance verification, OpenGL comparisons, validation-clean gameplay and captures, and reset/resize/admission-failure tests. |
| PBR, probes, and clustered decals | Reach the supported OpenGL material and environment/probe scope on Vulkan. Clustered decals need no port: they are an OpenGL modern-path routing transaction whose decal mode draws the classic decal result, which Vulkan already draws natively. | Authored fixture execution, equivalent visible results, resource lifecycle/admission tests, and fallback evidence for exhausted or invalid resources. |
| Temporal motion | The exact eligible rigid-object velocity path is implemented. Complete visible temporal-AA qualification and retain explicit reactive handling for unsupported geometry. | Moving-object and camera-cut fixtures, history invalidation, visible TAA comparisons, and validation-clean runtime evidence. |
| Shadows | Translucent moments implemented 2026-10-03 (moment atlas, GL caster/resolve ports, both receivers) and matched against OpenGL in a controlled transparent-caster scene. Remaining: complete mapped/stencil/hybrid qualification. | Controlled transparent-caster comparisons plus stock projected, point, CSM, dynamic, cutout, constrained-budget, and fallback gameplay captures. |
| Render targets and tools | Cubemap faces, depth-only targets and multiple color attachments are implemented; finish capture/debug parity qualification, documenting intentional asynchronous diagnostic latency. | Every cube face/aspect, nested capture, resolve, resize and resource-lifetime tests; engine-generated screenshot comparisons. |
| Optimization | Audit the planned indirect/culling, command recording, upload overlap, pipeline warm-up, descriptors, and barriers; implement the remaining applicable Vulkan paths. | Measured CPU/GPU pass times and memory use, performance validation, and correctness comparisons for each enabled path. |
| Release qualification | Windows physical coverage now spans two vendors (NVIDIA RTX 4060, Intel Iris Xe): all 29 stock SP maps load and 20 stock MP maps host bot matches validation-clean on both; a 25-minute 16-load soak with `vid_restart` stays validation-clean and plateaus like OpenGL; a five-run synchronous comparison of four scenes is recorded. Remaining: the harness's per-scene/preset budget runs, Linux/MoltenVK and AMD hardware coverage, and user visual/soak sign-off. | Retained provenance-bound reports, engine captures, user visual/soak sign-off, and Windows/Linux/MoltenVK hardware records. No synthetic claim for unavailable hardware. |
| Promotion | Windows x64 stable (supported opt-in) status signed off by the user on 2026-10-04, with status, usage and release documentation reconciled; `best` stays `gl`. Remaining before Linux/macOS support or any default change: the Vulkan-specific evidence/sign-off gate and AMD, Linux and MoltenVK hardware evidence. | Gate negative tests, exact evidence provenance, explicit sign-off, and a requirement-by-requirement completion audit before changing `best` or support status. |

## Work record

- 2026-10-04 adds multiplayer, soak and performance evidence and a memory
  report. Loopback-only listen servers (`net_ip 127.0.0.1`, `net_LANServer 1`)
  with four bots ran 20 stock MP maps (q4dm1-11, q4tourney1, q4ctf1-8) on
  Vulkan/NVIDIA, Vulkan/Intel and OpenGL: all 60 runs exit cleanly with zero
  VUIDs, and the only warnings Vulkan logs that OpenGL does not are random
  bot-character precache and ragdoll lines. A soak tours eight SP maps twice
  (16 loads, one `vid_restart`, shadow maps, CSM and translucent moments on,
  validation on) in 25 minutes with zero VUIDs; Vulkan heap allocations per map
  repeat across cycles (for example hub1 1746/1751, storage1 1859/1867) and
  settle near 990 MiB, and private bytes rise in the first cycle and then
  plateau, the same pattern the identical OpenGL soak shows. Five synchronous
  `benchmark` runs per scene (1280x720, default 8x MSAA and SMAA, validation
  off, RTX 4060) give median frame times of 5.8/3.5/3.5/3.4 ms on Vulkan
  against 4.8/2.0/2.7/2.6 ms on OpenGL for airdefense1, storage2, medlabs and
  hub1. Vulkan's figure includes a full device wait, presentation included,
  every frame, and both stay far inside the 20/28 ms budgets. `gfxInfo` and
  the new `rendererVulkanMemoryInfo` print VMA usage, budget and live
  allocations per heap. Evidence: `.tmp/vk-stable/` (`sweep-mpdm*`,
  `sweep-mpctf*`, `runs/soak-vk3`, `runs/soak-gl3`, `bench-perf.json`).

- 2026-10-03 (second batch) adds translucent moment shadows and a second
  physical GPU. `r_shadowMapTranslucentMoments` no longer stops at the
  front-end gate on Vulkan: each ownership pass with translucent casters takes
  a block of a three-image RGBA16F moment atlas whose blocks mirror the
  depth-atlas blocks (a 3x2 face grid for point lights) at one per-view scale,
  rendered after the depth maps with the GL caster's stage analysis, ONE/ONE
  accumulation and back-face culling. The atlas and its cleared placeholder
  are named by every set-7 shadow set, so they change only at a frame boundary
  with the device idle. In a laboratory scene (the PBR lab plus a cyan
  translucent pane under the shadowing key light) the moment contribution
  matches OpenGL with per-channel means of (-54.77, -17.78, 0) against
  (-54.83, -17.80, 0) and 95% of the 399k affected pixels within one display
  level, on NVIDIA and on Intel. A 29-map sweep with moments on stays
  validation-clean. Running Vulkan on the Intel Iris Xe (driver 101.5590)
  exposed VUID-vkCmdBindPipeline-variableSampleLocations-01525: pipeline sample
  locations need `variableSampleLocations` under dynamic rendering, so devices
  without it keep their native pattern. With that fixed, all 11 local Vulkan
  matrix cases pass on Intel, and all 29 stock SP maps load and draw their
  opening view validation-clean on Vulkan/NVIDIA, Vulkan/Intel and OpenGL (87
  runs) with no warning that OpenGL does not also log. Evidence is under
  `.tmp/vk-stable/` (`sweep-sp`, `sweep-mom`, `matrix-intel`, `momlab-*`).

- 2026-10-03 closes the remaining stock-independent implementation gaps and the
  runtime-robustness defects an audit of the module found. Authored ARB
  assembly material programs are translated to compatibility GLSL
  (`ARBTranslator.cpp`) and drawn through the authored-program path; all 15
  controls of the new `renderer_vulkan_arb_programs.py` laboratory, including
  reload and restarts, match OpenGL's native ARB execution within one display
  level, and the 32-case native translator test passes. Authored 2D lookups now
  flip for top-down render targets instead of refusing them; the GLSL
  laboratory (20 controls) and reload suite (16) still match OpenGL within one
  level. A latched device now queues an automatic renderer restart instead of
  freezing the window; surface loss rebuilds the surface; a failed swapchain
  create no longer reuses the retired swapchain; a lost strict present mode
  presents with FIFO; acquisition is bounded; minimized windows skip the
  per-frame device wait; live resizes update `glConfig`; a submitted frame's
  out-of-date present no longer escalates a partial `vid_restart`; persistent
  `SUBOPTIMAL` no longer recreates every frame; and shadow-cache, atlas and
  point-cube resizes never retire resources under a recording frame. Drills for
  device and surface loss and mid-game shadow resizes run validation-clean on
  `game/airdefense1`, and all 11 local Vulkan matrix cases pass. Vulkan also
  gains `r_showShadows`, `r_enhancedMaterials` (same on/off delta as OpenGL),
  the renderer-owned `r_resolutionScaleMode` 2/3 upscales, a benchmark command
  that waits for GPU work, and a load-only `GetMaterialStageImageInfo`.
  Evidence is under `.tmp/vk-stable/` in the working tree that produced it.

- v61 hardens the preliminary device inventory through the same compiled
  selection library. Complete physical-device and extension lists, bounded
  retries, dynamic queue storage and nonempty-queue checks replace the old
  fixed caps. Explicit choices query only that device and cannot substitute
  another adapter; verbose scoring only considers suitable candidates. Core
  diagnostic queries are scoped to the advertised API version. All 43
  renderer-selection and 31 probe cases pass, as do four source contracts,
  eight staged startup/GPU/recovery cases and six real-driver probe controls.
  Those controls cover the native NVIDIA/Intel adapters, rejection of a 1.2
  translation adapter, unavailable explicit selection and same-process OpenGL
  recovery. The Intel probe passes but takes 101 seconds; no startup-speed
  improvement is claimed. Stock SP/MP 0x MSAA HDR/resize/restart runs pass with
  16 valid engine captures, unchanged package hashes and no tracked renderer
  warnings. Representative initial and final captures show complete gameplay
  views. Instance-layer/extension queries, the optional
  extension lookup, later creation-failure retry, full visual parity and
  platform/performance qualification remain open. See
  [device admission](../../../vulkan-device-selection.md) and
  `.tmp/vulkan-gap-closure/probe-admission/`.
- v60 moves required device and surface checks ahead of renderer selection.
  Automatic selection can continue past incompatible adapters; explicit
  choices cannot silently substitute another GPU. Device/extension/format
  enumeration retries incomplete results, and admission shares SDR format
  selection with swapchain creation. All 43 native cases and eight staged
  startup/GPU/recovery cases pass. Four stock SP/MP 0x/4x lifecycle runs and
  two resource-failure recovery gameplay runs pass with 34 engine captures,
  unchanged runtime hashes and no tracked renderer warnings. These are local
  functional checks, not parity or timing qualification. A pre-existing shadow source-contract
  expectation is updated to verify the retained world-axis radial helper.
  The preliminary probe's device inventory is hardened in v61 above; earlier
  instance queries, later creation-failure retry,
  full rendering parity and hardware/performance qualification remain open.
  See [device admission](../../../vulkan-device-selection.md) and
  `.tmp/vulkan-gap-closure/device-admission/`.
- v59 traces the retained stalls through Windows GPU queues. Both APIs render
  on NVIDIA and present through Intel; mapped traces show Intel wait packets
  remaining pending for roughly half a second after their unwait events.
  Exact packet and shared-fence joins retain the delayed dependencies without
  treating queue residence as shader execution. A process-local direct-Intel
  control passes the unchanged budget at CPU/GPU p99 17.583/10.624 ms; returning
  to NVIDIA immediately reproduces a 400.538 ms CPU p99. The runtime and all
  rendering settings remain unchanged apart from the control's GPU selection.
  VSync-on hidden-window testing times out before sampling. GPU traces have no
  lost events; CPU scheduler profiling is unavailable under current Windows
  permissions. This narrows the observed path but does not identify its root
  cause or fix it. No renderer/default/quality changes are made; the full
  performance and implementation gates remain open. See the
  [frame-pacing investigation](../../../vulkan-frame-pacing.md) and
  `.tmp/vulkan-gap-closure/fence-scheduling/`.
- v58 corrects the Storage1 benchmark's scene identity. Its old static-spawn
  label described a moving drop-pod intro. The first-entry case is preserved,
  and a separate second-entry case waits for the stock lift to settle. Both
  assert map/filter identity and retain endpoint render-view poses; the second
  also checks its expected position and orientation. Schema-5 replay and
  negative contract tests reject altered or missing scene evidence. Unmodified
  Vulkan/OpenGL runs reach the same settled viewpoint, but CPU p99 remains
  399/463 ms respectively and all timing reports fail. Runtime binaries and
  budgets are unchanged. This is evidence-quality progress, not a stall fix,
  visual-parity claim or performance qualification. See the
  [frame-pacing investigation](../../../vulkan-frame-pacing.md) and
  `.tmp/vulkan-gap-closure/gameplay-pose/`.
- v57 localizes the recurring stock-scene CPU spikes to the Vulkan frame-slot
  fence wait. Short bounded waits and a visible non-focusable window both
  reproduce the delay; neither experiment is retained. The renderer trace now
  distinguishes fence waits, image acquisition, resource retirement and
  presentation. The cause upstream of fence completion and the performance
  gate remain open. A matching OpenGL control also stalls during resource
  retirement, so the symptom is not established as Vulkan-specific. The staged
  benchmark contract and Vulkan startup/HDR/motion checks pass; both stock
  timing controls still fail. See the [frame-pacing investigation](../../../vulkan-frame-pacing.md)
  and `.tmp/vulkan-gap-closure/frame-stall/` for failed controls and provenance.
- v56 isolates the nineteen mapped outliers to receiver radial-reference
  rounding plus caster component order. Lossless intermediates identify
  viewport-orientation interpolation and different square-summation orders on
  the qualification GPU. A general candidate uses canonical offscreen main
  scenes and explicit world-axis radial arithmetic, with normal presentation
  and unchanged shadow quality. The default nine-tap mapped image now passes
  the complete two-level gate; all 26 independent authored-lighting controls
  and twenty ordinary material comparisons pass. Three stencil boundary
  pixels, two single-lookup pixels and one disabled-bias pixel still fail their
  respective controls. PBR/HDR recovery controls, three staged GPU groups and
  four stock SP/MP 0x/4x runs pass without tracked warnings. Five stock timing
  runs before and after the change all fail the CPU budget with approximately
  0.4-second p99 stalls; GPU p99 remains below 10 ms. Those live-scene runs do
  not isolate the new presentation cost, and no performance claim is made.
  See the [point-shadow investigation](../../../vulkan-point-shadow-parity.md)
  and `.tmp/vulkan-gap-closure/point-shadow-arithmetic/`.
- v55 verifies lossless float32 byte capture across 981,153 mapped receiver
  pixels on each backend. Both instrumented normal-rendering controls exactly
  reproduce v54. Replaying GL's measured receiver vector, reference and bias at
  the nineteen failing pixels removes seventeen mismatches while leaving every
  other pixel unchanged. The remaining two are the same pixels affected by the
  v54 caster component-order experiment. This isolates receiver-input and caster
  arithmetic sensitivity without changing production quality or the image gate.
  The replay is diagnostic only and is removed; a general renderer correction
  remains open. Values, controls and source/runtime archives are retained under
  `.tmp/vulkan-gap-closure/point-shadow-values/`. See the
  [point-shadow investigation](../../../vulkan-point-shadow-parity.md).
- v54 reproduces the v53 point-shadow failures exactly and isolates them with
  seventeen GPU-projection and six CPU-projection controls per backend.
  Depth bounds, two-pass stencil and cap handling do not remove the three
  stencil boundary errors; changing depth bias moves them, and hiding the
  caster removes them. CPU/GPU extrusion comparisons agree. A radial-distance
  component-order prototype reduces mapped outliers from nineteen to seventeen
  but does not meet the unchanged gate, so it is reverted with evidence retained.
  Manual and hardware sampling probes narrow the remaining map investigation;
  the manual GL color-depth fallback is not the native-depth storage contract.
  No quality reduction or acceptance-threshold change is adopted. See
  [point-shadow investigation](../../../vulkan-point-shadow-parity.md).
- v53 adds authored GLSL per-light execution with light/view vectors, projected
  and falloff textures, material matrices/colors and vertex-color semantics.
  Generic mapped requests use receiver-specific retail stencil fallback while
  stock receivers keep mapped filtering. CPU-composed canonical vertex
  transforms preserve equal-depth coverage. Explicit linear/nearest samplers
  now ignore resident mip chains, fixing an exact image-reload mismatch.
  An OpenGL material-table repair clears conflicting shadow sampler state from
  unused declared texture slots. Both backends pass all 26 lighting controls,
  with exact reload/restart recovery and mapped-to-stencil equivalence on the
  custom receiver. All 26 receiver comparisons stay within one display level;
  the shadowed receiver comparisons are exact. The unchanged full-frame
  comparison still fails: three point-stencil background pixels exceed two
  levels (maximum 30), and nineteen point-map background pixels do so (maximum
  five). These failures remain recorded, not masked into a passing suite.
  Projected-shadow full frames differ by at most one level. The 33 native compiler cases and
  independent validation of 24 modules pass with the expanded 1,312-byte block.
  The final runtime passes twenty ordinary material comparisons, 35 OpenGL HDR
  controls and three Vulkan GPU groups without tracked diagnostics. The scoped
  successes and full-frame failures are bound by
  `.tmp/vulkan-gap-closure/authored-lighting/checkpoint-v53-authored-lighting.json`.
  Evidence is retained under `.tmp/vulkan-gap-closure/authored-lighting/`;
  broader shader/state/geometry, shadow, performance and release gates remain open.
- v52 makes stock GLSL selection depend on actual reviewed source fingerprints,
  with built-in compatibility defaults only for canonical names lacking every
  source candidate. Modified and incomplete sources cannot silently select a
  stock shader. Both backends now register and implement `reloadGLSLprograms`;
  `reloadARBprograms` also reloads GLSL. Failed GL compilations are cached until
  reload/context change, and Vulkan checks reusable versions before its cache
  limit. Sixteen live-edit, invalid-source, incomplete-pair and recovery image
  controls per backend pass, with exact same-backend recovery and at most one
  display level of GL/Vulkan difference. The unchanged three SMAA sources still
  select their verified native implementations. The new test caught and fixed
  Vulkan's missing reload-command registration and now rejects unknown commands.
  The native compiler and source-table Meson checks pass. All 35 OpenGL HDR/bloom
  controls pass, including exact shader-reload recovery. The final Vulkan
  target/HDR/temporal GPU groups have zero tracked warnings. Evidence is under
  `.tmp/vulkan-gap-closure/material-reload/`; broader custom-program and all
  other completion requirements remain open.
- v51 connects the authored GLSL compiler to native ambient draws for previously
  unknown program names. Source lookup is shared with GL; modules and bounded
  descriptor/uniform resources have explicit frame/device ownership. Complete
  file lengths preserve embedded-NUL rejection, and active parameter widths
  must match their authored declarations. The 33-case native suite and all 24
  independently validated modules pass. Twenty image controls match GL within
  one display level; all capacity/binding controls are pixel-identical. They
  also expose and repair missing named normal/tangent arrays in GL ambient
  GLSL. Each backend exactly restores its base image after image reload and
  partial/full restart. Its unchanged-shader control did not establish Vulkan
  reload-command registration; v52 supplies actual live-edit coverage.
  Stock-name overrides and changed-source reload were still open at this point.
  Custom lighting, flipped render textures, broader language and
  state coverage, resource exhaustion and authored ARB remain open. See
  [material program support](../../../vulkan-material-programs.md) and
  `.tmp/vulkan-gap-closure/authored-glsl/` for retained evidence. Experimental
  status and all other completion requirements above remain unchanged.
- v50 adds a native Meson-built GLSL compiler foundation for authored material
  programs, with source validation, compatibility translation, named bindings,
  paired linking and SPIR-V emission. Compiler fixtures and independent module
  validation exercise the initial language subset and explicit failures.
  Runtime source admission, drawing, resource recovery, custom lighting and ARB
  assembly remain open; the staged renderer still uses its embedded families.
  See [material program support](../../../vulkan-material-programs.md) and
  `.tmp/vulkan-gap-closure/material-programs/`. This does not replace or relax
  the outstanding image, sampling, hardware or release requirements.
- v49 tests two shared-filter prototypes on 1,042 actual, stress and degenerate
  inputs against independent full-area alpha integration. Twenty readbacks
  verify unchanged resident data and historical native samples. A discrete
  tap-count implementation matches the original 172 records but develops a
  0.125002 cross-API alpha jump near integer aspect ratios. Blending adjacent
  kernels reduces the maximum to 0.00121978; nineteen differences, per-input
  quality regressions and a potential 31-fetch cost remain. Neither prototype
  is adopted or presented as gameplay/performance qualification. Both production
  integration points are restored exactly. The clean rebuild passes ten capture
  controls and the target/HDR/motion GPU contracts; every image reproduces the
  named production reference. Source, runtime and experiments are bound by
  `shared-filter/checkpoint-v49-shared-filter.json`. See the
  [shared-filter assessment](../../../vulkan-pbr-cutout.md#v49-shared-filter-prototypes)
  and `.tmp/vulkan-gap-closure/shared-filter/`. No image limit, anisotropy
  quality or broader completion requirement is relaxed.
- v48 reproduces the cutout sampling difference without rasterization. A
  temporary compute probe feeds all 172 exact fragment inputs to the actual
  PBR texture and sampler, and reads every resident RGBA mip texel. Twenty
  readbacks across two processes per API repeat exactly: all 5,461 texels match,
  and each API reproduces its earlier actual-fragment alpha values. Explicit
  gradients still differ in twelve 16x samples and none at 1x. Fractional
  explicit-LOD controls also differ only with anisotropy enabled, so choosing
  another mip level alone is insufficient. Both production sources are restored
  exactly; no quality setting or image limit changes. The rebuilt runtime passes
  ten capture controls and the target/HDR/motion GPU contracts. All Vulkan and
  hard GL images repeat production; clean GL smoothed masks retain the known
  two/four-pixel variation at 16x/1x, without relaxing the failed parity gate.
  Source and runtime are bound by `sampler-compute/checkpoint-v48-fixed-sampling.json`. See the
  [fixed-input sampling diagnosis](../../../vulkan-pbr-cutout.md#v48-fixed-input-gpu-sampling)
  and `.tmp/vulkan-gap-closure/sampler-compute/`. Sampling, coverage and the
  broader qualification requirements remain open.
- v47 rejects sampler-bound and dither-mode shortcuts for the remaining
  cutout discrepancy. A -1000 lower mip-LOD bound reproduces all five Vulkan
  masks exactly. Thirty valid GL captures compare default, enabled and disabled
  NV dithering in two processes each. Default smoothed masks vary by two/four
  pixels at 16x/1x; explicit enable still varies by one 1x pixel. Disable repeats
  exactly but differs from Vulkan by 215/214 pixels, so it is not adopted.
  Every hard GL mask repeats production, including the one-pixel hard 16x
  cross-API failure. The first probe incorrectly reused the driver's raw
  boolean query value as a setter enum; its erroring run is rejected. The
  corrected probe uses advertised support and documented enums. All temporary
  source edits are restored to v46. The clean rebuild passes ten mask capture
  controls and all three target/HDR/motion GPU contracts without tracked renderer
  warnings. Every GL and Vulkan image reproduces the named v46 reference; source, runtime
  and experiments are bound by `sampler-footprint/checkpoint-v47-sampler-dither.json`.
  See the
  [sampler and dithering investigation](../../../vulkan-pbr-cutout.md#v47-sampler-limits-and-coverage-dithering)
  and `.tmp/vulkan-gap-closure/sampler-footprint/`. Full parity remains open.
- v46 fixes native PBR coverage multiplying sampled alpha by a perspective-
  interpolated constant. An authored 1.0 can become 0.99999994 and reject opaque
  texels at an inclusive 1.0 cutoff. The shader now reads constant stage alpha
  directly. A verified 4x fixture loses coverage in 4,436 pixels with the old
  module and matches opaque geometry exactly with the fix, including image
  reload and partial/full video restart. All 56 GL/native cutoff and minification
  controls pass at 0x/4x; all sixteen minification-suite pairs are exact.
  Actual fragment probes match GL's
  coordinates and texture gradients in all 172 records; corrected 1x alpha,
  alpha derivatives and coverage also match exactly. The hard 16x residual
  comes from sampled alpha straddling 0.5 despite matching measured inputs.
  The corrected probe's smoothed LOD-query metadata is not accepted as evidence.
  Temporary C++ instrumentation is removed from the production build. Clean
  ordinary masks retain one hard and four smoothed 16x differing pixels, so
  the unchanged strict parity gate remains failed. The final staged renderer
  reproduces all five clean isolated masks, passes target/HDR/36-case-motion GPU
  contracts without tracked renderer warnings, and passes shader/header pins.
  Engine captures were visually inspected. Evidence is pinned in
  `alpha-fragment-probe/checkpoint-v46-constant-alpha.json`. See
  [constant-alpha evidence](../../../vulkan-pbr-cutout.md#v46-constant-alpha-correction-and-fragment-evidence)
  and `.tmp/vulkan-gap-closure/alpha-fragment-probe/`.
- v45 separates the remaining cutout sampling and coverage observations.
  Eleven matched 4x cases exercise hard/smoothed coverage at 1x/2x/4x/8x/16x
  anisotropy and restoration. Hard-cutoff comparisons retain 0/6/5/7/1
  differing pixels respectively; the 16x mismatch is one covered sample at
  (697, 631). Repeated GL processes have exact hard masks but two or three
  changing smoothed pixels; the original Vulkan run reproduces its four
  common v44 images exactly. Explicit coarse gradients reproduce all eleven
  original images on each API, and fine Vulkan gradients worsen the previously
  exact 1x hard case. All three diagnostic variants are rejected as fixes.
  Four source files are restored byte for byte and both clean renderers are
  rebuilt and restaged. All eleven clean cases on each API reproduce their
  respective initial v45 images exactly in display and linear captures. The staged
  target/HDR/36-case-motion GPU contracts pass without tracked renderer warnings,
  and the embedded shader/header pins pass.
  Evidence is retained under `.tmp/vulkan-gap-closure/anisotropic-coverage/`
  and `checkpoint-v45-filtering.json`; see the
  [filtering investigation](../../../vulkan-pbr-cutout.md#v45-filtering-investigation).
  Direct fragment-input/sampled-alpha probes are still needed. No comparison
  tolerance, silhouette rule or reference result is waived; baked lighting,
  HUD anisotropy and the broader completion requirements remain open.
- v44 makes canonical offscreen Vulkan rendering use GL framebuffer coordinates,
  carrying the convention through viewports, scissors, winding, sample locations,
  screen-coordinate shaders, color/depth copies, motion inputs and presentation.
  Image writers record stored row order; resolves preserve it and consumers
  normalize it. The experimental switch is removed. The HDR boundary also
  restores the correct winding for later geometry with no direct lights.
  All sixteen ordinary/minified cutout and recovery pairs at 0x/4x now match GL
  exactly in display and linear captures. The original smoothed 4x/16x-anisotropic
  mask improves from 444 differing pixels to four; 1x smoothed and hard masks
  are exact. The retained 16x and baked-lighting comparisons still fail the
  unchanged full-image limits and remain open. All eighty independent GL/native
  preview controls pass; all forty 8x pairs differ by at most one display value,
  including an exact 125% case that previously failed by 49. A fresh GL reference
  satisfies the comparator's harness-source gate. Thirty-eight HDR post controls,
  all three target/HDR/motion GPU contracts, and staged stock SP/MP runs with
  sixteen captures pass without tracked renderer warnings. Motion fixtures now
  cover both stored depth origins, preserving the original numerical oracles.
  Shader/header and temporal contracts pass, and representative engine captures
  were inspected. Earlier build, synthetic-origin, stale-winding and comparison-
  provenance failures are retained as rejected evidence. Source, runtime and
  reports are bound by
  `.tmp/vulkan-gap-closure/framebuffer-orientation/checkpoint-v44-image-origin.json`;
  see [image orientation](../../../vulkan-image-origin.md). Native HUD filtering,
  broader lighting/material scope, performance, hardware/platform/soak
  qualification and promotion remain open.
- v43 fixes native PBR depth coverage selecting a classic image copy instead
  of the typed albedo. The actual checker mips contain classic alpha 127 and
  PBR alpha 128, which straddle the 0.5 cutoff. All 32 independent GL/native
  minification and recovery controls pass at 0x/4x; twelve paired minified,
  opaque and recovery cases are exact. The old module loses all 7,278 visible
  minified pixels and fails the same oracle. Ordinary cutout/restoration pairs
  retain one differing pixel at 0x and two at 4x, so both strict comparison
  reports remain failed. On the original isolated 4x specimen, the fix reduces
  hard-cutout differences from 19 pixels to four; smoothed coverage still
  differs at 444 pixels. A retained positive-height viewport control reduces
  that smoothed discrepancy to four pixels after deliberate image reflection,
  strongly implicating framebuffer orientation without supplying a production
  fix. The diagnostic module predates the typed-albedo repair; its first run
  failed because its test package omitted mod.json and is rejected evidence.
  No viewport or shader experiment is staged. Both target/HDR GPU contracts
  and staged stock SP/MP runs pass, with sixteen engine captures and no tracked
  rendering warnings. Representative images were inspected. Sources, runtime,
  fixture, negative controls and unchanged strict limits are retained under
  `.tmp/vulkan-gap-closure/pbr-cutout-coverage/` and
  `checkpoint-v43-cutout-coverage.json`; see [cutout coverage](../../../vulkan-pbr-cutout.md).
  Full coverage/lighting parity, the prior preview and HUD differences, broader
  material support, platform/performance qualification and promotion stay open.
- v42 implements bounded native baked PBR lighting in HDR views. Every receiver
  is prepared before ownership; baked irradiance replaces environment diffuse
  while authored or analytic reflections remain. Three existing grid atlases
  and their metadata share the native material/probe path, with image-generation
  tracking, frame-fenced descriptors and whole-view preparation rollback.
  Classic flat-normal receivers retain encoded accumulation and the same
  quantized normal decode as GL. HDR-off baked views keep the existing fallback.
  The final runtime passes 79 independent GL/native laboratory controls,
  including all receiver submissions, material/normal response, 4x MSAA,
  fog/blend composition, image/video recovery, preview fallback and six injected
  failures with exact restoration. Both target/HDR GPU contracts and staged
  SP/MP runs pass, with sixteen engine captures and no tracked renderer warnings.
  Shader pins pass. These are correctness results, not full-frame parity:
  the 0x isolated no-reflection display differs by at most one value, but its
  linear comparison still reaches 0.00390625 on emissive surfaces. Reflections
  differ even without baked lighting, and cutout/coverage differences are larger
  at 4x. The strict normal, preview and 4x isolated comparisons remain failed.
  The incomplete first candidate, incorrect GL-only shader-reload test and
  overbroad preview assumption are retained as rejected evidence. Standalone
  Vulkan shader-library reload remains unsupported. Source/build/runtime/bake
  provenance and the unchanged comparison limits are recorded in
  `.tmp/vulkan-gap-closure/hdr-lightgrid/checkpoint-v42-baked-hdr.json`; see
  [native baked HDR](../../../vulkan-pbr-baked.md). Broader material/grid/view,
  platform, performance and promotion requirements remain open.
- v41 narrows the remaining 125%/8x PBR edge difference to the viewport and
  rasterization coordinate convention. Engine-side probes verify all 1,223
  uploaded positions, 6,624 indices, XYW matrix rows, normalized scissors,
  viewports and sample locations. GL transform feedback and a diagnostic
  Vulkan vertex-storage variant produce identical XYW positions at the
  affected silhouette edge. Other vertices have small X differences, while
  all Y and W values match. Adding Vulkan position invariance changes no
  captured pixels and is rejected as a fix. A positive-height Vulkan viewport
  control, with corresponding sample/scissor reflection and winding state,
  matches the complete GL raw scene and display exactly after the deliberate
  image reflection. An explicitly labeled CPU rounding model predicts GL
  background and one Vulkan-covered sample at the failing texel; actual GPU
  fixed-function viewport outputs were not captured. This supplies a focused
  explanation, not production parity or a tolerance waiver. All six temporary
  renderer files are restored byte-for-byte to v40. Both clean PBR captures
  reproduce the original images exactly, and the staged render-target/HDR
  GPU contracts pass without tracked renderer warnings; shader pins pass.
  Probe validation and
  orientation-state failures are retained separately from accepted controls.
  Evidence: `.tmp/vulkan-gap-closure/clip-coverage/` and its
  `checkpoint-v41-clip-coverage.json`. The original maximum-49 comparison,
  native HUD anisotropy and the broader completion requirements remain open.
- v40 replaces native resolve for sampled two-dimensional RGBA8 multisample
  targets with an explicit average of their stored samples. The classic 8x
  color-edge SMAA failure is closed: the source now matches GL exactly and
  the display maximum drops from 59 to one. All thirteen raw/display pairs
  pass within one byte, with all 26 capture/recovery controls passing.
  All 124 independent SMAA controls pass at 4x/8x on both APIs. Sixty of 62
  full-frame comparisons pass within one byte; both remaining failures are
  the unchanged native HUD anisotropy case, maximum 78. All eighty 8x PBR
  preview controls pass independently and 39/40 pairs pass the unchanged
  gate. The separate 125% coverage comparison still fails at maximum 49.
  New GPU fixtures require exact non-halfway byte averages for every sample
  coverage count at supported 2x/4x/8x, all four channels, repeated resolves
  and larger/smaller/equal destinations with preserved uncopied pixels.
  The target/MRT/depth and HDR GPU contracts pass with active validation;
  shader/header pins pass. The scope retains single-sample, float and layered
  native paths and prepares every descriptor before writing any attachment.
  Both staged stock SP/MP runs pass with sixteen engine captures and no
  tracked renderer warnings; representative images were inspected. Existing
  MP navigation/precache, item-placement and loading-image warnings, the SDL3
  wrap warning and GL diagnostic performance notices remain separate.
  Sources, build, runtime, fixture and strict comparison reports are retained
  by `.tmp/vulkan-gap-closure/ldr-resolve/checkpoint-v40-ldr-resolve.json`.
  Task-created generated caches were removed. Broader completion requirements
  above remain open; there is no renderer promotion or platform/performance claim.
- v39 replaces the native intermediate float resolve in HDR-off PBR previews
  with an explicit average of the stored samples in the final copy shader.
  At the 150%/8x failure from v38, the native blue resolve was 0.98388671875
  instead of the stored samples' average of 0.99951171875. The repaired raw
  capture matches GL exactly and its SMAA display differs by at most one byte.
  All thirteen targeted raw-source comparisons now pass the original gate.
  All 160 clean-build preview/recovery controls pass independently at 4x/8x
  on both APIs. All forty 4x image pairs pass within one byte; 39/40 pass at
  8x. The Vulkan HDR GPU contract, shader/header pins and all 26 image-capture
  controls pass. Both staged stock SP/MP runs pass with sixteen captures and
  no tracked rendering warnings; representative engine images were inspected.
  The new 125%/8x preview control separately exposes one differing scene
  texel, affecting three display pixels with maximum 49. Engine-side probes
  show background in all eight GL depth samples and zero color before the
  final handoff; GL 3.3 and 4.5 agree exactly. Coverage/transform diagnosis
  remains open, and this strict comparison remains failed. Replaying the
  archived v38 Vulkan module reproduces it, excluding the new average as its
  cause.
  The classic 8x SMAA investigation now proves all 64 sampled RGBA8 values
  equal before native resolve; one blue average of 159.375 resolves to 159
  on GL and 160 on Vulkan. Explicit attachment-average resolve changed no
  pixels and was reverted. The display failure remains thirteen channels,
  maximum 59. All temporary probes have been removed from production source;
  rejected probe readings and unchanged-frame checks are retained under
  `.tmp/vulkan-gap-closure/msaa-input-parity/`. Its
  `checkpoint-v39-preview-average.json` binds the final source, build, fixture,
  runtime, reports and prior evidence. Task-generated caches were removed.
  Existing stock navigation/precache, item-placement and loading-image
  warnings, SDL3 wrap warning and GL diagnostic performance notices remain.
  Native HUD anisotropy and all broader completion requirements above remain open.
- v38 adds raw `screenshot image` exports on both backends, preserving stored
  RGBA8 pixels, target dimensions and frame state. All 26 independent image
  capture controls and 38 existing HDR lifecycle controls pass. The seventeen
  shared float pairs and eighteen HDR display pairs remain exact, and four GPU
  contracts pass with no tracked renderer warnings. All four staged stock
  SP/MP profiles pass with 32 gameplay captures; representative engine images
  were inspected. Existing MP navigation, item-placement and asset warnings
  remain, along with the SDL3 wrap-revision build warning. See the
  [image-capture contract](../../../renderer-image-capture.md).
  Raw captures place the classic 8x color-edge SMAA discrepancy before SMAA:
  seventeen resolved-scene pixels differ by one byte, and both APIs copy their
  resolved scene into SMAA exactly. At one pixel that byte changes the local
  contrast decision. Whether rasterized sample values or native resolve
  precision produces it still requires proof. Vulkan edge `texelFetch` and
  disabled OpenGL dithering experiments changed no pixels and were reverted.
  The original display failure remains thirteen channels, maximum 59.
  A newly exercised 150% PBR preview at 8x/HDR-off also fails: seven source
  channels differ by up to four bytes, expanding to 85 display channels with
  maximum 27 after SMAA. Twelve of thirteen raw-source pairs pass the unchanged
  two-byte gate; successful capture tests do not convert these rendering
  differences into parity passes. Native HUD anisotropy and the broader
  material/platform/release requirements also remain open. Sources, runtime,
  rejected experiments and evidence are bound by
  `.tmp/vulkan-gap-closure/smaa-color-parity/checkpoint-v38-image-capture.json`.
- v37 fixes the modern OpenGL reference's supersampling/MSAA policy and target
  cache exhaustion. Admitted PBR scenes keep requested MSAA at 125/150/200%;
  a full cache retires only unused allocations, with binding and attachment
  cache invalidation when GL object names can be reused. The initial expanded
  run reproduced whole-view fallback at 150/200% after reaching 64 allocations.
  Both GL 3.3 binding-based and GL 4.5 DSA paths now pass all 39 lifecycle
  controls, each proving 326 retirements before restart, bounded allocation
  counts and exact image restoration. All 124 independent SMAA controls pass
  at 4x/8x on both APIs, including the added scales. Every scale pair stays
  within one display byte. Strict full-frame comparison passes 30/31 pairs at
  4x and 29/31 at 8x; native HUD anisotropy still differs, and 8x classic LDR
  color-edge SMAA has thirteen channels outside the gate (maximum 59).
  These remain failures under the unchanged two-byte threshold.
  Fixed-tic, initially frozen HUD controls isolate the sampler difference:
  five ordinary filter pairs match exactly across the full image, while
  default/restored 16x anisotropy still differs by up to 78. A derivative-sign
  shader experiment made no difference and all three original shader/header
  files were restored exactly. No speculative shader change is retained.
  All 38 independent linear-capture controls pass; the seventeen shared PFM
  pairs and eighteen shared display pairs are exact. Vulkan's two additional
  rejected-capture controls remain independently checked. Four GPU contracts
  and all four staged stock SP/MP profiles pass, with 32 captured
  stock images and no tracked rendering warnings. Representative engine
  captures were inspected. Existing MP navigation/precache warnings remain.
  Sources, runtime, failed experiments and final reports are bound by
  `.tmp/vulkan-gap-closure/presentation-parity/checkpoint-v37-presentation.json`.
  Both renderer modules were rebuilt; the engine, game modules, assets and
  companion source pin are unchanged. Full material/HDR admission, the stated
  presentation differences, hardware/platform and release gates remain open.
- v36 extends OpenGL's exact authored fog/blend phase to eligible HDR-off PBR
  previews. The same sealed geometry, frustum caps and blend stages run after
  opaque lighting and before ordered transparency and MSAA resolve. The shader
  keeps classic preview colors encoded and skips its clustered approximation;
  shared ownership is consumed only after the exact phase executes. The Vulkan
  binary is unchanged from v35.
  All 111 full-frame image pairs pass the original two-byte gate at 0x/4x/8x,
  using the default lighting-parity setting on GL. Each tier has 37 independently
  qualified captures per API, including exact reload/restart and toggle recovery.
  The maximum differences are one byte at 0x/4x and two at 8x; the seventeen
  fog/blend failures per tier from v35 are closed within this fixture scope.
  Both seven-case HDR radiance suites also pass, checking 22 opaque specimens,
  continuous fog coverage, authored blend factors and transparent background
  composition. Twenty-eight whole-scene controls pass on actual GL 3.3 and 4.5
  compatibility contexts, including exact classic fallback when the required
  scissor contract is disabled and exact restoration. Both staged stock GL
  SP/MP profiles pass with sixteen 8x captures, reload/restart and no tracked
  rendering warnings. Engine captures were inspected; MP navigation/precache
  warnings remain separate. `checkpoint-v36-preview-fog.json` binds the
  sources, runtime and reports under `.tmp/vulkan-gap-closure/preview-fog/`.
  The parent failures and obsolete fallback expectations remain archived;
  this run's disposable generated caches were removed. Whole-view admission,
  broader material/platform qualification and experimental status remain open.
- v35 preserves HDR-off PBR radiance until multisample resolve. Classic
  accumulation keeps the original target format and stage-color limits;
  PBR accumulates in FP16. The opaque combine preserves the classic encoded
  domain, followed by native fog/blend and ordered transparent PBR in FP16.
  The resolved scene is then copied to the original destination before post
  processing. Transparent pipeline variants are prepared for the float target
  together; the original resources remain available for fallback. Stock-only
  views keep their original targets.
  The 37-case preview suite passes independently on both APIs at 0x/4x/8x,
  including exact recovery across scaling, target changes, HDR/PBR toggles,
  reload and restart. Twenty paired images per tier pass the unchanged
  two-byte gate (0x/4x exact); seventeen per tier still differ for diagnostic,
  ordinary and shared HDR-off fog/blend combinations. The GL comparison
  explicitly opts into its experimental fog parity domain. Those failures
  were left open rather than hidden by a wider gate; v36 addresses them above.
  All 24 new on-device
  clamp/resolve fixtures pass before/after restart; all 44 transparent resource
  controls and both staged stock SP/MP profiles pass, with sixteen 8x captures
  and no tracked rendering warnings. Both 29-case SMAA sequences pass their
  own orientation/recovery checks; 27 paired images now pass, including all
  five previously failing HDR-off PBR edges. HUD color and the 125% MSAA policy
  remain different. Earlier transparent attachment-format
  failures and harness/admission mistakes remain preserved as negative evidence.
  `checkpoint-v35-pbr-preview.json` binds the source, runtime and evidence under
  `.tmp/vulkan-gap-closure/pbr-preview/`. Full Vulkan
  closure, unsupported view admission and experimental status remain unchanged.
- v34 measures actual GL 4x/8x LDR/HDR attachment sample positions and confirms
  that the canonical Vulkan image orientation reflected their coverage pattern.
  Optional `VK_EXT_sample_locations` now supplies the lower-left standard
  2x/4x/8x pattern consistently across pipelines, compatible depth images and
  depth transitions/resolves. Device checks cover each count's coordinates,
  precision and grid plus both public depth formats; unsupported counts retain
  native MSAA. The choice stays fixed until device teardown.
  All 72 classic 4x pairs are exact, all 72 at 8x stay within one byte, and the
  two 2x controls are exact. All 21 linear HDR 4x float pairs pass their original
  fixed tolerances, with all 21 display pairs within one byte. The 58 SMAA
  orientation/recovery cases pass independently, with 22/29 strict image pairs
  passing. The five HDR-off PBR-preview pairs still fail; three distinct edge
  levels suggest clamping before versus after resolve, which needs its own
  investigation. The HUD still differs, and GL disables MSAA at 125% while
  Vulkan retains it. None of these comparisons uses a wider tolerance.
  Forced-native 4x/8x controls pass their own color/validation gates and retain
  the expected GL edge mismatch; the 4x native controls are byte-identical to
  the original Vulkan captures. The color harness records capability state,
  supports 2x and exposes an explicit native-fallback control. Temporary GL
  instrumentation was removed before the final build. GPU validation and both
  stock SP/MP profiles pass with sixteen 8x captures, including bulk reload and
  partial restart, and no tracked rendering warnings. MP AAS/precache warnings
  remain separate. `checkpoint-v34-msaa-samples.json` binds the evidence under
  `.tmp/vulkan-gap-closure/msaa-samples/`; local results do
  not supply cross-platform, hardware-family, performance or soak sign-off.
  Full Vulkan gap closure and experimental status remain unchanged.
- v33 fixes classic Vulkan stage-color limits and masked depth alpha without
  clipping native PBR emission. Primary colors clamp before texture modulation;
  vertex/inverse-vertex tints retain their range on floating-point attachments.
  The original ASE vertex-color fixture also exposed an uninitialized alpha
  byte in RGB-only imported colors; both renderers now receive opaque alpha.
  Shared world ambient preparation consumes validated modern-only lighting
  records while preserving the classic no-op contract, preventing spurious
  packet mismatch and backend rejection.
  All 324 independent color controls pass: 90 per API at 0x, including eighteen
  actual shared-owner controls, and 72 per API at 4x. The ninety 0x full-frame
  pairs are byte-identical. The final 58 GL/native SMAA/PBR recovery controls
  pass, with all ten previously failing classic scene pairs and eighteen PBR
  scene pairs within one byte. The HUD pair still fails (maximum 78), and sixty
  of seventy-two strict 4x color pairs fail at coverage; the twelve matching
  controls are deliberately black cutouts. No tolerance was widened.
  A broader stock-log audit found a second issue: bulk reloads could retire
  more than 128 image descriptors in a frame and skip subsequent draws. The
  reserve and descriptor pool now cover a full image-cache generation plus
  the existing feedback allowance, retaining fence-based release and bounded
  rollback. A mandatory GPU test preserves exact colors through 256 image
  generations per frame over four frames. Both validation runners now reject
  skipped/refused draw warnings, with positive and benign-log regression tests.
  Seven retained v32/v33 stock reports fail this corrected reload gate despite
  their original pass status. Final j stock SP/MP runs pass all sixteen captures
  at actual 8x MSAA, including reload and partial restart, with no Vulkan
  warnings; the complete GPU suite passes with active validation.
  Evidence is under `.tmp/vulkan-gap-closure/classic-colors/`, bound by
  `checkpoint-v33-classic-colors.json`. Color proofs retain their i (0x) and h
  (4x) binaries; j changes descriptor capacity and adds its diagnostic, and
  has separate GPU, stock and native SMAA evidence. Failed shared-path attempts,
  the initial mismatched content-pack copy, original GL interception controls,
  and superseded stock reports remain recorded. Optional modern GL visible
  execution still ignores the tested primary-stage modulation; the classic
  reference explicitly disables it. MP AAS/precache warnings remain separate.
  This closes these bounded defects, not the remaining HDR/material, HUD/MSAA,
  platform, performance, soak or promotion requirements. The goal stays active.
- v32 fixes the upside-down world found by the editor's engine capture when
  SMAA was enabled. An off-centre specimen reproduced the inversion with PBR
  both off and on; the same OpenGL views stayed upright. Native GLSL material
  stages now supply one orientation bit per bound image, and the three SMAA
  shaders convert each sample after its authored neighbor/search offset.
  Uploaded lookup textures retain their own orientation. `gfxInfo` also stops
  using OpenGL GLSL availability to disable its Vulkan SMAA report.
  All 174 GL/native laboratory cases at 0x/4x/8x pass: four SMAA presets,
  classic/PBR, HDR toggles, 50/75/125% scaling, image reload, partial/full restart
  and HUD. Thirty full-image restoration comparisons are exact. Four staged
  stock SP/MP GL/native profiles pass their original gates with actual 8x MSAA;
  all sixteen stock orientation comparisons pass, with 32 engine captures.
  The v33 audit later found uncounted descriptor-retirement warnings in the
  native stock reload controls; those profiles are not clean-reload evidence.
  Eighteen 0x PBR scene pairs stay within one byte/channel. Classic emission,
  the visible-HUD comparison and all strict 4x/8x pairs still fail their existing
  two-byte gate; no tolerance was widened. Actor/effect timing also precludes
  a full-frame stock parity claim. Those remaining color/coverage differences
  do not undo the separate orientation/recovery result.
  Evidence, pre-fix captures, the old-module diagnostic failure and two GL
  fixture assumptions are retained in `.tmp/vulkan-gap-closure/scene-orientation/`.
  A guarded install deferred while the editor runtime was active; later
  attempts encountered its build lock and executable lock. No other process
  was stopped. The editor's subsequent stage supplied the same verified
  renderer/game modules and its updated client for the passing stock profiles.
  `checkpoint-v32-smaa-orientation.json` binds the source/runtime archives,
  reports, image analysis and unresolved comparisons. This closes this SMAA
  defect locally; the overall goal and Vulkan's experimental status remain open.
  A subsequent editor rebuild changed both module identities without changing
  the pinned renderer sources. Two additional GL/native stock SP profiles pass
  on that package under the original gates; `integration-v32e.json` binds its
  binaries, sixteen captures and eight orientation checks. Its native reload
  warning is included in the v33 correction above. The older v31 HUD pair also reproduces a
  cross-API color difference while its scene-only pair is exact; it is retained
  in `prior-hud-comparison-v31.json`, without assigning a cause yet.
- v31 implements native `screenshot linear` for completed admitted HDR scenes.
  The output chain's existing capture has a dedicated image and completion
  lifetime; explicit float readback submits without presenting and resumes the
  same acquired frame. Frame/view, image-generation and restart guards reject
  unavailable or stale scene captures. All 84 initial GL/native composition
  controls pass at 0x/4x, along with 40 native and 18 GL lifecycle controls,
  three GPU cases and four stock SP/MP profiles. All 21 full-frame 0x float
  pairs pass. The strict 4x paired comparison remains failed at silhouette
  coverage; all twenty comparable native display images match pre-change v29c
  exactly. Reflected sample locations strongly fit the independent projection
  analysis, but actual hardware positions have not been queried and one residual
  boundary pixel remains. This is an inference, not a parity pass.
- The v31 HUD-after-reload check exposed empty TrueType scratch images and a
  real undefined-layout Vulkan sample. GUI, extended-character and console
  atlases now retain one-byte coverage planes and regenerate their pixels.
  Full video restart preserves those planes until image generators and the UI
  finish restoring; final renderer shutdown frees them. Both modules build and
  stage, with temporary diagnostics removed. Four GL/native 0x/4x sequences
  reproduce all 64 HUD/atlas restoration pairs exactly and preserve 28 public
  linear captures. The rebuilt candidate also passes both 4x lifecycle suites,
  all 42 repeated 0x composition controls and all 21 float pairs. GL's existing
  125% supersampling policy uses effective MSAA zero; its fixture now requires
  that explicit policy, without relaxing image tolerances.
  The four final native GPU cases pass. All four stock SP/MP 0x/4x profiles have
  passing evidence: shared staging interrupted SP4 and MP0, which the editor
  task then reran successfully with the same renderer/game modules and its
  updated client. Those reports, binaries, logs and captures were independently
  verified and retained here. The original batch stays failed; its passing SP0
  and MP4 profiles remain separately identified. Every candidate/integration
  run retains the exact binary identity it actually used.
  Evidence and failures are under `.tmp/vulkan-gap-closure/linear-capture/`.
  The initial marker/blend-light fixture mistakes, one-step shared-fog float
  difference, unclean menu-return run and actual font regression remain recorded.
  Blend lights deliberately exclude translucent interaction chains on both APIs.
  `checkpoint-v31-linear-capture.json` binds twenty accepted jobs plus the two
  passing profiles from the interrupted batch, source/runtime archives, exact
  glyph comparisons and the open 4x parity result. Disposable generated caches
  were removed; logs, captures and source evidence remain. The overall goal is
  still active and Vulkan remains experimental.
- v30 addresses the remaining scaled reference mismatch by preparing the GL
  graph and the single eligible root view in the requested scene coordinates.
  Color/depth allocations, packets, light-grid dimensions and light/surface
  scissors agree; a scope guard restores view rectangles before the ordinary
  command stream continues. Multi-view/portal streams keep their existing
  path. The off-centre diagnostic matches exactly without bloom and within
  one byte with bloom/exposure. All 33 v30b full post pairs and both GL
  0x/4x post sequences pass. A wider 50% composition test then exposed the
  game's GL RGBA8 forward target clipping emission before tone mapping.
  Canonical `openQ4-game` now requests HDR forward/resolve storage on both
  backends. The matching v30d runtime passes all 33 post pairs and sixty
  composition pairs at 50/75/125%, each within one byte/channel. Independent
  radiance checks, eight clear 4x controls, six scaled lighting controls,
  twelve CPU/GPU animation/restart controls and two GL integration cases pass.
  All four Vulkan stock SP/MP 0x/4x profiles and both 75%-scale GL stock profiles
  pass; the latter use the benchmark's fixed 1280x720 display contract with
  mode reasserted after multiplayer config reload. This is correctness evidence,
  not performance qualification. The GL integration harness now explicitly
  requests its fixture's 640x480 window and 4x MSAA, with hidden windows and
  input disabled; its permanent-source rerun also passes.
  `checkpoint-v30-scene-scale.json` under
  `.tmp/vulkan-gap-closure/scene-scale/` binds 17 terminal passing jobs, 93 strict
  image pairs, archived source/modules and all failed/interrupted attempts.
  The retained v30c clipping failure is the negative control. Shortened-fixture
  cleanup errors, self-test window-size assumptions and a nonstandard benchmark
  display request are retained separately as harness/setup failures. The overall
  goal remains active; multi-view/capture graphs and broader HDR/PBR scope remain.
  The original isolated v31 draft remains under
  `.tmp/vulkan-gap-closure/linear-capture/draft-v31/`; its applied implementation
  and qualification are recorded above. Frame lifetime, completed-scene and
  analytic requirements are in `scene-scale/capture_design_v31.md`.
- v29 extends admitted native linear HDR to bloom and automatic exposure.
  The full post chain is prepared before scene ownership, including readback
  storage and the final uniform reservation; rejected preparation returns
  unused uniform space. Numeric-domain changes invalidate exposure history.
  The v29c staged module passes all five GPU cases, including 32 post fixtures,
  six unchanged-scene/uniform rejections and four domain-reset checks before
  and after restart. Both 38-control native map runs and their four auxiliary
  images pass, including fixed-time domain changes, image/video reload and
  actual 0x/4x. All 33 GL controls pass their independent checks. An off-centre
  diagnostic exposed vertically inverted game-owned render textures; native
  fixed material consumers now compensate for their recorded orientation,
  with resolve/capture/upload provenance preserved.
  Strict paired output remains 30/33 passing: three scaled comparisons retain
  different raster domains (GL's native-sized graph is downsampled before post;
  Vulkan draws at the requested scene extent). The two-byte gate is unchanged.
  The original inversion and first epoch-isolation failure are retained as
  negative evidence. The final 40 composition and 90 ambient captures pass,
  including independent ambient radiance/alpha checks; all twenty composition
  pairs match GL within one byte/channel. All four staged stock SP/MP 0x/4x
  profiles pass. `checkpoint-v29-post.json` under
  `.tmp/vulkan-gap-closure/hdr-post/` binds the results, open parity failures
  and archived module/source. This does not close the
  remaining material, baked-lighting, portal, other post-effect or release work.
- v28 adds a native classic/PBR accumulation boundary: separate FP16 outputs
  through the existing light walk, per-sample classic decoding before resolve,
  then fog and prepared ordered transparency in linear space. Manual output is
  prepared before ownership and ends before authored post/UI. Whole-view
  admission retains the established path for unsupported material, baked,
  portal/feedback and post-effect combinations; these remain completion work.
  The real GPU boundary test passes 24 fixtures at actual 0x/4x and repeats after
  restart. All 40 native composition and 86 ambient/material/recovery captures
  pass at 0x/4x, including independent radiance/opacity and exact restoration
  checks. All twenty 0x OpenGL/native pairs pass with at most one byte per
  channel difference. The scalar control is now 207 against the independent
  expected 206.77, rather than the former 128. All five staged integration GPU
  cases pass. Qualification and hashes are under
  `.tmp/vulkan-gap-closure/hdr-scene/`. A stale-copy smoke and an initial GL
  entity-name setup failure remain retained and excluded from acceptance.
  Twelve additional native captures pass actual scaled/resized FP16 ownership,
  immediate screenshot/restart and exact restoration at both sample counts
  (`recovery-v28c-{0,4}/report.json`).
  All four staged stock SP/MP 0x/4x profiles also pass; SP 4x completes all 60
  views in each temporal interval without weakening the earlier requirement.
  The failed earlier run is retained and no performance claim follows.
  `checkpoint-v28-scene.json` binds this bounded result; the overall goal remains
  active and incomplete.
- The native HDR composite now has an explicit linear filmic/sRGB branch,
  selected only by committed scene ownership. The v27 staged GPU test passes
  640 linear, 64 bloom/grade/debug/alpha, 224 stock tone-map and 40 portal-sky
  fixtures around a full restart, plus 48 exposure fixtures. All run through
  production shaders; linear tests require actual 0x/4x targets. At that v27
  checkpoint native scene ownership remained false. It qualified the output
  prerequisite; the subsequent bounded scene implementation is recorded above.
  All five GPU cases pass; stock SP 0x and MP 0x/4x pass. SP 4x retains a failed
  resized temporal interval under slow presentation; the later v28 repeat above
  passes its unchanged profile. Other-project build/render activity was
  observed during the earlier queue; no thresholds were weakened or processes stopped.
  See [HDR](../../../vulkan-hdr.md) and `hdr-output/hdr-gpu-v27/renderer_validation_report.json`.
- The HDR ownership investigation found a prerequisite ambient-light defect:
  native PBR receivers still accumulated classic ambient lighting, and ambient
  stages bypassed transparent record capacity and ordered replay. The v26
  candidate now evaluates isotropic PBR diffuse and includes every active
  ambient stage in the existing transaction. All 82 lighting captures and
  110 numerical/material/recovery checks pass at 0x/4x; the v25 negative fails.
  The attempted GL mixed-material reference declines modern ambient ownership
  and is retained as invalid paired evidence. All 36 ambient capacity and 88
  resource/recovery captures also pass. Both 68-case direct-light regressions
  pass after correcting their transparent specimen's background isolation;
  the old predicate's failure reproduces byte-identically on v25. All 342
  accepted captures are bound in `pbr-direct-curvature/checkpoint-v26-ambient.json`.
  See [ambient lights](../../../vulkan-pbr-ambient.md).
  The complete mixed classic/PBR HDR output contract remains open.
- Native PBR now keeps its interpolated-normal receiver triangles separate
  from classic face culling, while retaining light-volume rejection and the
  original fallback geometry. The frozen v22 plane test passes all 11 GL/native
  comparisons at 0x; the same predicate rejects the previous binary. Curved
  normal-map silhouettes still fail strict comparison. v23 passes all 44
  transparent resource controls at both 0x/4x. The 4x plane receiver passes,
  while classic ceiling edges still fail the whole-frame gate. See
  [PBR receiver geometry](../../../vulkan-pbr-geometry.md).
- A single full-surface pass now provides native PBR material diagnostics even
  with no direct or environment light. The first candidate exposed another
  ambient-walker admission gate, which v25 corrects. Both 62-control suites
  pass channel values, light independence and data-layout checks at 0x/4x;
  the original seven unlit views pass too. Constant-normal and non-mipmapped
  controls isolate remaining normal differences to mipmapped sampling. The
  opaque sphere's 4x coverage matches independent API-specific sample oracles
  exactly. Strict cross-API image failures and other consumer integration
  remain recorded. See [material diagnostics](../../../vulkan-pbr-diagnostics.md).
- The v25 HDR diagnostic integration run isolated an additional visible PBR gap:
  all 20 GL/native image pairs failed because the native scene retained the stock
  numeric tone curve. Four independent clear-material oracles reproduce the
  different outputs, while all shared-setting fog/blend toggles agree within
  each backend. Those toggles do not prove shared-consumer ownership: native
  scene-target ownership suppresses its preflight even at 100% scale.
  The bounded v28 scene implementation above closes these diagnostic pairs;
  the complete material/post scope remains open. The earlier stock highlight
  repair addressed a separate contract.
- The default light-grid switch now preserves environment lighting when no
  baked grid applies. Frozen v21 passes 60 GL/native captures and 40 exact
  toggles at 0x/4x; v19 fails the four opaque controls. Actual baked PBR diffuse
  composition remains open.

- Native authored-probe atlas residency, shared CPU selection, per-view Vulkan
  storage and environment shader consumption are connected. Original LDR
  probes pass 46 Vulkan and 40 GL controls at each of 0x/4x, plus all 80 paired
  comparisons. Capacity, lifecycle, failure and transformed-receiver checks
  pass with active Vulkan validation and synchronous GL diagnostics. The frozen
  v19 checkpoint retains all reports, runtime/source hashes and earlier failures;
  see [native probes](../../../vulkan-pbr-probes.md). Complete HDR probe consumption,
  later integration candidates and platform qualification remain open.

- The authored-probe source bridge now reads complete immutable cubemaps from
  Vulkan GPU storage, preserving face orientation and sRGB/HDR radiance with
  storage/upload generation checks. Invalid sources return no partial data.
  Its upload checks also handle compressed cube mip padding explicitly.
  This v15 prerequisite did not include atlas residency, selection or visible
  authored-probe consumption; those are connected in the later work above.
  Source-reader implementation and qualification are tracked in
  [Vulkan probe sources](../../../vulkan-probe-sources.md). Final v15 GPU/lifecycle
  controls pass with active validation, and all 54 environment gameplay
  captures at 0x/4x match v12 exactly. The local checkpoint binds reports,
  all 50 runtime files, the source worktree and unchanged companion revision;
  it does not close authored-probe rendering or broader qualification.
- 2026-09-23: the user resumed this goal. The worktree is authoritative: the
  separate PBR task is terminal, and its v63 partial-restart/MSAA fixes and v70
  material work are preserved. Current work resumes here without a competing
  build or GPU process. The previous requested-pause turn stopped the suspended
  harness; this turn advances implementation and verification.
- Vulkan TAA now consumes a dedicated RGBA16F rigid-velocity target, with
  transform history committed alongside color history. Exact ownership requires
  matching frame/view/generation/extent and complete geometry admission; failed
  or unsupported surfaces retain reactive rejection. Eighteen numerical fixtures
  pass before and after full restart, including perspective, invalid clip,
  missing geometry and new-entity controls, with no Vulkan diagnostics
  (`.tmp/vulkan-gap-closure/temporal-rigid/gpu-perspective/`). All four SP/MP
  HDR/MSAA transition cases pass on the first runtime. The stricter telemetry
  run sampled a safe time-discontinuity rejection despite 82 completed rigid
  vector views; its retained failure led to an interval-based freshness check.
  The updated gameplay gate passes all four SP/MP 0x/4x cases, with 39-60 newly
  completed rigid-vector views per measured interval. Moving-scene visual
  comparisons and the full temporal acceptance requirement remain open.
- The resumed HDR investigation confirms the washed-out SP capture had PBR
  disabled. Fixed-view controls reproduce the same Vulkan image with PBR off,
  on and restored; exposure reproduces the highlight loss. A rational shoulder
  replaces the stock .98 knee while preserving lower-half midtones and GL's
  separate linear PBR curve. The final candidate passes 224 production GPU
  tone-map fixtures and 20 portal-sky admission/mask executions around restart,
  plus all four stock SP/MP HDR/MSAA lifecycle cases without tracked warnings.
  A matching preceding portal view now preserves the sky at the depth boundary;
  checking only visible mask materials was insufficient on the stock map.
  The reusable frozen-scene regression passes on Vulkan and GL and rejects the
  retained original washed-out image. This closes the observed highlight/sky
  defect, not full HDR or PBR color parity. Evidence and retained failed
  package-integrity startup: `.tmp/vulkan-gap-closure/hdr-highlight/`.
- The native analytic PBR environment pass now consumes shared filtered
  radiance, diffuse irradiance and BRDF data once per surface, with AO,
  world-space orientation, matching cutout depth and ordered transparency.
  The final local 0x/4x suites pass 27 Vulkan and 26 OpenGL controls each,
  including zero-direct-light transparency, exact restoration and image/video
  lifecycle. Both 26-control cross-backend comparisons pass, with at most one
  byte of color difference at 0x. All four reports preserve runtime integrity.
  This earlier environment checkpoint excluded `r_useLightGrid 1` and did not
  include authored probes. Later work above removes that blanket exclusion
  and qualifies LDR probes; baked PBR diffuse remains open. See
  [native environment lighting](../../../vulkan-pbr-environment.md).
- Environment qualification exposed a general 4x MSAA image-reload defect:
  adopted intrinsic resolve images reverted to their placeholder dimensions
  and formats. Scratch ownership now precedes placeholder generators during
  reload and load-after-purge. The v5 direct-scratch float-readback regression
  passed but gameplay still failed: the public CreateImage path bypassed
  adoption for existing intrinsic images. That path now adopts both new and
  existing images, and the regression uses the public entry point. The v7 GPU
  attachment/HDR/temporal suite passes 3/3 with active validation, and both
  paired environment suites restore the reference exactly after image reload.
- PBR cutout depth and matching emission now use the same alpha-footprint
  coverage as OpenGL. The 4x comparison separates coverage from radiance:
  hard masks agree exactly, filtered masks differ by at most one sample at
  0.876% of pixels, fully covered pixels agree within one byte, and holes are
  black. All 6,393 overlapping color channels pass the coverage-weighted check.
  The gate rejects the retained v6 shader's two-sample discrepancies, so the
  allowance does not hide the original defect. Details and report paths are
  in [native environment lighting](../../../vulkan-pbr-environment.md).
- The same v7 runtime passes all 68 native direct controls at 4x after the
  coverage change, plus all six full-room controls on each backend. Transparent
  ownership retains its independent `(0,112,0)` differential. The full room's
  analytic-environment comparison averages 0.882/255, but localized differences
  remain (p99 19, maximum 161), including the fifth roughness column, cutout and
  transparent specimens. They also occur with environment lighting disabled.
  These descriptive captures do not close complete scene color parity; their
  cause must be isolated independently of the now-qualified environment pass.
- Per-light controls now isolate the largest room differences to the projected
  light's receiver coverage. OpenGL's clustered PBR path samples clamped white
  light images without native per-light triangle membership; its transparent
  loop also omits the light scissor. Point-light mean errors are much smaller.
  The initially suspected emissive clipping is disproved: all five Vulkan
  controls retain the identical 7,814-pixel cyan mask, and the projector capture
  is independent of the preceding light sequence. This does not close projected
  lighting parity or justify changing the native BRDF.
- A dedicated partial-projector fixture reproduces native transparent opacity
  depending on the first light's receiver subset, plus lighting crossing between
  separate entities that instance one model. Native coverage now composites over
  the full mesh once; direct contributions replay their original triangles and
  scissors, keyed by entity and ambient geometry. Environment light adds after
  coverage, so its resource availability cannot suppress direct light or opacity.
  The new 25-control `renderer_vulkan_pbr_transparency.py` proves foreground
  coverage, additive lighting, instance isolation and lifecycle restoration;
  retained old captures fail its corrected foreground predicate. Final current
  binary qualification is recorded in [native environment lighting](../../../vulkan-pbr-environment.md).
  The subsequent record-table and resource-preparation qualifications are
  recorded below; failures outside that native transparent path remain open.
- Native transparency now preflights its entire view's record bound before
  drawing. This fixes a reproduced mixed native/classic owner above 256 records.
  The 18-control capacity suite passes at both 0x and 4x: exact-limit native
  lighting remains active, overflow retains zero native ownership and matches
  the complete classic frame exactly, and light/count/image/video restoration
  is exact. The retained v9 overflow fails that same image predicate by up to
  254 bytes. Evidence: `.tmp/vulkan-gap-closure/pbr-capacity/`. This does not
  close general allocation failure or shadowing-transparent ownership.
- Moving transparent admission out of the fog pass's borrowed interaction state
  also preserves the native owner through fog. Seven independent source-alpha,
  background, native replay and restoration controls pass at both 0x and 4x.
  The earlier 25-case partial-light suite passes at both sample counts, with all
  50 reference images byte-identical to v9. The v10 checkpoint therefore records
  100 passing controls; it does not promote the backend or close the remaining
  environment/probe, shadow, resource-failure and platform requirements.
- Native transparent resource ownership is now prepared before the light loop:
  coverage, direct draws and enabled environment draws retain their pipelines,
  descriptors, uniforms and exact geometry ranges. Failure restores speculative
  allocations and leaves zero native ownership. All 44 resource controls pass
  at both 0x and 4x, requiring exact classic fallback and native recovery across
  early/late failures, image/video reload, no-light and skipped-interaction
  views. Cold failures also prove actual descriptor rollback. Evidence is in
  `.tmp/vulkan-gap-closure/pbr-resources/`; other resource consumers, shadowing
  transparency and platform/promotion requirements remain open.
  The final v12 package passes 242 captures and the GPU render-target/contract
  suite. All 154 existing transparency/capacity/fog/environment TGA references
  remain byte-identical. `checkpoint-v12.json` pins the reports, source tree,
  all 50 runtime files and unchanged companion revision.
- An unrelated baseline contract failure remains in
  `tools/tests/game_type_module_selection.py`: its two-phase lifecycle check
  requires game API 46, while the unchanged companion `src/game/Game.h` declares
  API 48. Both values were verified at their respective HEAD revisions; this
  renderer work does not change either file. The retained failure is
  `.tmp/vulkan-gap-closure/pbr-environment/game-module-contract-v6.log`.
- The build wrapper also continues to report "GameLibs staging inputs changed"
  with the companion worktree clean, and Meson reports that the SDL3 wrap file
  changed while its subproject revision may be out of date. These separate
  build-maintenance warnings remain unresolved; renderer compilation succeeds.
- Three superseded HDR runtime copies were verified inside the project with
  no reparse links. Automatic approval review rejected their recursive cleanup
  with only "blocked by policy"; they remain under `.tmp/stock-runtime/`.
  The qualified HDR reports and v4 runtime are retained independently.

- The user paused the original Vulkan task and authorized takeover after the
  scoped GL PBR work. The [PBR audit](2026-09-20-pbr-rendering-audit.md) records
  that earlier takeover. Its task is now terminal; build/staging/GPU execution
  belongs here again. Existing recovery and attachment changes are preserved.
- The v61-v63 lifecycle fixes submit an open screenshot frame before swapchain
  resize, maintain real multiplayer MSAA color/depth targets through HDR/TAA
  toggles, and reject stale depth resolves. Stock SP/MP HDR transitions and GPU
  attachment/exposure fixtures pass locally; HDR visual parity remains open.
- v68 passes 55 native PBR controls each at 0x and 4x MSAA: scalar/packed/separate
  data, XYZ/RG/AGB normals, matching cutouts and emission, exact fallback,
  restarts and point/projected shadows. Raw FP16 tests prove finite emission
  after texture modulation and preserve faint channels. Its full-map gate
  remains 2/3 because native source-alpha ownership is missing. Environment and
  probe consumers, complete scene linearization, specular antialiasing and
  arbitrary additive overflow still require work. These results do not close
  the broader renderer or promotion requirements above.
- v69 adds final-normal variance filtering to all native direct PBR variants.
  The expanded suite passes 68 controls each at 0x/4x, including exact filter
  restoration and constant-normal/roughness-ceiling invariance. Attachment/HDR
  GPU checks pass 2/2, while full-map source-alpha ownership remains a retained
  failure. Quantified temporal stability and the broader open requirements are
  unchanged; source-alpha and environment lighting need a native surface pass
  with complete resource admission before it replaces classic ownership.
- v70 closes native source-alpha ownership. A translucent surface never reaches
  the depth fill, so its lighting and its authored composite belong to two
  different passes; the light pass now records the admitted draws instead of
  adding them and the material walk replays them in the authored stage's sort
  position, the first through the alpha and the rest adding through it. The
  full-map check passes with the ownership/emission difference measured at
  exactly (0, 112, 0), the same oracle the OpenGL reference satisfies, and the
  two backends' ownership captures agree to within one byte
  ((118.735, 213.918, 108.347) native against (118.306, 213.367, 108.388) GL).
  A shadowing light over a translucent receiver declines the whole view rather
  than owning a surface for one light and returning it for the next: stencil
  coverage is reset with its light and cannot be replayed. Environment/probe
  consumers, complete scene colour composition and the performance failures
  below remain open.
- Stock `game/storage1` timing exposes CPU/presentation stalls in both v68 and
  v69. GPU medians are 4.985/4.991 ms, but CPU P99 is 424.643/413.892 ms against
  the 28 ms budget. Disabling periodic renderer diagnostics still produces a
  415 ms presentation P99. The hidden-window runs do not establish the cause;
  retain the failures and isolate native presentation/CPU phases before any
  performance promotion. See `.tmp/pbr-audit/qualification-v69.json`.

- v70 measured the OpenGL/Vulkan colour gap instead of assuming it. On the same
  laboratory cameras, the lit frame differs by mean 8.149/255 with 17.69% of
  channels changed; with environment lighting disabled on both backends it
  falls to 1.002 and 4.33%, against 0.920 for the classic path with PBR off
  entirely. Native direct lighting is therefore already at classic-level
  agreement, and about seven eighths of the visible difference is the missing
  environment consumer -- which is what the survey below should be sized
  against.
- v70 surveyed what native environment/probe lighting actually needs, so the
  next increment starts from facts rather than a guess:
  - `ModernSpecularProbeAtlas.cpp` is **not** in the Vulkan module's source set
    (`tools/build/meson_sources.py --emit renderer_vk`), so there is no atlas
    to sample from.
  - `R_ModernLightImageAtlas_Acquire` is stubbed in `vk_Backend.cpp` and always
    returns `MODERN_LIGHT_ATLAS_REJECT_UNAVAILABLE`, which is why the shared
    clustered descriptors report `atlasReady = false` on this backend.
  - `ModernClusteredLighting.cpp` **is** compiled into the module but has no
    Vulkan consumer; its light descriptors already carry world origin, colour,
    falloff plane, projection planes and atlas rectangles.
  - `PBREnvironment.h` is header-only and backend-neutral. Its analytic
    environment needs no atlas at all, so the cheapest honest first step is a
    native analytic IBL consumer, with authored probes following once an atlas
    exists on this backend.
  - A route through the space constraint exists and is worth recording. The
    analytic environment needs a world-space normal and reflection, so the
    shader needs the object-to-world rotation per draw. The 256-byte uniform
    slice is full (16 vec4) and so is the 128-byte push block -- but `pc.b`
    carries the tangent-space ambient light direction, which a non-ambient PBR
    draw never reads, and a rotation packs into those four floats as a
    quaternion. The parallax enable in `pc.c.z` is likewise forced off for
    native PBR and can carry the IBL intensity once its branch is guarded by
    the PBR mode bit.
  - The real cost is not the data, it is the draw. Environment light is owed
    once per surface, not once per light, so it needs its own ambient-walk
    draw the way emission has one -- except emission substitutes an authored
    glow stage that a plain PBR material does not have. That pass also has to
    agree with the existing light-grid indirect pass on which one supplies
    diffuse (OpenGL's rule: baked replaces environment diffuse and keeps
    environment specular), rebuild the bump/diffuse/specular texture matrices
    the interaction path gets from `VK_SetDrawInteraction`, and feed the
    transparency composite as well. That is a feature with its own admission,
    ordering and controls, not a gap-fill.
  - The native interaction pipelines have six fixed 2D descriptor slots and PBR
    already uses four (normal, albedo, data, metallic). An environment pass can
    reuse the light-projection/falloff slots. The shared probe-atlas layout
    already reserves tiles for diffuse irradiance and the BRDF lookup table;
    those do not require additional independent textures.
- v70 re-measured the retained CPU/presentation stalls and **could not
  reproduce them**. Five runs of `sp-storage1` on the current binary pass the
  budget: 240 fps without validation (p50 7 ms, p99 9, max 17), 240 fps with
  validation (p50 11, p99 14, max 14), and the exact v68/v69 configuration --
  125 fps, hidden window, `r_vkValidation 1` -- three times (p50 12, p99 18,
  max 22; then two traced repeats with **zero** frames above 100 ms, CPU max
  15.5/16.4 ms and GPU max 5.2 ms).
  The retained v68/v69 traces attribute those failures to 2-6 isolated frames
  in 256, spent in the present/swap call or unattributed to any render phase,
  while the GPU stayed at 1.6-12 ms -- the process was waiting, not rendering.
  What the machine was doing then cannot be recovered, and this box runs
  parallel sessions, so contention is the most plausible explanation; it is a
  hypothesis, not a finding. What is established: the renderer measures inside
  the 20/28 ms budget in the same configuration on a quiet machine, and the
  failing reports stay retained rather than being reinterpreted.
  Measure performance with validation off: it costs about 57% of steady-state
  CPU frame time here (7 ms to 11-12 ms p50) and is a debugging instrument,
  not a shipped path. Reports: `.tmp/pbr-audit/v70-perf-novalidation`,
  `v70-perf-validation`, `v70-perf-v69match`, `v70-perf-trace1`, `v70-perf-trace2`.
- 2026-09-20: audited the current tree. Push/PR workflows run Vulkan source
  contracts but omit the existing runtime cases. The default matrix also
  excludes Linux Vulkan regardless of a staged module. Explicit `--cases`
  already bypasses that filter; the new CI selection must remain explicit.
- The Vulkan instance can retry without validation when layer creation fails;
  the runtime case must require a positive layer-and-debug-messenger marker so
  an unvalidated run cannot count as validation-clean.
- Existing worktree edits to gameplay, menus, translations, and shared release
  documents predate this task and must be preserved.
- Linux x64/ARM64 push and ARM64 pull-request workflows now select the Vulkan
  startup/render-target and two fallback cases with lavapipe and validation
  layers. Explicitly required missing modules and empty suites are errors.
  The first hosted results are still required; no hardware coverage is inferred.
- Cubemap attachment views select one face without replacing the full sampled
  cube view. Color and depth captures follow the selected face, post effects
  restore it, and image retirement includes every face view. Depth-only targets
  now support binding, draws, resize, capture and depth resolve. Matching cube
  resolves copy every layer; incompatible layer counts are rejected. Retirement
  queue overflow now remains behind its frame fence instead of freeing resources
  still referenced by the unsubmitted command buffer. The GPU test exceeds the
  fixed queue capacity through repeated cubemap resizing in one frame.
- Local Windows/NVIDIA startup, missing-module fallback and empty-driver
  fallback passed from an isolated copy of the staged package. The GPU test
  checks every captured pixel and draws into depth-only targets, including
  complete-layer resolves and 4x MSAA depth resolves. The expanded 66-capture
  test and retirement overflow stress pass with zero Vulkan validation warnings.
  The three-case report is
  `.tmp/vulkan-gap-closure/retirement-startup/renderer_validation_report.md`;
  the module in `builddir`, `.install` and the isolated package has the same
  SHA-256. Final gameplay evidence is retained in the adjacent
  `retirement-gameplay` directory.
- The runtime matrix previously ignored `--runtime-dir` when choosing its
  default executable, so a missing-module drill could hide the wrong package's
  DLL. The selection now follows the runtime directory, and `fs_devpath` follows
  the isolated evidence/save path. Behavioral regression checks cover both.
- Stock SP `game/airdefense1` and MP `mp/q4dm1` gameplay passed with validation
  enabled and engine screenshots. These hidden-window, short diagnostics do not
  satisfy performance, visual-parity, long-soak or hardware-promotion gates.
  The pacing-only MP harness needs `--set-cvar r_mode=-1` after its game-module
  reload; otherwise the archived machine-spec preset changes the mode selector.

- Multiple color attachments now share one admission check for binding and
  resolves. The limit matches OpenGL's five buffers, bounded by the physical
  device. Ordered formats participate in every pipeline cache key; blend/mask
  state, load barriers, clears and resolves cover all attachments. Invalid
  layouts and cross-index resolve aliases fail before recording partial work.
  Adding an attachment to a current target refreshes its rendering scope.
- The mandatory MRT GPU exercise passes two-buffer mixed-format targets in both
  format orders, six cube faces, and two- and five-buffer 4x MSAA targets at two
  sizes. Exact raw readbacks check unclamped half-float values, per-buffer
  output, blend masks, clears, depth and resumed-scope contents. Invalid counts,
  dimensions, sample combinations and aliases preserve the active target.
  Rectangular cube-target resizes are rejected before image allocation.
- MRT build/staging, shader-header regeneration and all three startup/fallback
  cases passed locally with active validation and no Vulkan validation warnings.
  Evidence is in `.tmp/vulkan-gap-closure/mrt-final-startup/`; the tested module
  SHA-256 is `1447ce0eb61d3c9ea7d72a6aa8330a999e03fb93b4f9d0d8d4a123be8012b89e`.
  An earlier negative fixture accidentally allocated a rectangular cubemap;
  the gate rejected its VUID diagnostics, and the corrected run is the accepted
  evidence. This render-target work does not supply the advanced feature
  consumers or close their separate HDR/PBR/temporal qualification requirements.
- The same MRT module passes stock SP `game/airdefense1` and MP `mp/q4dm1`
  listen/client gameplay in `.tmp/vulkan-gap-closure/mrt-gameplay/`, with the
  runtime's 156 hashed files unchanged. Engine screenshots were inspected.
  These remain short windowed diagnostics, not performance or visual-parity
  promotion evidence.

- Recoverable startup preparation now creates the real Vulkan window/device,
  swapchain and mandatory executor resources before UI/session/game startup.
  Failure returns to engine code for ordinary owner teardown before callbacks
  and the failed module unload. A single OpenGL retry then reruns initialization.
  The requested Vulkan preference and the original log survive. Renderer ABI 13
  carries this export; the engine and both renderer modules must match.
- All seven startup/fallback cases pass in `recovery-final-startup`; all four
  late-failure cases pass again in `recovery-repeat-startup`. Both reports are
  under `.tmp/vulkan-gap-closure/`, with active validation required wherever
  instance creation was reached and no Vulkan diagnostics. The first iterations
  exposed log truncation and a breadcrumb printed while the filesystem was down;
  both are fixed, and the retained engine log must prove the complete order.
- The deepest resource failure also recovers into stock SP `game/airdefense1`
  and an auto-joined MP `mp/q4dm1` listen game, with clean shutdown and inspected
  engine screenshots (`recovery-stock-gameplay/report.json`). Ordinary Vulkan
  SP and MP listen/client gameplay passes separately in
  `recovery-normal-vulkan-gameplay`. The same 156-file runtime remains unchanged
  throughout. These are short diagnostic runs, not soak/performance promotion.
- The tested engine, GL module and Vulkan module initially matched builddir,
  staging and the isolated package. `recovery-module-sha256.json` records all
  three binaries; Vulkan SHA-256 is
  `c76c281fe6779c3cc4621b437821a60324934ef293eff0a3f9eb943121eec5e7`.
  The complete checkpoint is `.tmp/vulkan-gap-closure/recovery-verification.md`.
- PBR work is coordinated with the separate PBR audit task: it owns shared/GL
  material and BRDF analysis, probe math, the procedural proof fixture and the
  coordinated Vulkan interaction-shader math update. Build/staging and GPU use
  were released after these recovery tests. That work does not reduce the PBR,
  probe, HDR or other completion requirements above.

## Separate issues found during validation

The authorized takeover closes the immediate screenshot/partial-restart
swapchain lifetime crash and hidden-window extent regression, implements real
MSAA in backend-owned MP scenes, and keeps spatial depth consumers behind a
successful current-generation resolve. v63 passes stock SP/MP at 0x/4x plus
the GPU attachment/MRT suite and 48 HDR fixture executions around full restart,
with active validation and unchanged runtime hashes. Reports:
`.tmp/pbr-audit/vulkan-v63-hdr-gameplay/report.json` and
`.tmp/pbr-audit/vulkan-v63-gpu/renderer_validation_report.json`.
The inspected SP sky/highlights remain overexposed with automatic exposure;
controlled HDR visual parity, native PBR parity and the broader gates stay open.

On 2026-09-20 the user paused this task and authorized the PBR task to take over after its
OpenGL PBR phase. The v60 PBR laboratory passes 74 controls and 15 renderer
self-test markers; retail SP/MP captures are retained, with an MP server CPU
budget miss still open. Vulkan work now continues in the PBR task, beginning
with the known HDR partial-restart crash and native PBR parity. This task
remained inactive during that takeover to avoid competing edits, builds or GPU runs. See the
[PBR audit](2026-09-20-pbr-rendering-audit.md) for current ownership and evidence.

- The earlier game ABI pin and renderer-header mismatches are reconciled in
  the shared tree: game ABI 48 and renderer ABI 14 now agree with their test
  contracts. The takeover recheck passes `level_load_cache.py`,
  `renderer_temporal_presentation.py` and `renderer_gpu_frame_timing.py`
  (`.tmp/pbr-audit/*static-v61.log`). This resolves those specific static
  blockers, without implying that the entire renderer suite has passed.
  A later source recheck still finds a separate ABI-46 assertion in
  `tools/tests/game_type_module_selection.py`; the companion declares ABI 48.
  That stale assertion remains unrelated to the renderer image qualification.

- The stock MP smoke also retains missing `q4dm1` AAS-size and non-precached
  declaration warnings. They are separate from Vulkan validation diagnostics
  and do not establish bot/navigation or asset-precache qualification.
