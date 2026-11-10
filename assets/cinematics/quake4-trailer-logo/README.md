# Quake 4 trailer title — cinematic 3D remaster

An editable Blender 4.5 LTS reconstruction of **2:00–2:06** in the
[Quake 4 E3 2005 trailer reference](https://www.youtube.com/watch?v=jHkjMqZJGuU&t=120s).

Open `quake4_trailer_logo.blend`. The **QUAKE 4 | Cinematic remaster** scene contains
180 frames at 30 fps and opens on the held title at frame 121. The MP4 is a silent,
1920 × 1080 Cycles render. The preceding gameplay cut at 120.00–120.27 seconds
is excluded; that interval stays dark and the title scene cuts in at 120.30.

The fifth revision was compared with the original every **200 ms**: 31 checkpoints
from 120.00 through 126.00 seconds. The local comparison viewer and paired frames
are retained in `.tmp/quake4-trailer-logo/audit-200ms-v5/`. `PARITY.md` records the
method, changes and remaining visual differences; topology checks alone do not
establish reference fidelity.

## Construction

The wordmark has six separately editable solid letters, drawn with deliberate
cubic curves and triangulated into closed meshes with sculpted metal chamfers. Hidden
source curves remain in **RM 04b / Editable letter masters**. The large iron
insignia has symmetric cubic arcs, defined gear shoulders, a tapered blade,
extruded sidewalls and a separate illuminated perimeter. Its upper horns now
follow the shorter cinematic outline. A closed mesh and clamped bevel replace
the curve offset that stretched the tips into needles. The round perimeter is
parented to the iron so their motion stays aligned. A hidden cubic master is
retained in **RM 03b / Editable insignia master**.

The hidden curves are authoring copies; editing them does not automatically
replace the rendered meshes. The mesh letters themselves remain editable, and
`remaster_lettering.py` holds the base curve definitions. `remaster_parity.py`
corrects the Q, U, K, E and 4 stroke weights and builds chamfer surfaces bounded by the contours,
avoiding the global bevel clamping that previously left flat white faces.

The background was rebuilt from the unobstructed **121.0-second** machinery
close-up and the **124.0-second** held shot. Broad crown and side panels replace
the previous regular spoke arrangement. The housing has separate diagonal load
arms, stepped covers, a vertical equipment pocket, deep bearing keyways and unequal
lower cooling and utility assemblies.

Each clamp is a closed casting with broad planar lands, slanted upper
fins and an angled lower toe. Three layered strap surfaces, rounded captive pivots and real
screwdriver slots sit over telescoping U-section rails. The jaws spread during
the reveal while the eye carrier recedes. The eye has a convex red globe, a
curved iris with irregular biological fibers, and a separate black pupil. The
optical opening is horizontally oval and seated in a thin olive metal bezel.

Procedural coating combines broad olive variation, fine grain, directional
scuffing and localized wear. A packed authored iris map supplies biological
fibers. Material nodes control roughness, relief and the red-to-amber transition.
The distinctive torn coating above the eye is placed separately
from the general weathering. The dark insignia has procedural iron pores;
silver roughness and small edge reflections keep the wordmark from reading as
flat white lettering. Paint color was compared with sampled reference patches.
The animated
camera, receding emblem, incoming title, red-to-amber eye, optical flashes and
closing fade follow the supplied shot. Cycles light linking controls the silver
reflections independently from the darker machinery. Compositing supplies soft
halation, brief horizontal flares, vignette and the trailer's letterbox.
The two reveal peaks are aligned to the 120.30-second cut and the 121.20-second
title rush. K crosses first; the remaining letters enter during the retreat.
Display-response curves make the closing silver highlights fade
together with the background. `display_transfer.json` records the measured AgX
response used for this attenuation.

**RM 07 / Animated optical overlays** contains the descending three-ring reticle,
its open outer contours and parallel diagonal leads, the nested right-hand glyph, faint peripheral arcs,
and drifting filaments and dust. These are separately editable 3D curves with
animated positions and transparency. Their reveal follows the title flash.
The former static wall etchings are retained hidden. A dedicated render AOV
isolates the insignia's green bloom so the technical graphics remain subdued.
The flash has separate source and pupil-occlusion passes, compact diffraction
and smooth diffusion. The horizontal flare follows its own brief envelope.

All of the machinery, eye, emblem and lettering are 3D objects. The iris texture
is packed into the self-contained scene. `textures/` also retains the earlier
authored enamel map as a source asset; the fifth revision uses procedural paint.
No footage cards, background image planes, downloaded models, external fonts or
extracted installed-game textures are embedded. The compressed trailer does
not expose its production geometry or exact material maps; this is a visual
reconstruction rather than the original production asset.

## Outputs

- `quake4_trailer_logo.blend` — editable scene and animation.
- `quake4_trailer_logo.mp4` — six-second 1080p render.
- `hero.png` — held title, frame 121.
- `contact_sheet.jpg` — selected frames from the delivered animation.
- `geometry_view.png` — oblique render showing actual depth and construction.
- `mechanical_clay.png` — neutral material study without the foreground title.
- `mechanical_closeup.png` — textured machinery before the wordmark reveal.
- `render_info.json` — verified output dimensions, duration and frame count.
- `QA.md` — scene checks, reference limitations and retained temporary evidence.
- `PARITY.md` — the 31-checkpoint comparison method and visual findings.

## Rebuilding and rendering

The scene was built and refined through Blender MCP. The adjacent Python scripts
also make the result reproducible:

```text
blender --factory-startup --background --python build_remaster.py
blender --factory-startup --background quake4_trailer_logo.blend --python render_scene.py -- animation /absolute/output/directory
```

`build_scene.py` forwards to the remaster builder. `remaster_scene.py` and the
`remaster_*` modules hold the geometry, materials, lighting, motion and finishing.
`remaster_lettering.py` holds the authored letter curves. `render_remaster.py`
provides a finite frame queue in a live Blender MCP session. `render_scene.py`
provides a background renderer with an explicit output directory and a CPU
fallback when OptiX is unavailable. The saved scene uses Cycles; an OptiX GPU is
recommended for interactive rendering. This asset is not part of the game runtime.

The current mechanical construction is in `remaster_mechanics.py`;
`remaster_wear.py`, `remaster_texture.py` and `remaster_mechanical_finish.py` apply
its surface treatment and final detail. The builder runs these after the earlier
camera, lettering and optical setup. `remaster_logo_overlays.py` then constructs
the corrected solid logo, refined metal finish and moving optical graphics.
`remaster_parity.py` applies the 200 ms audit corrections last: real silver
chamfers, revised castings and optical seat, the vertical pocket, measured
surface response, technical-line softness and optical timing.
The two texture maps were created with the
built-in image generation tool. Exact prompts are recorded in
[`texture_prompts.json`](texture_prompts.json).

## Reference credit

Quake 4, its wordmark, emblem and reference visual design belong to their respective
rights holders, including id Software and Raven Software. The user-supplied
[trailer upload](https://www.youtube.com/watch?v=jHkjMqZJGuU) supplied the composition
and timing. Locally installed Quake 4 lettering and emblem images were inspected
as silhouette guides; the deliverable uses reconstructed geometry and authored
materials. No third-party code or extracted game raster assets are incorporated.
This is an unofficial reconstruction.
