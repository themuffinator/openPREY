# Shadow Mapping — Production-Grade Assessment and Plan (2026-07-09)

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

This plan supersedes `2026-06-12-shadowmapping-rework.md` and `2026-06-13-shadowmapping.md` as the
authoritative roadmap for making shadow maps the shippable default. Every defect below was
re-verified against the tree at `c6817d5b` (2026-07-09) by an 8-layer audit with independent
per-finding adversarial verification (62 agents); claims from prior docs that no longer hold were
discarded. 51 findings were confirmed with file:line evidence; 1 was refuted.

**Headline discovery:** the 2026-06-12 plan's Phase A (functional caster bias, defined point
depth, hardware PCF, stencil-volume elision) **was implemented the same day — but on branch
`shadowmap-rework` (commits `2f9ef394`, `25e6a3b0`, `19544918`, forked at `73558fab`) and never
merged**. Main has since advanced 129 commits, including the 2026-06-13 contract-unification work
(`48bc8bc7`, `f0cad34a`, landed 2026-06-14: shared projected classification, planner/ARB2 parity,
budget fairness, real modern receiver *sampling* code). The result is a tree with Phase C
partially present but Phases A and B absent — modern shaders contain genuine sampling code that
has no atlas producer behind it, and the legacy path still has every Phase A bias/quality defect.

---

## 1. Verified current-state diagnosis

### 1.1 What is broken (confirmed, severity-ordered)

**Bias/correctness core — the acne↔peter-panning deadlock is structural, not tunable:**

