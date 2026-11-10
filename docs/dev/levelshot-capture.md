# Levelshot capture

Loading screens (`gfx/guis/loadscreens/<loadimage>`) are five 1024x1024 tiles plus a camera sidecar:
the 4:3 centre view stretched to a square, the `_left`/`_right`/`_top`/`_bottom` neighbours that the
expanded widescreen loading screen composes around it, a DXT1 `.dds` for each, and `<loadimage>.txt`
holding `x y z pitch yaw roll`. `tools/tests/levelshot_inventory.py` checks that every retail mapDef
`loadimage` has a complete, well-formed set.

This page covers the engine commands, how to drive them headlessly, and how the 24 sets that closed
GitHub issue #11 were matched to the retail loading screens.

## Commands

`levelshot [size]` captures the view the game last drew, with its field of view normalised to 4:3.
`levelshot <size> <x> <y> <z> <pitch> <yaw> <roll> [fovX]` captures an explicit camera instead
(fovX defaults to 90, the retail value for every loading screen). The player view is copied, so the
player's own body and view weapon stay suppressed and animated materials use that frame's time.

`r_levelshotSupersample` (1-4) renders each 4:3 source that many times the tile height and
area-averages it down; the shipped sets use 2, i.e. 2731x2048 sources for 1024 tiles. A source larger
than the window is rendered as a grid of off-axis sub-frustum regions with a 64-pixel guard band, so
screen-space passes see real neighbours at the seams. (The old viewport-offset tiling in
`R_ReadTiledPixels` only ever rendered its first tile into the scene render target.)

`levelshotProbe <requestFile>` (cheat) serves tools that search for or time a capture without moving
the player. The request file, relative to `fs_savepath`, holds one line per probe:

```
<output> <width> <height> <x> <y> <z> <pitch> <yaw> <roll> <fovX> [depth]
<output> <width> <height> current [depth]
levelshot <size> [<x> <y> <z> <pitch> <yaw> <roll> [fovX]]
```

Each probe writes `<output>.tga` and `<output>.pose` (`x y z pitch yaw roll fovX fovY width height time
depthWritten`); `depth` adds `<output>.depth`, float32 distances along the view axis, top row first,
-1 where nothing was drawn (the probe must fit the window). A `levelshot` line runs the five-tile
capture in the same frame. If the first line is `after <time>`, the whole request waits until the
view's time (the `.pose` time) reaches it, which lands a capture on an exact game time without the
requester racing the frame loop. The file is deleted once handled; that is the completion signal.

## Headless runs

- Launch hidden (`r_hiddenWindow 1`, `in_mouse 0`) with a per-run `fs_savepath`, and never inject
  input. `g_autoExecAfterMapLoad <cfg>` runs a staging script once the world is drawing; a poll
  loop in that script (`levelshotProbe lsq/req.txt; wait 1; exec <itself>`) serves requests.
- Put an empty `config.spec` in the savepath, or first-run machine-spec detection rewrites the
  config (MSAA, anisotropy).
- Pin presentation to retail: `r_ssao 0`, `g_simpleItems 0`, `r_bloom 0`, `r_hdrToneMap 0`. Personal
  settings leak in through a copied config, and `g_simpleItems 3` draws every MP pickup as a flat
  icon colour.
- Lights whose materials use `sound` (`lights/*_snd`) are dark with `s_noSound 1`. Run the sound
  system on OpenAL Soft's silent backend (`ALSOFT_DRIVERS=null`, `s_noSound 0`,
  `s_muteUnfocused 0`); `s_constantAmplitude 1` makes them deterministic.
- Single-player game time is deterministic from map load for a fixed boot sequence: sweep one run
  with probes, then capture a second run behind `after <best time>`. Keep `timescale` at or below 1
  before a gated capture; after a stretch at 8 the view clock no longer tracked the game clock that
  item spin runs on.
- Scripted scenes often hide the thing the retail shot shows, or show what it doesn't: the storage1
  intro hides the player's own pod, and the second visit folds the core-room bridge away until the
  player extends it. Read the level script and replay the relevant function with `script`.
- The console `script` command cannot carry quoted strings. Staging that needs them (for example
  `$light.setShader( "..." )`) goes in a function appended to a copy of the level script under the
  run's savepath, which overrides the pak copy; then `script "map_<name>::lsq_stage()"`.

