# Renderer Perf Pass 3: SSE2 SIMD, Backend Call Dedup, Front-End Sort (2026-06-10)

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

## Purpose

Deep-analysis follow-up to [2026-06-10-renderer-rework-2.md](2026-06-10-renderer-rework-2.md). That pass removed repeated-state front-end re-skinning and hardened the modern side path; this pass attacks the next tier of measured cost in the visible ARB2 path: scalar-only math in every per-tic geometry routine, redundant GL calls in the per-draw submission loop, and avoidable front-end per-view work.

## Baseline Findings (2026-06-10 deep analysis)

Measured baseline (builddir-perf debugoptimized, SP `game/storage1`, `com_maxfps 240`, vsync 0, 900-frame request, in-engine renderer benchmark): **frame avg=9 ms p50=9 p95=13 p99=17 max=20; cpu fe=10 submit=4 backend=4 present=1**.

1. **The engine has no SIMD implementations at all.** `idSIMD::InitProcessor` was hard-coded to `forceGeneric = true` ("jmarshall - temp disable SIMD"), and the tree only contains `Simd_generic.cpp` — the original MMX/SSE/SSE2 files (32-bit inline assembly, which MSVC x64 cannot compile) were removed upstream. Every MD5 skin (`TransformVertsNew`/`TransformVertsAndTangents[Fast]`), every shadow-volume facing pass (`Dot(idVec3, idPlane*)`), every bounds derivation (`MinMax(idDrawVert)`), every shadow cache projection, and all joint-matrix composition ran scalar C on x64.
2. **ARB2 per-draw GL call redundancy.** Per interaction draw, `RB_ARB2_DrawInteraction` re-sent up to 17 `glProgramEnvParameter4fvARB` values even though the light projection planes, light/view origins, and stage matrices are per-(light, entity) or per-stage constants (for world geometry under one light they are identical across every surface). The per-surface loop in `RB_ARB2_CreateDrawInteractions` re-issued 9 attrib-array enable/disable calls and re-bound the already-bound interaction vertex program for every surface. `GL_SelectTextureNoClient` never early-outed. `idVertexCache::Position` issued `glBindBufferARB` unconditionally on every call — several times per draw, re-binding the same VBO for every pass of multi-stage surfaces (and all frame-temp geometry shares one VBO per frame, so consecutive dynamic surfaces re-bound the same buffer too).
3. **Front-end per-view costs.** `R_SortDrawSurfs` used CRT `qsort` (indirect comparator call per comparison) at presentation rate. `idInteraction::AddActiveInteraction` evaluated the full shadow-map caster policy (string compare against `textures/common_lights/`, spectrum match, LOD admission) per surface per view even with shadow maps off — the default configuration.
4. Confirmed non-issues: light grid has no per-frame cost; GPU timer queries are correctly gated by `r_rendererMetrics`; the modern side pipeline is gated tight when off; `idImage::Bind` already filters redundant texture binds per unit.

## Implemented

### A. SSE2 SIMD processor (`src/idlib/math/Simd_SSE2.{h,cpp}`)

- New intrinsics-based `idSIMD_SSE2 : idSIMD_Generic`, MSVC-x64 safe, guarded so non-x86 targets compile the tree unchanged. Specialized routines: `Dot` (idVec3×idPlane[], idVec3×idDrawVert[], idPlane×idVec3[], idPlane×idDrawVert[]), `MinMax` (idDrawVert, plain and indexed), `TransformVerts`, `TransformVertsNew`, `TransformVertsAndTangents`, `TransformVertsAndTangentsFast`, `CreateShadowCache`, `CreateVertexProgramShadowCache`, `ConvertJointQuatsToJointMats`, `TransformJoints`, `MultiplyJoints`. Everything else falls through to generic.
- Float-order discipline: sum orders mirror the generic versions (bit-identical for joint composition and quat conversion); the only relaxation is exact `min/max` bounds instead of the generic midpoint-trick accumulation (≤1 ulp difference, conservative use only). `idDrawVert` stores use 8+4-byte partial stores so interleaved color bytes are never touched; 16-byte loads are only used where they provably stay inside the source allocation (the 12-byte-stride `idVec3` variant always leaves the final element to the scalar tail).
- `idSIMD::InitProcessor` now honors `com_forceGenericSIMD` again: x86-64 selects SSE2 unconditionally (architecturally guaranteed), 32-bit x86 checks `CPUID_SSE2`, other architectures keep generic. `testSIMD` was also fixed to not crash (and not delete the generic processor) when no specialized processor exists.
- Game modules pick the same code up automatically through `game_idlib_library` on their next rebuild; no engine/game contract change.

### B. Legacy-backend redundant-call filtering (gated by `r_useRedundantStateFiltering`, default `1`)

