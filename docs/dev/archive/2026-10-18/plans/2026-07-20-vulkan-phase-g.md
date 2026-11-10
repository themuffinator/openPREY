# Vulkan Phase G — stencil shadows, fog/blend lights, light-grid, F3 (staging plan)

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Status: recon complete (docs/dev/plans/phase-g-recon/ — READ THOSE FIRST);
G1 staged.
Status update (2026-09-18): G1, G2, and F3 landed (see the landed record
below); G3 stayed an audit, and Vulkan still has no light-grid pass.
Parent: [2026-07-16-vulkan-renderer.md](2026-07-16-vulkan-renderer.md) Phase G;
Phase F record: [2026-07-19-vulkan-phase-f.md](2026-07-19-vulkan-phase-f.md).
Milestone: retail-default shadows (r_shadows 1, r_useShadowMap 0) render on
Vulkan via stencil volumes; fog and blend lights draw; F3 (folded in from
Phase F) guarantees a stencil fallback when a shadow-map pass cannot own a
light.

## Decisions locked by recon (phase-g-recon/stencil-pass.md)

- G1 = the RB_StencilShadowPass/RB_T_Shadow port. All stencil state is
  core-1.3 dynamic (vkCmdSetStencilTestEnable/Op/CompareMask/WriteMask/
  Reference with face masks) — no pipeline-cache growth; the volume draw
  needs ONE new pipeline (shadowCache_t vec4-position vertex input,
  color writes off via colorWriteMask-off pipeline variant, depth LEQUAL
  no-write, depth bias from r_shadowPolygonFactor/-Offset via the
  existing dynamic bias).
- Volume vertex shader ports VPROG_STENCIL_SHADOW: w==1 verts stay at
  the model position, w==0 verts project away from the local light
  origin to infinity (the infinite projection with the clip-z fixup
  already in place; verify far-cap clipping under the [0,1] remap).
- Per-surface index-count selection ports RB_T_Shadow exactly:
  r_useExternalShadows ladder, DSF_VIEW_INSIDE_SHADOW, viewInsideLight +
  shadowCapPlaneBits/SHADOW_CAP_INFINITE → numIndexes vs
  numShadowIndexesNoCaps vs NoFrontCaps, external flag.
- Stencil sequences (two-sided single pass, the default under vk since
  wrap ops + separate face state are core): preload z-fail for internal
  volumes (front KEEP/DECR_WRAP/DECR_WRAP + back KEEP/INCR_WRAP/
  INCR_WRAP, one draw), then z-pass (front KEEP/KEEP/INCR_WRAP + back
  KEEP/KEEP/DECR_WRAP, one draw). frontSidedFace honors isMirror. The
  mapping must account for the vk negative-height viewport winding
  convention (front face CCW baseline) — derive against GL_Cull's
  glCullFace(GL_FRONT) semantics like the E cull mapping did.
- Exit contract: after a light's volumes draw, its interactions run with
  stencil test enabled, compare GEQUAL ref 128 mask 255, ops KEEP — the
  F1 interaction pass gains dynamic stencil enable per light (stencil
  ALWAYS/off for unshadowed and shadow-mapped lights, GEQUAL/128 after
  stencil volumes). Per-light stencil clear: scissored
  vkCmdClearAttachments (stencil aspect, value 128) over
  vLight->scissorRect when the light has shadow surfs.
- Light order per light: globalShadows → localInteractions →
  localShadows → globalInteractions (stencil ownership), translucent
  after with GEQUAL kept when r_stencilTranslucentShadows.
- Depth-bounds test (r_useDepthBoundsTest): requires the depthBounds
  device feature — enable if supported at device creation, use
  vkCmdSetDepthBounds (core dynamic when the feature is on) with the
  surf scissorRect zmin/zmax; skip silently when unsupported.
- Shadow volumes flow through the CPU-backed vertex cache like all
  Phase E geometry: tri->shadowCache holds shadowCache_t (vec4, stride
  16); a shadow variant of the ring uploader (vec4 stream) with the
  vert/index memo pattern. MD5R prim-batch shadow surfaces: skip
  (documented gap, packed VP path is Phase I).
- r_showShadows debug path: defer to Phase I rendertools.

## Stages

G1. Stencil shadow volumes + interaction stencil integration (above).
    Exit: q4dm2 + SP smoke with defaults (r_useShadowMap 0) show volume
    draws (one-shot bring-up evidence) and stencil-tested interactions,
    validation-clean; r_shadows 0 kills them; menu/2D unregressed.
G2. Fog + blend lights per phase-g-recon/fog-blend.md: RB_STD_FogAllLights
    port (fog plane S/T texgen math, _fog/_fogEnter textures, frustumTris
    caps), blend-light stage walk over lightProject texgens.
G3. Light-grid: per phase-g-recon/lightgrid-misc.md the draw-time path is
    gated off under the vk pins (GLSLProgramAvailable false) — verify and
    record the evidence; no implementation expected this phase.
F3. (folded in) RB_ShadowMapResourcesKnownGood per-light-class honesty +
    the sticky fallback contract (lightDef->shadowMapStencilFallbackSticky
    set exactly like the GL backend on caster/receiver failure), keeping
    the r_shadowMapMaxUpdatesPerView coupling and same-frame stencil
    availability — now meaningful because stencil volumes exist as the
    fallback.

