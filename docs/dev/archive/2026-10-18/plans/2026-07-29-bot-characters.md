# Bot characters, play styles and a real skill model

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Status: implemented. The current subsystem contract and authoring guide live in
[mp-bots.md](../../../mp-bots.md).

## Why

Today every bot on a server plays identically and every skill level plays
almost identically. The whole difficulty model is five numbers in
`rvBot::ResolveSkill` (`Bot.cpp:157-172`) and five consumption sites, and even
the worst of them is lethal. Concretely:

- `turnSpeed` 200..900 deg/s. 200 deg/s is still a snap turn — a human flick is
  roughly 400-800 deg/s. There is no bottom to the curve.
- `aimError` is a **steady-state offset** re-rolled every 400 ms
  (`BOT_AIM_JITTER_MSEC`). The slew in `UpdateAim` converges exactly onto
  `enemy centre + that offset`, so the bot's aim is perfect tracking with a
  fixed bias. There is no tremor, no lag behind a mover, no overshoot, no
  settle.
- The aim point is `GetAbsBounds().GetCenter()` of the **current** position.
  Zero leading: rockets and nails miss every mover at every skill, hitscan
  never misses.
- `UpdateFire` fires the instant the aim is inside a fixed ~16.3 degree
  half-cone (`BOT_FIRE_CONE_DOT 0.96`), with no discipline and no per-weapon
  behaviour.
- The reaction delay is measured from `enemyAcquiredTime`, which only resets
  after the enemy has been out of view for `BOT_REACQUIRE_MSEC` (500 ms).
  **Inside a continuous fight the reaction delay is zero, forever.**
- Nothing is randomised per bot.

This replaces all of that with a data-driven personality system, and moves the
tuning out of C++ constants into content files that ship in `pak0`.

## The three layers

Everything resolves into one flat `botTraits_t` per bot per spawn.

1. **Skill level 1..5** — the baseline curve. Every attribute has a value at
   every level; fractional levels (what `bot_skillVariance` produces) are
   linearly interpolated between the two bracketing rows. This layer alone is
   a complete, playable bot, and is exactly what `bot_characters 0` gives you.
2. **Play style** — a named archetype that biases the baseline. A style says
   *what a bot wants to do*, never *how well it does it*: a skill 1 sniper and
   a skill 5 sniper both hold range and both prefer the rail gun, and only one
   of them hits with it. Six ship: `rusher`, `sniper`, `roamer`, `hunter`,
   `ambusher`, `skirmisher`.
3. **Character** — identity. Display name, player model, skill band, personal
   per-attribute bias and per-skill-level overrides. Character-owned chat is
   stored separately and merged into the identity by name.

Layers 2 and 3 do not restate the attribute list. They carry sparse modifier
statements — `set`, `add`, `scale` — naming a trait field by the same word used
in `botTraits_t`, resolved through a static field table. Adding an attribute is
one row in that table and one line in the baseline curve; no parser, style or
character file has to know it exists.

Resolution order, and it matters because `scale` composes with whatever came
before:

```
baseline( EffectiveSkill( bot_skill, bot_skillVariance, clientNum ) )
  -> style body
  -> style  skill <n> { } block
  -> character body
  -> character skill <n> { } block
```

Each statement is applied in file order and the field is clamped to its table
range immediately after, so a typo in content cannot produce a bot that turns
at 90000 degrees a second.

Weapon biases are the one thing not reachable through the field table: they are
named entries, not scalars, and they **merge** rather than overwrite, so a
character expressing an opinion about one weapon leaves the rest of its style's
opinions intact.

## The trait table

All 39 traits are floats, including the millisecond and degree fields. That
keeps the modifier system uniform — one table, one apply path, one clamp — and
the handful of consumers that want an int cast at the point of use.

These are the tuning defaults. Where an existing `Bot.cpp` constant covers the
same ground it is named in the notes so the change is legible.

### Vision and reaction

| Field | 1 | 2 | 3 | 4 | 5 | Clamp | Meaning |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `sightRange` | 1200 | 1700 | 2200 | 2600 | 3000 | 128..8192 | units; beyond this a player is not noticed. Was 1400..3000. |
| `fov` | 130 | 145 | 155 | 170 | 180 | 60..360 | degrees, full cone. The low end is broad enough to join nearby fights without gaining rear vision. |
| `reactionMsec` | 460 | 390 | 320 | 220 | 140 | 0..2000 | fresh-sighting delay. Low skills were shortened after play showed stacked trigger gates made them too passive. |
| `reactionVarianceMsec` | 180 | 150 | 120 | 80 | 45 | 0..1000 | +/- spread rolled per acquisition, so it is never a fixed tick. |
| `reacquireMsec` | 150 | 250 | 400 | 550 | 700 | 0..4000 | out of view longer than this and the next sighting is a *fresh* one. Replaces the flat `BOT_REACQUIRE_MSEC 500`. |
| `reacquireFraction` | 1.00 | 0.85 | 0.70 | 0.55 | 0.40 | 0..1 | fraction of the full reaction paid on a re-acquisition inside that window. **This is the fix for the zero-reaction bug.** |
| `peripheralAngle` | 60 | 65 | 70 | 75 | 80 | 5..180 | degrees off view centre at which the peripheral penalty is full. |
| `peripheralPenaltyMsec` | 340 | 290 | 240 | 160 | 90 | 0..2000 | added reaction at that angle, scaled linearly from 0 dead ahead. |

### Aim

