# Renderer Rework 2: CPU-First Optimization And Visible-Path Promotion (2026-06-10)

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

## Purpose

This plan re-sequences the renderer rework around the measured bottleneck profile of the current build: with decoupled presentation (60 Hz simulation, up to 240+ FPS presentation), the binding constraint is **CPU front-end cost re-run on every presentation frame**, plus per-draw submission overhead in the visible ARB2 path. The clustered hybrid plan ([2026-05-13-clustered-hybrid-gl-renderer.md](2026-05-13-clustered-hybrid-gl-renderer.md)) remains valid for its own track, but the work below delivers more frame-time and frame-pacing improvement for the actual Quake 4 asset base, and it hardens the modern path the hybrid track depends on.

## Baseline Findings (2026-06-10 analysis)

- The visible renderer is the classic single-threaded ARB2 forward path. Front-end and back-end run synchronously on the main thread (`RenderSystem.cpp` `R_IssueRenderCommands` executes `RB_ExecuteBackEndCommands` in-place).
- With presentation decoupled, `R_RenderView` re-runs the **entire** front-end up to 4x per game tic: portal flood, light/entity scissors, interaction generation, full CPU MD5 re-skin, dynamic shadow-volume regeneration, and surface sort — even on repeated-state frames where simulation did not advance.
- MD5/MD5R skinning is 100% CPU (`Model_md5.cpp idMD5Mesh::UpdateSurface`), single-threaded SIMD, regenerated per presentation frame.
- The modern side-pipeline is fully gated and ~zero-cost when off (`tr_backend.cpp` gate via `R_ScenePackets_SidePipelineRequired`), but it also delivers zero visible benefit until promoted, and it carries known efficiency/correctness gaps (silent draw-plan overflow, per-draw MVP recompute, O(N) material lookup, fence-less validation fallback).
- Mouse input is sampled at 60 Hz on the async thread; repeated-state frames interpolate between past snapshots, adding ~8-17 ms of view latency relative to true per-frame sampling.

## Design Goals

- High, stable presentation framerates with unnoticeable drops in complex scenes, on stock Quake 4 assets.
- Reduce repeated-state front-end CPU work without changing simulation, networking, demo, or gameplay behavior.
- Harden and slim the modern executor path that future visible promotion depends on.
- Every behavior-affecting change is gated by a cvar with a safe default and covered by existing self-tests or new validation hooks, matching the project's rollback-first culture.

## Non-Goals

- No change to authoritative 60 Hz simulation timing, networking protocol, or demo determinism.
- No replacement of stencil shadows as the default look.
- No new external shader/content assets (engine-internal resources only).
- The clustered hybrid promotion track is not blocked or rewritten here; this plan feeds it.

## Master Progress Checklist

Update statuses in place as work lands. An item is checked only when implemented, compiled clean, and validated per the Validation section.

### Phase A: Modern-Path Correctness And Efficiency (low risk)

- [x] A1. Loud fallback on draw-plan/submit-plan overflow: transition-edge `Modern GL executor:` console reports for draw-plan-not-ready and draw-plan-overflow replace the silent submit-plan clear (`ModernGLExecutor.cpp` plan gating in `R_ModernGLExecutor_PrepareFrame`). The existing `drawPlanOverflow` stat keeps flowing to metrics/`gfxInfo`.
- [x] A2. Stale-location protection on shader reload: `R_ModernGLExecutor_InvalidatePlans()` clears the draw/submit plans whenever `rendererShaderLibraryReload` runs, so cached program handles/uniform locations can never outlive the library generation they were built from.
- [x] A3. GPU-validation readback hard gate: readbacks are refused at queue time when `glFenceSync`/`glClientWaitSync` are unavailable, and the fence poll no longer guesses readiness from frame age (fence-less pendings expire as skipped).
- [x] A4. O(1) material-record lookup: open-addressed material-pointer hash (`MATERIAL_RESOURCE_TABLE_HASH_SIZE`, first-record-wins semantics preserved) replaces the linear scan in `R_MaterialResourceTable_FindRecordForMaterial`.
- [x] A5. MVP precompute: `modelViewProjectionMatrix` is built once per command at submit-plan build (`R_ModernGLSubmitCommand_BuildModelViewProjection`, including depth-hack/weapon-FOV handling); the per-draw matrix multiply in `R_ModernGLExecutor_SubmitCommand` and `R_ModernGLExecutor_BuildDrawRecord` is gone.
- [x] A6. Verified no lazy compile path: `R_ModernGLShaderLibrary_Init` eagerly compiles every program kind for every supported GLSL version at init, and `FindProgram` only searches linked programs. No warm pass needed.

