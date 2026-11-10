# Arena Campaign

> **Development documentation:** This page follows the current source tree and may describe changes newer than the public download. See [release status and released-version guides](release-status.md) before using it with a release package.

> **Experimental.** Multiplayer and the single-player Arena Campaign are
> under active development and are not yet considered stable. Expect rough
> edges, changing behaviour between builds, and bugs. They are not
> representative of the finished feature.

The Arena Campaign is a single-player ladder built from Quake 4's stock
multiplayer maps and openQ4's character bots. It sits beside the original story:
choose **Single Player**, then choose **Mission** for the Quake 4 campaign or
**Arena** for the new circuit.

No internet connection, public server, community map pack, or replacement game
content is required. Arena matches run as private local multiplayer games so
the bots can use the same scoring, team, and match rules as human players.

## How the ladder works

The circuit contains five tiers with four matches in each tier, for twenty
matches in total:

1. The first three matches in a tier are available together.
2. Winning all three unlocks that tier's boss match.
3. Winning the boss match unlocks the next tier.
4. Defeated matches remain available for another attempt.
5. A draw does not award a win or unlock progress; replay it to settle the match.
6. Defeating the Makron in the final boss duel completes the campaign.

Completed matches can be replayed without losing progress. After a result,
**Retry Match** immediately reruns a defeat, **Replay Match** repeats a victory
or draw, and **Next Match** moves to the next match you still have to win —
the rest of the tier first, then the tiers after it. The browser's progress
bar, completion marks, boss accent, and tier briefing keep the route to the
next unlock visible while choosing a match; a tier with some qualifiers won
reads **IN PROGRESS**. A locked boss keeps its identity hidden — from the match
list and the tier briefing alike — until all three qualifiers are won.

## Best results

Every match keeps its **best result**, shown across the foot of the match's
picture in the browser: the outcome, the final score and the difficulty it was
played on, for example **VICTORY 10 - 3 VETERAN**. A match you have not yet
played to a result reads **No result yet**. A victory always beats a draw, and
a draw beats a defeat; between two results with the same outcome, the wider
winning (or narrower losing) margin is better, then the harder difficulty. When
a replay beats the record, the match report marks the score **NEW BEST**.

Only a match played out counts. A match whose opponents left, or that you
abandoned, leaves the record unchanged. Matches won before best results were
kept show **VICTORY** until you replay them. Best results are saved with your
campaign progress, survive restarts, and are cleared by **Reset Progress**.

Arena screens use the standard menu confirm and back controls on keyboard and
controller. The recommended action receives focus when a screen opens: next
match after a victory, retry after a defeat, replay after a draw, and cancel in
the destructive reset prompt. **Escape** or the controller back action dismisses
a result, cancels reset confirmation, or moves back one menu level.

## Match presentation

Arena has its own beginning-to-end match ceremony rather than exposing the
ordinary multiplayer lobby and score-summary flow:

1. **Challenge launch.** Confirming a match expands its challenge card over the
   selected map and then fades into the arena. Input is held during this short
   transition so one confirm press cannot accidentally perform two actions.
2. **Introductions.** Each fighter on the authored roster is presented in turn,
   named over a slow, face-on shot of the fighter themselves. In team matches
   your teammates come first and the opposition last, each card naming the
   side ("TEAMMATE 1 OF 2", "OPPONENT 2 OF 3"). Combatants are locked for the
   whole introduction, so nobody opens fire behind it.
3. **Countdown.** A four-second cinematic countdown follows automatically. There
   is no Ready button and no warmup vote. Combatants stay locked while a
   collision-aware camera sweeps in toward the player, with the tier, the
   match's place in it, the match name and its game type framed over the
   world.
4. **Spawn-in.** Control is held a moment longer while the camera circles your
   own body where it spawned, swings in behind your head, and settles exactly
   onto your first-person view. The announcer counts "three, two, one" over the
   move and **Fight** sounds as control returns. (Clan Arena and Red Rover count
   down their first round themselves.)
5. **The match.** Normal play, with the arena rules the match panel listed.
6. **Final tableau.** The exit condition freezes the whole arena — combatants,
   projectiles, movers and effects all stop where the match ended. The camera
   moves to the unique victor and hands the look controls back: **you** orbit the
   frozen victor freely while the winner is announced, with a restrained
   depth-of-field effect keeping that character sharp. This works whether or
   not you survived the final frag. Nothing moves no matter where you look. A
   draw uses a neutral presentation, does not declare a victor, and is
   announced as a tie.
