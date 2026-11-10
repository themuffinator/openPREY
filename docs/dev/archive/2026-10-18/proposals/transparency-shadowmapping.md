# Transparency Shadow Mapping for openQ4

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

## Executive summary

The GitHub connector repository (themuffinator/openQ4) already contains a mature *alpha-tested depth* path for the main view depth prepass (FillDepthBuffer): perforated (cutout) materials iterate alpha-test stages, bind the stage texture, apply the stage’s alpha modulation, evaluate an alpha threshold, and render depth only. fileciteturn42file0L1-L1 This same concept is **not currently mirrored in the shadow-map caster pass**, which explains why common transparency-shadowing scenarios (chainlink fences, grates, foliage cards) typically cast **solid silhouettes** (or are excluded entirely, depending on material flags) even when the main view correctly rejects pixels via alpha testing. fileciteturn34file0L1-L1 fileciteturn41file0L1-L1

For production-ready transparency shadowing in a real-time engine, the practical “sweet spot” is usually:

- **Alpha-tested (cutout) casters**: treat as binary occluders but evaluate alpha in the **shadow caster pass** using either classic alpha test (“clip/discard”) or **hashed/stochastic alpha testing** to reduce aliasing and distance-based disappearance. citeturn1search4turn1search2
- **Blended/translucent casters**: either (a) do not cast, (b) approximate with “screen-door / stochastic” coverage, or (c) adopt filterable/transmittance-capable techniques (moment/VSM/EVSM families, deep opacity/deep shadow maps) when the project can afford the complexity and GPU cost. citeturn2search2turn1search0turn3search4turn2search7

openQ4’s March 13–14, 2026 shadow mapping work introduced the core shadow-map system and then extended it with cascaded shadow maps (CSM) support. fileciteturn15file0L1-L1 fileciteturn22file0L1-L1 The key next step for “transparency shadow mapping” is to **port the existing FillDepthBuffer alpha-test logic into the shadow caster rendering path** (projected/cascaded directional & spot lights, and cubemap point lights), with a clear policy per material coverage type. fileciteturn42file0L1-L1 fileciteturn41file0L1-L1

Finally, the user-reported “Peter Panning” and “unravelled/splitting” artifacts cannot be reliably solved by CVar tuning alone when they stem from **mismatched depth spaces, cascade/atlas coordinate errors, or unstable projections**—all well-known failure modes in shadow mapping and especially in CSM. citeturn8search0turn6search3turn6search2 This report proposes concrete diagnostic overlays and stepwise implementation plans to isolate and fix both transparency correctness and these stability issues.

## Information needs and assumptions

This section states the specific engineering questions that must be answered (and tested) to deliver a production-ready implementation.

openQ4 repo and connector used: **GitHub (themuffinator/openQ4)**.

Information needs:

- How the engine currently classifies materials into opaque vs perforated (alpha-tested) vs translucent, and which of those are allowed to cast shadows (by default and by flags). fileciteturn40file0L1-L1 fileciteturn41file0L1-L1
- How alpha-tested geometry is rendered in the depth prepass (what alpha is compared, what threshold is used, how multiple alpha-test stages are handled, and whether alpha-to-coverage is available). fileciteturn42file0L1-L1
- How shadow maps are generated for (a) projected/cascaded lights (depth texture path) and (b) point lights (cubemap packed depth path), and where an alpha-test hook can be inserted with minimal pipeline disruption. fileciteturn34file0L1-L1 fileciteturn36file0L1-L1
- How shadow receiver shaders compute bias (constant + slope/normal components), and how that interacts with caster-side bias (polygon offset) to avoid both acne and Peter Panning. fileciteturn38file0L1-L1 citeturn8search0turn9search0
- How CSM is implemented (splits, atlas layout, cascade selection, stabilization/“texel snapping”, cascade blending), since transparency fixes must integrate with the atlas and selection logic. fileciteturn22file0L1-L1 citeturn6search3turn6search2turn8search0
- What the intended policy is for truly translucent/blended materials (glass, particles, smoke): no shadow, binary shadow, or transmittance-capable shadowing—because the implementation approach diverges dramatically. fileciteturn41file0L1-L1 citeturn2search7turn2search2turn1search0