### Multiplayer staging

- Spawn the matching gametype (`si_gameType CTF` for flags, `DeadZone` for Dead Zone pads and
  artifacts); `net_allowCheats 1`, `si_warmup 0`.
- Dead Zone artifacts only appear when a match goes live. A casual match needs two active players,
  so `addbot`, then `kick <client>` once it is live (`kickbots` queues its kicks with
  `CMD_EXEC_APPEND`, behind a self-re-executing poll loop that never drains). The local player joins
  through an archived `seta ui_autoJoin "1"`, then `noclip` and `setviewpos` move it out of frame.
  `si_countDown` must be 4-3600 and Dead Zone's `si_captureLimit` at least 1, or the rules fail
  validation and the match never counts down.
- Pickups spin and bob on game time (`idItem::UpdateModelTransform`: yaw = `(time & 4095)` /
  -4096 turns, height = `4 + 4cos((time + 1000) * 0.005 + entity offset)`). To match a retail
  angle, sweep a few turns with probes scored against the retail crop, then gate the capture on a
  later time that repeats both the spin phase (mod 4096 ms) and the bob phase (mod ~1257 ms).

## Recovering a retail camera

Every retail loading screen is a 90-degree 4:3 view stretched to a square. The camera was recovered by
matching the retail image against engine renders (RootSIFT features after CLAHE), turning the matched
render pixels into world points with probe depth, and solving PnP with RANSAC, iterating render,
match, solve until the pose converged; coarse starts came from map entities, geometry near
distinctive surfaces, or look-at shells around a landmark for exterior shots.

## The issue #11 sets

All 24 have a retail original in the Steam paks (storage1_second, not one of them, was redone the same way). Each set was recaptured at the recovered retail camera
with openQ4's shipped maps and assets; where the retail shot was taken in a pre-release build, the
shipped content wins and the difference is noted.

| Set | Map / mode | Staging | Remaining difference from retail |
| --- | --- | --- | --- |
| convoy2b | `game/convoy2b` | time chosen for sky scroll and fires | fire and smoke particles differ |
| defstation | `game/building_b` | `s_constantAmplitude 1`, time chosen for the flicker lights | retail has far stronger red light near the camera than the shipped lights give |
| medlabs | `game/medlabs` | `s_constantAmplitude 1` | retail shows a large hanging machine the shipped map does not have |
| storage1_first | `game/storage1 first` | drop-pod intro frozen at 16.1 s as the burning pod falls past; the player's own pod (`envPodInFlight`, which the intro script hides) shown, since retail frames it from behind and above where `light_8124` lights it | retail is hazier; smoke and fire particles differ |
| storage1_second | `game/storage1 second` | the core-room bridge and catwalks extended (`map_storage1::shaft_bridge()`), as retail shows them | an earlier openQ4 capture showed the Dark Matter Gun's energy ball; retail has none |
| storage2 | `game/storage2` | level-start alarm lighting, hidden monitor `func_static_13207` shown | retail's floor shows the grid of the ceiling spotlights, which the shipped map only turns on after the light changeover |
| tram1b | `game/tram1b` | none | none |
| q4ctf1 | CTF | flags | retail has a rock ceiling and fan the shipped map does not |
| q4ctf2, q4ctf3, q4ctf4, q4ctf6, q4ctf8 | CTF | flags | minor light-panel differences |
| q4ctf5 | CTF | flags | the 1.1 patch sky cube map is dimmer than the retail starfield |
| q4ctf7 | CTF | flags | a ceiling grate is lit in openQ4 |
| q4dm4, q4dm5, q4dm6 | DM | none | none |
| q4dm8 | DM | none | the 1.1 patch sky cube map is dimmer than the retail starfield |
| q4dz1, q4dz4 | DeadZone | none | none |
| q4dz2 | DeadZone | live match, artifact spin timed to the retail angle | glow particles |
| q4dz3 | DeadZone | live match, artifact spin and acceleration pad pulse timed | none |
| q4xctf6 | CTF | flags | none (with `r_ssao 1` the cryo liquid turns magenta; SSAO must stay off) |
| q4xdm13 | DM | rocket launcher spin timed to the retail angle | none |
