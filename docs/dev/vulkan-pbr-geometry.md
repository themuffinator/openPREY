# Native Vulkan PBR receiver geometry

Status: implementation under qualification. The focused back-facing plane
passes its lighting controls at 0x/4x. Whole frames pass at 0x, while 4x still
fails at the laboratory's classic ceiling edges. Curved normal-mapped surfaces
also have a few silhouette differences; integration checks remain open.
This work does not promote Vulkan from experimental status.

Classic interactions discard triangles whose geometric face normals point
away from the light. An interpolated or mapped PBR normal can still face the
light on those triangles. The native PBR pass previously inherited the classic
subset, leaving missing lighting around curved and normal-mapped receivers.

The Vulkan frontend now retains a separate PBR triangle set for authored PBR
materials when facing rejection would remove geometry. Both sets use the
existing light-volume and optional precise triangle tests. The classic set
keeps its original indexes and remains available when native material or
resource admission declines the surface. Even a completely empty classic set
can retain a nonempty PBR receiver. View culling includes the PBR bounds.

The interaction owns and frees both sets together. The draw surface carries
a frame copy of the PBR geometry that borrows the current ambient vertex
cache; temporary MD5R cache handles are never stored in the persistent set.
Native direct draws select that geometry, and ordered transparency records its
prepared offsets before taking ownership. Classic stages restore their original
binding. OpenGL does not construct the additional PBR set.

Native PBR light and eye vectors also stay in object space through interpolation
and are evaluated against the final object-space normal. The vertex basis now
uses the same tangent orthogonalization as the modern GL path. These changes
apply to the ordinary, projected-shadow and point-shadow shaders; the classic
shader branch keeps its previous calculation.

## Current evidence

The procedural laboratory generator includes the original two-triangle plane.
Prepare or update an independent laboratory runtime, then capture both backends
with `tools/tests/renderer_vulkan_pbr_geometry.py --runtime-root <laboratory>
--basepath <retail-assets> --output-dir <fresh-output> --backend <gl-or-vk>
--samples <0-or-4>`. Run `tools/tests/renderer_pbr_geometry_parity.py --gl-report
<gl-output>/report.json --vk-report <vk-output>/report.json --output
<comparison.json>` to qualify the images. Generic capture success alone is
insufficient; the comparator requires positive mapped lighting, black rejected
controls, exact restoration, active requested MSAA and matching provenance.

Evidence is retained under `.tmp/vulkan-gap-closure/pbr-direct-curvature/`.
The frozen v22 plane comparison (`plane-parity-v22.json`) passes all 11 controls
against `plane-gl-v22c/report.json`, with at most two bytes of full-frame error.
Mapped illumination is positive when both geometric triangles face away from
the light. Flat normals, classic rollback and receivers outside the light
volume remain black. Restoration, precise culling and the all-face diagnostic
switch reproduce the same native image exactly.

The same predicate rejects `plane-v21c-negative/report.json`: the old binary
loses the mapped back-face contribution. Earlier `plane-v22b` and
`plane-gl-v22` captures are invalid as proof: they omitted an explicit spawn
angle, leaving the plane edge-on to the camera. Their generic capture success
does not establish visible rendering correctness.

The 18-control sphere experiment also includes seven unlit diagnostic views.
In `parity-v23.json`, ordinary scalar, sharp/rough metal, translated and restored
PBR controls match GL within one byte, while the classic control remains within
two. Four mapped/rotated controls still fail the strict comparison at two to
six pixels near the silhouette. The v22 native PBR images exactly reproduce
the global all-face experiment while its classic image remains byte-identical
to the prior default-culling renderer. The global switch itself changes classic
lighting and is not the shipped correction.

The remaining silhouette differences, mapped
shadows and final probe/IBL integration are
separate unfinished checks. No comparison limit was loosened to accept these
differences. The original probe qualification remains tied to its v19 runtime.
The later v25 candidate passes all seven original unlit diagnostic views;
its scalar/metal controls pass and the four mapped-lighting failures remain.

The frozen v23 package additionally passes all 44 transparent resource controls
at both 0x and 4x in `resources-v23-0/report.json` and
`resources-v23-4/report.json`, including exact classic fallback for injected
preparation failures and native recovery after image/video reload. Those
results do not qualify the broader integration runs.

The canonical 4x geometry captures (`geometry-vk-v23-4` and `geometry-gl-v23-4`)
pass mapped illumination, black flat/classic/outside controls and exact native
restoration. The receiver differs by at most one byte, including its boundary.
The strict whole-frame gate remains failed: classic ceiling edges above the
receiver differ by up to eight bytes, including with PBR disabled. The original
`geometry-parity-v23-4.json` failure is retained; the subsequent report adds a
separate receiver result without relaxing the whole-frame gate.

The 0x curvature coverage diagnostic finds identical full ambient and direct
mesh masks in GL and Vulkan, including all remaining radiance mismatches.
There are 29,802 covered pixels in the ordinary orientation and 29,762 in the
rotated one, with no missing direct fragments. A temporary BRDF instrument
then confirms opposite signs of N.V at the mismatches; the light dot products
also differ. All instrumented source files were restored byte for byte and
rebuilt. The diagnostic binaries are isolated from production staging.

Explicit 1x/4x/16x anisotropy controls change the failed pixels. At 1x, the
ordinary RG-normal case passes within one byte, XYZ/AGB retain one failed
pixel, and the rotated case retains five. This implicates texture sampling
but does not establish a complete cause or close the strict radiance gate.
The APIs allow implementation-dependent anisotropic filtering
([Vulkan sampling specification](https://docs.vulkan.org/spec/latest/chapters/textures.html#textures-texel-anisotropic-filtering));
that permission alone is not proof of the source of these differences.
Reports `direct-coverage-diagnosis-v23-0.json`, `grazing-diagnostic-v23.json`
and `anisotropy-diagnosis-v23-0.json` retain the separate observations.

Later material-normal controls isolate the difference to mipmapped sampling:
all constant X/Y/Z normals and non-mipmapped bilinear/nearest controls match
within one byte, including rotation. Queried GL and standard Vulkan 4x sample
positions explain the opaque sphere's one-sample boundary differences. Both
complete coverage images match an independent raster oracle using their own
positions and eight-bit subpixel precision. See the
[diagnostic qualification](vulkan-pbr-diagnostics.md) for evidence and limits.
This result does not qualify the separate classic ceiling, cutout boundary
or mapped-lighting comparisons.
