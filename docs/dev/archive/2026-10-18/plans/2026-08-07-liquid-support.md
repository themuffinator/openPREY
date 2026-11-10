# Liquid support (water, slime, lava)

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Status: in progress, started 2026-08-07.

openQ4 inherits id Tech 4's liquid code, which is Quake 3's `pmove` water model with most of the
consequences removed and the whole thing switched off in multiplayer. This plan restores a complete
liquid system in line with the older Quake titles — Quake 3 Arena is the reference for feel and
numbers, Quake 2 for the presentation details Q3 dropped (splashes, bubble trails, per-liquid
surface reactions).

## What shipped in Quake 4, and what did not

`idPhysics_Player` already carries `waterLevel` (`WATERLEVEL_NONE/FEET/WAIST/HEAD`) and `waterType`,
and already implements `SetWaterLevel()`, `WaterMove()`, `WaterJumpMove()` and `CheckWaterJump()` as
faithful ports of Q3's `PM_SetWaterLevel`, `PM_WaterMove`, `PM_WaterJumpMove` and
`PM_CheckWaterJump`. Water friction and the wading speed clamp are in `Friction()` and `WalkMove()`.

What was missing or disabled:

- **Water was compiled out of multiplayer.** Every call site was wrapped in
  `if ( !gameLocal.isMultiplayer )` (`ddynerman: water disabled in MP`), in both game trees.
- **Lava and slime were not liquids.** `MASK_WATER` was `(CONTENTS_WATER)` alone, so a lava brush
  never raised `waterLevel` and never populated `waterType`.
- **Lava and slime could not be authored at all.** `CONTENTS_LAVA` and `CONTENTS_SLIME` exist in
  `contentsFlags_t` but had no entry in the `infoParms` table in `Material.cpp`, so no material
  could declare them and no brush could ever carry those bits.
- **No consequences.** No drowning, no air supply, no lava/slime damage, no water entry/exit
  sounds, no splashes, no bubbles, no underwater audio or screen treatment. The single consumer of
  `GetWaterLevel()` in the whole game was falling-damage reduction in `idPlayer::CrashLand`.
- **Nothing but the player knew about liquid.** Projectiles, moveables, corpses and items ignore
  liquid volumes entirely; bots have no notion of swimming and no way to route through or around
  liquid.

## Target behaviour

### Content flags and authoring

`water`, `lava` and `slime` are material keywords that set `CONTENTS_WATER`, `CONTENTS_LAVA` and
`CONTENTS_SLIME` and clear the solid flag, exactly as `water` already did. `MASK_WATER` is
`(CONTENTS_WATER|CONTENTS_LAVA|CONTENTS_SLIME)`, matching Q3's mask of the same name, so all three
drive water level, movement, and every consequence below. `waterType` carries the specific bits so
consumers can tell the three apart.

### Player movement

Unchanged from Q3, now running in multiplayer as well:

| quantity | value |
| --- | --- |
| swim speed scale | `PM_SWIMSCALE` 0.5 |
| water acceleration | `PM_WATERACCELERATE` 4.0 |
| water friction | `PM_WATERFRICTION` 2.0, scaled by water level |
| water jump velocity | 200 forward, 350 up, 2000 ms of `PMF_TIME_WATERJUMP` |
| sink speed with no input | 60 u/s |

Wading clamps ground speed by `1 - (1 - PM_SWIMSCALE) * (waterLevel / 3)`, so feet-deep water is a
mild slowdown and waist-deep is most of the way to swim speed. Swimming begins above
`WATERLEVEL_FEET`. Falling damage is reduced by half at feet depth, to a quarter at waist depth, and
removed entirely when the head is under. Water level is recomputed from the origin every movement
frame on both client and server, so it predicts without any new network state.

### Damage

Q3's `P_WorldEffects`, in openQ4 terms:

- **Drowning.** 12 seconds of air. When it runs out, damage every second starting at 2 and rising
  by 2 to a cap of 15, with a gurp sound instead of the normal pain sound. Air refills instantly on
  surfacing. Noclip and spectators never drown.
- **Lava.** 30 damage per water level per damage tick — lethal in about a second at full immersion.
- **Slime.** 10 damage per water level per damage tick.

Lava and slime burn at any water level, including feet-deep, and are gated by the usual pain
debounce so the rate does not depend on frame rate.

### Presentation

