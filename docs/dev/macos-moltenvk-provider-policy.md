# macOS MoltenVK Provider Policy

Updated: 2026-10-28 (provider pin unchanged)

This document records how openQ4 acquires, pins, stages, validates, and signs
the MoltenVK runtime that the macOS Vulkan renderer module depends on. It is the
companion to `docs/dev/archive/2026-10-18/macos-moltenvk-decision.md`, which records *why* macOS
Vulkan originally shipped as opt-in; this document records *where the library comes from* and what
must be true of it before it may ship.

`tools/build/prepare_macos_moltenvk.sh` is the executable form of this policy.
Anything asserted here that the script can check, the script checks, and it
fails closed when it cannot.

## What MoltenVK Is

MoltenVK is a Vulkan-on-Metal translation layer. openQ4 does not build it, does
not vendor its sources, and does not modify it.

MoltenVK is a translation layer. It must never be described as native Metal, a
Metal renderer, a native Vulkan driver, or an OpenGL-free renderer, in code
comments, build output, package documentation, release notes, or user-facing
text.
`tools/tests/macos_native_backend_containment.py` and
`tools/tests/macos_moltenvk_policy.py` enforce that wording contract.

## Current Release Decision

Both existing macOS package variants — the OpenGL package and the Metal bridge
package — bundle the pinned `libMoltenVK.dylib` and the Vulkan renderer module.
The renderer is a runtime cvar, not a package axis: there is no third package
variant and no new `macos_graphics_bridge` choice.

Fresh macOS configurations use `r_renderApi best`, which tries Vulkan through
MoltenVK with OpenGL fallback under the user-requested 28 October 2026
high-performance GPU policy. Existing explicit OpenGL selections are retained.
Backend and device preferences can be changed in the retained System menu.
Vulkan remains experimental on macOS; this default change does not qualify it.
The packaging/provider pin is unchanged by the selection policy.

Staging MoltenVK is mandatory for a macOS package that ships the Vulkan renderer
module. A package that ships the module without the library would advertise an
option that fails at load time, so packaging fails rather than shipping that
combination.

## Pinned Version

Release builds must use:

```text
MOLTENVK_VERSION="v1.4.1"
```

MoltenVK v1.4.1 (released 2025-11-24) is the newest release that still supports
macOS 11.0. MoltenVK v1.4.2 raised the runtime floor to macOS 12.0.

openQ4's `macos_deployment_target` and `MACOS_MIN_SYSTEM_VERSION` are 11.0, so
the pin must stay at v1.4.1 until the project's own macOS floor moves through
the full multi-file floor change described in
`docs/dev/macos-support-matrix-policy.md`.

This is the single most likely way to ship a broken macOS package, and it looks
exactly like routine dependency maintenance. A v1.4.2 or later MoltenVK produces
a package that fails to launch on the macOS floor the project advertises, on
machines nobody on the project owns. Do not "upgrade" the pin as housekeeping.

`tools/build/prepare_macos_moltenvk.sh` asserts the staged dylib's
`LC_BUILD_VERSION` minimum OS is at most 11.0, so an accidental version bump
fails in CI instead of at a user's launch.

## Acceptable Sources

The only acceptable source for a release artifact is the official Khronos
release asset for the pinned tag:

```text
https://github.com/KhronosGroup/MoltenVK/releases/download/v1.4.1/MoltenVK-macos.tar
```

verified by SHA-256, with the library taken from inside the archive at
`MoltenVK/MoltenVK/dynamic/dylib/macOS/libMoltenVK.dylib`.

These sources are **not** acceptable for release artifacts:

- **Homebrew (`brew install molten-vk`).** The Homebrew build is
  architecture-thin, so it cannot serve both macOS package variants from one
  file, and it installs with an unpinned Cellar install name that leaks a
  build-machine path into the binary. It is neither reproducible nor universal.
