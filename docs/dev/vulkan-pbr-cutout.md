# Native Vulkan PBR cutout coverage

Status: the native depth fill uses the admitted material's typed PBR albedo.
Native cutout alpha also uses the constant stage value directly, avoiding
precision loss from interpolating that constant across a triangle.
The subsequent [framebuffer-orientation change](vulkan-image-origin.md) also
reduces coverage differences. Full OpenGL cutout parity remains open, including
some anisotropically filtered multisample edges.
Vulkan remains experimental. The subsequent filtering investigation below also
records small between-process variation in the OpenGL smoothed reference.

## Texture identity

A classic diffuse image and a PBR albedo can share a source name and sampler
settings while having different generated mip levels. The classic RGBA8 path
truncates the alpha average; the typed sRGB PBR path rounds its linear alpha
channel to the nearest byte. For the laboratory's equal-area checker, the final
three mips contain alpha 127 in the classic image and 128 in the PBR image.
These values fall on opposite sides of a 0.5 cutout threshold.

The previous native depth fill sampled the classic image even when PBR owned
coverage. Strong minification could therefore remove samples that the PBR
material should retain. The fill now binds `GetPBRInfo().albedo.image` after the
existing native material/coverage admission succeeds. The classic path retains
its own image. Admission still requires one compatible alpha-tested diffuse
stage, matching source/sampler/UV semantics, supported material resources and
the existing state restrictions. No image format or shared mip-generation rule
changes, and no replacement game assets are required.

## Regression controls

`tools/tests/renderer_vulkan_pbr_cutout.py` generates a 256x tiled version of the
existing original laboratory sphere in an isolated save directory. Its minified
PBR alpha is uniformly above the cutoff. With hard alpha testing, its complete
linear coverage must equal an opaque instance of the same geometry exactly.
This is an independent same-backend oracle; it does not discard silhouette
pixels or relax a GL/Vulkan comparison.

Eight cases cover the ordinary cutout, minified cutout, opaque reference,
material restoration, image reload, partial/full video restart and restoration
of the ordinary cutout. The latter must retain both holes and visible material.
Restored display and linear captures must be byte-identical. Both 0x and 4x
profiles record effective samples, native HDR ownership, runtime hashes,
generated-model identity and harness sources. Engine captures use hidden,
windowed gameplay with input disabled.

Run the GL reference first, then pass its report to the Vulkan run:

```powershell
python -B tools/tests/renderer_vulkan_pbr_cutout.py --runtime-root .tmp/runtime/candidate --output-dir .tmp/cutout-gl --basepath "E:/SteamLibrary/steamapps/common/Quake 4" --backend gl --samples 4
python -B tools/tests/renderer_vulkan_pbr_cutout.py --runtime-root .tmp/runtime/candidate --output-dir .tmp/cutout-vk --basepath "E:/SteamLibrary/steamapps/common/Quake 4" --backend vk --samples 4 --compare-gl-report .tmp/cutout-gl/report.json
```

The runtime must contain a prepared PBR laboratory and its matching engine/game
modules, including `baseoq4/mod.json`. The full-frame comparison remains a
separate result with limits of two display values and 0.003 linear radiance per
channel. A passed minification/recovery oracle cannot waive that comparison.

The final v43 regression passes all 32 independent controls across GL/Vulkan at
0x/4x. All twelve minified/opaque/recovery GL/Vulkan case pairs match exactly in
both display and linear captures. The retained pre-fix Vulkan module loses all
7,278 visible specimen pixels in the 0x minified case and fails the same oracle
after every recovery operation. The ordinary cutout and its restoration still
fail the strict paired comparison: one pixel at 0x (linear maximum 1.0), two at
4x (maximum 0.5). Those four failed case pairs remain reported; this regression
closes only the depth-image identity defect.

The subsequent v44 framebuffer fix makes all sixteen 0x/4x case pairs exact,
including the ordinary cutout and restoration. The original isolated smoothed
and hard 1x-anisotropic masks also match exactly. At 16x anisotropy the smoothed
mask retains four differing pixels. The [orientation qualification](vulkan-image-origin.md)
records those strict failures and the remaining baked-lighting differences.

