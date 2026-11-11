# Release status

**openPREY has no release yet.** The current version line is `0.0.1`, and the
only way to play it is to build it yourself from this repository. Status
checked on 11 November 2026.

The [Releases page](https://github.com/themuffinator/openPREY/releases) still
lists nightly builds from April 2026. They predate openPREY's move onto the
current openQ4 engine and the in-tree PREY game library, so they don't match
these guides. Please don't report bugs against them.

## Getting openPREY today

1. Keep your legitimate copy of **PREY (2006)** where it is installed. openPREY
   ships no PREY game data.
2. Build and stage openPREY with [BUILDING.md](../../BUILDING.md). The staged
   package lands in `.install/`: the client, the dedicated server, the renderer
   modules, and `basepr/` with the unified `game_x64` module and openPREY's own
   packs.
3. Launch `openPREY-client_x64` from `.install/` (`.exe` on Windows). openPREY
   finds a CD-era or other retail install through the registry, App Paths and
   uninstall entries and the usual install folders. If it doesn't, point it at
   the folder that contains `base`:

   ```text
   openPREY-client_x64 +set r_fullscreen 0 +set fs_basepath "C:\path\to\Prey"
   ```

[Getting Started](getting-started.md) covers the details.

## Platforms

Active CI (`.github/workflows/openprey-validation.yml`) builds the engine,
dedicated server, OpenGL and Vulkan renderers and the unified game module on
Windows x64 and Linux x64 on every push. Nothing is packaged or published from
CI yet: the inherited openQ4 release, ARM64, macOS and signing workflows are
switched off until they are rebuilt around `basepr/` and one `game_<arch>`
module.

| Platform | Build | Runtime testing | Package |
|---|---|---|---|
| Windows x64 | Built in CI | Deepest testing: representative campaign maps, save/load and a two-client listen server | None published. `tools/build/package_nightly.py` can produce a local archive |
| Linux x64 | Built in CI | Retail gameplay validation still pending | None published |
| Steam Deck / SteamOS | `openPREY-steamdeck` launcher staged by Linux builds | Inherited from openQ4, not yet checked with PREY | None published |
| Linux AppImage | `tools/build/package_linux_appimage.py` is rebranded for openPREY | Not run | Not produced: the publication lane is switched off |
| Linux ARM64, Windows ARM64 | Build files inherited from openQ4; nothing builds them | None | Not supported |
| macOS | Build files and packaging helpers inherited from openQ4; nothing builds them | None | Not supported. See [macOS Support Data](macos-support-data.md) if you build it anyway |
| Android | Inherited openQ4 sources only | None | openPREY doesn't target Android |

The [platform support roadmap](../dev/platform-support.md) lists the evidence a
platform needs before openPREY claims it.

## What works and what doesn't

**Landed**

- PREY install discovery for CD-era installs, without depending on Steam or GOG.
- One `game_x64` module, built from the in-tree PREY SDK game library, for
  single-player and multiplayer.
- Retail base-pack validation. The consolidated retail layout is
  checksum-verified; CD-era numbered packs are checked for presence until their
  checksums are recorded.
- OpenGL rendering on PREY's original interaction stages, and baked
  [light grids](light-grids.md).

**Tested, but not signed off**

- Single-player: the stock menu and representative maps, including Roadhouse,
  Feeding Tower, the deathwalk, Shuttle and portal gameplay, plus save/load.
- Multiplayer: a listen server with two clients. See
  [Multiplayer Networking](multiplayer-networking.md).
- Vulkan (`r_renderApi vulkan`): reaches gameplay on focused Roadhouse and
  Biolabs runs, without full PREY feature parity.
- Multiplayer bots, which are experimental. See the
  [bot guide](../dev/mp-bots.md).

**Not yet claimed**

- Full single-player campaign completion on stock assets.
- Multiplayer parity with the retail game.
- Retail parity for the restored Doom 3/PREY-era particle, FX and beam paths.

**Unavailable in the current baseline**

- Multi-view demos and voice chat need game-API calls PREY's v7 game module
  doesn't have. See [Multi-View Demos](multiview-demos.md) and
  [Multiplayer Chat](multiplayer-chat.md).
- Mods built for the original proprietary PREY game DLLs don't load.

## About the other guides

Most guides in this directory describe engine features carried over from
openQ4: shadow maps, cel shading, temporal AA, screen-space lighting, PBR
materials, DDS texture replacements, the level-load cache, VR, controller
support and the server tools. Each one opens with a note saying it has not yet
been checked against PREY. They describe what the engine code does; PREY
behaviour stays validation-pending until the
[rebase status ledger](../dev/prey-rebase/status-ledger.md) records evidence
for it.

The [Technical Reference](../../TECHNICAL.md) holds the full compatibility
status, and the [release completion list](../dev/release-completion.md)
collects work for the first release's changelog. Neither announces a release.
