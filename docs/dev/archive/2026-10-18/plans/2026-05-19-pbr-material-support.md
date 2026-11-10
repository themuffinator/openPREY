# PBR Material Support Plan

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

## Purpose

Add physically based material support to openQ4 without changing how shipped Quake 4 assets render by default. PBR must be an opt-in extension for new openQ4 materials and future replacement-content work, while the existing `bumpmap`, `diffusemap`, `specularmap`, ambient-stage, GUI, post-process, light, fog, BSE, and ARB2 compatibility contracts remain intact.

The short version: stock materials stay stock; PBR materials get a modern material model; every unsupported case has a visible fallback reason and a legacy rendering path.

## Implementation Status

As of 2026-08-23, openQ4 has an **experimental, default-off Milestone F implementation whose local Windows exit gate has passed**: the compatibility-safe PBR authoring foundation, guarded OpenGL PBR lighting, a deliberately narrow Vulkan direct-light subset, authored bounded OpenGL specular probes, and atomic bounded OpenGL clustered decals. Namespaced parser metadata, typed image lifecycle handling, classic fallback generation, scene-packet propagation, and material-resource records remain intact. Eligible metallic/roughness materials can enter the modern G-buffer and clustered-forward paths, use GGX/Smith/Schlick direct lighting plus a content-free analytic environment contribution, and carry albedo, normal, packed ORM, separate metallic/roughness/AO, or scalar material data, emissive, and `r_pbrDebug` data through the existing graph resources.

This is deliberately a guarded renderer capability, not a promoted whole-frame renderer: `r_pbrMaterials`, `r_rendererReflectionProbes`, and `r_rendererClusteredDecals` default to `0`; PBR never reinterprets stock materials; unsupported workflows, dynamic images, custom programs, unsafe geometry, unusual blend expressions, or unavailable modern resources retain classic ownership. The current implementation supports a packed glTF-style ORM map, separate metallic/roughness/AO maps, or scalar-only material values. Separate maps use dedicated direct samplers after the four-entry classic material table and are admitted only when the complete resource/shader contract is available. Visible OpenGL PBR and probe evaluation additionally requires `r_rendererModernVisible 1`; enabling a PBR or probe leaf alone does not promote a visible PBR frame. `r_pbrIBL 1` supplies a neutral analytic environment for explicitly PBR-authored materials without requiring a new content asset; `r_pbrIBLIntensity` controls only that contribution. A conventional one-stage `blend blend` source-alpha declaration is admitted to the ordered PBR forward path, while complex transparency stays classic. `r_rendererModernQuality 0` is the one-setting rollback for PBR, authored probes, and clustered decals regardless of their leaf cvars. The legacy frame owner remains authoritative whenever its complete transaction cannot be replaced, and `MODERN_LIGHTING_PARITY_PROVEN_DOMAINS` remains `0`, so this is not a player-facing stock-map visual or GPU-driven-lighting promotion.

The OpenGL probe path accepts explicitly authored light-material metadata into a fixed eight-cubemap atlas and no more than 32 frame records, then selects at most two probes for each cluster deterministically. The September PBR audit adds linear HDR storage, GGX-prefiltered specular mip levels, diffuse irradiance and a split-sum BRDF integration table. The analytic environment uses the same filtering and stays fixed in world space. Missing images, stale generations or exhausted capacity retain the analytic fallback. Probe lights are metadata and never contribute ordinary additive lighting, including when precomputed interactions exist. The [production-readiness plan](2026-10-04-pbr-production-readiness.md) later added box-projected probes (`boxParallax`) and in-engine capture (`bakeReflectionProbes`); Vulkan has its own [native consumer](../../../vulkan-pbr-probes.md). The clustered-decal path is also OpenGL-only: an atomic prepare/seal transaction publishes at most 1,024 records and 65,536 cluster references, while malformed, stale, incomplete, or overflowing input publishes no ownership and leaves the complete affected subset classic.

Current implementation and qualification evidence is tracked in the [September PBR audit](2026-09-20-pbr-rendering-audit.md). Its original 24-station laboratory adds scalar/packed/separate comparisons, all normal encodings, cutout/source-alpha coverage, emissive float captures, moving and multiple shadow casters, MSAA, tone-map references and fail-closed resource controls. This broader audit remains in progress; the earlier Milestone F exit does not establish production admission or complete backend parity.

Eligible full-viewport OpenGL HDR PBR scenes now preserve the authored fog/blend
phase between opaque geometry and ordered source alpha. The complete phase is
preflighted before use and retains classic fallback if any receiver or resource
is unsupported. Linear render-target comparisons check every opaque specimen
and a hidden-background transparency control, including exact restoration when
the light is removed. Encoded preview and cropped/multiple-root fog views retain native ownership.
Eligible opaque/alpha-test HDR receivers also sample existing baked irradiance
inside their PBR draw: metalness, diffuse Fresnel and AO shape the contribution,
which replaces environment diffuse while retaining specular reflections.
GL 3.3/4.5 material/IBL, normal-map, MSAA, fog/blend and reload controls pass;
81 v47 map controls and their limits are recorded in the audit. Existing LDR bakes remain LDR; multi-grid portal and
view-weapon blending still use the native path.

The Vulkan backend retains a bounded PBR scope. The v69 audit supports opaque and matching alpha-tested metallic/roughness materials with scalar, packed ORM or separate metallic/roughness data and optional XYZ, RG or Quake 4 AGB normals. It requires exactly one declared and active classic bump -> diffuse -> specular sequence and rejects duplicate/invalid/reordered or custom-lighting ownership. Direct lighting replaces the final interaction submit; a matching additive glow stage is replaced once with typed linear emission, including with zero direct lights. Mismatched masks/glows retain classic ownership. Native specular antialiasing filters final shading-normal variance, including curvature. Source-alpha transparency, IBL/probes and full scene color parity remain open. The original narrow packed-ORM evidence below retains its original date/binary identity; the [current PBR audit](2026-09-20-pbr-rendering-audit.md) records 68 controls each at 0x and 4x MSAA, including emission references, cutout coverage, restarts and mapped shadows. Raw FP16 tests additionally qualify finite, texture-modulated emission storage; this does not bound arbitrary multi-light sums.

The retained local evidence is under `.tmp/milestone-f-evidence/20260823-final/`. A current-source debug x64 build passed the static PBR/advanced-lighting contracts, the final 10/10 dependency-light native run, the final 2/2 focused engine rerun after an earlier 8/8 safe set, and all four retail-PK4 baseline roles. That baseline used 40 retail PK4s and zero loose retail files. The procedural fixture passed on forced GL 3.3, 4.1, 4.3, and 4.5 with zero GL/FBO warning signatures: each real plan reduced 24 source packets to five depth plus five ambient owners with `planFallback=0`, forward+ executed five draws, and the visible bridge executed with resources, source, and composition present. The GL 4.5 debug-7 image contained the exact green ownership marker in 639,507 of 921,600 pixels (69.39%). `r_rendererModernQuality 0` matched the leaf-disabled OpenGL images exactly on all four tiers.