Assumptions (explicitly stated because constraints weren’t provided):

- Target OpenGL profile/version is “no specific constraint,” but openQ4 uses compatibility-era constructs (fixed-function arrays, `glAlphaFunc`, etc.) and GLSL ARB program objects. fileciteturn42file0L1-L1
- Performance budget is “no specific constraint,” so the report proposes a **tiered** plan: a fast, low-risk alpha-tested caster fix first; more advanced translucent techniques as optional upgrades. citeturn2search2turn3search4turn1search0

## Repository findings from March 13–14, 2026 shadow work

### What landed in those commits

The shadow map system was introduced and iterated rapidly across March 13–14, 2026:

- Initial introduction of GLSL shadow mapping, including casters/receivers and shadow-map rendering infrastructure. fileciteturn15file0L1-L1
- Fixes and refactors in interaction/caster handling (including reliability and cache touch/creation changes). fileciteturn19file0L1-L1
- Shader and GL-state updates for shadow interactions (receiver shading path). fileciteturn20file0L1-L1
- Cascaded shadow map support for directional lights and related atlas/cascade bookkeeping. fileciteturn22file0L1-L1

These commits establish the “where” for transparency work: casters are now drawn into shadow-map render targets (depth textures for projected/cascaded; packed depth for point), and receivers sample them in lighting stages. fileciteturn34file0L1-L1 fileciteturn38file0L1-L1

### How openQ4 classifies coverage and alpha test

openQ4 inherits the classic idTech4-style material coverage model:

- `MC_OPAQUE`: fully solid
- `MC_PERFORATED`: alpha-tested holes (“cutout”)
- `MC_TRANSLUCENT`: blended/translucent fileciteturn40file0L1-L1

Parsing `alphaTest` in a material stage sets `hasAlphaTest`, stores an `alphaTestRegister` threshold, and marks the material coverage as `MC_PERFORATED`. fileciteturn41file0L1-L1

Crucially: when a material is `MC_TRANSLUCENT`, openQ4 automatically sets a “no shadows” behavior by flagging the material as `MF_NOSHADOWS`. fileciteturn41file0L1-L1 This is consistent with historical idTech4 behavior in entity["video_game","Doom 3","idtech4 game 2004"] and entity["video_game","Quake 4","idtech4 game 2005"]-era content authoring, where many translucent effects were not intended to cast traditional hard shadows.

### Existing production-grade alpha-tested depth logic (main view prepass)

openQ4 already contains a correct and robust implementation for alpha-tested depth rendering in the main view depth prepass (`RB_T_FillDepthBuffer`):

- Translucent surfaces skip depth fill entirely. fileciteturn42file0L1-L1
- Perforated surfaces enable alpha test, loop over alpha-tested stages, bind each stage texture, apply the stage alpha modulation, set `glAlphaFunc(GL_GREATER, threshold)`, and draw depth-only. fileciteturn42file0L1-L1
- There is explicit support for **alpha-to-coverage** (A2C) when MSAA and `r_msaaAlphaToCoverage` are enabled and the surface is `MC_PERFORATED`. fileciteturn42file0L1-L1

This is a high-value implementation reference for transparency shadow maps: it codifies what “alpha-tested depth” means in openQ4’s material system.

### Current shadow-map caster paths do not mirror that alpha-tested logic

The shadow-map caster code path (as of `main`) draws caster geometry primarily as depth-only without applying per-material alpha testing; it sets vertex positions and renders into the shadow map resources. fileciteturn34file0L1-L1 This strongly implies that **perforated materials cast solid shadows** unless special handling is added (because nothing in the depth-only caster draw rejects pixels based on alpha). fileciteturn34file0L1-L1

