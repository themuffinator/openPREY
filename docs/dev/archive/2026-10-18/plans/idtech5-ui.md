# idtech5-ui: complete interface replacement

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Started 8 September 2026. Status: active; inventory qualification and runtime integration underway. This is a
development feature integrated into `main` at the user's request on 25 September 2026.
Since 1 October 2026 the retained title, pause and loading screens and the
campaign selectors are on by default, and each presents its stock GUI whenever
its retained content is missing or cannot load. The SYSTEM page stays opt-in
until every setting of the stock page works there. This does not close the
runtime, editor, screen migration or platform qualification gates. The [retained runtime checkpoint](../../../ui/runtime-spike.md)
records the stage 2 integration candidate and its remaining limitations.

The [product completion review and plan](ui-product-completion.md) audits the
implementation at `80bb3939` and defines the next delivery milestones, concrete
runtime/editor/corpus requirements and final quality/performance gates. It refines
delivery order without reducing the complete scope below. A representative screen
is an intermediate milestone; full implementation must deliver the complete,
high-quality UI product at an id Tech 5 standard.

The [product requirement register](../../../ui/product-requirements.md) tracks the
full normative scope, milestone ownership and acceptance evidence.

The ammo/health/armor [status bar](../../../ui/status-bar.md) now has a shared SP/MP
player bridge and separate Marine/Strogg vector documents, with live values,
centered bottom placement and stock fallback. The [HUD presentation bridge](../../../ui/hud-coverage.md)
now covers the remaining screen-space HUD families and game-owned overlays.
The [Remastered HUD](../../../ui/remastered-hud.md) now lays out the on-foot,
multiplayer, vehicle, objectives and scoreboard HUDs on the section 14.4
anchors; the remaining displays and world-surface migration requirements remain.

The 11 October status-bar review retains centered placement while matching
legacy gauge dimensions, internal offsets, background saturation and shading.
The [Remastered HUD record](../../../ui/remastered-hud.md) documents the vector
construction and validation location.

The 7 October scope and screen increment removes pointer-driven vector
recompilation from the title's framing, anchors loading furniture to the
leading/trailing screens (including portrait), and supplies the three retained
weapon scopes through the shared SP/MP preference gate. Source, tests and
engine capture evidence are recorded in [retained screens](../../../ui/retained-screens.md).
Visual specification 1.15 and the editable implant atlas sheet explicitly cover
Medical Labs `medchange`, including its full-view wide/tall composition and
activation/hurt timing. Its vector presentation now routes through the HUD bridge;
the complete Remastered composition in `FLOW-062` and the larger vehicle/editor gates remain.

[Visual specification 1.1](../../../ui-visual-design.md) (26 September 2026) records
measured stock geometry, palette, type, motion and composition from the
effective retail GUIs, and corrects plate, panel, checkbox and slider anatomy.
Version 1.2 adds the modern interface direction: viewing profiles, adaptive
layout, controller and touch input, Android lifecycle and first-run setup, and
a first-party touch gameplay overlay. [Register schema 2](../../../ui/product-requirements.md)
records eight supersessions and appends 40 requirements for both versions.
Version 1.3 measures the band motion, HUD and pop-up frames, and adds detailing
rules, modern components and a HUD section with the weapon wheel; version 1.4
adds the objectives display, boss, vehicle and scope displays, the multiplayer
HUD and scoreboard, and the Strogg weapon wheel. [Register schema 3](../../../ui/product-requirements.md)
records five supersessions and appends 29 requirements for both versions.
Version 1.5 lays the HUD out in screens with a centered status bar. It
rebuilds the multiplayer HUD's top, chat and kill feed, catalogues every
crosshair and item icon as vector art, and gives the weapon wheels the stock's
translation and transmission effects. Register schema 4 supersedes seven rows
and appends four for it. Version 1.6 adds the loading screens and the
multiplayer menus. The menus are a tabbed card over the softened view, in
Welcome and Escape variants that replace the join card and the full-screen menu.
It also traces the EKG and the transmission waveform from their textures.
Register schema 5 appends three rows for it. Version 1.7 restores the Quake
emblem to the title screen and sets the single-player pause menu apart from it,
with the current level block in the emblem's place and a Strogg variant after
Kane's stroggification. Register schema 6 appends two rows for it. Version
1.8 rebuilds the initializing screen from separate layers, and its rings turn
slowly while the engine starts. Register schema 7 appends two rows for it.
Version 1.9 replaces the modal scrim with a soft focus of the screen beneath;
register schema 8 supersedes two rows and appends one for it. Version 1.10 adds
a sub-page level beneath the menu pages: Single Player leads to Campaign and
Arena, and Multiplayer to Join Game, Create Server and Demos, with a one-notch
band step and a path crumb. Register schema 9 supersedes one row and appends one
for it. Version 1.11 takes the waveform out of the weapon wheel, keeps the
multiplayer chat clear of the status bar, rebuilds the scopes from their stock
layers, catalogues the squad patches and covers The Awakening's HUD content;
register schema 10 supersedes three rows and appends five for it. Version 1.12
adds the 9:16 portrait view, a multiplayer weapon wheel, the Competitive HUD and
a spectator follow camera, outlines the modal title and gives the initializing
screen Remastered accents; register schema 11 supersedes five rows and appends
four for it. Version 1.13 replaces the vehicles' bracketed exit and boost lines
with HUD prompts and keeps the transmission display in the right-hand screen's
corner on every HUD; register schema 12 supersedes one row and appends two for
it. Version 1.14 measures the modal against the stock (the title hangs in the
lit slot and the silhouette is inset in its rectangle); register schema 13
supersedes one row and appends one for it.

The wheel's hardcoded classic draw path previously bypassed `ui_retained`.
Native Marine/Strogg vector documents now bind the player's inventory, ammo and
selection; the eleven-position stock and thirteen-position Awakening rosters
share player logic with MP's reliable equip route. Visual 1.18 explicitly keeps
the original 77% horizontal default through archived `ui_weaponWheelOffset 27`;
zero centers, negative moves left, and narrow views fit without changing the
preference. Visual 1.19 adds smooth Gaussian scene focus before the HUD,
shared by SP and MP and faded with the wheel. See [weapon wheels](../../../ui/weapon-wheels.md) for runtime evidence, the
multiplayer quick-chat wheel and the remaining wider section 14.6 work.
openQ4-game's hit marker is on by default in single player and multiplayer and
replaces the stock pop, where section 14.7 keeps the pop and offers markers in
multiplayer only. The hit-marker discrepancy remains to be reconciled before that section is accepted.

The [17 September implementation audit](../../../ui/masked-input-review.md) refreshes
delivery priorities and repairs vector-mask pointer/focus eligibility. The
complete runtime/editor/corpus scope and every remaining stage gate stay open.

