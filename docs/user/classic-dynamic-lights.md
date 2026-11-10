# Classic Dynamic Lights

> **Development documentation:** This page follows the current source tree and may describe changes newer than the public download. See [release status and released-version guides](release-status.md) before using it with a release package.

Quake II and Quake III lit the world from the action itself. Every muzzle flash threw a pool of light
across the room, every rocket and plasma ball carried its own glow down the corridor, and every
explosion flashed the walls for a tenth of a second. Quake 4 replaced that with authored BSE effects,
and most of the shipped effects carry no light at all: apart from the single-player rocket and
grenade trails, player projectiles are unlit, and **no explosion in the game flashes the room**.

openQ4 adds that classic layer back. It is on by default.

## Quick Reference

| Setting | Default | Scope | What it does |
|---|---:|---|---|
| `g_classicDynamicLights` | `1` | SP and MP game code | Quake II/III style dynamic lights on muzzle flashes, bright projectiles and explosions. |
| `g_classicDynamicLightScale` | `1` | SP and MP game code | Radius multiplier for those lights, `0.25` to `4`. |

Both are archived, so a change survives a restart.

## What it adds

**Muzzle flashes.** Firing raises a short, wide world light at the barrel — roughly 100 ms, and half
again the radius of the weapon's own authored flash. It is layered on top of the stock flash rather
than replacing it, so the shot reads as a punchier pop that briefly reaches further into the room.
Weapons that carry no flash light of their own get one from this.

**Bright projectiles.** A rocket, plasma bolt or dark matter sphere carries a light with it. This
only fills gaps: a projectile whose def authors its own light (`mtr_light_shader`) keeps that light
untouched, and the single-player rocket and grenade — whose shipped trail effects already contain a
light segment — are left alone so their glow is not doubled. Their multiplayer trails carry no light
segment, so those do take the classic light.

**Explosions.** A detonation flashes the surrounding geometry and fades over 120–400 ms depending on
what went off. This is entirely new: nothing in the shipped explosion effects lights the room.
Exploding barrels and damagables get it too.

Bullets, nails, debris and glass deliberately get nothing. They are not bright, there are far too
many of them in flight to afford lighting them, and Quake II and Quake III did not light them either.

## Colors

The colors are taken from the shipped Quake 4 assets rather than invented, so a classic light reads
as part of the effect it belongs to instead of a wash of arbitrary color over it.

Muzzle flashes use the firing weapon's own `flashColor`, whatever a mod sets it to. For stock
weapons that is:

| Weapon | `flashColor` | Reads as |
|---|---|---|
| Blaster, Hyperblaster, Gauntlet | `0.7 0.8 1` | blue-white |
| Machinegun, Shotgun, Nailgun | `1 0.8 0.4` | warm white |
| Rocket Launcher, Grenade Launcher, Napalm Gun, Dark Matter Gun | `0.99 0.84 0.31` | amber |
| Railgun | `0.72 1 0.9` | pale green-white |
| Lightning Gun | `0.5 0.8 1` | pale blue |

Projectile and explosion colors come from the light segments Raven did author elsewhere in the same
asset set:

| Class | Color | Source |
|---|---|---|
| Rocket | `0.906 0.518 0.161` | `effects/weapons/rocketlauncher/fly.fx` |
| Grenade | `0.973 0.286 0.086` | `effects/weapons/grenadelauncher/trail.fx` |
| Napalm | `0.922 0.545 0.322` | `effects/weapons/napalmgun/globburn.fx` |
| Dark matter | `0.502 0 1` | `effects/weapons/dmg/core.fx` |
| Energy bolts | `0.7 0.8 1` | the energy weapons' own `flashColor` |
| Explosions | `1 0.824 0.290` | `effects/monsters/strogg_flyer/bomb_burst.fx` |

## Content overrides

An entity def can override the class the table picks for it:

```
"classic_light"         "0"             // never give this one a classic light
"classic_light_color"   "1 0.5 0.2"     // use this color instead of the table's
"classic_light_radius"  "180"           // tracking light radius, in units
```

`classic_light_radius` also overrides the "the shipped effect already lights this" rule, so a mod
that replaces the single-player rocket trail with an unlit one can ask for the classic light back.

## Cost and tuning

Each of these is a real light in this renderer, not the cheap vertex tint it was in Quake II. They
are all unshadowed, at most 24 one-shot flashes are alive at a time, flashes more than about 3000
units from the viewer are skipped, and the oldest flash is recycled when the pool is full.

If the effect is too strong for your taste, lower `g_classicDynamicLightScale` before turning the
feature off — `0.5` keeps the character at half the reach. Setting `g_classicDynamicLights 0` retires
every live flash immediately and stops new ones; projectiles already in flight keep the light they
were launched with until they expire.

`g_projectileLights 0` still hides projectile lights, classic ones included, and `g_muzzleFlash 0`
still suppresses muzzle flashes.

## Looking at them

With cheats enabled, `testClassicLight` raises the flashes in front of you without firing a shot:

```
testClassicLight                                  // one muzzle flash and one explosion
testClassicLight muzzle weapon_railgun            // that weapon's flash color
testClassicLight explosion projectile_dmg         // that projectile class's detonation flash
```
