# Renderer perf pass 4 (2026-06-11)

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Follow-up to `2026-06-10-renderer-perf-pass-3.md`. Post-pass-3 profile (storage1 smoke,
debugoptimized, vsync 0, fresh baseline `.tmp/perf4-baseline`): frame avg 5 ms (p50 5 /
p95 7 / p99 8), cpu fe=3 submit=2 backend=2, present 155.9 Hz, 832 draws, 1145 KB
per-frame upload. The front-end is the binding constraint; submission redundancy was
heavily filtered last pass.

Candidate selection comes from a 28-agent analysis pass (7 subsystem analysts + adversarial
hotness/safety verification per candidate; digest archived at `.tmp/perf4-analysis-digest.md`).

## Dispositions of pass-3 deferred candidates

- **Index buffer flip (deferred 1): CONFIRMED** — implement (section B). Three analysts
  independently converged on it; verification corrected impact from "high" to medium-on-storage1
  (~0.1–0.4 ms submit-side, plus speculative backpressure relief to the front-end) and found one
  deterministic crash that must be fixed first.
- **Interaction/light scissor caching (deferred 2): DROPPED** — the cacheable view-independent
  parts (interaction frustum, FloodFrustumAreas) are *already* cached on the interaction
  (`frustumState`, Interaction.cpp:1232-1321); the per-frame remainder is a function of the view
  pose, which changes every frame in gameplay, so a cross-frame cache would have a ~0% hit rate.
- **Shadow-volume caching across no-op entity updates (deferred 3): REFUTED on hotness** —
  SP game tics latch at 60 Hz and present-only frames never call `UpdateEntityDef`
  (Session.cpp:5345-5411); the Phase-3 game libs only push per-present updates for entities whose
  interpolated transform actually changed, which legitimately invalidates shadow volumes. The
  elide-eligible population (bit-identical parms + identical joints) is near-empty. Additionally,
  a correct implementation would have to re-evaluate retail shadow-LOD admission
  (Interaction.cpp:62-98) per frame, eroding the win. Not implemented.
- **DeriveTangents/DeriveTriPlanes SSE2 (deferred 4): SPLIT** — `DeriveTriPlanes` is per-frame hot
  (every animated shadow caster re-derives face planes every frame because Model_md5.cpp:451
  clears `facePlanesCalculated`); implement (section E). `DeriveTangents`/`NormalizeTangents`
  are dominated by load-time and bursty decal work — deferred again (smaller steady-state payoff,
  high blocker count around the `used[]` scatter and idDrawVert field-safe stores).
- **SMP front-end/backend overlap: DEFER AGAIN** — verified real with a ~15–18% wall ceiling, but
  the front-end issues GL directly (vertex cache allocs, image loads, deferred frees are retired
  only after the synchronous backend), the SDL3 thread machinery is Windows-only dead code, and
  driver backpressure couples FE and BE anyway. Revisit only after single-thread wins are
  exhausted.

## Work items

### A. Stop memsetting the ~1 MB idScenePacketFrame twice per frame (default path)

`R_ClearCommandChain` → `R_ScenePackets_EndFrame` → `idScenePacketFrame::Clear()` memsets
~1 MB of packet arrays, and runs twice per frame (EndFrame → R_IssueRenderCommands, and
R_ToggleSmpFrame), even though capture only opens the frame at `r_rendererMetrics >= 2`
(ScenePackets.cpp:34-36) — ~2 MB/frame of dead memset plus LLC eviction next to the
binding front-end.

- Reduce `Clear()` to: zero the stats struct, reset `activeScene=-1`, `activePass=-1`,
  `activePassLastSortKey=0`, `activePassSortKeyValid=false`. Every slot is already memset at
  allocation time (AddScene/AddPass/AddDrawPacket/FindOrAdd* — verified at ScenePackets.cpp:372,
  425, 510, 557, 584, 613) and all consumers iterate count-bounded (verified codebase-wide).
