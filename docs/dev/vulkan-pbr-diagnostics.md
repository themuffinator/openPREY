# Native Vulkan PBR material diagnostics

Status: implementation under qualification. Vulkan remains experimental.

Material views 1–5 and ownership view 7 now draw once using the complete
ambient mesh. They do not require a direct light, environment lighting or an
authored ambient stage. Direct PBR interactions contribute no color in these
views, preventing a separate diagnostic contribution from each point light.
Emission view 6 retains the matching authored emission stage. A successfully
drawn material diagnostic suppresses that emission stage in the other views.

The diagnostic uses the environment pass's material bindings without creating
an environment atlas or admitting probes. Normal colors use the modern GL
cluster/view basis. Metallic, roughness and AO show the authored values after
their scalar/map factors; the roughness view does not show specular AA's
temporary lighting adjustment. Packed and separate maps share their normal
color/data upload contracts. Ordered transparent coverage writes the
diagnostic through the authored source alpha and does not replay direct light.

The ordinary ambient walker and the shared classic ambient admission check
both account for PBR diagnostics. The v24 negative candidate omitted the
former gate: emissive and transparent materials rendered, while ordinary and
cutout materials were still skipped with IBL off. Its 62 captures completed,
but the image comparator correctly rejects the absent channel values and
ownership mask. v25 corrects both walker gates. At 0x, all independent value,
light-independence and data-layout checks pass. Fifty-two of 62 strict
whole-frame pairs pass; the six mapped-normal views and four cutout views
still fail. Each cutout failure is the same single boundary pixel. The 4x
suite also passes all semantic checks, while 58 of 62 strict whole-frame
pairs differ. No whole-frame tolerance was relaxed. Separate coverage and
sampling controls below distinguish these differences from material errors.

All seven unlit views also pass the original curvature comparison on v25
(`parity-v25.json`). Ordinary lit scalar/metal/translated controls retain
their previous results; the four mapped-normal lighting comparisons remain
failed at the same silhouette pixels.

## Sampling and multisample coverage

The 12-control normal experiment uses constant X/Y/Z tangent normals and the
same variable normal map with default, bilinear and nearest filtering, each
in ordinary and rotated orientations. Both backends complete all captures
without diagnostics. The six constant-normal images and four non-mipmapped
images match within one byte over the complete frame. Only the two default
mipmapped cases exceed the two-byte limit: 9 pixels with a maximum of 12
bytes, and 53 rotated pixels with a maximum of 4 bytes. This isolates the
remaining material-normal differences to mipmapped sampling, rather than
the vertex frame or normal decoding. It does not establish bitwise agreement
for every filter, driver or lighting result.

