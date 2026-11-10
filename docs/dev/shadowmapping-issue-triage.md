# Shadow Mapping Triage for openQ4 idTech4: Peter Panning and “Unravelled” Projected Shadows

## Context and scope

This report targets the shadow-mapping implementation landed in **openQ4** (idTech4-derived) across commits dated **March 13–14, 2026**, and focuses on two observed failures:

- **Peter Panning** (shadows detached from their casters).
- **“Unravelled” geometry/shadowing** when angled surface lights cast shadows, or when upright surface lights cast onto angled receiver surfaces: shadowed surface regions appear “split” and scattered rather than coherently shadowed (your note that **no combination of shadowmapping CVars resolves either issue** strongly suggests a **structural/math/state** defect rather than mere parameter tuning).

The relevant implementation chunks appear concentrated in:
- Initial projected-light shadow-map path + GLSL programs and OpenGL setup fileciteturn4file0L1-L1
- Follow-up changes to caster chains/cache handling and projected-light padding fileciteturn5file0L1-L1
- Shader and render-state refinements for the shadow interaction path fileciteturn6file0L1-L1
- Addition of projected-light **CSM (atlas + up to 4 cascades)** fileciteturn9file0L1-L1

## Production-ready shadow mapping fundamentals that directly impact these symptoms

Shadow mapping (in the modern sense) comes from rendering scene depth from the light’s point of view and comparing receiver depth against that stored depth to decide occlusion—an idea going back to early depth-map style shadows (e.g., Lance Williams’ foundational work on rendering curved shadows using depth maps). citeturn1search2

Two artifact families dominate production debugging:

**Bias tradeoff: shadow acne vs peter panning**
When comparing “receiver depth” and “stored depth,” finite depth precision and rasterization differences cause self-shadowing (“shadow acne”) unless you introduce bias. Too much bias moves shadows away from contact points, producing “Peter Panning.” GPU-focused guidance explicitly calls this tradeoff out and notes it worsens under grazing angles and with filtering (PCF), because filter taps cover a larger depth range. citeturn0search6turn0search49turn4search7

**How OpenGL’s slope-scale depth bias works (and why it matters)**
OpenGL’s `glPolygonOffset(factor, units)` offsets depth *after* interpolation by a term that scales with polygon slope and a constant term, affecting the value written to the shadow map and/or used in the depth test. This is one of the canonical “caster-side” bias mechanisms. citeturn0search0turn0search1

**Receiver-side bias mechanisms used in production**
Beyond constant bias, production systems often add:
- **Normal-based bias / “normal offset”**: bias grows when the surface normal is more perpendicular to the light direction.
- **Receiver-plane depth bias (RPDB)**: estimate receiver slope via derivatives and adjust bias in a way that tracks the receiver plane more accurately; Microsoft’s CSM documentation and other practitioner writeups emphasize that larger PCF kernels make biasing more critical and recommend tight depth ranges and careful bias strategies. citeturn4search7turn4search8

**CSM/PSSM fundamentals that interact with bias and stability**
Cascaded Shadow Maps (and closely related Parallel-Split Shadow Maps) reduce aliasing by splitting the view frustum into depth ranges and rendering separate shadow maps per range. A commonly cited “practical split scheme” blends uniform and logarithmic splits (controlled by a λ parameter), and stabilizing cascades often involves snapping to texel-sized increments. citeturn1search4turn2search1

image_group{"layout":"carousel","aspect_ratio":"16:9","query":["shadow mapping shadow acne vs peter panning diagram","glPolygonOffset slope scale depth bias shadow mapping illustration","cascaded shadow maps split frustum diagram"],"num_per_query":1}

## What openQ4 implemented on March 13–14 and why it matters for diagnosis

### Projected-light shadow mapping path and shader compare model

The March 13 work introduces the shadow-map path, GLSL interaction shaders, and supporting renderer wiring. fileciteturn4file0L1-L1