Point-light shadows are generated via a cubemap path that explicitly packs depth into RG in a fragment shader. fileciteturn36file0L1-L1 This path is *well-suited* to adding alpha testing, because a fragment shader already runs per caster fragment (easy insertion point for `discard` or hashed alpha).

### Receiver bias behavior exists (and why it won’t fix transparency by itself)

openQ4’s point-light shadow receiver shader computes a receiver-side bias using both a constant term and a slope/normal-based term derived from `dot(normal, lightDir)`, then compares `(depth - bias) <= storedDepth`. fileciteturn38file0L1-L1 This matches common industry guidance: slope-scale bias helps fight acne but can cause Peter Panning when excessive. citeturn8search0turn9search0

However, bias CVars cannot fix “transparent casters casting solid shadows,” because that is a **caster pass visibility** problem, not a receiver depth-comparison threshold problem. The fix must occur in the caster pass (or via an alternative shadow representation).

## Transparency shadowing techniques survey

This section summarizes credible, widely used methods and their tradeoffs in the context of openQ4.

### Alpha-tested shadow maps (cutout)

Mechanism: in the shadow caster pass, sample an alpha channel (usually from the diffuse/albedo texture or a dedicated opacity map), compare against an alpha reference, and discard fragments below the threshold.

- Strengths: simplest correct behavior for fences/grates/foliage cards; works with standard shadow maps and PCF; easy to integrate with CSM atlases. citeturn8search0turn6search3
- Weaknesses: still aliases at distance; can cause shimmering; requires consistent alpha thresholding and correct mip/filter policy to avoid “disappearing cutouts.” citeturn1search2turn1search4

### Alpha-to-coverage (A2C) for cutouts

Mechanism: with MSAA enabled, enable `GL_SAMPLE_ALPHA_TO_COVERAGE` so alpha modulates the sample coverage mask. Its mapping is intentionally implementation-dependent and often pseudo-random to reduce artifacts. citeturn3search45turn3search0

- Strengths: improves edge anti-aliasing of cutouts without sorting; can be order-independent. citeturn2search4turn3search45
- Weaknesses: to use A2C in shadow maps, the **shadow map render target must be multisampled**, and then sampling/filtering becomes more complex (no free hardware PCF path on multisampled depth textures in the same way as single-sample `sampler2DShadow`). citeturn5search3turn5search2

openQ4 already uses A2C for `MC_PERFORATED` in the depth prepass. fileciteturn42file0L1-L1 Adapting it to shadow maps is possible but costlier than it first appears.

### Stochastic / hashed alpha testing (screen-door style)

Mechanism: replace a fixed alpha reference with a pseudo-random threshold in [0,1), so alpha becomes a probability of keeping a fragment. With a stable hash, this becomes *hashed alpha testing*. citeturn1search4turn1search2

Primary sources:
- entity["people","Chris Wyman","graphics researcher"] and entity["people","Morgan McGuire","graphics researcher"] introduce hashed and stochastic alpha testing and analyze stability, aliasing, and interactions with anti-aliasing. citeturn1search4turn1search2

- Strengths: dramatically reduces distance/minification failures of alpha-tested detail; produces stable “blue-noise-like” dithering when hashed well; works with standard shadow maps, PCF, and CSM atlases (PCF averages the dither into a smooth transmittance-like result). citeturn1search4turn8search0
- Weaknesses: introduces noise (spatial and/or temporal) unless stabilized; can look grainy without sufficient filtering; still an approximation of true translucency. citeturn1search2turn1search4

For openQ4, hashed alpha testing is a particularly attractive *default* because it is a small delta from “alpha-test caster” and works with PCF-based receivers.

### Deep shadow maps (DSM)

Deep shadow maps store *fractional visibility as a function of depth* per texel, supporting semi-transparent and volumetric shadows (hair, fur, smoke). The canonical reference is the Stanford publication by entity["people","Tom Lokovic","graphics researcher"] and entity["people","Eric Veach","graphics researcher"]. citeturn1search0

