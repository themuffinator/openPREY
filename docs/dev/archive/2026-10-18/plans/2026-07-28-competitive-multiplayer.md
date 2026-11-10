# Competitive multiplayer layer

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Date: 2026-07-28
Status: **Design record — one slice has landed, see below.**

> **Landed 2026-07-28: damage numbers only.** `mp/HitFeedback.{h,cpp}`,
> `g_hitFeedback`, `hud_damageNumbers`, plus `hud_damageNumberStyle` and
> `hud_damageNumberScale`, ported from Quake Live's damage plums. `hud_hitBeep`,
> the coalesced multi-hit payload, stats and every other part of §8.7 are
> untouched. Three deliberate divergences from what is written below:
>
> 1. **The transport is unreliable, not reliable.** §8.7 puts HITINFO on the
>    reliable channel and then has to defend against overflowing it. Damage
>    numbers are cosmetic and drop-tolerant, so they ride
>    `GAME_UNRELIABLE_MESSAGE_HITINFO` through `idGameLocal::SendUnreliableMessage`,
>    which cannot overflow a reliable queue and already forwards to whoever is
>    spectating the attacker. The reliable HITINFO can still be added later for
>    the parts of §8.7 that genuinely need delivery guarantees.
> 2. **One hit per message, not coalesced.** Coalescing exists in §8.7 to protect
>    the reliable queue; on the unreliable channel it buys nothing and costs
>    clarity.
> 3. **`g_hitFeedback` defaults to `2`, not `1`.** At `1` the amount is withheld,
>    which with only damage numbers implemented means the feature does nothing
>    when a player turns it on. The client switches still default to off, so
>    §4's "a player who edits nothing sees exactly what they do today" holds.
>
> The nine-cvar **Competitive** settings page (§4) is not built, so the three
> `hud_damageNumber*` rows are console and config only for now. They are
> documented in `docs/user/gameplay-settings.md`.
>
> **Validation actually performed (2026-07-29).** Dedicated server plus a client
> on `mp/q4dm1` DM. The wire path is verified end to end: the server built and
> queued a 17-byte `GAME_UNRELIABLE_MESSAGE_HITINFO` addressed to the attacker
> (`queued for icl=0 size=17 added=1`) and the client dequeued it as type 4 and
> parsed it back with every field intact (`dmg=9999 weapon=5 flags=2`,
> `flags=2` being `HITFLAG_SELF`). The `Draw` hook in `idPlayerView::SingleView`
> runs every frame without disturbing the scene or the HUD.
>
> **What is NOT verified: the on-screen projection.** The only damage a test can
> provoke without a human at the controls is self damage (`kill` →
> `idPlayer::Damage( this, this, ... )`), which stages the number at the
> attacker's own bounds centre — inside `NUMBER_NEAR_CLIP`, so `Draw` correctly
> culls it and nothing is drawn. Confirming that a number actually appears needs
> a hit on another player, and console commands cannot drive `_attack`
> (`CommandStringUsercmdData` is reachable only from the key-binding system).
> That check is outstanding and needs a human in a real match.

This document supersedes the deferred `Timeouts and pausing` note in
[quakelive-multiplayer-port.md](quakelive-multiplayer-port.md) and extends the
gametype work recorded there.

**Module scope, stated once and enforced everywhere.**
`E:\Repositories\openQ4-game\src\` contains **two** complete, divergent game
trees — `src/game/` (builds `game-sp_<arch>`) and `src/mpgame/` (builds
`game-mp_<arch>`). They are independent forks, not shared sources: of the files
this plan touches, only `physics/Physics_Parametric.h` is byte-identical between
them, and the rest differ substantively (`Player.cpp` is 15957 lines in `game/`
against 14908 in `mpgame/`, with 2897 differing lines after stripping carriage
returns). `src/meson.build:364-372` selects them by directory through
`buildscripts/list_sources.py`, gated on `build_spgame` / `build_mpgame`, and
only `mpgame` receives `GAME_MPAPI`. The engine picks between them at runtime
from `si_gameType` alone — `Common.cpp:5212-5213`:

```cpp
const char *gameType = cvarSystem->GetCVarString( "si_gameType" );
return openQ4_IsMultiplayerGameType( gameType ) ? "game_mp" : "game_sp";
```

**Every game-side change in this plan lands in `openQ4-game/src/mpgame/` and
nowhere else. `openQ4-game/src/game/` is never edited by any phase.** Content,
language tables, `.gui` files, validation tests and user documentation live in
`openQ4`. Both facts are enforced mechanically by a diff-scope check in
`tools/tests/competitive_match_layer.py`, not by convention.

---

## 1. Intent and design principles

openQ4 already models a match as a replicated phase machine (`rvGameState`), a
replicated sub-phase machine (`rvRoundGameState`), a self-validating behaviour
table (`mp/GameTypes.{h,cpp}`), a localized server-driven announce channel
(`GAME_RELIABLE_MESSAGE_CENTERPRINT`) and an authoritative per-client state
channel (`GAME_RELIABLE_MESSAGE_READY`). What that model lacks is four things,
and every competitive feature anyone asks for is one of them:

1. **A clock the match owns.** Every deadline in the module is an absolute
   `gameLocal.time` value. A match that cannot stop its own clock cannot have
   timeouts, which is exactly why the Quake Live port deferred them.
2. **An authority.** The only in-game power today is the admin GUI proxying
   `rcon <command>` — all or nothing, and therefore unusable for a referee.
3. **An identity.** A server's ruleset is thirty loose cvars with no name and no
   way to tell whether they have drifted.
4. **A record.** A match leaves nothing behind: no accuracy, no damage, no
   export, no demo trigger.

So this design introduces exactly four nouns — a clock, an authority, an
identity, a record — and hangs every feature off one of them.

### Principles

**One declaration per capability.** The referee command table, the vote type
list, the `callvote ?` help, the `ref` help and the vote-permission gate are the
same array. A setting is written down once, with its permission level, argument
type, range and `#str_` ids. `ref timelimit 15` and a passed
`callvote timelimit 15` reach the same apply function through the same
validator. This is the pattern `mp/GameTypes.cpp` already proved when it
replaced six hand-written string switches, applied to verbs instead of
gametypes.

**Extend the mechanisms the project already chose.** Replicated match state uses
`rvRoundGameState`'s delta-tagged stream idiom. Every announcement uses
`GAME_RELIABLE_MESSAGE_CENTERPRINT` with `#str_` ids and typed parameters. Every
HUD addition is a state key written by `UpdateHud` and an `oq4_*` windowDef.
Every new table gets an `MPValidate*Table()` that `gameLocal.Error()`s at init on
drift. New cvars go in the one `// openQ4 BEGIN` block in
`mpgame/gamesys/SysCvar.cpp`; new commands go in the one registration function
with `CMD_FL_GAME`; server-only enforcement is the `ForceReady_f` runtime guard
(`mpgame/MultiplayerGame.cpp:7130-7135`), not an invented flag.

**Reuse the primitive that already exists before inventing one.** Two places in
this design were shortened by reading the code rather than assuming: the pause
does not need a new `idPhysics::ShiftFrozenTime` virtual because
`idPhysics::UpdateTime` already *is* the uniform trajectory-shift primitive
(`mpgame/physics/Physics_Parametric.cpp:657-670` computes one `timeLeap` and
adds it to all six stored start times), and the item-timer deadline does not
need a stored field because it can be derived from the item's already-posted
respawn event. Both are recorded in §8.2 and §8.9.

**Defaults change nothing.** Every new cvar defaults to the value that leaves a
server which upgrades and edits nothing behaving exactly as it does today.
Turning the layer on is one command, not a config archaeology exercise. The two
deliberate exceptions — `g_spectatorChat` losing `CVAR_ARCHIVE`, and the
`IMPULSE_17` ready path changing transport — are named in §11 and in the open
questions rather than buried.

**Delete as much as is added.** The legacy single-field vote path is retired —
the source itself calls the two-mechanism split a mistake at
`mpgame/MultiplayerGame.h:72-76`, and that path localizes on the *server* and
ships finished text, a standing violation of the project's own rule. The
rcon-proxy admin GUI is retired **and replaced by a real referee page**, not
merely removed. The scoreboard's literal gametype branch chain is replaced. A
splice of four mods adds four subsystems; this removes three that do not belong.

**A naming rule, stated once.** The module is a palimpsest: `id` is idTech4,
`rv` is Raven, `ri` is Ritual. openQ4-authored multiplayer code is `mp` — the
`mp/` directory, `mpGameTypeInfo_t` and `MP*()` already establish it. New
classes authored here are therefore `mpMatchState`, `mpMatchVote` and so on;
`rv` is reserved for types that extend a Raven hierarchy, which is why
`rvRoundGameState` is correctly named and a new standalone class would not be.

---

## 2. Scope

### In scope

Match administration and presets; timeout and pause; referee authority and a
referee GUI page; voting; a curated map pool and an optional referee-run map
draft; team management and a match roster; ready anti-stall; match-start world
reset; stats collection, live accuracy, hit feedback, end-of-match summary and
export; spectator and observer tooling including item timers; autoaction
(screenshot and stats); server-enforced client *cosmetic* settings; HUD and
scoreboard depth; chat location macros.

### Out of scope, with reasons

**Lag compensation — and the reason is not the one the draft of this document
gave.** The draft asserted that no server-side rewind exists anywhere in openQ4.
That assertion is wrong, and the correction matters. A complete server-side
rewind implementation **exists in `openQ4-game/src/game/` — the single-player
tree** — and is **entirely absent from `src/mpgame/`:

| Symbol | Location (SP tree only) |
| --- | --- |
| `net_mpLagCompensation` | `src/game/gamesys/SysCvar.cpp:616` — `CVAR_GAME \| CVAR_BOOL \| CVAR_NOCHEAT`, default `"1"` |
| `net_mpLagCompMaxMS` | `src/game/gamesys/SysCvar.cpp:617` — `"200"`, 0..1000 |
| `net_mpLagCompBiasMS` | `src/game/gamesys/SysCvar.cpp:618` — `"0"`, -200..200 |
| `net_mpLagCompDebug` | `src/game/gamesys/SysCvar.cpp:619` — `"0"`, 0..2 |
| `MP_LAGCOMP_HISTORY` (64) | `src/game/Game_local.h:1161` |
| `mpLagCompFrame_t`, `mpLagCompRestore_t` | `src/game/Game_local.h:1163`, `:1170` |
| `mpLagCompHistory[MAX_CLIENTS][64]` | `src/game/Game_local.h:1177` |
| Reset / Capture / Select / Compute / Begin / End | `src/game/Game_local.h:1245-1250` |
| Per-frame capture | `src/game/Game_local.cpp:4859` |
| Rewind around the hitscan trace | `src/game/Game_local.cpp:9433`, `:9723-9724` |

Greps run to establish this, recorded so a reader holding the older recon corpus
can see the check was made: `grep -rn "net_mpLagComp" openQ4/src openQ4-game/src`
returns 12 hits, all under `openQ4-game/src/game/`, none under
`openQ4-game/src/mpgame/` and none in the engine repo;
`grep -rniE "lagcomp|LagCompensation" openQ4-game/src/mpgame/` returns **no
output at all**; `grep -rniE "lagcomp" openQ4/src --include=*.cpp --include=*.h`
excluding `/external/` likewise returns nothing (the only engine-repo hits are
`vkAntiLagUpdateAMD` / `VkAntiLagModeAMD` in the Vulkan headers, which are
unrelated).

Because `Common.cpp:5213` loads `game_mp` for every `si_gameType` other than
`singleplayer`, **none of that code has ever executed in an actual multiplayer
match.** It is dead code in the tree that cannot reach it.

That changes the cost estimate rather than the decision. Lag compensation stays
out of scope for this document, but the honest reason is now *"a working
implementation must be ported across two divergent forks and then validated
against a real remote client, which is its own track with its own design record
and its own harness"* — not *"it must be written from scratch"*. It is
recommended as the immediate next track and is raised as an open question in
§10.

**Network settings parity.** Deliberately excluded, and named rather than
omitted. The corpus's enforcement set (OSP/CPMA `server_maxpacketsmin/max`,
`server_timenudgemin/max`, `server_ratemin`, `pmove_fixed`; Quake Live's
`sv_maxRate` / `sv_minPing` / `sv_maxPing`) is engine-side, and openQ4's closest
analogue is `net_clientPrediction` (`openQ4/src/framework/async/AsyncNetwork.cpp`,
`CVAR_SYSTEM | CVAR_NOCHEAT`, so a client may set it freely in a match) together
with `net_clientMaxRate`. Clamping those needs a server→client system-cvar
enforcement channel that does not exist in this engine, and it belongs with lag
compensation on the netcode track, because both are changes to
`openQ4/src/framework/async` and this document is scoped to
`openQ4-game/src/mpgame`. §8.11 therefore covers *cosmetic* parity only and says
so in its first sentence. Omitting this paragraph would have read as an
oversight, which is why it is here.

**Spectator delay.** Out of scope, and it is one of the named hard problems.
No game in this lineage implements a native spectator delay; the in-game
substitute is spec-lock (§8.6), whose actual purpose is anti-ghosting and
anti-stream-sniping rather than tidiness, backed by `g_spectatorChat` keeping
spectators off the live chat channel. A genuine broadcast delay is a tournament
*operations* concern — it lives in the streaming pipeline, not in the game
module — and pretending otherwise would mean holding a snapshot queue per
spectator for tens of seconds inside a module that ejects clients on a single
failed reliable send. Naming the exclusion is cheap; its silent absence would
not have been.

**Multiview and multi-POV demos.** Two independent engine-side blockers. A
spectator's snapshot is PVS-scoped to the followed client — `ServerWriteSnapshot`
receives a single `clientInPVS` set — so the game module does not have the other
players' state to draw. And the client renders exactly one view per frame:
`idPlayer::CalculateRenderView` produces one `renderView_t` and there is no
multi-viewport submission path. Real multiview needs the spectator PVS widened
to the union of every followed player and the renderer taught to submit N views.
Q4MAX shipped `g_allowMultipov` as a kill switch specifically because multipov
destabilised servers, which is a fair warning about the cost even when it is
done. What ships instead is listed in §8.9.

**Demo recording.** `recordDemo`/`playDemo` are Doom 3 render demos: renderer and
sound command streams, no game state, no POV switching, enormous. The game
module's `demoState`/`serverDemo`/repeater plumbing is entirely dead — nothing in
`E:\Repositories\openQ4\src` references `SetDemoState`, `SetRepeaterState`,
`ValidateDemoProtocol` or `GetDemoFollowClient`, and the repeater reliable
channel is commented out at `mpgame/Game_network.cpp:1410-1412`
(`// jmarshall - engine has no repeater reliable channel` /
`//networkSystem->RepeaterSendReliableMessage( -1, outMsg );` / `// jmarshall
end`; lines `:1401-1409` immediately above are live code building the outgoing
chat message). That code has
never been exercised against this engine and must not be assumed to compile.
Autoaction therefore ships the two thirds that are solved and **does not offer a
`demo` token at all**; a token that silently records nothing is worse than an
absent feature, because a league config that says `si_autoAction "demo ss stats"`
would produce no evidence and nobody would find out until a dispute.

**Stats upload over the network.** `ID_ENABLE_CURL` is 0 and
`idNetworkSystem::HTTPEnable` is a stub returning 0. Adding a curl dependency
across three platforms and two renderer backends to replace what `tail -f` on an
NDJSON file already does is the wrong trade, and it introduces a privacy surface
for zero in-game benefit.

**GUID-keyed referee lists and bans.** `com_guid` is `CVAR_ROM` and nothing in
the engine ever writes it, so `game->ServerAllowClient` always receives an empty
GUID. Any design resting on stable cross-session client identity is resting on
nothing. Referee authority is password-based, which is also the model Quake 4
players already expect from CPMA and OSP.

**Full inventory ghost/reconnect restore.** WORR restores a disconnected
player's health, armour, ammo, weapon and position on reconnect. That needs a
stable identity (see above) and a serialisation of a large slice of `idPlayer`.
What this plan does provide is the narrow, useful half, and it now provides it
explicitly rather than by implication: a per-connection token so pause
ownership, referee status and roster position are not inherited by a stranger
who lands in a recycled client slot, an `mpMatchRoster` that restores **team and
score** (not inventory) to a reconnecting player, and `g_pauseOnDisconnect` so a
dropped player's team is not simply punished. §8.5 states the boundary in one
sentence so no reader has to infer it.

