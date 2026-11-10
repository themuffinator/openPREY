# SYSTEM display lists

The settings service builds the lists the SYSTEM page's display rows choose
from: the display device, the display resolution and the refresh rate. It also
publishes them to the page and turns a pick into settings. The page declares
the keys; the rows that read them follow in their own increments.

## Lists

- **Devices.** The list starts with Auto (`r_screen` -1, `#str_229914`). Then
  comes one entry per current display, in SDL order, reading "N: name"
  (`#str_230086`). When the draft names a display beyond the connected ones,
  the list continues with "Display N (not connected)" entries (`#str_230087`)
  up to it, so the closed control can still name it. There are at most eight
  slots, so a draft `r_screen` of 8 or more has no entry.
- **Modes.**
  - The list starts with Desktop Native and the display's desktop size
    (`#str_229973`).
  - Next come the pixel sizes the display offers for exclusive fullscreen,
    from 320×240 to 16384×16384, sorted, with the stock aspect suffix:
    "1920 × 1080 (16:9)" (`#str_230083`, `#str_230084`).
  - It ends with Custom and the draft's custom size, clamped to
    320×240..16384×16384 (`#str_229974`).
  - The draft selects as the stock menu does. `r_mode` -2 is Desktop. -1
    picks the listed size equal to the custom size, else Custom. A legacy
    mode picks its listed size.
  - A legacy size the display does not offer goes in a reserved last slot
    (39). The popup never shows it, but the closed control still names it.
  - At most 39 slots are visible. On overflow the list keeps Desktop, Custom,
    the current size and the largest sizes.
- **Refresh.**
  - The list starts with Auto, then the whole-hertz rates the display offers
    at the requested size, rounded as the strict request matches them
    (`#str_230085`, "144 Hz").
  - The requested size is the desktop size for Desktop Native, the custom
    size for Custom, and the legacy size for a legacy mode.
  - Unlike the stock menu, the desktop rate is not added. The display
    request matches rates strictly, so a rate the size lacks could not
    apply.
  - An unlisted current rate goes in the reserved last slot (15). On overflow
    the list keeps the current rate and the highest ones.
  - Auto (`r_displayRefresh` 0) is the rate nearest the desktop's at the
    requested size, the one every display path chooses
    ([display device contract](display-device-contract.md)).
- **Descriptors.** Each display's size is its desktop mode's, which equals its
  bounds except while an exclusive mode resizes them, so an exclusive mode on
  a display no longer changes its descriptor's size. Its position still comes
  from the bounds.
- **Span.** Expanding across displays is available when there is more than one
  display, the window system offers absolute window placement, and the
  displays together fit within 16384 pixels.

The lists describe the display the draft's `r_screen` names. Auto describes
the window's display, or the primary display when there is no window. A
display index that is no longer connected has no sizes or rates.

**A deliberate departure:** display names longer than 48 code points are cut
at a code point boundary to 47 and an ellipsis. The stock menu showed whole
names. The cut keeps the device popup a bounded width in every language.

## Labels

The formats are localized strings with fixed placeholders: `%d × %d`, `%s (%s)`,
`%d Hz` (`%d Гц` in Russian and Ukrainian), `%d: %s` and
`Display %d (not connected)`. The builder fills only `%d` and `%s`, in order.
If a translation's placeholders differ from English, the builder uses the
English format instead, and `lang_table_encoding.py` checks that every
language's openQ4 table keeps them. A missing string keeps the English text.

## Service

- **Inputs.** The display host captures the SDL topology. The capture is kept
  while its stamp holds: the display topology generation, the window's display
  and the localized labels. Reading the stamp is cheap, so a language change or
  the window moving recaptures on the next read. `Sys_DisplayTopologyGeneration`
  counts SDL display events and SDL's window display and scale events. SDL
  reports a window display change only once most of the window is on the new
  display, so the stamp reads the window's display directly, as Apply does.
- **Keys.** All keys are owner-only:
  - `settings.display.available`, `.spanAvailable`, `.catalog`, `.count`
    and `.optionCount`;
  - `settings.display.0..7.label`;
  - `settings.display.mode.optionCount`, `.mode.selected` and
    `.mode.0..39.label`;
  - `settings.display.refresh.optionCount`, `.refresh.selected` and
    `.refresh.0..15.label`.

  `tools/ui/system_display_catalog.py` declares them through the display pass.
  Its slot counts match the builder's, and the service schema types every key
  as the page declares it.
- **Token.** `settings.display.catalog` is a decimal token naming the pickable
  entries and their labels. Selections and the reserved slots are not part of
  it, so a change of selection alone keeps it. A token is never reused, even
  by a later service.
