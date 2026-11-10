# Vulkan shadow maps — OpenGL parity closure (staging plan)

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Status: S1-S9 LANDED (2026-09-02); every verified gap is closed. One item
is deliberately out of scope and is named below. S1, S2 and S5 change
runtime behaviour that token pins cannot fully cover, and still want the
user's own gameplay sign-off.

Goal doc for the remaining Vulkan shadow-mapping gaps after Phase
F2a/F2b + the 2026-07-24 shadow parity follow-up. Parent:
[2026-07-19-vulkan-phase-f.md](2026-07-19-vulkan-phase-f.md);
stencil/F3 record: [2026-07-20-vulkan-phase-g.md](2026-07-20-vulkan-phase-g.md).

Scope: bring `r_renderApi vk` shadow mapping to the behaviour, cost, and
diagnosability of the OpenGL path. Out of scope: translucent shadow
moments (`r_shadowMapTranslucentMoments`, experimental, default 0 — the
Phase F closure deliberately excludes it on Vulkan), the modern
clustered receiver path (`ModernClusteredLighting`, GL-only by design),
and the `r_useShadowMap` default flip (separate, user-gated). Translucent
moments landed on Vulkan later, on 2026-10-03; see the
[gap-closure ledger](2026-09-20-vulkan-gap-closure.md).

## Audit ground truth (2026-09-02)

Most `r_shadowMap*` cvars that never appear under `src/renderer/Vulkan/`
are still honoured there — they reach Vulkan through the shared
`R_ShadowMapProjectedFilterSettings`,
`R_BuildShadowMapProjectedLightState`, and `ClassicInteractionDomain`
seals. A cvar-name grep overstates the gap. Vulkan already had CSM,
the 1/5/9/13 PCF tiers, rotated Poisson, PCSS-lite, receiver-plane
bias, normal-offset, hashed alpha, caster culling, subview policy,
update budgets, and both the projected-atlas and point-cube static
caches. The verified remainder was:

| # | Gap | Landed as |
| - | --- | --------- |
| S1 | stencil volumes never elided | `22eb0060` |
| S2 | no cached-static + dynamic compose | `742c7b91` |
| S3 | no CSM static caching | `2bc4b5ff` |
| S4 | no receiver debug modes | `981583bf` (overlay still open) |
| S5 | no importance-ordered admission | `c188c798` |
| S6 | thin `r_shadowMapReport` | `b930d486` |
| S7 | `r_shadowMapPointHighPrecision` inert | `b930d486` |
| S8 | no GPU shadow-pass timings | `2d1567af` |
| S9 | `r_shadowMapDebugOverlay` OpenGL-only | `fe6db0e7` |

## Correction to the 2026-07-24 Vulkan stencil-elision revert

The Phase G "Same-frame fallback amendment" kept
`RB_ShadowMapResourcesKnownGood` conservative on Vulkan because an
Air Defense run had a light whose volume was elided before the backend
learned its admission could not be satisfied, and "the affected receiver
had to be skipped fail-closed".

That hazard no longer exists. `vk_Interactions.cpp` now draws the
receiver unshadowed when nothing else resolved — "a transient loss of
shadowing is preferable to dropping the light contribution for a
complete frame" — which is exactly the OpenGL contract
(`RB_ShadowMapMarkStencilFallbackSticky` then a stencil fallback over a
possibly empty volume chain). The conservative return was therefore
over-conservative relative to the code it guarded, and S1 flipped it.

Residual per-view Vulkan-specific miss sources after S1: atlas row-scan
exhaustion, point-cube pool exhaustion, and caster representability.
Each costs one unshadowed frame plus a sticky restore, which is the
cost OpenGL already accepts. The shared front-end mirror
(`R_ShadowMapLightWillUseShadowMaps`) already refuses to elide under a
non-zero `r_shadowMapMaxUpdatesPerView` or in a subview with a non-zero
`r_shadowMapSubviewPolicy`, so those two policies cannot strand an
elided light on either backend.

## Landed record (2026-09-02)

S1. `VK_ShadowMap_ResourcesKnownGood` reports the per-light-class
    generation truth it already tracked. Shadow-mapped lights no longer
    extrude and link silhouette volumes nothing draws. The fail-open
    receiver contract is pinned so the 2026-07-24 shape cannot return
    unnoticed.

S2. Cached-static + dynamic-caster composition for projected lights. A
    pass that publishes or restores a cache entry renders its static
    chains only; after publication and restore a second depth scope with
    loadOp LOAD draws just the dynamic chains into the same tile. A
    composed cache hit revalidates the caster pipeline and
    representability that an exact hit normally inherits from the update
    which published its signature.

    Composition is a legacy-walker feature on BOTH backends: the sealed
    domain sets `allowCacheReuse` false for any pass with dynamic
    casters, and OpenGL composes only in `RB_ARB2_DrawInteractions`.
    Vulkan keeps the old conservative rule while
    `r_rendererSharedWorldInteraction` can own the view, so a composed
    hit can never fail the domain's physical reconciliation. That
    coupling is load-bearing — see the comment at the `composeDynamic`
    assignment.

S3. CSM static caching behind `r_shadowMapCacheCSM`. Resident projected
    entries carry the physical block edge (`tileSize * atlasDiv`); the
    image is created at that edge, a slot reused at a different edge
    retires its image first, and the edge joins the entry's identity so
    a lookup cannot return a differently shaped block. Reuse restores
    the resident fit along with the tiles, so it is self-consistent but
    deliberately stale — which is why the cvar defaults off.