7. **Scoreboard.** The arena fades down and the full scoreboard takes the
   screen, headed by the match.
8. **Match stats.** The scoreboard fades to the detailed end-of-match statistics.
9. **Match report.** The arena disconnects and a dedicated result ledger expands
   in the Arena browser. Outcome, final score, awards earned, unlocks, and the
   recommended replay, retry, or next action appear in deliberate stages instead
   of all at once.
10. **Campaign update.** Leaving a newly won report reveals the campaign board
    beneath it, then visibly records the completed match, fills the progress
    segment, and pulses any new boss or tier gate. Control returns only after
    the update has settled, with the next useful selection ready.

**Escape** skips straight to the match report from the tableau, the scoreboard
or the stats; so does **fire**, once a beat has been on screen for a moment.
Fire also skips the rest of the introductions. Skipping never changes the
result: it is decided when the match ends and recorded as normal. The
crosshair and status bar stay hidden during every cinematic shot and return
with control.

The cinematic framing used by the entrance and the final tableau is sized from
the actual display. Its bars always reach every screen edge, and they thicken on
narrower or taller displays so the framed picture stays close to a 16:9
cinematic window instead of shrinking to a fixed slice of a 4:3 layout. On 16:9
and wider displays the frame keeps its usual thin profile, and on every aspect
it stops short of the match clock and the surrounding interface. The frame lifts
as control returns.

The match is reported to the campaign at the end of the statistics screen, not
the moment the score freezes. Quitting the game during the tableau, the
scoreboard or the statistics abandons the match: nothing is recorded, and a win
taken that way does not count. Press Escape to skip to the report instead.

## Pausing and leaving a match

An Arena match pauses like a story level. Press Escape (or the controller's
menu button) during a match for the **MATCH PAUSED** menu, which shows the
match, its tier, game type and map, the paused clock and the score:

- **Resume** returns to the match. Escape or the back button does the same.
- **Restart match** asks first, then resets the same match on the spot: no
  reload, everyone respawns, the score and clock go back to zero and the
  introductions play again. Nothing is recorded. If an opponent has left the
  match, the match reloads instead, so the full line-up returns.
- **Settings** opens the normal settings screens. The match stays paused, and
  backing out returns you to the pause menu.
- **Leave match** asks first, then returns you to the Arena browser with a
  **Match abandoned** report that names the match and offers **Retry**.
  Nothing is recorded and your progress is unchanged.

While the pause menu or the settings are open, the bots, the match clock,
projectiles, respawns and round timers all stop. Chat does not pause the match,
because the bots answer it. Once a match has ended, Escape skips the rest of the
end-of-match ceremony to the match report instead.

A match has to be played out to count. Quitting to the menu any other way, for
example with the `disconnect` console command, also leaves the match with a
**Match abandoned** report. Once the match has ended, though, its result is
decided: leaving or quitting the game during the end-of-match ceremony still
records it, as skipping the ceremony would. A match whose opponents all leave (for example when
its bots are removed from the console) ends as **Match aborted**, with nothing
recorded and **Retry** offered.

If a match cannot be started or its result cannot be recorded, the browser
raises a **Match Aborted** report naming the match and the reason instead of
returning silently. The usual cause is another program — often a second copy of openQ4 —
already holding the network port the local server needs.

These ceremonies are exclusive to the single-player Arena Campaign. Private
matches opened from the multiplayer menus retain their normal ready-up,
scoreboard, and review behavior.

Arena matches have no spectator mode and no team picker. The roster, the sides
and the seat count are authored by the campaign, so the join, spectate, and team
controls are refused for the whole match, and no game rule can bench you either:
a campaign Duel is simply a one-on-one deathmatch rather than the multiplayer
tournament mode, and a tied match never puts the trailing fighter out to
sudden-death spectator. In Clan Arena you still sit out the remainder of a round
after being eliminated, which is that mode's own rule, and you return with the
next round.

Any end-of-match awards you earn are listed on the match report beside the score
and any unlock.

**Reset Progress** is unavailable until at least one match has been played to a
result. It clears every Arena win, best result and tier unlock, but asks for
confirmation before changing anything. It does not affect Mission saves, ordinary multiplayer
settings, or achievements.

