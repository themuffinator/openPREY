# Apple Support Gap Plan Without macOS Access

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Updated: 2026-08-26

This plan records the Apple/macOS compatibility, support, and robustness gaps
that can be worked from the current Windows/Linux development environment. It
is written in response to [issue #73](https://github.com/themuffinator/openQ4/issues/73),
where Apple Silicon users report a launch-time `SIGSEGV` after the renderer
reaches the Apple OpenGL 2.1 compatibility, ARB2, and renderer-upload startup
corridor.

The plan deliberately skips any checklist item that requires launching,
installing, signing assessment, Finder interaction, input/audio checking, or
manual runtime validation on macOS. Real Apple-hardware signoff remains useful,
but it belongs to the separate evidence workflow and is not a dependency for
the work below.

## Ground Rules

- [ ] Do not require local macOS hardware, a macOS VM, a hosted Apple shell, or
  a Finder/Terminal launch as part of this plan.
- [ ] Treat all macOS release wording as experimental until independent
  evidence exists outside this plan.
- [ ] Use static audits, synthetic capability tests, CI/workflow review,
  package-script review, symbol/log improvements, and user-supplied crash
  artifacts as the allowed evidence sources.
- [ ] Keep Quake 4 asset compatibility as the renderer and game-module
  constraint; do not solve Apple issues by shipping replacement content.
- [ ] Keep `openQ4-game` aligned because openQ4 stages game-library source from
  that companion repo.

## Opening Snapshot (historical)

This snapshot records the state that motivated the plan. Later phase-status
notes identify decisions that have since changed.

- [x] macOS is documented as experimental Apple Silicon/arm64 support.
- [x] The release backend is SDL3; `platform_backend=native` is comparison-only
  diagnostic infrastructure.
- [x] The current `-metal` package is a Metal bridge around the OpenGL renderer,
  not a native Metal renderer.
- [x] The package layout is an adjacent package root: `openQ4.app`, loose
  executables, and `baseoq4/` must stay together.
- [x] Credentialed release jobs can produce signed/notarized DMGs; unsigned
  tarballs remain experimental fallback output.
- [x] `openQ4-game` now has experimental Darwin/Clang `.dylib` module support
  with package-relative `@loader_path` install names.
- [ ] No completed first-class macOS runtime evidence is recorded.
- [ ] Issue #73 remains open, and reports through 0.6.8 indicate the crash can
  still occur even after the legacy upload bridge is disabled.

## Gap Register

| ID | Area | Gap | No-macOS-access response |
| --- | --- | --- | --- |
| APPLE-001 | Crash diagnostics | The POSIX/macOS signal path reports only the signal, not enough state to locate issue #73. | Add crash-safe renderer phase breadcrumbs and a support artifact checklist. |
| APPLE-002 | Renderer startup | Issue #73 sits in the Apple GL 2.1 ARB2 startup corridor, and upload-manager changes alone did not clear it. | Audit every ARB2, VBO, PBO, and program-upload decision with synthetic capability tests. |
| APPLE-003 | Driver quirks | Apple GL 2.1 fallback depends on string/capability matching that may not cover all Tahoe/M4/M5 reports. | Expand synthetic driver cases and make the fallback reason explicit in logs. |
| APPLE-004 | ARB program upload | A crash after interaction color-mode detection suggests the full interaction program or first ARB handoff can still be unsafe. | Add static tests for simple-interaction selection, missing entry points, and fail-closed reload paths. |
| APPLE-005 | Vertex arrays | CPU-backed fallback still shares legacy ARB2 client-array state with VBO-era code paths. | Inventory all `gl*Pointer` callsites and enforce buffer-state expectations around each path. |
| APPLE-006 | Symbolication | macOS packages reject `.dSYM` runtime payloads and do not publish a separate macOS symbolication artifact. | Add separate release/debug symbol artifacts outside the runtime package. |
| APPLE-007 | Support intake | User reports currently arrive as copied terminal text and screenshots. | Add an Apple crash-report template and a packaged support-info collector. |
| APPLE-008 | Package UX | The adjacent package-root layout is easy to break by moving only `openQ4.app`. | Add clearer missing-payload errors and static package-contract checks. |
| APPLE-009 | Architecture matrix | Current releases are arm64-only; Intel, universal2, and Rosetta are not supported. | Keep docs/tests preventing accidental broader claims. |
| APPLE-010 | OS floor | macOS 11 is the documented floor but is not proven by this no-platform plan. | Keep the floor experimental and make docs distinguish configured floor from proven runtime coverage. |
| APPLE-011 | Audio | Resolved statically: issue #122 supplied the provider evidence, and release packages now build and bundle pinned OpenAL Soft; physical audio signoff remains in the main compatibility plan. | Keep package/dependency/licence gates enforced and collect real-device evidence separately. |
| APPLE-012 | Native backend | Legacy native Cocoa/OpenGL code remains in-tree and can confuse support scope. | Keep it comparison-only or plan removal; static tests must keep it out of release claims. |
| APPLE-013 | Native Metal | There is no native Metal renderer, only a bridge label. | Keep naming honest and require a separate design before implementation. |
| APPLE-014 | Game modules | GameLibs macOS support is experimental and source-staged, not a proven runtime contract. | Add static ABI, naming, install-name, and build-string alignment checks. |
| APPLE-015 | Release notes | Apple limitations can drift between docs, release notes, and issue comments. | Add release-note checklist language tied to the experimental matrix and issue #73 status. |

## Phase 0: Keep The Support Claim Honest

- [x] Keep `README.md`, `BUILDING.md`, `docs/user/getting-started.md`,
  `docs/dev/platform-support.md`, and release notes aligned on
  "experimental Apple Silicon/arm64 macOS".
- [x] Keep Intel Mac, universal2, and Rosetta out of user-facing claims until a
  separate matrix expansion plan is accepted.
- [x] Keep `macos_graphics_bridge=metal` wording as "Metal bridge" everywhere.
- [x] Keep `platform_backend=native` documented as comparison-only.
- [x] Add a docs/static guard that fails if release notes promote macOS beyond
  experimental without an evidence reference.
- [x] Add release-note boilerplate for issue #73 until it is closed or
  explicitly moved to a known-limitation section.

### Phase 0 implementation status

- `README.md`, `assets/release/README.html`, and
  `docs/dev/platform-support.md` now spell out the current experimental
  Apple Silicon/arm64 macOS scope at front-door support surfaces.
- `docs/dev/release-completion.md` now has a macOS Support Claim Guard that
  blocks first-class, stable, or fully supported macOS wording unless
  `docs/dev/macos-signoff-evidence.md` and the macOS Evidence Gate support it.
- `docs/dev/releases/v0.6.5.md` now carries explicit experimental macOS
  limitation boilerplate for Apple Silicon/arm64-only packages, Metal bridge
  naming, comparison-only native backend scope, and GitHub issue #73.
- `tools/tests/macos_support_claim_policy.py` enforces the support-claim
  wording, curated release-note boilerplate, Phase 0 checklist status, and
  CI/local validation wiring without launching or testing on macOS.

## Phase 1: Improve Issue #73 Triage Without Running macOS

- [x] Add a macOS issue/support template requesting:
  - package version and artifact name
  - OpenGL vs Metal bridge package
  - launch method: `openQ4.app`, loose client, or loose dedicated server
  - macOS version/build and hardware model
  - full terminal output, not a screenshot
  - `~/Library/Logs/DiagnosticReports` `.ips` crash report when available
  - `~/Library/Application Support/openQ4/baseoq4/logs/openq4.log`
  - whether `openQ4.app`, loose binaries, and `baseoq4/` stayed together
- [x] Add a short packaged `collect_macos_support_info.sh` helper that gathers
  safe metadata and logs into one archive for users to attach.
- [x] Include renderer breadcrumbs, signing/Gatekeeper diagnostics, and
  quarantine presence in the support archive without launching openQ4.
- [x] Include Mach-O architecture, dependency, and game-module install-name
  diagnostics in the support archive without launching openQ4.
- [x] Include collector-process architecture and Rosetta translation state in
  the support archive without launching openQ4.
- [x] Make the helper redact obvious user secrets from paths or environment
  dumps before writing the archive.
- [x] Add a docs page explaining how users can provide crash data without
  requiring the maintainer to own a Mac.
- [x] Link the support-data request from issue #73 and future macOS release
  notes.

### Phase 1 implementation status

- `.github/ISSUE_TEMPLATE/macos-crash-report.yml` now asks macOS crash
  reporters for issue #73-relevant version, package, launch method,
  macOS/hardware, terminal output, `openq4.log`, app/client/dedicated
  DiagnosticReports, and package-layout details.
- `tools/macos/collect_macos_support_info.sh` gathers safe host/package/log
  metadata into `openq4-macos-support-YYYYMMDD-HHMMSSZ.tar.gz`, redacts
  obvious user paths and email addresses, avoids environment dumps, does not
  launch openQ4, does not copy retail `q4base` PK4 assets, stream-limits
  command/report output before redaction, and sanitizes copied public text so
  embedded control characters cannot poison issue attachments.
- The collector now adds `system/rosetta.txt` for collector-process
  architecture plus `sysctl.proc_translated` state,
   `logs/renderer-summary.txt` for renderer startup,
   driver-quirk, ARB2, and fatal-signal breadcrumbs,
   `logs/renderer-config.txt` for a privacy-filtered renderer/performance cvar
   snapshot that excludes bindings, player/account, network, audio-device, and
   arbitrary config settings,
   `package/binary-architecture.txt` for read-only `file`/`lipo` architecture
  output, `package/dylib-dependencies.txt` for read-only `otool` dependency
  and game-module install-name output, `package/signing.txt` for read-only
  `codesign`, `spctl --assess --type execute --verbose=4`, and
  `xcrun stapler validate` output, and `package/quarantine.txt` for
  extended-attribute names plus `com.apple.quarantine` presence without copying
  xattr values.
- The collector now also includes recent `openQ4-ded*.ips` and
  `openQ4-ded*.crash` DiagnosticReports so dedicated-server reports are not
  lost behind the client/app crash-report path.
- `tools/build/package_nightly.py` includes the collector in macOS package
  roots and macOS archive validation so users can attach a single support
  archive without moving files around.
- `docs/user/macos-support-data.md`, `README.md`,
  `docs/user/getting-started.md`, `assets/release/README.html`, and
  `docs/dev/releases/v0.6.5.md` now point users toward full terminal text,
  `openq4.log`, matching `.ips`/`.crash` reports, and the collector archive.
- `tools/tests/macos_support_intake.py` locks the issue template, collector,
  packaging contract, docs links, Phase 1 checklist status, and CI/local
  validation wiring without requiring any macOS platform test.

## Phase 2: Add Crash-Useful Renderer Breadcrumbs

- [x] Add a tiny crash-safe "last renderer phase" string or enum updated before
  these startup transitions:
  - `R_InitOpenGL`
  - `R_CheckPortableExtensions`
  - `R_ARB2_Init`
  - `R_ReloadARBPrograms_f`
  - `R_RendererUpload_Init`
  - `vertexCache.Init`
  - `tr.SetBackEndRenderer`
  - first ARB2 interaction handoff
- [x] Teach the POSIX signal handler to print the last renderer phase using only
  async-signal-safe output.
- [x] Print the same phase state in normal logs before and after renderer
  startup so copied logs are useful even without a crash report.
- [x] Add static validation that every renderer startup phase marker is present
  and updated in order.
- [x] Add a specific issue #73 breadcrumb around interaction program selection:
  full interaction, simple interaction, skipped full upload, and selected color
  mode.
- [x] Add a specific issue #73 breadcrumb when Apple GL 2.1 bypasses the ARB2
  light-interaction pass after renderer startup.

### Phase 2 implementation status

- `src/renderer/RendererStartupDiagnostics.h` and
  `src/renderer/RendererStartupDiagnostics.cpp` now store the last renderer
  startup phase in a `volatile sig_atomic_t` enum and expose fixed literal
  phase names for normal renderer logs and POSIX fatal-signal output.
- `src/sys/posix/posix_signal.cpp` now prints
  `openQ4: last renderer startup phase: ...` with async-signal-safe writes
  before exiting on fatal POSIX signals.
- `src/renderer/RenderSystem_init.cpp`, `src/renderer/RendererUpload.cpp`, and
  `src/renderer/draw_arb2.cpp` record ordered startup breadcrumbs for
  `R_InitOpenGL`, `R_CheckPortableExtensions`, `R_ARB2_Init`,
  `R_ReloadARBPrograms_f`, `R_RendererUpload_Init`, `vertexCache.Init`,
  `tr.SetBackEndRenderer`, startup completion, and the first ARB2 interaction
  handoff.
- `src/renderer/draw_arb2.cpp` also records issue #73-specific ARB interaction
  details for full interaction upload, simple interaction upload, skipped full
  upload, selected interaction family, and selected color mode.
- `src/renderer/draw_arb2.cpp` now records `ARB2 interaction driver bypass`
  when the Apple GL 2.1 compatibility quirk skips ARB2 light interaction draws
  to avoid the first-frame issue #73 crash.
- `docs/user/macos-support-data.md`, `docs/dev/releases/v0.6.5.md`, and
  `docs/dev/release-completion.md` now tell support users and release
  maintainers to preserve the `last renderer startup phase` and
  `first ARB2 interaction handoff` lines in crash reports.
- `tools/tests/macos_renderer_phase_breadcrumbs.py` enforces the phase enum,
  POSIX signal bridge, ordered renderer markers, interaction breadcrumbs,
  Phase 2 checklist status, docs/release-note wording, and CI/local validation
  wiring without requiring any macOS platform test.

## Phase 3: Harden The Apple GL 2.1 ARB2 Corridor

- [x] Expand `RendererDriverQuirks` synthetic cases for known report strings:
  Apple M4 Max, Apple M5, macOS 15.x, macOS 16/Tahoe, renderer unknown, and
  `2.1 Metal` style version strings.
- [x] Make Apple GL 2.1 fallback detection depend on normalized vendor/version
  and selected context facts, not only a fragile renderer substring.
- [x] Log every driver quirk that changes `hasVBO`, simple-interaction
  preference, PBO availability, or ARB2 path selection.
- [x] Add a static test proving Apple GL 2.1 disables the VBO vertex cache even
  when `GL_ARB_vertex_buffer_object` is advertised.
- [x] Add a static test proving Apple GL 2.1 prefers `SimpleInteraction.vfp`
  and skips the full `interaction.vfp` upload.
- [x] Add a static test proving Apple GL 2.1 bypasses ARB2 light-interaction
  draws on the fragile compatibility path and leaves a diagnostic breadcrumb.
- [x] Add a fail-closed path if the simple interaction program cannot load:
  print a clear unsupported-Apple-OpenGL message instead of continuing into
  the first draw.
- [x] Audit every `glBindProgramARB`, `glProgramStringARB`,
  `glProgramEnvParameter4fvARB`, and `glVertexAttribPointerARB` callsite for a
  preceding capability/entry-point contract.
- [x] Move repeated ARB program binding checks behind small helpers where that
  reduces missed callsites.
- [x] Add static coverage for disabled upload-manager state: no ring buffers, no
  sync objects, no buffer deletes without `glDeleteBuffersARB`, and no later
  code assuming VBO availability.
- [x] Add static coverage for CPU-backed vertex-cache paths: all client-array
  pointers must be real CPU pointers when array buffers are unbound.
- [x] Add static coverage for VBO-backed paths: all `idDrawVert` member offsets
  must be byte offsets, never undefined member pointers formed through offset
  tokens.

### Phase 3 implementation status

- `src/renderer/RendererCaps.cpp` now detects Apple OpenGL 2.1 compatibility
  fallback from normalized vendor/version data and the selected context facts
  (`glMajor`, `glMinor`, profile, fixed-function compatibility), independent
  of fragile renderer-name matching.
- The `RendererCompatibilityGates` synthetic matrix now covers Apple M4 Max,
  Apple M5, macOS 15.x, macOS 16/Tahoe, unknown/empty renderer names,
  `2.1 Metal`/`OpenGL 2.1 Metal` strings, and a negative modern Apple context.
- Driver-quirk logging now records selected context, fixed-function state,
  VBO/PBO before/after values, simple-interaction preference, and ARB2
  compatibility availability in one line.
- Apple GL 2.1 synthetic cases now also set the ARB2 light interaction bypass
  quirk so issue #73 comment 4874832470-style M4 Max reports degrade lighting
  instead of entering the fragile first-frame interaction draw.
- The July 5 issue #73 follow-up report for 0.6.91 reached
  `ARB2 interaction driver bypass` before crashing, so
  `src/renderer/draw_arb2.cpp` now restores the classic post-interaction GL
  state, texture-unit, and ARB program-binding baseline on the bypass path and
  `src/renderer/draw_common.cpp` records post-bypass light-scale,
  ambient-rescue, and frame-tail breadcrumbs.
- The July 6 issue #73 follow-up report for 0.6.92 reached
  `ARB2 interaction bypass light scale` before crashing, so the bypass path now
  forces a neutral light-scale/overbright state, skips the post-interaction
  `RB_STD_LightScale()` fullscreen pass, and records
  `ARB2 interaction bypass light scale skipped` before ambient rescue.
- `src/renderer/draw_arb2.cpp` already routes repeated required program binds
  through `R_BindARBProgram`; Phase 3 now adds
  `RB_ErrorIfDriverRequiredSimpleInteractionFailed()` so Apple GL 2.1 fallback
  stops with `Unsupported Apple OpenGL 2.1 compatibility path` if
  `SimpleInteraction.vfp` cannot load.
- Static coverage now checks ARB entry-point gates, ARB program upload failure
  handling, disabled upload-manager state, guarded buffer deletion,
  CPU-backed vertex-cache pointers, and VBO-backed `idDrawVert` byte-offset
  usage for the classic ARB2 interaction path.
- `tools/tests/macos_apple_gl21_arb2_corridor.py` enforces the Phase 3
  contract, documentation wording, checklist status, and CI/local validation
  wiring without requiring any macOS platform test.

## Phase 4: Make Symbolication Possible

- [x] Add a macOS release/debug symbol artifact that is separate from the
  runtime package, such as a `.dSYM` archive named with version, arch, and
  bridge.
- [x] Keep `.dSYM` bundles out of runtime DMG/tarball packages.
- [x] Ensure symbol artifacts cover:
  - `openQ4.app/Contents/MacOS/openQ4`
  - loose `openQ4-client_arm64`
  - loose `openQ4-ded_arm64`
  - `openQ4.app/Contents/Frameworks/game-sp_arm64.dylib`
  - `openQ4.app/Contents/Frameworks/game-mp_arm64.dylib`
- [x] Document how to pair a user `.ips` report with the correct symbol archive.
- [x] Add package-script tests that symbol archives cannot be mistaken for
  runtime payloads.

### Phase 4 implementation status

- `tools/build/package_nightly.py` now writes a macOS package-root
  `SYMBOLS.txt` manifest with the runtime archive name, matching dSYM symbol
  archive name, SHA-256s, sizes, Mach-O UUID lines, and dSYM paths for the app
  executable, loose client/dedicated binaries, and SP/MP game dylibs.
- The macOS packager now creates separate
  `openq4-<version>-macos-arm64-<bridge>-symbols.tar.xz` dSYM archives with
  `dsymutil`, validates the archive contents, and keeps `.dSYM` bundles out of
  runtime DMG/tarball packages.
- `.github/workflows/manual-release.yml` now verifies macOS runtime package
  names do not look like symbol/debug artifacts, verifies `SYMBOLS.txt`, and
  uploads the dSYM symbol archive as a separate release artifact.
- `tools/macos/collect_macos_support_info.sh` now copies package
  `SYMBOLS.txt` into support archives so maintainers can pair `.ips` reports
  with the correct symbol archive without rerunning on macOS.
- `docs/dev/macos-symbolication.md`,
  `docs/user/macos-support-data.md`, `docs/dev/macos-signoff-evidence.md`,
  `docs/dev/release-completion.md`, and `docs/dev/releases/v0.6.5.md` document
  the crash-log pairing workflow and evidence requirements.
- `tools/tests/macos_symbolication_policy.py` enforces the Phase 4 package,
  workflow, docs, checklist, and local/CI wiring contract without requiring any
  macOS platform test.

## Phase 5: Strengthen Package Robustness Without Finder Testing

- [x] Add a localized, clear startup error when adjacent runtime files are
  missing beside `openQ4.app`.
- [x] Make the error name the expected adjacent package-root contract:
  `openQ4.app`, loose binaries, and `baseoq4/` together.
- [x] Add static tests for package layout docs, app metadata, and error text so
  the app-only move case stays documented.
- [x] Keep symlink, AppleDouble, `.DS_Store`, `__MACOSX`, debug bundle, and
  case-fold collision rejection in package scripts.
- [x] Keep signed/notarized DMG as the only first-class release path.
- [x] Keep unsigned tarballs clearly named and documented as experimental
  fallback output.
- [x] Add support-info output showing package root, app path, `fs_basepath`,
  `fs_cdpath`, and `fs_savepath` without requiring the maintainer to reproduce
  Finder behavior.

Phase 5 implementation status:

- `src/sys/osx/macosx_compat.mm` now fails app-bundle launches early when the
  adjacent package root is incomplete, using localized `OpenQ4PackageRoot`
  strings from the generated app bundle with an English fallback.
- `tools/build/package_nightly.py` now writes and validates localized
  `OpenQ4PackageRoot.strings` resources, and archive validation treats them as
  required app metadata alongside the existing InfoPlist strings.
- `tools/macos/collect_macos_support_info.sh` now writes
  `package/path-resolution.txt` with package root, app path, expected loose
  runtime paths, and copied `fs_basepath`/`fs_cdpath`/`fs_savepath` log lines.
- `tools/tests/macos_package_robustness.py` enforces the Phase 5 startup error,
  package metadata, package-hygiene, release-path, support-info, docs, and
  local/CI wiring contract.
- No macOS platform testing is required or claimed for Phase 5.

## Phase 6: Audio Provider Decision Work

- [x] Keep release builds pinned to `macos_openal_provider=apple_framework`
  until the project intentionally changes policy; issue #122 subsequently
  supplied the evidence for that policy change.
- [x] Write and enforce the package policy for the OpenAL Soft macOS provider:
  library location, install names, codesigning, license notice, and notarization
  allowlist.
- [x] Promote `-Dmacos_openal_provider=system` from migration-only to the
  release provider once the pinned build and package gates are present.
- [x] Add static tests that user-facing release docs describe bundled OpenAL
  Soft only when package scripts, dependency validation, signing, notices, and
  corresponding source actually carry it.
- [x] Add crash/support template fields for OpenAL vendor, renderer, device
  name, and EFX warning lines from `openq4.log`.

Phase 6 implementation status (updated after issue #122):

- `docs/dev/macos-openal-provider-policy.md` records pinned OpenAL Soft 1.25.1
  as the release provider and defines its library location, install name,
  architecture/floor, codesigning, licence/source, and notarization gates.
- `BUILDING.md`, `docs/dev/platform-support.md`, and
  `docs/dev/macos-vm-testing-workflow.md` describe the pinned dependency and
  retain Apple's framework as compatibility-diagnostic coverage only.
- `.github/ISSUE_TEMPLATE/macos-crash-report.yml`,
  `docs/user/macos-support-data.md`, and
  `tools/macos/collect_macos_support_info.sh` now request or collect OpenAL
  vendor, renderer, version, device, and EFX warning/status lines from existing
  `openq4.log` files.
- `tools/tests/macos_openal_provider_policy.py` enforces the Meson option,
  checksum/build recipe, release workflow selection, package contract,
  attribution, non-fatal allocation path, support-intake fields, and local/CI
  wiring.
- No macOS platform testing is required or claimed for Phase 6.

## Phase 7: Contain Legacy And Future Renderer Paths

- [x] Keep Carbon and NSOpenGL isolated to the native comparison backend.
- [x] Add a static guard that SDL3 macOS sources never import or link Carbon.
- [x] Keep native Cocoa/OpenGL backend support wording out of release notes.
- [x] Decide whether to keep the native backend indefinitely or create a
  removal plan after SDL3 coverage is mature.
- [x] Keep native Metal out of implementation work until a separate design plan
  covers material/shader parity, BSE effects, readback, screenshots, diagnostics,
  fallback, and packaging names.

Phase 7 implementation status:

- `docs/dev/macos-native-backend-containment-policy.md` records the current
  decision: SDL3 remains the release backend, native Cocoa/OpenGL remains
  comparison-only diagnostic infrastructure, and a native-backend removal plan
  should be created after SDL3 OpenGL and Metal bridge coverage is mature across
  the documented macOS floor and latest public macOS.
- `tools/tests/macos_native_backend_containment.py` validates that
  `SDL3_DARWIN_SOURCES` excludes `macosx_event.mm` and `macosx_glimp.mm`, SDL3
  Darwin sources do not import Carbon or use NSOpenGL/CGL APIs, Meson links
  Carbon only for `platform_backend=native`, release notes avoid unsupported
  native-backend support wording, and active renderer/macOS sources do not grow
  native Metal implementation tokens.
- The new guard is wired into local validation plus commit, push, and macOS
  debug workflows.
- No macOS platform testing is required or claimed for Phase 7.

## Phase 8: Align `openQ4-game`

- [x] Keep `openQ4-game` Darwin/Clang support in the companion repo, not copied
  into `openQ4/src/game`.
- [x] Add or keep static tests for `.dylib` names:
  `game-sp_arm64.dylib` and `game-mp_arm64.dylib`.
- [x] Add or keep static tests for `@loader_path/<module>.dylib` install names.
- [x] Make build strings report the actual macOS architecture instead of a
  misleading universal label in support logs.
- [x] Add ABI/static checks for ARM64-sensitive game allocations, savegame
  serialization, pointer-width fields, and alignment-sensitive classes.
- [x] Record both openQ4 and `openQ4-game` commits in release metadata and
  support-info output.

Phase 8 implementation status:

- `openQ4` still has no `src/game` mirror; `meson.build` stages SDK/game
  sources from the sibling `openQ4-game` checkout into `.tmp/gamelibs_stage/`
  and requires the staged manifest.
- `tools/tests/macos_gamelibs_alignment.py` now validates the cross-repo macOS
  GameLibs contract: companion Darwin/Clang ownership, arm64 `.dylib` naming,
  `@loader_path` install names, architecture-specific macOS build strings,
  package/support provenance metadata, and validation wiring.
- `src/sys/sys_public.h` now reports concrete macOS build strings such as
  `macos-arm64` and `macos-x64` instead of `MacOSX-universal`.
- `tools/build/package_nightly.py`, `tools/macos/collect_macos_support_info.sh`,
  the signoff report generator, and the signoff archive validator now carry or
  require both openQ4 and `openQ4-game` commit fields.
- `openQ4-game/tools/tests/arm64_abi_contract.py` now statically guards
  ARM64-sensitive idClass allocation, savegame object serialization, script
  pointer-width fields, event `intptr_t` save/restore helpers, and
  alignment-sensitive stack/heap allocation sites.
- No macOS platform testing is required or claimed for Phase 8.

## Phase 9: Local Validation Track

These checks are allowed because they do not run openQ4 on macOS:

- [x] Run Python static/policy tests on Windows or Linux after plan work changes
  scripts or docs.
- [x] Run renderer self-test binaries only on available non-macOS hosts when the
  touched code is shared renderer logic.
- [x] Use synthetic driver/capability tests to model Apple GL 2.1 behavior.
- [x] Use archive/package fixture tests with synthetic macOS payloads.
- [x] Use CI/workflow linting and dry-run validation for release matrix changes.
- [x] Do not mark a checkbox complete merely because hosted macOS compiled; this
  plan is about no-platform-access robustness, not platform proof.

Phase 9 implementation status:

- `python tools/validation/openq4_validate.py macos-static` is now the named
  no-macOS-runtime profile. It defaults to `--skip-build`, runs the Python
  static/policy suite, lints shell validation entrypoints when Bash is
  available, and dry-runs the push/PR validation profiles.
- `tools/validation/validate_macos_static.ps1` and
  `tools/validation/validate_macos_static.sh` provide platform-friendly entry
  points for the same profile.
- `docs/dev/macos-local-validation-track.md` records the evidence boundary,
  the Windows/Linux commands, the optional non-macOS renderer self-test command,
  and the reason this track does not prove macOS runtime behavior.
- `tools/tests/macos_local_validation_track.py` now validates the Phase 9
  checklist, docs, `macos-static` profile behavior, workflow wiring, synthetic
  Apple GL 2.1 coverage, synthetic macOS package/archive fixture coverage, and
  dry-run validation hooks.
- The `macos-static` profile rejects `--runtime` on macOS; renderer self-test
  binaries are allowed only on available non-macOS hosts.
- No macOS platform testing is required or claimed for Phase 9.

## Definition Of Done For This Plan

- [ ] Issue #73 has enough requested artifacts to diagnose future reports
  without screenshots.
- [ ] A crash log can identify the last renderer startup phase before SIGSEGV.
- [ ] Apple GL 2.1 synthetic cases force CPU-backed vertex cache and simple ARB
  interaction fallback.
- [ ] ARB2, VBO, PBO, and program-upload callsites have static capability
  coverage or are routed through guarded helpers.
- [ ] macOS release/debug symbols are available outside runtime packages.
- [ ] Package layout failures produce clear user-facing errors and matching docs.
- [ ] macOS audio provider claims match actual package behavior.
- [ ] Native backend and Metal bridge wording cannot drift into unsupported
  promises.
- [x] `openQ4-game` macOS module names, install names, build strings, and ABI
  assumptions are statically covered.
- [x] No checklist item in this document requires the maintainer to run or test
  openQ4 on macOS.