- Strengths: high quality for many overlapping semi-transparent primitives; prefiltering; handles volumetrics and motion blur in its original formulation. citeturn1search0
- Weaknesses: substantially more complex data representation and filtering than standard shadow maps; not typically implemented unchanged in modern real-time game renderers; likely heavy for openQ4’s current architecture. citeturn1search0

### Deep opacity maps (DOM)

Deep opacity maps extend opacity shadow maps to represent per-pixel distributions of opacity layers; they were presented by entity["people","Cem Yuksel","computer graphics researcher"] and entity["people","John Keyser","computer graphics researcher"]. citeturn3search4turn3search1

- Strengths: designed specifically to reduce layering artifacts of opacity shadow maps for hair-like semi-transparent geometry with fewer layers. citeturn3search4
- Weaknesses: still significantly more complex than alpha-tested shadow maps; requires layered representations and careful integration; mainly targets hair/fur. citeturn3search4

### Filterable shadow maps (VSM / EVSM / MSM) with translucent occluders

Filterable shadow maps store statistics/moments to enable wide, efficient filtering. The lineage includes:

- Variance Shadow Maps (VSM), introduced by entity["people","William Donnelly","graphics researcher"] and entity["people","Andrew Lauritzen","graphics researcher"]. citeturn1search43turn4search0
- Summed-area VSM extensions and detailed practical guidance are covered in entity["book","GPU Gems 3","nguyen 2007"] (Chapter 8). citeturn4search0turn8search1
- Exponential shadow maps (ESM) were proposed by entity["people","Thomas Annen","graphics researcher"] et al. citeturn2search8
- Moment Shadow Maps (MSM) and extensions for translucent occluders are developed by entity["people","Christoph Peters","graphics researcher"] and collaborators; the JCGT extended paper explicitly discusses translucent occluders rendered with alpha blending into moment maps. citeturn2search2turn4search38

- Strengths: can represent *partial occlusion* (transmittance-like results) and filter widely; good for smoke-like layered alpha casters when tuned. citeturn2search2turn4search38
- Weaknesses: prone to light leaking depending on technique/precision; significantly more math, more bandwidth, more tuning; the “right” bias/exponent/moment quantization is technique-specific. citeturn4search0turn4search38turn2search8

### Translucent Shadow Maps (TSM) for subsurface scattering

Translucent Shadow Maps for subsurface scattering (not to be confused with “translucent occluders” in the cutout sense) were presented by entity["people","Carsten Dachsbacher","computer graphics researcher"] and entity["people","Marc Stamminger","computer graphics researcher"]. citeturn2search7

This is typically not the right tool for “glass casts a faint shadow” gameplay shading; it is specialized for subsurface scattering approximations.

### Weighted blended order-independent transparency (WBOIT) and shadowing

Weighted blended OIT (WBOIT) is a fast, approximate OIT method by entity["people","Louis Bavoil","graphics engineer"] and Morgan McGuire (JCGT 2013). citeturn0search48turn0search0

WBOIT is about view rendering order-independence, not shadow maps directly, but the underlying idea—accumulating opacity/coverage without sorting—can inspire approximate “opacity maps” in light space. In practice, implementing WBOIT-style accumulation *for shadows* still needs a depth/ordering model, so it tends to drift toward k-buffers, deep maps, or moment methods.

## Implementation options for openQ4

### Ground truths and constraints from openQ4’s codebase

- openQ4 already has **correct alpha-tested depth** for the main depth prepass, including multi-stage alpha test and optional alpha-to-coverage. fileciteturn42file0L1-L1
- Shadow map casters currently do not replicate that multi-stage alpha-test logic in the caster pass. fileciteturn34file0L1-L1
- Point shadow casters already use a fragment shader to pack depth, making them the lowest-risk place to add alpha masking. fileciteturn36file0L1-L1
- The engine already has receiver-side slope/normal bias logic for point shadows. fileciteturn38file0L1-L1
- openQ4 uses a CSM atlas for directional lights (March 14 commit). fileciteturn22file0L1-L1

