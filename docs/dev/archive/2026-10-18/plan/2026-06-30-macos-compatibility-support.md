# macOS Compatibility And Support Gap Plan

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Updated: 2026-07-15

This plan records the current Apple macOS compatibility and support gaps found during a repo audit and turns each gap into concrete work. It covers the engine repo, the release/package tooling, CI workflows, runtime validation assets, documentation, and the companion `openQ4-game` game-library repo consumed at build time.

## Scope

In scope:

- macOS engine builds, package generation, signing, notarization, and release documentation.
- macOS game-library builds from `../openQ4-game`.
- SDL3 macOS backend support, the native macOS fallback backend, renderer startup, the OpenGL package, and the Metal bridge package.
- OpenAL provider support and real device behavior on macOS.
- Compliant Apple-hardware runtime validation through `tools/macos/Invoke-openQ4MacOSWorkflow.ps1`.
- User-facing support claims in `README.md`, `BUILDING.md`, `docs/user/`, `docs/dev/`, and release assets.

Out of scope:

- Hackintosh or Windows-hosted VMware unlocker workflows. These are explicitly not acceptable for openQ4 automation.
- Proprietary Quake 4 game DLL compatibility.
- Shipping replacement game content to compensate for engine or loader issues.

## Current Support Snapshot

The current tree has a substantial macOS bring-up foundation:

- `meson.build` supports Darwin hosts, sets the deployment target to macOS 11.0, defaults to SDL3 on macOS, and exposes `macos_graphics_bridge=opengl|metal`.
- `meson_options.txt` correctly describes the Metal path as a bridge around the SDL3/OpenGL renderer path, not a native Metal renderer.
- `.github/workflows/commit-validation.yml` builds macOS arm64 and experimental Intel x64 thin slices on hosted macOS runners for both OpenGL and Metal bridge variants, then verifies a non-publishing universal2 assembly corridor.
- `.github/workflows/manual-release.yml` publishes macOS arm64 OpenGL and Metal packages; credentialed runs produce signed and notarized DMGs, while uncredentialed runs produce unsigned tarballs.
- `tools/build/package_nightly.py` contains app bundle validation, strict macOS bundle allowlists, Developer ID signing, Hardened Runtime, notarization, stapling, DMG verification, and entitlement rejection for sandbox/get-task-allow.
- `tools/tests/macos_static_policy.py`, `tools/tests/macos_metal_bridge.py`, `tools/tests/macos_renderer_startup_guard.py`, and `tools/tests/macos_signoff_archive.py` encode many macOS policy and packaging expectations.
- `docs/dev/macos-vm-testing-workflow.md` documents a compliant Apple-hardware VM or host workflow with signoff archives and optional completed-checklist enforcement.
- `docs/dev/platform-support.md`, `BUILDING.md`, `docs/user/getting-started.md`, and `assets/release/README.html` currently describe macOS as experimental Apple Silicon/arm64 support.
- `../openQ4-game` has experimental standalone macOS Meson support for Darwin game modules plus hosted arm64 and Intel x64 CI.

Despite that foundation, macOS should remain experimental until the gaps below are closed or explicitly accepted as unsupported.

## Promotion Criteria

Move macOS from experimental to first-class only when all of these are true:

- A recent real Apple-hardware signoff archive exists for both OpenGL and Metal bridge packages.
- The signoff archive was collected with `-RequireCompletedSignoffChecklist` and includes in-game SP and MP coverage, not only main-menu startup.
- The package can launch from Finder and from terminal in the supported distribution layout.
- OpenAL behavior is validated on real devices, including default device changes and physical hotplug.
- The supported architecture and OS-version matrix is explicit, tested, and enforced by docs and release workflows.
- Release packages are signed and notarized for user-facing macOS releases, or the release is clearly marked as unsigned experimental/developer output.
- The companion `openQ4-game` support level matches the engine release claim.
- Any known unsupported macOS paths, such as Intel Macs or native Metal rendering, are clearly documented.

## Gap Register

