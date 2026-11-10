# Shadow Mapping Rework — Diagnosis and Plan (2026-06-12)

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

This plan supersedes the artifact-level guesses in `docs/dev/shadowmapping-issue-triage.md` and
the strategy proposals (`shadow-mapping-assessment-30-04-2026.md`, `shadowmapping-new-improvements.md`)
with a code-verified diagnosis, and defines the phased rework toward shadow maps becoming a
worthy default replacement for stencil volumes.

## Verified diagnosis (what is actually broken)

Severity-ordered, every item verified directly in the current tree:

1. **Caster-side depth bias has never worked on the projected path.**
   `shadow_proj_caster.fs` writes `gl_FragDepth` from the falloff-plane depth (required: the
   shadow projection matrix has a zero Z row, `RB_ShadowMapClipPlanesToGLMatrix`), and per GL
   spec a shader-written fragment depth **bypasses `glPolygonOffset` entirely**. The
   `glEnable(GL_POLYGON_OFFSET_FILL)` + `glPolygonOffset(...)` state in `RB_RenderShadowMap`
   is inert, `r_shadowMapPolygonFactor/Offset` are no-ops, and debug mode 10
   ("caster polygon offset off") toggles nothing. All acne suppression therefore leans on
   receiver-side bias, which is exactly the acne↔Peter-Panning deadlock the triage doc
   documented as "no cvar combination fixes it".

2. **Point caster fragment depth is undefined behavior on the default path.**
   `shadow_point_caster.fs` writes `gl_FragDepth` only inside a uniform branch
   (`uPointShadowDepthCompare > 0.5`). A shader that *statically* writes `gl_FragDepth` but
   skips the write on an execution path yields undefined fragment depth on that path — and the
   skip path is the **default** configuration. Inter-caster occlusion ordering inside the
   cubemap is undefined; on well-behaved drivers it degrades to rasterized depth, on others it
   produces garbage point shadows. (Also: when the compare branch *is* taken, polygon offset is
   bypassed as in item 1.)

3. **The modern (deferred-lite / forward+) path never samples shadow maps.**
   `R_ModernShadowPlanner_ModernReceiverSamplingAvailable()` is hard-coded `false`;
   `ModernClusterShadowVisibility()` in the modern shader library returns 1.0 ("fully lit") for
   mapped lights. Every shadowed frame therefore fail-closes modern visible replacement
   (`R_ModernGLExecutor_ModernVisibleShadowReceiversReady`). Root architectural cause: the
   legacy path renders each light's map into a **reused scratch/cached FBO immediately before
   that light's receiver pass**, so per-light maps are never simultaneously resident — there is
   nothing a clustered shader *could* sample. Fixing this requires the persistent atlas
   (Phase B), not a shader patch.

4. **Both shadow pipelines run on the CPU simultaneously.**
   `idInteraction::AddActiveInteraction` builds and links stencil shadow volumes
   (`vLight->localShadows/globalShadows`, including per-frame dynamic/turbo volume generation in
   `CreateInteraction`) for every shadow-casting light even when the light will render shadow
   maps; the volumes are discarded unless the rare backend fallback triggers. With
   `r_useShadowMap 1`, animated scenes pay full silhouette/volume cost for nothing.

5. **Filtering quality is far below what the hardware gives for free.**
   The shadow depth textures are created `TF_NEAREST` and stay nearest even in compare mode, so
   every PCF tap is a hard binary compare (`r_shadowMapDepthCompare` also defaults off). A
   13-tap kernel yields 13 visible bands. Compare-mode samplers with `GL_LINEAR` provide
   hardware 2×2 PCF per tap at the same cost — the single biggest quality win available.

6. **Minor verified defects.**
   - `R_ClassifyShadowMapCasterReject` (Interaction.cpp) misreports translucent casters that
     were rejected by cast/LOD checks as `TRANSLUCENT_UNSUPPORTED` (unconditional early return).
   - `EffectiveShadowFilterRadius()` (shadow_interaction.fs) computes the PCSS guard radius with
     `min(PCSSMaxRadius, PCSSLightRadius)` — under-guards whenever the filter clamp exceeds the
     search radius (default 8 vs 4); should be `max`.
   - Per-surface `glUseProgramObjectARB(bind)/(0)` churn and redundant per-surface uniform
     uploads in `RB_ShadowMapDrawCasterChain` (model rows + depth row only change per space).

Falsified during verification (claims from earlier docs/agent passes that do **not** hold):
- The projected caster/receiver depth conventions are consistent (both evaluate the same
  local-space falloff plane; the un-divided storage convention is correct and robust).
- Translucent moment variance math is correct for layered casters and floored by
  `uTranslucentShadowMinVariance` for the single-layer case.
- `GL_TEXTURE_COMPARE_MODE` is correctly toggled per sampling mode (no undefined-sampler bug).

## Architecture assessment