### Option set overview

The table below compares realistic options for openQ4. (“Compatibility with PCF/CSM” means it can remain a standard depth shadow map sampled with PCF and a CSM atlas.)

| Technique | Target materials | Shadow representation | Compatibility with PCF/CSM | Expected quality | GPU cost | Implementation complexity | Main risks |
|---|---|---|---|---|---|---|---|
| Alpha-test in caster pass (`discard` / alpha func) | `MC_PERFORATED` | Standard depth map | Excellent citeturn8search0 | Correct binary cutouts, aliased edges | Low–medium (extra texture fetch) | Low | Shimmering at distance; mip/alpha policy |
| Hashed/stochastic alpha test in caster pass | `MC_PERFORATED` (+ optional “soft” translucency) | Standard depth map | Excellent citeturn1search4turn8search0 | Better distant stability; dither converges under PCF | Low–medium | Medium | Noise if hash/stabilization poor |
| Alpha-to-coverage in caster pass (MSAA shadow map) | `MC_PERFORATED` | MSAA depth map | Medium (sampling complexity) citeturn3search45turn5search3 | Good edge AA | Medium–high | High | Requires MSAA shadow targets; filtering path rewrite |
| Moment / VSM / EVSM family with alpha blending | “true” translucent occluders (smoke) | Filterable moments | Poor–medium (receiver rewrite) citeturn2search2turn4search0 | Soft partial shadows possible | Medium–high | High | Light leaking, precision/bias tuning |
| Deep opacity / deep shadow maps | Hair/fur/smoke | Layered transmittance | Low (new system) citeturn3search4turn1search0 | High for target cases | High | Very high | Large re-architecture |

### Recommended default approach for openQ4

**Default recommendation:**

- Implement **alpha-tested shadow casters for `MC_PERFORATED`** by porting the FillDepthBuffer alpha-test stage logic into the shadow caster pass.
- Upgrade that to **hashed alpha testing** (optional, via CVar) to improve minification stability and reduce aliasing for foliage/grates.
- Keep **`MC_TRANSLUCENT` as “no shadow” by default**, matching openQ4’s current material semantics (translucent implies noShadows). fileciteturn41file0L1-L1

This produces the best cost/benefit profile and aligns with industry practice for engines using standard depth shadow maps + PCF/CSM. citeturn8search0turn6search3turn1search4

### Concrete implementation plan

#### Stepwise design

**Step A: Add a dedicated “alpha-tested shadow caster” draw path**

For each shadow-caster surface:

- If `Coverage() == MC_OPAQUE`: keep current fast depth-only draw.
- If `Coverage() == MC_PERFORATED`: render the caster using an alpha-tested stage loop similar to `RB_T_FillDepthBuffer`. fileciteturn42file0L1-L1
- If `Coverage() == MC_TRANSLUCENT`: skip (default), consistent with translucent ⇒ noShadows in material parsing. fileciteturn41file0L1-L1

**Step B: Reuse the engine’s alpha-tested stage semantics**

Mirror FillDepthBuffer semantics:

- Iterate stages; for each stage with `hasAlphaTest` and enabled condition register:
  - Determine `alphaRef = regs[pStage->alphaTestRegister]`
  - Determine `alphaScale = regs[pStage->color.registers[3]]`
  - Bind `pStage->texture.image`
  - Apply texture matrix/texgen rules used in depth fill (at least explicit ST + matrix) fileciteturn42file0L1-L1

This ensures that what is “visible” in the main depth buffer is also what casts shadows.

#### Projected / cascaded shadow maps: GL state and shaders