The final staged runtime also passes both Vulkan target/HDR GPU contracts and
stock single-player/multiplayer gameplay runs, including image reload and
partial restart, with sixteen engine captures and no tracked rendering warnings.
Representative captures were inspected. `checkpoint-v43-cutout-coverage.json`
binds these reports to the source and runtime; broader qualification remains open.

## Retained v43 multisample investigation

The original isolated cutout still differs at 4x with filtered coverage. On the
retained local NVIDIA run, switching the depth image reduced the hard-cutout
comparison from 19 differing pixels to four. The 16x-anisotropic smoothed mask
still differs at 444 pixels, with maximum linear coverage error 0.5. Reducing
anisotropy to 1x does not remove the discrepancy. The baked-only and reflection
images retain corresponding errors; they are failed parity evidence.

A retained diagnostic module using a positive-height Vulkan viewport reduces
the smoothed-mask discrepancy to four pixels, maximum 0.25, after deliberately
reflecting its engine capture. Its 1x hard-cutout comparison still differs at
16 pixels and predates the typed-albedo fix. This strongly implicates framebuffer
orientation in the large coverage mismatch; it does not establish a production
fix, identical shader interpolation, or a portable hardware coverage rule.
That reflected diagnostic was absent from the v43 source and staging. The v44
[image-orientation implementation](vulkan-image-origin.md) carries the convention
through geometry, captures and presentation, so exported images need no manual
reflection. Its qualification and remaining differences are recorded separately.

Evidence is retained in `.tmp/vulkan-gap-closure/pbr-cutout-coverage/`. The first
orientation run failed before rendering because the diagnostic package omitted
its runtime manifest. Its debugger transcript and failed report are retained;
the corrected run supplies the orientation evidence above. These are local
Windows/NVIDIA correctness investigations, not performance or wider platform
qualification. Baked-lighting scope remains documented in
[native baked HDR](vulkan-pbr-baked.md).

## v45 filtering investigation

The isolated 4x specimen now has matched hard/smoothed controls at 1x, 2x, 4x,
8x and 16x anisotropy, followed by a restored 16x case. Both APIs use the same
compiled map, typed albedo, scene profile, bake and capture harness. The initial
Vulkan run reproduces all four common v44 captures byte for byte, but a fresh
OpenGL run changes two smoothed 16x pixels and four smoothed 1x pixels relative
to the retained reference. An identical second OpenGL run changes two or three
smoothed pixels relative to the first, while every hard-cutoff image repeats
exactly. Each changed smoothed pixel differs by one of the four MSAA samples.
Within each run, the restored 16x image matches its initial capture.

Against the first fresh OpenGL run, the hard-cutoff discrepancy is:

| Anisotropy | Differing pixels | Maximum linear coverage difference |
|---|---:|---:|
| 1x | 0 | 0 |
| 2x | 6 | 0.25 |
| 4x | 5 | 0.25 |
| 8x | 7 | 0.25 |
| 16x | 1 | 0.25 |

The 16x hard mismatch is at exported image coordinate (697, 631), where GL has
one covered sample and Vulkan has none. The mismatch therefore also exists
without alpha-to-coverage smoothing. This narrows the next investigation to
sampled alpha, interpolation and the texture footprint; it does not yet prove
which component causes the difference.

Diagnostic shader variants test explicit fine and coarse texture gradients.
Coarse gradients reproduce all eleven original Vulkan images exactly. Fine
gradients introduce four differing pixels into the previously exact 1x hard
case and do not close the anisotropic comparisons. Applying explicit coarse
gradients to the GL 4.5 depth and alpha shaders also reproduces all eleven
images from the first fresh OpenGL run. All three variants are rejected as
fixes; none supplies new full-frame parity evidence. The four edited production
files are restored byte for byte, and both renderer modules are rebuilt from
those restored sources. All eleven clean cases on each API reproduce their
respective initial v45 images exactly in display and linear captures. The staged
Vulkan target, HDR and 36-case motion contracts pass without tracked renderer
warnings, and the embedded shader/header pins pass.