- Early-out `R_ScenePackets_EndFrame` when `!rg_frontEndScenePacketFrameOpen`.
- Keep a debug-only (`_DEBUG`) full memset so the ~20 stack-allocated frames keep zeroed arrays
  under debugging; document the slot-memset-at-allocation invariant in `Clear()`.
- No cvar: bit-identical by construction. Validate `r_rendererMetrics 2` capture and the
  scene-packet/geometry-resources/draw-plan self-tests.

### B. Index buffers on by default (r_useIndexBuffers → 1)

Today every glDrawElements draws 32-bit indexes from client memory while vertices sit in VBOs —
the classic worst-case driver combination, re-paying per pass (depth fill + N interactions +
2–4× stencil shadow draws). All allocation plumbing already exists behind the cvar.

Pre-flip fixes (mandatory, from adversarial verification):

1. **TAG_TEMP free crash**: `R_FreeStaticTriSurfVertexCaches` (tr_trisurf.cpp:368-390) calls
   `vertexCache.Free()` which FatalErrors on TAG_TEMP blocks. With the cvar on,
   Interaction.cpp:1755-1762 assigns a frame-temp block to heap-allocated packed-ambient
   `lightTris->indexCache`; freeing the interaction (entity/light moved) then crashes
   deterministically. Fix: skip TAG_TEMP blocks (null the pointer without Free), mirroring
   R_TouchVertexCache's tag awareness.
2. **BSE hardening**: BSE_Effect.cpp:520-521 nulls `tri->indexCache` without `vertexCache.Free()`
   (currently dead, but becomes a leak + dangling `block->user` if any path allocates one) —
   route through `vertexCache.Free()`.
3. **Legacy frame-temp alignment**: the non-upload-bridge `AllocFrameTemp` fallback packs offsets
   with no round-up (VertexCache.cpp:~525); add an explicit 4-byte round-up so index offsets stay
   aligned.
4. **Churn mitigation = section C** (VBO name pooling) lands first: with the flip, every
   regenerated dynamic-model surface adds a static index-VBO gen/data/delete trio per frame on
   top of the existing vertex-side churn.

The flip itself: change the default to "1" and drop `CVAR_ARCHIVE` (existing configs pin 0
otherwise, and the VBO-unavailable force-off in `idVertexCache::Init` would persist 0 into
configs). `r_useIndexBuffers 0` stays the instant rollback.

Known cap: MD5R packed prepared-batch draws (draw_arb2.cpp:717/762/846/927/1438) intentionally
draw client indexes and are untouched by the flip — wins concentrate in world/brush geometry,
prelight shadow volumes, static interactions and frame-temp paths.

### C. VBO name pooling in idBufferAllocator (new cvar `r_rendererUploadBufferPool`, default 1)

`AllocStaticBuffer`/`FreeStaticBuffer` (RendererUpload.cpp:47-94) do glGenBuffers +
glBufferData(GL_STATIC_DRAW) + glDeleteBuffers per tri surf with no pooling; animated MD5
surfaces free and re-create vertex caches **every frame** (Model_md5.cpp:433-441 →
tr_light.cpp:229 ambient + tr_light.cpp:450-484 shadow projection caches). Original idTech4
kept the VBO name on the free header and re-specified with glBufferData (orphaning).

- Pool freed names per target (ARRAY vs ELEMENT_ARRAY) in idBufferAllocator; Alloc pops a pooled
  name and re-specifies storage (orphaning idiom — spec-safe for in-flight reads).
- FreeStaticBuffer must still zero the caller's vbo reference (self-test asserts vbo==0).
- Cap retained bytes, not just name count (PurgeAll at level transition frees world-sized
  buffers); glDelete on pool overflow / oversized buffers.
- InvalidateBufferBindings only on actual glDeleteBuffers; pooled frees make no GL calls.
- Drain the pool in Shutdown (GL context still current — ordering verified) and on cvar toggle.
- Keep stats honest: count pooled-vs-live separately; update RendererUpload_RunSelfTest.

