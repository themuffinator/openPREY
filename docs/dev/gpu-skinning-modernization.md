# Shared Renderer Contracts and GPU Animation

This document is the authoritative implementation and qualification boundary
for Milestone C of the [idTech 5-level modernization roadmap](archive/2026-10-18/idtech5-modernization-roadmap.md).
The capability is deliberately reversible: `r_gpuSkinning 0` retains the
established CPU renderer path, and every unsupported or invalid surface falls
back as a whole rather than mixing partially transformed vertex data.

## Delivered contract

The renderer now has a small backend-neutral contract layer for the semantic
data that OpenGL and Vulkan must agree on:

- ordered material/pass records retain stage order, repeated texture
  semantics, condition and color registers, texture matrices, texgen and
  vertex-color policy, blend/depth/cull/color-mask state, alpha test, polygon
  offset, and program-family identity;
- a canonical OpenGL clip convention converts explicitly to Vulkan's zero-to-one
  depth interval and negative-height viewport convention;
- semantic vertex layouts describe the 64-byte `idDrawVert` ABI and a separate
  full-precision skin binding without embedding GL or Vulkan formats;
- typed, generational buffer handles and checked slices reject stale, expired,
  wrong-kind, empty, or overflowing ranges before a backend sees a native
  object.

These records are intentionally narrower than complete modern-frame ownership.
They establish the shared vocabulary required by both current backends;
Milestone D remains responsible for making complete classic material domains
consume the pass representation.

## Exact four-weight corridor

GPU animation uses a dedicated 32-byte record per vertex:

| Field | Format | Purpose |
|---|---:|---|
| joint indices | `uint32[4]` | Full joint indices; no 8-bit joint ceiling |
| joint weights | `float32[4]` | Exact authored weights, including signed MD5R values |

Joint palettes use three row-major `vec4` rows (12 floats) per joint, matching
`idJointMat`: translation is stored in elements 3, 7, and 11. The format does
not reuse `idDrawVert::color` or `color2`, so authored diffuse vertex colors
survive unchanged.

Classic MD5 meshes are admitted only when every final output vertex, including
mirrored vertices, is exactly representable with at most four meaningful
influences. The implementation does not truncate or renormalize a residual
tail. Packed MD5R data preserves its signed implicit fourth-weight rule and is
normalized into the same sidecar contract. Rigid and one- through four-weight
vertices share the same validation path.

Invalid counts, non-finite data, out-of-range joints, unsupported skin-scale or
topology variants, allocation exhaustion, stale generations, unavailable
compute support, and backend submission failures all select the complete CPU
path. The fallback reason remains visible in diagnostics and is never treated
as successful GPU admission.

The per-vertex rules are proven once, when the model packs its immutable
sidecar. The model records the highest joint any influence uses, and the
attach rejects a palette that cannot cover it. Every later use of the surface
(admission, scene packets, stencil-volume classification, backend dispatch)
then checks only the palette header, generation, and that bound, instead of
walking every vertex several times per frame. A sidecar without a recorded
bound keeps the full per-vertex validation.

## Ownership and CPU invariants

Immutable bind-pose and four-weight sidecars are owned by the source render
mesh. A dynamic triangle surface only references those arrays. Its current
joint palette is copied into triangle-owned storage with separate logical count
and allocation capacity, then retired through the established deferred
triangle lifetime.

Reference surfaces may borrow the immutable contract but never its allocation
marker. Topology-changing copies, reversed back sides, decals, overlays,
deforms, cache serialization, and frame-arena copies clear or explicitly
reference the metadata so they cannot retain a stale pointer or double-free a
palette.

GPU admission does not change gameplay geometry ownership:

- CPU positions and bounds remain current for collision, traces, hit
  detection, decals, overlays, and software/debug consumers;
- compatible MD5 surfaces can avoid CPU normal/tangent skinning while the GPU
  produces the complete visible `idDrawVert` stream;
- stencil shadow volumes remain explicitly CPU generated and bind through the
  existing shadow-cache path;
- disabling the feature restores the previous full CPU deformation behavior.

No network, save, demo, material, model, or stock-asset format changes are
introduced. The mirrored `srfTriangles_t` ABI in the companion game-library
repository is updated in lockstep because game code allocates that structure
directly.

## Backend execution

Both backends consume the same bind-pose, skin, and palette contract and emit
an ordinary 64-byte `idDrawVert` stream. Existing visible passes therefore do
not need skin-specific material permutations.

### OpenGL