The validation-enabled Vulkan fixture also passed and differed non-vacuously from its leaf-disabled control (per-channel RGB RMS 26.374685/20.829991/21.549890, maximum delta 252); the Vulkan master-disabled image then matched that control at exact RMS 0 and maximum delta 0. These results prove implementation, execution, and rollback, not broad visual-quality, authored-probe/decal scene, or RenderDoc coverage. All feature leaves remain default-off, `MODERN_LIGHTING_PARITY_PROVEN_DOMAINS` remains `0`, and final committed-package, platform/driver, retained-review, and release promotion remain pending. Checked items below distinguish this local implementation exit from those broader release gates.

## Suitability Review

This plan is suitable for openQ4 only if legacy fallback is treated as a first-class authoring contract, not as a nice-to-have conversion step. openQ4's shipped-content compatibility still comes from the classic material parser and the `SL_BUMP`/`SL_DIFFUSE`/`SL_SPECULAR` interaction model, so PBR metadata must never be the only runtime description for a material that can ship in `baseoq4/`.

Required adjustments:

- Use a namespaced `pbr { ... }` block as the canonical syntax. This adds one top-level parser entry point instead of many new general material keywords and keeps classic stage parsing easy to audit.
- Prefer dual-authored materials: classic `bumpmap`, `diffusemap`, and `specularmap` stages remain the seamless fallback for ARB2, legacy GL tiers, PBR-disabled runs, and any modern fail-closed case.
- Treat generated fallback as development convenience only. A generated fallback may keep a test material visible, but release validation should fail if shipped PBR materials depend on approximate generated classic stages.
- Do not promise that older Quake 4 or pre-PBR openQ4 binaries will ignore new PBR tokens. They generally will not. Backward compatibility for old binaries requires separate legacy material declarations or content overlays, not mixed new syntax.
- Keep explicit fallback ownership independent of PBR rendering cvars. A user disabling PBR must still get the authored classic material, not a missing/default material.

## Current Baseline

openQ4 currently has two material/rendering worlds that need to stay in sync:

- The legacy material parser in `src/renderer/Material.cpp` compiles classic stages into `SL_BUMP`, `SL_DIFFUSE`, `SL_SPECULAR`, and `SL_AMBIENT`. It adds implicit `_flat` and `_white` stages when an interaction would otherwise be incomplete, then sorts interaction stages into the order expected by the classic renderer.
- The classic interaction path in `src/renderer/tr_render.cpp` and `src/renderer/draw_arb2.cpp` decomposes a surface/light pair into one or more `drawInteraction_t` records with bump, diffuse, and specular images. This is the compatibility authority for shipped assets.
- The modern renderer already has a bridge through `ScenePackets`, `MaterialResourceTable`, `ModernGLShaderLibrary`, G-buffer, deferred-lite, forward+, and guarded visible-frame paths. These systems are default-off or promotion-gated and already expose fallback metrics.
- `r_enhancedMaterials` is an opt-in GLSL enhancement for existing classic materials. It is not PBR and should not become the PBR switch.

The design should use the modern material bridge instead of replacing the classic parser contract.

## Compatibility Invariants

- Existing material declarations must parse to the same classic stage list unless they use new PBR-specific tokens.
- Existing stock materials must not be reinterpreted as PBR by default.
- `r_renderer arb2`, `r_glTier legacy`, and default conservative startup must remain valid rollback paths.
- A PBR material intended for shipped content must include authored classic fallback stages or explicit legacy fallback maps. Generated approximation stages are acceptable for tests and local authoring previews, but they are not considered seamless enough for release assets.
- New PBR parser tokens are openQ4 material syntax, not legacy Quake 4 syntax. Do not require old binaries to ignore them; if old-binary compatibility is ever needed, ship a separate legacy declaration or content overlay.
- In openQ4, unknown tokens should still default the material as they do today, so real typos remain visible. The PBR parser should recognize only the `pbr`/`physicallyBased` block entry point at the top level, then validate all PBR tokens inside that block.
- No repo `q4base/` or replacement-asset dependency may be introduced to make stock maps work.
- All PBR features must fail closed in modern rendering: unsupported texture layout, shader tier, dynamic image, custom program, or material feature means fallback to classic material ownership, not partial lighting.

## Material Authoring Model

Add a top-level PBR metadata block to the material language. The preferred openQ4 authoring shape is dual-authored: classic stages first for the legacy interaction path, then a `pbr { ... }` block for modern PBR ownership.

```text
materials/example/pbr_panel
{
    bumpmap textures/example/panel_local
    diffusemap textures/example/panel_d
    specularmap textures/example/panel_s

    pbr {
        workflow metallicRoughness

        albedoMap textures/example/panel_albedo
        normalMap textures/example/panel_normal
        normalFormat tangentRG
        ormMap textures/example/panel_orm
        emissiveMap textures/example/panel_emit

        metallic 0.0
        roughness 0.55
        normalScale 1.0
    }
}
```

PBR-only materials are allowed during bring-up, but they still need a classic fallback before they are treated as shippable:

```text
materials/example/pbr_panel_preview
{
    pbr {
        workflow metallicRoughness
        albedoMap textures/example/panel_albedo
        normalMap textures/example/panel_normal
        normalFormat tangentRG
        ormMap textures/example/panel_orm

        legacyBumpMap textures/example/panel_local
        legacyDiffuseMap textures/example/panel_d
        legacySpecularMap textures/example/panel_s
    }
}
```

For conventional source-alpha PBR, keep the declaration deliberately simple: use one ordinary `blend blend` stage whose map is the PBR `albedoMap`, then provide the normal material PBR block. The direct path preserves ordered source-alpha blending and samples the PBR albedo alpha. Multiple blend/add/filter stages, alpha-tested blends, animated stage state, and other complex transparency are intentionally not promoted and remain on their authored classic path.

```text
materials/example/pbr_window
{
    {
        blend blend
        map textures/example/window_albedo
    }

    pbr {
        workflow metallicRoughness
        albedoMap textures/example/window_albedo
        normalMap textures/example/window_normal
        normalFormat tangentRG
        ormMap textures/example/window_orm
    }
}
```

Recommended initial tokens:

