# Outdoor terrain shadow mapping

The stock Sandstorm (`mp/q4dm2`) terrain showed repeating dark filter lines.
Air Defense 1 (`game/airdefense1`) also lost terrain brightness and useful debris
shadows in its opening outdoor view. These scenes use authored point sources;
fixing only parallel sunlight would not address them.

## Changes

Point shadow filtering previously compared neighbouring cubemap texels against
one radial receiver depth. On sloped terrain their correct depths differ, often
by more than the four-world-unit bias budget. The receiver now derives a triangle
plane before divergent fragment control flow and compares each sample at the
ray/plane intersection. Hardware PCF is reconstructed with its bilinear weights
where that correction is needed. Samples crossing a cube seam use the adjacent
face's actual texel centre. Manual raw-depth sampling uses the same geometric
reference. The native lookup remains when the existing bias safely covers the
tap displacement and texel footprint; bias debug modes retain their bypasses.

Air Defense 1's main light is far outside its authored radius box. Its 512-pixel
cube faces cannot resolve nearby curved terrain and thin debris well enough,
even with corrected planar sampling. Such sources now use a perspective map
covering the complete oriented radius box, provided every corner lies in front
of the source. Ordinary enclosing point sources keep their cubemaps. The new
projection preserves the source position and ray directions, uses linear depth
along its axis, and includes blockers between the source and light volume.
It shares the existing cascade fitting, overlap, stabilization, caching and
distant-source filtering policies. Authored illumination and light attenuation
are unchanged. Point-shadow disabling still selects stencil for these lights.

Keep `r_shadowMapCSM 1` for outdoor quality; disabling cascades uses the complete
single projection at lower receiver resolution. No map-specific rules or stock
asset replacements are involved. Vulkan's ordinary and HDR shader variants are
regenerated from the same receiver source.

The expanded Air Defense 1 route exposed another omission at the entrance:
railings first rejected by shadow LOD could remain rejected after the camera
approached them. The surface cache and randomized hold used the host's
`idLib::frameNumber`, which does not advance in the renderer modules' separate
idLib state. Shadow admission now refreshes for each renderer view, while the
hold uses the renderer's frame counter. Both backends share this correction.
It preserves the authored distance/coverage thresholds and staggered hold.

## Reproduction

```powershell
python tools/tests/renderer_shadow_mapping_maps.py --terrain-check --hidden `
  --basepath 'E:\SteamLibrary\steamapps\common\Quake 4' `
  --output .tmp/outdoor-shadow-review
```

The runner uses the repository's mode-specific SP/MP launches, staged binaries,
isolated saves, disabled mouse grabbing, explicit multiplayer auto-join and an
engine-owned window. Captures come from the registered `screenshot` command.
`--basepath` overrides a stale machine-specific asset path in the launch catalog.

The image check identifies lit terrain from agreement between each run's stencil
and shadows-off images. It rejects mean darkening beyond two display levels or
more than 10% of that region darkened by over six levels. A separate stencil
shadow region must retain at least 80% of the reference shadow contrast, so an
unshadowed image cannot pass. These gates reject the original captures: Sandstorm
darkened 24% of its lit terrain region; Air Defense 1 darkened 99% and retained
only 67% of the selected debris shadow contrast.

`rendererShadowProjectedDiagnosticSelfTest` also exercises the production distant
projection on 32 receiver/blocker rays under rotation and translation. It checks
volume coverage, equal projected coordinates along each ray, monotonic stored
depth, and retention of ordinary point/parallel classifications.

For the wider Air Defense 1 comparison:

```powershell
python tools/tests/renderer_shadow_mapping_maps.py --scenario airdefense1-outdoor `
  --hidden --basepath 'E:\SteamLibrary\steamapps\common\Quake 4' `
  --output .tmp/airdefense1-outdoor-review
```

This route covers nine distinct outdoor poses: the opening, wreckage, tank,
ridge, crater, reverse view, entrance, elevated vista and distant terrain.
It approaches the entrance before any shadow-mode switches can recreate
interactions, revisits it later, and returns to the opening. Each of the eleven
stops captures mapped, cache-bypassed, stencil and unshadowed rendering with
simulation frozen. Logged camera poses must match, including equivalent wrapped
angles. The lower-screen terrain and caster regions use the same brightness
and contrast gates as above. Cached/fresh images must agree within one RMS
display level. A separate entrance check allows two pixels of filter spread
but requires at least 90% of the stencil railing-shadow footprint to retain
nearby mapped occlusion; the missing-rail capture fails at 41%.

`rendererShadowPlannerSelfTest` also checks the production LOD cache with a
far-to-near view change within one renderer frame, retention during the hold,
and rejection after the hold expires. This catches the stale-clock problem
without depending on one map or backend.

## Local validation

