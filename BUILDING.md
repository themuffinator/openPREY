# Building openPREY from Source

This guide covers building openPREY on Windows and Linux, the two x64 platforms CI builds. The build files also cover macOS hosts, but macOS isn't supported yet: nothing builds or tests it for openPREY.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Game Library Sources](#game-library-sources)
- [Build Setup](#build-setup)
- [Build Options](#build-options)
- [Building on Windows](#building-on-windows)
- [Building on Linux](#building-on-linux)
- [Output Files](#output-files)
- [Packaging](#packaging)

---

## Prerequisites

### Compiler

| Platform | Minimum | Notes |
|---|---|---|
| **Windows x64** | MSVC 19.46+ (Visual Studio 2026+) | Use the Developer PowerShell or run `tools/build/openprey_devcmd.cmd` to initialise the environment |
| **Linux x64** | GCC 13+ or Clang 17+ | Distro packages are fine |

### Build Tools

- **[Meson](https://mesonbuild.com/)** 1.6.0 or newer
- **[Ninja](https://ninja-build.org/)** (recommended backend)
- **Python 3** (used by the build wrapper scripts and code generators)

### Linux System Packages

The engine links against the system OpenGL and OpenAL libraries, and SDL3, which builds from its Meson subproject, needs the usual Linux desktop development headers for X11, Wayland, input and audio. On Ubuntu 24.04 this is the set the Linux CI lane installs:

```bash
sudo apt-get install binutils libasound2-dev libdbus-1-dev libdecor-0-dev libdrm-dev libegl1-mesa-dev libfribidi-dev libgbm-dev libgl1-mesa-dri libgl1-mesa-dev libglx-mesa0 libibus-1.0-dev libjack-dev libopenal-dev libpipewire-0.3-dev libpulse-dev libsndio-dev libthai-dev libudev-dev libwayland-dev libx11-dev libxcursor-dev libxext-dev libxfixes-dev libxi-dev libxkbcommon-dev libxrandr-dev libxss-dev libxtst-dev libxxf86dga-dev libxxf86vm-dev
```

A Wayland-only build (`-Dlinux_x11=disabled`) can do without the X11 packages. Other distributions package the same libraries under their own names.

### Windows Note

On Windows, always invoke Meson through `tools/build/meson_setup.ps1` rather than calling `meson` directly from an arbitrary shell. The wrapper ensures MSVC tools (`cl.exe`, `link.exe`, etc.) are on `PATH` before setup, compile, and install steps.

```powershell
# Open a regular PowerShell window and use the wrapper:
powershell -ExecutionPolicy Bypass -File tools/build/meson_setup.ps1 <meson-command> [args...]
```

Alternatively, open `tools/build/openprey_devcmd.cmd` first to initialise the Visual Studio environment, then call `meson` directly.

> [!NOTE]
> Windows builds use Meson's `b_vscrt=static_from_buildtype` policy so openPREY itself does not require a separate Visual C++ redistributable install.

### Windows OpenAL Runtime

Windows builds link against OpenAL, so the client needs `OpenAL32.dll` beside it. The DLL isn't in the repository. After `compile` and `install`, the `meson_setup.ps1` wrapper copies it into `builddir/` and `.install/`, and stops with "OpenAL32.dll runtime not found" when it has none. It takes the DLL from `<OPENPREY_OPENAL_ROOT>\bin\OpenAL32.dll` when that environment variable is set, and from `src\external\openal-soft\bin\win64\OpenAL32.dll` otherwise.

Prepare one once per checkout, the way CI does:

```powershell
# Downloads and builds OpenAL Soft 1.25.2 into .tmp\openal-soft-windows-x64\ (bin\, lib\ and include\).
# Needs network access and the Visual Studio C++ tools, including CMake.
powershell -ExecutionPolicy Bypass -File tools/build/prepare_windows_openal.ps1 -Architecture x64

# Point the wrapper at it in each shell you build from...
$env:OPENPREY_OPENAL_ROOT = (Resolve-Path .tmp\openal-soft-windows-x64).Path

# ...or copy the DLL to the location the wrapper checks by default.
New-Item -ItemType Directory -Force src\external\openal-soft\bin\win64 | Out-Null
Copy-Item .tmp\openal-soft-windows-x64\bin\OpenAL32.dll src\external\openal-soft\bin\win64\
```

To link against a different OpenAL package, pass `-Dopenal_root_override=<path>` (a folder with `include\` and `lib\`) at configure time, and set `OPENPREY_OPENAL_ROOT` to the same folder so its `bin\OpenAL32.dll` is staged.

---

## Game Library Sources

openPREY's game library builds from this checkout. The SDK-derived trees are
`src/game/`, `src/Prey/` and `src/preyengine/`; they compile into the unified
`game_<arch>` module against the engine headers in the rest of `src/`. No
companion checkout, staging step or environment variable is needed.

The game trees stay under the PREY SDK EULA while the engine is GPLv3. See
[LICENSING.md](LICENSING.md) for the boundary and
[docs/dev/game-source-provenance.md](docs/dev/game-source-provenance.md) for the
import record. The former `OpenPrey-game` companion repository is historical.

---

## Build Setup

Third-party libraries come from Meson subprojects (`subprojects/`) and vendored sources (`src/external/`): SDL3, GLEW, libogg, libvorbis, stb_vorbis, glslang, RmlUi, JsonCpp, libtess2 and the OpenXR SDK, plus a prebuilt OpenAL Soft runtime on Windows. With `--wrap-mode=forcefallback`, the first configure step unpacks and builds the subprojects, so Windows needs nothing installed beyond the compiler, the build tools and the [OpenAL runtime](#windows-openal-runtime). Linux also needs the [system packages](#linux-system-packages) above.

---

## Build Options

Pass any of these with `-D<option>=<value>` on the `meson setup` command line:

| Option | Default | Description |
|---|---|---|
| `build_engine` | `true` | Build `openPREY-client_<arch>` and `openPREY-ded_<arch>` |
| `build_games` | `true` | Build the unified game module from the in-tree game sources |
| `build_renderer_gl` | `true` | Build the OpenGL renderer module (`renderer-gl_<arch>`) |
| `build_renderer_vk` | `true` | Build the Vulkan renderer module (`renderer-vk_<arch>`) |
| `openxr` | `auto` | Build OpenXR VR support into the SDL3 client on Windows and Linux |
| `platform_backend` | `sdl3` | `sdl3`; or `legacy_win32` on Windows and `native` on Linux, both transitional |
| `linux_x11` | `auto` | SDL3's X11/XWayland driver on Linux; `disabled` gives a Wayland-only build |
| `use_pch` | `true` | Use precompiled headers |
| `enforce_msvc_2026` | `false` | Fail configure if MSVC is older than 19.46+ (Windows only) |

`meson_options.txt` lists the rest. Options for Android, OpenGL ES and macOS are carried over from openQ4 and aren't used by openPREY.

---

## Building on Windows

### Debug Build

```powershell
# 1. Configure
powershell -ExecutionPolicy Bypass -File tools/build/meson_setup.ps1 setup --wipe builddir . --backend ninja --buildtype=debug --wrap-mode=forcefallback

# 2. Compile
powershell -ExecutionPolicy Bypass -File tools/build/meson_setup.ps1 compile -C builddir

# 3. Run directly from builddir
builddir\openPREY-client_x64.exe +set r_fullscreen 0
```

### Release Build

```powershell
# 1. Configure
powershell -ExecutionPolicy Bypass -File tools/build/meson_setup.ps1 setup builddir . --backend ninja --buildtype=release --wrap-mode=forcefallback

# 2. Compile
powershell -ExecutionPolicy Bypass -File tools/build/meson_setup.ps1 compile -C builddir

# 3. Stage the runtime package into .install/
powershell -ExecutionPolicy Bypass -File tools/build/meson_setup.ps1 install -C builddir --no-rebuild --skip-subprojects
```

### From a Visual Studio Developer Command Prompt

Once the MSVC environment is initialised via `tools/build/openprey_devcmd.cmd` you can call `meson` directly:

```batch
meson setup builddir . --backend ninja --buildtype=release --wrap-mode=forcefallback
meson compile -C builddir
meson install -C builddir --no-rebuild --skip-subprojects
```

---

## Building on Linux

> [!NOTE]
> SDL3 selects the available Wayland or X11 display path on Linux. Use `OPENPREY_FORCE_X11=1` only when an XWayland fallback is required.

### Debug Build

```bash
# 1. Configure
bash tools/build/meson_setup.sh setup --wipe builddir . --backend ninja --buildtype=debug --wrap-mode=forcefallback

# 2. Compile
bash tools/build/meson_setup.sh compile -C builddir

# 3. Run directly from builddir
./builddir/openPREY-client_x64 +set r_fullscreen 0
```

### Release Build

```bash
# 1. Configure
bash tools/build/meson_setup.sh setup builddir . --backend ninja --buildtype=release --wrap-mode=forcefallback

# 2. Compile
bash tools/build/meson_setup.sh compile -C builddir

# 3. Stage the runtime package into .install/
bash tools/build/meson_setup.sh install -C builddir --no-rebuild --skip-subprojects
```

---

## Output Files

### Build directory (`builddir/`)

| File | Description |
|---|---|
| `openPREY-client_x64[.exe]` | Main engine executable |
| `openPREY-ded_x64[.exe]` | Dedicated server |
| `renderer-gl_x64[.dll/.so]`, `renderer-vk_x64[.dll/.so]` | OpenGL and Vulkan renderer modules |
| `basepr/game_x64[.dll/.so]` | Unified game module |

- On Windows, import libraries (`.lib`), program databases (`.pdb`), and export files (`.exp`) may be present in debug builds; these are development-only artifacts.

### Install directory (`.install/`)

After the install step, `.install/` holds the runtime package:

```
.install/
├── openPREY-client_x64[.exe]   # Main executable
├── openPREY-ded_x64[.exe]      # Dedicated server
├── renderer-gl_x64.dll/.so     # OpenGL renderer module (the default)
├── renderer-vk_x64.dll/.so     # Vulkan renderer module (r_renderApi vulkan)
├── OpenAL32.dll                # (Windows) OpenAL Soft runtime
├── openPREY-steamdeck          # (Linux) Steam Deck launcher
├── share/                      # (Linux) desktop entries and icons
├── openPREY.ico / openPREY.icns
└── basepr/
    ├── game_x64.dll/.so        # Unified game module
    ├── pak0.pk4                # openPREY text, script, GUI and config content
    ├── pak1.pk4                # openPREY binary assets
    └── mod.json
```

> [!NOTE]
> Do not distribute raw `buildtype=debug` artifacts in public packages. MSVC import libraries (`*.lib`) are development-only artifacts and are not required in the package.

---

## Packaging

openPREY has no published release yet. The `meson install` step stages everything into `.install/`, which is the input for packaging.

The packaging scripts in `tools/build/` (`package_release.py`, `package_nightly.py`, `package_linux_appimage.py`) are carried over from openQ4. A Windows x64 archive built from `.install/` has been produced, inspected and launched in isolation; the other formats the scripts know about, such as Linux AppImages and macOS archives, haven't been checked for openPREY.

The inherited nightly, release and signing workflows in `.github/workflows/` are switched off until they're rebuilt around the in-tree game library, `basepr` and the unified module. Active CI (`openprey-validation.yml`) builds and stages Windows x64 and Linux x64 on every push and pull request, and uploads no packages.

---

[← Back to README](README.md)