| Token | Meaning | Notes |
|---|---|---|
| `pbr { ... }` or `physicallyBased { ... }` | Starts PBR metadata for this material | Does not alter classic stage parsing by itself. Bare flags are not the canonical form. |
| `workflow metallicRoughness` | Uses metallic/roughness BRDF inputs | Initial supported workflow. |
| `workflow specularGlossiness` | Future compatibility path | Parse can record it before rendering supports it. |
| `albedoMap <imageProgram>` | Base color texture | Color data; sampled as albedo in PBR shaders. |
| `normalMap <imageProgram>` | Tangent-space normal texture | Must declare or infer normal encoding. |
| `normalFormat quake4AGB | tangentRG | tangentXYZ` | Normal-channel convention | Required for new `normalMap` authoring. `quake4AGB` may be inferred only when the PBR normal deliberately reuses a classic `bumpmap` image. |
| `metallicMap <imageProgram>` | Metallic data texture | Linear data. |
| `roughnessMap <imageProgram>` | Roughness data texture | Linear data. |
| `ormMap <imageProgram>` | Packed occlusion/roughness/metallic map | glTF-compatible: R = AO, G = roughness, B = metallic. |
| `aoMap <imageProgram>` | Ambient occlusion data texture | Multiplies indirect/ambient only. |
| `emissiveMap <imageProgram>` | Emissive color texture | Optional. |
| `metallic <expr>` | Scalar fallback or multiplier | Material expression register. |
| `roughness <expr>` | Scalar fallback or multiplier | Clamp perceptual roughness to `[0.045, 1.0]`; screen-space normal variance can broaden the highlight to control aliasing. |
| `ao <expr>` | Scalar fallback | Default `1.0`. |
| `emissiveColor <expr> <expr> <expr>` | Emissive multiplier | Default black. |
| `normalScale <expr>` | Normal XY scale | Default `1.0`. |
| `legacyBumpMap <imageProgram>` | Optional explicit ARB2 fallback bump | Used only when no authored classic `bumpmap` stage exists. |
| `legacyDiffuseMap <imageProgram>` | Optional explicit ARB2 fallback diffuse | Used only when no authored classic `diffusemap` stage exists. |
| `legacySpecularMap <imageProgram>` | Optional explicit ARB2 fallback specular | Avoids poor generated approximations. |
| `legacyEmissiveMap <imageProgram>` | Optional explicit ambient fallback | Generates an ambient/additive stage only when the material has no authored equivalent. |
| `autoLegacyFallback 0 | 1` | Allows generated preview fallback | Defaults to `1` for local development, but release validation should require explicit fallback for shipped content. |

Do not add `metalmap` or `roughmap` shorthand in the first pass. PBR materials will be rare at first, and clear names are worth the extra typing.

An image-program path is parsed as an expression, not as a raw filename. Use parser-safe asset names such as `procedural_panel_albedo`: a hyphen is an image-program operator and must not be used unescaped in a map path.

### Authored Specular-Probe Metadata

Author a probe as a dedicated point-light material. The light entity supplies
the origin, axis, and radius used as the probe volume; `openQ4SpecularProbe`
supplies only immutable cubemap and blend metadata:

```text
lights/openq4/probe_room
{
    openQ4SpecularProbe {
        cubeMap env/openq4/room_probe
        tint 1.0 0.95 0.9
        intensity 1.25
        blendFraction 0.25
        priority 16
    }
}
```

Use exactly one `cubeMap` (native face convention) or `cameraCubeMap` (camera
face convention) with a static cubemap image. Render targets, image programs,
mutable images, and 2D images fail the complete declaration. `tint` defaults to
`1 1 1` and accepts finite components in `[0,64]`; `intensity` defaults to `1`
and accepts `(0,64]`; `blendFraction` defaults to `0.25` and accepts `(0,1]` as
the fraction of the point-light radius used at the volume edge; `priority`
defaults to `0` and accepts an integer from `0` through `255`.

`boxParallax` (a flag, no value) makes the probe a box instead of a sphere:
its light volume, the light's `light_radius` half extents along its axes
around its origin, is the room the cubemap shows. Each reflection is looked up
where it leaves that box (box-projected parallax correction), so it lines up
with the room's walls for every receiver, and the weight fades in from the
box faces over `blendFraction` of the smallest half extent. A box may have
unequal half extents; a spherical probe still requires equal radii. Capture
the cubemap from the light origin, which `bakeReflectionProbes` does: for
every probe light of the loaded map with a native `cubeMap` it renders the six
faces from the light origin in the light's axes and writes them to
`<cubeMap>_px.tga` .. `_nz.tga` under `fs_savepath`, then reloads the image.
The capture omits post-process and glow stages, subviews, view models,
bloom, motion blur, tone mapping, exposure, CRT filtering, gamma/brightness
and authored probes, so it is repeatable. `cameraCubeMap` probes, non-point
lights and cube images shared by several probe lights are skipped. openQ4
searches `fs_savepath` last, so the command warns when another copy of the
faces would still load. Leave `light_center` at zero on probe lights: it
moves the probe and its box away from the light volume's scissor.

The probe light is metadata-only and never contributes an additive classic
light, even if ordinary light stages are present in the same material. Keep it
separate from visible classic lights. If the OpenGL probe transaction is
disabled, unsupported, incomplete, or over budget, PBR surfaces use the
analytic environment fallback; the metadata light does not become a classic
light. At most eight cubemaps can be resident, at most 32 probe records can be
published per frame, and each cluster selects at most two probes.

### Authoring Fast Path

Use an 8-bit tangent-space normal map and either one glTF-compatible ORM image or separate linear metallic, roughness, and AO maps. The packed route has the most portable binding contract: ORM is always **R = AO, G = roughness, B = metallic**. `tools/assets/pack_pbr_orm.py` packs separate input maps without colour-space conversion and deliberately refuses to overwrite an existing output unless `--force` is supplied:

```powershell
python tools\assets\pack_pbr_orm.py `
    --ao path\to\asset_ao.tga `
    --roughness path\to\asset_roughness.tga `
    --metallic path\to\asset_metallic.tga `
    --output path\to\asset_orm.tga
```

`--ao` is optional; omitting it writes white AO. The tool accepts source images Pillow can decode and writes `.png` or `.tga`. It is covered by `python tools\tests\pbr_orm_packer.py`; use a normal file destination rather than a link. Do not gamma-correct, premultiply, or use a colour LUT on normal, ORM, metallic, roughness, or AO inputs. Albedo and emissive use the exact sRGB transfer function, with mip filtering in linear light; the remaining maps stay linear data. Material AO attenuates indirect illumination only.

For a distributable material, dual-author ordinary Quake 4 `bumpmap`/`diffusemap`/`specularmap` stages or provide the explicit `legacy*Map` fields. `autoLegacyFallback 1` is a development preview and ARB2 safety net, not release-quality art. Keep generated PBR validation assets outside `content/` unless the project has intentionally approved them as shippable content. The repository's procedural fixture is original openQ4 test data generated only below `.tmp/`; it is validation scaffolding, not release art.