The v44 results remain comparisons against their named archived references;
they do not establish that every new OpenGL process produces identical smoothed
coverage. No comparison limit, silhouette exclusion or image orientation is
changed. Evidence and diagnostic binaries live under
`.tmp/vulkan-gap-closure/anisotropic-coverage/`, with provenance recorded in
`checkpoint-v45-filtering.json`. These tests do not close the separate baked
lighting, HUD filtering or broader material/hardware qualification requirements.

## v46 constant-alpha correction and fragment evidence

Native PBR cutouts passed constant stage alpha through a perspective-interpolated
vertex output before multiplying it by texture alpha. Actual fragment records
show that an authored 1.0 arrives as 0.9999999403953552 in 91 of 172 measured
Vulkan fragments. At 1x anisotropy, raw sampled alpha and its derivatives match
OpenGL exactly, but this multiplication changes 80 alpha values and 142 gradient
records. It can reject fully opaque texels at an inclusive cutoff of 1.0 and
introduce false gradients into filtered coverage.

The native hard and filtered coverage modes in `gui.frag` now multiply texture
alpha by the push-constant stage alpha directly, matching the modern GL path.
Classic material alpha rules remain separate. The ordinary and HDR-domain
embedded shader headers are regenerated from the same source. All temporary
C++ probes are removed before rebuilding the production renderers.

### Independent cutoff regression

`tools/tests/renderer_vulkan_pbr_cutout_alpha.py` uses the laboratory's fully
opaque grey albedo and an inclusive cutoff of 1.0. Its cutout must have exactly
the same complete display and linear coverage as an opaque instance of the
same geometry. A uniquely named material is generated in the isolated save
directory and touched from the supported startup configuration, before level
loading. The report verifies the printed material, effective sample count,
native HDR ownership, nonempty geometry, capture hashes and runtime identity.
This avoids relying on cross-API texture filtering or alpha-to-coverage.

Six controls cover the opaque reference, cutoff, image reload, partial/full
video restart and opaque restoration. Run either backend at 0x or 4x:

```powershell
python -B tools/tests/renderer_vulkan_pbr_cutout_alpha.py --runtime-root .tmp/runtime/candidate --output-dir .tmp/cutout-alpha-vk --basepath "E:/SteamLibrary/steamapps/common/Quake 4" --backend vk --samples 4
```

With the same verified material and profile, the retained pre-fix Vulkan module
loses coverage in 4,436 of 7,848 visible specimen pixels at 4x, including after
each recovery operation. The final shader matches the opaque reference exactly
in all six controls, without engine diagnostics. No replacement game asset is
shipped. Earlier fixture attempts that loaded the original checker or produced
a late-precache warning are retained as rejected qualification evidence.

The final runtime passes all 24 new cutoff controls across GL/Vulkan at 0x/4x,
plus all 32 existing minification and recovery controls. All sixteen existing
full-frame GL/Vulkan minification-suite pairs match exactly, including the
ordinary cutout in that camera. These are distinct from the isolated 16x
filtering specimen below.

### Remaining filtering difference

Temporary storage-buffer probes record the actual indexed cutout draw, including
texture coordinates, fine/coarse gradients, sampled alpha, threshold and computed
coverage. All 172 corresponding GL/Vulkan records have bit-identical texture
coordinates and texture gradients; GL depth and forward alpha also match. After
the correction, all measured 1x alpha, alpha derivatives and computed coverage
match GL. The correction is too small to change the ordinary 0.5-cutoff images
in this fixture; the independent 1.0-cutoff test above supplies the visible oracle.