From the March 14 CSM commit, the projected-light interaction shader pipeline now includes:
- Receiver-side biasing with uniforms for **shadow bias**, **normal bias**, and **filter radius**, and PCF sampling logic. fileciteturn9file0L1-L1
- A normal-angle term (`vShadowLightCos`) used to scale bias (higher bias at grazing angles). fileciteturn9file0L1-L1
- For CSM: up to 4 cascades, atlas rects, split depths, cascade selection by view depth, and optional blending across cascade boundaries. fileciteturn9file0L1-L1

This is consistent with mainstream practice: PCF + bias + (optionally) cascade selection by view-space depth. citeturn5search1turn4search7turn4search8

### Shadow-map rendering side: multi-pass atlas rendering and state restoration

The CSM commit describes a per-cascade rendering loop that:
- Computes cascade clip planes, atlas rects and tile sizes, snaps bounds to texels when enabled, then renders each cascade tile into an atlas with its own viewport/scissor and projection matrix. fileciteturn9file0L1-L1
- Clamps PCF taps to tile bounds in shader (a common atlas leakage mitigation). fileciteturn9file0L1-L1

On the bias side, the implementation uses both:
- **Caster-side** polygon offset in the shadow map render pass. fileciteturn9file0L1-L1
- **Receiver-side** bias in the compare shader. fileciteturn9file0L1-L1

This dual-bias setup is common, but it also means **systematic math mistakes** (e.g., wrong depth mapping, wrong projection, wrong sampler contents) can masquerade as “bias issues” while resisting all CVar tuning—exactly the situation you described. citeturn0search49turn4search7

### The caster chain and cache handling changed during rollout

A March 13 follow-up commit explicitly reorganizes shadow-map caster chains and cache handling, and introduces a projected-light padding CVar. fileciteturn5file0L1-L1

Given your “unravelled geometry” symptom, anything that changes *which draw surfaces are treated as casters* and *how their cached vertex/index data is touched/bound* is a prime suspect: geometry corruption inside the shadow map will project as “scattered” shadow shapes.

## Root-cause hypotheses consistent with “CVars cannot fix it” and how to test each

This section favors hypotheses that explain:
- Why bias/filter/size knobs do **not** converge on correctness.
- Why the artifact correlates with **angled** projected lights and/or angled receivers.

### Peter panning that doesn’t respond to bias CVars

In normal shadow mapping, Peter Panning is usually reducible by lowering bias, tightening depth range, or reducing PCF radius. citeturn0search6turn4search7turn0search49
If *no* CVar combination resolves it, prioritize these structural causes:

**Hypothesis A: Depth mapping mismatch between caster pass and receiver compare**
If the shadow map stores depth in one convention (e.g., OpenGL depth after projection/divide) but the shader reconstructs a different convention (e.g., wrong NDC mapping, wrong clip-plane rows, wrong divide semantics), you can get an “effective bias” that is wildly wrong and not tunable.

Diagnostic:
- Add a debug mode that outputs **(computedDepth − storedDepth)** as grayscale for a known flat receiver (e.g., a large plane) with a single caster (e.g., a box). A correct implementation should show near-zero difference away from edges, with small gradients due to interpolation differences.
- Force **all** bias contributions to zero **in code** (not just via CVars): disable polygon offset, set `uShadowBias = 0`, `uShadowNormalBias = 0`, and set PCF radius to 0. If Peter Panning remains, it’s not “bias”; it’s a mapping mismatch. (This approach is directly motivated by the known bias tradeoff dynamics: removing bias should swing the artifact toward acne, not persist as panning.) citeturn0search6turn0search0turn4search7

**Hypothesis B: Shadow map is not the texture being sampled (binding/unit/sampler mismatch or stale atlas tile)**
If the receiver pass samples the wrong depth texture or wrong tile/region (especially in an atlas setup), changing bias won’t fix “detached” shadows because you’re comparing against unrelated content.

Diagnostic:
- Add a mode to draw the shadow atlas (or single shadow map) fullscreen.
- Render per-light hash/ID into an unused color target alongside depth during the caster pass (or encode a simple pattern into a separate attachment) and confirm the receiver shader sees the expected pattern when sampling.

Why this fits your symptom:
- A wrong-sampler issue produces stable-but-wrong shadowing that is highly insensitive to bias CVars.

