# OpenGL Renderer Robustness and Optimization Plan

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Date: 2026-07-10  
Status: Stage 0 implementation and robustness validation complete; listen-host frame-time acceptance remains open

## Scope and architectural conclusion

The renderer should be hardened incrementally, not replaced wholesale. Its front end already produces scene packets, draw and submit plans, and a resource-backed render graph. Shared capability selection, upload management, state caching, metrics, GPU timers, and self-tests provide the right seams for measured work.

The visible shipping/default path is still ARB2. `r_renderer best` resolves to `BE_ARB2`, and the conservative defaults leave the modern executor, submit, visible, and auto-promotion paths disabled. The GL 3.3+ modern executor is an opt-in preparation/diagnostic path; GL 4.3 adds SSBO, compute, and indirect work, while GL 4.5 adds DSA, persistent upload, and multi-bind work. `r_rendererModernVisible` is a guarded hybrid bridge, not evidence that ARB2 parity has been achieved. Every correctness and performance result must therefore name the path tested: default/ARB2, modern preparation, masked modern submission, or guarded modern-visible.

This split matters operationally:

- ARB2 robustness changes affect players immediately and receive release-blocking priority.
- Modern-path changes may be exercised only on requested tiers and must fail closed to ARB2.
- An optimization is not a default-promotion argument until it has visual-parity, gameplay, recovery, and frame-time evidence.

## Evidence-backed findings

| Priority | Finding | Consequence | Disposition |
|---|---|---|---|
| P0 | `idRenderTexture` FBO names survived context generations and were validated with `glIsFramebuffer`. A recycled numeric name after full `vid_restart` could alias an unrelated current-context FBO. | Incorrect deletion/binding after context recreation; synchronous driver query on common handle use. | Implemented in this pass. |
| P0 | `idImage::Bind` called optional `glBindMultiTextureEXT` unconditionally. | Null entry-point call or non-portable binding on drivers without EXT DSA. | Implemented in this pass. |
| P0 | Generated draw-record, bucket, and indirect-command SSBO accesses lacked complete GPU-side bounds contracts. | Undefined shader memory access after a bad CPU record, content edge case, or future regression. | Implemented in this pass with counts, safe fallback, and validation counters. |
| P1 | The state cache treated `GL_ELEMENT_ARRAY_BUFFER` as global even though it is VAO state; its multi-bind fallback also assumed `GL_TEXTURE_2D`. | Suppressed required EBO binds and incorrect cube/array/multisample fallback binds. | Implemented in this pass. |
| P1 | Persistent upload reuse probed one modulo-selected slot and could enter an indefinite wait immediately. | Avoidable CPU hitch under transient GPU latency; unsafe persistent reuse when sync support is incomplete. | Alternate-slot scan, bounded retries, failure handling, and counters implemented. A final correctness-preserving blocking fallback remains after all slots/retries are exhausted. |
| P1 | Debug groups and labels existed without a registered KHR/ARB debug callback. | Driver errors and performance diagnostics were easy to miss. | Queued callback lifecycle and filtering implemented. |
| P1 | Cube render targets repeated framebuffer-completeness checks and render-target handle validation performed hot `glIsFramebuffer` calls. | CPU/driver synchronization and redundant validation. | Generation ownership and per-face completeness caching implemented. |
| P1 | Renderer validation suppressed GL errors, omitted several GL failure signatures, ignored process output when a logfile existed, and accepted `thresholdPass=0`. | False-green validation and benchmark reports. | Harness truthfulness implemented. |
| P1 | The combined modern-executor foundation self-test crashed after nested shader/draw-plan tests, while the component tests passed separately. Large test objects remained live across nested self-tests. | Baseline regression gate was unreliable on Windows. | Fixed by running component self-tests before allocating the large packet/graph/plan objects; post-change matrix rerun pending. |
| P1 | Render-graph physical allocations are exact-size, fixed-slot, and not reclaimed during dimension/feature churn. | Long-session VRAM growth and eventual slot pressure. | Planned: byte-budgeted LRU eviction with allocation/cache generations. |
| P2 | Framebuffer-copy helpers snapshot state with `glGetIntegerv`, and modern shadow setup performs runtime uniform reflection/sampler setup. | Avoidable synchronous queries and repeated CPU/driver work. | Planned. |
| P2 | Modern submission retains CPU-heavy cluster construction, duplicated consumers, narrow command batches, and only partial state-local sorting. | Front-end and submission overhead can dominate before GPU throughput does. | Planned and benchmark-gated. |

