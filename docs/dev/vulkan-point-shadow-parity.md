# Vulkan point-shadow comparison investigation

Status: partially corrected locally. The v56 candidate passes the default
nine-tap point-map comparison over the complete image, with a maximum difference
of two display levels. The v53 baseline failed at nineteen pixels, maximum five.
Three point-stencil boundary pixels still fail, maximum 30, and single-lookup
and disabled-bias map controls retain small failures. The custom receiver itself
matches OpenGL exactly under shadows. Broader shadow and platform qualification
remain open; this investigation does not promote Vulkan.

## Reproduction and isolation

The v54 diagnostic profile keeps the v53 runtime, retail assets, compiled map,
camera, lighting, material and geometry inputs. Engine screenshots from both
backends reproduce the original unshadowed, stencil and mapped images exactly.
All launches are hidden, windowed and input-disabled. Seventeen GPU-projection
controls and six CPU-projection controls are captured on each backend; runtime,
source, command, log and screenshot hashes are retained under
`.tmp/vulkan-gap-closure/point-shadow-parity/`.

| Diagnostic setting | Pixels exceeding two levels | Maximum difference |
|---|---:|---:|
| Default stencil shadows | 3 | 30 |
| Disable depth bounds | 3 | 30 |
| Use two separate stencil passes on OpenGL | 3 | 30 |
| Force internal-volume cap handling | 3 | 30 |
| Disable stencil depth bias | 1 | 23 |
| Increase stencil depth bias to four units | 2 | 33 |
| Hide the test caster | 0 | 1 |
| Default hardware comparison with nine taps | 19 | 5 |
| Hardware comparison with a single lookup | 4 | 4 |
| Manual comparison with a single lookup | 0 | 1 |

CPU-generated shadow volumes reproduce the same stencil comparison results.
The three default stencil failures are isolated boundary pixels on the test
caster's shadow. The controls rule out the depth-bounds optimization, the
one-pass stencil formulation and the choice of CPU/GPU extrusion in this scene.
Changing bias moves the affected boundary pixels; increasing bias is not adopted
as a correction. Depth transformation, interpolation and rasterization remain
to be distinguished with stronger evidence.

The manual nine-tap comparison differs more widely: 6,415 pixels, maximum eleven
levels. It is not a like-for-like storage comparison. OpenGL's disabled hardware
comparison path uses its packed color-depth fallback with
`r_shadowMapPointHighPrecision 0`; Vulkan continues to store native depth. The
saved configurations establish that setting. This diagnostic does not justify
reducing Vulkan precision or replacing the production hardware comparison path.
The production nineteen-pixel failure remains independently open.

The probe called `mapped_factor` actually selects debug mode 1, which displays
cube lookup direction in RGB. It does not display the shadow factor. Mode 4
displays normalized receiver depth. Their small display differences do not
prove equality of the underlying floating-point values.

## Rejected radial-order prototype

Vulkan's point caster originally evaluates radial length in cube-face view
coordinates. OpenGL evaluates it in world-relative coordinates. These are
mathematically equivalent signed permutations, but the component order can
change floating-point summation. A prototype restored world-axis order in the
vertex shader, using the unused fourth depth-row component for the face index
on both legacy and shared caster submission paths. It added no texture samples
and retained the original filters and biases.

The prototype changed twelve default mapped pixels and reduced out-of-limit
pixels from nineteen to seventeen; the maximum remained five. With receiver
bias disabled, out-of-limit pixels decreased from 33 to 27. Stencil output was
unchanged. This does not close the requirement, and the prototype was reverted.
Its exact source, renderer binary, captures and analysis remain in
`archive-radial-order`, `vk-radial-order-v54c` and
`analysis-radial-order-v54c.json` under the investigation directory.

After reversion, the renderer was rebuilt and staged from the original source.
All seventeen resulting Vulkan images match the pre-prototype images pixel for
pixel. The render-target/startup, HDR and temporal-motion GPU groups pass without
tracked warnings. The final binary, source and report identities are bound by
`.tmp/vulkan-gap-closure/point-shadow-parity/checkpoint-v54-point-shadow-parity.json`.