### “Unravelled” / scattered shadowing tied to light/receiver angle

This symptom is **most characteristic** of one of these failure modes:

**Hypothesis C: The shadow map contains corrupted geometry (caster pass is drawing the wrong triangles or wrong transforms)**
If the shadow map depth texture itself contains “exploded” triangles or seemingly random slivers, then projecting those depths back onto receivers creates scattered shadow fragments.

Why it fits:
- You explicitly saw geometry-like fragmentation (“split and scattered”), not just noisy shadow edges.
- The roll-out included **caster chain + cache handling changes** that could cause VBO/index binding or stale cache pointer issues. fileciteturn5file0L1-L1

Diagnostic:
- Visualize the shadow map depth (and, if possible, normal/debug ID) for the problematic angled light. If the depth map image is already “unravelled,” the bug is upstream of sampling.
- Temporarily change the caster list to only include “known-good” static world geometry (e.g., a single test mesh) and verify whether the corruption disappears. If yes, the bug likely lives in caster chain selection / cache binding logic rather than projection math.

**Hypothesis D: Homogeneous `w` instability in projected-light shadow coordinates (near-zero/negative w within triangles) causing NaN/Inf coordinates and undefined sampling**
The receiver shader path divides by `w` to project into shadow UV/depth space; if `w` approaches 0 or crosses 0 within a triangle (more likely near the edges of a projected-light frustum and in grazing configurations), interpolation can yield extremely large values or NaNs. NaNs can bypass bounds checks (comparisons are false), leading to undefined texture coordinates and “random” shadowing that can look like scattered fragments.

This is especially plausible when:
- The light is angled such that parts of receivers/casters approach the frustum’s projective singularity.
- You see the problem triggered by “angled surface lights” (projective lights).

Diagnostic:
- Add debug outputs for `shadowCoord.w` (magnitude and sign), and for `isnan(projected.xy)` using `projected.x != projected.x` patterns if GLSL version limits `isnan`.
- Correlate the artifact region with near-zero/invalid `w`.

Mitigation (structural, not CVar):
- In the receiver shader, treat `abs(w) < ε` as unshadowed (or clamp `w` to ε before divide).
- Additionally, clip triangles against the light frustum in the caster pass (or ensure the projected-cull path is correct) so `w` cannot cross zero across a triangle.

**Hypothesis E: Out-of-bounds shadow sampling repeating/clamping edge texels (wrap mode / atlas edge leakage)**
Repeating/clamped edge sampling can create “phantom” shadow regions outside the light’s valid projection. It often appears as smeared or tiled shadow shapes that do not correspond to actual scene geometry.

Although openQ4’s CSM shader work clamps UVs to atlas tile bounds and checks local UV ∈ (0,1), this hypothesis remains relevant if NaNs bypass the checks or if non-CSM paths still rely on sampler wrap behavior. fileciteturn9file0L1-L1
The general OpenGL shadow-mapping guidance is to avoid unintended repetition and use border handling (or explicit bounds checks), because edge repetition can yield unpredictable results. citeturn5search0turn5search1

Diagnostic:
- Force wrap to border with a border depth that represents “lit” (where available), and see whether scattered fragments disappear specifically near projection edges.

## Diagnostic tests to add to openQ4 that will localize the defect quickly

These tests are designed to produce binary outcomes (pass/fail) and distinguish “bias tuning” problems from “math/state/data” problems.

### Shadow atlas/single-map visualization overlay

Add a debug overlay mode that shows:
- The depth atlas (CSM) or depth map (non-CSM) in screen space.
- A per-cascade viewport outline (for CSM) and a per-tile “stamp” (e.g., render a small constant-depth quad in one corner of each cascade tile) to verify correct tile addressing.

Rationale:
- If “unravelled geometry” is visible in the shadow depth image, the bug is in caster pass (caster chain, transforms, index/vertex cache binding, scissor/viewport, or FBO clearing). If the shadow depth image is clean, focus on receiver projection/sampling. This matches standard shadow mapping debugging practice: always validate “what’s in the shadow map” before touching bias. citeturn5search1turn0search6

### Receiver-space debug views in the interaction shader