openQ4 currently renders projected/cascaded shadow maps primarily as depth-only. fileciteturn34file0L1-L1 To add alpha test, you have two viable tactics:

**Tactic 1: Keep fixed-function alpha test (lowest risk)**
Use the same approach as FillDepthBuffer:

- `glEnableClientState(GL_TEXTURE_COORD_ARRAY)` and point `glTexCoordPointer` at `idDrawVert::st`. fileciteturn42file0L1-L1
- `glEnable(GL_ALPHA_TEST)` + `glAlphaFunc(GL_GREATER, alphaRef)` and ensure texture env produces correct alpha (typically `GL_MODULATE` with a uniform/constant alpha scale). fileciteturn42file0L1-L1
- Render depth-only (color mask off) as already done.

**Tactic 2: Use a minimal GLSL caster program (recommended when adding hashed alpha)**
Bind a simple vertex+fragment program for perforated casters. Depth is written automatically from `gl_Position`. The fragment shader only decides whether the fragment exists (discard) and optionally performs hashed alpha.

Example GLSL fragment for cutout casters (binary):

```glsl
uniform sampler2D uAlphaMap;
uniform float uAlphaRef;     // threshold
uniform float uAlphaScale;   // stage alpha modulation
in vec2 vTexCoord;

void main() {
    float a = texture(uAlphaMap, vTexCoord).a * uAlphaScale;
    if (a <= uAlphaRef) { discard; }
    // Depth output happens automatically.
}
```

Hashed alpha extension (stochastic threshold) per entity["people","Chris Wyman","graphics researcher"] / entity["people","Morgan McGuire","graphics researcher"]:

- Compute a stable hash from **light-space texel coordinates** (recommended) or world position, then compare alpha against that threshold. citeturn1search4turn1search2

Key GL state (both tactics):

- Disable blending (`glDisable(GL_BLEND)`) for depth-only.
- Enable depth writes (`glDepthMask(GL_TRUE)`), depth test enabled.
- For caster-side bias, prefer `glEnable(GL_POLYGON_OFFSET_FILL); glPolygonOffset(factor, units);` and tune. citeturn9search0turn8search0

The OpenGL polygon offset formula is explicitly `factor * DZ + r * units`, applied before the depth test. citeturn9search0 This is the canonical caster-side complement to receiver-side bias.

#### Point shadow maps: integrate alpha test into the existing caster shader

Because openQ4’s point shadow caster already uses a fragment shader to write packed depth, the change is localized:

- Add ST (or whichever texcoord corresponds to the alpha map) as a varying from the vertex shader.
- Bind the alpha texture and alpha params.
- Discard before packing depth. fileciteturn36file0L1-L1

This yields correct alpha cutouts in point-light shadows with minimal changes.

#### Shadow sampling, comparisons, and “NaN/w” handling

openQ4 uses manual compare in at least the point-light receiver shader (unpack RG depth, subtract bias, compare). fileciteturn38file0L1-L1

For projected/cascaded shadow maps, the engine may sample depth as a regular `sampler2D` and do manual compare, or use shadow samplers. If you decide to migrate to hardware comparison for quality/perf, OpenGL requires consistent configuration:

- Set `GL_TEXTURE_COMPARE_MODE = GL_COMPARE_REF_TO_TEXTURE` for depth compare mode and select a compare func; otherwise `GL_NONE` for raw depth reads. citeturn5search2turn5search4
- In GLSL, use `sampler2DShadow` for compare lookups and pass a 3D coordinate (uv + reference depth). citeturn5search3turn5search2

If openQ4 remains on manual compare, you still must ensure:

- Shadow projection coordinates perform **perspective divide by W** and are mapped consistently into [0,1], otherwise depth comparisons become unstable and can create “scattered” shadow fragments. This is a standard failure mode noted across shadow mapping guidance. citeturn8search0turn5search2

Given the earlier report of “unravelled geometry/shadowing,” you should add defensive checks (debug builds at least) for `w <= 0`, NaN/Inf, and out-of-range atlas coordinates before sampling.

