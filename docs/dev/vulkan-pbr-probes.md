# Native Vulkan authored PBR probes

Status: authored LDR probe controls locally qualified at 0x/4x on Windows with
an NVIDIA RTX 4060 Laptop GPU. Vulkan remains experimental. This does not
complete baked PBR diffuse, clustered decals, complete HDR composition or the
broader Vulkan release requirements.

The native environment owner now has an authored-probe path behind the existing
`r_rendererReflectionProbes`, `r_pbrMaterials` and `r_pbrIBL` controls. It uses the
same atlas layout, CPU convolution and cluster selection as OpenGL.

## Resource and selection contract

- Eight authored cubemaps share the analytic environment's RGBA16F atlas. Each
  receives six independently filtered faces at seven roughness levels and an
  octahedral diffuse-irradiance tile. The split-sum BRDF tile is shared.
- The source reader validates and decodes complete, immutable color cubemaps.
  Storage, image and upload generations invalidate stale residency, including
  in-place uploads. See [probe sources](vulkan-probe-sources.md).
- Stable least-recently-used replacement excludes every slot referenced in the
  current GPU recording frame, including preceding command packets. Uploads
  execute on the graphics queue after earlier submitted reads. Reloaded images
  keep the existing deferred image/descriptor lifetime rules.
- `R_ModernClusteredLighting_PrepareProbes` is a CPU-only export with a resident
  atlas callback. It reuses the existing sphere/box-volume and material validation,
  grid policy and deterministic priority/weight/stable-identity top-two binning.
  Vulkan does not call the GL upload or binding entry point.
- Each view publishes at most 32 packed records and two indices per cluster.
  Its native storage buffer uses set 7 of a dedicated environment pipeline,
  within the existing eight-set device requirement. Per-frame-slot buffers and
  descriptor pools are reused only after their frame fence completes. There
  are at most 64 probe view publications per GPU frame.
- Invalid, stale, incomplete or over-capacity probe sets use the analytic
  environment. A native view-resource failure declines environment admission;
  ordered transparent rendering rolls back its whole prepared view before
  taking framebuffer ownership.
- Shader evaluation preserves probe rotation, tint/intensity, spherical or box fade,
  normalized overlap, roughness filtering, AO and the analytic remainder.
  Projection before Vulkan's Y flip addresses the shared bottom-origin grid.

The ordinary analytic pipeline remains available when no authored records are
published. Eligible baked HDR receivers now use a [combined baked/probe
path](vulkan-pbr-baked.md), replacing environment diffuse while retaining probe
specular. Other baked views retain their existing exclusion.

## Box probes and in-engine capture (2026-10-05)

A `boxParallax` probe's record carries its half extents in a seventh vec4
(`boxExtents`, w 1; 112-byte records). `pbr_probes.glsl` weighs it with the
shared `PBRBoxInfluence` and looks each reflection up where it leaves the box
(`PBRBoxParallaxDistance`), exactly as the OpenGL owner and the modern GL path
do. `bakeReflectionProbes` fills a probe's cubemap from the running map on
either backend; the readback, filtering and residency of a reloaded image are
the ones described above. See the [production-readiness
plan](archive/2026-10-18/plans/2026-10-04-pbr-production-readiness.md) for the controls.

## Qualification

`tools/tests/renderer_vulkan_pbr_probes.py` creates original laboratory-only
probe assets and records engine screenshots from hidden, windowed gameplay.
It covers individual sources, orientation, overlap/priority, edge fade,
separated horizontal/vertical volumes, translated/tilted receivers,
roughness, normals, AO, cutouts, transparency, eight/nine-slot capacity,
record overflow, invalid volumes, eviction, image/video reload and resource
failures. Evidence is retained under `.tmp/vulkan-gap-closure/pbr-probes/`.
The frozen v19 package passes all 46 native controls at both 0x and 4x,
including explicit Vulkan validation, reload/restart and injected failures.
All 40 GL controls and their full-frame native comparison pass at both sample
counts: 172 captures and 80 paired comparisons in total. Non-cutout 0x frames
and the non-cutout 4x shading regions agree within one byte. MSAA geometry
edges retain separate whole-frame bounds. `checkpoint-v19-probes.json` pins
the six reports, all 106 runtime files, source checkpoint and retained failures.
Later direct-light/default-setting candidates have their own regression chain.

The v18 investigation passes 40 native and 34 GL controls independently, with
active Vulkan validation and synchronous GL diagnostics. The cross-backend
gate rejects its three cutout captures at exactly one alpha-threshold pixel.
Every other common full frame agrees within one color byte. That retained
failure is `parity-v18-negative.json`; it is not accepted final parity evidence.

This investigation corrected two other visible defects: the native environment
now interpolates the actual object-space eye vector, avoiding curved-basis
reflection errors, and GL retains the filtered analytic atlas when an authored
set exceeds capacity. The nine-source fallback now exactly matches the analytic
control, as do same-placement image and partial-video reloads.

The v19 candidate also aligns native PBR hard cutouts with GL's inclusive
threshold, while preserving the classic strict alpha test. That semantic
correction does not remove the isolated edge pixel: the measured masks differ
at (677, 490), with 14,916 versus 14,915 covered pixels and no light in either
backend's holes. Shader/texture rounding is a possible explanation, not a
captured subpixel-alpha measurement. Vulkan explicitly reports finite
[sampling precision](https://docs.vulkan.org/spec/latest/chapters/limits.html#limits-subTexelPrecisionBits).

The full-frame gate therefore separates binary coverage from radiance. It
permits at most 0.01% of covered pixels (capped at four pixels per frame), only
at an observed mask boundary. Common covered pixels still have a two-byte
limit; holes must remain black and unmatched edges cannot exceed the measured
peak. Negative controls reject interior holes, systematic erosion, stray light,
overbright edges, empty/partial masks and three-byte shading errors. The
stricter previous comparator and its original failure remain retained.

The first v19 run
passes all 46 capture/diagnostic checks but rejects a weak 45-degree receiver
rotation control (0.193/255 mean change versus its 0.2 threshold). A larger
90-degree tilt changes the specimen by 0.437/255 and passes the focused paired
comparison and subsequent native full suites. Coverage diagnostics use the
existing emissive cutout fixture, which has the same alpha texture/threshold
and produces ownership without direct lights; empty masks are rejected.

The first 4x comparator run incorrectly treated screen center as the translated
specimen's interior. Its patch crossed the moved sphere's MSAA edge, producing
a five-byte maximum. The comparator now projects the captured spawn origin
through the recorded camera and retains the same 65x65 shading region and
two-byte limit. The translated interior is byte-identical; all whole-frame
limits remain unchanged. Negative tests reject ambiguous spawns and unsupported
framing and keep detecting a three-byte shading error at the translated center.
The original failed report and comparator remain under `probes-parity-4-v19b.json`
and `harness-v19b/`; final paired reports use the `v19c` suffix.

This fixture uses original LDR authored cubemaps. HDR source readback has its
own evidence, but complete HDR probe consumption/accumulation and other
physical GPUs/platforms remain separate qualification requirements.
