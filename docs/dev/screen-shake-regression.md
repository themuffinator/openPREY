# Camera-shake regression after 0.13.2

The audio modernization in `d1e1c8248` (6 October 2026) restored the game's
previously stubbed sound-shake query, but returned the audio mix's light-flicker
amplitude. This made the repeated cannon sounds in `game/airdefense1` too strong
and allowed positional sounds to shake the camera at the wrong distance.

## Cause and correction

- Camera envelopes use **600** per authored letter. Material/light envelopes
  use **2800**. Reusing the latter overstates the camera motion.
- Quake 4 sound-shader ranges and speaker overrides are in **map units**. The
  inherited audio mixer converts emitter distance to metres. Its attenuation
  is therefore unsuitable for the camera query.
- Apply shader volume, `shakes` and direct-distance attenuation to the envelope
  **before** converting it with `atan(high / 32767) / radians(45)`. Multiplying
  the converted angle by the gain changes the response, especially for large
  authored shake values.
- Take the strongest channel on each emitter; add the resulting emitter
  amplitudes. Adding every channel separately multiplies overlapping effects.
- Sample authored `shakeData` only. A missing envelope, its silent tail, or the
  light-only `no_flicker` flag must not manufacture camera motion.

`idSoundSystemLocal::CurrentShakeAmplitudeForPosition` now evaluates this
calculation at the supplied position using the sound world's playback clock.
It does not depend on the audible gain or hardware voice allocation. The
existing shifted/slow-motion clock and looping envelope behavior are retained.
`s_constantAmplitude` suppresses shake while holding lights constant. Slot zero
is included because openQ4 uses it for the world's `localSound` emitter.

The camera implementation is separate from `CurrentAmplitude`, the PCM envelope,
and controller rumble. No stock assets or game camera coefficients were changed.
The serialized world shake field remains in place, preserving save layout.

## Retail reference

The installed Steam **Quake4.exe 1.4.2** was inspected read-only with Capstone.
`FindAmplitude` starts at **0x10173eb0**:

- `0x10173ed0`: screen scale 600; `0x10173f0c`: material scale 2800.
- `0x10173ecd`–`0x10173efe`: Euclidean distance in unconverted map coordinates.
- `0x10173fb6`–`0x10174061`: volume, shakes, global flag and direct falloff.
- `0x10174076` onward: selected variant's authored envelope, with no PCM fallback.
- `0x1017414c`–`0x10174170`: scale/gain before maximum-channel selection.
- `0x10174198`–`0x101741b8`: normalization and arctangent conversion.

The local decompilation was used to locate the behavior; the retail binary
verified the constants and calculation. No decompiled source was incorporated.

## Validation on 7 October 2026

`tools/tests/sound_screen_shake.py` compiles the production emitter/world/system
queries, playback clock and falloff against small test doubles. It covers
camera versus light scale, minimum/midpoint/maximum distance, global sounds,
quadratic falloff, high gains, channel maximum versus emitter sum, explicit
query position, local emitter slot zero, variant choice, looping, silence,
missing envelopes, stopped/future/completed channels, `no_shakes`, `no_flicker`,
`s_constantAmplitude`, and pitch-adjusted playback. Both validation workflows
run it. The fixture uses original synthetic envelope strings and needs no game
assets.

For the stock cannon's -4 dB, `shakes 1`, and peak `z`:

| Query distance (map units) | Expected camera amplitude (degrees) |
| --- | ---: |
| 0 through 500 | 0.358016 |
| 2750 | 0.182617 |
| 5000 and farther | 0 |

The Windows x64 build completed through `tools/build/meson_setup.ps1 compile
-C builddir`, then staged with `install -C builddir --no-rebuild
--skip-subprojects`. Audio payload/save restoration and the retail reverb
contract also passed.

Runtime tests used the generated SP Air Defense launch configurations, installed
Steam PK4s and the stable `.install/openQ4-client_x64.exe` path. Each test had an
isolated writable profile, windowed hidden rendering, disabled mouse/controller
input and rumble, and OpenAL's null output. The level entered gameplay and the
registered engine `screenshot` command captured it. No OS capture or host input
injection was used.

The actual `s_showVoices` peak during `testSound airdefense_cannon_fire` fell from
**0.896–0.909** in the pre-fix staged build to **0.357** on both OpenGL and Vulkan.
Envelope sampling and random sound-variant selection explain the small
difference from the analytical peak. This is about **60% less nearby angular
shake**, while preserving the authored effect. A later map phase also exercised
the stock muffled cannon; exact distance boundaries are covered by the compiled
query tests because live map sounds overlap.

Engine logs, command lines, binary hashes, reports, captures and retail
disassembly evidence are under `.tmp/screen-shake/`. Useful runtime evidence is
in `baseline-distance/`, `fixed-gl/` and `fixed-vulkan/`; the engine logs are
`baseoq4/logs/openq4.log` within each. On-demand loading of the diagnostic cannon
reports the expected non-pre-cached-sound warning.

## Separate issues observed

- The audible mixer still has the metres/map-units mismatch, including its
  source-radius conversion. Camera shake now bypasses it; the audible mix needs
  separate qualification. This is also recorded in the audio modernization
  document's deferred work.
- Meson reports the existing RmlUi wrap/revision mismatch during reconfiguration
  and include-directory sandbox warnings. They did not prevent compilation or staging.