### CSM-specific improvements and likely “unravelled” failure modes

CSM (and related PSSM) is recommended to combat perspective aliasing. citeturn8search0turn6search3turn6search0 But it introduces its own stability requirements:

- **Cascade selection must be stable** and derived from consistent view-space depth. citeturn6search2turn8search0
- **Atlas coordinates must map to the correct viewport region**, or sampling reads unrelated depths, presenting as “random” or “scattered” shadows across surfaces.
- **Texel snapping / stabilization** is often necessary to prevent shimmering when the camera moves; Microsoft’s CSM guidance emphasizes cascade fitting and stability issues, and GPU Gems discusses practical split schemes and projections. citeturn6search2turn6search3turn6search0
- **Cascade seam blending** reduces visible discontinuities when multiple cascades differ in resolution and filter radius. citeturn6search2turn6search3

If the reported “unravelled” artifacts correlate strongly with angled lights on angled surfaces, the most suspicious categories (that CVars won’t fix) are:

- wrong matrix loaded per surface (modelView mismatch) leading to incorrect shadow/projected coordinate and/or cascade index,
- incorrect perspective divide or incorrect usage of `clip.w`,
- incorrect atlas offset/scale applied (sampling outside the intended cascade tile),
- inconsistent near/far fitting per cascade causing extreme precision loss and bias sensitivity (acne ↔ panning swing). citeturn8search0turn6search3

## Diagnostics, debug overlays, and integration checklist

### Diagnostic tests that isolate transparency correctness

Create “golden” test scenes and a deterministic camera/light script:

- A chainlink fence plane (single quad + alpha texture) over a flat ground plane.
- A grate texture with large holes, and a second with subpixel holes.
- Foliage cards (multiple overlapping alpha planes).
- A mixed scene: opaque pillar behind perforated fence casting onto a slanted ramp.

For each, run:

- Spotlight at grazing angles (nearly parallel to receiver plane).
- Directional light with CSM across multiple cascade depths.
- Point light near the caster (short near-to-far ratio).

Expected results:

- Perforated casters produce perforated shadows (not silhouettes).
- Shadow stability is consistent under slow camera motion (no swimming, no “scatter”).
- Bias changes shift acne ↔ panning tradeoff, but do not fundamentally break projection. citeturn8search0turn9search0

### Debug overlays that make shadow bugs obvious

Implement toggles that render these overlays full-screen or in a corner:

- Shadow atlas visualization (per cascade tile): show depth as grayscale; for packed point shadows show unpacked depth.
- Cascade index visualization on receivers: output cascade ID as a color.
- “Out-of-range” highlight: if projected UV is outside [0,1] (or outside the cascade tile), paint bright magenta.
- “Invalid coordinate” highlight: if `w <= 0` or NaN/Inf, paint cyan and skip sampling.
- Alpha caster debug: render the alpha-tested caster pass into a color target (debug-only) where white = kept fragment, black = discarded; optionally show hashed alpha threshold noise.

These overlays directly validate whether “unravelled” artifacts are coming from atlas addressing/cascade selection, rather than the depth compare itself.

### Shadow bias validation protocol (addresses Peter Panning)

Shadow acne and Peter Panning are the two ends of the bias spectrum; Peter Panning is explicitly described as resulting from overly large depth offsets, especially under low precision. citeturn8search0

Use a structured sweep:

- Fix shadow map resolution, near/far fit method, and filter radius.
- Sweep caster-side polygon offset (`glPolygonOffset(factor, units)`) and receiver bias (`uShadowBias`, `uShadowNormalBias`) separately.
- Record: acne count, panning distance (shadow detachment), and worst-case on sharp edges.

Caster-side polygon offset behavior is defined by OpenGL as `factor * DZ + r * units`. citeturn9search0 Receiver-side slope-scale bias behavior is also well documented in the Direct3D depth bias literature and conceptually maps to OpenGL’s factor/units model. citeturn8search4turn9search0