The hard 16x mismatch at exported coordinate (697, 631) has raw alpha
0.5253833532 in GL and 0.4912184477 in Vulkan, on opposite sides of 0.5.
Earlier repeated unmodified-shader records report LOD pairs (2, 2) and
(2.484375, 2.484375), respectively. The actual bound sampler settings correspond,
both images are 64x64 with seven mips, and the generated typed albedo bytes match.
This establishes a sampling difference despite matching measured coordinates
and gradients; changing interpolation or selecting another GL reference does
not resolve it. The corrected probe's smoothed cases return -32 for the second
`textureQueryLod` component, so that metadata is explicitly excluded from the
LOD conclusion. Independently exact alpha/derivative/coverage records remain
separate evidence.

The clean production pair reproduces the initial v46 images exactly. Its 1x hard
and smoothed masks match GL; 16x retains one hard and four smoothed differing
pixels, each differing by one of four samples. These still fail the unchanged
full-image limits of two display values and 0.003 linear radiance. Other GL
processes retain the small smoothed-mask variation documented in v45.

Evidence lives under `.tmp/vulkan-gap-closure/alpha-fragment-probe/`. The bounded
alpha correction does not close anisotropic sampling, baked-lighting or HUD
differences, broader material support, or hardware/platform/performance/soak
qualification. Vulkan remains experimental.

The final staged renderer reproduces all five clean isolated masks exactly and
passes the target, HDR and 36-case motion GPU contracts without tracked renderer
warnings. Embedded shader/header pins pass, and the engine-generated before/after
cutoff captures were visually inspected. `checkpoint-v46-constant-alpha.json`
binds the source, runtime, accepted tests and rejected experiments. This is local
Windows/NVIDIA evidence; stock SP/MP qualification remains the earlier v44 run.

## v47 sampler limits and coverage dithering