- **The LunarG Vulkan SDK.** The SDK is a developer toolchain, not a
  redistribution channel. Its MoltenVK copy is not pinned to a digest the
  project controls, it moves independently of the SDK version, it carries SDK
  licensing and layer components openQ4 does not ship, and it offers no
  guarantee about the deployment-target floor that this policy depends on.
- **`MoltenVK-macos-privateapi.tar`.** That variant links Apple private API and
  is unsuitable for a distributed, notarized package.
- **Any locally built or hand-copied dylib.** A release artifact must be
  reproducible from the pinned tag and digest alone.

The LunarG SDK and Homebrew remain fine for local developer experiments. They
must never produce a file that ends up in a package.

## License And Attribution

MoltenVK is licensed under Apache-2.0. Redistribution is permitted with
attribution.

Release packages and package documentation must carry the MoltenVK license
notice and attribution alongside the other bundled third-party notices, in the
same place and by the same mechanism as the project's existing third-party
license collateral. The attribution obligation is part of shipping the library,
not a follow-up task: a package that bundles `libMoltenVK.dylib` without the
notice is not releasable.

## Package Policy

Every one of these must hold before a macOS package that bundles MoltenVK is
releasable:

- Library location: the bundled dylib lives at
  `openQ4.app/Contents/Frameworks/libMoltenVK.dylib`, beside the game modules
  and the Vulkan renderer module, with no loose Homebrew, MacPorts, `/opt`, or
  `@rpath` dependency leaking into release binaries.
- Install names: the staged dylib's own install name is rewritten to
  `@executable_path/../Frameworks/libMoltenVK.dylib`. The upstream published
  install name is `@rpath/libMoltenVK.dylib`; staging replaces it so the bundle
  location is explicit rather than rpath-dependent. Absolute local developer
  paths are forbidden, in this dylib and in everything that references it.
- Real file, never a symlink: the staged dylib must be a regular file.
  Packaging, archive validation, and notarization all reject symlinks, so the
  acquisition script copies with `cp -L` and asserts the result is not a link.
- Dependency allowlist: the dylib may link only `/System/Library/*` and
  `/usr/lib/*`, plus its own install name. A Homebrew, MacPorts, `/opt`,
  `@rpath`, or absolute developer path dependency is a ship blocker.
- Architecture: the dylib must be genuinely universal, `arm64` and `x86_64` in
  one file, so a single staged artifact serves both macOS package variants.
- Deployment floor: the dylib's `LC_BUILD_VERSION` minimum OS must be at most
  macOS 11.0, matching `MACOS_MIN_SYSTEM_VERSION`.
- Codesigning: the upstream dylib ships **ad-hoc signed only**, and rewriting
  the install name invalidates even that signature. Credentialed release runs
  must re-sign it with the Developer ID Application identity as nested code,
  signed inside-out — the dylib first, then the app bundle — before
  notarization upload, archive validation, and DMG creation. An ad-hoc
  signature surviving into a notarized package is a signing defect, not an
  acceptable state. The acquisition script re-applies an ad-hoc signature after
  the install-name rewrite so the staged file stays loadable on Apple silicon;
  that signature is a placeholder for the release identity, never a substitute
  for it.
- License notice: the Apache-2.0 notice and attribution ship with the package,
  per "License And Attribution" above.
- Notarization allowlist: package and archive validators add only
  `Contents/Frameworks/libMoltenVK.dylib` to the app/package allowlist, while
  keeping `.dSYM`, Finder metadata, symlinks, case-fold collisions, stale
  frameworks, and unrelated dylibs rejected.

## Acquisition Script

`tools/build/prepare_macos_moltenvk.sh` runs on a GitHub `macos-15` or
`macos-15-intel` runner and needs only the Xcode Command Line Tools.