| Field | 1 | 2 | 3 | 4 | 5 | Clamp | Meaning |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `turnSpeed` | 170 | 280 | 420 | 640 | 900 | 20..2000 | deg/s cap on the slew. The low half stays visibly slow without taking too long to enter a fight. |
| `turnAccel` | 750 | 1350 | 2400 | 4800 | 9000 | 50..40000 | deg/s^2. Low values make the view lag then overshoot. |
| `turnDamping` | 0.42 | 0.55 | 0.70 | 0.90 | 1.10 | 0.1..3.0 | damping ratio. Below 1.0 overshoots and hunts; 1.0 settles cleanly. |
| `aimTrackTimeConst` | 0.40 | 0.30 | 0.22 | 0.14 | 0.08 | 0.01..2.0 | seconds; first-order lag of the *believed* target position behind the real one. |
| `aimTremorDeg` | 4.2 | 3.0 | 2.1 | 1.2 | 0.5 | 0..30 | continuous tremor amplitude. Replaces the 400 ms step offset `aimError` 7.0..0.5. |
| `aimTremorRateHz` | 0.6 | 0.8 | 1.1 | 1.4 | 1.8 | 0.05..10 | how fast the tremor wanders. Slow and wide reads as an unsteady hand. |
| `aimTrackError` | 2.8 | 2.1 | 1.5 | 0.8 | 0.3 | 0..20 | degrees of cross-view lag per 100 deg/s of target angular rate. |
| `aimSettleMsec` | 240 | 200 | 170 | 110 | 60 | 0..2000 | how long the aim must sit inside the cone before the trigger is allowed. |
| `aimLead` | 0.10 | 0.35 | 0.60 | 0.82 | 0.97 | 0..1.5 | how correctly a mover is led with a projectile weapon. **New** — today it is 0 at every skill. |
| `aimLeadError` | 0.45 | 0.32 | 0.20 | 0.11 | 0.05 | 0..2 | random fraction of the computed lead added or removed per shot. |

### Trigger

| Field | 1 | 2 | 3 | 4 | 5 | Clamp | Meaning |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `fireConeDeg` | 14.0 | 10.0 | 6.5 | 4.0 | 2.0 | 0.25..45 | half angle. Low skill fires early and misses; high skill waits and hits. |
| `holdFireTurnRate` | 1000 | 700 | 500 | 340 | 220 | 10..4000 | deg/s; will not fire while the view slews faster than this. At skill 1 it effectively never holds. |
| `burstMinMsec` | 480 | 380 | 300 | 210 | 140 | 30..4000 | automatic weapons: shortest burst. |
| `burstMaxMsec` | 1400 | 1000 | 700 | 460 | 300 | 30..8000 | longest burst. Skill 1 holds the trigger; skill 5 taps. |
| `burstPauseMsec` | 220 | 180 | 140 | 110 | 80 | 0..2000 | gap between bursts, during which the aim re-settles. |

Note the duty cycle: skill 1 is 1400/(1400+220) = 86 % trigger-down, skill 5 is
300/(300+80) = 79 %. Low skill *fires more* and hits far less, which is the
intended read — spray and pray, not a nerfed rate of fire.

### Mistakes

| Field | 1 | 2 | 3 | 4 | 5 | Clamp | Meaning |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `mistakeChance` | 0.45 | 0.32 | 0.20 | 0.10 | 0.03 | 0..1 | chance a combat decision comes out wrong. |
| `mistakeMsec` | 900 | 750 | 600 | 450 | 300 | 50..5000 | how long one mistake lasts before recovery. |

A mistake is rolled once on each enemy acquisition and again every
`mistakeMsec` while engaged. On a hit, pick one uniformly:

- **lose tracking** — freeze the belief position for `mistakeMsec`;
- **mistimed shot** — ignore `aimSettleMsec` for the next trigger decision;
- **wrong weapon** — skip the next `UpdateWeapon` range check and keep what is
  in hand;
- **late dodge** — double `dodgeReactMsec` for `mistakeMsec`.

### Movement and engagement

| Field | 1 | 2 | 3 | 4 | 5 | Clamp | Meaning |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `strafeChance` | 0.15 | 0.30 | 0.45 | 0.58 | 0.70 | 0..1 | dodging while fighting. Matches the existing 0.15..0.70. |
| `dodgeReactMsec` | 900 | 700 | 500 | 320 | 180 | 0..3000 | delay between taking fire and starting to dodge it. |
| `jumpChance` | 0.05 | 0.12 | 0.22 | 0.34 | 0.45 | 0..1 | chance a dodge becomes a jump instead of a sidestep. |
| `combatRange` | 500 | 500 | 500 | 500 | 500 | 32..4096 | units. Flat by design — this is the axis **styles** own. Matches `BOT_COMBAT_RANGE`. |
| `rangeDiscipline` | 0.20 | 0.35 | 0.50 | 0.68 | 0.85 | 0..1 | how hard it works to stay at `combatRange`. |
| `aggression` | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 | 0..1 | push in vs back off on an even trade. Style-owned. |
| `patience` | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 | 0..1 | hold a position vs go looking. Style-owned. |
| `retreatHealth` | 0.15 | 0.20 | 0.25 | 0.30 | 0.35 | 0..1 | fraction of max health below which it breaks off for health. |
| `pursuit` | 0.30 | 0.42 | 0.55 | 0.68 | 0.80 | 0..2 | scales `BOT_ENEMY_MEMORY_MSEC`: memory = 3000 * (0.5 + pursuit). |
| `itemFocus` | 0.25 | 0.38 | 0.50 | 0.65 | 0.80 | 0..2 | how much an item goal outweighs an enemy goal. |