## Exact receiver measurements

The v55 probes encode each float32 component as four separate RGB byte captures.
A white control independently identifies 981,153 ordinary mapped receiver pixels
on each backend. An x-dependent color pattern exercises every byte value in
every channel, with zero errors on that entire mask. Repeated white and pattern
captures are exact. A normal-rendering branch in each instrumented shader also
reproduces its uninstrumented v54 image exactly, before and after the byte captures.
These controls qualify the encoding without selecting pixels by whether their
encoded values happen to agree.

The probe keeps production hardware comparison, nine taps, radius and bias.
Diagnostic selectors bypass the shaders' debug-mode changes to filtering and
receiver bias. Modes 10 and 12 are excluded because the CPU changes caster offset
or depth-comparison storage for those modes. The GL source override must live in
the isolated candidate runtime: its packaged sources precede the save directory.
The first attempt using only a save-directory override failed the independent
marker check and is explicitly excluded from the measurements.

The measured maximum component differences across the receiver mask are:

| Value | Maximum absolute difference |
|---|---:|
| Receiver vector, x or z | 0.00018310546875 world units |
| Receiver vector, y | 0.00006103515625 world units |
| Normalized radial reference | 0.00000011920928955078125 |
| Receiver bias | 0.00000000011641532182693481 |
| Filtered shadow factor | 0.1484375 |

A second disposable shader replays OpenGL's measured vector, radial reference
and bias at exactly the nineteen failing pixel coordinates. Byte readback proves
that all three replayed inputs equal the GL values exactly. Seventeen resulting
shadow factors and displayed pixels now match GL exactly. The whole image outside
those nineteen coordinates is unchanged from the original Vulkan image. This
establishes receiver-input sensitivity; it does not identify which individual
input or interpolation operation needs correction.

The remaining pixels are (1175,125) and (1189,313), using the engine image's top
origin. Their factors still differ by approximately 0.1263 and 0.1367, with at
most four display levels of error. These are the same two outliers removed by
the v54 caster component-order prototype. The two experiments isolate
complementary arithmetic effects. Stored native depth and individual lookup
directions have not yet been measured on both backends, so the precise remaining
lookup/storage mechanism is still open.

The coordinate-specific replay is a counterfactual experiment, not a renderer
fix or a passing production result. Both diagnostic shaders are removed from
production source and runtime. Evidence is retained under
`.tmp/vulkan-gap-closure/point-shadow-values/`: `analysis-v55b.json` contains
qualified values, `analysis-v55c.json` contains the replay, and their `.npz`
companions retain the decoded float arrays. The next work is to isolate the
receiver arithmetic and establish a general correction, then reassess the
caster arithmetic together with it. Production quality settings and the
full-frame threshold remain unchanged.

After removing the v55 instrumentation, all seventeen Vulkan controls are
pixel-identical to the v54 production controls. The startup/render-target, HDR
and temporal-motion GPU groups pass with zero tracked warnings. The restored
build still has the original three stencil and nineteen mapped outliers.
The evidence and complete runtime/source identities are sealed in
`.tmp/vulkan-gap-closure/point-shadow-values/checkpoint-v55-point-shadow-values.json`.

## General radial-depth correction

The v56 isolation replay substitutes one receiver input at a time at the same
nineteen diagnostic coordinates. Substituting only the measured GL radial
reference removes seventeen failures. Substituting only lookup direction or
receiver bias changes none of them. A refactored sampling control reproduces
the original factor at every independently marked receiver pixel, so splitting
the inputs did not itself change the comparison.

A disposable positive-height swapchain viewport then isolates interpolation
orientation. After exactly one documented vertical row reversal for this
experiment, all three receiver-vector components equal GL across all 981,153
marked pixels. Radial references still differ. Further byte captures establish
that GL's squared length matches x-y-z fused accumulation, while Vulkan's
matches y-x-z fused accumulation, at every marked pixel on this GPU/driver.
Both use the same far distance and reciprocal; equal squared lengths produce
equal square roots. Their final references equal length times reciprocal far.
These are measured implementation results, not a guarantee about other drivers.