```sh
# Download, verify, stage, fix up, and validate.
tools/build/prepare_macos_moltenvk.sh --output-dir .install

# Re-run every assertion against an already-staged copy.
tools/build/prepare_macos_moltenvk.sh --verify-only --output-dir .install

# A loose development package may also keep dylibs grouped here. Both the SDL
# surface path and Vulkan module probe this layout as well as .install itself.
tools/build/prepare_macos_moltenvk.sh --output-dir .install/Frameworks

# Validate the copy inside an assembled app bundle.
tools/build/prepare_macos_moltenvk.sh --verify-only \
  --dylib openQ4.app/Contents/Frameworks/libMoltenVK.dylib
```

In its default mode the script downloads the pinned tar with `curl -fsSL
--retry`, verifies the SHA-256 against the pinned constant, extracts only
`MoltenVK/MoltenVK/dynamic/dylib/macOS/libMoltenVK.dylib`, copies it out as a
real file, sets the package-relative install name with `install_name_tool -id`,
re-applies an ad-hoc signature, and then asserts the architecture set, the
install name, the dependency allowlist, and the macOS 11.0 minimum-OS ceiling.
It is idempotent: a verified tar in the download cache is reused, and re-running
it simply re-stages and re-validates.

Every run ends with a one-line provenance summary that CI captures as evidence:

```text
moltenvk_provenance: version=v1.4.1 tar_sha256=<digest> dylib_sha256=<digest> archs="arm64 x86_64" minos=11.0 install_name=@executable_path/../Frameworks/libMoltenVK.dylib signature=valid path=<staged path>
```

Any failure exits non-zero with an actionable message naming the offending
value. The script never degrades to an unverified or partially validated
artifact.

## Updating The Pin

`MOLTENVK_TAR_SHA256` in `tools/build/prepare_macos_moltenvk.sh` ships as a
deliberate placeholder, because the digest could not be produced on the machine
that wrote the script. Every mode except `--print-sha256` fails closed while the
placeholder is in place: with no verifiable digest, the script stages nothing.

To fill it in, or to move the pin to a new MoltenVK version:

1. Confirm the target version's macOS runtime floor is at most openQ4's
   `MACOS_MIN_SYSTEM_VERSION`. If it is higher — as it is for v1.4.2 and later —
   stop. Moving the pin requires moving the project's macOS floor first, through
   `docs/dev/macos-support-matrix-policy.md`.
2. Update `MOLTENVK_VERSION` in `tools/build/prepare_macos_moltenvk.sh` if the
   version is changing.
3. Regenerate the digest:

   ```sh
   tools/build/prepare_macos_moltenvk.sh --print-sha256
   ```

   That mode needs only `curl` and `shasum`, so it can run anywhere with network
   access, and it stages nothing.
4. Cross-check the printed digest against the release page from a second machine
   or network before trusting it. A digest generated and consumed on the same
   compromised path proves nothing.
5. Paste the 64-character lowercase hex digest into `MOLTENVK_TAR_SHA256`, next
   to the comment explaining the macOS 11.0 floor. Update this document's pinned
   version and asset URL in the same change.
6. Run `tools/build/prepare_macos_moltenvk.sh --output-dir .install` on a macOS
   runner and confirm the provenance line reports the expected version, archs,
   and `minos`.

Never relax or bypass the checksum check to unblock a build. A failing digest
means either the download is corrupt or the pin is wrong, and both are reasons
to stop.

## Support Data

macOS Vulkan crash and startup reports should include the renderer and loader
lines that already exist in `openq4.log`:

- `r_renderApi`
- `Vulkan: loader `
- the Vulkan device, driver, and API-version lines the Vulkan renderer logs at
  startup
- any Vulkan initialization failure and OpenGL fallback lines

Support tooling must not launch openQ4 to collect MoltenVK provenance. The
staged library's version and digest come from the release job's
`moltenvk_provenance:` line, not from a user's machine.

Report format note: because MoltenVK is a translation layer, a MoltenVK-backed
Vulkan report describes Metal behavior reached through Vulkan. Reports and
triage notes must say so rather than attributing the behavior to a native Metal
or native Vulkan driver.