The legacy Windows Material Editor is not a supported openQ4 authoring workflow: it is not a Meson-built tool and this workspace does not ship its required `editors/material.def`. Use a text editor with the declaration form above, then run `rendererPBRMaterialSelfTest` and a windowed test-map probe. This avoids an obsolete editor silently dropping a `pbr { ... }` block during source round-tripping.

## Data Model

The live implementation stores this compact PBR metadata record on `idMaterial` rather than encoding PBR as extra classic stages:

```cpp
enum pbrWorkflow_t {
    PBR_WORKFLOW_NONE = 0,
    PBR_WORKFLOW_METALLIC_ROUGHNESS,
    PBR_WORKFLOW_SPECULAR_GLOSSINESS
};

enum pbrNormalFormat_t {
    PBR_NORMAL_UNSPECIFIED = -1,
    PBR_NORMAL_QUAKE4_AGB = 0,
    PBR_NORMAL_TANGENT_RG,
    PBR_NORMAL_TANGENT_XYZ
};

struct pbrMaterialTexture_t {
    idImage *image;
    bool present;
    int filter;
    int repeat;
    bool allowPicmip;
    bool noMips;
    bool highQuality;
    bool forceHighQuality;
};

struct pbrMaterialInfo_t {
    bool enabled;
    pbrWorkflow_t workflow;
    pbrNormalFormat_t normalFormat;
    pbrMaterialTexture_t albedo;
    pbrMaterialTexture_t normal;
    pbrMaterialTexture_t orm;
    pbrMaterialTexture_t metallic;
    pbrMaterialTexture_t roughness;
    pbrMaterialTexture_t ao;
    pbrMaterialTexture_t emissive;
    pbrMaterialTexture_t legacyBump;
    pbrMaterialTexture_t legacyDiffuse;
    pbrMaterialTexture_t legacySpecular;
    pbrMaterialTexture_t legacyEmissive;
    int metallicRegister;
    int roughnessRegister;
    int aoRegister;
    int normalScaleRegister;
    int emissiveColorRegisters[3];
    bool autoLegacyFallback;
    bool hasAuthoredClassicFallback;
    bool hasExplicitLegacyFallback;
    bool usesGeneratedLegacyFallback;
    bool usesApproximateLegacyFallback;
    bool legacyFallbackMissing;
};
```

Implementation details:

- Store PBR image references outside `stages[]` so `SortInteractionStages`, `AddImplicitStages`, coverage, classic lighting, and GUI/post behavior remain unchanged.
- Initialize and clear the PBR record in `CommonInit`/`FreeData`, then copy it out of parser-temporary state before `pd` is cleared. PBR data must not point into stack-owned parsing storage.
- Expose const getters such as `HasPBR()`, `GetPBRInfo()`, and targeted image/scalar helpers. Avoid exposing mutable parser internals.
- Include the PBR images in `ReloadImages`, `AddReference`, `SetImageClassifications`, `FreeData`, `Size`, `Print`, and material validation.
- Keep material expressions as the single scalar system. PBR scalar tokens should call existing expression parsing and use `shaderRegisters` at draw time.
- Use `TD_MATERIAL_DATA` for ORM, metallic, roughness, and AO. Do not load these as `TD_SPECULAR`, because that path may modify alpha and compression behavior for classic specular maps.
- Add a color-input usage or explicit PBR image flag for albedo/emissive if the final sRGB policy needs them to bypass the legacy `TD_DIFFUSE` cache identity. Do not let PBR albedo change how stock diffuse maps are cached.

## Parser Strategy

Phase the parser work in carefully:

1. Add a no-op parse path for top-level `pbr { ... }`/`physicallyBased { ... }` that records metadata and reports through `Print`.
2. Keep PBR keywords invalid outside the block. A stray top-level `workflow`, `albedoMap`, or `roughness` should still default the material, matching the current typo-visible parser contract.
3. Add image-token parsing through a shared helper that mirrors `ParseStage` image-option handling where needed: `nearest`, `linear`, `clamp`, `noclamp`, `zeroclamp`, `highquality`, `forceHighQuality`, `nopicmip`, and `nomips`.
4. Do not accept dynamic render maps, video maps, arbitrary `program`/`glslProgram`, or material-stage draw-state tokens inside the PBR block in the first pass. Those features must stay on authored classic stages until explicit modern support exists.
5. Load albedo as color data, normal as bump/normal data, and ORM/metallic/roughness/AO as linear material data.
6. Warn, but do not default, when a PBR material is missing optional maps and has valid scalar fallback values.
7. Default only true authoring errors: missing image program after a PBR image keyword, bad workflow enum, bad normal format enum, invalid packed-map channel specification, malformed scalar expression, duplicate mutually exclusive maps, or unclosed `pbr` block.

The existing classic shortcuts (`diffusemap`, `specularmap`, `bumpmap`) should remain untouched. If a material declares both PBR metadata and classic stages, the classic stages are authoritative for legacy rendering, and the PBR metadata is authoritative only for modern PBR-capable passes.

## Legacy Fallback

PBR must not require the modern renderer to be usable.

Fallback policy:

- If a PBR material already declares classic `bumpmap`, `diffusemap`, and optional `specularmap` stages, keep them and use them for ARB2. This is the preferred release path because it preserves the existing interaction contract exactly.
- If a PBR material declares `legacyBumpMap`, `legacyDiffuseMap`, `legacySpecularMap`, or `legacyEmissiveMap`, generate classic fallback stages from those explicit maps only for missing classic stage types.
- If no explicit classic fallback exists, synthesize an approximation after parsing only when `autoLegacyFallback 1` is in effect:
  - `normalMap` with `normalFormat quake4AGB`, `legacyBumpMap`, or `_flat` -> `SL_BUMP`
  - `legacyDiffuseMap`, `albedoMap`, or `_white` -> `SL_DIFFUSE`
  - `legacySpecularMap`, a constant low-intensity `_white` specular stage if scalar data can be represented safely, or `_black` -> `SL_SPECULAR`
- Do not generate a roughness-derived texture in the first pass. That would introduce a new image-generation/cache path and can be added later if it is proven necessary. Prefer explicit `legacySpecularMap` for assets that need close visual parity.
- Preserve material behavior that affects the legacy path: `coverage`, alpha-test, cull type, sort, polygon offset, `noShadows`/`forceShadows`, `surfaceParm` effects, and editor image selection must come from authored classic stages or explicit fallback metadata, not from PBR guesses.
- Emit a one-line material warning when fallback is generated or approximate, so authors know to provide better classic fallback maps.
- Add metrics for authored classic fallback, explicit generated fallback, approximate fallback, and fallback missing. Release validation should require zero approximate fallback for shipped `content/baseoq4/` PBR materials unless the project explicitly accepts a documented exception.

