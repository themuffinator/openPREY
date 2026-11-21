# TrueType font system

openPREY renders GUI, HUD and console text from scalable TrueType faces. The
menu, alien and console faces are reconstructed from Prey (2006)'s retail
bitmap fonts; the default face is Talon, drawn for openPREY (see
[Talon](#talon-the-default-face)). The renderer rasterises them at the
display's resolution instead of magnifying the fixed 12/24/48-pixel atlases.
The original bitmap path remains available as the compatibility fallback.

## Shipped faces

The generated files live in `content/basepr/pak0/fonts/` and use the names that
the renderer resolves after a GUI requests a font.

| File | GUI / engine consumer | Source |
| --- | --- | --- |
| `english.ttf` | `fonts` (the default UI/HUD face) | Talon, drawn in `tools/assets/fonts/talon/`; no retail source |
| `menu.ttf` | `fonts/menu` | `fonts/english/menu/fontImage_48.dat` and five atlas pages |
| `alien.ttf` | `fonts/alien` | `fonts/english/alien/fontImage_48.dat` and three atlas pages |
| `bigchars.ttf` | `textures/bigchars` (console and loading text) | `textures/gfx/bigchars.tga` |

`alien.ttf` intentionally remains a Latin-symbol face. It folds accents onto
their base symbol rather than mixing the retail alien alphabet with donor
scripts. The other three faces carry the extended Latin, Greek, Cyrillic,
Arabic, Hebrew, punctuation and HUD-symbol coverage supplied by the shared
generator.

`english.ttf` is licensed under the SIL Open Font License 1.1
([LICENSES/OFL-1.1.txt](../../LICENSES/OFL-1.1.txt)): Talon is openPREY's own
drawing, and its glyphs for the scripts it does not draw are derived from the
Noto fonts, which are under the same licence. The traced faces keep the
attribution to the retail bitmap fonts in their name tables.

## Rebuild process

The generated TTFs are committed runtime assets; the retail `.dat` files and
atlas pages are only temporary inputs and must not be added to the repository.

```powershell
python tools/assets/fonts/extract_source_fonts.py `
  --install "C:/Program Files (x86)/Human Head Studios/Prey" `
  --output .tmp/prey-fontsrc
```

`--install` accepts either the game install root or its `base` directory. The
extractor reads the pk4 archives in the same override order as the engine and
also handles retail archives whose central-directory and local-header paths use
different slash directions.

Download the following variable fonts from the Google Fonts repository into a
temporary donor directory (alongside their OFL notices):

- `NotoSans-var.ttf`
- `NotoSansArabic-var.ttf`
- `NotoSansHebrew-var.ttf`

Then build the complete set:

```powershell
python tools/assets/fonts/build_openprey_fonts.py `
  --source .tmp/prey-fontsrc `
  --donors .tmp/fontdonors `
  --output content/basepr/pak0/fonts
```

Pass `--faces english,menu,alien,bigchars` to rebuild a selected subset. The
output must contain all four files before a runtime package is made. Talon
needs no retail extraction, so the default face alone rebuilds with:

```powershell
python tools/assets/fonts/build_openprey_fonts.py --faces english `
  --donors .tmp/fontdonors --output content/basepr/pak0/fonts
```

Talon's construction needs [Shapely](https://pypi.org/project/shapely/) 2.x
besides FontTools, NumPy and Pillow. The build is deterministic: rebuilding
from the same sources gives the same bytes.

`english.ttf` is Talon build 2.000 (21 November 2026). The current `menu.ttf`
and `alien.ttf` are build 1.100 (10 November 2026; `menu.ttf` regenerated
11 November 2026 with the image-rect stretch described under Pipeline).
Against the retail 48-point coverage of every traced slot, as the bitmap path
draws it, their mean intersection-over-union is 0.974 and 0.966, and every
advance still matches its `.dat` record exactly. The traced default face it
replaced, build 1.100, scored 0.976. The menu figure is measured against each
atlas block stretched over its image rect; the earlier menu build, traced 1:1,
scores 0.61 on that measure because its letters were 3 units short and lifted
off the baseline. `bigchars.ttf` remains build
1.000: a rebuild with the current pipeline leaves U+00A0 unmapped, which the
console sheet has not been checked against.

After rebuilding, refresh the copies embedded in the
[Interface Atlas](prey-ui/atlas/prey-interface-atlas.html):

```powershell
python tools/assets/fonts/embed_atlas_fonts.py
```

It subsets the three GUI faces to Latin, packs them as WOFF and rewrites the
atlas's `@font-face` block, so the atlas always draws what the engine ships.

### Pipeline

1. The reader decodes Prey's original Doom 3 glyph record, preserving each
   glyph's screen-space advance, bearing and UV bounds.
2. The serialized material name selects the correct source atlas page for that
   glyph; this is essential because the default and menu faces use five pages
   at 48 pixels and alien uses three.
3. The bitmap path draws a glyph's atlas block across its recorded image rect
   (`imageWidth` x `imageHeight`), not at the block's own texel size. Prey's
   menu face records every image 3 units taller than its block at 48 point
   (1 unit at 24), so the retail menu letters are drawn stretched.
   `FaceBuilder._trace_slot` maps each trace onto the image rect the same way
   (`slot_stretch` in `q4font/fontdat.py`); grid-sliced faces (`bigchars`) are
   exempt. The default and alien faces have no such gap and are unaffected.
4. The tracer recovers the sub-pixel outline from the atlas alpha coverage,
   then applies axis snapping and curve fitting to retain sharp stems and
   corners. Prey's 48-point atlases are small for what they carry (the menu
   face's capitals are 18 pixels tall, and the alien digits are pixel-art
   diagonals), so `build_openprey_fonts.py` first resamples each 48-point
   glyph six times with bicubic reconstruction and a light Gaussian
   (σ 0.32 source pixels). Curves are then fitted to the edge rather than to
   the 1/255 quantisation and staircase noise, with the curve tolerance held at
   0.07 source pixels and subdivision capped at four levels. `bigchars` keeps
   the shared densified path.
5. Accents are extracted from retail precomposed glyphs where available,
   shared Greek/Cyrillic shapes reuse the authentic outline, and remaining
   ordinary-script glyphs are imported from Noto at a weight and width fitted
   to the traced face. Common UI symbols are constructed at the same weight.
6. `bigchars` is traced from its 16×16 source grid and forced to one-cell
   advances, matching the console's existing fixed-cell indexing.

## Talon, the default face

Talon replaced the traced retail default face on 21 November 2026. The retail
face was condensed and heavy, with counters so narrow that small HUD text
clogged; its tracing inherited that. Talon keeps the retail layout and the
Prey look, and fixes legibility:

- **Two sources.** Impact gives the condensed frame, the very tall x-height
  (0.80 of the capital height), straight-sided bowls and terminals cut square
  to an axis. The PREY wordmark gives the bowls: superellipse corners
  (exponent 2.6) with a large outer radius around a tight inner one, softly
  rounded outer corners where a stroke turns (E, F, L, P, R, B, D), R's
  straight diagonal leg and the straight spines of S, s, 2, 3 and 5. No
  outline is traced from either.
- **Lighter and more open.** Stems are 0.19 of the capital height (retail
  face 0.215, Impact 0.26) and a line of text carries 12% less ink than the
  retail face. The counter of `o` is 2.3 times as wide.
- **Same set width.** Across the stock menu labels Talon sets 1.2% narrower
  than the retail face at equal capital height, so retail GUI rects keep
  fitting and centred labels land on the same pixels.
- **Shapes that cannot be confused.** `l` has a tail and `1` a flag; `O` is an
  oval and `0` a squared slot; figures are tabular (one advance for all ten).

Its own drawings cover ASCII, the Latin-1 and Windows-1252 letters and
symbols, the combining accents, Greek, and the Russian and Ukrainian Cyrillic
letters (lower-case Cyrillic drawn as small capitals, as grotesques do). The
shared pipeline then composes the accented letters of Latin-1 and Latin
Extended, Greek and Cyrillic from Talon's letters and marks, builds stroked
letters and the remaining Latin-1 symbols from its parts, draws the HUD
shapes at its weight, and takes what is left (IPA, the rarer Cyrillic, Arabic,
Hebrew) from Noto at Talon's weight and width. The face covers exactly the
code points the traced face did.

### Construction

`tools/assets/fonts/talon/glyphs.py` draws every glyph on a 1000-unit grid
(capital height 700, x-height 560, ascender 730, descender −150, stems 132
and 124) from the parts in `geometry.py`: superellipse bowls, soft turns, and
straight strokes clipped flat. Shapely combines the parts as polygons, so
curves are sampled densely; `to_path` then finds each run of samples that came
from a curve (outline turning less than 14° per vertex along short edges),
fits it with cubic Béziers under fixed end tangents, converts those to
quadratics within 0.4 units, and leaves straight runs and corners as lines.
`TalonFaceBuilder` in `build_openprey_fonts.py` hands the drawn glyphs and
marks to the shared `FaceBuilder` in place of a retail trace. The line box
stays the retail face's (ascender 1920, descender at least 299 font units).

At runtime nothing about the face is special: `R_TTFFitSlotsToRetail` fits
it to the retail 12, 24 and 48 point slots like any other face.

## Runtime

`src/renderer/tr_fontTTF.cpp` loads a requested face from `fonts/*.ttf`, builds
12/24/48-point atlas slots with the same `fontInfo_t` layout as the bitmap
loader, and falls back to the retail `.dat` files if a face is absent or fails
to load. The high Windows-1252 byte range is translated to its Unicode
codepoints before lookup, so the TTF uses normal Unicode mappings while legacy
GUI text keeps its original byte encoding.

### Fitting each size to its retail atlas

Prey's 12, 24 and 48 point atlases are drawn separately and are not rescales of
one another. The menu face's 24 point capitals are 86% as tall as its 48 point
ones and its 12 point capitals about two thirds, and each slot reserves its own
line height (the menu face's 48 point cell is 50 units, far taller than its
letters). The GUI chooses the slot from the authored text scale, and `DrawText`
puts the first baseline of a text rect one line height below its top. A single
outline rasterised uniformly at all three sizes therefore put TTF text on a
different baseline from the bitmap text and drew it too tall below 48 point.

`R_TTFFitSlotsToRetail` fits every slot to the retail `.dat` of the same size,
read through `R_ReadLegacyFontSlotMetrics` (`tr_font.cpp`), whenever those files
exist (always, for a Prey install):

- The slot's line height becomes the retail one.
- The outline is stretched vertically about the baseline so glyph tops land on
  the retail tops. The factor is the median, over letters and digits, of the
  retail top over the face's own top at that size. Retail tops include the
  one-unit atlas border where a face has one (the default face does; menu and
  alien do not), so the border is measured at 48 point, where the face was
  traced, and removed first. Factors within 2% of 1 are left at 1.
- Fitted slots are named `ttfretail/<face>_<size>` instead of `ttf/...`, so
  `openQ4_FontAtlasesAreProportional` no longer lets the GUI sample a larger slot
  in their place: like the retail atlases, they are selected by authored scale.
  The medium slot serves scales up to `gui_mediumFontLimit` (0.6, a 28.8 unit
  em against its 24), so it is rasterised that much finer to stay sharp.

Widths and advances are not fitted. With `r_ttfFontDebug 1` the log reports each
slot's fit; the current faces give english (Talon) 1.071 / 1.071 / 1.000 and
menu 0.662 / 0.834 / 1.000 at 12 / 24 / 48 point. The traced default face
Talon replaced gave 0.970 / 1.031 / 1.000. With that face, on the main menu and
the opening caption at 1440x1080, TTF and bitmap text started and ended on the
same pixel rows, or one row apart where antialiasing differed. A face with no retail `.dat` behind
it stays a uniform rescale under the `ttf/` name.

The console and loading paths do not use `RegisterFont`; they directly slice
`textures/bigchars` as a 16×16 grid. `R_BuildConsoleFontAtlas` rebuilds that
sheet from `bigchars.ttf` at display resolution and retargets the existing
`textures/bigchars` material, preserving its blend and UV behaviour.

Font atlases follow the renderer restart lifecycle. A full `vid_restart`
releases cached TrueType faces before image purge, retains atlas coverage while
generated images rebuild with the new context, reinitialises the font reader, and immediately
rebuilds the console sheet. A successful partial restart keeps the context,
faces, and images alive, but still refreshes the resolution-dependent console
sheet. Cached GUI fonts notice the renderer restart generation on their next
lookup or selection and re-register in place, preserving the integer indices
stored by parsed GUIs as well as the active font and size selection.

GUI, extended-character and console atlases retain one byte of coverage per
texel in CPU memory. Their image generator expands that coverage to white RGB
with alpha when storage is recreated, including `reloadImages all`. A scratch
allocation alone loses the glyph pixels and can leave Vulkan sampling an
undefined image. Re-registering a font replaces the retained coverage for its
new scale/codepage; final renderer shutdown frees it. This cache adds one
quarter of the atlas's RGBA8 GPU footprint in CPU memory.

### Keeping the atlas materials alive

Each atlas is bound through a material this module generates at registration
time. Those declarations have no `.mtr` behind them, which makes them fragile in
a way a shipped material is not.

The material and its intrinsic generated image intentionally use the same
`_ttfatlas...` identity. The declaration manager parses a newly requested
implicit material before the font module can replace its source, and that
implicit stage maps an image named after the material. Sharing the already
uploaded atlas identity makes this first parse valid and prevents spurious
missing-image warnings and redundant defaulted image records. The font module
then installs its full generated stage unconditionally so the required blend,
linear filtering, clamp, and no-picmip state remains explicit.

`idDeclManagerLocal::BeginLevelLoad` purges every declaration that is not marked
as parsed outside a level load, and `FindType` clears that mark on anything it
resolves *during* a load. A face a map's own GUIs are the first to name is
registered inside that window, so it ends up classified as level media. For a
shipped material that costs nothing: the next reference reparses it from its
file. For a generated one there is no file, and the implicit text the manager
synthesises for a declaration with no source maps an image named after the
material itself, which nothing is registered under. That resolves to the default
image, which is **fully transparent outside developer builds**, so the failure
is not a missing-texture box — every glyph in the face silently draws nothing,
with no warning, and nothing short of a restart brings it back.

Two things close that off:

- `R_TTFInstallAtlasStage` calls `SetText` before parsing, so the declaration
  carries the generated source itself and a purge becomes recoverable. Implicit
  declarations are excluded from the network decl checksum, so this stays
  process local — a graphical client does not gain a declaration a dedicated
  server can never create.
- `idRenderSystemLocal::BeginLevelLoad` calls `R_TTFRestoreAtlasMaterials`,
  which runs immediately after the declaration purge and before the loading
  screen draws its first frame of text. It looks each material up *without*
  parsing first, so a healthy declaration costs nothing and is not demoted by
  the lookup itself.

Registration is also self-healing: `R_TTFCreateAtlasMaterial` always reinstalls
the complete generated stage. This is intentionally stronger than comparing
the old stage's image name, because a full renderer restart can recreate the
image manager while leaving a generated declaration carrying a stale image
pointer.

A related hazard sits on the GUI side. `idDeviceContext` holds `activeFont` and
`useFont` as pointers into its `fonts` list, and that list has granularity 1, so
`FindFont` reallocates it on every registration. `idWindow::SetFont` re-points
`activeFont` before each draw, but nothing re-points `useFont`, and `DrawText`
reads it through `MaxCharWidth`/`MaxCharHeight` *before* `SetFontByScale`
reselects it — so the character cell and line skip the whole layout is built
from would be read out of a freed allocation. `FindFont` reseats both pointers
by index across the append.

| Cvar | Default | Meaning |
| --- | --- | --- |
| `r_useTrueTypeFonts` | `1` | Draw GUI, HUD and console text from the TTF atlases; `0` returns to the retail bitmaps. |
| `r_ttfFontResolution` | `1.0` | Multiplier for TTF atlas rasterisation resolution. |
| `r_ttfFontDebug` | `0` | Dump generated atlas pages to `fs_savepath/ttfatlas` and log their layout. |

The scalable path is the default. It falls back cleanly to the retail bitmap
data when a face cannot be registered, and `r_useTrueTypeFonts 0` selects the
bitmaps outright (languages whose letters the bitmaps lack ignore that; see
[text-encoding-and-localization.md](text-encoding-and-localization.md)). The
cvar is archived, so a configuration saved while the default was `0` keeps
the bitmap path until the cvar is set to `1`.

Prey's retail spline text effect (`splineIn` windows) works with both paths.
It only moves and fades each glyph's quad and never reads the glyph's pixels,
so `idDeviceContext::DrawText` applies it to TTF glyphs exactly as it does to
bitmap ones. No shipped GUI enables it; the credits definitions set
`splineIn 0`.

### Quake 4 face names

Prey's GUIs name only the default face, `fonts/menu` and `fonts/alien`, but
engine code inherited from Quake 4 still asks for Quake 4's faces: the
multiplayer chat window and HUD text capture use `fonts/lowpixel`, the level
editor labels `fonts/lowpixel`, and the retained interface `chain`, `marine`,
`profont` and `strogg`. Prey has none of them, so those requests used to fail,
fall back to font 0 without the TTF face being asked for, and warn. Because a
failed lookup is not cached, they then retried registration on every call,
which for the editor labels was every frame.

`R_CanonicalFontName` (inline in `RenderSystem.h`, because the GUI layer and
the renderer module both use it) folds those names onto the Prey face with the
same role: `chain`, `lowpixel`, `marine` and `profont` become the default face;
`strogg` and `r_strogg` become `alien`. It is applied in
`idDeviceContext::FindFont` (so an aliased name shares the existing font entry
instead of registering a second copy of its atlases), in
`idRenderSystemLocal::RegisterFont`, and in the TTF face lookup the retained
interface calls directly. Any other name passes through unchanged.

## Validation

After rebuilding, verify all four TTFs with FontTools and package them through
the normal Meson `pak0.pk4` target. For a renderer check, launch windowed with
`+set r_fullscreen 0 +set r_ttfFontDebug 1`, inspect the generated engine-side
`ttfatlas` images, and confirm the log has no `couldn't find font` warning.
Then repeat with `+set r_useTrueTypeFonts 0` to confirm the bitmap fallback;
`uiFontParitySelfTest` runs its retail-atlas parity cases only in that mode. `tools/assets/fonts/audit_fonts.py` still imports the Quake 4 generator
(`build_openq4_fonts`) and does not run against these faces until it is
ported; its atlas-space renderer already applies the image-rect stretch.

## Text background

Independent of which font path is active, `gui_textBackground` draws a solid
black backing behind each line of text so contrast no longer depends on what
happens to be underneath.

| Cvar | Default | Meaning |
| --- | --- | --- |
| `gui_textBackground` | `0` | Backing opacity; 0 off, 1 opaque |
| `gui_textBackgroundPadding` | `2` | Padding past the text, in virtual units |

The box is drawn once per line before any glyph, so it never shows through the
gaps between characters, and colour escapes inside a line change the text colour
without affecting the backing.

Its height comes from the font's **measured glyph ink extents**, not from
`fontInfo_t`'s `ascender`/`descender`. Those fields do not reliably describe where
the ink is, so the box is sized from the glyphs themselves. Measuring the glyphs
also means every line of a given font gets the same box height whatever
characters it contains, so a wrapped paragraph does not come out ragged. `uiFontParitySelfTest` covers both the extent measurement and
the rect placement.

## Known limitations

The TTF files carry wider coverage than the retail atlases. The engine text
path inherited from upstream draws by code point (see
[text-encoding-and-localization.md](text-encoding-and-localization.md)); Prey
GUI coverage of that path remains runtime-validation pending.

- **Text input above ASCII is not wired up.** Engine text is UTF-8 and the text
  path draws by code point, but `idEditField` and the
  platform scan tables are still byte-oriented, so typing Cyrillic into the
  console or a chat box does not work.
- **No Arabic shaping or bidi.** The faces include the Presentation Forms-B
  joined shapes precisely so a shaper can use them, but no shaper exists yet.
  Until one does, Arabic coverage is not usable text.
- **The code-point page directory stops at the BMP.** Nothing the GUI draws
  lives above U+FFFF, and stopping there keeps the directory to 256 pointers per
  font size.
- Atlases are rebuilt only when fonts are registered; a resolution change does
  not currently re-rasterise them at the new upscale factor, so changing
  resolution wants a restart for text to be pixel-exact again.
- `FMT_ALPHA` would quarter atlas memory and is swizzled to RGB=1/A=R on both
  backends, but a `ScratchImage` in that format renders nothing through the GUI
  blend path. Unresolved; RGBA8 is used instead.
