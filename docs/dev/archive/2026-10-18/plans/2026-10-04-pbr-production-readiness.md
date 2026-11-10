# PBR production readiness

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Status: complete (2026-10-04 to 2026-10-05). Stages A-F landed; the
remaining limitations are listed under Stage F.

This plan takes the authored PBR material path from a qualified laboratory
feature to a production feature. Production means that a mod author can ship
dual-authored PBR materials, a player sees them rendered as PBR in ordinary
gameplay on the default renderer, stock content renders exactly as before, and
every material channel reaches every lighting term it should on both backends.
The earlier work and its evidence are in the
[September audit](2026-09-20-pbr-rendering-audit.md) and the
[original plan](2026-05-19-pbr-material-support.md).

## Gap audit (2026-10-04)

The audit traced every PBR input through both backends. Each row names the gap,
the decision and the stage that closes it.

| ID | Gap | Decision | Stage |
|---|---|---|---|
| G1 | Single-scattering GGX loses up to 69% of a rough white conductor's energy (1 - ln 2 at roughness 1). Rough metals rendered far too dark on both backends. | Multiple-scattering energy compensation on every specular lobe, direct and environment. | A |
| G2a | Authored ambient lights ignored material AO on both backends, although they stand in for bounced light. | Ambient-light diffuse takes the same multi-bounce AO as environment diffuse. | A |
| G2b | Environment specular was multiplied by raw AO, darkening smooth head-on reflections as much as rough ones. | Specular occlusion from AO, NoV and roughness. | A |
| G2c | Raw AO over-darkened bright occluded albedo. | Multi-bounce AO on diffuse (by albedo) and specular (by F0). | A |
| G2d | Normal maps could send reflections below the geometric surface. | Horizon occlusion against the interpolated vertex normal. | A |
| G2e | SSAO multiplies the whole lit frame, direct light included, and ignores material AO. On Vulkan it also disables the linear PBR scene and drops the environment pass of baked receivers. | SSAO attenuates PBR indirect light only, combined with material AO. | D |
| G3a | Without the filtered atlas, GL's analytic environment ignored roughness and the split-sum table. | Roughness-convolved analytic lobe and an analytic split-sum fallback. | A |
| G3b | GL's deferred `r_pbrDebug 4` showed filtered roughness, forward showed authored roughness. | Both show authored roughness. | A |
| G4 | OpenGL, the default renderer, draws PBR only when a whole frame qualifies for the modern visible path. That needs six developer cvars, and any weapon, stock specular material, ambient light or stencil shadow sends the frame back to classic. Ordinary gameplay never shows PBR on GL. | Per-surface native PBR inside the classic GL light loop, mirroring native Vulkan. | B |
| G5 | Presentation: HDR-off PBR radiance is added to the display domain without the sRGB transfer, a PBR surface shows about a fifth of the brightness of the same surface lit classically, and Vulkan's HDR scene linearizes and filmic-maps every view once `r_pbrMaterials` is on, changing stock frames. | Calibrate PBR irradiance to the classic light term and composite every PBR draw in the classic display domain on both backends. Stock pixels stay unchanged, and the tone curve does not depend on whether PBR is in view. The linear scene becomes the explicit laboratory mode `r_pbrLinearScene`. | C |
| G6 | Environment lighting in real maps: without authored probes every PBR surface reflects the analytic studio sky, even in dark interiors. | Indirect light follows the map: authored ambient lights become uniform environments (diffuse and specular), the studio sky becomes the laboratory mode `r_pbrAnalyticEnvironment`, and baked light grids reach every native owner. | E |
| G7 | Defaults and UX: `r_pbrMaterials` defaults to 0, GL needs the non-archived `r_rendererModernVisible`, and there is no menu control. | `r_pbrMaterials` defaults to 1 with a one-time profile migration, and frames without a PBR material skip all PBR work; authored probes stay opt-in. No menu control: the setting changes nothing in stock content (Stage F). | F |
| G8 | Found by the Stage B parity comparison: every direct-light evaluation (Vulkan, modern GL) returned black where a normal map turned the shading normal away from the viewer, speckling normal-mapped silhouettes, and which pixels went black differed between backends. | Clamp N.V in every direct term (`PBRShadingNoV`). | B |

## Stage A: complete roughness and AO shading (both backends)

The shared kernel (`src/renderer/PBRMath.h`) gains five numerically tested
functions, embedded in OpenGL's modern shaders and included by Vulkan's:

- `PBRSpecularAlbedo(NoV, r)`: the directional albedo E of the
  single-scattering lobe with F = 1, the A + B of the split-sum table. It is a
  15-term fit in r and sqrt(NoV), over NoV in [0.1, 1] and the shading
  roughness range. 1/E is within 2.5% of the integrated table.
- `PBREnergyCompensation(f0, E)`: `1 + f0 (1/E - 1)`. A compensated white
  furnace lands in [0.975, 1.023]; no F0 gains energy beyond that bound.
- `PBRSpecularOcclusion(NoV, ao, r)`: Lagarde and de Rousiers (2014).
  AO 1 is unoccluded, AO 0 fully occluded, and rough lobes follow AO.
- `PBRMultiBounceAO(v, albedo)`: Jimenez et al. (2016), bounded to [v, 1].
- `PBRHorizonOcclusion(dot(R, Ngeom))`.

