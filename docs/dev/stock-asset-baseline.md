# Retail-PK4 Compatibility Baseline With Packaged openQ4 Overlays

[`stock_asset_baseline.py`](https://github.com/themuffinator/openQ4/blob/master/tools/validation/stock_asset_baseline.py) is the authoritative P0 capture harness for Quake 4 retail-asset compatibility. It binds an evidence run to the exact retail PK4 bytes and approved-manifest file, selected client, packaged renderer modules, SP/MP game modules, other packaged shared libraries, openQ4 overlay packages, current openQ4 Git revision and dirty-state policy, the versioned per-map renderer budget contract, logs, saves, demos, engine-rendered screenshots, and measured CPU/GPU frame percentiles.

This is not an overlay-free or “stock-only” execution claim. `baseoq4` is the active game directory and its packaged openQ4 PK4s take normal virtual-filesystem precedence over the verified retail `q4base`/`q4mp` fallback. The report preserves both facts: retail archive bytes must match the separately approved manifest, while every packaged-overlay member that supersedes a retail virtual path is inventoried and counted.

The harness is deliberately non-interactive:

- every real evidence client is forced to the versioned bordered-window
  1280x720 display contract: `r_fullscreen 0`, `r_borderless 0`, the legacy
  migration guard, non-desktop fullscreen policy, and matching window/custom
  dimensions; runtime `MODE` output and engine-written TGA dimensions must
  independently confirm that exact workload;
- map actions are registered console commands in generated cfg files;
- images are produced by the engine `screenshot` command from the render target;
- it does not call an operating-system capture API;
- it does not control, inject, or capture mouse or keyboard input;
- every role uses an isolated save path below the chosen evidence directory.
- the staged package is mounted through the engine's working-directory
  `fs_cdpath`, while writable `fs_devpath` output is confined to that role's
  isolated evidence tree.

## Evidence sequence

| Role | Automated evidence |
|---|---|
| SP capture | Loads stock `game/storage1`, records a render demo, takes a full-size engine screenshot immediately before writing `StockBaselineSP`, loads that save, waits for an active restored draw, emits renderer/frame-pacing information plus the versioned OpenGL CPU/GPU timing marker, enforces the exact per-map budget row, and takes a separate post-load engine screenshot. |
| SP demo playback | Reopens the recorded demo with `timeDemoQuit`; a completed timedemo line and clean exit prove that the recorded stream can be read, not merely that a file exists. |
| MP server | Starts a windowed pure `mp/q4dm1` listen server, accepts the loopback run, records a demo, emits diagnostics and the versioned OpenGL CPU/GPU timing marker, enforces the server's exact per-map budget row, and takes an engine screenshot. |
| MP client | Connects through IPv4 loopback with the existing archived `ui_autoJoin 1` userinfo setting, proves the local player is in-game and neither spectating nor requesting spectate, proves the session GUI is closed and the HUD is enabled, records a demo, emits the versioned OpenGL CPU/GPU timing marker, enforces the client's exact per-map budget row, and takes its own gameplay screenshot. |

Each role must exit normally, reach its explicit completion marker, avoid the harness's blocking diagnostic denylist, and produce non-empty expected artifacts. That denylist is limited to fatal errors, line-start engine `ERROR` records, shader compile/program-link failures, Vulkan validation messages or VUIDs, and OpenGL errors. Other warnings are retained in the evidence but do not by themselves fail the baseline, so an automated pass is not a warning-free-log claim. The MP client also requires exact active-player proofs on both sides of the screenshot; those proofs include closed game/session menu state and an enabled HUD, so a joined player hidden behind the JOIN GAME screen cannot pass. TGA screenshots must fully decode, contain an exact uncompressed 24/32-bit payload, exactly match the renderer dimensions recorded by `gfxInfo`, and avoid blank or recursive scaled-strip corruption. The SP save preview is held to the same pixel-content checks and the retail 320x240 dimensions. It must also remain visually coherent with the full-size engine screenshot issued immediately before `saveGame`, while simulation state is unchanged. The later post-load screenshot remains separately required and proves that the restored game reaches a renderable gameplay frame; it is deliberately not the preview-comparison reference because the validation waits and renderer measurements allow the live scene, vehicle pose, and effects to advance. The harness centre-aspect-crops and bilinearly downsamples the same-state reference and preview to 80x60, then requires a luma correlation of at least 0.75. For the secondary colour check, it fits one shared, bounded affine exposure transform from preview luma to reference luma (gain 0.25–4.0 and bias -192–192), applies that same transform to all three colour channels, and requires the remaining mean absolute RGB error to be no greater than 48. A single shared transform tolerates capture-path exposure and contrast changes without concealing an arbitrary per-channel colour defect. Raw RGB error, fitted exposure parameters, and compensated error are all recorded for review. The combined correlation, colour, and recursive-strip gates deliberately permit modest post-process differences while rejecting structurally valid feedback/recursion captures. The report hashes every artifact with SHA-256.

The 2026-08-19 Milestone A development capture exercised report schema 10 and
passed all four roles plus immediate `--verify-report` replay. It retained the
canonical 1280x720 display contract, versioned CPU/GPU budget rows, pure MP and
`ui_autoJoin 1` proofs, save/demo lifecycle, and artifact hashes. Local human
review found the SP before/after images and save preview coherent, and both
`mp/q4dm1` roles showed active gameplay with the HUD rather than the join menu.
This is current-build evidence only: it came from an immutable development
runtime staged from an uncommitted source tree, so it is not the clean-source,
freshly staged final-package bundle required for release promotion.

Both MP roles explicitly launch with `ui_autoJoin 1`. This follows the normal
game userinfo/server-policy path and avoids automating menu input. All openQ4
MP validation should keep auto-join enabled unless the subject of the test is
the join menu or the initial spectator/join flow itself. Such a test must set
`ui_autoJoin 0` explicitly rather than relying on omission because the CVar is
archived.

The MP server also runs with the normal `si_pure 1` policy and with
`net_serverAllowServerMod 0`. A baseline therefore has to complete the real
pure-PK4 negotiation; disabling pure mode or using the legacy server-mod escape
hatch cannot produce promotable compatibility evidence.

Before reporting success, the harness re-hashes the retail assets, staged
runtime and overlays, and all captured artifacts. It also recomputes the SP
save-preview comparison against the same-state pre-save screenshot and requires
the recorded reference artifact, algorithm, thresholds, and metrics to match,
so updating an image's recorded hash cannot hide an incoherent preview. A run that mutates the staged
package or any other recorded input therefore fails in the same invocation.

The default `stock-baseline-targets-v1` contract is stored at
`tools/validation/renderer_per_map_budgets.json`. Its repeated 20 ms P95 / 28
ms P99 CPU and GPU values are initial cross-map baseline target ceilings, not
claimed measurements. Every evidence result records the selected contract row,
minimum samples, ceilings, exact timing marker, and measured CPU/GPU P50/P95/P99
values so results from this machine remain distinguishable from universal
release qualification and confirmed rows can be tightened without changing
the schema. Required GPU timing is fail-closed: unavailable, insufficient,
malformed, duplicate, identity-mismatched, or over-budget samples cannot
produce a passing stock report.

Passing budget evidence is comparable only at the canonical bordered-window
1280x720 workload. Non-dry captures reject other `--width`/`--height` values,
and report replay rejects a changed display contract, non-windowed or
non-1280x720 runtime `MODE` evidence, and screenshots whose decoded TGA size is
not exactly 1280x720. Custom sizes remain available only for dry planning and
do not produce promotable budget evidence.

`--verify-report` fails closed unless the report represents a real capture
(`dryRun` is exactly `false`), every top-level and per-role failure array is
empty, the bound expected-assets file still exists at its recorded absolute
path and has its recorded SHA-256, and that manifest's retail inventory matches
the report. It resolves the explicitly selected/default budget contract,
requires its stable id/schema/SHA-256 to match the portable report binding, and
recomputes each role's measurements and thresholds from the hashed diagnostic
streams. A changed marker, map/backend/profile, sample count, threshold,
contract byte, runtime byte, or recorded measurement fails replay. The verifier
also requires the recorded openQ4 HEAD and dirty flag
to match the current checkout under the named provenance policy. A dirty flag
records only that uncommitted changes exist; it is not a fingerprint of those
changes, so promotion evidence should come from a clean checkout.

Capture and dry-run output directories must be new or empty. The harness will not reuse earlier logs, screenshots, saves, or demos. Both process streams are captured and hashed even when empty; report verification requires the exact four roles, their lifecycle fields, completion markers, artifact kinds and paths, and unchanged engine log/stdout/stderr bytes. It reconstructs and compares the complete canonical argument list for every role, including `fs_game`, SP map/game type, MP listen map/game type/dedicated mode, loopback connection, `ui_autoJoin 1`, and pure/server-mod policy. The per-role engine logfile is authoritative for ordered lifecycle markers and MP screenshot-bracketing proofs. This avoids false duplicate-proof failures on POSIX builds that mirror identical engine diagnostics to stdout; stdout and stderr remain independently hashed and all three channels are scanned for the same blocking denylist described above, while general warnings remain review evidence rather than automatic failures.

The timeout is applied independently to each SP role. Multiplayer uses one absolute timeout deadline beginning when the listen server is launched; the server and loopback client are monitored together and any roles still running at that deadline are terminated together. The client-start delay consumes part of that shared MP budget rather than granting either process a second sequential timeout.

## Run it

List the fixed cases and safety invariants without touching assets or launching:

```text
python tools/validation/stock_asset_baseline.py --list
```

First create a PK4-only view. A normal Steam tree is not suitable because saves,
generated collision caches, extracted maps, or mod files can override the retail
archives even when every loose byte is hashed:

```powershell
$source = "C:\Program Files (x86)\Steam\steamapps\common\Quake 4"
$assetRoot = ".tmp\stock-assets-pk4-only"
New-Item -ItemType Directory -Force "$assetRoot\q4base", "$assetRoot\q4mp"
Copy-Item "$source\q4base\*.pk4" "$assetRoot\q4base\"
Copy-Item "$source\q4mp\*.pk4" "$assetRoot\q4mp\"
```

Write the complete plan and the separately reviewed expected-assets manifest
without launching the game:

```text
python tools/validation/stock_asset_baseline.py --dry-run --asset-root .tmp\stock-assets-pk4-only --output-dir .tmp\stock-baseline\approved
```

Capture the baseline. Every non-dry capture must bind to an approved manifest
from the same retail edition/language set; a missing binding, archive mismatch,
or loose q4base/q4mp file fails before openQ4 launches:

```text
python tools/validation/stock_asset_baseline.py --asset-root .tmp\stock-assets-pk4-only --expected-assets .tmp\stock-baseline\approved\stock_pk4_manifest.json --budget-contract tools\validation\renderer_per_map_budgets.json --output-dir .tmp\stock-baseline\candidate
```

By default the harness hashes and launches the canonical repository `.install`
package. If that directory is occupied by an unrelated running test, stage one
fresh, ordinary alternate package below `.tmp/stock-runtime/` with the canonical
fast-staging tool, then name that exact directory explicitly for capture and
verification:

```text
python tools/build/stage_fast_install.py --build-dir builddir --install-dir .tmp/stock-runtime/current-build --temporary-runtime
python tools/validation/stock_asset_baseline.py --runtime-dir .tmp/stock-runtime/current-build --asset-root .tmp/stock-assets-pk4-only --expected-assets .tmp/stock-baseline/approved/stock_pk4_manifest.json --output-dir .tmp/stock-baseline/candidate
python tools/validation/stock_asset_baseline.py --runtime-dir .tmp/stock-runtime/current-build --asset-root .tmp/stock-assets-pk4-only --verify-report .tmp/stock-baseline/candidate/stock_asset_baseline_report.json
```

Temporary staging refuses an existing destination, links/junctions, or a path
outside `.tmp/stock-runtime/`. The report and runtime manifest record its
resolved root, and every collector, launch working directory, post-capture
rehash, and later verifier uses that same root. This proves the recorded current
build against verified retail assets plus its packaged openQ4 overlays; it does not replace the separate release-packaging
gate that restages and validates canonical `.install`.

Re-hash an existing report's retail assets, bound expected-assets manifest, openQ4 runtime/overlays, current source provenance, exact launch contract, and recorded artifacts without launching. Keep the evidence directory and expected-manifest file at their recorded absolute locations and verify from the same openQ4 HEAD/dirty state:

```text
python tools/validation/stock_asset_baseline.py --asset-root .tmp\stock-assets-pk4-only --verify-report .tmp\stock-baseline\candidate\stock_asset_baseline_report.json
```

The output directory contains:

- `stock_asset_baseline_report.json`: full machine-readable plan, identities, results, artifact hashes, compatibility model, retail/overlay path-collision inventory, portable budget-contract binding, per-role thresholds, and measured CPU/GPU percentiles;
- `stock_asset_baseline_report.md`: concise reviewer report, collision counts by packaged overlay, and manual gates;
- `stock_pk4_manifest.json`: portable retail PK4 identity manifest;
- `openq4_runtime_manifest.json`: resolved runtime root plus the selected client, dedicated server, diagnostic symbols, all packaged renderer/game modules and shared libraries, overlay PK4s, and loose overlay files;
- `savepaths/`: isolated cfg files, engine logs, screenshots, demos, and saves;
- per-role stdout/stderr text.

The retail manifest hashes every top-level `.pk4` under `q4base/` and `q4mp/`; any loose non-PK4 file is a hard failure. It establishes byte identity with the separately supplied approved manifest; by itself it does not establish ownership or authenticity. The runtime manifest separately hashes the selected client, dedicated server, diagnostic symbols, every packaged dynamic library under the recorded runtime root (including renderer modules, both game modules, and packaged dependencies such as OpenAL), every top-level `baseoq4/*.pk4`, and every loose file recursively visible under its `baseoq4/`. The verifier opens the retail and packaged-overlay PK4s as ZIP archives, compares their case-insensitive idTech virtual paths, and requires the recorded path-by-path collision inventory and count to match the current packages.

The baseline fixes `r_renderApi gl`, `r_rendererBenchmarkPreset baseline`, and backend-neutral whole-frame GPU timestamps; requires the OpenGL renderer module on non-macOS packages; and records any additional packaged renderer module. Vulkan per-map evidence is captured separately with the renderer gameplay benchmark because this compatibility baseline intentionally has one fixed backend launch contract. Only the SP/MP modules, their top-level Windows symbol sidecars, and `mod.json` may be loose below the recorded runtime's `baseoq4/`; any other loose overlay file fails preflight before launch. Symbol sidecars are hashed but are not VFS game content. This prevents an unreported map, material, GUI, or script from weakening the declared retail-fallback-plus-packaged-overlay model.

The harness fails closed when the supplied asset root has a non-empty `baseoq4/` directory. With `fs_game=baseoq4`, that second asset-root overlay would silently alter the explicitly inventoried precedence model. Use a clean retail fallback view containing only top-level retail PK4s in `q4base/` and `q4mp/`. The tool rejects every loose retail file, and by default rejects links at or inside those trees so recursive inventory cannot be bypassed.

A boundary junction is accepted only with explicit opt-in and only when its
resolved directory has already been made PK4-only. Never junction the normal
Steam q4base/q4mp directories: loose generated or extracted files in those
trees take precedence over shipped archive members.

```powershell
python tools/validation/stock_asset_baseline.py --allow-asset-dir-links --asset-root .tmp\stock-assets-linked-pk4-only --expected-assets .tmp\stock-baseline\approved\stock_pk4_manifest.json --output-dir .tmp\stock-baseline\candidate
```

The explicit flag permits links only at the `q4base`/`q4mp` boundary. Their resolved targets are recorded in the JSON, Markdown, and retail manifests; links nested inside either content tree and every loose file still fail closed.

## Promotion gate

An automated `pass` establishes the artifact and lifecycle contract only. Before using a bundle as the release baseline, a reviewer must still:

1. inspect the engine screenshots for black frames, broken materials, missing effects, bad UI/subviews, and obvious shadow or post-process failures;
2. play representative SP and MP sequences to assess input, audio, scripting, collision, prediction, and subjective presentation;
3. capture from a clean source checkout, then retain the approved JSON report and PK4 manifest with the tested binary or immutable build identifier;
4. verify the final, freshly staged release package rather than treating a debug/development staging tree as release proof;
5. record platform/driver coverage separately rather than treating one host as universal qualification.

The broader renderer visual/performance promotion rules remain in the [renderer validation matrix](renderer-validation-matrix.md). This P0 harness is the compatibility identity and lifecycle baseline, not a replacement for renderer-specific image references or target-hardware performance evidence.