The Windows x64 debug build passes the native renderer contracts, Vulkan shadow
compatibility checks and generated SPIR-V header verification. The staged client,
renderer modules, game modules and shader package match their build outputs by
SHA-256. Both outdoor maps pass the image gates on OpenGL and Vulkan:

| Scene / renderer | Lit mean difference (0–255) | Excessively dark lit pixels | Retained shadow contrast |
| --- | ---: | ---: | ---: |
| Sandstorm / OpenGL | +0.83 | 1.12% | 94.3% |
| Sandstorm / Vulkan | −0.21 | 1.27% | 94.3% |
| Air Defense 1 / OpenGL | +1.38 | 0.10% | 89.1% |
| Air Defense 1 / Vulkan | −0.01 | 0.08% | 89.2% |

An additional six-run matrix covers those maps and Air Defense 2's indoor opening
on both renderers. Engine captures were reviewed with raw-depth comparison,
cache bypass, a single projection, rotated filtering and point-shadow disabling.
Air Defense 1 and the indoor control reproduce the stencil image exactly when
point shadow mapping is disabled. Air Defense 1's single projection remains
usable, with reduced terrain and shadow detail compared with cascades. The MP
scene continues to animate, so its sequential whole-image controls are not
expected to match byte for byte. No renderer or shadow-resource failures were
reported.

### Expanded Air Defense 1 validation

The final Windows x64 staged build passes all eleven outdoor stops on both
OpenGL and Vulkan (88 scenario captures). The entrance railing check rises
from 40.8% support in the failing capture to 97.8% on OpenGL and 97.9% on Vulkan,
both on the initial approach and the return. All cached/fresh full-frame pairs
are identical. Visual review confirms terrain, structure, debris and railing
occlusion with the expected filtered edges relative to stencil.
Stock mover, helmet and door exclusions can still emit `SM missing caster`
diagnostics with retained stencil volumes. The existing compatibility path
keeps those volumes available as supplements to mapped ownership.

| View | GL lit delta (0–255) | Vulkan lit delta (0–255) | GL shadow contrast | Vulkan shadow contrast |
| --- | ---: | ---: | ---: | ---: |
| Entrance, first approach | +0.59 | −0.23 | 82.4% | 83.6% |
| Opening | +1.15 | −0.02 | 89.9% | 90.5% |
| Wreckage | +1.23 | 0.00 | 99.4% | 99.5% |
| Tank | +0.79 | −0.03 | 96.1% | 96.2% |
| Ridge | +0.74 | −0.01 | 87.4% | 92.3% |
| Crater | +0.76 | −0.01 | 83.1% | 90.3% |
| Reverse | +0.86 | −0.02 | 92.5% | 96.4% |
| Entrance, return | +0.52 | −0.23 | 81.8% | 82.7% |
| Elevated vista | +0.80 | 0.00 | 87.5% | 88.3% |
| Distant terrain | +2.13 | 0.00 | 89.8% | 90.5% |
| Opening, return | +1.15 | −0.02 | 90.2% | 90.8% |

At most 1.2% of the lit reference pixels exceed the six-level darkening
threshold at any stop. Shadow contrast is relative to each run's frozen
stencil/shadows-off pair; actor and effect state can differ between processes.
The first ridge angle faced predominantly lit ground and could contain too few
reference shadow pixels to qualify. Full-detail and lower-camera controls
confirmed this, so the final ridge view looks toward structure shadows on the
slope instead of weakening the reference-mask gate.

The LOD self-test passes in both renderer modules, including Vulkan without
the optional scene-packet planner. Sandstorm's terrain comparison and Air
Defense 2's indoor opening also pass on both backends after the LOD change.
Air Defense 1 reports no warnings. No renderer-resource or Vulkan validation
failures occur in these six final runs.

Expanded evidence is retained under `.tmp/airdefense1-outdoor-views/`: `final/`
contains the complete route, `sandstorm/` and `indoor/` contain the control
runs, and `final_image_validation.json` records the image checks and LOD test.
`entrance_before_after.png` shows the repaired railing shadows;
`final_gl_1.png` through `final_gl_3.png` and their Vulkan counterparts compare
all nine views with stencil and unshadowed rendering. `runtime_identity.json`
records the six matching build/stage hashes. Diagnostic probes and logs remain
alongside this evidence; automatic approval review blocked removal of their
verified disposable caches.

Unrelated stock-content diagnostics remain: Sandstorm reports missing AI AAS,
sound and precache warnings; Air Defense 2 reports uppercase asset paths. The
local launch catalog also retains a C-drive Steam asset path; the test command
above supplies the installed E-drive location explicitly.

Local Windows x64 evidence is retained under `.tmp/outdoor-shadows/`, including
the stock before/after images, launch/configuration files, logs and runtime
hashes. Other-platform qualification and the separate general Vulkan parity and
frame-pacing investigations remain open.