### Phase B: Repeated-State Front-End Reuse (the 240 FPS fix)

- [x] B1. Dynamic-model reuse: `UpdateEntityDef` classifies transform-only updates (same model/skin/shader/joints pointer/shaderParms/suppress state, DM_CACHED, non-callback, not demo playback) and proves joint content unchanged via an FNV-1a hash recorded at snapshot generation (`R_HashJointMatrices`, `dynamicModelJointsHash`). Qualifying updates keep `dynamicModel`/`dynamicCollisionModel` through a new `keepDynamicModel` parameter on `R_FreeEntityDefDerivedData`, skipping `InstantiateDynamicModel` (CPU re-skin + tangents). Interactions, shadow volumes, and entity refs still rebuild against the new transform, preserving shadow/light correctness for moving entities. `ProjectOverlay` now explicitly clears the snapshot so new wound overlays appear next frame. Gated by `r_useRepeatedStateReuse` (default 1).
- [x] B2. Derived-data reuse verified by construction: kept snapshots retain their static-tagged `ambientCache` vertex-cache blocks (allocated via `vertexCache.Alloc`, touched per frame at draw, never auto-purged), so reuse costs zero re-upload. View-dependent deforms are untouched: deform sources run per-view from the snapshot, and DM_CONTINUOUS models (particles/BSE/sprites/beams) are excluded from reuse by classification.
- [x] B3. Reuse instrumentation: new `tr.pc.c_entitySnapshotsReused` counter, printed as `snapshotsReused` under `r_showUpdates 1`; regeneration pressure remains visible via the existing `md5:` counter under `r_showDynamic 1`.

### Phase C: Visible Backend Wins

- [x] C1. Verified already default-on: `r_rendererUploadPersistent` defaults to 1 and the upload manager selects persistent mapping on GL 4.4+/buffer-storage tiers. No change needed.
- [x] C2. Verified already implemented upstream: `idImage::CopyFramebuffer` uses `glBlitFramebuffer` whenever a render texture is the source (the HDR/offscreen path), keeping `glCopyTexSubImage2D` only for direct back-buffer reads where a blit has no bandwidth advantage. No change needed.
- [x] C3. Verified already default-on: `r_useDepthBoundsTest` (default 1, extension-gated) and `r_useLightScissors` (default 1). No gap found.
- [x] C4. Reworked on evidence: the planned luminance-floor bloom trim was REJECTED (it would pop bloom in dark scenes with bright sources — the most visible bloom case). The real post-chain stall was the synchronous `glReadPixels` for HDR auto exposure; it is now a double-buffered `GL_PIXEL_PACK_BUFFER` async readback with one frame of exposure latency, gated by `r_hdrAutoExposureAsync` (default 1) with automatic fallback when PBOs are unsupported.

### Phase D: Structural Projects (design-gated)

- [x] D1. Presentation view sampling groundwork (engine side): `in_presentationView` cvar (default 0) plus `idUsercmdGen::GetPresentationViewDelta`, which drains pending mouse input under the async critical section and reports the accumulated, not-yet-consumed view rotation in degrees without consuming it (next 60 Hz usercmd still receives full movement). Game-side consumption in openQ4-game remains a companion-repo task.
- [x] D2. Parallel front-end jobs: resolved as DEFERRED via design note (see below) — four concrete thread-safety blockers enumerated; B1/B2 removed the repeated-state cost that motivated the item.
- [x] D3. SMP front-end/back-end split: design note below; recommendation NO-GO for GL-context-migration SMP on this codebase generation, revisit after modern-executor promotion.
- [x] D4. GPU matrix-palette skinning scope note for MD5R: scope note below; sequence after modern executor depth/opaque promotion.

## Phase A Detail (as built)