The [independent text-scale increment](../../../ui/text-scale.md) adds runtime
100–200% typography and responsive SYSTEM field, column, status and modal layout.
The subsequent [interface preference increment](../../../ui/interface-size-preferences.md)
adds transactional scale choices/reset and a root-menu window-fit limit.
Complete screen/editor qualification remains required; the full plan stays active.

The [output-size font increment](../../../ui/output-size-fonts.md) replaces the
retained adapter's fixed 48-point slot with bounded physical-size glyph atlases.
`TXT-002` remains partial: style/weight, largest animated transform density,
complete text services and full qualification are still required.

The [paired-field visibility repair](../../../ui/paired-field-focus.md) aligns
SYSTEM slider and numeric viewport heights under independent text scaling.
Focus now reveals their complete paired values; full `LAY-004` and product
acceptance remain open.

The [SYSTEM display-control increment](../../../ui/display-controls.md) adds four
existing catalog settings to the production document and observes the strict
display path's MSAA availability. Fullscreen/window-manager qualification,
dynamic catalogs, complete effects and the editor round trip remain required;
`BEH-002` and `FLOW-002` stay partial.

The [SYSTEM dimension-field increment](../../../ui/dimension-controls.md) adds window
and custom fullscreen width/height, exact integer text validation and dependent
availability. Intermediate dimensions remain drafts; complete capability checks
guard Apply. Dynamic display/resolution/refresh choices, visible fullscreen,
native input, complete effects and the editor remain required. No gate closes.

