# Native Vulkan PBR environment lighting

Status: implemented and locally qualified at 0x/4x MSAA on Windows/NVIDIA.
This records the analytic environment contribution for admitted authored PBR
surfaces. Since Stage E of the
[production-readiness plan](archive/2026-10-18/plans/2026-10-04-pbr-production-readiness.md) the
analytic studio environment lights only the laboratory
(`r_pbrAnalyticEnvironment 1`); production environment light comes from
authored probes, baked light grids and ambient lights. [Authored reflection probes](vulkan-pbr-probes.md) also have local
LDR qualification at 0x/4x. Baked PBR diffuse composes in the environment
pass ([baked lighting](vulkan-pbr-baked.md)); full scene color parity remains
open; Vulkan remains experimental.

The existing `r_pbrIBL` and `r_pbrIBLIntensity` controls now drive a native
once-per-surface pass. Its lazily generated RGBA16F atlas uses the same analytic
source, GGX convolution, diffuse irradiance and split-sum BRDF integration as
OpenGL. Seven separately convolved mip levels retain at least 4x4 samples per
face. Face coordinates address texel centers, and explicit adjacent-level
sampling keeps filtering inside the selected atlas cells. The atlas reserves
the existing authored-probe slots, now populated by the separate native probe owner.

The pass shares direct-material admission and supports scalar, packed ORM and
separate data, AO, XYZ/RG/AGB normals and the existing specular footprint filter.
Object-space normals and view directions are transformed into world space for
environment lookup. Opaque and matching cutout draws use the existing depth
coverage, now sourced from the admitted material's typed albedo rather than a
classic image copy with potentially different alpha mips. See the
[cutout regression and remaining MSAA differences](vulkan-pbr-cutout.md).
The ordinary material walk visits eligible PBR materials even when
they contain no ambient stage. Shared classic ambient replay yields these
materials to that walk.

Translucent coverage first composites black over the full ambient mesh through
its authored alpha. Each direct light then adds through that alpha,
using its original receiver triangles and scissor. Light records include entity
identity, so separate objects that instance the same model cannot share lighting.
With all lighting disabled, the admitted surface still composites black through
its alpha instead of returning to the unlit classic color stage. The environment
adds over the full mesh after direct lighting; unavailable indirect-light
resources cannot suppress the coverage pass or the recorded direct lights.
Admission is evaluated even when the view contains no direct lights. Existing
whole-view rejection for shadowing translucent receivers remains in place.
Authored [ambient light stages](vulkan-pbr-ambient.md) now also take part in
that complete record bound and ordered replay, with their own PBR diffuse
response. They remain separate from the once-per-surface environment source.

Generated image ownership handles image reload and device restart. Every mip
must upload successfully before the atlas is usable; a partial upload purges
the image. Ordinary stock materials and disabled PBR do not request it.

The atlas keeps a sampler of its own that addresses the whole mip chain
(`VK_Image_UseExplicitMipChain`). From c850233d (2026-09-25) until 2026-10-04,
an explicit `TF_LINEAR` sampler clamped every image to its base level to match
`GL_LINEAR`. The atlas is `TF_LINEAR`, so every explicit-LOD read returned the
mirror level: rough Vulkan reflections and authored probes showed an unfiltered
key highlight, and GL/Vulkan IBL parity failed `rough-high` and `double`
(maximum 4 bytes; 11 once energy compensation brightened the specimen). With
the dedicated sampler all 26 paired IBL controls match exactly. The OpenGL
atlas is a raw texture with `GL_LINEAR_MIPMAP_LINEAR` and was never affected.

Since 2026-10-04 the pass applies the shared roughness/AO kernel: specular
occlusion and multi-bounce AO, horizon occlusion against the interpolated
vertex normal, and multiple-scattering energy compensation from the split-sum
table's `A + B`. See the [production-readiness plan](archive/2026-10-18/plans/2026-10-04-pbr-production-readiness.md).