Generated fallback stages must use the same `ParseStage` machinery as the existing top-level `bumpmap`/`diffusemap`/`specularmap` shortcuts and implicit `_flat`/`_white` stages so draw-state, texture repeat, register, and image-loading behavior stays conventional. Run this before final `AddImplicitStages()`/`SortInteractionStages()` so the existing interaction cleanup still owns ordering and missing-stage completion.

## Material Resource Table

Extend `MaterialResourceTable` and packet material records to carry PBR semantics:

New texture semantics:

- `MATERIAL_RESOURCE_TEXTURE_ALBEDO`
- `MATERIAL_RESOURCE_TEXTURE_NORMAL`
- `MATERIAL_RESOURCE_TEXTURE_ORM`
- `MATERIAL_RESOURCE_TEXTURE_METALLIC`
- `MATERIAL_RESOURCE_TEXTURE_ROUGHNESS`
- `MATERIAL_RESOURCE_TEXTURE_AO`
- `MATERIAL_RESOURCE_TEXTURE_EMISSIVE_PBR`

Record additions:

- `bool hasPBR`
- `bool pbrModernReady`
- `int pbrWorkflow`
- `int pbrNormalFormat`
- `bool hasAlbedo`, `hasNormal`, `hasORM`, `hasMetallic`, `hasRoughness`, `hasAO`
- `bool hasAuthoredClassicFallback`, `hasExplicitLegacyFallback`, `usesGeneratedLegacyFallback`, `usesApproximateLegacyFallback`
- register indices for metallic, roughness, AO, normal scale, emissive color
- per-record fallback reason for PBR-specific unsupported features

Implementation notes:

- Keep the legacy `uTextureIndices` table ABI at four entries. Separate metallic/roughness/AO maps use direct sampler units 4, 5, and 6, so they cannot silently displace classic or shadow sampler bindings. Prefer packed `ormMap` when authoring portability-sensitive content.
- Preserve the existing classic `BUMP`, `DIFFUSE`, `SPECULAR`, and `EMISSIVE` semantics for non-PBR materials.
- Add metrics: PBR record count, PBR-ready record count, missing albedo/normal/ORM counts, separate-map count, packed-map count, authored-legacy-fallback count, explicit-generated-fallback count, approximate-fallback count, modern-PBR fallback count, and old-style classic record count.
- Add `rendererMaterialResourceTableSelfTest` cases for PBR packed ORM, PBR separate maps, scalar-only fallback, explicit legacy fallback, and unsupported workflow fallback.
- Keep the existing record `fallbackReason` meaningful for classic modern ownership. Add a separate PBR fallback reason/flag field instead of overloading classic fallback reasons in a way that would make stock material metrics harder to compare.

## Shader And Render Pipeline

Add PBR as new shader families, not as a mutation of existing legacy families.

Initial modern shader families:

- `GBufferPBR` opaque
- `GBufferPBRAlphaTest`
- `DeferredResolvePBR`
- `ForwardPlusPBR`
- `ForwardPlusPBRAlphaTest`
- `TransparentPBR` only after opaque/perforated support is stable

Keep existing legacy G-buffer/forward variants for classic materials.

Recommended G-buffer packing:

| Attachment | Format | PBR payload |
|---|---|---|
| `gbufferAlbedo` | RGBA8 or sRGB-aware equivalent after policy is decided | Linearized albedo RGB, alpha |
| `gbufferNormal` | Existing packed normal target initially | View-space normal, tangent sign/debug as today |
| `gbufferMaterial` | RGBA8 initially | R = metallic, G = roughness, B = AO, A = flags or specular fallback |
| `gbufferEmissive` | Existing RGBA16F where available, RGBA8 fallback | Emissive/light-grid payload |

BRDF requirements:

- Use metallic/roughness Cook-Torrance shading with GGX normal distribution, Smith visibility, and Schlick Fresnel.
- Clamp roughness to a small nonzero floor to avoid unstable highlights.
- Keep direct light inputs compatible with Quake 4 light falloff/projection images and `backEnd.lightScale` behavior.
- Apply AO to ambient/light-grid/indirect contribution, not direct light.
- Treat emissive as additive material output after direct lighting.
- Keep all math in the modern PBR path linear. Do not change the legacy gamma-ish path for classic materials in the same patch.

Color-space policy must be explicit before visible promotion:

- Albedo and emissive are color inputs and need a documented decode path.
- Normal, ORM, metallic, roughness, and AO are data inputs and must not be gamma-decoded.
- If the engine does not yet have robust sRGB texture state, decode albedo/emissive in shader under PBR-only code paths and document that as the initial policy.

## Runtime Controls

Add separate PBR controls instead of overloading enhanced materials:

| Cvar | Default | Purpose |
|---|---:|---|
| `r_rendererModernQuality` | `1` | Master permit for Milestone F quality domains. Set to `0` for one-setting rollback of PBR, authored specular probes, and clustered decals even if their leaf controls are enabled. |
| `r_pbrMaterials` | `0` initially | Allows modern PBR shader ownership for PBR-authored materials when the modern renderer gates also pass. |
| `r_rendererReflectionProbes` | `0` | Enables the authored bounded OpenGL specular-probe consumer for eligible PBR views. Incomplete probe ownership falls back to the remaining environment sources (the analytic studio environment only in the laboratory mode). |
| `r_rendererClusteredDecals` | `0` | Enables atomic bounded OpenGL clustered-decal ownership for complete eligible subsets. Rejected transactions remain entirely classic. |
| `r_pbrGeneratedLegacyFallback` | `1` | Allows approximate generated classic fallback stages for development/test PBR materials. Authored classic stages and explicit legacy fallback maps remain valid regardless of this cvar. |
| `r_pbrDebug` | `0` | Debug overlay: albedo, normal, metallic, roughness, AO, emissive, fallback state; mode `7` is a state marker (green = PBR shader, magenta = contract mismatch). |
| `r_pbrIBL` | `1` | Enables environment lighting (authored probes) for explicitly PBR-authored materials. It never changes stock material interpretation. |
| `r_pbrIBLIntensity` | `1` | Scales that PBR environment contribution from `0` to `4`. |
| `r_pbrAnalyticEnvironment` | `0` | Laboratory mode (not saved): adds the content-free analytic studio environment under `r_pbrIBL`, the reference lighting of the PBR laboratory. Production environment light comes from authored probes, baked grids and ambient lights (production-readiness Stage E). |
| `r_pbrInferFromLegacyMaterials` | `0` | Experimental legacy material reinterpretation for research only. Never required for stock support. |

`r_pbrMaterials 0` must not change existing rendering. `r_pbrMaterials 1` should affect only materials whose parsed metadata says PBR is enabled, and it is necessary but not sufficient: `r_rendererModernQuality`, `r_rendererModernVisible`, G-buffer/deferred/forward+ readiness, material-table readiness, geometry readiness, shadow policy, and pass-owner gates still decide visible ownership. The probe and decal leaf cvars follow the same master gate. Setting `r_rendererModernQuality 0` must restore classic ownership for all three Milestone F domains without requiring a list of settings.