A key practical point from bias literature: **tight near/far planes** reduce both acne and panning by increasing depth precision, and are recommended in Microsoft’s shadow map guidance. citeturn8search0 This is especially important per cascade.

### Migration plan and CVar guidance

**Phase plan (recommended):**

- Phase 1 (correctness-first): implement alpha-tested casters for `MC_PERFORATED` by reusing FillDepthBuffer alpha-test stage iteration semantics in shadow caster passes (projected/CSM and point). fileciteturn42file0L1-L1
- Phase 2 (quality): add optional hashed alpha testing for cutouts (CVar-controlled) for better distance stability as per Wyman/McGuire. citeturn1search4turn1search2
- Phase 3 (optional advanced translucency): experiment with moment shadow maps for smoke-like layered translucency if gameplay/visual targets justify the cost. citeturn2search2turn4search38

**CVar philosophy (given the user report that no combination fixes core artifacts):**

- Treat CVars as *fine-tuning* after coordinate correctness is validated by overlays. Bias CVars cannot correct an atlas addressing bug, missing perspective divide, or mismatched depth space. citeturn8search0turn6search3

### Appendix with suggested shader code diffs

#### Projected/CSM caster: add alpha discard support (conceptual diff)

```diff
+ // glprogs/shadow_proj_caster.vs
+ attribute vec2 attr_TexCoord0;
+ varying vec2 vTexCoord;
+ void main() {
+     vTexCoord = attr_TexCoord0;
+     gl_Position = ftransform();
+ }

+ // glprogs/shadow_proj_caster.fs
+ uniform sampler2D uAlphaMap;
+ uniform float uAlphaRef;
+ uniform float uAlphaScale;
+ varying vec2 vTexCoord;
+ void main() {
+     float a = texture2D(uAlphaMap, vTexCoord).a * uAlphaScale;
+     if (a <= uAlphaRef) discard;
+     // depth only
+ }
```

#### Point caster: discard before packing depth (conceptual diff)

```diff
  uniform float uPointShadowFar;
+ uniform sampler2D uAlphaMap;
+ uniform float uAlphaRef;
+ uniform float uAlphaScale;
+ varying vec2 vTexCoord;

  void main() {
+     float a = texture2D(uAlphaMap, vTexCoord).a * uAlphaScale;
+     if (a <= uAlphaRef) discard;
      float depth = clamp(length(vPointShadowVector) / uPointShadowFar, 0.0, 1.0);
      vec2 packed = PackDepth16(depth);
      gl_FragColor = vec4(packed, 0.0, 1.0);
  }
```

Hashed alpha testing variant can replace `uAlphaRef` with a stable hash threshold from light-space texel coords. citeturn1search4turn1search2

### Testing matrix for regressions and edge cases

| Scene | Light type | Key stressor | Expected pass condition |
|---|---|---|---|
| Fence alpha cutout over flat ground | Spot + CSM directional | Alpha-tested caster correctness | Shadow shows holes matching alpha |
| Dense foliage cards | Directional (CSM) | Minification + cascade transitions | No “disappearing” foliage shadows; stable cascade selection |
| Grate with subpixel holes | Spot | Shadow map resolution + PCF | Holes may blur, but silhouette not solid |
| Thin wall edges / sharp corners | Any | Bias stress (acne vs panning) | Bias sweep shows monotonic tradeoff, not chaotic artifacts |
| Smoke planes (blended) | Any | Translucent policy | By default: no shadow (consistent). Optional: stochastic/moment method test |
| Slanted receiver ramp with grazing light | Directional (CSM) | Projective aliasing + stability | No “scattered/unravelled” sampling; UV range debug stays sane |

These scenarios map directly to known artifact classes in shadow mapping literature (projective aliasing, acne, Peter Panning) and CSM stability concerns. citeturn8search0turn6search3turn9search0