Exit: retail-default lighting+shadows+fog on Vulkan for q4dm2 and SP
smokes, validation-clean, both r_useShadowMap states correct, GL default
untouched; full gate + Linux leg; user visual soak remains the promotion
gate (Phase J).

## G3 audit — light-grid rendering is inert under the vk pins (no work this phase)

Verified against the code (recon: phase-g-recon/lightgrid-misc.md §1-2):
- The entire draw-time light-grid path lives in the excluded
  draw_common.cpp (RB_STD_LightGridIndirect :9142, inline variant :9085,
  the dedicated lightgrid_indirect.fs GLSL program) — not compiled into
  the vk module at all.
- Every availability gate keys on `glConfig.GLSLProgramAvailable`, which
  is NEVER set under vk (its only assignment is the GL extension probe
  RenderSystem_init.cpp:1141 that VK_InitRenderDevice replaces; it stays
  false from zero-init). `RB_STD_LightGridInlinePassAvailable` (:8974)
  and `R_ScenePackets_DrawSurfLightGridEligible` (ScenePackets.cpp:1274)
  therefore reject universally; the RENDER_PASS_LIGHT_GRID packet pass is
  always empty. ModernGLExecutor hardcodes `lightGridModern = false`
  (ModernGLExecutor.cpp:6094) — it's a legacy-pass-only feature even on
  GL.
- Net: under vk nothing samples, streams, or draws light-grid data. This
  is a genuine parity gap (maps shipping .lightgrid files lose the
  default-on indirect overlay), but it is NOT reachable by flipping a
  gate — it requires a NEW vk pass (a SPIR-V port of the
  lightgrid_indirect.fs semantics + atlas materialization through
  vk_Image, which mechanically already works via AllocImage/
  SubImageUpload). Deferred: it is an additive lit-overlay feature best
  sequenced with the Phase H/I capture and long-tail work, not the
  retail-default lighting Phase G targets. Front-end light-grid parse +
  deferred image handles (RenderWorld_lightgrid.cpp) already run
  harmlessly under vk.
- Free-perf follow-up (Phase J note): with grids loaded,
  `AnyLightGridAvailable()` is true, so the per-drawSurf PointInArea BSP
  descent (tr_light.cpp:2024, gate tr_main.cpp:1278-1280) runs every
  frame with zero vk consumers — a vk-side skip until a real light-grid
  pass exists is free.

## Landed record (2026-07-22)

- G1 stencil shadow volumes: c98888ba (zero-finding review).
- G2 fog + blend lights: b471b4b5 (zero-finding review, fog evidence on
  game/storage2).
- F3 shadow-map resource honesty + sticky fallback: this commit —
  RB_ShadowMapResourcesKnownGood reports per-light-class truth keyed on
  tr.videoRestartCount; every shadow-pass failure path marks
  lightDef->shadowMapStencilFallbackSticky (GL parity). Verified on
  game/storage1 via the SP benchmark harness: defaults draw 15 stencil
  volumes with NO elision; r_useShadowMap 1 draws point shadows + "stencil
  elision active: 1 of 1 shadow-mapped lights carry no stencil volumes";
  zero validation both runs.
- G3: audit only (above).

## Same-frame fallback amendment (2026-07-24)

The F3 validation above proved the resource-ready path but not every
per-view admission outcome. A later Air Defense run exposed the missing
case: the front end had already elided a light's volume before the backend
learned that its atlas/update/material admission could not be satisfied,
so the affected receiver had to be skipped fail-closed.

Vulkan now deliberately keeps `RB_ShadowMapResourcesKnownGood` conservative
and retains stock per-surface stencil volumes through front-end submission.
Successful mapped lights still bypass their full volume draws, but an atlas
allocation failure, unsupported caster, late descriptor/pipeline failure, or
discretionary update-budget/subview miss can immediately execute the
already-linked stencil path when actual linkage proves that receiver
ownership complete. Dedicated supplement lists contain only casters absent
from a partial map, so mapped casters are not stamped again as hard
silhouettes. If map-only casters make stencil incomplete, the required map
bypasses those scheduling policies; only a genuine map failure fail-closes
that ownership. Required ownership maps are admitted before discretionary
maps can consume bounded resources, and a stencil-less subview target renders
its required maps despite the normal cache-only subview policy.
LOCAL and GLOBAL ownerships are resolved independently, late volume upload
failures invalidate only affected receivers, and a volume set proven empty
by view culling can fall back without a stencil attachment. Map-only casters
without a complete stencil representation remain fail-closed. Sticky
fallback remains part of the shared front-end volume-retention contract;
Vulkan still retries mapped admission on later views rather than treating a
transient per-view miss as permanent. This supersedes the earlier Vulkan
stencil-elision claim; correctness takes priority over the saved front-end
volume work until all per-view admissions can be proven before submission.

## World-interaction state follow-up (2026-07-24)

The optional `depthBounds` feature is now queried and enabled with the Vulkan
device when supported. Every compatible graphics pipeline declares the
depth-bounds enable/range state dynamically; stencil-volume rendering applies
each surface's clamped `scissorRect.zmin/zmax` and restores the disabled
0..1 baseline before returning. Unsupported devices retain the full-depth
stencil path.

Interaction and stencil-clear scissors now also follow `r_useScissor`
accurately. Enabled mode uses the surface/light rectangle; disabled mode
retains `RB_BeginDrawingView`'s view scissor rather than expanding a subview
to the framebuffer. All converted rectangles are clipped to the active
viewport and framebuffer before command recording.