## Stock And Procedural Test Candidates

Retail Quake 4 declarations do not currently contain `pbr { ... }` metadata, so there is no native stock PBR material to enable. The best real-asset candidate for authoring and map validation is `textures/medlabs/tubearmsplatform_fastener`: `materials/medlab.mtr` supplies its diffuse, local-normal-plus-height, and specular maps, and `game/medlabs` references the material in its compiled world. It is a useful high-frequency metal fastener surface, but `game/medlabs` is BSE-heavy and should be used only after a controlled map probe is clean.

For repeatable implementation checks, generate the original openQ4 fixture below the repository `.tmp/` tree:

```powershell
python tools\validation\generate_pbr_fixture.py --runtime-root .tmp\milestone-f-fixture
```

The standard-library-only generator creates deterministic 24-bit TGA albedo, `tangentXYZ` normal, and packed ORM images, a dual-authored material declaration, and a SHA-256 manifest. It reads or copies no external texture, shader, or material asset, and its output is temporary validation scaffolding rather than shippable `content/`. `tools/tests/pbr_procedural_fixture.py` checks deterministic bytes and hashes, material wiring, manifest provenance, TGA layout, and the `.tmp` containment rule. `tools/assets/pack_pbr_orm.py` remains the authoring helper for separate data maps; it reads an explicitly selected stored channel instead of deriving luminance and writes `R=AO`, `G=roughness`, `B=metallic`.

Run the generated material windowed on stock `maps/tools/mv2`, retain only engine-render-target screenshots, and compare the enabled case with `r_rendererModernQuality 0` plus the appropriate leaf-disabled controls. `gfxInfo` must expose exact PBR/probe/decal readiness and fallback reasons; `r_pbrDebug 7` must show PBR ownership without a magenta contract mismatch. The 2026-08-23 local campaign now records real PBR ownership on GL 3.3/4.1/4.3/4.5, an exact 639,507-pixel green debug-7 marker on GL 4.5, a non-vacuous validation-enabled Vulkan result, and exact master rollback on both APIs. Probe validation must separately exercise the eight-cubemap atlas limit, 32-record limit, top-two cluster selection, analytic fallback, and malformed/stale/capacity rejection. Clustered-decal validation must separately exercise the 1,024-record and 65,536-reference limits plus atomic zero-ownership rollback. The bounded dependency-light and engine contracts pass, but broad authored probe/decal scene review and RenderDoc evidence remain unclaimed release work.

## Implementation Phases

### Phase 0: Baseline And Gates

- [x] Record the current-source windowed stock SP load/save/reload/demo and pure MP server/auto-joined-client baseline, plus controlled leaf-disabled and `r_rendererModernQuality 0` fixture references. All four stock roles passed against 40 retail PK4s and zero loose retail files.
- [ ] Repeat every Milestone F leaf independently across stock SP and pure MP only if that broader matrix is selected for final release promotion; the local implementation gate does not claim this breadth.
- [x] Add `r_rendererModernQuality`, `r_pbrMaterials`, `r_rendererReflectionProbes`, `r_rendererClusteredDecals`, `r_pbrGeneratedLegacyFallback`, `r_pbrDebug`, `r_pbrIBL`, `r_pbrIBLIntensity`, and `r_pbrInferFromLegacyMaterials`.
- [x] Add `gfxInfo` lines that show PBR parser support, PBR modern support, and fallback status.
- [x] Add PBR metrics counters to the material-resource table.
- [x] Confirm from current-source SP/MP logs that PBR/probe/decal records remain zero on stock startup with legacy inference disabled.
- [ ] Acceptance: the final safe validation matrix passes, stock startup logs do not gain material warnings, and leaf cvar changes do nothing when no matching authored metadata is loaded.

### Phase 1: Parser Metadata Only

- [x] Add `pbrMaterialInfo_t` to `idMaterial`.
- [x] Parse `pbr { ... }` tokens into metadata without changing classic stages.
- [x] Add image loading for PBR maps with correct texture usage classes.
- [x] Update material lifecycle methods for PBR images.
- [x] Add parser validation tests through material decl validation.
- [x] Acceptance: PBR sample declarations parse, stock declarations remain metadata-free, and metadata enters only the guarded, default-off PBR visible path.

### Phase 2: Legacy Fallback For PBR Authored Materials

- [x] Detect whether a PBR material already has classic interaction stages.
- [x] Add explicit `legacyBumpMap`/`legacyDiffuseMap`/`legacySpecularMap`/`legacyEmissiveMap` support.
- [x] Add generated fallback stages for PBR-only materials as development fallback, not as release-quality fallback.
- [x] Report one aggregate approximate-fallback warning per material parse.
- [x] Track authored, explicit-generated, approximate, and missing fallback counts.
- [x] Add a self-test that creates a PBR-only material and verifies ARB2 sees bump/diffuse/specular interaction stages.
- [ ] Acceptance: PBR materials render something sane under the default ARB2 path, explicit fallback maps generate the expected classic stages, approximate fallback is visible in metrics, and stock materials remain unchanged.

### Phase 3: Material Resource Table Integration

- [x] Extend packet material records with PBR flags and first PBR texture handles.
- [x] Extend `MaterialResourceTable` semantics, records, fallback reasons, and metrics.
- [x] Dump PBR metadata in `rendererMaterialResourceTableDump`.
- [x] Update draw/submit plan fallback checks to understand PBR-ready versus legacy-ready materials.
- [x] Acceptance: modern side paths can identify PBR materials and explain why they are or are not renderable.

### Phase 4: PBR G-buffer Side Path

- [x] Add guarded PBR branches to the existing opaque and alpha-test G-buffer shader families.
- [x] Pack albedo, normal, metallic, roughness, AO, and emissive into graph-owned attachments.
- [x] Add `r_pbrDebug` material outputs (albedo, normal, metallic, roughness, AO, emissive, and an unmistakable PBR marker).
- [x] Keep the pass sidecar/default-off and preserve classic ownership on every unsupported PBR record.
- [x] Acceptance: the synthetic PBR command contract binds the expected G-buffer inputs and values; non-PBR records keep their classic shader route.

### Phase 5: PBR Direct Lighting