### D. Two-sided stencil shadows (wire the dead `r_useTwoSidedStencil` cvar)

`RB_T_Shadow` draws each volume 4× (internal) / 2× (external) with glStencilOp + GL_Cull churn
between draws (draw_common.cpp:7136-7154). `glStencilOpSeparate` (GL 2.0 core, loader already
initialized) collapses these to 2×/1× with bit-identical output under wrap ops.

Corrections from adversarial verification baked into the design:

- **Face mapping**: in non-mirror views `CT_FRONT_SIDED` culls GL_FRONT (tr_backend.cpp:194-206),
  so the legacy CT_FRONT_SIDED preload ops belong to **GL_BACK** and CT_BACK_SIDED ops to
  GL_FRONT; swap when `backEnd.viewDef->isMirror`. (The naive mapping inverts every stencil
  delta and erases all shadows.)
- Gate on `glStencilOpSeparate != NULL` (GL 2.0), **not** `glConfig.twoSidedStencilAvailable`
  (that's the NVIDIA-only GL_EXT_stencil_two_side string and a different API).
- Require wrap ops (`tr.stencilIncr == GL_INCR_WRAP_EXT`) for provable order-independence;
  otherwise fall back to the legacy multi-draw.
- Keep the legacy path verbatim for `r_useTwoSidedStencil 0` and the `r_showShadows` branch;
  pass exit already restores both faces via plain glStencilOp/glStencilFunc.
- Validate: c_shadowElements ≈ halves; mirror scene + demo playback for the isMirror swap;
  image diff vs baseline (an inverted mapping yields a stable-but-shadowless image).

### E. SSE2 DeriveTriPlanes (idDrawVert overload only)

Every animated surface re-derives face planes once per frame before any shadow/light-tri work
(Interaction.cpp:487-488; Model_md5.cpp:451 clears the flag every skinned update); the loop is
the last scalar per-triangle math on the interaction critical path.

- 4 triangles per iteration: scalar gathers + transpose (idDrawVert stride 64B), 4-wide cross
  product, **bit-exact vectorization of idMath::RSqrt's 0x5f3759df integer trick + one NR step**
  (NOT `_mm_rsqrt_ps` — rsqrt(0)=inf→NaN, while RSqrt(0) returns huge-finite; skinned meshes
  legitimately contain degenerate triangles, and face planes feed tr_trace → in-world gui
  clicks).
- `facePlanes` is allocated at exactly numIndexes/3 planes — scalar tail for numTris%4, no
  overstore; unaligned loads/stores throughout.
- `using idSIMD_Generic::DeriveTriPlanes;` so the caller-less rvSilTraceVertT overloads are not
  hidden (match the existing Dot/MinMax pattern); guard with the existing SSE2 availability
  macros.
- Validate: testSIMD ok (bit-exact makes it exact); validation matrix; com_forceGenericSIMD A/B.

### F. Light-grid availability latch (skip provably-dead per-surface work)

`R_AddDrawSurf` runs a full BSP descent (`PointInArea`) per ambient draw surface per view to
resolve `drawSurf->area` (tr_light.cpp:1148-1164, 1906), and `RB_STD_LightGridIndirect` does two
full numDrawSurfs filter walks + a GLSL program bind + a portal-area residency walk per 3D view
(draw_common.cpp:8342-8419) — but both only matter when some portal area has a usable baked
light grid. Stock Quake 4 content has none.

- Compute `world->anyLightGridAvailable` once (loop portalAreas with the RB_LightGridIsUsable
  criteria); invalidate on map load and light-grid (re)build/bake.
- In `R_AddDrawSurf`: when no grid is usable AND scene-packet capture is not active
  (front-end or backend legacy-stream capture — both read `drawSurf->area`), use the fallback
  entity-ref area and skip PointInArea. Zero output risk: nothing reads the value.
- In `RB_STD_LightGridIndirect` (and the residency walk): early-out on the same latch.
- No cvar: both changes only skip work whose result is provably unused.

### G. Small wins bundled (each trivially safe)

- **Material register memoization** per (viewEntity, material) within a view: R_LinkLightSurf
  re-evaluates the same registers per light (id's own FIXME, tr_light.cpp:1113); memo lives in
  frame memory on viewEntity_t, dies with the view, gated by `r_useRedundantStateFiltering`.
  Only fires when the renderEntity is the entityDef's own parms (BSE stack-local entities skip).
- **RendererBootstrap promotion-state memoization**: ShouldAutoPromoteModernVisible re-runs the
  full evaluation (440-byte memset + idStr heap churn) 5–8×/frame; latch keyed on the relevant
  cvar modified-counters.

## Explicit non-goals this pass

- In-world GUI geometry caching: measurement-first item (r_skipGuiShaders ceiling); redraw runs
  ON_FRAME/ON_TIME game logic, so caching is semantically risky — only worth designing if the
  measured ceiling justifies it.
- RB_SetDefaultGLState per-frame reset gating: medium risk (editor/external dirtying), ~100
  GL calls/frame — small next to what pass 3 removed; revisit with profiler evidence.
- DeriveTangents/NormalizeTangents SSE2, SMP overlap, MD5R packed index VBOs: deferred (above).

## Validation plan

- Build debug (`builddir`) + debugoptimized (`builddir-perf`) clean; install to `.install`.
- `testSIMD` (SSE2 active): all routines ok vs generic, incl. DeriveTriPlanes.
- Renderer validation matrix: all 26 cases, including modern-visible/deferred self-tests
  (ScenePackets change), present-* probes, and tier probes.
- Benchmark A/B vs `.tmp/perf4-baseline` (storage1 smoke, 900 frames): all-changes, plus
  one-cvar-off runs for r_useIndexBuffers 0, r_useTwoSidedStencil 0, r_rendererUploadBufferPool
  0, com_forceGenericSIMD 1.
- Shadow/character coverage for the index flip + pooling churn path (non-static scene),
  watching static alloc counters and tempOverflow/frameStalls.
- Adversarial multi-agent code review of the final diff before benchmarking.

## Rollback contract

`r_useIndexBuffers 0` (B), `r_rendererUploadBufferPool 0` (C), `r_useTwoSidedStencil 0` (D),
`com_forceGenericSIMD 1` (E). A and F are skip-dead-work-only (no observable behavior change);
G is gated by `r_useRedundantStateFiltering 0` where it touches evaluation order.

## Review findings applied (multi-agent adversarial review of the diff)

- SSE2 DeriveTriPlanes tail condition uses `numIndexes`, not `numTris`, so a malformed
  trailing partial triangle behaves exactly like generic.
- `TestDeriveTriPlanes` was inside testSIMD's commented-out block — re-enabled, with
  degenerate (zero-area) triangles added to exercise the RSqrt(0) huge-finite path.
- AllocFrameTemp's static-overflow fallback returns an already-deferred-freed STATIC header
  that gets recycled — a stale pointer on a heap tri could alias another surface's live cache.
  The packed light-tris path now links a frame-local tri copy (BSE frame-submit pattern) and
  clears the heap tri's temp pointers; `R_FreeTriSurfVertCache`'s comment documents the
  remaining (pre-existing, packed-model-ambient) exposure. The TAG_TEMP tag check itself is
  reliable for normal temp blocks (dynamic headers are never recycled into static blocks).
- Buffer-name pool drains eagerly in BeginFrame when the cvar is switched off.
- gfxinfo's two-sided-stencil report now reflects the real gate (glStencilOpSeparate + wrap).
- Light-grid latch invalidates explicitly in SetupLightGrid/LoadLightGridImages so bake paths
  that render without advancing tr.frameCount can't pin a stale value.

## Results (2026-06-11, builddir-perf debugoptimized, SP `game/storage1`, com_maxfps 240, vsync 0, tier TopGL46)

- Renderer validation matrix: **26 of 26 cases passed** (`.tmp/perf4-validation/`).
- `testSIMD`: all comparisons ok vs generic, including the new `DeriveTriPlanes` (with
  degenerate triangles).
- Gameplay benchmark (`renderer_gameplay_benchmark.py --profile smoke --sample-frames 900`):

| configuration | frame avg | p50 | p95 | p99 | cpu fe | submit | backend | present rate |
|---|---|---|---|---|---|---|---|---|
| baseline (pre-change, same day) | 5 ms | 5 | 7 | 8 | 3 | 2 | 2 | 155.9 Hz |
| **all changes** | **4 ms** | **4** | **6** | **6** | **2** | **1** | **1** | **169.0 Hz** |
| all changes, r_useIndexBuffers 0 | 4 ms | 4 | 6 | 7 | 2 | 2 | 2 | 162.4 Hz |
| all changes, r_useTwoSidedStencil 0 | 4 ms | 4 | 6 | 7 | 3 | 1 | 1 | 206.4 Hz |
| all changes, r_rendererUploadBufferPool 0 | 4 ms | 4 | 6 | 7 | 3 | 2 | 2 | 193.9 Hz |
| all changes, com_forceGenericSIMD 1 | 4 ms | 4 | 6 | 8 | 2 | 1 | 1 | 176.4 Hz |

- Net on the static smoke scene: ~20% lower frame avg, p99 8 → 6 ms, every CPU bucket down
  one integer millisecond. The present-rate column has high run-to-run variance (162–206 Hz
  across toggles) — the frame/cpu buckets are the reliable signal at this resolution.
- Attribution: the index-buffer flip carries the submit/backend reduction (toggling it off
  returns both buckets to 2/2); the front-end drop comes from the ScenePackets memset
  removal + area-resolve skip + register memo. The two-sided-stencil, pool, and
  DeriveTriPlanes wins are below integer-millisecond resolution on this static spawn view —
  they target shadow/character-dense scenes (same caveat as the pass-3 SIMD work).
- Log review: warning sets byte-identical between baseline and all-changes runs.

## Addendum (same day): two post-landing fixes

### SSAO white-frame corruption (pre-existing, root-caused)

Intermittent near-white frames with `r_ssao 1` (near geometry dark, far world white = a
depth buffer drawn fullscreen). Root cause: `idImage::CopyFramebuffer` / `CopyDepthbuffer` /
`SetSamplerState` / `SubImageUpload` / `AllocImage` issued raw `glBindTexture` calls that
replace the active unit's binding BEHIND `idImage::Bind()`'s per-TMU redundant-bind filter
(`tmu[].current2DMap`), and `BindNull()` never clears the tracker. Once a `_currentRender`
material left tracking[0] == scene, the SSAO depth copy raw-bound its depth scratch over it
and the scene `Bind()` was silently filtered — the shader sampled depth as `Scene`. Fixed
with `R_BindTextureForDirectAccess()` (tr_local.h), which keeps the tracker coherent at all
five raw-bind sites. Verified: 26/26 validation matrix, SSAO-on storage1 capture renders
correctly (zero near-white pixels). This bug class is stock-idTech4-era; SSAO's per-frame
copies made it visible, and cinematics (`SubImageUpload` every video frame) were equally
exposed.

### Index-VBO churn pacing regression on dynamic geometry (pass-4 regression, fixed)

Real gameplay (animated characters, BSE effects) regressed in frame-rate consistency vs the
pre-pass-4 build while the static storage1 spawn benchmark improved — exactly the blind spot
the verification flagged. Mechanism: with the flip, every per-frame-regenerated tri surf
(dynamic-model ambient tris, per-light interaction lightTris/shadowTris, shadow-map caster
tris) allocated and re-uploaded a STATIC index VBO every frame. Demonstrated on
`sp-medlabs` (BSE-heavy): **1001 KB/frame upload with the flip vs 21 KB/frame with the
fix** (48x), pacing max 19 -> 13 ms; on storage1 the all-changes 94 ms pacing spike
disappeared (max 16 ms, p95 8 ms, present 184 Hz — better than both the pre-pass-4
baseline and the original flip).

Fix: `r_useIndexBuffers` is now tiered — `0` = never, `1` = static geometry only:
world/brush models, static entity models, prelight shadow volumes, static interactions;
`2` = all geometry (the regressing upload-everything behavior, kept for A/B).
Gating helper `R_StaticIndexCacheAllowed()` (tr_light.cpp) checks
`hModel->IsDynamicModel() == DM_STATIC`. Frame-temp index paths (deforms, BSE frame-submit,
packed MD5R) are unaffected — they go through the persistent-mapped ring, which is cheap.
Lesson recorded: static-spawn benchmarks cannot see per-frame regeneration churn; any
geometry-lifetime change must be A/B'd on `sp-medlabs` (BSE) and a character-dense scene,
watching the per-frame `upload=` KB and `framePacing` max, not just frame averages.

## Addendum 2 (same day): default revert + further combat-path optimizations

Persistent user reports of lower/less-consistent real-gameplay framerates vs the post-pass-3
build narrowed the remaining default-path delta to the index flip even at mode 1: a per-draw
GL_ELEMENT_ARRAY bind across thousands of distinct per-surface buffers (never elided by the
bind filter) plus lazy index-VBO alloc bursts on first surface visibility while traversing —
neither visible to the static spawn-view benchmarks. **`r_useIndexBuffers` default reverted
to `0`** (exact pass-3 submission behavior); modes 1/2 retained for per-machine A/B. The
measured spawn-view benefit was within the established ±20% run-to-run Hz noise anyway.

New optimizations landed in the same change:
- **SSE2 CmpGT/CmpGE/CmpLT/CmpLE** (plain + bitNum forms, 8 overrides): shadow facing
  (`R_CalcInteractionFacing`) and cull-bit classification (`R_CalcInteractionCullBits`,
  stencil-shadow clip bits) run per (caster × light) every frame in combat; byte-exact vs
  generic (ordered SSE compares match scalar NaN semantics). `testSIMD` now also runs
  `TestCompare()`/`TestMinMax()` plus a new edge block (odd counts forcing scalar tails,
  bitNum 7, NaN/-0.0 inputs, non-zero constants) — all ok.
- **Decal stage-register hoist** (ModelDecal.cpp): `EvaluateStageRegisters` was run per
  TRIANGLE per stage per frame; consecutive triangles of one impact share identical
  (life, spawnTime) inputs, so it now re-evaluates only when the pair changes —
  decal-heavy firefights stop re-interpreting identical material expressions hundreds of
  times per frame. Bit-identical output by construction.
- **Dormant-pipeline bookkeeping latch**: `R_ModernGLExecutor_SkipFrame`'s ownership-table
  string rewrites, ~2 KB stats reset, and several-hundred-scalar metrics fan-out (plus the
  five zero-fill mirror Records in `RB_ExecuteBackEndCommands`) now run once per
  active→dormant transition (and per-frame only while `r_rendererMetrics > 0`). The latch is
  cleared inside `R_ModernGLExecutor_ResetPassOwnershipTable`, which every state-mutating
  path traverses (PrepareFrame, Shutdown, all modern selftests), and the readback poll
  ordering preserves pre-latch semantics (reset before poll). An adversarial review caught
  and fixed three majors here before landing (poll-ordering wipe, selftest poisoning,
  once-per-process mirror flag).

Validation: 26/26 matrix; testSIMD fully ok incl. new edge cases; medlabs pacing max
improved to 8 ms (best recorded); storage1 within the established noise band with the
pass-3 submission path restored.