**Binary client attestation** (OSP's `server_ospauth`). An unwinnable arms race
and a cross-platform maintenance sink. Cosmetic settings *parity* is in scope;
client integrity checking is not.

**Rulesets and factories** remain excluded, as recorded in the Quake Live port
doc. §8.1 recovers the four properties a ruleset token actually buys without
reintroducing the system.

---

## 3. Module layout

Every row below names its repository and its tree. There is no row under
`openQ4-game/src/game/` anywhere in this plan, and that is the point of
annotating them: the two trees are divergent forks that happen to share
filenames, and a reviewer reading "`Game_local.cpp`" without a prefix cannot
tell which of two 10000-line files is meant.

### New files — all under `openQ4-game/src/mpgame/`

`mp/match/` holds match **administration** and nothing else. The draft put five
unrelated modules there; they now sit directly under `mp/`, which is where
`mp/GameTypes.{h,cpp}`, `mp/GameState.{h,cpp}` and `mp/RoundGameState.{h,cpp}`
already live, and `mp/stats/` remains the precedent for a subdirectory that
means exactly one thing.

| Path (under `openQ4-game/src/mpgame/`) | Responsibility |
| --- | --- |
| `mp/match/MatchState.{h,cpp}` | `mpMatchState`: the match-invariant replicated state — pause clock and accumulator, timeout budgets, referee mask, team locks, spec-locks, captains, team names, preset identity and drift flag, and the `mpMatchRoster` (§8.5). Owns `MatchTime()`, `IsWorldFrozen()`, the pause/resume state machine, `Run()`, and `UpdateMatchHud()`. Replicated as a delta-tagged stream by `GAME_RELIABLE_MESSAGE_MATCHSTATE`. |
| `mp/match/MatchCommands.{h,cpp}` | The single verb registry: `mpMatchCmdInfo_t`, `mpMatchCmd_t` (append-only wire enum), `mpAuthority_t`, the `MCF_*` flags, and `MPValidateMatchCommandTable()`. Feeds the referee dispatcher, the vote registry, `ref`/`callvote`/`commands` help, argument completion, the referee GUI page and the audit log. |
| `mp/match/MatchAuthority.{h,cpp}` | Per-client authority: `ref <password>` login against `g_refPassword`, attempt counting and per-map lockout, listen-host implicit console authority, revocation on disconnect and map change, the `g_adminLog` audit writer, and `MPResolveAuthority( idPlayer *caller, int targetTeam )` — the one place authority is decided. |
| `mp/match/MatchDispatch.{h,cpp}` | `MPExecuteMatchCommand( caller, row, args, source )`: the one entry point every verb passes through whether it arrived from the console, `GAME_RELIABLE_MESSAGE_MATCHCMD`, the referee GUI page, or a passed vote. Re-validates authority, match phase, pause legality and argument range server-side. |
| `mp/match/MatchVote.{h,cpp}` | `mpMatchVote`: ballot lifecycle only — live electorate recount, tally, early pass and early fail, thresholds, per-caller cooldown and budget, arm delay, execute delay, referee pass/veto, and the HUD payload. Carries no knowledge of what any vote does; it calls the command table's apply function. |
| `mp/match/MatchPresets.{h,cpp}` | The compiled preset table (no content files), the optional `presets/<name>.cfg` override loader, atomic apply deferred to a match boundary, `MPHashMatchSettings()` producing the drift hash, and `MPBuildMatchRulesDigest()` producing `si_matchRules`. |
| `mp/match/MatchTeams.{h,cpp}` | Captains, roster lock, spectator lock, spectator invites, team display names, team size caps, invite/accept/remove, score-weighted shuffle, late-join policy, ready anti-stall, `MPResetWorldForMatch()`, and the pure side-effect-free `MPEvaluateTeamJoin()` returning Allow / Queue / Deny. |
| `mp/match/MatchMaps.{h,cpp}` | `g_mapPool` parsing and validation, the `SendMapList` filter, the `maplist` command, and the optional referee-run ban/pick draft (`g_mapDraft`). Match administration, so it belongs in `mp/match/`. |
| `mp/match/MatchLog.{h,cpp}` | Newline-delimited JSON match record written under `fs_savepath` via `fileSystem->OpenFileAppend`, schema-stamped, per-match GUID on every event, atomic temp-then-rename for the final report. Field vocabulary mirrors Quake Live's ZMQ schema where the concept matches so existing tooling ingests openQ4 matches. |
| `mp/match/MatchScoreboard.{h,cpp}` | `mpColumnSet_t` / `mpColumn_t`, the named column sets, `MPValidateColumnTable()`, and the `scoreboard_columnset` state key. Replaces the per-gametype branch chain in `UpdateDMScoreboard`/`UpdateTeamScoreboard` and in `scoreboard.gui`. |
| `mp/ItemTimers.{h,cpp}` | `mpItemTimers`: the map's timed-item registry built once at map load. Each entry's deadline is **derived at send time** from the item's pending `EV_RespawnItem` event and is never stored (§8.9). Writes a fixed-size block into `idMultiplayerGame::WriteToSnapshot` so deadlines are delta-compressed and never PVS-gated. Not match administration — it is world state — hence `mp/`, not `mp/match/`. |
| `mp/SpectatorTools.{h,cpp}` | Follow by name or slot, reverse cycle, sticky auto-follow modes (killer, leader, powerup, flag carrier), `speconly`/`specdefer` on the Duel queue, spec-lock enforcement at every point the chase target can change, the coach role, and the spectator team-vitals overlay. |
| `mp/AutoAction.{h,cpp}` | Reacts to the `COUNTDOWN` to `GAMEON` and `GAMEON` to `GAMEREVIEW` transitions; owns `MPBuildMatchBasename()` so screenshot and stats dump share one name. Screenshot via `renderSystem->CaptureRenderToFile`. |
| `mp/Enforcement.{h,cpp}` | Cosmetic client-settings parity (`si_forceModels`, `si_maxFov`, `si_allowSimpleItems`) applied at the existing read sites; chat and command flood token buckets; inactivity-to-spectator; self-kill cooldown. |
| `mp/ChatMacros.{h,cpp}` | `%h %a %w %l %n %i` expansion in `say`/`sayTeam`. Location (`%l`) is derived from the nearest significant item spawn — weapon, armour, powerup or mega — present or not, so it needs no per-map annotation and no new content file, and the name comes from the item decl's own `#str_` display name. |
| `mp/HitFeedback.{h,cpp}` | Per-frame coalesced attacker-only hit events behind `g_hitFeedback`, feeding `hud_hitBeep` and `hud_damageNumbers` (§8.7). |

**No `meson.build` edit is required for any of the sixteen new pairs.**
`openQ4-game/src/meson.build:364-372` obtains the `mpgame` source list by running
`buildscripts/list_sources.py`, which rglobs `*.cpp` under `mpgame`, so a new file
is picked up automatically. But that is a `run_command` evaluated at **configure**
time, so adding a file requires re-running `meson setup` before `ninja` will see
it — an incremental `ninja` alone will silently build without it.

### Existing files that change — `openQ4-game/src/mpgame/`

| Path (under `openQ4-game/src/mpgame/`) | Change |
| --- | --- |
| `MultiplayerGame.{h,cpp}` | Gains the `mpMatchState matchState` member, `MatchTime()`, `IsWorldFrozen()`, the `ShiftFrozenDeadlines` pass in `Run()`, one call in `UpdateHud()`, and the data-driven scoreboard model. `ToggleReady` (`:8499`, declared `MultiplayerGame.h:603`) stops using `ui_ready` as its transport — today it reads and writes the literal strings `"Ready"`/`"Not Ready"` at `:8514-8519` — and sends `GAME_RELIABLE_MESSAGE_READY` (`:7211`) like the console commands already do. `g_spectatorChat`'s inline declaration at `:11` is removed and re-declared in `gamesys/SysCvar.cpp` without `CVAR_ARCHIVE`; its sole consumer at `:8357` is unchanged. The `IsModified()` live-reapply poll in `idMultiplayerGame::CommonRun` (`:3837`) — `g_forceModel` / `g_forceMarineModel` / `g_forceStroggModel` at `:4006-4019`, the `updateModels` respawn loop at `:4021-4028`, and the `g_simpleItems` reassignment loop at `:4031-4098` — is extended to re-evaluate the `si_forceModels` / `si_allowSimpleItems` gates on a **serverInfo** change as well, because a serverInfo change sets no `IsModified()` flag on any client cvar (§8.11). **Loses** `ClientCallVote` (`:7753`), `ServerCallVote` (`:7814`), `ServerStartVote` (`:7571`), `ClientStartVote` (`:7600`), `ClientUpdateVote` (`:7644`) and their server-side `GetLocalizedString` calls (`:7844`, `:7849`, `:7865`, `:7881`, `:7896`, `:7907`, `:7948`, `:7960`; the map-name path at `:7921-7923` localizes server-side into a `ServerSendChatMessage` and is removed with them). **Loses** the rcon-proxy admin GUI handlers — the `admin` branch at `:5132-5161` and the server-admin GUI block at `:5441-5602`, the latter explicitly including the `populateBanList` handler at `:5599-5602` (`gameLocal.PopulateBanList( mainGui )`), which feeds the same tab and would otherwise be left live against a deleted page; ban-list display moves to **server console only** and is not a referee-page row, because §5 keeps IP disclosure off the referee tier. **Loses** `HandleServerAdminCommands`' hand-written gametype conversion at `:9016-9045` — a six-name `si_gametype` read chain (`:9016-9031`, defaulting to `GAME_SP`) plus a seven-case write switch (`:9034-9045`) — which predates `mp/GameTypes.cpp` and mis-sets `si_gameType` for everything the Quake Live port added. |
| `MultiplayerGame.cpp` packed-vote strings | The three raw English strings at `:3020` (`"Selected map does not exist on the server"`), `:3038` (`"gametype incompatible with map"`) and `:3047` (`"map incompatible with gametype"`) are **not** in the removed single-field path. All three are inside `idMultiplayerGame::ServerCallPackedVote` (`:2954`), the packed multi-field GUI mechanism this plan **keeps and repoints** rather than retires (§8.4; `mpmain.gui`'s vote tab and `ClientStartPackedVote` at `:3175` stay). They are replaced by `#str_` ids sent through `GAME_RELIABLE_MESSAGE_VOTESTATE` in the same change, so Phase 3 exit (l)'s zero-survivor grep is satisfied by editing `ServerCallPackedVote`, not by deleting the five legacy functions. |
| `MultiplayerGame.cpp` scoreboard block | `UpdateDMScoreboard` (`GAME_DM` branch at `:1501`, `GAME_TOURNEY` branch at `:1550`, closing at `:1642`, blanking writes at `:1525`, `:1546`, `:1634`, `:1639`, counts at `:1644-1646`) and `UpdateTeamScoreboard` (`:1820`, clear loop `:1824-1829`, counts `:1835-1839`) are replaced by the column-set writer. `scoreBoard->SetStateInt( "gametype", gameLocal.gameType )` at `:1466` is **kept** — `gameType_t` is the first byte of the gamestate packet and is compared literally by `.gui` files, so the key stays; only the *layout* stops branching on it. `g_testScoreboard`'s fake-row path (gates `:1489`, `:1704`; seed `:2064`; loop bounds `:2067`, `:2078`, `:2093`; reported counts `:2118-2123`) is extended to drive whichever column set is active and to *remove* surplus rows. |
| `MultiplayerGame.cpp` summary block | `ShowStatSummary`, `UpdateSummaryBoard`, `DrawStatSummary` and the `sm_select_player` handler at `:5692` are repointed at `GAME_RELIABLE_MESSAGE_MATCHSTATS` and the column table. `BuildSummaryListString` (`MultiplayerGame.h:903`, defined `MultiplayerGame.cpp:1878`, called at `:1984` and `:2030`) is replaced — it is a member of `idMultiplayerGame`, **not** of `rvStatManager`, and lives nowhere under `mp/stats/`. Listed explicitly because retiring `_ALL_STATS` breaks this wiring and the draft did not say so. |
| `Game_local.{h,cpp}` | **Seven** appended `GAME_RELIABLE_MESSAGE_*` ordinals (41-47, including `_HITINFO` at 47). One gate in the `RunFrame` active-entity think loop (all three variants at `:4159`, `:4199`, `:4212`), plus the ordered head-of-`RunFrame` pass `idEvent::ShiftEventTimes( gameLocal.msec )` then `idPlayer::ShiftFrozenDeadlines`, which must precede both the entity loop and `idEvent::ServiceEvents()` (`:4250`); `idMultiplayerGame::Run()` is at `:4264`, after both, and is therefore not a legal site for either pass (§8.2). `MatchTime()` retargeting at the enumerated deadline sites in §8.2. |
| `Game_network.cpp` | **Seven** cases — including `GAME_RELIABLE_MESSAGE_HITINFO` — in each of `ServerProcessReliableMessage` (`:1238`), `ClientProcessReliableMessage` (`:2038`) and `RepeaterProcessReliableMessage` (`:1383`). One gate plus the `isNewFrame`-guarded shift in `ClientPrediction` (`:2484`, re-prediction `isNewFrame` computation `:2514-2519`, `snapshotEntities` loop `:2547-2552` with its pre-existing `thinkFlags != 0` guard, the local player's separate `ClientPredictionThink()` at `:2568`, and `idEvent::ServiceEvents()` at `:2581` which the client-side `ShiftEventTimes` must precede). `idGameLocal::WriteGameStateToSnapshot` (`:805`, its `mpGame.WriteToSnapshot` call at `:812`, itself reached from `idGameLocal::WriteSnapshot` at `:836` / `:992` under `idGameLocal::ServerWriteSnapshot` at `:1001`) gains an `int clientNum` recipient parameter and loses `const`, so the item-timer block can be filtered per recipient; `idMultiplayerGame::WriteToSnapshot` (`MultiplayerGame.cpp:6508`) takes the same parameter under the same change. `ReadGameStateFromSnapshot` (`:820`, call at `:827`) and `idMultiplayerGame::ReadFromSnapshot` (`MultiplayerGame.cpp:6583`) are unchanged in signature. `competitive_match_layer.py` pins the two new signatures alongside the ordered token list for the block itself. |
| `gamesys/Event.{h,cpp}` | Three new statics, all of which **must** live in `Event.cpp` because `idEvent::time` is private (`Event.h:68`) and `EventQueue` is a file-static with no accessor (`Event.cpp:279`): `idEvent::ShiftEventTimes( int deltaMsec )`; `idEvent::TimeRemaining( const idClass *obj, const idEventDef *evdef )` returning milliseconds or -1, sibling to the existing `EventIsPosted` (`Event.h:93`); and `idEvent::DebugDumpQueue( int maxEntries )` for the Phase 1 instrumented check. Uniform shift preserves the sort, so `Schedule` (`:648-674`, absolute deadline assigned at `:660`, insert compare at `:664-667`) and `ServiceEvents` (`:766-777`, head test at `:775`) need no change at all. |
| `gamesys/Class.{h,cpp}` | `idClass::EventTimeRemaining( const idEventDef *ev )` forwarding to `idEvent::TimeRemaining`, mirroring `idClass::EventIsPosted` at `Class.cpp:657-658` — which returns `bool` and is, today, the only query the codebase exposes over a posted event. |
| `Entity.{h,cpp}` | `virtual void idEntity::ShiftFrozenTime( int deltaMsec )` — default implementation calls `GetPhysics()->UpdateTime( gameLocal.time )`, shifts the animator, and shifts `renderEntity.shaderParms[SHADERPARM_TIMEOFFSET]`. `virtual bool idEntity::PausesWithMatch() const` returning true by default. |
| `physics/Physics_Parametric.{h,cpp}` | **No change.** The draft proposed a new `idPhysics::ShiftFrozenTime` virtual; it is unnecessary. `idPhysics_Parametric::UpdateTime` (`:657-670`) already computes `int timeLeap = endTimeMSec - current.time` (`:658`) and adds it to `linearExtrapolation` (`:662`), the other three interpolators, `splineInterpolate` and `current.spline->ShiftTime( timeLeap )` (`:667`) — precisely the uniform trajectory shift a pause needs. The reason a pause cannot be implemented by skipping `Think()` alone is unchanged and verified: `Evaluate` (`:563`) uses only the absolute `endTimeMSec`, feeding it to `GetCurrentValue()` at `:579`, `:586`, `:588`, `:592`, `:594` and storing it at `:643`, so a mover mid-travel would snap forward by the whole pause duration on resume. Row retained so a reviewer can see the decision was made, not missed. |
| `physics/Physics_Base.cpp` | **No change.** `idPhysics_Base::UpdateTime` is an empty body (`:225-226`), so physics types that store no absolute trajectory start silently and correctly ignore the shift. `idPhysics_Static`, `idPhysics_StaticMulti`, `idPhysics_Player`, `idPhysics_Monster`, `idPhysics_RigidBody`, `idPhysics_AF` and `rvPhysics_Particle` all provide their own overrides, so `UpdateTime` is an established hierarchy-wide rebase primitive rather than a parametric quirk. Its existing callers are `Entity.cpp:3142` and the cinematic-freeze paths at `Game_local.cpp:4161` and `:4201`. |
| `anim/Anim.h`, `anim/Anim_Blend.cpp` | `idAnimator::ShiftFrozenTime`; shifts each `idAnimBlend` channel start time so frozen entities do not jump on resume. **There is no `anim/Anim_Blend.h` in either tree** — the draft named a file that does not exist. The anim directory contains `Anim.h`, `Anim.cpp`, `Anim_Blend.cpp`, `Anim_Import.cpp` and `Anim_Testmodel.{h,cpp}`; the animator classes are declared in `anim/Anim.h`. |
| `Weapon.{h,cpp}` (`rvWeapon`) | `ShiftFrozenDeadlines` for `nextAttackTime` and the weapon state timers, driven from `idPlayer`. |
| `Player.{h,cpp}` | `PausesWithMatch()` returns false (the player still thinks, with a frozen pmove: movement and weapon fire suppressed, view angles free); `ShiftFrozenDeadlines` for `inventory.powerupEndTime[]` (`Player.h:208`, absolute values written at `Player.cpp:395`, polled server-authoritatively at `:5430-5463` with the server gate at `:5455`, replicated as absolute longs at `:13257-13259` / `:13295-13298`) and the weapon timers; `connectionToken`; `specFollowMode`, `specOnly`, `coachTeam`; `matchStats`. `IMPULSE_17` (`:8987-8992`) and the GUI `"ready"` token path (`:7067-7068`) are retargeted at the reliable ready message; the existing `readyUserInfo` anti-clobber at `:3671` is retained. `DefaultFov`'s multiplayer clamp (`:11040-11045`, currently a hard [90, 175]) gains the `si_maxFov` ceiling. `Player_ForcedModelCVarString` (used at `:3371`) becomes the single choke point for `si_forceModels`. |
| `Item.{h,cpp}` | `ShiftFrozenTime` for the shell/glow timers only. **No respawn deadline is stored** — `idItem` has no such field today (`Item.h:88-110` contains only `inViewTime`, `lastCycle` and `lastRenderViewTime`; the `time`/`droppedTime` at `Item.h:152`/`:154` belong to `idItemPowerup` and are hold duration and drop expiry). The registry in `mp/ItemTimers` derives the deadline from the posted `EV_RespawnItem` (duration read at `Item.cpp:723-726` — `:723` reads `respawn_<si_gameType>` with a **-1.0 sentinel** default and `:724-726` falls back to `respawn` with the 5.0 default — posted at `:738-743` along with `EV_RespawnFx` half a second earlier, handled at `:998`, cancelled at `:1026`), so the double-compensation invariant of §8.2 holds by construction. `respawn` is forced to 0 in single player at `:730-731` and, in buying modes, when `givenToPlayer != -1` at `:732-736`, so `EV_RespawnItem` is **not posted at all** in a DeadZone-style buying game; the derived deadline must therefore handle `TimeRemaining == -1` for a live item, not only for an item that is currently present. `si_allowSimpleItems` gates the `g_simpleItems` read at `:515` (§8.11). |
| `mp/GameState.{h,cpp}`, `mp/RoundGameState.{h,cpp}` | Deadline fields converted to match time. No wire-format change; the base header and the round tag stream are untouched. `rvGameState::NewState`'s duplicate `statManager->Init()` at `GameState.cpp:483-486` (WARMUP) and `:568-570` (GAMEON) is replaced by an explicit scope (§8.7), which also stops `rvStatManager::Init` re-registering the `ShowInGameStats` console command on every call (`StatManager.cpp:332`). The two client-side `Init()` calls in `rvGameState::UnpackState` (`:263`, `:302`) follow the same scope. |
| `mp/stats/StatManager.{h,cpp}` | The `mpStatFieldInfo_t` table (Phase 0, `wireBits 0` for anything not yet on the wire). `rvPlayerStat::PackStats` (`:1302-1323`) currently ships only `weaponShots` (`:1304`), `weaponHits` (`:1308`), `inGameAwards` (`:1313`), `endGameAwards` (`:1316`), `deaths` and `kills` (`:1321-1322`), omitting `weaponKills` (`StatManager.h:191`), `suicides` (`:195`), `damageRatio` (`:196`), `damageGiven`/`damageTaken` (`:200-201`) and `lastUpdateTime` (`:207`) — widened and versioned. `weaponShots`/`weaponHits` are `int` on the struct but written as `WriteShort`, so counts above 32767 wrap — fixed by the field table's declared `wireBits`. `SendAllStats` (`:812`) chunked. `UpdateEndGameHud` (`:1237-1276`) is commented out in its entirety and, as written, references `clientStat->weaponAccuracy[]` (`:1251`) and `inGameAwards.Num()`, neither of which exists on the current `rvPlayerStat` — it is rewritten, not merely uncommented. `rvStatAllocator` gains a free list; today `GetBlock` wraps to block 0 past `MAX_BLOCKS` (`:134-139`, slab sized `BLOCK_SIZE 1024 * MAX_BLOCKS 128` at `StatManager.h:110-111`, `:115`) and calls `FreeEvents` (`:148`), which returns 0 without removing anything when the block's events run to the end of `statQueue` (`:544-548`) while `GetBlock` hands out and overwrites that memory anyway, leaving dangling `rvStat*` in the queue; `RemoveRange( blockStart, blockEnd - 1 )` at `:550` is separately suspect against a half-open intent. |
| `gamesys/SysCvar.{h,cpp}` | The new cvar block. `g_spectatorChat` re-declared here (currently inline at `MultiplayerGame.cpp:11`). `g_fov`'s empty description (`:556`) filled in as a drive-by. `g_testScoreboard` (`:618`, extern at `SysCvar.h:348`) gains 0..`MAX_CLIENTS` bounds. `g_announcerDelay` (`:670`) is deleted — it is declared `CVAR_SOUND \| PC_CVAR_ARCHIVE` with no `CVAR_GAME`, is not declared in `SysCvar.h`, and a grep of all of `src/mpgame/` for `announcerDelay` returns exactly one hit, the definition itself. |
| `gamesys/SysCmds.cpp` | The new registration block plus argument-completion functions, beside the existing ready block (`ready`/`notready`/`unready`/`readyup` at `:3492-3495`). `allready` (`:3496`) and `serverForceReady` (`:3483`, inside the `#ifndef ID_DEMO_BUILD` span `:3448-3485`) both keep their existing `idMultiplayerGame::ForceReady_f` registration; `allready` is additionally declared as a table row carrying `MCF_EXISTINGCMD` so a remote referee can reach it (§5). Also registers `debugMatchTime [count]` (`CMD_FL_GAME`, never `CMD_FL_CHEAT`), the permanent console command behind `idEvent::DebugDumpQueue` and the `powerupEndTime[]` dump used by Phase 0 exit (d), Phase 1 exit (d) and Phase 6 exit (i). |

### Existing files that change — `openQ4` repository

| Path (under `E:\Repositories\openQ4\`) | Change |
| --- | --- |
| `content/baseoq4/pak0/guis/mphud.gui` | New `oq4_*` windowDefs; alive counts, spread, warmup-blocking reason, pause banner, timeout budget, referee marker, item timers, accuracy overlay, hit feedback, team vitals, vote banner. The literal gametype chains at lines 168-174 and 286-451 are replaced by generic rendering. |
| `content/baseoq4/pak0/guis/scoreboard.gui` | The four-way literal chain — `4/5/6/7/8` at `:64`, `== 3` at `:120`, `== 1` at `:176`, final `else` showing the Tourney panel at `:219-221` — is replaced by a server-supplied column set; **`p_tourney` is retained** and selected by `columnSet == tourney` (§8.8), because that panel is correct for `GAME_TOURNEY` and only its selection-by-fall-through is wrong. The stale documentation block at `:51-61`, which enumerates only gametypes 0 through 8, is rewritten. The end-of-match summary board's `listDef`s are repointed at the new stats path. |
| `content/baseoq4/pak0/guis/mpmain.gui` | Vote tab repointed at the new vote transport; the admin tab's rcon proxy **replaced** by the referee page (§8.3), not merely removed; a Competitive client-settings page for the `hud_` band (§4). |
| `content/baseoq4/pak0/strings/{english,french,italian,spanish}_openq4.lang` | The `#str_41410`-`#str_41999` band, all four mirrors in the same commit. |
| `docs/dev/settings-menu-registry.json` | Entries for the nine new `hud_` cvars that appear on the Competitive settings page. |
| `tools/tests/competitive_match_layer.py` | New token-pinning contract, including the diff-scope check that no path under `openQ4-game/src/game/` is touched; registered in `tools/validation/openq4_validate.py` and twice each in both workflows. |
| `docs/user/competitive-play.md` (new), `docs/user/server-setup.md`, `README.md`, `docs/dev/release-completion.md`, `docs/dev/archive/2026-10-18/plans/quakelive-multiplayer-port.md` | User documentation, cvar and command tables, Player Guides index entry, Ready For Changelog entry, and the deferred-timeouts note updated to point here. |

### Files this plan does **not** touch

`openQ4-game/src/game/**` — the single-player tree — in any phase. The Meson
targets are separate (`src/meson.build:56-57`), the sources are separate, and
`Common.cpp:5213` never loads `game_sp` for a multiplayer gametype, so there is
no reachability argument for editing it. The draft's Phase 1 exit criterion
"single-player campaign map plays through a save/load cycle unchanged" is
therefore **deleted as vacuous** and replaced by the diff-scope check named
above.

---

## 4. Cvar catalogue

### Prefix rationale — what openQ4 actually does today

The draft asserted that `g_` in openQ4 means "server-side policy and enforcement
no client reads, never replicated". That is false, and since the entire `si_`
budget argument was built on it, the premise is restated from the code before
the catalogue hardens.

**`g_` in openQ4 means "a cvar declared by the game module". It says nothing
about who reads it.** Verified in `openQ4-game/src/mpgame/gamesys/SysCvar.cpp`:

| Cvar | Line | Flags | Actually |
| --- | --- | --- | --- |
| `g_forceModel`, `g_forceStroggModel`, `g_forceMarineModel` | 201-203 | `CVAR_GAME \| CVAR_ARCHIVE` | Purely client-local; the description says "*Locally* forces all players to this model". Read at `Player.cpp:3371` through `Player_ForcedModelCVarString`. No server gate exists. |
| `g_simpleItems` | 537 | `CVAR_GAME \| PC_CVAR_ARCHIVE \| CVAR_BOOL` | Client rendering; read at `Item.cpp:515`. |
| `g_fov` | 556 | `CVAR_GAME \| CVAR_FLOAT \| PC_CVAR_ARCHIVE` | Client view. **No min/max declared** and an **empty description string**. Clamped imperatively to [90, 175] only in multiplayer, inside `idPlayer::DefaultFov` (`Player.cpp:11040-11045`); `idCamera` reads it unclamped at `Camera.cpp:2202`, as does `rvTarget_SetFOV`. |
| `g_crosshairSize` | 564 | `CVAR_GAME \| CVAR_INTEGER \| CVAR_ARCHIVE`, 16..48 | Client HUD. Uses plain `CVAR_ARCHIVE` where its neighbours use `PC_CVAR_ARCHIVE`, and is read back by name rather than through the object at `Player.cpp:4313`. |
| `g_announcerDelay` | 670 | `CVAR_SOUND \| PC_CVAR_ARCHIVE` | Carries **no `CVAR_GAME` at all** despite the prefix, is absent from `SysCvar.h`, and is **dead**: one grep hit in all of `src/mpgame/`, the definition itself. |
| `g_fixedHorizFOV` | 207 | `CVAR_RENDERER \| CVAR_BOOL` | Declares a C++ symbol named `g_fixedHorizFOV` but registers the cvar under the name **`r_fixedHorizFOV`**. |
| `cl_gun_x`, `cl_gun_y`, `cl_gun_z` | 547-549 | `PC_CVAR_ARCHIVE \| CVAR_FLOAT \| CVAR_NOCHEAT` | A `cl_` family living in the game module's `SysCvar.cpp` with no `CVAR_GAME` flag at all. |
| `g_spectatorChat` | — | `CVAR_GAME \| CVAR_ARCHIVE \| CVAR_BOOL` | Not in `SysCvar.cpp` at all: declared inline at `MultiplayerGame.cpp:11`, read only on the server at `:8357`. A server rule that is archived into client configs. |

The full client-side `g_` population in that one file runs to roughly fifty
declarations covering player and item rendering (201-203, 533-537), world FX
(213-232, 542), view and weapon model (544-559, 589-593, 700), damage-view
effects (339-348), and crosshair and HUD (538-575). A `hud_` family already
exists alongside them at 193-196 with `CVAR_GAME`.

`si_forceModels` and `si_allowSimpleItems` **do not exist today** — zero hits in
either repository. They are introduced by this plan. The only existing
replicated gate of that family is `si_allowHitscanTint` (`SysCvar.cpp:75`,
`CVAR_GAME | CVAR_SERVERINFO | PC_CVAR_ARCHIVE | CVAR_INTEGER`, default `"2"`),
and its precedent shape is worth reading precisely: it is consumed by reading
the key out of `gameLocal.serverInfo` at the point of use (`Player.cpp:14633`,
`:14646`), **not** through the `idCVar` object. That is the shape §8.11 follows,
because `gameLocal.serverInfo` is populated on clients as well as the server.

### The new discipline, stated as new

Given the above, the following is a **new rule this plan introduces**, not an
existing convention it obeys. It applies to cvars added by this layer and to
nothing else; no existing declaration is renamed, and the migration note is that
the pre-existing client-side `g_` population stays exactly where it is because
renaming a shipped archived cvar breaks every player's config for no functional
gain.

- **`si_`** = `CVAR_GAME | CVAR_SERVERINFO` — a rule **a client or the server
  browser must actually read**. Replicated. New `si_` declarations in this layer
  must justify themselves against the datagram budget below.
- **`g_`** = `CVAR_GAME` without `CVAR_SERVERINFO` — for cvars added by this
  layer, server-side policy and enforcement that no client reads. All passwords
  and file paths live here. **This narrower meaning is local to the new block**
  and is asserted by `competitive_match_layer.py`, which pins that no cvar
  declared inside the layer's `// openQ4 BEGIN` / `// openQ4 END` block carries
  both a `g_` prefix and `CVAR_SERVERINFO`.
- **`hud_`** = client display, `CVAR_GAME | PC_CVAR_ARCHIVE`. The prefix is
  already established at `SysCvar.cpp:193-196`; new declarations use
  `PC_CVAR_ARCHIVE` rather than the plain `CVAR_ARCHIVE` those four use, to
  match the majority of client display cvars in the same file.
- **`ui_`** = `CVAR_USERINFO` — per-player identity the server or other clients
  need.
- **There are no `cg_` cvars in openQ4** and this design does not create that
  family; a fifth prefix borrowed from another lineage is exactly the
  spliced-from-four-mods failure this plan exists to avoid. The stray `cl_gun_*`
  trio is noted in §11 and left alone.

### The `si_` datagram budget

The budget is a real constraint, not a style preference. `ProcessGetInfoMessage`
(`AsyncServer.cpp:2044-2080`) sends the entire serverInfo dict plus a per-client
name/ping/rate row in one **unfragmented** datagram, and it emits one row for
every slot in a `MAX_ASYNC_CLIENTS` loop (`:2064`; `MAX_ASYNC_CLIENTS` is **32**,
`openQ4/src/framework/async/AsyncNetwork.h:44`).

The 1400-byte figure is a **self-imposed budget, not an engine invariant, and it
is Windows-only.** `MAX_UDP_MSG_SIZE 1400` is defined solely in
`openQ4/src/sys/win32/win_net.cpp:863`, and the only size asserts that use it are
at `:986` and `:1065` in that same Windows-only file — and they are debug-only.
`openQ4/src/sys/posix/posix_net.cpp` contains no such constant and no size assert
at all, so on Linux and macOS an oversized dict fails silently or is fragmented by
the IP layer with no diagnostic. Separately, `ProcessGetInfoMessage` buffers into
`byte msgBuf[MAX_MESSAGE_SIZE]` (`AsyncServer.cpp:2047`), not into a 1400-byte
buffer, so 1400 bounds the platform send path rather than the buffer. Phase 7 (g)
therefore asserts against 1400 explicitly as this project's own budget.

There are already **63** `si_` declarations in `SysCvar.cpp`
(`grep -c 'idCVar[[:space:]]*si_'`), and Phase 7 (g) derives the count at check
time from `MoveCVarsToDict( CVAR_SERVERINFO )` rather than restating a literal
that will drift again. So the test for `si_` is not "is it a
competitive rule" but "does a client or the browser read it" — and for most of
this feature set the answer is no, because the *derived* state rides
`mpMatchState` instead. Timeout policy is the clearest case: the client needs
the live budget and the live deadline, which are replicated on `mpMatchState`;
it never needs the configured maximum, so those stay `g_`. Hit feedback is the
second clearest: the gate is `g_hitFeedback` rather than `si_hitFeedback`
because the data is server-sent, so a client that is not permitted the feature
simply receives no messages and needs no key to read.

That discipline holds the new replicated surface to **eight** keys.

Every numeric cvar carries min/max. Every description names its unit and the
meaning of 0. **Every duration is seconds** except the flood delays and
`g_allowKillMsec`, which are milliseconds and carry `Msec` in the name to say
so. Enumerated-token cvars ship an `ArgCompletion_String` list. All of it goes
in one `// openQ4 BEGIN` / `// openQ4 END` block in
`openQ4-game/src/mpgame/gamesys/SysCvar.cpp`.

### New `si_` — replicated (8)

```
si_matchPreset       ""     ROM STRING       active match preset; a trailing * means a setting has changed since it was applied
si_matchRules        ""     ROM STRING       compact digest of how this server's rules deviate from stock
si_matchPhase        ""     ROM STRING       warmup / countdown / live / overtime / review, for the server browser only
si_itemTimers        "1"    INTEGER 0..2     item respawn timers: 0 off, 1 spectators and coaches only, 2 everyone
si_forceModels       "0"    INTEGER 0..2     model policy: 0 player choice, 1 forbid client model forcing, 2 force team and enemy models
si_allowSimpleItems  "1"    BOOL             allow clients to render items as sprites
si_maxFov            "0"    INTEGER 0 or 90..130   ceiling on player field of view during a match, 0 for no ceiling
si_autoAction        ""     STRING           force autoaction tokens on every client, e.g. "ss stats"; empty leaves it to ui_autoAction
```

`si_matchPreset` is capped at 16 characters and `si_matchRules` at 32; both are
ROM so no operator can enlarge them.

**`si_maxFov`'s legal range is 0, or 90 through 130 — not 0..130.** The clamp in
§8.11 is a *ceiling* raised over the floor `idPlayer::DefaultFov` has enforced
since retail, so a value in 1..89 would invert it (`ClampFloat` with `min > max`)
and drive every client **below** 90. The `idCVar` declaration therefore carries
`0, 130` as its declared bounds — the constructor cannot express a hole — and the
set-time handler in `mp/Enforcement` prints a `Warning()` naming the cvar and
clamps any value in 1..89 up to 90. The same clamp runs once at init, because an
operator may already have persisted an out-of-band value before the check
existed.

**`si_refAvailable` is deleted from the design.** The draft spent one of these
slots on a key whose only stated purpose was "so clients can show referee UI"
while simultaneously removing the only referee UI. The replacement (§8.3) needs
no advertisement key: the referee page is reachable at all times, its login
field submits `ref <password>` over `GAME_RELIABLE_MESSAGE_MATCHAUTH`, and the
server answers with either a grant or one of two distinct localized refusals —
*this server has no referee system* when `g_refPassword` is empty, or *incorrect
password* otherwise. Only the second increments the attempt counter. Whether a
server runs referees is not a secret, so distinguishing the two costs nothing
and saves a replicated key.

**`si_matchPhase` is browser-only.** The client's authority on match phase is
`rvGameState`, which is already replicated and already drives every HUD branch.
Nothing client-side may bind to this ROM string, or the module acquires a second
source of truth for phase; `competitive_match_layer.py` pins that
`si_matchPhase` appears in no `.gui` file and in no client-side read.

`si_voteFlags` is **left alone**. It is shipped as
`CVAR_GAME | CVAR_SERVERINFO | CVAR_INTEGER | PC_CVAR_ARCHIVE`
(`gamesys/SysCvar.cpp:663` — `PC_CVAR_ARCHIVE`, not plain `CVAR_ARCHIVE`; §11
flags exactly that distinction as a defect for `g_crosshairSize`, so it is not
blurred here), and is a *disallow* mask whose documented bit meanings already
disagree with `voteFlag_t`: the help text at `:664-674` documents bit 1 (+2) as
"min players" while `VOTEFLAG_BUYING` is `0x0002` (`MultiplayerGame.h:96`), and
the help text stops at bit 10 so `VOTEFLAG_CONTROLTIME` (`0x0800`, `:106`) is
undocumented. Re-deriving its bit meanings from a new
table would silently change what every existing server with a persisted non-zero
value is disallowing, with no error and no migration path. The new system uses
`g_voteAllow` (a token whitelist) instead; `si_voteFlags` continues to gate the
legacy vote types it always gated, its help text is corrected as a drive-by, and
a `Warning()` is printed once at init if it is non-zero while `g_voteAllow`
differs from `*`, so the operator learns the two are both live.

### New `g_` — server-side (42, of which `g_spectatorChat` is relocated rather than new)

```
# authority
g_refPassword          ""      STRING           referee password; empty disables the referee system entirely
g_refAllowVote         "0"     BOOL             allow players to vote a referee in with callvote referee
g_refAuthAttempts      "5"     INTEGER 1..50    failed referee logins before a client is locked out
g_refLockoutTime       "300"   INTEGER 0..3600  seconds a client is locked out after exhausting its attempts
g_adminLog             ""      STRING           file under fs_savepath to append referee actions to; empty disables

# pause and timeouts
g_timeoutLength        "60"    INTEGER 0..600   seconds a player timeout lasts; 0 disables player timeouts
g_timeoutCount         "0"     INTEGER 0..10    timeouts per team per match (per player in Duel); 0 disables
g_timeoutResumeDelay   "5"     INTEGER 0..30    seconds of warning before play resumes; 0 resumes immediately
g_timeoutWarnTime      "60"    INTEGER 0..300   seconds before auto-resume at which a warning is announced
g_pauseOnDisconnect    "0"     INTEGER 0..600   seconds to auto-pause when a live player drops; 0 disables

# ready and match start
g_readyDelay           "0"     INTEGER 0..600   seconds after the first ready before g_readyDelayAction fires; 0 disables
g_readyDelayAction     "0"     INTEGER 0..2     0 announce only, 1 move un-ready players to spectator, 2 force everyone ready

# voting
g_voteAllow            "*"     STRING           slash-delimited whitelist of votable command names; * for every votable row
g_voteTime             "30"    INTEGER 5..120   seconds a ballot stays open
g_votePassPercent      "51"    INTEGER 1..100   percentage of the live electorate required to pass
g_voteExecDelay        "3"     INTEGER 0..30    seconds between a vote passing and taking effect
g_voteArmDelay         "3"     INTEGER 0..10    seconds before Yes/No are accepted, so a bound key cannot misfire
g_voteDelay            "0"     INTEGER 0..300   seconds after map load during which voting is refused
g_voteLimit            "0"     INTEGER 0..20    votes each player may call per match; 0 for unlimited
g_voteCooldown         "10"    INTEGER 0..300   seconds a caller must wait after their own vote fails
g_voteAllowMidMatch    "1"     BOOL             allow votes other than restart and referee during a live match
g_voteAllowSpectators  "1"     BOOL             allow spectators to call and cast votes

# maps
g_mapPool              ""      STRING           slash-delimited list of maps callvote map and the draft may select; empty means every installed map
g_mapDraft             "0"     BOOL             enable the referee-run ban/pick draft over g_mapPool

# teams
g_allowCaptains        "0"     BOOL             enable the captain role and its commands
g_allowTeamLock        "1"     BOOL             let a captain lock their own team; referees may always lock
g_allowSpecLock        "1"     BOOL             let a captain hide their team from spectators
g_lateJoin             "1"     BOOL             allow connecting players to join a team during a live match
g_coach                "1"     BOOL             teams may invite a spectator as a coach

# spectators and chat
g_specFreeFly          "1"     BOOL             allow spectators to leave follow mode and free-fly
g_spectatorChat        "0"     BOOL             let spectators talk to everyone during a live match (relocated; see below)
g_allTalk              "0"     BOOL             let both teams hear each other
g_chatFloodMsec        "0"     INTEGER 0..10000 minimum milliseconds between chat messages from one client; 0 disables
g_chatFloodBurst       "4"     INTEGER 1..20    messages a client may send back to back before the delay applies
g_cmdFloodMsec         "0"     INTEGER 0..10000 minimum milliseconds between match commands from one client; 0 disables
g_inactivity           "0"     INTEGER 0..3600  seconds before an idle player is moved to spectator; 0 disables
g_allowKillMsec        "0"     INTEGER 0..60000 minimum milliseconds between self-kills; 0 for no limit

# feedback
g_hitFeedback          "1"     INTEGER 0..2     server permission for attacker hit feedback: 0 none, 1 hit cue only, 2 cue and damage amount

# record
g_matchLog             "0"     BOOL             write a newline-delimited JSON match record
g_matchLogPath         "matchlogs"  STRING      directory under fs_savepath for match records
g_statsRedactOpponent  "1"     BOOL             hide an opponent's detailed stats until intermission
g_matchPresetPath      "presets"    STRING      directory searched for optional <name>.cfg preset overrides
```

**`g_spectatorChat` is relocated and its `CVAR_ARCHIVE` flag is dropped.** The
draft said its "name, flags and default are unchanged" while simultaneously
declaring a strict prefix discipline, which cannot both be true: it is read only
on the server (`MultiplayerGame.cpp:8357`) and archiving a server rule into
every client's config is meaningless at best and misleading at worst. The
declaration moves from `MultiplayerGame.cpp:11` into the new block in
`SysCvar.cpp` with an extern in `SysCvar.h`, keeping the name, the type and the
default `"0"`, and losing `CVAR_ARCHIVE`. **This is a behaviour change and it is
named as one**: any value persisted in an existing `autoexec.cfg` or
`Quake4Config.cfg` stops taking effect, and an operator who had set it must set
it in `server.cfg` instead. It is called out in the user documentation's upgrade
notes and raised as an open question in §10 rather than being done silently.

### New `ui_` (2)

```
ui_autoAction   ""   USERINFO ARCHIVE STRING  space-separated: ss, stats, playing. Server can read it and si_autoAction can force it.
ui_specDefer    "0"  USERINFO ARCHIVE BOOL    sit out the Duel queue rather than being pulled in
```

### New `hud_` (9)

```
hud_itemTimers     "1"       BOOL           draw item respawn timers when the server permits them
hud_accuracy       "1"       BOOL           draw the accuracy overlay while the _ingameStats button is held
hud_teamOverlay    "1"       INTEGER 0..2   team overlay detail: 0 off, 1 names and health, 2 with armour and weapon
hud_aliveCount     "1"       BOOL           draw per-team alive counts in round based gametypes
hud_pauseBanner    "1"       BOOL           draw the timeout banner and countdown
hud_matchTimer     "0"       INTEGER 0..2   match clock: 0 counts down, 1 counts up, 2 hidden
hud_hitBeep        "0"       INTEGER 0..2   hit confirmation cue: 0 off, 1 one cue per hit, 2 pitch varies with damage
hud_damageNumbers  "0"       INTEGER 0..2   floating damage numbers: 0 off, 1 damage dealt by this player, 2 all recent damage
hud_specTimersPos  "10 380"  STRING         spectator item timer list position
```

**These nine appear in the Settings menu.** The draft left this undecided, which
would have made `settings_menu_coverage.py` pass vacuously — it checks that
cvars *in* the registry have GUI blocks, so a band that is entirely absent from
the registry passes trivially. Since the project's stated goal is "intuitive,
configurable", a console-only band of nine display options is the wrong answer.
Phase 7 adds a **Competitive** page under the multiplayer settings in
`mpmain.gui` with `docs/dev/settings-menu-registry.json` entries for exactly
these nine, and for nothing else: `si_` and `g_` rows are server rules and reach
operators through presets and `matchsettings`, not through a client menu.
`hud_specTimersPos` is a position pair and appears as a two-field numeric entry
rather than a slider.

### Why the defaults leave casual servers unchanged

Every switch that grants a new power or changes an existing behaviour is off:
`g_refPassword` empty disables the entire authority tier including the login
command; `g_timeoutCount 0` removes `timeout` and `timein` outright;
`g_readyDelay 0` disables the anti-stall;
`g_allowCaptains 0` hands no pubber captain powers; `g_mapPool` empty
means every installed map, exactly as today; `g_mapDraft 0` hides the draft
entirely; `g_matchLog 0` writes nothing; `si_maxFov 0` clamps nobody;
`g_allowKillMsec 0`, `g_chatFloodMsec 0` and `g_cmdFloodMsec 0` add no throttle
where none exists today; `g_inactivity 0` kicks nobody; `si_forceModels 0`
preserves player choice; `si_matchPreset` is empty until someone applies a
preset. `g_voteAllowMidMatch 1` and `g_voteAllowSpectators 1` preserve today's
vote behaviour, and the competitive presets set both to 0. `si_allowVoting`
already defaults to 0 and is not changed. `g_hitFeedback 1` permits a feature
whose client-side switches (`hud_hitBeep`, `hud_damageNumbers`) both default to
0, so a player who edits nothing sees and hears exactly what they do today.

Three deliberate exceptions are recorded rather than hidden. `g_spectatorChat`
loses its archived persistence (above). The `IMPULSE_17` ready bind changes
transport (§8.5) — the observable effect is that a ready keypress stops being
swallowed, which is a bug fix rather than a policy change, but it is still a
change to shipped behaviour. And **`si_itemTimers` ships at `1`, not `0`**: a
server that changes nothing begins showing item respawn timers to spectators and
coaches, though never to a live player. This was decided deliberately on
2026-07-29 (open question 1, now closed) on the grounds that a match should be
castable out of the box and that a spectator already sees the item itself
respawn — the timer discloses nothing a watcher could not time by hand. Live
players are unaffected at this default, so competitive integrity is not the
thing being traded; only spectator convenience changes.

Phase 7's exit criteria measure all of this rather than assert it.

---

## 5. Console command surface

### Registration

All commands are added in the existing `idGameLocal::InitConsoleCommands()`
block in `openQ4-game/src/mpgame/gamesys/SysCmds.cpp`, one per line, with
`CMD_FL_GAME` and a plain-English help string, in a new
`// openQ4: competitive match layer` section beside the existing ready block at
`:3492-3496`. **Never `CMD_FL_CHEAT`** — the multiplayer gate at
`CmdSystem.cpp:557` would make a referee command unusable in the exact situation
it exists for. Console help strings and `gameLocal.Printf` diagnostics stay
plain English by established practice in this codebase; the project rule governs
*display* text, and every row's in-game description and usage string is a
`#str_` id on the table.

**`idCmdSystemLocal::AddCommand` is first-wins, not last-wins.** It walks the
existing list and, on a name match with a different function, prints
`idCmdSystemLocal::AddCommand: %s already defined` (`CmdSystem.cpp:432`) and
**returns without registering**. The game module loads after the engine, so a game
command whose name is already taken by the engine silently never runs, and the
only trace is one `Printf` line in `openq4.log` that the standing gate's "no new
warnings" check does not classify as a warning. This is why `help` is **not** a
spelling of `commands` (`Common.cpp:4741` already registers `help` for
`Com_Help_f`), and it is also the fact that makes the `MCF_EXISTINGCMD` exemption
below safe: an existing registration is never displaced, so a row that shares a
name with one must share its handler too.

There is no client-to-server console fallthrough in this engine
(`CmdSystem.cpp:533-590` ends at "Unknown command"), so every player command is
a locally registered handler that explicitly sends
`GAME_RELIABLE_MESSAGE_MATCHCMD`. Server-only enforcement is a runtime guard in
the handler in the shape `ForceReady_f` already establishes
(`MultiplayerGame.cpp:7130-7135`, which refuses when
`!gameLocal.isMultiplayer || gameLocal.isClient`).

### Authority model

`mpAuthority_t` is a **monotonic level**, not a bitmask — a bitmask invites a row
that a referee cannot run, which is exactly how AfterShock ended up with two
disagreeing permission models:

```cpp
typedef enum {
    MPA_PLAYER = 0,   // any connected client
    MPA_CAPTAIN,      // captain of the affected team (see MCF_SELFTEAM)
    MPA_REFEREE,      // authenticated with g_refPassword, or the listen host
    MPA_CONSOLE       // server console / rcon; implicit superuser
} mpAuthority_t;
```

Higher includes lower, always. Team scope is a separate concern and is a *flag*,
not a level: a row marked `MCF_SELFTEAM` restricts an `MPA_CAPTAIN` caller to
their own team, while an `MPA_REFEREE` caller may target either. That is why
`MPResolveAuthority` takes the target team as a parameter — without it, "captain
of red may lock red but not blue" cannot be expressed in the table and would
leak back into every handler.

### Already shipped, and reused rather than duplicated

Listed because the draft omitted `allready` and then invented a near-homonym
beside it.

| Token | Registration | Handler | Disposition |
| --- | --- | --- | --- |
| `ready` | `SysCmds.cpp:3492` | `idMultiplayerGame::Ready_f` | Unchanged; already goes over `GAME_RELIABLE_MESSAGE_READY` |
| `notready` | `:3493` | `NotReady_f` | Unchanged |
| `unready` | `:3494` | `NotReady_f` | Unchanged |
| `readyup` | `:3495` | `ReadyUp_f` | Unchanged |
| `allready` | `:3496` | `idMultiplayerGame::ForceReady_f` | **Promoted to a table row at `MPA_REFEREE`, carrying `MCF_EXISTINGCMD`.** Registration and handler are unchanged; the handler additionally accepts a dispatch from `MPExecuteMatchCommand`, so a referee on a remote client can now reach it, and `ForceReady_f` **is** the row's apply function, which is what the flag asserts. Today `ForceReady_f` refuses when `gameLocal.isClient`, which means only the listen host or the server console can run it — the promotion is a widening for remote referees and leaves every other caller's behaviour identical. |
| `serverForceReady` | `:3483`, inside `#ifndef ID_DEMO_BUILD` (`:3448-3485`) | `ForceReady_f` | **Console-only, `MPA_CONSOLE`, unchanged, not a table row.** It keeps its preprocessor guard; `allready` sits after the `#endif` and is therefore always registered, which is why `allready` and not `serverForceReady` is the row that gets promoted. |

There is consequently **no `ref allReady` row**. The canonical name is
`allready`, matching the shipped spelling; `allReady` is declared in the row's
`aliases` list so both spellings complete and both dispatch, and `ref allready`
works because `ref <any row the caller's authority permits>` is the universal
referee form (below). `unreadyall` is a new row with alias `unreadyAll`.

**`MCF_EXISTINGCMD` marks a row that deliberately shares its name with a console
command registered outside this layer.** Four rows carry it: `allready`
(`SysCmds.cpp:3496`, `ForceReady_f`), `kick` (engine-side, `Common`/`Session`),
`say` (already registered in this codebase) and `mute`. For those rows the
validator does not treat the name as a collision; it instead asserts that the
existing registration's handler **is** the row's own apply function, so the row
and the registration are provably one capability rather than two. Every other row
is still refused if its name or any alias collides with a command this layer does
not own — `serverForceReady` being the canonical illegal case (§8.3).

### Player commands (`MPA_PLAYER`)

```
ready | notready | unready | readyup                already shipped
teamready | readyteam | notreadyteam                ready or unready an entire side
timeout | pause | calltime                          spend one of the caller's team timeouts
timein | unpause | resume                           resume early; caller or referee only
concede                                             concede the match; Duel only, live only, runner-up only
callvote | cv <setting> [value]                     with no args, lists what this server allows
callvote ? | callvote <setting> ?                   format, range and current value
vote yes | no | y | n | 1 | 2
commands | mphelp                                   list the commands the caller's authority permits
players                                             roster: slot, name, team, ready, (R) referee, (C) captain
maplist                                             the server's map pool, or a note that every installed map is allowed
matchsettings | settings                            the full competitive setting set, deviations marked
matchstats | stats [player]                         per-weapon accuracy, damage given and taken, item control
teamstats                                           team aggregate
topshots | bottomshots                              best and worst player per weapon this match
_ingameStats                                        hold to show accuracy; while spectating, the followed player's
acc                                                 toggle the same overlay, for players who prefer a console command
follow | spec | obs | chase <name|slot>
follownext | followprev
follow killer | leader | quad | regen | haste | invis | flag
speconly | specdefer [n]
coach | coachDecline
mute | unmute <name|slot>                           local ignore, distinct from a referee mute
motd
```

**There is no `+acc` / `-acc`, because idTech4 has no `+cmd`/`-cmd`
convention.** The draft listed one and it could not have been built inside this
plan's module scope. `idKeyInput::ExecKeyBinding`
(`openQ4/src/framework/KeyInput.cpp:763`) buffers a binding verbatim and never
synthesizes a release form, and its only caller runs bindings on key **down**
only (`Session.cpp:5671`, guarded by `event->evType == SE_KEY &&
event->evValue2 == 1`). Held-button state exists solely for bindings that match
the compiled `userCmdStrings[]` table (`UsercmdGen.cpp:178`), which resolves them
into `usercmdButton_t` bits. A player binding `+acc` would get one execution on
key down and nothing on release, and the overlay would stick on forever.

So the hold reuses the button that already exists and is already exactly this
shape: **`_ingameStats`** (`UsercmdGen.cpp:197`, `UB_BUTTON5`). The accuracy
overlay is drawn while that bit is set in the usercmd, which needs no engine-side
change and keeps §9's "every phase is `openQ4-game/src/mpgame/`-only on the game
side" intact. `acc` is a plain toggle command for players who would rather not
share the bind. Adding a dedicated `_accuracy` entry to `userCmdStrings[]` was
considered and rejected: it would put `openQ4/src/framework/UsercmdGen.{h,cpp}` in
§3 and force an engine-side exception into Phase 5 for a cosmetic overlay.

**`concede`, not `forfeit`.** `si_forfeit` already ships and is a different
mechanism — it ends a match automatically when one side empties, a server rule
with no caller. Reusing the word for a player-initiated surrender would leave
two unrelated things with one name in the same command and cvar namespace. The
two coexist: `si_forfeit` continues to fire on an emptied side regardless of
whether anyone runs `concede`, and `concede` is refused if `si_forfeit` has
already ended the match.

Aliases are deliberate and cheap, and a row may carry **more than one** — which
is why the descriptor's alias member is a NULL-terminated `const char **` and not
a single pointer (§8.3). `timeout | pause | calltime`,
`timein | unpause | resume` and `follow | spec | obs | chase` each declare two or
three. A Q4MAX veteran types `pause`; a CPMA or OSP veteran types `cv tl 15`; an
OpenTDM veteran types `calltime`. All of them work. Vote aliases `tl`, `fl`,
`cl`, `rl`, `sl`, `od` are declared in the same list, so they appear in
`callvote ?` and complete in the console.
`topshots` keeps its OSP/CPMA meaning — best player per weapon across the server
— and is not reused for a team aggregate.

### Captain commands (`MPA_CAPTAIN`, `MCF_SELFTEAM`; a referee may target either team)

```
captain [name|slot]                claim a vacant captaincy, or hand it over
lockTeam | unlockTeam
specLock | specUnlock              hide the caller's team from spectators
specInvite <name|slot>             whitelist one spectator while spec-locked
invite <name|slot>                 consent-based team join; the invitee types accept
accept
removePlayer <name|slot>           move one of the caller's own team to spectator
teamName <text>                    scoreboard team name (user text, the one legitimate #str_ exception)
coachInvite <name|slot>
veto <map> | pick <map>            only while a map draft is running
```

Multi-word commands use the codebase's existing camelCase (`serverForceReady`,
`removeClientFromBanList`, `clientCallVote`), not run-together Q3 casing.

### Referee commands

Authenticate once with `ref <password>`, compared against `g_refPassword`. The
listen-server host and any rcon caller are implicitly `MPA_CONSOLE`. Status is
replicated in `matchState.refMask` so the scoreboard and `players` show `(R)`,
and the grant is announced — a hidden admin is worse than no admin.
`ref logout` resigns. A referee cannot kick, mute or move another referee.

**Because the referee table and the vote table are one table,
`ref <any votable setting> <value>` applies that setting directly, skipping the
ballot.** So the list below is only the referee-*exclusive* rows; `ref timelimit
15`, `ref map q4dm1`, `ref shuffle`, `ref matchpreset duel`, `ref allready` and
every other permitted row work without being enumerated separately.

```
ref <password> | ref logout
ref                                  print the caller's level and the actions it permits
ref pause | ref unpause              indefinite; supersedes and locks a player timeout
ref abort                            abandon a live match, return to warmup, clear ready
ref lock [red|blue|both] | ref unlock [...]
ref specLock [red|blue|both] | ref specUnlock [...]
ref putTeam <name|slot> <red|blue|spec>
ref remove <name|slot>
ref captain <red|blue> <name|slot>
ref coach <red|blue> <name|slot>
ref mute <name|slot> [seconds] | ref unmute <name|slot>
ref kick <name|slot> [reason]
ref passVote | ref cancelVote
ref setScore <name|slot> <value>
ref setTeamScore <red|blue> <value>
ref setMatchTime <seconds>
ref say <message>                    an announcement visually distinct from player chat
ref cointoss                         public randomised heads/tails, for map and side picks
ref draft start [sequence] | ref draft cancel | ref draft status
ref veto <map> | ref pick <map>      act on behalf of a captain who is absent or stalling
```

Deliberately **not** referee commands: anything that grants console access.
`ref` cannot execute arbitrary console commands. IP disclosure stays
server-console only.

### Server console commands

```
matchPreset <name>          apply a preset atomically at the next match boundary
applyMatchSettings          re-derive everything after a manual si_ edit; recomputes the drift hash
listPresets
refStatus                   who is currently a referee
matchInfo                   machine-readable live match state for scorebots and overlays
debugMatchTime [count]      dump MatchTime(), gameLocal.time, the next [count] queued events with
                            their remaining delays, and every player's powerupEndTime[] remainders
serverForceReady            already shipped; console-only path to ForceReady_f
```

`debugMatchTime` is a **permanently registered** command, not a temporary one:
Phase 0 exit (d), Phase 1 exit (d) and Phase 6 exit (i) all read it, so removing
it after Phase 1 would make the last of those unperformable. It is camelCase like
its neighbours, `CMD_FL_GAME` like every other row (never `CMD_FL_CHEAT`, per the
Registration paragraph), and it is a **command**, so it carries no cvar prefix —
the draft's `g_debugMatchTime` contradicted §4's `g_` rule by putting a cvar
prefix on a console command. It is a pure read and mutates nothing.

`matchPreset` is **also a table row** (`MPA_REFEREE`, `MCF_WARMUPONLY`,
`MCF_VOTABLE`), so a referee on a remote client can run it and players can
`callvote matchpreset duel`. This is the flagship workflow and it must execute
for the person the documentation says will type it.

### Running a match, end to end

Operator, once, in `server.cfg`:

```
seta g_refPassword     "somethingprivate"
seta si_allowVoting    "1"
seta si_autoAction     "ss stats"
seta g_mapPool         "q4dm1/q4dm2/q4dm3/q4dm7/q4tourney1"
matchPreset duel
```

Referee, in game:

```
] ref somethingprivate      -> "Nickname is now a referee", announced to everyone
] players                   -> confirm the roster and slot numbers
] maplist                   -> the five maps in the pool
] matchsettings             -> nothing marked; the server is standard
] ref lock                  -> rosters frozen
   ... both players type ready; countdown; FIGHT ...
] timeout                   -> "Nickname called a timeout (60s), 1 remaining"
] timein                    -> "Resuming in 5..." ; the world unfreezes on 0
] ref pause                 -> indefinite, for a disconnect
] ref unpause
] ref abort                 -> back to warmup with ready cleared
] matchstats                -> full report; also written to matchlogs/ if g_matchLog 1
```

A player who configures nothing types `ready`, holds their existing
`_ingameStats` bind to see accuracy, and never learns any of the rest exists.

---

## 6. Network plan

### New reliable messages — seven, appended

The enum in `mpgame/Game_local.h:293-341` uses 41 of 256 slots and carries an
explicit APPEND ONLY comment at `:336-337`, immediately above
`GAME_RELIABLE_MESSAGE_CENTERPRINT` ("openQ4: localized centre-screen notice,
server driven. Append only - these ordinals are the wire format."). The last
entry, `GAME_RELIABLE_MESSAGE_READY`, carries its own comment at `:339` with no
append-only language. Seven ordinals are appended after
`GAME_RELIABLE_MESSAGE_READY` (40):

```
41  GAME_RELIABLE_MESSAGE_MATCHSTATE   server -> client   mpMatchState delta tag stream
42  GAME_RELIABLE_MESSAGE_MATCHCMD     client -> server   one verb from the match command table
43  GAME_RELIABLE_MESSAGE_MATCHAUTH    both ways          referee login, and the granted level back
44  GAME_RELIABLE_MESSAGE_VOTESTATE    server -> client   ballot descriptor, tallies, deadline
45  GAME_RELIABLE_MESSAGE_MATCHSTATS   server -> client   widened, chunked, per-recipient-redacted stat block
46  GAME_RELIABLE_MESSAGE_ACCURACY     both ways          compact per-weapon accuracy request and reply
47  GAME_RELIABLE_MESSAGE_HITINFO      server -> client   attacker-only, per-frame coalesced hit feedback
```

One opcode carries the entire verb surface rather than one opcode per command.
Each addition requires a case in **all three** dispatch switches —
`ServerProcessReliableMessage` (`Game_network.cpp:1238`),
`ClientProcessReliableMessage` (`:2038`) and `RepeaterProcessReliableMessage`
(`:1383`) — or the module emits `Warning("Unknown ... reliable message")`. The
repeater path is dead in openQ4 but the case must still exist so the warning does
not fire. The validation test pins all three.

**MATCHSTATE** carries only changed fields, self-describing by `MSG_MATCH_*` tag
byte, terminated by exhausting `GetRemainingData()` — the
`rvRoundGameState::PackState`/`UnpackState` idiom at `RoundGameState.cpp:813-871`.
It is sent from `idMultiplayerGame::Run` only when
`matchState != previousMatchState`, and in full from `WriteStartState` so a
join-in-progress client gets the pause state, referee mask, team locks and
roster immediately. **It is its own message, not an addition to the
`rvGameState` base header.** That placement matters: `rvGameState::SendState`
early-outs on `*this == *previousGameState` (`GameState.cpp:132-134`; `:129-131`
is the preceding
`assert( (gameLocal.isServer || gameLocal.isRepeater) && trackPrevious );` and
its surrounding blank lines), so a
field added to the base header without also being added to `operator==`,
`operator!=` **and** `operator=` replicates exactly never, silently — the header
says so at `GameState.h:148-150`. Keeping match state off the base header
sidesteps the single nastiest replication trap in the module rather than
navigating it, and it also avoids having to prefix a count byte so
`rvRoundGameState`'s `GetRemainingData()` read loop does not consume the wrong
tags. Steady-state cost: zero bytes. Cost of a timeout: about a dozen.

`mpMatchState` has the *same shape* and therefore the same operator hazard, so
the validation test requires every `MSG_MATCH_*` tag to appear in `PackState`,
`UnpackState` and `operator==`.

**MATCHSTATE additionally carries the settings mirror, and it has to.** §4's
whole point is that a `g_` cvar is not replicated, so a remote client cannot read
`g_voteAllow`, `g_timeoutCount`, `g_hitFeedback` or `g_mapPool` at all. But §8.1
requires `matchsettings` to cover "every `si_` *and* every `g_` row in the table",
§8.4 requires `callvote` with no arguments to print "exactly the rows
`g_voteAllow` permits, with their localized descriptions and current values", and
Phase 3 exit (g) requires a `g_voteAllow` edit to change `callvote ?` **in the
same frame** — which no request/reply round trip can deliver. So one tag group is
added to this same delta stream:

```
MSG_MATCH_VOTEMASK      bitmask over the command table, one bit per MCF_VOTABLE row,
                        set when g_voteAllow currently permits that row
MSG_MATCH_SETTINGS      one entry per table-declared setting: row id byte, then the
                        current value in the row's declared argType
```

Both are pushed on change and in full from `WriteStartState`, exactly like every
other tag, so the client always holds the current answer locally and both the
same-frame property and the "no new opcode" property come for free. `matchsettings`
and `callvote`/`callvote ?` then render entirely from client-side state plus the
shared table, with no request, no reply and no second source of truth. The two
tags are pinned by the same check that requires every `MSG_MATCH_*` tag to appear
in `PackState`, `UnpackState` and `operator==`.

**MATCHCMD** payload: `mpMatchCmd_t` byte, an argument-presence byte, then only
the present arguments in the table row's declared order — target client byte,
team byte, short integer, string. The server re-reads it, looks the row up in the
same table the client used, and re-validates *everything*: the row exists, the
caller's **server-side** authority level and team scope permit it, the match phase
allows it, the pause state allows it, the target exists and is an `idPlayer`, and
the argument is inside the row's declared range. A client's claim about its own
authority is never trusted. `mpMatchCmd_t` is append-only and carries that comment.

**MATCHAUTH** carries the password client-to-server and the granted level
server-to-client. It is separate from MATCHCMD so the secret never shares a
payload with the audited command stream and the audit log can record every
command without ever recording a password. Attempts are counted per client,
rate-limited by `g_cmdFloodMsec`, and a client that exhausts
`g_refAuthAttempts` is locked out for `g_refLockoutTime`. The two refusal
reasons are distinct `#str_` ids — *no referee system on this server* and
*incorrect password* — and only the second increments the counter, which is what
lets the referee GUI page exist without `si_refAvailable`. The password is
`CVAR_GAME` and never `CVAR_SERVERINFO`, so it is not in the browser or the
connect handshake — explicitly not the CPMA/OSP model, which puts it in a
userinfo key where anyone who can dump user info can read it.

**VOTESTATE** carries `mpMatchCmd_t`, the argument, `yes`, `no`, `electorate`,
the deadline in match time and a flags byte. The client builds the display string
from the row's `voteDescId` plus the typed argument, exactly as
`ClientStartPackedVote` already does. This is the load-bearing detail of the
shared-table claim: the vote description `#str_` id and the argument's display
type are **columns on the table row**, so the client derives its text from the
same declaration the server validates against and no per-vote switch survives on
either side.

**MATCHSTATS** supersedes `GAME_RELIABLE_MESSAGE_ALL_STATS`, which is explicitly
retired (its handler becomes a no-op; the ordinal stays for wire-format
stability) so no double summary can appear at `GAMEREVIEW`. Retiring it also
orphans the summary-board wiring — `ReceiveAllStats` calls `ShowStatSummary`,
which drives `UpdateSummaryBoard` / `DrawStatSummary` and the summary board
`listDef`s — so those call sites are repointed in the same change and are listed
in §3 rather than left to be discovered. Two rules ride with the message. It is
**chunked** — at most four clients per message, one message per server frame —
because **thirty-two** full stat blocks pushed at intermission over a 25600 B/s
rate cap is a realistic way to overflow the reliable queue, and reliable-queue
overflow calls `DropClient(..., "#str_07136")`
(`openQ4/src/framework/async/AsyncServer.cpp:829-831`, inside
`idAsyncServer::SendReliableMessage` at `:820`; the declaration at
`AsyncServer.h:260` carries the comment "checks for overflow and disconnects the
faulty client" but is not the call site). **`MAX_CLIENTS` is 32
(`Game_local.h:59-62`); the 16 in the `#ifdef _XENON` branch at `:59` is dead on
every platform this project ships**, so a check sized against 16 computes half the
real worst case. Four clients per message over 32 clients is eight consecutive
server frames of burst, not four, and Phase 5 (k) re-derives the chunk size
against 32 rather than restating the draft's figure. And it is
**redacted per recipient**: during `GAMEON` with `g_statsRedactOpponent 1` a
player receives full detail only for themselves and their own team, while
spectators and everyone at `GAMEREVIEW` receive everything. Redaction is a
per-recipient decision, which is precisely why this rides a reliable message and
not the broadcast snapshot.

**ACCURACY** is a request byte plus an optional target client num; the reply is a
source client num followed by `MAX_WEAPONS` bytes of `hits*100/shots`. When the
requester is a spectator following someone, the server substitutes the followed
client. A caster holding the accuracy button must see the player being watched,
and it is the detail every implementation forgets.

**HITINFO** is the message the draft's `hud_damageNumbers` cvar implied and never
had. It is sent **only to the attacker**, **only when `g_hitFeedback` is
non-zero**, and **at most once per attacker per server frame** — every hit
applied during a frame is coalesced into one message carrying a count byte and,
per hit, a victim client num, a damage short and a flags byte (headshot, team
damage, self damage, kill). At `g_hitFeedback 1` the damage short is written as
zero and only the cue fires; at `2` the amount is included. If the attacker's
reliable queue is above a threshold the message is **dropped**, because it is
cosmetic and the alternative is ejecting the player it was trying to please.
This keeps the "nothing in this layer is periodic" property intact in the only
sense that matters: the message is bursty and bounded by the server frame rate,
never scheduled.

### Centre-print channel widening

`centerPrintParm_t` is currently `{ CPARM_NONE, CPARM_INT, CPARM_CLIENT,
CPARM_TEAM }` (`MultiplayerGame.h:413-418`) with a 2-bit type field and two
parameter slots, written on the wire at `MultiplayerGame.cpp:6758-6761` as
`WriteBits( type1, 2 )` / `WriteShort( parm1 )` / `WriteBits( type2, 2 )` /
`WriteShort( parm2 )`. The competitive layer needs to announce preset names,
user-entered team names, map names and kick reasons, and messages of the shape
"X called a timeout, N seconds, M left". So the channel is **widened, not
duplicated**.

The shipped implementation is more constrained than "add a type and a slot"
suggests, and the change list is therefore concrete rather than one sentence:

1. The type field goes from **2 to 3 bits** at both write sites
   (`:6758`, `:6760`) and their read mirror in `ReceiveCenterPrint`.
2. `CPARM_TIME` (rendered mm:ss) and `CPARM_STR` are appended to
   `centerPrintParm_t` — append only, since the enum is on the wire.
3. A **third** type/parameter slot is added.
4. **The parameter is a `short`, so `CPARM_STR` cannot ride it.** Every case
   this widening exists for — team name, preset name, map name, kick reason — is
   a string. `CPARM_STR` therefore writes its payload with `WriteString` after
   the type bits, capped at `MAX_CENTERPRINT_STR` (16 characters, the same cap
   `teamName` and `si_matchPreset` already carry, declared once as a named
   constant); `parm` stays a `short` for `CPARM_INT`, `CPARM_CLIENT`,
   `CPARM_TEAM` and `CPARM_TIME`.
5. The four C++ overloads at `MultiplayerGame.h:421-424` all take `int parm`; a
   third overload family is added, taking a `const char *` for the string case.
6. `MPFormatCenterPrintParm` (`MultiplayerGame.cpp:6705`) gains a string path.
7. The render sites at `MultiplayerGame.cpp:6780` and `:6834` call
   `local->GUIMainNotice( va( common->GetLocalizedString( strId ),
   MPFormatCenterPrintParm( type1, parm1 ), MPFormatCenterPrintParm( type2,
   parm2 ) ), persist )` — a **two**-argument `va()` that becomes three, at both
   sites.
8. Every `#str_` id already authored for this channel is re-checked so none
   supplies fewer `%s` than the new arity passes; `va()` reading a third argument
   a format string does not consume is harmless, but the reverse is not, and the
   audit is cheap because the channel is openQ4-authored and its id set is small.

This is a wire change to an openQ4-authored
message; openQ4 has never supported mixed-build matches (`si_pure` defaults to 1)
and this plan does not claim otherwise. Adding a second announcement channel
instead would be the wrong trade — the Quake Live port's own record names
widening as the right move when two parameters is not enough.

### Snapshot: the item timer block

Item timers must **not** go in the `idItem` snapshot. `idItem::WriteToSnapshot`
(`Item.cpp:825-831`) writes the item's whole physics state when `syncPhysics` is
set (`:826-828`) plus one `srvReady` bit (`:830`), and is PVS-gated — and a timer
is only useful for an item that cannot be seen, exactly the case that snapshot
never covers.

Instead a fixed block is appended to `idMultiplayerGame::WriteToSnapshot`
(`MultiplayerGame.cpp:6508`) **after** the existing trailing ping block, with its
mirror at the identical position in `ReadFromSnapshot` (`:6583`):

```
byte                      numTimedItems       (0 when si_itemTimers is 0)
per item:
  ASYNC_ITEM_INDEX_BITS   entity index
  ASYNC_ITEM_TIME_BITS    respawn time REMAINING, in milliseconds, not an absolute
```

Bit widths are named constants derived from `idMath::BitsForInteger` of a `MAX_`
constant, following `ASYNC_PLAYER_*_BITS` at `MultiplayerGame.h:284-289` rather
than magic numbers. `MAX_TIMED_ITEMS` is 32 and §8.9 says what happens on item
33 and how the figure is checked rather than asserting it.

#### The game-state block budget

**The draft's version of this block would have `FatalError`ed the server, and
unconditionally.** The argument that "`idBitMsgDelta` delta-encodes, so a static
field costs essentially nothing" is true of the *message* and false of the *base
state*. `idBitMsgDelta::WriteBits` (`openQ4/src/idlib/BitMsg.cpp:610-613`) opens
with `if ( newBase ) { newBase->WriteBits( value, numBits ); }` — the full
uncompressed value is written into the base buffer on **every** snapshot whether
or not it changed. That buffer is `byte stateBuf[MAX_ENTITY_STATE_SIZE]` with
`MAX_ENTITY_STATE_SIZE = 512` (`Game_local.h:260`, `:270`), allocated for the
`ENTITYNUM_NONE` game-state pseudo-entity at `Game_network.cpp:979-992`. Overflow
is not a warning: `idBitMsg::CheckOverflow` calls
`idLib::common->FatalError( "idBitMsg: overflow without allowOverflow set" )`
(`openQ4/src/idlib/BitMsg.cpp:35-39`).

Measured current occupancy at `MAX_CLIENTS` 32: 12 `globalShaderParms` floats
(48 B, `Game_network.cpp:808-810`) + the DeadZone header bits + `TEAM_MAX` x
(short + long) + the 4 B ingame bitfield + 32 x (2 x `ASYNC_PLAYER_FRAG_BITS` +
32-bit DeadZone score + `ASYNC_PLAYER_WINS_BITS`) + 32 x
`ASYNC_PLAYER_PING_BITS` — roughly **359 bytes**, leaving about 153. A 32-entry
block of 12-bit index plus a 32-bit absolute match time is 1 + 176 = **177
bytes**. Over the limit, before Tourney, which adds a presence bit plus
`ASYNC_PLAYER_INSTANCE_BITS` and tourney-status bits per client on top.

So `ASYNC_ITEM_TIME_BITS` is a **bounded remaining time**, not an absolute:
`idMath::BitsForInteger( MAX_ITEM_RESPAWN_MSEC )`, about 17 bits for a 131-second
ceiling, giving 32 x 29 bits + 1 byte ≈ **117 bytes** worst case. The cost of
that choice is stated rather than hidden: a remaining-time field **changes every
snapshot**, so it delta-encodes to nothing and costs roughly 72 B per snapshot
per client at 32 timed items, where the absolute would have been free in the
message and fatal in the base. That is the correct trade, because the absolute
does not fit at all.

A startup assertion sums the entire `idMultiplayerGame::WriteToSnapshot` bit
count at `MAX_CLIENTS` in the worst-case gametype and `gameLocal.Error()`s if it
exceeds `MAX_ENTITY_STATE_SIZE`; `competitive_match_layer.py` pins that assertion
alongside the `MAX_UDP_MSG_SIZE` check §4 already has. Deriving the deadline from
the event rather than storing it (§8.2, §8.9) is unaffected — the value written is
simply `idEvent::TimeRemaining( item, &EV_RespawnItem )` directly, with no
`MatchTime()` term, which is also why it needs no pause compensation of its own.

The `si_itemTimers` policy is enforced **at send time, per recipient** — a client
whose viewer class the policy excludes receives `numTimedItems 0`. A client-side
filter would be a trivially defeated cheat. That filter needs a recipient the
current signatures do not carry: §3 records that
`idGameLocal::WriteGameStateToSnapshot` (`Game_network.cpp:805`) and
`idMultiplayerGame::WriteToSnapshot` (`MultiplayerGame.cpp:6508`) both gain an
`int clientNum` parameter and lose `const`, supplied down from
`idGameLocal::ServerWriteSnapshot` (`Game_network.cpp:1001`) through
`idGameLocal::WriteSnapshot` (`:836`, the game-state call at `:992`).

Appending at the end is safe; **inserting anywhere else is not**. The snapshot
read/write order is untagged and unversioned, so a field added on one side and
not the other corrupts everything after it. The validation test pins the write
and read sequences as ordered token lists.

Nothing reuses `mpPlayerState_t::fragCount` (clamped -100..999) or
`teamFragCount` (already triple-purpose; the port doc explicitly warns against a
fourth meaning). New data gets new fields.

### Stats wire widening

`rvPlayerStat::PackStats` (`StatManager.cpp:1302-1323`) ships `MAX_WEAPONS`
shorts of shots, `MAX_WEAPONS` shorts of hits, the award arrays, deaths and
kills — and nothing else. `damageGiven`, `damageTaken`, `weaponKills`,
`suicides` and `damageRatio` are computed server-side and never leave it, which
is why no real client can display damage today, and `UnpackStats`
(`:1325-1345`) mirrors exactly the packed set so the omitted fields sit at
whatever `Clear()` left them on every client. The payload gains a leading
`STAT_PACK_VERSION` byte and those fields, plus per-weapon damage, item pickup
counts and pickup intervals, and a per-round array. The version byte means a
future change is detectable rather than silently corrupting.

`mpStatFieldInfo_t` declares each stat's `wireBits` next to the stat itself, so
"tracked server-side but never shipped" becomes a visible `0` in a table row
rather than an omission in a hand-written pack function. It also fixes a live
truncation: `weaponShots` and `weaponHits` are `int` on the struct but written
with `WriteShort`, so a long match can wrap them; the declared `wireBits` is the
single place that width is now written down.

**The table lands in Phase 0, not Phase 5.** `MPValidateColumnTable()` errors at
init if a column's `statKey` does not resolve in the stat table, so the stat
table must exist before the column table does — the draft had them in Phase 5
and Phase 0 respectively, which is circular. Phase 0 lands the table with
`wireBits 0` for every field not yet on the wire, and the validator additionally
errors if any *named column set* references a field whose `wireBits` is 0. Phase
5 flips those widths and adds the columns to the sets in one change. That
ordering is also what the plan's own "declare once" principle implies.

### Wire compatibility

- `GAME_RELIABLE_MESSAGE_*`, `mpMatchCmd_t`, `MSG_MATCH_*`, `gameType_t`,
  `vote_flags_t` and `vote_gametype_t` are **append only**, each carrying that
  comment in the same words the existing ones do.
- **No engine protocol bump.** Everything rides
  `SERVER_RELIABLE_MESSAGE_GAME` / `CLIENT_RELIABLE_MESSAGE_GAME`, existing
  serverInfo keys and the existing snapshot framing. `ASYNC_PROTOCOL_VERSION` is
  untouched.
- **Server and client must be the same build.** This is already true of openQ4
  (`si_pure 1`) and is the same assumption the Quake Live port made when it
  appended the overtime triple to the base gamestate header. It is stated
  explicitly rather than assumed, because the snapshot layout and the widened
  centre-print payload are untagged.
- Nothing periodic goes on the reliable channel. Item timers ride the snapshot;
  live accuracy is request/reply on a key press; hit feedback is bursty and
  bounded by the frame rate and is dropped under queue pressure; MATCHSTATE only
  moves when the match state actually changes; the intermission stats burst is
  chunked.
- Nothing pre-translated crosses the wire.

### The listen-server trap

`LocalClientSendReliableMessage` (`AsyncServer.cpp:2301-2307`) short-circuits the
host client's messages straight into `ServerProcessReliableMessage` with no
serialization at all. A bug in a read path therefore shows up only against a real
remote client. Every new message must be exercised on the two-instance harness,
never validated on a listen server alone. This is a standing rule for every phase.

---

## 7. Localization plan

### Band — settled here, not deferred

The competitive layer claims **`#str_41410`–`#str_41999`** (590 ids). The draft
claimed 41410–41799, then admitted in the same section that the command-table
sub-band "deliberately overflows into the reserve" and that "the exact split is
settled in Phase 2" — while Phase 0's scope required declaring the band. That
sequence guarantees that every id assigned in Phases 0 and 1 moves when Phase 2
arrives, and renumbering ids that have already shipped in four mirrors is
precisely the churn the Quake Live port's band discipline exists to prevent. So
the arithmetic is done now.

The existing high-water mark in `english_openq4.lang` is `#str_41409` (the Quake
Live port's HUD labels), so the band is contiguous with what came before and
does not touch the `#str_2299xx` GUI band — which already carries a duplication
between `english_guis.lang:1118` and `english_openq4.lang` that this plan does
not want to make worse. Nothing in the repository uses 41410–41999 today; that
is pinned by `competitive_match_layer.py` so the claim cannot rot.

### Sub-bands, sized from the actual row counts

```
41410-41449  (40)   pause, timeout and resume
41450-41479  (30)   referee authority: grant, resign, refusal, lockout, audit
41480-41779  (300)  the command table: descId + usageId per row, voteDescId per votable row
41780-41819  (40)   voting: prompts, tallies, refusals, results
41820-41859  (40)   team management: locks, captains, invites, shuffle, late join, ready anti-stall
41860-41909  (50)   stats, awards, hit feedback and scoreboard column headers
41910-41939  (30)   spectator, coach and item timers
41940-41959  (20)   presets, drift, settings audit, map pool and draft
41960-41979  (20)   enforcement, flood, inactivity and autoaction
41980-41999  (20)   reserve
```

The command-table sub-band is sized from a count, not a guess. The surface in §5
is roughly **95** rows (aliases are a *column*, not a row): about 28 player rows,
11 captain rows, 20 referee-exclusive rows, 30 votable-setting rows and 6 console
rows, which sums to 95. Two ids per row is 190, plus a `voteDescId` for the
roughly 35 votable rows, giving **225**. The sub-band is 300, so the table has
roughly **37** rows of headroom before it touches anything else — enough that a
future feature adds rows without renumbering.

**Allocation rule.** Ids are assigned within a sub-band in phase order and are
never reused, even if a feature is cut. A sub-band that fills does not spill
into its neighbour; it takes from the 41980–41999 reserve at the tail, and doing
so is recorded by editing this section rather than by convention. The band as a
whole is declared once in Phase 0 as a `// section` comment at the head of the
block in all four mirrors, the way `english_guis.lang:1118` declares its reserved
band — **declaring the band is not declaring 590 entries**; each phase adds only
the ids it actually uses.

### Runtime-selected ids are validated at init, not by grep

The standing per-phase gate says "no unresolved `#str_` ids on either client".
A static scanner catches ids written literally in sources and `.gui` files; it
cannot catch an id selected from a table by index at runtime, and the command
table's `descId` / `usageId` / `voteDescId` columns are exactly that case. So
the mechanism the gate names is **`MPValidateMatchCommandTable()` resolving
every `#str_` id on the table through `common->GetLocalizedString` at game init
and calling `gameLocal.Error()` naming the row if the call returns the raw id
back**. The same resolution pass is required of `MPValidateColumnTable()` (column
headers), `MPValidateMatchPresetTable()` (preset display names) and
`MPValidateStatFieldTable()` (stat display names). Four tables, one contract:
a missing id is a startup error naming its row, not a `#str_41537` rendered on
someone's scoreboard.

The static scan stays, because it covers the `.gui` files and the literal
call sites the tables do not own. The two together are the coverage claim;
neither alone is.

### Files that must stay in sync

`content/baseoq4/pak0/strings/english_openq4.lang`, `french_openq4.lang`,
`italian_openq4.lang`, `spanish_openq4.lang` — **all four in the same commit**,
untranslated mirrors carrying the English text as placeholder, which is the
accepted practice already visible in the Quake Live block.

### Constraints

- UTF-8, **no BOM**, and every code point representable in Windows-1252 — pinned
  by `tools/tests/lang_table_encoding.py`, because the stock fonts are a
  256-glyph atlas and `idLangDict` transcodes at load. No typographic quotes, no
  em dashes, no arrows, and no check marks for ready state; use a
  `TAB_TYPE_ICON` material instead.
- Nothing may follow the closing brace — a bug the Quake Live port already had to
  fix in all four files.
- Format strings in this block may use **`%s` only**, because every parameter is
  pre-formatted to text before `va()` sees it.
- Team names, preset names and map names entered by an operator or captain are
  **user data**, not display strings, and are the one legitimate exception. They
  are validated (no colour codes, no quotes, length-capped) and carried as
  `CPARM_STR`.
- Console help strings and `gameLocal.Printf` diagnostics stay plain English.
  This boundary is stated explicitly so a reviewer does not read it as a
  violation.

The single highest-value check in `competitive_match_layer.py` is the one that
scans `openQ4-game/src/mpgame` sources **and** the `.gui` files for `#str_`
references and requires each to exist in all four mirrors. Roughly 400 new ids
across four files is the easiest project rule in the repository to break, and it
is the only rule a compiler cannot catch — which is why the table validators
above exist to catch the half a compiler and a grep both miss.

---

## 8. Feature-by-feature design

### 8.1 Match administration and presets

A preset is a **compiled table plus an optional `.cfg` override** — deliberately
not a new file format:

```cpp
typedef struct mpPresetSettingInfo_s { const char *cvar; const char *value; } mpPresetSettingInfo_t;
typedef struct mpMatchPresetInfo_s {
    const char *                  name;           // si_matchPreset token
    const char *                  localizedName;  // #str_ id
    int                           gameTypeMask;   // which gametypes it makes sense for
    const mpPresetSettingInfo_t * settings;
    int                           numSettings;
} mpMatchPresetInfo_t;
```

Shipped presets (`duel`, `tdm`, `ctf`, `ca`, `casual`) live in this table and need
**no content files at all**, satisfying the stock-asset rule outright. An operator
may additionally drop `presets/<name>.cfg` in the mod directory; `.cfg` is already
on `FileAllowedFromDir`'s whitelist (`openQ4/src/framework/FileSystem.cpp:5812-5858`,
`.cfg` matched at `:5824`) so it works on a
pure server. **Precedence is explicit and one-way: a `.cfg` of the same name is
applied *after* the compiled table, so it overrides rather than replaces**, and
`listPresets` marks any preset that has a `.cfg` override.

The `.cfg` is **parsed, not exec'd**. Each line must be `<cvar> <value>` where
`<cvar>` resolves in the competitive setting set; unknown keys are refused with a
console warning and the preset is rejected as a whole. Handing a player-votable
path straight to `cmdSystem->BufferCommandText( "exec ..." )` is OpenTDM's known
hole and this design does not reproduce it.

**Apply is atomic and deferred.** `matchPreset` during `GAMEON` stages the whole
setting list and commits it at the next `WARMUP` entry, because serverInfo
replicates every individual `si_` write immediately and a half-applied ruleset is
silently wrong. `applyMatchSettings` forces an immediate re-derive after a manual
edit.

**The drift flag is what makes the name mean anything.** `MPHashMatchSettings()`
hashes the competitive setting set — defined as exactly the rows in the setting
table, so there is no blind spot — at apply time. The hash is snapshotted *after*
the command buffer drains, not at invocation. Every subsequent modification
recomputes it; on mismatch `si_matchPreset` is republished as `duel*`.
`matchsettings` then prints exactly which rows diverged. Both CPMA and Quake Live
ship named rulesets that can silently be voted off-standard with no indication;
a one-character marker fixes the entire class of "is this server actually
standard" disputes for the cost of a hash.

`si_matchRules` additionally publishes a compact digest of *how* the config
deviates from stock, so the server browser can answer the same question before
connecting. `si_matchPhase` publishes warmup/countdown/live/overtime/review for
the same reason, and for that reason only — §4 records that the client's
authority on phase is `rvGameState` and that binding HUD logic to the ROM string
is forbidden.

**`matchsettings` covers the full competitive set — every `si_` *and* every
`g_` row in the table — not just the replicated ones.** The `si_`/`g_` split is a
replication decision; extending it to the audit surface would be a category error
that leaves an operator unable to see whether timeouts exist, whether hit
feedback is permitted, or whether spectators can vote.

This is also where the four properties a ruleset token would have bought are
recovered without reintroducing rulesets: a **name** (`si_matchPreset`), a
**one-operation apply** (`matchPreset`), a **deviation indicator** (the drift
marker and `si_matchRules`) and an **audit** (`matchsettings`).

### 8.2 Timeout and pause

This is the item the Quake Live port deferred, and the deferral was correct: the
port doc says it "needs a pause-offset audit of every stored deadline". The
solution below does not eliminate that audit, it makes it **enumerable, safe by
default, and mechanically checkable**.

#### The invariant, stated in one sentence

> **Every deadline is compensated exactly once: it is either a posted `idEvent`
> shifted by `idEvent::ShiftEventTimes`, or a stored absolute value shifted by
> `ShiftFrozenTime` / `ShiftFrozenDeadlines`, or a value compared against
> `MatchTime()` — never two of the three, and never none.**

The draft asserted that `MatchTime()` and `ShiftEventTimes()` compose, and then
walked straight into the failure it implies: item respawn is backed by an
`idEvent` (shifted) *and* was to be registered with `mpItemTimers` as a stored
match-time deadline (compensated again), so on resume it would have come back
wrong by exactly the pause duration. The invariant above is what forbids that,
and §8.9 shows the item timer discharging it by **deriving** its deadline from
the event rather than storing a second copy.

#### Deadline ownership table

Enumerated here so the audit is reviewable in one pass rather than distributed
through §8. Rows marked *(recon)* are asserted from the port work rather than
re-verified for this document; Phase 0 confirms each one and this table is
corrected in place if any is wrong.

| Deadline | Where it lives | Single mechanism |
| --- | --- | --- |
| `idItem` respawn (`EV_RespawnItem`) | event queue, posted at `Item.cpp:743` | `ShiftEventTimes` |
| `idItem` respawn FX (`EV_RespawnFx`) | event queue, posted at `Item.cpp:741` | `ShiftEventTimes` |
| Item timer display remaining | **nowhere — derived** | `idEvent::TimeRemaining( item, &EV_RespawnItem )` alone, computed at snapshot send time; no `MatchTime()` term, so `ShiftEventTimes` is its single mechanism (§8.9) |
| `inventory.powerupEndTime[]` | stored absolute, `Player.h:208` | `ShiftFrozenDeadlines` on `idPlayer`, **server only** |
| `rvWeapon::nextAttackTime` and weapon state timers | stored absolute | `ShiftFrozenDeadlines`, driven from `idPlayer` |
| `idPhysics_Parametric` trajectory start times | stored absolute, `Physics_Parametric.h:26-31` | `ShiftFrozenTime` -> `UpdateTime` |
| `idAnimBlend` channel start times | stored absolute | `ShiftFrozenTime` -> `idAnimator` |
| `renderEntity.shaderParms[SHADERPARM_TIMEOFFSET]` | stored absolute, seconds | `ShiftFrozenTime` |
| `rvGameState::nextStateTime` | compared | `MatchTime()` |
| `fragLimitTimeout`, `overtimeStartTime`, `matchStartedTime`, `GetMatchLengthMsec()` | compared | `MatchTime()` |
| `ScheduleTimeAnnouncements()` | compared | `MatchTime()` |
| `rvRoundGameState::roundStartTime` / `roundStateTime` | compared | `MatchTime()` |
| `rvTourneyArena` timers | compared | `MatchTime()` (Tourney is excluded from pause regardless) |
| `idPlayer` respawn deadlines *(recon)* | compared | `MatchTime()` |
| Freeze Tag thaw accumulators *(recon)* | compared | `MatchTime()` |
| `mpMatchVote::voteTimeOut` / `voteExecTime` | compared | `MatchTime()` |
| `g_readyDelay` countdown start (§8.5) | compared | `MatchTime()` |
| Map draft turn deadline | compared | `MatchTime()` |
| `pauseStartTime`, `pauseEndTime`, `resumeAtTime` | compared | engine time — the pause's own clock is never compensated |
| `ThrottleUserInfo`'s `switchThrottle[]`, `lastSpectateChange` | compared | engine time |
| Chat and command flood buckets, `g_allowKillMsec`, `g_inactivity` | compared | engine time — a pause must never grant free spam |
| Referee auth attempt windows and `g_refLockoutTime` | compared | engine time |
| `CheckClientTimeouts` | framework | engine time, not the module's to touch |

`competitive_match_layer.py` pins this table as a token list: every symbol in the
left column must appear in exactly one of the three mechanism sets in the
sources. It cannot find a deadline nobody thought of — §10 says so plainly — but
it can find one that acquires a second mechanism later, which is the failure
this invariant exists to prevent.

#### Why the clock cannot simply be stopped

On the client, `gameLocal.time` is assigned from the engine snapshot header
(`framenum = gameFrame; time = gameTime;`, `Game_network.cpp:1574-1575`), so the
game module cannot freeze it there at all. On the server, stalling `gameFrame`
would stall snapshots and client prediction while `CheckClientTimeouts` kept
running on wall time and began dropping clients after `net_serverClientTimeout`
(40s). WORR's "do not advance the frame" answer works because Quake II's frame is
one flat loop; idTech4's is not, and the client's clock is not the module's to
set. The accumulator is not a compromise; it is the only correct answer in this
engine.

#### The four mechanisms

**(1) A read-time accumulator for match rules.**

```cpp
ID_INLINE int idMultiplayerGame::MatchTime( void ) const {
    return gameLocal.time - matchState.GetPausedMsec();
}
```

`GetPausedMsec()` returns
`pausedMsecTotal + ( IsWorldFrozen() ? gameLocal.time - pauseStartTime : 0 )`.
Monotonic, never rewinds, and correct on both sides because `pausedMsecTotal` and
`pauseStartTime` are replicated and both are in **game time**.

**Every field of the pause is in game time.** `pauseStartTime`, `pauseEndTime`
and `resumeAtTime` are all `gameLocal.time` values. This is not an oversight and
it is not a second clock: `gameLocal.time` keeps advancing during a pause — that
is the whole point of the accumulator — so a timeout deadline expressed in it
both expires correctly and replicates correctly, and the client can render the
countdown directly. There is no wall clock anywhere in this design and no
dimensional mixing.

**(2) A uniform shift of the one event queue.** `EventQueue`
(`gamesys/Event.cpp:279`) is a single time-sorted `idLinkList<idEvent>`;
`Schedule` (`:648-674`) converts the caller's relative delay to an absolute
deadline at `:660` and inserts by a forward scan whose compare is
`this->time >= event->time` (`:664-667`, so equal deadlines are FIFO); and
`ServiceEvents` (`:766-777`) takes only the head and breaks at `:775` on the
first event with `time > gameLocal.time`, relying entirely on the sort
invariant. Adding the same integer to every node is a strictly monotone map, so
relative order and the FIFO tie-break are both preserved and no re-sort is
needed:

```cpp
void idEvent::ShiftEventTimes( int deltaMsec ) {
    for ( idEvent *e = EventQueue.Next(); e != NULL; e = e->eventNode.Next() ) {
        e->time += deltaMsec;
    }
}
```

Three verified constraints ride with this, all of which shape §3's file list:

- It **must** be written inside `Event.cpp`. `idEvent::time` is private
  (`Event.h:68`), `EventQueue` is a file-static with no accessor, and the public
  API (`Event.h:77-103`) exposes no time query at all — only `EventIsPosted`,
  which returns `bool`. Nothing under `mp/` can reach the queue.
- The queue is **global and shared by every `idClass`**, so a shift moves every
  pending event in the game, not only the ones a match pause means to freeze.
  In a multiplayer match essentially every queued event belongs to a gameplay
  entity, so this is right far more often than it is wrong; the exceptions
  (ambient sound scheduling, GUI-driven events) drift by the pause duration and
  are part of the cosmetic residual §10 records.
- `time` is a plain `int` in milliseconds with the wrap acknowledged in-source
  at `Event.cpp:659` (`// wraps after 24 days...like I care. ;)`). Pausing adds
  to absolute times and therefore moves the wrap earlier by the total paused
  duration — an hour of pause moves a 24-day horizon by an hour. Noted, not
  mitigated. `Save`/`Restore` persist absolute times without rebasing
  (`:933`, `:970`), which is a real hazard for savegames and is irrelevant here
  because multiplayer has none and the single-player tree is not touched.

**Call site and ordering, both load-bearing.** `idEvent::ShiftEventTimes(
gameLocal.msec )` is called once per frozen frame from the **head of
`idGameLocal::RunFrame`**, before the active-entity loop and **immediately before
the `idEvent::ServiceEvents()` call at `Game_local.cpp:4250`**. The ordering is
not stylistic: `ServiceEvents` (`Event.cpp:766-777`) fires every head event whose
`time <= gameLocal.time`, and `gameLocal.time` keeps advancing through the pause
by design, so shifting *after* `ServiceEvents` leaks one frame's worth of
near-due events per frozen frame while shifting *before* it does not. On the
client the same call runs from `idGameLocal::ClientPrediction` under the
`isNewFrame` guard and in the same relative position — before that function's own
`idEvent::ServiceEvents()` at `Game_network.cpp:2581`.
`competitive_match_layer.py` pins the ordered sequence `ShiftEventTimes` ->
`ShiftFrozenDeadlines` -> entity loop -> `ServiceEvents` alongside the gate's own
token sequence.

Incremental per-frame shifting is exactly correct, including for events posted
during the pause: they begin being shifted from the following frame, so their
remaining delay is preserved to the frame.

**Only deadlines that are genuinely posted events are covered by this
mechanism** — item respawn (`EV_RespawnItem`), item respawn FX (`EV_RespawnFx`)
and script-posted mover events. Powerup expiry, weapon refire and
`idPhysics_Parametric` trajectory start times are **not** events and are covered
by `ShiftFrozenDeadlines` and `ShiftFrozenTime` respectively; see the ownership
table above. `inventory.powerupEndTime[]` is a stored absolute polled per frame in
`idPlayer::UpdatePowerUps` (`Player.cpp:5430-5463`, server gate at `:5455`), never
a posted event, and `idPhysics_Parametric`'s start times live in
`parametricPState_t` (`Physics_Parametric.h:26-31`), not in the queue. **A
deadline named in that table is compensated by the mechanism its row names and by
no other.** `competitive_match_layer.py` carries the negative form of this as
well: `powerupEndTime`, `nextAttackTime` and the six `parametricPState_t` start
fields must appear in the `ShiftFrozenDeadlines` / `ShiftFrozenTime` token sets
and must **not** appear in any `PostEvent*` call site added by this layer.

**(3) A shift of the enumerable non-event absolute state — and its exact call
site.** The draft named `ShiftFrozenTime` but never said where it was called
from, which left it racing the gate's `UpdateTime` for ownership of
`current.time`. Both halves are settled here.

The event queue is not the whole story and the design says so plainly.
`idPhysics_Parametric::Evaluate` (`Physics_Parametric.cpp:563`) uses **only** the
absolute `endTimeMSec` — it never touches `timeStepMSec` — feeding it to
`GetCurrentValue()` for the spline, both interpolations and both extrapolations
(`:579`, `:586`, `:588`, `:592`, `:594`) and then storing it as the new physics
time (`:643`). Those `GetCurrentValue` implementations subtract their own
absolute `startTime` (`idlib/math/Extrapolate.h:101`, `:111`), so a mover's
position is a pure function of *absolute now minus absolute start*. Skipping
`Think()` freezes the displayed position, but nothing shifts those start times,
so on resume every door, plat and mover mid-travel snaps forward by the entire
pause duration. `idAnimator` has the same shape: channels store absolute start
times and `CreateFrame` is evaluated against `gameLocal.time` on the render path.

**The primitive for that shift already exists and is not new work.**
`idPhysics_Parametric::UpdateTime` (`:657-670`) computes
`int timeLeap = endTimeMSec - current.time` (`:658`) and adds it to
`linearExtrapolation` (`:662`), `angularExtrapolation`, `linearInterpolation`,
`angularInterpolation`, `splineInterpolate` and `current.spline->ShiftTime(
timeLeap )` (`:667`). `idPhysics_Base::UpdateTime` is an empty body
(`Physics_Base.cpp:225-226`), and `idPhysics_Static`, `idPhysics_StaticMulti`,
`idPhysics_Player`, `idPhysics_Monster`, `idPhysics_RigidBody`, `idPhysics_AF`
and `rvPhysics_Particle` all provide their own overrides. So `UpdateTime` is
already the hierarchy-wide "rebase to this absolute time" call, with existing
callers at `Entity.cpp:3142` and the cinematic-freeze paths at
`Game_local.cpp:4161` and `:4201`. **The draft's proposed
`idPhysics::ShiftFrozenTime` virtual is therefore deleted from the design**, and
with it one of the two competing writers of `current.time`.

`idEntity` gains one virtual:

```cpp
virtual void idEntity::ShiftFrozenTime( int deltaMsec );   // default is NOT empty
```

whose **default implementation** is exactly three things, in this order:

```cpp
void idEntity::ShiftFrozenTime( int deltaMsec ) {
    GetPhysics()->UpdateTime( gameLocal.time );          // the only writer of current.time
    if ( GetAnimator() ) {
        GetAnimator()->ShiftFrozenTime( deltaMsec );
    }
    renderEntity.shaderParms[ SHADERPARM_TIMEOFFSET ] += MS2SEC( deltaMsec );
}
```

That polarity is deliberate: a class that forgets to override still gets the
three things that matter.

**(4) One gate in the think loop, with one call site each for the two shift
methods.** In `idGameLocal::RunFrame`'s active-entity loop
(`Game_local.cpp:4159`, `:4199`, `:4212` — all three variants):

```cpp
if ( mpGame.IsWorldFrozen() && ent->PausesWithMatch() ) {
    ent->ShiftFrozenTime( gameLocal.msec );
    continue;                       // no Think() this frame
}
ent->Think();
```

Its client mirror in `idGameLocal::ClientPrediction` is **not the same loop and
cannot take the same code**, and the draft was wrong to say it was.
`Game_network.cpp:2547-2552` walks `snapshotEntities`, not `activeEntities`,
calls `ClientPredictionThink()`, not `Think()`, and is already wrapped in a
pre-existing `if ( ent->thinkFlags != 0 )` guard. Its literal form is therefore:

```cpp
for ( ent = snapshotEntities.Next(); ent != NULL; ent = ent->snapshotNode.Next() ) {
    if ( mpGame.IsWorldFrozen() && ent->PausesWithMatch() ) {
        if ( isNewFrame ) {
            ent->ShiftFrozenTime( gameLocal.msec );
        }
        continue;
    }
    if ( ent->thinkFlags != 0 ) {
        ent->ClientPredictionThink();
    }
}
```

Two consequences follow and are stated rather than left to be discovered. The
shift is applied **even to entities whose `thinkFlags` are zero**, unlike the
think call — which is correct, because a mover with `thinkFlags == 0` still owns
absolute trajectory start times that would otherwise never be rebased on the
client. And the **local player is thought separately**, outside this loop, at
`Game_network.cpp:2568` (`player->ClientPredictionThink()`), so the client-side
frozen pmove is its own edit at that line and is not covered by the loop gate at
all.

`competitive_match_layer.py` therefore pins **two** token sequences, one per call
site, rather than one shape claimed to serve both.

`ShiftFrozenTime` is called **only** on entities that skip `Think()` (or
`ClientPredictionThink()`) this frame. That is what makes `UpdateTime`
unambiguous: nothing else writes `current.time` on a frozen entity, and an entity
that is still running its own physics is never handed a second rebase. The gate's
exact form — including the absence of any other `UpdateTime` call inside it — is
part of the pinned sequence.

Entities that keep thinking but still own stored absolute deadlines need the
other half, and they are a small, named set: **players**. `idPlayer` overrides
`PausesWithMatch()` to false and instead runs a frozen pmove — movement and
weapon fire suppressed, view angles free, the thing Quake Live got wrong where
paused players could still walk and reposition. Its deadlines are shifted by a
separate method with a separate call site:

```cpp
// head of idGameLocal::RunFrame, once per frozen frame,
// after ShiftEventTimes and before the active-entity loop
for ( each connected idPlayer p ) {
    p->ShiftFrozenDeadlines( gameLocal.msec );   // powerupEndTime[], weapon timers
}
```

`idPlayer::ShiftFrozenDeadlines` does **not** call the `ShiftFrozenTime` base
implementation, because the player is still evaluating its own physics and
animator this frame. The two methods have disjoint call sites and disjoint
subject sets; that is the whole content of the resolution, and it is why the
invariant at the head of this section is checkable.

**Both passes run at the head of `idGameLocal::RunFrame`**, before the
active-entity loop and before `idEvent::ServiceEvents()`
(`Game_local.cpp:4250`), in the order `ShiftEventTimes` ->
`ShiftFrozenDeadlines` -> entity loop -> `ServiceEvents`. The draft hedged that
`idMultiplayerGame::Run()` might be the site; it is not, and the question is
answerable from the source rather than deferred to Phase 1. `mpGame.Run()` is
invoked at `Game_local.cpp:4264`, **after** all three entity-loop variants
(`:4159`, `:4199`, `:4212`) and after `ServiceEvents()` (`:4250`), so it is not a
legal site for either pass.

One consequence of `Run()` sitting last: the gate at `:4159` reads an
`IsWorldFrozen()` that the **previous** frame's `Run()` set, not the current
frame's. The pause and resume edges are therefore applied one frame late, by
design. That is 16 ms of latency on a transition both sides already learn about a
round trip apart, it is deterministic rather than racy, and it is strictly
preferable to splitting the pause state machine across the frame to save one
frame.

Spectator cameras, GUI entities and ambient sound override `PausesWithMatch()`
to false so a referee can still fly and read the board, and they define no
`ShiftFrozenDeadlines`, so they are touched by neither mechanism — correct,
because they own no match deadline.

Shifting **every frozen frame** rather than accumulating a delta and applying it
on resume removes an entire bug class: WORR ships a live bug where aborting out
of a pause clears the state without applying the delta and leaves every powerup,
respawn and warmup deadline in the past, and AfterShock's changelog records five
separate follow-up fixes for the same design.

#### The client side

The server is authoritative. On the client:

- The same `PausesWithMatch()` **decision** is applied in `ClientPrediction`,
  driven by the replicated pause state — but in the different literal form given
  in (4) above, over `snapshotEntities` and `ClientPredictionThink()`, plus a
  separate edit for the local player at `Game_network.cpp:2568`. It is the same
  rule, not the same code.
- `ShiftEventTimes` and `ShiftFrozenTime` are called on the client **only when
  `isNewFrame` is true**. `ClientPrediction` runs repeatedly per render frame for
  re-prediction with `isNewFrame` false (`Game_network.cpp:2514-2519`) and calls
  `idEvent::ServiceEvents()` on every one of those passes; an ungated shift would
  advance the client's queue by prediction-depth multiples of the server's.
- **`ShiftFrozenDeadlines` is server-only for any field that is replicated
  absolutely.** `inventory.powerupEndTime[]` is written into the snapshot as
  absolute longs (`Player.cpp:13257-13259`, read at `:13295-13298`), so the
  client receives values the server has already shifted; shifting them again
  client-side would double-compensate — the same class of bug the invariant
  forbids, arriving through the wire instead of through a second store. The
  client applies `ShiftFrozenDeadlines` only to fields it predicts and the
  server does not correct; Phase 1 enumerates that set and pins it, and today it
  is expected to be empty.
- The client learns of a pause one reliable round-trip late and will have
  predicted a frame or two into it. The server is authoritative and the next
  snapshot corrects the position; the visible artifact is a small snap at the
  moment of pause, which is what every implementation in this lineage does. It is
  *not* acceptable at resume, which is precisely why `g_timeoutResumeDelay`
  exists: the unfreeze moment is known to both sides in advance.
- Purely client-side effect and sound timing may drift by the round-trip. That is
  cosmetic and is documented rather than papered over.

#### The hoist list — what keeps running while frozen

Stated deliberately rather than discovered later: snapshot writing, `UpdateHud`,
the scoreboard, chat, referee and admin commands, `players`, `matchsettings`,
`maplist`, stats commands, spectator camera movement, map-draft turns, and
client-timeout accounting. Whether a verb survives the freeze is a **column on
the command table** (`MCF_WHILEPAUSED`), not a condition scattered through
handlers. Vote *counting* is suspended automatically because ballot deadlines are
in match time — putting the ballot on match time *is* the suspension, for free,
and means a ballot cannot expire while the world is frozen. WORR hoists only
`ClientEndServerFrames` and consequently cannot take an admin command while
paused; that is a mistake worth not repeating.

#### Policy

`timeout` spends one of the caller's team budget (`g_timeoutCount`, per team in
team modes, per player in Duel) and runs for `g_timeoutLength`. `timein` resumes
early — **caller or referee only** — and starts the `g_timeoutResumeDelay`
countdown. A warning is announced at `g_timeoutWarnTime` before auto-resume.

**A coach spends the team's budget.** The draft left this undefined: §8.6 gives a
coach the right to call a timeout while remaining a spectator, and budgets are
per team or per player, and a coach is on neither roster. The rule is that a
coach's `timeout` decrements the coached team's budget, is announced with the
coach's name and the team, and is subject to the identical `MPS_RESUMING` lock.
In Duel, where the budget is per player, a coach spends the budget of the player
they coach. A coach may not `timein` a timeout they did not call unless the
caller has disconnected.

`IsWorldFrozen()` returns **true for both `MPS_PAUSED` and `MPS_RESUMING`**, and
`MatchTime()` is frozen through both. The countdown is announcement only; the
world unfreezes on zero. Any other reading is an exploit: it would hand players
`g_timeoutResumeDelay` seconds of free movement off the clock.

Ownership survives a disconnect. `pauseOwner` is a client slot **plus a
`connectionToken`** — a monotonically increasing per-connection value assigned at
`ClientBegin` — so a stranger who lands in a recycled slot does not inherit the
right to resume. The same token guards `refMask` bits, captaincy and roster
entries; all four are cleared on disconnect and on map change. If the owner
disconnects, the pause auto-resumes at its deadline and a referee may resume
immediately.

The alternating-callers loophole is closed explicitly: while `MPS_RESUMING` is
active, no new `timeout` may be opened by anyone until the world has actually
unfrozen. OpenTDM has this griefing vector and its absence here must be shown,
not assumed.

`g_pauseOnDisconnect` auto-pauses when a live player drops and auto-resumes when
they return — and "they" is now defined, because §8.5's `mpMatchRoster` records
the connection token and team of every player at `GAMEON`. A different player
taking the freed slot does not satisfy the resume condition. A referee pause
supersedes and locks a player timeout: the original caller can no longer cancel
it.

**Tourney is excluded from pause in Phase 1** with a localized refusal.
`rvTourneyArena` is a multi-arena elimination bracket with its own state machine;
Q4MAX's own documentation says pause does not work in Tourney and tells
tournaments to use Duel instead. Being explicit beats shipping a pause that
silently corrupts a bracket. The exclusion is an `MCF_` gate on the row, and
lifting it is a separate, auditable change.

### 8.3 Referee authority and the referee page

`mp/match/MatchCommands.{h,cpp}` holds one descriptor table, built in the house
style of `mp/GameTypes.cpp`:

```cpp
typedef struct mpMatchCmdInfo_s {
    mpMatchCmd_t    id;             // wire value; the table is indexed by it. APPEND ONLY.
    const char *    name;           // console token, and the callvote token
    const char **   aliases;        // NULL-terminated secondary spellings, or NULL.
                                    // A row may carry several: timeout has { "pause", "calltime" },
                                    // follow has { "spec", "obs", "chase" }, timelimit has { "tl" }.
    mpAuthority_t   level;          // minimum authority
    int             flags;          // MCF_*
    mpArgType_t     argType;        // MAT_NONE / INT / CLIENT / TEAM / STRING / TOKEN / MAP
    int             argMin, argMax;
    const char **   argTokens;      // MAT_TOKEN: NULL-terminated legal values
    const char *    descId;         // #str_ id, one line
    const char *    usageId;        // #str_ id, argument form
    const char *    voteDescId;     // #str_ id used to render the ballot, or NULL
    mpApplyFn_t     apply;
} mpMatchCmdInfo_t;
```

`MCF_VOTABLE` · `MCF_SELFTEAM` (a captain may only target their own team) ·
`MCF_LIVEONLY`, `MCF_WARMUPONLY`, `MCF_REVIEWOK`, `MCF_WHILEPAUSED` ·
`MCF_SPECTATOR` (a spectator may issue it) · `MCF_TEAMGAME`, `MCF_DUEL`,
`MCF_NOTOURNEY` · `MCF_AUDIT` (always written to `g_adminLog`) · `MCF_HIDDEN` ·
`MCF_GUI` (appears on the referee page) · `MCF_EXISTINGCMD` (this row
deliberately shares its name with a console command registered outside this
layer; see below).

`MPValidateMatchCommandTable()` runs at game init and `gameLocal.Error()`s if a
row is not indexed by its own `mpMatchCmd_t`, if `name` or **any entry in
`aliases`** collides with another row, if any of `descId` / `usageId` /
`voteDescId` fails to resolve through `common->GetLocalizedString`, if
`MCF_WARMUPONLY | MCF_LIVEONLY` are both set, if an `MCF_VOTABLE` row has no
`voteDescId`, or if a name in `g_voteAllow`'s default whitelist has no row — the
same loud-failure contract `MPValidateGameTypeTable()` already provides.

**The console-command collision rule needs stating precisely, because the naive
form errors on the shipped table.** Almost every row in §5 is *also* a locally
registered console command — that is forced, since there is no client-to-server
console fallthrough, so `ready`, `timeout`, `callvote`, `players`,
`matchsettings`, `matchPreset` and the rest each have a registration whose handler
sends `GAME_RELIABLE_MESSAGE_MATCHCMD`. A rule reading "error if the name matches
any registered console command" would fire on all of them. The rule is therefore:

> The validator errors if `name` or any entry in `aliases` matches a console
> command registered **outside** the layer's `// openQ4: competitive match layer`
> registration block and not dispatched through `MPExecuteMatchCommand` — unless
> the row carries `MCF_EXISTINGCMD`, in which case it instead asserts that the
> existing registration's handler **is** the row's own apply function.

A row whose console registration is this layer's own handler for that row is not
a collision. A row whose name is owned by someone else — `serverForceReady`,
`kick`, `say`, `mute` — is, and must declare `MCF_EXISTINGCMD` and prove the
handlers match. `allready` is the case this exists for: its registration at
`SysCmds.cpp:3496` predates the layer and its handler
`idMultiplayerGame::ForceReady_f` is the row's apply function, so the row and the
registration are one capability and the validator recognises the pairing rather
than rejecting it. `serverForceReady` remains illegal as a row name because it is
console-only at `MPA_CONSOLE` and has no row (§5). This is also why
`AddCommand`'s first-wins behaviour (§5) matters: an existing registration is
never displaced, so a matching handler is the only safe way to share a name.

**The table is the vote table.** A referee running `ref timelimit 15` and a passed
`callvote timelimit 15` invoke the same apply function through the same
validator. This is what stops the result reading as two mods: there is exactly one
place where "what a match setting is" is written down, and the console help, the
vote list, `g_voteAllow`, the referee dispatcher, argument completion, the audit
log, the referee GUI page and `commands` are all derived from it. Adding
`shuffle` as both a referee action and a vote is one row.

Every referee action carrying `MCF_AUDIT` writes a structured line to
`g_adminLog`: timestamp, caller name, caller level, verb, target, arguments and
accept/reject. **Refused attempts are logged too** — that is what makes the log
usable in a dispute. Passwords are never logged, which is why MATCHAUTH is a
separate message from MATCHCMD.

`ref` is a single registered command whose second token indexes the table.
Registering thirty separate referee commands would pollute the global console
namespace, need thirty hand-written permission guards, and make the capability
set discoverable only by reading source. **`ref <unrecognised token>` prints a
usage error and does not fall through to the login path**; login is
`ref <password>` only when the caller is *not already a referee*, and resignation
is the explicit `ref logout`. Without that rule a referee who mistypes
`ref unpuase` silently loses their referee status mid-match.

#### The referee page — the replacement, not a removal

The rcon-proxy admin tab in `mpmain.gui` is deleted. The draft stopped there,
which would have left a listen-server host who used that tab with nothing but
console commands, and would have left `si_refAvailable` — a replicated key
declared "so clients can show referee UI" — with no consumer at all. Both are
fixed by building the successor:

- A **Referee** page in `mpmain.gui`, reachable at all times from the
  multiplayer menu, with a password field that submits
  `GAME_RELIABLE_MESSAGE_MATCHAUTH`. It is not gated on a replicated
  advertisement key, because the server's answer is itself the advertisement:
  either a grant, or *this server has no referee system*, or *incorrect
  password*.
- Once the grant arrives, the page enables an action list **generated from the
  command table** — every row carrying `MCF_GUI` that the caller's authority
  permits, with its localized `descId`, its argument widget chosen from
  `argType`, and its range taken from `argMin`/`argMax`. There is no hand-written
  button list, which is the same "declare once" property the console help gets.
- Player-targeted rows (`MAT_CLIENT`) render a roster picker fed by the same
  data `players` prints. `pause`, `unpause`, `abort`, `putTeam` and `kick` are
  the minimum set that must be reachable from the page, and Phase 2's exit
  criteria name exactly those.
- The page issues `GAME_RELIABLE_MESSAGE_MATCHCMD` like every other caller and
  is re-validated server-side like every other caller. It is a front end, not a
  second authority path.

This is strictly more capable than what it replaces: the rcon proxy required the
rcon password and granted everything or nothing, and it was unusable from a
remote client without handing out server-console access.

### 8.4 Voting, the map pool and the map draft

#### The ballot

`mp/match/MatchVote.{h,cpp}` owns the ballot lifecycle over the §8.3 table and
has no per-vote logic of its own.

- Eligibility is recomputed **every frame** from the live roster, so joins and
  leaves cannot deadlock a ballot and a leaver changes the denominator.
- The caller is auto-YES. The ballot **passes early** the instant
  `yes > eligible/2` and **fails early** the instant `no >= (eligible+1)/2`,
  rather than waiting out `g_voteTime`. A 2-0 vote in a duel resolves
  immediately.
- `g_votePassPercent` sets the threshold; `g_voteArmDelay` blocks Yes/No for the
  first seconds so a bound key cannot misfire; `g_voteExecDelay` defers execution
  so players see the result; `g_voteCooldown` blocks the same caller after their
  own vote fails; `g_voteLimit` caps calls per player per match; `g_voteDelay`
  blocks voting after map load. Every one of those deadlines is in match time,
  so a pause suspends the ballot rather than expiring it.
- `g_voteAllow` is a slash-delimited token whitelist, not a bitmask.
  `si_voteFlags`' own help text already disagrees with `voteFlag_t`, and Quake
  Live's equivalent mask carries a typo that propagated through every third-party
  guide. A string is editable, self-documenting, printed verbatim by
  `callvote ?`, and impossible to get subtly wrong. **An unrecognised token in
  `g_voteAllow` produces a `Warning()` at set time**, so a typo does not silently
  disable a vote.
- `ref passVote` and `ref cancelVote` force a ballot through or kill it. An
  admin's vote does *not* magically decide a ballot; a referee uses an explicit
  referee command.
- `callvote` with no arguments prints exactly the rows `g_voteAllow` permits, with
  their localized descriptions and current values. `callvote <setting> ?` prints
  the usage and the current value. That is the entire in-game documentation story
  and it is free, because it walks the table.
- HUD: a vote banner with a live yes / needed / no tally and a countdown,
  replacing the one-shot notice. **The tally the banner shows is the tally that
  decides the ballot** — both come from one function; OpenTDM has two and they
  disagree.

The legacy single-field vote path is **removed**: `ClientCallVote`,
`ServerCallVote`, `ServerStartVote`, `ClientStartVote` and `ClientUpdateVote`,
together with the server-side `GetLocalizedString` calls and the three raw
English strings. The legacy ordinals stay in the enum (removing them would
renumber the wire format) and their handlers become no-ops. `mpmain.gui`'s vote
tab and its `setVoteMapList` / `setVoteData` feeds are repointed at
`GAME_RELIABLE_MESSAGE_VOTESTATE` in the same change — this is not optional
cleanup, it is the difference between a working and a dead vote menu.

#### The map pool

The draft said "the existing `SendMapList` / `ReadMapList` / `RequestVoteMaps`
transport is reused as-is", which is true of the transport and misses the point:
without a filter, `callvote map` on a competitive server can load a
single-player campaign map, and every reference implementation in the lineage
has a pool (OpenTDM `g_maplistfile`, CPMA `map_cfgdir`, Quake Live
`sv_mapPoolFile`, Q4MAX `maplist`).

`g_mapPool` is a slash-delimited list of map names, empty by default meaning
"every installed map", which is exactly today's behaviour. It does three things
and no more:

1. **Filters `SendMapList`.** Clients receive only the pool, so the vote menu
   and console completion show only legal choices.
2. **Validates `callvote map` and `ref map` server-side.** A client that sends a
   map outside the pool is refused with a localized message naming the pool
   size, not silently ignored — the transport is a reliable message and a
   fabricated payload must be rejected, not trusted.
3. **Backs the `maplist` command**, which prints the pool with its localized
   header, or a note that every installed map is allowed when the pool is empty.

Entries are validated at set time against the map decl for the current gametype
(the `mapDeclKey` column `mp/GameTypes.cpp` already carries), and an entry that
does not resolve produces a `Warning()` naming it — the same shape
`g_voteAllow`'s unknown-token warning takes, for the same reason. The pool is a
`g_` cvar rather than an `si_` one: clients receive the pool through the existing
map-list transport, so nothing needs it in the serverInfo datagram.

#### The map draft

Every duel league's actual workflow is alternating ban and pick over a pool. The
draft plan had `ref cointoss` — the tool used to decide *who bans first* — and
nothing to ban with, and did not exclude the feature either. It is designed
here, small, and gated off by default (`g_mapDraft 0`).

A draft is a short-lived state on `mpMatchState`: an ordered sequence of turns,
a current turn index, the acting side, a per-turn deadline in match time, and
the set of maps already removed. `ref draft start [sequence]` opens it; the
sequence is a token string like `ban/ban/pick/pick/ban/ban/pick` defaulting to
alternating bans until one map remains. The acting side is the team captain in
team modes, or the player themselves in Duel; `ref veto <map>` and
`ref pick <map>` let a referee act for a side that is absent or stalling.
`ref draft cancel` abandons it; `ref draft status` prints the state; the whole
thing is refused outside `WARMUP`.

Each turn is announced through the widened centre print with `CPARM_STR` for the
map name, the remaining pool is pushed to clients through the same filtered map
list `SendMapList` already uses, and the final result sets the next map exactly
as a passed `callvote map` would. Turn deadlines are in match time and the draft
is on the hoist list, so a pause during a draft suspends the turn clock rather
than timing a captain out.

This is the one feature in this document with no in-repo precedent to extend,
which is why it sits behind a default-off gate and is raised as an open question
in §10.

### 8.5 Team management, the match roster, ready and match start

#### Captains, locks and invites

Captains (`g_allowCaptains`) are auto-assigned to the first joiner and
auto-reassigned when they leave, so captaincy never becomes a blocker. Every
captain command is gated `MPA_CAPTAIN | MCF_SELFTEAM`, so a referee reaches the
same handler for either team and there is exactly one implementation.

Roster lock and spectator lock are replicated on `mpMatchState`, not smuggled
through loose cvars written from three call sites. Spec-lock is enforced at
**every** point the chase target can change — `SpectateFreeFly`, `SpectateCycle`,
`UpdateSpectating` and follow-by-name — and when both teams are spec-locked the
spectator is placed on a fixed overhead camera with a localized notice rather than
left free-flying inside the locked area, which is worse than showing them the
game.

Invites are consent-based (`invite` then `accept`) and are **re-validated at
accept time**, not at issue time: the inviter must still be connected and still
be captain, the team must still be under its cap, and mid-match the team must
still be under the size it started the match with. That last clause is only
meaningful because the roster below defines where "the size it started the match
with" is stored. Invites are cleared at every match-state boundary, so a warmup
invite cannot become a mid-match team-stacking exploit. `removePlayer` moves one
of the caller's own team to spectator. Forcible picking is not offered; a
referee's `ref putTeam` covers the case a captain cannot.

`teamName` sets a replicated per-team display name, replacing the hardcoded
`Marine`/`Strogg` at `MultiplayerGame.cpp:45-48`. Validation: no colour codes, no
quotes, no control characters, 16 characters maximum — the same rules external
scoreboard scrapers need. It is user data, so it travels as `CPARM_STR` and is
not a `#str_` id; the *default* names remain **`#str_108026` (Marine)** and
**`#str_108025` (Strogg)** — note the ids are in the reverse of the obvious
order — resolved by `MPLocalizedTeamName` at `MultiplayerGame.cpp:6683-6685`,
which states the mapping in a comment at `:6684`. Only `english_code.lang:663-664`
and `spanish_code.lang:663-664` carry these two ids in this repository; the French
and Italian code tables must be checked before any team-name feature depends on
them resolving.

`shuffle` is a score-weighted snake draft (highest current match score first,
alternating), warmup-only, requiring at least two players; it unreadies everyone
and announces. It is one table row, so `ref shuffle` and `callvote shuffle` share
it. `g_lateJoin 0` places a client connecting during `GAMEON` in spectator until
the match ends. `speconly` and `specdefer` layer onto Duel's existing queue and
publish the caller's position.

An `EndmatchGraceScope` RAII guard wraps the population-dependent end-of-match
conditions (no players, too few players, imbalanced teams) with a 200 ms grace
window, so a player switching teams for one frame cannot end a match. Each
violation gets a fresh window; the destructor resets the timer if nothing fired.

#### The match roster

openQ4 has no concept of a match roster distinct from the connected client list,
and several features in this document quietly assume one. `mpMatchRoster` is a
small fixed array on `mpMatchState`, populated at the `COUNTDOWN` to `GAMEON`
edge and cleared at `NEXTGAME`:

| Field | Purpose |
| --- | --- |
| `connectionToken` | Identity across a slot recycle, the same token that guards `pauseOwner`, `refMask` and captaincy |
| `team` | The team the player started the match on |
| `score` | Score at disconnect, restored on reconnect |
| `flags` | Present / disconnected / substituted-out |
| `matchStartTeamSize[TEAM_MAX]` | The size each team had at `GAMEON` |

It is consulted in exactly four places, and naming them is the whole design:

1. `MPEvaluateTeamJoin()` refuses a mid-match join that would take a team over
   `matchStartTeamSize`.
2. `g_pauseOnDisconnect`'s resume condition matches on `connectionToken`, so a
   different player taking the freed slot does not end the pause.
3. A reconnecting player with a matching token is placed back on their original
   team with their score restored.
4. `MATCH_REPORT` in the match log carries the roster, so a substitution is
   visible in the record.

**The boundary is stated so no reader has to infer it: roster and score are
restored; inventory, health, armour, ammo, weapon and position are not.** §2
excludes inventory restore; this is where it says what *is* restored instead. A
substitution is expressed as a referee `putTeam` plus the roster's
substituted-out flag, not as a distinct command.

#### Ready anti-stall

openQ4 gates warmup on `si_warmupReadyPercentage` (default 0.51) with Duel
demanding both players. A percentage does not solve the actual tournament
problem, which is an opponent who will not ready: in Duel, 51% of 2 is still 2.
The draft's answer was `ref allready`, which is a referee-only fix to a problem
that mostly occurs when no referee is present.

Two cvars and one timer:

- `g_readyDelay` — seconds after the **first** ready in a warmup before the
  action fires. 0 disables, which is today's behaviour.
- `g_readyDelayAction` — 0 announce only, 1 move every un-ready player to
  spectator, 2 force everyone ready.

A localized warning is announced at the halfway point and again at five seconds,
naming the remaining time; the countdown resets if everyone readies or if the
last ready player un-readies (so the timer cannot be farmed by a single ready
press). The timer is in **match time**, consistent with the ownership table, so
it is suspended by a pause. `g_readyDelayAction 1` moving players to spectator
uses the same path `g_inactivity` does, so there is one implementation of "move
this player to spectator with a localized notice".

#### Match start world reset

Warmup state persists into the live match today: doors and lifts sit wherever
warmup left them, projectiles fired during the countdown survive into `GAMEON`,
and a player standing on a spawn point at `Fight!` can bias or telefrag the
first spawn. WORR's `PrepareCountdownEnvironment` and OpenTDM's two-pass
unlink-then-respawn both exist for exactly this. Since this plan is already
inside the entity think loop and already understands `idPhysics_Parametric`,
the work is adjacent and cheap.

`MPResetWorldForMatch()` runs at the `COUNTDOWN` to `GAMEON` edge and does four
things in order:

1. Return every triggered mover to its rest state and cancel its pending move
   events.
2. Free every live projectile and its effects.
3. **Unlink every player** from the clip world, then respawn all of them, so no
   player's warmup position can influence another player's spawn selection or
   cause a telefrag — the two-pass order is the whole point and doing it in one
   pass reproduces the bug.
4. Re-run the item respawn pass so every timed item is present at `Fight!`
   regardless of what warmup consumed, and rebuild the `mpItemTimers` registry.

It is not configurable. A match that starts from a different world state
depending on what happened during warmup is not a match, and an operator gate
here would only ever be used to reintroduce the defect.

#### The ready path defect

`idMultiplayerGame::ToggleReady` (`MultiplayerGame.h:603`,
`MultiplayerGame.cpp:8499`) is the handler behind `IMPULSE_17`
(`Player.cpp:8987-8992`) and behind the GUI `"ready"` token, which forwards to
the same impulse (`Player.cpp:7067-7068`). It works by reading and writing the
`ui_ready` userinfo cvar with the literal strings `"Ready"` and `"Not Ready"`
(`MultiplayerGame.cpp:8514-8519`) and self-throttles at 500 ms through
`lastReadyToggleTime`.

The defect is narrower than it first appears, and the correction matters because
it changes how much work this is. openQ4 has **already** built the authoritative
path: `idPlayer` carries a `bool ready` (`Player.h:933`) with a `readyUserInfo`
shadow (`Player.h:938`) and `GetReady`/`SetReady` accessors
(`Player.h:654-655`); the console commands go over
`GAME_RELIABLE_MESSAGE_READY` (`MultiplayerGame.cpp:7211`); and
`UserInfoChanged` only acts on a genuine `ui_ready` transition
(`Player.cpp:3671`) so a stale userinfo resend cannot clobber a reliable ready.

What remains is that the **bind** and the **console command** take different
transports. A bound ready key still travels as a userinfo change and can be
swallowed by `ThrottleUserInfo`'s five-second cap, while `ready` typed into the
console cannot. Since this plan adds per-player ready dots to the HUD and an
entire authority layer around ready state, leaving two transports for one fact
would be indefensible.

The fix is one edit with two call sites already pointing at it: `ToggleReady`
stops using `ui_ready` as its transport and instead sends
`GAME_RELIABLE_MESSAGE_READY` carrying the negation of the authoritative
`idPlayer::GetReady()`. `ui_ready` continues to be written as a **shadow** so
the existing menu widget still reflects state, and the `readyUserInfo`
anti-clobber at `Player.cpp:3671` is retained unchanged. The 500 ms
`lastReadyToggleTime` self-throttle stays — it is a sane debounce on a key
repeat, and unlike `ThrottleUserInfo` it does not silently discard the last
press. Phase 4 pins the result: a ready bind and the `ready` command must
produce identical state within one frame.

### 8.6 Spectator and observer tooling

`follow <name|slot>`, `follownext`, `followprev`, and the sticky auto-follow modes
`follow killer` (retargets about 400 ms after the followed player dies),
`follow leader` (tracks the score leader across a lead change) and
`follow quad|regen|haste|invis|flag` (cycles through holders on repeat). These
three are what a caster actually uses and openQ4 has none of them; each is a
per-frame target-selection policy over the existing follow machinery, hooked to
the kill and pickup events that already exist.

Free-fly is gated by `g_specFreeFly`. The 500 ms spectate-change cooldown is
relaxed for spectators and referees — it is a caster annoyance, not an anti-abuse
measure. It is **two** edits, not one: `lastSpectateChange` is written at
`Player.cpp:6967` and again at `:6996` (`lastSpectateChange = gameLocal.time +
500;`) and tested at `:6934` and `:6979`, with the member cleared at `:1430` and
`:1940` and declared at `Player.h:945`. The draft cited `Player.cpp:73-74`, which
is `const int SPECTATE_RAISE = 25;` — an unrelated view-height constant.

**Spec-lock is the anti-ghosting mechanism, and that is its purpose rather than
a side effect.** Because openQ4 has no spectator delay and will not gain one
(§2), a spectator watching a live match is a live intelligence channel; a
spectating team mate, or a player watching an opponent's stream, sees positions
and item timings in real time. `specLock` hides a team from uninvited
spectators, `specInvite` whitelists individuals, and `g_spectatorChat 0` keeps
spectators off the live chat channel so what they see cannot be relayed
in-game. Together those are the whole in-game answer; a broadcast delay is a
tournament-operations concern and lives in the streaming pipeline. Stating the
rationale matters because a reader who does not know why spec-lock exists will
configure it wrong.

The **coach role** is invite-and-consent: a team member runs
`coachInvite <player>`, the spectator accepts with `coach` or refuses with
`coachDecline`, `coachKick` revokes, and a referee can install or remove one
directly. A coach receives team chat and the team overlay and may call a timeout
while remaining a spectator, spending the coached team's budget under the rules
§8.2 sets out. `g_coach` is the server gate.

The **spectator team-vitals overlay** shows every player's health, armour, weapon
and nearest-item location, built entirely from data the team overlay already
carries.

Spectator chat routing keeps `g_spectatorChat`'s existing meaning (spectators not
heard by live players during a match by default, the check at
`MultiplayerGame.cpp:8357`) and adds `g_allTalk`. The cvar's flags change (§4);
its behaviour does not.

### 8.7 Stats, accuracy and hit feedback

**Collection.** Per client, per weapon: shots, hits, kills, deaths, damage dealt,
damage received. Plus totals for damage given and taken, suicides, team damage
(bucketed separately), kill streaks, per-item pickup counts **and mean pickup
interval** for mega health, red armour, yellow armour and each powerup, and
powerup hold time.

The accumulation rules are the difference between believable numbers and garbage,
and they are fixed up front: **one hit per shot** except hitscan, which counts per
beam — a shotgun blast hitting one target is one hit, not eight; **self damage**
counts in damage received and never in damage dealt or accuracy; **team damage**
is bucketed separately and never pollutes accuracy; **corpse damage** scores
nothing; **warmup is excluded entirely**.

`statManager->Init()` runs at both `WARMUP` and `GAMEON` entry today
(`GameState.cpp:483-486` and `:568-570`), and `Init()` calls `Shutdown()`, which
default-constructs every `rvPlayerStat` (`StatManager.cpp:344`) and resets the
allocator — so everything accrued during warmup is discarded when `GAMEON` is
entered, which is the documented intent, but it also makes per-round
accumulation impossible and it re-registers the `ShowInGameStats` console
command on every call (`StatManager.cpp:332`). An explicit `MPSS_MATCH` /
`MPSS_ROUND` scope replaces the double `Init()`, so round modes accumulate per
round and per match independently, and command registration moves to a one-shot
path. The two client-side `Init()` calls in `rvGameState::UnpackState`
(`GameState.cpp:263`, `:302`) take the same scope.

Item pickups become **counters on the per-client stat struct**, not queued
`rvStat` events. `rvStatAllocator` is a fixed 128 KB slab (`BLOCK_SIZE 1024 *
MAX_BLOCKS 128`, `StatManager.h:110-111`, `:115`) with no heap growth and no
failure path: past `MAX_BLOCKS` it wraps to block 0 (`StatManager.cpp:134-139`)
and calls `FreeEvents` to drop the events pointing into the block it is about to
overwrite (`:148`) — but `FreeEvents` returns 0 **without removing anything**
when the block's events run to the end of `statQueue` (`:544-548`), while
`GetBlock` hands out and overwrites that memory regardless, leaving dangling
`rvStat*` in the queue. A free list is added regardless of the pickup-counter
change, and `RemoveRange( blockStart, blockEnd - 1 )` at `:550` is re-derived
against a half-open intent at the same time.

`GetPlayerTime` (`MultiplayerGame.cpp:9768`) reports whole minutes since connect
and is useless as a competitive stat; it is replaced by time played this match.

**Live HUD.** The accuracy overlay is hold-to-show over
`GAME_RELIABLE_MESSAGE_ACCURACY`, redirected to the followed player when the
requester is spectating. The hold is the existing `_ingameStats` usercmd button
(`UsercmdGen.cpp:197`, `UB_BUTTON5`) rather than a `+acc` / `-acc` pair, which
this engine cannot express — see §5 for why. `acc` toggles the same overlay from
the console. The `stats` family remains available as commands. During
`GAMEON` with `g_statsRedactOpponent 1`, a player sees only their own and their
team's detail; spectators see everything; everyone sees everything at
`GAMEREVIEW`. In Duel the item-control columns are specifically blanked on the
opponent's row during a live match — a player and a caster get their own timing
data without handing the opponent a free readout.

**Hit feedback.** The draft declared `hud_damageNumbers` in §4 and then never
mentioned it again: no wire, no design, no phase, no exit criterion. Every
reference in the lineage ships hit confirmation (Q4MAX `g_crosshairblink` plus
hit beeps, Quake Live `cg_hitBeep` with damage buckets, WORR
`MM_HitSoundForDamage`, AfterShock's crosshair blink scaled by victim armour)
and none of it appeared in the plan. It is designed here rather than deleted,
because openQ4's damage amounts are server-only — `PackStats` omits
`damageGiven` and `damageTaken` entirely — so there is genuinely no way for a
client to know it landed a hit today.

`mp/HitFeedback.{h,cpp}` accumulates, per attacker, every damage application
during a server frame, and emits at most one `GAME_RELIABLE_MESSAGE_HITINFO` per
attacker per frame (§6). The gate is `g_hitFeedback`: 0 sends nothing, 1 sends
the hit with a zeroed damage field, 2 sends the amount. The client renders
`hud_hitBeep` (0 off, 1 one cue per hit, 2 pitch varies with damage, using stock
sound shaders only) and `hud_damageNumbers` (0 off, 1 damage this player dealt,
2 all recent damage the client has been told about, which is the same set —
mode 2 differs only in retaining a short history rather than showing one
number). Team damage and self damage carry flags and are rendered distinctly or
suppressed by the client; they never move accuracy either way, consistent with
the accumulation rules above.

Both client cvars default to 0, so a player who edits nothing hears and sees
exactly what they do today. `g_hitFeedback` defaults to 1 so the server permits
the feature without imposing it, and its state is visible in `matchsettings`
alongside the other `g_` rows, which is how a player discovers a server has
turned it off. It ships in Phase 5, alongside the stats widening it depends on.

**End-of-match summary.** `UpdateEndGameHud` (`StatManager.cpp:1237-1276`) is
commented out in its entirety, so clicking a player on the end-game summary does
nothing today; and as written it references `clientStat->weaponAccuracy[]`
(`:1251`) and `inGameAwards.Num()`, neither of which exists on the current
`rvPlayerStat` — it would not compile if uncommented. It is **rewritten** and
driven by the column table, not revived. `BuildSummaryListString`
(`MultiplayerGame.cpp:1878`, declared `MultiplayerGame.h:903`, called at `:1984`
and `:2030`) shows only rank, name, clan and up to three weapon icons with no
numbers; it is replaced. It is a member of `idMultiplayerGame` and is not in
`mp/stats/` — `StatManager.cpp` is 1345 lines long and has no line 1877, which is
where the draft filed it. `ShowStatSummary`, `UpdateSummaryBoard`,
`DrawStatSummary` and the
`sm_select_player` handler (`MultiplayerGame.cpp:5692`) are repointed at
`GAME_RELIABLE_MESSAGE_MATCHSTATS`, because retiring `_ALL_STATS` orphans all of
them.

**Export.** `mp/match/MatchLog.{h,cpp}` writes newline-delimited JSON under
`fs_savepath/<g_matchLogPath>/`, one file per match, with `schemaName`
(`openq4.match_stats`), `schemaVersion` and a per-match GUID stamped on every
event. Events: `MATCH_STARTED`, `PLAYER_CONNECT`, `PLAYER_DISCONNECT`,
`PLAYER_SWITCHTEAM`, `PLAYER_KILL`, `PLAYER_DEATH`, `ROUND_OVER`, `PLAYER_STATS`,
`MATCH_REPORT`. Field names mirror Quake Live's ZMQ vocabulary where the concept
matches, so qlstats- and quakestats-style tooling points at openQ4 with near-zero
work; openQ4's own gametypes get their own fields rather than being forced into
Quake Live's vocabulary. `MATCH_STARTED` and `MATCH_REPORT` carry
`si_matchPreset`, `si_matchRules` and the `mpMatchRoster`, so the ruleset and the
substitutions travel with the data. The final report is written
temp-then-rename. Nothing here is display text, so this is one of the very few
subsystems with no localization surface at all.

### 8.8 Scoreboard and HUD depth

#### The live bug, stated accurately

The draft got this partly wrong, and the corrected version is worse than the
draft's version, which is why it matters.

`scoreboard.gui`'s gametype dispatch branches on `4|5|6|7|8` (`:64`), `3`
(`:120`) and `1` (`:176`), with a final `else` (`:219-221`) that hides
`p_scoreboard` and shows the **Tourney bracket** panel. The value it tests is the
raw `gui::gametype` int that `MultiplayerGame.cpp:1466` sets directly from
`gameLocal.gameType`; there is no remapping layer, because `mpGameTypeInfo_t` has
no scoreboard-style column (its fifth and sixth columns are `entityFilter` and
`mapDeclKey`, `GameTypes.h:66-67`). The `.gui`'s own documentation block
(`:51-61`) enumerates only 0 through 8.

Gametype 2 (Tourney) legitimately lands in the `else`. So does **every one of
the eight gametypes the Quake Live port appended** — `GAME_DUEL` (9) through
`GAME_ATTACK_DEFEND` (16), `MultiplayerGame.h:45-52` (`:44` is the third line of
the APPEND ONLY comment). The consequences differ by
mode and both are broken:

- **The team modes among them** — Clan Arena, Freeze Tag, Red Rover, Attack &
  Defend — take `UpdateTeamScoreboard`, which writes
  `team_%i_scores_item_%i` (`:1820-1829`), while the Tourney panel's `listDef`s
  bind `scores` and `spectator_scores`, which are never written. **Those
  gametypes render a completely empty scoreboard.**
- **Duel is worse than the draft said.** `GAME_DUEL`'s flags are
  `GTF_DUEL | GTF_FRAGLIMIT` with no `GTF_TEAM` (`mp/GameTypes.cpp:63-64`), and
  `idGameLocal::IsTeamGame` is
  `( isMultiplayer && MPGameTypeHasAny( gameType, GTF_TEAM ) )`
  (`Game_local.h:1478-1479`) — not to be confused with its sibling
  `idGameLocal::IsTeamGameType()` at `Game_local.h:1019`, which tests the same
  flag **without** the `isMultiplayer` guard, so a fix that picks the wrong one
  changes behaviour outside multiplayer. Duel therefore routes to
  `UpdateDMScoreboard`. That
  function's inner chain is `if ( gameType == GAME_DM ) { ... } else if
  ( gameType == GAME_TOURNEY ) { ... }` with **no trailing else** (`:1501`,
  `:1550`, closing at `:1642`). Duel therefore falls through both branches and
  writes **no `scores_item_*` at all** — neither new rows nor the blanks the DM
  path writes at `:1525`, `:1546`, `:1634` and `:1639`. The draft said Duel
  renders "populated, but with the wrong columns". It renders *whatever was last
  written*, which is stale rows from a previous gametype or nothing.

Row shrinking works today for the modes that do write rows, and the mechanism is
worth recording because the fix must not break it: the game blanks unused keys
with `SetStateString( ..., "" )`, and `idListWindow::UpdateList`
(`openQ4/src/ui/ListWindow.cpp:772-784`) skips zero-length strings when building
`listItems` and breaks only when the state key is entirely **absent**. So
blanked-but-present keys compact rather than terminating the scan. Row heights
are separately driven by the `num_total_players` / `num_players` /
`num_spec_players` ints the game sets (`:1644-1646`, `:1835-1839`).

#### The fix

The data-driven column model rather than eight more literal branches: a
`columnSet` column is added to the gametype descriptor table, the server pushes a
`scoreboard_columnset` state key plus tab-delimited rows built from the stat
field table, and the `.gui` renders generically from one generous `listDef` per
named column set. Adding a gametype then never requires a new scoreboard layout.
`MPValidateColumnTable()` errors at init if a column's `statKey` does not resolve
in the stat field table, if a named column set references a field whose
`wireBits` is 0, or if a column header `#str_` id does not resolve.

`scoreBoard->SetStateInt( "gametype", gameLocal.gameType )` at `:1466` is
**kept**. `gameType_t` is the first byte of every gamestate packet and is
compared literally by `.gui` files, which is a project invariant; the key stays
and stays correct. What changes is that scoreboard *layout* stops branching on
it.

Named column sets: `duel` (head-to-head, per-weapon accuracy, item control),
`ffa`, `team` (damage dealt/taken, spread), `round` (alive count, eliminated
marker, round wins), `flag` (captures, defends, carrier icon), and **`tourney`**
(the multi-arena elimination bracket). In Phase 0 these sets contain only columns
whose data exists today — name, score, ping, time, ready, team score, alive count
— because the validator forbids naming a `wireBits 0` field; Phase 5 adds the
accuracy, damage and item-control columns in the same change that gives them a
wire width.

**`tourney` exists because Tourney's bracket panel is correct and must survive.**
The `else` branch at `scoreboard.gui:219-221` is broken for the eight appended
gametypes and *right* for `GAME_TOURNEY`, so replacing the chain wholesale would
delete a working view inside a phase titled "with no behaviour change" and fail
Phase 0 exit (c)'s "the four already-working ones must not regress". The
`p_tourney` panel is therefore **retained** and selected by
`columnSet == tourney`; only its selection stops being a fall-through.

**The `columnSet` column is filled for every `gameType_t` value, and the mapping
is written down here rather than left to the implementer.** `mpGameTypeInfo_t`
(`mp/GameTypes.h:61-69`) gains a seventh `const char *columnSet` member between
`mapDeclKey` and `flags`, and `MPValidateGameTypeTable()` errors if any row's
value does not name a declared set:

| `gameType_t` | Value | `columnSet` |
| --- | --- | --- |
| `GAME_SP` | 0 | `ffa` (never rendered; the table is dense and must be total) |
| `GAME_DM` | 1 | `ffa` |
| `GAME_TOURNEY` | 2 | `tourney` |
| `GAME_TDM` | 3 | `team` |
| `GAME_CTF` | 4 | `flag` |
| `GAME_1F_CTF` | 5 | `flag` |
| `GAME_ARENA_CTF` | 6 | `flag` |
| `GAME_ARENA_1F_CTF` | 7 | `flag` (marked "is not used" at `MultiplayerGame.h:36` and kept only so `GAME_DEADZONE` is not renumbered; the row still needs a legal value) |
| `GAME_DEADZONE` | 8 | `team` |
| `GAME_DUEL` | 9 | `duel` |
| `GAME_CA` | 10 | `round` |
| `GAME_FREEZETAG` | 11 | `round` |
| `GAME_REDROVER` | 12 | `round` |
| `GAME_OVERLOAD` | 13 | `team` |
| `GAME_HARVESTER` | 14 | `team` |
| `GAME_DOMINATION` | 15 | `team` |
| `GAME_ATTACK_DEFEND` | 16 | `round` |

All `NUM_GAME_TYPES` rows are present, which is what lets Phase 0 begin: the
draft's first deliverable was "add the `columnSet` column" with no statement of
what to put in it, and `GAME_SP` and `GAME_ARENA_1F_CTF` in particular have to
carry legal values or the validator errors on rows nobody thinks about.

Rows must **shrink** correctly. The blank-and-compact behaviour above works, but
it depends on the game writing a blank for every index up to `MAX_CLIENTS`, which
the Duel path demonstrably fails to do. The column writer instead uses
`DeleteStateVar` for indices past the live count, so the list terminates at the
first absent key and cannot show a stale row from a previous frame or a previous
gametype.

**Verification uses `g_testScoreboard`.** It already exists
(`SysCvar.cpp:618`, `CVAR_GAME | CVAR_INTEGER`, default `"0"`, extern at
`SysCvar.h:348`) and fabricates fake scoreboard rows client-side through eleven
sites in `MultiplayerGame.cpp` (gates `:1489`, `:1704`; RNG seed `:2064`; loop
bounds `:2067`, `:2078`, `:2093`; reported counts `:2118-2123`). A two-client
harness cannot meaningfully test a five-column team layout — Clan Arena with one
player per side proves nothing about column widths and nothing at all about the
shrink path — so Phase 0's **primary** verification is
`g_testScoreboard MAX_CLIENTS` (32) rendering all six column sets with synthetic
rows, then stepping the value down to prove `DeleteStateVar` shortens the list,
with the live two-client run as the secondary check. That requires extending the
cvar's reach from the DM and team paths to whichever column set is active, and
giving it 0..`MAX_CLIENTS` bounds it does not currently declare.

**The fake rows are injected server-side, into the column writer, and the phase
criterion has to say so.** Today `g_testScoreboard` is `CVAR_GAME |
CVAR_INTEGER`, un-replicated and un-archived, and drives eleven purely local
`scoreBoard->SetState*` sites — which was coherent while row construction was
client-side. This plan moves construction to the server (the pushed
`scoreboard_columnset` key plus tab-delimited rows built from the stat field
table), so a client-side `g_testScoreboard` could no longer affect a single row.
The fabrication therefore moves with the construction: the **server** appends the
synthetic rows to the pushed set, exactly as it would real ones, and the client
consumes them through the same path a real row takes. That is also the only
placement that exercises the serialized path §6's listen-server trap makes a
standing rule. Phase 0 exit (b) consequently runs `g_testScoreboard` **on the
dedicated server** and observes the result **on a client**, not "on one client".

#### New HUD state keys

Written by `UpdateHud`, rendered by new `oq4_*` windowDefs:

```
showpause, pausetext, pausetime, pauseowner, timeoutsown, timeoutsnme
showref, refname, presetname, presetdirty
warmupreason                        which condition is blocking the start
readydelay                          seconds left before g_readyDelayAction fires
aliveown, alivenme                  per-team alive counts
spread                              team score spread
showacc, acc_%d                     accuracy overlay
showtimers, timer_%d_icon, timer_%d_time
showhit, hit_%d_amount, hit_%d_age  hit feedback numbers
vote_desc, vote_yes, vote_no, vote_needed, vote_time, vote_canvote
draft_turn, draft_side, draft_time, draft_pool
scoreboard_columnset, scoreboard_headers
ready_%d                            per-player ready dot, not just a count
```

`warmupreason` is the single highest-value small addition: openQ4 currently
cannot tell a player whether warmup is blocked on player count, team balance or
readiness. It flashes for three seconds on change rather than nagging
permanently.

**Every displayed time is quantised to whole seconds server-side**, rounding up
for countdowns and down for elapsed, so the client and server cannot disagree on
the last second of a countdown. That kills the classic "my clock says 0:01, yours
says 0:00" argument at its source.

Announcer cues for pause, resume, timeout and vote events **alias onto stock
clips**, exactly as the Quake Live port established. `announcerSoundDefs[]` is
index-parallel with `announcerSound_t` with no compile-time check, retail Quake 4
ships no voice-overs for any of these events, and the stock-assets rule forbids
adding them. The validation test asserts the two array lengths agree.

Note for completeness, because the draft's Phase 1 exit criterion assumed
otherwise: openQ4 **does** already display the local player's held-powerup
remaining time. `idPlayer::UpdateHudPowerUps` writes `powerup%d_time` in whole
seconds rounded up (`Player.cpp:4025`, guarded at `:4018`, flags excluded at
`:4021-4022`), reached from `UpdateHudStats` (`:3858`) via `DrawHUD` (`:4365`),
and `DrawHUD` sets `_hud->SetStateBool( "mp", true )` at `:4297` so it is live in
multiplayer; the consuming windowDefs exist in stock assets
(`hud.gui:1931`, `:1935`; `hud_strogg.gui:187`). What does **not** exist is any
display of another player's powerup time or of any world item's respawn time,
which is what §8.9 adds.

### 8.9 Item timers, and the verdict on multiview

#### The deadline is derived, never stored

`idItem` stores no respawn deadline. `idItem::GiveToPlayer` reads a float
`respawn` in seconds from the spawnArgs (`Item.cpp:723-726`): `:723` reads the
per-gametype override key `respawn_<si_gameType>` whose own default is the
**-1.0 sentinel**, and `:724-726` falls back to plain `respawn`, which is where
the 5.0 default actually lives. It then posts `EV_RespawnItem` that far out, plus
an optional `EV_RespawnFx` half a second earlier (`:738-743`).

Two gates zero the duration before that post, and the registry must handle both:
`respawn` is forced to 0 in single player at `:730-731`, and in a buying mode
when `givenToPlayer != -1` at `:732-736`. In a DeadZone-style buying game
`EV_RespawnItem` is therefore **never posted at all**, so `TimeRemaining` returns
-1 for an item that is alive and will not come back on a timer. The derived
deadline's `-1` branch is thus the *normal* case there, not only the
already-present case, and the registry publishes no timer for such an item rather
than publishing a zero.

`Event_Respawn` (`:998`) just
un-hides and re-enables the trigger and stores no time; `CancelEvents(
&EV_RespawnItem )` at `:1026` prevents a double respawn. The member list at
`Item.h:88-110` contains no respawn field at all — the `time` and `droppedTime`
at `Item.h:152`/`:154` belong to `idItemPowerup` and are the powerup's hold
duration and drop expiry.

That is the whole reason the draft's design would have double-compensated. Its
`mpItemTimers` was to register a match-time deadline **alongside** the posted
event; `ShiftEventTimes` would shift the event and the stored value would also be
compared against a frozen `MatchTime()`, so on resume the timer would have been
wrong by the pause duration.

The item timer therefore stores nothing. Its wire value is computed at snapshot
send time as:

```cpp
int remaining = item->EventTimeRemaining( &EV_RespawnItem );   // -1 if not pending
// -1 means no timer for this item this frame: it is not registered in the block
// at all, rather than being registered with a zero deadline.
```

`remaining` is what goes on the wire, and §6's "game-state block budget"
paragraph is why: a 32-bit absolute match time does not fit in
`MAX_ENTITY_STATE_SIZE`, and overflowing that buffer is a `FatalError`, not a
warning. The field is bounded by `MAX_ITEM_RESPAWN_MSEC` and costs about 17 bits.

The consequence for the pause is that this value needs **no compensation at
all**, which is stronger than the draft's claim that two compensations cancel.
`idEvent::ShiftEventTimes` adds `gameLocal.msec` to the event's absolute time
every frozen frame while `gameLocal.time` advances by the same amount, so
`TimeRemaining` — the difference of the two — is constant through a pause by
construction. Outside a pause it decreases at one millisecond per millisecond,
exactly as a countdown should. No `MatchTime()` term appears anywhere in the item
timer, so the deadline is touched by exactly one mechanism and §8.2's invariant
holds without an argument about cancellation.

The client renders the countdown from `remaining` directly; it does not
reconstruct an absolute, so it also needs no pause state to display a frozen
timer correctly.

Deriving it requires the one accessor the codebase does not have. `idEvent::time`
is private (`Event.h:68`), `EventQueue` is a file-static (`Event.cpp:279`), and
the only query exposed is `EventIsPosted`, which returns `bool`
(`Class.cpp:657-658`). So `idEvent::TimeRemaining( const idClass *obj, const
idEventDef *evdef )` is added in `Event.cpp` beside `EventIsPosted`, with
`idClass::EventTimeRemaining` forwarding to it — one accessor, in the file that
already owns the queue, next to its existing sibling. It is the same file and
the same reason `ShiftEventTimes` lives there.

#### The registry and its cap

The registry is built once at map load and rebuilt by `MPResetWorldForMatch()`.
An item is timed if its classname appears in a compiled `mpTimedItemClasses[]`
table (mega health, red and yellow armour, and each powerup — not weapons, whose
timers are not what anyone means by item control) **and** its decl declares a
non-zero respawn for the active gametype. The class table gets an
`MPValidateTimedItemTable()` like every other table here.

`MAX_TIMED_ITEMS` is 32. The draft asserted that this "covers every stock Quake 4
multiplayer map's mega, armour and powerup set" and no phase checked it, which is
exactly the kind of claim a competitive player discovers mid-match. Two things
fix that:

- **Overflow is loud, not silent.** Registration keeps the first
  `MAX_TIMED_ITEMS` entries in spawn order and emits one `gameLocal.Warning`
  naming the map and the true count. A truncated timer set is a visible startup
  warning, never a quietly missing icon.
- **The figure is measured, not asserted.** Phase 6 loads every stock multiplayer
  map in each supported gametype with a temporary console print of the registry
  size, and the resulting table of map-to-count is recorded in this document. If
  any map exceeds 32, the constant is raised before the phase closes rather than
  after a dispute.

#### Policy

`si_itemTimers` is a three-state, server-authoritative, **votable** policy: 0 off,
1 spectators and coaches only, 2 everyone. It defaults to **0**. This is a rules
decision, not a display decision, and the two ends of the lineage disagree — CPMA
restricts timers to spectators and demos because timing is a skill; Quake Live
gives them to everyone and makes them votable because third-party overlays
existed anyway. Defaulting to off and offering all three puts the decision with
the server operator rather than with whoever implements it. Shipping
player-facing timers on by default would be a competitive regression dressed as a
feature.

The policy is enforced at **send time, per recipient** (§6). A client whose
viewer class the policy excludes receives `numTimedItems 0`, so editing
`hud_itemTimers` locally reveals nothing. A client-side filter would be a
trivially defeated cheat.

Presentation is a **numeric countdown over the item decl's own icon material** in
the existing HUD font. The CPMA and Quake Live wedge shaders do not exist in
retail Quake 4 and no new content is introduced.

#### Multiview

**It is not attempted, and the reason is a networking judgement rather than a
scheduling one** — see §2. What ships instead is the set of things casters
actually use multiview for: the sticky auto-follow modes, the team-vitals
overlay, the item timers, the accuracy overlay redirected to the followed player, and the
NDJSON event stream for overlays. That covers most of the use at a fraction of
the cost. If multiview is ever built, MVD-style multi-POV demos fall out of the
same machinery, which is the argument for doing both together or neither.

### 8.10 Autoaction

`ui_autoAction` is a space-separated token string — `ss`, `stats`, `playing` —
with `si_autoAction` forcing it server-side. Token strings extend without a new
cvar; a bitmask does not, and Quake Live's vote bitmask typo is the standing
demonstration of why.

The server drives it from the authoritative `COUNTDOWN` to `GAMEON` and `GAMEON`
to `GAMEREVIEW` edges rather than leaving it to the client's own guess, so a
late joiner is covered and there is no dead warmup at the front.
`MPBuildMatchBasename()` is the single filename generator —
`Name-vs-Name-map-YYYY_MM_DD-HH_MM_SS` for Duel,
`Team-gametype-player-map-timestamp` otherwise, with every unsafe character
replaced — so a match produces one consistently named pair. The shared basename
is the detail players actually praise about CPMA's implementation.

Screenshot uses `renderSystem->CaptureRenderToFile`; stats writes through the
match log. Filenames pushed to a client are sanitised server-side against path
traversal. `si_autoAction` forcing a client to write files to disk is announced
in the HUD, not silent.

There is no `demo` token. See §2.

### 8.11 Cosmetic settings parity and anti-abuse

The honest framing is **cosmetic settings parity**, not anti-cheat and not
network parity: making sure two players in the same match see the same game.
Network-side parity (`net_clientPrediction`, rate) is excluded and the reason is
in §2; saying "settings parity" without that qualifier, as the draft did, would
have implied a great deal more than this section delivers.

The precedent is `si_allowHitscanTint` (`SysCvar.cpp:75`), and its shape is
specific: the value is read out of `gameLocal.serverInfo` at the point of use
(`Player.cpp:14633`, `:14646`), not through the `idCVar` object.
`gameLocal.serverInfo` is populated on clients as well as the server, so the same
shape works for a policy the client must apply.

**`si_forceModels`** (0 player choice / 1 forbid client model forcing / 2 force
one model per team) has to suppress three *archived* client cvars —
`g_forceModel`, `g_forceStroggModel`, `g_forceMarineModel` (`SysCvar.cpp:201-203`,
`CVAR_GAME | CVAR_ARCHIVE`) — **without destroying the player's saved values**.
It does that at the single existing choke point: `Player_ForcedModelCVarString`
(`Player.cpp:174`), the accessor every read goes through, returns the empty
string when `gameLocal.serverInfo.GetInt( "si_forceModels" ) >= 1`.

**The gate goes inside the accessor's body, not at any one call site**, and the
distinction matters because there are **six** call sites, not one. All six are in
`idPlayer::UpdateModelSetup` (`Player.cpp:3347`): the team branch reads
`g_forceMarineModel` at `:3360`/`:3361` and `g_forceStroggModel` at
`:3362`/`:3363`, and the non-team branch reads `g_forceModel` at `:3371`/`:3372`.
The draft cited `:3371` alone and called it "the single existing choke point",
which is true of the accessor and false of the citation. One edit inside the
accessor covers all three cvars and all six reads.

The cvars keep their values and a player who disconnects finds their
configuration intact. At `si_forceModels 2` the same accessor returns the
server's per-team model instead of the empty string, so there is still exactly
one decision site.

**But the existing `IsModified()` poll does not fire on a serverInfo change, so
the enforcement module must drive the reapply itself.** The poll lives in
`idMultiplayerGame::CommonRun` (`MultiplayerGame.cpp:3837`) at `:4006-4019`
(`g_forceModel` under `!IsTeamGame()`, `g_forceMarineModel` and
`g_forceStroggModel` under `IsTeamGame()`), feeding the `updateModels` respawn
loop at `:4021-4028`, and again at `:4031` for `g_simpleItems` with its
reassignment loop running to `:4098`. Every one of those flags is set **only when
the client's own cvar is written**. An `si_forceModels` or `si_allowSimpleItems`
change arriving from the server sets no `IsModified()` flag on any of them, so
nothing calls `UpdateModelSetup()` and nothing reassigns `item->simpleItem`; the
new policy would take effect only when the player next edited their own cvar or
the entity respawned. Saying the poll "continues to work unchanged" is precisely
the bug.

So `mp/Enforcement` caches the last-seen `si_forceModels` and
`si_allowSimpleItems` values and, on a change, runs the **same** two loops the
`IsModified()` path runs — the `updateModels` loop at `MultiplayerGame.cpp:4021-4028`
and the `g_simpleItems` reassignment loop at `:4031-4098` — so there is one
implementation of "reapply the model policy" reached by two triggers rather than
two implementations. Phase 7 exit (e) tests the live flip.

**`si_allowSimpleItems`** gates `g_simpleItems` (`SysCvar.cpp:537`) the same way,
at its single read site (`Item.cpp:515`), with the same serverInfo-change
trigger.

**`si_maxFov`** clamps `g_fov` (`SysCvar.cpp:556`), which is worth naming
precisely because the draft never did. `g_fov` is `CVAR_GAME | CVAR_FLOAT |
PC_CVAR_ARCHIVE` with **no declared min or max** and an **empty description
string**; the only bound anywhere is imperative and multiplayer-only, inside
`idPlayer::DefaultFov`, which returns 90 below 90 and 175 above 175
(`Player.cpp:11040-11045`). `si_maxFov` extends exactly that clamp:

```cpp
// idPlayer::DefaultFov, multiplayer branch
float ceiling = 175.0f;
int   maxFov  = gameLocal.serverInfo.GetInt( "si_maxFov" );
if ( maxFov > 0 ) {
    // clamp the ceiling into [90, 175] first: si_maxFov is declared 0..130 because
    // idCVar cannot express "0 or 90..130", so a stale or hand-edited value in
    // 1..89 must not be allowed to drive ceiling below the 90 floor and invert
    // the ClampFloat below into min > max.
    ceiling = idMath::ClampFloat( 90.0f, 175.0f, (float)maxFov );
}
return idMath::ClampFloat( 90.0f, ceiling, fov );
```

The set-time `Warning()` and init-time clamp in §4 exist so an operator learns
about an out-of-band value; this second clamp exists so the read path is correct
even if they never do. Both are cheap, and only having one of them is how the
draft ended up specifying a clamp that drove every client **below** the floor
retail has enforced since `idPlayer::DefaultFov` was written.

**The clamp is at read, never a write-back.** The archived cvar is never
force-set, so a client at `g_fov 110` on an `si_maxFov 100` server still has
`g_fov 110` after disconnecting — Phase 7 tests exactly that. `si_maxFov`
defaults to 0, meaning no ceiling, because a default of 110 would silently clamp
every existing player running wider on a server that changed nothing. The empty
description on `g_fov` is filled in as a drive-by. Two other consumers read
`g_fov` unclamped — `idCamera` (`Camera.cpp:2202`) and `rvTarget_SetFOV` — and
are deliberately left alone: both are cinematic paths that do not run in a
multiplayer match, and the fact that they were checked is recorded here so a
later reader does not have to re-check them.

**Anti-abuse.** Chat and command flood token buckets (`g_chatFloodMsec` /
`g_chatFloodBurst` / `g_cmdFloodMsec`), all defaulting to off, all measured in
engine time so a pause grants no free spam, and all exempting referees.
`g_inactivity` moves an idle player to spectator through the same path
`g_readyDelayAction 1` uses. `g_allowKillMsec` throttles self-kills, which
matters now that Clan Arena and Freeze Tag have landed and suiciding is a
tactic. Referee auth attempts are rate-limited and locked out per map.

One shared per-client cooldown slot throttles every command that produces global
output, which is crude but has the virtue that a caller cannot round-robin
between commands to defeat it.

### 8.12 Chat location macros

`%h` health, `%a` armour, `%w` current weapon and ammo, `%l` location, `%n`
nearest visible team mate, `%i` last item picked up, `%%` a literal percent.

`%l` is derived from the nearest significant item spawn in the player's PVS —
weapon, armour, powerup or mega health, *whether or not the item is currently
present* — prefixed "upper" or "lower" when another instance of the same item
exists at a different height. It therefore needs no `.loc` file and no new
content, and the item name comes from the item decl's own `#str_` display name.
`%n` requires a real line-of-sight trace; without it the macro is a wallhack.

Expansion is single-pass with an advancing write cursor so a macro cannot expand
into another macro, aborts the whole expansion on overflow, matches
longest-token-first, and is applied only for players on a team. It lands with the
team-management phase because it is a team-communication feature, not a chat
feature.

---

## 9. Phased roadmap

### The standing gate

Every phase ends with: Windows Meson wrapper build clean via
`tools/build/meson_setup.ps1`; `python tools/validation/openq4_validate.py
--profile push` green; `python tools/tests/competitive_match_layer.py` prints
`ok`; a dedicated-server load of the affected gametypes reaching
`Dedicated map ready` with no new warnings in `openq4.log`; **no unresolved
`#str_` ids on either client**, meaning both the static scan and the four table
validators of §7; and **the diff-scope check passes — no file under
`openQ4-game/src/game/` appears in the change set**.

Every multi-client criterion is exercised on the two-instance harness — a
dedicated server plus two clients, each with its own `fs_savepath`,
`win_allowMultipleInstances 1`, and `ui_joined 1` / `ui_spectate Play` to leave
spectator — never on a listen server alone, because
`LocalClientSendReliableMessage` never serializes the host's messages. `+set` on
the command line does not reach `CVAR_GAME` cvars, so every phase's configuration
is done through an exec'd `.cfg` or the console. Never `+devmap` an `mp/` map in
single player.

### Module scope, per phase

**Every phase is `openQ4-game/src/mpgame/`-only on the game side.** No phase
edits `openQ4-game/src/game/`. Each phase additionally touches the `openQ4`
repository under `content/baseoq4/`, `tools/` and `docs/` as listed in §3. This
is restated per phase below rather than assumed, because it is the single
largest thing the draft left ambiguous.

### Phase 0 — Scoreboard columns, the stat field table and the match clock, with no behaviour change

**Module scope.** `openQ4-game/src/mpgame/` only; plus `scoreboard.gui`,
`mphud.gui`, the four `.lang` mirrors, and the new validation test in `openQ4`.

**Scope.** Three things that must precede everything and are independently
valuable.

First, fix the live bug. Add the `columnSet` column to the gametype descriptor
table (`mpGameTypeInfo_t`, `mp/GameTypes.h:61-69`) and fill it for **every**
`gameType_t` row from the table §8.8 now carries, `GAME_SP` and
`GAME_ARENA_1F_CTF` included. Land `mp/match/MatchScoreboard.{h,cpp}` with
`MPValidateColumnTable()`, push `scoreboard_columnset` and `scoreboard_headers`,
and replace the literal branch chains in `scoreboard.gui` and `mphud.gui` with
generic rendering — **retaining `p_tourney`** and selecting it by
`columnSet == tourney`, so the one branch that is correct today is preserved
rather than deleted inside a phase titled "with no behaviour change". Fix the
row-shrink path (`DeleteStateVar`, not blanking) and the Duel fall-through in
`UpdateDMScoreboard`. Move `g_testScoreboard`'s fake-row fabrication to the
**server** side of the new column writer (§8.8), extend it to drive the active
column set, and give it 0..`MAX_CLIENTS` bounds.

Second, land the **`mpStatFieldInfo_t` table** with `wireBits 0` for every field
not yet on the wire, and `MPValidateStatFieldTable()`. This is what makes
`MPValidateColumnTable()` non-circular: the column validator resolves `statKey`
against it, and additionally errors if a named column set references a
`wireBits 0` field. Phase 0's column sets are therefore limited to data that
exists today — name, score, ping, time, ready, team score, alive count — and
Phase 5 adds the rest in the change that gives them widths. The draft had the
column validator in Phase 0 and the table it validates against in Phase 5.

Third, introduce `idMultiplayerGame::MatchTime()` and `mpMatchState` with the
pause fields present but permanently zero, and convert every match deadline in
§8.2's ownership table to store and compare in match time. With `pausedMsecTotal`
pinned at 0, `MatchTime() == gameLocal.time` and behaviour is bit-identical. This
lands the audit as a reviewable, testable diff with no functional risk, instead of
hiding it inside the pause feature where a regression would be indistinguishable
from a pause bug. The ownership table's *(recon)* rows are confirmed here and the
table is corrected in place if any is wrong.

Also lands: `GAME_RELIABLE_MESSAGE_MATCHSTATE` with its three dispatch cases; the
`#str_41410`-`#str_41999` band declaration as a `// section` comment in all four
`.lang` mirrors; `tools/tests/competitive_match_layer.py` with its registration
in the runner and both workflows, including the diff-scope check and the
"nothing else uses 41410-41999" pin; server-side second quantisation of every
displayed time.

Also lands here rather than in Phase 1: **`idEvent::DebugDumpQueue` and the
`debugMatchTime` console command** (§5). Both are pure reads with no dependency on
the pause, and exit (d) below is the criterion that most needs real measurement —
it is where the entire deadline-ownership audit is confirmed. Deferring the
instrumentation to Phase 1, as the draft did, left Phase 0's audit resting on a
stopwatch.

**Dependencies.** None.

**Exit.**

(a) Dedicated server loads on stock maps in DM (q4dm1), Tourney (q4dm1), Team DM
(q4dm4), CTF (q4ctf1), Duel (q4dm1), Clan Arena (q4dm1), Freeze Tag (q4dm2), Red
Rover (q4dm3) and One Flag CTF (q4ctf1) all reach `Dedicated map ready`.

(b) **Primary scoreboard verification, using `g_testScoreboard` set on the
dedicated server and observed on a client.** The fake rows are fabricated
server-side inside the column writer (§8.8), so the cvar is set on the server and
the result is read on a connected client — which also exercises the serialized
path a listen server would bypass. With `g_testScoreboard MAX_CLIENTS` (32) in
each of the nine gametypes, all six column sets render with 32 synthetic rows,
correct localized headers and no clipped or overlapping columns. Stepping the
value 32 to 16 to 8 to 3 to 0 shortens the list each time with no stale row
surviving — the check the two-client harness structurally cannot make, and the
one that proves the `DeleteStateVar` fix.

(c) **Secondary scoreboard verification, on the two-instance harness.** The
scoreboard renders with populated rows and correct headers in all nine gametypes:
the four already-working ones must not regress and the five broken ones must now
populate. Tourney must still show its bracket panel, now selected by
`columnSet == tourney` rather than by fall-through. Duel in particular must show
its own rows rather than the stale rows the current fall-through leaves. The
scoreboard shrinks when a client disconnects.

(d) **The match-time conversion is verified by instrumentation, not by
stopwatch.** With `pausedMsecTotal` pinned at zero, `debugMatchTime` prints
`MatchTime()` and `gameLocal.time` as **equal on every frame sampled**, and
prints each converted deadline from §8.2's ownership table alongside its
pre-change absolute value; the two must be **bit-identical**, not merely close.
Sampled in DM, Team DM and Clan Arena, across a countdown, a frag-limit delay, a
respawn and an overtime entry. The on-screen clocks reaching 1 then 0 identically
on both instances is a secondary confirmation, not the test — "agree within one
frame" is roughly 16 ms and there is no way for a human with two builds and a
stopwatch to establish that on a HUD clock, which is why the draft's version of
this criterion could not be performed.

(e) Deliberately setting a column set to name a `wireBits 0` field makes
`MPValidateColumnTable()` fail at game init with a message naming the column and
the field.

(f) Validation sweep green, including the diff-scope check.

### Phase 1 — The pause primitive

**Module scope.** `openQ4-game/src/mpgame/` only. Specifically
`gamesys/Event.{h,cpp}`, `gamesys/Class.{h,cpp}`, `Entity.{h,cpp}`,
`anim/Anim.h` + `anim/Anim_Blend.cpp`, `Player.{h,cpp}`, `Weapon.{h,cpp}`,
`Item.{h,cpp}`, `Game_local.{h,cpp}`, `Game_network.cpp` and `mp/match/`. The
`mpgame` copies of these files are divergent forks of their `src/game/`
namesakes and the `src/game/` copies are not edited, so no dead virtual and no
dead static appears in the single-player module.

**Scope.** `idEvent::ShiftEventTimes` and `idEvent::TimeRemaining` in
`gamesys/Event.cpp` (`DebugDumpQueue` and `debugMatchTime` already landed in
Phase 0); `idClass::EventTimeRemaining`; `idEntity::ShiftFrozenTime` with its
non-empty default and the `idAnimator` and `idItem` pieces;
`idPlayer::ShiftFrozenDeadlines` and its `rvWeapon` delegate;
`idEntity::PausesWithMatch`; the head-of-`RunFrame` pass and the gate in all
three `RunFrame` entity-loop variants, plus the separately shaped
`isNewFrame`-guarded mirror in `ClientPrediction` and the local player's own edit
at `Game_network.cpp:2568`; the frozen pmove; `pausedMsecTotal` begins
accumulating; the `MSG_MATCH_PAUSE*` tags; the hoist list.

**No new physics virtual.** `idPhysics_Parametric::UpdateTime` is used as-is;
`physics/` is not edited. The gate calls `ShiftFrozenTime` and nothing else, and
`ShiftFrozenTime`'s default calls `UpdateTime` exactly once — the single writer
of `current.time` on a frozen entity. `competitive_match_layer.py` pins **two**
token sequences — the server gate and the `ClientPrediction` mirror — plus the
ordered head-of-`RunFrame` sequence `ShiftEventTimes` -> `ShiftFrozenDeadlines`
-> entity loop -> `ServiceEvents`, in each case including the absence of any
second `UpdateTime` call.

**This phase has no command table, and says so rather than borrowing one.** The
draft's scope ended with "`MCF_WHILEPAUSED` on the command table rows that need
it" and named `ref pause` / `ref unpause` as its entry points, but
`mp/match/MatchCommands.{h,cpp}`, the `MCF_*` flags, `mpAuthority_t`,
`MPValidateMatchCommandTable()`, `MPResolveAuthority`, `MatchDispatch`, the `ref`
command and `g_refPassword` are **all Phase 2**, whose own dependency is Phase 1.
That is the same circularity the Phase 0 / Phase 5 stat-table fix removed, one
phase over. It is resolved by shrinking Phase 1 rather than by pulling Phase 2
forward:

- The two entry points are **`mp_pause` and `mp_unpause`**, two temporary
  `CMD_FL_GAME` console commands registered in `gamesys/SysCmds.cpp`, each
  guarded at runtime in the `ForceReady_f` shape
  (`MultiplayerGame.cpp:7130-7135` — refuse when
  `!gameLocal.isMultiplayer || gameLocal.isClient`), so they are effectively
  `MPA_CONSOLE`/listen-host only. They are **replaced by table rows in Phase 2**
  and unregistered in the same change; §5's permanent surface never contains
  them.
- `MCF_WHILEPAUSED` and the `ref pause` / `ref unpause` spellings move to
  **Phase 2**. The hoist list still lands here as a documented property of the
  freeze; what lands in Phase 2 is its expression as a table column.
- The Tourney exclusion is likewise a runtime refusal inside `mp_pause` in this
  phase, using a `#str_` id from the 41410-41449 sub-band, and becomes an `MCF_`
  gate on the row in Phase 2.

The pause primitive is therefore proved through a deliberately minimal, temporary
dispatch that the document designs, rather than through a "second dispatch path"
that Phase 2's dependency line concedes exists but that nothing specifies.

**Dependencies.** Phase 0, and Phase 0 only.

**Exit.** Two-instance harness on q4dm1 in Duel, `mp_pause` issued from the
server console or the listen host, a real remote client:

(a) `mp_pause` freezes both clients: neither player can move or fire, both HUD
clocks stop, and a rocket in flight stops in mid-air on both screens.

(b) View angles still turn while paused, and chat sent from either side is
delivered. `mp_pause` and `mp_unpause` themselves remain usable while frozen.
Nothing here tests `players`, `matchsettings` or referee commands — those are
registered in Phase 2 and do not exist in this build; Phase 2 exit (b) tests
them.

(c) The remote client is **not dropped** by a five-minute pause, confirming
`CheckClientTimeouts` is unaffected — this is the specific failure mode any
clock-stalling approach produces and it must be shown not to occur.

(d) **Deadline preservation, measured by instrumentation rather than by
stopwatch.** The draft asked an observer to watch a mega-health countdown and a
quad timer on screen; item respawn countdowns do not exist until Phase 6, so
that criterion could not be performed in this build. It is replaced by two
instrumented reads:

  - `debugMatchTime 32` — the command Phase 0 already registered — runs
    `idEvent::DebugDumpQueue( 32 )` and prints the next 32 queued events with
    their object, their event def and their **remaining** delay. Sample it
    immediately before `mp_pause`, again 60 seconds into the pause, and again
    immediately after `mp_unpause`. Every remaining delay must be unchanged
    across all three samples, to the frame.
  - The same command prints `inventory.powerupEndTime[]` minus `gameLocal.time`
    for every connected player. A held quad's remaining milliseconds must be
    unchanged across the same three samples.

  As a secondary on-screen check only, the local player's held-powerup countdown
  **is** already displayed (`powerup%d_time`, `Player.cpp:4025`) and must agree
  with the instrumented figure. Wall-clock observation of a screen element is
  not the test; it is the confirmation that the instrumentation matches what a
  player sees.

(e) **Non-event state preservation, measured.** Stand a player on a moving lift
and pause mid-travel; on resume the lift continues from where it stopped and does
not snap to where it would have been. Repeat with a door mid-swing and with a
player mid-animation. This is the observation that proves `ShiftFrozenTime` is
correct, and it is the check that the naive "just skip `Think()`" design fails.

(f) Match clock, round clock and overtime accumulator resume from where they
stopped.

(g) Repeat (a) through (f) in Clan Arena to exercise the round layer's deadlines.

(h) Log inspection after a five-minute paused match shows no reliable-channel
warnings — two MATCHSTATE sends per pause, not one per frame.

(i) `mp_pause` in Tourney is refused with a localized message drawn from the
41410-41449 sub-band. (The refusal becomes an `MCF_NOTOURNEY` gate on the table
row in Phase 2; in this phase it is a runtime check inside the temporary
command, because no table exists yet.)

(j) **The single-player module is untouched.** Verified by the diff-scope check
in `competitive_match_layer.py`, not by playing a campaign map. The draft's
criterion — "single-player campaign map plays through a save/load cycle
unchanged" — was vacuous once the module scope is stated, because no phase edits
the tree that builds `game_sp` and `Common.cpp:5213` never loads `game_sp` for a
multiplayer gametype. A static scope check is both stronger and cheaper than a
play session that could not have failed.

(k) Validation sweep green.

### Phase 2 — Authority, the command table and the referee page

**Module scope.** `openQ4-game/src/mpgame/mp/match/`, `MultiplayerGame.{h,cpp}`,
`Game_network.cpp`, `gamesys/SysCmds.cpp`, `gamesys/SysCvar.{h,cpp}`; plus
`mpmain.gui` and the `.lang` mirrors in `openQ4`.

**Scope.** `mp/match/MatchCommands.{h,cpp}`, `MatchAuthority.{h,cpp}`,
`MatchDispatch.{h,cpp}`. `MPValidateMatchCommandTable()` erroring at init,
including the `#str_` resolution pass of §7 and the console-command collision
check. `GAME_RELIABLE_MESSAGE_MATCHCMD` and `_MATCHAUTH` with full server-side
re-validation. `g_refPassword` login with attempt counting and lockout, `refMask`
replication with the `connectionToken` guard, the `(R)` marker, and the announce
on grant and resign. `ref` help and `commands` generated from the table and
filtered to the caller's authority. `g_adminLog`.

**The referee GUI page**, replacing the rcon-proxy admin tab in the same change.
Not a later phase, because deleting a working user-facing surface and shipping
the gap is what the draft did.

The referee-exclusive rows land here: `pause`, `unpause`, `abort`, `allready`
(promoted, §5), `unreadyall`, `kick`, `mute`, `unmute`, `setScore`,
`setTeamScore`, `setMatchTime`, `say`, `cointoss`, `putTeam`, `remove` — together
with the `MCF_*` flag set including `MCF_WHILEPAUSED` and `MCF_EXISTINGCMD`, and
the `MCF_NOTOURNEY` gate on `pause`. **Phase 1's temporary `mp_pause` and
`mp_unpause` console commands are unregistered in this same change**, replaced by
the `pause` and `unpause` rows reached through `ref`; they never appear in §5's
permanent surface. Votable
rows are declared with `MCF_VOTABLE` but their vote front-end is Phase 3; a
referee can already execute them directly, which is how the shared-table claim
gets proved *before* the vote system exists to double-implement it.

Retires the rcon-proxy admin GUI path and `HandleServerAdminCommands`'
hand-written gametype switch. Widens the centre-print channel to three parameters
plus `CPARM_TIME` and `CPARM_STR`. Registers `players` and `matchsettings`.
Relocates `g_spectatorChat` and drops its `CVAR_ARCHIVE` flag. Deletes the dead
`g_announcerDelay`.

**Dependencies.** Phase 1, whose temporary `mp_pause` / `mp_unpause` commands
this phase retires in favour of table rows, so exactly one dispatch path survives
the pair.

**Exit.** Two-instance harness:

(a) `ref <wrong password>` is refused and appears in the admin log; the correct
password grants, is announced to both clients, and shows `(R)` on both
scoreboards and in `players`.

(b) Every referee-exclusive command executes from the **remote** client and is
refused with a localized message when run by a non-referee — verified for at least
`kick`, `abort`, `allready`, `setTeamScore` and `pause`.

(c) A client that fabricates a `GAME_RELIABLE_MESSAGE_MATCHCMD` payload without
having logged in is rejected server-side; tested by temporarily removing the
client-side gate in a scratch build.

(d) `ref abort` during a live match returns both clients to `WARMUP` with ready
cleared.

(e) `ref` with no arguments lists a strictly larger set for a referee than for a
player, and the server console lists more than either.

(f) `ref <typo>` prints a usage error and a logged-in referee **remains** a
referee.

(g) Deliberately breaking one table row makes `MPValidateMatchCommandTable()`
fail at game init with a message naming the row. The enumerated failures are:
wrong index; missing `#str_` id; an alias duplicated across two rows;
`MCF_WARMUPONLY | MCF_LIVEONLY` both set; an `MCF_VOTABLE` row with no
`voteDescId`; and a name colliding with a console command **this layer does not
own** — a scratch row named `serverForceReady` is the canonical case. Rows whose
own registration is this layer's handler are *not* failures, which is why the
shipped table (where nearly every row is also a registered command) passes; and
`allready`, `kick`, `say` and `mute` are legal because they carry
`MCF_EXISTINGCMD` and their apply functions match their existing registrations.

(h) `g_refPassword` empty disables the whole system including the login command,
and the referee page's login returns the *no referee system on this server*
refusal rather than the *incorrect password* one, without incrementing the
attempt counter.

(i) `g_refAuthAttempts` failures lock the client out for `g_refLockoutTime`.

(j) A referee disconnects and a second client connects into the freed slot; the
newcomer is **not** a referee.

(k) **The referee page works from the remote client.** A referee logs in through
the page and executes `pause`, `abort`, `putTeam` and `kick` from it, with the
roster picker showing correct names and slots and the action list containing no
row the caller's authority forbids. This is the criterion that proves the rcon
proxy was replaced rather than removed.

(l) `allready` typed by a remote referee forces everyone ready and
`serverForceReady` still works from the server console, neither shadowing the
other. The validator rule behind that is tested directly rather than restated: a
scratch row named `serverForceReady`, **or** a second row named `allready` whose
apply function is not `idMultiplayerGame::ForceReady_f`, makes
`MPValidateMatchCommandTable()` error at init; the shipped `allready` row, whose
apply function *is* `ForceReady_f`, does not.

(m) Validation sweep green, including the pin that every `MCF_VOTABLE` row has a
`voteDescId` and that every `#str_` id on the table resolves.

### Phase 3 — The unified vote system, the map pool and the map draft

**Module scope.** `openQ4-game/src/mpgame/mp/match/`, `MultiplayerGame.{h,cpp}`,
`Game_network.cpp`, `gamesys/SysCvar.{h,cpp}`, `gamesys/SysCmds.cpp`; plus
`mpmain.gui` and the `.lang` mirrors in `openQ4`.

**Scope.** `mp/match/MatchVote.{h,cpp}` over the Phase 2 table.
`GAME_RELIABLE_MESSAGE_VOTESTATE`. All gates. `callvote` / `cv` /
`callvote ?` / `callvote <setting> ?` / `vote`. `ref passVote` /
`ref cancelVote`. The vote HUD banner. Removal of the legacy single-field path and
repointing of the `mpmain.gui` vote tab. The `si_voteFlags` help-text correction
and the coexistence warning.

`mp/match/MatchMaps.{h,cpp}`: `g_mapPool` with its `SendMapList` filter, its
server-side validation of `callvote map` and `ref map`, its set-time warning for
an unresolvable entry, and the `maplist` command. The `g_mapDraft` ban/pick
sequence with `ref draft start|cancel|status` and `veto`/`pick`, default off.

**Dependencies.** Phase 2.

**Exit.** Two-instance harness, Team DM on q4dm4 with `si_allowVoting 1`:

(a) `callvote` with no args lists exactly the settings `g_voteAllow` permits, with
usage and current values, all localized.

(b) `cv tl 15` resolves through the alias; `callvote timelimit ?` prints the range
and the current value.

(c) A 2-player vote passes on 2-0 **immediately** rather than after the full
timeout, and fails immediately on 0-2.

(d) A player leaving mid-ballot changes the denominator and can flip the outcome;
verified by disconnecting the second instance mid-vote.

(e) Yes/No are ignored for `g_voteArmDelay` seconds after the ballot opens.

(f) `g_voteLimit`, `g_voteCooldown` and `g_voteDelay` each refuse with a
distinct localized message.

(g) Removing a setting from `g_voteAllow` removes it from `callvote ?` **in the
same frame** and refuses the vote; an unrecognised token in `g_voteAllow` produces
a `Warning()`.

(h) `g_voteAllowMidMatch 0` refuses every vote except `restart` and `referee`
during `GAMEON`.

(i) `ref passVote` forces a losing ballot through after `g_voteExecDelay`;
`ref cancelVote` kills it instantly.

(j) The banner's yes/needed/no figures match the figures that actually decide the
ballot.

(k) The in-game vote menu in `mpmain.gui` calls, displays and resolves a vote.

(l) A grep of `MultiplayerGame.cpp` finds no `GetLocalizedString` on any
server-side vote transmission path and none of the three previously hardcoded
English strings — pinned by the validation test.

(m) **Map pool.** With `g_mapPool` set to three maps, `maplist` prints those
three, the vote menu offers only those three, and a fabricated
`callvote map <map outside the pool>` sent from a scratch build with the
client-side filter removed is refused server-side with a localized message. With
`g_mapPool` empty, everything behaves exactly as before the phase.

(n) **Map draft.** With `g_mapDraft 1` and a five-map pool, `ref draft start`
runs an alternating ban sequence to a single surviving map, announces each turn
with the map name through the widened centre print, pushes the shrinking pool to
both clients, and sets the next map. `ref draft cancel` abandons it cleanly. A
pause during a draft suspends the turn clock. With `g_mapDraft 0` every draft
command is refused and the feature is invisible.

### Phase 4 — Timeouts, team management, the roster and match start

**Module scope.** `openQ4-game/src/mpgame/mp/match/`, `mp/ChatMacros.{h,cpp}`,
`MultiplayerGame.{h,cpp}`, `Player.{h,cpp}`, `gamesys/SysCvar.{h,cpp}`,
`gamesys/SysCmds.cpp`; plus `mphud.gui` and the `.lang` mirrors in `openQ4`.

**Dependencies. Phases 1 and 2.** The draft made this phase depend on Phase 3 as
well, with no stated reason, which put the flagship feature — the timeout this
document exists to discharge — fourth in line behind a vote rewrite it does not
use. Timeouts, budgets, team locks, captains, the roster, the ready anti-stall,
the world reset and the chat macros need the pause primitive (Phase 1) and the
command table plus authority tier (Phase 2), and nothing else. `callvote
timeout`-shaped rows light up automatically when Phase 3 lands, because the
shared table gives that for free — which is the plan's own argument for the
shared table. **Phases 3 and 4 may therefore proceed in either order.**

**Scope.** Policy on the Phase 1 primitive: `g_timeoutLength`, `g_timeoutCount`
per team (per player in Duel), `timeout` / `timein`, caller-or-referee resume with
the `connectionToken` identity, coach timeout rules, auto-expiry with the
`g_timeoutWarnTime` warning, a referee pause absorbing and locking a player
timeout, `g_pauseOnDisconnect`.

Team management: locks, spec-locks and spectator invites enforced at every chase
point; captains with auto-assign and auto-reassign; invite/accept re-validated at
accept time and cleared at every match-state boundary; `putTeam`, `removePlayer`,
`teamName`, `teamready`; `g_lateJoin`; score-weighted shuffle; `speconly` and
`specdefer`; the `EndmatchGraceScope` guard; chat location macros.

New in this phase relative to the draft: the **`mpMatchRoster`** on
`mpMatchState`; the **ready anti-stall** (`g_readyDelay`, `g_readyDelayAction`);
**`MPResetWorldForMatch()`** at the `COUNTDOWN` to `GAMEON` edge; and the
**`IMPULSE_17` ready-transport fix** (§8.5).

HUD: timeout budget per team, pause owner, per-player ready dots, ready-delay
countdown, alive counts, spread, `warmupreason`.

**Exit.** Two-instance harness (plus a third spectating instance where the
harness permits):

(a) A player timeout decrements the correct budget, is announced with the caller's
name and the duration through the widened centre print, and is refused when the
budget is exhausted.

(b) In team modes the budget is shared: a second team member can call `timein`.

(c) A referee pause taken during a player timeout leaves the original caller
unable to resume.

(d) **The alternating-callers loophole is closed** — during `MPS_RESUMING` a
second player cannot open a fresh timeout. This is a real griefing vector present
in OpenTDM and its absence must be shown, not assumed.

(e) The timeout caller disconnecting does not strand the pause: it auto-resumes at
its deadline and a referee can resume immediately.

(f) `g_pauseOnDisconnect` pauses when the remote instance is killed and resumes
when **that same connection token** reconnects.

(g) **Roster.** A player disconnected mid-match and reconnecting lands on their
original team with their score intact. A *different* player taking the freed slot
lands in spectator, does not resume the pause, and does not inherit the score.
A mid-match join that would take a team over its `matchStartTeamSize` is refused.

(h) A locked team refuses a join and accepts an invited player; the invite is
refused if the inviter has since lost captaincy or the team is at its
match-start size.

(i) A spec-locked team cannot be followed by an uninvited spectator, and with both
teams locked the spectator is on the overhead camera, not free-flying inside the
area.

(j) `teamName "Blue Ravens"` renders on both scoreboards and is rejected for a
name containing a quote or a colour code.

(k) `teamready` readies a whole side; captaincy transfers when the captain leaves.

(l) **Ready anti-stall.** With `g_readyDelay 30` and `g_readyDelayAction 1`, one
client readying and the other not results in the un-ready client being moved to
spectator after 30 seconds with a localized warning at the halfway mark; with
`g_readyDelayAction 2` both are forced ready; with `g_readyDelay 0` nothing
happens, exactly as today. The countdown resets if the ready player un-readies.

(m) **Ready transport.** Two presses of the ready **bind** (`IMPULSE_17`)
**600 ms apart** both register, where the pre-change build swallows the second
through `ThrottleUserInfo`'s five-second cap. Two presses **100 ms apart**
register **once**, because §8.5 deliberately retains the 500 ms
`lastReadyToggleTime` debounce. In both cases the resulting state matches what
the `ready` console command produces, within one frame. The draft's "twice within
one second" was satisfiable or not depending on the tester's timing, since two
presses inside one second can land inside the retained 500 ms window — it tested
the debounce by accident instead of testing the transport change on purpose.

(n) **World reset.** A lift ridden mid-travel during the countdown is at rest at
`Fight!`; a projectile fired during the countdown does not survive into
`GAMEON`; a player standing on a spawn point during warmup neither telefrags nor
displaces the first live spawn; every timed item is present at `Fight!`
regardless of warmup pickups.

(o) A player switching teams for a single frame does **not** end the match (grace
scope).

(p) `bind x sayTeam "%h %a %w %l %n"` produces a correct report, `%l` names a real
item spawn from its localized decl name, and `%n` does not report a team mate
through a wall.

(q) `g_timeoutCount 0` removes `timeout` and `timein` entirely, leaving only the
referee pause.

(r) A coach calls a timeout and it decrements the coached team's budget, is
announced with the coach's name, and is subject to the `MPS_RESUMING` lock.

(s) Validation sweep green.

### Phase 5 — Stats depth, live accuracy, hit feedback and the match record

**Module scope.** `openQ4-game/src/mpgame/mp/stats/`, `mp/match/MatchLog.{h,cpp}`,
`mp/HitFeedback.{h,cpp}`, `MultiplayerGame.{h,cpp}`, `Player.{h,cpp}`,
`Game_network.cpp`; plus `scoreboard.gui`, `mphud.gui` and the `.lang` mirrors in
`openQ4`.

**Scope.** Flipping the Phase 0 `mpStatFieldInfo_t` table's `wireBits` for the
fields that now ship, and adding the corresponding columns to the named column
sets. Per-round scope replacing the double `Init()`. Item pickup counters and
intervals. The free list on the stat slab and the `FreeEvents` / `RemoveRange`
correction. Widened, versioned, chunked, per-recipient-redacted `MATCHSTATS`;
retirement of `_ALL_STATS` **with its summary-board wiring repointed in the same
change**. The accuracy overlay on the `_ingameStats` hold plus the `acc` toggle,
both with spectator redirection. Rewritten
`UpdateEndGameHud` and replaced `BuildSummaryListString`.
`GAME_RELIABLE_MESSAGE_HITINFO` with `g_hitFeedback`, `hud_hitBeep` and
`hud_damageNumbers`. `mp/match/MatchLog.{h,cpp}`.

**Dependencies.** Phases 0 and 2.

**Exit.** Two-instance harness on q4dm1:

(a) Fire a hand-counted 20 rail shots with 12 hits and confirm exactly 60.0%
on **both** the local and the remote client — this is the test that proves the
widened wire format actually arrives, since damage and accuracy are server-only
today.

(b) One shotgun blast hitting one target counts one hit, not eight.

(c) Self damage appears in damage taken and never in damage dealt or accuracy;
team damage in Team DM is bucketed separately and does not move accuracy; corpse
damage scores nothing; warmup is excluded.

(d) Damage dealt and taken appear on the scoreboard on the remote client.

(e) Holding `_ingameStats` shows the local player's accuracy while playing and
the followed player's while spectating; `acc` toggles the same overlay. A key
bound to `_ingameStats` must **release** the overlay on key up, which is the
property a `+acc` binding could not have delivered (§5).

(f) With `g_statsRedactOpponent 1`, `stats` during `GAMEON` shows the caller's own
weapons only, and at `GAMEREVIEW` shows both; a spectator sees both throughout.

(g) In Clan Arena, per-round stats accumulate across rounds and reset per round
independently.

(h) A 20-minute match does not exhaust the stat allocator; verified by logging
block usage. A forced wrap past `MAX_BLOCKS` in a scratch build frees its events
instead of leaving dangling pointers.

(i) The end-of-match JSON parses with a stock parser, carries a stable
`MATCH_GUID` on every event, carries `si_matchPreset` and the roster, and its
`PLAYER_STATS` weapon sub-fields match what the scoreboard displayed exactly.

(j) Duel item-control columns are blank on the opponent's row during `GAMEON` and
populated at `GAMEREVIEW`.

(k) **Reliable-queue headroom, measured statically rather than on a full
server.** The draft asked for "an intermission with the maximum connected clients
produces no reliable-queue warning", which the two-instance harness cannot
perform and which §10 simultaneously admits is never tested. It is replaced by a
check in `competitive_match_layer.py` that computes the worst-case `MATCHSTATS`
byte count for `MAX_CLIENTS` — **32**, from `Game_local.h:59-62`, not the 16 in
the dead `#ifdef _XENON` branch — from the `mpStatFieldInfo_t` widths, divides by
the chunk size, and asserts that the resulting per-frame byte rate stays inside
`net_serverMaxClientRate` with margin. The chunk size is **re-derived against 32
here rather than inherited**: four clients per message over 32 clients is eight
consecutive server frames of burst, twice what the draft's figure assumed, so the
check either confirms four still fits or the constant changes — §12 records that
in a failure it is the constant and the field widths that move, never the check.
No clients are needed and the arithmetic is the thing that was actually at risk.
The two-instance run still confirms no `#str_07136` drop occurs in the case the
harness *can* produce.

(l) **Exactly one summary appears at `GAMEREVIEW`, and it is populated.** The
draft's criterion was "exactly one", which passes trivially if zero appear —
which is precisely what retiring `_ALL_STATS` without repointing
`ShowStatSummary` would cause. The summary board must render rows from the new
path with real numbers, and clicking a player must populate the per-player panel
that `UpdateEndGameHud` has never populated in this codebase.

(m) **Hit feedback.** With `g_hitFeedback 2` and `hud_hitBeep 1`, a landed rail
shot produces one cue and no cue on a miss; with `hud_damageNumbers 1` the
number matches the damage the scoreboard's damage-dealt total accrues; team
damage is rendered distinctly and moves neither accuracy nor damage-dealt; with
`g_hitFeedback 0` nothing is sent and the client shows nothing regardless of its
own settings. With both client cvars at their defaults the match is
indistinguishable from the pre-change build.

(n) Validation sweep green.

### Phase 6 — Spectator tooling and item timers

**Module scope.** `openQ4-game/src/mpgame/mp/SpectatorTools.{h,cpp}`,
`mp/ItemTimers.{h,cpp}`, `Player.{h,cpp}`, `Item.{h,cpp}`,
`MultiplayerGame.{h,cpp}`; plus `mphud.gui` and the `.lang` mirrors in `openQ4`.

**Scope.** Follow by name/slot, reverse cycle, sticky auto-follow modes, relaxed
spectate cooldown, team-vitals overlay, coach role, spectator chat routing and
`g_allTalk`. The timed-item registry with its `mpTimedItemClasses[]` table and
`MPValidateTimedItemTable()`, the derived deadline over
`idClass::EventTimeRemaining`, the delta-compressed snapshot block appended after
the ping block, `si_itemTimers` as a three-state policy enforced per recipient at
send time, and a votable `timers` row.

**Dependencies.** Phases 0, 1 (timers must survive a pause), 2, 4.

**Exit.** Two-instance harness plus a third spectating instance:

(a) `follow <name>`, `follow <slot>`, `follownext` and `followprev` all reach the
intended target and skip spectators and eliminated players; repeated
`follow quad` cycles through holders.

(b) `follow killer` retargets within a second of the followed player dying;
`follow leader` tracks a lead change.

(c) A spectator cannot follow a spec-locked team and is not left free-flying
inside it.

(d) `speconly` keeps a player out of the Duel queue; `specdefer` moves them down
it and publishes the new position.

(e) A coach receives team chat and the team overlay, can call a timeout, and
appears as a coach on the scoreboard; `coachDecline` and `ref coach` both work.

(f) `si_itemTimers 0` shows timers to nobody; `1` shows them to spectators only
and **not** to live players; `2` shows them to everyone; `callvote timers 0` flips
it live.

(g) A timer is correct for an item on the far side of the map that the viewer has
never seen and has no line of sight to — the specific case the PVS-gated `idItem`
snapshot cannot serve, and the reason for the dedicated block.

(h) With `si_itemTimers 1`, a live player who edits `hud_itemTimers 1` still sees
nothing (the filter is at send time, not client-side).

(i) **Timers survive a pause with their remaining time intact**, checked against
`debugMatchTime`'s event dump as well as on screen — the value on the wire and
the event's remaining delay are the same quantity (§8.9) and must agree, and be
unchanged, before, during and after.

(j) **`MAX_TIMED_ITEMS` is measured, not asserted.** Every stock multiplayer map
is loaded in each gametype it supports with the registry size printed, and the
resulting map-to-count table is pasted into §8.9 of this document. If any map
exceeds 32 the constant is raised before the phase closes. A scratch build with
the cap lowered to 4 must emit exactly one warning naming the map and the true
count, and must keep four working timers rather than corrupting the block.

(k) With `g_spectatorChat 0` a spectator's global chat during `GAMEON` reaches
only other spectators. An operator who previously had `g_spectatorChat` in a
client-side config is warned in the upgrade notes that it must move to
`server.cfg`.

(l) **No new content file is added**; verified by the staged-content check.

### Phase 7 — Presets, cosmetic parity, autoaction, the settings page and documentation

**Module scope.** `openQ4-game/src/mpgame/mp/match/MatchPresets.{h,cpp}`,
`mp/Enforcement.{h,cpp}`, `mp/AutoAction.{h,cpp}`, `Player.{h,cpp}`,
`Item.{h,cpp}`, `gamesys/SysCvar.{h,cpp}`; plus `mpmain.gui`,
`settings-menu-registry.json`, the `.lang` mirrors and `docs/` in `openQ4`.

**Scope.** `mp/match/MatchPresets.{h,cpp}`: the compiled table shipping `duel`,
`tdm`, `ctf`, `ca` and `casual`; the parsed-and-whitelisted `presets/<name>.cfg`
override with defined precedence; `matchPreset` as a table row and
`applyMatchSettings`; atomic apply deferred to a match boundary;
`MPHashMatchSettings()` and the drift flag; `si_matchRules` and `si_matchPhase`;
`matchsettings` covering the full competitive set including the `g_` rows.

`mp/Enforcement.{h,cpp}`: `si_forceModels` through
`Player_ForcedModelCVarString`, `si_maxFov` as a clamp inside
`idPlayer::DefaultFov`, `si_allowSimpleItems` at `Item.cpp:515`, the flood
buckets, `g_inactivity`, `g_allowKillMsec`.

`mp/AutoAction.{h,cpp}`: `ui_autoAction` / `si_autoAction`,
`MPBuildMatchBasename()`, screenshot and stats dump.

**The Competitive settings page** in `mpmain.gui` for the nine `hud_` cvars, with
`docs/dev/settings-menu-registry.json` entries. The draft left the menu question
open, which would have made `settings_menu_coverage.py` pass vacuously.

`docs/user/competitive-play.md` linked from README.md's Player Guides list and
cross-linked from `server-setup.md`; extension of `server-setup.md`'s cvar and
command tables including the two upgrade notes (`g_spectatorChat` persistence,
ready bind transport); a Ready For Changelog entry in
`docs/dev/release-completion.md`; the deferred-timeouts note in
`quakelive-multiplayer-port.md` updated to point here.

**Dependencies.** All previous phases.

**Exit.**

(a) `matchPreset duel` from a **referee on a remote client** applies every setting
in one operation, announces it, and sets `si_matchPreset` to `duel` on both
clients and in the server browser entry. A `matchPreset` issued during `GAMEON`
takes effect only at the next `WARMUP`.

(b) Changing any one competitive setting afterwards flips the name to `duel*` on
both clients within a frame and `matchsettings` names exactly that row and no
other; re-applying clears it. This is the phase's defining test and nothing else
in the reference lineage implements it.

(c) A preset survives a map change. A `presets/duel.cfg` containing an unknown key
is refused as a whole with a console warning, and one containing a known key
overrides the compiled value.

(d) `matchsettings` lists the `g_` rows as well as the `si_` rows, including
`g_hitFeedback`, `g_timeoutCount` and `g_mapPool`.

(e) `si_maxFov 100` clamps a client at 110 and leaves one at 90 alone, **and the
clamped client still reads `g_fov 110` after disconnecting** — the archived value
is never written back. `si_forceModels 1` suppresses a client's `g_forceModel`
without clearing it, and `si_forceModels 2` forces enemy models on the remote
client. Twenty chat lines in one second throttle rather than overflowing the
reliable channel and do not drop the client. `g_inactivity 60` moves an idle
player to spectator.

(e1) **`si_maxFov` cannot invert the clamp.** `si_maxFov 45` is either refused at
set time with a localized `Warning()` naming the cvar, or floors at 90 — never
accepted as a ceiling below 90. Verified by reading a client's effective FOV at
`si_maxFov` 45, 89, 90 and 130: the first two must behave exactly as 90 does, and
no value may drive a client below the 90 floor `idPlayer::DefaultFov` has enforced
since retail. This is the case the draft's code shape got backwards and that
testing only 100 and 110 could not reach.

(e2) **Cosmetic policy reapplies on a live serverInfo change, within one frame,
with no client action.** Flipping `si_forceModels` 0 -> 2 on the server changes
the models the *remote* client renders within one frame **without that client
touching `g_forceModel`**, and flipping `si_allowSimpleItems` 1 -> 0 restores
full item models on the remote client the same way. Both fail on the naive
implementation, because `IsModified()` fires only when the client's own cvar is
written (§8.11); this criterion is what proves the enforcement module drives the
two reapply loops itself.

(f) `ui_autoAction "ss stats"` produces a screenshot and a stats file at
intermission sharing a basename containing both player names, the map and a
timestamp; `si_autoAction` overrides a client that opted out; a client with both
empty records nothing.

(g) **The serverInfo datagram, measured synthetically rather than on a full
server.** The draft required this measurement "on a full server", which the
harness cannot produce. It is replaced by a check in
`competitive_match_layer.py` that builds the serverInfo dict via
`MoveCVarsToDict( CVAR_SERVERINFO )` after a full preset apply — **deriving the
`si_` count from that call rather than restating a literal**, since the figure has
already drifted once — appends **32** synthetic client rows at maximum name
length with worst-case ping and rate fields in the exact format
`ProcessGetInfoMessage` uses (`AsyncServer.cpp:2044-2080`), and asserts the total
stays inside 1400 bytes with margin.

The row count is **32 because `ProcessGetInfoMessage` loops `MAX_ASYNC_CLIENTS`**
(`AsyncServer.cpp:2064`; `MAX_ASYNC_CLIENTS = 32`,
`openQ4/src/framework/async/AsyncNetwork.h:44`) — not because of `MAX_CLIENTS`,
which happens to be 32 as well but is a different constant governing a different
loop. Sixteen rows, as the draft specified, computes half the real worst case in
exactly the term this check exists to bound.

1400 is asserted as **this project's self-imposed budget, not an engine
invariant**: `MAX_UDP_MSG_SIZE` is defined only in
`openQ4/src/sys/win32/win_net.cpp:863` with debug-only asserts at `:986` and
`:1065`, and `sys/posix/posix_net.cpp` asserts nothing at all, so on Linux and
macOS an oversized dict fails silently rather than loudly (§4). This is the one
silent, release-build-only failure mode the whole `si_`/`g_` budget discipline
exists to prevent, and a static byte count catches it where a platform-specific
debug-only assert does not. The live two-instance run additionally confirms the
server remains visible in the browser after a preset apply.

(h) **A server that upgrades and changes no cvar behaves identically to the
previous build across a full match in Duel, Team DM and Clan Arena** — no referee,
no timeouts, no timers, no clamps, no throttles, no hit cues, voting unchanged.
The two known exceptions are exercised explicitly rather than glossed: a
`g_spectatorChat` value persisted in a client config no longer takes effect, and
a ready bind pressed twice in a second now registers both presses.

(i) **The settings page.** All nine `hud_` cvars appear on the Competitive page,
each round-trips through the menu, and
`docs/dev/settings-menu-registry.json` lists exactly those nine and no `si_` or
`g_` row. `settings_menu_coverage.py` passes non-vacuously.

(j) `docs_link_integrity.py`, `settings_menu_coverage.py`,
`lang_table_encoding.py` and `competitive_match_layer.py` all pass; full
validation sweep green on the `push` and `pr` profiles.

---

## 10. Risks and open questions

### The pause is the load-bearing risk

Everything else assumes it. Four specific failure modes.

**A deadline that is covered by two mechanisms.** This was the draft's largest
unstated hazard: `MatchTime()` and `ShiftEventTimes()` were asserted to compose,
and the draft's own enumeration then listed item respawn as both an `idEvent`
and a stored match-time deadline. §8.2 states the invariant, §8.2 enumerates
every deadline against exactly one mechanism, §8.9 removes the item timer's
second store by deriving it, and `competitive_match_layer.py` pins the ownership
table as a token list. Residual risk: the pin catches a deadline that acquires a
*second* mechanism; it cannot catch one that has none.

**A deadline that is neither an `idEvent` nor covered by a shift method.** That
is the remaining residual and it is where the risk lives. Mitigation is
threefold: Phase 0 lands the match-time conversion with the accumulator pinned at
zero, so the audit is a reviewable no-op diff rather than a change hidden inside
a feature; `idEntity::ShiftFrozenTime`'s default implementation is **not empty**,
so a class that forgets to override still has its physics, animator and shader
time shifted — the safe polarity; and Phase 1's exit criteria are written as
*instrumented* timer and mover checks rather than "it looks paused", because that
is the only way this failure class surfaces. Residual risk: BSE effect start
times and sound-emitter timing are not shifted and will drift by the pause
duration. That is cosmetic, it is stated here rather than discovered later, and
it is the one thing this design knowingly leaves imperfect.

**The global event queue is shifted, not the match's subset.** `EventQueue` is
one file-static list shared by every `idClass` (`Event.cpp:279`), so a pause
shifts every pending event in the process, including ones belonging to entities
that deliberately keep running. In a multiplayer match nearly every queued event
belongs to a gameplay entity, so this is right far more often than wrong, and
the exceptions fall into the cosmetic residual above. Filtering the queue by
owner would require walking and testing every node every frame and would still
need a definition of "belongs to the match" that no existing field carries.

**Client/server disagreement for a round trip.** MATCHSTATE is reliable and
ordered, so the client learns of a pause one round-trip late and will have
predicted into it. The server is authoritative and the next snapshot corrects it;
the artifact is a small snap at the moment of pause. It is not acceptable at
resume, which is why the resume countdown exists.

### The validation test cannot prove the audit is complete

It can pin the overrider set, the ownership table, the gate's exact token
sequence and `MatchTime()` at the enumerated deadline sites; it cannot find a
deadline nobody thought of. A test that required every entity class to override
`ShiftFrozenTime` would fail for every class that legitimately has no stored
deadline, and the first person under time pressure would loosen it. The pin is
therefore on the *known* set plus the two call sites, and the real coverage is
the exit criteria.

### The serverInfo datagram

`ProcessGetInfoMessage` sends the whole serverInfo dict plus one per-client row
per `MAX_ASYNC_CLIENTS` slot (**32**) in one unfragmented datagram against a
1400-byte limit that is Windows-only (`sys/win32/win_net.cpp:863`) and whose
asserts are debug-only; the POSIX send path asserts nothing. There are already
**63** `si_` declarations. This is why the design holds new `si_` to eight — down
from the draft's nine, since `si_refAvailable` was deleted — and pushes
everything else to `g_` with derived state on `mpMatchState`. Residual risk:
`si_matchPreset`, `si_matchRules`, `si_matchPhase` and `si_autoAction` are
strings, and strings are the expensive kind. Mitigation: the first three are ROM
and length-capped (16/32/12 characters), and Phase 7's exit criterion (g)
measures the dict **synthetically**, with **32** worst-case client rows, in the
validation test rather than on a server the harness cannot build. This is a
silent, release-build-only failure and it is the risk most likely to be
discovered by a user rather than by CI, which is exactly why the check had to
become one CI can run.

### Reliable-channel overflow ejects players

A single failed reliable send clears the queue and calls
`DropClient(..., "#str_07136")`. Four realistic sources are addressed by design:
the pause replicates two state transitions rather than a per-frame offset; the
intermission stats burst is chunked to four clients per message per frame and
its worst case is asserted statically in Phase 5 (k); the flood buckets exist;
and hit feedback is coalesced to one message per attacker per frame and is
*dropped* under queue pressure rather than queued. Nothing in this layer is
periodic. The temptation to "just send the timers every second" is the one that
ejects players — item timers ride the snapshot for that reason.

### Fragile inherited tables with no compile-time check

`announcerSoundDefs[]` is index-parallel with `announcerSound_t` with nothing
enforcing it. Every new announcement aliases onto a stock clip, and the validation
test asserts the two array lengths agree. `vote_gametype_t` mirrors
`mpVoteGameTypeOrder[]` by hand. `si_voteFlags`' documented bits disagree with
`voteFlag_t` today; this plan corrects the help text and warns at init rather than
re-deriving the mask, because re-deriving it would silently change what every
existing archived value disallows. `rvPlayerStat` and `PackStats` are the same
hazard in a different shape and are the reason `mpStatFieldInfo_t` exists.

### Wire-format hazards

`rvGameState::SendState` early-outs on `*this == *previousGameState`, so a field
added without also landing in `operator==`, `operator!=` **and** `operator=`
replicates exactly never — and looks correct on a listen server, because the host
never receives its own reliable messages. This design avoids the base header
entirely, but `mpMatchState` has the same shape, so the test requires every
`MSG_MATCH_*` tag in `PackState`, `UnpackState` and `operator==`. The snapshot
read/write order is untagged and unversioned, so the item-timer block is appended
at the end and its position is pinned as an ordered token list on both sides. The
widened centre-print payload is a genuine wire change to an openQ4-owned message
and rests on the same-build assumption, stated rather than assumed.

### Localization is the easiest rule to break

Roughly 400 new `#str_` ids across four mirrors. The reference mods are no help:
every one of them hardcodes English, and OpenTDM and AfterShock build fixed-width
ASCII tables whose alignment depends on English word lengths. The specific traps
are listed in §7. The highest-value pin in `competitive_match_layer.py` is the one
that scans `mpgame` sources and the `.gui` files for `#str_` references and
requires each to exist in all four mirrors; the four table validators cover the
runtime-selected ids a static scan structurally cannot see.

### Test coverage is structurally limited

There are no bots in the game module, so nothing multi-client can be validated in
a single instance, and `+set` does not reach `CVAR_GAME` cvars. Nothing in this
plan asserts behaviour at 8, 16 or 32 players from a live session — the two
criteria that used to claim otherwise are now static or synthetic checks, sized
against the real constants (`MAX_CLIENTS` 32, `MAX_ASYNC_CLIENTS` 32), so the
Risks section and the exit criteria finally agree. Never `+devmap` an `mp/` map in
single player. Never measure performance in `builddir` (it is `-O0`), which
matters for the item-timer snapshot cost and the stat accumulation.

### Scope

Sixteen new modules, eight phases, roughly 400 `#str_` ids, roughly 60 cvars
(8 `si_` + 42 `g_`, one of which is a relocation rather than a new declaration,
+ 2 `ui_` + 9 `hud_` = 61 declarations for 60 new capabilities),
roughly 95 commands, seven reliable messages, a snapshot block, a stats wire
version, three `.gui` rewrites and two new GUI pages. This is larger than the
Quake Live port it extends. The phasing is designed so each phase is
independently shippable and each has a defensible reason to exist on its own —
Phase 0 fixes a live bug, Phase 1 discharges a documented deferral, Phase 2
replaces the rcon proxy, Phase 3 deletes a path the source calls a mistake,
Phase 4 no longer waits on Phase 3. But cohesion is partly whether one author can
hold it, and the honest statement is that this plan is at the edge of that.

### Open questions needing a human decision

1. ~~**Item timer default.**~~ **Closed 2026-07-29: `si_itemTimers` ships at
   `1`** — spectators and coaches see item respawn timers, live players never do.
   A match is castable out of the box; competitive integrity is untouched because
   no player in the match gains information. §4 and §8.9 carry the default and
   §4's "defaults leave casual servers unchanged" paragraph records it as one of
   the three deliberate exceptions rather than pretending nothing changed.

2. **Whether captains ship enabled.** `g_allowCaptains 0` is proposed so a pub
   server does not hand the first joiner on each side the power to lock the
   roster. Competitive servers turn it on via the preset. If captains should be on
   by default, say so now, because the default determines whether `lockTeam` needs
   a second gate.

3. **Whether `si_voteFlags` is eventually retired.** This plan keeps it alive
   alongside `g_voteAllow` with a coexistence warning. Retiring it is cleaner but
   changes behaviour for every server with a persisted value. A deprecation
   release followed by removal is the third option.

4. **Whether the centre-print widening is acceptable.** It is a wire change to a
   shipped openQ4 message. The alternative — a second announcement channel — is
   worse, and mixed builds were never supported. Confirm the same-build
   assumption is one this project is willing to write down.

5. **Whether Tourney gets a pause.** Phase 1 excludes it. Lifting the exclusion
   needs an audit of `rvTourneyArena`'s own timers and a decision about whether a
   pause is global or per-arena. Q4MAX never solved it.

6. **Client identity.** Referee auto-lists, persistent bans, cross-session stats
   and full reconnect restore all gate on a stable per-player identity that
   Quake 4 does not have (`com_guid` is ROM and never written). This plan works
   around its absence everywhere — `connectionToken` is per-connection, not
   per-player, so the roster restore of §8.5 survives a drop and reconnect within
   one match and nothing more. Whether openQ4 should invent a real identity is a
   foundational decision deserving its own track, and it should be answered
   before anyone asks for any of those four features.

7. ~~**Lag compensation, and specifically the port.**~~ **Closed 2026-07-29: the
   port runs first, ahead of Phase 0.** A complete implementation already exists
   in `openQ4-game/src/game/` and is unreachable from multiplayer because the
   engine loads `game_mp` for every non-singleplayer gametype (§2), so this is a
   port plus a validation problem rather than a from-scratch design problem. It
   is the single largest item for competitive credibility and every other feature
   in this document is administration around a game whose hit registration must
   be right first. It gets its own design record rather than a phase here,
   because it is a `src/game/` → `src/mpgame/` port across two divergent forks
   and its validation problem (proving a hit registers where the client aimed,
   with no bots) is unrelated to anything else in this plan.

8. **Whether the map draft ships at all.** §8.4 designs it and `g_mapDraft 0`
   hides it. It is the only feature here with no in-repo precedent to extend, and
   the alternative is that leagues run their draft in a Discord channel as they
   do today. If it is cut, `ref cointoss` and `g_mapPool` still cover the useful
   part and §8.4's draft subsection moves to Out of scope.

9. **Whether `g_spectatorChat` may lose `CVAR_ARCHIVE`.** §4 drops it because a
   server rule archived into client configs is meaningless. The cost is that an
   operator with a persisted value silently loses it on upgrade. The alternative
   is to keep the flag and document that the plan's own prefix discipline has one
   grandfathered exception. Either is defensible; doing it silently is not, which
   is why it is here.

10. **Whether hit feedback should default to permitted.** *Still open.* It was
    put to the author on 2026-07-29 alongside the item timer default and was the
    one of the pair left unanswered, so the landed slice's `g_hitFeedback 2`
    stands by default rather than by decision. At `2` the server permits the cue
    and the amount, while `hud_damageNumbers` and `hud_hitBeep` both default to
    `0`, so a player who edits nothing sees and hears exactly what they do today
    and only a player who opts in is affected. The stricter alternatives are `1`
    (cue without the amount — but with only damage numbers implemented, that
    makes the feature do nothing when a player enables it) and `0` (invisible
    until an operator opts in, which in practice means most servers never enable
    it). Revisit when §8.7's hit sounds land, since `1` becomes meaningful then.

11. **Whether the nine `hud_` cvars belong in the Settings menu.** §4 says yes and
    Phase 7 builds the page. The cost is nine registry entries and a GUI page to
    maintain; the benefit is that the project's "intuitive, configurable" goal is
    not contradicted by a console-only band. If the answer is no, §4 must say so
    explicitly and record that `settings_menu_coverage.py` is vacuous for this
    band.

12. **Whether `si_forceModels 2` is wanted at all.** Forcing enemy models is a
    real competitive setting in this lineage, but it is also the setting most
    likely to be read as the server dictating a player's aesthetics. Modes 0 and
    1 carry the parity argument on their own; mode 2 is the one that needs a
    deliberate yes.

---

## 11. Defects found while writing this plan

Nothing has landed, so nothing has been fixed. These are recorded because
several of them changed the design, several will surprise whoever implements it,
and a few are worth fixing on their own regardless of whether this layer ships.

**Scoreboard**

- `UpdateDMScoreboard`'s inner chain is `if ( gameType == GAME_DM )` / `else if
  ( gameType == GAME_TOURNEY )` with **no trailing else** (`:1501`, `:1550`,
  closing `:1642`). `GAME_DUEL` is `GTF_DUEL | GTF_FRAGLIMIT` with no `GTF_TEAM`
  (`mp/GameTypes.cpp:63-64`) and `IsTeamGame` tests `GTF_TEAM`
  (`Game_local.h:1478-1479`; the sibling `IsTeamGameType()` at `:1019` tests the
  same flag without the `isMultiplayer` guard), so Duel routes here and writes **no scoreboard rows
  at all** — not even the blanks — leaving whatever the previous gametype wrote.
- `scoreboard.gui`'s final `else` (`:219-221`) shows the Tourney bracket panel,
  so all eight Quake Live gametypes (`GAME_DUEL` 9 through `GAME_ATTACK_DEFEND`
  16, `MultiplayerGame.h:45-52`) land there. The team modes among them take
  `UpdateTeamScoreboard`, which writes `team_%i_scores_item_%i`, while the
  Tourney panel binds `scores` and `spectator_scores` — so **Clan Arena, Freeze
  Tag, Red Rover and Attack & Defend render an entirely empty scoreboard today**.
- `scoreboard.gui`'s own documentation block (`:51-61`) enumerates only gametypes
  0 through 8 and has not been updated since the port.

**Lag compensation**

- A complete server-side rewind implementation lives in
  `openQ4-game/src/game/` (four `net_mpLagComp*` cvars at
  `game/gamesys/SysCvar.cpp:616-619`, a 64-frame per-client ring buffer at
  `game/Game_local.h:1161-1177` with methods at `:1245-1250`, capture at
  `game/Game_local.cpp:4859`, rewind around the hitscan trace at `:9433` and
  `:9723-9724`) and is **completely absent from `src/mpgame/`**. Because
  `Common.cpp:5213` loads `game_mp` for every multiplayer gametype, none of it
  has ever run in a multiplayer match. This is the single most consequential
  finding in the whole review.

**Stats**

- `rvStatManager::UpdateEndGameHud` (`StatManager.cpp:1237-1276`) has its entire
  body inside one comment block, so its only live caller — the `sm_select_player`
  menu command at `MultiplayerGame.cpp:5692` — does nothing. The commented code
  also references `clientStat->weaponAccuracy[]` (`:1251`) and
  `inGameAwards.Num()`, neither of which exists on the current `rvPlayerStat`, so
  it would not compile if uncommented.
- `rvStatAllocator::FreeEvents` (`:531-553`) returns 0 without removing anything
  when the block's events run to the end of `statQueue` (`:544-548`), while
  `GetBlock` (`:134-148`) proceeds to hand out and overwrite that memory —
  leaving dangling `rvStat*` in `statQueue`. The `Warning()` that would have
  flagged it is itself commented out at `:545-546`, and the diagnostic reporting
  how much history was lost is commented out at `:141-142`.
- `RemoveRange( blockStart, blockEnd - 1 )` at `:550` is suspect against a
  half-open `[blockStart, blockEnd)` intent and should be re-derived
  independently of this plan.
- `rvGameState::NewState` calls `statManager->Init()` at both `WARMUP`
  (`GameState.cpp:483-486`) and `GAMEON` (`:568-570`) entry, and `Init` calls
  `cmdSystem->AddCommand( "ShowInGameStats", ... )` (`StatManager.cpp:332`) every
  time — so the command is re-registered once per warmup and once per gameon for
  the life of the process.
- `PackStats` writes `weaponShots` and `weaponHits` with `WriteShort` (`:1304`,
  `:1308`) although both are `int` on the struct, so counts above 32767 wrap.
- `PackStats` omits `weaponKills`, `suicides`, `damageRatio`, `damageGiven`,
  `damageTaken` and `lastUpdateTime` entirely, so no client has ever been able to
  display damage.

**Cvars**

- `g_announcerDelay` (`SysCvar.cpp:670`) is declared `CVAR_SOUND |
  PC_CVAR_ARCHIVE` with no `CVAR_GAME` despite its prefix, is not declared in
  `SysCvar.h`, and is dead — one grep hit in all of `src/mpgame/`, the definition.
- `g_fixedHorizFOV` (`:207`) declares a C++ symbol under one name and registers
  the cvar under another (`r_fixedHorizFOV`).
- `cl_gun_x` / `cl_gun_y` / `cl_gun_z` (`:547-549`) carry no `CVAR_GAME` flag at
  all despite living in the game module's `SysCvar.cpp`.
- `g_fov` (`:556`) has an **empty description string** and no declared min or
  max, and its only bound is an imperative multiplayer-only clamp inside
  `idPlayer::DefaultFov` (`Player.cpp:11040-11045`).
- `g_crosshairSize` (`:564`) uses plain `CVAR_ARCHIVE` where its neighbours use
  `PC_CVAR_ARCHIVE`, and is read back by name rather than through the object
  (`Player.cpp:4313`).
- `g_spectatorChat` is declared inline at `MultiplayerGame.cpp:11` rather than in
  `SysCvar.cpp`, and is `CVAR_ARCHIVE` although it is a server rule read only on
  the server (`:8357`).
- `g_testScoreboard` (`:618`) declares no min or max and no cheat flag.

**Events and time**

- `idEvent::time` is private (`Event.h:68`) and `EventQueue` is a file-static
  (`Event.cpp:279`) with no accessor, and the public API exposes no
  remaining-time query at all — only `EventIsPosted`, returning `bool`. Any
  feature that needs to know when a posted event fires has to add an accessor
  inside `Event.cpp`; there is no way around it from `mp/`.
- `idEvent::Save` / `Restore` persist **absolute** event times (`:933`, `:970`)
  with no rebasing on restore. Harmless for multiplayer, which has no savegames,
  and untouched here because the single-player tree is not edited — but it is a
  real hazard for the tree that does have savegames.
- The 24-day millisecond wrap is acknowledged in-source at `Event.cpp:659` and a
  pause moves it earlier by the total paused duration.

**Engine and framework surprises**

- `idCmdSystemLocal::AddCommand` is **first-wins**: on a name match with a
  different function it prints `AddCommand: %s already defined`
  (`openQ4/src/framework/CmdSystem.cpp:432`) and returns without registering. The
  game module loads after the engine, so a game command that collides with an
  engine one silently never runs, and the only trace is a `Printf` line that the
  standing gate's "no new warnings" check does not classify as a warning.
- **There is no `+cmd`/`-cmd` convention in idTech4.**
  `idKeyInput::ExecKeyBinding` (`openQ4/src/framework/KeyInput.cpp:763`) buffers a
  binding verbatim and synthesizes no release form, and bindings are executed on
  key **down** only (`Session.cpp:5671`). Held-button state exists solely for
  bindings matching the compiled `userCmdStrings[]` table
  (`UsercmdGen.cpp:178-210`). Any Quake 3 lineage feature specified as `+x`/`-x`
  has to be redesigned onto an existing usercmd button or demoted to a toggle.
- `idBitMsgDelta::WriteBits` writes the **full uncompressed value** into the base
  buffer on every snapshot regardless of change
  (`openQ4/src/idlib/BitMsg.cpp:610-613`), so "it delta-encodes, so it is free"
  is true of the message and false of the base. The game-state pseudo-entity's
  base is `MAX_ENTITY_STATE_SIZE` = 512 bytes (`Game_local.h:260`), current
  occupancy is roughly 359 bytes at 32 clients, and overflow is
  `FatalError`, not a warning (`BitMsg.cpp:35-39`).
- `MAX_UDP_MSG_SIZE` (1400) and both of its size asserts exist **only** in
  `openQ4/src/sys/win32/win_net.cpp` (`:863`, `:986`, `:1065`) and are debug-only;
  `sys/posix/posix_net.cpp` has neither, so an oversized datagram fails silently
  on Linux and macOS.
- `MAX_CLIENTS` is 32 (`Game_local.h:62`); the 16 at `:59` is inside
  `#ifdef _XENON` and is dead on every platform this project ships. The serverInfo
  response is sized by a *different* constant, `MAX_ASYNC_CLIENTS`, also 32
  (`openQ4/src/framework/async/AsyncNetwork.h:44`).
- `idMultiplayerGame::CommonRun`'s `IsModified()` reapply polls
  (`MultiplayerGame.cpp:4006-4098`) fire only when a **client's own** cvar is
  written. A serverInfo change sets no such flag, so any server-driven cosmetic
  policy must drive the reapply itself or it takes effect only on the next
  respawn.

**Files and trees**

- `anim/Anim_Blend.h` exists in **neither** tree. The animator classes are
  declared in `anim/Anim.h`; only `Anim_Blend.cpp` exists. The draft of this plan
  named the header, which is how the discrepancy surfaced.
- `openQ4-game/src/game/` and `src/mpgame/` are divergent forks with the same
  filenames and substantially different contents; of the files this plan touches,
  only `physics/Physics_Parametric.h` is byte-identical. `mpgame`'s
  `Physics_Parametric.cpp:2` and `gamesys/Event.cpp:8` carry an explicit
  `#include "../../idlib/precompiled.h"` where the `game/` copies have a blank
  line at the same position.

**Commands**

- `serverForceReady` (`SysCmds.cpp:3483`) sits inside `#ifndef ID_DEMO_BUILD`
  (`:3448-3485`) while `allready` (`:3496`) sits after the `#endif`, so the two
  aliases of the same handler have different availability in a demo build.
- `idMultiplayerGame::ToggleReady` (`:8499`) writes the literal English strings
  `"Ready"` and `"Not Ready"` into `ui_ready` (`:8514-8519`). They are cvar
  tokens rather than display text, so this is not a localization violation, but
  it is the reason a bind and a console command take different transports.

---

## 12. Validation

**Nothing in this document has been built, run or measured.** It is a design
record. This section states what the plan commits to exercising, and — in the
same unhedged voice the Quake Live port record uses when it admits two-player
round progression was never tested — what it structurally cannot.

### What has been verified for this document

Only static reading of the two repositories. Every file path, line number, flag
set and default in §3, §4, §6, §8, §11 and Appendix B was read out of the sources
rather than recalled, and the citations were re-verified against the working tree
after review — roughly thirty of them moved by one to five lines, and several
named the wrong function or the wrong file entirely (`BuildSummaryListString` was
filed under `mp/stats/` at a line `StatManager.cpp` does not have; the three raw
English vote strings were attributed to the removed single-field path when all
three live in the *kept* packed path). The ones still not re-verified are marked
*(recon)* in §8.2's ownership table and are confirmed in Phase 0. The claim that
no lag-compensation symbol exists in `src/mpgame/` is a recorded grep result
(§2), not an impression. The claim that `anim/Anim_Blend.h` does not exist is a
directory listing. No build was run, no game was launched, and no behaviour was
observed.

### What each phase will exercise

Every phase's exit criteria are written to be performable on the stated harness,
and the ones that were not have been rewritten: Phase 5 (k) and Phase 7 (g) are
now static checks in `competitive_match_layer.py`, sized against `MAX_CLIENTS`
(32) and `MAX_ASYNC_CLIENTS` (32) rather than the draft's 16; Phase 0 (d) and
Phase 1 (d) are instrumented `debugMatchTime` dumps rather than stopwatches
against a HUD clock; Phase 0 (b) names which side fabricates its synthetic rows;
and Phase 4 (m) states two press intervals rather than one that could land on
either side of a retained 500 ms debounce. The
harness is a dedicated server plus two clients, each with its own `fs_savepath`,
`win_allowMultipleInstances 1`, and `ui_joined 1` / `ui_spectate Play`; a third
spectating instance is added where the criterion needs one. `+set` on the
command line does not reach `CVAR_GAME` cvars, so every phase configures through
an exec'd `.cfg` or the console.

### What will not be exercised, and will be said so in the eventual record

- **Behaviour at 8, 16 or 32 connected players.** There are no bots in the game
  module and the harness tops out at three instances. The two places where the
  draft claimed a full-server measurement are now static and synthetic, which is
  an improvement in rigour and a reduction in coverage at the same time: the
  arithmetic is checked, the live behaviour is not.
- **Sustained load.** Nothing measures the item-timer snapshot cost or the stat
  accumulation cost under real player counts, and nothing may measure them in
  `builddir` at all, which is `-O0`.
- **Mixed builds.** Explicitly unsupported (`si_pure 1`) and not tested.
- **The repeater path.** Dead in openQ4. The three dispatch cases exist so the
  unknown-message warning does not fire; none of them is exercised.
- **Non-Windows behaviour of anything in this layer.** The design introduces no
  platform-specific code — file writes go through `fileSystem`, screenshots
  through `renderSystem` — but the phases are written against the Windows Meson
  wrapper and the Linux and macOS builds are covered only by the standing
  validation sweep.
- **Translated strings.** The French, Italian and Spanish mirrors carry English
  placeholder text, as the Quake Live block already does. `lang_table_encoding.py`
  checks encoding and structure; nobody checks meaning.
- **The single-player module.** Deliberately: no phase edits it, and the diff
  scope check is what proves that rather than a campaign play session.

### What would falsify the central claims

Recorded so a reviewer has something concrete to attack:

- If any deadline in §8.2's ownership table turns out to be covered by two
  mechanisms after Phase 0's confirmation pass, the invariant is wrong and the
  pause design needs rework before Phase 1.
- If `idPhysics_Parametric::UpdateTime` turns out not to be safe to call every
  frozen frame — for instance if some caller depends on `current.time` advancing
  monotonically with `gameLocal.time` in a way a repeated zero-delta rebase
  breaks — then the deleted `idPhysics::ShiftFrozenTime` virtual comes back and
  §8.2's simplification is lost.
- If the worst-case `MATCHSTATS` byte count computed in Phase 5 (k) does not fit
  the chunk size and rate cap, the chunk size changes and the stats field table's
  widths are re-derived, not the check.
- If the synthetic serverInfo measurement in Phase 7 (g) exceeds 1400 bytes, at
  least one of the eight `si_` keys becomes derived state on `mpMatchState`
  instead, and the `si_`/`g_` discipline of §4 is what decides which.
- If the startup bit-count assertion in §6's game-state block budget fires at
  `MAX_CLIENTS` in any gametype, `MAX_TIMED_ITEMS` drops below 32 and §8.9's
  overflow warning becomes the normal path on large maps — or the block moves off
  the game-state pseudo-entity entirely, which would mean a new periodic message
  and would contradict §6's "nothing in this layer is periodic" property. That is
  the single measurement most likely to force a redesign, and it is a
  `FatalError` rather than a warning if it is got wrong.
- If `idEvent::TimeRemaining` cannot be implemented as a cheap query — if the
  queue must be walked linearly per item per snapshot rather than reached through
  the object's own event list — the derived item-timer deadline stops being free
  and either gains a cache (reintroducing the second store §8.2 forbids) or the
  registry is capped well below 32.
- If `idPlayer::ShiftFrozenDeadlines` cannot run at the head of `RunFrame`
  because some pause-relevant state is only valid after `mpGame.Run()`, then the
  one-frame-late pause edge of §8.2 becomes a correctness problem rather than a
  latency one, and the pause state machine has to be split across the frame.

---

## Appendix A — Corrections applied

Each numbered item from the completeness critique, and one line on how it is
discharged. A reviewer can audit this document against this table.

| # | Severity | Discharged by |
| --- | --- | --- |
| 1 | P0 | Every row of §3 is annotated `openQ4-game/src/mpgame/`, `openQ4-game/src/game/` or `E:\Repositories\openQ4\`; the front matter and §9 state that **every phase is `mpgame`-only** and that `src/game/` is never edited; Phase 1 exit (j) is replaced by the diff-scope check in `competitive_match_layer.py`. The Meson and runtime evidence for the two-tree split is quoted in the front matter. |
| 2 | P0 | The invariant is stated in one sentence at the head of §8.2 and backed by a full deadline-ownership table pinned as a token list. The item timer stores nothing and carries no `MatchTime()` term at all — it ships `idEvent::TimeRemaining` directly (§8.9), so `ShiftEventTimes` is its single mechanism by construction rather than by a cancellation argument. §8.2(2) no longer claims powerup expiry, weapon refire and movers "survive a pause with no per-call-site change": it names the three explicitly as **not** events, points at their rows in the ownership table, and adds the pin's negative form — `powerupEndTime`, `nextAttackTime` and the six `parametricPState_t` start fields must appear in the shift token sets and in **no** `PostEvent*` call site this layer adds. |
| 3 | P0 | §8.2 fixes both call sites from the source instead of hedging. `idEvent::ShiftEventTimes( gameLocal.msec )` and the `idPlayer::ShiftFrozenDeadlines` pass both run at the **head of `idGameLocal::RunFrame`**, in the order `ShiftEventTimes` -> `ShiftFrozenDeadlines` -> entity loop -> `ServiceEvents` (`Game_local.cpp:4250`); `mpGame.Run()` is at `:4264`, after all three loop variants and after `ServiceEvents`, so it is named as **not** a legal site, and the resulting one-frame-late pause edge is recorded as deliberate. The `ServiceEvents` ordering is justified (shifting after it leaks near-due events every frozen frame). The `ClientPrediction` mirror is given its **own literal form** over `snapshotEntities` / `ClientPredictionThink()` inside the pre-existing `thinkFlags != 0` guard, with the local player's separate edit at `Game_network.cpp:2568` named, and `competitive_match_layer.py` pins **two** token sequences plus the ordered head-of-frame sequence. `ShiftFrozenTime` remains the single writer of `current.time` on a frozen entity and the `idPhysics::ShiftFrozenTime` virtual stays deleted. |
| 4 | P0 | `mpStatFieldInfo_t` and `MPValidateStatFieldTable()` move to **Phase 0** with `wireBits 0` for unshipped fields; `MPValidateColumnTable()` additionally errors if a named column set references a `wireBits 0` field, so Phase 0's column sets are limited to data that exists and Phase 5 adds the rest with their widths. |
| 5 | P0 | The instrumentation moves to **Phase 0**, where the deadline audit actually lands: `idEvent::DebugDumpQueue` plus the **permanently registered** `debugMatchTime` console command (§5, registered in §3's `SysCmds.cpp` row — not a `g_`-prefixed cvar and not temporary, since Phase 6 exit (i) also reads it). Phase 0 exit (d) requires `MatchTime()` and `gameLocal.time` to print **equal**, and each converted deadline to be **bit-identical** to its pre-change absolute; Phase 1 exit (d) reuses the same command across three samples of a five-minute pause. On-screen clocks are secondary in both, because "agree within one frame" is ~16 ms and cannot be established with a stopwatch. §8.8 records that the local powerup countdown **does** exist (`Player.cpp:4025`). |
| 6 | P0 | Phase 5 (k) becomes a static worst-case `MATCHSTATS` byte-count assertion; Phase 7 (g) becomes a synthetic serverInfo dict measurement. Both are sized against the **real** constants after the draft used 16 throughout: `MAX_CLIENTS` is **32** (`Game_local.h:59-62`; the 16 is inside `#ifdef _XENON`), and Phase 7 (g)'s row count is **32 from `MAX_ASYNC_CLIENTS`** (`AsyncNetwork.h:44`), because `ProcessGetInfoMessage` loops that constant and not `MAX_CLIENTS`. Phase 5 (k) re-derives its chunk size against 32 rather than inheriting a figure sized for 16, and Phase 7 (g) derives the `si_` count from `MoveCVarsToDict( CVAR_SERVERINFO )` instead of restating a literal (63 today, not the 61 the draft carried). §6, §10 and §12 now all say 32. |
| 7 | P0 | §4's preamble is rewritten from the code with a table of eight counter-examples, states the narrower `g_` rule as a **new** rule scoped to the layer's own block with a migration note, and records that `si_forceModels` and `si_allowSimpleItems` do not exist today. §8.11 puts the `si_forceModels` gate **inside `Player_ForcedModelCVarString`'s body** (`Player.cpp:174`) rather than at any one call site, since there are **six** (`:3360-3363`, `:3371-3372`) and the draft cited one. It also replaces "the `IsModified()` poll continues to work unchanged" — which was the bug — with an explicit trigger: the enforcement module caches the last-seen serverInfo values and on a change runs the same `updateModels` loop (`MultiplayerGame.cpp:4021-4028`) and `g_simpleItems` reassignment loop (`:4031-4098`), because a serverInfo change sets no `IsModified()` flag on any client cvar. §3 carries the three enforcement sites: `Player_ForcedModelCVarString` on the `Player.{h,cpp}` row, `Item.cpp:515` on the `Item.{h,cpp}` row, and the `CommonRun` poll on the `MultiplayerGame.{h,cpp}` row. Phase 7 exit (e2) tests the live flip. |
| 8 | P1 | Hit feedback is **designed**, not deleted: `GAME_RELIABLE_MESSAGE_HITINFO` (§6), `mp/HitFeedback.{h,cpp}` (§3), `g_hitFeedback` plus `hud_hitBeep` and `hud_damageNumbers` (§4), the design in §8.7, and Phase 5 scope and exit (m). |
| 9 | P1 | `g_mapPool` added (§4), `mp/match/MatchMaps.{h,cpp}` added (§3), designed in §8.4 with the `SendMapList` filter, server-side `callvote map` validation and the `maplist` command, in **Phase 3** with exit (m). |
| 10 | P1 | Map veto/pick is designed as a referee-run ban/pick draft over `g_mapPool` (`g_mapDraft`, §8.4), in Phase 3 with exit (n), default off, and raised as open question 8 because it is the one feature with no in-repo precedent. |
| 11 | P1 | `g_readyDelay` and `g_readyDelayAction` added (§4), designed in §8.5 with the warning announcements and the match-time timer, in **Phase 4** with exit (l). |
| 12 | P1 | Network settings parity is **excluded explicitly** in §2 with the reason named: `net_clientPrediction` and `net_clientMaxRate` are engine-side in `openQ4/src/framework/async`, need a server-to-client system-cvar enforcement channel that does not exist, and belong with lag compensation on the netcode track. §8.11 is retitled "cosmetic settings parity" and says so in its first sentence. |
| 13 | P1 | `MPResetWorldForMatch()` added to `mp/match/MatchTeams` (§3), designed in §8.5 with its four ordered steps including the two-pass unlink-then-respawn, in **Phase 4** with exit (n) requiring a mid-travel lift at rest at `Fight!`. |
| 14 | P1 | `mpMatchRoster` defined on `mpMatchState` (§8.5) with its fields, its four consumers and an explicit statement that **roster and score are restored, inventory is not**; §2's reconnect-restore exclusion now points at it. Phase 4 exit (g) tests the reconnect and the recycled-slot case. |
| 15 | P1 | Spectator delay is named and excluded in §2, with spec-lock plus `g_spectatorChat` identified as the in-game anti-ghosting mechanism and broadcast delay identified as a tournament-operations concern. §8.6 states the rationale at the point of use. |
| 16 | P1 | §5 adds an "already shipped" table listing `allready` (`SysCmds.cpp:3496`) and `serverForceReady` (`:3483`, inside `#ifndef ID_DEMO_BUILD`). `allready` is **promoted to a table row** at `MPA_REFEREE` with `allReady` as an alias; `ref allReady` as a separate row is **dropped**; `serverForceReady` stays console-only at `MPA_CONSOLE`. The collision check that polices this is narrowed so it does not error on the shipped table: because every row is *also* a locally registered console command (there is no console fallthrough), the rule fires only on a name owned **outside** the layer's registration block, and an `MCF_EXISTINGCMD` flag marks the four rows that deliberately share a name (`allready`, `kick`, `say`, `mute`), for which the validator instead asserts that the existing registration's handler **is** the row's apply function. §5 records that `AddCommand` is first-wins (`CmdSystem.cpp:432`), which is what makes that exemption safe. Phase 2 exit (g) enumerates the failures that remain legal-to-fail and exit (l) tests the rule directly — a scratch `serverForceReady` row, or a second `allready` row whose apply function is not `ForceReady_f`, must error at init. |
| 17 | P1 | §8.5 corrects the owning class (`idMultiplayerGame::ToggleReady`, not `idPlayer`), records that openQ4 has **already** built the authoritative path (`idPlayer::ready`, `readyUserInfo`, `GAME_RELIABLE_MESSAGE_READY`, the `Player.cpp:3671` anti-clobber), and narrows the remaining defect to the bind's transport. `ToggleReady` is retargeted at the reliable message with `ui_ready` kept as a shadow; §3 lists it; Phase 4 exit (m) requires bind and command to agree within one frame. |
| 18 | P1 | `si_refAvailable` is **deleted** and the slot freed (§4), and the admin tab is **replaced** rather than removed: §8.3 designs a referee page in `mpmain.gui` generated from the command table's `MCF_GUI` rows, with the two distinct MATCHAUTH refusals that make an advertisement key unnecessary. It lands in **Phase 2** with exit (k) requiring `pause`, `abort`, `putTeam` and `kick` from the page on a remote client. |
| 19 | P2 | `mp/match/` now contains only match-administration modules (MatchState, Commands, Authority, Dispatch, Vote, Presets, Teams, Maps, Log, Scoreboard). `ItemTimers`, `SpectatorTools`, `AutoAction`, `Enforcement`, `ChatMacros` and the new `HitFeedback` sit directly under `mp/`, with the reason stated. |
| 20 | P2 | `g_spectatorChat` **loses `CVAR_ARCHIVE`** and moves from `MultiplayerGame.cpp:11` into the new `SysCvar.cpp` block. The behaviour change is named in §4, in the Phase 6 exit (k), in the user-documentation upgrade notes, and as open question 9. |
| 21 | P2 | §8.11 names `g_fov` (`SysCvar.cpp:556`, no min/max, empty description), specifies **clamp-at-read** inside `idPlayer::DefaultFov`, states the archived value is never written back, records that `idCamera` and `rvTarget_SetFOV` read it unclamped and why they are left alone, and adds Phase 7 exit (e). The clamp is also made sound against the cvar's own reachable range, which the draft's shape was not: `si_maxFov` is declared **0, or 90..130** (§4) with a set-time `Warning()` and an init-time clamp for the 1..89 hole `idCVar` cannot express, and the §8.11 snippet clamps the ceiling into [90, 175] **before** the final `ClampFloat`, so no operator value can produce `min > max` and drive every client below the 90 floor retail has always enforced. Phase 7 exit (e1) tests 45, 89, 90 and 130 rather than only 100 and 110. |
| 22 | P2 | §8.2's Policy subsection states that a coach spends the coached team's budget (the coached player's in Duel), is announced with the coach's name, is subject to the same `MPS_RESUMING` lock, and may not `timein` a timeout they did not call unless the caller has dropped. Phase 4 exit (r). |
| 23 | P2 | §8.9 specifies loud overflow — first 32 in spawn order plus one `gameLocal.Warning` naming the map and the true count — and Phase 6 exit (j) **measures** every stock map's timed-item count, pastes the table into §8.9, raises the constant if any map exceeds it, and tests the overflow path with a lowered cap in a scratch build. |
| 24 | P2 | Decided: the nine `hud_` cvars **get a Competitive settings page** in `mpmain.gui` with `docs/dev/settings-menu-registry.json` entries (§4, §3, Phase 7 scope and exit (i)), so `settings_menu_coverage.py` passes non-vacuously. `si_` and `g_` rows deliberately stay out of the client menu. |
| 25 | P2 | `g_testScoreboard` is the **primary** Phase 0 verification: `MAX_CLIENTS` (32) synthetic rows across all six column sets in all nine gametypes, then stepped down to prove `DeleteStateVar` shrinks the list, with the live two-client run as secondary. §8.8 and Phase 0 exit (b) also state **which side fabricates the rows**: since this plan moves row construction to the server, the fake rows are injected server-side into the column writer, so the cvar is set on the dedicated server and the result observed on a client — which is also the only placement that exercises the serialized path §6's listen-server trap makes a standing rule. Requires extending its reach to the active column set and adding 0..`MAX_CLIENTS` bounds (§3, §8.8, Phase 0 exit (b) and (c)). |
| 26 | P2 | The band is settled **now**: `#str_41410`-`#str_41999`, 590 ids, ten contiguous sub-bands summing to exactly 590, and an explicit allocation rule that a full sub-band takes from the tail reserve rather than spilling. The sizing derivation is also made to add up: the §5 breakdown sums to **95** rows, not the 85 the draft's prose asserted, so the command-table sub-band needs 190 + 35 = **225** ids against 300 allocated, leaving **37** rows of headroom. §10's Scope figures follow (≈95 commands, ≈60 cvars against §4's actual 8 `si_` + 42 `g_` + 2 `ui_` + 9 `hud_`). Nothing is deferred to Phase 2. |
| 27 | P2 | §7 promotes `#str_` resolution to the mechanism the standing gate names: `MPValidateMatchCommandTable()` resolves every `descId`/`usageId`/`voteDescId` through `common->GetLocalizedString` at init and errors naming the row, and the same pass is required of `MPValidateColumnTable()`, `MPValidateMatchPresetTable()` and `MPValidateStatFieldTable()`. The static scan is retained for `.gui` files and literal call sites, with the coverage split stated. |
| 28 | P2 | Phase 4's dependencies are **Phases 1 and 2**, with the reasoning stated and an explicit note that `callvote timeout`-shaped rows light up for free when Phase 3 lands, so Phases 3 and 4 may proceed in either order. |
| 29 | P2 | §3 gains rows for `ShowStatSummary` / `UpdateSummaryBoard` / `DrawStatSummary` / `BuildSummaryListString` / the `sm_select_player` handler and for `scoreboard.gui`'s summary board `listDef`s; §6 and §8.7 state that retiring `_ALL_STATS` orphans them and repoints them in the same change; Phase 5 exit (l) requires the summary board to render **populated** rather than merely to appear once. `BuildSummaryListString` is filed correctly: it is `idMultiplayerGame::BuildSummaryListString` (`MultiplayerGame.h:903`, `MultiplayerGame.cpp:1878`, called at `:1984` and `:2030`), listed on §3's `MultiplayerGame.cpp` summary-block row and cited that way in §8.7 — not, as the draft had it, at `StatManager.cpp:1877`, a file with 1345 lines that does not contain the symbol. |
| 30 | P2 | The player command is renamed **`concede`**; `forfeit` is not an alias. §5 states in one sentence how it coexists with the shipped `si_forfeit` and that `concede` is refused if `si_forfeit` has already ended the match. |
| 31 | P2 | §4 and §8.1 state that `si_matchPhase` is **browser-only** and that the client's authority on match phase is `rvGameState`; `competitive_match_layer.py` pins that it appears in no `.gui` file and in no client-side read. |
| 32 | P2 | §2 records the greps verbatim and corrects both the draft and the critique: `net_mpLagComp*` **does** exist, in `openQ4-game/src/game/` only, with the full symbol and line inventory, and is unreachable in multiplayer because `Common.cpp:5213` loads `game_mp`. The out-of-scope reason is restated as "port and validate", not "write from scratch", it is listed in §11 as the most consequential finding, and it is raised as the highest-value open question (10.7). |

### Defects found by independent review of this document

Three reviewers read the record against the sources after the table above was
written. What they found is recorded separately, because these are errors in the
*design record* rather than gaps in the original critique, and a reader who
trusts the table above should know the document was wrong in these ways and is no
longer.

| Area | Was | Is |
| --- | --- | --- |
| Game-state snapshot budget | §6 argued the item-timer block "costs essentially nothing" because `idBitMsgDelta` delta-encodes. **This would have `FatalError`ed the server unconditionally.** `WriteBits` writes the full value into the base buffer every snapshot (`BitMsg.cpp:610-613`); that buffer is 512 bytes and is already ~359 bytes occupied at 32 clients, and a 32-entry block of absolute match times is ~177 bytes. | §6 gains a "game-state block budget" subsection with the measured occupancy, and `ASYNC_ITEM_TIME_BITS` becomes a **bounded remaining time** (~17 bits) rather than an absolute — explicitly accepting ~72 B/snapshot/client instead of a field that was free in the message and fatal in the base. A startup bit-count assertion against `MAX_ENTITY_STATE_SIZE` is added and pinned. §8.9 drops its `MatchTime()` term accordingly, which also *strengthens* correction 2. |
| `+acc` / `-acc` | Listed as a player command, called a hold-to-show overlay in §8.7, and tested by Phase 5 (e). **idTech4 has no `+cmd`/`-cmd` convention**: bindings execute on key down only (`Session.cpp:5671`) and `ExecKeyBinding` synthesizes no release form, so the overlay would stick on forever. | The hold is the existing `_ingameStats` usercmd button (`UsercmdGen.cpp:197`, `UB_BUTTON5`), plus an `acc` toggle. No engine-side edit, so §9's `mpgame`-only rule survives; the rejected alternative (a new `userCmdStrings[]` entry) is recorded with its cost. |
| `matchsettings` and `callvote ?` | §8.1 required `matchsettings` to cover every `g_` row and §8.4 required bare `callvote` to list what `g_voteAllow` permits — **but §4's whole point is that a client cannot read a `g_` cvar**, and none of the seven reliable messages carried a settings dump. Phase 3 exit (g)'s "in the same frame" made it unbuildable, not merely unspecified. | §6's MATCHSTATE gains `MSG_MATCH_VOTEMASK` and `MSG_MATCH_SETTINGS`, pushed on change and in full from `WriteStartState`. No new opcode, and the same-frame property comes for free because the client always holds the current answer locally. |
| Command descriptor | `const char *alias` — exactly one per row, while §5 declares rows with two and three (`timeout \| pause \| calltime`, `follow \| spec \| obs \| chase`) and §7 justified the row count by calling aliases "a column, not a row". | `const char **aliases`, NULL-terminated. §8.3's validator rule and §5's `allReady` sentence follow. |
| `help` | Listed as a spelling of `commands`. `Common.cpp:4741` already registers `help`, and `AddCommand` is **first-wins** (`CmdSystem.cpp:432`) — the game module loads second, so the row would silently never run. | Dropped; the second spelling is `mphelp`. §5 records the first-wins rule, which is also what makes the `MCF_EXISTINGCMD` exemption safe. |
| Gametype -> column set | Phase 0's first deliverable was "add the `columnSet` column" with **no statement of what to put in it**, and §3 deleted `scoreboard.gui`'s final `else` — the branch §8.8 itself calls *correct* for Tourney — inside a phase titled "with no behaviour change". | §8.8 carries the full mapping, one row per `gameType_t` value including `GAME_SP` and the unused `GAME_ARENA_1F_CTF`, and adds a sixth `tourney` column set whose binding is the **retained** `p_tourney` panel. §3 and Phase 0's scope say so. |
| Phase 1 / Phase 2 circularity | Phase 1's scope ended with "`MCF_WHILEPAUSED` on the command table rows", its entry points were `ref pause` / `ref unpause`, and its exit (b) tested `players` and `matchsettings` — all Phase 2 artifacts, while Phase 2's dependency is Phase 1. The same class of circularity correction 4 removed from Phase 0/5. | Phase 1 ships two temporary `mp_pause` / `mp_unpause` console commands in the `ForceReady_f` runtime-guard shape, which Phase 2 unregisters when the table rows land. `MCF_WHILEPAUSED`, `ref` and the Tourney `MCF_` gate move to Phase 2; Phase 1 exit (b) tests only what exists in that build. |
| Phase 4 exit (m) | "Press the bind twice within one second", while §8.5 deliberately **retains** a 500 ms debounce — so the criterion passed or failed on the tester's timing. | 600 ms apart (both must register, where the old build swallows one) and 100 ms apart (must register once, proving the debounce is intact). |
| Ready-delay deadline | `g_readyDelay`'s countdown was declared to be "in match time, consistent with the ownership table" but had **no row in that table** — the one artifact the validation test pins. | A row was added. |
| `debugMatchTime` | Used by two phases' exit criteria as a "temporary `g_debugMatchTime` console command", declared in neither §4 nor §5, carrying a cvar prefix on a command. | Registered permanently in §5's server console block and §3's `SysCmds.cpp` row as `debugMatchTime [count]`, `CMD_FL_GAME`, and moved into Phase 0 where the audit it verifies actually lands. |
| `si_maxFov` range | Declared `0..130`, so 1..89 was reachable and produced `ClampFloat( min=90, max=<90 )` — driving every client **below** the floor the clamp was meant to raise. | `0, or 90..130`, with a set-time `Warning()`, an init-time clamp for persisted values, a ceiling pre-clamp in the §8.11 snippet, and Phase 7 exit (e1). |
| Meson | Sixteen new file pairs, with no statement of how they enter the build. | One sentence: `list_sources.py` globs them automatically, but at **configure** time, so `meson setup` must be re-run before `ninja` sees a new file. |
| Line-number drift | Roughly thirty citations were off by one to five lines, and several named the wrong function or file: `BuildSummaryListString` under `mp/stats/`; the three raw English vote strings attributed to the *removed* path when all three are in the *kept* `ServerCallPackedVote`; the `ServerCallVote` `GetLocalizedString` list two entries short, guaranteeing Phase 3 exit (l) would fail; `populateBanList` left live against a deleted GUI page; the spectate cooldown cited at a view-height constant; `#str_108025`/`108026` implied in the wrong order. | All re-verified against the working tree and corrected in §2, §3, §4, §6, §8, §11 and Appendix B, which now also carries a **Network and wire format** group and a **Retired surfaces** group. §12 records that the re-verification happened and what it moved. |

---

## Appendix B — Evidence index

The file-and-line references this design rests on, grouped so a reviewer can
re-check a claim without reading the whole document. Paths are relative to
`E:\Repositories\openQ4-game\` unless prefixed `openQ4/`.

**Two game trees**

- `src/meson.build:56-57` — `game-sp_<arch>` / `game-mp_<arch>` target names
- `src/meson.build:364-372` — `mpgame` source listing; `:388-391` — `GAME_MPAPI`
- `openQ4/src/framework/Common.cpp:5212-5213` — runtime module selection
- `src/mpgame/physics/Physics_Parametric.cpp:2`, `src/mpgame/gamesys/Event.cpp:8`
  — the precompiled-header include the `game/` copies lack

**Pause primitive**

- `src/mpgame/gamesys/Event.h:68` (private `time`), `:77-103` (public API),
  `:93` (`EventIsPosted`)
- `src/mpgame/gamesys/Event.cpp:279` (`EventQueue`), `:648-674` (`Schedule`,
  absolute deadline at `:660`, insert compare `:664-667`), `:659` (wrap comment),
  `:766-777` (`ServiceEvents`, head test `:775`), `:933`/`:970` (Save/Restore)
- `src/mpgame/gamesys/Class.cpp:657-658` — `idClass::EventIsPosted`
- `src/mpgame/physics/Physics_Parametric.cpp:563` (`Evaluate`), `:579`, `:586`,
  `:588`, `:592`, `:594` (`GetCurrentValue` calls), `:643` (`current.time`),
  `:657-670` (`UpdateTime`, `timeLeap` at `:658`, `ShiftTime` at `:667`)
- `src/mpgame/physics/Physics_Parametric.h:19`, `:26-31` — `parametricPState_t`
- `src/mpgame/physics/Physics_Base.cpp:225-226` — empty `UpdateTime`
- `openQ4/src/idlib/math/Extrapolate.h:32`, `:101`, `:111` — absolute start times
- `src/mpgame/Entity.cpp:3142`, `src/mpgame/Game_local.cpp:4161`, `:4201` —
  existing `UpdateTime` callers
- `src/mpgame/Game_local.cpp:4159`, `:4199`, `:4212` (the three active-entity loop
  variants), `:4250` (`idEvent::ServiceEvents()`), `:4264` (`mpGame.Run()`, after
  both) — the ordering that fixes the two shift passes at the head of `RunFrame`
- `src/mpgame/Game_network.cpp:2484` (`ClientPrediction`), `:2514-2519`
  (`isNewFrame`), `:2547-2552` (`snapshotEntities` loop with its `thinkFlags != 0`
  guard and `ClientPredictionThink()`), `:2568` (the local player, outside the
  loop), `:2581` (`idEvent::ServiceEvents()`)
- `src/mpgame/Game_network.cpp:1574-1575` — client clock from the snapshot header

**Items and powerups**

- `src/mpgame/Item.cpp:723-726` (`respawn_<gametype>` with its -1.0 sentinel at
  `:723`, the `respawn` fallback and 5.0 default at `:724-726`), `:730-731`
  (forced to 0 in SP), `:732-736` (forced to 0 in buying modes when
  `givenToPlayer != -1`), `:738-743` (event posts),
  `:998` (`Event_Respawn`), `:1026` (`CancelEvents`), `:515` (`g_simpleItems`),
  `:825-831` (`WriteToSnapshot`: physics at `:826-828`, `srvReady` bit at `:830`)
- `src/mpgame/Item.h:88-110` (no respawn field), `:152`, `:154` (powerup hold and
  drop expiry)
- `src/mpgame/Player.h:208` — `powerupEndTime[]`
- `src/mpgame/Player.cpp:395` (absolute deadline), `:5430-5463` (expiry poll,
  server gate `:5455`), `:13257-13259` / `:13295-13298` (replication),
  `:4018-4025` (HUD countdown), `:3858`, `:4297`, `:4365` (HUD call chain)
- `openQ4/content/baseoq4/pak0/guis/hud.gui:1931`, `:1935`;
  `hud_strogg.gui:187` — the consuming windowDefs

**Scoreboard**

- `src/mpgame/MultiplayerGame.cpp:1466` (`gametype` state int), `:1489`, `:1501`,
  `:1525`, `:1546`, `:1550`, `:1634`, `:1639`, `:1642`, `:1644-1646`, `:1704`,
  `:1820-1829`, `:1835-1839`, `:2064`, `:2067`, `:2078`, `:2093`, `:2118-2123`
- `src/mpgame/MultiplayerGame.h:45-52` — the appended gametype ordinals
  (`GAME_DUEL` 9 through `GAME_ATTACK_DEFEND` 16; `:42-44` is the APPEND ONLY
  comment)
- `src/mpgame/mp/GameTypes.cpp:63-64` — `GAME_DUEL` flags
- `src/mpgame/mp/GameTypes.h:66-67` — descriptor columns
- `src/mpgame/Game_local.h:1478-1479` — `IsTeamGame` (guarded by
  `isMultiplayer`); `:1019` — the unguarded sibling `IsTeamGameType()`
- `src/mpgame/Game_local.h:59-62` — `MAX_CLIENTS` 32, with 16 in the dead
  `#ifdef _XENON` branch; `:260`, `:270` — `MAX_ENTITY_STATE_SIZE` 512 and
  `stateBuf`
- `src/mpgame/MultiplayerGame.h:26-53` — the full `gameType_t` enum, `GAME_SP` at
  0 through `GAME_ATTACK_DEFEND` at 16, backing §8.8's `columnSet` mapping;
  `:36` — `GAME_ARENA_1F_CTF` marked "is not used"
- `src/mpgame/mp/GameTypes.h:61-69` — `mpGameTypeInfo_t`, the descriptor the
  `columnSet` column is added to
- `openQ4/src/ui/ListWindow.cpp:772-784` — blank-and-compact behaviour
- `openQ4/content/baseoq4/pak0/guis/scoreboard.gui:51-61`, `:64`, `:120`, `:176`,
  `:219-221`
- `openQ4/content/baseoq4/pak0/guis/mphud.gui:168-174`, `:286-451` — the two
  literal gametype chains

**Network and wire format**

- `src/mpgame/Game_network.cpp:1238` (`ServerProcessReliableMessage`), `:1383`
  (`RepeaterProcessReliableMessage`), `:2038` (`ClientProcessReliableMessage`)
- `src/mpgame/Game_network.cpp:1410-1412` — the commented-out repeater reliable
  send (`:1401-1409` above it is live outgoing-chat code)
- `src/mpgame/Game_network.cpp:805` (`WriteGameStateToSnapshot`), `:812`
  (`mpGame.WriteToSnapshot`), `:820`/`:827` (the read mirror), `:836`
  (`WriteSnapshot`), `:979-992` (the `ENTITYNUM_NONE` base-state allocation and
  the game-state call), `:1001` (`ServerWriteSnapshot`, which has the recipient)
- `src/mpgame/MultiplayerGame.cpp:6508` (`WriteToSnapshot`), `:6583`
  (`ReadFromSnapshot`)
- `src/mpgame/MultiplayerGame.h:284-289` — `ASYNC_PLAYER_*_BITS`
- `src/mpgame/MultiplayerGame.h:413-418` (`centerPrintParm_t`), `:421-424` (the
  four `int parm` overloads); `MultiplayerGame.cpp:6705`
  (`MPFormatCenterPrintParm`), `:6758-6761` (the 2-bit type and short parm
  writes), `:6780` and `:6834` (the two-argument `va()` render sites)
- `src/mpgame/mp/GameState.cpp:132-134` — `rvGameState::SendState`'s early-out
  (`:129-131` is the preceding assert)
- `openQ4/src/idlib/BitMsg.cpp:35-39` — `CheckOverflow`'s `FatalError`;
  `:610-613` — `idBitMsgDelta::WriteBits` writing the full value into `newBase`
- `openQ4/src/framework/async/AsyncServer.cpp:820` (`SendReliableMessage`),
  `:829-831` (the `DropClient(..., "#str_07136")` call);
  `AsyncServer.h:260` (the declaration and its comment, not the call site)
- `openQ4/src/framework/async/AsyncServer.cpp:2044-2080`
  (`ProcessGetInfoMessage`), `:2047` (`msgBuf[MAX_MESSAGE_SIZE]`), `:2064` (the
  `MAX_ASYNC_CLIENTS` per-client row loop);
  `openQ4/src/framework/async/AsyncNetwork.h:44` — `MAX_ASYNC_CLIENTS` 32
- `openQ4/src/sys/win32/win_net.cpp:863` (`MAX_UDP_MSG_SIZE 1400`), `:986`,
  `:1065` (the two debug-only asserts); `openQ4/src/sys/posix/posix_net.cpp` has
  neither

**Stats**

- `src/mpgame/mp/GameState.cpp:263`, `:302`, `:483-486`, `:568-570` — the
  `Init()` calls
- `src/mpgame/mp/stats/StatManager.h:110-111`, `:115` (slab), `:188-207`
  (`rvPlayerStat` members)
- `src/mpgame/mp/stats/StatManager.cpp:134-148` (`GetBlock`), `:141-142`,
  `:326-327`, `:332`, `:344`, `:531-553` (`FreeEvents`, `:544-548`, `:550`),
  `:812` (`SendAllStats`), `:1237-1276` (`UpdateEndGameHud`, `:1251`),
  `:1302-1323` (`PackStats`), `:1325-1345` (`UnpackStats`)
- `src/mpgame/MultiplayerGame.h:903`, `src/mpgame/MultiplayerGame.cpp:1878`,
  `:1984`, `:2030` — `idMultiplayerGame::BuildSummaryListString` (a member of
  `idMultiplayerGame`, not of `rvStatManager`; `StatManager.cpp` is 1345 lines
  long and has no line 1877)
- `src/mpgame/MultiplayerGame.cpp:5692` (`sm_select_player`), `:9768`
  (`GetPlayerTime`)

**Cvars and commands**

- `src/mpgame/gamesys/SysCvar.cpp:75`, `:193-196`, `:201-203`, `:207`, `:537`,
  `:547-549`, `:556`, `:564`, `:618`, `:663` (`si_voteFlags`,
  `CVAR_GAME | CVAR_SERVERINFO | CVAR_INTEGER | PC_CVAR_ARCHIVE`), `:664-674`
  (its help text, which stops at bit 10), `:670`
- `src/mpgame/MultiplayerGame.h:96` (`VOTEFLAG_BUYING` `0x0002`), `:106`
  (`VOTEFLAG_CONTROLTIME` `0x0800`)
- `src/mpgame/gamesys/SysCvar.h:348`
- `src/mpgame/MultiplayerGame.cpp:11` (`g_spectatorChat`), `:8357` (its use)
- `src/mpgame/gamesys/SysCmds.cpp:3448-3485`, `:3483`, `:3492-3495`, `:3496`
- `openQ4/src/framework/Common.cpp:4741` — the engine's own `help` registration;
  `openQ4/src/framework/CmdSystem.cpp:432` — `AddCommand`'s first-wins refusal
- `openQ4/src/framework/KeyInput.cpp:763` (`ExecKeyBinding`, no release form),
  `openQ4/src/framework/Session.cpp:5671` (bindings executed on key down only),
  `openQ4/src/framework/UsercmdGen.cpp:178` (`userCmdStrings[]`), `:197`
  (`_ingameStats` -> `UB_BUTTON5`)
- `src/mpgame/MultiplayerGame.cpp:7130-7135` (`ForceReady_f`), `:7211`
  (`GAME_RELIABLE_MESSAGE_READY`), `:8499`, `:8514-8519` (`ToggleReady`)
- `src/mpgame/MultiplayerGame.h:603` (`ToggleReady` declaration)
- `src/mpgame/MultiplayerGame.cpp:3837` (`CommonRun`), `:4006-4019` (the three
  forced-model `IsModified()` polls), `:4021-4028` (the `updateModels` loop),
  `:4031-4098` (the `g_simpleItems` reassignment loop) — the live-reapply path
  that a serverInfo change does **not** trigger
- `src/mpgame/Player.cpp:174` (`Player_ForcedModelCVarString` definition),
  `:3347` (`UpdateModelSetup`), `:3360-3363` and `:3371-3372` (its six call
  sites), `:3671` (ready anti-clobber), `:4313` (`g_crosshairSize`),
  `:6934`/`:6967`/`:6979`/`:6996` (the two `lastSpectateChange` write sites and
  their two tests; `Player.h:945` declares it), `:7067-7068` (GUI ready token),
  `:8987-8992` (`IMPULSE_17`), `:11040-11045` (`DefaultFov` clamp), `:14633`,
  `:14646` (`si_allowHitscanTint`)
- `src/mpgame/Player.h:654-655`, `:933`, `:938` — the authoritative ready state
- `src/mpgame/Camera.cpp:2202` — unclamped `g_fov` consumer
- `src/mpgame/MultiplayerGame.cpp:45-48` (`teamNames[]`, `"Marine"` then
  `"Strogg"`), `:6683-6685` (`MPLocalizedTeamName`, the reversed id mapping);
  `openQ4/content/baseoq4/pak0/strings/english_code.lang:663-664` and
  `spanish_code.lang:663-664` — the only two mirrors carrying `#str_108025`
  ("Strogg") and `#str_108026` ("Marine")
- `openQ4/src/framework/FileSystem.cpp:5812-5858` (`FileAllowedFromDir`), `:5824`
  (the `.cfg` whitelist entry)

**Retired surfaces**

- `src/mpgame/MultiplayerGame.cpp:5132-5161` — the `admin` rcon-proxy handler
- `src/mpgame/MultiplayerGame.cpp:5441-5602` — the server-admin GUI block
  (`checkAdminPass` at `:5442`), including `populateBanList` at `:5599-5602`
- `src/mpgame/MultiplayerGame.cpp:9016-9031` (the six-name `si_gametype` read
  chain), `:9034-9045` (the seven-case write switch)
- `src/mpgame/MultiplayerGame.cpp:7571` (`ServerStartVote`), `:7600`
  (`ClientStartVote`), `:7644` (`ClientUpdateVote`), `:7753` (`ClientCallVote`),
  `:7814` (`ServerCallVote`); server-side `GetLocalizedString` at `:7844`,
  `:7849`, `:7865`, `:7881`, `:7896`, `:7907`, `:7948`, `:7960`, and the map-name
  path at `:7921-7923`
- `src/mpgame/MultiplayerGame.cpp:2954` (`ServerCallPackedVote`, **kept** and
  repointed), `:3175` (`ClientStartPackedVote`); its three raw English strings at
  `:3020`, `:3038`, `:3047`

**Lag compensation, in the wrong tree**

- `src/game/gamesys/SysCvar.cpp:616-619`
- `src/game/Game_local.h:1161`, `:1163`, `:1170`, `:1177`, `:1245-1250`
- `src/game/Game_local.cpp:4859`, `:9433`, `:9723-9724`
