# macOS Support Data

> [!NOTE]
> macOS isn't supported yet. The build files still cover macOS hosts, but nothing builds or tests openPREY on a Mac, there is no package, and the release and signing workflows are switched off. This page is for people who build it from source anyway.

If you build openPREY on macOS, a complete report is much more useful than a screenshot, because the maintainer may not have access to a Mac. Reports that it simply works are useful too, especially on a macOS version older than the current one. Identify the exact source commit (the PREY game library is built from the same checkout), the Meson options, the architecture and the graphics backend you used.

## Minimum useful report

Include:

- `git rev-parse HEAD` for the openPREY checkout (it includes the in-tree PREY game library);
- macOS version and hardware model;
- `uname -m` and whether the process ran natively or through translation;
- the full terminal transcript;
- the saved `basepr/logs/openprey.log` (under `fs_savepath`, which defaults to `~/Library/Application Support/openPREY`);
- the selected `r_renderApi` and the renderer/driver lines from `gfxInfo`;
- any macOS `.ips` crash report;
- the exact Meson setup command and build type.

Do not use an operating-system screen capture to validate rendering. Use the engine's
registered `screenshot` command and attach the image it writes from the render target.

## Reproduction launch

Always force windowed mode for development runs:

```sh
./openPREY-client_arm64 \
  +set r_fullscreen 0 \
  +set fs_game basepr \
  +set fs_savepath ../.home \
  +set logFile 2 \
  +set logFileName logs/openprey.log
```

Point `fs_basepath` at a legitimate PREY (2006) installation when automatic discovery
does not find one. Do not copy retail `base/` PK4s into `basepr/`.

## Support collector

The collector lives at `tools/macos/collect_macos_support_info.sh`. If your staged tree
contains a copy, run it from the package root and inspect the archive before attaching it. The collector is diagnostic tooling;
its presence does not imply a supported macOS build.

The archive's `package/path-resolution.txt` records the package root, app path,
expected loose openPREY runtime paths, embedded `basepr` data and unified game-module
paths, plus any `fs_basepath`, `fs_cdpath`, and `fs_savepath` lines it can find. The
collector gathers this information without launching openPREY.

## Current boundaries

- OpenGL is the first compatibility target.
- Vulkan through MoltenVK and other backend parity remain validation TODOs.
- macOS isn't in CI; the inherited macOS workflows are switched off until they're rebuilt for openPREY.
- One unified `game_<arch>` module serves SP and MP; split `game-sp`/`game-mp`
  packages are not part of openPREY.
- See [the rebase status ledger](../dev/prey-rebase/status-ledger.md) for current
  validation and release-lane TODOs.
