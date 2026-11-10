# Paired slider and numeric-field visibility

17 September 2026. This increment repairs an enlarged-text SYSTEM defect found
in the [output-size font review](output-size-fonts.md). It adds evidence for the
existing partial `LAY-004` requirement; no requirement or screen is accepted.
All 227 requirements, 271 unaccepted migrations and seven final gates remain
in scope.

## Cause and correction

Brightness and ambient-light numeric viewports grew to 2.25 em with independent
text scaling, while their paired sliders retained a fixed 36 dp height. Focus
reveal correctly scrolled the shorter slider into view, leaving the lower part
of its numeric value clipped by the settings body. At 200% text this hid much
of values such as `1.1`, even though the focused slider was fully visible.

The shared authoring generator now gives both sliders the same 2.25 em height
as their numeric viewports. Their fixed-size track is vertically centered and
cannot shrink. Both field frames therefore align at the supported sizes, and
existing focus reveal includes the complete neighboring value. This also keeps
the slider visible when focus moves to the numeric field. No new focus-target
heuristic, application operation, runtime behavior or display string is needed.

The canonical production document is regenerated from this definition. Field
IDs, editable vector artwork, readbacks, proposal ownership and the normal
Apply/Discard flow remain intact.

## Qualification

The expanded native production-page regression first fails against the saved
pre-fix document at 150% text: slider and numeric viewport heights no longer
agree. It checks actual RmlUi geometry, containment of both fields after focus
and status changes, track centering, reverse focus, stable unchanged frames,
and absence of setting edits caused by focus. The existing locale, expansion,
modal, dropdown, viewport and independent-text checks remain part of this suite.

All 84 cases across six shipped languages, two glyph-width models and seven
viewport/text configurations pass (244,860 checks). Fourteen field-generation,
seven preset and 18 capture-oracle tests pass; the latter reject 1,224 negative
mutations. The full Windows build and staging pass.

Source generation, test, build and staged engine evidence is retained under
`.tmp/ui/paired-field-focus/`. Engine probes inspect the current slider,
numeric viewport, track and scroll-body bounds before registered `screenshot`
captures. Screenshots come from the engine render target, with no OS capture
or host input injection.

French SP/OpenGL at 125% interface size and English MP/Vulkan at a requested
200% (window-fitted to 150%) both use 200% text at 1280x720. All 54 semantic
stages pass. Ten geometry probes confirm complete paired fields, aligned frames
and centered tracks, including reverse focus and video restart. All 22 images
were reviewed, with full-size brightness and ambient-light checks; two images
show the legacy parent and qualify return routing only. SP has no diagnostics;
MP retains the same 94 baseline asset/gameplay warnings without new messages.

The initial SP capture was rejected because the existing semantic oracle did
not recognize the added read-only inspection records. Its original report and
log are preserved; a separate qualified report verifies the same bytes against
the corrected semantic and geometry oracles. Negative tests also exposed a
malformed-record exception in the temporary geometry qualifier. The hardened
qualifier records structured failures for five mutations, including clipped
values, shifted tracks, unexpected identities, malformed and nonnumeric data.
The helper version used for capture remains separately preserved and hashed.

This qualification covers the authored brightness and ambient-light pairs in
SYSTEM. It does not accept all controls, native text entry, touch, arbitrary
editor layouts, projected world surfaces or the full UI corpus. Native-output
qualification, font styles/shaping and animated transform density remain open
as described by the full implementation plan. The earlier font review's
85% resolution plus CRT image does not isolate scene scaling from the
intentional CRT effect. The existing [native-output repair](native-output.md)
already covers ordinary OpenGL modes 1–3; that combined image alone does not
demonstrate a regression in that repair.
