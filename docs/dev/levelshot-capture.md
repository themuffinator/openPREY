# Levelshot capture

openPREY ships recaptures of retail Prey's loading screens with the tiles a
wide or tall window needs around them. Each set is a faithful copy of the
retail picture: the retail camera is recovered from the art, and the set is
rendered there by openPREY with shadow maps for every light. This page covers
what ships, how the engine uses it, how the sets were made, and how to make
them again.

## What ships

`content/basepr/pak2/` becomes `pak2.pk4` (client-only, bulk: the
"loadscreens" pack in `tools/build/content_packs.json`). Every set is five
1024x1024 tiles, each a 4:3 view stretched to a square as retail stores its
loading art:

| File | Use |
| --- | --- |
| `guis/assets/loading/<map>.tga` | the 4:3 centre; the compositor reads it |
| `guis/assets/loading/<map>_left.tga`, `_right`, `_top`, `_bottom` | the neighbouring views, continuing the centre's projection plane |
| `dds/guis/assets/loading/<map>{,_left,...}.dds` | DXT1 copies; the renderer prefers a `dds/` file, so these override retail's `dds/guis/assets/loading/<map>.dds` by name |

The TGA and DDS are both kept, as openQ4 decided for its loadscreens
(`content-pack-distribution.md`, PKG-03): materials sample the DDS, and the
wide picture is composed on the CPU from the TGAs. `roadhouse` uses the
generic key art (its retail `roadhouse.tga` is byte-identical to
`loading.tga`), so pak2 carries the generic art's four tiles under its name;
git stores them once.

pak2 holds all 33 of retail's in-game loading screens and the roadhouse tiles:
334 files, 275 MB compressed.

## How the engine uses it

- **Loading art lookup.** Retail Prey loads every level under
  `guis/map/loading.gui` and picks its picture in this order
  (`idSessionLocal::LoadLoadingGui` and `idFileSystemLocal::FindMapScreenshot`
  in `PREY.exe` 1.4, the latter asked for the loading art rather than the menu
  thumb):
  1. when a save is loading, the save's own screenshot,
     `savegames/<save>.tga`;
  2. `guis/assets/loading/<map>.tga`;
  3. that picture from an addon pak that is not mounted yet, copied to
     `guis/assets/loading/addon/<map>.tga` under `fs_savepath`;
  4. the generic `guis/assets/loading/loading.tga`.

  The menus' pictures under `loading/thumbs/` are never the loading art.
  openPREY drops step 1: a save's preview screenshot is never the loading
  backdrop, so a save loads under its map's loading art like any other load.
  `Session_FindMapLoadingImage` (`Session.cpp`) follows steps 2 to 4 for the
  stock screen, the retained screen (`guis/loading/loading.rui`,
  `prey-ui-visual-design.md` section 12.5) and the retained pause shot.
  openPREY adds a mapDef's `loadimage` ahead of them (no retail mapDef has
  one), and copies an addon map's `_left`, `_right`,
  `_top` and `_bottom` tiles beside its picture.
- **Wide and tall windows.** The session composes the centre and its tiles
  into one picture of the window's shape (`Session_EnsureExpandedLoadingBackground`,
  `prey-ui-visual-design.md` section 12.1), named afresh for each
  composition. A picture without both of the tiles its window needs (a save's
  screenshot, `feedingtowera`, most addon art) is drawn at 4:3; its edge
  columns were stretched across the rest before.
- **The stock screen's default.** openPREY's `guis/map/loading.gui` set the
  generic picture in `onTime 0` whenever `gui::loading_bkgnd` equalled `""`.
  GUI expressions compare as numbers, so every image name equalled `""` and
  the stock screen always showed the generic picture. The session sets the
  picture on every load, and the default is gone.