On compute/SSBO-capable contexts, bounded frame-ring slices hold source
vertices, skin records, palettes, and output. A 64-thread compute dispatch
copies non-deformed fields verbatim and transforms position, normal, and both
tangents. A shader-storage-to-vertex barrier publishes the result before the
existing ambient cache is bound. Any missing capability or allocation returns
to CPU cache creation.

### Vulkan

The per-frame vertex ring also carries storage-buffer usage. Eligible surfaces
are deformed in a bounded compute prepass before the view's graphics state is
established, and the ordinary geometry memo points later depth, ambient,
interaction, subview, view-model, and shadow-map draws at the computed slice.
Host-to-compute and compute-to-vertex barriers make the ownership transition
explicit. The separate stencil-shadow binding never consumes the computed
stream.

Because the front end cannot record compute, Vulkan accepts an admitted
surface as *deferred* instead of returning a prepared stream. The CPU ambient
cache it still allocates (the draw memo key and the fallback) then carries the
current positions only: the front end skips the normal/tangent derivation that
the compute pass replaces. Before the view's first draw, every deferred
surface reachable from the view's surface list or a light's interaction chains
that the dispatch did not cover (disabled, unavailable, out of ring or memo
space, refused validation) is completed on the CPU, its cache rewritten, and
any ring copy of the incomplete stream retired. Shadow-map casters read only
positions, which a deferred stream already holds. Before this, a Vulkan
GPU-skinned surface paid for both the compute pass and the full CPU tangent
derivation, so enabling the feature could cost CPU time instead of saving it.

A CPU `deform expand` offsets along vertex normals that a GPU-skinned pose does
not carry on the CPU, so it derives the basis into its own copy over the source
topology (seams and mirrored vertices still share their normals) whenever the
source tangents were not calculated.

## Controls and diagnostics

`r_gpuSkinning` is archived, experimental, and defaults to `0`. It is safe to
toggle for an A/B capture; a renderer restart is not required. `gfxInfo`
reports backend availability and the shared counters distinguish eligible,
admitted, dispatched, and CPU-fallback work, including vertices, joints,
palette bytes, and fallback reasons. The Vulkan line adds `deferred` (surfaces
accepted without a CPU basis) and `cpuRepairs` (deferred surfaces the dispatch
did not cover and the CPU completed).

The dependency-light `RendererContractsTest` validates ordered/repeated passes,
clip conversion, viewport orientation, semantic layouts, and typed buffer
slices. `rendererContractsSelfTest` and `rendererGpuSkinningSelfTest` exercise
the same contracts through either renderer module. The validation matrix must
observe the same versioned semantic markers for OpenGL and Vulkan; a skipped
GPU-animation contract test is not a pass.

## Acceptance procedure

Use a fresh bordered-window 1280x720 runtime and engine-written screenshots.
Never compare OpenGL directly with Vulkan pixel-for-pixel: capture a CPU
reference for each backend, then compare its GPU run against that reference
from a pose frozen at launch with `g_stopTime 1`.

Required gameplay coverage is:

- SP `game/airdefense2` and `game/mcc_landing`, including animated characters,
  view models, interactions, decals, subviews, and mapped shadows;
- pure, auto-joined MP `mp/q4dm1` with the stock package contract;
- one explicit stencil-shadow run proving the CPU fallback counter and image;
- an animation-heavy `evaluateMPPerformance` workload, repeated at least three
  times per backend with GPU skinning off and on.

The paired performance report must prove that GPU work was actually admitted,
retain the per-run source/package/GPU/driver identity, and report whole-frame
CPU percentiles together with the skinning-specific CPU time and fallback
inventory. A change in collision or hit results, an unclassified fallback, a
missing screenshot, or a performance result without admitted vertices fails
the gate.

Capture each backend as its own CPU/GPU pair, changing only the launch-time
feature switch. For example:

```powershell
python tools/tests/renderer_gameplay_benchmark.py --cases sp-airdefense2,shadow-character-airdefense2,sp-mcc-landing --render-api gl --shadow-presets stencil --set-launch-cvar g_stopTime=1 --set-launch-cvar r_gpuSkinning=0 --output-dir .tmp/renderer-gameplay/gpu-skinning-cpu-gl
python tools/tests/renderer_gameplay_benchmark.py --cases sp-airdefense2,shadow-character-airdefense2,sp-mcc-landing --render-api gl --shadow-presets stencil --set-launch-cvar g_stopTime=1 --set-launch-cvar r_gpuSkinning=1 --output-dir .tmp/renderer-gameplay/gpu-skinning-gpu-gl
python tools/validation/gpu_skinning_evidence.py .tmp/renderer-gameplay/gpu-skinning-cpu-gl/renderer_gameplay_benchmark_report.json .tmp/renderer-gameplay/gpu-skinning-gpu-gl/renderer_gameplay_benchmark_report.json --minimum-cpu-p95-improvement 1.0 --output .tmp/renderer-gameplay/gpu-skinning-gl-evidence.json
```