## Changes in the current working pass

1. Render-texture lifetime now stamps each FBO with `tr.glContextGeneration`. Stale-generation names are forgotten without querying or deleting them in a new namespace. Allocation and entry-point failures fail closed, zero/sentinel names are guarded, and attachment changes still rebuild the FBO.
2. Cube render targets cache successful completeness by face. Revalidation occurs after FBO recreation or attachment refresh; ordinary face rebinding no longer performs the same completeness query repeatedly.
3. Image binding now validates the tracked texture unit and selects core/ARB DSA `glBindTextureUnit`, EXT DSA `glBindMultiTextureEXT`, or legacy active-unit plus `glBindTexture`. The tracked state is updated only after a successful bind.
4. `GLStateCache` invalidates cached EBO state on VAO changes and tracks 2D, 3D, cube, array, multisample, and rectangle targets. Multi-bind emulation receives per-unit targets and mirrors unbind semantics.
5. Persistent uploads now require a complete sync contract, scan the ring for another ready slot before waiting, use bounded retry intervals, count submission/timeouts/fallback/wait failures, and use a conservative finish when fence creation or a sync wait fails. The final all-slots-busy path preserves correctness rather than overwriting in-flight storage.
6. Debug contexts register a KHR or ARB callback, filter notifications by default, queue callback messages outside normal console work, flush them at controlled renderer boundaries, and detach before context shutdown. Synchronous callback mode remains an explicit developer option.
7. GPU-driven shaders receive draw-record, bucket, and command-capacity counts. Invalid indices fall back or are rejected, and dedicated invalid-bucket/indirect-overflow counters feed validation metrics.
8. The validation and gameplay runners force `r_ignoreGLErrors 0`, scan logfile plus stdout/stderr, recognize out-of-memory, stack, context-loss, incomplete-FBO, and high-severity debug signatures, and fail a benchmark whose reported threshold result is zero.
9. The combined executor self-test runs its nested shader/draw/submit checks before constructing large local frame objects, removing the Windows stack-overflow condition reproduced by the pre-change foundation gate.
10. Classic modern-buffer updates keep their state-cache-tracked target binding after `glBufferSubData` instead of unbinding to zero and forcing the next update to miss.

No FPS, frame-time, memory, or parity improvement is claimed by these code changes until the validation table is populated with artifacts from this turn.

## Prioritized implementation roadmap

### Stage 0: close the robustness pass

- Compile with the supported Windows Meson wrapper and run the foundation, GL 3.3 debug, GL 4.3 GPU-driven, and GL 4.5 low-overhead gates.
- Exercise repeated full `vid_restart`, SP gameplay, and MP gameplay. Check the configured `fs_savepath/<gameDir>/logs/openq4.log`, not only process exit status.

Acceptance: all renderer self-test/tier gates exit zero; no access violation, high-severity debug message, GL error, incomplete FBO, shader failure, or renderer overflow; ten full context restarts recreate render textures without stale-name symptoms. SP must meet its frame-time threshold. MP host/client correctness must remain clean, while any measured threshold miss remains an explicit optimization blocker rather than being suppressed.

### Stage 1: eliminate synchronous queries and bound resource lifetime

1. **Framebuffer-copy query elimination.** Extend the authoritative GL state cache to cover read/draw FBO, read/draw buffer, scissor enable/box, and the texture destination used by copy helpers, or use named/explicit copy operations where the selected tier supports them. Remove steady-frame `glGetIntegerv` snapshots from `idImage` copy paths.

   Acceptance: zero `glGet*` calls in a steady-state `_currentRender`/depth-copy API trace after warm-up; identical color/depth results across ARB2 and relevant modern sidecars; recovery remains correct after resize and `vid_restart`.