- **`levelshot`** writes `guis/assets/loading/<map>` by default, Prey's path
  (it wrote openQ4's `gfx/guis/loadscreens/`), and logs `Capturing levelshot`
  before its tile views so a log can be read for exactly those views.

## Capture settings

The capture pins live in `tools/assets/levelshots/capture.py`:

- Shadow maps for every light class at the Ultra recipe: `r_useShadowMap 1`,
  `r_shadowMapPointLights 1`, 4096 projected maps in an 8192 atlas, 1024 point
  cubes, PCSS-lite filtering, cascaded sunlight. No stencil shadows anywhere.
  Each capture runs the tile views at `r_shadowMapReport 3` and fails if any
  view takes a stencil path.
- No screen-space post effects (`r_temporalAA`, MSAA, post AA, bloom, SSAO,
  HDR tone mapping, motion blur, CRT all 0) and no light grid: Prey had none.
  Prey's own glow overlay stays on at retail's defaults (`r_glowStrength 0.5`,
  `r_glowAlpha 0.55`, `r_glowAlphaChange 0.85`, `r_glowSteps 8`).
  Antialiasing comes from rendering each 4:3 source at 1.4 times the tile
  height (1912x1434) and area-averaging it down.
- A 2560x1440 hidden window; a hidden window cannot be larger than the
  desktop. A source larger than the window is rendered in sub-frustum regions
  and matches a one-pass render of it (see the renderer changes below), so
  supersampling is no longer capped by the window. The shipped sets were
  captured at 1.4x in one pass, and the capture fails if its source is not
  that 1912x1434, so a recapture reproduces them.
- OpenGL, muted rather than silent (`s_volume 0` with OpenAL Soft's null
  backend): lights whose materials read sound stay lit, and map scripts do not
  loop on zero-length sounds.
- Talon is removed before the shot (`hhTalon_spiritpower_hawk_<n>`); hidden,
  he shows himself again when he lands on a perch.
- The shot is taken 6 s after the map loads unless a set says otherwise.

### Renderer changes the captures needed

- **Prey program receivers take the shadow map.** Surfaces drawn by Prey's own
  ARB interaction programs (skin, cloth, hair, parallax, masked, the organic
  walls) cannot sample a shadow map and were shadowed by the light's stencil
  volumes even on shadow-mapped frames. The receiver program now writes the
  map's filtered visibility to destination alpha for them first, and their
  additive programs then draw with a `DST_ALPHA, ONE` blend
  (`r_shadowMapProgramReceivers`, default 1; `docs/user/shadow-mapping.md`).
  Surfaces it cannot cover (a non-additive stage, GPU-skinned geometry, a
  hybrid pass) keep the volumes, and `r_shadowMapReport 3` names them
  (`SM stencil-receiver`).
- **A levelshot leaves out the view weapon's shadow** with the weapon. A view
  model is never admitted to a shadow map, so its volume had turned its light's
  pass into a stencil hybrid in shots the weapon is not in.
- **Prey's distortion programs survive off-axis projections.** `heathaze`,
  `heatHazeWithMask(AndVertex)`, `refraction`, `distort`, `liquid` and
  `membrane` scale their deform by projection row 0 dotted with
  `(1, 0, z, 1)`, which is the row's scale term only for a symmetric
  projection. A side tile's shift (and a VR eye's asymmetry) added its shift
  times the view depth and smeared the glass. The ARB loader rewrites that
  line to the scale term, which is the same value in a symmetric view.
- **Beams face the view again** (`spindlea`'s forcefield beams). Retail's
  `.beam` model builds a view-independent ribbon, three rows of nodes on the
  beam's local X with the side rows on Y, and the beam materials'
  `deform beam` turns it to the viewer. openPREY's model built the ribbon
  facing the view already, so the deform turned it edge-on and every beam
  with that deform vanished. `hhRenderModelBeam` now builds retail's
  template, from `PREY.exe` 1.4 (`Model_hhBeam.cpp`).
- **The glow overlay follows retail** (`spindlea`'s energy spill, and the
  orange haze around its beams). Retail renders the `glowStage` passes into
  a 256x256 corner, blurs there with taps weighted alpha squared, and
  stretches the result over the view; the full-size blur with alpha-weighted
  taps drew the spill as an opaque white burst over the beams
  (`RB_STD_GlowOverlay`, `draw_common.cpp`). The same blur drew the
  multiplayer maps' hexagonal wall-walk panels (`textures/special/wallwalk`,
  whose additive stage is a `glowStage`) as thick white outlines that read as
  a hexagon twice the size; with the overlay off the pattern already matched.
  openPREY draws the glow-only view at full size, so the depth later passes
  read stays intact, and box-reduces it to the 256x256 image by repeated
  halving. The overlay is skipped when nothing in the view has a glow stage.
  Measured at `dmshuttle2`'s camera, the panels' mean colour is within 2 of
  retail's in every channel; it was two to three times brighter.