- **Env-param value cache** (`draw_arb2.cpp`): `RB_ARB2_SetVertexEnvParm`/`RB_ARB2_SetFragmentEnvParm` skip `glProgramEnvParameter4fvARB` when the 16-byte payload matches what that register already holds. Cache covers the classic interaction registers (< 32); packed MD5R registers (75+) pass through. Invalidated at every `RB_ARB2_CreateDrawInteractions` entry and whenever a packed MD5R surface is encountered (the packed path uploads joint palettes into the low registers and binds its own program), because other passes write those registers without the helpers.
- **Per-surface loop hoisting** (`RB_ARB2_CreateDrawInteractions`): the 9 attrib-array enable/disables and the interaction vertex-program re-bind are now issued only for the first classic surface and after any packed MD5R surface (including partially failed packed bind attempts, which can leave the packed program bound), instead of for every surface.
- **`GL_SelectTextureNoClient`** early-outs when the unit is already current (server-side active texture only; the pre-existing `GL_SelectTexture` client/server mixing semantics are unchanged).
- **Buffer-bind shadowing** (`idVertexCache::BindArrayBuffer/BindIndexBuffer/InvalidateBufferBindings`): all legacy-path `GL_ARRAY_BUFFER`/`GL_ELEMENT_ARRAY_BUFFER` binds (`VertexCache.cpp`, `RendererUpload.cpp`, the MD5R client-array unbinds in `draw_arb2.cpp`) go through a shadow that drops redundant rebinds. Invalidations: `RB_SetDefaultGLState`, `R_GLStateCache_LegacyHandoffReset` (modern pipeline may bind behind the filter), buffer deletion (GL resets bindings of deleted buffers to 0), `idVertexCache::Init`, upload-manager shutdown.

### C. Front-end

- **`R_SortDrawSurfs`**: stable LSD radix sort on the IEEE-754 bit pattern of the float sort key (insertion sort below 65 surfaces), with constant-byte passes skipped. Replaces CRT `qsort`. Scratch comes from `R_FrameAlloc`.
- **`AddActiveInteraction`**: the entire shadow-map caster policy block (including the `textures/common_lights/` `Icmpn`, spectrum match, and LOD admission per surface) is skipped when `r_useShadowMap` is 0 (the default). Shadow-map-enabled configurations evaluate exactly what they did before.

## Non-Goals / Deferred

- `r_useIndexBuffers` default flip (index data currently draws from client memory): needs its own A/B benchmark first; archived cvar, users may have overrides.
- Interaction scissor / light-scissor caching across presentation frames, and shadow-volume caching keyed on (model snapshot, model-space light origin): real wins but need a careful invalidation design; candidates for the next pass.
- `DeriveTangents`/`DeriveTriPlanes` SSE2 ports: skipped to keep float-behavior risk near zero this pass.
- GLStateCache integration into the ARB2 hot path: superseded by the targeted filters above for now.

## CVar Plan (as landed)

- `r_useRedundantStateFiltering` (default `1`): all of section B. `0` restores the previous always-send behavior.
- `com_forceGenericSIMD` (existing, default `0`): now meaningful again; `1` restores the generic scalar processor.
- Existing rollback contract unchanged (`r_renderer arb2`, `r_glTier legacy`, modern quarantine cvars).

## Validation

- Build: `builddir` (debug) and `builddir-perf` (debugoptimized) clean.
- `testSIMD` (optimized build): "using SSE2 for SIMD processing"; BlendJoints, ConvertJointQuatsToJointMats, ConvertJointMatsToJointQuats, TransformJoints, UntransformJoints, TransformVertsNew, TransformVertsAndTangents, TransformVertsAndTangentsFast all **ok** against generic.
- Renderer validation matrix: see results below.
- Gameplay benchmark (storage1 smoke, same configuration as baseline): see results below.

### Results (2026-06-10, builddir-perf debugoptimized, SP `game/storage1`, `com_maxfps 240`, vsync 0, tier TopGL46)

- Renderer validation matrix: **26 of 26 cases passed** (`.tmp/perf-validation/`), including `renderer-modern-visible-selftest`, all tier probes, and all three `present-*` probes.
- `testSIMD`: SSE2 active by default, all comparisons vs generic **ok**.
- Gameplay benchmark (`renderer_gameplay_benchmark.py --profile smoke --sample-frames 900`), in-engine renderer benchmark + frame pacing snapshot:

| configuration | frame avg | p50 | p95 | p99 | cpu fe | submit | backend | present rate |
|---|---|---|---|---|---|---|---|---|
| baseline (pre-change) | 9 ms | 9 | 13 | 17 | 10 | 4 | 4 | 63.8 Hz (bound=simulation) |
| **all changes** | **4 ms** | **4** | **5** | **6** | **3** | **1** | **1** | **179.7 Hz (uncapped)** |
| all changes, `com_forceGenericSIMD 1` | 4 ms | 3 | 5 | 6 | 3 | 2 | 2 | 184.7 Hz |
| all changes, `r_useRedundantStateFiltering 0` | 8 ms | 8 | 10 | 11 | 8 | 1 | 1 | 91.0 Hz |

- Net: **~2.2x lower average frame time, ~2.8x higher presentation rate** on the dense-lighting acceptance scene; p99 fell from 17 ms to 6 ms.
- Attribution: the redundant-call filtering is the dominant contributor in this scene (~2x alone) — notably it also cut *front-end* time from 8 ms to 3 ms, which means the redundant submission stream was generating driver backpressure that stalled front-end GL usage (vertex-cache uploads), not just backend submission time. The SIMD contribution is small in this static-spawn view (few animated characters on screen) and within run noise; it is expected to matter in combat/character-dense scenes and during load (tangent/bounds derivation), and is proven output-compatible by `testSIMD`.
- Log review per Procedure 1: no new warnings; the only log noise is the stock retail edge-direction warnings and `.mtr` duplicate-material parse noise present on baseline.

## Rollback

Section A: `com_forceGenericSIMD 1`. Section B: `r_useRedundantStateFiltering 0`. Section C sort: no cvar (ordering-equivalent replacement; radix is stable where qsort was unstable on equal keys, which is a strict superset guarantee); shadow-map policy skip only changes work done when the feature is off.