| # | Defect | Evidence |
|---|--------|----------|
| B1 | Caster-side bias entirely non-functional on every path: projected caster writes `gl_FragDepth` (bypasses `glPolygonOffset` per GL spec), point caster stores depth in color. `r_shadowMapPolygonFactor/Offset` are inert knobs; debug mode 10 toggles a no-op; tuning them spuriously invalidates the static cache (they are hashed). | `shadow_proj_caster.fs:59`, `draw_arb2.cpp:7114-7115/7273-7274/7390-7391/7529-7530`, hash at `draw_arb2.cpp:3120-3121` |
| B2 | Point caster statically declares `gl_FragDepth` but writes it only when `uPointShadowDepthCompare > 0.5` — fragment depth is **spec-undefined on the default path** (`r_shadowMapPointDepthCompare 0`). The pass depends on LEQUAL to keep the nearest caster's packed radial depth; on spec-strict drivers (Apple GL) cube texels can retain the *farther* caster. Also forfeits early-Z on all drivers. | `shadow_point_caster.fs:72-74`, `RenderSystem_init.cpp:313`, `draw_arb2.cpp:7266-7268` |
| B3 | Texel-aware receiver bias is **exactly zero for projected (spot) lights** — `R_ShadowMapLightWorldTexelSize` derives from `vLight->lightRadius`, which only point lights populate (`Light.cpp:115-139` fills it in the `!gotTarget` branch only). `r_shadowMapTexelBiasScale` (default 0.45) is a silent no-op for the entire projected path in default single-cascade mode. | `ShadowMapProjected.cpp:247-262`, `:445-452` |
| B4 | CSM per-cascade texel depth bias uses the wrong normalization (camera slice length `sliceFar-sliceNear` instead of the light's falloff-depth extent); the degenerate-fit fallback uses a third convention. Bias magnitude jumps discontinuously across splits. | `ShadowMapProjected.cpp:497`, `:426`, vs. correct single-cascade convention at `:446` |
| B5 | "Normal bias" is depth-space only — no true world-space normal-offset exists anywhere. Pure depth bias cannot resolve the acne/panning tradeoff at grazing angles; this is the standard structural fix and it is missing. | `shadow_interaction.fs:262-279`, `shadow_interaction.vs` |
| B6 | Receiver-plane bias computes `dFdx/dFdy` inside divergent control flow (undefined derivatives); PCSS guard radius still uses `min()` where the 06-12 plan proved `max()` (unfixed A6); PCSS silently unavailable under hardware compare with no auto-select. | `shadow_interaction.fs:274-276`, `:190` |

**Coverage gaps — things that lose shadows when maps turn on (parity regressions vs stencil):**

| # | Defect | Evidence |
|---|--------|----------|
| C1 | **Parallel (sun) lights have no shadow-map path at all** — classified `SHADOWMAP_LIGHT_PARALLEL` for stats only, then routed by raw `vLight->pointLight` (parallel lights *are* point lights with origin faked 100 000 units out, `tr_lightrun.cpp:415-423`). With `r_shadowMapPointLights 1` the radial far envelope saturates and they render **with no shadows and no stencil fallback**; with the default 0 they at least fall back to stencil. Q4 outdoor maps use these. | `ShadowMapClassification.cpp:14/58`, `draw_arb2.cpp:6695`, `:10317-10329` |
| C2 | Translucent/`forceShadows` casters that cast in the shipping stencil path (`r_stencilTranslucentShadows` defaults 1) silently lose all shadows for every light that maps successfully — the opaque map policy requires `coverage != MC_TRANSLUCENT` regardless of `MF_FORCESHADOWS`, and the moments pipeline is opt-in (`r_shadowMapTranslucentMoments 0`) + capability-gated. Glass/grates/authored occluders go shadowless. | `Interaction.cpp:137-159`, `:1642-1652`, `draw_arb2.cpp:9757-9781/9839-9848` |
| C3 | Translucent **receivers** get zero shadowing under mapped lights (no translucent variant of the mapped receiver; mapped branch forces `GL_ALWAYS` stencil). Stencil path shadowed them. | `draw_arb2.cpp:10332` |
| C4 | All caster passes hard-code `glCullFace(GL_BACK)` and ignore material cull type — `twoSided`/`backSided` casters (foliage, grates, curtains) are one-sided-culled out of the map. | `draw_arb2.cpp:7113/7272/7389/7528` |
| C5 | Point-light per-face near plane clips casters up to 16 world units from the light with no depth-clamp/pancaking fallback — casters hugging the light vanish. | `draw_arb2.cpp:7212` |
| C6 | Shadow-LOD admission is latched on persistent `surfaceInteraction_t` with no invalidation: an entity first seen far away caches `admitted=false` **forever** (both stencil and map paths) until its dynamic model changes — permanent shadow pop-out for static/idle entities; the reverse latch defeats the LOD optimization. Also uses unseeded `rand()` — nondeterministic across runs/demos. | `Interaction.cpp:89-98`, `:80`, `:1878-1881` |
| C7 | Skinned receiver exclusion is too broad: every dynamic model falls back to hard stencil next to soft mapped world shadows, though CPU-skinned MD5 ambientCache verts are final-pose and would sample correctly; only GPU-skinned MD5R genuinely needs exclusion. | `draw_arb2.cpp:7958-7994` |
| C8 | Partial receiver-mask failure double-lights surfaces: one failed surface prepare fails the whole mask pass and the stencil fallback re-draws interactions already drawn additively by the mapped pass. | `draw_arb2.cpp:8978`, fallback `:9267-9300` |
| C9 | Shadow FBO incompleteness is a `FatalError` — the single hole in an otherwise fully defensive fallback lattice. | `gl_RenderTexture.cpp:290-292/352-354` |

**Stability/quality:**

| # | Defect | Evidence |
|---|--------|----------|
| S1 | CSM texel snapping quantizes in **base-projection** texel units, not the cascade's own grid, and the crop extent is refit every frame — stabilization does not stop shimmer under translation and pops under rotation even with `r_shadowMapCascadeStabilize 1`. | `ShadowMapProjected.cpp:355-361`, fit `:283-353` |
| S2 | Cascade blend band samples outside the next cascade's fitted crop (fit never includes the band), cross-fading toward *fully lit* — bright bands at split boundaries. | `shadow_interaction.fs:537-545`, `ShadowMapProjected.cpp:462-500` |
| S3 | Default filtering is binary NEAREST taps — hardware LINEAR compare (free 2×2 PCF per tap) never used; 13-tap kernels band visibly. Compare defaults off (`r_shadowMapDepthCompare 0`, `r_shadowMapPointDepthCompare 0`), textures `TF_NEAREST`. | `draw_arb2.cpp:5257`, `:8858-8863`, `RenderSystem_init.cpp:302/313` |
| S4 | Point fp16 "high precision" storage (default on) quantizes coarser near the far envelope (~4.9e-4 ULP) than the RGBA8 packed path (~1.5e-5), marginal against the default receiver bias — acne risk unique to the "high-precision" mode. | `draw_arb2.cpp:5308` |
| S5 | Cascade bounds double-pad (`r_shadowMapProjectionPad` baked into base planes *and* re-applied to fitted extents) — ~30 % wasted resolution at default 0.15. | `ShadowMapProjected.cpp:52-62`, `:346-352` |

**Performance architecture:**

| # | Defect | Evidence |
|---|--------|----------|
| P1 | Dual-pipeline CPU cost: stencil volumes are still generated/cached/linked every frame for lights that render maps (planned `r_shadowMapSkipStencilShadows` never landed on main). | `Interaction.cpp:1686-1692`, `:2147-2175` |
| P2 | One dynamic caster disables and actively invalidates the light's entire static cache — no static/dynamic layer split. Combined with P3, a settled ragdoll/corpse forces full map re-render of every containing light **every frame forever**. | `draw_arb2.cpp:3229-3236` |
| P3 | Skeletal/AF entities are permanently classified dynamic even physics-asleep (`callback != NULL`, `DM_CACHED`, cached dynamicModel — all three clauses latch). Static-mesh moveables settle correctly; ragdolls never do. | `Interaction.cpp:442-450` |
| P4 | Every light with both local and global interactions renders its map **twice** per frame (LOCAL pass with global casters, GLOBAL pass re-rendering global+local), with ~30 uniforms re-uploaded per pass. | `draw_arb2.cpp:10324-10328`, `:8756-8871` |
| P5 | Point maps draw all caster chains into all 6 cube faces unconditionally — no per-face culling, face skipping, or empty-face elision. CSM likewise re-draws all chains per cascade with no per-cascade caster cull. | `draw_arb2.cpp:7281-7295`, `:7118-7137` |
| P6 | Update budget (`r_shadowMapMaxUpdatesPerView`) is first-come-first-served in viewLight order — no importance ordering, no round-robin aging; over-budget lights stencil-fallback in a fixed pattern. Static cache is 8 slots/type with 2 entries per light → residency ceiling ≈ 4 lights, LRU-thrash in normal Q4 scenes. | `draw_arb2.cpp:3427-3431`, `:2247` |
| P7 | Per-surface program bind/unbind + full uniform re-upload in the projected caster chain, ×cascade count; synchronous `glGetFloatv(GL_COLOR_CLEAR_VALUE)` reads in hot passes; dead caster-chain construction for point lights when `r_shadowMapPointLights 0`; shadow GPU memory never freed on cache expiry or feature disable (only vid_restart). | `draw_arb2.cpp:6469/6476`, `:7230-7231`, `Interaction.cpp:2065`, `:3278-3290` |

**Modern path (opt-in today, but the intended end-state):**

| # | Defect | Evidence |
|---|--------|----------|
| M1 | **No atlas producer exists.** Planner assigns tiles; GLSL contains real sampling code; nothing renders casters in light space into those tiles. The modern "shadow depth" pass renders with the **camera MVP** into one whole-texture viewport (fail-closed diagnostic sidecar — refuted as a visible bug, confirmed as dead-end architecture). Modern bindings alias ARB2's per-light scratch texture as "the atlas". | `ModernGLExecutor.cpp:4238-4245`, `:4920-4961`, `draw_arb2.cpp:2667-2676` |
| M2 | Coordinate-space mismatch: forward+ passes GL eye space (z negative) where cluster/light math expects the cluster basis (x=left, z=forward-positive) — cascade selection always picks 0 in forward+; deferred reconstruction ignores real projection terms and mirrors x. | `ModernGLShaderLibrary.cpp:282/604-608/772/1141`, `ModernClusteredLighting.cpp:369-378` |
| M3 | Frame-global fail-close: one fallback/receiver-blocked light discards the entire modern frame; enabling the modern path also disables the planner's only cache-reuse budget escape → more fallbacks → guaranteed fail-close in real scenes. Modern shadows are structurally unobservable outside trivial scenes, while the sidecar GPU cost is still paid. | `ModernGLExecutor.cpp:5817-5871/7221-7226`, `ModernShadowPlanner.cpp:307-313/807` |
| M4 | Planner is write-only telemetry for ARB2 — two independent budget systems (planner quotas vs `r_shadowMapMaxUpdatesPerView`) can silently disagree; metrics can claim MAPPED for lights ARB2 fell back on. | `draw_arb2.cpp:5720/3403/3427`, `ModernShadowPlanner.cpp:359-381` |
| M5 | Dead/conflicting contracts: planner XYWH tile rects uploaded but never consumed (GLSL samples per-light min/max `projectedAtlasRect`); `ModernClusterShadowVisibility` fails **open** (returns lit) on every inconsistency with no diagnostic; self-tests have trivial-pass escape hatches and zero consumption-side coverage (no std140-vs-GLSL layout check, no freshness check). | `ModernShadowPlanner.cpp:1071-1096`, `ModernGLShaderLibrary.cpp:849-863`, `ModernShadowPlanner.cpp:2124-2127/2310-2339` |

**Game-side (openQ4-game):**

| # | Defect | Evidence |
|---|--------|----------|
| G1 | Gun flashlight and projectile lights gate `noShadows` on `com_machineSpec >= 3` — machines detected below tier 3 request no shadows at spawn; reads as "shadow maps broken" during bring-up. Flashlight also defaults to a **point** light (`flashlightPointLight` default 1), so with `r_shadowMapPointLights 0` it can never map — the primary flashlight test case needs both facts understood. | `Weapon.cpp:897/899`, `Projectile.cpp:280` |
| G2 | Ragdoll/AF at-rest classification (see P3) originates in entity callbacks staying set; gibs, burn/sink corpses, brittle glass, client moveables force `noShadow` — stencil-era choices that are cheap to lift under maps (dissolves are perforated-caster compatible). | `AFEntity.cpp:1577/1623`, `AI_States.cpp:865/924`, `Player.cpp:15004` |
| G3 | First-person shadow-suppress lightId computes to 0 for entityNumber-0 players when the flashlight is inactive — 0 is the "unset" sentinel, so the muzzle-flash suppression documented in `Player.cpp:10709` is permanently inert (currently masked by hard `noShadows` on muzzle flashes). | `Weapon.cpp:22-36`, `Weapon.h:116`, `Interaction.cpp:2041-2042` |
| G4 | `memset(renderEntity, 0, sizeof(renderEntity))` zeroes 8 bytes (pointer size) in both MP simple-items refresh paths. | `game/MultiplayerGame.cpp:3620-3621`, `mpgame/MultiplayerGame.cpp:3761-3762` |
| G5 | `g_showPlayerShadow` defaults 0 — no first-person body shadow; a stencil-cost choice worth revisiting under maps. | `SysCvar.cpp:475` |

**Process/tooling:**

| # | Defect | Evidence |
|---|--------|----------|
| T1 | **Zero shadow validation in CI.** The assetless self-test cases exist in the validation matrix (`renderer-shadow-planner-selftest`, `renderer-shadow-projected-diagnostic`) but no workflow selects them; the screenshot profile has no committed golden references and passes when references are absent. | `.github/workflows/commit-validation.yml:319/324`, `renderer_validation_matrix.py:606/660` |
| T2 | Shadow maps are structurally impossible on the Apple GL2.1 path (interaction loop bypassed) and no platform support matrix says so; user doc documents inert knobs as primary bias controls and omits debug modes 12-14; `r_shadowMapSize` silently diverges (point 2048 cap, modern-path benchmark-budget cap at 1024); performance presets silently revert a user's shadow-map opt-in; no menu/localization exposure at all. | `draw_arb2.cpp:10228-10244`, `docs/user/shadow-mapping.md:250-251/282-294`, `Common.cpp:2686-2688`, `system.gui:401-423` |

### 1.2 What is right (preserve these — do not regress)

- **Depth conventions are in exact caster/receiver parity** for both light types: projected =
  un-divided falloff-plane depth (same localized plane row both sides); point = radial
  distance / shared padded-far function. Uniform bias units across the volume. Keep this design.
- **The projected-light CSM crop math is algebraically correct** (23-point sampling, NaN/w
  guards, ≥4 valid points, mixed-sign detection) and **fails safe** to a single full-volume
  cascade with telemetry.
- **The fallback lattice** (mapped → cache-reuse → stencil → per-receiver filtered fallback) is
  the right shape; receivers that fall back keep stencil shadows rather than losing them.
- **Static-cache invalidation is correct** (signature hashes caster entity index + full
  modelMatrix + lastModifiedFrameNum + camera pose for CSM): movers/doors/moveables invalidate
  properly, no staleness, no settle pop. CSM caching is correctly conservative (default off).
- **Frontend selection is healthier than the old docs claim**: off-screen casters handled via
  default-on conservative caster path with portal-flood area trimming; local/global
  noSelfShadow ownership matches retail stencil semantics; spectrum/depth-hack/fog/blend
  exclusions correct; suppression flags (`suppressShadowInViewID/InLightID`) flow into the map
  path at the shared gate; per-view chain lifecycle is clean.
- **Planner/ARB2 *classification* contract is unified** (shared padded clip planes, cascade
  gates, invariant validation, parity self-test) — the 06-13 work landed and holds.
- **Receiver shader robustness**: w/NaN guards, fail-to-lit OOB policy, atlas guard-banding
  consistent between render and sample, compare/non-compare program variants toggled correctly.
- **Diagnostics are unusually deep**: 15 shader debug modes, atlas overlay, multi-line SM
  report with per-phase GPU timings, reject-reason histograms, fairness history. Build on this.
- **Game-side flag plumbing is complete and canonical** (spawnargs, savegame round-trip,
  projected-light sanitization via `rvNormalizeProjectedRenderLight`).

### 1.3 Prior-plan ledger

| Item (06-12 plan) | Status |
|---|---|
| A1 caster slope bias, A2 point depth variants, A3 bind-once, A4 hw-PCF defaults, A5 stencil elision, A6 min→max + reject fix, A7 docs, A8 validation | **Implemented on stranded branch `shadowmap-rework`; absent from main** (A6's reject-reporting half landed independently via `48bc8bc7`) |
| Phase B persistent atlas | Never started (M1) |
| Phase C modern receiver sampling | Sampling code + capability gate landed (`48bc8bc7`, 2026-06-14) but is unconsumable without B (M1, M3) |
| Phase D default flip | Correctly withheld |
| 06-13 plan (contract unification, quotas, fairness, diagnostics) | Fully landed on main (`48bc8bc7` + `f0cad34a`) |

---

## 2. Architecture decision

Three half-finished architectures currently coexist: ARB2 per-light scratch rendering, a bolt-on
all-or-nothing static cache, and a planner/modern-sampler with no producer. The end-state is
**one architecture**:

> A **persistent shadow page atlas** (D24/D32 depth, target 4096², tiles 256–1024) rendered
> **up front** each frame before the interaction loop, with **static/dynamic layer
> composition** per tile, allocated by `ModernShadowPlanner` acting as the **single authority**
> for both the ARB2 receiver path (which already addresses tiles via `uShadowAtlasRect`) and the
> modern clustered path (whose sampling code already exists). Point lights move to a small
> cube-array pool (GL3.3+) with a dual-paraboloid atlas fallback. Stencil volumes remain the
> per-light fallback and the rollback default.

Everything in Phases 0–4 is deliberately valuable *on its own* on the legacy path and survives
the Phase 5 unification unchanged (bias contract, cull policy, filtering, stability, coverage
parity, game-side fixes are all atlas-agnostic).

## 3. Production invariants (definition of "AAA-grade", enforced by tests)

- **I1 — No silent shadow loss.** Every shadow-casting light resolves to exactly one of
  {mapped, cached, stencil, explicitly-unshadowed-with-reason}; the SM report enumerates all of
  them and CI asserts zero `UNKNOWN` reject reasons and zero unexplained unshadowed lights.
- **I2 — Bias is tunable and monotonic.** With all bias hard-zeroed (debug modes 8/10/11), a
  test scene shows acne, not detachment; each bias knob's response is monotonic (captured via
  debug mode 12 compare-delta screenshots).
- **I3 — Depth-convention parity is asserted in code**, not maintained by parallel construction:
  startup self-test asserts caster/receiver depth-row pairing and point far-function pairing.
- **I4 — Determinism.** No unseeded `rand()` in any shadow decision; identical demo playback
  produces identical shadow admission frame-by-frame.
- **I5 — Temporal stability.** Unit test: translating the camera moves each cascade's snapped
  crop center by an integer number of *that cascade's* texels; sub-threshold rotation leaves the
  crop bit-identical. No per-frame extent refit without hysteresis.
- **I6 — Graceful degradation ladder.** Over budget: reduce update rate → reduce resolution →
  reduce cascades → cached → stencil. Never full-quality→nothing; a light may only become
  unshadowed if it is explicitly declared so (I1).
- **I7 — Fail-visible, not fail-open.** GPU-side inconsistencies (descriptor/atlas/policy
  mismatch) produce a debug-visualizable state and a counted stat, never a silent `return 1.0`.

## 4. Phased plan

### Phase 0 — Regression net + salvage the stranded Phase A  *(prerequisite for everything)*

1. **CI first**: add `renderer-shadow-planner-selftest` and `renderer-shadow-projected-diagnostic`
   to `--runtime-cases` in `commit-validation.yml` and `push-verification.yml` (the xvfb +
   software-GL harness already runs matrix cases). Commit golden screenshot baselines for the
   `shadow-regression` benchmark profile and pass `--require-reference` so absent references fail.
2. **Reconcile `shadowmap-rework` onto current main.** Fork point is 129 commits back and
   `draw_arb2.cpp` has since absorbed the 06-13 contract work — expect a manual re-apply per
   item rather than a clean rebase: A1 (in-shader slope+constant caster bias driven by the
   existing cvars, honoring debug mode 10; drop the inert `glPolygonOffset` state), A2 (two
   compiled point-caster variants — packed variant never references `gl_FragDepth`; compare
   variant always writes it), A3 (bind caster program once per pass; per-space uniforms only on
   space change), A4 (`r_shadowMapDepthCompare 1`, `r_shadowMapPointDepthCompare 1` defaults;
   LINEAR filters in compare mode; PCSS auto-selects the manual program), A5
   (`r_shadowMapSkipStencilShadows 1` with per-light sticky fallback on render-fail), A6
   (PCSS `min→max`), A7/A8 (branch docs + validation).
3. Quick wins riding along: fix divergent-flow `dFdx/dFdy` in `ShadowReceiverBias` (compute
   derivatives unconditionally at function top); delete dead `RB_ShadowMapRestorePolygonOffset`;
   fix both game-side undersized `memset`s (G4).

*Acceptance:* I2 passes for the first time (zero-bias → acne); banding visibly reduced at
default settings; frame CPU cost drops in mapped scenes (A5); CI red on any shadow self-test
regression. **Note:** `draw_arb2.cpp` is macOS-facing — run the `tools/tests/macos_*.py` sweep
after every phase touching it.

### Phase 1 — Bias contract correctness  *(kills acne/peter-panning structurally)*

1. **True normal-offset bias**: offset the shadow-coordinate evaluation point along the
   interpolated geometric normal, scaled by per-cascade world texel size, in
   `shadow_interaction.vs` before plane evaluation. Keep depth-space bias as the residual term.
2. **Fix world-texel derivation for projected lights** (B3): derive from the light-space crop
   footprint back-projected to world (available from `ndcMaxs-ndcMins` × frustum dimensions),
   not `lightRadius`. This also makes the texel-size debug output truthful.
3. **One depth normalization for texel bias** (B4): falloff-depth extent everywhere
   (single-cascade, CSM, fallback), so per-cascade bias scales continuously across splits.
4. **Cull policy** (C4): respect material cull in caster passes (disable cull for
   `CT_TWO_SIDED`, flip for `CT_BACK_SIDED`, mirroring `GL_Cull`); document the facing
   convention at the four call sites; add `r_shadowMapCasterCulling 0|1|2` (off/back/front) with
   front-face culling as a deliberate, per-material-overridable anti-panning option for closed
   meshes.
5. **Clamp, don't discard**, at the caster depth-range boundary; move the alpha fetch above the
   non-uniform discard (derivative correctness at `#version 110`).
6. **Point near-plane** (C5): enable `GL_DEPTH_CLAMP` where available; otherwise clamp
   `vShadowDepth`-equivalent radial depth for inside-near casters (pancake); shrink the 16-unit
   near.
7. **fp16 point precision** (S4): floor the point receiver bias by the storage format's ULP at
   depth≈1, or prefer the depth-compare cube path by default where GLSL 1.30 exists.
8. **I3 self-test**: assert depth-row/far-function pairing at startup.

*Acceptance:* contact shadows hold at grazing angles on the airdefense2 benchmark without
detaching (screenshot diff); bias heatmap (mode 7) shows smooth per-cascade transitions.

### Phase 2 — Coverage parity: nothing loses shadows when maps turn on

1. **Parallel lights** (C1): immediately fail-safe — classification-level block of the point
   cube path for `parms.parallel` lights (route to stencil, count in report). Then implement a
   **directional orthographic cascade path**: ortho fit along the light direction over the view
   frustum slices, cascade-texel snapping per I5, same falloff-depth storage convention, reusing
   the existing atlas tiles/receiver uniforms. This is the largest new feature in the plan and
   the key to Q4 outdoor maps.
2. **Translucent casters** (C2): default-parity policy — under maps, admit
   `MC_TRANSLUCENT + MF_FORCESHADOWS` (and the `r_stencilTranslucentShadows` class) as
   **binary alpha-thresholded depth casters** by default (cheap, matches stencil parity), with
   the existing moments pipeline remaining the opt-in high-quality tier. Resolve the policy in
   one table so stencil and map admission can never diverge silently again.
3. **Translucent receivers** (C3): DEFERRED to Phase 5. Implementation review found the
   plan-stated approach unsound: translucent interactions render through material *stages*
   (per-stage blend modes), not the interaction receiver program, so they cannot be routed
   through it. The stencil path shadows them via the stencil buffer masking arbitrary stage
   draws — the mapped equivalent is a screen-space shadow mask, which belongs with the Phase 5
   atlas architecture. Until then translucent receivers under mapped lights stay unshadowed
   (retail stencil behavior before r_stencilTranslucentShadows).
4. **Narrow the skinned-receiver exclusion** (C7) to genuinely GPU-skinned geometry (MD5R
   `primBatchMesh`/`skinToModelTransforms`); CPU-skinned MD5 receivers use the mapped path.
5. **Mask-pass resilience** (C8): per-surface failure tracking; stencil-fallback only the failed
   surfaces via the existing filtered-fallback predicate — eliminates double-lighting.
6. **FBO incompleteness** (C9): demote `FatalError` to per-light render-fail → existing sticky
   stencil fallback.
7. **LOD determinism and freshness** (C6): re-evaluate map admission per frame (the check is a
   few compares); replace `rand()` with a hashed, seeded jitter keyed on entity index + frame;
   add `SHADOWMAP_CASTER_REJECT_LOD`; invalidate interactions on shadow-relevant cvar toggles.
8. **Game-side candidates** (G1/G2/G3/G5) — canonical edits in `openQ4-game` first per repo
   rules: replace `com_machineSpec` gates on flashlight/projectile shadows with a dedicated
   archived cvar (e.g. `g_projectedLightShadows`) evaluated live, not latched at spawn; drop
   `noShadow` force-flags on gibs/burn/sink/client-moveables when shadow maps are active
   (dissolves are perforated-compatible); revisit `g_showPlayerShadow 1` default under maps
   (flashlight-cone suppression already works); make suppress-lightId non-zero by construction
   (`lightIndex*100 + entityNumber + 1` on both producer and light), fixing the sentinel
   collision.
9. Verify against retail assets (dev-procedure rule 1) which SP defs set `flashlightPointLight`
   / `noshadows` so the effective caster population is enumerated, not assumed.
   **Verified 2026-07-09**: retail defs set `flashlightPointLight 0` with authored projections
   (`def/weapons/blaster.def`, `machinegun.def`, `def/ai/char_marine*.def`, plus level defs) —
   the gun flashlight is a projected light in stock content, served by the projected path and
   its authored-single-projection classification guard.

*Acceptance:* A/B toggling `r_useShadowMap` on representative SP maps changes shadow *quality*,
never shadow *existence* (I1 report diff is empty); parallel-light maps show cascaded sun
shadows; ragdolls, gibs, moveables, movers, vehicles, AF corpses all cast.

### Phase 3 — Temporal stability and filtering quality

1. **Snapping rework** (S1): snap the crop center in the **cascade's own** texel units; quantize
   the crop extent to discrete steps (e.g. ×1.25 ladder) with hysteresis so the scale changes
   rarely instead of every frame; keep rotation-invariance by fitting in a light-axis-aligned
   frame. Add the I5 unit test that would have caught the current bug.
2. **Blend-band containment** (S2): extend each cascade's fit by its blend band so
   `SampleCascadeByIndex(i+1)` is always inside the next crop; remove the double pad (S5, one
   authoritative pad site).
3. Intersect cascade slice fitting with the light frustum (empty-overlap cascades stop wasting
   tiles; near-apex cameras stop tripping the mixed-w collapse).
4. Optional per-cascade Z remap (fit already measures `clipZExtent`) with matched receiver
   reconstruction — tightens depth precision and lowers required bias.
5. Filtering polish: `GL_TEXTURE_CUBE_MAP_SEAMLESS` on GL3.2+; early-out the second cascade
   sample when blend < 0.05 or first sample saturated; keep the rotated-Poisson kernel.

*Acceptance:* I5 test green; walk/strafe/turn capture on airdefense2 shows no edge crawl at
default settings; split boundaries invisible in cascade-debug blend view.

### Phase 4 — Scalability: simple to complex scenes alike

1. **Static/dynamic layer composition** (P2): per cached light, keep a persistent static-caster
   depth layer; per frame, copy it and overlay dynamic casters only. A settled corpse costs one
   small draw, not a full-scene re-render.
2. **At-rest reclassification** (P3): treat casters as static when `lastModifiedFrameNum` is
   stale for N frames even if `DM_CACHED`/callback-bearing (all three latch clauses addressed);
   game-side, ensure AF/animated entities stop calling `UpdateEntityDef` at rest.
3. **Single map render per light** (P4): render the global map once; satisfy noSelfShadow
   receivers by per-receiver masking (or accept local-caster shadows behind a cvar). Halves
   shadow raster cost in the common case.
4. **Per-face and per-cascade caster culling** (P5): cull caster bounds against each cube-face
   frustum and each cascade's NDC bounds; skip empty faces/cascades entirely.
5. **Importance-ordered budget** (P6): order update candidates by screen coverage × intensity ×
   staleness; round-robin aging guarantees eventual refresh (planner fairness history already
   exists — consume it here, making the planner authoritative for ARB2 scheduling and collapsing
   the two budget systems — resolves M4 ahead of Phase 5); grow the cache to a size-classed
   tile pool (Phase 5 formalizes it).
6. **Housekeeping** (P7): skip point caster-chain construction when the backend will refuse the
   light (frontend/backend admission-symmetry self-test); drop `glGetFloatv` readbacks; free
   render textures on cache expiry and after N frames of `r_useShadowMap 0`; add VRAM bytes to
   the SM cache report line.
7. Subview policy: skip or budget-cap shadow-map updates in mirror/remote subviews; reuse
   main-view maps where the signature allows; extend stats to subviews.

*Acceptance:* gameplay benchmark scenes with 15+ shadowed lights + 10 settled ragdolls hold
frame budget with zero I6 ladder violations; SM report shows cache hit-rate > 90 % for static
scenes; no per-frame full re-renders attributable to sleeping entities.

**Phase 4 outcome notes (2026-07-09):** items 1-2 landed as at-rest reclassification (the
settled-corpse cliff); per-cascade/per-face culling, cache capacity/pass-collapse, VRAM
visibility/purge, and budget stale-reuse landed; **point lights became the default mapped
path** (field testing showed Q4 content is point-dominated, so `r_shadowMapPointLights 0`
made the feature a near no-op). Three items are deliberately re-homed to Phase 5, where the
atlas makes them structurally simple instead of throwaway plumbing on the scratch/cube model:
layered static/dynamic composition (tile-to-tile copy in one texture vs per-face cube FBO
blit juggling), the planner-authoritative importance-ordered budget (the planner becomes the
allocator there anyway), and the subview single-cascade cache policy (tile sizing flows from
one allocator instead of three consistency layers).

### Phase 5 — One architecture: persistent atlas + modern unification

1. Persistent depth page atlas resource in the render graph (replacing the camera-MVP sidecar
   pass, M1); planner allocates tiles (its rect/budget machinery already exists), rendered up
   front before the interaction loop; static/dynamic composition from Phase 4 becomes per-tile.
2. ARB2 receivers consume tile rects (already supported via `uShadowAtlasRect`); the scratch/
   cache FBO model and its 8-slot ceiling retire.
3. Modern path: upload descriptors (already built) referencing real tiles; delete the dead XYWH
   contract or make it the one true rect convention (M5); fix the coordinate basis with one
   canonical view space + real inverse-projection reconstruction (M2); per-light shadow gating
   instead of frame-global fail-close, with cache-reuse escape restored (M3); freshness stamps
   (`descriptor.updateFrame`) validated at bind, fail-visible per I7.
4. Point lights: cube-array pool (GL3.3+) with dual-paraboloid atlas tiles as the GL2.1-class
   fallback.
5. Self-tests hardened: std140 layout vs GLSL struct assert, consumption-side sampling test
   (MAPPED descriptor's texture rendered this frame), no trivial-pass escape hatches (M5).

*Acceptance:* identical scene renders byte-comparable shadows on ARB2 and modern paths
(golden-image diff within tolerance); multiple mapped lights resident simultaneously; planner
stats equal rendered reality frame-for-frame.

**Phase 5 outcome notes (2026-07-10):** landed across four slices on `main` — 5a persistent
projected atlas (`50bf1f9e`), 5b layered static/dynamic composition (`1fb5f9b4`), 5c modern
consumption of the real atlas with per-light gating, the M2 basis fix, freshness stamps, and
self-test hardening (`688a0999`), 5d subview reuse-or-stencil policy, importance-ordered
update admissions, and translucent shadow-map receivers (C3 stencil parity). Two items are
**deliberately re-homed to the modern-renderer track** rather than this shadow roadmap:
the up-front atlas producer for fully modern-owned frames (today ARB2's interaction loop is
the atlas producer; a modern-owned frame that goes stale self-corrects through the per-light
gate with a one-frame legacy fallback, which is correct-if-suboptimal for an opt-in
diagnostics path) and the point cube-array pool (without a modern producer it would repeat
the M1 mistake — a resource nothing renders into; until it lands, the executor enforces the
single-cube constraint honestly by fail-closing on a second distinct consumable point
light). Both become worthwhile when the modern path graduates from sidecar to owner, which
is a modern-renderer milestone, not a shadow-quality one.

### Phase 6 — Product polish and the default flip

1. Menu exposure with localized `#str_*` entries: Shadows = Off / Stencil / Shadow Maps
   (Low/Medium/High/Ultra) mapping to size / cascade count / filter / update-budget bundles;
   presets stop silently reverting an explicit user opt-in.
2. Platform support matrix in `docs/user/shadow-mapping.md`: Apple GL2.1 = stencil only (T2),
   documented honestly; Steam Deck recommended settings (size 1024, budget 2, measured on RADV);
   macOS policy-test token added pinning the Apple-path shadow behavior.
3. Docs refresh: debug modes 12-14, effective-size clamps (unified or logged), bias-tuning
   guide rewritten for the now-live caster bias, silent-degradation warnings surfaced in the SM
   report (point-lights-off, compare unavailable, moments capability-gated).
4. Optional premium tier (post-flip, behind cvars): screen-space contact shadows to complement
   reduced bias; EVSM/MSM evaluation for selected light classes; shadow-aware volumetrics
   roadmap note.
5. **Default flip**: `r_useShadowMap 1` (then `r_shadowMapPointLights 1`) after SP/MP gameplay
   sign-off per the promotion-evidence process; stencil remains the archived rollback;
   release-notes entry per the changelog workflow.

*Acceptance:* full SP campaign + MP soak with maps on, zero I1 violations, performance parity
or better vs stencil on min-spec, golden-image suite green on Windows/Linux/Deck.

**Phase 6 outcome notes (2026-07-10):** items 2 and 3 landed — platform support matrix and
Steam Deck recommendations in `docs/user/shadow-mapping.md` / `docs/user/steam-deck.md`,
debug modes 12-14 and the SM metrics/SM modern report format documented, defaults tables
synced with the shipped cvar values, and `tools/tests/macos_shadow_policy.py` pins the
Apple-path capability gating plus the per-light stencil-fallback contract. Item 1 (menu
exposure) is **handed off**: the settings-menu/performance-preset system is under active
rework on a parallel branch of work whose own design notes keep shadow maps as a separate
opt-in, so the shadow quality bundles should be added when that rework lands rather than
racing it. Item 5 (the default flip) is **ready to execute pending the gameplay sign-off
its own acceptance gate requires**. Flip-readiness evidence collected on Windows/RTX-class
hardware, `r_shadowMapPointLights 1`, CSM preset vs stencil, 600-frame captures:

| Scene | Stencil | Shadow maps + CSM | Delta |
|---|---|---|---|
| `sp-airdefense1` (outdoor, CSM-heavy) | 114.3 Hz, p95 12 ms | 115.2 Hz, p95 13 ms | parity |
| `sp-storage1` (dense indoor, point-heavy) | 124.7 Hz, p95 11 ms | 116.7 Hz, p95 12 ms | -6.4% avg, +1 ms p95 |

The bounded-budget path (`r_shadowMapMaxUpdatesPerView 2`, importance-ordered) narrows the
indoor gap further and is the recommended Deck configuration. Everything else the flip
needs is green: 5-case bit-exact regression net, planner/projected/cluster-grid self-tests
with unconditional pins, macOS policy sweep, and per-light fail-closed degradation at
every capability boundary. To flip: set `r_useShadowMap` default to `1` in
`RenderSystem_init.cpp`, re-bless the golden references captured with maps on, and add the
release-notes entry; stencil remains the archived rollback via `r_useShadowMap 0`.

## 5. Pitfall coverage matrix

| Pitfall | Where this plan kills it |
|---|---|
| Peter panning | P0 functional caster bias (small, slope-aware) + P1 normal-offset + tight per-cascade depth (P3.4) + front-face-cull option for closed meshes (P1.4) — bias becomes small and structural, not a large constant |
| Shadow acne / slope issues | P0 slope-scaled caster bias + P1 correct texel-world metric (non-zero for spots at last) + one depth normalization + fp16 ULP floor + receiver-plane bias with defined derivatives |
| Shimmer / temporal instability | P3 cascade-texel snapping + extent quantization with hysteresis + I5 unit test + deterministic LOD (P2.7) |
| Cascade seams / blend-to-lit | P3 blend-band-inclusive fitting + single pad site + blend-region debug view (exists) |
| Light leaks at atlas/tile edges | Guard-band clamping (already correct — preserved) + clamp-not-discard casters (P1.5) |
| Cube-face seams | Seamless cube filtering + per-face guard (P3.5); dual-paraboloid fallback gets its own seam guard (P5.4) |
| Missing casters (popping, off-screen, two-sided, near-plane) | Conservative caster path (already right) + cull policy (P1.4) + depth clamp/pancake (P1.6) + per-frame LOD (P2.7) + parallel-light path (P2.1) |
| Silent shadow loss in complex scenes | I1 + I6 ladder + importance-ordered round-robin budget (P4.5) + static/dynamic split (P4.1) |
| Double-lighting / double-darkening | Mask-pass per-surface fallback (P2.5) + single-render-per-light masking (P4.3) + prelight handling (already right) |
| Undefined behavior / driver variance | P0 A2 point-depth variants + derivative ordering (P1.5) + I3/I7 self-tests + spec-strict Apple path documented (P6.2) |

## 6. Validation strategy

- Every phase lands with: build (Windows via `tools/build/meson_setup.ps1`, Linux CI), the
  renderer validation matrix shadow cases (CI-blocking from Phase 0), the gameplay benchmark
  shadow + shadow-regression profiles with committed golden references, and the macOS policy
  sweep (`tools/tests/macos_*.py`) whenever `draw_arb2.cpp`/`RenderSystem_init.cpp`/macOS docs
  are touched.
- In-game validation per repo rules: SP launch task into `game/airdefense2` (projected/CSM) and
  a point-light-dense map; MP launch task for the MP soak; never menu-only validation.
- New tests introduced by this plan: I2 bias-zeroing capture, I3 convention parity self-test,
  I5 snapping unit test, frontend/backend admission-symmetry self-test (P4.6), std140/GLSL
  layout assert + consumption freshness test (P5.5), determinism demo-replay check (I4).

## 7. Risks

- **`shadowmap-rework` reconciliation** is a re-implementation against a heavily-moved
  `draw_arb2.cpp`, not a merge; budget it as such (the branch is the reference spec, not the
  patch).
- **Directional cascades for parallel lights** are new surface area in a projective-space
  design; the falloff-depth convention must be preserved or I3 will catch the divergence.
- **Static/dynamic layer composition** interacts with the cache signature scheme; the
  order-dependent caster hash should first be made commutative (noted in audit: tie to
  frame-alloc pointer ordering is fragile).
- **Default flip** is gated on the promotion-evidence process; every phase is independently
  shippable behind the existing opt-in cvars, so no phase blocks the release train.