- **The glow includes the sky's glow stages** (`dmshuttle1`'s window). Retail's
  glow view is a full re-render, so its skybox subview draws its own glow
  stages too; there, the light cones around the Earth tint the stars teal.
  The glow pass now draws the view's skybox subview's glow stages first
  (`viewDef_t::skyboxSubview`, set by `R_GenerateSubViews`), and the view's
  own depth fill keeps them only behind its skyboxportal surfaces.
- **Fog lights fog only lit surfaces** (`dmshuttle1`'s Earth window). A black
  fog light (`fogs/basicfog`, `_color 0 0 0`) encloses the sky portal brush
  above the window. Retail creates a light's interaction with a surface only
  if the surface has lighting stages, fog and blend lights included
  (`idInteraction::CreateInteraction` in `PREY.exe` 1.4, Doom 3's rule).
  openPREY used Quake 4's rule for fog and blend lights, `ReceivesFog()`,
  which also takes ambient-only surfaces, so the fog painted the
  skyboxportal surface black over the sky (`Interaction.cpp`). The window
  frame, which is lit, still fogs black, as in retail.
- **A region-split source matches a one-pass render.** A source larger than
  the window is drawn as regions (each with a 64-pixel guard band), every one
  its own narrower sub-frustum of the 4:3 view. Two things in a region
  followed the region rather than the view:
  - *Shadow cascades.* Cascaded maps (here the parallel lights) were fitted to
    the region's frustum, so a region's cascades had smaller crops, finer
    texels and different biases, and a surface shadowed in a one-pass render
    could come out lit. In `keeperfortress` at `84 -160 -46.75 0 90 0` the
    room light (`light_4962`) lit a wall panel behind the corridor's glass
    and a wedge of the window frame, which looked like broken glass
    refraction and a bright polygon at the glass's lower edge. The screen
    copy (`_currentRender`) and its texture coordinates were correct
    throughout. A region now fits its cascades to its whole tile
    (`R_ShadowMapGetViewExtents`, from `tr_levelshotRegionScale` and
    `tr_levelshotTileShift`), so it renders the tile's own shadow maps.
  - *The distortion deform.* The rewritten scale term grows with a region's
    narrower field of view, which an offset in the region's own 0..1 screen
    units wants, but the programs clamp it (`MIN R1, R1, 0.02`) and apply one
    value to both axes. The loader now takes the scale back to the whole
    view's before the clamp and divides it by the region's share of the width
    and of the height after it (`program.local[8]`, identity outside
    regions).

  Checked with `r_levelshotSupersample 2` and `levelshot 512` at that
  camera: a 1365x1024 source in an 800x600 window (nine regions) against the
  same source in one pass at 2560x1440. Every tile differs from the one-pass
  render by no more than two one-pass launches differ from each other (mean
  0.32 against 0.51 for the centre tile; a creature moving behind the right
  tile's glass is the largest difference between launches). Before the fix
  the region-split centre tile differed in 2.7% of its pixels by more than 40
  levels.

## Recovering a retail camera

Every retail loading screen except `loading` and `roadhouse` (key art) is a
90-degree 4:3 in-game view. `pose_solve.py` renders probes with linear depth
(`levelshotProbe`), matches RootSIFT features (after CLAHE) between the
retail art and the probe, lifts the matched probe pixels to world points
through the depth, and solves PnP with RANSAC, repeating from each new pose
until it settles. Seeds:

1. Each player start at its own heading. Every single-player shot is a start
   view: the eye of the player as the level begins, after the drop from the
   start's origin where there is one.
2. Cube faces, six square 90-degree probes, at the starts and at a spread of
   map entities, scored by PnP inliers. The multiplayer shots, taken from
   vantage points, were all found this way.

A solve is accepted at a sub-pixel median reprojection error (0.22 to 0.48 px
here) and a gradient similarity of at least 0.3 between the retail art and a
render at the solved camera, which rejects a rotation-only fit to distant sky.
Solved cameras sit on clean values (a start's eye height, whole degrees) and
are snapped to them.

Where most of a shot is sky or effect, the features that remain decide the
fit. `dmgravitylab_6`'s nebula sky fills most of its frame and gave fits with
the right orientation at the wrong place (similarity 0.05 to 0.19); matched
only on the structure (the lattice tower and hex panel on the left, the
bridge and the walkway on the right), cube faces from 120 entities found it
at 0.21 px and similarity 0.98.

## The sets

`tools/assets/levelshots/poses.json` is the source of truth: the camera
(`x y z pitch yaw roll`, fovX 90), staging commands, the solve's quality and
whether the set ships.

| Set | Camera | Solve (px) | Staging | Remaining difference from retail |
| --- | --- | --- | --- | --- |
| biolabsa | `-4668 -1956 76.25 0 0 0` | 0.45 | none | none |
| biolabsb | `-386 -894 76.25 0 90 0` | 0.36 | none | none |
| feedingtowerb | `-1792 -2984 364.25 0 180 0` | 0.38 | none | none |
| feedingtowerc | `-63 -1032 340.25 0 180 0` | 0.37 | none | none |
| feedingtowerd | `4752 5096 -723.75 0 270 0` | 0.40 | none | none |
| girlfriendx | `8518 -6616 7684.25 0 90 0` | 0.32 | none | retail's wall lamps flare more |
| harvestera | `11984 -8288 -899.75 0 0 0` | 0.40 | none | none |
| harvesterb | `12608 -416 3580.25 0 0 0` | 0.37 | none | none |
| keeperfortress | `84 -160 -46.75 0 90 0` | 0.31 | none | none |
| lotaa | `2090.25 360.5 365.25 0 200 0` | 0.29 | none | retail shows the spirit-walk arrival overlay; a screen effect the tiles cannot continue, so the set shows the scene beneath it |
| lotab | `-447.5 791.094 341.583 0 270 0` | 0.46 | none | the canyon's sky is orange in play; retail's art shows it pale blue |
| lotad | `1440 1047.75 368.134 0 270 0` | 0.41 | none | none |
| salvage | `72 -7779.75 -627.75 0 359.933 0` | 0.43 | player moved away, `func_door_20` closed | `func_door_20` opens as the player spawns beside it; retail shows it shut |
| salvageboss | `324 -420 836.25 0 90 0` | 0.35 | none | none |
| shuttlea | `-75536 -2000 -955.75 0 90 0` | 0.31 | none | none |
| shuttleb | `23592 1344 23468.25 0 0 0` | 0.29 | none | the hanging creature at the right reads brighter |
| spherebrain | `-2368 -64 -83.75 0.217 90 0` | 0.41 | none | none |
| spindlea | `-9172 -3856 -30971.75 0 0 0` | 0.31 | none | none beyond the energy spill's moving particles |
| spindleb | `-8116 23712 -10715.75 0 180 0` | 0.35 | none | two red lamps on the left are lit |
| superportal | `5600 -1868 576.25 0 225 0` | 0.39 | none | none |
| dmescher | `5643.16 -1986.84 -1456.75 -31.109 187.578 86.061` | 0.31 | none | a wall-walk view, rolled 86 degrees |
| dmescher2 | `-1519.75 -1495.5 33.904 -34.324 65.197 0` | 0.37 | none | a glow at the top reads stronger |
| dmsphere | `363 268.25 849.25 -31.134 215.931 0` | 0.28 | none | none |
| dmroadhouse | `-16.91 3217.59 182.75 -12.445 320.254 0` | 0.41 | none | none |
| dmplanes_4 | `-61.113 529 -415.103 57.089 323.679 0` | 0.23 | none | none |
| dmtunnelrat_8 | `-206.379 -1162.35 120.134 -14.521 23.93 180` | 0.27 | none | none |
| dmshuttle1 | `-14323.334 26658.583 -11139.25 -52.93 229 0` | 0.48 | none | the Earth model turns with game time, so it shows a different face |
| dmshuttle2 | `-2697.151 -939.583 702.658 58.185 35.848 0` | 0.29 | none | the floor under the light shaft reads darker |
| dmwallwalk2 | `1018.5 -2822.25 -172.5 8.469 312 0` | 0.29 | none | a small orange wall lamp at the top right is lit |
| dmtopillogical_4 | `492.661 202.75 258.83 19 188.232 0` | 0.22 | deathmatch session, player moved behind the camera | none |
| dmsalvagewalk | `3195.136 6297.669 -203.406 -16.393 282.619 0` | 0.29 | none | none |
| dmgravitylab_6 | `-1184 790.584 475.75 12.76 207.722 0` | 0.21 | none | none |
| feedingtowera | `326.7 -41.8 68.3 -62.2 359.8 0` | 0.39 | a staged copy of roadhouse, frozen at 43.4 s ([scenes](#scenes)) | retail's haze in the lower left is greener |

Multiplayer maps are captured in a single-player session (`devmap` with
`si_gameType singleplayer`); retail's shots show no players. A map without an
`info_player_start` cannot run as single-player (`No info_player_start on
map`, every probe black): its set names a `gameType` in `poses.json`, which
`solve` and `capture` pass as `si_gameType`, and moves the listen server's
player out of the view (`dmtopillogical_4`).

### Held back

These keep their retail art (centre only, no tiles). A set is held back when
its camera cannot be recovered, or when an engine rendering difference, not
the scene or its timing, changes the picture.

| Set | Why |
| --- | --- |
| loading, roadhouse | Key art; the generic tiles in pak1 (and their copies for roadhouse) widen it. |

### Scenes

`feedingtowera`'s picture is not of feedingtowera. It is the end of
roadhouse: from the bar, the view looks up through the torn-off roof's frame
at the ship, as the ship's grab light swings onto Tommy. No level reaches that
moment with the camera free, so the set captures it in a staged copy of
roadhouse. Its `scene` entry in `poses.json` names the map to copy, entity key
edits, and a staging script (`tools/assets/levelshots/scene.py`):

- The copy, `levelshot_feedingtowera`, is written from the user's own retail
  pak into the slot's savepath: the `.map` with the edits applied, and the
  `.proc`, `.cm` and `.aas48` unchanged. No retail data is redistributed.
- The level's own script runs as usual. Prey compiles every map script at
  startup, and the copy keeps the worldspawn's `call map_roadhouse::main`.
  The staging function is added as one more `call` key.
- `rhEndLevel` becomes an `info_null`, so the level does not end.
- The staging function stands the player in the bar and starts
  `map_roadhouse::AbductionStart`. Standing there, he trips the ship's entry
  as the level does, and the grab lights later aim at him. The bar placement
  also matters for the ship: entities outside the player's PVS do not think.
  With the player elsewhere, the lights bound to the ship went dormant and
  kept the positions the ship's 1024-unit setup lift had given them, so the
  hull rendered unlit.
- At 43.4 s of game time the function sets `g_stopTime 1`. Frames at the
  capture settings are slow enough to step past the moment, and the rays
  sweep quickly: similarity to retail is 0.94 at 43.4 s and 0.73 half a
  second later. The set's `after` gates the levelshot on that time, once the
  world has stopped.

The camera was solved with the green rays masked out of the retail art. The
roof frame (near) and the ship (far) solve to the same camera independently,
which places the ship at its final height. A scan of game time at that camera
then found retail's moment. `capture` loads the scene and names the tiles
after the set.

## Making them again

```
set OPENPREY_RETAIL_BASE=C:\path\to\Prey\base
python tools/assets/levelshots/levelshots.py solve a <map> ...
python tools/assets/levelshots/levelshots.py capture a [<set> ...]
python tools/assets/levelshots/levelshots.py stage [<set> ...]
```

`solve` prints each camera as a `poses.json` entry. `capture` with no sets
captures every shipped set; up to four slots (`a` to `d`) run at once, each
with its own savepath and port. Captures land in `.tmp/levelshots/final/`
beside a retail comparison (`<set>_cmp.png`), and `stage` copies them into
`content/basepr/pak2`. It needs a staged `.install` built from this tree,
Python with OpenCV, NumPy and Pillow, and `unzip`.

Traps met:

- `r_shadowMapProgramReceivers` and other archived cvars persist in a slot's
  savepath; the capture pins every cvar it depends on, so an earlier A/B run
  cannot leak into a capture.
- `levelshotProbe` output names are tokenised: use letters, digits and `_`.
- Staging `.install` stops every client running from it, captures included:
  let captures finish before staging a new build.
