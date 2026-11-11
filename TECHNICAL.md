# openPREY Technical Reference

This reference is for advanced players, server operators, modders and developers. It covers compatibility status, the install layout, asset checks, useful console settings, file paths, crash reports, mod packaging, the game code and version numbers.

For installation and a feature overview, see the [README](README.md). For building from source, see [BUILDING.md](BUILDING.md).

---

## Table of Contents

- [Compatibility](#compatibility)
- [Install Layout](#install-layout)
- [Asset Validation](#asset-validation)
- [Console Settings](#console-settings)
- [File System Paths](#file-system-paths)
- [Crash Reports](#crash-reports)
- [Mods](#mods)
- [Game Code](#game-code)
- [Version Numbers](#version-numbers)

---

<a id="prey-compatibility-status"></a>

## Compatibility

openPREY runs the official PREY (2006) game data from your own install with its own engine and its own build of the PREY SDK game code. Compatibility here means compatibility with the official assets, not binary interchangeability with the proprietary retail DLLs. openPREY has no release yet; the April 2026 nightlies on the Releases page predate the move onto the current openQ4 engine.

### Landed

- **Project rebrand** — Meson project metadata, staged binaries, VS Code launch settings and documentation use openPREY naming throughout.
- **PREY install discovery** — `fs_basepath` auto-detection checks the PREY registry keys, App Paths and uninstall entries and the known CD-era install roots before any Steam or GOG library, so disc installs need neither. See [File System Paths](#file-system-paths).
- **Unified game module loader** — the engine builds and stages one `game_<arch>` module under `basepr/` for both single-player and multiplayer.
- **In-tree game library** — the PREY SDK-derived game sources live in `src/game/`, `src/Prey/` and `src/preyengine/` and build into that one module.
- **Official PK4 layout validation** — startup rejects missing or modified required base packs while `fs_validateOfficialPaks 1` is set. See [Asset Validation](#asset-validation).
- **Windows and Linux x64 CI** — active CI (`openprey-validation.yml`) builds and stages the engine, dedicated server, OpenGL and Vulkan renderers and the unified game module on Windows x64 and Linux x64. The macOS and ARM64 build files are inherited from openQ4, but nothing builds them and they aren't supported.
- **Precomputed light-grid irradiance** — portal-area light grids can be baked, loaded, visualized and applied as an indirect-diffuse pass. See [Light Grids](#light-grids).

### In Progress

- **Stock-asset SP/MP smoke validation** — the default staged launch flow is still being verified across single-player and multiplayer startup cases.
- **PREY gameplay bring-up** — the in-tree game library is integrated; retail runtime verification continues during the migration.
- **Particle and FX compatibility** — Doom 3 / PREY-era declarations and runtime paths are restored, with retail parity checks still pending.
- **Cross-host runtime validation** — Windows remains the deepest runtime-validation path; Linux map validation is still being extended.

### Not Yet Claimed

- **Full campaign completion** — the project does not yet claim end-to-end single-player completion against stock assets.
- **Multiplayer parity** — multiplayer compatibility remains under active validation.

The [rebase status ledger](docs/dev/prey-rebase/status-ledger.md) records what has been ported, how each piece was tested and the explicit deferrals; [docs/dev/release-completion.md](docs/dev/release-completion.md) collects work for the first release's changelog. Please report anything that breaks on the [issue tracker](https://github.com/themuffinator/openPREY/issues).

---

<a id="game-directory-structure"></a>

## Install Layout

Local builds stage this layout into `.install/`, the runtime package root.

```
.install/
├── openPREY-client_x64      # The game (.exe on Windows)
├── openPREY-ded_x64         # Dedicated server (.exe on Windows)
├── renderer-gl_x64          # OpenGL renderer module, the default (.dll / .so)
├── renderer-vk_x64          # Vulkan renderer module, opt-in with r_renderApi vulkan (.dll / .so)
├── OpenAL32.dll             # (Windows) OpenAL Soft runtime; see BUILDING.md
├── openPREY-steamdeck       # (Linux) Steam Deck launcher
├── share/                   # (Linux) desktop entries and icons
└── basepr/                  # The single openPREY game directory
    ├── game_x64             # Unified game module (.dll / .so)
    ├── pak0.pk4             # openPREY core runtime content: GLSL programs, fonts, strings, menus, scripts
    ├── pak1.pk4             # openPREY interface artwork (clients only)
    └── mod.json             # Game-directory manifest
```

- Single-player and multiplayer load the same unified `game_<arch>` module from `basepr/`. The retail module names `gamex64` / `gamex86` are still accepted as loader aliases during the migration.
- Your retail game data stays in the PREY install's `base/` directory; openPREY reads it from there.
- When updating, replace the whole staged tree. The engine, renderer modules and game module must come from the same build.

### Dependencies

| Library | Version | Purpose |
|---|---|---|
| [SDL3](https://www.libsdl.org/) | 3.4.18 | Cross-platform window, input, and display management |
| [GLEW](https://github.com/nigels-com/glew) | 2.3.4 | OpenGL extension loading |
| [OpenAL Soft](https://openal-soft.org/) | system library on Linux; prebuilt runtime on Windows | 3D audio rendering |
| [libogg](https://xiph.org/ogg/) | 1.3.6 | Ogg bitstream support |
| [libvorbis](https://xiph.org/vorbis/) | 1.3.7 | Ogg Vorbis audio decoding and file access |
| [stb_vorbis](https://github.com/nothings/stb) | vendored | Ogg Vorbis decoding |
| [glslang](https://github.com/KhronosGroup/glslang) | 16.6.0 | GLSL-to-SPIR-V compilation for the Vulkan renderer |
| [RmlUi](https://github.com/mikke89/RmlUi) | 6.3 | Layout library behind the retained interface |
| [JsonCpp](https://github.com/open-source-parsers/jsoncpp) | 1.9.8 | JSON parsing for the retained interface |
| [libtess2](https://github.com/memononen/libtess2) | `8dbd648` | Polygon tessellation for the retained interface's vector shapes |
| [OpenXR SDK](https://github.com/KhronosGroup/OpenXR-SDK) | 1.1.65 | OpenXR loader for the experimental VR mode |

Dependencies come from Meson subprojects and wraps (`subprojects/`) or vendored sources (`src/external/`); their licence notices live in [LICENSES/](LICENSES/). Windows needs nothing installed beyond the build tools, apart from the OpenAL runtime described in [BUILDING.md](BUILDING.md#windows-openal-runtime). Linux needs the system development packages listed there.

---

## Asset Validation

openPREY checks at startup that your PREY installation has the required official base packs, unmodified.

1. It scans the detected `base/` pack set.
2. It chooses the required layout to validate against:
   - classic retail naming (`pak000.pk4` ... `pak004.pk4`), or
   - consolidated retail naming (`pak_data.pk4`, `pak_sound.pk4`, `pak_en_v.pk4`, `pak_en_t.pk4`).
3. It strictly checks the known consolidated-layout checksums. Classic-layout packs remain presence-only until independently verified CD-era checksums are recorded.

`fs_validateOfficialPaks 1` (the default, set at startup) enables these checks. The [official PK4 checksum reference](docs/dev/prey-rebase/official-pk4-checksums.md) lists the expected files.

openPREY also checks its own `basepr/pak0.pk4` and `pak1.pk4` against checksums built into the executable, and refuses to start if one is missing or modified. A dedicated server needs only `pak0.pk4`; `pak1.pk4` is client-only. A pack that passed is remembered in `generated/packs/verified.txt` under `fs_cachepath` and hashed again only after the file changes. `+set fs_cacheVerifiedPaks 0` hashes every pack at every launch. See [Content Pack Distribution](docs/dev/content-pack-distribution.md).

---

<a id="advanced-configuration"></a>

## Console Settings

Some of these are also in the stock PREY **Options** menus; the rest are console or config-file settings. The [player guides](README.md#player-guides) explain each area in more depth. Settings marked as inherited come from the openQ4 engine and have not yet been checked against PREY's content.

### Display

- `r_screen -1` — use the current display (default); `r_screen 0..N` picks a monitor. `listDisplays` lists them.
- `r_fullscreen 0|1` — windowed or fullscreen. Agent and CI validation runs always force `+set r_fullscreen 0`.
- `r_fullscreenDesktop 1` — desktop fullscreen (default); `0` uses exclusive fullscreen at `r_mode` / `r_customWidth` / `r_customHeight`. `r_mode -2` (the default) requests the native desktop resolution. `listDisplayModes [displayIndex]` lists the available exclusive modes.
- `r_borderless 1` — borderless window while `r_fullscreen 0`.
- `r_windowWidth` / `r_windowHeight` — window size when windowed. `win_xpos` / `win_ypos` hold the window position and update when you move the window.
- There is no aspect-ratio setting: the horizontal FOV is derived from the render size, keeping PREY's 4:3 vertical view.

See [Display Settings](docs/user/display-settings.md).

### Resolution Scaling

- `r_screenFraction 10..200` — render scale in percent (default `100`). Below `100` renders fewer pixels; above `100` supersamples.
- `r_resolutionScaleMode` — `0` legacy cropped viewport, `1` bilinear upscale (default), `2` high-quality upscale with sharpening, `3` nearest-neighbour upscale.
- `r_resolutionScaleSharpness 0.0..1.5` — sharpening strength for mode `2` (default `0.4`).

### Renderer

- `r_renderApi best|gl|vulkan|gl-module|gles` selects the renderer and takes effect on engine restart, not `vid_restart`. `best` (the default) picks OpenGL on desktop, the only renderer that runs PREY's own ARB interaction stages. Vulkan is opt-in and not at PREY parity yet; if it can't start, openPREY falls back to OpenGL and `r_actualRenderApi` reports `gl`.
- `r_renderDevice auto|<id>` selects the GPU for Vulkan; `rendererDevices` lists the stable device IDs.

See [Rendering Backend and Device](docs/user/display-settings.md#rendering-backend-and-device) and [Performance Presets](docs/user/display-settings.md#performance-presets).

### Post-Processing and Materials

Inherited from openQ4; all off by default.

- `r_bloom 0|1` — bloom.
- `r_hdrToneMap 0|1` — HDR filmic tone mapping and colour correction.
- `r_ssao 0|1` — screen-space ambient occlusion.
- `r_crt 0|1` — CRT monitor filter. `r_crtChromatic` adds a colour-channel offset (default `0`).
- `r_enhancedMaterials 0|1` — enhanced GLSL interaction shading for existing materials. Tune with `r_enhancedMaterialNormalScale`, `r_enhancedMaterialSpecularBoost` and `r_enhancedMaterialFresnel`.

`r_softParticles 0|1` (default `1`) fades eligible particles where they meet opaque geometry; `r_softParticleFadeDistance` sets the fade distance in world units (default `64`).

### Shadows

- `r_useShadowMap 0|1` — shadow maps instead of classic stencil shadows. The `enhanced`, `quality`, `ultra` and `maximum` performance presets turn it on and shadow-map point lights too, because PREY lights its levels almost entirely with point lights.
- `r_shadowMapFilterMode 0|1|2` — projected-light filtering: fixed PCF, rotated Poisson, or PCSS-lite (default), with `r_shadowMapFilterRadius` (default `2.0`) as its radius.
- `r_shadowMapCSM 0|1` — cascaded shadow maps for projected lights.
- `r_shadowMapHashedAlpha 0|1` — shadows from cutout surfaces such as grates and fences (default `1`).
- `r_shadowMapTranslucentMoments 0|1` — experimental shadows from translucent surfaces.
- `r_stencilTranslucentShadows 0|1` — let translucent materials cast and receive classic stencil shadows (default `1`). Reload the map (or run `regenerateWorld`) after changing it.

See [Shadow Mapping](docs/user/shadow-mapping.md) for presets and troubleshooting.

### Light Grids

openPREY supports idTech 4-style precomputed irradiance volumes for indirect diffuse lighting. Runtime data is stored in two parts:

- `maps/<map>.lightgrid` — probe layout, atlas metadata, and per-area light-grid parameters
- `env/maps/<map>/area*_lightgrid_amb.tga` — baked irradiance atlas images, typically one per populated portal area

See the [Light Grid Guide](docs/user/light-grids.md) for workflows and troubleshooting.

#### Baking

Run baking from a staged `.install/` launch against a valid PREY asset install and always force windowed mode:

```powershell
.\openPREY-client_x64.exe +set fs_game basepr +set fs_savepath ..\.home +set r_fullscreen 0 +bakeLightGrids game/roadhouse force
```

Command form:

```text
bakeLightGrids [all | all-mp | <map> ...] [force] [-quit] [limit<num>] [bounce<num>] [size<num>] [blends<num>] [samples<num>] [separateAreas] [grid ( x y z )]
```

Important options:

- `all` — bake every discovered map
- `all-mp` — bake only maps whose names start with `mp/`, a Quake 4 convention. PREY's multiplayer maps live under `game/dm*`, so `all-mp` finds none of them yet and `all` bakes them as single-player loads; name them explicitly
- `force` — remove existing `.lightgrid` and atlas outputs before rebaking
- `-quit` — exit automatically after the bake batch completes
- `limit<num>` — cap the number of generated probes for a bake pass
- `bounce<num>` — number of diffuse bounces to integrate
- `size<num>` — per-probe capture resolution
- `blends<num>` — atlas blend samples per probe
- `samples<num>` — supersample count per capture
- `separateAreas` — regenerate per-area layouts during baking to reduce peak memory use
- `grid ( x y z )` — override probe spacing in world units

#### Runtime and Debugging

- `r_useLightGrid 1` — enable the indirect-diffuse light-grid pass when grid data is present (default `1`)
- `r_showLightGrid 0..3` — visualize probe placement by area
- `r_forceAmbient <value>` — lift the final scene toward a minimum brightness floor
- `r_lightGridBakeWorkers` — control CPU worker count during baking
- `r_lightGridBakeAsyncReadback 0|1` — enable async GPU readback when supported
- `r_lightGridBakeMemoryMB` — cap transient bake memory usage
- `r_lightGridBakeReadbackSlots` — control async readback buffer count

Use `r_showLightGrid 1` to inspect only the current portal area, `2` to draw valid probes in all areas, and `3` to include invalid probe locations as well.

### Experimental Previews

Inherited from openQ4 and not yet tried on PREY's maps, portals or spirit walk. Each can be turned on independently:

- `r_temporalAA 0|1|2` — temporal anti-aliasing and upscaling. The default `2` (automatic) switches it on only while the 3D scene renders below native resolution with a smooth scale mode, or with dynamic resolution.
- `r_rendererDynamicResolution 0|1` — adjust resolution automatically to hold frame time, within `r_dynamicResolutionMinScale` and `r_dynamicResolutionMaxScale` (default off).
- `r_pbrMaterials 0|1` — physically based lighting for materials authored with PBR data (default `1`); stock PREY materials are never PBR and keep their classic look.
- `r_rendererReflectionProbes 0|1` — authored reflection probes (default off).
- `r_rendererClusteredDecals 0|1` — clustered decals on OpenGL (default off).
- `r_rendererFroxelVolumetrics 0|1` — volumetric lighting (default off).
- `r_rendererSSR 0|1` — screen-space reflections (default off).
- `r_rendererSSGI 0|1` — screen-space indirect light (default off).
- `r_gpuSkinning 0|1` — animate eligible models on the GPU (default off).
- `com_levelLoadModernization 0|1` — local level-load caches (default off).

`r_rendererModernQuality 0` switches off the modern material and lighting previews together (default `1`). See [Temporal AA and Dynamic Resolution](docs/user/temporal-presentation.md), [Advanced Screen-Space Lighting](docs/user/advanced-screen-space-lighting.md), [PBR Materials](docs/user/pbr-materials.md) and [Level-Load Cache](docs/user/level-load-cache.md).

### Shader Troubleshooting

- `r_shaderReport 1` — print a shader summary after startup and `vid_restart`; `2` also warns when an invalid shader program is used.
- `reportShaderPrograms` — print the current shader program status.
- `r_interactionColorMode` — interaction shader colour mode (`0` auto, `1` packed, `2` vector). Leave on `0` unless asked to test.

### Controllers

Controller input works in SDL3 builds on Windows and Linux. The stock PREY menu has no controller page, so set these from the console or a config file.

- `in_joystick` — enable or disable gamepad input (default `1`).
- `in_joystickDeadZone` — analog stick dead zone.
- `in_joystickLookSensitivity` — look speed.
- `in_joystickLookCurve` / `in_joystickMoveCurve` — look and movement response curves.
- `in_joystickInvertLook` — invert look pitch.
- `in_joystickSouthpaw` — swap the movement and look sticks.
- `in_joystickTriggerThreshold` — trigger sensitivity.
- `in_joystickRumble` / `in_joystickRumbleScale` — enable and scale rumble.
- `com_platformProfile` — startup profile (`default`, `steamdeck` or `couch`).

Controllers can be connected or disconnected at any time and every button can be bound; PREY's `default.cfg` has no controller binds, so bind the buttons you want. `JOY7` (Start) and `JOY8` (Back) both open the in-game menu. See [Input Settings](docs/user/input-settings.md) and [Steam Deck](docs/user/steam-deck.md).

---

<a id="file-system-and-validation"></a>

## File System Paths

openPREY looks for your PREY installation in this order:

1. A valid `fs_basepath` set with a cvar or on the command line
2. The current working directory
3. Windows registry install entries: the Human Head Studios, 2K Games and 3D Realms keys, the `prey.exe` App Paths entry and uninstall metadata
4. Known CD-era install roots: `Human Head Studios/Prey`, `2K Games/Prey`, `3D Realms/Prey` and `Prey` under Program Files, and `Games/Prey` on the system drive; `~/Games/Prey` on Linux
5. Steam library and GOG install locations, checked last so disc installs never depend on them

The registry and known-root candidates are written to the log, which helps when an install isn't found.

- `fs_basepath` — PREY installation directory, the folder that contains `base/` (detected automatically).
- `fs_homepath` — writable user directory.
- `fs_savepath` — saves, configuration and logs (defaults to `fs_homepath`): `%LOCALAPPDATA%\openPREY` on Windows, `$XDG_DATA_HOME/openprey` or `~/.local/share/openprey` on Linux. Each game directory keeps its own folder here, so openPREY uses `basepr`.
- `fs_cachepath` — regenerable `generated/` caches (defaults to `fs_savepath`). Safe to delete.
- `fs_game` — active game directory (`basepr`, or a mod).
- `fs_cdpath` — extra read-only search root, set at startup only; used for local `.install/` overlays, so launch from `.install/` when testing.

If your PREY installation is not found automatically, launch with:

```
openPREY-client_x64 +set fs_basepath "C:\path\to\Prey" +set r_fullscreen 0
```

Point it at the folder that contains `base/`, not at `base/` itself.

---

## Crash Reports

On Windows, a crash writes `openprey_crash_*.log` and `openprey_crash_*.dmp` files to a `crashes/` folder beside the executable. Please attach both files when [reporting a crash](https://github.com/themuffinator/openPREY/issues). On Linux, a fatal signal prints the signal and the last renderer and game-module startup phases to the terminal and appends the same line to `logs/fatal.txt` under `fs_savepath/basepr/`. macOS isn't supported; if you build it anyway, follow the [macOS support-data guide](docs/user/macos-support-data.md).

<a id="debugging-and-local-validation"></a>

### Logs and Local Validation

openPREY writes no log file unless you ask for one. The recommended local validation loop:

1. Launch from `.install/` in windowed mode:
   ```powershell
   .\openPREY-client_x64.exe +set fs_game basepr +set fs_savepath ..\.home +set logFile 2 +set logFileName logs/openprey.log +set r_fullscreen 0
   ```
2. Inspect `.home\basepr\logs\openprey.log` after each run (logs go under the game directory in `fs_savepath`).
3. Fix warnings and errors in engine/game/parser/loader code before resorting to content-side workarounds.

**Useful log cvars:** `s_logSpeech 1` prints each speech start (`SOUND_SPEECH`). `s_logSubtitles 1` prints each change to the PREY sound-shader caption queue (`SOUND_SUBTITLE`). Set `s_muteUnfocused 0` for unattended runs: an unfocused window otherwise plays no sound world, which also clears captions.

On Windows, `tools/build/meson_setup.ps1 compile -C builddir` runs `meson setup` itself (debug, `--wrap-mode=forcefallback`) when the build directory is missing or invalid. See [BUILDING.md](BUILDING.md) for the build workflow.

---

## Mods

Every runnable mod needs a `mod.json` file in its root directory. This includes `basepr/` itself, mods picked from the Mods menu, and mods a multiplayer server switches to. Mod directories are found under `fs_cdpath`, `fs_basepath` and `fs_savepath`.

The manifest is a flat JSON object with these required string fields:

- `name`
- `version`
- `releaseDate`
- `website`
- `author`
- `requiredopenPREYVersion` — the oldest openPREY version the mod works with, as `major.minor.patch`. The inherited `requiredopenQ4Version` key is still read when `requiredopenPREYVersion` is absent.

Mods without a valid manifest, or that need a newer openPREY than the one running, are skipped with a warning and hidden from the Mods menu.

Example:

```json
{
  "name": "My Mod",
  "version": "1.0.0",
  "releaseDate": "2026-10-01",
  "website": "https://example.com",
  "author": "Your Name",
  "requiredopenPREYVersion": "0.0.1"
}
```

Game modules are optional. openPREY first looks for `game_<arch>` in the mod's directory beside the executable and otherwise uses the one in `basepr/`, so a content-only mod needs just its `mod.json` and content files. Game modules are never loaded from PK4s or from `fs_savepath`.

A mod built on the retail base (`fs_game_base` other than `basepr`) still gets openPREY's runtime content: the filesystem searches `basepr/` between the mod and `base/`, so openPREY's shaders, GUIs and fonts remain available.

When a mod ships a declaration file with the same name as one beneath it, openPREY reads the mod's copy first and then the copies below it. The mod's definitions win, and the base file's other definitions are still found. Set `decl_layerModFiles 0` at startup to have a mod's file hide the base file entirely, as in the original game.

---

<a id="sdk-and-game-library"></a>

## Game Code

openPREY's game code is derived from the PREY Software Development Kit and lives in this repository under [`src/game/`](src/game/), [`src/Prey/`](src/Prey/) and [`src/preyengine/`](src/preyengine/). Meson compiles those trees in place against the engine headers in the rest of `src/`. The former `OpenPrey-game` companion repository is historical; its history was merged in with the import (see [game source provenance](docs/dev/game-source-provenance.md)).

The game code remains under the original Human Head Studios SDK EULA (`LICENSES/PREY-SDK-EULA.rtf`), which permits non-commercial modification for use with a legitimate copy of PREY but prohibits commercial exploitation and standalone redistribution of the SDK-derived code. The engine is GPLv3. [LICENSING.md](LICENSING.md) explains the separate terms.

Retail map-script compatibility is audited against the retail 32-bit game module in [`docs/dev/retail-script-parity.md`](docs/dev/retail-script-parity.md). It covers the event surface, the 64-bit callback ABI check, the script VM conformance test (`tools/tests/script_vm_conformance.py`), retail quirks kept on purpose, and the remaining known divergences.

### Game Library Workflow

- Edit the game library in place under `src/game/`, `src/Prey/` and `src/preyengine/`.
- Keep engine code out of the game trees and game code out of the engine directories; the two sides carry different licences.
- Stage targets: `builddir/basepr/` and `.install/basepr/`.

### Script VM on 64-bit

Script stack slots are pointer-sized on 64-bit, and a vector is pushed as `E_EVENT_SIZEOF_VEC` (16 bytes). A vector stack variable reserves exactly one vector slot. Its `_x`, `_y` and `_z` defs alias that slot at +0, +4 and +8 and do not reserve slots of their own. Before this was fixed, the three component defs each reserved a pointer-sized float slot, 24 bytes in all. Every parameter after a vector parameter was then read 8 bytes past where the caller pushed it. Two retail scripts broke this way:

- In `game/roadhouse`, `DistanceToXY( vector, vector )` measured the player against the wrong point, so Enisi never saw the player arrive and repeated his "come back" callbacks.
- In `game/feedingtowera`, `SlabNPCGetOffsetOrigin( float, vector, float, float )` placed the slab victims off their slabs.

The compiler now fails a function whose parameter frame differs from what its callers push. The script checksum now includes each function's frame sizes, so a save written with the old frames is not resumed with misaligned locals. Such a save takes the level-restart path with the player's persistent data.

---

<a id="versioning"></a>

## Version Numbers

Release builds report a plain version such as `X.Y.Z`. Development and pre-release builds add a track and the source commit, for example `X.Y.Z-dev+gabcdef12` or `X.Y.Z-nightly.20260330.1+gabcdef12`; a build with uncommitted changes also adds `dirty`. Type `si_version` in the console to see the running build's version, and include it in bug reports.

The version starts from the base version in `meson.build` (currently `0.0.1`) and appends the build track set by the `version_track` Meson option:

- `stable` — release builds, e.g. `X.Y.Z`
- `dev` — default local builds, e.g. `X.Y.Z-dev+gabcdef12`
- `nightly` / `beta` / `rc` — pre-release labels, with an optional `version_iteration`

The `meson.build` version is a floor. `tools/build/openq4_version.py` raises it to the highest `vX.Y.Z` tag in the local repository, and `-Dversion_base_override` pins it exactly. openPREY's GitHub repository has no such tags yet. A checkout that has fetched tags from the `openq4-upstream` remote picks up openQ4's release tags, though, and reports an openQ4 version such as `0.13.2-dev`. Fetch upstream with `--no-tags`, or delete those local tags, to avoid that.

---

[← Back to README](README.md)