- A1: transition-edge `common->Printf` reports at the plan-gating site in `R_ModernGLExecutor_PrepareFrame` for draw-plan-not-ready (with status string) and draw-plan-overflow (with source/planned counts). Warnings re-arm when the condition clears, so a persistent overflow prints once per episode rather than per frame. The pre-existing `drawPlanOverflow` stat already reaches metrics and `gfxInfo`.
- A2: plans are rebuilt every backend frame, so a stale-location window cannot occur in the current call order; the fix makes that structural: `R_ModernGLExecutor_InvalidatePlans()` clears both plans in the `rendererShaderLibraryReload` command handler, immediately after the library rebuild.
- A3: `R_ModernGLExecutor_QueueGpuDrivenValidationReadback` refuses to queue when `glFenceSync`/`glClientWaitSync` are missing (counted as skipped readbacks), and `R_ModernGLExecutor_PollGpuValidationFence` returns not-ready for fence-less pendings instead of guessing from frame age; such pendings expire through the existing max-safe-age path.
- A4: open-addressed hash (`materialHash`, 2x record capacity, linear probe, entry = record index + 1 so memset clears it) inside `materialResourceTableState_t`; inserts are first-record-wins to preserve the previous linear scan's "first match" semantics; cleared in `R_MaterialResourceTable_ResetFrameStats` which all build paths (frame prepare and self-tests) go through.
- A5: `R_ModernGLSubmitCommand_BuildModelViewProjection` (ModernGLSubmitPlan.cpp, declared in the header) reproduces the depth-hack/weapon-FOV projection adjustments and stores the MVP in the new `modelViewProjectionMatrix` field at `AddCommand` time; both executor consumers (`SubmitCommand` uniform upload and `BuildDrawRecord` GPU-driven record fill) read the precomputed matrix, and the executor-local projection helpers were removed.
- A6: verified — `R_ModernGLShaderLibrary_Init` compiles every `modernGLShaderProgramKind_t` for every supported GLSL version eagerly; `FindProgram` only searches already-linked programs. No lazy compile path exists, so no warm pass was added.

## Phase B Detail

The decoupled presentation path means `tr.frameCount` advances per presentation frame, so every `R_EntityDefDynamicModel` consumer regenerates per presentation frame. The reuse contract:

- A dynamic snapshot is reused only when ALL of: same `hModel` (and `DM_CACHED`), no callbacks on either side, same `customShader`/`customSkin`/`referenceShader`, same `suppressSurfaceMask`/`suppressLOD`, same `callbackData`, identical `shaderParms` (covers MD3 frame selection and MD5 skin-scale), same joints pointer and joint COUNT, and an FNV-1a content hash over the joint matrices matching the hash recorded when the snapshot was generated. `forceUpdate` and demo playback bypass reuse entirely.
- View-dependent deforms (`DFRM_SPRITE`, `DFRM_TUBE`, eyeball, etc.) run per-view from the snapshot and are unaffected; DM_CONTINUOUS models (particles, BSE, beams, liquids) never qualify for reuse.
- Kept snapshots retain their static-tagged ambient vertex-cache blocks (allocated via `vertexCache.Alloc`, touched at draw time), so a reuse hit costs zero re-skin AND zero re-upload. Interactions and entity refs are still freed and rebuilt, because a moved entity changes its light-relative shadow geometry and potentially its light set.
- Worst-case overhead added to the non-reuse path is one joint-content hash per candidate entity update (~0.3 µs for a 100-joint character), paid only when the cheap pointer/field equality checks already passed.

## Phase D Notes

- D1 keeps authoritative usercmds at 60 Hz. The engine exposes the accumulated mouse delta since the last usercmd latch; the game lib may rotate the presentation render view by that fractional delta. Prediction, networking, and gameplay continue to consume only the 60 Hz usercmds.
- D2 and D3 are explicitly design gates: no code lands from either item without the corresponding design note's go decision.

## D2 Design Note: Parallel Front-End Jobs (2026-06-10)

Recommendation: **DEFERRED (no-go for this milestone)**. Audit of the candidate dispatch sites found four thread-safety blockers that each require their own preparatory work before any worker-pool dispatch is safe:

1. `R_EntityDefDynamicModel` can issue game-code entity callbacks (`R_IssueEntityDefCallback`); game code is not re-entrant and must stay on the main thread, so per-entity parallel dispatch needs a serial callback pre-pass.
2. `R_FrameAlloc` is a single-threaded linear allocator and `Mem_Alloc`/`R_StaticAlloc` are not audited for concurrent use; shadow-volume and interaction generation allocate through both.
3. `tr_stencilshadow.cpp` accumulates into shared `static` vertex/index buffers (`shadowVerts`, `shadowIndexes`); these need per-worker instances.
4. `vertexCache` allocation issues GL calls and must remain on the context thread, so parallel phases must end before cache population.

Priority context: the B1/B2 repeated-state reuse removed the dominant front-end cost at high presentation rates (repeated re-skinning). The remaining skinning happens once per game tic per animated entity, which is within serial budget for stock Quake 4 scenes. Revisit D2 after the modern-executor promotion, when per-worker frame allocators can be designed together with the executor's submit phases.

## D3 Design Note: SMP Front-End/Back-End Split (2026-06-10)

Recommendation: **NO-GO** for a GL-context-migration SMP split on the current codebase generation. Revisit only after the modern executor owns the visible frame.

Constraints found:

1. GL context ownership: the entire backend (`RB_ExecuteBackEndCommands`, all `qgl*` calls) currently runs on the main thread that owns the GL context. A render thread requires `wglMakeCurrent`/SDL context migration plus an audit of every GL call site outside the backend (image uploads from `idImage::ActuallyLoadImage`, cinematics, vertex-cache allocation paths, GUI captures, and the modern side-pipeline) — many of these are invoked from front-end code today and would need queueing or context sharing.
2. Vertex cache frame mapping: `idVertexCache` frame-temp allocation toggles per frame and writes directly into mapped GL buffers on capable tiers. With a pipelined backend, frame N+1 front-end writes would overlap frame N backend reads; this requires at least triple buffering and fence retirement keyed to backend completion, not front-end frame toggles. The `UploadManager` already has multi-buffered fenced streams, so this is solvable, but `vertexCache` legacy fallback paths are not fence-aware.
3. Synchronous read-paths: `R_IssueRenderCommands` is also used for immediate-mode operations (screenshots, env captures, light-grid bake readbacks) that assume completion on return. These need an explicit sync API.
4. Input latch ordering: the decoupled tickrate work latches `com_ticNumber` inside `idSessionLocal::Frame()`; a pipelined backend adds one frame of latency between latch and present, partially offsetting D1's latency win.
5. Risk/benefit: the Phase B reuse work removes most repeated-state front-end cost, which was the dominant CPU share at high presentation rates. After B1/B2, the front-end share shrinks enough that SMP's payoff is mostly spike absorption — better obtained via the modern executor promotion (which batches submission and reduces backend CPU directly).

## D4 Scope Note: GPU Matrix-Palette Skinning For MD5R (2026-06-10)

The MD5R packed interaction path already ships three vertex-program variants (`md5rinteraction.vp`, `md5rinteraction1.vp`, `md5rinteraction4.vp`) that consume packed vertex data with 0/1/4 weight layouts, with joint data delivered through program-env registers (c[75]+). The remaining work to move skinning fully on-GPU:

- Extend the ambient/depth/shadow passes (not just interactions) with matching palette variants so a skinned mesh never needs CPU-skinned position data: depth fill, stencil shadow volume extrusion (CPU silhouette stays; volume vertices reference post-skin positions, so shadow volumes either stay CPU on cached skinned meshes from B1/B2 or move to the shadow-map path for skinned casters).
- Upload the joint palette once per entity per game tic (not per presentation frame) into a UBO on GL3.3+ tiers; program-env fallback for legacy.
- Fallback contract: any material/stage that reads per-vertex CPU-modified data (deform stages, texgen requiring CPU normals) classifies back to the CPU path, mirroring the modern draw plan's conservative classification.
- Sequencing: after modern executor depth/opaque promotion, since the executor's UBO/state-cache infrastructure is the natural home for palette uploads. Do not bolt palette UBOs onto the ARB2 bridge.

## CVar Plan (as landed)