### Tactical personality

Most of these traits are flat across skill and styles or characters move them
to create different fights. Initiative and suppression also shape the low-skill
trigger: novices accept imperfect shots and waste rounds through cover.

| Field | 1 | 2 | 3 | 4 | 5 | Clamp | Meaning |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `initiative` | 0.80 | 0.70 | 0.58 | 0.50 | 0.50 | 0..1 | willingness to accept an imperfect shot; changes reaction, effective cone, settle and allowed slew without improving aim. |
| `targetStickiness` | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 | reluctance to abandon the current target for a better-scoring one. |
| `opportunism` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | preference for wounded targets; 1 preserves the original health weighting. |
| `vengefulness` | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | preference for the opponent that last killed this bot. |
| `suppressionMsec` | 1200 | 700 | 250 | 0 | 0 | 0..2000 | time spent firing at the last believed position after contact enters cover. |
| `strafeRhythmMsec` | 400 | 400 | 400 | 400 | 400 | 100..3000 | base interval between combat strafe direction changes. |
| `strafeRhythmVarianceMsec` | 800 | 800 | 800 | 800 | 800 | 0..3000 | random spread added to the strafe interval. |
| `weaponSwitchMsec` | 500 | 500 | 500 | 500 | 500 | 100..3000 | delay between weapon-choice re-evaluations. |
| `aimHeight` | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | -0.4..0.4 | personal vertical aim bias as a fraction of target height. |

`aggression`, `patience` and seven tactical-personality fields are flat across
skill on purpose. They are taste, not competence. Initiative and suppression
are intentionally low-skill-shaped because spraying a marginal angle is a
readable weakness as well as a cure for passive novice bots.

### Decision quality and chat

| Field | 1 | 2 | 3 | 4 | 5 | Clamp | Meaning |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `weaponSkill` | 0.20 | 0.38 | 0.55 | 0.75 | 0.92 | 0..1 | chance the range-correct weapon is chosen over merely the first available. |
| `targetSelection` | 0.25 | 0.40 | 0.55 | 0.72 | 0.88 | 0..1 | chance the best enemy is chosen rather than simply the nearest. |
| `chatiness` | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 | 0..1 | chance a chat-worthy event produces a line. Character-owned. |
| `chatDelayScale` | 1.60 | 1.35 | 1.10 | 0.90 | 0.75 | 0.1..5 | multiplier on the thinking pause and CPM typing delay. A worse player takes longer to type. |

### Sanity check against today

At skill 3 the bot is roughly where the current default sits but with real
texture: it turns at 420 deg/s instead of 550, carries 2.1 degrees of moving
tremor instead of a 2.6 degree fixed bias, waits 170 ms on target before
shooting instead of firing instantly, pays 320 ms on a fresh sighting and
224 ms on a re-acquisition instead of 260 ms once per lifetime, and leads
projectiles at 60 % correctness instead of not at all.

Skill 1 is genuinely poor but no longer passive: it notices you inside a 130
degree cone at 1200 units, takes 460 ± 180 ms to react and pays that again
nearly every time you break line of sight, tracks with a 0.40 s lag and 4.2
degrees of tremor, turns at 170 deg/s with an underdamped slew that overshoots,
uses 0.80 initiative to turn its raw 14 degree / 240 ms trigger values into an
effective 18.2 degree cone and 96 ms settle, barely leads, and gets one combat
decision in two wrong.

Skill 5 is sharp but not an aimbot: 140 ± 45 ms reaction that it still re-pays
at 40 % on a re-peek, 0.08 s belief lag, 0.5 degrees of tremor it can never
switch off, a 2 degree cone it will not shoot outside of, a 60 ms settle, and
97 % lead correctness with a 5 % random error — so a strafing target at range
still survives the occasional rocket.

## File format

Text, brace blocks, parsed with `idLexer` under `DECL_LEXER_FLAGS`. They are not
decl types: the design required no engine change, and `DECL_LEXER_FLAGS` carries
`LEXFL_NOFATALERRORS`, so a malformed content file warns and is skipped instead
of killing the server.

```
content/baseoq4/pak0/botfiles/styles/<style>.style
content/baseoq4/pak0/botfiles/characters/<name>.bot
content/baseoq4/pak0/botfiles/chats/<name>.chat
```

These extensions and subdirectories are independent of the pre-existing
`botfiles/bots/*.c`, `botfiles/items.c` and `botfiles/weapons.c`, which are dead
Quake 3 format prototypes that nothing parses; the new readers can never see
them. No build-system change is needed — `tools/build/openq4_pak.py` enumerates
`content/baseoq4/pak0` with `rglob("*")` and filters only binary suffixes, so new
text content is packed automatically.

### Grammar

```
style "<name>" {
    description  "<text>"
    inherit      "<other style>"        // optional, resolved after every file is read

    set    <field> <number>             // field  = number
    add    <field> <number>             // field += number
    scale  <field> <number>             // field *= number

    weapon "<weapon class>" <bias>      // 1.0 neutral, 0.0 last resort

    skill <1..5> { <same statements> }  // layered after this file's body
}

character "<display name>" {
    description  "<text>"
    inherit      "<style>"              // the style layer; optional
    skillBand    <min> <max>            // lowest and highest bot_skill this character is picked for
    model        "<playerModel decl>"   // non-team games
    modelMarine  "<playerModel decl>"   // team games, marine side
    modelStrogg  "<playerModel decl>"   // team games, strogg side

    set/add/scale <field> <number>
    weapon "<weapon class>" <bias>
    skill <n> { ... }
}

characterChat "<display name>" {
    chat <event> {
        "line"
        "line"
    }

    reply <rule name> {
        priority  <0..100>
        source    any | player | bot
        addressed either | required | forbidden

        trigger "<word or phrase>"
        trigger "<another phrase>"

        "response line"
        "another response"
    }
}
```