- [x] Add PBR deferred resolve for opaque PBR G-buffer records.
- [x] Add PBR clustered forward paths for opaque and alpha-tested PBR records.
- [x] Reuse clustered point/projected light records, light images, falloff images, shadow descriptors, and light-grid data; AO affects indirect light only.
- [x] Keep the GGX distribution, Smith visibility, Schlick Fresnel, scalar multipliers, and roughness floor directly covered by shader-source and synthetic-command tests.
- [ ] Retain a human-reviewed engine-TGA shaded capture of the original procedural PBR fixture with analytic IBL enabled.
- [x] Add a fail-closed Vulkan direct-PBR branch for opaque `tangentXYZ` metallic/roughness materials with packed ORM, reusing the established interaction normal/albedo/specular descriptor slots as normal/albedo/ORM.
- [x] Validate the Vulkan subset windowed and unshadowed on `maps/tools/mv2` with the original procedural packed-ORM fixture, validation enabled, a non-vacuous leaf-enabled/disabled image delta, and exact `r_rendererModernQuality 0` rollback.
- [ ] Retain the point-shadow-mapped Vulkan fixture and broader human visual review before making a wider Vulkan PBR qualification claim.

### Phase 6: Guarded Visible Ownership

- [x] Admit eligible PBR records when `r_rendererModernVisible 1` and the existing modern ownership gates are all satisfied.
- [x] Keep classic materials on their existing legacy or modern-classic routes.
- [x] Block modern PBR ownership for unsupported workflow/layout, dynamic image, custom shader, unsafe geometry, or missing graph resources.
- [x] Report PBR modern readiness and named resource fallback reasons through `gfxInfo` and material-resource diagnostics.
- [x] Retain real OpenGL plans on GL 3.3/4.1/4.3/4.5 with 24 source packets becoming five depth plus five ambient owners, `planFallback=0`, five forward+ draws, visible execution/resources/source/composition, and an exact green debug-7 ownership marker.
- [ ] Retain current-source human-reviewed PBR-owned opaque and source-alpha whole-frame engine-TGA images without forcing stock materials into PBR interpretation.

### Phase 7: Authoring And Tooling

- [x] Document material syntax, supported packing, test candidates, compatibility behavior, and rollback in `docs/dev`.
- [x] Decide Material Editor ownership: the legacy MFC editor is not Meson-built and lacks its required definition file, so it is explicitly unsupported rather than allowed to lose PBR source blocks.
- [x] Add an optional, tested import helper and guidance for glTF-style ORM maps (`tools/assets/pack_pbr_orm.py`; `R=AO`, `G=roughness`, `B=metallic`).
- [x] Generate original deterministic openQ4 validation assets only below `.tmp/`; do not incorporate external assets or ship the generated fixture as `content/`.
- [x] Acceptance: the declaration template, texture rules, ORM helper, fallback rules, and test commands allow artists to author a PBR material without reading renderer code.

### Phase 8: Optional IBL And Quality Layer

- [x] Add a PBR-only analytic diffuse/specular environment baseline behind `r_pbrIBL` and `r_pbrIBLIntensity`; it needs no content asset and does not alter legacy materials.
- [x] Add guarded authored OpenGL specular-probe support with a fixed eight-cubemap atlas, at most 32 records, deterministic top-two-per-cluster selection, and analytic fallback.
- [x] Replace the original base-mip approximation with GGX-filtered specular, diffuse irradiance and split-sum integration in the September audit. Box-projected parallax, in-engine capture and the native Vulkan consumer followed later.
- [x] Add guarded atomic OpenGL clustered-decal ownership bounded to 1,024 records and 65,536 cluster references, with zero published ownership on a rejected transaction.
- [x] Pass current-source dependency-light and engine contracts for probe atlas packing, bounded top-two selection, analytic fallback, and atomic malformed/stale/capacity decal rejection.
- [ ] Consider clearcoat, sheen, anisotropy, height/parallax, and detail normals as later material extensions.
- [ ] Acceptance for broad release promotion: retain authored probe/decal scene evidence beyond the passing bounded contracts; analytic IBL remains the complete PBR fallback when probe ownership is unavailable, and advanced quality features never become required for base PBR correctness.

### Phase 9: Promotion And Release

- [x] Extend renderer validation coverage for the PBR parser, material table, G-buffer, deferred, forward+, visible, source-alpha, analytic-IBL, authored-probe atlas/selection, atomic clustered decals, master rollback, and fallback contracts.
- [x] Run current-source windowed stock SP load/save/reload/demo and pure MP server/auto-joined-client gameplay with the Milestone F leaves at their default-off values; retain controlled enabled/disabled fixture runs separately.
- [x] Run the original procedural PBR fixture on `gl33`, `gl41`, `gl43`, and `gl45`, retaining engine-TGA ownership images and exact master-disabled controls. These prove PBR execution and rollback, not broad human visual-quality acceptance; `auto` remains part of general promotion coverage.
- [x] Run the procedural packed-ORM fixture through validation-enabled Vulkan unshadowed direct interactions with `r_pbrIBL 0`, including a non-vacuous enabled/disabled delta and exact master-disabled control. Authored probes and clustered decals remain OpenGL-only.
- [ ] Add the point-shadow-mapped Vulkan case and any wider stock/leaf matrix selected for final release promotion.
- [ ] Capture RenderDoc on forced modern tiers.
- [x] Record the local current-source implementation-exit evidence while leaving final committed-package, platform/driver, retained-review, and release promotion in carry-forward.
- [x] Update curated `docs/dev/releases/v0.12.0.md` notes before shipping.
- [ ] Acceptance: no stock asset regression, PBR feature documented, rollback documented, shipped PBR assets have authored/explicit legacy fallback with zero approximate fallback unless explicitly waived, and release notes are player-readable.

## Validation Matrix Additions

Add safe tests:

- [x] Parser metadata, scalar registers, image usage classes, normal format enum, and error cases through `rendererPBRMaterialSelfTest`.
- [x] Generated classic-stage fallback and explicit fallback maps through `rendererPBRMaterialSelfTest`.
- [x] Packet propagation plus PBR semantics, texture binding counts, packed/separate maps, and fallback reasons through `rendererScenePacketSelfTest` and `rendererMaterialResourceTableSelfTest`.
- [x] Guarded opaque PBR resource admission, G-buffer command/input packing, scalar propagation, `r_rendererModernQuality 0` rollback, and clustered-forward surface-owner deduplication through `rendererPBRVisibleSelfTest`; attachment-overlay readiness remains covered by `rendererGBufferSelfTest`, while PBR debug shader routes remain covered by `renderer_pbr_materials.py`.
- [x] G-buffer/deferred/forward PBR program-link readiness through `rendererPBRVisibleSelfTest`; direct texture-unit bindings, normal-format markers, scalar/BRDF source contracts, source-alpha admission, and analytic-IBL routes through `renderer_pbr_materials.py`.
- [x] Guarded visible PBR ownership admission on a synthetic packet frame through `rendererPBRVisibleSelfTest`.
- [x] Source-alpha PBR blend admission, ordered forward selection, and analytic-IBL uniform/shader contracts through the static `renderer_pbr_materials.py` contract.
- [x] Original fixture determinism, hashes, TGA layout, manifest provenance, material wiring, and `.tmp` containment through `pbr_procedural_fixture.py`.
- [x] Explicit stored-channel ORM packing and dependency-injected core behavior through `pbr_orm_packer.py`.
- [x] Run and retain the current-source PBR, authored-probe, clustered-decal, and master-rollback reports: final focused engine 2/2 after the earlier 8/8 set, static PBR/advanced-lighting passes, and the final native 10/10 pass.

