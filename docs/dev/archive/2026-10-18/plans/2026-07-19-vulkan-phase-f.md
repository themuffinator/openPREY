# Vulkan Phase F — interaction lighting + shadow maps (staging plan)

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Status: F1+F2 LANDED (2026-07-19/20) — F1 unshadowed interactions
(1a13441e + review fixes f156a978: entry-viewport baseline, split
vert/index memos), F2a projected shadow maps (d94750fb), F2b point-light
cube shadows (45aa208f), F2 review fix (6e94da92: translucent receivers
keep the shadow map per r_shadowMapTranslucentReceivers). Evidence on
q4dm2 with r_useShadowMap 1: "first point shadow light: 3 point shadow
lights, 512 cube faces" + "165 shadowed interactions across 3 shadow
lights", zero validation-layer messages; defaults (r_useShadowMap 0)
byte-identical behavior. The combined F2 adversarial review returned one
confirmed minor finding (fixed) and refuted nothing else — the
cross-frame image-sync and lifetime lenses found nothing.
SEQUENCING CHANGE: F3 (RB_ShadowMapResourcesKnownGood honesty + the
sticky stencil-fallback contract) moves AFTER Phase G1 lands stencil
volumes — the fallback contract is only meaningful once a stencil path
exists to fall back TO; eliding stencil volumes before then saves
front-end cost but has nothing to restore on failure. F3 is folded into
Phase G's exit criteria.
Documented scratch-first divergences (revisit in Phase J): combined
caster set per light (no LOCAL/GLOBAL stencil-ownership split),
constant-only caster depth offset, no CSM/static caches/translucent
moments/update budgets, radial-depth point convention (GL contract),
no packed-color fallback, single 2x2 hardware PCF tap, per-face
positive-height viewport CW-front winding (derivation in comments).
Recon ground truth: docs/dev/plans/phase-f-recon/.
Parent: [2026-07-16-vulkan-renderer.md](2026-07-16-vulkan-renderer.md) Phase F;
Phase E record: [2026-07-18-vulkan-phase-e.md](2026-07-18-vulkan-phase-e.md).
Milestone: q4dm2 lit by real per-light bump/diffuse/specular interactions on
Vulkan (validation-clean), then shadow maps; stencil shadows stay Phase G.

## Decisions locked by recon

- F1 = unshadowed interactions for ALL lights. This is exactly the GL
  behavior for lights without shadow surfs (stencil ALWAYS + interactions),
  and vk pipelines have stencil off entirely. r_useShadowMap defaults 0, so
  the shadow-map branch is opt-in later anyway.
- Loop skeleton = RB_ARB2_DrawInteractions (draw_arb2.cpp:11458-11666):
  per viewLight; skip IsFogLight/IsBlendLight/empty; opaque interactions
  (localInteractions then globalInteractions) at additive ONE/ONE +
  GLS_DEPTHMASK off + depth EQUAL; translucentInteractions at depth LESS.
  Runs between the depth fill and the ambient walks in Draw3DView
  (RB_STD_DrawView order: fill 9717 → interactions 9732 → ambient 9774).
- Must PORT from excluded TUs (GL-free rewrite in a new vk TU):
  RB_DetermineLightScale (tr_render.cpp:675-726),
  RB_CreateSingleDrawInteractionsFiltered walk (tr_render.cpp:875-1033),
  R_SetDrawInteraction (:782-829), RB_SubmittInteraction (:836-861).
  drawInteraction_t itself is in tr_local.h (shared).
- Walk vLight chains directly; ModernShadowPlanner is dormant under vk —
  do not depend on it. lightingCache is NEVER allocated under vk
  (backEndRendererHasVertexPrograms=true) — never reference it.
- Shaders: new interaction.vert/.frag SPIR-V pair. Normalize in-shader
  (no normalization cube map); SAMPLE the real specularTableImage for
  parity with the ARB2 lookup. Reference semantics: interaction.vfp param
  list at draw_arb2.cpp:11098-11169 and glprogs/material_interaction.*.