On the recorded NVIDIA driver, GL reports the same numerical four-sample
positions as Vulkan's standard pattern, but in lower-left pixel coordinates.
Vulkan defines them relative to the upper-left corner
([Vulkan rasterization specification](https://docs.vulkan.org/spec/latest/chapters/primsrast.html)).
After image-origin conversion the patterns are reflections of each other.
The default and rotated green sphere masks differ at 254 and 278 pixels,
respectively, by exactly one coverage sample. Reflecting the GL pattern on
the horizontally symmetric fixture reproduces both native masks exactly.
An independent convex-silhouette rasterizer additionally reproduces every
pixel of both default-orientation captures using each API's sample locations
and the reported eight-bit subpixel precision. This closes the opaque sphere
coverage discrepancy on this driver; it is not an exception for cutouts,
mapped radiance, other scene geometry or other hardware.

## Reproduction and evidence

Use an independently prepared laboratory runtime and fresh output directories:

```text
python -B tools/tests/renderer_vulkan_pbr_diagnostics.py --runtime-root <laboratory> --basepath <retail-assets> --output-dir <captures> --backend <gl-or-vk> --samples <0-or-4>
python -B tools/tests/renderer_pbr_diagnostic_parity.py --gl-report <gl-captures>/report.json --vk-report <vk-captures>/report.json --output <comparison.json>
```

The suite captures 62 controls: ordinary and emissive materials with zero/one
lights, ownership with two lights, scalar/packed/separate data, three normal
encodings with rotation, cutouts and transparent materials. The comparator
requires active requested MSAA, fixed framing and matching provenance. It
checks independent channel values, exact light independence on fully covered
opaque pixels, equivalent data layouts and a strict two-byte whole-frame
comparison. Capture completion alone is insufficient.

The current evidence is under
`.tmp/vulkan-gap-closure/pbr-direct-curvature/`. The first GL attempt,
`diagnostics-gl-v23-0`, failed before launch because a new test CVar lacked a
base value; the corrected capture is `diagnostics-gl-v23-0b`.
`diagnostics-parity-v24-negative-0.json` retains the failed first implementation.
The v25 binary and source hashes are pinned in `runtime-v25-provenance.json`.
`diagnostics-parity-v25-0.json` retains both the passing semantic result and
the failed whole-frame result. The exact remaining pixels are listed in
`diagnostic-sampling-differences-v25-0.json`.

`diagnostics-parity-v25-4.json` retains the 4x semantic pass and strict
whole-frame failures. `sampling-comparison-v25-0d.json` binds the 12-filter
experiment to its captures and independently compiled, precached fixture.
Earlier sampling attempts failed fixture preparation/precache checks and
remain excluded. `sample-positions-proof-v25-4.json` binds the queried GL
sample positions, Vulkan device properties, reflected masks and independent
CPU coverage oracle. The first CPU attempt used the requested eye height;
the corrected oracle uses the logged rendered eye height, 380.5 instead of
380, and the reported subpixel precision. The temporary GL query was restored
byte for byte, rebuilt and staged; the instrumented DLL remains isolated.

Mapped-normal sampling differences remain under investigation in the
[receiver geometry ledger](vulkan-pbr-geometry.md). The 20-control HDR
fog/blend experiment completed on both APIs in v25. All 16 shared-setting
toggle comparisons are exact within their backend, but every cross-API
pair failed. Even the clear scalar albedo was 128 in Vulkan and 207 in GL.
Independent material-value and tone-curve calculations reproduce all four
clear controls within one byte: v25 Vulkan applied the stock numeric
shoulder, while GL uses the admitted linear PBR filmic/output-transfer path.
This retained negative control isolates the HDR/PBR presentation defect, not normal
decoding or fog ordering. Diagnostic colors are composited by fog/blend on
both backends. See `diagnostic-composition-hdr-parity-v25-0.json`; the initial
HDR-off GL run cannot qualify this path because modern ownership declined
its fog/blend scenes. The v28 native scene boundary now corrects the clear
scalar control to 207, and all 40 native fog/blend/alpha controls pass at
0x/4x. All twenty 0x GL/native full-frame comparisons also pass, with a maximum
difference of one byte per channel (`hdr-scene/composition-parity-v28b-0.json`).
The whole-view admission limits and current qualification are recorded
in [Vulkan HDR](vulkan-hdr.md).

These toggles do not establish shared-consumer ownership. The native scene
target sets `sceneScaleState.active` even at 100% scale, and that suppresses
shared fog/blend preflight. Explicit consumer admission/completion telemetry
is needed before treating a matching setting as coverage of a second path.

Baked grids, ambient lights, shared ambient mode and complete diagnostic
resource/restart behavior still need explicit integration checks. The
ordinary lighting checks for those consumers do not establish diagnostic
parity, and matching consumer switches do not close HDR color parity.

The v25 candidate repeats all 44 transparent resource/fallback/restart controls
successfully at both sample counts (`resources-v25-0` and `resources-v25-4`).
Those include the ownership view, exact rollback and image/video restoration;
they do not exercise every diagnostic mode under resource failure. The
combined `checkpoint-v25-diagnostics.json` verifies retained report/image/log
hashes, frozen runtimes, restored production GL source, staged/build module
agreement and the unchanged ordinary-lighting images.