The opaque environment pass checks the existing baked receiver rules per surface:
the default `r_useLightGrid 1` switch no longer disables environment lighting
when the map or receiver has no eligible baked grid. The frozen v21 regression
passes 15 controls on each backend at 0x and 4x: analytic lighting, authored
probes, metal, cutouts and transparency all remain byte-identical when the grid
switch is enabled and restored. The v19 negative fails the four opaque cases.
The 60 captures and 40 exact comparisons are pinned in
`.tmp/vulkan-gap-closure/pbr-grid-default/checkpoint-v21.json`.
Baked receivers use a [combined baked/environment
owner](vulkan-pbr-baked.md). It replaces classic grid and environment diffuse
with PBR baked diffuse, preserving environment specular: per surface in an
ordinary display-referred frame, and prepared for the whole view in the
laboratory's linear HDR scene, where unsupported views keep the existing grid
path. Transparent surfaces do not receive the classic grid
and keep their environment pass.

## Qualification

The `ibl` laboratory suite switches off every direct light and exercises
27 Vulkan controls: data layouts, AO, intensity, roughness, normal encodings,
cutouts, transparency, exact rollback/restoration, shared ambient, image reload
and partial/full video restart. OpenGL runs the same 26 common controls. Its
shared-ambient switch deliberately excludes the aggregate modern PBR owner,
so the extra shared-ambient control belongs to Vulkan only.

Use an independent laboratory runtime prepared by
`tools/tests/renderer_pbr_laboratory.py --prepare`, then run fresh output paths:

```text
python tools/tests/renderer_pbr_laboratory.py --runtime-root <laboratory> --basepath <retail-assets> --output-dir <vk-output> --backend vk --suite ibl --samples 0 --batch
python tools/tests/renderer_pbr_laboratory.py --runtime-root <laboratory> --basepath <retail-assets> --output-dir <gl-output> --backend gl --suite ibl --samples 0 --batch --gl-debug
python tools/tests/renderer_pbr_environment_parity.py --vk-report <vk-output>/report.json --gl-report <gl-output>/report.json --output <comparison.json>
```

Repeat both runs with `--samples 4`. The comparator requires the same runtime
package, fixture, compiled map, sample count and harness; verifies retained
capture/log hashes; reruns the individual proof gates; and bounds both average
image error and the fraction of significantly different channels. These are
controlled specimen comparisons, not whole-frame HDR or performance evidence.