2. **Modern shadow reflection and sampler caching.** Reflect all shadow uniform/block locations once at link time, store them in the program record, set fixed sampler units once per program generation, and invalidate only when the program generation changes.

   Acceptance: zero `glGetUniformLocation`/`glGetUniformBlockIndex` calls from shadow draw hot paths; shadow regression captures match; program reload and `vid_restart` rebuild the cache cleanly.

3. **Render-graph byte-budgeted eviction with cache generations.** Track dimensions, format, samples, estimated bytes, last-use frame, and allocation generation. Reuse exact compatible allocations, evict only inactive least-recently-used allocations when over a configurable byte budget, and propagate generation changes to FBO attachment caches so recycled GL names cannot look current.

   Acceptance: allocation bytes and object count plateau during at least 100 resize/scale cycles and a long multi-map run; no live resource is evicted; no stale attachment-cache hit; budget pressure is visible in metrics; no GL/debug errors.

4. **Legacy state-query inventory.** Add counters around remaining backend `glGet*`, `glIs*`, map/unmap, readback, and finish calls, then classify them as initialization, explicit diagnostics/capture, or hot-path defects.

   Acceptance: ordinary gameplay reports zero synchronous legacy queries/readbacks after warm-up except explicitly documented compatibility operations; diagnostics remain opt-in.

### Stage 2: benchmark-gated CPU and submission optimization

1. **Static index-buffer A/B.** Compare the current index-cache/upload behavior with dedicated immutable/static index residency using identical scenes and memory accounting. Keep both paths behind one test control until evidence is stable.

   Acceptance: five-run matched captures show lower median backend CPU time or at least a 5% lower backend p95, no p99 regression above run-to-run noise, no draw/index corruption, and bounded additional resident memory. Otherwise retain the current path.

2. **Clustered buffers.** Replace per-frame allocation/flatten churn with reusable capacity-managed light, grid, offset/count, and reference buffers; use compact offset/count plus flat-index storage across tiers.

   Acceptance: zero cluster-buffer allocations after warm-up in a stable scene, fewer uploaded bytes or lower cluster-build p95, identical light/reference/overflow counts, and unchanged rendered lighting.

3. **Remove CPU binning duplication.** Build cluster membership once per view and share the immutable result with deferred, forward+, GPU validation, and debug consumers. Keep the GL 3.3 CPU implementation as the compatibility baseline and evaluate compute binning only on GL 4.3+.

   Acceptance: one binning build per eligible view, consumer counters agree, light-heavy front-end p95 improves, and GL 3.3/4.3 images remain equivalent within the established visual tolerance.

4. **Command sorting and broader batches.** Stable-sort only reorder-safe opaque, depth, G-buffer, and shadow work by pipeline/program/material/geometry/scissor. Preserve source order for transparent, GUI, postprocess, subview, and explicitly ordered surfaces. Broaden indirect batches by compatible signature rather than one first-seen run.

   Acceptance: eligible state buckets and program/material/VBO transitions fall by at least 20% in representative scenes; backend CPU p95 improves; draw count and visual output are unchanged; ordered-category self-tests prove stability.

## Measurement policy

- Use matched executable, assets, resolution, quality, map position, warm-up, and capture duration.
- Record at least five runs per A/B case and retain p50, p95, p99, backend CPU time, GPU time, draw/state-transition counts, upload/fence counters, render-graph bytes, and warning signatures.
- Compare default/ARB2 first, then enable one modern feature at a time. Do not combine feature changes until the first regression or gain is attributable.
- Do not change renderer defaults unless required SP/MP gameplay and deterministic visual checks pass and the modern candidate is consistently ARB2-or-better at p50/p95/p99 on the supported tier matrix.

## Validation matrix for this pass

