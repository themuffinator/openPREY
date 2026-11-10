# openPREY Agent Guide

This file describes project goals, rules, and workflow expectations for anyone working on openPREY.

**Project Metadata**
- Name: openPREY
- Author: themuffinator
- Company: DarkMatter Productions
- Version: 0.0.1
- Repository: `https://github.com/themuffinator/openPREY`
- Game library: in-tree `src/game/`, `src/Prey/`, `src/preyengine/` (Prey SDK EULA; see `LICENSING.md`)

**Goals**
- Deliver a minimal, clean adaptation of the OpenQ4-derived engine for Prey (2006).
- Preserve behavior expected by shipped Prey assets where practical.
- Keep single-player and multiplayer behavior compatible with Prey’s unified game-library model.
- Prefer Doom 3 lineage behavior over Quake 4-specific behavior where Prey requires it.
- Restore missing Doom 3/Prey-era systems where required for compatibility (including particle-system behavior).
- Keep a unified runtime game directory layout under `basepr/`.

**Rules**
- The Prey game library is canonical in this repository: `src/game/`, `src/Prey/` and `src/preyengine/`. The former `OpenPrey-game` companion repository is historical; its history is a merge parent of the import commit (see `docs/dev/game-source-provenance.md`).
- Keep the licence boundary explicit: engine code is GPLv3 (`LICENSE`); the game trees are SDK-derived and stay under the Prey SDK EULA (`LICENSES/PREY-SDK-EULA.rtf`). Never move engine code into the game trees or game code into engine directories, and never relicense either side. Preserve original notices.
- Keep `openPREY` free of references to the old OpenQ4 closed-source BSE companion-repo workflow.
- Do not assume Steam/GOG distribution paths for Prey (2006). Auto-detection must support CD-era installs.
- Prefer robust install discovery from registry/app-path/uninstall entries and known legacy install roots.
- Never launch openPREY in fullscreen from agent workflows; always force windowed mode with `+set r_fullscreen 0` (and equivalent config/cvar handling).
- Keep Meson as the canonical openPREY build entry point.
- Use `builddir/` as standard local build output.
- Use `.install/` as staged runtime package root.
- Keep compiler/linker intermediates in `builddir/`, not `.install/`.
- Keep documentation current whenever workflow, naming, or repository structure changes.

**Build/Tooling Conventions**
- On Windows, use `tools/build/meson_setup.ps1 ...` (or `tools/build/openprey_devcmd.cmd`) so MSVC environment setup is consistent.
- Use `meson install -C builddir --no-rebuild --skip-subprojects` when staging `.install/`.
- Legacy `OPENQ4_*` variants are accepted only as temporary migration compatibility inputs.

**Runtime Module Direction**
- Build and package one unified Prey game module (`game_<arch>`) for both single-player and multiplayer.
- Do not reintroduce split `game_sp`/`game_mp` build outputs; legacy retail module names may remain loader aliases only where compatibility requires them.

**.install Layout (Staging Target)**
- `.install/` is the runtime package root used by local staging and `fs_cdpath` overlays.
- Keep executables in `.install/`.
- Keep game modules and staged content in `.install/basepr/`.
- Keep repo-authored runtime content under `content/basepr/pak0/` and `content/basepr/pak1/`; keep development-only fixtures under `content/basepr/dev/`.
- Avoid shipping build-only artifacts (for example import libs) in `.install/`.

**Development Procedure (Current Direction)**
1. Develop against installed Prey assets (not repo-side replacement content when avoidable).
2. Prefer launches from `.install/` so staged overlays are exercised.
3. Fix compatibility in engine/game/parser/loader code rather than shipping content hacks.
4. Validate with log-driven short-run loops, then with in-game map gameplay relevant to the change.

**Debug Loop**
1. Launch with the mode-appropriate debug configuration in windowed mode only (force `+set r_fullscreen 0`).
2. Let the engine initialize and enter the target gameplay state.
3. Close and inspect `fs_savepath\<gameDir>\logs\openprey.log`.
4. Resolve errors/warnings.
5. Repeat until clean.

**Temporary Files**
- Use `.tmp/` under the repository root for temporary task artifacts.

**References (Local, Not Included In Repo)**
- OpenQ4 source snapshot baseline: `E:\Repositories\OpenQ4`
- dhewm3 reference baseline: `E:\_SOURCE\_CODE\dhewm3-master`
- Historical Prey game-library repository (retired, read-only): `E:\Repositories\OpenPrey-game`
- Prey retail install (example legacy path): `C:\Program Files (x86)\Human Head Studios\Prey`

**Upstream Credits**
- Justin Marshall
- Robert Backebans
- id Software
- Raven Software
- Human Head Studios