- `r_useRepeatedStateReuse` (default `1`): keep model-space dynamic snapshots across transform-only entity updates (Phase B). `0` restores legacy per-presentation-frame regeneration. Reuse hits are visible as `snapshotsReused` under `r_showUpdates 1`.
- `r_hdrAutoExposureAsync` (default `1`): asynchronous double-buffered PBO readback for the HDR auto-exposure luminance sample (Phase C4); one frame of exposure latency instead of a per-frame GPU pipeline stall. `0` restores the synchronous readback.
- `in_presentationView` (default `0`): engine-side groundwork toggle for presentation-frame view sampling (Phase D1); requires game-side consumption of `idUsercmdGen::GetPresentationViewDelta` in the companion GameLibs repo before it has a visible effect.
- Existing rollback contract unchanged: `r_renderer arb2`, `r_glTier legacy`, and the modern side-path quarantine cvars keep working.

## Validation

### Results (2026-06-10)

- Build: `tools/build/meson_setup.ps1 compile -C builddir` clean after each phase (A, B, C, D1).
- Safe matrix (`python tools\tests\renderer_validation_matrix.py`, full run with all rework changes): **25 of 27 automated cases passed**, including every self-test that exercises the changed code (`renderer-visible-depth-selftest`, `renderer-gbuffer-selftest`, `renderer-cluster-grid-selftest`, `renderer-shadow-planner-selftest`, `renderer-deferred-resolve-selftest`, `renderer-forward-plus-selftest`, `renderer-modern-compatibility-selftest`, `renderer-compatibility-gates-selftest`, `renderer-default-promotion-selftest`, `renderer-default-safety-selftest`, `renderer-benchmark-selftest`, `renderer-gpu-driven-selftest`, `renderer-low-overhead-selftest`, all seven `tier-*` probes, `tier-gl33-debug-context`, and the three `present-*` probes).
- The two failing cases were re-run against the **unmodified baseline tree** (changes stashed, rebuilt, restaged) and fail identically there, so both are pre-existing on this machine and unrelated to this plan's changes:
  - `renderer-foundation-selftests`: times out mid `r_rendererMetrics 2` dump even at 120 s, after 17 individual self-tests already passed and 0 failed inside the batch.
  - `renderer-modern-visible-selftest`: `RendererModernVisible self-test failed: composition execution mismatch (deferred=0 forward=1 ...)` — byte-identical failure text on baseline. Tracked as a pre-existing modern-visible composition issue, out of scope here.
- Gameplay smoke (`python tools\tests\renderer_gameplay_benchmark.py --profile smoke`) with all rework changes active (including `r_useRepeatedStateReuse 1`): **passed** — SP `game/storage1` (dense indoor lighting acceptance scene) at `com_maxfps 240`, vsync 0, tier auto/best, 600-frame sample, in-engine frame timing `avg=8 ms p50=8 p95=11`, screenshot + `rendererBenchmarkCapture` + `framePacingSnapshot` + `gfxInfo` captured, renderer warning gates green (the only log warnings are stock retail `.mtr` parse noise present on baseline).

### Remaining manual validation before release sign-off

- Phase B feel/visual pass: SP gameplay (`game/airdefense1`, `game/airdefense2` for animated characters) with `com_maxfps 240`, `r_swapInterval 0`, `com_showFramePacing 2`; compare front-end ms and `snapshotsReused` (under `r_showUpdates 1`) with `r_useRepeatedStateReuse 0` vs `1`; verify no visual deltas in animated characters, wound overlays, BSE effects, or stencil shadows. MP (`mp/q4dm1`) equivalent pass.
- Phase C4 parity: scene with `r_hdrToneMap 1 r_hdrAutoExposure 1`, toggle `r_hdrAutoExposureAsync 0/1` and confirm identical exposure behavior (no pumping/oscillation) plus improved frame pacing under `com_showFramePacing`.
- Log review per Procedure 1 (`.home/baseoq4/logs/openq4.log`).

## Rollback

Each phase item is independently revertible: Phase A items are internal to the gated modern path; Phase B/C items sit behind their cvars; Phase D items default off. `r_renderer arb2` + `r_glTier legacy` remain the global escape hatch.