- Entry and exit splashes sized by the entity's speed and bounds, per liquid type.
- Water enter, exit, submerge and surface sounds on the player, matching Q3's
  `EV_WATER_TOUCH` / `EV_WATER_LEAVE` / `EV_WATER_UNDER` / `EV_WATER_CLEAR`.
- Bubble trails from a submerged player, and from projectiles travelling underwater.
- Wade ripples at the surface when moving with feet or waist in liquid.
- Muffled audio while the listener's head is submerged.
- A per-liquid screen tint and warp while the view is submerged.
- Footsteps and impacts pick the liquid reaction through the existing `SURFTYPE_LIQUID` surface
  type.

### Other entities

- Projectiles detect the liquid surface on entry: splash effect and sound, with drag applied
  underwater. Liquid does not stop a projectile, matching Q3.
- Moveables, corpses, debris and dropped items get buoyancy and drag, so light objects float and
  heavy ones sink slowly rather than falling as if through air.
- Explosions still propagate through a liquid surface.

### Bots

- Bots recognise liquid, swim when submerged, surface for air, and use the water jump to leave a
  pool.
- Lava and slime are treated as lethal terrain and avoided by routing, not merely reacted to.
- Navigation marks liquid areas so paths can cross water deliberately rather than by accident.

## What landed

Everything below builds clean in the engine and both game DLLs, and the gameplay core has been run
in a stock Quake 4 map — see "Testing" for what was verified and what that turned up.

**Engine**

- `lava` and `slime` material keywords, so those volumes can be authored at all
  (`src/renderer/Material.cpp`). `CONTENTS_LAVA` and `CONTENTS_SLIME` had existed since a
  `jmarshall - todo` block with no way to set them.
- `idSoundWorld::SetUnderwater`, muffling the mix at 0.75 occlusion, sharing the hardware path the
  enviro suit already used (`src/sound/`). Mirrored into the game repo's `sound.h`.

**Player**

- Water runs in multiplayer. Every `ddynerman: water disabled in MP` gate is gone from both trees.
- `MASK_WATER` is `(CONTENTS_WATER|CONTENTS_LAVA|CONTENTS_SLIME)`, matching Q3's mask of the same
  name, so lava and slime raise water level and populate `waterType`.
- `idPlayer::UpdateLiquid` — Q3's `PM_WaterEvents` plus the sizzle half of `P_WorldEffects`: entry,
  exit, submerge and surface sounds and splashes, and lava/slime damage scaled by water level.
- Drowning folded into `UpdateAir`, reusing the vacuum air reservoir, its HUD readout and its
  sounds, draining `pm_air / pm_waterAir` times faster while submerged. Q3's rising damage ramp,
  capped by `g_drownDamageMax`.
- **Swimming revised.** Jump and crouch are the vertical axis and now work while stood on the
  bottom: `CmdScale` zeroed `upmove` whenever `walking` was set, and a swimmer resting on the floor
  of a pool is still "walking", so neither key did anything. `CmdScale` takes an `allowVertical`
  flag and `WaterMove` passes it.
- **Swimming is its own gait.** `MovePlayer` substitutes `swimSpeed` for `playerSpeed` once above
  `WATERLEVEL_FEET`, after `CheckDuck`. Without that, holding crouch to descend dropped the swimmer
  to `crouchSpeed` — descending was half the speed of ascending — and swimming straight up with no
  other key held counted as "not running" in `AdjustSpeed` and fell to `pm_walkspeed`.
- **Swim speed matches Quake 3.** `pm_swimSpeed` 160, which is Q3's 320 run speed times its
  `pm_swimScale` 0.5. openQ4 runs at 160, so parity puts swimming at the same number as running —
  a consequence of Quake 4's slower footspeed. `pm_swimSpeedFast` 200 applies in multiplayer and
  once `isStrogg` is set, which the campaign flips when the player's model changes to a strogg-team
  one. `idPlayer::OpenQ4_SwimSpeed` picks between them and applies the same haste/influence/turbo
  modifiers the run speed gets; `PM_SWIMSCALE` survives only as the wading clamp it also feeds.
- **`PM_WATERFRICTION` 2.0 → 1.0**, Quake 3's value. Doom 3 doubled it, and that extra drag was
  eating the acceleration before it ever reached the speed cap — most of why id Tech 4 swimming
  feels like treacle.
- Looping bubble trail from the head while submerged.
- Wade footsteps, finally reading the `snd_water_wade` key that retail `player.def` has carried
  since 2005 and that nothing had ever looked at.