| Gate | Command/workload | Required evidence | Result from this turn |
|---|---|---|---|
| Build | `tools/build/meson_setup.ps1 compile -C builddir` | Successful x64 client/dedicated build; no new warnings attributable to this pass. | Pass; client and dedicated linked. Staged with the supported wrapper install command. |
| Harness syntax | `python -m py_compile tools/tests/renderer_validation_matrix.py tools/tests/renderer_gameplay_benchmark.py` | Exit zero. | Pass. |
| Foundation | `python tools/tests/renderer_validation_matrix.py --cases renderer-foundation-selftests` | All component and combined self-tests pass. | Pass after final review changes. The pre-change Windows exit `3221225477` is resolved. Artifact: `.tmp/renderer-validation/20260710-090203/`. |
| Debug context | `python tools/tests/renderer_validation_matrix.py --cases tier-gl33-debug-context` | Callback registers when supported; zero high-severity/GL-error signatures. | Pass after final review changes; actual GL 3.3 debug context, callback active, all warning signatures zero. Artifact: `.tmp/renderer-validation/20260710-090223/`. |
| GL 4.3 bounds | `python tools/tests/renderer_validation_matrix.py --cases renderer-gpu-driven-selftest` | GPU-driven test passes; invalid-bucket and indirect-overflow counters remain zero for valid input and can detect synthetic invalid input. | Pass after final review changes; `boundsProbe=1`, `mismatches=0`, all warning signatures zero. Artifact: `.tmp/renderer-validation/20260710-090256/`. |
| GL 4.5 upload/state | `python tools/tests/renderer_validation_matrix.py --cases renderer-low-overhead-selftest` | Low-overhead test passes; no sync submission/wait failure; fallback/timeout counters are reported. | Pass after final review changes; persistent path active and submission failures/waits/timeouts/fallbacks/wait failures all zero. Artifact: `.tmp/renderer-validation/20260710-090238/`. |
| Context lifetime | Storage 1 gameplay with a debug context and ten scripted `vid_restart` commands | Ten full restarts; callback re-registers; no stale FBO symptoms or severe driver errors. | Pass: 11 GL initializations/callback registrations including initial startup, threshold pass 1, p95/p99 9/10 ms, zero GL/FBO/high-severity signatures. One medium NVIDIA pixel-transfer performance message occurred at the explicit screenshot readback, not during steady rendering. Artifact: `.tmp/renderer-gameplay/20260710-084523/`. |
| SP gameplay | `python tools/tests/renderer_gameplay_benchmark.py --profile smoke --timeout 180` | Enters gameplay, captures benchmark/screenshot, threshold passes, zero warning signatures. | Pass in `game/storage1`: full 256-sample run p95/p99 10/11 ms (`.tmp/renderer-gameplay/20260710-084003/`); final post-review 120-sample smoke p95/p99 8/8 ms (`.tmp/renderer-gameplay/20260710-090406/`). Both reported threshold pass 1, captured screenshots, and had all warning signatures zero. |
| MP listen gameplay | `mp-q4dm1-listen` with `ui_autoJoin=1` for the new join-screen policy | Host and loopback client enter the map, capture screenshots/metrics, and remain GL-clean; both performance thresholds pass before release acceptance. | Correctness pass but performance acceptance open. Both roles entered `mp/q4dm1`, captured screenshots, and had zero GL/FBO/shader/fatal signatures. Client passed at p95/p99 4/28 ms; listen host reported p95/p99 23/34 ms and correctly failed `thresholdPass=0`. Artifact: `.tmp/renderer-gameplay/20260710-084344/`. |
| Remaining required/tier gameplay | `python tools/tests/renderer_gameplay_benchmark.py --profile required` and `--profile tiers` | Remaining SP maps pass; forced tiers reach gameplay or fail closed with an explicit contract reason. | Not run in this bounded pass. |
| Performance A/B | Default/ARB2 versus one modern feature at a time in the established comparison scenes | Five matched runs, raw JSON/log artifacts, no visual or p99 regression hidden by averages. | Not started; no performance claim in this pass. |

A successful build or main-menu startup alone is not sufficient validation. This pass entered SP and MP maps; the listen-host threshold miss above is retained as roadmap evidence and must not be represented as a full MP performance pass.
