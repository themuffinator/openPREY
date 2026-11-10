# Game source consolidation and campaign selection

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Status: complete and published; both historical repositories archived,
1 October 2026.

The game libraries and Awakening single-player additions move into openQ4.
`openQ4-game` and `openQ4-game-awakening` become historical, read-only
repositories after their retirement notices and the replacement are published.

## Required result

- Preserve the existing worktree in a separate commit before migration.
- Preserve the imported source histories, original notices, SDK EULA and credits.
- Build the canonical `src/game` and `src/mpgame` directly from this checkout;
  builds, tests, CI and packages must not require either companion checkout.
- Compile Awakening's existing independently implemented SP classes, weapons,
  effects and script events into `game_sp`. Do not import the reconstruction or
  the expansion's multiplayer layer.
- Keep stock class spawning and saved object representations unchanged when
  Quake 4 is active. Scope Awakening class substitutions to its active campaign.
- Discover expansion content without mounting it or mistaking packaged metadata
  or old game binaries for a playable installation. Support loose and PK4 data
  under configured roots, plus an explicitly configured external content root.
- Present localized campaign selection in the existing single-player menu.
  Preserve the Arena Campaign option. Keep saves, Continue and autosaves in the
  existing `baseoq4` and `q4xbase` namespaces.
- Switch campaigns through a complete content reload, preserving the pending
  launch/menu request. Restore base content before multiplayer or Arena begins.
- Never load obsolete expansion modules or the leaked game binary. Preserve the
  user's original content and saves during upgrades.
- Keep all runtime modules under `baseoq4`, refresh release documentation and
  package notices, and make the SDK-derived source licence scope explicit.
- Publish retirement documentation to both companion repositories, archive
  them, and verify the resulting remote state.

## Validation

Record the source/build identity and savegames before migration. Verify the
Windows integrated build and stage; standalone engine-only and game-only
configurations; platform/packaging/CI contracts; stock SP with the expansion
absent and present; all thirteen expansion maps and save/restore; campaign
switches, class substitution, declaration precedence, module selection and
multiplayer/Arena isolation. Check both OpenGL and Vulkan where runtime evidence
is available. Promote the useful temporary Awakening checks into maintained
tests, with portable paths and engine-issued captures.

Source relocation must not change serialization. Existing saves from the
current supported save format must remain loadable. The alpha's missing assets,
unreachable features and invalid authored script calls remain documented content
limitations; they do not justify regressions in stock Quake 4.

## Licence and provenance boundary

This is a source consolidation, not a relicensing of id Software's SDK. Engine
GPL notices and accompanying Additional Terms remain intact. SDK-derived game
sources and their additions retain the SDK EULA and require the full game.
The licensing inventory must distinguish these scopes and must not suggest that
adding an EULA notice settles compatibility of linked distributions. No new
rights-holder permission or legal compatibility opinion is asserted here.

## Evidence

- Existing worktree snapshot: `98e453662704a79df722bc2f4696ddba8c42de03`.
- Base game import source: `4d87dbdb6934307988b371d3c794190a1380f322`.
- Awakening import source: `c49842986c0a519feeebc68d78e6f5509d99c3a7`.
- History-preserving import merge: `53a9bf2823e3123b8e1c2e19e7ff2dfbda3379bb`.
- Base retirement notice: `51c8d76927a6e9942865b048df0a28a34e1c55d5`.
- Awakening retirement notice: `d970ddfa908925e4d3878e2045065cbefb4c766f`.
- Published integration, including concurrent UI work: `14fb954e15cdf16546323fc0b6ccbe7265ca4c54`.
- GitHub confirms both companion default branches contain their retirement
  notices and both repositories have `archived: true`.

### Build and source checks

The integrated Windows x64 build, stage, standalone engine-only build and
standalone SP/MP game-only build pass using the canonical source tree. The
293 portable Python check entries were run; stale companion assumptions and
fixture adapters were corrected and failed entries rerun. The final macOS
alignment rerun also passes. Source stability guards pass on the rerun after
implementation edits stop. The campaign scope harness compiles and exercises
the production class substitution code in both SP and MP configurations.

