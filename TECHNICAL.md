# openPREY Technical Reference

This document covers technical details for advanced users and developers: compatibility status, file layout, configuration cvars, asset validation, build dependencies, versioning, and the SDK/game library structure.

For installation and a feature overview, see the [README](README.md). For building from source, see [BUILDING.md](BUILDING.md).

---

## Table of Contents

- [PREY Compatibility Status](#prey-compatibility-status)
- [Game Directory Structure](#game-directory-structure)
- [Asset Validation](#asset-validation)
- [Advanced Configuration](#advanced-configuration)
- [Light Grids](#light-grids)
- [SDK and Game Library](#sdk-and-game-library)
- [Dependencies](#dependencies)
- [Versioning](#versioning)

---

## PREY Compatibility Status

This status reflects compatibility with the official PREY (2006) assets, not binary interchangeability with the proprietary retail DLLs. openPREY has no release yet; the April 2026 nightlies on the Releases page predate the move onto the current openQ4 engine.

### Landed

- ✅ **Project Rebrand Completed** — Meson project metadata, staged binaries, VS Code launch settings, and documentation use openPREY naming throughout
- ✅ **PREY Install Discovery** — `fs_basepath` auto-detection checks the PREY registry keys, App Paths and uninstall entries and the known CD-era install roots before any Steam or GOG library, so disc installs need neither
- ✅ **Unified Game Module Loader** — Engine builds and stages a unified `game_<arch>` module under `basepr/` for both SP and MP paths
- ✅ **In-tree Game Library** — The PREY SDK-derived game sources live in `src/game/`, `src/Prey/` and `src/preyengine/` and build into one unified module
- ✅ **Official PK4 Layout Validation** — Engine startup rejects missing or modified required base-pack layouts when `fs_validateOfficialPaks 1` is enabled
- ✅ **Windows and Linux x64 CI** — Active CI (`openprey-validation.yml`) builds and stages the engine, dedicated server, OpenGL and Vulkan renderers and the unified game module on Windows x64 and Linux x64. The macOS and ARM64 build files are inherited from openQ4 but nothing builds them and they aren't supported
- ✅ **Precomputed Light-Grid Irradiance** — Portal-area light grids can be loaded, baked, visualized, and applied as an indirect-diffuse pass in the renderer

### In Progress

- ❌ **Stock-asset SP/MP Smoke Validation** — Default staged launch flow is still being verified across single-player and multiplayer startup cases
- ❌ **PREY Gameplay Bring-up** — The in-tree game library is integrated; retail runtime verification continues during the migration
- ❌ **Particle and FX Compatibility** — Doom 3 / PREY-era declarations and runtime paths are restored, with retail parity checks still pending
- ❌ **Cross-host Runtime Validation** — Windows remains the deepest runtime-validation path; Linux map validation is still being extended

### Not Yet Claimed

- **Full Campaign Completion** — The project does not yet claim end-to-end single-player completion against stock assets
- **Multiplayer Parity** — Multiplayer compatibility remains under active validation

The [rebase status ledger](docs/dev/prey-rebase/status-ledger.md) records what has been ported, how each piece was tested and the explicit deferrals; [docs/dev/release-completion.md](docs/dev/release-completion.md) collects work for the first release's changelog.

---

## Game Directory Structure

```
.install/
├── openPREY-client_x64      # Main executable (.exe on Windows)
├── openPREY-ded_x64         # Dedicated server (.exe on Windows)
├── renderer-gl_x64          # OpenGL renderer module, the default (.dll / .so)
├── renderer-vk_x64          # Vulkan renderer module, opt-in with r_renderApi vulkan (.dll / .so)
├── OpenAL32.dll             # (Windows) OpenAL Soft runtime; see BUILDING.md
├── openPREY-steamdeck       # (Linux) Steam Deck launcher
├── share/                   # (Linux) desktop entries and icons
└── basepr/
    ├── game_x64             # Unified game module (.dll / .so)
    ├── pak0.pk4             # openPREY text, script, GUI and config content
    ├── pak1.pk4             # openPREY binary assets
    └── mod.json
```

- **Single-player**: loads `game_<arch>` from `basepr/`
- **Multiplayer**: loads the same unified `game_<arch>` module
- **Legacy compatibility**: `gamex86` / `gamex64` aliases are still accepted during migration

---

## Asset Validation

openPREY automatically validates your PREY installation at startup to confirm the required official base packs are present and unmodified.

**How it works:**

1. Engine scans the detected `base/` pack set
2. Chooses the required layout to validate against:
   - Classic retail naming (`pak000.pk4` ... `pak004.pk4`)
   - Consolidated retail naming (`pak_data.pk4`, `pak_sound.pk4`, `pak_en_v.pk4`, `pak_en_t.pk4`)
3. Strictly checks known consolidated-layout checksums; classic-layout packs remain
   presence-only until independently verified CD-era checksums are recorded

**Configuration:**

- `fs_validateOfficialPaks 1` (default) — enable asset validation
- See [docs/dev/prey-rebase/official-pk4-checksums.md](docs/dev/prey-rebase/official-pk4-checksums.md) for the full checksum reference

---

## Advanced Configuration

### Display and Graphics

#### Multi-Monitor Support

- `r_screen -1` — auto-detect current display (default)
- `r_screen 0..N` — select a specific monitor
- `listDisplays` — list available monitor indices in the console
- `listDisplayModes [displayIndex]` — list available exclusive fullscreen modes for a display

#### Display Modes

- `r_fullscreen 0|1` — windowed vs fullscreen
- `r_fullscreenDesktop 1` — desktop-native fullscreen (default, recommended)
- `r_fullscreenDesktop 0` — exclusive fullscreen (uses `r_mode`/`r_custom*`)
- `r_mode -2` — request native desktop resolution for fullscreen mode selection
- `r_borderless 1` — borderless window when `r_fullscreen 0`

#### Windowed Sizing

- `r_windowWidth` / `r_windowHeight` — window size when running windowed
- `win_xpos` / `win_ypos` — window position (updated automatically when you move the window)
- Agent and CI validation runs should always force `+set r_fullscreen 0`

See [docs/user/display-settings.md](docs/user/display-settings.md) for the full display reference.

### File System and Validation

#### Path Variables

- `fs_basepath` — detected PREY install root (auto-discovered)
- `fs_homepath` — writable user path
- `fs_savepath` — save/config/log path (defaults to `fs_homepath`): `%LOCALAPPDATA%\openPREY` on Windows, `$XDG_DATA_HOME/openprey` or `~/.local/share/openprey` on Linux
- `fs_game` — active game directory (`basepr`)
- `fs_cdpath` — extra read-only search root, set at startup only; used for local `.install/` overlays, so launch from `.install/` when testing

#### Path Discovery Order

1. Valid `fs_basepath` override if set via cvar or command line
2. Current working directory
3. Windows registry install entries (Human Head Studios, 2K Games and 3D Realms keys, the `prey.exe` App Paths entry, uninstall metadata)
4. Known CD-era install roots: `Human Head Studios/Prey`, `2K Games/Prey`, `3D Realms/Prey` and `Prey` under Program Files, and `Games/Prey` on the system drive; `~/Games/Prey` on Linux
5. Steam library and GOG install locations, checked last so disc installs never depend on them

#### Manual Path Configuration

If your PREY installation is not auto-detected, launch with:

```
openPREY-client_x64 +set fs_basepath "C:\path\to\Prey"
```

Point it at the folder that contains `base/`, not at `base/` itself.

### Debugging and Local Validation

**Recommended local validation loop:**

1. Launch from `.install/` in windowed mode:
   ```powershell
   .\openPREY-client_x64.exe +set fs_game basepr +set fs_savepath ..\.home +set logFile 2 +set logFileName logs/openprey.log +set r_fullscreen 0
   ```
2. Inspect `.home\basepr\logs\openprey.log` after each run (logs go under the game directory in `fs_savepath`)
3. Fix warnings and errors in engine/game/parser/loader code before resorting to content-side workarounds

**Build automation helpers:**

- `tools/build/meson_setup.ps1` auto-detects and initialises the Visual Studio developer environment
- `compile -C builddir` auto-runs `setup --wipe` if the build directory is missing or invalid
- `tools/build/openprey_devcmd.cmd` is available as a reusable MSVC developer shell

---

## Light Grids

openPREY supports idTech 4-style precomputed irradiance volumes for indirect diffuse lighting. Runtime data is stored in two parts:

- `maps/<map>.lightgrid` — probe layout, atlas metadata, and per-area light-grid parameters
- `env/maps/<map>/area*_lightgrid_amb.tga` — baked irradiance atlas images, typically one per populated portal area

### Baking

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

### Runtime and Debugging

- `r_useLightGrid 1` — enable the indirect-diffuse light-grid pass
- `r_showLightGrid 0..3` — visualize probe placement by area
- `r_forceAmbient <value>` — lift the final scene toward a minimum brightness floor
- `r_lightGridBakeWorkers` — control CPU worker count during baking
- `r_lightGridBakeAsyncReadback 0|1` — enable async GPU readback when supported
- `r_lightGridBakeMemoryMB` — cap transient bake memory usage
- `r_lightGridBakeReadbackSlots` — control async readback buffer count

Use `r_showLightGrid 1` to inspect only the current portal area, `2` to draw valid probes in all areas, and `3` to include invalid probe locations as well.

---

## SDK and Game Library

openPREY's game code is derived from the PREY Software Development Kit and lives in this repository under `src/game/`, `src/Prey/` and `src/preyengine/`. Meson compiles those trees in place against the engine headers in the rest of `src/`. The former `OpenPrey-game` companion repository is historical; its history was merged in with the import (see `docs/dev/game-source-provenance.md`).

The SDK is subject to the original Human Head Studios EULA, which permits non-commercial modification for use with a legitimate copy of PREY, but prohibits commercial exploitation and standalone redistribution of the SDK-derived code. For complete terms, see [`LICENSES/PREY-SDK-EULA.rtf`](LICENSES/PREY-SDK-EULA.rtf) and [`LICENSING.md`](LICENSING.md).

### Game Library Workflow

- Edit the game library in place under `src/game/`, `src/Prey/` and `src/preyengine/`
- Keep engine code out of the game trees and game code out of the engine directories; the two sides carry different licences
- Stage targets: `builddir/basepr/` and `.install/basepr/`

---

## Dependencies

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

## Versioning

openPREY's version starts from the base version in `meson.build` (currently `0.0.1`) and appends an explicit build track:

- `stable` — release builds, e.g. `X.Y.Z`
- `dev` — default local builds, e.g. `X.Y.Z-dev+gabcdef12`
- `nightly` / `beta` / `rc` — pre-release labels, e.g. `X.Y.Z-nightly.20260330.1+gabcdef12`

The `meson.build` version is a floor. `tools/build/openq4_version.py` raises it to the highest `vX.Y.Z` tag in the local repository, and `-Dversion_base_override` pins it exactly. openPREY's GitHub repository has no such tags yet. A checkout that has fetched tags from the `openq4-upstream` remote picks up openQ4's release tags, though, and reports an openQ4 version such as `0.13.2-dev`. Fetch upstream with `--no-tags`, or delete those local tags, to avoid that. Track labels, iterations, git metadata and resource build numbers are generated by the build system (`tools/build/meson_setup.ps1` / `tools/build/meson_setup.sh`).

---

[← Back to README](README.md)