- **Bug fixed**: `WaterJumpMove` applied `gravityNormal` — a unit vector — instead of
  `gravityVector`, so a water jump barely fell and had to wait out its 2000 ms timer.

**Other entities**

- `idGameLocal::LiquidContentsAtCollision / LiquidContentsAtPoint / LiquidTypeName /
  PlayLiquidImpact` — one shared liquid API for everything that is not the player.
- **Bug fixed**: the projectile water test only looked at the *hit entity's* contents, which is
  true for a water brush bound to an entity and never true for a world brush. Map water — the
  normal case — never splashed. Now tests the collision material too, in both trees; the MP tree
  had no splash code at all.
- **Bug fixed**: `rvPhysics_Particle` latched `inWater` permanently and permanently cleared
  `CONTENTS_WATER` from its member clip mask, so a projectile could detect exactly one liquid
  surface in its entire lifetime. The exclusion is now local to the move and `inWater` is
  re-derived from position.
- Buoyancy and drag for particle-physics projectiles and for rigid bodies.
- **Bug fixed**: `idPhysics_Base::IsInWater` returned `false` unconditionally, blinding every
  physics type that did not override it — articulated figures, monsters, actors, parametric movers.
- Hitscan masks, projectile clip masks and rigid-body masks widened from `CONTENTS_WATER` to
  `MASK_WATER`, so shots trace lava and slime surfaces instead of passing through them unseen.

**View and audio**

- `idPlayerView::LiquidAtEye` drives the audio muffle and the view treatment. Both key off the
  **eye position**, not `waterLevel`: `WATERLEVEL_HEAD` needs the whole bounding box under, and the
  camera sits 8 units below the top of that box standing and 16 crouched, so keying off water level
  would leave the screen clear and the audio dry while the view was visibly submerged.
- **Underwater view post-process** (`glprogs/underwater.{vs,fs}`, `RB_STD_Underwater` in
  `draw_common.cpp`): crossed dual-frequency sine refraction, a rotated six-tap soft focus whose
  radius grows toward the view edge, per-liquid absorption with chroma loss, vignette and faint
  caustics.
- It is a **scene pass, not a back-buffer one**. It runs inside `RB_STD_DrawView` after the world's
  own `_currentRender` overlays and before `RB_RenderDebugTools`, confined to
  `backEnd.viewDef->viewport` and `->scissor`, and gated on `RB_IsMainScenePostProcessView()`. So
  the HUD, menus, debug tools, mirrors, portal skies and in-world monitors are all left dry — only
  the 3D view is under the water. Verified by screenshot: the crosshair stays crisp and white while
  the world behind it is tinted, warped and soft at the edges.
- The scene texture is larger than the viewport, so texture coordinates arrive as `0..texScale`
  rather than `0..1`. The shader takes `texScale` as a uniform and normalises before doing anything
  positional; getting this wrong puts the focus mask centre in the wrong place and samples outside
  the view.
- **It is depth-aware.** The pass copies the depth buffer alongside the scene (the same way
  `RB_STD_CelWorldOutline` does) and reconstructs view-space Z from `projectionMatrix[10]/[14]`.
  Absorption is Beer-Lambert per channel, in-scattering fills back what absorption removes, and
  scattering blur and bloom radius both grow with travelled distance. This is what separates a
  volume from a tint, and none of it works without depth.
- The tint the game sends is **the transmittance at `fogDistance`**, so `pow( tint, travel )` is
  the extinction: a designer picks a colour and a range and the physics falls out. Water 1400
  units, slime 420, lava 110.
- **The edge treatment is a focus mask, not a vignette.** It never darkens; it drives the soft
  focus and the chromatic aberration. Classic corner darkening was tried first and rejected — it
  reads as a black frame rather than as water, and it disappears entirely in a dark scene.
- The state reaches the renderer through `idRenderSystem::SetUnderwaterView( amount, tint )`, which
  **returns whether the backend will actually draw it**. The Vulkan module supports only a fixed set
  of natively reimplemented material program families and no arbitrary GLSL, so it answers false
  (`vk_GLStubs.cpp`) and `idPlayerView` falls back to a flat colour wash. `r_underwater 0` produces
  the same fallback on GL. The amount eases in and out over ~1/6 s so breaking the surface does not
  cut.
- The tint the game publishes is an **absorption filter** — what the liquid lets through — not a
  wash laid over the top, because the shader multiplies the scene by it.

**Monsters and NPCs**