The [SYSTEM render-options increment](../../../ui/system-render-options.md) adds
Preload Light Grids with its help and a status line naming what the loaded map
does with its light grids. Apply completes it through the deferred executor
without Keep/Revert, and the next map load uses it. The following increment
adds Renderer Fallback: the row drafts `r_renderer` (Auto or ARB2) and applies
it through the renderer executor's checked restart. It is available where a
presenting OpenGL renderer reports its selection, and a notice says when the
renderer fell back from an unavailable or retired request. The
[display list increment](../../../ui/system-display-catalog.md) adds the service
those rows will read. It builds the device, resolution and refresh lists from
one cached topology capture, with localized labels, publishes them to the page
owner and turns a pick checked against the list's token into settings. A
display picked from the list must still be that monitor at Apply. The
[display rows increment](../../../ui/system-display-rows.md) adds Display Device and
Expand Across Displays over those lists, hidden on one display unless the draft
names a display or a span the lists cannot offer, or holds a change not yet
applied. The [resolution rows increment](../../../ui/system-resolution-rows.md) adds
Display Resolution and Refresh Rate, so the page now has a control for every
stock setting; it stays opt-in while presets cannot apply from it. Its size
fields take typed digits since committed characters reach retained fields
([typed characters](../../../ui/numeric-fields.md#typed-characters)). Auto refresh now means the desktop rate on every
display path, and MSAA applies on Vulkan. `BEH-002` and `FLOW-002` stay
partial.

The [retained screen increment](../../../ui/retained-screens.md) builds the title
screen, the single-player pause menu and the stock loading screens from
visual specification 1.7 and the design atlas, behind one `ui_retained` gate
(on by default for new profiles again since 14 October, after the 12 October
prerelease turned it off; `ui_retainedSystem` opts into the SYSTEM page,
which joins the gate once every stock setting works there). It adds image
nodes, additive and multiply path blends, a view-height canvas, typed session
menu requests and exact overflow clipping under translation and scale. The
loading screen shows the Remastered progress: the loader's phase with its
place or asset count, the percentage, the load time and a controller continue
prompt, and in multiplayer the server card and JOINING. Its confirmations
and the pause menu soften the screen beneath them on OpenGL and Vulkan,
keeping a darkening scrim for the opaque-backing option and GLES; resuming
releases the pause's softening over 250 ms as the game runs. After
Kane's stroggification the pause menu takes the Strogg family, and its labels
translate from runes as it opens. The pause menu's OBJECTIVES opens the
objectives display as a page of the pause, with every objective, its
screenshot and description, and the ones completed on the level. A
multiplayer load fills the arsenal with each kind of item as it spawns, and
Single Player's Campaign opens as a sub-page with the band step and crumb.
Single player loads run localized tips. The multiplayer server card lists the
players by team and the server's message, on the host, on a map change and on
a fresh connection (an optional roster block after the connect response's
server info). The [multiplayer Escape card](../../../ui/multiplayer-menus.md) now
covers the game's in-match menu by default: the card, its header, the
eight-tab strip, the prompt bar, the Disconnect confirmation and the
softening, with every page built: Team, Players, Vote, Settings (name and
clan in its own text fields), Voice, Server, Match (all six of Match
Control's sections, the referee signing in with a masked field) and Admin
(the remote console password, Players with kick, ban, force team switch and
the ban list, Server with the drafted rules and Apply changes, and Console);
the Welcome card covers the connect-time join offer, by default now that all
its pages are built, and a join's loading screen hands over to it.
Event programs can move focus; Q, E and the shoulders page a document's
tabs, the triggers its sections, and a controller's west and north run its
secondary and tertiary actions. Prompts show the active device's glyphs:
keycaps, or the controller family's face buttons (Xbox, PlayStation,
Nintendo, Steam Deck or generic), which the HUD's `in_promptStyle` forces
for the menus too, and
Nintendo layouts confirm on the east button unless `in_swapConfirmBack` says
otherwise. The initializing screen and the weapon wheels are the ones
described above; the retained page line built its own of both, and of the
campaign difficulty page, and gave them up when it merged into main on
14 October. LOAD GAME on the title and the
Marine pause opens the retained [Load Game page](../../../ui/retained-screens.md#load-game-page),
the stock page's content over the home that handed off to it, with selection,
loading, deletion with confirmation, failures in context, the empty state and
paging. SAVE GAME on the Marine pause opens the retained
[Save Game page](../../../ui/retained-screens.md#save-game-page) the same way, its
name in a new `text` field ([text fields](../../../ui/numeric-fields.md#text-fields)),
with the overwrite confirmation, the autosave refusal and the session's
reasons in context. Committed characters now type into a focused retained
field ([typed characters](../../../ui/numeric-fields.md#typed-characters)), so the
SYSTEM page's size fields take typed digits and only presets keep it opt-in.
RESTART LEVEL on the Marine pause opens the retained
[Restart Level page](../../../ui/retained-screens.md#restart-level-page): the
difficulty plates beside their description and the enlarged primary plate of
the stock New Game layout.
Accepting a campaign on the Campaign sub-page descends to its difficulty and
Turbo setup, the fourth level (`campaign_skill.q4ui`).
DEMOS on the title opens the retained
[Demos page](../../../ui/retained-screens.md#demos-page): the demo library under
filter tags, the selected demo's picture and lines, and PLAY, DELETE and
REFRESH, on the Load Game page's construction.
MODS on the title opens a retained list dialog, the modal construction grown
to 280 u, with the installed mods, their details, LOAD MOD and CANCEL.
After the player dies the retained
[restart screen](../../../ui/retained-screens.md#restart-screen) offers RESTART,
LOAD GAME, MAIN MENU and EXIT GAME over the stock popup art.
CREDITS on the title opens the retained [Credits page](../../../ui/retained-screens.md#credits-page):
the stock credits' choreography compiled into one repeating timeline, its words
read from the stock menu at runtime.
ARENA on the Single Player page opens the retained [Arena page](../../../ui/retained-screens.md#arena-page),
its second sub-page: the Arena campaign's tier ladder, matches, detail column,
entrance and result ledger, the campaign publishing into it and keeping its
authority.
MULTIPLAYER on the title opens the retained [Multiplayer page](../../../ui/retained-screens.md#multiplayer-page),
the stock Multiplayer page's level: JOIN GAME, CREATE SERVER and PLAYER SETUP
open the stock browser, Create Server and Settings pages, whose Back returns
to it. CREATE SERVER goes deeper to the retained
[Create Server sub-page](../../../ui/retained-screens.md#create-server-sub-page), the
stock page's map selection and options with the session owning each setting,
the passwords on masked text fields
([text fields](../../../ui/numeric-fields.md#text-fields)) and the ban list in a
nested dialog; it is the default, as it offers all the stock page does.
JOIN GAME goes deeper to the retained
[Join Game sub-page](../../../ui/retained-screens.md#join-game-sub-page), the
server browser's list with its sources, column sorts, symbols, mod filter,
a filter row under the list (the game type's spinner and the NOT FULL, NOT
EMPTY and NO PASSWORD tags), favorite toggle and the chosen server's levelshot, JOIN IP ADDRESS and FIND
PLAYER/CLAN in entry dialogs, the scan's progress bar under the list, a
network quality bars beside each ping, a server's players and settings in
the stock tooltip's card beside the
pointer's or the focused row (the runtime's detail card), a controller's
west refreshing the list and north sorting it by the next column, the session
publishing the scan as it finds servers; it is the default, as it offers every control the stock page does.
After Kane's stroggification the pause's SAVE GAME, LOAD GAME and RESTART
LEVEL open the same pages in the Strogg family
([Strogg pause pages](../../../ui/retained-screens.md#strogg-pause-pages)).
In-field composition remains. No gate closes.

## Objective and immutable completion scope

Plan, implement and publish a complete idTech 5-esque replacement for openQ4's
GUI system on branch `idtech5-ui`. Commit and push after each completed stage.
Deliver DPI-aware, aspect-expanding, high-definition Quake 4 interfaces,
quality vector furniture, continuous transitions and an extensive visual
editor. Replace every current GUI. Use bitmaps only for complex imagery.

The normative [visual design specification](../../../ui-visual-design.md) precedes
screen/vector/editor design. Preserve the complete objective when stages need
more than one work session. Neither conversion counts nor a successful main
menu launch establishes completion. Temporary coexistence is a migration tool,
not the final architecture.

## Branch and source ownership

- Engine branch: `idtech5-ui`, initially based on `23847b22` from the current
  `android-gles` checkout so its Android/GLES integration is retained.
- Companion branch: `idtech5-ui`, initially based on `f9bf8a692de539b9d149cc7b2c47759dbb1ddd62`
  from its current `android-gles` checkout. Record paired revisions in reports.
- New game/UI bridge edits are canonical in `openQ4-game`; no `src/game` mirror.
- Runtime-authored sources live under `content/baseoq4/`; engine defaults that
  need no user editing can be compiled resources. Build outputs belong in
  `builddir/`; runtime installation remains `.install/` and `.install/baseoq4/`.
- Retain evidence for each completed stage. The user-directed main integration
  supersedes the original branch merge gate; release promotion still requires
  the final qualification stage and does not follow from this merge.

## Architecture decision

Adopt an idTech 5-style retained document/component and timeline architecture,
with a modern density/layout model and an editable vector source pipeline.
Use RmlUi as the initial layout/text/input integration candidate, with native
engine vector components and a renderer adapter. Its standard SVG bitmap
plugin is not sufficient for the required vector furniture. The dependency
selection is gated on the stage 2 spike; if RmlUi prevents faithful vector
composition or editor round trips, record the evidence and revise the
implementation choice without narrowing the visual/functional requirements.

Do not port an entire Flash VM simply to obtain paths and transitions. The
GPL-released Doom 3 BFG/RBDOOM SWF systems are useful references for retained
display lists, masks, state and timeline editing. They are not proof of
automatic DPI awareness or high-refresh animation. Current reference sources:

- [Doom 3 BFG](https://github.com/id-Software/DOOM-3-BFG): GPLv3 with additional
  notices; retail data excluded from its source licence.
- [RBDOOM](https://github.com/RobertBeckebans/RBDOOM-3-BFG): SWF/JSON tooling and
  maintained id-family rendering reference.
- [RmlUi](https://github.com/mikke89/RmlUi): MIT layout/input library;
  [render integration](https://mikke89.github.io/RmlUiDoc/pages/cpp_manual/interfaces/render.html),
  [density units](https://mikke89.github.io/RmlUiDoc/pages/rcss/syntax.html),
  [SVG bitmap behavior](https://mikke89.github.io/RmlUiDoc/pages/cpp_manual/svg.html).
- [SDL3 DPI model](https://wiki.libsdl.org/SDL3/README-highdpi): distinct window,
  drawable, density and content-scale values.

No external implementation code is incorporated in the specification stage.
Before integrating a library, pin an exact release/commit, inspect its licence
and transitive dependency licences, preserve notices and add README credits.
Use Meson subprojects; do not add an independent build/package system.

### Document and renderer boundaries

Canonical UI sources need stable document/node/component IDs, typed properties,
constraints, vector paths, tokens, state variants, bindings and timelines. The
editor must losslessly round-trip these sources and explicit extension metadata.
Choose the serialization during stage 2 and version it before translating
assets. If layout markup is generated, it is derived from this model and must
never become a competing source of truth.

The runtime translates documents into ordered draw operations for triangles,
strokes, gradients, text, pictorial materials, clips, transforms and composition
layers. OpenGL, Vulkan and GLES consume equivalent operations. Vector flattening
uses output-space error bounds; cache keys include relevant scale and transforms.
Keep generated geometry out of fixed-size texture atlases. Font atlases may
remain generated coverage textures with density-aware cache invalidation.

The renderer owns graphics resources and thread synchronization. The UI model
owns layout, state, input and animation. The editor owns source mutations and
history. Game libraries communicate through semantic state/events/commands,
not renderer internals or implementation-specific node pointers.

### Behavior compatibility

Translate geometry and behavior. Preserve GUI dictionary values, expressions,
named events, timelines, commands, script-driven visibility, material stages,
text escapes, localization, sound routing and world-GUI instances. Preserve
save/restore semantics and define a migration/version policy before cutover.

The transitional `idUserInterface` now exposes presentation value and focused
text-field operations in place of `GetDesktop()`/`idWindow`. The coordinated
[presentation boundary](../../../ui/presentation-bridge.md) removes direct session,
SDL and SP/MP player accesses. Retained alias mapping and complete semantic
state/action dispatch remain to be implemented; removing pointers alone does
not establish replacement parity.

Inventory special window types and implement functional replacements, including
render/model previews and any used custom game/instrument widgets. Unsupported
syntax, missing includes or unresolved materials must produce explicit
diagnostics and keep a resource unqualified, never silently disappear.

### Input and application ownership

Use SDL3 platform events, localized text input/composition, navigation actions
and projected world-GUI hit coordinates. Window/drawable/layout transforms must
be composed once and inverted for hit testing. Menus have explicit focus,
modal and activation lifetimes. Press/release pairing prevents click-through.
Touch and gamepad interaction share semantic controls without requiring a
synthetic pointer for every operation.

For automated validation, use engine-internal named events/state fixtures and
engine screenshot commands. Do not inject or capture OS keyboard/mouse input.
Interactive manual manipulation requires specific user permission. No game
test may launch fullscreen without permission for that exact test.

### Editor ownership

Provide a desktop editor integrated with the engine UI renderer and runtime.
It must expose hierarchy, precise layout and vector manipulation, components,
variants, bindings, state preview, timeline/easing editing, localization,
undo/redo, atomic save, autosave/recovery, source diagnostics and output presets.
See the visual specification for detailed acceptance requirements. Preview
and the game share evaluators/renderers; a separately styled web preview is
insufficient. Runtime packages must not acquire editor-only linker artifacts.

## Stages and exit evidence

Stages are ordered dependencies, not estimates. Each needs a scoped review,
appropriate tests, documentation and pushed commits. Split work within a stage
when useful, but mark the stage complete only when its exit evidence exists.

### Stage 0 — specification and delivery plan

- [x] Create `idtech5-ui` branches in engine and companion repositories.
- [x] Write extensive normative appearance, density, layout, state, motion,
  vector, family, editor and qualification requirements before visual authoring.
- [x] Retain old GUI conventions as a clearly historical translation reference.
- [x] Record complete scope, dependency decision, stages and completion audit.
- [x] Review links/status, commit both repositories and verify pushed heads:
  engine `7a0b8153897d37feeaab0cd883697e245f727500`, companion
  `9a2d8715fc40d4f5b1ca1cfd7f90230baf3192f2`.

Exit: published specification/plan and companion integration note. No runtime
or visual-completion claim is associated with this stage.

### Stage 1 — asset and behavior inventory

- [x] Enumerate effective sources from installed PK4s and repo overrides with
  explicit precedence, duplicates, case collisions, hashes and include graph.
- [ ] Parse/tokenize resources without interpreting comments/strings as syntax;
  enumerate windows, properties, expressions, named events, scripts and assets.
- [ ] Classify every root, include, special widget and referenced material;
  distinguish geometry furniture from complex bitmap exceptions.
- [ ] Produce a migration manifest with unresolved cases explicit, dependency
  ordering and per-resource behavioral/visual qualification fields.
- [ ] Record baseline engine captures and behavior fixtures for every family,
  with SP/MP entry paths and map/state requirements.

Exit: reproducible complete inventory and family baseline evidence, including
all diagnostics and still-unclassified resources; no inferred translated status.

### Stage 2 — document, layout, time and engine integration

- [x] Pin/check dependencies, integrate through Meson and credit incorporated code.
- [ ] Version canonical document/token/path/timeline schemas and editor metadata.
- [ ] Load/validate documents with stable IDs and actionable source locations.
- [ ] Implement DPI, viewport, anchoring/expansion, text-scale and clipping math.
- [ ] Implement continuous timelines, easing, interruption, pause and cancellation.
- [ ] Introduce runtime/game bridge and retain explicit temporary migration routing.
- [ ] Render and interact with one representative screen on GL/Vulkan in gameplay;
  validate the chosen layout library against vector/editor requirements.

Exit: an actual integrated runtime, native behavioral/math tests, paired game
builds and windowed engine captures. A standalone math test is partial evidence.

### Stage 3 — production vector renderer and component kit

- [ ] Adaptive paths, fills/holes, strokes/caps/joins, gradients, masks and layers.
- [ ] Antialiasing, premultiplied/color contracts, transforms and density caches.
- [ ] Font rendering, localization, escapes, shaping policy and IME integration.
- [ ] Measured Marine/Strogg/world/vehicle primitives, icons and all widget states.
- [ ] Screenshot comparisons across DPI/backends and measured rendering cost.

Exit: every specified primitive/component represented with editable sources,
state gallery, output-space quality evidence and backend equivalence.

### Stage 4 — editor foundation and real source round trip

- [ ] Shared runtime preview, document hierarchy, selection and property inspector.
- [ ] Editable source model, undo/redo, atomic save and reopen without data loss.
- [ ] Canvas transforms, snapping, anchors/constraints and component instances.
- [ ] Initial path/timeline editing and source-linked diagnostics.
- [ ] Edit/package/run a representative screen through engine and companion.

Exit: demonstrated source round trip, recovery tests and exact-renderer preview.
This is an intermediate editor, not the full editor-delivery gate.

### Stage 5 — full translation and behavior replacement

- [ ] Import every inventoried GUI/include into canonical replacement documents.
- [ ] Implement all used properties, expressions, events, commands and widgets.
- [ ] Replace `idWindow` coupling in engine and canonical SP/MP game sources.
- [ ] Verify per-entity instances, game-state updates, model/material previews,
  save/checkpoint/restore, loading, cinematic and scripted-terminal behavior.
- [ ] Inventory confirms zero missing replacements and zero silently ignored syntax.

Exit: complete functional replacement corpus and per-resource parity evidence.
Retaining bitmap furniture or old GUI rendering does not qualify visually.

### Stage 6 — full visual reconstruction and screen polish

- [ ] All furniture vectorized with source-specific silhouette/detail fidelity.
- [ ] Responsive composition, optical alignment, states and motion for every screen.
- [ ] All bitmap exceptions reviewed as complex imagery, not convenience fallbacks.
- [ ] All languages, text scales and families reviewed against the specification.
- [ ] Every manifest entry has traceable behavioral and visual acceptance evidence.

Exit: high-definition full corpus; generic styled approximations do not pass.

### Stage 7 — extensive editor completion

- [ ] Full vector pen/handles/gradients/fill rules/import/export.
- [ ] Timeline/easing/multi-key editing, state graphs and binding ownership tracing.
- [ ] Dockable/multiple-document workspace, component variants, align/distribute,
  preview fixtures, asset search, diagnostics and performance inspection.
- [ ] Autosave recovery, external changes/conflicts, stable source round trips.
- [ ] Full specified edit/localize/bind/animate/save/package/SP+MP demonstration.

Exit: the complete editor contract, not a subset renamed as finished.

### Stage 8 — cutover, packaging and release qualification

- [ ] Replacement is the default for all current GUIs; obsolete renderer/window
  implementation removed or isolated solely for an explicit external-mod policy.
- [ ] No current resource relies on temporary legacy routing or raster furniture.
- [ ] Windows/Linux/macOS/Android-GLES and dedicated build/packaging qualification.
- [ ] SP/MP gameplay, world terminals, scope/vehicle/cinematic/save/restore coverage.
- [ ] DPI/aspect/refresh/input/localization/extreme-combination evidence matrix.
- [ ] No unexplained renderer/UI warnings, file leaks, unbounded cache growth or
  material performance regressions against the captured representative baselines.
- [ ] README, user/editor documentation, credits, candidate and curated release
  notes describe the delivered behavior and actual upgrade requirements.
- [ ] All stage commits pushed and exact remote revisions verified.

Exit: requirement-by-requirement audit of actual files, builds, packages,
screenshots, behavior results and editor use. Missing or indirect evidence keeps
the goal active. Do not claim cross-platform support from Windows-only tests.

## Evidence discipline and progress log

Store temporary tools/captures under `.tmp/`; keep reproducible commands and
compact reports in documentation. Do not commit proprietary retail extractions.
Use `builddir/` and the provided MSVC-aware Meson wrapper. Stage with
`meson install -C builddir --no-rebuild --skip-subprojects` through that wrapper.
GUI captures come from engine `screenshot`; logs come from the configured
savepath/game directory. Do not substitute OS captures or main-menu-only tests.

Before marking a stage complete, record requirements covered, exact commands,
tested revisions, outcomes, remaining scope and unrelated issues. After a
successful commit/push, verify remote heads before saying the stage is published.

| Date | Stage | Authoritative progress | Remaining |
| --- | --- | --- | --- |
| 2026-09-08 | 0 | Specification/integration contracts committed and pushed in both repositories; remote heads verified | Complete |
| 2026-09-08 | 1 | Effective VFS inventory and native structured import implemented for 271 resources; 15,414 preprocessed windows and 8,654 events, with two explicit expression diagnostics; migration seed remains pending | Full semantic/binding classification, material/bitmap decisions and family gameplay baselines |
| 2026-09-08 | 2 | Retained engine rendering, density and rectangular clipping integrated; canonical documents, value edits, presentation tracks, controls, SDL/session ownership and typed application/CVar expression bindings implemented | Complete component/event/binding semantics, game bridge and legacy lowering, text/IME and broader input qualification, transformed overflow clipping, text backend and representative screen/editor qualification |
| 2026-09-08 | 3 | Editable responsive paths, winding fills, stroke unions, linear paints, analytic coverage, isolated subtree opacity and editable alpha masks integrated | Broader composition effects, complete paints/strokes/fonts, production components and all artwork, performance and broader platform/visual qualification |

Inventory methodology and limitations: [inventory report](../../../ui/inventory-report.md).
The [native import checkpoint](../../../ui/legacy-import.md) records source/hash-bound
preprocessing, ordered declarations, expression/script trees and dependency
records. SP/OpenGL and MP/Vulkan produce identical exports; none of the 271
resources is accepted as a replacement.
Canonical source and motion contract: [document checkpoint](../../../ui/document-format.md).
[Live state bindings](../../../ui/bindings.md) now update geometry, text and availability
without rebuilding documents, validate state batches atomically and retain
application values through renderer/language changes. Native checks and reviewed
SP/OpenGL and MP/Vulkan captures pass. The game bridge, legacy lowering and full
Stage 2 completion remain open.
The [presentation boundary](../../../ui/presentation-bridge.md) now separates session,
game and SDL consumers from legacy windows, with read-only value queries and
explicit expression overrides. Game API 48 requires coordinated engine/SP/MP
modules; retained document alias mapping and action dispatch remain open.
The [instance checkpoint](../../../ui/instances.md) removes the single-document
runtime restriction, isolates state/input/layout/clocks, reuses per-view render
backends and protects composition target identities within a host submission
frame. Normal GUI-manager routing, coordinated engine multi-view resource
reset, world surfaces and save restoration remain open.
The [ownership and persistence checkpoint](../../../ui/instance-persistence.md)
adds a private manager contract with safe allocation/destruction and versioned,
transactional canonical snapshots. Preview resource reload now preserves focus,
modal scopes, unbound control availability and transition progress as well as
application values. The retained manager adapter, real application operations,
world output and game-save/demo framing remain required M1 work.
The subsequent [application integration checkpoint](../../../ui/managed-application.md)
adds explicit retained/deferred normal loading, typed brightness/shadow operations,
bounded per-GUI save framing and coordinated engine view invalidation. Complete
events/aliases, text/control contracts, production mappings, world surfaces and
the surrounding game save/demo format remain M1 work. This does not accept a
production GUI or close the complete system-screen/editor milestone.
The [writable presentation alias checkpoint](../../../ui/presentation-aliases.md)
extends this integration with shared metadata slots, typed property conversion
and durable expression ownership. Full semantic lowering and production screen
acceptance remain open.
The [event-program increment](../../../ui/event-programs.md) adds ordered canonical
state/presentation/motion programs, typed action capture and lifecycle delivery
through normal session ownership. Source-specific legacy lowering, complete
widgets, world/save/demo integration and production GUI/editor acceptance remain
required work; this does not close Stage 2 or M1.
The [SYSTEM settings increment](../../../ui/system-settings-contract.md) adds a fixed
53-field catalog, owned drafts, typed application operations, conflict-safe
rollback and frame-owned closure/recovery. Reserved settings state cannot be
overwritten by GUI programs or pending caller data. Immediate changes use the
production host. Eligible confirmation documents can now apply display batches
through the [durable confirmation coordinator](../../../ui/display-confirmation.md);
audio/resource, next-map and preset effects still reject the entire batch before
writes. Complete settings controls, editor and platform qualification remain
required M1/M2 work.
The [display-device foundation](../../../ui/display-device-contract.md) adds strict
actual window queries, recoverable typed renderer restart/restore and backend
presentation observations. An engine-owned SDL video reference preserves live
display identity across failed attempts. The asynchronous settings coordinator,
durable journal, owner-present confirmation and strict startup recovery are now
implemented. Complete platform/production qualification remains required, and
this integration accepts none of the 271 production GUI entries.
Semantic buttons now use authored state timelines, projected hit testing,
source-order/spatial navigation and modal focus ownership. The
[interaction checkpoint](../../../ui/interaction.md) records native behavior checks,
SP/OpenGL and MP/Vulkan engine traces and reviewed rendered states. Game
dispatch, other widgets and the full Stage 2 gate remain open;
these fixtures accept no stock GUI as a finished replacement. Subsequent
[SDL/session ownership](../../../ui/input-routing.md) integrates the device adapter,
console handoff and gameplay release gates; game dispatch and complete platform/
widget qualification remain open.
Native path source/compiler: [vector checkpoint](../../../ui/vector-paths.md). Curves,
holes, strokes, gradients, responsive cuts and
[analytic pixel coverage](../../../ui/coverage-antialiasing.md) are integrated.
Broader composition effects, quality/performance qualification, full art reconstruction
and the complete Stage 3 gate remain open.
Runtime CPU counters, repeatable native/gameplay profiles, opacity/integer-motion
cache reuse and stable tessellation are recorded in the
[performance checkpoint](../../../ui/runtime-performance.md). Optimized-build, GPU and
full-corpus costs are still unqualified.
Isolated source-over opacity layers are now integrated with GL/Vulkan targets,
transparent clears, image alpha coverage and stable subtree ordering. The
[composition checkpoint](../../../ui/composition.md) tracks native overlap checks,
matching-panel pixel comparisons and paired renderer/game API requirements.
Editable mask geometry now uses the same vector compiler for shaped clipping,
holes and soft reveals. The [mask checkpoint](../../../ui/masks.md) records its alpha,
nesting, resource lifetime and qualification evidence. Other effects and the
complete Stage 3 gate remain open.
GL/Vulkan composition pixels pass in the current fallback draw paths; requesting
the shared GUI owner still reports zero owned views in these captures. Shared
ownership and total GPU image-pool trimming remain explicit follow-up work.

The subsequent [native-output OpenGL repair](../../../ui/native-output.md) removes a
completed-frame scale filter that could blur UI-only frames. Scene sizing and
resolves remain in place, including the explicit legacy mode-0 crop. Bound
Windows SP/OpenGL before/after pixels provide partial evidence for SUR-006;
M6 and every original runtime,
editor, artwork, migration and platform gate remain required.

The subsequent [text-entry foundation](../../../ui/text-entry-foundation.md) adds
atomic Unicode editing, bounded undo/redo, exact numeric parsing, checked
Windows clipboard primitives and pending event-payload cleanup. These are
build-integrated services. This checkpoint accepts no original stage gate.

The [numeric field integration](../../../ui/numeric-fields.md) adds the canonical
Number role, actual RmlUi caret/selection/composition rendering from shared
scalar runs, precise typed proposals and durable local drafts. Focus and input
loss retire composition and edit identities while preserving text/history;
explicit Keep/Reload decisions resolve authoritative-source conflicts. Nested
widget snapshot version 2 restores drafts inactive and rejects malformed or
over-budget state atomically. Semantic adapter diagnostics exercise this layer
without device input. Event-journal ownership/validation is hardened as an
adjacent prerequisite for additional owned input records. Ordered native/IME
delivery, shaped/grapheme/bidirectional runs, production field artwork and
validation, Apply/exit handling of unconfirmed drafts, and full platform
qualification remain required. No requirement, migration or final gate becomes
accepted merely from these integration tests.

The [editing-command and native-delivery increment](../../../ui/text-input-routing.md)
adds ordinary numeric command keys, current-buffer text-run navigation, exact
held-source ownership, per-event modifier metadata, a bounded native input broker,
an explicit wire codec and exact SDL echo association. The reviewed Windows
observer is compiled but remains disabled while managed owner delivery, dispatch
fencing and native TSF ownership are implemented. This does not accept the text,
platform, editor, migration or final product gates; every original requirement
remains in force.

The subsequent owner/store checkpoint adds exact managed allocation, backend,
document and editor checks; event-queue continuity; a portable native shadow
document; and an actual Windows SDK text store with application change and
layout notifications. Its final Windows build and 29 UI suites pass, including
the updated text-store suite. Two windowed gameplay captures cover 32 semantic
operations and ten render-target images. The first disabled SDL dispatch fence
still needs checked queue consumption before activation. Native field routing,
composition reconciliation, complete text shaping, production controls, artwork,
editor and every migration/final gate remain required. Evidence is preserved in
`.tmp/ui/native-owner-integration/validation-evidence.json`.

The precise SYSTEM-field increment pairs the original Brightness and Ambient
Brightness sliders with numeric entry, localized validation and checked
clipboard commands. Unfinished active or inactive text blocks conflicting
settings work and exit; Keep Editing resumes the draft, and Discard waits for
completed service cancellation before clearing local text. The production
modal-focus path refreshes projected layout before resuming the field. The
Windows build and 32 UI suites cover these changes, including an actual-Rml
same-dispatch modal regression and growing-validation scroll checks. SP/OpenGL
at 125% density and MP/Vulkan at 200% each pass 37 semantic operations with 17
reviewed engine images after gameplay; notices, safe draft continuation, Apply,
Discard and reopen are covered. The scoped record is
`.tmp/ui/native-editing-integration/validation-evidence.json`.
Checked SDL queue consumption, owned event
collections and the portable multi-transaction composition reconciler are also
implemented, with native activation still disabled. The scoped evidence remains
separate from complete native input, international text, all production pages,
the editor, every migration and all final gates. No acceptance status changes.

The [managed native bridge and focus increment](../../../ui/numeric-fields.md) connects
the private managed-owner endpoints and Windows collection hooks, with exact
lifecycle receipts and copied idle coordinator barriers. Exact numeric values
also survive transaction, journal and startup-recovery comparisons. Shared
[focus reveal](../../../ui/focus-reveal.md) keeps the complete focused control border
inset within authored scroll limits. The Windows build and all 40 UI suites pass;
SP/OpenGL at 125% and MP/Vulkan at 200% each pass 38 semantic operations and
12 reviewed engine images after gameplay. At 200%, the focused field has the
intended 8-pixel gap inside its scroll body. The source-bound record is
`.tmp/ui/native-managed-bridge-integration/validation-evidence.json`.
Native activation, production Session delivery, complete settings effects,
international text, full layouts and editor support remain in development.
The full original scope, all 271 migrations and every final gate remain open.

The preset and Windows text-session increment adds shared six-profile draft
expansion and source-derived localized controls to the opt-in SYSTEM page.
Guarded publication preserves unrelated edits; incomplete local Number edits
prevent conflicting actions. A checked constructing-STA controller owns Windows
text-service activation and quiescence, with live activation still disabled.
See [performance presets](../../../ui/performance-presets.md),
[native text routing](../../../ui/text-input-routing.md) and the source-bound record
`.tmp/ui/preset-session-integration/validation-evidence.json`.
The [unified effect direction](../../../ui/settings-effect-execution.md) preserves one
durable operation across renderer, image, audio and deferred policy. Full
implementation, editor, platform qualification and all migration/final gates
remain required; this increment changes no acceptance status.

The effect/input increment adds explicit automatic completion to the same
settings transaction/controller, and checked in-place audio ownership with
untouched-preparation cancellation and nonreleasing completion readback.
See [effect execution](../../../ui/settings-effect-execution.md) for its qualified
boundaries, the explicit schema-2 envelope and remaining portable recovery work.
Native event-storage sidecars and immutable polled slices retain original route
identity and payload ownership without changing the event wire format. Two
fixed schedules account for the real Session-first and POSIX poll-first entry
points. The SYSTEM opening layout gains a compact preset and wrapping footer
while retaining full-size targets and flowing text. Ordinary native delivery
and mixed settings Apply remain gated while their complete integration is built.
The source-bound record is
`.tmp/ui/native-effects-integration/validation-evidence.json`. No product,
migration or final gate is accepted by these foundation tests.

The checked renderer image/material restart now retains original recovery
inventories and invalidates them on instance replacement or metadata-only
changes. Full module linking, 49 UI suites and windowed gameplay through ordinary
video restart pass. See [effect execution](../../../ui/settings-effect-execution.md)
and `.tmp/ui/renderer-effects-integration/validation-evidence.json` for the
bounded result. Historical consumed policy, portable content reconstruction,
mixed Apply and every remaining product/editor/migration gate are still required.

The following increment adds exact [native input retirement](../../../ui/native-input-retirement.md)
inspection and original-editor presence checks, plus portable audio records and
historically consumed image/material policy observations. The engine and both
renderer modules build, and all 56 integrated UI suites pass. Native activation,
actual queue disposal, complete audio/image reconstruction and the unified
durable Apply path remain in development. Scrollbar geometry and editable SYSTEM
artwork are prepared; shared schema, interaction and rendered qualification are
being implemented. This progress does not accept any migration or final gate.

## Campaign source consolidation (1 October 2026)

Single Player → Campaign now shares engine-owned discovery and transition
commands across the compatibility menu and opt-in retained presentation.
`singleplayer.q4ui` and `campaigns.q4ui` are generated with the existing editable
Marine vector plates, docked 45-degree bands, typed readiness bindings and
localized text. The compatibility selector remains available with `ui_retained=0`.
Campaign setup now uses the fourth retained level described below. Chapters
and Arena remain part of the wider retained-screen migration. This completes campaign selection only;
it does not claim the complete UI/editor/migration programme is finished.

## Retained screens on by default (1 October 2026)

Historical milestone: the 12 October prerelease restores `ui_retained 0` as
the shipping default because performance overhead is still not negligible.
Archived preferences remain intact; this section records the earlier gate
and fallback work rather than the current default.

`ui_retained` now defaults to 1 and is archived. The SYSTEM page joins it only
once it has a control for every setting of the stock page; it still lacks the
display mode list, display device, multi-monitor, refresh rate, video quality
and light-grid preload, and `ui_retainedSystem 1` opts into it meanwhile. Each
retained screen presents its stock GUI instead when its document is not
installed (quietly) or cannot load (reported once), when the legacy main menu
lacks a page the title and pause screens hand off to (a mod's own menu), or when
its view fails after a renderer or language change. The SYSTEM page and the
campaign selectors fall back the same way, from the click that asked for them,
and CONTINUE shows a save's picture only when its file exists.
`ui_retainedStatus` lists the fallbacks after `stock=`. See [falling back to the
stock screens](../../../ui/retained-screens.md#falling-back-to-the-stock-screens). The
remaining stock pages, the editor and every migration and final gate stay open;
`SHIP-001` and `GATE-007` still require every stock route to have a qualified
retained replacement.

## Startup and view continuity (7 October 2026)

The 11 October refinement adds one settling focus swell and delayed inner
shade to death, and follows the three Air Defense crash wake-ups and two
blackouts with warm soft focus and feathered eyelids. Stock camera and script
timing remain authoritative. Reduced motion/flashing removes the transient
focus/afterimage accents. Qualification is recorded in
[retained screens](../../../ui/retained-screens.md) under `.tmp/view-effects-refinement/`;
this does not close the wider migration or platform gates.

11 October follow-up: initialization now redraws at cooperative startup
checkpoints, with a 30 Hz ceiling, measured-cost backoff and cached rotating
fill geometry. Reduced Motion skips optional frames. Native checks and staged
OpenGL/SP and Vulkan/MP gameplay entry pass; long synchronous operations still
limit continuity. [Performance evidence and limits](../../../ui/runtime-performance.md#initialization-animation-11-october-2026)
record this incremental qualification.

The engine's first initialization frames now use the layered vector design,
including localized stages and reduced motion. Shared menu-level helpers extend
the retained hierarchy to a fourth level: both campaigns open difficulty and
Turbo setup through the same reversible transition, and commit those drafts
only on Start Game. The route audit classifies settings tabs and Arena selection
as edits in place, multiplayer browser/create/demos as third-level pages, and
dialogs as modals. Future qualifying children, including Chapters, use the same
level helper.

All three scopes soften the view beyond a feathered optical aperture. The
`mcc_2` treatment gains gradual focus recovery tied to its original white fades;
death gains restrained color loss, peripheral shading and a brief afterimage.
Loading begins after a short smooth fade has reached full black. These effects
fill wide and tall views without stretching the optical center or obscuring HUD
text. The shared SP/MP implementation preserves the original game-state timing.

The [implementation record](../../../ui/retained-screens.md) links native geometry,
menu-routing and adapter checks, and engine screenshots from windowed OpenGL
and Vulkan gameplay. Evidence under `.tmp/ui-continuity/` also covers portrait,
German labels, reduced motion, real campaign progression and native 4K mesh
checks. Oversized engine screenshots expose a separate retained-effect tiling
defect and are excluded from visual acceptance. This is bounded development
evidence; the editor, outstanding screen
migrations, portable qualification and final product gates remain open.

### 7 October 2026: playback-driven graphs

Radio now uses a dedicated-channel PCM history through both legacy HUD drawing
paths, with silence, pause, stop and source changes reflected directly. The
atlas's radio and two voice sources use independent local audio playback.
See [implementation and evidence](../../../ui/audio-graphs.md). The MP drawing adapter
accepts separate incoming/outgoing stream bindings, but microphone voice capture,
codec and playback remain stubbed and are explicitly unqualified. Complete
Remastered HUD layout/behavior migration and other platform acceptance remain open.

### 7 October 2026: complete screen-space HUD presentation routing

The [HUD presentation bridge](../../../ui/hud-coverage.md) routes the
17 retail and 10 expansion screen-space HUD roots through the retained
renderer, with canonical vector art, preserved gameplay GUI state and atomic
stock fallback. Game-owned hit markers, damage numbers, movement input and
the client network graph use the same submission path. This is presentation
coverage; the remaining Remastered layout/behavior enhancements, world-surface
GUI migration and product/editor/platform gates remain open.

### 8 October 2026: the Remastered HUD layout

The [Remastered HUD](../../../ui/remastered-hud.md) pairs each covered stock HUD GUI
with a generated retained document that answers the same state and events and
lays its groups out on the section 14.4 anchors: the on-foot Marine and Strogg
HUDs (with The Awakening's), the multiplayer HUD, the walker and hover tank
HUD, the flatbed and tram gauges, the objectives display and notices, and the
scoreboard. The game publishes the fields the stock GUIs lack (structured kill
feed and chat, ordinals and gaps, the jump key, every objective, scoreboard
rows). Event replay before a HUD's first frame, copy-on-write motion values
with undoable event sampling, and frame-only incremental motion application
keep the large documents cheap. `openq4-ui-remastered-hud` checks every
document; captures cover gameplay in single player, multiplayer, a vehicle and
the objectives. The scoreboard includes Tourney's bracket tree. Later the same
day multiplayer gained the respawn prompt, the Minimal preset arrived
(`ui_hudLayout 2`), Settings > Game Options gained a HUD section, and the
air-defence cannon gained its Remastered optic with the transmission display
and the HUD prompt. The match summary, the chat entry and The Awakening's
vehicle displays remain on the stock layout.

### 11 October 2026: legacy instruments and retained HUD cost

The follow-up review approves the installed `waveform.tga` for radio and
voice displays, with the stock scroll and complete 21-sample height table.
This supersedes the approximate preset. The ECG also uses a stationary
repeating bitmap quad. Masks, colours, labels and Reduced Motion semantics
remain authored in the editable document.

Icons already originate as SVG and compile into retained native paths. Warm
icons reuse their tessellation and engine mesh. The current optimization
keeps those sources, caches completed vector panels, defers mask snapshots,
draws additive traces through disjoint mask coverage, limits composites to
artwork bounds and avoids redundant target binds. Application state parsing
and presentation layout also skip unchanged work. Hidden branches keep
advancing authored time without updating visible layout, and presentation-only
RmlUi updates defer their descendants until shown. Native qualification and
OpenGL/Vulkan engine captures pass. Isolated 720p SP/Vulkan and MP/OpenGL
comparisons still add 0.60 and 1.25 ms respectively; negligible-overhead
acceptance remains open in
[the release checklist](../../../release-completion.md).

The next optimization pass adds bounded runtime coverage atlases, settled-frame
replay with live bitmap UV sampling, direct opacity for disjoint image/glyph
quads, and deferred hidden CSS writes. Editable SVG sources remain canonical.
Allocation recovery and same-frame legacy fallback close implementation gaps;
the HUD state bridge also preserves case-insensitive keys and avoids repeated
normalization. Fourteen native suites, including full screens, all HUD families,
interactive widgets, document replacement and masked animation replay, pass.
The compiled production adapter and its 17 rejected mutations also pass.
The coordinated visible-window retry eliminates the former presentation stalls
but still measures +0.343 ms SP/Vulkan and +0.570 ms MP/OpenGL. Further fixes
preserve crosshair coverage quads for atlasing, replay unchanged captured HUD
packets, resolve isolated opacity without document layout, read HUD geometry
only after layout changes, and advance the stock peer's scripts without its
discarded layout/paint. Leaf opacity now remains live through replay, with
overlapping text retaining its composed target after an earlier-frame warm-up.
The warm-up closes a Vulkan first-draw font-upload gap; six opacity levels match
ordinary composition pixel-for-pixel on OpenGL and Vulkan. HUD forwarding uses
case-insensitive hash lookup. Detailed retained stopwatches run only on a profiler
request. Leaf-opacity reuse also skips redundant CSS formatting. Eight native
suites pass; seven sequential opacity samples, including returning to an earlier
value and crossing zero/full opacity, match ordinary composition exactly on
both APIs. After background jobs were paused, whole-window comparisons add
0.049 ms SP and 0.358 ms MP. The updated build's near-zero MP aggregate hides
opposing block differences; a longer-settled MP repeat still adds 0.218 ms
(+4.93%). The negligible-overhead requirement remains open. Work pauses at the
user's request after this validation checkpoint; the test reservation is released.
Current gameplay evidence and acceptance limits are recorded in
[coverage atlases and presentation replay](../../../ui/runtime-performance.md#coverage-atlases-and-presentation-replay-11-october-2026)
and `.tmp/ui-negligible-overhead/REPORT.md`.

The 13 October menu pass expands the existing coverage atlas to exact tiles and
multiply artwork, reuses stable compound plates, and caches the unchanged paused
single-player scene while continuing HUD/menu animation. It also reduces dense
coverage sorting and Gaussian shader work and skips quiet button layout.
Native fixtures and OpenGL/Vulkan engine captures qualify the individual paths.
The user's acceptance scope explicitly includes title and pause-menu frame
times alongside SP/MP gameplay; this gate is still open. Current measurements
and limits are in [menu and gameplay optimization](../../../ui/runtime-performance.md#menu-and-gameplay-optimization-13-october-2026).

The 14 October follow-up replays settled interactive paint, recaptures live
backdrops, and reuses unchanged button hit geometry. Eight native UI suites pass;
OpenGL/Vulkan captures cover focus, modal transitions and restart at 1280x720,
with the replay path also qualified at 720x1280. Pause CPU p50 is about
0.07–0.08 ms, but whole-frame title and pause comparisons remain above legacy.
The parity gate remains open.

The moving title glint now uses shader-evaluated convex mask coverage. A
retained-only off/on comparison reduces title frame time from 1.539 to 1.000 ms
on OpenGL and 1.255 to 0.574 ms on Vulkan. Nine native UI suites and same-frame
CPU/shader captures pass, including live opacity, source-cache fallback, resize,
four-sided masks and video restart. This is a measured improvement, not closure
of the legacy title/pause parity gate. Larger atlas pages were rejected for
worse residency; the 512-square/32-page bound remains.

The subsequent candidate holds the ordinary pause scene clock, reuses an
identical stock HUD evaluation and reduces repeated dictionary/number work.
Full-view soft focus uses a filtered half-resolution path only within its
qualified kernel and viewport guards; other cases retain full resolution.
The eleven UI/material suites and five production renderer/HUD adapters pass.
A flattened-menu surface experiment was removed after small, inconsistent
cross-renderer gains and additional composition rounding. Final comparisons
were refreshed at uncapped, 144 Hz and the default 240 Hz cap, with normal
menu animation. Refresh-limited means differ by at most 0.3%, but uncapped
title overhead is 2.9% on Vulkan / 17.6% on OpenGL and pause remains 39–44%.
The parity gate remains open; capped throughput is not an uncapped-cost result.

Moving-mask replay and fitted-image opacity replay now preserve the title's
glint and montage without repeated full-tree layout/traversal. Both APIs have
RGB-exact engine captures through motion and video restart, and all eleven
UI/material suites pass after rebuilding restored interface dependents.
Updated title comparisons are +1.1% on Vulkan and +10–17% on OpenGL in opposing
orders. Stable pause comparisons remain +40% on Vulkan and +49% on OpenGL.
A slow legacy Vulkan pause window remains recorded, without a parity claim.
Recorded draw reordering and constant blur weights did not show consistent
benefit and remain rejected. The [current evidence](../../../ui/runtime-performance.md#moving-mask-and-crossfade-replay-14-october-2026)
keeps the menu gate open.
