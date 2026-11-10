# SYSTEM dimension fields

17 September 2026. This increment adds window and custom fullscreen width/height
to the opt-in retained SYSTEM page. It contributes to partial `BEH-002` and
`FLOW-002`; no screen, migration, milestone or final gate is accepted.

## Implementation and boundaries

Four Number controls reuse the existing editable vector plates, focus artwork
and field viewports. Existing localized labels and new validation/help text
cover all six languages. Width accepts 320–16384 pixels; height accepts
240–16384. Window fields are available in a windowed draft. Custom fullscreen
fields are available under Exclusive policy, including while preparing that
configuration in a window. Inactive families dim and reject activation.

Each window edit changes one owned draft value. A custom dimension edit also
selects `r_mode=-1` in the same typed patch, matching the legacy Custom-size
operation without replaying command text. No edit writes live settings. Local
unfinished text remains editable while the existing draft barrier prevents
Apply, conflicting sibling actions and accidental dismissal.

The layout matrix exposed clipping when expanded Russian labels made a field
taller than its scroll body at 640x480 with 200% text. Shared focus reveal now
prioritizes the Number editing viewport on each oversized axis, while retaining
the complete control wherever it fits. The same projected bounds determine
visibility, and viewport geometry participates in reflow detection. Invalid-text
feedback can therefore resize the field without clipping its editable value.
Unchanged frames preserve deliberate scrolling. This also contributes partial
`LAY-004` evidence; full text/layout qualification remains required.

The shared Number model now accepts an optional Boolean `integer` policy,
defaulting to false. It checks decimal text before binary64 conversion, so a
fractional suffix such as `1280.00000000000000001` cannot become 1280 by rounding.
Invalid text stays available for correction. Exponent syntax remains a separate
policy; these pixel fields disable it. Finite observed custom values remain
exact readbacks rather than being silently rounded to fit an editor.

The review found that checking the complete display tuple on every single-field
edit made transitions between supported width/height pairs impossible when
their intermediate combination was unsupported. `ValidateDraft` now checks the
complete snapshot's intrinsic types, changed writable fields, bounds and choices
without querying or changing display topology. Existing hosts default to their
original full validation. SYSTEM's read-only Apply readiness performs the full
current-capability validation and shows localized guidance for an unsupported
combination. Apply, preparation, execution, restoration and recovery retain
their existing full checks; capability loss cannot turn an old prepared request
into an unchecked write.

Display Resolution and Refresh Rate now sit in this column as
capability-backed choices over the published lists
([SYSTEM resolution rows](system-resolution-rows.md)). Further dependent
controls, Defaults, complete effect execution, in-field input method
composition (the size fields take typed digits through the committed-character
route, [typed characters](numeric-fields.md#typed-characters)), full responsive artwork/motion
acceptance and the editor round trip remain required. Actual fullscreen, borderless,
multiple-monitor and window-manager behavior require separate qualification.
Automated gameplay validation remains hidden and windowed.

## Qualification

Evidence is retained under `.tmp/ui/dimension-controls/`. The native page matrix
uses the production document and Runtime with counted fonts/hosts; it does not
establish physical input, shaping or operating-system display behavior. The
final document and binaries pass 36 dimension cases (120,715 checks): six
languages, two glyph-width models, and 1280x720 at 125% interface size, 640x480
at 200% text, and ultrawide output at 200% interface/text size. Tests cover exact
one/two-key proposals, zero live writes, invalid-text correction, dependent
availability, modal guards, snapshot recreation and stale proposal refusal.
They require the complete editing viewport to remain visible before editing
and during repeated invalid-text/status reflow.

The final general text regression repeats 14 Russian cases (45,502 checks).
The preceding six-language 84-case run passed 274,813 checks before the shared
focus repair and local-draft readback alias; its separate source/binary record
is preserved and is not relabeled as a final-source run. Generic projected
focus passes 3,616 checks, and all four focused numeric runtime/view/snapshot
regression suites pass. The core text, Number control and transaction suites
also pass. Clang's text-model run passes 1,105 checks and rejects ten compiled
mutations, including both integer-validation guards. The production-body
service passes 92 scenarios; actual host extraction passes with SDL and without
SDL, checking intrinsic drafts, complete tuples and refused writes.

The full engine build, staging and eight authoring checks pass. Capture tests
pass 19 page-oracle tests and 20 exit-oracle tests, rejecting 1,224 and 1,368
log corruptions respectively. Each backend's dimension extension rejects a
further 784 draft/baseline/local-barrier/device corruptions. Resized screenshot
payloads are checked against the expected stage dimensions, including a
negative mocked capture that substitutes the old window size.

Rejected evidence remains available. The first six-language dimension run
exposed the Russian clipping defect. The first OpenGL capture confused the
service's valid-draft readiness with the separate local unfinished-text barrier;
final captures read both values, while native cases test the actual Apply
control. The final OpenGL engine, settings, persistence and warning checks all
passed directly, but the shared image utility still required 1280x720 and
rejected valid 960x600 TGAs. Its original report is retained alongside a separate
requalification using stage-specific image dimensions. That requalification
checks the original logs, source/binary identities, script, configuration and
images; it is not an additional game run.

Final SP/OpenGL (`airdefense1`, French) and MP/Vulkan (`mp/q4dm1`, English)
flows each cover 26 stages, three real renderer restarts and 12 reviewed engine
screenshots at 125% interface density and 200% text. The actual hidden window
changes from 1280x720 to 960x600, returns to 1280x720 through Revert, then keeps
960x600 through Apply-and-exit and reopening. Typed window/custom dimensions,
Custom mode, local unfinished text, confirmation ownership, archived settings
and recovery-journal cleanup agree with their expected states. Vulkan passes
the corrected capture harness directly. Focused labels, values, validation and
modal actions fit in the reviewed images; the four legacy parent-menu images
establish return routing only.

OpenGL is warning-free. Vulkan retains 94 reviewed baseline stock/gameplay
warnings plus two expected cache-initialization warnings for the additional
restarts, with no unexplained additions or removals. These baseline diagnostics
and older renderer fixtures with stale ABI-15 literal assertions remain
unrelated open issues; the renderer ABI remains 18. Final source, binary,
script, log, configuration and image bindings are recorded in
`.tmp/ui/dimension-controls/validation-evidence.json`. The complete plan remains
at 69 partial, 157 pending and one verified requirement, with all 271 migrations
and seven final gates unaccepted.