Each tier raises the base bot skill from 1 to 5. Individual opponents may be
one step easier or harder than the tier baseline to preserve their
personalities and make a roster feel less uniform. The **−** and **+** controls
on the **DIFFICULTY** row shift the campaign challenge while keeping that
relative spread, stepping through **TRAINING**, **ROOKIE**, **VETERAN** (the
default), **NIGHTMARE**, and **IMPOSSIBLE**. Effective bot skill is kept inside
the normal 1-to-5 range, so the lower settings make no further difference in
Boot Camp and the higher ones make none in the Final Gauntlet — those tiers are
already at the ends of the scale. The match panel shows the resulting bot skill
or skill range, so the selected tier, campaign difficulty, and opponent offsets
are visible before the match starts.

## The circuit

| Tier | Match | Map | Game type | Featured roster |
| --- | --- | --- | --- | --- |
| Boot Camp | First Blood | The Fragging Yard (`mp/q4dm1`) | Duel | Bagby |
| Boot Camp | Crossfire | Sandstorm (`mp/q4dm2`) | Deathmatch | Anderson, Bagby, Tetzlaff |
| Boot Camp | Fireteam | The Lost Fleet (`mp/q4dm3`) | Team Deathmatch | Anderson, Bagby, Tetzlaff, Sorg, Strauss |
| Boot Camp | Transfer Test | Bloodwork (`mp/q4dm4`) | Duel | Sorg |
| Ironworks | Thorns | The Rose (`mp/q4dm5`) | Deathmatch | Sorg, Strauss, Hollenbeck |
| Ironworks | Shifting Lines | No Doctors (`mp/q4dm6`) | Red Rover | Sorg, Strauss, Hollenbeck, Marsh, Anderson |
| Ironworks | Last Squad Standing | Over The Edge (`mp/q4dm7`) | Clan Arena | Sorg, Strauss, Hollenbeck, Marsh, Tetzlaff |
| Ironworks | The Marshal | Railed (`mp/q4tourney1`) | Duel | Marsh |
| Blood Circuit | Longest Odds | The Longest Day (`mp/q4dm8`) | Deathmatch | Bidwell, Cortez, Morris, Rhodes |
| Blood Circuit | Campground Clash | Campgrounds Redux (`mp/q4dm9`) | Team Deathmatch | Bidwell, Cortez, Morris, Rhodes, Voss |
| Blood Circuit | Skeleton Crew | Skeleton Crew (`mp/q4dm11`) | Clan Arena | Bidwell, Cortez, Morris, Rhodes, Voss |
| Blood Circuit | Officer's Challenge | The Fragging Yard 1v1 (`mp/q4dm11v1`) | Duel | Voss |
| Strogg Trials | Central Pressure | Central Industrial (`mp/q4xdm10`) | Deathmatch | Gunner, Rhodes, Cortez, Voss |
| Strogg Trials | Red Shift | Stroyent Red (`mp/q4xdm13`) | Red Rover | Gunner, Rhodes, Cortez, Voss, Kane |
| Strogg Trials | Warforged | Warforged (`mp/q4xdm11`) | Team Deathmatch | Gunner, Kane, Sledge, Voss, Rhodes |
| Strogg Trials | Sledgehammer | Verticon (`mp/q4xtourney2`) | Duel | Sledge |
| Final Gauntlet | Last Alliance | Retrophobopolis (`mp/q4xdm14`) | Team Deathmatch | Kane, Sledge, Gunner, Morris, Voss |
| Final Gauntlet | Firewall | Firewall (`mp/q4xdm15`) | Clan Arena | Kane, Sledge, Gunner, Morris, Voss |
| Final Gauntlet | Champion's Circle | Skeleton Crew (`mp/q4dm11`) | Deathmatch | Kane, Sledge, Gunner, Morris, Voss |
| Final Gauntlet | The Makron | Stroggenomenon (`mp/q4xtourney1`) | Duel | Makron |

The team modes use five bots plus the player, giving the matchmaker enough
players for balanced three-versus-three sides. Red Rover moves players between
teams as frags are scored. Clan Arena gives each player one life for the round,
so positioning and survival matter as much as aim.

## Stock-content compatibility

Every campaign map comes from the official Quake 4 files required by openQ4.
The optional `q4cmp` community map pack is deliberately not part of the
progression. The campaign also avoids CTF, DeadZone, and other objective modes:
the current bots fight, navigate, collect items, and obey combat match rules,
but do not yet pursue flags or map objectives.

Bots build navigation from the loaded map's collision at runtime. The first
bot match on a map can therefore spend a brief moment preparing navigation;
there is no separate bot-map download or AAS file to install.

If the Arena screen reports **Missing Required Map**, verify the retail Quake 4
installation and openQ4 content paths using the
[Getting Started guide](getting-started.md). Do not install loose replacement
maps over the campaign maps.
