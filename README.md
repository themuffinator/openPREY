<div align="center">

<img src="assets/docs/img/banner.png" alt="openPREY banner">

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Version](https://img.shields.io/badge/version-0.0.1-green.svg)](https://github.com/themuffinator/openPREY)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](https://github.com/themuffinator/openPREY)
[![Architecture](https://img.shields.io/badge/arch-x64%20%7C%20arm64-orange.svg)](https://github.com/themuffinator/openPREY)
[![Build System](https://img.shields.io/badge/build-Meson%20%2B%20Ninja-yellow.svg)](https://mesonbuild.com/)

**PREY (2006) reborn — open-source, modern platform, classic feel.**

[Features](#features) • [Installation](#installation) • [Building](BUILDING.md) • [Documentation](#documentation) • [Credits](#credits)

</div>

---

## About

**openPREY** is a free, open-source replacement for **PREY (2006)** that brings your classic game into the modern era. Built on the shoulders of Quake4Doom, it keeps everything you love about the original — the brutal combat, the tight gameplay, the iconic atmosphere — and layers on a fresh set of visuals and quality-of-life upgrades that make it feel right at home on today's hardware.

Plug in a controller and play from the couch, enjoy crisp widescreen and ultrawide support, or push the visuals further with HDR rendering, dynamic shadow maps, and a suite of post-processing effects. The best part? It all runs on your existing copy of PREY — no new assets, no subscription, just your game looking and playing better than ever.

**openPREY** is under active development, with a maintained Issues tracker. Despite the remaining issues, it provides what is to date by far the most developed and refined custom source port available.

Run your existing copy of Prey on modern hardware across **Windows**, **Linux**, and **macOS** — without changing the game you remember.

> [!NOTE]
> **openPREY does not include game assets.** You must own a legitimate copy of Prey (2006) to play. On Windows, `fs_basepath` auto-discovery checks the current working directory, registry install entries (including App Paths and uninstall metadata), and known legacy install roots such as `Human Head Studios/Prey`, `2K Games/Prey`, and `Games/Prey`.

---

## Features

### PREY Compatibility
- **Unified Game Module Model** — Engine loads `game_<arch>` for both SP and MP paths, with legacy `gamex86`/`gamex64` aliases accepted during migration
- **Legacy Install Discovery** — Windows install detection covers CD-era registry keys, App Paths, uninstall entries, and known install roots without assuming Steam/GOG-only layouts
- **Official Asset Validation** — Startup validation checks the required official Prey base PK4 layout before the game runs

### Modern Platform and Tooling
- **SDL3-first Windows Backend** — SDL3 is the default window, input, and display backend; the legacy Win32 backend remains as a transitional fallback
- **Meson + Ninja Build System** — Canonical configure/build/install path with repo-local staging under `.install/`
- **Cross-platform Packaging Tooling** — Windows, Linux, and macOS packages share the same Meson staging flow
- **Crash Diagnostics** — Windows debug builds write crash logs and minidumps into `crashes/` beside the executable

### Display and Runtime
- **Modern Window Modes** — Windowed, borderless, desktop-native fullscreen, and exclusive fullscreen all supported
- **Monitor Selection** — SDL3 builds expose `r_screen`, `listDisplays`, and `listDisplayModes` for multi-monitor setup
- **Aspect Ratio and FOV** — Automatically derived from the current render size; no manual aspect-ratio setting needed

---

## Installation

### Step 1 — Get PREY (2006)

You need a copy of **PREY (2006)** installed from original media or another legitimate distribution. openPREY supports CD-era install layouts.

### Step 2 — Download the latest openPREY release

Head to the **[Releases page](https://github.com/themuffinator/openPREY/releases)** and download the latest archive for your platform (Windows, Linux, or macOS).

### Step 3 — Extract

Unzip or unpack the archive to any folder you like.

### Step 4 — Play

Launch `openPREY-client_x64` (that's `openPREY-client_x64.exe` on Windows). openPREY will find your PREY (2006) installation automatically in most cases.

> [!NOTE]
> **Windows players:** The package is self-contained — no extra software needs to be installed.

> [!NOTE]
> **Linux players:** SDL3 selects native Wayland or X11 from the host. Use
> `OPENPREY_FORCE_X11=1` only when an XWayland fallback is required.

Linux packaging tooling can produce AppImages named with the standard `x86_64` or
`aarch64` architecture suffix. Publication lanes remain gated until the unified-module
runtime matrix is complete.

> [!TIP]
> If openPREY can't find your PREY installation automatically, launch with `+set fs_basepath "C:\path\to\PREY"`. See the [manual path configuration](TECHNICAL.md#manual-path-configuration) section in the technical reference.

---

## Documentation

- [Display Settings](docs/user/display-settings.md) — fullscreen, borderless, monitor selection, and anti-aliasing
- [Technical Reference](TECHNICAL.md) — compatibility status, advanced configuration, file layout, dependencies, and versioning
- [Building from Source](BUILDING.md) — compiler requirements and build options
- [Licensing](LICENSING.md) — the GPLv3 engine and the Prey SDK EULA game library

---

## Building from Source

Want to compile openPREY yourself? Full instructions and compiler requirements live in **[BUILDING.md](BUILDING.md)**. The engine and the game library build from this one checkout.

---

## Contributing

openPREY is an open project and welcomes contributions of all kinds — bug reports, code fixes, documentation, and platform testing.

1. Fork the repository
2. Create a feature branch
3. Make your changes and test thoroughly
4. Submit a pull request

Keep compatibility with official PREY assets in mind, follow the existing code style, and see [BUILDING.md](BUILDING.md) for build setup instructions.

---

## Credits

### Project Lead

- **themuffinator** — openPREY development and maintenance

### Upstream Credit

- **[openQ4](https://github.com/themuffinator/openQ4)** — the engine openPREY tracks; its engine history is merged here
- **Justin Marshall** — [Quake4Doom](https://github.com/jmarshall23/Quake4Doom) baseline and related reverse-engineering work
- **Robert Beckebans** — RBDOOM-3-BFG modernization work that informs this ecosystem
- **[Emile Belanger (emileb)](https://github.com/emileb)** — original Android, SigmaTouch and OpenGL ES work in the upstream engine (see [CONTRIBUTORS.md](CONTRIBUTORS.md))

### Original Developers

- **id Software** — idTech 4 engine lineage
- **Raven Software** — Quake 4 codebase lineage used by OpenQ4
- **Human Head Studios** — PREY (2006) and the PREY SDK

### Third-Party Libraries

- **Xiph.Org Foundation** — [libogg and libvorbis](https://xiph.org/vorbis/) audio codecs
- **GLEW Team** — OpenGL extension wrangler
- **OpenAL Soft Contributors** — 3D audio implementation
- **SDL Team** — Cross-platform framework
- **Sean Barrett** — [stb_vorbis](https://github.com/nothings/stb) Ogg Vorbis decoder
- **RmlUi, glslang, OpenXR SDK, JsonCpp and libtess2 contributors** — retained UI, shader compilation, VR, JSON and tessellation libraries carried with the upstream engine; notices in [LICENSES/](LICENSES/)

---

## License

openPREY is licensed under the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0) (GPLv3). You are free to use, modify, and distribute the software under its terms.

See the [LICENSE](LICENSE) file for full details.

**Note:** The GPLv3 license applies to openPREY's engine code only. The game library in `src/game/`, `src/Prey/` and `src/preyengine/` is derived from the PREY SDK and remains subject to the original Human Head Studios [SDK EULA](LICENSES/PREY-SDK-EULA.rtf). See [LICENSING.md](LICENSING.md) for the full breakdown. PREY game assets remain the property of Human Head Studios and 2K.

---

## Disclaimer

openPREY is an independent project and is not affiliated with, endorsed by, or sponsored by Human Head Studios, 2K, Bethesda, ZeniMax, id Software, or Raven Software. PREY is a trademark of ZeniMax Media Inc.

You must own a legitimate copy of PREY (2006) to use this software. openPREY does not include any copyrighted game assets.

**THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.** openPREY is software under active development. Use at your own risk.

---

## Links

[Repository](https://github.com/themuffinator/openPREY) • [Issue Tracker](https://github.com/themuffinator/openPREY/issues) • [Releases](https://github.com/themuffinator/openPREY/releases) • [OpenQ4](https://github.com/themuffinator/OpenQ4)