Direct lights (point and projected) apply the energy compensation and stay
AO-free. The environment pass uses the split-sum table's A + B where it is
bound, and the fit elsewhere (Vulkan's per-light passes bind no table).

Evidence: `tools/tests/native/PBRMathTest.cpp` and
`tools/tests/renderer_pbr_materials.py`
(`test_pbr_energy_and_occlusion_contract`); laboratory runs below.

### Vulkan rough-reflection regression found by the audit

The paired IBL comparison failed `rough-high` and `double` on HEAD, before
any Stage A change. OpenGL's specimen values still matched the retained v7
qualification exactly (rough metal mean 4.518), while Vulkan had drifted
(4.252) and showed a crisp key-light rim on a roughness-1 metal. The cause was
c850233d (2026-09-25): explicit `TF_LINEAR` samplers now clamp to the base
level to match `GL_LINEAR`. The PBR environment atlas is `TF_LINEAR` and reads
its prefiltered levels with explicit `textureLod`, so every rough Vulkan
reflection and authored probe sampled the mirror level. The atlas now has a
sampler that keeps the chain (`VK_Image_UseExplicitMipChain`), and
`test_vulkan_environment_mip_chain_sampler` pins it. The regression never
reached a tagged release; v0.13.2 predates c850233d.

### Stage A laboratory evidence (2026-10-04)

Private build `+g632d66b1.dirty` (HEAD plus Stage A only), Windows/NVIDIA,
runtime `.tmp/wt-pbr/.tmp/lab-b` (Stage A) against `.tmp/wt-pbr/.tmp/lab-base`
(HEAD renderer modules in the same package).

| Suite | Result |
|---|---|
| Native math (`openq4-pbr-math`) | pass, including 21x19 fit/furnace grid and occlusion invariants |
| GL core (`lit,ownership,no-probes,direct,legacy,master-off`) | 6/6 |
| Vulkan direct suite, 0x | 68/68; A/B against HEAD changes only `rough-high`/`aa-rough` (max +29 bytes, 2.6% of pixels) |
| Vulkan ambient lights, 0x | 41/41; independent oracle with multi-bounce AO passes within 1.1 bytes, `ao-zero` black |
| IBL suites, 0x | Vulkan 27/27, GL 26/26; GL/Vulkan parity exact on all 26 paired controls (HEAD: 2 failures) |
| IBL suites, 4x | Vulkan 27/27, GL 26/26; parity maximum 1 byte |
| Probes, 0x | Vulkan 46/46, GL 40/40; probe proof and GL/Vulkan parity pass |
| Transparency / cutout / fog / capacity / resources | 25/25, pass, 7/7, 18/18, 44/44 |
| Geometry | 11/11 per backend; parity pass |
| Baked lighting | GL 6/6; native baked composition passes |
| Diagnostics | 62/62 per backend; paired whole-frame comparison keeps its documented mapped-normal and cutout-boundary failures, identical on HEAD |

The IBL A/B against HEAD isolates each term: the roughness-1 metal gains up to
76 bytes from energy compensation, AO-0.75 specimens up to 5 bytes from
multi-bounce and specular occlusion, normal-mapped specimens lose up to 9 bytes
at grazing reflections from horizon occlusion, and `ao-zero` stays black.

## Stage C: calibration and display-domain composition (both backends)

Quake 4 lights are display-referred. A classic interaction multiplies the
light term (projection x falloff x color, with `r_lightScale`) by the diffuse
texture and adds the product to the framebuffer, one draw per light stage, so
a white classic surface shows the light term itself and two lights show the
sum of their terms. PBR shaded the same light term as linear irradiance and
wrote its linear radiance into that encoded framebuffer. A grey dielectric
sphere that shows 112/255 lit classically showed 25/255 as PBR.

The calibration (`PBRClassicLightIrradiance`) reads the light term as encoded
radiance: the PBR irradiance is pi times its sRGB-decoded value, which is the
irradiance at which a white Lambertian surface leaves exactly the classic
radiance at normal incidence. PBR keeps its cosine falloff and specular lobe in
linear light, so its terminator is physically shaped rather than the classic
display-space falloff, but its brightness matches the level the map's author
balanced.

Composition: every PBR draw that writes the display-referred framebuffer
encodes its radiance (`PBRLinearToSRGBExtended`, continued above one for the
FP16 HDR scene) and adds it like a classic light: each light, each stage of a
multi-stage light, the environment term and emission are encoded on their own.
Encoding is concave, so this is not the same as encoding the sum once, and it
is the rule that reproduces classic multi-light balance: two equal lights on a
white PBR surface show twice the classic term, exactly like classic. It is also
the only rule every pipeline shares. Vulkan composites one draw per light and
replays ordered transparency per light; the modern GL clustered shaders, which
evaluate all lights in one pass, encode inside their light loop. Their cluster
builder now gives ambient lights one record per stage like other additive
lights, so a two-stage ambient light composes as two lights, as on Vulkan (the
GL whole-frame owner still declines ambient-light scenes, so the Vulkan oracle
is the proof).

The linear scene (PBR radiance accumulated separately and encoded once, with
the whole view presented through the PBR filmic curve under `r_hdrToneMap`)
changes how classic surfaces look, so it is no longer implied by tone mapping.
It is the laboratory mode `r_pbrLinearScene` (default 0, not archived). With it
off, `r_hdrToneMap 1` keeps the classic HDR presentation: PBR draws encode into
the classic FP16 scene and share its tone map. Vulkan's HDR-off floating-point
preview (`r_pbrLinearScene 1` without HDR) now stores the same per-draw encoded
values and only keeps them in floating point until the scene is resolved. The
laboratory pins `r_pbrLinearScene 1` in its base profile so its linear and
preview machinery stays under test; the `vk-direct-composite`,
`vk-direct-calibration` and `vk-direct-calibration-classic` controls select
production composition.

Debug views 1-5 and 7 still show raw material data. The emission view
(`r_pbrDebug 6`) shows the emission term exactly as it reaches the frame, so it
is encoded where emission is.

Evidence: `tools/tests/native/PBRMathTest.cpp` (`ClassicCalibrationTests`),
`tools/tests/renderer_pbr_materials.py`
(`test_pbr_display_calibration_contract`) and the laboratory runs below.

### Laboratory consequences of calibration

Calibrated PBR is about three times brighter in linear light, so several
measurements had to follow it. Each change below is a consequence the
calibration predicts, not a tolerance loosened to pass:

- The overview's key light is three times overbright and the base profile ran
  the game's `r_lightScale 2`. Classic and calibrated PBR alike then saturated
  40% of the frame (means 187 and 188), most stations read white and the
  probe-effect, AO-zero and station checks measured nothing. The base profile
  now lights the overview at `r_lightScale 0.5` (classic mean 64, 4% of pixels
  at white); every suite that needs another level already sets its own.
- Emission references are linear radiance encoded once (`vk-direct`
  `emission-half` 187.5, 146.3, 19.0); the emission view (`r_pbrDebug 6`)
  shows emission as it reaches the frame on both backends.
- The Vulkan ambient oracle models the calibration, the per-stage encode and
  the framebuffer's white limit (two lights read 255, 127, 57 against 266, 127,
  57 unclamped). The linear-scene ambient oracle in
  `renderer_vulkan_hdr_scene.py` gains the calibration and the AO that ambient
  lights have carried since Stage A; it had not been rerun then and would
  have failed.
- GL/Vulkan whole-frame parity gates of two bytes admit an encoded-frame
  allowance: at most 0.01% of channels may differ by up to four bytes. The same
  small relative evaluation difference in a normal-mapped highlight or at a
  grazing silhouette, previously below one byte, now spans three or four
  (`probes-normal`: three channels; `backface-front-normal`: 162). Specimen
  interiors keep their exact or two-byte gates.