- `idAI::UpdateLiquid` — Quake 2's `M_WorldEffects` for openQ4: lava and slime burn monsters at the
  same rate and water-level scaling as the player, a submerged monster drowns after
  `pm_waterAir`, and breaking the surface splashes and sounds. `canBreatheLiquid` and
  `liquidImmune` on a monster def opt out of drowning and of lava/slime respectively.
- `idGameLocal::LiquidLevelForEntity` — Q3's `PM_SetWaterLevel` generalised to any entity's bounds,
  since only the player has an `idPhysics_Player` to keep water level for it. It costs a single
  point query for anything that is dry, which is the normal case.
- `idGameLocal::PlayLiquidSoundOn` / `PlayLiquidEffectAt` — the shared presentation path; `idPlayer`
  now delegates to these rather than carrying its own copies.

**Trails and sound**

- Smoke does not survive underwater. `idGameLocal::PlayLiquidTrail` draws the liquid's own wake
  effect along a segment, and both the projectile fly trail (`idProjectile::Think`, which swaps the
  effect on the liquid transition and restores `fx_fly` on the way out) and the hitscan tracers in
  `HitScan` fall back to it when the shot starts inside a liquid.
- **Sound occlusion across the surface.** The global muffle was not enough: an air/water boundary
  reflects most of the energy that hits it. `idSoundWorld::SetLiquidTest` takes a callback from the
  game — liquid lives in the collision world, which the sound system cannot reach — and the
  per-emitter spatialisation step that already does portal tracing uses it to mark emitters that
  are in a different medium from the listener. Those get `SOUND_LIQUID_BOUNDARY_OCCLUSION` on top
  of any portal occlusion.

**Bots**

- Navigation refuses to place nodes in lava or slime, so routes never cross them. Water stays in
  the graph because it is crossable.
- Bots swim up when submerged, climb when burning, and veto a step that would walk them into a
  hazard. Both trees.

**Content** (`content/baseoq4/pak0`)

- `materials/liquids_openq4.mtr` — water, calm water, slime and lava, all `translucent` because
  dmap seals a brush whose sides are all opaque and an opaque lava brush produces a pool nothing
  can enter.
- `materials/types/liquids_openq4.mtt` — `lava` and `slime` material types; Quake 4 ships only
  `water`.
- `def/liquids_openq4.def` — damage defs and the `liquid_openq4` presentation def that every sound
  and effect is keyed off, pointing at stock Quake 4 assets. Precached from `idPlayer`.

**Cvars**: `pm_waterAir`, `g_liquidDamageInterval`, `g_drownDamageMax`, `g_liquidScreenTint`.

## Testing

No retail or community Quake 4 map declares liquid contents, so there was nothing to test against.
Rather than build a map, the system grew a way to put a liquid volume anywhere:

- **`idLiquidVolume` / `func_liquid_openq4`** — a liquid volume that is a box rather than a brush.
  Mappers get it as a real entity; testing gets it via the `spawn` console command.
- **`g_liquidTestVolume`** (`water`/`slime`/`lava`) and **`g_liquidTestVolumeSize`** — drop one
  around the player as they spawn. The console route alone is not enough, because a successful
  `devmap` swallows the rest of the startup command buffer, so `+exec` after it never runs.
- **`g_debugLiquid`** — logs water level and type transitions, the air reservoir, and each damage
  tick.

Run with:

```bash
openQ4-client_x64.exe +set si_gameType singleplayer +set logFile 2 +set g_debugLiquid 1 +set g_liquidTestVolume lava +set g_liquidTestVolumeSize 8192 +devmap game/mcc_1
```

Verified in `game/mcc_1`, reading `qconsole.log`:

| behaviour | result |
| --- | --- |
| water level detection | `level 0 -> 3` on spawning inside the volume |
| water type per liquid | `0x4` water, `0x4000000` lava, `0x8000000` slime, named correctly |
| air drain rate | 150 per 60 frames = 2.5/frame, so 1800 air lasts 720 frames — Q3's 12 s |
| drowning ramp | 2, 4, 6, 8, 10, 12, 14, then capped at 15; health 99 → 9 → death |
| air refill on surfacing | reservoir back to 1800 the moment the head clears |
| slime damage | ticks every 500 ms scaled by water level; 100 → 72 → 44 → 16 → dead |
| lava damage | 100 → 15 → dead, about a second at full immersion — Q3-lethal |
| drown + burn together | air drains while slime burns, both clocks independent |
| monster lava/slime | every AI in the map burns; JUDD/EVANS 125 → 95 → 65 |
| monster drowning | JUDD/EVANS/PAULSON/DUNNIGAN 125 → 110 → 95 after twelve seconds under |
| invulnerable NPCs | Quake 4's story marines correctly ignore both, no special case needed |
| swim up | holding jump underwater rises through level 3 → 2 → 1 → 0, air refilling as it goes |
| swim speed | ~155-160 u/s measured with forward held, against Quake 3's 160 (was capped at 80) |
| underwater view | shader compiles and loads; water reads blue with edge vignette and soft focus |
| lava view | same pass, warm amber - red kept, blue cut - visibly distinct from water |