Rules the parser must hold to:

- **Unknown keys warn and continue.** `common->Warning( "bot character '%s': unknown key '%s'", file, token.c_str() )`, then `SkipRestOfLine`, or `SkipBracedSection` when the next token is `{`. Never fatal.
- **Unknown trait field names warn and are skipped**, as do out-of-range `skill <n>` indices.
- A **fresh `idLexer` per file**, or `FreeSource()` between files —
  `idLexer::LoadFile` calls `common->Error` if a script is already loaded.
- `LoadFile` with `OSPath = false` so the read goes through
  `fileSystem->OpenFileRead` and resolves inside pk4s.
- Load from a top-level init path only. `idLexer::LoadFile` silently prefixes
  the path with the process-global static `idLexer::baseFolder` when it is
  non-empty, so loading from inside a decl parse would read the wrong place
  with no diagnostic.
- Chat event words are case-insensitive: `entergame`, `levelstart`, `kill`,
  `killGauntlet`, `killStreak`, `revenge`, `death`, `deathAccident`,
  `itemDenied`, `leadTaken`, `leadLost`, `matchWin`, `matchLose`, `farewell`.
- A `characterChat` owner is matched case-insensitively to a loaded character.
  An unknown owner warns and is ignored; it never creates an incomplete
  character. The shipped `.bot` files contain no inline chat.
- A chat line longer than `BOT_CHAT_MAX_LEN` (160) warns and is dropped at load
  rather than silently vanishing at broadcast time.
- A line starting with `#` is **rejected at load**:
  `ProcessChatMessage` runs the text through `common->GetLocalizedString`, so
  `#str_` would be substituted out from under the author.

### Worked example: a style

`content/baseoq4/pak0/botfiles/styles/sniper.style`

```
// Holds range and trades with hitscan.  Patient, immobile, and useless in a
// corridor - which is the point: a server full of snipers should lose to a
// server full of rushers on q4dm1.

style "sniper" {
	description	"holds range and trades with hitscan"

	set	combatRange		1400
	set	aggression		0.28
	set	patience		0.85

	scale	strafeChance		0.65
	scale	jumpChance		0.55
	add	rangeDiscipline		0.15

	// Takes its time and will not shoot at anything it is not sure of.
	scale	aimSettleMsec		1.30
	scale	fireConeDeg		0.70
	scale	reactionMsec		1.08

	// Standing still means the view is already roughly where it needs to be.
	scale	aimTrackTimeConst	0.85

	add	retreatHealth		0.08
	scale	itemFocus		1.10
	scale	pursuit			0.70

	weapon	"weapon_railgun"		2.00
	weapon	"weapon_lightninggun"		1.25
	weapon	"weapon_machinegun"		1.15
	weapon	"weapon_rocketlauncher"		0.85
	weapon	"weapon_shotgun"		0.35
	weapon	"weapon_gauntlet"		0.20

	// A bad sniper is worse than a bad anything else: it stands still at range
	// and cannot hit, so give the low levels back some willingness to move.
	skill 1 {
		scale	strafeChance		1.50
		scale	combatRange		0.75
	}
	skill 2 {
		scale	strafeChance		1.25
	}

	// At the top the discipline is the weapon.
	skill 5 {
		scale	aimSettleMsec		1.10
		add	aimLead			0.02
	}
}
```

### Worked example: character mechanics

`content/baseoq4/pak0/botfiles/characters/voss.bot`

```
// Voss - Rhino Squad's field leader: controlled, protective, and decisive.

character "Voss" {
	inherit		"roamer"
	description	"calm field leader who values discipline over heroics"

	skillBand	3 5

	model		"model_player_marine_voss"
	modelMarine	"model_player_marine_voss"
	modelStrogg	"model_player_kane_strogg"

	// Voss reads the whole map instead of waiting on one firing lane.  He holds
	// useful ground, protects his health and refuses to turn one kill into an
	// undisciplined chase.
	set	combatRange		720
	scale	aggression		0.84
	add	patience		0.15
	scale	pursuit			0.75
	add	retreatHealth		0.08
	add	rangeDiscipline		0.06
	scale	jumpChance		0.80

	// His edge is judgment, not superhuman aim.
	scale	targetSelection		1.06

	// Talks rarely, but an order arrives while it can still matter.
	set	chatiness		0.30
	scale	chatDelayScale		0.90

	weapon	"weapon_machinegun"	1.15
	weapon	"weapon_railgun"	1.10

	skill 5 {
		add	targetSelection		0.03
	}
}
```

### Worked example: a character voice

`content/baseoq4/pak0/botfiles/chats/voss.chat`

