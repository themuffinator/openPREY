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

pak2 holds 25 of retail's 33 in-game loading screens and the roadhouse tiles:
254 files, 197 MB compressed.

## How the engine uses it

- **Loading art lookup.** Retail Prey's loading screen shows
  `guis/assets/loading/<map>.tga`, and its menus the separate pictures under
  `loading/thumbs/`. openPREY's `FindMapScreenshot` answers for the menus, so
  single-player levels loaded over the generic art and multiplayer levels over
  their 512 menu thumb. `Session_FindMapLoadingImage` (`Session.cpp`) now
  restores the retail step for the loading screen and the retained pause shot;
  a mapDef's `loadimage` still comes first.
- **Wide and tall windows.** The session composes the centre and its tiles
  into one picture of the window's shape (`Session_EnsureExpandedLoadingBackground`,
  `prey-ui-visual-design.md` section 12.1). Maps without tiles keep the 4:3
  retail art.
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
  Antialiasing comes from rendering each 4:3 source at 1.4 times the tile
  height (1912x1434) and area-averaging it down.
- A 2560x1440 hidden window. A hidden window cannot be larger than the desktop,
  and a source larger than the window is rendered in sub-frustum regions,
  which breaks screen-copy effects such as window glass and heat haze; the
  capture fails if the source was not rendered in one pass.
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

A solve is accepted at a sub-pixel median reprojection error (0.23 to 0.46 px
here) and a gradient similarity of at least 0.3 between the retail art and a
render at the solved camera, which rejects a rotation-only fit to distant sky.
Solved cameras sit on clean values (a start's eye height, whole degrees) and
are snapped to them.

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
| spindleb | `-8116 23712 -10715.75 0 180 0` | 0.35 | none | two red lamps on the left are lit |
| superportal | `5600 -1868 576.25 0 225 0` | 0.39 | none | none |
| dmescher | `5643.16 -1986.84 -1456.75 -31.109 187.578 86.061` | 0.31 | none | a wall-walk view, rolled 86 degrees |
| dmescher2 | `-1519.75 -1495.5 33.904 -34.324 65.197 0` | 0.37 | none | a glow at the top reads stronger |
| dmsphere | `363 268.25 849.25 -31.134 215.931 0` | 0.28 | none | none |
| dmroadhouse | `-16.91 3217.59 182.75 -12.445 320.254 0` | 0.41 | none | none |
| dmplanes_4 | `-61.113 529 -415.103 57.089 323.679 0` | 0.23 | none | none |
| dmtunnelrat_8 | `-206.379 -1162.35 120.134 -14.521 23.93 180` | 0.27 | none | none |

Multiplayer maps are captured in a single-player session (`devmap` with
`si_gameType singleplayer`); retail's shots show no players.

### Held back

These keep their retail art (centre only, no tiles). A set is held back when
an engine rendering difference, not the scene or its timing, changes the
picture; each can be captured again from `poses.json` once that is fixed.

| Set | Why |
| --- | --- |
| spindlea | Camera solved (0.31 px). The energy spill (`fx/starenergyspill.fx`) draws far brighter than retail at every moment and hides the four orange forcefield beams. |
| dmshuttle1 | Camera solved (0.48 px). The Earth window draws black, and the hexagonal glow panels draw brighter and coarser than retail. |
| dmshuttle2, dmwallwalk2 | Cameras solved (0.29 px). The hexagonal glow panels draw brighter and coarser than retail. |
| dmtopillogical_4, dmsalvagewalk | No solve: the same hexagonal panels dominate the shot and do not match. |
| dmgravitylab_6 | No solve: the star field on nearby geometry gives a consistent but wrong fit (similarity 0.05). |
| feedingtowera | No solve: the shot is dominated by the green light-ray effect. |
| loading, roadhouse | Key art; the generic tiles in pak1 (and their copies for roadhouse) widen it. |

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