The full debug native suite has 107 passes and five layout timeouts. All five
pass separately in an optimized build with assertions enabled, covering
scroll geometry, popup placement and SYSTEM display, dimensions and text
scaling. Together these qualify all 112 native cases. These checks do not
qualify runtime behavior on Linux, macOS or Android.

Python compilation, workflow YAML parsing, embedded Bash syntax and changed
PowerShell script parsing pass. Windows packaging and installer-script
generation pass. The generated package contains the component licensing
overview, byte-identical SDK EULA, engine Additional Terms and offline notices;
it contains no expansion content or expansion game modules. The installer
presents the component overview before installation. Inno Setup is not
installed on this host, so the installer executable was not compiled.

### Campaign runtime evidence

All tests use hidden windowed rendering, private writable paths and the staged
executables. They do not inject input or capture the desktop. Expansion assets
are independent test copies; the installed content is not modified.

| Gate | Result |
| --- | --- |
| Pre-migration stock saves | Five maps, save and load: ten individual cases pass; the combined baseline run was interrupted by an oversized expansion test PK4 |
| Pre-migration Awakening saves | All thirteen maps, save and load: 26 cases pass after splitting the test PK4s below the legacy ZIP limit |
| Existing saves with unified code | All five stock and thirteen Awakening saves load: 18 cases pass |
| Fresh OpenGL saves | Air Defense 1, Walker, Awakening's opening map and Cryofac each save and load: eight cases pass |
| Fresh Vulkan saves | Air Defense 1 and Awakening's opening map each save and load: four cases pass |
| Discovery | Absent, metadata-only, partial, complete loose and complete PK4 fixtures behave correctly; empty loose-file and late-patch shadows make the campaign unavailable |
| Campaign menus | Legacy and retained screens load; absent/partial/ready states fit 4:3 OpenGL and wide Vulkan captures, including German labels; retained parser warnings are rejected |
| Awakening to Quake 4 | Expansion gameplay followed by stock gameplay passes after a full reload |
| Awakening to Arena | Expansion gameplay followed by the base Arena browser passes; its engine capture is reviewed |
| Awakening to multiplayer | CTF gameplay uses the base MP module and excludes expansion content, even with an archived DM setting and a stale startup SP setting |
| MP startup and dedicated server | Both ignore the requested expansion overlay and enter stock CTF with the MP module |

The campaign handoff exposed two engine lifetime issues. Collision models held
material pointers across declaration teardown; shutdown now retires that cache
after the game releases its clips and before declarations are destroyed.
Replayed startup/config settings could also reset a queued CTF handoff to DM;
the rebuild now preserves the explicitly pending module and mode.

The maintained opt-in harnesses are `tools/tests/campaign_runtime.py` and
`tools/tests/campaign_selection_runtime.py`. Local reports, logs and
engine-rendered captures are retained under `.tmp/game-consolidation/`, including
`saves/baseline-awakening-gl.json`, `saves/unified-load-resumed-gl.json`,
`fresh-saves/`, `vulkan-saves/`, `selection-strict-gl/`, `menus-43-gl/` and
`menus-wide-vulkan/`. Each runtime report records the tested binary hashes.
Failure logs are retained alongside the corrected reruns.

This is map initialization, gameplay, switching and save compatibility
evidence, not a full campaign playthrough. The unfinished expansion still emits
known missing-effect, authored-script and spawn warnings. Stock MP precache/AAS
warnings and broader UI/platform qualification remain separate work.

### Publication reconciliation

The engine default branch advanced during validation. Its visual specification
1.14, modal motion, additive compositing and soft-focus changes were merged,
including the later pause-screen update. The affected production adapter,
resource lifetime and layer/soft-focus checks pass, as do the retained UI,
document and authored screen native checks. Retained campaign menus pass again
on OpenGL and Vulkan, and Awakening-to-stock gameplay passes again after the
merge. The requirement register keeps the earlier confirmation evidence and
passes its structural/source-binding audit without accepting new product gates.
Reports are retained alongside the original qualification evidence.