### Stage C laboratory evidence (2026-10-04)

Private build of Stage A plus Stage C, Windows/NVIDIA, runtime
`.tmp/wt-pbr/.tmp/lab-a`, base profile `r_pbrLinearScene 1`, overview at
`r_lightScale 0.5`. The commit is rebased onto e21230cd (the grazing-wall
shadow-acne fix, which touches disjoint hunks of the shared files); the SPIR-V
headers are regenerated from the merged sources, and the static contracts,
header pins and the PR validation profile pass on the rebased tree.

| Suite | Result |
|---|---|
| Native math | pass, including the extended transfer and classic calibration identities |
| Vulkan direct, 0x | 71/71. `calibration`: classic peak 153, PBR 151 against a predicted 149.5 (Stage A: 33). `composite` (production, `r_pbrLinearScene 0`) equals the floating-point preview within 0.008 mean bytes |
| Vulkan ambient lights | 41/41; independent oracle passes within 1.1 bytes |
| HDR linear scene | composition 20/20 per backend and GL/Vulkan comparison pass; ambient radiance within 0.35 bytes; recovery pass |
| HDR-off preview, 4x | GL 40/40, Vulkan 40/40; all 40 GL/Vulkan pairs within one byte |
| Overview | Vulkan map 4/4, GL core 6/6 (probes change the copper station by 39 bytes), GL HDR 7/7 |
| IBL, 0x | Vulkan 27/27, GL 26/26; parity pass on 26 controls |
| Probes, 0x | Vulkan 46/46, GL 40/40; parity pass |
| Diagnostics | 62/62 per backend; semantics pass; whole-frame failures identical to Stage A |
| Geometry | 11/11 per backend; parity pass |
| Transparency / cutout / fog / capacity / resources | 25/25, pass, 7/7, 18/18, 44/44 |
| Baked lighting | GL 6/6; Vulkan native baked composition passes |

## Stage B: native per-surface PBR in the classic OpenGL light loop

OpenGL, the default renderer, drew authored PBR materials only when a whole
frame qualified for the experimental modern visible path, which needs six
developer settings and falls back to classic for any weapon, stock specular
material, ambient light or stencil shadow. Ordinary gameplay therefore never
showed PBR on OpenGL. `draw_pbr.cpp` now owns admitted surfaces inside the
classic light loop, the way native Vulkan does:

- Admission is the shared material contract (`PBRNativeContract`, a
  backend-neutral copy of the Vulkan rules: one active bump/diffuse/specular
  sequence, matching cutout coverage, ready images, a single replaceable glow
  stage, a provable source-alpha stage), plus the OpenGL resources (GLSL,
  fourteen image units, the PBR programs) and geometry the GLSL path can draw
  (no GPU-posed MD5R surfaces). The material contract table is prepared every
  frame PBR is on, as on Vulkan, without starting the rest of the modern side
  pipeline. `r_glPBR 0` returns every surface to its classic stages.
- Every light keeps its classic shadowing. The classic decomposition skips an
  owned surface and the native draw skips everything else, so each surface is
  lit by exactly one owner per light. Unshadowed and stencil-shadowed lights
  draw with a PBR variant of the projected receiver program
  (`OPENQ4_PBR_UNSHADOWED`) under the current stencil state; shadow-mapped
  lights run the classic receiver pass a second time with PBR variants of the
  projected and point receivers swapped in. The variants compile the shipped
  receiver sources with `OPENQ4_PBR` defined and a shading library appended,
  so their shadow filtering, biases and cascades are the classic receivers'
  own. Ambient lights take the isotropic AO-occluded diffuse of Stage A.
- The shading library is the Vulkan evaluation term for term
  (`pbr_vertex.glsl`, `pbr_direct.glsl`): an orthonormal object-space frame,
  object-space light and view vectors, specular AA from the final normal's
  derivatives, the calibrated irradiance and the per-draw display encode.
  Classic light triangles drop faces turned from the light; PBR draws use the
  full set (`pbrLightTris`, now built for OpenGL too), so smooth normals light
  every face they can.
- The ambient walk draws one environment pass per owned surface (the filtered
  analytic environment, the split-sum table and authored probes, ported from
  `pbr_environment.glsl` and `pbr_probes.glsl`), replaces the glow stage with
  the typed emission, and masks a perforated surface's depth fill with its PBR
  albedo. Material diagnostics draw once per surface there, as on Vulkan.
  Authored probes use the same CPU clustering as Vulkan, uploaded per view as
  small float textures.
- Translucent (source-alpha) owners composite at their authored stage, as on
  Vulkan: the light loop draws nothing for them; in the stage's sort position
  the background keeps 1 - alpha, then every light that reaches the surface
  and its environment add alpha times their encoded radiance. OpenGL can
  re-evaluate a light's interaction at any time, so it replays the light where
  Vulkan replays a recorded draw. A replay cannot reproduce a light's stencil
  or per-light shadow-map coverage, so -- exactly as on Vulkan -- a view in
  which a shadow-casting light reaches a translucent receiver keeps classic
  ownership of every translucent surface, lighting included. Opaque owners in
  that view are unaffected.

Not yet owned on OpenGL: surfaces posed on the GPU (`r_gpuSkinning 1`, packed
MD5R meshes; both off by default) keep their classic stages. In a map with a
baked light grid the classic grid pass still adds its indirect diffuse to an
owned surface, where Vulkan and the modern GL path replace environment diffuse
with PBR-weighted baked diffuse; Stage E brings that composition to the owner.

### Continuous N.V on every backend

The paired comparison found a shared defect, not a GL one: every direct-light
evaluation (Vulkan, modern GL and the new owner) returned black when the
mapped normal turned away from the viewer. A normal map does that at
silhouettes, so normal-mapped spheres showed black pixels along their rims,
and which pixels went black flipped between backends with the last bit of
interpolation (up to 115 bytes on seven pixels). The direct terms now clamp
N.V (`PBRShadingNoV`, Neubelt and Pettineo 2013): diffuse is independent of
N.V and the Smith term stays finite, so the result is continuous. Environment
terms already clamped.

### OpenGL/Vulkan parity rules

`renderer_pbr_native_gl_parity.py` compares the classic OpenGL owner with
native Vulkan on the same runtime: the specimen patch within two bytes, the
whole frame within the encoded-frame allowance of Stage C, after two
documented exclusions that both come from the classic renderer:

- Classic surfaces. Controls may name a PBR-off capture of the same scene. A
  pixel PBR changed on neither backend belongs to the classic renderer. The
  projected-shadow scene differs by up to 25 bytes on 6% of the frame, all of
  it on the classic walls and floor, where the two backends' classic shadow
  filters differ; the many-light scene differs by up to four bytes of classic
  rounding on the lit room, while its PBR emitter matches exactly.
- Edges. A step beyond the allowance counts as an edge shift when each
  backend's value lies within the other's 3x3 neighbourhood range (at most
  0.05% of the frame). Alpha-tested specimens may also flip up to sixteen
  isolated silhouette pixels: at grazing angles the coverage texture is read
  from its coarsest mips, averaged to the threshold. The classic cutout control
  shows the same flips (20 pixels).

The extreme-emission control is reported but exempt: it exercises Vulkan's
float-HDR auto exposure, and OpenGL's auto exposure follows the modern
visible post path. So are the controls that turn off `r_vkPBRSpecularAA`,
which OpenGL does not expose.

### Stage B laboratory evidence (2026-10-05)

Private build of Stage C plus Stage B, Windows/NVIDIA, runtime
`.tmp/wt-pbr/.tmp/lab-a`. "GL native" runs the laboratory with the modern
visible path off (`--gl-native`), so the classic light loop owns every PBR
surface; each GL-native suite is paired with the Vulkan suite captured in the
same batch from the same runtime and harness.

| Suite | Result |
|---|---|
| Native math | pass, including the continuous shading N.V |
| Material contracts (`renderer_pbr_materials.py`) | pass, including the OpenGL owner and continuous N.V contracts |
| Vulkan direct, 0x | 73/73 (two new PBR-off baselines) |
| GL native direct, 0x | 73/73; parity with Vulkan passes on all 73 controls, 7 exempt with stated reasons |
| GL native ambient | 40/40; independent oracle within 0.91 bytes (translucent alpha controls included); Vulkan 41/41; paired interiors within one byte |
| GL native IBL | 26/26; environment parity with Vulkan passes on 26 controls |
| GL native probes | 40/40; probe proof passes (a 33-record overflow now falls back to the analytic environment, as on Vulkan); parity with Vulkan passes, the cutout controls allowing the classic depth fill's alpha-test edges on 0.25% of covered pixels (26 edge pixels, lighting within one byte, no interior mismatch) |
| GL native diagnostics | 62/62; semantics pass; whole-frame comparison keeps the documented mapped-normal and cutout-boundary set, identical to modern GL's since before Stage A |
| GL native geometry | 11/11; backface parity with Vulkan passes |
| GL native overview (`lit,ownership,no-probes,direct,legacy,master-off`) | 6/6 |
| Modern GL and Vulkan regression suites | Vulkan map 4/4, GL HDR 7/7, GL core 6/6, probes 46/46 and 40/40 with parity, diagnostics 62/62 per backend (same documented set), geometry 11/11 per backend with parity, transparency 25/25, cutout pass, fog 7/7, capacity 18/18, resources 44/44, baked 6/6, HDR scene composition/ambient/recovery pass, HDR-off preview at 4x passes on both backends |

## Stage E: environment lighting in real maps (both backends)

Without authored probes every PBR surface reflected the analytic studio
environment: a bright sky gradient with a key lobe, chosen to qualify the
filtering, not to light a level. In a dark Quake 4 interior it lit every PBR
surface from nowhere, and metals glowed. Quake 4 maps are lit by their lights,
and their authored ambient lights stand in for bounced light. Production
environment lighting now follows the map:

- Authored ambient lights are uniform environments. An ambient light of
  calibrated irradiance E is an environment of radiance E / pi in every
  direction, so it reaches diffuse and specular exactly as the environment
  term does: Fresnel-weighted diffuse with multi-bounce AO, and the split-sum
  specular f0 * A + B with energy compensation, specular occlusion and horizon
  occlusion. A white rough surface still matches the classic ambient term at
  normal incidence; metals now reflect the ambient light instead of going
  black. Per-light passes bind no split-sum table, so the bias B has its own
  fit (`PBRSpecularBias`, a 30-term polynomial in sqrt(N.V) and roughness,
  within 0.0095 of the integrated table; the common analytic approximation was
  0.28 off) beside the existing directional albedo A.
  `PBRUniformEnvironmentSpecular` composes them; a white conductor reflects
  exactly one.
- The analytic studio environment is the laboratory mode
  `r_pbrAnalyticEnvironment` (default 0, not saved), as the linear scene became
  `r_pbrLinearScene` in Stage C. The laboratory pins it on. With it off,
  `r_pbrIBL` draws only authored probes, blended over black, and a view without
  probe records draws no environment pass at all.
- Baked light grids light the OpenGL owner as they light modern GL and
  Vulkan's laboratory linear scene. The owner's environment pass replaces environment diffuse with PBR-weighted
  baked diffuse (Fresnel-weighted, AO-occluded, clamped to the grid's maximum
  contribution), keeps the environment's specular, and the classic grid pass
  skips owned surfaces, so a grid adds its light once. This closes the gap
  Stage B left open. Vulkan's production frame does the same since the
  follow-up below. The same work found a modern GL defect: baked samples
  were decoded to linear light only in the linear-scene laboratory mode, so
  once Stage C composed each draw in the display domain, production frames
  encoded baked PBR diffuse twice. PBR receivers now always decode them.
- Separate metallic, roughness and AO maps are packed at load into one
  generated ORM image (`packORM( ao, roughness, metallic )`, an image-program
  operator), so every backend shades one material-data texture and every
  channel reaches every term. Vulkan's per-light layout had no slot for three
  data maps beside the light's own images, which an ambient light's new
  specular term needs. Maps keep their exact values; differing sizes resample
  to the largest.

### Independent shading oracle

