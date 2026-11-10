# External settings refresh and queued value ownership

23 October 2026. Bounded UI-01/UI-09 completion on the
[development roadmap](../roadmap.md#new-user-interface). This increment fixes
SYSTEM's stale external-preset readback and protects queued value controls when
their starting values change. It does not accept a complete page, migration
resource or final product gate.

## Behavior

`SettingsTransaction::Refresh` observes the complete typed host catalog while
the owning session is editing. If the draft is clean, it publishes the new
baseline and draft together. It retains exact custom values, including values
outside normal editor ranges, as opening the page already does. The observation
performs no setting writes, validation-driven normalization, device work or
configuration persistence.

If the draft is dirty and the host changed, both original snapshots stay intact.
SYSTEM displays its existing localized external-change message and disables
Apply. It does not merge unrelated external changes into a potentially coupled
draft. Discarding or reopening starts from the actual live values. Apply still
checks the host independently before writing, so calling it directly cannot
bypass the conflict.

Failed reads, changed catalog types and invalid values preserve the previous
snapshots. A later successful read recovers automatically. Refresh does not erase
an earlier operation's error. Foreign, closed and retired owners cannot refresh;
confirmation, application, restoration, startup recovery and closing retain
their existing ownership and original recovery baseline.

The service refreshes before publishing normal page readback, which also occurs
before queued controls dispatch. An unfinished local numeric editor keeps its
text and gains a conflict when its bound value changes; it continues to block
Apply/dismissal until explicitly resolved or discarded.

The document regression exposed a related shared-toolkit gap: choice, slider
and toggle actions previously checked control eligibility but not their starting
values. Each queued proposal now retains its starting value and mixed state.
Dispatch requires matching current readback and the same pending sequence.
Sequential changes remain ordered: each step becomes eligible when its
predecessor's actual result arrives. Failed or externally invalidated steps
cannot overwrite a newly observed value. Choice dispatch also rechecks the
option's availability and counted-list length. Numeric proposals retain their
existing editor-session/revision checks. These transient guards do not change
document or save formats.

## Validation

The source and binary identities, commands, native logs and engine captures are
bound in `.tmp/ui-completion/validation-evidence.json`. The implementation starts
from `56a74bd48` and is identified by the file hashes in that record.

- The added production-service regression fails on the original implementation
  at clean external readback. With the fix, all 110 production-body service
  scenarios pass, including dedicated stubs, persistence and recovery guards.
- Eleven Meson suites pass: settings transaction, exact values, display and
  journal; SYSTEM presets; numeric runtime and commands; value interaction and
  runtime; modal interaction and runtime. The actual SYSTEM/RmlUi suite includes
  seven languages, expanded glyph widths and resize/density cases. Its new
  queued-preset regression also failed before the shared dispatch repair.
- Native controls cover ordered pending toggles, mixed-state changes, stale
  sliders, disabled/removed choice options, completed sequences, malformed
  reads, foreign owners and pending effects. The actual page preserves an
  unfinished numeric buffer and requires explicit conflict resolution.
- Windows debugoptimized SP/OpenGL on `game/airdefense1` and MP/Vulkan on
  `mp/q4dm1` use the staged `.install` executable and matching modules, installed
  stock assets, hidden 1280x720 windows and isolated writable profiles. Each run
  enters gameplay before opening the normal Session SYSTEM child. Nine stages
  cover Balanced/Minimum/Ultra, two video restarts, language reload, dirty draft
  conflict, discard/reopen and local numeric conflict/resolution. Each stage
  has nine ordered readbacks and an engine-render-target screenshot.
- The capture oracle has negative controls for stale labels/baselines, erased
  drafts, incorrect availability, lost numeric text, wrong mode/menu route and
  missing/reordered/duplicate evidence. Renderer identity comes from the loaded
  module, not the requested CVar.
- The immutable-Git checkpoint audit passes against the starting revision. It
  preserves all 349 requirement rows, 358 migration variants and seven final
  gates; the five affected requirements remain partial. Its report is
  `.tmp/ui-completion/register-audit-final.json`.

The capture script uses registered semantic diagnostics and `screenshot`; it
does not control OS mouse/keyboard input or use OS screen capture. Reproduction:

```powershell
python tools/ui/capture_system_refresh.py --mode sp --renderer gl --assets 'E:/SteamLibrary/steamapps/common/Quake 4' --output .tmp/ui-refresh-sp
python tools/ui/capture_system_refresh.py --mode mp --renderer vulkan --assets 'E:/SteamLibrary/steamapps/common/Quake 4' --output .tmp/ui-refresh-mp
```

Use new evidence directories and re-stage after rebuilding. The harness checks
staged binaries against the current standard build directory and binds the
effective packaged SYSTEM document.

## Limits and unrelated findings

The capture matrix reports no errors. It retains the known player-model
precache warning in SP and 95 MP warnings, including the existing missing AAS
and stock-sound warnings. A fresh worktree also needed the repository's existing
OpenAL DLL copied into its ignored dependency location before staging; no new
dependency or release asset was introduced.

These checks do not qualify physical input, other platforms, full audio/resource
or mixed-effect preset execution, every settings page, the visual editor, or
UI-07 CPU/GPU budgets. Identical external values remain indistinguishable from
an unchanged synchronous host, as the transaction contract already states.
`BEH-002`, `FLOW-002`, `WID-005`, `WID-017` and `WID-018` gain bounded evidence;
their statuses and all migration/final acceptance remain unchanged.
