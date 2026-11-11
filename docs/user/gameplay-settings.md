# Gameplay and Audio Settings

> [!NOTE]
> Inherited from openQ4 and not yet checked against PREY. This page describes what the engine code does; PREY behavior stays validation-pending until the [rebase status ledger](../dev/prey-rebase/status-ledger.md) records evidence for it.

This guide covers PREY's own game options and the audio settings openPREY's engine adds.

openQ4's other gameplay toggles (corpse cleanup and sinking, the hit marker, damage numbers and the weapon-wheel offset) live in Quake 4 game code. PREY's game module doesn't have them, so they aren't covered here.

## Game Options

**Options -> Game Options** in the stock PREY menu sets these game cvars:

| Setting | Default | What it does |
|---|---:|---|
| `g_decals` | `1` | Show decals such as bullet holes. |
| `g_showHud` | `1` | Show the HUD. |
| `ui_showGun` | `1` | Show the first-person weapon. |
| `g_subtitles` | `1` | Show subtitles. |
| `com_profanity` | `0` | `0` censors profanity; `1` plays and displays uncensored dialogue. |
| `g_crosshair` | `1` | Which crosshair to use (`0` = off, `1`-`8`). |
| `g_useDDA` | `1` | Use PREY's dynamic difficulty adjustment. |

The same page also has mouse options (`m_pitch` for inverted mouse, `m_smooth`, `sensitivity`, `in_freelook` and `in_toggleZoom`); see [Input Settings](input-settings.md).

## openPREY Game Cvars

| Setting | Default | What it does |
|---|---:|---|
| `g_autoSkipCinematics` | `0` | Single-player only. Skips cinematics and other scripted sections where the player has no control, as soon as they begin. Ignored in multiplayer. |
| `g_showPlayerShadow` | `1` | Shows your own player model's shadow, with the weapon in your hand, in your own first-person view. Other players' shadows always show, in single-player and multiplayer. Retail PREY shipped `0` and gave multiplayer players no shadow at all; a config saved with the retail `0` is switched on once (`g_showPlayerShadowMigrated`). |

## Quick Reference: Audio