```
// Voss's voice remains independently editable from his combat tuning.

characterChat "Voss" {
	chat entergame {
		"Voss here. Watch your lanes."
		"Get set. Nobody runs off alone."
	}
	chat levelstart {
		"$map. Check the routes before you commit."
	}
	chat kill {
		"$other overcommitted. Don't do the same."
		"I had the angle."
		"One down. Eyes on the next."
	}
	chat killGauntlet {
		"You came in too close, $other."
	}
	chat killStreak {
		"Three down. No heroics."
	}
	chat revenge {
		"We're even. Stay focused."
	}
	chat death {
		"Good shot. I gave you the angle."
		"The $weapon found a gap."
	}
	chat deathAccident {
		"My fault. I rushed it."
	}
	chat itemDenied {
		"$other has the $item. Don't contest blindly."
	}
	chat leadTaken {
		"Ahead now. No heroics."
	}
	chat leadLost {
		"$other's ahead. Change the approach."
	}
	chat matchWin {
		"Solid work. No wasted risks."
	}
	chat matchLose {
		"We lost control early. That's on me."
	}
	chat farewell {
		"Voss out. Keep your heads down."
	}
}
```

## The aim model

`dt` is `MS2SEC( gameLocal.GetMSec() )` throughout. All of this replaces the
body of `rvBot::UpdateAim` and `rvBot::UpdateFire`.

**1. Belief.** The bot aims at where it *thinks* the target is, which trails
where the target actually is:

```
alpha    = 1 - exp( -dt / aimTrackTimeConst )
believed += ( truePos - believed ) * alpha
```

Snap `believed` to `truePos` on a fresh acquisition so the bot does not start
an engagement aiming at the last fight's position. While a **lose tracking**
mistake is active, skip the update entirely.

**2. Lead.** Only for projectile weapons. The test is
`self->weapon->spawnArgs.GetString( "def_projectile", "" )[0] != '\0'` — *not*
`!wfl.attackHitscan`, which is false for the gauntlet and the lightning gun
even though both are instant-hit. Speed comes from
`idProjectile::GetVelocity( gameLocal.FindEntityDefDict( projName, false ) ).x`
so the `_mp` retune is picked up (rocket 935 not 900, nail 1400 not 1200).

```
flight    = |aimPoint - eye| / speed          // two fixed-point iterations is plenty
relVel    = targetVel - ownVel * (1 - aimLead)   // own-motion compensation rides the same knob
lead      = relVel * flight * aimLead * ( 1 + CRandomFloat() * aimLeadError )
aimPoint  = believed + lead
```

`idProjectile::GetGravity` is non-zero only for `projectile_grenade` and
`projectile_napalm`; for those two, drop the linear lead and bias the weapon
choice away instead. MP forbids speed ramps (`Projectile.cpp:370-374` asserts
`!gameLocal.isServer` when `speed_end` is present), so a single constant speed
is the whole flight model.

**3. Tracking error.** A lag *across* the view, not noise: the faster the
target crosses, the further behind the bot's aim sits.

```
angVel   = |angle(aimPoint) - angle(aimPointLastFrame)| / dt      // deg/s, low-passed over ~4 frames
trackErr = aimTrackError * angVel / 100
```

applied as an offset opposite the target's screen-space direction of travel.

**4. Tremor.** Continuous and smooth, so it reads as a hand rather than as
white noise. Two octaves, phases seeded from the bot's client number so no two
bots shake in step:

```
w      = 2*pi * aimTremorRateHz
tremor = aimTremorDeg * ( 0.65*sin( w*t + p0 ) + 0.35*sin( 2.37*w*t + p1 ) )
```

separately for pitch and yaw with four different phases. The 2.37 is
deliberately irrational-ish so the two octaves never re-align into a beat.

`desired = angles( aimPoint - eye ) + trackErr + tremor`.

**5. Turn.** A damped second-order slew, which is what produces overshoot and
hunting at low skill and a clean settle at high skill:

```
wn     = turnAccel / turnSpeed                      // natural frequency, keeps the two knobs consistent
err    = AngleDelta( desired[i], aim[i] )
accel  = wn*wn*err - 2*turnDamping*wn*rate[i]
rate[i]= ClampFloat( -turnSpeed, turnSpeed, rate[i] + accel*dt )
aim[i] = AngleNormalize180( aim[i] + rate[i]*dt )
```

for pitch and yaw. `rate` is new per-bot state and must be zeroed in
`rvBot::OnSpawn`. Pitch still clamps to ±85 and roll is still forced to 0, and
`cmd.angles[i] = ANGLE2SHORT( aim[i] - self->GetDeltaViewAngles()[i] )` is
unchanged.

**6. Reaction.** Computed once per acquisition, not per frame:

```
offAxis  = angle between the view forward and the direction to the target, at the moment of sighting
periph   = peripheralPenaltyMsec * ClampFloat( 0, 1, offAxis / peripheralAngle )
base     = fresh ? reactionMsec : reactionMsec * reacquireFraction
fireTime = gameLocal.time + base + CRandomFloat()*reactionVarianceMsec + periph
```

"Fresh" means a different player, or the same player unseen for longer than
`reacquireMsec`. A re-acquisition inside that window still pays
`reacquireFraction` of the cost — that is the fix for the zero-reaction bug,
and it is why `reactionMsec` at skill 5 rose from 70 to 140.

**7. Trigger.** The fire gate and the aim point must agree, or the bot aims at
the lead point and refuses to shoot at the centre:

```
onTarget = angle( aimForward, aimPoint - eye ) <= fireConeDeg
           && |rate| <= holdFireTurnRate
onTargetMsec  = onTarget ? onTargetMsec + GetMSec() : 0
mayFire = gameLocal.time >= fireTime
          && visible this frame
          && ( onTargetMsec >= aimSettleMsec || mistimed-shot mistake active )
          && burst allows
```