Add a `r_shadowMapDebugMode` that replaces lighting with:
- `localUv` heatmap (after divide and 0..1 mapping).
- `depth` heatmap.
- `shadowCoord.w` magnitude/sign visualization.
- A “validity mask” (1 if all checks pass; 0 otherwise).

Rationale:
- These views isolate projective singularities and coordinate discontinuities that produce scattered fragments.

### Hard-disable all bias in code and observe the transition

Because you stated “no CVar combination fixes it,” do not trust CVar-driven “zero bias” as proof. Instead:
- In the caster pass: hard-disable polygon offset (`GL_POLYGON_OFFSET_FILL` off, or `glPolygonOffset(0,0)` and disable the enable).
- In the receiver pass: hard-set biases to 0 and make PCF radius 0.

Expected outcomes (based on established bias behavior):
- A correct mapping with no bias should produce **shadow acne**, not persistent detachment or random “unravel.” citeturn0search6turn4search7
- If you still see detachment/unravel, the defect is not “bias value,” but “depth/coord correctness” or “wrong shadow map contents.”

### Shadow map caster sanity scene

Create a minimal test map or dev-only scene:
- One static plane receiver
- One simple box caster
- One projected light with adjustable orientation (roll/pitch/yaw)

Then:
- Compare shadow map depth image against expected silhouette as you rotate the light.

This is important because your symptom is angle-sensitive: you want a test that sweeps the problematic parameter (light orientation) while holding complexity constant.

### GPU state validation around shadow-map passes

Add guarded asserts/logging to record and verify:
- Viewport/scissor state
- Color/depth mask
- Bound FBO and depth attachment
- Active texture unit and bound texture for the shadow sampler
- Program bindings for the interaction pass

CSM explicitly adds scissor enable/restore and multi-viewport rendering, which increases the likelihood of state leaks manifesting as bizarre downstream rendering. fileciteturn9file0L1-L1

## Solutions and improvements tailored to openQ4 idTech4, including CSM hardening

### Fix path for the “unravelled geometry” symptom

Given your “CVars don’t fix it” constraint, treat this as a **correctness bug** first, quality bug second.

**Priority 1: Prove whether corruption originates in the shadow map**
- If the depth map is corrupted: focus on caster chain composition and cache binding logic introduced during rollout. fileciteturn5file0L1-L1
  - Ensure the caster list used for shadow maps includes only valid, front-facing occluder geometry (ambient tris), not shadow volume geometry or other derived surfaces.
  - Add validation that vertex and index caches are valid and match `numVerts/numIndexes` before drawing (fail fast in debug builds).

**Priority 2: Make the receiver sampling robust to projective degeneracies**
Even with correct caster geometry, projected lights can generate near-singular coordinates. Add structural guards:
- In shader: treat `abs(w) < ε` as unshadowed, and treat NaNs as unshadowed. (This prevents undefined UVs from sampling “random” depth results and producing scattered fragments.)
- In caster pass: ensure triangles outside the light volume are culled/clipped before rasterizing into the shadow map. The engine already has a concept of projected-light culling, and correctness here is critical for projective stability. fileciteturn9file0L1-L1

**Priority 3: Enforce deterministic out-of-bounds behavior**
Even with explicit UV checks, prefer additional safety:
- Clamp to border where available, or explicitly clamp UVs before sampling.
- In an atlas, always clamp taps to tile bounds (openQ4 already added this for CSM). fileciteturn9file0L1-L1

This aligns with widely documented shadow-map edge behavior: accidental reuse of border/edge texels leads to non-physical “phantom shadows.” citeturn5search0turn5search1

### Fix path for Peter Panning, assuming mapping correctness is restored

Once you’ve proven the mapping is correct (depth map clean, receiver UV/depth valid), then treat Peter Panning as a bias design issue.

**Rebalance caster-side vs receiver-side bias**
openQ4 currently uses polygon offset in the caster pass and receiver-side bias terms. fileciteturn9file0L1-L1
Production references emphasize that:
- Slope-scale bias helps but cannot eliminate the fundamental “large texel depth range” problem, especially at grazing angles and with PCF. citeturn0search6turn0search0
- Too much bias produces Peter Panning, and PCF typically pushes you toward larger offsets unless you improve depth precision and fitting. citeturn4search7turn0search49

