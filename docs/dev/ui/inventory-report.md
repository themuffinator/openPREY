# GUI replacement inventory

Refreshed 22 October 2026. This is source inventory evidence, not conversion or
product acceptance. The [roadmap](../roadmap.md) owns scheduling, the
[visual specification](../ui-visual-design.md) owns current visual policy, and
the register preserves the complete acceptance scope.

## 22 October 2026 audio and voice merge revision

Combining the Stage 2 line with the audio and voice milestones changes three
base variants: `guis/mainmenu.gui` (Android setup action plus the Dialogue
Volume row), `guis/menu/settings/audio.gui` (dialogue, subtitle and voice
controls) and `guis/mpmain.gui` (voice controls). Awakening's
`guis/menu/settings/audio.gui` variant changes with it; Awakening's own main and
multiplayer menus override the other two. Retail is unchanged. A fresh
inventory of the same three mount sequences retains 358 variants, all pending.
Base now has 15,364 window declarations and Awakening 17,185. The retained
`.q4ui` documents those changes touched are outside this lexical GUI inventory.

The current manifest's immutable predecessor is
`18f000a7ff3b99f1da25a73282a0eca1dc1244f0:docs/dev/ui/migration-manifest.json`.
The reproducible revision is under `.tmp/merge-ab/ui/`. The register adds
`inventory-audio-voice-merge`; all earlier evidence and the 349 requirements
retain their scope/status. This refresh grants no GUI migration or product
acceptance.

## 21 October 2026 Android Settings revision

The standalone Android setup action changes the base `guis/mainmenu.gui`
variant. A fresh inventory of the same three mount sequences retains 358
variants, all pending. Base now has 15,340 window declarations; retail and
Awakening are unchanged. Awakening's own menu overrides this base entry and
has not been qualified for the Android setup-return flow.

The current manifest's immutable predecessor is
`96b53793884e82c69d296f6ac3db3a581dec44a5:docs/dev/ui/migration-manifest.json`.
Reports and the reproducible revision are under `.tmp/stage-two/ui-*`.
The register adds `inventory-android-setup-return`; all earlier evidence and
the 310 requirements retain their scope/status. This refresh grants no GUI
migration or product acceptance.

## 18 October 2026 reconciliation

The [source snapshot](inventory-sources.json) records effective source selection,
raw and newline-normalized SHA-256, include closures, special widgets and mount
precedence. It contains metadata only. The [migration manifest](migration-manifest.json)
uses unique `(path, transitive include text identity)` variants as its denominator;
identical variants shared by configurations count once. Its immutable predecessor
was Git blob `8c1a49ca7a033e163e271ef3787a4a9ba73f7479:docs/dev/ui/migration-manifest.json`.

| Configuration, mounts low to high | Effective roots/includes | Window declarations | Render/editor widgets |
| --- | ---: | ---: | --- |
| Installed retail q4base PK4s | 264 | 13,442 | 2 / 0 |
| Retail, content/baseoq4/pak0, content/baseoq4/pak1 | 276 | 15,339 | 2 / 3 |
| Base configuration, installed q4xbase | 324 | 17,166 | 2 / 3 |

The union is **358 variants**, all pending with no replacement or migration
acceptance. Base adds five paths and changes 18 old paths after newline
normalization; it removes none. Awakening adds 53 and changes 23 relative to the
old base manifest. Retail alone omits seven overlay-only paths; these are not
deleted from scope. Every added/changed/absent path is enumerated in `changes`.
Changing an included file invalidates its parent variant too. The three new
`editorViewDef` widgets remain in scope even while map-editor work is paused.
All configurations retain the known `tram1/bridge1.gui` lexical fragment;
none has a missing include or include cycle. Unresolved lexical asset references
(retail 23, base 17, Awakening 31) remain investigation inputs, not missing-media verdicts.

The old inventory verification no longer describes this corpus. `INV-001` is
partial, its acceptance references are cleared, and its original evidence is
retained. No other requirement, supersession or gate changes. The new
`--inventory-revision` audit permits source reconciliation and this invalidation;
it rejects acceptance promotion and protects all other register fields. The
checkpoint, archive and scope-revision modes retain their restrictions.

Re-run `legacy_inventory.py` with the three mount sequences above, then:

```powershell
python tools/ui/inventory_revision.py --baseline 8c1a49ca7a033e163e271ef3787a4a9ba73f7479 `
  --report retail=.tmp/stage-one/ui-retail-inventory.json `
  --report base=.tmp/stage-one/ui-base-inventory-v2.json `
  --report awakening=.tmp/stage-one/ui-awakening-inventory.json `
  --output-dir .tmp/stage-one/ui-revision-new
python tools/ui/validate_product_requirements.py --baseline 8c1a49ca7a033e163e271ef3787a4a9ba73f7479 `
  --inventory-revision --output .tmp/stage-one/ui-register-audit-new.json