`tools/tests/pbr_reference.py` writes the shading kernel out again in NumPy,
so a regression in the shared C++/GLSL source cannot hide in the oracle that
checks it. Fitted polynomials are copied as definitions; their accuracy is
tested natively (`PBRMathTest`). The module also models the specimen sphere as
the sampling camera sees it (the eye 400 units from a 72-unit sphere, the
16:10 view's focal length), so the ambient oracle predicts the view-dependent
uniform-environment response pixel by pixel instead of at the patch centre.
It compares every pixel with N.V of at least 0.6, where the tessellated
sphere's interpolated normals follow the analytic sphere. The HDR-scene
ambient check and its GL/Vulkan comparison use the same model.

### Laboratory consequences of production environments

The laboratory pins `r_pbrAnalyticEnvironment 1`, so its captures keep the
studio environment its expectations were qualified against. Production is
proved by controls that turn it off: the IBL suite's production control
(no probes) must draw no environment at all, and the probe suite's production
controls prove that authored probes still light a receiver over black.

### Stage E laboratory evidence (2026-10-05)

Private build of Stage B plus Stage E, Windows/NVIDIA, runtime
`.tmp/wt-pbr/.tmp/lab-a`; each GL-native suite is paired with the Vulkan suite
captured in the same batch from the same runtime.

| Suite | Result |
|---|---|
| Native math | pass, including the uniform environment: the fitted bias within 0.012 of the integrated table between its fitting points, a white conductor reflecting exactly one, monotonic in F0 |
| Material contracts (`renderer_pbr_materials.py`) | pass, including the production-environment contract |
| Vulkan ambient | 41/41; independent per-pixel oracle within 0.57 bytes for one draw, 1.0 for composites |
| GL native ambient | 40/40; oracle within 0.68 bytes for one draw and 1.46 for three rounded draws (each further draw into the 8-bit frame may add half a byte); paired with Vulkan the interiors agree within one byte, and 6-16 grazing silhouette pixels shift as edges (allowance 0.05% of the frame) |
| IBL | Vulkan 28/28 and OpenGL 27/27 with parity on 27 controls; the production control (no studio environment, no probes) draws no environment |
| GL native IBL | 27/27; parity with Vulkan on 27 controls |
| Probes | Vulkan 48/48 and OpenGL 42/42 with parity, including the production controls (authored probes over black) |
| GL native probes | 42/42; probe proof and parity with Vulkan pass |
| GL native baked grid | 6/6: grid diffuse on every dielectric station (6-19 bytes), none on metals or zero AO, more at double intensity, drawn in the owner's environment pass |
| Direct | Vulkan 73/73, GL native 73/73, parity on all 73 controls |
| Diagnostics | 62/62 on Vulkan, modern GL and GL native; the whole-frame comparison keeps the documented 10-control set |
| Geometry | 11/11 on every owner; backface parity passes |
| Other regression suites | Vulkan map 4/4, GL HDR 7/7, GL core 6/6, GL native core 6/6, transparency 25/25, cutout pass, fog 7/7, capacity 18/18, resources 44/44, baked 6/6 GL with the Vulkan baked proof, HDR scene composition (GL/Vulkan compare), ambient and recovery pass, HDR-off preview at 4x passes on both backends (40 controls each) |

### Vulkan as shipped (2026-10-05)

The laboratory pins `r_pbrLinearScene 1`, so most Vulkan suites had qualified
the linear scene and float preview rather than the display-referred frame
players see. That gap hid a production defect: Vulkan composed baked grids for
PBR only inside the linear scene, so in an ordinary frame a PBR receiver in a
grid lost its environment pass and took the classic grid pass through its
legacy diffuse stage, metals included.

- The display-referred frame composes a native receiver's grid in its
  environment pass, as the OpenGL owner does: the same grid contract and
  shader, with single-attachment variants of the baked environment shaders for
  display targets. The classic grid pass skips native PBR receivers
  (`VK_PBR_GridOwned`); a receiver the grid contract declines keeps its
  environment pass alone. The baked shaders decode the atlas for PBR in every
  mode; they decoded it only under `r_hdrToneMap`, which the linear scene
  requires.
- `--production` runs a Vulkan suite with the linear scene off. Each
  production suite is paired with the GL-native suite of the same batch: both
  compose every draw into the display-referred frame, so they are compared
  directly. Overview grid controls are judged per station: their frames hold
  the classic room, whose texture filtering differs by a byte or two between
  the APIs, and the laboratory's four-probe DXT1 grid samples differently
  along thin bands of normal directions on OpenGL (modern and native alike)
  and on Vulkan, up to 16 display values on a few hundred pixels, while every
  station agrees within one.
- The extreme-emission control's production reference now models Stage C's
  per-draw encode (display BGR 27.3/13.9/2.9 against the captured 27/14/3);
  it had still modelled the unencoded pre-Stage C composition.

| Suite (Vulkan with `--production`, paired with GL native) | Result |
|---|---|
| Direct | 73/73 with the production emission reference; parity with GL native on all 73 controls |
| Ambient | 41/41; independent oracle passes; paired with GL native |
| IBL | 28/28; environment parity on 27 controls |
| Probes | 48/48; probe proof and parity pass |
| Diagnostics | 62/62; the documented 10-control whole-frame set, as in every pairing |
| Geometry | 11/11; backface parity passes |
| Baked grid | 6/6: 23 receivers composed per view, grid diffuse on every dielectric station and none on metals or zero AO, more at double intensity; every station within 0.96 of GL native |

The laboratory-mode suites of the same batch (Vulkan direct, probes, IBL,
ambient, diagnostics, geometry, transparency, cutout, fog, capacity,
resources, baked, HDR scene, preview) and every GL-native pairing pass as in
Stage E.

## Stage D: SSAO occludes PBR indirect light only (both backends)

Screen-space ambient occlusion (`r_ssao`, off by default) is a whole-frame
post pass: it multiplied the finished frame, so it darkened a PBR surface's
direct light as much as its bounced light, and on top of material AO that
already described the same crevices. Native PBR now treats SSAO as what it
estimates, visibility of indirect light:

- A view whose native PBR owns world surfaces snapshots the world depth twice
  before its prepass, classic surfaces alone and then with native PBR, and
  right after the prepass draws an occlusion field from them (the classic
  pass's own shader, `ssao.fs` / `post_ssao.frag`, in a field mode). Its red
  channel is the occlusion native PBR reads; its green channel the factor for
  classic world pixels; blue marks pixels with world depth.
- Native PBR folds the field into the AO of its indirect light only, as the
  lesser of the two: authored ambient lights, environment and probe light and
  baked grid diffuse, specular occlusion included. Direct lights and emission
  never read it, and neither do translucent surfaces, which the field does not
  describe.
- The post pass then applies the green channel instead of computing the
  occlusion again, so classic pixels darken exactly as before and native PBR
  pixels are left alone. A view without native PBR world surfaces, or with the
  cel world ink on, keeps the classic whole-frame pass unchanged.
- OpenGL binds the field on image unit 14 (the owner now needs fifteen units).
  Vulkan's eight-set contract has no free set, so the field takes the
  material's metallic slot, which packing (Stage E) leaves free; flags 32 and
  64 select it and its row order. Vulkan's linear laboratory scene declines
  SSAO as before, so SSAO frames are always display-referred.

The modern visible GL path, a developer path, kept the whole-frame pass; it
now leaves such frames to the light loop (see "SSAO on the modern visible
path" below).

### Stage D laboratory controls

Eight overview captures per owner (`ssao-*`), every one with SSAO on so that
OpenGL draws all of them through its scene target, which alone moves classic
pixels by a byte. The unoccluded controls fade SSAO out at the nearest
distance (`r_ssaoMaxDistance 16`) instead of turning it off, and the occluded
ones use 2048: the laboratory room lies beyond the default 220-unit fade, so
SSAO had computed no occlusion there at all.

- Native PBR pixels (pure green in the ownership capture) lit only directly
  do not change.
- With the environment as their indirect light, every native pixel lies
  between its direct-only and its unoccluded value, and thousands darken.
- Classic pixels equal, within the last bit of the half-float field, the
  classic pass of the same frame with PBR off; the debug view
  (`r_ssaoDebug 1`) is identical with and without native PBR.
- The OpenGL owner and Vulkan agree per station; the PBR-off baselines are
  classic references.

### Stage D laboratory evidence (2026-10-05)

Private build of Stage E (with the Vulkan production grid) plus Stage D,
Windows/NVIDIA, runtime `.tmp/wt-pbr/.tmp/lab-a`, one batch.

| Suite | Result |
|---|---|
| SSAO, GL native | 8/8: 0 of 182,539 native PBR pixels change under direct light alone; indirect light darkens 3,825 of them, every one within its direct-only and unoccluded values; classic pixels equal the PBR-off frame (92,945 darkened by SSAO); debug view unchanged |
| SSAO, Vulkan production and laboratory | 8/8 each, with the same results (3,799 and 3,827 indirect pixels darkened); paired with GL native per station, the PBR-off baselines being classic references |
| Regression | every Stage E suite and pairing passes again: Vulkan, modern GL and GL native direct (73/73 each, Vulkan production included), ambient, IBL, probes, diagnostics (the documented 10-control set), geometry, transparency, cutout, fog, capacity, resources, baked, HDR scene and preview |

## Stage F: promotion (both backends)

With every channel reaching every term on both owners, PBR materials become a
supported default:

- `r_pbrMaterials` defaults to 1. Stock materials are never PBR, so stock
  frames are unchanged. Every archived profile carries the cvar, so a profile
  saved under the old default (0) switches once
  (`R_MigrateLegacyPBRMaterialsDefault`, flagged by the archived
  `r_pbrMaterialsDefaultMigrated`, run with the other migrations after the
  archived configs); a later 0 is a player's choice and is kept. The
  renderer's default-safety inventory expects it on.
- A frame that draws no PBR-authored material skips every per-frame PBR
  preparation on both backends: the scene packets, the material contract
  table, and the probe atlas and clusters (`R_ScenePackets_CommandStreamHasPBR`
  walks the frame's draw lists first). Before, `r_pbrMaterials 1` built them on
  every frame, stock content included.
- Authored reflection probes stay opt-in (`r_rendererReflectionProbes 0`):
  enabling them starts the modern scene-packet pipeline, and on OpenGL the
  modern executor as a sidecar, on every frame. Production PBR takes its
  environment from ambient lights and baked grids (Stage E); a map or mod that
  authors probes turns them on.
- No menu control. The setting changes nothing in stock content, so a menu row
  would offer players a switch with no visible effect, and the SYSTEM page's
  settings catalog is frozen against its recovery journal: a field means a new
  catalog version, a journal upgrade and retained-page state. `r_pbrMaterials
  0` stays the documented switch for a mod's classic look.
- README, the user guide, the capability matrix and the roadmap describe PBR
  materials as a supported default.

Remaining limitations, documented in the user guide: surfaces posed on the
GPU (`r_gpuSkinning 1`, packed MD5R meshes, both off by default) keep their
classic stages on OpenGL; the modern visible GL path, a developer path, keeps
whole-frame SSAO; box-parallax probes and runtime probe capture do not exist;
qualification is Windows/NVIDIA, with other platforms' release review open.

### Stage F evidence (2026-10-05)

| Check | Result |
|---|---|
| Stock map, OpenGL, fresh profile | Air Defense 1 renders normally with no warnings; `PBR materials: effective=1`, `PBR material resources: records=0` (no table built), the native owner admitted nothing and never loaded its programs; default-safety report conservative with `pbr=1 probes=0` |
| Stock map, Vulkan, fresh profile | renders normally; `records=0`; the default-safety report shows `pbr=1` and its pre-existing `rollback` issue only (Vulkan has no GL legacy bridge) |
| Migration | a profile with `seta r_pbrMaterials "0"` logs the migration and archives `r_pbrMaterials 1` and the flag; with the flag already set, a deliberate 0 stays 0 (`effective=0`) |
| Laboratory | the full batch passes on the Stage F build: every Vulkan, modern GL and GL-native suite, every production and SSAO pairing, diagnostics with the documented set. The GL-native probe suite failed once on scene setup under machine load (its specimen spawned twice, a laboratory console-timing race) and passed on rerun with both probe pairings |

### Cross-module audit after promotion (2026-10-05)

The stages were qualified on Windows, where MSVC links every module. A Linux
GCC build of the promoted tree with CI's options (debug, forcefallback,
native tests) compiles and links the client, the dedicated server, both game
modules, both renderer modules and the native tests, and the renderer
modules resolve every symbol (`ldd -r`). Two regressions surfaced outside
that qualification and are fixed:

- The shared world-interaction domain (`r_rendererSharedWorldInteraction`,
  opt-in) rejected every view while `r_pbrMaterials` was on, so promotion
  switched it off on stock maps: on Air Defense 1 it owned the view with PBR
  off (`ready=1 lights=5 surfaces=183`) and fell back with PBR on, on both
  backends. The view gate now covers only the switches that reinterpret stock
  materials; `ValidateSurfaceMaterial` still rejects every PBR-authored
  receiver. The gameplay benchmark's interaction profile expects that
  ownership on stock scenes.
- The OpenGL ES module compiles `tr_backend.cpp` and `ModernGLExecutor.cpp`
  but not `draw_pbr.cpp` or `draw_common.cpp`, and links with `-z defs`.
  Stage B's two calls into the native owner are compiled out there
  (`OPENQ4_RENDERER_GLES_MODULE`, as `RenderSystem_init.cpp` and
  `Interaction.cpp` already were), and Stage E's shared baked-grid packing
  (`RB_LightGridBakedParams`) moved from `draw_common.cpp` into
  `ModernGLExecutor.cpp`. With the Android branch's ES compile fixes applied,
  every ES object compiles and the link reports only the twelve OpenGL-only
  symbols that predate this plan, which that branch stubs in
  `gles_Backend.cpp`; before the fix it also reported these three. main's ES
  module did not compile on desktop Linux by itself, for desktop-GL calls in
  four shared files that predate this plan; see "The OpenGL ES module
  builds again" below.

CI builds neither the ES module nor this closure, so
`renderer_pbr_materials.py` scans every translation unit the Vulkan and ES
modules compile for `RB_GLPBR_*` calls outside a branch that excludes the
module (with a negative control), and pins the baked-grid helper to
`ModernGLExecutor.cpp`. A libc++ (clang 18) syntax pass over every C++ file
the plan touched, 52 compile commands across the client, both renderer
modules and the native tests, is clean, and the PBR math test passes against
both libstdc++ and libc++.

The PR validation profile on the promoted tree failed one check: the
vid_restart route harness compiles `InitOpenGL` with stubs and had none for
the new migration. The harness now stubs it and expects the three
migrations in order.

| Check on the fixed build | Result |
|---|---|
| Shared world interaction, Air Defense 1, PBR on | owns the view on OpenGL and Vulkan (`ready=1 lights=5 surfaces=183`), as with PBR off; on the PBR laboratory map it falls back at the first PBR receiver (`failure=enhancedMaterial`, with its draw packet) |
| OpenGL owner and Vulkan production | direct 73/73 each, parity 73/73; ambient 40 and 41 controls, oracle and parity pass; environment 27 and 28, parity 27; diagnostics 62/62 each, the documented 10-control whole-frame set; SSAO 8/8 each, parity 8; baked grids 6/6 each, parity 6 |
| OpenGL owner and the Vulkan laboratory | direct parity 73/73, ambient and environment parity pass, diagnostics the documented set |
| Modern GL and Vulkan laboratory | Vulkan direct 73/73, ambient 41/41, IBL 28/28 with modern GL 27/27 and parity, diagnostics 62/62 each, baked 6/6 each. Modern GL diagnostics first failed every capture while the PR profile loaded the machine: its specimen spawned twice (the laboratory's console-timing race), the error dropped the client to the menu, and it passed 62/62 on a quiet rerun |

## Remaining limitations, resolved

### Animated and converted models on OpenGL

The listed limitation was half wrong. `r_gpuSkinning 1` never left PBR
surfaces classic on OpenGL: its compute pass writes a posed `idDrawVert` cache
that every draw path, the native owner included, reads like CPU-skinned
geometry. The skinned laboratory controls (`skin-cpu-*`, `skin-gpu-*`, never
in a batch before) pass 10/10 on the OpenGL owner and on Vulkan production;
GPU skinning matches the CPU reference and the specimen is PBR-owned.

Packed MD5R was a real gap. A model converted with `r_convertMD5toMD5R`
draws its primitive batches through the md5r vertex programs, which pose
rest-pose vertices on the GPU, so the owner declined them
(`gpu-posed-geometry`). Vulkan never uses packed batches; it CPU-skins
classic geometry. Now OpenGL does the same for a PBR-authored mesh
(`R_MD5R_MeshUsesPackedRuntimeSurface`, decided by the authored material so the
static and both dynamic paths agree), and the GPU-posed test reads only the
primitive batch: a classic MD5R surface keeps a skin-to-model table for GPU
skinning's compute pass, but its vertex stream is posed. `printModel` marks
such a mesh `[classic: PBR]`. A packed surface whose entity skin swaps in a
PBR material still keeps its classic stages.

New `skin-md5r-*` controls convert the skinned specimen at load (they run as
their own process). Before the change the OpenGL owner left it classic
(`MD5R model`, packed batches, ownership failed); after, 5/5 on the OpenGL
owner and on Vulkan production, with the rest pose and the ownership view
identical to the unconverted CPU reference. The bent pose differs from it by
about three bytes on both backends alike: the converted model's CPU path
re-derives its tangents where the MD5 path skins the authored basis, which
the MD5R track fixes on `origin/main` (66ebfed8). The engine's ARB2
receiver self-test now models a packed surface with its primitive batch and
checks that a classic MD5R surface stays a mapped receiver.

### The OpenGL ES module builds again

Shared renderer code that landed after the Android port was last validated
(2026-09-08) used desktop-only GL, so main's ES module stopped compiling,
for Android and desktop GLES alike, and nothing in CI noticed. The Android
review branch had already fixed it (`claude/gles-android-support-d5763a`,
3ce8167b0, "Build the OpenGL ES renderer module again"); main now carries
those changes unchanged, so merging the branch later sees identical hunks:
the ten ES pixel-store names in `idGLPixelTransferScope`, runtime-resolved
`glGetTexLevelParameteriv`, refusals where ES has no `glGetTexImage`, ES
names for the desktop multisample and matrix enums, and "not taken" stubs
for the twelve OpenGL-only functions the kept front end calls. A Linux GCC
build with `-Dbuild_renderer_gles=enabled` now compiles and links every
target, the ES module under `-z defs`, and `ldd -r` finds no undefined symbol
in the OpenGL, Vulkan or ES module.

### Box-projected parallax probes

A probe flagged `boxParallax` is a box, not a sphere: its light volume
(`light_radius` half extents along the light's axes, around its origin) is
the room its cubemap shows. Each owner looks a reflection up where it leaves
the box (`PBRBoxParallaxDistance`) and weighs the probe by its distance inside
the faces over `blendFraction` of the smallest half extent (`PBRBoxInfluence`).
Both come from the shared kernel in `PBRMath.h`, so Vulkan, the OpenGL owner
and the modern GL path evaluate one formula, and `PBRMathTest` sweeps them
against a slab-intersection reference. The probe record carries the half
extents as a seventh vec4 (112 bytes; the OpenGL owner's record texture is
seven texels wide). A box may have unequal half extents; a sphere probe still
needs equal radii, and its bounding sphere still selects it per cluster.

The probe suite adds seven controls on a mirror sphere reflecting the warm
room's far-wall stripe:

- A box probe moved 150 units to +X moves the reflected stripe to screen
  right, a mirrored probe moves it left, and a plain probe at the same offset
  keeps it centred: the mean right-minus-left brightness of the specimen
  patch is +24.7, -24.8 and +0.9 (the check requires twice the plain value).
- A shallower box (`light_radius 600 300 600`, accepted where the sphere
  control `invalid-volume` rejects it) moves the stripe further.
- Its blend margin is measured from the box faces (`box-fade` against a
  narrow-margin `box-hard`).
- Outside the box, within its bounding sphere, the probe is published and
  selected but has no weight: the frame equals the analytic control exactly.

### Probes captured in the engine

`bakeReflectionProbes [size] [blends]` captures every native-cube probe of
the loaded map from its light origin, in the light's axes, writes the faces
its `cubeMap` names under `fs_savepath` and reloads the image, so the probes
use the capture at once on either backend. The capture leaves out post
process and glow stages, subviews, view models, bloom, motion blur, tone
mapping, exposure, CRT filtering, gamma/brightness and authored probes,
restoring them afterwards. openQ4 searches `fs_savepath` last, so the command
warns when another copy of the faces would still load. `cameraCubeMap` probes,
non-point lights and cube images shared by several probe lights are skipped.

Writing it found that `envshot`, whose capture path the command reuses, sized
its view in window pixels where view rectangles are virtual-screen units: a
128-pixel capture in a 1280x800 window drew a 256x213 view and kept its
corner. Both now use the 640x480 virtual screen, as levelshots do. The
light-grid bake shared the sizing; its fix (55abaa03), and whether to re-bake
the grids shipped in `pak1`, are handled separately. With whole faces the
laboratory's own grid varies more with direction: the baked controls still
pass 6/6 on every owner, and the documented band difference between the APIs'
DXT1 sampling grows to 1.12 bytes on one station mean (1.33 with the doubled
grid), so baked-grid stations are now judged within 1.5 bytes; SSAO stations
keep one byte.

The `baked` control bakes two probes at 128 pixels: one in the dark
laboratory room, holding a red and a blue unlit marker behind the camera, and
one far from the specimen, so a single command captures several. The `-Y` face must
show red at the top right and blue at the bottom left, where GL's cube
convention puts them (measured centroids 0.74/0.34 and 0.28/0.66, predicted
0.73/0.35 and 0.29/0.65), and the mirror sphere must reflect red above and
right of its centre and blue below and left (measured within three pixels of
the prediction). The face check pins the capture to the convention authored
cubemaps use; the reflection check pins the atlas lookup to it. The markers
are textured: the modern GL path drops a stage's color modulation.

| Suite | Result |
|---|---|
| Probes, Vulkan laboratory and production | 56/56 each, probe proof passes |
| Probes, modern GL and the OpenGL owner | 50/50 each (Vulkan's failure-injection controls are Vulkan-only), probe proof passes |
| Probe parity | modern GL/Vulkan, OpenGL owner/Vulkan and Vulkan production/OpenGL owner pass; the box and baked controls agree within two bytes |
| Box and baked measurements | identical on all four owners |

### SSAO on the modern visible path

The modern visible GL path (`r_rendererModernVisible 1`, a developer path)
draws whole frames with its own PBR and had applied SSAO to the finished
frame, direct light included. It cannot read the occlusion field, so a frame
whose render graph requests SSAO and that draws a PBR material now declines to
the light loop (`R_ModernGLExecutor_DeclinePBRUnderSSAO`, blocker
`pbr-ssao-indirect-only`), whose native owner applies SSAO to indirect light
only. Frames without SSAO or without PBR are unchanged. The SSAO suite now
also runs on that path: each of its PBR controls declines with that reason,
the native owner admits the specimen, and the results equal the OpenGL
owner's (182,539 native pixels, none changed by direct light, 3,825 darkened
indirectly, no classic pixel changed). It passes 8/8 and pairs with Vulkan
production, as the OpenGL owner and Vulkan production also pass 8/8 each.

### OpenGL contexts without GLSL 1.30

The OpenGL owner's receivers are GLSL 1.10, but its environment, emission and
translucent programs are GLSL 1.30. On a context without 1.30, such as the
GL 2.1 legacy context macOS gives openQ4 (GLSL 1.20), the receivers compiled,
so the owner admitted PBR surfaces and then failed to build the environment
program on first use: on a Mac those surfaces would render without indirect
light and print shader errors. The owner now requires
`glConfig.GLSL130Available` (`RB_GLPBR_ContextSupported`); without it PBR
materials keep their classic stages and the console says so once.

Under an emulated Apple GL 2.1 context (WSL Mesa llvmpipe with GL 2.1, GLSL
1.20, Apple's extension list and `r_forceAppleGL21InteractionCorridor 1`),
the laboratory's PBR controls crashed the client before the change: Mesa's
compiler faulted on the GLSL 1.30 environment program, which Apple's would
reject. With the change the client renders them like the PBR-off controls,
prints the note once and declines every PBR surface (`declined=115
lastDecline=resources`). Its only warnings are the two the PBR-off controls
also print: the `gl45` tier falls back to the legacy one, and vertex arrays
live in system memory.

### Other GPUs and platforms

The stages were qualified on an NVIDIA RTX 4060 Laptop GPU on Windows. The
same suites then ran on three more stacks, each OpenGL run paired with a
Vulkan run of the same build and runtime:

| Stack | Result |
|---|---|
| Windows, Intel Iris Xe (Vulkan production on the integrated GPU, `r_vkDevice 2`; OpenGL owner on NVIDIA for the cross-vendor pairs) | direct 73/73, ambient 41/41 and its oracle, environment 28/28, diagnostics 62/62, baked grids 6/6, skinned 10/10, converted MD5R 5/5; direct parity 73/73 and environment parity 27/27 across vendors. SSAO passes 7 of 8: `ssao-on` changes 6 of 833,291 classic pixels and 9 debug-view pixels with native PBR, deterministically (NVIDIA: none) |
| Linux Mesa 25.2.8 (WSL2 Ubuntu 24.04 under Xvfb): the OpenGL owner on llvmpipe (LLVM 20.1.2), Vulkan production on lavapipe | direct 73/73 each, parity 73/73; probes 50/50 and 56/56 (box and baked controls included), parity passes; SSAO 8/8 each, parity 8/8; environment 27/27 and 28/28, parity 27/27; ambient 40/40 and 41/41, with the oracle and parity passing every check but one: on lavapipe one pixel of 1,024,000 differs by one byte between the scalar material and its packed and separate texture forms, where the check demands byte equality (llvmpipe and the Windows GPUs are exact) |
| Apple's GL 2.1 legacy context, emulated on the same Mesa (see above) | PBR materials keep their classic stages without warnings of their own; the frame matches the PBR-off controls |

Mac hardware was not available. Vulkan on macOS runs through MoltenVK, which
these suites have not exercised.