- Uniforms: per-draw payload ≈ 296B > 128B push floor. Keep the 128B push
  block for MVP + params; add a host-visible UNIFORM_BUFFER_DYNAMIC ring
  (vkRing_t pattern, 256B-aligned slices) for the interaction block
  (origins, lightProjection[4], bump/diffuse/specular matrices, colors).
- Descriptors: reuse the existing per-image single-sampler set cache —
  pipeline layout = 6 identical image-set slots (1=bump, 2=falloff,
  3=lightProjection, 4=diffuse, 5=specular, 0=specularTable) + set 6 =
  dynamic UBO. One vkCmdBindDescriptorSets with 6 cached sets + the UBO.
- Pipeline: one interaction pipeline (blend fixed ONE/ONE) + full
  idDrawVert vertex input (xyz@0, color u8x4@12, normal@16, tangent0@32,
  tangent1@44, st@56); depth func/write via the existing dynamic state
  (EQUAL opaque / LESS translucent), cull per material as in the ambient
  walk; scissor per surface (vLight->scissorRect ∩ surf scissor matches GL
  per-surface behavior — GL sets light scissor only in the stencil-clear
  path, per-surface scissors rule).

## Stages

F1. vk_Interactions.cpp: light loop + decomposition walk + lightScale
    port; interaction SPIR-V pair; UBO ring + 7-slot pipeline layout;
    Draw3DView insertion. Exit: q4dm2 visibly lit per-light,
    validation-clean, menu/2D and GL default unregressed, full gate green.
F2. Shadow maps, scratch-first: module-owned atlas VkImage (reuse
    vkCtx.depthFormat), tile allocator (row scan), depth-only caster
    pipeline (+ perforated alpha-test variant), point-light cube pass,
    comparison sampler in vk_Image, frame-scope suspend/resume with
    loadOp LOAD (split VK_Exec_Begin/EndMainRendering), receiver shader
    variants (projected + point), per-light shadow UBO block. Defer:
    static caches/compose, CSM (default 0), translucent moments (off),
    update budgets. Failure → draw unshadowed (no stencil until G).
F3. RB_ShadowMapResourcesKnownGood honesty (per light class) + the sticky
    fallback contract (lightDef->shadowMapStencilFallbackSticky) so the
    front-end can shed stencil volumes; keep the r_shadowMapMaxUpdatesPerView
    coupling. Only after F2 soaks.

Exit: interactions + shadow maps render correctly on Vulkan for q4dm2 SP
and MP smokes, validation-clean; GL default untouched; r_useShadowMap
default flip remains a separate user-gated decision.

## Shadow parity follow-up (2026-07-24)

The scratch-first F2 limitations have now been closed for stock opaque and
perforated shadows:

- projected, parallel/global, and point lights retain separate LOCAL/GLOBAL
  ownership resources, with GLOBAL aliasing only when no local caster chain
  exists;
- one to four stabilized projected cascades use contiguous atlas blocks,
  per-cascade caster culling, split blending, and cascade-aware receiver bias;
- fixed and stable-rotated PCF support 1/5/9/13 taps, projected lights also
  support PCSS-lite, and both projected and point receivers can select
  hardware comparison or raw-depth manual comparison at runtime;
- stock perforated casters preserve LESS/EQUAL/GREATER alpha tests, texture
  matrices, vertex color, and stable hashed-alpha coverage; unsupported
  dynamic/cinematic coverage never becomes an opaque substitute;
- ordinary triangle surfaces, packed MD5R interactions, and CPU-decoded or
  skinned stencil volumes participate in the same ownership policy;
- exact static-only projected and point maps can be reused across views,
  while discretionary update-budget or subview cache misses retain stencil
  for that frame; ownerships containing map-only casters schedule the required
  map beyond the nominal budget instead, and required maps are admitted before
  optional maps can consume the bounded light table, atlas, or cube pool;
- independent Vulkan depth-format/filter probing and fail-closed descriptor,
  pipeline, atlas, and cube readiness prevent partially valid maps from being
  sampled.