Burst state is per-bot: on the first `mayFire` frame roll a burst length in
`[burstMinMsec, burstMaxMsec]`, hold `BUTTON_ATTACK` for it, then release for
`burstPauseMsec`. Weapons that fire one shot per press (rail gun, shotgun,
rocket launcher) ignore the burst window and just obey the settle — the
distinction is `rvWeapon::spawnArgs` `"fireRate"` relative to the frame time,
or simply a per-weapon flag on the preference list.

## Chat

Server-side only, broadcast through
`gameLocal.mpGame.ProcessChatMessage( clientNum, teamOnly, name, text, NULL )`,
which asserts `!gameLocal.isClient` and produces a line indistinguishable from
a human's. **`ProcessChatMessage` is currently private
(`MultiplayerGame.h:550`) and has to be moved to the public block** — the only
engine-adjacent change this design needs, and it is a game-repo header, not the
engine.

Do not route through `Cmd_Say` (every bot would speak as the host) and do not
hook `ReceiveDeathMessage` (its local branch never runs on a dedicated server,
so bots would be silent there).

### Events and their sources

| Event | Key word | Fired from |
| --- | --- | --- |
| `BOTCHAT_ENTERGAME` | `entergame` | `rvBotManager::OnSpawnPlayer`, first spawn only |
| `BOTCHAT_LEVELSTART` | `levelstart` | new `rvBotManager::OnMatchStart`, called from `rvGameState::NewState` case `GAMEON` (`mp/GameState.cpp:514`) |
| `BOTCHAT_KILL` | `kill` | new `rvBotManager::OnPlayerDeath`, called beside `statManager->Kill` (`MultiplayerGame.cpp:2712`) |
| `BOTCHAT_KILL_GAUNTLET` | `killGauntlet` | same hook, when `methodOfDeath` is the gauntlet slot |
| `BOTCHAT_KILL_STREAK` | `killStreak` | same hook, at 3 kills without dying |
| `BOTCHAT_KILL_REVENGE` | `revenge` | same hook, when the victim is the bot's own `lastKiller` |
| `BOTCHAT_DEATH` | `death` | same hook, bot is the victim and `killer` is another player |
| `BOTCHAT_DEATH_ACCIDENT` | `deathAccident` | same hook, `killer` NULL or self |
| `BOTCHAT_ITEM_DENIED` | `itemDenied` | `rvBot::AbandonGoal` when the goal item was taken by a player inside the last second |
| `BOTCHAT_LEAD_TAKEN` | `leadTaken` | new server-side rank tracking in `rvBotManager::Think` — `idMultiplayerGame::UpdateLeader` is declared but never defined, and the `CommonRun` lead logic is local-player-only |
| `BOTCHAT_LEAD_LOST` | `leadLost` | same |
| `BOTCHAT_MATCH_WIN` | `matchWin` | new `rvBotManager::OnMatchEnd`, `rvGameState::NewState` case `GAMEREVIEW` (`mp/GameState.cpp:622`) |
| `BOTCHAT_MATCH_LOSE` | `matchLose` | same |
| `BOTCHAT_FAREWELL` | `farewell` | `rvBotManager::RemoveBot`, before the slot is released |

Every round-based subclass overrides `NewState`; verify all of them reach the
hook (`rvTourneyGameState` calls the base at `mp/GameState.cpp:1907`).

### Tokens, selection and throttling

Lines may use `$self`, `$other`, `$weapon`, `$map` and `$item`. A candidate
requiring a token that the event cannot supply is skipped rather than emitting
a partial sentence. `$map` is available for every event, combat events provide
opponent and weapon context, and `$item` belongs to `itemDenied`.

Selection is uniform over the event's lines excluding the one used last
(`rvBotCharacter::lastChat[]`), so nothing ever repeats back to back. A
character with no lines for an event says nothing — silence is a valid answer
and callers must not invent a fallback.

The shipped content gives all sixteen characters eight alternatives for every
one of the fourteen events: 112 lines per character and 1,792 in total. The
parser still permits smaller add-on banks and intentional silence.

### Triggered replies

`reply` blocks extend the same character voice with bounded phrase matching.
They are evaluated after an accepted typed player message or ordinary
event-driven bot message has passed through `ProcessChatMessage`. Voice macros,
server text, spectator-only messages and generated replies do not enter the
matcher.

The shipped banks use nine rules in descending intent priority: `help`,
`goodGame`, `challenge`, `greeting`, `thanks`, `praise`, `apology`, `farewell`
and the name-addressed fallback `direct`. `source any` allows either a person
or another bot to start the exchange. The first eight use `addressed either`;
`direct` uses `addressed required` and the character's display name as its
trigger.

Matching strips Quake colour escapes, lower-cases ASCII text, replaces
punctuation with word boundaries and collapses whitespace. Triggers therefore
match contiguous whole words rather than substrings. Eligible rules are ranked
by priority and then normalised trigger length; file order breaks a remaining
tie. The chosen rule randomises its responses and excludes the immediately
previous line. A named bot is preferred, but only one bot may queue a response
to any source message.

Parser limits keep add-on content bounded: 32 rules per character, 32 triggers
and 32 responses per rule, and 64 normalised characters per trigger. Priority
is clamped to 0..100. Reply responses accept only `$self`, `$other` and `$map`,
and invalid tokens are rejected at load.

Replies do not replace a pending event line. They use the normal character
typing delay and existing per-client/global flood throttles, with an additional
per-source cooldown and a reduced chance for unaddressed bot speakers. A
provenance bit follows the queued line into `ProcessChatMessage`; it is false
for generated replies, which is the hard loop-prevention boundary.