| ID | Gap | Risk | Priority |
| --- | --- | --- | --- |
| MAC-001 | No completed real Apple-hardware runtime signoff is checked into the release evidence trail. | CI can pass while input, audio, display, Gatekeeper, or runtime package behavior fails on real Macs. | P0 |
| MAC-002 | User-facing macOS releases remain arm64-only; thin Intel CI and a hosted universal2 assembly gate are configured but have no accepted hosted or real-hardware evidence. | Intel/universal build regressions can now be caught, but publishing before gameplay/package/signing proof would overstate compatibility. | P1 |
| MAC-003 | The supported macOS version matrix is not backed by floor-version evidence. | The deployment target is macOS 11.0, but hosted validation mainly covers current hosted images. | P1 |
| MAC-004 | Both macOS packages still depend on the OpenGL renderer path; Metal is a bridge, not a native renderer. | Apple OpenGL limitations may become the long-term blocker for reliable macOS rendering. | P1 |
| MAC-005 | Release packages now bundle pinned OpenAL Soft, but real-device switching and long-session Apple-hardware evidence remain incomplete. | Static/package gates can pass while physical output switching, hotplug, or long-session audio still regresses. | P0 |
| MAC-006 | The self-contained app implementation still needs real Finder, copied-app, mounted-DMG, and Gatekeeper evidence. | Static/package validation can pass while end-user installation behavior fails on real macOS. | P1 |
| MAC-007 | `openQ4-game` has experimental ARM64 and Intel CI configured, but hosted Intel results and engine-mediated real gameplay evidence are still pending. | Engine releases can appear stronger than the game-library support they consume. | P1 |
| MAC-008 | A manual macOS sanitizer lane now exists, but clean hosted results have not yet been recorded for both bridges. | macOS-only lifetime, Obj-C/C++ interop, filesystem, and loader bugs need repeatable instrumented evidence. | P2 |
| MAC-009 | The legacy native macOS backend remains as a fallback without a clear maintenance policy. | Carbon/NSOpenGL fallback code can accumulate stale behavior or confuse support scope. | P2 |
| MAC-010 | Unsigned macOS tarballs remain a release fallback when Apple credentials are absent. | Users may hit Gatekeeper friction, and first-class support can be undermined by unsigned artifacts. | P1 |
| MAC-011 | macOS runtime validation is not yet tied into release-note and release-completion gates. | A release can ship with stale or missing support evidence even when docs say macOS is supported. | P1 |
| MAC-012 | Multiplayer macOS validation is not called out as a required signoff path. | SP may work while MP input, networking, module loading, or menu flows regress. | P1 |
| MAC-013 | The latest public engine revision does not yet reproduce the locally passing source state. | Hosted macOS output cannot be treated as current evidence until matching engine and GameLibs changes are committed and CI is green. | P0 |

## MAC-001: Real Apple-Hardware Runtime Signoff

Current state:

- The workflow exists in `docs/dev/macos-vm-testing-workflow.md` and `tools/macos/Invoke-openQ4MacOSWorkflow.ps1`.
- Archive validation exists in `tools/macos/validate_signoff_archive.py`.
- `docs/dev/release-completion.md` still carries a signoff task requiring real Apple hardware and a completed manual checklist.

Gap:

- The tree has process and tooling, but no fresh release evidence proving both macOS packages on real Apple hardware with completed manual checks.
- Hosted CI package validation is not a substitute for real display, input, audio, and Gatekeeper behavior.

Tasks:

- [ ] Assign an Apple Silicon host or compliant Apple-hardware VM for recurring openQ4 signoff.
- [ ] Run `tools/macos/Invoke-openQ4MacOSWorkflow.ps1 -Action Signoff -MacOSGraphicsBridge both` from Windows against that host.
- [ ] Complete every manual checklist item in `macos-runtime-signoff.md`, including Finder/Desktop launch, keyboard, mouse, controller if available, audio output switching, window/fullscreen/HiDPI, and in-game rendering.
- [ ] Run `tools/macos/Invoke-openQ4MacOSWorkflow.ps1 -Action CollectResults -MacOSRunId <id> -MacOSGraphicsBridge both -RequireCompletedSignoffChecklist`.
- [ ] Store the validated archive under `.tmp/` while working, then attach or reference it from release evidence rather than committing bulky binary archives.
- [x] Add a lightweight evidence index document under `docs/dev/` that records run ID, host model, macOS version, package version, graphics bridges tested, archive checksum, and any known exceptions.
- [x] Update `docs/dev/release-completion.md` so macOS runtime signoff cannot be considered done until the evidence index points to a completed-checklist archive.
- [x] Add first-party evidence recording tooling that validates the completed archive, computes SHA-256, extracts bridge/hardware metadata, and updates `docs/dev/macos-signoff-evidence.md`.
- [x] Add hardware inventory to generated signoff reports so host model and CPU do not rely on manual transcription.

Validation:

- `python tools/macos/validate_signoff_archive.py <archive> --require-completed-checklist`
- Confirm `macos-runtime-signoff.md` has checked manual items for both OpenGL and Metal bridge sections.
- Confirm the archive contains workflow logs, hardware inventory, `renderer-smoke`, `renderer-mp-smoke`, `renderer-matrix`, and staged package details.

Exit criteria:

- A release manager can answer which Mac, OS version, package, bridge variants, and manual tests were used for the latest macOS signoff.
- macOS remains experimental if this evidence is absent.

## MAC-002: Architecture Support Decision

Current state:

- Public docs say macOS support is Apple Silicon/arm64 only.
- Release workflows build `macos-arm64-opengl` and `macos-arm64-metal`.
- openQ4 and `../openQ4-game` now have dedicated `macos-15-intel` x86_64 CI jobs in addition to ARM64 jobs; clean hosted results have not yet been recorded for the new jobs.
- Intel CI builds thin x64 outputs and runs assetless renderer/dedicated lifecycle checks, but there is still no Intel release lane, universal2 package, or real Intel gameplay/package/signing evidence.

Gap:

- Intel user-facing support remains deferred rather than silently implied by build-system capability.
- If universal2 is added later, final combined binaries still need post-`lipo` install-name, signing, notarization, and runtime gates.

Tasks:

- [x] Record an explicit architecture policy in `docs/dev/platform-support.md`: `arm64 only`, `x86_64 planned`, or `universal2 planned`.
- [x] If staying arm64-only for now, keep the user docs explicit and add a regression test that prevents accidental Intel/universal2 claims in release-facing docs.
- [x] Document the current architecture policy and expansion requirements in `docs/dev/macos-support-matrix-policy.md`.
- [x] Confirm the current release workflow publishes only `macos-arm64-opengl` and `macos-arm64-metal` package variants.
- [x] Add a standard hosted Intel Mac runner for experimental compile, stage, assetless renderer, and dedicated-module-loader validation.
- [ ] Secure physical Intel Apple hardware or a compliant Intel Mac host for stock-asset gameplay, audio/input/display, package, signing, and Gatekeeper signoff.
- [x] Add `../openQ4-game` macOS x86_64 CI before claiming engine Intel support.
- [x] Add openQ4 macOS x86_64 staged-package validation for both bridge variants.
- [x] Extend package validation to check every executable and dylib slice with `lipo -archs`.
- [x] Add a universal2 runtime module fallback so both executable slices can load one trusted merged SP/MP module pair without changing thin-package behavior.
- [x] Document the universal2 merge, exact-slice, symbol, install-name, inside-out signing, notarization, and dual-architecture evidence contract.
- [x] Implement the fail-closed universal2 merge/assembly job and final-package validator: matched thin provenance, mode-preserving thin artifact transfer, byte-identical shared payloads after validating and normalizing host-dependent MoltenVK ad-hoc signatures, exact dual Mach-O slices, per-slice metadata, final dSYMs, and native assetless dedicated-server smoke are required before CI uploads its evidence.
- [x] Add a non-publishing universal2 candidate gate that can re-run code signing, notarization, stapling, `spctl`, and install-name validation after `lipo` creation when Developer ID mode is selected; hosted and hardware evidence remains pending.
- [ ] Update release artifact naming to distinguish `macos-arm64`, `macos-x64`, and `macos-universal2`.
- [ ] Record clean hosted results for the new openQ4 and `openQ4-game` Intel jobs.

Validation:

- For the arm64-only release line: user docs and release artifact names consistently say arm64 while CI artifacts are explicitly labeled experimental x64 evidence.
- For thin Intel CI: `lipo -archs` reports only `x86_64` for the client, dedicated server, and game dylibs; renderer and dedicated-module assetless smokes pass for both bridge configurations.
- For universal2: `lipo -archs` reports both `x86_64` and `arm64` for the app executable, dedicated server, and game dylibs.
- Runtime signoff passes on both Apple Silicon and Intel hardware if Intel is claimed.

Exit criteria:

- The architecture claim is intentional, documented, and enforced by CI/release validation.

## MAC-003: macOS Version Matrix

Current state:

- Meson sets `-mmacosx-version-min=11.0`.
- Docs state macOS 11 or later as the floor.
- Hosted macOS validation uses current GitHub-hosted macOS images, currently represented by `macos-15` workflows.

Gap:

- There is no evidence that the macOS 11 deployment floor has been runtime-tested.
- There is no explicit policy for validating current and previous macOS releases before promoting support.

Tasks:

- [x] Define the supported OS matrix in `docs/dev/platform-support.md`, such as `macOS 11 floor plus latest public macOS on Apple Silicon`.
- [x] Add an evidence table to the macOS signoff evidence index with OS version, kernel version, Xcode/SDK version, CPU architecture, and bridge variant.
- [x] Add signoff report and evidence-recorder fields for architecture policy, CPU architecture, OS matrix role, Xcode version, and macOS SDK version.
- [ ] Run real-hardware or compliant Apple VM signoff on the oldest supported macOS version before first-class promotion.
- [ ] Run signoff on the latest public macOS version for every release that changes platform, input, audio, renderer, packaging, or loader behavior.
- [x] Decide whether macOS 11 remains the floor after SDL3, Xcode, and package-notarization requirements are reviewed.
- [ ] If the floor changes, update Meson deployment target, `BUILDING.md`, `docs/dev/platform-support.md`, user docs, release README, and workflow validation expectations together.

Validation:

- Built binaries report the expected deployment target.
- Signoff evidence includes both the floor-version result and latest-version result, or the support matrix explains why a version is not covered.
- Docs and release notes all match the Meson deployment target.

Exit criteria:

- The documented macOS version range is not broader than what the project can validate.

## MAC-004: OpenGL Dependency And Metal Bridge Limits

Current state:

- The OpenGL package uses the SDL3/OpenGL path.
- The Metal package is a macOS bridge around the OpenGL renderer path and links Metal/QuartzCore.
- Docs correctly warn that this is not a native Metal renderer.
- Static tests protect Apple OpenGL startup behavior and bridge policy.

Gap:

- Long-term macOS rendering still depends on Apple OpenGL behavior, including macOS 4.1 core limitations and guarded 2.1 compatibility behavior.
- In-game real hardware evidence is still needed for both package variants.

Tasks:

- [x] Keep package names and docs explicit: `OpenGL` and `Metal bridge`, not `native Metal`.
- [x] Add the bridge variant to every macOS signoff result and release evidence entry.
- [ ] Validate both SP and MP in-game rendering on OpenGL and Metal bridge packages.
- [x] Add issue links or plan entries for any renderer features blocked by macOS OpenGL 4.1.
- [x] Decide whether the long-term target is to keep the bridge, use a translation layer, or implement a native Metal renderer.
- [x] If native Metal is chosen, create a separate renderer design plan that covers stock asset compatibility, shader translation, BSE effects, screenshot/readback behavior, performance counters, diagnostics, and fallback behavior.
- [x] Keep `tools/tests/macos_renderer_startup_guard.py` and `tools/tests/macos_metal_bridge.py` updated as renderer policy changes.

Validation:

- Renderer matrix and in-game smoke logs exist for both bridge variants.
- User-facing docs never imply native Metal rendering until a native renderer exists.
- Any new renderer path has parity tests against existing Quake 4 assets and BSE effects.

Exit criteria:

- The project either accepts the OpenGL/bridge architecture as the supported macOS renderer path or has a tracked native Metal migration plan.

## MAC-005: OpenAL Provider And Real Audio Device Behavior

Current state:

- macOS release and validation builds select `-Dmacos_openal_provider=system` with checksum-pinned OpenAL Soft 1.25.1.
- Packages embed and sign `libopenal.1.dylib`, include its LGPL notice and exact source archive, and reject non-package dependencies.
- `docs/dev/archive/2026-10-18/plans/2026-06-24-openal.md` tracks OpenAL reliability work.
- Synthetic tests exist, but physical device switching and hotplug remain a real-hardware validation item.

Gap:

- The Apple-framework capacity failure from issue #122 is addressed by the bundled provider and non-fatal allocation fallback.
- Real device switching, requested device disappearance/return, and hotplug behavior need Apple-hardware proof.

Tasks:

- [ ] Run macOS signoff with the release `system`/OpenAL Soft provider.
- [x] Retain a compile-only `apple_framework` compatibility corridor.
- [ ] Test default output device changes while the game is running.
- [ ] Test physical output hotplug, such as USB headset or HDMI/display audio, where hardware is available.
- [ ] Test requested device removal and return.
- [ ] Verify audio device errors and fallbacks in `logs/openq4.log`.
- [x] Choose bundled OpenAL Soft for release packages based on issue #122 evidence.
- [x] Update package scripts, codesigning/notarization allowlists, dependency validation, install names, license/source payloads, and user docs.
- [x] Update `docs/dev/archive/2026-10-18/plans/2026-06-24-openal.md` with macOS-specific evidence and decision status.

Validation:

- Runtime logs show clean audio startup, device switch handling, and shutdown.
- No package dependency escapes the app/package allowlist.
- If OpenAL Soft is bundled, notarized DMGs still pass `spctl`, `stapler`, and dependency checks.

Exit criteria:

- macOS audio has a chosen release provider, known fallback behavior, and real-device validation evidence.

## MAC-006: Package Layout And Finder Launch UX

Current state:

- macOS package generation moves staged PK4 data into
  `openQ4.app/Contents/Resources/baseoq4` and signed game dylibs into the flat
  `Contents/Frameworks` nested-code location.
- `openQ4.app` is drag-installable without the adjacent loose binaries; loose
  diagnostic/client-server binaries discover the sibling app runtime.
- Package validation checks bundle structure, no-duplication, archive paths,
  architecture, dependencies, deployment floors, install names, nested signing,
  symbols, Finder-style path selection, and DMG integrity.

Gap:

- The self-contained implementation is not yet proven through the required
  Finder, copied-app, mounted-DMG, Gatekeeper, and gameplay checks on real Apple
  hardware.

Tasks:

- [x] Document the intended package layout as a support contract: self-contained app bundle, adjacent package root, or hybrid.
- [ ] Validate launch by double-clicking `openQ4.app` from the mounted DMG.
- [ ] Validate launch after copying the whole package folder to a user-writable location.
- [x] Implement app-only movement with embedded content roots, trusted Frameworks module discovery, loose-binary sibling discovery, and localized damaged-app diagnostics.
- [x] Record trusted module roots and every checked module path on a missing-module failure, then retain that diagnostic in the privacy-filtered support archive.
- [x] Record the selected module and platform-loader rejection when `dyld` cannot load a found module, then retain both diagnostics in the privacy-filtered support archive.
- [ ] Confirm `fs_basepath`, `fs_cdpath`, and `fs_savepath` resolution in `logs/openq4.log` for Finder and terminal launches.
- [x] Put PK4 data under `openQ4.app/Contents/Resources/baseoq4` and Mach-O game modules flat under `openQ4.app/Contents/Frameworks`.
- [x] Update package allowlists, signing/notarization, DMG generation, install-name validation, symbols, support intake, release smoke, release docs, and user docs together.
- [x] Add signoff checklist items for Finder launch from mounted DMG and from copied package.
- [x] Add evidence-index fields for mounted-DMG launch, copied-package launch, app-only move behavior, path-resolution logs, and Gatekeeper assessment.
- [x] Add validation coverage so future signoff archives must include the package UX checklist items.

Validation:

- Runtime logs identify the expected base path, save path, and loaded game dylibs.
- Gatekeeper assessment passes for the final user-facing package.
- The app shows a localized, actionable error if required embedded data or signed modules are missing; complete legacy adjacent packages remain compatible.

Exit criteria:

- A macOS user can install and launch the package using the documented flow without relying on terminal-only behavior.

## MAC-007: Companion Game-Library macOS Support

Current state:

- openQ4 consumes game-library sources from `../openQ4-game`.
- The companion repo has experimental Darwin Meson support with ARM64 and Intel x64 CI jobs configured.
- Standalone `openQ4-game` docs say gameplay validation must happen through the openQ4 engine checkout.

Gap:

- Engine macOS support can only be as strong as the game modules it stages.
- Clean hosted Intel results are not yet recorded, and standalone module success does not prove runtime module loading in packaged openQ4.

Tasks:

- [x] Keep openQ4 staged builds as the release source of truth for game-module validation.
- [x] Add a cross-repo validation note to the macOS evidence index: openQ4 commit, `openQ4-game` commit, staged game dylib names, and install names.
- [x] Verify `@loader_path/game-*.dylib` install names in release validation after every packaging change.
- [x] Add `../openQ4-game` macOS x86_64 CI for the experimental Intel corridor.
- [x] Keep `openQ4-game` README support claims aligned with openQ4 platform support docs.
- [x] Add a small scripted check in openQ4, if practical, that validates staged macOS game dylib names and architecture against the selected package architecture.

Validation:

- Release logs show game module compile and staging from the companion repo.
- `otool -L` and install-name checks pass for staged game dylibs.
- SP and MP both load the correct game dylibs on real macOS signoff runs.

Exit criteria:

- macOS engine, SP game module, and MP game module support claims are synchronized.

## MAC-008: macOS Sanitizer And Instrumentation Coverage

Current state:

- macOS hosted workflows compile and package variants.
- Platform-specific static policy tests are strong.
- `.github/workflows/macos-sanitizer.yml` provides a manual arm64 ASan+UBSan
  matrix for OpenGL and Metal bridge configurations.
- The workflow disables PCH, builds the engine and staged game modules, checks
  their instrumentation, runs an optional-by-input but default-on assetless
  fail-fast smoke, and retains diagnostic artifacts.
- `tools/tests/macos_sanitizer_ci.py` guards this contract in local, commit, and
  push validation.

Gap:

- Obj-C/C++ lifetime bugs, filesystem path issues, loader issues, and macOS-only undefined behavior may escape compile/package CI.

Tasks:

- [x] Add a manual macOS sanitizer workflow for platform-sensitive branches.
- [x] Start with engine and game-library compile coverage and a bounded assetless smoke.
- [x] Disable PCH for sanitizer builds.
- [x] Capture sanitizer, toolchain, build, staging, and runtime logs as artifacts.
- [x] Keep sanitizer runs as manual debug tooling until hosted stability justifies a required lane.
- [x] Document invocation in `BUILDING.md` and `docs/dev/platform-support.md`.
- [ ] Run the manual sanitizer workflow for both bridges and record clean hosted results.

Validation:

- Sanitizer workflow compiles both OpenGL and Metal bridge configurations, or documents why one is sufficient.
- At least one assetless smoke or startup command can run without sanitizer findings if hosted macOS allows it.

Exit criteria:

- macOS-specific memory and undefined-behavior investigations have a repeatable first-party workflow.

## MAC-009: Native macOS Backend Maintenance Policy

Current state:

- SDL3 is the default macOS backend.
- Native macOS fallback code remains isolated and guarded by static tests.
- Carbon is only allowed in the native fallback boundary.

Gap:

- The project has not stated whether the native backend is maintained as a supported fallback, retained only for comparison, or planned for removal.

Tasks:

- [x] Decide the native backend policy: supported fallback, comparison-only, or removal candidate.
- [ ] If supported, add a periodic native-backend build check and minimal launch validation.
- [x] If comparison-only, document that releases use SDL3 and native backend results are diagnostic.
- [ ] If removing, create a separate cleanup plan that preserves any required macOS behavior through SDL3 first.
- [x] Keep static policy tests blocking Carbon and NSOpenGL from leaking into the SDL3 path.

Validation:

- CI or manual docs match the chosen maintenance level.
- No release docs imply native backend support unless it is actively tested.

Exit criteria:

- Native fallback code has a clear ownership and support status.

## MAC-010: Signed/Notarized Release Policy

Current state:

- Credentialed release runs create signed and notarized DMGs.
- Uncredentialed runs create unsigned tarballs.
- Docs disclose the distinction.

Gap:

- If macOS becomes first-class, unsigned artifacts should not be the normal user-facing release path.
- Gatekeeper behavior for unsigned tarballs is support-hostile.

Tasks:

- [x] Decide that first-class macOS releases require signed and notarized DMGs.
- [x] Keep unsigned tarballs only for development snapshots or clearly marked experimental fallback output.
- [x] Add a release workflow gate that fails macOS first-class release jobs when signing/notarization secrets are missing.
- [x] Keep `tools/build/package_nightly.py` entitlement rejection and Hardened Runtime checks mandatory for signed releases.
- [x] Add release-note wording for unsigned development artifacts when they are intentionally published.

