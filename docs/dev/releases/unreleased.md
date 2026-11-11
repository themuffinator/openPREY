# Unreleased openPREY changes

openPREY has no published release yet. [v0.0.1.md](v0.0.1.md) is the draft for the first release and describes the rebase onto the openQ4 engine as of August 2026. This file collects what changed after that draft, for curation when the first release is cut. It promises no version or date. The nightly builds on the Releases page date from April 2026, before the rebase, and contain none of this.

Engine changes merged from openQ4 are listed in openQ4's own release notes. They are inherited, not yet checked against PREY, until the [rebase status ledger](../prey-rebase/status-ledger.md) records evidence for them.

## Highlights

- **The game library is in this repository.** The PREY SDK-derived trees, `src/game/`, `src/Prey/` and `src/preyengine/`, were imported with their history from the former `OpenPrey-game` companion repository. Meson builds the unified `game_<arch>` module in place, so no companion checkout, configure-time staging or `OPENPREY_GAMELIBS_REPO` is needed. This supersedes the developer upgrade note in the 0.0.1 draft. The game trees stay under the PREY SDK EULA and the engine stays GPLv3; see [LICENSING.md](../../../LICENSING.md) and the [game source provenance record](../game-source-provenance.md).
- **Multiplayer bot characters (experimental).** Nineteen named bots built on PREY's own artificial player (`hhArtificialPlayer`), each with one of six fighting styles, a retail player model and its own chat lines, added with `addbot [character] [skill]`. Retail maps ship no bot navigation, so bots fight what they can see rather than planning routes. See the [bot guide](../mp-bots.md).
- **Damaged retail Ogg Vorbis files play through.** Sounds that stop early under stb_vorbis are decoded again with libvorbisfile (libogg 1.3.6 and libvorbis 1.3.7 Meson wraps), which resumes after a bad page instead of truncating the sound.

## Engine

- Merged openQ4 engine work through upstream `b4d3fd700` (November 2026), adapted to PREY's v7 game API. It includes the extended graphics presets with Auto-Detect, the classic menus laid out like the new interface, and cached shadow casters and projected shadow maps on Vulkan.
- Rebase hardening: guards for the render-demo header, the network rate defaults (32000), the GUI stream marker and window-flag layout, and the loading-music declaration scope; the missing autosave string `#str_107240`; lazy loading of dormant ARB programs; the particle deform implementation; and image alias handling.
- Shadow maps are the default shadow technique (`r_useShadowMap 1`) on every preset that draws shadows, Low, Performance and Balanced included; stencil volumes remain the per-light fallback. TrueType text is the default (`r_useTrueTypeFonts 1`). Configurations saved with the old values are moved to the new defaults once (`r_preyDefaultsMigrated`).
- Vulkan draws PREY's glow overlay: every `glowStage` material stage is redrawn into a black copy of the view, blurred per axis with `r_glowSteps`, `r_glowAlpha` and `r_glowAlphaChange`, and added over the scene at `r_glowStrength`, as the OpenGL renderer does.
- The classic GUI pointer is retail PREY's size: 16 canvas units on the menus (it was 15) and 32 on world GUIs (it was Doom 3's 64, twice retail's). `openq4_guiCursor <x> <y>` places a classic GUI's pointer for scripted captures.
- The in-game and system consoles use the PREY palette instead of Quake 4 amber and olive: the in-game console keeps a black field with portal-cyan text and edge, and the system console is dark Sphere-shell slate.

## Build and CI

- `openprey-validation.yml` builds the engine, dedicated server, OpenGL and Vulkan renderers and the unified game module as debug builds on Windows x64 and Linux x64, then checks the staged payload. The Linux lane installs its native development packages and the Windows lane prepares an OpenAL Soft runtime before staging.
- Fixed debug-only build failures in the game library on MSVC x64 and GCC, and header spellings that resolved only on case-insensitive filesystems.
- VS Code launch configurations come in OpenGL and Vulkan variants and cover the deathwalk maps.

## Documentation

- The player guides now describe openPREY only. Guides for Quake 4-only features carried in by engine merges were removed: The Awakening, campaigns, the Arena Campaign, competitive matches, liquids, classic dynamic lights, Android, the level editor and languages. The remaining inherited guides say where PREY testing is still pending.
- Getting Started, BUILDING.md, TECHNICAL.md and the contributing guide describe building from source, the Windows OpenAL runtime, the supported platforms (Windows x64 and Linux x64) and where configs, saves and logs go.

## Known Limitations

- Full campaign completion and multiplayer parity aren't claimed yet.
- Multi-view demos and the demo repeater are compiled out (`OPENPREY_ENABLE_MVD=0`, `OPENPREY_ENABLE_REPEATER=0`), along with openQ4's engine-side bot integration.
- ModernGL and Vulkan feature parity with PREY's original interaction stages is deferred; OpenGL stays the default.
- Checksums for the CD-era numbered `pak000.pk4`–`pak004.pk4` layout aren't recorded yet; those packs are checked for presence only.
- macOS, ARM64 and the inherited release, signing and publishing workflows stay switched off until they're rebuilt for openPREY.