Add gameplay/manual coverage:

- Stock SP map with `r_pbrMaterials 0`.
- Stock SP map with `r_pbrMaterials 1` and `r_pbrInferFromLegacyMaterials 0`.
- Stock MP listen-server case with the same two settings.
- Original procedural PBR fixture under `r_rendererModernVisible 1` with retained human-reviewed PBR-owned whole-frame engine-TGA images on each applicable OpenGL tier.
- Authored-probe fixture with atlas-ready and analytic-fallback controls, including record/cubemap limits and deterministic top-two cluster selection.
- Clustered-decal fixture with a sealed complete subset plus malformed, stale, incomplete, record-overflow, and reference-overflow zero-ownership controls.
- PBR test material scene under `r_renderer arb2`, `r_glTier legacy`, `r_pbrMaterials 0`, and `r_pbrGeneratedLegacyFallback 0` to prove authored/explicit fallback does not depend on modern PBR or approximate generation.
- One-setting Milestone F rollback with `r_rendererModernQuality 0`, plus legacy renderer/tier fallback with `r_renderer arb2` and `r_glTier legacy`.

Failure conditions:

- Any new stock material parser warning.
- Any PBR-disabled visual delta in stock captures.
- Any unsupported PBR material silently drawn by a partial modern path.
- Any `r_pbrInferFromLegacyMaterials 1` behavior appearing in default settings.
- Any generated fallback stage changing classic materials that are not PBR-authored.
- Any shipped PBR material depending on approximate generated fallback without an explicit release waiver.

## Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Stock `specularmap` content is mistaken for roughness or metallic data | Never infer PBR from classic stages by default. Keep `r_pbrInferFromLegacyMaterials 0`. |
| PBR normal maps use different channel conventions than Quake 4 bump maps | Require `normalFormat` for new PBR maps or warn loudly; support both Quake 4 A/G and common RG encodings. |
| Color-space mismatch makes PBR look wrong | Define PBR-only albedo/emissive decode policy before visible promotion; keep legacy path unchanged. |
| Texture unit pressure on GL 3.3 | Separate metallic/roughness/AO direct samplers are fixed at units 4–6 and are admitted only with a complete sampler contract; prefer packed `ormMap` for portability-sensitive content. |
| Legacy fallback looks poor | Prefer authored classic stages; support explicit `legacyBumpMap`, `legacyDiffuseMap`, and `legacySpecularMap`; warn and fail release validation when fallback is approximate. |
| PBR shader variants explode | Add dedicated PBR families with compact workflow flags; do not cross-product every legacy feature. |
| Modern visible path drops special effects or shadows | Reuse existing pass ownership and fallback gates; PBR cannot override those gates. |
| Authors ship materials that only work on modern tiers | Keep generated or explicit classic fallback as part of the definition of done. |
| New PBR material syntax is loaded by an old binary | Do not promise old-binary parsing. Provide separate legacy material declarations or overlays if old-binary compatibility becomes a project goal. |

## Code Targets

Primary:

- `src/renderer/Material.h`
- `src/renderer/Material.cpp`
- `src/renderer/Image.h`
- `src/renderer/Image_load.cpp`
- `src/renderer/ImageManager.cpp`
- `src/renderer/ScenePackets.h`
- `src/renderer/ScenePackets.cpp`
- `src/renderer/MaterialResourceTable.h`
- `src/renderer/MaterialResourceTable.cpp`
- `src/renderer/ModernGLShaderLibrary.h`
- `src/renderer/ModernGLShaderLibrary.cpp`
- `src/renderer/ModernGLExecutor.h`
- `src/renderer/ModernGLExecutor.cpp`
- `src/renderer/ModernClusteredLighting.h`
- `src/renderer/ModernClusteredLighting.cpp`
- `src/renderer/ModernSpecularProbeAtlas.h`
- `src/renderer/ModernSpecularProbeAtlas.cpp`
- `src/renderer/AdvancedLightingCore.h`
- `src/renderer/RenderSystem_init.cpp`
- `src/renderer/tr_local.h`

Secondary:

- `tools/tests/renderer_validation_matrix.py`
- `tools/tests/renderer_gameplay_benchmark.py`
- `tools/tests/pbr_procedural_fixture.py`
- `tools/tests/pbr_orm_packer.py`
- `tools/validation/generate_pbr_fixture.py`
- `tools/assets/pack_pbr_orm.py`
- `docs/dev/gl-renderer-modernization.md`
- `docs/dev/renderer-validation-matrix.md`
- `docs/dev/release-completion.md`
- `README.md` when user-facing support is ready

## Definition Of Done

The 2026-08-23 local Windows implementation exit satisfies the scoped
implementation, stock-compatibility, execution, and master-rollback portion of
this list. It does not by itself satisfy final committed-package,
platform/driver, RenderDoc, broad authored probe/decal visual, retained-review,
or release-promotion requirements.

PBR support is complete enough to ship when:

- Existing shipped Quake 4 materials render through the same default compatibility path unless explicitly opted into modern visible rendering.
- New PBR-authored materials parse, load, reload, reference-count, validate, and dump correctly.
- PBR-authored materials have a working ARB2 fallback, and shipped PBR materials use authored classic stages or explicit legacy fallback maps rather than approximate generation.
- Modern PBR G-buffer, deferred, and forward+ paths are cvar-gated, fail closed, and covered by self-tests.
- Authored OpenGL probes stay within eight cubemaps and 32 records, publish no more than two deterministic indices per cluster, and fall back to a world-anchored analytic environment. Both use GGX-filtered specular, diffuse irradiance and split-sum integration; box-projected parallax (`boxParallax`) and in-engine capture (`bakeReflectionProbes`) joined this contract in the production-readiness plan.
- OpenGL clustered decals publish only a completely prepared and sealed transaction within the 1,024-record and 65,536-reference limits; every rejected transaction retains classic ownership.
- `MODERN_LIGHTING_PARITY_PROVEN_DOMAINS` remains `0` until its separate visible-lighting parity gate is proven, and `r_rendererModernQuality 0` restores classic ownership for every Milestone F domain.
- PBR debug overlays show albedo, normal, metallic, roughness, AO, emissive, and fallback state.
- SP and MP validation passes with PBR disabled and enabled on stock assets.
- A PBR test scene validates modern visible output and legacy rollback.
- Documentation and release notes describe the feature, authoring syntax, compatibility behavior, and rollback path.