The retained general candidate uses world-axis caster vectors and explicit
x-y-z fused radial accumulation for casters, receivers and receiver normal
offsets. Eligible native-resolution main scenes use the existing lower-origin
offscreen attachment and ordinary spatial presenter, as scaled/HDR scenes
already do. The presenter produces upright engine captures. Swapchain viewport
behavior, admission checks and resource-failure fallbacks remain intact.
No coordinate-specific substitution, diagnostic float encoding, post-capture
reflection, filter reduction, bias change or tolerance increase is present in
the candidate. Both ordinary and HDR point-interaction shader headers are
regenerated and pass the complete shader/header pin check.

The seventeen production/diagnostic controls retain these full-frame results:

| v56 setting | Pixels exceeding two levels | Maximum difference |
|---|---:|---:|
| Default stencil shadows | 3 | 30 |
| Default hardware comparison with nine taps | 0 | 2 |
| Hardware comparison with a single lookup | 2 | 4 |
| Manual comparison with a single lookup | 0 | 1 |
| Hardware comparison with receiver bias disabled | 1 | 3 |

The manual nine-tap case still uses unlike depth-storage paths and is not a
native-depth equivalence result. Its 6,397 out-of-limit pixels remain recorded.
The unchanged authored-lighting suite passes all 26 independent controls,
including exact reload/restart and mapped-request receiver fallback recovery.
Twenty-five full-frame GL/Vulkan comparisons now pass; only the point-stencil
case fails. All twenty ordinary authored-material comparisons also pass within
one display level. PBR minification, inclusive-alpha and HDR resize/restart
controls pass on the candidate. The staged startup/render-target, HDR and motion
GPU groups pass with zero tracked warnings. Four stock SP/MP runs at 0x/4x MSAA
also pass, retaining 32 engine screenshots through HDR/temporal toggles, scaling,
resize and restart. Inspected SP and MP captures retain upright worlds and HUDs.

Eight native PBR point controls additionally pass with preview and HDR output:
off/on visibly changes the shadow, the material owns its specimen, and restoration
is exact over the complete display image (and complete linear image for HDR).
The HDR ownership oracle requires every pixel in the authored 65x65 specimen
interior to equal linear `(0,1,0)`, before tone mapping. This is an ownership
control, not a cropped cross-API parity claim. Preview output correctly rejects
linear export. Initial wrappers wrongly required that export from preview and
then reused an encoded-green ownership oracle for HDR; those two failed reports
remain excluded from qualification. Corrected evidence is in
`pbr-point-preview-v56i` and `pbr-point-hdr-v56j`.

Five stock `storage1` timing runs per version use matching settings and packages
that differ only in the Vulkan module and its debug symbols. All ten fail the
unchanged CPU budget. Before the change, CPU p99 ranges from 389.8 to 409.4 ms;
afterward it ranges from 388.5 to 403.3 ms. GPU p99 stays below 10 ms in both sets.
The live simulation is not frozen and every capture differs, so these runs do
not isolate the presentation pass's cost. They establish a retained timing
failure on both versions, with no performance improvement or release claim.
The cause of those CPU stalls, repeatable cost measurement, longer gameplay
and other GPU/platform qualification remain open.

Evidence is retained under `.tmp/vulkan-gap-closure/point-shadow-arithmetic/`:
`analysis-v56a.json` through `analysis-v56c.json` bind the input and arithmetic
experiments; `analysis-general-v56d.json` and `comparison-lighting-v56e.json`
bind the general correction and the remaining failed full-frame gate.
`analysis-performance-v56f.json` retains every timing failure. The first timing
attempt was rejected before game launch for redundantly overriding the display
contract; its preflight logs remain separate from the ten measured runs.
