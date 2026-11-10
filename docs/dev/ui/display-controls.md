# SYSTEM display controls

17 September 2026. This increment adds fullscreen, borderless, fullscreen policy
and MSAA controls to the opt-in retained SYSTEM page. It contributes to the
partial `BEH-002` and `FLOW-002` requirements; no screen, milestone, migration
or final gate is accepted.

## Implementation and boundaries

The four controls reuse SYSTEM's editable vector artwork and existing typed
settings catalog. Fullscreen and borderless are toggles; fullscreen policy
selects desktop or exclusive behavior, and MSAA lists Off, 2x, 4x, 8x and 16x.
Labels come from the existing six language tables. The MSAA option string is
derived from each language's existing legacy options, removing their legacy
quote delimiters.

Selection changes an owned draft only. Apply uses the existing asynchronous
display service, strict device validation, Keep/Revert confirmation, durable
recovery and protected Apply-and-exit path. Highlighting or canceling a choice
does not change the draft, and document recreation reads the current service
state without replaying operations. The new column flows with the existing
responsive page and scroll body.

MSAA availability is a read-only observation of the active renderer and its
ready window/presentation state. An unavailable renderer disables the control,
and the service refuses a changed nonzero MSAA draft before writing settings or
preparing a restart. The OpenGL family multisamples its window: a display Apply
requests `r_multiSamples` samples for it, and the strict path verifies the
actual count, so a count the device lacks fails and reverts. Vulkan presents
through a single-sample swapchain and multisamples its scene render targets
instead, so on Vulkan the display request always asks for a single-sample
window, whatever `r_multiSamples` holds. The successful device restart, before
Keep or Revert, destroys Vulkan's backend scene target, which the next view
rebuilds from `r_multiSamples`, and advances `videoRestartCount`, which makes
single-player rebuild its forward target; a Revert restarts the device again.
On Vulkan the strict check therefore proves the restarted window, not the
scene's sample count. That count is the highest the GPU supports up to the
request, and never above 8x, exactly as after `vid_restart`; `gfxInfo` reports
it (`Renderer AA: MSAA requested=N effective=M reason=vulkan-scene`). Until 3
October 2026 the page sent `r_multiSamples` to Vulkan as a window request,
which Vulkan's strict device initialization refuses: every display Apply on
Vulkan failed and reverted while MSAA was on, and the control stayed disabled
there. Unavailable MSAA is visibly dimmed while its label and current value
remain readable; availability restores normal opacity. The 45% group opacity
combines with the existing 88% label paint to give approximately 40% label
opacity, matching the visual specification's disabled-text baseline. Unchanged
observed MSAA does not prevent an unrelated immediate edit, and the service
permits a request to disable MSAA. The choices do not promise that every GPU
supports every listed count. Windows/NVIDIA Vulkan runs applied and kept a
V-Sync change under 4x, 4x to off and off to 8x (16x renders at 8x); no Linux
or macOS runtime qualification is claimed.

The first recovery run exposed a separate timing defect. The controller based
its 20-second first-presentation deadline on the frame timestamp from before a
blocking renderer restart. A sufficiently slow reload could consume that
entire interval before the owning confirmation view appeared; restoration
used the same stale timestamp. The engine now supplies its existing monotonic
clock to the controller, which samples it after a successful restart returns.
Apply and restoration receive a fresh, bounded presentation window. Invalid,
regressing, overflowing or throwing clock observations retain recovery
ownership. The 20-second readiness limit, fresh owner/presentation checks and
15-second user confirmation remain unchanged.

The settings service now builds the display, resolution and refresh lists
([SYSTEM display lists](system-display-catalog.md)). That page records two
deliberate departures: display names are cut to 48 code points, and the
refresh list does not add the desktop rate to every size. Display Device and
Expand Across Displays read the lists ([SYSTEM display rows](system-display-rows.md)),
and so do Display Resolution and Refresh Rate
([SYSTEM resolution rows](system-resolution-rows.md)). The full SYSTEM
migration still needs typed entry in the size fields, dependent-setting
presentation, Defaults, complete effect/preset execution, complete artwork and
motion qualification, and the editor round trip. Visible fullscreen,
borderless, window-manager and multiple-monitor behavior require separate
qualification. The automated engine probes keep fullscreen and borderless off
on the actual window throughout; their toggle checks only stage and discard
draft values.

## Qualification

Evidence and the initial rejected tests/captures are retained under
`.tmp/ui/display-controls/`. The final page and native binaries pass 36
display-control cases (63,640 checks) and 84 text-layout cases (254,739 checks)
across six languages and two counted glyph-width models. Coverage includes
640x480 at 200% text, 1280x720 at 125% interface size, and ultrawide output at
200% interface/text sizes. Draft proposals, acknowledgment, cancellation,
context recreation, modal guards, capability loss and restored opacity are
checked against the real Runtime and production document. Counted font widths
stress layout; they do not establish native shaping or physical input behavior.

The controller passes 983 checks with both MSVC and Clang, including a
simulated 60-second restart and exact deadline behavior. Three compiled
mutations reject stale Apply timing, stale restoration timing and omitted
completion-clock validation. The service passes 91 production-body scenarios,
and the engine display host passes 441 checks. The base capture oracle passes
18 tests and rejects 1,316 corruptions; the display extension rejects another
592 corruptions for each backend. Seven authoring generators, the complete
engine build and runtime staging pass.

Final SP/OpenGL and MP/Vulkan captures pass directly with the final document:
25 stages and ten reviewed engine screenshots each, with three real renderer
restarts per run. Both use hidden 1280x720 windows, 125% interface size and
200% text; OpenGL uses French and Vulkan uses English. The flows enter
`airdefense1` and `mp/q4dm1`, stage/discard fullscreen and borderless, and
exercise Apply, Revert, Keep-and-exit, reopening, archived configuration and
recovery-journal cleanup. OpenGL observes MSAA 0 -> 2 -> 0 -> 2; Vulkan keeps
MSAA at zero and visibly unavailable. Both verify fullscreen-policy and VSync
drafts through confirmation and restoration while the actual window remains
windowed. Labels, values, focus, footer actions and confirmation controls fit
in all 20 reviewed images. Four images show the existing parent menu only;
they qualify return routing, not its visual migration.

OpenGL is warning-free. Vulkan retains 94 reviewed baseline warnings plus two
expected cache-initialization warnings for the two additional renderer
restarts; there are no unexplained warning additions or removals. These stock
asset/gameplay diagnostics and older renderer fixtures with stale ABI-15
assertions remain unrelated open issues. The final source, binary, script,
configuration, log and image bindings are recorded in
`.tmp/ui/display-controls/validation-evidence.json`.

The investigation preserves rejected evidence rather than replacing it with
the successful runs. This includes an initial test fixture that omitted
layout frames, the original 240-second capture timeout, a shared capture
command-list defect, and the real stale-clock recovery failure. The first
successful OpenGL flow also exposed a capture-oracle error: a closed choice
retains valid measured popup geometry. Its original report and separate
requalification remain available. The final capture oracle checks that cache
against the owning context and modal transitions instead of requiring it to
be empty. Authored controls and bounded captures alone do not establish
product acceptance.
