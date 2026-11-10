# Native Vulkan baked PBR lighting

Status: bounded HDR implementation with local correctness evidence. Vulkan remains
experimental. Full-frame OpenGL parity and broader baked material/view coverage
remain open.

## Composition and admission

Eligible root HDR views now prepare native baked-light receivers before taking
framebuffer ownership. Baked irradiance replaces environment diffuse, while
analytic or authored-probe specular remains available. Metallic, roughness and
occlusion channels retain the existing PBR material contract. Zero baked
intensity suppresses baked diffuse without restoring environment diffuse.

The shader consumes the existing area irradiance, visibility and relocation
atlases. It preserves interpolation, visibility weighting, black-probe handling,
intensity, gamma and contribution limits. PBR decodes each contributing encoded
irradiance sample before interpolation. Admitted classic flat-normal receivers
keep encoded lighting in the classic attachment until the complete classic
result is decoded by HDR composition. Their quantized AGB flat normal is decoded
like OpenGL's; assuming an exact `(0,0,1)` changed the sampled baked lighting.

All receiving surfaces must be prepared successfully. A failed grid, material,
descriptor, uniform or geometry preparation clears the prepared receiver set
and restores the existing uniform/geometry/image-descriptor checkpoints. Both
required pipeline variants are obtained before HDR composition starts. The
classic baked walker is suppressed only while the complete prepared HDR view
owns its receivers; a rejected view follows the existing rendering path.

The additional descriptor set holds the three grid atlases, their seven-vector
metadata block and optional authored-probe records. It stays within the existing
eight-set device contract. Per-frame descriptor pools and immutable cache entries
are reused only after their slot's fence completes. Image generations participate
in cache identity. Grid residency advances once per view even when modern
admission later fails.

The admitted scope excludes portal/multiple-grid blends, view-weapon depth
ranges, baked diagnostics, unsupported classic bump/ambient/program combinations,
and the other whole-view HDR exclusions. Classic receivers currently require
three static explicit bump/diffuse/specular stages and the engine flat normal.
HDR-off baked PBR previews remain outside this scope, matching the existing
OpenGL restriction; they keep their established fallback, which is the
production composition below.

## Production composition

The whole-view preparation above belongs to the laboratory's linear HDR scene
(`r_pbrLinearScene 1`). In an ordinary display-referred frame, as players run
it, a native PBR receiver composes its grid in its own environment pass, like
the OpenGL owner (stage E of the
[production-readiness plan](archive/2026-10-18/plans/2026-10-04-pbr-production-readiness.md)): the
same grid contract (`VK_LightGrid_PrepareModern`) and shader, decoding each
atlas sample to linear light and encoding the draw once into the frame. The
classic grid pass skips every native PBR receiver (`VK_PBR_GridOwned`), so a
grid adds its light once and never lights a PBR surface through its legacy
diffuse stage; a receiver the grid contract declines keeps its environment
pass alone, as on OpenGL. Classic receivers keep the classic grid pass.
`gfxInfo` counts these draws as `production` on its `Vulkan baked lighting:`
line.

Paired with the OpenGL owner in the laboratory (`--production`), every one of
the 24 stations agrees within one display value, metals and zero-AO surfaces
receive no grid diffuse on either backend, and doubling the grid intensity adds
the same light. The room's frame differs only along thin bands of normal
directions on grid-lit spheres (up to 16 display values, a few hundred pixels):
the laboratory's four-probe DXT1 atlas samples differently there on OpenGL and
Vulkan, and modern GL shows the same band against Vulkan's linear scene.

## Diagnostics and qualification

`gfxInfo` reports requested, prepared and submitted baked receivers, the
admission reason, and rollback counters. `r_vkPBRBakedFailure` injects grid (1),
descriptor (2), uniform (3), geometry (4) or pipeline (5) failure;
`r_vkPBRBakedFailureAfter` delays it until a specified number of receivers have
prepared. Both default to zero. A declined HDR view must refuse a public linear
screenshot rather than export a stale scene.

`tools/tests/renderer_vulkan_pbr_baked.py` binds both renderers to one unchanged
OpenGL-authored laboratory bake and records engine screenshots and linear
captures in hidden, windowed gameplay. Its suites cover material response,
isolated baked lighting, normal encodings, authored reflections, fog/blend
composition, image/video recovery, HDR-off fallback and late admission failure.
Successful baked controls require every requested receiver to prepare and submit
exactly once. The reference bake, runtime, fixture, settings and harness sources
are hashed in each report.

Independent controls and full-frame comparisons are separate results. The latter
retain limits of two display values and 0.003 absolute linear radiance per
channel. A passing material or lifecycle control does not waive a failed image
comparison. The original candidate that prepared 25 receivers but submitted only
one is retained as a rejected negative control; its apparent success under the
older generic harness is not accepted evidence.

The current investigation is retained under
`.tmp/vulkan-gap-closure/hdr-lightgrid/`. The first recovery test incorrectly
called the OpenGL-only `rendererShaderLibraryReload` command on Vulkan. The
corrected native suite tests image reload and partial/full `vid_restart`;
standalone Vulkan shader-library reload remains unsupported.

The final v42 runtime passes 79 independent GL/native laboratory controls and
both Vulkan target/HDR GPU contracts. Staged stock SP/MP runs pass with sixteen
engine screenshots, including image reload and partial restart, with no tracked
rendering warnings. Representative stock and laboratory captures were inspected.
`checkpoint-v42-baked-hdr.json` binds source, build, runtime, fixture, bake and
retained reports. All runs are local Windows NVIDIA RTX 4060 Laptop GPU
correctness checks; they provide no wider hardware, performance or soak claim.

The isolated 0x HDR tests locate remaining linear differences on bright emissive
surfaces, with a maximum of 0.00390625 without reflections. The corresponding
display comparison differs by at most one value. With reflections, a separate
maximum of 0.083984375 persists even when the baked grid is disabled. Normal-map
controls also retain full-frame edge differences. At 4x, the isolated baked-only
display comparison reaches 80 values around the cutout specimen; the linear
maximum there is 0.0873870849609375. Reflections increase the full-frame error,
including in grid-disabled controls. HDR-off fallback comparisons also remain
failed. These results are retained without a coverage/precision waiver; neither
a complete PBR parity claim nor a renderer promotion follows from this
implementation.

The follow-up [cutout coverage investigation](vulkan-pbr-cutout.md) corrects a
typed-albedo/depth-image mismatch and isolates most of the remaining smoothed
4x coverage difference to framebuffer orientation. The strict baked comparisons
above remain failed; the depth-image fix does not close them.

The subsequent [framebuffer-orientation implementation](vulkan-image-origin.md)
reduces the isolated coverage error while retaining explicit failures for baked
lighting beyond the strict comparison limit. It does not retroactively pass the
broader v42 comparison or extend the admitted baked-lighting scope.
