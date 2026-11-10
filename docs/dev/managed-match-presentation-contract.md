# Managed match HUD and scoreboard contract

The managed-match context is a read-only presentation of the current accepted,
recipient-scoped match view. It does not infer match state, parse display text,
or emit commands. The multiplayer adapter builds every line from structured
fields, localizes the complete line, and projects the same state set to both
`guis/mphud.gui` and `guis/scoreboard.gui` in one update.

## State keys

| GUI state | Presentation content |
| --- | --- |
| `match_context_visible` | `1` only when the adapter has a usable managed-match view; `0` for stock/casual play, invalid views, and cleared sessions |
| `match_context_phase` | Lifecycle phase plus live period/round when applicable |
| `match_context_role` | The recipient's current public match role, side, readiness, and queue state |
| `match_context_pause` | Pause kind, owning side or official, and authoritative countdown/deadline |
| `match_context_readiness` | Ready participant/team counts and the bounded blocker summary visible to the recipient |
| `match_context_timeouts` | Remaining timeout budgets for the two competition sides |
| `match_context_proposal` | Current recipient-visible proposal and its deadline/status, or a localized no-proposal summary |
| `match_context_series` | Best-of length, series score, and current or next map |
| `match_context_items` | Recipient-authorized item availability/countdowns; absent for audiences that were not sent timing data |

All eight text values are already localized before they enter a GUI state. The GUI
contains no labels to concatenate and never parses these values. Empty values
are allowed, but the adapter should normally provide a localized neutral summary
so layout does not jump as state changes.

`match_context_visible` is the only visibility decision. Child windows are
always present beneath the gated parent, which keeps stock and casual
presentation unchanged and prevents individual lines from independently
revealing stale state.

## Placement

- The in-play HUD uses `oq4_match_context_hud` at virtual rectangle
  `400,8,232,106`, anchored to the upper-right. The phase is emphasized above a
  thin rule; role, pause, readiness, timeouts, proposal, series, and authorized
  item timing occupy seven compact rows below it. The card stays away from the crosshair and the existing
  upper-left per-mode score panels.
- The scoreboard uses `oq4_match_context_scoreboard` at virtual rectangle
  `83,427,477,49`. It is drawn after both normal and Tourney score surfaces as a
  footer. Phase, pause, readiness, and role occupy the left column; series,
  timeouts, proposal, and authorized item timing occupy the right column.

Both parents have `noevents 1`: they are informative surfaces only. Operations
remain in Match Control, and authoritative availability remains in the match
view rather than being reconstructed by either presentation.

## Adapter update boundary

Refresh both GUI projections after accepting a replacement or advanced match
view and while an authoritative deadline is counting down. Write all eight text
states first, write the visibility gate last, and call `StateChanged` once per
GUI after the complete projection. When the accepted session is cleared or
invalid, clear the text states and set the gate to `0` on both GUIs.

The static cross-repository contract in
`tools/tests/competitive_match_layer.py` pins the state set, single gate,
read-only construction, and exact placement in both GUI files.