Validation:

- Signed DMGs pass `codesign`, `stapler`, `spctl`, and `hdiutil verify`.
- Release artifacts and notes clearly distinguish signed supported packages from unsigned experimental packages.

Exit criteria:

- Users receive a Gatekeeper-compatible package for supported macOS releases.

## MAC-011: Release Evidence And Changelog Gates

Current state:

- `docs/dev/release-completion.md` tracks in-progress release work.
- User-facing curated release notes belong in `docs/dev/releases/vX.Y.Z.md`.
- macOS signoff is listed as a carry-forward release task.

Gap:

- Runtime support evidence is not yet a hard release gate tied to curated release notes and release completion.

Tasks:

- [x] Add a `macOS Evidence` section to the release completion template or current release document.
- [x] Add release-completion and evidence-index fields for run ID, archive checksum, OS version, hardware model, graphics bridges, OpenAL provider, and package artifact names.
- [x] Add `tools/macos/record_signoff_evidence.py` so a validated archive can update the evidence index with those fields.
- [x] Require release notes to call out any macOS support limitation, such as arm64-only, unsigned package, or known renderer/audio issue.
- [x] Add a docs test or release checklist item that fails if first-class macOS notes are written without evidence references.
- [ ] Keep internal investigation details out of public release notes unless they directly help users.

Validation:

- `docs/dev/releases/vX.Y.Z.md` matches the actual tested support level.
- `docs/dev/release-completion.md` links to or records the evidence before release signoff.

Exit criteria:

- macOS support claims in release notes are backed by named evidence.

## MAC-012: Multiplayer Runtime Coverage

Current state:

- Project rules require SP launch tasks for single-player testing and MP launch tasks for multiplayer testing.
- macOS signoff docs call for in-game coverage but do not isolate MP as a separate required path in the gap checklist.
- Commit and push jobs now contain a hosted assetless dedicated-server smoke for both bridge package configurations; a clean hosted result is still pending after publication of the workflow change.

Gap:

- macOS MP can regress independently through menu flows, module loading, input handling, networking setup, or dedicated/client package behavior.

Tasks:

- [x] Add explicit MP steps to `macos-runtime-signoff.md` generation: launch MP package path, load MP game module, enter a local listen or test map flow, and exit cleanly.
- [x] Validate `game-mp_arm64.dylib` loading from the staged package through the new MP listen-server smoke evidence path when signoff runs.
- [x] Add a hosted assetless dedicated-server smoke that loads the staged MP module, reaches an initialized server frame, shuts down cleanly, and retains diagnostics.
- [ ] Validate the dedicated server binary on real Apple hardware with retail assets and load the MP game module far enough to initialize a local server configuration.
- [x] Capture MP logs separately from SP logs in signoff archives.
- [ ] Add MP-specific known issues to release notes when they exist.

Validation:

- Signoff archive includes SP and MP logs.
- Logs show both `game-sp` and `game-mp` module load paths.
- Dedicated server startup is covered or explicitly documented as unsupported for that release.

Exit criteria:

- macOS support is not inferred from SP-only startup.

## MAC-013: Reproducible Hosted Source State

Current state:

- The current local tree passes the macOS static profile, but it is dirty in both the engine and companion GameLibs checkout.
- Public engine revision `a635c622` fails its validation-script-smoke job before macOS jobs start: `filesystem_case_segments.py` requires `Parser_NormalizeIncludeBase`, which is present in the current local source tree but not that public revision.
- Staged payload manifests and hosted debug evidence record both engine and GameLibs commits plus dirty-state fields, so a future hosted artifact can identify the exact source pair it used.

Gap:

- A hosted macOS result from an older or independently cloned source pair cannot prove the current implementation, even when local static checks pass.

Tasks:

- [x] Record engine/GameLibs commit and dirty-state provenance in staged-package and hosted-debug evidence.
- [ ] Commit and publish the matching engine and GameLibs source changes that make the current validation profile pass.
- [ ] Record clean hosted OpenGL and Metal results from the published source pair before treating any hosted macOS result as current evidence.

Validation:

- The validation-script-smoke job passes on the published engine revision.
- Hosted artifacts name the matching engine and GameLibs commits and report clean source state.
- The ARM64 and Intel bridge jobs begin only after that source baseline is green.

Exit criteria:

- Every macOS hosted artifact used for release evidence is reproducible from published, clean engine and GameLibs commits.

## Recommended Work Order

Phase 0: Evidence plumbing

- [x] Create the macOS signoff evidence index.
- [x] Add release-completion fields for macOS evidence.
- [x] Add MP-specific signoff checklist entries.

Phase 0 implementation status:

