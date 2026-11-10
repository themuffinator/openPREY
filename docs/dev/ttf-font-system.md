# TrueType font system

openPREY can render scalable TrueType faces reconstructed from Prey (2006)'s
retail bitmap fonts. The renderer rasterises those same letterforms at the
display's resolution instead of magnifying the fixed 12/24/48-pixel atlases.
The original bitmap path remains available as the compatibility fallback.

## Shipped faces

The generated files live in `content/basepr/pak0/fonts/` and use the names that
the renderer resolves after a GUI requests a font.

| File | GUI / engine consumer | Retail source |
| --- | --- | --- |
| `english.ttf` | `fonts` (the default UI/HUD face) | `fonts/english/fontImage_48.dat` and five atlas pages |
| `menu.ttf` | `fonts/menu` | `fonts/english/menu/fontImage_48.dat` and five atlas pages |
| `alien.ttf` | `fonts/alien` | `fonts/english/alien/fontImage_48.dat` and three atlas pages |
| `bigchars.ttf` | `textures/bigchars` (console and loading text) | `textures/gfx/bigchars.tga` |

`alien.ttf` intentionally remains a Latin-symbol face. It folds accents onto
their base symbol rather than mixing the retail alien alphabet with donor
scripts. The other three faces carry the extended Latin, Greek, Cyrillic,
Arabic, Hebrew, punctuation and HUD-symbol coverage supplied by the shared
generator.

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
output must contain all four files before a runtime package is made.

### Pipeline

1. The reader decodes Prey's original Doom 3 glyph record, preserving each
   glyph's screen-space advance, bearing and UV bounds.
2. The serialized material name selects the correct source atlas page for that
   glyph; this is essential because the default and menu faces use five pages
   at 48 pixels and alien uses three.
3. The tracer recovers the sub-pixel outline from the atlas alpha coverage,
   then applies axis snapping and curve fitting to retain sharp stems and
   corners.
4. Accents are extracted from retail precomposed glyphs where available,
   shared Greek/Cyrillic shapes reuse the authentic outline, and remaining
   ordinary-script glyphs are imported from Noto at a weight and width fitted
   to the traced face. Common UI symbols are constructed at the same weight.
5. `bigchars` is traced from its 16×16 source grid and forced to one-cell
   advances, matching the console's existing fixed-cell indexing.

## Runtime

`src/renderer/tr_fontTTF.cpp` loads a requested face from `fonts/*.ttf`, builds
12/24/48-point atlas slots with the same `fontInfo_t` layout as the bitmap
loader, and falls back to the retail `.dat` files if a face is absent or fails
to load. The high Windows-1252 byte range is translated to its Unicode
codepoints before lookup, so the TTF uses normal Unicode mappings while legacy
GUI text keeps its original byte encoding.

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
| `r_useTrueTypeFonts` | `0` | Enable TTF GUI and console atlases; `0` keeps retail bitmaps authoritative. |
| `r_ttfFontResolution` | `1.0` | Multiplier for TTF atlas rasterisation resolution. |
| `r_ttfFontDebug` | `0` | Dump generated atlas pages to `fs_savepath/ttfatlas` and log their layout. |

The default remains bitmap-first while Prey's retail spline/credits text effect
has no TTF glyph-path implementation. Enable the cvar explicitly when testing
the scalable path; it falls back cleanly to bitmap data when a face cannot be
registered.

## Validation

After rebuilding, verify all four TTFs with FontTools and package them through
the normal Meson `pak0.pk4` target. For a renderer check, launch windowed with
`+set r_fullscreen 0 +set r_useTrueTypeFonts 1 +set r_ttfFontDebug 1`, inspect
the generated engine-side `ttfatlas` images, then repeat with the cvar at `0`
to confirm the bitmap fallback and `uiFontParitySelfTest` still pass.

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