Repeat the same commands with `--render-api vk` and distinct output paths. The
strict pair pins `--shadow-presets stencil` so its required CPU stencil-volume
fallback is deterministic; run a separate backend-local pair with
`--shadow-presets mapped` for the shadow-map caster corridor rather than
claiming that the stencil pair covers it.
Capture `mp-q4dm1-listen` as its own pure, auto-joined CPU/GPU campaign without
`g_stopTime`; retain its hashes, logs, and human engine-screenshot review as
separate promotion evidence rather than feeding live multiplayer frames to the
strict frozen-image pair verifier. The verifier reads and hashes the retained
engine logs and engine-written TGA
screenshots, requires a clean identical runtime/source identity, verifies the
launch-time `r_gpuSkinning=0/1` pairing, rejects missing or unnamed fallbacks,
requires admitted GPU work and an observed CPU stencil-volume fallback, and
defaults to at least a one-percent reduction in CPU P95 for every paired role.

## Evidence status

The 2026-08-20 Windows x64 implementation gate passed the full MSVC build for
the client, dedicated server, OpenGL/Vulkan renderer modules, and SP/MP game
modules; all six Meson native tests; the GPU-skinning, MD5R/Vulkan compatibility,
shader-header-pin, evidence-verifier, and validation-wiring checks; the windowed
OpenGL foundation self-test case; and the staged windowed Vulkan startup case
with the identical renderer-contract and GPU-skinning success markers. A
windowed `game/airdefense2` SP gameplay smoke run also passed the renderer
budgets and wrote engine-target screenshots on both backends. Its final
diagnostics recorded 942 admitted/prepared surfaces on OpenGL and 1,662 on
Vulkan, with compute available and no validation, allocation, stale-palette,
or backend-unavailable fallback.

Those runs were integration evidence from a dirty source pair, not a release
qualification. Stock-package screenshot, pure-MP,
animation-heavy performance, and cross-platform/driver evidence remain
release-promotion evidence until they have been captured from clean committed
source and a freshly staged final package. That separation does not weaken the
runtime rollback: the feature remains opt-in and fail-closed while promotion
evidence is accumulated.

### 2026-10-06 promotion attempt: not beneficial for stock content

The strict pairs above were run on Windows x64 from a clean commit with the
deferred Vulkan basis and prevalidated sidecars (OpenGL and Vulkan, stencil
preset, `g_stopTime 1`, `sp-airdefense2`, `shadow-character-airdefense2`,
`sp-mcc-landing`). Vulkan accepted 3,924 surfaces as deferred and dispatched all
3,924, so no CPU repair was needed, with the validation layer clean.

The decisive measurement is the engine's own skinning counter, not the
whole-frame percentile. CPU skinning with tangents costs about 10-15 ns per
vertex and the position-only path GPU admission keeps costs about 6-11 ns, and
these maps skin roughly 1,400-1,500 vertices per frame. CPU skinning is therefore
about 15 microseconds of a 1-2 ms frame; removing all of it is below what a
CPU P95 comparison can resolve. The pairs could not show the required 1%
improvement on either backend (they reported regressions of 6-98%), but those
whole-frame numbers were dominated by peer builds saturating the shared
machine and by recurring ~0.5 s frames that also appeared with GPU skinning
off, so they are not evidence of a regression either. The paired verifier had
also stopped accepting the benchmark's report schema (3 vs the current 5); it
now follows the benchmark and a static contract fails if the two drift again.
The pinned cases also never produced the classified stencil-volume fallback
the verifier requires.

`r_gpuSkinning` therefore stays opt-in. For stock Quake 4 content the work it
removes is too small to matter, while it adds a compute pass and, on Vulkan, a
split of the view's rendering scope. It remains useful for animation-heavy
community content, where two costs still stand in the way of a clear win:

- OpenGL dispatches each surface separately, each followed by its own
  compute-to-vertex barrier;
- both backends re-upload each surface's immutable bind pose and four-weight
  stream (96 bytes per vertex) with every dispatch instead of keeping them in a
  persistent per-mesh device buffer.

Batched OpenGL dispatches with one barrier per view and persistent per-mesh
source buffers are the prerequisites for any future promotion attempt, which
should use an animation-heavy multiplayer workload rather than these maps.
