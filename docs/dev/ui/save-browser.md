# Save browser controls, 23 October 2026

This UI-03 increment adds sorting, filtering and explicit refresh to the Marine
and Strogg Load Game and Save Game pages. The existing preview, list, save-name
field and confirmation layouts remain the basis of both pages.

## Behavior

- The header sort control cycles date newest/oldest, name ascending/descending,
  and location ascending/descending. Its label identifies the key and its vector
  marker identifies the direction. Color escapes are removed before comparing
  labels; equal keys use filename order for deterministic results.
- Manual Saves and Autosaves are mutually exclusive filter tags. Activating a
  selected tag or Clear Filters restores the full catalog. Autosaves use the
  existing description's screenshot/no-overwrite classification. A filtered
  empty list explains how to clear the filter.
- Refresh List reads the current save directory. The controller's semantic west
  action refreshes and north cycles sorting. Selection and focused rows follow
  filenames, including across the 64-row page boundary. A removed or filtered-out
  selection clears; a lost focused row moves to Refresh List. Other controls
  keep focus. These operations never replace a typed save name.
- A successful save selects the written filename under the current sort. If an
  autosave filter would hide it, that filter clears. Each new visit starts with
  the full catalog in newest-first order.

Seven new labels are present in all twelve bundled language tables. The controls
use editable vector plates, crosses and direction markers; no bitmap art is added.
The fixed-size document still pages through arbitrarily long catalogs rather
than creating one control for every file. Enumeration is explicit, not per frame.

## Ownership contract

Each catalog publication advances a transient positive generation. The existing
`session.menu` operation carries numeric `index` and `generation` operands for
`loadSelect`, `saveSelect`, `loadSave` and `loadDelete`. Both are frozen during
event evaluation. The adapter rejects missing, fractional, nonfinite, negative
and out-of-range operands; the session checks the generation and index again
before touching the catalog. Older one-argument requests fail safely.

Rows use generation/filename button contexts. Load and Delete use the selected
save's context. Refresh cancels a held row, and a request already in the session
queue cannot act on a newer catalog. The delete confirmation freezes the index
and generation of the save it asked about. No save format or network protocol
changes are involved. The engine and generated documents must be staged together.

## Validation and limits

The production session harness covers all six orders, both filters, clearing,
selection and focus through insertion/removal and page boundaries, a retained
name draft, selection after saving under a name sort, stale requests and invalid
operands. Native tests load both page families, check the sort marker and filtered
empty state, exercise semantic actions and freeze the delete confirmation. The
adapter harness checks typed validation and captured operands across later state
changes. Existing page and pointer-reach tests cover the updated documents.

`tools/ui/capture_save_browser.py` creates real SP saves, browses them through
the normal pause-menu routes, refreshes during a held press, cancels deletion,
writes a save through the sorted page and restores it to gameplay. It uses a
hidden window, isolated writable data and engine render-target screenshots.
The console services diagnostic events individually, so delayed queue ordering
is tested in the production-method harness rather than inferred from a live
sequence of console commands. Run results, source/binary identities and reviewed
captures are bound in `.tmp/ui-save-browser/validation-evidence.json`.

The Windows MSVC build and staged package passed. Final validation includes:

- All three native page suites (Marine, Strogg and pointer reach); the two
  value interaction/runtime suites also passed before the document-only fixes.
- 851 session gate checks, plus its server-card, loading-hold and prompt-glyph
  suites and generated-document check; all twelve language tables pass encoding
  validation.
- The production adapter harness and all twenty existing mutation rejections.
- OpenGL Marine/English at 1280x720 and Vulkan Strogg/Russian at 1920x1080:
  seventeen automated checks per run, zero reported errors and all sixteen
  engine screenshots visually reviewed. Sort/filter controls, selection/focus,
  deletion cancellation and the saved-name field are readable without overlap;
  gameplay is visible before saving and after restoring. Each run preserves its
  source and runtime identities.

The first capture attempts exposed harness ordering and log-matching mistakes;
those failed reports remain diagnostic evidence and are not qualified. The final
runs use the corrected harness. Existing stock-asset warnings and four dynamic
save-preview material precache notices per final run are retained in the logs. This does not qualify physical controller/touch input,
every language/aspect ratio, GLES or other operating systems. Chapter, objective
and play-time details, remaining confirmations/loading flows and full UI-03
acceptance remain open. No requirement status, migration or final gate is accepted.