- [x] Created `docs/dev/macos-signoff-evidence.md` as the current evidence index and completed-evidence template.
- [x] Added a `macOS Evidence Gate` to `docs/dev/release-completion.md`.
- [x] Added `run_mp_smoke` to `tools/macos/guest/openq4-macos-sync-build-test.sh`, producing `renderer-mp-smoke` evidence for `mp/q4dm1`.
- [x] Updated `tools/macos/validate_signoff_archive.py` so accepted signoff archives require `renderer-smoke`, `renderer-mp-smoke`, and `renderer-matrix` for each requested bridge.
- [x] Updated `tools/tests/macos_signoff_archive.py` and `tools/tests/macos_metal_bridge.py` for the new MP evidence contract.
- [x] Added `tools/tests/macos_evidence_plumbing.py` and wired it into local, commit, and push validation.
- [ ] Run the updated signoff workflow on real Apple hardware and record the accepted archive in `docs/dev/macos-signoff-evidence.md`.

Phase 1: Current arm64 support proof

- [ ] Run real Apple Silicon signoff for OpenGL and Metal bridge packages.
- [ ] Complete the manual hardware checklist.
- [ ] Collect and validate the archive with `-RequireCompletedSignoffChecklist`.
- [x] Add the evidence recorder needed to record results and exceptions from a validated archive.
- [ ] Record real hardware results and exceptions in `docs/dev/macos-signoff-evidence.md`.

Phase 1 implementation status:

- [x] Added `tools/macos/record_signoff_evidence.py` to validate completed signoff archives, compute SHA-256, extract bridge reports, summarize hardware/OS/OpenAL/package metadata, and update `docs/dev/macos-signoff-evidence.md`.
- [x] Added hardware profile capture (`system_profiler SPHardwareDataType`) to generated `macos-runtime-signoff.md` reports.
- [x] Updated `tools/macos/validate_signoff_archive.py` so completed signoff archives must include `## Hardware` evidence.
- [x] Added privacy-filtered `logs/renderer-config.txt` support evidence, capturing only renderer/performance cvars from safe saved configs so graphics-setting changes can be compared without collecting a full personal config.
- [x] Added `tools/tests/macos_evidence_recording.py` and wired it into local, commit, and push validation.
- [x] Documented the post-collection evidence recording command in `docs/dev/macos-vm-testing-workflow.md`.
- [x] Updated `docs/dev/release-completion.md` so the macOS evidence gate requires the recorder step.
- [ ] Run `tools/macos/Invoke-openQ4MacOSWorkflow.ps1 -Action Signoff -MacOSGraphicsBridge both` on real Apple Silicon hardware.
- [ ] Run `tools/macos/Invoke-openQ4MacOSWorkflow.ps1 -Action CollectResults -MacOSRunId <id> -MacOSGraphicsBridge both -RequireCompletedSignoffChecklist`.
- [ ] Run `python tools/macos/record_signoff_evidence.py .tmp/macos-vm/results/openq4-macos-results-<run-id>.tar.gz --version vX.Y.Z --update-index` with final package artifact and release-note metadata.

Phase 2: Audio decision

- [x] Select and package pinned OpenAL Soft; retain Apple OpenAL only for compile diagnostics.
- [x] Update package validation, attribution, source distribution, and provider docs.
- [ ] Run OpenAL Soft real-device, device-switch, hotplug, and long-session tests.

Phase 3: Package UX and release policy

- [ ] Validate Finder, mounted-DMG, copied-package, and terminal launch flows.
- [x] Decide whether the app bundle remains adjacent-layout or becomes self-contained.
- [x] Require signed/notarized DMGs for first-class macOS releases.

Phase 3 implementation status:

- [x] Recorded the self-contained contract and release requirements in `docs/dev/macos-package-layout-and-release-policy.md`.
- [x] Migrated `openQ4.app` to a self-contained client contract with data in `Contents/Resources`, code in `Contents/Frameworks`, and no duplicated adjacent `baseoq4` payload.
- [x] Retained a compatibility fallback for complete older adjacent packages and added localized diagnostics for damaged embedded runtimes.
- [x] Updated the macOS VM/signoff workflow and generated signoff reports with mounted-DMG, copied-package, terminal, app-only move, path-resolution log, and Gatekeeper checklist items.
- [x] Updated `docs/dev/macos-signoff-evidence.md` and `tools/macos/record_signoff_evidence.py` so accepted evidence records those package UX fields.
- [x] Updated the manual release workflow with `macos_support_tier=first-class`, which fails when Apple Developer ID signing or notarization secrets are missing.
- [x] Updated `BUILDING.md`, `docs/dev/platform-support.md`, `docs/user/getting-started.md`, `assets/release/README.html`, and `docs/dev/release-completion.md` with the self-contained-app and signed/notarized first-class release policy.
- [ ] Run the updated package UX checklist on real Apple hardware for both OpenGL and Metal bridge packages.
- [ ] Record the real mounted-DMG, independently dragged-app, whole-package loose-tool, embedded resource/module path, path-resolution, and Gatekeeper results in `docs/dev/macos-signoff-evidence.md`.

Phase 4: Matrix expansion

- [x] Decide architecture policy for Intel/universal2.
- [x] Decide OS-version validation policy for the macOS 11 floor and latest public macOS.
- [x] Add guardrails for the current arm64-only matrix and floor/latest evidence fields.
- [x] Add runners, build lanes, and validation only for support claims the project is ready to make.

Phase 4 implementation status:

- [x] Added `docs/dev/macos-support-matrix-policy.md` to define the current `arm64 only` macOS release policy, unsupported Intel/universal2/Rosetta paths, and the requirements for future matrix expansion.
- [x] Updated `docs/dev/platform-support.md`, `BUILDING.md`, `docs/user/getting-started.md`, `assets/release/README.html`, and `docs/dev/release-completion.md` so macOS release-facing claims match the current Apple Silicon/arm64, macOS 11+, experimental matrix.
- [x] Added `-MacOSOSMatrixRole` to `tools/macos/Invoke-openQ4MacOSWorkflow.ps1` and `OPENQ4_MACOS_OS_MATRIX_ROLE` to the guest signoff script so floor-candidate, latest-public-macOS, hosted-CI, and manual-current runs can be recorded deliberately.
- [x] Updated signoff report generation, archive validation, and evidence recording so accepted archives include architecture policy, CPU architecture, OS matrix role, Xcode version, and macOS SDK version.
- [x] Added `tools/tests/macos_matrix_policy.py` and wired it into local, commit, and push validation to prevent accidental Intel/universal2 claims and to keep floor/latest evidence fields present.
- [x] Added separate `macos-15-intel` OpenGL/Metal engine jobs and a matching companion GameLibs job, with thin-slice/floor/install-name checks plus assetless renderer and dedicated-module lifecycle coverage while keeping user-facing releases arm64-only.
- [x] Added a manual non-publishing macOS universal2 candidate workflow that builds matched ARM64/Intel inputs, creates evidence artifacts for both bridge variants, and can perform final Developer ID signing, notarization, stapling, Gatekeeper, and per-slice install-name validation without publishing a release.
- [ ] Record passing hosted results for the experimental Intel engine and GameLib jobs.
- [ ] Run oldest-supported-version signoff with `-MacOSOSMatrixRole floor-candidate` on macOS 11 or update the documented floor before promotion.
- [ ] Run latest-public-macOS signoff with `-MacOSOSMatrixRole latest-public-macos` for the release candidate before promotion.
- [ ] Intel release expansion remains deferred until the configured hosted jobs pass and real Intel gameplay, package, signing/notarization, Gatekeeper, and architecture-specific runtime signoff exist; universal2 additionally requires a final combine-and-resign lane.

Phase 5: Renderer and backend future

- [x] Keep OpenGL/Metal bridge support honest and validated.
- [x] Create a separate design plan if native Metal becomes a target.
- [x] Decide the maintenance status of the native macOS fallback backend.

Phase 5 implementation status:

- [x] Added `docs/dev/macos-renderer-backend-policy.md` to define the current SDL3/OpenGL renderer release path, the Metal bridge wording contract, Apple OpenGL risk, the native Metal design gate, and native Cocoa/OpenGL backend maintenance policy.
- [x] Decided that the current release line keeps the OpenGL renderer plus Metal bridge package rather than choosing a native Metal renderer.
- [x] Documented that a future native Metal renderer requires a separate design plan covering stock asset parity, shader translation, BSE effects, screenshot/readback behavior, diagnostics, performance counters, and fallback behavior before implementation.
- [x] Decided that the native Cocoa/OpenGL backend is comparison-only diagnostic infrastructure, not a supported release backend.
- [x] Added a Meson warning when macOS `platform_backend=native` is selected so local comparison builds do not look like release coverage.
- [x] Updated `BUILDING.md`, `docs/dev/platform-support.md`, `docs/dev/archive/2026-10-18/sdl3-linux-macos-migration.md`, `docs/dev/macos-vm-testing-workflow.md`, `docs/dev/macos-signoff-evidence.md`, `docs/user/getting-started.md`, `assets/release/README.html`, `README.md`, and `docs/dev/release-completion.md` with the renderer/backend policy.
- [x] Added `tools/tests/macos_renderer_backend_policy.py` and wired it into local, commit, and push validation.
- [ ] Run real Apple-hardware OpenGL and Metal bridge SP/MP signoff before promoting macOS renderer support beyond experimental.
- [ ] Create a native Metal renderer design plan only if the project explicitly chooses native Metal as a target.
- [ ] Add dedicated native-backend build/package/runtime lanes only if the project decides to support `platform_backend=native` for releases.

## Definition Of Done For First-Class macOS Support

- [ ] `docs/dev/platform-support.md` states the exact architecture and OS-version support matrix.
- [ ] `BUILDING.md`, `docs/user/getting-started.md`, release README, and release notes match that matrix.
- [ ] Signed and notarized DMGs are produced for supported user-facing macOS releases.
- [ ] Real Apple-hardware signoff passes for OpenGL and Metal bridge packages.
- [ ] Signoff includes SP, MP, Finder launch, terminal launch, audio, input, fullscreen/windowed, HiDPI, and package-layout checks.
- [ ] The signoff archive validates with `--require-completed-checklist`.
- [ ] Audio provider policy is decided and validated.
- [ ] Game-library staging from `../openQ4-game` is recorded and verified.
- [ ] Unsupported scenarios, such as Intel Macs or native Metal rendering if not implemented, are stated plainly.
- [ ] Release notes include macOS limitations and required user actions.