Team messages consider only same-team bots and produce team replies. The
server-supplied user-info name populates `$other`, never the untrusted display
name carried beside incoming chat text.

Fifteen characters ship four lines in every reply rule. Kane ships two terse
lines in every rule. The 558 reply lines bring the complete authored dialogue
count to 2,350 without changing the existing 1,792 event lines.

Delay after the event is the `bot_chatDelay` thinking pause plus the line's
visible character count at `bot_chatCPM`, all multiplied by
`traits.chatDelayScale` and given a small random jitter. Formatting escapes do
not count, the result is clamped to 750..5000 ms, and `isChatting` stays set
during the wait so Quake 4's existing `mtr_icon_chatting` appears above the bot.
The line is queued on the bot and sent when the timer expires.

Throttles, because **the engine has no chat flood protection anywhere** and
`idAsyncServer::SendReliableMessage` drops a client whose reliable queue
overflows — unbounded bot chatter can kick real players off a server:

- per bot: `BOT_CHAT_CLIENT_THROTTLE_MSEC` 6000
- server wide: `BOT_CHAT_GLOBAL_THROTTLE_MSEC` 1200
- `bot_chat 2` halves both and adds 0.35 to `chatiness`
- `bot_chat 0` suppresses everything

Team chat is only ever used when `gameLocal.IsTeamGame()` —
`ProcessChatMessage` does not guard that itself, and `team = true` in DM colours
everyone as Marine and restricts delivery by the team field.

## Cvars

| Cvar | Default | Flags | Effect |
| --- | --- | --- | --- |
| `bot_chat` | `1` | `CVAR_GAME｜CVAR_ARCHIVE｜CVAR_INTEGER` | 0 off, 1 normal, 2 chatty |
| `bot_chatDelay` | `600` | `CVAR_GAME｜CVAR_ARCHIVE｜CVAR_INTEGER` | initial thinking pause before typing, in ms |
| `bot_chatCPM` | `900` | `CVAR_GAME｜CVAR_ARCHIVE｜CVAR_INTEGER` | base visible characters typed per minute |
| `bot_characters` | `1` | `CVAR_GAME｜CVAR_ARCHIVE｜CVAR_BOOL` | 0 disables character files; bots run the plain skill curve |
| `bot_forceCharacter` | `""` | `CVAR_GAME` | forces every bot onto one character |
| `bot_skillVariance` | `0` | `CVAR_GAME｜CVAR_ARCHIVE｜CVAR_FLOAT` | per-bot random skill spread, 0..2 levels |
| `bot_debugAim` | `0` | `CVAR_GAME｜CVAR_INTEGER` | logs aim and fire decisions for tuning |

Declared as `extern idCVar` in `gamesys/SysCvar.h` beside the existing bot block
(`:476-482`) and defined in `gamesys/SysCvar.cpp` beside `:719-725`. In
`SysCvar.cpp` the quoted name starts at column 44, the quoted default at 80 and
the flags at 96, hard tabs at width 4. Range arguments go **after** the
description.

Anything a launch harness needs to set must carry `CVAR_ARCHIVE`: a
command-line `+set` never reaches a `CVAR_GAME` cvar, because the game DLL
registers it after the engine has parsed the command line, so only archived
values survive through `openQ4Config.cfg`.

`bot_forceCharacter` is deliberately not archived — it is a debugging knob, and
a server that archived it would put a whole roster of clones on the field.

## Commands

| Command | Effect |
| --- | --- |
| `addbot [name] [skill]` | Add one bot, optionally with a per-bot skill override that bypasses `bot_skill` and `bot_skillVariance` |
| `botcharacters` | List loaded characters with style, skill band and which bot has each |
| `botreload` | Re-parse the style, character and chat files without a map change |
| `botlist` | Extended: character, style and effective skill per bot |

Registered in `idGameLocal::InitConsoleCommands` beside the existing bot block
(`SysCmds.cpp:3632-3637`), `CMD_FL_GAME`. Teardown is the blanket
`RemoveFlaggedCommands( CMD_FL_GAME )`, so no removal code is needed.
`botcharacters` should take the file-scope `ArgCompletion_DefFile` shape if a
name argument is added later.

## Loading, lifetime and reload

Characters describe opponents, and opponents outlive a map change — bots hold
their client slots across one. So this is **game init** state, not map state,
and the model to copy is the viseme table (`FAS_Init` / `FAS_Shutdown`).

```
idGameLocal::Init      (Game_local.cpp:652, beside FAS_Init)      -> botCharacterManager.Init();
idGameLocal::Shutdown  (Game_local.cpp:703, beside FAS_Shutdown)  -> botCharacterManager.Shutdown();
```

`rvBotManager::Init` and `rvBotManager::Shutdown` are declared and defined but
**never called from anywhere in the repo**. `botCharacterManager` is the first
heap-owning bot state, so this wiring has to be added rather than assumed, and
it has to be pinned by a test.

`Init` enumerates through the file system so pk4s and mods work:

```
fileSystem->ListFiles( "botfiles/styles",     ".style" )
fileSystem->ListFiles( "botfiles/characters", ".bot" )
fileSystem->ListFiles( "botfiles/chats",      ".chat" )
```

with a mandatory `fileSystem->FreeFileList` after each — the list is
engine-allocated and the game module runs under `RV_UNIFIED_ALLOCATOR`, so
freeing it any other way corrupts the heap. Styles are read first, then
characters, then chat banks; `ResolveInheritance()` runs last and links
`inherit` names to pointers in a second pass so file order does not matter.
Chat banks therefore merge only after their owning characters exist. An
unresolved `inherit` or chat owner warns and leaves that layer empty.

