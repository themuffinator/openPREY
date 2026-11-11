# Prey screen effects

Prey draws its full-screen effects as 2D quads over the player's view. Most of
them sample `_currentRender` through one of three retail ARB programs. This
page lists them, says which code drives each one, and records how to check them
on both renderers. The player-view code is `src/Prey/game_playerview.cpp`
(`hhPlayerView`).

## What draws them

| Layer | Drawn by | Material (retail) |
|---|---|---|
| Damage motion blur | `hhPlayerView::MotionBlurVision`: the view is rendered into `_scratch` and redrawn shifted. Damage defs set `mb_time` and `mb_amplitude`; `g_doubleVision 0` turns it off | `_scratch` |
| Damage blobs | `hhPlayerView::DamageImpulse`: `mtr_blob`, `blob_*` keys on the damage def | `textures/damage/*`, `textures/particles/bloodwound` |
| Low health | `hhPlayerView::SingleView` below 25 health; parm0 is the smoothed health / 25 | `textures/decals/hurtview` |
| Script overlay | `setOverlayMaterial`, `setOverlayColor`, `setOverlayTime` on `$player1`; the colour reaches the material as parm0-parm3 | see below |
| Spirit walk | `hhPlayerView::SpiritVision`, from the player's `mtr_spiritWalk` | `textures/decals/spiritview` |
| Death walk | Overlay from the player's `mtr_deathWalk`; parm3 is the resurrection flash | `textures/decals/deathview` |
| Fade, letterbox | `idPlayerView::ScreenFade`, `hhPlayerView::ApplyLetterBox` | `_white`, `_black` |

The script overlays and the materials that use the screen programs:

| Program | Materials | Driven by |
|---|---|---|
| `screeneffect.vfp` | `textures/decals/spiritview`; `textures/sfx/flashbackStart`, `flashbackEnd`; `textures/special/abduction_screenfx` (roadhouse abduction, parm3 fades it in); `spherevoice_intro`, `_intro2`, `_loop`, `_outro` (`SphereVoice_Start` / `SphereVoice_Stop` in `prey_util2.script`); `spherebrain_flash1`-`8`, `spherebrain_white_flash1`-`5`; `keeper_genocide`, `keeper_flash1`-`9` | Map scripts |
| `screenprocess.vfp` | `textures/decals/painview`, `textures/sfx/scanburn` (feedingtowera), `textures/sfx/screen_lotatransition` (epilogue and `prey_util2.script`) | Map scripts; parm0-parm3 are saturation, contrast, multiply and add |
| `radialblur.vfp` | `textures/decals/deathview`, `textures/outro/blur` (spherebrain), `textures/special/keeper_flash10`, `keeper_flash11` | Death walk, map scripts |

OpenGL runs the ARB programs as written. Vulkan translates them
(`src/renderer/materialprogram/ARBTranslator.cpp`) and fills `program.local`
from the stage's `fragmentParm` registers and `program.env[0]`/`[1]` from the
`_currentRender` size and the viewport, as `RB_SetProgramEnvironment` does.

### Timed overlays

The Keeper, Sphere and spherevoice materials animate on `time + parm0`. The
script passes `-sys.getTime()` as parm0, so the sum counts from zero when the
effect starts. A 2D quad evaluates its registers when its batch is emitted, not
when it is drawn. The player view draws at level time, but the subtitles GUI
redraws later in the frame at presentation time. On Vulkan the overlay was still
pending then, so its `time + parm0` came out several seconds past the effect's
end:

- `spherevoice_outro` turned the whole view black for its 1.5 seconds.
- The Keeper and Sphere white flashes never showed.
- `spherebrain_flash8` sat at full white.

OpenGL hid this only because it flushes a batch that samples `_currentRender`
early. `idRenderSystemLocal::SetFrameShaderTime` now emits the screen-level
batch before a GUI moves the shader time. In-world GUIs (`guiRecursionLevel >
0`) and `BeginFrame` do not flush.

### The spiritWalk register

Retail materials gate stages on `spiritWalk` and `notSpiritWalk` (the Land of
the Ancients cave paintings, Hider burn decals, `vortex4_spirit`, the cave
bird). Prey's game code never calls `SetSpiritWalkView`; it marks the view
instead (`renderView->viewSpiritEntities` in `hhPlayer::CalculateRenderView`).
`idMaterial::EvaluateRegisters` now sets `EXP_REG_SPIRIT_WALK` from either.
Before, the register was always zero and those stages never drew.

## Checking them

`testViewOverlay <material> [r g b a] [requiresScratch]` (cheat) sets the
overlay exactly as a script does. Any of `r g b a` may be `now`, which passes
the negated game time the way scripts pass `-sys.getTime()`. `testViewOverlay
off` clears it. The console splits `-word` into two tokens, so the marker is a
plain word.

```text
testViewOverlay textures/special/keeper_flash1 now 1 1 1
testViewOverlay textures/special/abduction_screenfx 0 0 0 0.5
testViewOverlay textures/sfx/scanburn 1.5 3.5 1.75 2.5 1
testDamage melee_harvester_swipe 90
```

`screenshot` re-renders the frame without temporal history. Check effects that
depend on what reaches the window in a windowed run as well.

## Evidence, 11 November 2026

RTX 4060 laptop, `game/feedingtowerb` and `game/lotab`, windowed:

- All 47 overlay cases match between OpenGL and Vulkan in `screenshot` captures
  at 0.13, 0.8 and 2.8 seconds: every material above, with the parameters its
  scripts use.
- A live Vulkan capture of the window, read with `PrintWindow`, shows the
  `spherevoice_outro` fade, the `keeper_flash1` flash and the
  `spherebrain_flash8` ramp, as on OpenGL.
- In `lotab`, the cave paintings glow in spirit walk and not outside it, on
  both renderers.
- Damage blur, blobs, attacker indicators and the low-health overlay showed no
  blackout:
  - from `testDamage`, `damage player1` and a spawned hunter and mutate;
  - on both renderers;
  - with a fresh profile and with a profile using Vulkan, 8x MSAA, temporal AA
    and an HDR scene target.

Three retail damage defs give a blob an empty `mtr_blob`
(`missile_centurion_autocannon`, `splash_plasma`, `splash_plasmac`). They draw
nothing, which matches retail.