A temporary Vulkan sampler variant sets the lower mip-LOD bound to -1000 for
mipmapped images, matching the queried GL setting; nonmipmapped samplers retain
their existing bounds. All five isolated masks are byte-identical to production
in both display and linear captures. This rejects the lower sampler LOD clamp
as a fix for the observed mismatch. The [sampler specification](https://docs.vulkan.org/refpages/latest/refpages/source/VkSamplerCreateInfo.html)
describes these bounds separately from the anisotropic filtering control.

The measured texture-gradient matrix at (697, 631) has principal footprint
lengths of approximately 76.48 and 0.564 texels, a ratio of about 136:1 against
the requested 16x limit. These derived values provide inputs for a controlled
sampling investigation; they do not prove which approximation either driver
uses. The [GL anisotropic-filtering extension](https://registry.khronos.org/OpenGL/extensions/EXT/EXT_texture_filter_anisotropic.txt)
permits implementation-dependent filtering schemes. That latitude does not
close the project's failed image comparison.

The local GL driver advertises
[NV alpha-to-coverage dither control](https://registry.khronos.org/OpenGL/extensions/NV/NV_alpha_to_coverage_dither_control.txt).
Two independent processes per mode exercise the same five masks, including
hard-cutoff controls and restoration. All thirty corrected diagnostic captures
are validation-clean. Their smoothed-mask results are:

| GL dither mode | Between-run differing pixels, 16x / 1x | Differences from the fixed Vulkan reference, 16x / 1x |
|---|---:|---|
| Default | 2 / 4 | 4 then 6 / 0 then 4 |
| Explicitly enabled | 0 / 1 | 6 in both runs / 3 then 4 |
| Disabled | 0 / 0 | 215 / 214 in both runs |

Every hard GL mask reproduces the named production reference, and each restored
smoothed mask matches its initial image within the same process. The 16x hard
GL/Vulkan discrepancy remains one pixel for every mode. Disabling dithering
removes the measured between-run variation but changes more than two hundred
coverage pixels and worsens parity; it is not adopted. Explicit enabling does
not remove all variation. The sampling discrepancy and coverage-conversion
variation therefore remain separate requirements.

The first dither probe is rejected: it passed a returned raw value of 1 back to
the setter as an enum, causing GL errors. This driver reports raw 1/0 values
for the query. The corrected probe checks advertised support, uses only the
documented setter enums and restores DEFAULT in its isolated context. Its raw
query observations are recorded without treating them as documented mode tokens.

All temporary source changes are restored byte for byte to v46 before the clean
rebuild. No sampler limit, dither mode, comparison limit or production behavior
is changed by this investigation. Evidence is retained under
`.tmp/vulkan-gap-closure/sampler-footprint/`.

The restored build passes all ten GL/Vulkan mask capture controls and all three
target/HDR/36-case-motion GPU contracts with no tracked renderer warnings. Every
GL and Vulkan image reproduces the named v46 production references exactly.
`checkpoint-v47-sampler-dither.json` binds the unchanged production sources,
rebuilt runtime, rejected probe and comparisons. The existing v46 cutoff fix
remains staged; full filtered-cutout parity and wider Vulkan qualification stay
open.

## v48 fixed-input GPU sampling

A temporary compute probe uses the actual typed cutout texture and sampler,
with the exact IEEE float inputs from the 172 paired fragment records. Its
`textureGrad` calls supply the recorded coarse gradients explicitly; no triangle,
interpolation, depth test or alpha-to-coverage operation participates. A second
output reads all 5,461 resident RGBA texels across seven mip levels with
`texelFetch`. These operations follow the
[GLSL texture-function contracts](https://docs.vulkan.org/glsl/latest/chapters/builtinfunctions.html#texture-functions).
Vulkan readback uses a compute-to-host dependency, fence completion and mapped
memory invalidation as described by the
[Vulkan synchronization guide](https://docs.vulkan.org/guide/latest/synchronization_examples.html#cpu-read-back-of-data-written-by-a-compute-shader).

Two independent processes per API exercise the five existing anisotropy,
hard/smoothed-coverage and restoration controls. All twenty complete readbacks
repeat exactly, every resident mip texel matches between APIs and controls,
and each of the 172 sampled alphas reproduces its API's earlier actual-fragment
record exactly. The cross-API results are:

| Sampling operation | Different alpha values at 16x / 1x, out of 172 |
|---|---:|
| Explicit recorded gradients | 12 / 0 |
| Explicit LOD 2.0 | 0 / 0 |
| Explicit LOD 2.484375 | 166 / 0 |
| Explicit LOD approximately 2.257077 | 171 / 0 |

The hard failing sample still returns 0.5253833532 in GL and 0.4912184477 in
Vulkan. The maximum gradient-sampled alpha difference is approximately 0.1035172.
This directly isolates the observed difference to anisotropic sampling with
identical resident image data. Fractional explicit-LOD results also depend on
the enabled anisotropic sampler; a shared filter cannot assume `textureLod`
alone removes this difference. The 1x controls are a diagnostic comparison,
not a proposal to lower the user's filtering quality.

All twenty engine capture controls pass. The first probe pair reproduces its
named production images exactly; hard GL and every Vulkan image also repeat
in the second pair. Independent GL coverage variation remains a separate issue.
The temporary GL readback emits driver performance diagnostics from synchronous
buffer transfers; no API errors are accepted and no performance conclusion is
drawn from the probe.

Evidence is retained under `.tmp/vulkan-gap-closure/sampler-compute/`, including
the exact inputs, resident texture outputs, archived probe sources and modules,
and `compute-reproduction.json`. The production sources are restored byte for
byte before rebuilding. No filtering algorithm, anisotropy setting, coverage
mode or comparison threshold is changed. This local Windows/NVIDIA diagnosis
does not close filtered-cutout parity or broader Vulkan release qualification.

The restored runtime passes ten clean capture controls and all three target,
HDR and 36-case motion GPU contracts without tracked renderer warnings. Every
Vulkan image and both hard GL controls reproduce production exactly. Clean GL
smoothed masks differ from the named reference by two/four pixels at 16x/1x,
matching the separate process variation above; they are retained as failed
strict comparisons, not waived. Vulkan still differs from the fixed GL reference
by four smoothed and one hard 16x pixel. The source/runtime and all accepted
evidence are bound by `checkpoint-v48-fixed-sampling.json`. The earlier PBR
cutoff fix remains staged, and stock SP/MP evidence remains the v44 run.

## v49 shared-filter prototypes

Two task-only compute prototypes explore explicit anisotropic filtering through
a separate nonanisotropic trilinear sampler. Neither is used by production draws.
The dataset expands the 172 recorded fragments with 864 rotated/skewed footprints
and six degenerate cases. All 1,042 inputs remain finite. Twenty GPU readbacks
retain exact resident mip data, reproduce the earlier native sampled values,
and pass same-process restoration controls.

An independent CPU reference integrates the bilinearly reconstructed mip-zero
alpha signal over the complete pixel parallelogram. Dense quadrature is refined
from 128/256 samples per axis up to 2,048 where needed; the final maximum change
between the last two resolutions is approximately 0.0002045. This is a specified
quality reference for one periodic cutout texture, not a claim that either API
requires this exact reconstruction kernel or that all content has been covered.

The first prototype chooses a tap count with `ceil` of the footprint aspect
ratio. It matches between APIs on the original 172 fragments, but the enlarged
dataset exposes a numerical discontinuity: a one-ULP change near an integer
ratio selects a different sampling kernel. The largest shared-filter alpha
difference reaches 0.125002. Accurate footprint lengths alone do not make this
discrete decision stable.

The second prototype blends adjacent tap-count kernels continuously and bounds
the minor length against numerical reversal at isotropy. This reduces the
largest cross-API shared-16x alpha difference to approximately 0.00121978, but
19 inputs still differ, including four of the original 172. The two prototypes'
shared-16x results are:

| Measure | Discrete tap count | Continuous kernel blend |
|---|---:|---:|
| Cross-API differing alpha values, out of 1,042 | 26 | 19 |
| Maximum cross-API alpha difference | 0.125002 | 0.00121978 |
| Mean absolute error against area reference, GL / Vulkan | 0.014788 / 0.014714 | 0.014845 / 0.014844 |
| Inputs worse than native by more than 0.01, GL / Vulkan | 87 / 71 | 91 / 74 |
| Maximum explicit texture fetches at the 16x setting | 16 | 31 |

Native mean absolute error on the same dataset is approximately 0.016158 in GL
and 0.017246 in Vulkan. Better aggregate error does not erase the per-input
regressions. Observed mean fetch counts for the continuous prototype are about
7.8/8.0; these are shader-work counts, not GPU timings or a gameplay performance
qualification. Its residual differences, quality tradeoffs, temporal behavior,
broader texture coverage and runtime cost all need further work before adoption.
No filtered draw or alpha-to-coverage behavior is changed by these compute tests.

Evidence lives in `.tmp/vulkan-gap-closure/shared-filter/`, including both
archived prototypes, the exact inputs, the independent reference, and
`shared-filter-assessment.json`. The first observer-summary draft compared the
Vulkan report against the GL reference under the GL label; the corrected
analysis selects each API's report and preserves the superseded draft. This
affected the summary only, not the GPU readbacks or numerical quality results.
Corrected image checks retain exact hard GL and all Vulkan production images;
the GL smoothed masks show the previously known process variation.

Both C++ integration points are restored byte for byte before the clean rebuild.
The v46 constant-stage-alpha fix remains the production implementation. The
strict image limits and requested anisotropy are unchanged; filtering, coverage
and the larger Vulkan qualification goal remain open.

The clean v49 runtime passes ten capture controls and all three target/HDR/
36-case-motion GPU contracts without tracked renderer warnings. All ten images
reproduce the named GL/Vulkan production references exactly. This restores the
prior implementation, including its unresolved cross-API 16x cutout comparison;
it does not qualify the new sampling algorithms for rendered use.
`checkpoint-v49-shared-filter.json` binds the sources, prototypes, analysis
corrections and clean runtime. Stock SP/MP evidence remains the earlier v44 run.