python tools/tests/ui_inventory_revision.py
```

### Scope decisions paired with UI-05

Editable vector framing, controls, icons and the 45-degree motif remain the
default reconstruction policy. Native import is semantic/reference input; it
does not authorize wholesale bitmap substitution or make a translated GUI
accepted. The two dated HUD imagery exceptions below remain narrowly scoped
implementation exceptions, not blanket approvals for any of the 358 variants.
The later product-owner voice-graph exception is preserved as history alongside
the visual register; UI-05 must reconcile its exact acceptance wording before
accepting that requirement. Retained screens running by default do not close
UI-03/UI-04 migration, UI-06 editor work, UI-09 toolkit qualification or UI-11
acceptance tooling. Awakening remains additive SP under q4xbase; no expansion MP
module is added. Savepath/mod/developer overrides require their own named
configuration and fresh source bindings before acceptance.

## Historical 8 September inventory

The following measurements and captures retain their original scope and identities.

## Reproduction

From the engine repository root, run:

```powershell
python tools/ui/legacy_inventory.py `
  --mount 'retail=C:\Program Files (x86)\Steam\steamapps\common\Quake 4\q4base' `
  --mount 'openq4-pak0=content/baseoq4/pak0' `
  --mount 'openq4-pak1=content/baseoq4/pak1' `
  --output .tmp/ui/legacy-inventory.json