The original F3 assumption that the front end could generally elide Vulkan
stencil volumes was too optimistic: atlas capacity, per-view budgets, and
late material admission are not all knowable before front-end submission.
Vulkan therefore reports shadow-map resources conservatively and retains
volumes so a mapped-light failure can use a same-frame stencil fallback
when the required receiver ownership has a complete silhouette-volume set.
A set proven empty by per-view culling is also complete and needs no stencil
attachment. Mixed lights no longer have to choose between map-only and
stencil-only casters: the front end builds ownership-specific supplement
chains containing only casters absent from the map, and Vulkan samples the
partial map while applying those volumes through stencil in the same receiver
draw. This avoids both skipped light contribution and duplicate hard stencil
silhouettes for casters already represented in the map. Completeness and
supplement membership use silhouette volumes actually generated and
successfully linked, not caster eligibility alone. Mapped Vulkan lights
therefore build stock per-surface volumes even when a combined optimized
prelight exists. The combined optimized-prelight path remains available to
OpenGL and stencil-only Vulkan, but is never used as a partial-map supplement.
Update and subview fallback policies apply only when that actual linkage
proves a complete stencil result; map-only ownerships schedule the required
map beyond the nominal update budget. Required ownerships are processed before
discretionary maps, and subview targets without a usable stencil attachment
render required maps instead of selecting an impossible fallback. LOCAL and
GLOBAL receivers choose their complete map, hybrid map-plus-stencil result,
or fallback independently, so failure in one ownership never discards a valid
resource for the other.
Vulkan retains stock translucent receiver behavior. The experimental
translucent-moment caster extension is outside this closure and remains
disabled on Vulkan.

## World-interaction parity follow-up (2026-07-24)

The F1 interaction walk now carries the complete stock rendering contract,
not only the common one-bump/one-diffuse/one-specular case:

- every active light stage is decomposed against conditioned bump, diffuse,
  and specular surface stages with the stock texture matrices, color clamps,
  vertex-color mode, local origins, light projections, and ambient-light
  specular suppression;
- Raven `Customlit` and `Parallaxbump` stages participate once per active
  light stage and keep their authored maps under the legacy `r_skipBump`,
  `r_skipDiffuse`, and `r_skipSpecular` debug switches, matching the separate
  OpenGL custom-GLSL path;
- opaque LOCAL/GLOBAL receivers retain depth EQUAL and retail shadow
  ownership, translucent receivers use LEQUAL, and all interaction draws keep
  additive ONE/ONE blending, material culling, polygon offset, depth hacks,
  and fail-closed shadow selection; mixed mapped/stencil caster sets compose
  in one receiver draw through ownership-specific supplement volumes, and
  the lazy point-cube pool has one slot for both receiver ownerships of every
  admitted light rather than imposing a sixteen-map cutoff on dense worlds;
- non-RXGB bump images expose their authored red X-normal through the sampled
  alpha component, reproducing the legacy interaction-program input contract;
- `r_useScissor 0` keeps the view-level scissor established for the current
  main or subview, while the enabled path retains per-surface/per-light
  clipping.

A frozen-camera `game/core1` Windows x64 comparison exercised the normal
frame plus scissor, diffuse, specular, bump, whole-interaction, stencil-shadow,
and mapped-shadow variants. The matched normal Vulkan/OpenGL captures differed
by 0.056 mean RGB levels (0.40 RMS), and Vulkan validation reported no VUID,
validation error, fatal error, or device error. The source contract is pinned
by `tools/tests/renderer_vulkan_world_interaction_compatibility.py`.

The final staged runtime pass also exercised the dense `game/core1` point-light
case with shadow maps enabled: Vulkan prepared all 17 required ownership maps
and drew 419 interactions, including 250 shadow-receiving draws across nine
mapped lights, without an allocation fallback or validation error. Default
stencil regressions reached the same 419 SP interactions plus 230 volumes, and
an `mp/q4dm1` listen server drew 471 interactions plus 59 volumes through the
MP module.
