# Scene and reference verification

Reference fidelity was reviewed at all 31 timestamps, spaced 200 ms apart.
`PARITY.md` lists each checkpoint, the alignment method, changes and remaining
differences. Local paired images and the interactive comparison viewer are in
`.tmp/quake4-trailer-logo/audit-200ms-v5/`. Luminance measurements supplement
visual inspection; they are not a similarity or quality score.

## Editable construction

- The scene opens in Blender 4.5.2 LTS and rebuilds from `build_remaster.py`
  under factory startup. `scene_validation.json` records saved-file checks.
- The revised construction has 477 objects, including 324 meshes and 108 curves,
  plus camera, lights and motion controls. This is an authored 3D scene with
  genuine depth, rather than footage projected onto background cards.
- All six silver letters are closed meshes with zero nonmanifold edges. Their
  chamfers are triangulated, bounded surfaces. Six hidden editable cubic masters
  preserve the matching outlines. Q, U, K, E and 4 have revised stroke weights.
- The large iron insignia is a closed 1,928-vertex extrusion with zero
  nonmanifold edges. Its evaluated upper tips and width cannot extend beyond
  the authored silhouette. A clamped bevel replaces the earlier acute offset.
  The separate swept rim is parented to the iron and follows its animated scale.
- Both replacement clamp castings are closed meshes. Broad lands, three
  layered strap surfaces and recessed captive pins sit above telescoping rails.
  Jaw displacement and rail extension were checked before and after opening.
- The oval optical seat, vertical background recess, narrow lower braces and
  unequal lower utility assemblies are separate geometry. `geometry_view.png`
  shows the assembly obliquely, and `mechanical_clay.png` shows neutral geometry.
- One authored iris image is packed. The current paint and metal finishes use
  procedural material nodes. The earlier authored enamel map is retained in
  `textures/` as source material, but is not required by the current scene.

## Motion, overlays and optics

- The scene contains 180 frames at 30 fps, rendered at 1920 × 1080 in Cycles.
  Frame 181 is additionally rendered for the exact 126.00-second QA endpoint.
- The source's preceding gameplay is excluded. Frames 1–9 remain dark; the
  modeled title cuts in at frame 10. The second flash and near-camera title
  crossing occur at frame 37. Only K is visible during that crossing; all six
  letters are visible by frame 43 during the retreat.
- The overlay collection contains 83 native curves and 13 controls. The
  descending reticle moves from approximately (437, 271) at frame 76 to
  (450, 367) at frame 121. Independent right glyph strokes, diagonal leads,
  outer arcs, fine filaments and dust appear during the reveal. The outer reticle
  contours are open beside the leads. The held opacity envelope stays at 0.19
  through frames 61–121, with no leftover brightness key from the earlier setup.
- Overlay graphics have physical curve thickness, animated depth and opacity.
  They do not cast shadows or illuminate the machinery. The former static wall
  etchings remain hidden. No new extracted game raster assets are included.
- Separate render passes isolate the iron rim, optical core, physical pupil
  mask and compact diffraction point. Compositing adds halation and flares.
  The bounded horn geometry is independent of those optical effects.
- The closing fade uses the measured view-response table in
  `display_transfer.json`, keeping the silver and background attenuation
  synchronized. The final dark olive floor matches the source more closely
  than a late white title over true black.
- No ray-traced Bevel material node remains. The visible bevels are geometry.

## Delivery checks and limitations

`render_info.json` records the decoded MP4 frame count, frame rate, dimensions,
changed frame transitions, ending pixel level and encoded hero-frame error.
The full animation uses 96 samples with denoising. It is six seconds and silent.
The additional endpoint still is excluded from the 180-frame MP4.

The delivered file was decoded and checked on 1 October 2026: **180 frames,
30 fps, 1920 × 1080, six seconds**, with 177 changed frame transitions. The
last frame's maximum channel value is 11/255. Mean absolute channel error
between the decoded held frame and its PNG render is 1.255/255. The manifest
includes SHA-256 hashes of the Blender file and MP4. All 31 final comparison
pairs were inspected across seven sheets; the review movie holds those pairs
at five frames per second, including the extra endpoint.

The original's exact optical scattering, temporal ghosting, fine casting
transitions and individual wear patterns remain approximate. The first two
checkpoints still contain preceding gameplay absent from this title scene.
Passing topology, rebuild or encoding checks does not establish a perfect
reference match; see the explicit open differences in `PARITY.md`.

The engine workspace contained unrelated changes before this work. This task
edits only the cinematic asset directory and project-local temporary evidence.
No game launch, operating-system screenshot or input injection was used.

The Blender saved-file check exits successfully but prints a shutdown allocation
warning for four blocks totaling 0.000095 MB. The factory rebuild exits cleanly.
The warning has not prevented validation or rendering.

Automatic approval review previously rejected disposable render/cache cleanup
with `blocked by policy`. Those project-local files remain; no alternate deletion
method was used to bypass that rejection. Reference evidence is intentionally
retained for continued comparison.
