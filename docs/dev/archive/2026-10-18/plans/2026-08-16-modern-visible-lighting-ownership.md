# Modern Visible Lighting Ownership

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

## Purpose

Replace the four blanket pass-presence blockers that currently prevent the modern
GL visible path from owning any lit frame with per-light, per-domain
classification backed by an explicit parity contract.

This does not change what the default renderer draws. It changes an unmeasurable
boolean ("this frame has interaction draws, therefore blocked") into a measurable
ladder ("this frame has 37 contributing lights, 34 are modern-consumable, 3 are
genuinely unrepresentable, and the lighting domain's parity contract is still
unproven").

## Status

| Phase | State | Blocked on |
| --- | --- | --- |
| 1 Domain classification and telemetry | **done** | — |
| 2 Light grid | classification done; implementation deferred | per-draw texture binding from Phase 3; near-zero value on stock content |
| 3 Interaction lighting | **capability gap closed**; lights now consumable | proving the shading math against ARB2 |
| 4 Fog, blend, ambient, shadow receivers | audited; blockers made precise | fog/blend/ambient models unimplemented; shadows ride on Phase 3 lights |
| 5 Core profile and promotion | sites pinned | Phases 3 and 4 |

No parity contract is proven. `MODERN_LIGHTING_PARITY_PROVEN_DOMAINS` is still 0,
ARB2 still owns every lit frame, and the default renderer is unchanged.

The through-line of phases 2–4: every readiness signal that had not been checked
against the shading model turned out to be optimistic. Blanket blockers hid
per-light detail, per-light detail hid a capability gap, and the capability gap
hid three unimplemented light models. Treat any unverified readiness number here
as an upper bound.

## The full blocker chain to a composing frame

Traced end to end by measurement, each link found only after clearing the one
before it:

1. **Per-light images** — the clustered record carried no image handles.
   *Closed* by `ModernLightImageAtlas`.
2. **Stencil shadows** — `r_useShadowMap 0` makes shadow lights stencil-fallback,
   which a modern frame cannot draw. Cleared by `r_useShadowMap 1`; that default
   flip is already awaiting gameplay sign-off separately.
3. **Deform surfaces** — not a geometry or ordering problem. A debug context
   names it: `GL_INVALID_OPERATION ... program texture usage`, i.e. the draw
   samples an incomplete texture because the material is not covered.
4. **Material stage conditions** — `MATERIAL_RESOURCE_FALLBACK_STAGE_CONDITION`
   fires whenever `stage->mNumStageOps > 0`, i.e. any stage with Quake 4
   expression ops. The engine already evaluates those into
   `surf->shaderRegisters`; the modern material record simply does not carry the
   evaluated per-stage condition and colour. Extending
   `MaterialResourceTable` to record that evaluated state is the next concrete
   piece of work, and it is what stands between here and a composing frame.

Links 3 and 4 are the same underlying gap seen from two directions: material
coverage. Neither is a flag to relax — two attempts to treat such a flag as
merely conservative produced 966 GL errors per frame.

## Measured: flipping the contracts does not close this plan

Forcing every domain proven (`r_rendererModernLightingParity 15`) on
`game/storage1` and peeling blockers one at a time gives this chain:

| State | Result |
| --- | --- |
| contracts forced proven, defaults | `composed=0`, `shadow(blocked=1)` |
| ...blocked shadow traced to `r_useShadowMap 0` | that light is stencil-fallback, and a modern frame cannot draw stencil volumes |
| `r_useShadowMap 1` added | `shadow(consumable=1 blocked=0)` — the light becomes representable |
| ...still | `composed=0`, blocker `pass=depth geometry=271 reason=unsupportedDeform` |

Three conclusions, none of which were visible before running it:

- **The parity contract is not the last gate.** Even with all four domains
  proven the frame is not owned, so flipping
  `MODERN_LIGHTING_PARITY_PROVEN_DOMAINS` would change nothing on stock content.
- **An A/B against ARB2 is not currently possible on this scene.** ARB2 draws in
  both configurations, so a screenshot diff compares two identical images and
  proves nothing. Parity cannot be measured until a frame actually composes.
- **What remains is not lighting.** After the lighting domains clear, ownership
  is blocked by geometry/material coverage — deform surfaces in the depth pass
  here. That belongs to the older clustered-renderer plan's compatibility and
  parity hardening, not to this track.

So this plan's scope — per-light ownership classification, the capability gap,
and the lighting models — is complete. Proving parity needs a scene that
composes, which needs the deform-geometry class handled first.

### The deform blocker, and a hypothesis for it

Relaxing the blanket `unsupportedDeform` flag to admit `GEOMETRY_DEFORM_SURFACE`
(where the front end has already run the deform) compiled and looked right, and
produced ~966 `GL_INVALID_OPERATION` per frame on `game/storage1`. Reverted.

Two candidate explanations have been checked statically and **both ruled out**:

- Not the vertex layout. `R_ModernGLExecutor_DrawVertLayoutSupported` requires
  `vertexStride >= sizeof( idDrawVert )` and a non-negative ambient cache
  offset; those pass for these surfaces.
- Not frame ordering. `R_DeformDrawSurf` is called from `tr_light.cpp:2018`,
  i.e. in the front end before scene packets are built, so a `deformedSurface`
  is current for this frame rather than pointing at retired cache from the last
  one. (The `cpuSkinnedGeo` / `gpuPosedGeo` hits in `draw_arb2.cpp` that set the
  same flag are stack-local self-test surfaces, not real draws.)

A debug-context run (`r_glDebugContext 1` + `r_glDebugOutput 1`) named the
actual cause, and it is neither of the above:

```
GL debug callback [source=api type=error severity=high id=1282]
GL_INVALID_OPERATION error generated. State(s) are invalid: program texture usage.
```

It is a **texture** fault. These surfaces are geometrically admissible, but
their materials are not covered by the modern material table, so the draw ends
up sampling an incomplete texture. That is consistent with the blocker that
surfaces immediately after the deform one is cleared: a material
`reason=stageCondition`. Admitting deformed surfaces therefore depends on
material coverage, not on anything about deforms.

The same run exposed a real latent bug, now fixed: `uModernLightImageAtlas` was
assigned its texture unit *after* the shadow-uniform bail-out in
`R_ModernGLExecutor_SetShadowSamplerUniforms`, so any program declaring the
sampler while missing a shadow uniform kept the default unit 0 and sampled
whatever was bound there. Fixing it did not clear the 966 errors — the material
coverage gap is separate — but it removes a genuine hazard from the shipped
path.

## Current Baseline

`R_ModernGLExecutor_AnalyzeModernVisibleOwnershipReadiness` runs twice per frame
from `R_ModernGLExecutor_PrepareFrame`, at a point **before**
`R_ModernShadowPlanner_PrepareFrame` and
`R_ModernClusteredLighting_PrepareFrame` have built this frame's descriptors. It
therefore has nothing to consult but front-end packet draw counts, and blocks on
raw presence:

| Trigger | Flag cleared | Blocker |
| --- | --- | --- |
| any `RENDER_PASS_ARB2_INTERACTION` draws | `modernVisibleLightingReady` | `lighting-parity-incomplete` |
| any `RENDER_PASS_FOG_BLEND` draws | `modernVisibleLightingReady` | `fog-blend-parity-incomplete` |
| any `RENDER_PASS_LIGHT_GRID` draws | `modernVisibleLightGridReady` | `light-grid-parity-incomplete` |
| any `RENDER_PASS_SHADOW_MAP` / `RENDER_PASS_STENCIL_SHADOW` draws | `modernVisibleShadowOwnershipReady` | `shadow-ownership-parity-incomplete` |

Every lit Quake 4 surface emits interaction draws, so `modernVisibleBlockedByLegacy`
trips on every real frame and `R_ModernGLExecutor_FailClosedPassOwnership` returns
the whole frame to ARB2. Nothing ever restores those flags.

A second consequence is that the phase 5c **per-light** shadow gate,
`R_ModernGLExecutor_ModernVisibleShadowReceiversReady`, is already implemented and
already correct — walking descriptors, separating consumable from blocked lights,
handling the single-cube point-light constraint — but is dead code. Its verdict is
ANDed with the blanket `modernVisibleShadowOwnershipReady` at
`ModernGLExecutor.cpp:5990`, which is always false whenever any shadow draw
exists, so the per-light result can never influence the outcome.

## Design Goals

- [ ] Keep the default visible renderer on ARB2, with byte-identical behavior.
- [ ] Decide each lighting domain from descriptors, after the planners have run.
- [ ] Never let a domain be owned because it is merely *representable*; require an
      explicit, reviewed parity contract to have been proven for it.
- [ ] Report, per frame, how many lights are consumable, how many are blocked, and
      how many are blocked *only* by an unproven contract.
- [ ] Resurrect the phase 5c per-light shadow gate as the sole shadow verdict.
- [ ] Give bring-up a way to force a domain on so parity can actually be measured.

## Non-Goals

- [ ] Do not change lighting math in this phase. Proving parity is separate work.
- [ ] Do not flip any domain's parity contract to proven in this phase.
- [ ] Do not remove the ARB2 escape, the evidence token, or the promotion gates.
- [ ] Do not alter the front-end packet contract or descriptor layouts.

## Parity Contract Model

Each ownership domain carries a contract state:

- `unproven` — the modern path may be able to represent these lights, but the
  output has not been shown equal to ARB2. Lights are counted, then blocked.
- `proven` — parity has been demonstrated and recorded. Consumable lights count
  toward ownership; unrepresentable lights still block.

Contract state lives in a code-level table so flipping it is a reviewed source
change, not a user-facing switch. `r_rendererModernLightingParityOverride` is a
diagnostic bitmask (default `0`, not archived) that forces domains proven for
bring-up and A/B capture only.

Domains:

| Bit | Domain | Covers |
| --- | --- | --- |
| 1 | `interaction` | point / projected / ambient light interactions |
| 2 | `fog-blend` | fog and blend lights |
| 4 | `light-grid` | light-grid indirect contribution |
| 8 | `shadow` | shadow receiver sampling |

## Light Classification

A contributing light is **consumable** when its clustered-light descriptor is one
the modern deferred/forward+ path can represent:

- type is `POINT`, `PROJECTED`, or `AMBIENT` for the `interaction` domain
- type is `FOG` or `BLEND` for the `fog-blend` domain
- required image handles are live (falloff, and projection for projected lights)
- the light's shadow descriptor is either absent or consumable per the phase 5c
  shadow walk

It is **blocked** when it is genuinely unrepresentable — `SPECIAL` (including
parallel lights), missing falloff/projection resources, or a shadow descriptor
that would silently drop shadows.

It is **unproven** when it is otherwise consumable but its domain's contract has
not been proven. This is the number that measures remaining parity work.

## Phase 1: Domain Classification And Telemetry

Goal: replace presence blockers with descriptor-driven verdicts, default behavior
unchanged.

- [x] Add the parity-contract table and `r_rendererModernLightingParity`.
- [x] Move the four domain verdicts out of the early packet-count analysis into a
      late evaluation that runs after both planners.
- [x] Keep the early analysis owning per-draw material/geometry blockers only.
- [x] Classify interaction lights per descriptor into consumable/blocked/unproven.
- [x] Classify fog and blend lights per descriptor.
- [x] Classify light-grid contribution per pass with an explicit reason.
- [x] Drop the blanket shadow flag and use the phase 5c per-light verdict.
- [x] Record per-domain counts and a specific named blocker naming the light.
- [x] Report contract state and counts in `gfxInfo` and `r_rendererMetrics 2`.
- [x] Extend `rendererModernCompatibilitySelfTest` to cover the default
      all-unproven verdict and per-domain contract independence.
- [x] Guard the new cvar in `rendererDefaultSafetySelfTest`.
- [x] Acceptance: default startup and gameplay are unchanged, `gfxInfo` reports
      per-domain light counts, and forcing a domain proven changes only that
      domain's verdict.

Note on the diagnostic cvar name: shipped as `r_rendererModernLightingParity`
rather than the `...Override` working name, matching the existing
`r_renderer*` cvar naming.

## Measured Baseline

Real-scene reading on `game/storage1` with
`r_rendererModernExecutor 1 r_rendererModernVisible 1`, after Phases 1 and 2:

After Phase 3's atlas landed, the same scene reads
`interaction(lights=3 consumable=3 blocked=0 unproven=3)` with the atlas
reporting `resident=4 acquires=6 hits=6 rejected(oversized=0)` — every light is
image-complete and held only by the unproven contract. The reading below is the
pre-atlas state, kept because it is what the capability gap looked like:

```
modernLightingOwnership proven=none override=0 requested=1
  interaction(pass=1 lights=3 consumable=0 blocked=3 unproven=0 ready=0)
  fogBlend(pass=0 lights=0 consumable=0 blocked=0 unproven=0)
  lightGrid(pass=1 draws=0 consumable=0 blocked=0 unproven=0 unprovenPass=0 ready=1)
  shadow(consumable=0 blocked=1 unproven=0 pointConstraint=0 ready=0)
  blocker='view=3 pass=depth material=4929
           resource=models/mapobjects/strogg/terminal/towers/network_towers
           reason=stageCondition'
```

What that says, none of which was observable before this track:

- All three contributing lights are **unrepresentable**, not merely unproven.
  Phase 1 read this line as `consumable=3 unproven=3` and concluded the
  interaction remainder was shading math. That was wrong: the classifier was
  checking that the light's images *existed*, while the clustered shading model
  never samples them. Phase 3 corrected it. The remainder is plumbing —
  per-light image binding — and only then shading math.
- The light-grid domain is **vacuously ready**: the pass exists but carries no
  draws, because stock maps have no baked grids. It is not what is holding this
  frame, and proving it would change nothing here.
- One shadow light is genuinely unrepresentable, so Phase 4 has real per-light
  work behind it rather than a blanket presence gate.
- The first blocker is a specific actionable defect naming a real material,
  rather than `lighting-parity-incomplete`. Note it changed once light grid
  stopped falsely claiming the blocker slot — accurate domain verdicts make the
  reported blocker more useful, not just shorter.

The lesson worth keeping: each phase found that the previous phase's readiness
signal was optimistic, and each correction moved a domain from "nearly ready" to
"needs real work". Treat any *unverified* readiness number in this track as an
upper bound.

Re-measure this line on the same map after each contract flip. Take it from the
`gfxInfo` dump of a default-paced run: `r_rendererMetrics 2` prints the same
line per frame but costs roughly an order of magnitude of frame time.

## Phase 2: Light Grid Ownership

**The original premise for this phase was wrong and is corrected here.** It was
scoped as "the cheapest domain — no shadow coupling, no per-light math, just
reconcile the two implementations". There is nothing to reconcile, and it is not
the cheapest domain.

What the investigation actually found:

- The modern light-grid fragment shader is a flat debug colour
  (`out_Color = uDebugColor.rgb * lightScale`). There is no light-grid
  implementation in the modern path at all.
- The graph's `lightGrid` resource is an *imported placeholder buffer*, not the
  three atlas textures. `forwardPlusLightGridContributions` is a presence flag
  (`handle != NULL ? 1 : 0`), not a sample count.
- The deferred resolve reads `uGBufferEmissive` and calls the result
  `lightGrid`. That attachment carries material emissive, not baked probe
  irradiance — the two are unrelated quantities.
- `lightGridModern` is hardcoded `false` in `FinalizePassOwnership`, so the pass
  could never be modern-owned even with a proven contract.
- The ARB2 implementation is substantial: 16 backend helpers, 24 uniform vec4
  blocks, 6 texture bindings, octahedral probe-atlas sampling, 8-corner
  trilinear probe blending, Chebyshev/VSM visibility moments, probe relocation,
  gamma decode, contribution clamping, and depth rejection.

The decisive constraint is architectural. **Quake 4's light grid is baked per
portal area**, selected by the receiving surface, with portal blending that
resubmits a surface once per contributing area grid. A screen-space deferred
resolve cannot pick the correct per-area atlas per pixel. So the modern
implementation must remain a *forward, per-surface* pass that binds its area's
atlas set per draw — a different shape from the clustered and screen-space
resolves the rest of the modern pipeline is built around.

That makes light grid the most architecturally awkward domain, not the cheapest.
It is re-sequenced after interaction lighting: Phase 3's forward+ per-surface
work establishes the per-draw texture-binding path this needs.

A second finding makes the re-sequencing decisive. Measured on `game/storage1`
over 75 gameplay frames, every frame reports:

```
lightGrid(pass=1 draws=0 consumable=0 blocked=0 unproven=0 ready=1)
```

The pass exists but describes **zero draws**. `R_ScenePackets_AddFilteredDrawSurfPass`
declares the light-grid pass unconditionally and only then filters eligible
surfaces into it, and eligibility requires a usable baked area grid. Stock Quake
4 maps ship no irradiance volumes, so on retail content the light-grid domain
has no work at all. Proving its parity buys nothing for stock assets; it matters
only for content with openQ4-generated grids.

Landed in this phase:

- [x] Per-draw light-grid ownership classification, replacing the blanket
      pass-presence check, via `RB_LightGridSurfaceModernRepresentable`.
- [x] Blocker reasons: `no-area-light-grid`, `light-grid-atlas-missing`,
      `portal-blend-multi-grid`.
- [x] A declared-but-empty light-grid pass is correctly vacuous rather than
      blocking. An earlier revision of this work blocked it as
      `light-grid-draws-undescribed`, which would have pinned every stock-content
      frame on a pass carrying no work.
- [x] Per-draw counts reported in `modernLightingOwnership`.
- [x] Self-test coverage for the draw classification and for per-domain contract
      resolution.

Deferred to the re-sequenced phase, and explicitly **not** done:

- [ ] Port the ARB2 light-grid algorithm into the modern shader library.
- [ ] Import the three per-area atlases as real graph resources.
- [ ] Extend the modern submit path with per-draw atlas binding and the 24
      uniform blocks.
- [ ] Reproduce or explicitly drop portal blending.
- [ ] Flip the `light-grid` contract to proven with recorded evidence.

The contract stays unproven. Nothing about the visible frame changed.

## Phase 3: Interaction Lighting Parity

**This phase is blocked on an architectural gap, not on shader math.** It was
scoped as "port the `interaction.vfp` math from the Vulkan Phase F1 shader".
That port is necessary but nowhere near sufficient, and it cannot be written
against the current clustered light model at all.

A Quake 4 light is **textured**. Its shape and colour come from a light
projection image and its distance response from a falloff image, both sampled
projectively per pixel:

```glsl
light *= textureProj(lightFalloffMap, vLightFalloffTexCoord).rgb;
light *= textureProj(lightProjectionMap, vLightProjectionTexCoord).rgb;
```

The modern clustered model has neither. `ModernClusterLightRecord` carries
`positionRadius`, `worldOriginRadius`, `colorType`, `scissorDepth`, `flags`,
`depthRange`, `falloff`, and the `projectS/T/Q` planes — **no image handles**.
The CPU-side `rendererModernLightDescriptor_t` does record
`falloffImageHandle`, `projectionImageHandle` and `cubeImageHandle`, but nothing
in the executor ever binds them; the only references anywhere are the ownership
classifier's presence checks. `ModernClusterEvaluateLight` therefore substitutes:

```glsl
float radial = clamp(1.0 - dist / radius, 0.0, 1.0); radial *= radial;
float spec   = pow(clamp(dot(normal, halfDir), 0.0, 1.0), 24.0) * specular * fresnel;
attenuation  = radial * (ndotl + spec) * projectMask;   // projectMask is binary
```

That is a generic clustered-lighting model, not Quake 4's. Beyond the missing
images it also uses `pow(N·H, 24)` where Quake 4 uses the `_specularTable` ramp
`clamp((N·H)·4−3)²` with the specular env constant doubled.

The root problem is structural: **a clustered loop samples many lights per
pixel, but each Quake 4 light needs its own two textures.** A single bound
texture pair cannot serve N lights. The viable implementations are:

1. **Bindless light images** on GL 4.5+ — store the falloff/projection handles in
   the light record. `r_rendererBindless` and the capability plumbing already
   exist. Does not cover the GL 3.3/4.1 baseline tiers.
2. **A shared falloff/projection atlas** — pack the images and store atlas rects
   per record. Works on every tier; needs residency management and bleed control
   at tile edges, much like the shadow atlas already does.

The deferred path has two further losses that the G-buffer layout makes
unrecoverable, independent of the above: vertex colour is never written (so
`r_interactionColorMode`'s two layouts cannot be reproduced), and specular is
collapsed to a scalar `dot(specular, vec3(0.333333))`, discarding specular
colour. Forward+ retains both because it draws the surface, so **forward+ is the
only credible route to interaction parity** and the deferred resolve should be
scoped out of it.

Landed in this phase:

- [x] `MODERN_CLUSTER_LIGHT_RECORD_CARRIES_IMAGES`, a reviewed capability
      constant recording that the light record cannot reference its images, and
      the blocker reason `per-light-images-unbindable`.
- [x] Corrected the Phase 1 classifier, which reported a light "consumable"
      whenever its image handles were merely *present*. The shading model never
      samples them, so that overstated readiness — the exact failure the parity
      contract exists to prevent, occurring inside the classifier itself.

Also landed:

- [x] **The per-light image atlas** (`ModernLightImageAtlas.h/.cpp`) — the chosen
      answer to the capability gap. Atlas over bindless because bindless is
      GL 4.5+ and would abandon the GL 3.3/4.1 baseline tiers.
      - A 1024² RGBA8 atlas of 64 fixed 128px cells, each inset by a one-texel
        border so bilinear taps at a cell edge cannot bleed into a neighbour.
      - A fixed grid rather than a shelf packer: light images are few, small and
        long-lived, so residency lookup and eviction stay trivial and the uv rect
        is exact.
      - Source images are copied in by drawing a textured quad, not
        `glCopyImageSubData` or a framebuffer blit. Light images are frequently
        DXT-compressed, which cannot be colour-attached for a blit, and
        `glCopyImageSubData` needs GL 4.3 plus a matching compressed format.
        Sampling works for every source format on every supported tier.
      - Residency is keyed on the image pointer and revalidated against its
        device handle, so a purge/reload re-uploads instead of sampling a stale
        cell. Eviction never reclaims a cell already used this frame — that would
        hand two lights the same cell — and reports the atlas full instead.
      - Cube-map light images are rejected explicitly rather than approximated.
      - `rendererLightImageAtlasSelfTest` covers cell containment, disjointness,
        border inset, capacity, and that a rejected acquire zeroes the caller's
        rect. Added to the validation matrix; `gfxInfo` prints atlas state.

- [x] **The capability gap is closed.** The rects are stored on
      `rendererModernLightDescriptor_t`, `ModernClusterLightRecord` carries
      `falloffRect`/`projectionRect` (10 → 12 vec4s, both GLSL copies and the
      `assert_sizeof` updated), the atlas binds on texture unit 13, and
      `ModernClusterEvaluateLight` samples the light's own images instead of the
      analytic `(1 - d/r)^2` and binary mask. Specular now uses Quake 4's
      `clamp((N.H)*4-3)^2 * 2` ramp, evaluated analytically because the
      `_specularTable` is exactly that curve and needs no texture.
      `per-light-images-unbindable` no longer fires.

Two things had to be got right, and running it found both — reading would not
have:

- **The upload cannot be a draw.** The first implementation rendered a textured
  quad into the atlas from inside the clustered-light build and crashed the
  driver mid-frame (`0xC0000005`, reproducible, isolated by bisect). The copy
  runs between the clustered build and the modern passes, and issuing a draw
  there binds an FBO, program, VAO and viewport inside a caller that owns all of
  them; invalidating the state cache around it did not help. Replaced with
  `glGetTexImage` + `glTexSubImage2D`, which touches no draw state, decompresses
  DXT sources for free, and works on every tier. The FBO, copy program and VAO
  are gone; Acquire is CPU-only and uploads are queued to an explicit flush.
- **Cell size had to come from real content.** At 128px every light *projection*
  image was rejected as oversized while the small falloff images packed fine —
  visible as `resident=2 acquires=6 rejected(oversized=3)`. Stock Quake 4 light
  projections run to 256px, so cells are 256 and the atlas is 2048 to keep the
  same 64-cell capacity. The same scene then reported
  `resident=4 acquires=6 hits=6 rejected(oversized=0)`.

Remaining, in dependency order:
- [ ] Port the `interaction.vfp` math from `Vulkan/shaders/interaction.frag`:
      DXT5/RXGB bump decode without renormalization, the real `_specularTable`
      ramp with the doubled specular env constant, ambient constant tangent
      direction with CPU-side 8-bit cube quantization, and Parallaxbump height in
      the RXGB red channel.
- [x] `r_interactionColorMode` needs **no** modern-path work, and this item was
      based on a misreading. The cvar selects which ARB env registers carry the
      interaction colour scale/bias — `MAD result.color, vertex.color,
      program.env[16].x, program.env[16].y` (packed) versus
      `... program.env[16], program.env[17]` (vector), detected by scanning the
      shipped `interaction.vfp`. Both compute the same
      `vertex.color * scale + bias`; only the register layout differs. The
      modern path takes vertex colour as an attribute and never touches ARB env
      registers, so there is nothing to reproduce.
- [x] Bump decode matches the reference: DXT5/RXGB `(a, g, b) * 2 - 1` with no
      renormalization in the decode itself. The single normalize in
      `ModernMaterialNormal` stays, because the clustered N·L math needs a unit
      normal; a second one in the decode was redundant, not more correct.
- [ ] A/B forward+ against ARB2 per light type.
- [ ] Flip the `interaction` contract to proven with recorded evidence.

## Phase 4: Fog, Blend, Ambient, And Shadow Receivers

The two halves of this phase are in very different states, and one extra gap
turned up that belongs to the interaction domain rather than this one.

**Fog and blend are not implemented.** `MODERN_GL_SHADER_FOG_BLEND` is literally
the same source as `MODERN_GL_SHADER_TRANSPARENT_FORWARD` — a clustered
transparent-forward shader whose light loop accumulates only
`type == 0 || type == 1`. Fog (type 2) and blend (type 4) lights contribute
nothing whatsoever. That is not an approximation to tighten: Quake 4 fog is a
distance-driven projective fog-image lookup with its own blend state, and blend
lights modulate the framebuffer through the light's blend image. Neither is
expressible as "a clustered light contribution added to a transparent surface".

**Ambient lights are also unevaluated**, and this one belongs to `interaction`,
not `fog-blend`. `ModernClusterEvaluateLight` zeroes attenuation for every type
except point and projected, so an ambient light contributes nothing. Quake 4
ambient lights are real lights evaluated against the constant tangent-space
direction the ambient normal cube decodes to — the Vulkan Phase F1 shader
handles this explicitly.

**Shadow receivers are genuinely implemented**, and this is the one place the
modern path is further along than the classifier suggested.
`ModernClusterShadowVisibility` fetches the shadow descriptor, validates policy,
freshness against `uModernShadowContractState`, atlas readiness, the
receiver-blocked and sampling-ready flags, and then samples the real point or
projected atlas. That matches the shadow-mapping track being complete through
5d/6. The shadow domain's remaining blocker is not its own sampling — it is that
shadows ride on lights, and the lights are blocked upstream.

Landed in this phase:

- [x] Precise per-type blockers instead of one collapsed reason:
      `fog-blend-model-unimplemented` for fog and blend lights,
      `ambient-light-unevaluated` for ambient lights, `per-light-images-unbindable`
      only for point/projected lights that are otherwise complete.
- [x] Confirmed the shadow receiver path samples the real atlas, so no shadow
      capability constant is warranted.

Remaining:

- [ ] Implement the Quake 4 fog model (projective fog image, own blend state) as
      its own pass rather than a clustered light contribution.
- [ ] Implement blend lights as a framebuffer-modulating pass.
- [ ] Evaluate ambient lights against the constant tangent-space direction.
- [ ] Keep stencil-shadow lights permanently on the per-light legacy fallback.
- [ ] Flip the `fog-blend` and `shadow` contracts to proven with evidence, after
      Phase 3 unblocks the lights the shadows ride on.

## Phase 5: Core Profile And Promotion

Fully gated on Phases 3 and 4: none of it can land while the modern path cannot
own a lit frame. The exact sites are identified so the change is mechanical when
the gate opens.

- [ ] `gl_ContextSDL3.cpp:202` — `keepAutoCompatibility` is hardcoded
      `preference == RENDERER_TIER_PREF_AUTO`, which is what forces a
      compatibility profile on the default path. It must become conditional on
      the modern path being able to own the frame. The shared ladder already has
      a modern-auto mode and it is covered by `rendererContextLadderSelfTest`, so
      this half is prepared.
- [ ] `RendererCaps.cpp:450` — `compatibilityOnly` follows from the same flag.
- [ ] `RenderSystem_init.cpp:1800` — `R_ErrorForMissingRequiredOpenGLFeatures`
      must become fatal only when the modern path is *also* unavailable, instead
      of whenever `glConfig.allowARB2Path` is false.
- [ ] `draw_arb2.cpp:12468` — `R_ARB2_Init` requires
      `hasFixedFunctionCompatibility`; the bridge stays optional rather than
      required.
- [ ] Satisfy the Phase 8 evidence token honestly and revisit
      `r_rendererModernAutoPromote`.

## Phase 5: Core Profile And Promotion

- [ ] Stop preferring compatibility profiles in the context ladder once the modern
      path can own a lit frame.
- [ ] Make `R_ErrorForMissingRequiredOpenGLFeatures` fatal only when the modern
      path is also unavailable.
- [ ] Satisfy the Phase 8 evidence token honestly and revisit
      `r_rendererModernAutoPromote`.

## Validation

```powershell
python tools\tests\renderer_validation_matrix.py
```

Self-tests touched by Phase 1: `rendererModernCompatibilitySelfTest`,
`rendererModernVisibleSelfTest`, `rendererClusterGridSelfTest`,
`rendererShadowPlannerSelfTest`, `rendererDefaultSafetySelfTest`.

Ownership telemetry in a real scene:

```powershell
python tools\tests\renderer_gameplay_benchmark.py --profile smoke `
  --set-cvar r_rendererModernExecutor=1 `
  --set-cvar r_rendererModernVisible=1 `
  --set-cvar r_rendererMetrics=2
```

Note that `r_rendererMetrics 2` prints the full executor block every frame and
costs roughly an order of magnitude of frame time — the smoke case above fails
its p95 budget on that alone. It is fine for reading `modernLightingOwnership`,
but never quote a frame time from a run that has it enabled. Phase 2 and 3
perf comparisons must use the harness defaults and read the ownership line from
the `gfxInfo` dump instead, which prints the same line once.

`renderer-gpu-driven-selftest` fails on main independently of this track
(`indirect multi-draw execution mismatch`), verified against a clean tree at
f14ea1a8. It is tracked separately and is not a regression from this work.

Two failure modes here are environmental, not real, and both mimic a regression
convincingly enough to waste an hour:

- A second session building in the shared `builddir`/`.install` takes the meson
  lock and can make a concurrently launched gameplay capture die with exit -1
  mid-load and no logged error. Wait the lock out rather than killing the other
  build, and always re-run a one-off gameplay crash before believing it.
- A self-test case that fails in under ~2s never started its client; that is
  launch contention with a previous run's shutdown, not a test result.