python tools/tests/ui_legacy_inventory.py
```

The tool is platform-independent Python using the standard library. On other
hosts, supply the actual installed asset directory with the same explicit
mount order. It reads archives in place and writes metadata, never extracted
retail source or images. Full generated output stays under `.tmp/`.

The tracked [migration manifest](migration-manifest.json) is initialized using
the optional `--seed-manifest` argument. That operation refuses to overwrite an
existing manifest so later translation/acceptance evidence cannot be erased.
Each source hash binds evidence to the corresponding effective GUI content.
The optional `--export-requests` output feeds the subsequent
[native preprocessing and structured import](legacy-import.md) pipeline.

## Observed corpus

| Measurement | Result |
| --- | ---: |
| Effective GUI resources, including GUI include files | 271 |
| Lexical window declarations | 14,517 |
| Event declarations | 8,037 |
| Timeline event declarations | 5,497 |
| Named-event declarations | 530 |
| Unique referenced localization keys | 1,237 |
| Distinct artwork/font/model references | 1,222 |
| Missing include/cyclic include errors | 0 |
| Source fragments requiring brace review | 1 |

| Window type | Count |
| --- | ---: |
| `windowDef` | 14,131 |
| `choiceDef` | 152 |
| `editDef` | 86 |
| `listDef` | 66 |
| `bindDef` | 48 |
| `sliderDef` | 32 |
| `renderDef` | 2 |

The two model/render widgets are the player previews in `guis/mainmenu.gui`
and `guis/mpmain.gui`; they need functional rendering, not a static replacement.
The corpus includes 124 monitor GUIs, 59 map GUIs, 23 shared/common GUIs,
12 weapon GUIs, six mover GUIs, six vehicle GUIs and four model GUIs, in
addition to menus, HUDs and other root resources. All remain in migration scope
even when a resource's stock gameplay reachability is not yet established.

## What the tool proves

- Explicit low-to-high mounts; engine-compatible numbered/non-numbered PK4
  ordering; loose overrides; ignored official game-binary archives in q4base.
- Effective source selection, SHA-256 and all shadowed source locations for
  inventoried resources. Same-layer duplicates/case collisions are errors.
- Comment/string-aware lexical locations and declarations, includes and their
  dependency order, state/key references and script command tokens.
- Direct braced material declaration candidates and direct file/image/font
  candidates for GUI artwork references. Duplicate declarations remain
  ambiguous rather than being assigned an invented winner.
- Every migration seed starts pending, with no replacement, bitmap approval,
  behavioral acceptance or visual acceptance. Family hints are routing aids,
  not completed source/design review.

## What remains unproven

This is not an engine parser. It does not expand macros, evaluate conditions or
expressions, prove reachability, resolve every declaration guide, enumerate
all images inside multi-stage material programs or execute GUI scripts.
Lexical counts include include files as sources and are not counts of live
runtime instances. Console strings and dynamically supplied game state need
the semantic translation/behavior analysis stage.

Resource discovery only covers the supplied mounts. Savepath/developer loose
files are intentionally excluded from this canonical-source report, and actual
runtime mount diagnostics must be checked when capturing a baseline. A seed's
source hash must match fresh inventory before future evidence is accepted.

The 17 unresolved artwork references after lexical name disambiguation include
colored weapon/teammate symbols and console/test-loading imagery. They need
engine-generated/alias, source-presence or unused-resource investigation before
being called missing assets. No artwork has yet been classified as an approved
bitmap exception in this original seed; simple furniture remains mandatory
vector reconstruction. Later implementation exceptions are recorded below
without rewriting the immutable source inventory.

`guis/maps/tram1/bridge1.gui` has an extra lexical closing brace. Its behavior
must be recorded before translation. Subsequent native preprocessing and
structured import consume its full token stream successfully. This lexical
observation is not evidence of a runtime failure or permission to drop it.

### HUD implementation exception, 9 October 2026

The Remastered Strogg gauges load `gfx/guis/hud/s_static.tga` from the player's
installed Quake 4 assets. The stock full-field grain is complex imagery whose
appearance depends on that texture, within section 6's existing grain
exception. Its gauge mask, tint, repeated layout and reduced-motion-aware
animation remain editable. The shared Awakening Strogg construction uses the
same exception. No extracted texture is included in the repository. This
implementation record does not accept a GUI migration or change the pending
source-inventory rows.

## Validation

### HUD ECG exception, 11 October 2026

The product owner approved the installed `gfx/guis/hud/ekg.tga`, `s_ekg.tga`
and `s_ekg2.tga` for the Remastered Marine/Strogg ECG, including Awakening.
The repeated vector strokes and glow caused substantial submission work.
Masks, tint, health response, scrolling and scale remain editable; two copies
of each installed bitmap cover its complete moving period. No extracted pixels
are added to the repository. Radio/voice graphs use a separately approved
cached vector preset after measurement showed costly live audio updates.

### Inventory validation

`tools/tests/ui_legacy_inventory.py` exercises real temporary ZIP/directory
mounts, package priority, loose overrides, case collisions, ignored game
archives, comment/string adversaries, source locations, relative/root include
resolution, cycles, missing includes, malformed tokens, and material/file/
runtime-binding distinctions. Window names such as `online`, `one`, `font`
and `background` cannot masquerade as events or asset properties.

Before baseline launches, the Windows menu-cursor path was found to synchronize
the host pointer even with `in_mouse 0`. A guard now prevents routing from
disabled/hidden windows and prevents synchronization while unfocused. Native
tests execute the production functions in both Windows and POSIX branches over
32 state combinations plus an absent window. Full game captures require the
newly built guarded executable; an older staged binary is not sufficient.

## Initial gameplay reference captures

The MSVC-aware wrapper compiled the current client and staged it using
`install -C builddir --no-rebuild --skip-subprojects`. Client SHA-256:
`8e2f74e071877b849c1dde39e5885ee6839d623b796e6a958029836a4079c2b7`.

`tools/ui/capture_legacy_baseline.py` derives its mode-specific map arguments
from the SP airdefense1 / MP q4dm1 VS Code tasks, overrides the display with a
1280x720 hidden window, disables mouse/controller input, uses a new isolated
savepath and invokes the registered `screenshot` command three seconds after
active gameplay drawing begins, followed by `quit`. Each evidence directory
records exact arguments, binary hashes, log hash and screenshot hash. Hidden
window captures are limited to 60 Hz by the existing Windows presentation cap;
they do not establish high-refresh motion quality.

```powershell
python tools/ui/capture_legacy_baseline.py --mode sp --renderer gl --assets 'C:\Program Files (x86)\Steam\steamapps\common\Quake 4' --output .tmp/ui/baseline/sp-gl-01
python tools/ui/capture_legacy_baseline.py --mode mp --renderer vulkan --assets 'C:\Program Files (x86)\Steam\steamapps\common\Quake 4' --output .tmp/ui/baseline/mp-vulkan-01
```

Use new output directory names on repetition; existing evidence is not overwritten.

| Capture | Visual observation | Engine outcome |
| --- | --- | --- |
| `sp-gl-01` | Marine health/weapon HUD, crosshair and incoming-transmission overlay in airdefense1 gameplay | Exit 0; screenshot marker; no WARNING/ERROR records |
| `mp-vulkan-01` | MP health/ammo HUD, rank/timer/warmup overlays and crosshair after explicit automatic join | Exit 0; screenshot marker; 93 WARNING records, no ERROR records |

TGA SHA-256 values:

- SP: `1237198293f61707df86b6a8b950542d73e65250d86bd9319356a06a4184897b`
- MP: `76ae602768191be32f84817c593738fcdedbd1ee2e515ceef482dd998d697670`

Both engine images were decoded and visually inspected. PNG copies preserve
the captured pixels for convenient review; they are not OS captures. These are
usable existing-UI references, not acceptance evidence for the replacement.
The MP warnings include non-precached napalm GUI materials/tables and remain
open for the migration/qualification work; capture success is not a clean-log
claim. Logs/captures reside under each evidence directory's `save/baseoq4/`.

Remaining family gameplay captures, complete property/command classification,
vector/bitmap decisions and full conversion are outstanding. Stage 1 is not
complete merely because this inventory and two captures succeeded.
