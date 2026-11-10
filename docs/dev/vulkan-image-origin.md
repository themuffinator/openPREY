# Vulkan framebuffer and image orientation

Status: the canonical offscreen path uses a positive-height viewport and GL
window coordinates, with local numerical, gameplay and paired-image validation.
Vulkan remains experimental; this does not promote the backend.

## Storage and rendering

Canonical geometry stores offscreen color and depth in GL row order. The
swapchain retains its existing top-down convention. Viewports, scissors,
depth/stencil clears and face winding follow the active attachment convention.
Supported custom MSAA sample locations use the same coordinates and indices in
pipeline creation, depth transitions and depth resolves. Unsupported devices
retain their native sample locations.

The pipeline target includes its coordinate convention. Fragment specialization
constant 15 supplies it to screen-coordinate material, light-grid and particle
shaders. Raw texel-copy and HDR per-sample composition shaders continue to use
physical image coordinates. HDR composition restores canonical face winding
even when there are no direct lights; otherwise subsequent geometry can be
culled incorrectly.

`materialSampleFlipY` records the stored row order for both color and depth.
Writers update it, resolves preserve it, and target binds leave it alone.
CopyRender exports GL row order. Material sampling, temporal scene/depth/history
sampling and presentation normalize each input separately. Motion-vector images
keep their established GL coordinate convention, while temporal resolve outputs
retain top-down storage. The temporal uniform remains 256 bytes; existing
recenter flags now share a word with the three input-orientation flags.

The temporary `r_vkImageOrigin` switch is removed. The target policy cannot
change halfway through a process and invalidate existing depth sample metadata.
No replacement game assets or external shader files are required.

Eligible native-resolution main scenes also use the canonical offscreen path,
including ordinary single-sample LDR views. This avoids changing interpolated
radial shadow references solely because the viewport reverses on the swapchain.
The existing spatial presenter writes the upright result; root-view admission,
resource preflight and fallback behavior remain in place. The local
[point-shadow investigation](vulkan-point-shadow-parity.md#general-radial-depth-correction)
records the numerical evidence and the remaining stencil/sampling differences.

## Qualification

The staged default implementation passes the Vulkan target, HDR and temporal
GPU contracts with validation enabled, including full renderer restart. The
motion contract now exercises 36 numerical cases: both stored depth origins,
two image sizes and nine independent motion/occlusion/scissor fixtures. Its
expected vectors and HDR radiance values are unchanged. Synthetic HDR patterns
are authored in the same visual orientation for either attachment convention.
The embedded shader/header pins and temporal source contract pass.

All 38 native HDR post controls pass, covering manual and automatic exposure,
bloom thresholds and mip chains, preparation failure and restoration, scaling,
asymmetric image positions, resize, image reload, full/partial video restart
and capture stability. All 80 GL/native 8x preview controls pass independently,
and all 40 paired images pass within one display value; 27 are exact. The
125%/8x specimen that failed by 49 values in v40/v41 now matches exactly without
post-capture reflection. The fresh GL reference uses the same harness as the
Vulkan run; the retained v40 report was rejected for a source fingerprint mismatch.

Both staged stock SP/MP runs pass with sixteen engine captures, including 8x
MSAA, SMAA modes, HDR, image reload and partial video restart. No tracked
renderer warnings occur. A fresh OpenGL SP run also passes its eight captures.
The inspected SP scenes have comparable floor filtering and upright geometry
and HUD; moving actors and effects prevent an exact gameplay image comparison.
Representative MP and laboratory engine captures were also inspected.

All sixteen ordinary/minified cutout pairs now match the retained OpenGL
reference exactly at 0x/4x MSAA in both display and linear captures. Independent
opaque-mask, restoration, image-reload and partial/full video-restart controls
also pass. This closes the ordinary cutout's v43 one-pixel/two-pixel residuals
without changing either comparison limit.

The final v44 candidate reduced the original smoothed 4x,
16x-anisotropic cutout mismatch from 444 pixels to four, without reflecting the
exported image. At 1x anisotropy, both hard and smoothed cutout coverage matched
OpenGL exactly. Environment lighting at that setting differed by at most
0.000244140625 in linear radiance and matched in display space. Baked lighting
still exceeded the existing comparison limit. The full-frame comparison uses
the same scene profile, compiled map, bake and OpenGL module as its reference.

| Isolated 4x case | Maximum linear difference | Maximum display difference | Strict result |
|---|---:|---:|---|
| Smoothed coverage, 1x anisotropy | 0 | 0 | Pass |
| Hard coverage, 1x anisotropy | 0 | 0 | Pass |
| Smoothed coverage, 16x anisotropy | 0.25 | 165 | Fail |
| Environment, 1x anisotropy | 0.000244140625 | 0 | Pass |
| Environment, 16x anisotropy | 0.09600830078125 | 97 | Fail |
| Baked, 1x anisotropy | 0.00426483154296875 | 6 | Fail |
| Baked, 16x anisotropy | 0.0331573486328125 | 37 | Fail |

The later [filtering investigation](vulkan-pbr-cutout.md#v45-filtering-investigation)
also finds small between-process variation in the GL smoothed mask. The table
above records the named v44 capture pair; it is not a claim that every new GL
process produces the same coverage. The hard-cutoff controls remain repeatable.

Evidence lives under `.tmp/vulkan-gap-closure/framebuffer-orientation/`.
`archive-v44e-source` and `archive-v44e-runtime` identify the default candidate.
`checkpoint-v44-image-origin.json` binds final sources, runtime, reports and
visual inspection; `archive-v44-final` preserves those final sources.
Rejected earlier runs are retained: the first build lacked two declarations;
the first GPU fixtures assumed the old storage order; and the first minification
run exposed the HDR pass's stale face-winding state. None is accepted as passing
evidence. A prototype-only profile mismatch is likewise not a paired pass.

The unchanged paired-image limits are two display values and 0.003 linear
radiance per channel over the complete image. No silhouette exclusion,
post-capture reflection or tolerance increase is used. Current evidence is
local Windows/NVIDIA correctness evidence. Other GPU families, operating
systems, long sessions and performance remain separate requirements.
