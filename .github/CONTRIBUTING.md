# Contributing to openPREY

Thank you for your interest in helping openPREY run PREY (2006) on modern systems with its own engine and game module. Bug reports, compatibility reports, testing feedback, documentation fixes and code are all welcome.

openPREY has no release yet. To play or test it you build it from source; see [Getting Started](../docs/user/getting-started.md) and [BUILDING.md](../BUILDING.md). The April 2026 nightlies on the Releases page predate the move onto the current openQ4 engine, so please don't report bugs against them.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Reporting Compatibility Issues](#reporting-compatibility-issues)
  - [Suggesting Features or Improvements](#suggesting-features-or-improvements)
  - [Contributing Code](#contributing-code)
- [Development Workflow](#development-workflow)
  - [Prerequisites](#prerequisites)
  - [Building](#building)
  - [Project Structure Notes](#project-structure-notes)
  - [Engine Changes from openQ4](#engine-changes-from-openq4)
  - [Before Submitting a Pull Request](#before-submitting-a-pull-request)
- [Style and Conventions](#style-and-conventions)
- [Licensing and Attribution](#licensing-and-attribution)
- [Getting Help](#getting-help)

---

## Code of Conduct

This project is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold it. Please report unacceptable behavior to the maintainers.

---

## How to Contribute

### Reporting Bugs

Before opening a new issue, please search [existing issues](https://github.com/themuffinator/openPREY/issues) to avoid duplicates.

When filing a bug report, include as much of the following as possible:

- The commit SHA you built (`git rev-parse HEAD`) and the version string printed at startup.
- Your operating system, CPU, GPU and driver version, and the renderer (`r_renderApi`: OpenGL is the default, Vulkan is opt-in).
- How your PREY (2006) install is laid out: original discs or another source, the install path, and whether `base/` holds the numbered `pak000.pk4`–`pak004.pk4` packs or the consolidated `pak_*.pk4` set.
- Clear steps to reproduce the problem, the map, and whether it happens in single-player, multiplayer or on a dedicated server.
- The expected behavior and what actually happened.
- A log. Launch with `+set logFile 2 +set logFileName logs/openprey.log`, reproduce the problem, and attach `logs/openprey.log` from the `basepr/` folder in your save path (`%LOCALAPPDATA%\openPREY` on Windows, `~/.local/share/openprey` on Linux).
- For crashes on Windows, the crash log and minidump from the `crashes/` folder beside the executable.

Windows x64 and Linux x64 are the supported platforms. macOS and ARM64 aren't supported yet; reports from those builds are welcome, but say clearly how you built them.

### Reporting Compatibility Issues

openPREY targets the official PREY (2006) retail assets and ships its own engine and game module. It can't load mods built for the proprietary retail game DLLs. When reporting a compatibility problem:

- Confirm the issue reproduces with the unmodified retail `base/` packs, not only with custom content or mods.
- Note whether it's specific to single-player, multiplayer, a dedicated server or a particular map.
- Don't rely on repo-side content overrides when validating; the goal is to run cleanly with the original assets alone.

### Suggesting Features or Improvements

Feature suggestions are best opened as issues with the `[Request]` or `[Enhancement]` prefix. To help discussion:

- Explain the player or developer benefit.
- Describe how it relates to stock-asset compatibility or the project goals in [AGENTS.md](../AGENTS.md).
- Mention any prior art from PREY, its SDK, Doom 3 or other idTech 4 projects.

openPREY values compatibility with the shipped PREY assets. Proposals that would break stock-map behavior or split the player base need extra justification.

### Contributing Code

1. Fork the repository and create a topic branch for your change.
2. Make focused commits with clear messages.
3. Follow the [Development Workflow](#development-workflow) and [Style and Conventions](#style-and-conventions) below.
4. Open a pull request referencing any related issue.

---

## Development Workflow

[AGENTS.md](../AGENTS.md) holds the project rules: the licence boundary, the `basepr/` layout, the unified game module, install discovery and the debug loop. The [rebase plan](../docs/dev/prey-rebase/plan.md) explains how openPREY sits on the openQ4 engine, and the [status ledger](../docs/dev/prey-rebase/status-ledger.md) records what has been ported, how it was tested and what is deferred. Relate your work to those records and update them when it changes what they say.

### Prerequisites

See [BUILDING.md](../BUILDING.md) for the full requirements. In short:

- **Windows x64:** MSVC 19.46+, Meson 1.6.0+ and Ninja. Use `tools/build/meson_setup.ps1` from a regular PowerShell window instead of invoking `meson` directly, and provide an [OpenAL runtime](../BUILDING.md#windows-openal-runtime).
- **Linux x64:** GCC 13+ or Clang 17+, Meson 1.6.0+, Ninja and the [system packages](../BUILDING.md#linux-system-packages).

### Building

A typical local build on Linux:

```bash
bash tools/build/meson_setup.sh setup builddir . --backend ninja --buildtype=debug --wrap-mode=forcefallback
bash tools/build/meson_setup.sh compile -C builddir
bash tools/build/meson_setup.sh install -C builddir --no-rebuild --skip-subprojects
```

On Windows, use the wrapper so the MSVC toolchain is available:

```powershell
powershell -ExecutionPolicy Bypass -File tools/build/meson_setup.ps1 setup builddir . --backend ninja --buildtype=debug --wrap-mode=forcefallback
powershell -ExecutionPolicy Bypass -File tools/build/meson_setup.ps1 compile -C builddir
powershell -ExecutionPolicy Bypass -File tools/build/meson_setup.ps1 install -C builddir --no-rebuild --skip-subprojects
```

In VS Code, the tasks in `.vscode/tasks.json` configure, build and stage the same way, and `.vscode/launch.json` has launch entries for each single-player and multiplayer map.

### Project Structure Notes

- **Engine code** lives under `src/` (GPLv3).
- **Game code** lives in `src/game/`, `src/Prey/` and `src/preyengine/`. It is derived from the PREY SDK and stays under the SDK EULA. It builds into one unified `game_<arch>` module for single-player and multiplayer. The former `OpenPrey-game` companion repository is historical.
- **BSE** lives under `src/bse/` and is built into the engine.
- **Runtime content** authored in this repository belongs under `content/basepr/pak0/` and `content/basepr/pak1/`; development-only fixtures go in `content/basepr/dev/`. `.install/basepr/` is staged output, not an editing target.
- **Build output:** use `builddir/` for build artifacts and `.install/` for the staged runtime package.
- **Layout and naming:** [Source Layout and Naming](../docs/dev/source-layout.md) describes every top-level directory, where vendored code and licence notices go, and how new files are named.

### Engine Changes from openQ4

openPREY takes engine work from openQ4 by merging `openq4-upstream/main`. When you merge:

- Keep the PREY game trees, `content/basepr/` and openPREY naming on the openPREY side.
- Never import Quake 4 game code (`src/mpgame/`, Quake 4's `src/game/`) or `content/baseoq4/`.
- PREY's game API is v7 (`src/game/Game.h`). Where new engine code calls Quake 4-only `idGame` methods, adapt it to v7 or gate it with the `OPENPREY-GATED(Dn)` markers described in the [rebase plan](../docs/dev/prey-rebase/plan.md).
- Upstream merges also bring openQ4's Quake 4-specific documentation. Adapt or drop it rather than letting it describe Quake 4 as if it were openPREY.

### Before Submitting a Pull Request

- Build your change and confirm the project still compiles.
- Launch from `.install/` in windowed mode (`+set r_fullscreen 0`) and enter gameplay on a map your change affects. Reaching the main menu alone isn't enough.
- Check the log for new warnings or errors.
- Run the source contracts that CI runs:
  ```bash
  python tools/tests/openprey_rebase_contract.py
  python tools/tests/linux_sanitizer_source_contract.py
  ```
- Update documentation if your change affects player-facing behavior, build steps or technical assumptions.
- Add release-note material to [`docs/dev/releases/unreleased.md`](../docs/dev/releases/unreleased.md) or [`docs/dev/release-completion.md`](../docs/dev/release-completion.md) when the change is user-facing, packaging-related or platform-related.
- Keep commits focused and rebased on the latest default branch when practical.

---

## Style and Conventions

- Match the existing style of the file you are editing.
- Prefer cross-platform abstractions through SDL3 rather than new platform-specific code in shared engine paths.
- Don't add hardcoded user-facing UI strings when a `#str_*` localization lookup is possible.
- Fix compatibility in engine, game, parser or loader code rather than with content workarounds. Add content files only when they're required.
- Keep `basepr/` as the single game directory; don't split single-player and multiplayer into separate modules or folders.
- Don't assume Steam or GOG install paths; install discovery must work for CD-era installs.
- Keep accurate credits, and add upstream attributions whenever you bring in outside work.

---

## Licensing and Attribution

- openPREY engine code is licensed under the [GNU General Public License v3.0](../LICENSE).
- Game code in `src/game/`, `src/Prey/` and `src/preyengine/` is derived from the PREY SDK and remains under Human Head Studios' [SDK EULA](../LICENSES/PREY-SDK-EULA.rtf).
- Never move engine code into the game trees or game code into the engine directories, and never relicense either side. Preserve original notices.
- PREY's game assets remain the property of their rights holders and are not included.

Contributions follow the licence of the component they modify. See [LICENSING.md](../LICENSING.md) for the component boundaries, original notices and distribution considerations.

---

## Getting Help

- [Discord](https://discord.gg/T32mFejwR4): the best place for informal questions and community discussion.
- [Issue tracker](https://github.com/themuffinator/openPREY/issues): bug reports, feature requests and structured technical discussion.
- [Website](https://www.darkmatter-quake.com): DarkMatter project news.

Thank you for helping keep PREY playable on modern systems.
