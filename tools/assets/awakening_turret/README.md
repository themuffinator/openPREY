# Awakening chaingun turret skin

Rebuilds openQ4's skin for The Awakening's mannable Strogg chaingun turret
(model `common_turret_strogg`, entity `vehicle_q4x_turret_chaingun`, used in
m01 and m04). The expansion's alpha shipped this model with grey
ambient-occlusion bakes as its diffuse maps, a black specular map and a dotted
placeholder in its drum, so it rendered as bare clay.

The shipped result lives in `content/baseoq4/pak0`:

| File | What it is |
|---|---|
| `materials/00_awakening_turret_openq4.mtr` | The model's four materials, loaded ahead of the expansion's `q4x_mapobjects.mtr` |
| `models/openq4/awakening/turret_strogg/turret_strogg0N_{d,s,glow}` | Colour, specular and glow maps |
| `effects/openq4_awakening_turret_*.fx` | Muzzle flash, tracer and barrel smoke |
| `def/vehicles/awakening_turret_openq4.def` | The turret weapon's `_q4x_openq4` definition and its tracer hitscan and casing defs |

The materials keep the expansion's normal maps, which stay in the player's
copy of The Awakening; openQ4 ships none of the expansion's files.

## Rebuilding

Needs Blender 4.x (Cycles) and Python with numpy, scipy, OpenCV and Pillow.

```bash
python tools/assets/awakening_turret/build_skin.py --awakening "<path>/q4xbase" --preview --export
```

1. `blender_bake.py` imports the md5mesh in its bind pose (`blender_md5.py`)
   and bakes, per material, UV coverage, ambient occlusion and object-space
   normals (both through the expansion's normal map, green flipped: id's
   tangent space has texture t growing downward) and object-space position.
2. `paint.py` paints from those bakes: per-island roles (armour enamel,
   gunmetal, blued steel, deck, drum), seam-free 3D noise, grime in cavities,
   streaks on vertical faces, rust low and in creases, dust on top faces,
   chipped edges with a primer ring, scratches, bullet strikes, heat tint and
   soot at the muzzle, Strogg glyph and chevron stencils, amber vent and red
   sensor glow, and brass rounds placed on the drum's normal-map rings. The
   drum windows' outline is traced from the expansion's alpha channel so the
   cut-outs line up with the model.
   `details.py` adds the finishes on top: panel tones split along the normal
   map's creases by a watershed from seed points (light brushed steel cover
   plates, field-grey lower shield, bone blocks on the pedestal, oxblood plates
   on the gun), worn-through edgings in patches, braided hoses with brass
   ferrules and colour ID bands, a rubber sleeve, coloured wires, chrome column
   bands and bearing rings, and brass or steel bolt heads. Hoses, wires and
   rings are found in the height field integrated from the normal map; their
   UV boxes, seeds and the bolt positions were measured on the model.
3. `--preview` renders a Cycles turnaround to `.tmp/awakening_turret/preview`.
4. `--export` copies the masters into `content/baseoq4/pak0`.

A rebuild reproduces the shipped maps byte for byte: the bakes use a fixed
Cycles seed, and the data bakes (coverage, normals, positions) take one sample
per texel, because the GPU sums several samples in a varying order and the
last-bit differences moved a few texels of the painter's noise. All bakes are
written as Non-Color data; a float image left in linear colour space is saved
through the sRGB curve, which corrupted the positions in the first version.
Work files go to `.tmp/awakening_turret`.
