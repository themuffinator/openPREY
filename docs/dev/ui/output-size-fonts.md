# Retained text at its output size

17 September 2026. This is a partial implementation of `TXT-002`, not font,
language, screen or product acceptance. All 227 requirements, 271 unaccepted
migrations and seven open final gates remain in scope.

## Review and change

The retained adapter previously registered all three legacy font slots and
always selected the 48-point slot. RmlUi requested physical text sizes, but
the adapter enlarged or reduced that slot's raster. Layout and independent
text scaling therefore did not establish output-size rasterization.

The renderer now exposes separate retained font metrics, glyph and reset
services. The existing first-party TrueType reader/rasterizer reads the same
VFS font faces and rasterizes misses at the requested physical em size, from
1 to 512 pixels. Density and independent text scale have already been applied
by retained layout; the font service applies neither a second time. Font
advances come directly from design units, and each raster texel occupies one
output pixel. The existing immutable text-run service supplies measurement,
number-field geometry and drawing from those same glyphs.

The cache distinguishes resolved font path, physical size and glyph index.
Missing scalars share the resolved question-mark glyph, or `.notdef` if that
face has no question mark. It accepts Unicode scalars above the BMP when the
face's existing cmap supports them; this is not shaping or fallback-font
qualification. Spaces retain their advance without allocating atlas art.
X-height now comes from the face's glyph metrics rather than a legacy padded
bitmap rectangle.

Normal installed Marine, Lowpixel and Chain faces are reused. The existing
language-specific lookup and English fallback remain. No new dependency or
font asset is incorporated. `r_useTrueTypeFonts` still controls legacy font
selection; retained output text uses its own scalable service.

## Ownership and limits

All retained views share append-only 1024-square RGBA8 atlas pages. Each glyph
has a transparent gutter around the rasterizer's own antialiased edge. Later
uploads cannot overlap a published glyph. Pages, image names and UVs remain
stable while another view or a queued draw can reference them.

The cache allows 32 pages (128 MiB of GPU image storage), 16,384 glyph records
and 4,096 face/size metric records. These are separate limits: blank glyphs
cannot evade the metadata budget. Raster coverage and upload buffers are
temporary; full CPU copies of pages are not retained. Allocation/upload
refusal cannot publish incomplete glyph metadata. A refused upload may leave
unused page space, which is reclaimed at the resource barrier.

Pages are generated images. `reloadImages` and the texture-reduction reload
reallocate an image's storage without any resource barrier, so the page
generator rasterizes every glyph already placed on that page into the same
rectangle again. Published UVs stay valid and no view rebuilds its text. Until
4 October 2026 the pages were scratch images, which that reload reallocated
empty while their glyphs stayed published: on Vulkan the retained menus lost
all their text and the validation layer reported sampling an image in
`VK_IMAGE_LAYOUT_UNDEFINED`; OpenGL happened to keep the old texels.

There is no live eviction. The existing coordinator first retires queued
submissions and closes every retained context, then clears the cache and
purges its images before restoring view snapshots. Renderer shutdown also
clears the cache before image-manager teardown. Names are reused only after
that barrier. Language and video changes use this same path.

Unavailable faces, glyph/raster failures or exhausted budgets explicitly use
the old font path, with one warning per resource generation. This preserves
readability, but the degraded path does not meet output-resolution acceptance.
`r_ttfFontDebug 1` logs requested retained pixel sizes and reset residency.

The three appended renderer-service methods require renderer ABI 18. Replace
the client and renderer modules together; the existing loader rejects mixed
ABI versions.

## Qualification and remaining work

The native cache test exercises exact requested sizes through 512 pixels,
family separation, stable shared lookup, non-BMP and deduplicated fallback
identities, blank glyphs, gutters, non-overlap, all three budgets, resource
reset, invalid source results and refused device operations. It compiles with
both MSVC and Clang. The generated-material warning test covers the new
runtime-only atlas namespace without exempting ordinary materials.

The renderer display-service fixture had stale doubles for image-recovery
ownership and fallible unloading. Those were corrected, with an added check
that refused unloading keeps the display pin and epoch until teardown succeeds.
Its builtin, module-only and dedicated branches pass.

The full Windows client, dedicated server, game libraries and OpenGL/Vulkan
modules build and stage successfully. All 85 selected UI regression suites
pass, including the new cache test. The two long SYSTEM size matrices were
already qualified in the preceding interface-size increment; their fake-font
layout tests were not rerun for this renderer/engine font-adapter change.
The cache also passes a separate warning-clean Clang build. Engine qualification
and visual review are recorded with the increment's source/binary-bound evidence
under `.tmp/ui/output-fonts/`.

Two hidden, windowed staged-engine runs exercise the normal SYSTEM Session
route after active SP `game/airdefense1` and MP `mp/q4dm1` gameplay, without
host input injection. French/OpenGL requests 125% density and English/Vulkan
requests 200%; both use 200% text. At 1280x720 the established window fit
reduces the latter's effective density to 150%. The 50 semantic stages cover
draft/Apply/Discard, dropdowns, language reload, video restart, parent return
and reopening. All 18 engine render-target screenshots were reviewed through
pixel-identical PNGs/contact sheets, with full-size modal, popup and restored
text checks. Two images show the legacy parent and qualify return routing only.
Observed raster requests extend to 70 pixels in SP and 84 pixels in MP.
Each of the three logged reset generations per run uses one atlas page and
at most 153 glyphs. Neither run uses the emergency legacy fallback.

SP has no warnings or errors, eliminating the earlier six late legacy-font
material warnings. MP has the same 94 baseline asset/gameplay warnings, with
no added messages or errors. The companion game repository remains clean.

Review also exposes existing incomplete UI behavior: focusing the brightness
slider can leave part of its adjacent numeric readout below the scroll edge.
The earlier text-scale capture already exhibits that clipping. Applying the
85% scene-resolution/CRT combination in OpenGL also softens the whole retained view;
that combined image does not isolate scene scaling from the intentional CRT
effect or establish a regression in the existing native-output repair. Further
composition qualification remains open. These views establish
font-cache operation and lifecycle, not complete focus/layout/composition
acceptance. The build still unnecessarily repacks unchanged `pak1.pk4`, and
several older renderer source checks retain stale ABI-15 literal assertions.

`TXT-002` remains partial. Style/weight selection is still absent from the
retained face interface; canonical documents do not yet expose those traits.
Font-size animation samples rasterize at their requested integer size, but
transform-scale animation does not yet reserve density for its largest size.
Animation churn, projected world surfaces, cross-platform behavior, complete
real-font layout and the required fractional-scale gallery need qualification.
Shaping, kerning, fallback-font selection, bidirectional text and grapheme/IME
work remain separate unfinished requirements. The cache's emergency fallback
and fixed budgets also need full-corpus performance qualification.

The follow-up 17 September source/stage audit finds no `kern` or `GPOS` tables
in any of the seven packaged generated faces. The existing `KernAdvance`
function cannot provide missing pair data. Completing `TXT-003` must therefore
address the generated font data and source-faithful spacing policy alongside
the shared measurement/draw/caret path, token-boundary context and shaping.
Adding a lookup call alone would not change shipped text. The table inventory
and source/stage hashes are retained in
`.tmp/ui/paired-field-focus/font-table-audit.json`; no font data is changed or
language/shaping qualification inferred by this audit.
