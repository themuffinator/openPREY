# Gameplay Settings and Runtime Toggles

> [!NOTE]
> This page documents inherited engine/tooling capability. Retail Prey behavior remains
> runtime-validation pending unless the rebase status ledger records specific evidence.

This guide covers a small set of gameplay and audio cvars that are useful for testing, accessibility, and personal preference.

The auto-skip cinematics, corpse cleanup, and corpse sink controls are also available in the in-game menu at `Settings -> Game Options`.

## Quick Reference

| Setting | Default | Scope | What it does |
|---|---:|---|---|
| `ui_weaponWheelOffset` | `27` | SP and MP client | Horizontal wheel offset as a percentage of screen width from center, −40 to +40. `0` centers it; `27` preserves the usual right-side position. Also in Game Options > Controller, beside wheel sensitivity. |
| `g_autoSkipCinematics` | `0` | Single-player | Automatically skips cinematics and other scripted sections where the player has no control, as soon as they begin. Ignored in multiplayer. Disabled by default. |
| `g_corpseRemoveDelaySP` | `0` | Single-player | Controls how long SP corpses remain before disappearing. `0` uses stock timing, `-1` disables corpse removal. |
| `g_corpseRemoveDelayMP` | `0` | Multiplayer | Controls how long MP corpses remain before disappearing. `0` uses stock timing, `-1` disables corpse removal. |
| `g_corpseSink` | `0` | SP and MP game code | Selects corpse sink mode instead of the normal dissolve or burn-away behavior. |
| `g_showPlayerShadow` | `1` | SP and MP client | Shows your own player model's shadow, with the weapon in your hand, in your own first-person view. Other players' shadows always show, in single-player and multiplayer. Retail Prey shipped `0` and gave multiplayer players no shadow at all; a config saved with the retail `0` is switched on once (`g_showPlayerShadowMigrated`). |
| `s_musicVolume` | `0.5` | Client audio | Controls music volume independently of the main sound mix. |
| `s_dialogueVolume` | `1` | Client audio | Spoken dialogue volume, from `0` (mute) to `1` (full), independently of effects and music. |
| `s_useEAXReverb` | `1` | Client audio | The map's per-area room reverb, as the level designers set it up. See [Room Reverb](#room-reverb). |
| `s_useEAXOcclusion` | `1` | Client audio | Closed doors muffle the sounds behind them. Works while `s_useEAXReverb` is on. |
| `s_numberOfSpeakers` | `0` | Client audio | Speaker layout. `0` follows your output device, `2` forces stereo, `6` forces 5.1. See [Speaker Layout](#speaker-layout). |
| `hud_damageNumbers` | `0` | Multiplayer client | Floating damage numbers over the players you hit. `0` off, `1` opponents only, `2` all damage you deal. |
| `hud_damageNumberStyle` | `1` | Multiplayer client | How damage numbers are coloured. `1` white through red, `2` one colour per damage band, `3` one colour per weapon. |
| `hud_damageNumberScale` | `1` | Multiplayer client | Damage number size multiplier, `0.25` to `4`. |
| `hud_hitMarker` | `1` | SP and MP client | Crosshair hit marker on hits you land. On by default. |
| `hud_hitMarkerScale` | `1` | SP and MP client | Hit marker size multiplier, `0.25` to `4`, on top of `g_crosshairSize`. |
| `hud_crosshairHitFlash` | `0` | SP and MP client | Recolours the crosshair on a hit, as stock Prey (2006) does. Implied when `hud_hitMarker` is off. |
| `g_hitFeedback` | `2` | Multiplayer server | Whether the server tells attackers about their hits at all. `0` none, `1` without the amount, `2` with the amount. |

## Cinematics

`g_autoSkipCinematics` is intended for repeat testing runs, speed-focused replays, and development workflows where you do not want to manually skip every scripted sequence.

The in-game menu exposes this as `Settings -> Game Options -> Auto Skip Cinematics`.

Behavior:
- `0`: normal behavior, cinematics play as authored.
- `1`: cinematics are skipped automatically when they start.

Notes:
- The cvar is archived, but it is disabled by default.
- The change affects future cinematics. It does not retroactively alter one that has already finished.

Example:

```cfg
seta g_autoSkipCinematics 1
```

## Corpse Cleanup

openPREY now exposes separate corpse-removal timing controls for single-player and multiplayer.

### Single-player

`g_corpseRemoveDelaySP` accepts three useful ranges:
- `0`: use stock timing.
- `-1`: never remove corpses automatically.
- `> 0`: override the delay in seconds before corpse removal begins.

Example:

```cfg
seta g_corpseRemoveDelaySP 20
```

### Multiplayer

`g_corpseRemoveDelayMP` behaves the same way, but applies to the multiplayer game module.

Example:

```cfg
seta g_corpseRemoveDelayMP 10
```

Notes:
- These cvars affect corpse cleanup timing. They do not change health, gibbing, or damage behavior.
- New values are most useful for newly created corpses. Existing corpses may already be partway through their current cleanup path.

## Corpse Sinking

`g_corpseSink` switches corpse disappearance to a Quake 3 style sink animation.

Behavior:
- `0`: use the normal stock-style dissolve or burn-away path.
- `1`: sink corpses into the floor before removal while keeping ragdoll active.
- `2`: sink corpses into the floor before removal after stopping ragdoll first.

Notes:
- This cvar is shared by SP and MP.
- The configured SP or MP corpse delay still controls when the sink starts.
- If the relevant corpse-delay cvar is `-1`, corpse removal is disabled and sinking will not start.
- Mode `2` uses the actor's normal corpse physics while the sink runs, so the body no longer keeps simulating as a ragdoll during the sink.

Example:

```cfg
seta g_corpseSink 1
seta g_corpseRemoveDelaySP 15
```

No-ragdoll sink example:

```cfg
seta g_corpseSink 2
seta g_corpseRemoveDelaySP 15
```

## Music Volume

`s_musicVolume` controls the volume of music-tagged sound shaders without changing the rest of the game mix.

Behavior:
- `0`: mute music.
- `0.5`: default music level.
- `1`: full music level.

Notes:
- This is separate from the master sound volume.
- It applies to music shaders authored under the stock Prey (2006) music paths, including both `sound/musical/` and `sound/ambience/musical/`.
- The setting is live and can be adjusted while the game is running.

Examples:

```cfg
seta s_musicVolume 0.2
```

```cfg
seta s_musicVolume 0
```

## Dialogue Volume

**Settings > Audio > Dialogue Volume** changes spoken dialogue without lowering
weapons or music. The setting takes effect immediately and is saved.
`seta s_dialogueVolume 0.6` sets it to 60% of the authored level; `0` mutes
dialogue. Master volume still affects everything.

NPC lip-sync speech, radio lines and sounds using the game's voice-over asset
paths share this control, including English audio fallback in other text
languages. Multiplayer microphone audio has its own settings. A mod that mixes
speech and music into one recording cannot separate those parts with this slider.

## Room Reverb

A map's reverb table tells the game which reverb each of its rooms, corridors and outdoor areas uses: a
tiled bathroom rings, a hangar booms, a canyon sounds open. openPREY plays these the way EAX sound
hardware did:

- the reverb follows you from area to area, and the areas next to you keep their own reverb, so a
  gunshot in the hangar next door still sounds like the hangar;
- each nearby area's reverb comes from the doorway that leads to it;
- closed doors muffle the sounds behind them, and their reverb with them;
- radio chatter stays dry and voice-over sits a little further back, as in the original mix.

It needs OpenAL's EFX extension. OpenAL Soft provides it: openPREY ships it on Windows and macOS, and
Linux distributions install it as their OpenAL. Apple's own OpenAL framework has no EFX, so a build
using it plays without reverb.

Behavior:
- `s_useEAXReverb 1` (default): room reverb on, in every performance preset. `0` turns it off, along with door muffling, as in
  the original game. Changing it from the console takes effect after `s_restart`.
- `s_useEAXOcclusion 1` (default): closed doors muffle sound while reverb is on.
- `s_muteEAXReverb 1`: silences the reverb of the area you are standing in, for comparison.

Notes:
- Maps without a reverb table use the Generic reverb everywhere.
- `listReverbs` lists the reverbs, the current map's areas and the reverbs playing around you.
  `s_showReverb 1` prints a line whenever they change.

## Speaker Layout

openPREY now follows your audio device by default. Headphones and stereo speakers get stereo, with
OpenAL Soft's 3D headphone audio (HRTF) switching on by itself when the system reports headphones,
and a 5.1 or 7.1 system gets all of its channels.

The in-game menu exposes this as `Settings -> Audio -> Surround Speakers`: `Auto`, `Off` (stereo)
or `On` (5.1).

Behavior:
- `s_numberOfSpeakers 0` (default, `Auto`): use the output device's own layout.
- `s_numberOfSpeakers 2` (`Off`): always stereo, as the original game's default.
- `s_numberOfSpeakers 6` (`On`): always 5.1. On a stereo device the system downmixes it, and
  headphone HRTF cannot engage, so pick this only for a 5.1 system that misreports its layout.

Notes:
- Earlier openPREY builds asked for 5.1 on every device. A saved `6` from those builds moves to `0`
  once. A saved `2` is kept.
- `s_openALHRTF` chooses headphone HRTF: `0` automatic (default), `1` off, `2` on. Earlier builds
  could not turn it off on headphones; `1` now does.
- Unplugging a headset or switching the default device keeps the sound going, including music
  and looping ambience, and keeps your speaker and HRTF choices. Dialogue and other sounds that
  were playing pick up where the scene is when audio returns, instead of being cut off, and a
  line paused in a menu continues from where it stopped.
- Changing `s_numberOfSpeakers`, `s_openALHRTF` or `s_outputLimiter` applies to the open device
  in place: sounds keep playing without reloading, and a line that is playing moves to or from
  the centre speaker at its current point.

## Audio Quality

These are on by default and rarely need changing. Each takes effect after `s_restart`.

- `s_sourceRadiusScale 0.5`: a sound has a size, half of its shader's `minDistance`. Standing next
  to a machine or a fire, it surrounds you instead of jumping from ear to ear as you turn, and
  your own footsteps and weapons play evenly instead of from straight ahead. `0` makes every
  positioned sound a point.
- `s_directStereo 1`: music and other stereo sounds play straight to your speakers or headphones.
  With 3D headphone audio on, they used to pass through it as two virtual speakers, which
  narrowed the stereo and made them quieter.
- `s_resampler auto`: sounds recorded at a low rate such as 22 kHz are upsampled with a sinc
  filter for cleaner high frequencies. `default` keeps OpenAL's own, and `listResamplers`
  lists the choices.
- `s_outputLimiter 1`: loud scenes compress instead of clipping.
- `s_airAbsorption 1`: distant sounds lose a little treble, by the air absorption each room's
  reverb preset sets.

## Hit Marker

Every hit you land blooms four short angled marks out of your crosshair and fades
them within a fraction of a second. It works in single-player and multiplayer, and
it is on by default: `Settings -> Game Options -> Crosshair -> Hit Marker`.

The marker reads the hit back to you rather than just confirming it:

- A graze or a splash hit is a small, quiet tick.
- A normal hit is the reference pulse.
- A heavy hit - a rail, a rocket, a direct dark matter hit - is wider, brighter,
  and lasts a beat longer.
- A hit that finishes the target flashes white hot and travels furthest.
- Armour absorbing part of the hit lifts the marks towards white.
- Team damage shows amber and self damage shows a muted grey-blue, so a mistake
  never reads like a reward.

Sustained fire re-arms the marker instead of stacking a second one, and a heavier
hit landing behind a lighter one keeps the heavier look for the rest of the pulse.

`hud_hitMarker 0` turns it off. `hud_hitMarkerScale` scales it between `0.25` and
`4`; it already follows `g_crosshairSize`, so the marks frame whatever crosshair
you use.

Stock Prey (2006) recolours the crosshair red for a moment when you hit something. The
marker replaces that cue, so the recolour is off while the marker is on. Turning
the marker off brings the recolour back on its own, and
`hud_crosshairHitFlash 1` asks for both at once.

In multiplayer the marker sizes itself from the same server-permitted hit
information as damage numbers, so with `g_hitFeedback 1` or `0` you still get a
marker on every hit - just always the normal one, because the server is not
telling you what the hit was worth.

## Damage Numbers

In multiplayer, openPREY can float the damage you deal above the player you hit, the
way Quake Live's damage plums do. The numbers are projected from the point of
impact and then drift along a short arc before fading, so they stay readable
during a fight without ever sitting on top of your crosshair.

This is a display choice and it is off by default.

`hud_damageNumbers` decides which of your hits are shown:
- `0`: off.
- `1`: opponents only. This is what Quake Live shows.
- `2`: everything you deal, adding team damage and self damage.

`hud_damageNumberStyle` decides how they are coloured:
- `1`: white for a scratch through red at 100 damage.
- `2`: one colour per damage band - blue up to 25, yellow to 50, orange to 75, red above.
- `3`: one colour per weapon.

`hud_damageNumberScale` scales the text between `0.25` and `4`.

The number is the full worth of the hit, so armour counts towards it rather than
being subtracted from it.

### Server permission

`g_hitFeedback` is a **server** setting and it decides whether attackers are told
about their hits at all:
- `0`: no hit feedback. Damage numbers show nothing regardless of client settings.
- `1`: the hit is announced but the amount is withheld, so damage numbers stay blank.
- `2`: the amount is included. This is the default.

A server that wants to keep exact damage off the table sets `g_hitFeedback 1` or
`0`; no client setting can override it.

Example:

```cfg
seta hud_damageNumbers 1
seta hud_damageNumberStyle 2
seta hud_damageNumberScale 1.25
```

## Example Presets

### Fast Testing Setup

```cfg
seta g_autoSkipCinematics 1
seta g_corpseRemoveDelaySP 2
seta g_corpseSink 1
seta s_musicVolume 0.2
```

### Keep Corpses Around

```cfg
seta g_corpseRemoveDelaySP -1
seta g_corpseRemoveDelayMP -1
```

## Troubleshooting

- If `g_autoSkipCinematics 1` appears to do nothing, verify you are testing a real in-game cinematic and not a normal scripted gameplay event.
- If corpses still disappear quickly, check whether you are in SP or MP and set the matching delay cvar for that game module.
- If `g_corpseSink 1` or `g_corpseSink 2` is enabled but corpses never sink, make sure the relevant corpse delay is not set to `-1`.
- If music does not respond to `s_musicVolume`, test on a map or menu that is actively playing music rather than general ambience or voice-over audio.
- If damage numbers never appear, check `g_hitFeedback` on the server: at `0` or `1` the amount never reaches you. They are also multiplayer only, and they only cover damage dealt to players.
- If damage numbers appear for opponents but not team mates, that is `hud_damageNumbers 1` working as intended. Set it to `2` to include team and self damage.
