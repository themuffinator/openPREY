# Advanced Screen-Space Lighting

> **Development documentation:** This page follows the current source tree and may describe changes newer than the public download. See [release status and released-version guides](release-status.md) before using it with a release package.

openQ4 provides three experimental, independently controlled screen-space
lighting effects on OpenGL and Vulkan:

- view-aligned froxel volumetrics;
- screen-space reflections (SSR); and
- screen-space diffuse global illumination (SSGI).

They are optional, default off, and do not alter the installed Quake 4 assets.
The effects share the native scene-presentation pass, run before temporal AA
when TAA is enabled, and leave the HUD, menus, and console at native resolution.
Engine screenshots include the effect result.

## Enable and roll back

The Milestone F master permit must be on. It defaults to `1`, while each effect
leaf defaults to `0`:

```text
set r_rendererModernQuality 1
set r_rendererFroxelVolumetrics 1
set r_rendererSSR 1
set r_rendererSSGI 1
```

Use any subset of the three leaf settings. Set
`r_rendererModernQuality 0` for immediate one-setting rollback of these effects
and the other experimental Milestone F lighting domains. The renderer publishes
an exact zero-feature packet when the master is off, even if archived leaf
settings remain enabled.

## Controls and bounds

| Setting | Default | Effect |
|---|---:|---|
| `r_rendererFroxelVolumetrics` | `0` | Enables bounded view-depth volumetric integration. |
| `r_froxelVolumetricDensity` | `0.00012` | Base extinction density, clamped to `0.00001`--`0.01`. |
| `r_froxelVolumetricMaxDistance` | `2048` | Maximum integrated world-space distance, clamped to `64`--`8192`. |
| `r_froxelVolumetricSlices` | `12` | View-depth slices, clamped to `4`--`16`. |
| `r_rendererSSR` | `0` | Enables bounded depth/normal screen-space reflections. |
| `r_screenReflectionIntensity` | `0.35` | Maximum reflection contribution, clamped to `0`--`1`. |
| `r_screenReflectionMaxDistance` | `512` | Maximum view-space ray distance, clamped to `32`--`2048`. |
| `r_screenReflectionSteps` | `10` | Ray-march steps, clamped to `4`--`16`. |
| `r_rendererSSGI` | `0` | Enables fixed eight-tap screen-space diffuse GI. |
| `r_screenGIIntensity` | `0.25` | Maximum GI contribution, clamped to `0`--`1`. |

Changing a leaf or tuning value invalidates temporal history so the new result
does not blend with stale lighting.

## Deliberate limitations

These are bounded scene-colour/depth effects, not replacements for authored
lighting:

- Froxel volumetrics integrate analytic ambient/directional scattering through
  view-depth slices. They do not inject every scene light, cast volumetric
  shadows, or supply a persistent world voxel volume.
- SSR reconstructs normals from depth. It has no material roughness/G-buffer
  input, cannot see off-screen or occluded colour, and keeps the current scene
  colour when a ray has no usable hit.
- SSGI uses eight depth-derived neighbour samples. It is a local diffuse
  approximation, not a multi-bounce world-space light solver.

Missing scene colour/depth or shader resources fail safely to the established
presentation path. These effects do not promote GPU-driven visible-lighting
ownership; the classic renderer remains authoritative.

## Performance and troubleshooting

Each enabled leaf adds bounded work to one full-screen presentation pass. SSR
step count and froxel slice count are the main quality/performance controls.
Test the effects individually first, particularly at high resolutions.

If an effect is absent:

1. Check that `r_rendererModernQuality` and the intended leaf are both `1`.
2. Run `gfxInfo` and check the renderer log for shader or framebuffer errors.
3. Test with the default tuning values and native resolution.
4. Set `r_rendererModernQuality 0` to confirm the classic rollback path.
