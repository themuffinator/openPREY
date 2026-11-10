# Quake 4: The Awakening (`q4xbase`) support plan

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Status: in progress. This is the living plan for running the unreleased Raven/Ritual
expansion on openQ4. The gap analysis it works from is
[the support audit](../../../q4x-awakening-support-audit.md). What has changed for players
is summarised in [The Awakening on openQ4](../../../../user/awakening.md); keep that page
current when a change here reaches the campaign.

## Current architecture (1 October 2026)

Awakening is an optional **single-player campaign** built into the canonical
`src/game/` SP library in openQ4. Its independent additions are in
`src/game/awakening/`; `src/mpgame/` remains the ordinary multiplayer game.
The two companion repositories are historical import sources, not build inputs.
See [source provenance](../../../game-source-provenance.md),
[licensing](../../../../../LICENSING.md) and the
[consolidation/evidence plan](game-source-consolidation.md).

Single Player → Campaign queries loose files and PK4 indices without mounting
them. A ready installation requires the defining declarations/scripts and all
thirteen compiled campaign maps. Only selecting Awakening mounts `q4xbase`,
which keeps its saves/configuration separate from `baseoq4`. Its turret
substitution is scoped to the filesystem's active game directory. Retail,
Arena and online multiplayer unload expansion overrides through a full restart.
Both story campaigns load the trusted `baseoq4` SP module, ignoring old expansion
DLLs. Expansion menu/default configuration files cannot replace engine navigation.

The original leaked game binary and reconstructed GPL source remain behaviour
references only. No recovered implementation or proprietary art is imported.
Awakening multiplayer code, maps and pricing changes are excluded from this
integration. No expansion assets are distributed; installation is described in
the [campaign guide](../../../../user/campaigns.md).

The sections below retain the historical feature and content investigation.
References to separately linked layer modules describe the pre-consolidation
implementation; the architecture above governs current builds.

## Status

### Single player

| Class / feature | Maps | State |
|---|---|---|
| 10 new script events | all | Done |
| `riFireFX` (`func_fire_volume`) | m01, m01 part 2, m02, m03, m04 | Done |
| `riMonsterWalker` | m01, m01 part 2, m06 invasion | Done |
| `riMonsterRetch` (buffs allies) | m01 part 2, m02, m04, m05, m08 | Done |
| `riMonsterTank` (breakable launcher and chest) | m02, m04, m08, m09 | Done |
| `idTarget_ObjectiveBeacon` | m04, m05, m06, m06 invasion, m08 | Done (the compass that reads it is commented out of the shipped HUD) |
| `WeaponGoobGun` + `DOTEntity` / `FireDOTEntity` | m02 on | Done |
| `rvWeaponFreezeGun`, `WeaponSpikeGun` | player arsenal | Done, with freezing, sticky spikes and corpse pinning |
| `riMonsterTurret` (every turret spawn) | m01, m01 part 2, m04, m05 | Done |
| `riMonsterPainLord` | m05 | Done |
| `riMonsterValkaryne` | m08 (set piece), m09 | Done |
| `riVehicleSpeederBike`, `riVehiclePartBoost` | m06 invasion, the three m07 race maps | Done |
| `riVCWPulseCannon`, `riVCWMissileTurret`, `riProjectileSpaceRocket` | m03, m06 invasion | Done |

### Multiplayer

The drop's multiplayer maps run as listen servers with a bot in a live match: `q4xctf1-6`
in CTF, `q4xctf2` in Arena CTF, `q4xctf3` in DeadZone, `q4xctf5` and `q4xdm12` in DM, and
`q4xtourney1` in Tourney and Team DM. Only `q4xctf1-5` and `q4xdm12` are new. `q4xctf6`,
`q4xtourney1` and `q4xdm10`, `11` and `13`-`15` are Raven's post-release maps, already in
retail's `pak019.pk4`; the drop carries other builds of them, which win under `q4xbase`.
`q4xdm1-6` re-export retail's DM maps. The expansion's powerup numbering, its two new
powerups and its buy menu work (Phase 3). Its effects and materials name images that
neither it nor retail ships (`gfx/effects/fire/p_fire2a`, `gfx/mp/ctf_neutral_flagstrip*`,
`models/monsters/burn_misc_sm`); they load as the default image, as they would under
retail.

## Phases

### Phase 1 — the campaign plays (done)

