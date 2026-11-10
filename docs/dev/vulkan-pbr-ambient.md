# Native Vulkan PBR ambient lights

Status: implemented; 41 lighting, 18 capacity and 44 resource controls pass on
Windows/NVIDIA (the counts below are from the v26 qualification; the current
evidence is in the production-readiness plan). This is authored `ambientLight`
material lighting, separate from analytic IBL, reflection probes and baked
light grids.

Eligible PBR receivers evaluate an ambient light in the same linear material
domain as their point and projected lights. Since Stage E of the
[production-readiness plan](archive/2026-10-18/plans/2026-10-04-pbr-production-readiness.md) an
authored ambient light is a uniform environment: an irradiance E (pi times the
sRGB-decoded classic light term, projection x falloff x light color,
`PBRClassicLightIrradiance`) is radiance E/pi from every direction. It reaches
Fresnel-weighted diffuse, (1 - F) x linear albedo x (1 - metallic) x E/pi with
F the roughness-aware Fresnel at N.V, and the split-sum specular
(f0 A + (1 - f0) B) x E/pi with energy compensation
(`PBRUniformEnvironmentSpecular`), so metals reflect it. Per-light passes bind
no split-sum table, so the bias B has its own fit (`PBRSpecularBias`). Material
AO occludes both terms, as for environment light: the multi-bounce form
`PBRMultiBounceAO(ao, (1 - metallic) albedo)` on diffuse, specular occlusion
and horizon occlusion on specular. Each light stage is one draw whose radiance
is encoded into the display-referred framebuffer on its own, like a classic
interaction; a white rough dielectric seen head-on returns 0.97 of the classic
term and a white conductor all of it. The AO scalar travels in `pc.b.x`, which
the classic ambient direction occupies for classic draws only. Separate
metallic, roughness and AO maps are packed into one ORM image at load
(`packORM`), so the stage reads all three channels from the slot that holds
material data. The parity oracle (`renderer_pbr_ambient_parity.py`, with the
NumPy reference `pbr_reference.py`) predicts the view-dependent response pixel
by pixel over the specimen sphere, with the per-stage encoding and the
framebuffer's white limit; `ao_zero` is black under an ambient light. OpenGL's
classic light loop owns the same evaluation (Stage B), and the modern
clustered path builds one record per ambient stage like other additive lights,
although its whole-frame owner still declines scenes with ambient lights
(below).
Material diagnostics and emission retain their once-per-surface owner.

Previously, `VK_PBRDirectInteraction` rejected ambient lights. Opaque PBR
surfaces therefore accumulated the classic tangent-space ambient response, and
transparent PBR surfaces received classic lighting before their ordered native
alpha composite. Ambient stages were also absent from the transparent record
bound and resource transaction. They now use the same admission, preparation,
recording, rollback and ordered replay as other supported lights. Every active
ambient stage counts toward the complete 256-record bound. Classic materials
and rejected PBR materials retain their existing shader.

## Reproduction and acceptance

Prepare a fresh laboratory runtime with `renderer_pbr_laboratory.py --prepare`
after generating the current fixture. The two precached ambient materials have
white projection/falloff textures and one or two colored stages. The dedicated
capture tool uses constant radiance to make the material response independently
calculable, with a classic background retained behind source-alpha surfaces.

```text
python tools/tests/renderer_vulkan_pbr_ambient.py --runtime-root <laboratory> --basepath <retail-assets> --output-dir <captures> --backend vk --samples 0
python tools/tests/renderer_pbr_ambient_parity.py --vk <captures>/report.json --output <proof.json>
python tools/tests/renderer_vulkan_pbr_capacity.py --runtime-root <laboratory> --basepath <retail-assets> --output-dir <capacity> --samples 0 --ambient-lights
python tools/tests/renderer_vulkan_pbr_resources.py --runtime-root <laboratory> --basepath <retail-assets> --output-dir <resources> --samples 0 --ambient-lights
```

Repeat with `--samples 4`. The 41 lighting captures cover scalar/packed/separate
material data, zero AO, roughness extremes, metallic rejection, normal encodings,
rotation, cutouts, diagnostics, emission, two lights, two stages, transparent
backgrounds, resource rejection and image/partial/full restart. The proof checks
absolute pixel values and alpha composition within 1.1 display bytes, plus exact
material, rollback and restoration comparisons. Fully covered interior pixels
are identified from a separate ownership capture, including a cutout control.
It validates complete capture sets, image/log hashes and actual sample counts.

The v25 negative and v26 candidate are retained under
`.tmp/vulkan-gap-closure/pbr-direct-curvature/`. The old scalar sample reads
147/73/37 at its center; the corrected value is 24/12/6. A metallic sample changes
from 191/62/20 to black with IBL disabled. The negative fails both the numerical
checks and complete ambient-record ownership. Both candidate sample counts pass
all 55 independent checks, including exact full-frame material, rollback and
image/restart restoration comparisons. Numerical error remains below one byte.
The 36 ambient-stage capacity captures pass at, below and above the record bound,
including exact complete classic fallback. All 88 ambient resource captures pass
early/late failure, descriptor rollback, image/video recovery and unlit/skipped
view checks. Six classic/background controls match v25 byte-for-byte.

The first complete direct-light run passed 67/68 controls. Its source-alpha
predicate wrongly rejected green opaque diagnostic spheres visible behind the
transparent specimen; the same image is byte-identical on v25. The direct suite
now hides the background stations before drawing its isolated specimen. The
original failure and old-binary reproduction remain in `direct-v26-0` and
`direct-alpha-background-v25-0`. Both corrected 68-case runs pass in
`direct-v26-0b` and `direct-v26-4b`, including point/projected shadows, emission,
cutouts and restarts. Their complete alpha interior is exactly 0/112/0, matching
the authored source alpha. The 342 accepted captures, retained negatives,
runtime/source hashes and staging state are bound in `checkpoint-v26-ambient.json`.

The attempted production GL pair is **not a valid PBR reference**: its mixed
classic/ambient scene declines modern lighting ownership. That failed capture is
retained as `ambient-gl-v26-0`; no diagnostic parity override is used to turn it
into production evidence. The optional `--gl` comparison rejects that report.
Independent native radiance qualification does not claim GL scene parity.

## Remaining scope

Ambient admission removes one source of mixed numeric lighting on PBR surfaces.
Production composition no longer needs a linear scene: every PBR draw encodes
into the classic display-referred framebuffer, and the linear scene is the
laboratory mode `r_pbrLinearScene`. Linear HDR scene ownership remains a
laboratory feature. See
[native HDR acceptance](vulkan-hdr.md#remaining-acceptance).