The isolated cutout has separate filtered and hard green coverage captures.
Hard masks must match exactly. At 4x, filtered masks may differ by one sample
at no more than 5% of pixels, with at most 1% aggregate coverage error. This
accounts for the coordinate-dependent alpha-to-coverage conversion allowed by
the [Vulkan specification](https://github.khronos.org/Vulkan-Site/spec/latest/chapters/fragops.html#fragops-covg).
Lighting is then checked independently: holes remain black, common fully
covered pixels agree within two bytes, and colors weighted by measured coverage
must agree within quantization bounds. Unmatched single-sample edges cannot
exceed the fully covered specimen's radiance. Other material controls retain
the original mean/fraction tolerances; raw cutout differences remain reported.

The independent native math test covers all 31,744 nonnegative finite binary16
values and their midpoint rounding, alongside existing furnace, convolution,
cube-seam, irradiance and BRDF integration checks.

Evidence lives in `.tmp/vulkan-gap-closure/pbr-environment/`. The first runtime
retains a rejected copy missing two laboratory AAS files. The first cross-backend
comparison retained the zero-direct-light transparency failure and a mistaken
GL shared-ambient expectation; both informed the final controls rather than
being counted as qualification.

The v4 runtime passes all 25 Vulkan and 24 OpenGL controls at 0x, with at most
one byte of channel difference in the common specimen patches. Its 4x Vulkan
run fails image reload: intrinsic generators reset adopted forward resolve
images to 16x16 RGBA16F/depth placeholders, replacing the game's actual
dimensions and formats. Scratch ownership now takes precedence over the
original generator in both reload and load-after-purge. Generated persistent
images that have not been adopted still regenerate, including the PBR atlas.
The v5 GPU regression passed direct scratch adoption at both sample counts,
but the scene still failed: the public `CreateImage` path bypassed that adoption
for existing images. It now uses the scratch owner for both new and existing
images, and the regression follows the public path. The retained v5 gameplay
failure is not qualified evidence. The v7 GPU regression and paired gameplay
suites pass after this correction, including exact image-reload restoration.

The v6 runtime closes the live reload defect: the 4x Vulkan image is identical
to the entire pre-reload capture, and both suites pass individually (25 Vulkan,
24 OpenGL). The strict cross-backend comparator still rejects cutout edges:
mean error 0.563/255, maximum 14, with 9.85% of channels above two bytes. Other
opaque controls remain within one byte. The two backends used different
alpha-to-coverage inputs: GL's admitted PBR pass normalizes alpha around the
threshold using its pixel footprint, while Vulkan used the classic alpha test.
Native admitted PBR depth and matching emission now use that filtered coverage;
classic and rejected materials keep their existing rules.

The final v7 runs include both coverage controls and hide background specimens.
All four reports are complete, with identical runtime and harness provenance,
unchanged runtime files, and no tracked rendering diagnostics:

| Evidence under `.tmp/vulkan-gap-closure/pbr-environment/` | Result |
|---|---|
| `ibl-vk0-v7/report.json`, `ibl-vk4-v7/report.json` | 27/27 controls each |
| `ibl-gl0-v7/report.json`, `ibl-gl4-v7/report.json` | 26/26 controls each, synchronous GL diagnostics |
| `parity-0-v7.json`, `parity-4-v7.json` | All 26 common controls pass at each sample count |
| `gpu-v7/renderer_validation_report.json` | 3/3 suites: attachments/scratch lifecycle, HDR and temporal motion |
| `coverage-negative-v7.json` | Current cutout passes; the retained v6 shader fails the coverage bound |
| `direct4-v7/report.json` | 68/68 native direct, emission, cutout, transparency, fallback, restart and shadow controls at 4x |
| `overview-vk-v7/report.json`, `overview-gl-v7/report.json` | 6/6 broader laboratory controls each |

At 0x every common color patch differs by at most one byte. At 4x the cutout's
raw mean error is 0.0389/255, with maximum six; hard masks match exactly.
Filtered masks differ by at most one sample at 0.876% of pixels (0.220%
aggregate coverage). All 2,076 common fully covered pixels agree within one
byte, holes are black, and all 6,393 overlapping color channels pass the
coverage-weighted check. The same gate rejects the retained v6 shader's
two-sample discrepancies at 9.44% of pixels (3.01% aggregate coverage).
Image reload and partial/full video restart restore each backend's reference
exactly. These are controlled local material proofs; authored probes, baked
PBR diffuse, full scene color transfer and broader hardware qualification
remain separate requirements.

The broader room retains correct transparency ownership: ownership minus
emission is `(0,112,0)` on Vulkan and `(0,112.081,0)` on OpenGL. Its descriptive
full-frame comparison with authored probes disabled has mean error 0.882/255,
against 1.002 with environment lighting disabled and 0.920 for the classic
path. This average is not a parity gate: the environment-lit frame still has
p99 error 19, maximum 161, and 2.38% of channels differ by more than two bytes.
The fifth roughness column, cutout and transparent specimens retain localized
differences that also appear in the direct-only comparison; their attribution
remains open. `overview-color-v7.json` records the complete-frame metrics and
report hashes. Engine-derived PNGs under `inspection-v7/` were inspected.

## Partial-light transparency

The subsequent per-light investigation separates two issues. The broader
OpenGL/Vulkan discrepancy is concentrated in the laboratory projector; individual
point-light whole-frame mean errors are 0.023-0.033/255, versus 0.198 for the
projector. Native receiver triangles exclude surfaces outside its light volume.
The GL clustered path evaluates clamped white projection/falloff images without
the same receiver-triangle membership, and its transparent loop also omits the
light scissor. These are coverage differences, not evidence that the analytic
environment needs a different BRDF. Complete projected-light parity remains open.

A separate native Vulkan defect is reproduced with a transparent sphere and two
projectors, each covering only part of it. The previous first-light composite
attenuated the background only on that light's triangle subset. Switching lights
therefore changed opacity, and a second instance of the same model could replay
the first instance's local-space lighting. The full-mesh composite, per-entity
record identity and original-light scissor now correct those contracts.

`tools/tests/renderer_vulkan_pbr_transparency.py` captures 25 controls: ownership,
black opacity over an emissive background, direct and environment lighting with
zero/left/right/both lights, a second unlit model instance, restoration, image
reload, partial/full video restart and reversed light creation order. It checks
the independent source-alpha and additive-light equations. Foreground material
coverage is checked separately from the room, whose classic lighting legitimately
changes when lights switch. The proof requires actual direct and environment
lighting effects and retained capture/log hashes. Use `--samples 0` and `4` with
an independent laboratory runtime.

Evidence is retained under `.tmp/vulkan-gap-closure/pbr-direct-parity/`.
The subsequent record-capacity qualification is documented below. General
resource failure and native ownership of shadowing transparent views remain open.

The final v9 renderer is identical in `builddir`, `.install` and the independent
test runtime (SHA-256 `75ede5a3c15a941b6a66cc7c7d98c2f36527aa83fb59da309af9985d3053a926`).
The engine, GL module and laboratory inputs match the preceding v7 checkpoint.
All retained runtime inputs remain unchanged during these runs:

| Evidence under `pbr-direct-parity/` | Result |
|---|---|
| `transparency-v9-0/report.json`, `transparency-v9-4/report.json` | 25/25 each, including every image equation |
| `overview-v9/report.json` | 6/6 broader room controls |
| `alpha-ibl-v9-0/report.json`, `alpha-ibl-v9-4/report.json` | 3/3 existing environment transparency controls each |
| `regression-comparison-v9.json` | All 12 retained-reference comparisons pass |
| `transparency-negative-replay-v8.json` | The current foreground predicate rejects the v7 defect and accepts its repaired v8 counterpart |
| `emissive-clipping-controls-v7.json` | Identical emissive masks disprove the separate scissor-leak suspicion |

Both sample counts retain exact foreground opacity and zero light contribution
on the unrelated instance. Direct and environment-plus-direct light additivity
have maximum byte error zero. The authored-alpha masks contain 64,721 fully
covered pixels at 0x and 64,257 at 4x. Every restoration, image reload, partial/full
restart and light-creation-order comparison is byte-identical across the entire
frame. All 62 controls retain active Vulkan validation and no tracked rendering
diagnostics. Engine-derived PNGs in `inspection-opacity-v9/` were inspected.

The six existing environment-only transparency images and both classic rollback
frames are byte-identical to v7. All broader-room pixels outside the transparent
specimen are also unchanged; its lit images differ by at most one byte. This
confirms that the repaired partial-light cases do not redefine ordinary room
lighting. The separate GL/projector receiver-coverage discrepancy remains open.

An initial diagnostic omitted explicit light orientation and therefore produced
no direct-light effect; it is not qualification evidence. The first v8 comparison
also incorrectly demanded unchanged classic room lighting when projectors were
enabled. The corrected comparison isolates the authored foreground rectangle,
keeps a zero-error coverage requirement, and requires light effects on the actual
PBR specimens. It still rejects the old binary's opacity errors up to 112 bytes
and cross-instance lighting up to 39 bytes. Original reports remain retained.

Automatic approval review rejected deletion of the superseded `runtime-v8` copy
with only `blocked by policy`; no part of that cleanup command ran. It remains
intact. Earlier blocked `hdr-highlight-v1` through `v3` cleanup is unchanged.

## Transparent record capacity

The v9 renderer can exhaust its 256-entry transparency table partway through
the light loop. Its old rejection path replays native PBR records additively
while retaining the authored classic alpha stage, mixing two owners. If the
new surface had no earlier record, that path did not even preserve a rejection
marker for the material walk. The retained 65-instance/four-light capture is
validation-clean but differs from the complete classic reference by up to
254 bytes across 89,406 color channels.

Vulkan now decides capacity before the first interaction draw. Each admitted
canonical bump/diffuse/specular sequence emits at most one native record per
active light stage. The view preflight sums that conservative bound, excluding
fog, blend and ambient lights. If it exceeds 256, all translucent surfaces keep
their classic lighting and blend stages. No recorded native work needs to be
returned halfway through a surface. A violation of the proven bound is now an
internal error instead of a mixed rendering fallback. Resource availability can
reduce the number of records; it cannot increase this upper bound.

The admission decision is cached once for the view, independently of the
interaction state borrowed by the fog pass. `gfxInfo` prints its reason,
`requiredAtLeast`, capacity, recorded light draws, replayed contributions and
composited surfaces. The bound saturates at 257 when the scan first proves
overflow; it is not a total count of the remaining rejected scene.

`tools/tests/renderer_vulkan_pbr_capacity.py` captures 18 controls at each sample
count. Both `capacity-v10-0b/report.json` and `capacity-v10-4/report.json` under
`.tmp/vulkan-gap-closure/pbr-capacity/` pass, with active Vulkan validation,
unchanged runtime inputs and no tracked diagnostics. The exact-limit case
records all 256 draws and composites 64 surfaces. At 65 instances with four
lights, admission reports `reason=capacity`, bound 257, and zero native records
or composites. Reducing that to three lights admits 195 records; switching all
lights off still composites all 65 surfaces. The single-layer ownership masks
contain 29,802 fully covered pixels at 0x and 29,577 at 4x.

Every whole-frame overflow comparison is byte-identical to the classic
reference, including debug and environment-light controls. Restoring the
instance count, image reload, partial video restart and full restart restore
their respective native reference exactly. Real lighting at the exact limit
differs from classic rendering in over 73,000 sampled foreground channels,
preventing an always-classic implementation from passing this gate.

The independent runtime's Vulkan module matches `builddir` and `.install`:
SHA-256 `43afef433bdee5c0eb85da45307d4fa84d629596a00f98087e16df9c7a20bec8`.
The engine, GL module and fixture retain their v9 inputs. The first minimal test
package omitted the required `baseoq4/mod.json` and stopped before rendering;
that failed `capacity-v10-0` report remains retained. The unchanged v9 manifest
was restored before qualification and is pinned with all 50 retained runtime
files in `runtime-v10-final-provenance.json` (one map path has both slash spellings).

This v10 result closes ordinary bounded record exhaustion for the tested native
transparency path. Resource preparation is qualified separately below;
shadowing transparent ownership and broader hardware/platform qualification
remain separate requirements.

The same v10 binary also passes all 25 partial-light/instance controls at both
sample counts. `retained-reference-v10.json` verifies that all 50 complete TGA
files are byte-identical to their v9 references, and retains the old renderer's
failing capacity comparison. The two static material/Vulkan safety contracts
pass, and engine-derived capacity PNGs were inspected.

## Admission across fog

The fog walker resets `interPass` for its own drawing state. Previously that
also cleared native transparent admission before the post-fog material walk,
which could discard the recorded PBR lighting and restore the classic stage.
Keeping the admission decision in dedicated view state preserves it through
this boundary.

`tools/tests/renderer_vulkan_pbr_fog.py` isolates one transparent sphere, four
lights and the laboratory fog volume. It independently captures the fogged
background and requires the authored source-alpha equation over the complete
interior mask, plus nonzero native record/composite counters. The seven controls
also check fog removal/restoration and unchanged output when the shared fog
option is toggled. Both `post-fog-v10-0b/report.json` and
`post-fog-v10-4/report.json` pass with validation active, unchanged runtime inputs
and no tracked diagnostics. This is transparent compositing qualification;
broader authored fog and shadow interactions retain their separate gates.

The initial `post-fog-v10-0` setup attempted to disable a fog stage with constant
color registers using `Off()`. Its intended clear reference remained fogged, and
the coverage/effect checks rejected it. The corrected harness removes the fog
entity for the clear control; it retains the same one-byte source-alpha bound.

`post-fog-negative-v10.json` reapplies only the image equations to the old v9
runtime and both repaired runs. It rejects the old renderer with maximum error
112.016/255, independently of its missing new telemetry, and accepts v10 with
error below 0.385/255 at both sample counts. Every fully covered pixel in the
29,802-pixel (0x) and 29,577-pixel (4x) masks has a visible fog background. Fog
removal restores the clear frame exactly, and toggling the shared fog option
produces identical ownership and lit frames on v10. Engine-derived ownership
PNGs retain the before/after comparison.

## Transparent resource preparation

Capacity admission alone cannot promise that a later coverage, direct-light or
environment draw will have its resources. Native transparent views now prepare
all three before the light loop writes color. Each draw retains its pipeline,
descriptor sets, uniform offsets and exact vertex/index ranges. The material
walk also binds the retained geometry before visiting stages, avoiding a new
upload if another surface has replaced its geometry-cache entry.

Preparation uses transactions for the frame's uniform and geometry rings,
geometry lookup caches, and image descriptor cache. A failure discards all
prepared transparent records, restores the allocation cursors and descriptor
retirement state, and frees newly allocated descriptor sets. The ordinary
classic light and material walks then retain the entire transparent view.
Successfully created image and pipeline caches remain reusable. This fallback
requires the classic renderer's own resources to remain available; it does not
promise recovery from device loss or universal resource exhaustion.

Unsupported materials remain classic. Native material admission after commit
is restricted to the prepared surface list, so an image becoming available
later cannot change ownership halfway through the view. Zero-light and
`r_skipInteractions` views still prepare their coverage and environment.
The prepared list survives the intervening fog pass, and is disarmed when the
shared classic interaction consumer owns a view.

`r_vkPBRPrepareFailure` is a non-archived diagnostic: 1–4 reject coverage
pipeline/descriptor/uniform/geometry preparation; 5–8 reject the same direct
resources; 9–12 reject the environment resources; 13 rejects the environment
image. `r_vkPBRPrepareFailureAfter` counts successful matching checks before
failure in each view. Zero disables failure injection. `gfxInfo` additionally
reports readiness, records prepared before rollback, restored uniform bytes,
freed descriptors and matching fault-check visits.

`tools/tests/renderer_vulkan_pbr_resources.py` uses the same runtime/output/
basepath/sample arguments as the transparency suite. Its 44 controls cover
early and late failures for every diagnostic, exact classic fallback,
non-vacuous native recovery, cold descriptor rollback, image reload, partial/
full restart, no-light views and skipped direct interactions. Qualification
compares the complete engine screenshot, verifies ownership/rollback telemetry,
requires active Vulkan validation, and pins runtime and harness inputs.

Both `resources-v12-0/report.json` and `resources-v12-4/report.json` under
`.tmp/vulkan-gap-closure/pbr-resources/` pass all 44 controls. Every failure and
recovery comparison has zero whole-frame error. The ownership masks contain
63,824 fully covered pixels at 0x and 63,366 at 4x; recovered native lighting
changes over 190,000 foreground channels, including environment-only views.
The cold environment failure releases one new descriptor and 512 uniform
bytes. The late direct failure after image reload discards three prepared
records, releases two descriptors and restores 2,048 uniform bytes. Both
sample counts retain active validation and no tracked rendering diagnostics.
Engine-derived native/fallback PNGs were inspected.

The tested Vulkan module SHA-256 is
`b72c0eedb500f149a4dd8812cc37d6dadd2549949dec5b6c5c11513adec2195e`, identical
in `builddir`, `.install` and the independent `runtime-v12` package. The engine,
GL module and all other runtime inputs remain identical to v10. The preparation
manifest pins all 50 files. The earlier v11 trial passed its 25 partial-light
controls; v12 additionally reuses prepared geometry at the material-walk entry.

The final v12 regression also passes the existing 25 transparency, 18 capacity,
seven post-fog and 27 environment controls at both sample counts: 242 capture
controls in total with the new resource suite. All 154 existing complete TGA
files match their retained v10 transparency/capacity/fog or v7 environment
references exactly. The GPU render-target suite passes attachment/depth and
MRT drawing, MSAA resolves, scratch reload and the shared renderer contracts.
`checkpoint-v12.json` pins the reports, 50 runtime files, source worktree and
unchanged companion revision. These are local Windows/NVIDIA results; the
broader Vulkan gap-closure goal remains active.
