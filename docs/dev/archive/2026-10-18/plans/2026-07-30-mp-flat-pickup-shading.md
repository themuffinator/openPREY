# Multiplayer flat pickup shading

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Status: implemented and validated on Windows x64. OpenGL received in-game
multiplayer validation; OpenGL and Vulkan passed build and shader-contract
validation.

## Player-facing result

Multiplayer players can choose one of four pickup presentations in
`Settings -> Game Options`:

| `g_simpleItems` | Pickup style |
| ---: | --- |
| `0` | Original models and materials |
| `1` | Legacy simple icons |
| `2` | Original models with icon-coloured diffuse layers |
| `3` | The same flat colour plus a soft upward-moving light sweep |

The existing values keep their original meaning, so old configs do not change
appearance. `g_mpFlatOpponentWeapons 1` independently applies the flat colour
to weapons held by opponents.

Both settings are archived, client-local presentation choices. They do not
affect snapshots, hit detection, server authority, or another player's view.

## Visual contract

- The override applies only to material stages classified as diffuse.
  Normal/bump, specular, emissive, ambient, decal, effect, and GUI stages keep
  their authored behavior.
- Alpha-tested coverage continues to use the authored texture. Translucent
  shells and ambient passes, including the bubbles around health pickups, are
  not replaced.
- Every surface of one pickup model uses one colour resolved from that
  pickup's authored icon. A future or modded entity can supply an explicit
  colour override; known stock icon families provide semantic fallbacks when
  their material colour is texture-driven rather than a constant.
- The sweep uses model-local vertical position and the entity's local bounds,
  so it travels from the bottom of a pickup to the top regardless of how the
  model is placed in the map. It is a soft, repeating lightness lift rather
  than a hard emissive stripe.
- The sweep is enabled only for world `idItem` entities in style `3`.
  Dropped and placed weapon pickups are items and therefore participate.
- First-person view weapons are hard-rejected by the renderer even if a caller
  accidentally sets the flag.
- Opponent-held world weapons may receive the flat diffuse colour but never
  the sweep. Team modes classify opponents relative to the local viewer;
  free-for-all treats every other player as an opponent. Spectator and demo
  viewing follow the existing local-viewer classification path.

## Data flow

The game library resolves the colour and places a presentation-only colour and
flags on `renderEntity_t`. The renderer copies that state into the frame's
`viewEntity_t`, along with normalized local-height bounds, so the back end does
not read mutable front-end entity state.

OpenGL and Vulkan consume the same contract at interaction submission:

1. reject view-weapon/depth-hacked surfaces;
2. replace only the diffuse interaction image with white;
3. multiply only the diffuse interaction colour by the resolved icon colour;
4. when requested, pass local height, bounds, and time phase to the interaction
   shader, which softly lifts the diffuse colour toward white inside the moving
   band.

The ordinary material, shadow-mapped material, and point-shadow material
interaction programs share the same calculation. Unsupported accelerated
paths fall back to the compatible interaction path rather than silently
showing the original diffuse texture.

Render demos serialize the presentation state. Older demos initialize it to
disabled, preserving their original appearance.

## Live updates

The existing `g_simpleItems` modified-state rebuild remains the single pickup
refresh point. Switching among any of the four styles frees and recreates item
render definitions immediately. Opponent-held weapon state is refreshed by
the existing per-frame multiplayer visibility update, so its toggle is also
immediate.

## Validation

- Static contract tests cover all OpenGL and Vulkan interaction shaders,
  diffuse-only submission, view-weapon exclusion, render-demo compatibility,
  game-library style handling, and settings/localization wiring.
- The standard Meson wrapper built the Windows x64 client, dedicated server,
  OpenGL and Vulkan renderer modules, and both SP/MP game modules, then staged
  the complete `.install/` runtime package.
- A stock `mp/q4dm1` OpenGL run exercised flat-colour and swept world ammo,
  weapon, and health pickups, a bot opponent, and a live style change without
  reconnecting.
- Timed close captures of `item_health_large_mp` confirmed that the lightness
  band moves while the translucent bubble remains authored. The first-person
  machinegun retained its original diffuse texture throughout.
- The runtime log confirmed that the staged MP module and modified interaction
  shaders loaded without renderer, material, GUI, or game-module errors.
- Focused regression tests passed for the flat-diffuse contract, settings
  coverage, language tables, Vulkan shader-header pin, cel shading, player
  visibility, Vulkan world interactions, and Vulkan shadows.
