# macOS OpenAL Provider Policy

Updated: 2026-08-26

## Release provider

macOS release, commit-validation, push-validation, sanitizer, and universal2
jobs use:

```text
-Dmacos_openal_provider=system
```

For those jobs, `system` means the project’s checksum-pinned OpenAL Soft 1.25.2
build, not an untracked library from the build host. The build recipe is
`tools/build/prepare_macos_openal_soft.sh`. It downloads the official
[OpenAL Soft](https://openal-soft.org/) tag archive, verifies SHA-256
`fb27e5839aa11f0e5b9d33756965291fad5d6909ab928ea1f796f4a1a6877894`,
builds a dynamic CoreAudio runtime for the package architecture and macOS 11.0
floor, and exposes it to Meson through pkg-config. The lookup remains
pkg-config-only so a missing dependency fails configuration instead of silently
selecting incompatible headers or Apple’s framework.

`-Dmacos_openal_provider=apple_framework` remains available only as a
compatibility diagnostic. A compile-only debug lane keeps that path from
silently rotting, but published packages must not use it. This decision follows
GitHub issue #122, which demonstrated that Apple’s implementation exhausts its
buffer pool on stock single-player levels and then returns `AL_INVALID_VALUE`.
Staged validation reads the selected provider from Meson's build-option
metadata: it requires the OpenAL Soft runtime and source/license payload for
`system`, while allowing an `apple_framework` diagnostic stage to remain
self-consistent. Release-package validation always enforces the OpenAL Soft
contract below.

## Package contract

Every macOS package must meet all of these requirements:

- Library location: exactly one `libopenal.1.dylib` is embedded at
  `openQ4.app/Contents/Frameworks/libopenal.1.dylib`.
- Install name: the library ID and client dependency are
  `@rpath/libopenal.1.dylib`. The client’s reviewed `@loader_path` search paths
  cover direct `.install` runs, the app executable, and the loose diagnostic
  client beside `openQ4.app`; absolute Homebrew, MacPorts, `/opt`, and build-tree
  paths are rejected.
- Architecture and floor: thin packages contain exactly their requested Mach-O
  slice; universal2 assembly lipo-merges the independently validated arm64 and
  x86_64 runtimes; every slice must retain the macOS 11.0 deployment target.
- Codesigning and notarization: OpenAL Soft is signed inside-out with the other
  `Contents/Frameworks` images before the app. Dependency, signature,
  notarization, archive, symlink, file-mode, case-fold, and allowlist checks all
  include it.
- License and corresponding source: `Contents/Resources/licenses/openal-soft/`
  contains `COPYING`, `SOURCE.md`, the PFFFT/fmt/Microsoft GSL notices, and the
  verified `openal-soft-1.25.2.tar.gz` source archive. Package validation
  rejects a missing or misplaced item.

The OpenAL Soft runtime is LGPL-licensed and dynamically linked. The repository
already carries its license under `src/external/openal-soft/COPYING`; the source
notice and exact build recipe are maintained beside it.

## Allocation-failure behavior

OpenAL buffer creation or upload failure is not a valid reason to tear down a
successfully loaded map. Decoded sample data remains available to the voice
streaming path, the first allocation failure is logged with the sample and AL
error, repeated allocation warnings are suppressed, and an affected sound may
be skipped if the provider has no buffers left. Invalid or unsupported source
audio formats remain content errors and retain their existing diagnostics.

Bundled OpenAL Soft is the primary fix; the non-fatal path is defense in depth
for resource exhaustion or unusual third-party implementations.

## Support data

Crash and audio reports should include these existing `openq4.log` lines:

- `OpenAL vendor:`
- `OpenAL renderer:`
- `OpenAL version:`
- `OpenAL requested device:`
- `OpenAL default device:`
- `OpenAL active device:`
- any `OpenAL EFX ...` warnings or status lines

The macOS support collector copies them to `logs/openal-summary.txt` when an
existing log is available. It must not launch openQ4 merely to collect provider
evidence.