- **Picks.** `settings.system.display`, `.displayMode` and `.displayRefresh`
  take exactly `{index: number, catalog: string}`.
  - A token other than the current one is a Conflict (`#str_230011`), and
    nothing is written.
  - Otherwise the pick becomes an ordinary generated edit:
    - a display writes `r_screen`. If the new display (for Auto, the
      window's, else the primary) lacks the draft's listed or legacy size, the
      pick also writes `r_mode` -2 (Desktop Native); a typed Custom size
      stays. If it lacks the draft's rate at the resulting size, the pick also
      writes `r_displayRefresh` 0;
    - a mode writes `r_mode` -2 for Desktop, -1 with the custom size Custom
      shows, or a listed size's width and height with its legacy mode (-1 if
      it has none). If the listed display lacks the draft's rate at that
      size, it also writes `r_displayRefresh` 0;
    - a refresh writes `r_displayRefresh`.
  - `SystemDisplayCatalog::autoDisplay` names the descriptor Auto describes.
    Like the selections, it is not part of the token.
  - Picking the selected entry writes nothing. A re-pick therefore never turns
    a custom size into its legacy mode, which would restart the display for
    the same size.
  - A display that is not connected and a reserved slot cannot be picked.
- **Picked display.** A display picked from the list is recorded by its
  descriptor: name, bounds and desktop mode.
  - While that `r_screen` change is pending, Apply needs the same monitor at
    that index. If the monitor was replaced or moved, the page shows
    `#str_230023`.
  - Choosing the selected display again records the monitor now at that
    index.
  - The record lapses once the change is no longer pending: taken back,
    applied, cancelled or reverted. A new session starts without one; a second
    Begin while editing keeps it.
- **Number fields.** A size pick edits the custom width and height. Like a
  preset, the page refuses it while a custom size field holds an unconfirmed
  number.

## Qualification

- `tools/tests/ui_system_display.py` runs the pure builder over:
  - one display and several, with and without span;
  - pixel-density sizes, 59.94 Hz shown as 60, and several rates at one size;
  - legacy and non-legacy sizes;
  - Desktop, Custom and an unlisted current size, and an unlisted rate;
  - overflow of both lists;
  - a stale `r_screen`, a failed capture and an incomplete draft;
  - long and multibyte names, and sizes above 16384;
  - a translation with the wrong placeholders;
  - Auto following the window's display, the desktop rate not added, and span
    refused beyond 16384 pixels;
  - every patch, re-picks that write nothing, the clamped Custom size, every
    refused pick, and monitor descriptors.

  It also checks that the page declares exactly the catalog keys and types,
  that the schema types them the same way, and that display events and the
  window changing display or scale advance the generation.
- `tools/tests/ui_settings_service.py` runs two scenarios. `display_catalog`
  covers:
  - owner-only lists and the pick shapes;
  - stale and malformed tokens;
  - device, size and rate picks, a re-pick writing nothing, and a slot past
    the list;
  - a selection-only change keeping the token, and a pick that changes the
    lists moving it so a pick from the earlier list is refused;
  - the reserved slots naming an unlisted size and rate;
  - recapture on a topology, window display or label change;
  - a failed capture.

  `display_pick_drift` covers a replaced monitor blocking Apply, a second
  Begin keeping the record, picking the monitor again, and the record
  clearing, including after a session closed without Cancel.
  `display_pick_resets` covers a display pick returning a size and a rate the
  new display lacks to Desktop Native and Auto, and Auto following the
  window's display; `display_catalog` proves a size pick's rate reset.
- `tools/tests/ui_system_display.py` covers rates and sizes a size or display
  pick resets, a typed Custom size kept, Auto's display, and descriptors that
  keep the desktop size while an exclusive mode resizes the bounds.
- `tools/tests/ui_settings_display_service.py` runs the host's stamp and
  capture: the generation, the window's display or the primary, all eight
  labels with English for missing strings, and a failed capture.
- `tools/tests/ui_performance_presets.py` checks that a size pick waits for
  an unconfirmed custom size field and that display and rate picks do not.
- An SP map load on OpenGL opened the page with console verbs only. The
  adapter accepted the declared keys, and the service built one catalog for
  the machine's one display: 26 mode slots and 3 refresh slots for the
  1280×720 custom size.

Evidence: `.tmp/ui/system-display-catalog/validation-evidence.json`, SHA-256
`aaf2b08b88a32d8096460f8031f6b176f31974c5c67ce7ca548839f40f624e2f`.

Display Device and Expand Across Displays now read the lists
([SYSTEM display rows](system-display-rows.md)), and so do Display Resolution
and Refresh Rate ([SYSTEM resolution rows](system-resolution-rows.md)).