| Setting | Default | What it does |
|---|---:|---|
| `s_volume` / `s_volume_dB` | `0.5` / `-6` | Master volume, as a linear value or in decibels. The two stay in sync. |
| `s_musicVolume` / `s_musicvolume_dB` | `0.5` / `-6` | Music volume, independently of the rest of the mix. The two stay in sync. |
| `s_dialogueVolume` | `1` | Spoken dialogue volume, from `0` (mute) to `1` (full), independently of effects and music. |
| `g_levelloadmusic` | `1` | Play map-defined music while levels load. |
| `s_useEAXReverb` | `1` | The map's per-area room reverb. See [Room Reverb](#room-reverb). |
| `s_useEAXOcclusion` | `1` | Closed doors muffle the sounds behind them. Works while `s_useEAXReverb` is on. |
| `s_numberOfSpeakers` | `0` | Speaker layout. `0` follows your output device, `2` forces stereo, `6` forces 5.1. See [Speaker Layout](#speaker-layout). |
| `s_reverse` | `0` | Swap the left and right channels. |

**Options -> Audio** in the stock menu sets the master and music volume, level-load music, OpenAL, the speaker layout, reversed stereo, the output device and EAX reverb.

## Music Volume

`s_musicVolume` scales music without changing the rest of the game mix. The stock menu's music slider sets the matching `s_musicvolume_dB`, and the two cvars follow each other.

- `0`: mute music.
- `0.5`: default music level.
- `1`: full music level.

It applies to sound shaders in PREY's music sound class and to samples under the `sound/musical/`, `sound/ambience/musical/` and `sound/music/` paths. The setting is live and can be adjusted while the game is running.

```cfg
seta s_musicVolume 0.2
```

## Dialogue Volume

`s_dialogueVolume` changes spoken dialogue without lowering weapons or music. It takes effect immediately and is saved. `seta s_dialogueVolume 0.6` sets it to 60% of the authored level; `0` mutes dialogue. Master volume still affects everything. The stock PREY menu has no slider for it; the retained interface (`ui_retained 1`) does.

Lip-synced speech and sounds on the voice-over asset paths share this control. Multiplayer voice chat has its own settings. A mod that mixes speech and music into one recording can't separate them with this setting.

## Room Reverb

A map's reverb table tells the game which reverb each of its rooms, corridors and outdoor areas uses. openPREY plays these the way EAX sound hardware did:

- the reverb follows you from area to area, and the areas next to you keep their own reverb, so a gunshot in the next room still sounds like that room;
- each nearby area's reverb comes from the doorway that leads to it;
- closed doors muffle the sounds behind them, and their reverb with them;
- radio chatter stays dry and voice-over sits a little further back.

It needs OpenAL's EFX extension. OpenAL Soft provides it: Windows builds bundle it, and Linux distributions install it as their OpenAL.

- `s_useEAXReverb 1` (default): room reverb on, in every performance preset. `0` turns it off, along with door muffling. Changing it from the console takes effect after `s_restart`.
- `s_useEAXOcclusion 1` (default): closed doors muffle sound while reverb is on.
- `s_muteEAXReverb 1`: silences the reverb of the area you're standing in, for comparison.
- Maps without a reverb table use the Generic reverb everywhere.
- `listReverbs` lists the reverbs, the current map's areas and the reverbs playing around you. `s_showReverb 1` prints a line whenever they change.

## Speaker Layout

openPREY follows your audio device by default. Headphones and stereo speakers get stereo, with OpenAL Soft's 3D headphone audio (HRTF) switching on by itself when the system reports headphones, and a 5.1 or 7.1 system gets all of its channels.

- `s_numberOfSpeakers 0` (default): use the output device's own layout. Set it from the console.
- `s_numberOfSpeakers 2`: always stereo.
- `s_numberOfSpeakers 6`: always 5.1. On a stereo device the system downmixes it and headphone HRTF can't engage, so pick this only for a 5.1 system that misreports its layout.

The stock **Options -> Audio** speaker choice switches between `2` and `6`. Choosing either there replaces the automatic default; run `seta s_numberOfSpeakers 0` to return to it.

- `s_openALHRTF` chooses headphone HRTF: `0` automatic (default), `1` off, `2` on.
- Unplugging a headset or switching the default device keeps the sound going, including music and looping ambience, and keeps your speaker and HRTF choices.
- Changing `s_numberOfSpeakers`, `s_openALHRTF` or `s_outputLimiter` applies to the open device in place: sounds keep playing without reloading.

## Audio Quality

These are on by default and rarely need changing. Each takes effect after `s_restart`.

- `s_sourceRadiusScale 0.5`: a sound has a size, half of its shader's `minDistance`. Standing next to a machine or a fire, it surrounds you instead of jumping from ear to ear as you turn. `0` makes every positioned sound a point.
- `s_directStereo 1`: music and other stereo sounds play straight to your speakers or headphones instead of passing through 3D headphone audio as two virtual speakers.
- `s_resampler auto`: sounds recorded at a low rate such as 22 kHz are upsampled with a sinc filter for cleaner high frequencies. `default` keeps OpenAL's own, and `listResamplers` lists the choices.
- `s_outputLimiter 1`: loud scenes compress instead of clipping.
- `s_airAbsorption 1`: distant sounds lose a little treble, by the air absorption each room's reverb preset sets.

## Troubleshooting

- If music doesn't respond to `s_musicVolume`, test on a map or menu that's actively playing music rather than ambience or voice-over.
- If there's no room reverb, check that `s_useEAXReverb` is `1` and that your OpenAL is OpenAL Soft (the log reports the EFX extension at startup), then run `s_restart`.
- If 5.1 output sounds wrong on headphones, set `s_numberOfSpeakers 0` so the device's own layout and HRTF apply.