Practical approach:
- Prefer *smaller* constant bias + *angle-aware* adjustments rather than large constant offsets.
- Tighten near/far depth ranges for the shadow projection (see CSM section), reducing the needed bias overall. Microsoft’s CSM guidance explicitly notes that tight depth ranges reduce the impact of bias. citeturn4search7

**Add Receiver-Plane Depth Bias as an optional mode**
Receiver-plane depth bias can significantly reduce the need for coarse biasing when it’s stable, but it can produce degenerate cases; treat it as a toggleable mode and fall back to normal-bias + small constant bias when it misbehaves. citeturn4search8turn4search7

**Scale bias per cascade (CSM)**
Because cascades have different depth ranges and resolution footprints, bias parameters that are “correct” for one cascade can cause panning or acne in another. This is a known practical detail discussed in CSM-focused biasing writeups. citeturn4search8turn4search7

### CSM implementation improvements and idTech4-specific cautions

openQ4’s CSM implementation already includes:
- 1–4 cascades in a 2×2 atlas
- log/uniform blended split scheme (λ)
- optional stabilization via texel snapping
- blending between cascades
- tile-bounded PCF tap clamping fileciteturn9file0L1-L1

These are all aligned with established PSSM/CSM practice. citeturn2search1turn1search4

However, there are concrete robustness upgrades to prioritize given your failure modes:

**CSM upgrade A: Make depth-range fitting a first-class invariant**
Bias problems worsen when the light’s near/far planes are loose; tightening near/far reduces quantization and bias sensitivity. citeturn4search7turn0search49
For projected-light CSM (which is less standard than directional-light CSM), ensure that per-cascade clip/depth bounds are not only cropped in XY but also meaningfully fitted in Z where possible.

**CSM upgrade B: Validate cascade bounds against projective singularities**
The implemented cascade bounds computation skips points when `clip.w` is near zero and requires a minimum number of valid points. fileciteturn9file0L1-L1
Given your angle-triggered unraveling, extend this by:
- Tracking how often corners are skipped due to `w≈0` and reporting it (per light, per frame, in debug).
- Falling back to 1-cascade mode for that light if bounds become unstable (fail safe rather than produce broken shadows).

**CSM upgrade C: Restrict CSM usage to lights that benefit**
CSM is most common for large “sun/sky” directional lighting; applying CSM to small projected lights can increase complexity and edge cases with minimal benefit. citeturn2search1turn4search7
openQ4 already gates CSM by `r_shadowMapCSM` and cascade count; consider adding an additional heuristic gate per light (e.g., only use CSM for large projected frusta / long distances).

**CSM upgrade D: Add a cascade debug HUD**
For production debugging, add overlays showing:
- Split depths
- Active cascade index distribution on screen
- Blend region visualization

This makes “wrong cascade selected” bugs obvious, and it catches cases where view depth used in selection diverges from the split computation. fileciteturn9file0L1-L1

### A practical “fix order” that matches your constraints

Because parameter tweaks do not resolve the issues, the most efficient order is:

1. **Shadow map visualization**: prove whether the depth map is correct (atlas tile-by-tile for CSM).
2. **Caster correctness**: validate caster chain inputs and cache pointers; reduce to minimal casters until stable. fileciteturn5file0L1-L1
3. **Receiver coordinate robustness**: clamp/guard projective `w`, detect NaNs, and ensure strict out-of-bounds handling.
4. **Only after correctness**: redesign biasing (small constant + normal bias; optional RPDB; per-cascade scaling). citeturn0search6turn4search7turn4search8
5. **CSM hardening**: fail-safe fallback when cascade bounds become unstable; deepen per-cascade depth fitting; add debug HUD. fileciteturn9file0L1-L1

This order is consistent with the core lesson from major shadow mapping references: bias tuning cannot compensate for incorrect depth/coord mapping or corrupted shadow maps; it only trades acne for panning once the mapping is correct. citeturn0search6turn0search49turn4search7