**Is the falloff-depth projective design right for idTech4 content?** Yes. Q4 projected lights
are authored as S/T/Q projection + falloff; using the light's own projective space for the map
and the authored falloff axis as linear depth means: bias is uniform across the volume (falloff
units), receivers already carry the exact plane equations, no second depth convention exists,
and `w≈0` instability is confined to the S/T divide where guards already exist. CSM as a
view-slice crop of that projective space is unusual but sound. Point lights correctly use
radial distance vs a padded `light_radius` envelope. Prelight (`_prelight`) models are correctly
treated as stencil-only inputs; shadow-map casters draw real ambient geometry, and
`noShadows/noSelfShadow/shadowLOD/spectrum/depth-hack` semantics are carried over. The asset
contract is respected.

**Is the pipeline suitable, or does it need rework?** The *per-light render→sample* flow inside
the ARB2 interaction loop is fine as the compatibility path, but it is the thing that blocks
modern-renderer unification (defect 3) and per-frame map residency. The end-state is a
**persistent per-frame shadow page atlas** rendered up front, with per-light descriptors
(matrices, tile rects, bias) in a UBO — the legacy receiver path keeps working (it already
addresses tiles via `uShadowAtlasRect`), and the modern clustered shaders gain something real to
sample. `ModernShadowPlanner` already computes budgets/tiles/matrices for exactly this and is
currently write-only; it becomes the allocator.

**Sharing with stencil volumes** is already correctly minimal: caster *selection* shares the
interaction lists and cull info (right), geometry does not (volumes vs ambient tris, right).
The wrong sharing is temporal — both pipelines paid for every frame (defect 4).

## Phase A (this change): correctness + quality + cost

| # | Item | Files |
|---|------|-------|
| A1 | Functional caster depth bias: slope-scaled + constant offset applied to `gl_FragDepth` in the caster shaders (exact `glPolygonOffset` semantics: `factor·max|dz/dxy| + units·2⁻²⁴`), honoring debug mode 10; drop the inert polygon-offset GL state on the projected pass | shadow_proj_caster.fs, draw_arb2.cpp |
| A2 | Point caster depth variants: default variant never writes `gl_FragDepth` (defined behavior, working polygon offset, early-Z); compare variant (compile-time define, generation-tracked like the receiver) always writes radial depth + manual slope offset | shadow_point_caster.fs, draw_arb2.cpp |
| A3 | Bind caster programs once per pass; move per-space uniforms (model rows, depth row) to space changes | draw_arb2.cpp |
| A4 | Hardware-compare by default: `r_shadowMapDepthCompare 1`, `r_shadowMapPointDepthCompare 1`; compare-mode samplers switch to `GL_LINEAR` (hardware 2×2 PCF per tap), manual paths stay `GL_NEAREST`; PCSS-lite (`r_shadowMapFilterMode 2`) auto-selects the manual path instead of silently breaking | draw_arb2.cpp, RenderSystem_init.cpp |
| A5 | Skip stencil volume linking + dynamic volume generation for lights that will render shadow maps (`r_shadowMapSkipStencilShadows`, default 1), with per-light sticky fallback on backend render-fail and auto-disable when `r_shadowMapMaxUpdatesPerView > 0`; static interactions keep one-time volume creation so fallback stays instant for them | Interaction.cpp, tr_light.cpp, draw_arb2.cpp, tr_local.h, RenderSystem_init.cpp |
| A6 | Minor fixes: caster-reject reporting fall-through, PCSS guard `min→max` | Interaction.cpp, shadow_interaction.fs |
| A7 | Docs: user shadow-mapping guide (new defaults, functional caster offset, new cvar), release-completion entry | docs/user, docs/dev |
| A8 | Validation: build, renderer validation matrix self-tests, gameplay benchmark `game/airdefense2` (projected/CSM) and point-light scene with screenshots, stencil-default regression run | tools/tests |

## Phase B: persistent shadow atlas (next)

- One persistent depth atlas (target 4096² D32, tiles 256–1024) owned per frame; planner-driven
  tile allocation (`ModernShadowPlanner` becomes the allocator; budget cvars already exist).
- `RB_RenderShadowMap`/`RB_RenderPointShadowMap` render into assigned tiles up front (before the
  interaction loop); receiver passes consume tile rects (already supported by the shaders).
- Static cache becomes tile residency (no FBO juggling); CSM tiles stay view-fitted.
- Point lights move to a small cube-array pool (or dual-paraboloid tiles in the atlas as the
  GL3.3 fallback) so multiple point lights stay resident.

## Phase C: modern receiver sampling (unblocks modern-visible shadowed frames)

- Upload the planner's descriptors (policy, tile rect, matrix rows, bias, type) to the
  `shadowDescriptors` UBO/SSBO already declared in the render graph.
- Implement real sampling in `ModernClusterShadowVisibility()` (projected first, point second);
  flip `R_ModernShadowPlanner_ModernReceiverSamplingAvailable()` to a capability check.
- Keep fail-closed gating for anything not yet sampled (cascade blend parity, translucent).

## Phase D: default flip and premium quality

- Flip `r_useShadowMap 1` (and eventually `r_shadowMapPointLights 1`) after SP/MP gameplay
  sign-off per the existing promotion-evidence process; stencil remains the rollback.
- Optional: screen-space contact shadows to complement reduced bias; evaluate EVSM/MSM only for
  selected light classes after the atlas lands.
