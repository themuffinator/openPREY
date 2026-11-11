# Retail Prey Decl Audit

This audit checks openPREY's decl system against the shipped Prey (2006) decl
files and the retail engine (`PREY.exe`, 1.4 patch, November 2007). The Quake 4
audit in [retail-q4-decl-parity-audit.md](retail-q4-decl-parity-audit.md)
covers the inherited Raven parsers. This one covers what Prey's own assets and
engine need.

## Decl Types And Folders

Every top-level decl header in `pak_data.pk4`, `pak_sound.pk4`, `pak_en_v.pk4`
and `pak_en_t.pk4` uses a registered type:

| Folder | Extension | Types found in retail files |
| --- | --- | --- |
| `materials/` | `.mtr` | implicit `material`, `table`, `skin` |
| `skins/` | `.skin` | implicit `skin`, `skin` |
| `sound/` | `.sndshd` | implicit `sound` (no subdirectories) |
| `def/` | `.def` | `entityDef`, `model`, `mapDef`, `export`, implicit `entityDef` |
| `fx/` | `.fx` | `fx` |
| `particles/` | `.prt` | `particle`, `material` |
| `beams/` | `.beam` | `beam` |
| `af/` | `.af` | `articulatedFigure` |

The retail engine registers `materials`, `skins`, `sound` and `beams`, and the
game library registers `def`, `fx`, `particles`, `af` and `newpdas`. openPREY
registers the same folders. Retail has no `newpdas/` content. The one file
under `liquids/` (`feedingtower/crouch.liquid`) and the `guis/*.guifragment`
includes are not decls.

## Keyword Coverage

The keyword string tables in `PREY.exe` were compared against the openPREY
parsers:

- material keywords are covered in full; see [Materials](#materials) for
  what each Human Head keyword does;
- particle stage keywords (`lowSkippable`, `bounds`, `customPath spherical`,
  `gravity world`, parametric `with` curves) match;
- beam keywords (`numNodes`, `numBeams`, `thickness`, `taperEnds`, `flat`,
  `quad*`, the `Spline*` and `Node*` commands) match;
- sound shader keywords (`soundClass` with `SC_*`, `subtitle*`, `jawflap`,
  `omniwhenclose`, `antiPrivate`, `noreverb`, `noportalflow`, `mask_*`) match;
- FX, AF, skin and table keywords match.

## Retail Behaviour Ported

### Signed particle parms

Retail `idDeclParticle::ParseParms` joins a lone `-` token with the number that
follows it, and errors with `no number after minus sign` when none follows.
Doom 3's parser does not do this, and openPREY used to read
`distribution sphere 0.000 -1.000 -1.000` as five parms. That overflowed the
array, so the particles `crawler_spooge` and `ash` were defaulted. Six more
stages that use negative `distribution`, `orientation` or `customPath` parms
loaded with shifted values. openPREY now follows the retail parser.

### `_nogore` sound shaders

Retail `idDeclManager::FindSound` looks up `<name>_nogore` first whenever the
game's `g_nogore` cvar is set. The retail sound files ship 35 such variants,
which cover the possessed children on the feeding tower maps. openPREY's
`FindSound` now does the same lookup. Entity defs already swap to their
`_nogore` variants in the game library.

### Console commands

`checkDecls` (parse every loaded decl) is now available with loose decl folders
as well as packed `.decls` files, and `printBeam` was added to match retail.

## Materials

Every material keyword retail `PREY.exe` accepts was mapped to its handler in
the retail parser (`ParseMaterial`, `ParseStage`, `ParseDeform`,
`CheckSurfaceParm`) and in the renderer code that reads the result. The
Prey SDK's `src/renderer/Material.h` confirmed the field names. Shipped
materials were counted to rank the gaps. The fixes below bring openPREY to
retail behaviour.

### Surface parms

Retail treats an info parm's `clearSolid` as a mask of contents bits to remove,
not a boolean. openPREY now does the same, and its Prey table matches retail:

| Parm | Retail effect |
| --- | --- |
| `forcefield` | non-solid; `CONTENTS_FORCEFIELD`, `CONTENTS_BLOCK_RADIUSDAMAGE` and `CONTENTS_SHOOTABLE`; forcefield surface type |
| `forcefield_nobullets` | non-solid; `CONTENTS_FORCEFIELD` only, no surface type |
| `seeThru` | removes `CONTENTS_OPAQUE` (opaque coverage adds it back once parsing ends) |
| `noSeeThru` | adds `CONTENTS_OPAQUE` |

Before this, a duplicate `forcefield` entry meant forcefields stayed solid,
had no surface type and blocked neither shots nor splash damage as retail does.

### Material macros

| Macro | Retail effect | Shipped uses |
| --- | --- | ---: |
| `DECAL_MACRO`, `SCORCH_MACRO`, `OVERLAY_MACRO` | polygon offset 1, `discrete` and `noimpact`, non-solid, decal sort, no shadows, translucent, no overlays | 198, 44, 23 |
| `DECAL_ALPHATEST_MACRO` | as above without the polygon offset | 163 |
| `GLASS_MACRO` | no shadows, translucent, force overlays, medium sort, clears `CONTENTS_OPAQUE`, glass surface type | 51 |
| `SKYBOX_MACRO` | no shadows or self-shadows, `noimpact` and `noFragment`, no overlays, opaque | 39 |
| `SPRITE_MACRO` | `discrete`, non-solid, no shadows, translucent, sprite deform, two-sided | 0 |
| `EFFECT_MACRO` | non-solid, no shadows, `noimpact`, translucent, two-sided | 0 |
| `ALPHA_MACRO` | no shadows, `noimpact`, translucent, two-sided | 0 |

openPREY used to ignore `OVERLAY_MACRO`, `GLASS_MACRO` and `SKYBOX_MACRO`, so
the wound overlays had no polygon offset and glass had no glass surface type.
It also gave `DECAL_ALPHATEST_MACRO` a polygon offset that retail does not.

### Deforms

Retail's deform list is `sprite`, `tube`, `flare`, `expand`, `move`,
`eyeBall`, `beam`, `corona`, `jitter`, `particle`, `particle2`, `turbulent`.
openPREY used to treat `beam` as `tube`, which errors on any mesh that is not
made of quads, and dropped `jitter`. Both now follow retail:

- `deform beam` (61 materials: projectile trails, energy beams): the mesh is
  authored along local X with its cross-section in Y/Z. The beam axis runs
  between the vertices a third of the way in from each end. Each vertex is
  rebuilt as `x·axis + y·right + z·up`, where `right = normalize(view ×
  axis)` and `up = normalize(axis × right)`, so the beam always shows its
  broad side to the viewer. Unlike `tube`, it changes neither culling nor
  shadowing.
- `deform jitter <expression>` (6 materials): the expression is truncated to an
  integer bit mask. Bits `0x01`/`0x02`, `0x04`/`0x08` and `0x10`/`0x20` offset
  x, y and z by +1/−1. Bits `0x40`, `0x80` and `0x100` scale x, y and z by
  1.1. Bit `0x1000` doubles the offset. The `jacobladder` tables drive it.

### Image options

`highres` (591 stages) marks a source authored at twice its intended size.
Retail halves such an image once, even under `nopicmip`, unless
`image_useHighRes` is set, and only its top machine spec set it. openPREY now
records the flag on the image and honours `image_useHighRes`, which defaults to
`1` so textures keep their current full size. As in retail, the flag is not
part of an image's identity, so the first material to name an image decides.
`fragmentMap` and `shaderTexture` accept the option too.

### Per-stage specular power

`specularExp <exponent>, <brightness>` (36 stages) is parsed and stored on
every stage. Retail defaults are exponent 22 and brightness 1.4, which is why
so much content repeats `22, 1.4`.

Retail picks its interaction program from two cvars, both `"1"` in the
`PREY.exe` cvar table (`r_cubemapNormalize`, `"0"`, only chose a slower
normalization):

| `r_normalizeBumpmap` | `r_correctSpecular` | Retail program | Specular |
| --- | --- | --- | --- |
| 0 | 0 | `interaction.vfp` | Doom 3 `_specularTable` ramp of N·H |
| 1 | 0 | `interactionNormBump.vfp` | ramp, renormalized bump normal |
| 0 | 1 | `interactionUpdate.vfp` | `pow(N·H, exponent) · brightness` |
| 1 | 1 | `interactionNormBumpH.vfp` | `pow`, renormalized bump normal |

With correct specular the vertex program passes the vector to the viewer
instead of a per-vertex half angle, and the fragment program rebuilds
`H = normalize(L + normalize(V))` per pixel. The interaction's specular stage
supplies the exponent and brightness through fragment environment parameter 2;
the specular colour and the `× 2` on the specular map are unchanged, so the
two models differ only in the falloff term.

Retail applies that `× 2` in the fragment program (`ADD R2, R2, R2`) and passes
the bare specular colour in environment parameter 1. This engine passes the
colour already doubled (`RB_ARB2_DrawInteraction`, inherited from openQ4, whose
Quake 4 program does not double), so openPREY's `interaction.vfp` does not
double the map again. Until 11 November 2026 it did, and the stock OpenGL path
drew specular at twice the brightness of every other path: the Vulkan
interaction, the GLSL material interaction and the shadow-map receivers all
apply the factor once. That is what made a shadow-mapped light look dimmer
than the same light under stencil shadows.

openPREY renders this on every backend. `R_InteractionSpecularParms`
(`tr_local.h`) packs the specular stage's exponent and brightness with the two
cvars, and each stock interaction path consumes the same four values:

- ARB2: `glprogs/interaction.vfp` takes them in `program.env[2]` and selects
  the model with `LRP`, so one program serves all four combinations. Its
  vertex program adds the vector to the viewer as `texcoord[7]`. The shared
  world-interaction executor uses the classic-domain primitive's
  `specularParms`, which are part of its semantic hash.
- GLSL: `uStockSpecularParams` in `material_interaction.fs` (cel banding and
  flat-diffuse chains) and both shadow-map receivers; the GL modern classic
  accumulator carries them as `uClassicParams[15]`.
- Vulkan: `stock_specular.glsl`, fed by push constant `d.yzw` on stock draws,
  in `interaction.frag` and both shadow variants.
- GLES: `uSpecularParams` in the `glesd3` interaction shader.

`r_enhancedMaterials`, native PBR, custom Prey interaction programs and
SimpleInteraction keep their own specular models. `r_correctspecular 0` with
`r_normalizebumpmap 0` restores the earlier look, except on the GL shadow-map
receivers, which always renormalized and so match `r_normalizebumpmap 1`. Both cvars
are archived; a config written before they took effect may hold
`r_normalizebumpmap 0`, the old placeholder default, which is the retail
`interactionUpdate.vfp` combination.

On the opening `game/roadhouse` sink, the default now gives a smooth,
material-shaped highlight where the ramp showed blotchy, clipped bands, on
both GL and Vulkan. Overriding that material's stage with
`specularExp 200, 6` tightens the highlight, which confirms the per-material
values reach the shader.

### Confirmed no-ops

- `lightWholeMesh` and `skipClip` set `MF_LIGHT_WHOLE_MESH` and `MF_SKIPCLIP`
  in retail, but nothing in `PREY.exe` or the game library ever tests either
  flag.
- `detail`, `bumpforceHighQuality` and `shadowdraw` are not retail keywords;
  retail defaults those materials too.

## Remaining Warnings Are Content

Running `checkDecls` against the retail install leaves only warnings that the
retail engine hits as well:

- `unknown general material parameter` for `detail` and `bumpforceHighQuality`,
  and `unknown token 'shadowdraw'`. These are not retail keywords. Retail
  defaults the material just as openPREY does (`MF_DEFAULTED`, checked in the
  disassembly);
- `Bad term` for `ember1`, `fireballtable` and `animbump_speed`, and
  `unknown token '1'` for `table tabletest { 1, 0 }`. No such tables exist, and
  the table syntax is malformed in `shaderdemo.mtr` and `organic_decals.mtr`;
- `had stage with no image` for the `fragment_fx` test materials. Their
  `colorMatrix*.vfp` programs do not ship;
- missing images, cube maps, models and anims named by unused decls. None of
  those files exist in the retail paks.

## Reproducing

Launch from the staged `.install/` against a retail install, in windowed mode,
with an isolated save path:

```powershell
.install\openPREY-client_x64.exe +set r_fullscreen 0 +set developer 1 +set logFile 2 `
  +set logFileName logs/checkdecls.log +set fs_savepath .tmp\decl-audit\save `
  +set fs_basepath "<Prey install>" +set fs_game basepr +checkDecls +wait +quit
```

Then filter `logs/checkdecls.log` for `WARNING: file <folder>/...` lines. To
check the gore lookup, load `game/feedingtowerc` with `+set g_nogore 1 +set
decl_show 2` and look for `referencing sound ..._nogore`.