`Reload()` drops styles, characters and chat banks and re-runs that load order,
then re-binds every live bot to the character with the same name where it still
exists. A bot whose character vanished picks a new one. Traits re-resolve on the
next `rvBot::Think`, so there is no separate propagation step.

`rvBot` holds `const rvBotCharacter *character` and calls
`botCharacterManager.ReleaseCharacter()` from `rvBot::Shutdown`, so a kicked
bot's identity returns to the pool. `PickCharacter` falls back — unused in
band, then any in band, then any at all — because a full roster must never stop
a bot being added.

Include order: `BotCharacter.h` goes into `Game_local.h` immediately **before**
`bots/Bot.h` (currently `:1456`), because `rvBot` gains a
`const rvBotCharacter *` member and a `botTraits_t`. It uses `MAX_CLIENTS`,
which `Game_local.h` defines at `:59`.

## The roster

Sixteen characters, reusing the existing `botNames[]` pool so the cast still
looks like Quake 4. Each has a distinct voice; none is offensive.

| Character | Style | Skill band | Voice |
| --- | --- | --- | --- |
| Voss | roamer | 3-5 | calm field authority; disciplined, protective orders |
| Cortez | sniper | 3-5 | courteous, composed sharpshooter with quiet confidence |
| Bidwell | rusher | 3-5 | gruff, profane sergeant with little patience |
| Rhodes | ambusher | 3-5 | warm Texas demolition swagger and craftsman's pride |
| Sledge | rusher | 4-5 | thoughtful, formal and dryly understated |
| Morris | roamer | 3-5 | fast, crude commentary backed by real competence |
| Strauss | ambusher | 2-4 | precise, vain technician whose temper breaks through |
| Tetzlaff | sniper | 1-3 | self-promoting range ego with an excuse for everything |
| Marsh | roamer | 2-4 | warm, observant competitor who respects good play |
| Hollenbeck | roamer | 2-4 | practical field officer who turns setbacks into orders |
| Sorg | skirmisher | 2-4 | restless pathfinder always reading the next opening |
| Anderson | skirmisher | 1-3 | reassuring young medic, proactive under pressure |
| Gunner | rusher | 3-5 | translated Strogg combat reports: suppress and advance |
| Makron | hunter | 5-5 | imperious ruler who issues threats, not conversation |
| Kane | skirmisher | 4-5 | sparse, plain human tactical speech |
| Bagby | roamer | 1-2 | chatty, candid novice who learns out loud |

Styles ship in six files with the trait bodies sketched above:
`rusher` (combatRange 220, aggression 0.88, patience 0.15, close weapons,
wider cone), `sniper` (as the worked example), `roamer` (combatRange 620,
`itemFocus` ×1.40, everything else near baseline), `hunter` (combatRange 480,
`pursuit` ×1.60, `reacquireMsec` ×1.40 so it holds a target through cover,
`itemFocus` ×0.65), `ambusher` (combatRange 700, patience 0.95,
`peripheralPenaltyMsec` ×0.60 and `reactionMsec` ×0.85 because it is pre-aimed
at a choke, `strafeChance` ×0.55), `skirmisher` (combatRange 850,
`strafeChance` ×1.30, `jumpChance` ×1.45, `retreatHealth` +0.12,
`burstMaxMsec` ×0.75 for short trades).

## Documentation landing

The landing update turned `docs/dev/mp-bots.md` into the living subsystem and
authoring guide. It now covers the personality layers, distinct mechanics and
voice files, roster, commands, cvars, chat safety and known limits.
`docs/user/server-setup.md` exposes the operator-facing bot variables and
commands and links back to that deeper guide.

## Testing

A sibling to `tools/tests/mp_bot_navigation.py` — `tools/tests/mp_bot_characters.py` —
pinning the agreements the compiler cannot check:

- `botCharacterManager.Init()` is called from `idGameLocal::Init` and
  `Shutdown()` from `idGameLocal::Shutdown` (the existing `rvBotManager::Init`
  is dead code precisely because nobody pinned this);
- every file read uses `DECL_LEXER_FLAGS`, so malformed content warns instead
  of killing the server;
- every `ListFiles` is paired with a `FreeFileList`;
- the projectile test is `def_projectile`, not `!wfl.attackHitscan`;
- projectile speed is resolved through `gameLocal.FindEntityDefDict`, so the
  `_mp` retune applies, with no hardcoded speed table;
- `ProcessChatMessage` is called with `team` only under `IsTeamGame()`;
- the chat path passes through a throttle before reaching
  `ProcessChatMessage`;
- every trait field name in the field table exists in `botTraits_t`, and the
  baseline curve has `BOT_SKILL_LEVELS` entries for each;
- every shipped `.style`, `.bot` and `.chat` file parses to known keys; every
  character names a real style, every chat owner names a real character
  case-insensitively, shipped `.bot` files contain no inline dialogue, and no
  chat line starts with `#` or exceeds `BOT_CHAT_MAX_LEN`.

Registration is three files or it silently never runs in CI:
`tools/validation/openq4_validate.py` (the alphabetical `tests` list),
`.github/workflows/commit-validation.yml` (both the `py_compile` batch and the
execution list) and `.github/workflows/push-verification.yml` (the same two).

For a live check: `bot_debugAim 1` with two bots at `bot_skill 1` and two at
`bot_skill 5` on `mp/q4dm1`, and read the logged reaction, settle and lead
values per shot.