Everything in the status table above, plus the engine work, the build, and the headless
harness `.tmp/awakening/run_q4x.py` (local, untracked) used to boot each map.

### Phase 2 — campaign polish (done)

- **Freezing** (done, in `openQ4-game`). Each `freezeEnemies` bolt adds 0.05 to an AI's
  freeze factor, capped at 0.9; the factor slows its animation (to a quarter at most),
  thaws at 0.3 a second and shows `common/freeze_overlay1` above 0.15. `filter_freeze`
  damage that would kill it freezes it solid instead: `common/freeze_death_overlay`,
  `snd_freezeDeathBegin`, animation stopped, and four seconds later (or when anything
  else kills it) `damage_freezegib` shatters it with `fx_freezegib`. Version 4 saves
  preserve the status, timer and animation modifiers; v3 solid ice recovers with
  a fresh shatter timer and partial chill thaws. See the
  [status and targeting regression record](../../../awakening-status-targeting.md).
- **Turrets** (done, `riMonsterTurret` substituted for `rvMonsterTurret`):
  `dynamicAccuracy` (spread tightens over `accuracyLerpTime` of firing),
  `delayedTracking` / `lockDelay` (turn sounds, and a pause before firing again),
  `scanAnim` (the security cameras sweep).
- **Sticky spikes and pinning** (done, in `openQ4-game`'s `idProjectile`). Retail's SDK
  declares a `sticky` flag and never reads it; the expansion's spike and Pain Lord
  projectiles set it. A sticky projectile that does not detonate on the world stays where
  it hits it (bound to a mover it hits), and one that kills an actor stays in the corpse,
  bound to the joint it hit, until its fuse runs out. `passThroughActors` spikes hurt a
  living actor once and glance off it instead of detonating; the spike has no bounce, so
  it drops away, as it did in the expansion's code. In single player a spike stuck in a
  corpse pins it once its ragdoll is up: a ball-and-socket joint from the body it hit to
  the first surface within `maxPinDistance` behind that body, free to swing 90 degrees
  about the spike's line, unless the corpse's def says `canBePinned 0` (the Tank and the
  Walker). The spike's `maxPinDistance` is 10, so a corpse is pinned only when it lands
  against a wall. The joint is a *transient* AF constraint, which `idPhysics_AF::Save`
  leaves out, so a game saved with a pinned corpse loads, with the corpse unpinned. None
  of these keys appears in retail content.
- **Scripted targets** (done, in `openQ4-game`'s `idAI`). `onlyTarget`, `onlyTarget2`, ...
  name the only actors an AI may take as an enemy (`subStringOnlyTarget` lets a name match
  by its start), and spawners pass them on as `spawn_onlyTarget*`. The set pieces rely on
  them: m03's Strogg shoot at invisible targets on the dropship rather than at the player
  inside it, m04's marine goes for one jumping grunt, m06's harvesters shoot at the
  trucks, m07's bridge duel keeps to its two marines and a gladiator, and m09's Valkaryne
  fights only the player.
- **Savegames** (done). `idAI` saves one attack offset per animation of its model. Stock
  models have at most 244 animations and openQ4's restore rejected more than 256; the
  expansion's marines have 540 (its reference marine 1015), so a game saved on m04 never
  loaded. The bound now follows the range of an animation number (32768).
- **Dead keys.** `iff`, `spawn_iff`, `bindOrientied` and `ignoreAAS` have no reader in
  the expansion's own code either. Three keys first filed here do have one (Phase 5):
  the hurt trigger's `velscale` (dictionary keys ignore case), the Strogg flyer's
  `canturn`, and `useMasterRoll` / `useMasterPitch`, which its monster physics reads
  for the space flyers bound to m03's spline movers. The movers, dropships and static
  models that also carry them ignore them.

### Phase 3 — multiplayer (done)

- `"TeamDM"` accepted as `"Team DM"` in `maps.def`, in the game and in the engine's
  create-server map list (done).
- **Powerups** (done, in `openQ4-game`'s multiplayer module). The expansion inserted
  Adrenaline at 12 in its `powerup_types` def, which pushes DeadZone and the team powerups
  one along, and added FC Armor Regen at 17. openQ4 keeps its own numbering and translates
  a content number through the def name `powerup_types` gives it
  (`idPlayer::PowerupForContentType`, `GetPowerupDefName`), so every retail number maps to
  itself and the expansion's DeadZone tokens stay DeadZone tokens. The two new powerups are
  appended (`POWERUP_ADRENALINE`, `POWERUP_FC_ARMOR_REGEN`); the powerup bits now travel as
  `POWERUP_MAX` bits instead of a short.
  - Adrenaline lends 400 health at once, less one second's share, and takes that share
    back every second while health is at max or above; it ends when health falls below max
    or the payback reaches 100. No map places it; `give adrenaline` works where its def exists.
  - FC Armor Regen, the fourth team special on the buy menu, builds armor 5 every half
    second up to 100 over max (capped at 255, the snapshot's byte) instead of letting it
    tick down. It stays with its buyer when they die.
- **The buy menu** (done). The expansion's `buymenu.gui` runs `sq_buy <item>` and reads 27
  `canbuy_*` states; its `default.cfg` binds `sq_buyMenu`. Both names are the `buy` and
  `buyMenu` commands, and the menu refresh fills retail's `buyStatus_*` states and the
  expansion's `canbuy_*` states from one table (firing retail's `update_buymenu` and the
  expansion's `redraw`). The expansion kept its prices in code, so the layer registers them
  (`BUY_ITEM_PRICE`, `src/mpgame/BuyPrices.cpp`), ahead of the content's
  `ItemCostConstants`. An item is for sale only when something prices it: that puts the
  nine weapon mods (each only with its weapon, once) and FC Armor Regen (team games) on
  sale in `q4xbase` and keeps them off it in `baseoq4`. A buy travels as impulse
  `IMPULSE_100` plus its index in one table; the Awakening's items fill the numbers retail
  left unused and the goob gun takes 128. The expansion's own check for the spike gun
  scope looked for a `weapon_scope` that does not exist, so the scope never sold there;
  openQ4 reads a mod's weapon from its def, and it does.
- Weapon groups (nothing to do). The expansion registers `g_weaponGroup0..7` (impulse
  lists a key would cycle through) and `g_weaponPickupPriority` (an auto-switch order on
  pickup), but its code never reads them: the only references to those cvars are their
  static registration and destruction. `default.cfg` sets the priority and the
  developers' own configs leave every group empty, so neither changes play there.

### Phase 4 — latent content (nothing reaches it)

Classes the expansion's code has but nothing in its content reaches:

- `WeaponGrappleHook`, with a rope mode in `idPhysics_Player`. No def gives it; the
  player def carries its beam and crosshair keys, `func_grapplenode` exists but no map
  places one, and `default.cfg` binds `g` to `_impulse27`, which openQ4 leaves unused.
- `rvWeaponConcussionGun`. No def gives it; the player def only carries its animations.
  The grenade launcher's concussion blast, which m02, m08 and m09 hand out, is unrelated:
  an ordinary weapon mod whose `def_projectile` swaps in a grenade with a wider, harder
  splash, applied by the same code as retail's mods.
- `riVehiclePartSplineTether`. The speeder bike's def comments its part out.
- `rvVehicleGravGun`. `vehicle_turret_gravgun` exists, but no map places it.

The compass (`gui::objectiveYaw`) waits on content that is commented out.

### Phase 5 — gameplay audit (done, 5 October 2026)

Every unique monster, weapon and vehicle was driven in headless runs (scripted input
through `openq4_testInput`, never real input) and its behaviour compared with the
expansion's code. What changed:

**Monsters**

- **Valkaryne (m09 finale).** She now runs her `requestDocking` script the first time
  she has an enemy, which the intro gives her with `becomeAggressive()` as it raises the
  Makron sphere's shields. She docks on her platform, where nothing hurts her, and fires
  death-ray volleys with about two seconds of warning; the arena's pillars block them.
  When the sphere dies she undocks and fights on foot, and her death starts the escape.
  The key names the function without its `map_m09` namespace, so a name that does not
  resolve is looked up as the one script function of that name in any namespace.
- **The beach death-ray turret (m01 part 2).** `ignoreplayer` now holds however an
  enemy reaches an AI (sight, a heard sound, a teammate's enemy, pain), in
  `idAI::IsAllowedTarget`. The expansion checked it only in its sight search, so the
  turret could take the player from the turrets beside it.
- **Pain Lord.** Headshots count. The def scales the head 2 and the legs 0.75 but lists
  the legs zone (`*root origin`, every joint) after the head (`*neck1`), and the later
  zone wins, so in the expansion a headshot was a leg hit. A zone that a later one
  swallows whole gets its joints back; no other stock or expansion def has one. His
  stuns, the dudes' shared pool, their tearing off, the enrage and the processing that
  dude damage interrupts all match the expansion.
- **Tank.** Its rockets scatter with the expansion's accuracy (10) once its launcher
  smokes, and breaking either armoured part plays the def's break effect, staggers it
  and ends its rocket attack. Its heart is the weak spot (head zone, 6 times damage);
  legs and plates take a twentieth.
- **Retch.** Its def asks for `aas96`, which m02 does not ship and m01 part 2 ships
  empty, so four retches could never move. A retch without its own AAS walks on
  `aas48`, which its bounds fit. In melee tactics it holds its lightning.
- **Elites.** Elite grunts (`q4xElite`) pull a player 128 to 256 units away towards
  them (`gravity_well`, every `gravityWellTime`); elite gunners switch three nailgun
  bursts in four for a spread fire; the tactical elites throw offhand grenades, at
  most every `grenadedelay`. Only the expansion's elite model has `throw_grenade`.
- **Space flyers (m03).** `canturn 0` and `noFaceEnemy` keep them on their spline, and
  they climb, dive and bank with their mover (`useMasterPitch`, `useMasterRoll`).
  The movers bank because the expansion's `idPhysics_Parametric` rolls every mover
  that faces along its spline: against the change of heading between the next two
  `g_splineRollLookahead` spans of the spline (500, five spline points), times
  `g_splineRollMultiplier` (2.0), both its defaults. Retail's movers never banked, so
  openQ4 banks only the Awakening's. m03's and m06's fighters ride such movers.
- The walker monster is a marine ally (team 0): it fights the Strogg, never the player.

**Weapons**

- **Goob gun.** Its projectile's `impactEntity` (the expansion's key name) now spawns the
  six-glob burst, which is precached. Burns of one kind on one victim merge instead of
  stacking without limit: a new one adds its damage up to three times the base and
  extends the burn. The flamethrower shows its alternate muzzle flash.
- **Freeze gun.** Chills, freezes solid and shatters four seconds later, and puts out
  the fire vents (m04's 50-health vent in about four and a half seconds of fire).
- **Spike gun.** A spike kills a Strogg marine outright, throws the body back
  (`impactForce`) and pins it to the surface behind.

**Vehicles**

- **m03 and m06 cannons.** The gunner cannot be hurt while seated (`useGodMode`), and
  leaving takes god mode away only if the cannon gave it. The turret swings back to rest
  when its gunner leaves (`resetOnExit`). m03's ammo-jam script freezes the turret until
  the jam clears (`allowDisableMovement`, on by default only in the Awakening, off in
  the walker's cockpit), and the turret does not snap round when it frees. The pulse
  cannon overheats after about seven and a half seconds of fire; its screens' JAMMED
  text, which the scripted jam also uses, stays up while the script has the gun
  disabled. Rockets lock on in 250 ms and home.
- m03's gun scripts set `g_fov` to 80 on entering and 90 on leaving. openQ4 turns that
  into an offset on the player's view, kept in the savegame, instead of overwriting
  the player's FOV setting.
- **m07 races.** The 122 slow-down volumes' `velscale` scales the speed of what they
  hurt. The bike touches them before its hidden rider, so it drops to a tenth of its
  speed or less and its shield takes the damage.
- The speeder bike cruises at about 690 units a second and boosts (crouch) to about
  1,090. m06's hacked Strogg fighters fly their splines, and the walker drives.
- A vehicle passes its script `guiEvent` and `setGuiParm` calls to its HUD as well as
  its world screens, as the expansion's `rvVehicle` did (its event table overrides
  both). m07's race scripts run the speeder bike's HUD race clock this way and m06
  sets the MCC cannon's health readout; neither appeared before. Retail's vehicle
  HUDs handle none of the events retail scripts send to vehicles.
- The expansion's `rvVehicle::UpdateHUD` also wrote `playerYaw` (the local player's
  view yaw) to the HUD and `vehicle_speed` to the vehicle's own screens (a quarter of
  its speed less four, never below 0), and its `idPlayer::DrawHUD` wrote `playerYaw`
  after the HUD stats. openQ4 does the same: the speeder bike's speedometer
  (`speeder.gui`) reads its speed and the m03 ship panels' view cones turn
  (`turretplayerhud.gui`, `q4xhud.gui`). Retail reads `playerYaw` only on weapon
  scopes, which are separate GUIs, and never reads `vehicle_speed`.
- `idPlayer::UpdateFocusCharacter` writes the character's talk state to the cursor
  as `npc_talkstate`, as the expansion's did; its `cursor.gui` shows `crosstalk_wait`
  at `TALK_WAIT`. Retail's cursor does not read it.
- The goob gun's alternate fire holds the player's flamethrower pose (`useAltFireAnim`
  picks `fire_alt` while `wsfl.zoom` is set), which shows in shadows, mirrors and
  third person.
- m09's flares are not the single quads `deform flare` expects; `R_FlareDeform` logged
  that about 340 times a second and now warns once per material.
- The pulse cannon's barrels (the turret model's `pulse_cannon_l` and `pulse_cannon_r`)
  move as the expansion's barrel helper moved them, through `JOINTMOD_LOCAL` joint
  mods: a shot kicks the firing barrel 32 units back along the pivot's forward axis at
  once and it slides home over 0.1 s; while the other weapon is selected both barrels
  fold over 0.4 s (12 units outward and 12 down, turned -7.5 degrees about the barrel's
  x axis, then -15 about its z axis) and unfold over 0.2 s when the cannon is selected
  again. The motion is not saved: a spawned or loaded cannon settles its barrels to the
  selection. The m03 cannons and m06's MCC cannon all use that model.
- The expansion's `rvVehiclePosition` ran a second per-frame virtual on every weapon
  but the selected one. openQ4 adds `rvVehiclePart::RunInactivePostPhysics`, empty by
  default so retail vehicles are unchanged: through it the pulse cannon cools and folds
  its barrels, and the missile launcher reloads its magazine, while the other weapon is
  selected.
- The m07 races fail by design: each lockdown gate closes on a timer and, if the player
  is not past it, the script triggers the area's `objectivefailed` item.
- `rvMonsterHarvester` turns in place only when its model has the turn animation.
  m07's background harvester is retail's cinematic `monster_harvester` (`noturn`, no
  turn animations), which failed the turn every 250 ms, logging a warning each time (158
  in one race) and skipping that think's attack checks. Retail's combat harvesters have
  the animations and turn as before.

**Audits.** Beyond the key scan, every `object_call` frame command in the
expansion's models resolves to a state of its class (state names ignore case; the
spike gun's `AddToClip` sits in a reload animation its clip size of 0 never plays),
every action its defs configure that its code initialises is initialised here, and
the script events and states its code registers match openQ4's, class for class
(`.tmp/awk/objcallaudit.py`, `actionaudit.py`, `evcompare.py`, `statecompare.py`).
The only difference left is `idAFEntity_Base`'s `canDamage`, which no script calls.
Every `gui::` state and named event the expansion's single-player GUIs use is now
written by openQ4's code or by a script, or the GUI sets it itself
(`guistateaudit.py`); what remains is multiplayer GUI state.

**Content holes found** (no code change helps): m09 has no `valk_forcefield` or
`mvr_makShields` for its script to show and hide; after the Valkaryne dies the escape
objective is given, then the script re-triggers the used `obj_project_navajas` and stops
there, harmlessly; m04's start inventory gives `weaponmod_goobgun_burst`, which has no
def; the m08 and m09 development give lists have typos; the Tank's rocket flash names a
joint (`gunBarrelReal`) its model lacks; m07's background harvester is retail's
cinematic one (`noturn`), which has no turn animations; `m07_race1.aas48` is empty, which
leaves its scripted gunner and fighters without navigation. m08's first-lab scientists'
`script_death` names `FirstLabCleared`, which the script never defines (the counter it
would have kept, `first_lab_enemy_count`, is declared and never used); m07_race2's
`guis/monitors/strogg/stroyent/stroyent_flow1.gui` exists nowhere; and the expansion's
charge effects use retail's `gfx/effects/fire/p_fire2a`, whose image retail never
shipped, so they draw nothing there, as on retail. m07_race1 and m07_race2 call
`setFOV` on the player, which only cameras handle in the expansion's code as in
retail's; the call is ignored with a warning. m09's `coldInHere` binds its breath
effects to `legs_channel`, a joint only the marine and player models have, and stops at a
`cold_breath_*` entity the map lacks; `trigger_once_70` calls `spawnTactical02`, which
the script has commented out, and `trigger_once_96` calls `spawnTrashCan01`, which it
never defines.

### Phase 6 — the chaingun turret's skin and effects (done, 15 October 2026)

The mannable Strogg chaingun (`vehicle_q4x_turret_chaingun` and
`vehicle_q4x_turret_chaingun_trench` on model `common_turret_strogg`: m01 part 1,
two in m04) was the alpha's one untextured model. Its four diffuse maps are grey
ambient-occlusion bakes of the high-poly model, its specular map is black, and its
drum texture (`common_turret_strogg04`) is a field of yellow dots that does not
line up with the cartridge rings in its own normal map. In game it rendered as
clay. Its weapon fired the player's hand-held round (`hitscan_bullet`): no tracer,
no muzzle light, no casings.

**Skin.** `materials/00_awakening_turret_openq4.mtr` re-declares the four
materials with openQ4's own colour, specular and glow maps
(`models/openq4/awakening/turret_strogg/`) and the expansion's normal maps. It sorts
ahead of the expansion's `q4x_mapobjects.mtr`, so its copies are kept; files named
`materials/*_openq4.mtr` now re-declare quietly, as `def/*_openq4.def` files already
did (`DeclManager_IsopenQ4OverrideDeclFile`). The palette follows Quake 4's Strogg
hardware: oxblood armour enamel on the shield and pedestal, oily gunmetal on the gun,
blued steel on the column and yoke, brass on the drum's feed lips and its rounds,
amber vent glow and a red sensor lens. The drum's rounds are painted on the 228
cartridge rings found in its normal map, and the disc is two-sided so the front
windows show them too (it faces only the gunner, so the front windows used to look
straight through the drum). The maps are generated by `tools/assets/awakening_turret/` (Blender bakes
plus a procedural painter); a rebuild reproduces them exactly. The drum windows'
outline is the only thing traced from the expansion's art. pak0 grows by 2.5 MB.

**Second pass (same day).** More variety in the finish: light brushed steel cover
plates on top of the gun, oxblood plates along its flank, a field-grey lower shield,
bone-coloured blocks in the pedestal band, chrome column bands and bearing rings,
and brass or steel bolt heads. Panel boundaries come from a watershed over the
normal map's creases, so a tone always changes on a real seam. Some edgings are
rubbed through to bright metal in patches. The three hoses on the gun's flank are
braided rubber with brass ferrules and red, amber and orange ID bands; the sleeve
under the receiver is ribbed rubber and the wires on the receiver and yoke are
orange and red. The first pass's position bake had been saved through the sRGB
curve (a float image left in linear colour space), so its 3D noise was distorted
and the muzzle heat tint and soot never landed; all bakes are now Non-Color data,
and the data bakes take one sample per texel so a rebuild matches byte for byte.

Generated image cache: a file inside a pk4 always reported timestamp 0, which was
what the generated `.bimage` cache checked, so a changed openQ4 pak texture under an
unchanged name kept the old cached image until `generated/images` was cleared. Fixed
separately on 15 October 2026: the cache now compares a pk4 member's zip CRC-32 and
length (see [generated image source identity](../../../loading-cache-modernization.md#generated-image-source-identity)),
so this repaint and later pak0/pak1 texture updates reach players with a cache.

**Effects.** While q4xbase is the active game, `idGameLocal::FindEntityDef` looks up
`<name>_q4x_openq4` before `<name>` (multiplayer keeps its `_mp` redirect; `inherit`
still reaches the original). `vehicle_chaingun_weapon_q4x_openq4` inherits the
expansion's turret weapon and adds only presentation: a hotter Strogg muzzle flash
(`effects/openq4/awakening/turret_muzzleflash`) with a 240-unit orange flash light,
a `hitscan_awakening_turret_chaingun` round with orange tracers on 60% of shots and
the walker's heavier impacts, casings, and smoke from the muzzle after a burst of 16
or more rounds. Damage, rate of fire and spread stay the expansion's.

- `rvVehicleWeapon::EjectBrass` never ejected a casing: it returned whenever
  `gameLocal.time` had passed `brassEjectNext`, which starts at 0. Casings now leave
  `ejectOffset` in the `joint_view_eject` joint's frame (Raven's code used the
  player's view axis and depth-hacked them over the view), every brass `delay`
  seconds, and live as long as a hand-held weapon's. No stock vehicle sets
  `def_ejectBrass`.
- `rvVehicleWeapon::EndBurst` plays `fx_burstSmoke` from the last muzzle when the
  trigger is let go after `burstSmokeShots` or more rounds. The count is presentation
  only and never saved.
- pak0 has no directory entries, so the decl manager never lists a folder only
  openQ4 adds: openQ4's effect files sit directly in `effects/` and carry the longer
  decl name inside, like the liquids effects. A file in `effects/openq4/awakening/`
  silently became an empty implicit decl.

Verified headless on m04 and m01 (seated and third-person firing, exterior views):
the skin, flash, flash light, tracers, casings and smoke all show, the expansion's
`q4x_mapobjects.mtr` raises no redefinition warning, an m04 run logs no warning the
pre-change run did not, and a stock Quake 4 map loads with no warnings. Quake 4's
tracers (`useEndOrigin` lines) draw their bright head at the impact end, so a still
frame often shows only a short streak near the target. Pinned by
`tools/tests/awakening_turret_skin_contract.py`.

## What the expansion's code taught us

Recorded because each one changed what "support" means here.

- A damage def with a `spawnclass` does no direct damage to actors in the expansion;
  its entity does all of it (the goob gun's 35-point hit is never applied). openQ4
  keeps that. Players, who have their own damage path, take the direct damage.
- The expansion's burn looked its effect up on the *victim*, where no def sets it, so
  the first flame never showed; openQ4 takes it from the damage def.
- The speeder bike's boost set `g_fov` and left it at 90; openQ4 widens the view through
  the vehicle instead and leaves the player's FOV alone. The boost fires on *crouch*
  (the bike's HUD says so), not a new button.
- The bike's script events drive a spline tether its def leaves out, so they do nothing
  in the expansion or here.
- The expansion's rigid bodies take friction values up to 10; Quake 4 drops the whole
  friction set when one passes 1. The bike's `friction_angular` of 5 is what stops it
  turning: on the 0.6 fallback a held turn spun it up past 500 degrees a second, and
  it turned two more full circles after the stick was let go. openQ4 raises the
  ceiling for the bike alone (`riVehicleSpeederBike::GetMaxFriction`), because a
  global change would also apply convoy1's landmine friction of 5, which retail drops.
  Rigid vehicles apply the def's friction again on restore, so older saves pick it up.
- Its hoverpads take `traceRelativeDirection`: the pad probes along that direction in
  the vehicle's frame and pushes straight back. The bike's antisuspensor probes up,
  holding it off ceilings, and its six bumpers probe out, holding it off walls. Probing
  down instead, as stock pads do, the antisuspensor pressed the bike towards the ground.
- openQ4's first rebuild of the bike's grip turned its velocity by twice the bike's
  heading every tic (it multiplied by the axis instead of projecting onto it), so
  thrust could not build speed on most headings. On open track three seconds of full
  forward thrust moved the bike about 25 units; it now covers about 1100 and reaches
  about 580 units a second.
- Vehicle turrets follow only the change in the player's own aim, so a script that
  seats the player and then turns the vehicle (m07's race start turns the bike 165
  degrees) leaves the guns pointing ahead, here and in the expansion. A gun camera
  facing backwards at the race start came from VR's seat tracking, not the bike.
- The finale Valkaryne's `requestDocking` names m09's `valkaryne_dock`, which the
  expansion's code parses and never calls. m09's script docks only the descent's
  set-piece Valkarynes, so the finale's never docked (Phase 5). She spawns with her
  ranged and melee attacks switched off.
- `ai_valkaryneShots` is registered and never read, and so are the weapon-group and
  pickup-priority cvars.
- Some of its map scripts call events their target classes do not have, in its own game
  code as much as in openQ4's: `playCycle` on m04's security cameras (turrets) and
  `becomeSolid` / `becomeNonSolid` on m02's `func_static` leaper clips. The calls do
  nothing and openQ4 logs "not supported", as the SDK does. The expansion DLL's event
  tables, read statically, register those events on the same classes as retail.

## Validation

- `.tmp/awakening/run_q4x.py <map>` boots a map in a hidden client with an isolated
  savepath and runs an after-load cfg (the Awakening content comes from the drop at
  `E:\Games\Quake_4_Alpha-main`).
- `damage <entity> 1 damage_goobDirect` with `g_debugDamage 1` shows the burn ticking
  once a second on an AI.
- Every campaign map must load, spawn its entities without class errors and run to its
  after-load quit.
- `.tmp/awakening/save_sweep.py` (local) saves every campaign map a few seconds in and
  loads it in a second client. A load passes when nothing errors after the savegame
  banner and the after-load cfg, which only runs once the restored map is live, echoes
  its marker. `--game baseoq4` runs it on stock maps.
- Gameplay probes never synthesise real input. The cheat `openq4_testInput <msec>
  [attack] [zoom] [run] [crouch] [jump] [forward|back|right|left <0-127>] [aim <entity>]
  [yaw|pitch <deg/s>] [impulse <n>]` holds buttons, movement, turning and one impulse on
  the local player's usercmd for a stretch of game time; turning moves the usercmd's
  angles as a mouse would, so vehicle turrets follow it, and `impulse 1` picks a
  vehicle's second weapon. `openq4_viewReport` prints the player's view (a gunner's
  follows the turret), field of view and god mode. `ai_debugActions <name|*>` prints an
  AI's actions, attacks and the Awakening's docking, buffs, part breaks and freezing.
  `damage <entity> <n> [def] [joint]` lands a hit in a joint's damage zone, and
  `g_debugVehicle 1` reports the cockpit guns' overheating, cooling and lock-on.
- `.tmp/awk/awkprobe.py <tag> --map game/<map> --cfg <cfg>` (local) boots a campaign map
  hidden, with an isolated savepath, and runs a probe cfg after it loads; the Phase 5
  probes are its `probes/*.cfg`. Console `script` lines cannot hold string literals
  (vectors in single quotes can), and a map's own script variables are reachable by
  namespace (`m06b::spawnedFighter`).
- `.tmp/awakening/pin_test.py` (local) launches a spike at the world and at a fresh
  Strogg marine on m04 with `openq4_launchTestProjectile`, and reads `g_debugDamage`'s
  stick and pin reports; it then saves and loads the game with the corpse pinned.
- `.tmp/awakening/onlytarget_test.py` (local) spawns a Strogg marine facing the player on
  m04 with `noDamage 1` (so the level's marines cannot kill it first): with
  `onlyTarget player1` it hurts the player, with `onlyTarget nobody` it never does.
- `run_q4x.py mp/q4xdm1 --mp "Team DM"` starts a listen server; with `net_allowCheats`,
  `addbot` and `serverForceReady` the match goes live, and `openq4_reportMPWorld player1`
  reads the player back. `.tmp/awakening/mp_phase3_test.py` (local) picks up a spawned
  Adrenaline, buys the spike gun, its scope and FC Armor Regen, and picks up a DeadZone
  token; `mp_stock_buy_test.py` checks that `baseoq4` buying is unchanged. Game time trails
  the real-time waits in a hidden run, so waits are generous and checks look for steps,
  not totals.
- `.tmp/awakening/script_sweep.py` (local) fires every `trigger_*` of each campaign map in
  file order, with the map's `target_endlevel` removed, god mode and `notarget`, under
  cdb so a crash reports a stack. All 13 maps run to the end without an error or a
  crash. Firing sequences out of order makes warnings of its own (scripted moves that
  cannot start, entities a sequence already removed, which a plain boot never shows);
  the rest are the script calls above, retail's harvester lacking the `turn_90_lt` its
  code asks for, and m09's ragdoll marines, which spawn with `spawn_health 0` on purpose.
- `.tmp/awakening/mp_maps_boot.py` (local) boots the expansion's multiplayer maps in the
  gametypes listed under Status, adds a bot, forces the match live and reads the player
  back.
- `.tmp/awakening/levelshot_test.py` (local) checks `openq4_mapLevelshot` for the
  expansion's maps, and that stock maps keep their levelshots.
- For interactive testing the expansion's content sits in the development savepath,
  `.home/q4xbase/`, copied from the drop without its leaked `gamex86.dll` and never
  committed. The `(SP) Awakening ...` and `(MP) Awakening ...` launch configurations run
  it from there, with retail content from the Steam install. Like the stock entries, they
  cover the menus and every map the expansion carries (13 campaign maps, 19 multiplayer
  maps), each on GL and on Vulkan, and the multiplayer ones start at the join screen
  (`ui_autoJoin 0`). `launch_entry_check.py` (local) runs a map entry's arguments headlessly
  against an isolated copy, and `launch_menu_check.py` does the same for a menu entry.