S4. Receiver debug modes in both Vulkan interaction shaders, driven
    through the shadow ABI. Coordinate rejection moved into a shared
    `ProjectShadowCoord` so the invalid-mask view classifies exactly
    what sampling rejected; the selected cascade and split blend are
    recorded during sampling so a view describes the sample the lit path
    took. Mode 10 is caster-side and zeroes the shadow pass's offsets.
    Modes 13/14 upload reason 0 because Vulkan admits shadow maps per
    light, not per receiver surface.

S5. Importance-ordered update admission. Cost is the ownership maps a
    light would render fresh; score is screen coverage, staleness of its
    newest resident content, and whether the camera stands inside the
    light. The estimate is side-effect free (read-only peers of the
    cacheability test, both resident lookups, and the history lookup),
    because the scheduling walk runs afterwards and would otherwise see
    state it did not create.

S6. `r_shadowMapReport` level 1 gains admission denials separately from
    an exhausted budget, tiles rendered against blocks allocated, cube
    faces, and resident memory; level 2 adds a per-light line naming
    each ownership's decision.

S7. `r_shadowMapPointHighPrecision` is documented OpenGL-only and
    announced in the Vulkan report. It also no longer partitions the
    Vulkan point cache, where toggling it discarded every resident map
    without being able to change a depth cube's contents.

S8. GPU shadow-pass timings. Timestamp spans measure the pass in the two
    phases OpenGL reports: `map` (the fresh atlas scope, the compose
    scope, and the point cube faces, the same grouping GL uses) and
    `reuse` (the resident publish and restore transfers).

    OpenGL brackets each phase with `glFinish` under
    `r_shadowMapGpuSyncTimings`. Vulkan structurally cannot: the pass is
    being RECORDED, so nothing is submitted to wait for. The synchronized
    mode is applied at readback instead, where it means no sample is ever
    dropped rather than a stall for accuracy -- the wait is gated on an
    age past which the frame loop has already waited that slot's fence,
    so it returns immediately. That is a better trade than `glFinish`,
    but it is not the same behaviour.

    Three failure modes are closed deliberately: a span whose command
    buffer was never submitted ages out instead of being waited on; a
    span opened but never closed is reclaimed instead of leaking its
    query pair; and ring pressure degrades to a dropped sample, never to
    a stall. Every span opens outside a dynamic-rendering scope, because
    resetting its query pair inside one is illegal.

S9. `r_shadowMapDebugOverlay`. The mini-map and its stats readout, drawn
    at the end of the interaction pass where `RB_ARB2_DrawInteractions`
    draws them, from one call site that covers both interaction walkers
    and the views where neither drew a light.

    Three pipelines over one vertex stage that builds its quad from
    `gl_VertexIndex`, so the overlay allocates nothing. The two panel
    variants differ only in the view type they declare for set 0
    binding 2, which is the same shadow receiver set layout the
    interaction pipelines use — the published atlas set and the point
    cube sets bind unchanged. The text variant declares no sampler at
    all, which is what lets the "NO MAP" readout draw when there is no
    shadow resource to bind, and keeps the 5x7 font in exactly one
    shader instead of three.

    Nothing is captured while the shadow pass runs, unlike the OpenGL
    driver's `RB_ShadowMapDebugOverlayCapture`: the per-view light table
    survives until the next `PrepareViewLights`, so the overlay selects
    from it afterwards. `vkShadow.preparedView` is what makes that safe —
    shared ownership can reach a view that prepared nothing at all, and
    the previous view's table must not be displayed as this view's.

    Two things the overlay must prove before it samples. The render
    scope: the shadow pass interrupts it and can fail to resume, so
    `VK_Exec_MainRenderingScopeOpen` gates every recorded command. The
    image layout: both descriptor families declare
    `DEPTH_STENCIL_READ_ONLY_OPTIMAL`, so a light whose atlas or cube did
    not end the pass in that layout is skipped rather than sampled
    through a descriptor that disagrees with the image.

    Two deliberate differences from OpenGL. The panel's cascade grid is
    computed in panel-local space while only the sample coordinate comes
    from the light's atlas block, so the grid lines up with the panel's
    own edges wherever the block was allocated; the GL fragment program
    grids on the slot UV, which drifts once the slot is not at the
    atlas origin. And the point panel reads native depth directly,
    because Vulkan cubes never carry the packed two-channel encoding
    `r_shadowMapPointHighPrecision` selects on OpenGL (S7).

    The readout carries Vulkan's own accounting rather than a
    transliteration of the GL counters: the selected pass's cache
    decision and caster split, then the view's cache hits, fresh
    updates, composed passes, tiles, cube faces, and the three fallback
    classes S5 and S6 separated.

## Deliberately out of scope

- Translucent shadow moments stay excluded on Vulkan, per the Phase F
  closure.

## Validation

Build plus the token-pinning suite; no in-game runs in this track.

```
powershell -ExecutionPolicy Bypass -File tools/build/meson_setup.ps1 compile -C builddir
python tools/tests/renderer_vulkan_shadow_compatibility.py
python tools/tests/renderer_vulkan_world_interaction_compatibility.py
python tools/tests/vk_shader_header_pin.py
python tools/tests/macos_shadow_policy.py
```

Each stage extended `renderer_vulkan_shadow_compatibility.py` with pins
for the contract it introduced, and each new pin was checked by breaking
the source it guards and confirming the failure. Token pins cannot cover
runtime behaviour, so S1 (lights lose their stencil volumes), S2 (moving
casters compose over cached tiles) and S5 (which lights spend a limited
budget) still want the user's own gameplay sign-off before the
`r_useShadowMap` default flip is reconsidered.