Getting a level to actually simulate unattended is its own problem. A loaded Quake 4 map can sit
waiting on input, and with no input the session never runs a game tic — the player spawns, one
think happens, and the frame counter stays at zero. What works reliably is to let the map load, then
`AppActivate` the process and send a couple of keystrokes:

```powershell
$shell = New-Object -ComObject WScript.Shell
$shell.AppActivate($p.Id)
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
```

Forcing the window to the foreground on a timer does **not** work — it disrupts the game more than
it helps, and was the cause of several runs that looked like feature failures.

**Three real defects the testing found**, all fixed:

1. **`idLiquidVolume` was never registered.** Raven does not use static class construction — the
   `CLASS_DECLARATION` macro only defines a `RegisterClass()` that `idClass::RegisterClasses()`
   must call explicitly from its `REGISTER()` list in `gamesys/Class.cpp`, "so they aren't
   dead-stripped". A new entity class that is not added to that list compiles, links, and then
   fails at runtime with `Class 'x' not found`.
2. **Damaging the player during a map's settle frames wedges the level load.** A player spawning
   into lava took the first burn tick during the settle frames at the end of `ExecuteMapChange`,
   and the map never finished loading — the game sat there with the player alive and the frame
   counter stuck at zero. Liquid damage now waits a second after spawn, and liquid events are
   suppressed entirely while `GameState()` is not `GAMESTATE_ACTIVE`.
3. **`waterType` carried non-liquid content bits.** `SetWaterLevel` probes with a `-1` content mask
   and stored the raw result, so `waterType` came back as `0x2004` or `0x1004` — water plus
   whatever trigger and AAS brushes overlapped the point. Masked to `MASK_WATER`.

Two smaller fixes came out of it too: the air drain was an integer division that turned Q3's twelve
seconds into fifteen (now spread Bresenham-style, exact with no saved carry), and the liquid damage
calls passed joint `0` as the hit location where `INVALID_JOINT` is meant.

Also worth knowing for anyone testing: **openQ4 only simulates while its window has focus**, so an
unattended launch that loses focus will load the map and then sit at zero frames. Repeatedly forcing
the window foreground from a script makes it worse, not better.

## Not done

- **Only the gameplay core was exercised.** Player and monster damage, drowning and water level are
  verified in a running game. Splashes, bubbles, wade footsteps, the underwater tint and the audio
  muffle are wired and compile, but were not visually confirmed; nor were bots in liquid, projectile
  splashes, or buoyancy. Those need a human at the keyboard or a purpose-built map.
- **Monsters do not swim or path around liquid.** They take the consequences, but their movement is
  unchanged: there is no wading slowdown for AI and no way for them to route around a lava pool,
  because AI speed is script-driven and the AAS carries no liquid data.
- **No swim animation.** The player animation state machine is entirely ground/air — `pfl` has no
  water bit, and `State_Legs_Idle` falls through to `Legs_Fall` when not on the ground, so a
  swimming player plays the falling animation. Retail `player.def` has no swim animation either, so
  this is new art, not just new code.
- **No AAS swim reachabilities.** There is no AAS compiler in the repo, so `AREACONTENTS_WATER`,
  `TFL_SWIM` and `TFL_WATERJUMP` can never be produced. SP bot water navigation is limited to the
  runtime behaviour above. The MP navmesh is generated at runtime and was fixable, which is why it
  was.
- **No moving liquid volumes.** `KeepContents` exists on `idStaticEntity` and `idDamagable` only;
  every mover hardcodes its contents, so a rising pool or a lava flow would need new code.
- **`trigger_hurt` overlap.** Maps that faked lava with a trigger over decorative water will
  double-damage if the brush is converted to a real lava material without deleting the trigger.
  Documented for mappers rather than solved in code.
- **`airTics` is not replicated.** The client drains its own copy for the HUD from the same
  deterministic water level; drowning damage stays server-side.
