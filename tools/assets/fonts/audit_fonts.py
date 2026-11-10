"""Audit the shipped openQ4 TrueType faces against the retail bitmap atlases.

Every glyph a face traced from a retail atlas is rasterised back into that
atlas's own pixel space - same scale, same bearings - with the generator's own
analytic rasteriser, and scored against the retail coverage it came from:

* IoU and mean error of the coverage, and the count of pixels that disagree by
  more than half a level (lost or extra ink a reader would see);
* topology: connected ink components and enclosed holes at the 50% level, so a
  closed counter, a lost i-dot or a merged stroke is caught even when the area
  barely changes;
* the advance against the retail one (the generator rounds advances up).

Glyphs with no retail source - composed accents, donor scripts, synthesized
symbols - have nothing to be compared against, so they are checked for
structural faults instead (stray specks, empty or out-of-band outlines, marks
that collide with their base) and drawn on specimen sheets for inspection.

Finally the required character set - every code point any shipped string table
uses, all of Latin-1 and Windows-1252, Latin Extended-A and the Cyrillic block -
is checked against every face's cmap.

Usage:
    python audit_fonts.py --source <dir with *_48.fontdat/*.tga and bigchars.tga>
                          --fonts content/baseoq4/pak0/fonts --output .tmp/fontaudit

The source directory is what ``extract_source_fonts.py`` produces.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parent))

from q4font.charset import byte_to_unicode  # noqa: E402
from q4font.donor import _record_to_path  # noqa: E402
from q4font.fontdat import SourceFont, load_source_font  # noqa: E402
from q4font.grid import load_grid_font  # noqa: E402
from q4font.path import Path2D  # noqa: E402
from q4font.raster import rasterize  # noqa: E402
from build_openq4_fonts import FACES as SPECS  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
STRINGS = ROOT / "content" / "baseoq4" / "pak0" / "strings"

# Faces and the atlas each one was traced from.
FACES = {
	"chain": "chain",
	"lowpixel": "lowpixel",
	"marine": "marine",
	"profont": "profont",
	"r_strogg": "r_strogg",
	"strogg": "strogg",
	"bigchars": "bigchars.tga",
}

# 'strogg' is a decorative rune face, Latin-only by design: the retained Strogg
# pause folds everything else onto it, so it is exempt from script coverage.
LATIN_ONLY = {"strogg"}

# Score thresholds that flag a traced glyph for a closer look.
IOU_FLAG = 0.90
GRID_IOU_FLAG = 0.75
BAD_PIXEL_FLAG = 6


def required_code_points() -> dict[str, set[int]]:
	"""What every extended face has to draw, grouped by why."""
	groups: dict[str, set[int]] = {}
	tables: set[int] = set()
	for path in STRINGS.glob("*.lang"):
		for character in path.read_text(encoding="utf-8"):
			if ord(character) >= 0x20:
				tables.add(ord(character))
	groups["string tables"] = tables
	groups["ASCII"] = set(range(0x20, 0x7F))
	# Latin-1 is what typed text and a legacy table can produce; NBSP and the
	# soft hyphen included, since an engine-side fold is not a glyph.
	groups["Latin-1"] = set(range(0xA0, 0x100))
	groups["Windows-1252"] = {byte_to_unicode(b) for b in range(0x80, 0xA0)} - set(range(0x80, 0xA0))
	groups["Latin Extended-A"] = set(range(0x100, 0x180))
	groups["Cyrillic"] = set(range(0x400, 0x460)) | {0x490, 0x491}
	groups["typography"] = {0x2013, 0x2014, 0x2018, 0x2019, 0x201A, 0x201C, 0x201D, 0x201E,
	                        0x2020, 0x2021, 0x2022, 0x2026, 0x2030, 0x2039, 0x203A, 0x20AC, 0x2116, 0x2122}
	return groups


class Face:
	def __init__(self, path: Path) -> None:
		self.path = path
		self.font = TTFont(path)
		self.glyph_set = self.font.getGlyphSet()
		self.cmap = self.font.getBestCmap()
		self.upem = self.font["head"].unitsPerEm
		self.hmtx = self.font["hmtx"]
		os2 = self.font["OS/2"]
		self.cap_height = getattr(os2, "sCapHeight", 0) or 0
		self.x_height = getattr(os2, "sxHeight", 0) or 0
		self.ascender = self.font["hhea"].ascent
		self.descender = -self.font["hhea"].descent

	def outline(self, codepoint: int) -> tuple[Path2D, int] | None:
		name = self.cmap.get(codepoint)
		if name is None:
			return None
		pen = DecomposingRecordingPen(self.glyph_set)
		self.glyph_set[name].draw(pen)
		return _record_to_path(pen.value), self.hmtx[name][0]


def render_in_atlas_space(face: Face, codepoint: int, source: SourceFont, slot, shape) -> np.ndarray | None:
	"""Rasterise a face glyph into the pixel block the retail slot occupies."""
	result = face.outline(codepoint)
	if result is None:
		return None
	path, _ = result
	scale = face.upem / source.point_size
	# Inverse of the generator's placement: font units -> slot-local pixels.
	local = path.transformed(1.0 / scale, -1.0 / scale, -slot.bearing_x, slot.bearing_y)
	return rasterize(local, shape[1], shape[0])


def components(mask: np.ndarray) -> int:
	"""4-connected component count of a boolean image."""
	try:
		from scipy import ndimage
	except ImportError:
		ndimage = None
	if ndimage is not None:
		return int(ndimage.label(mask)[1])
	seen = np.zeros(mask.shape, dtype=bool)
	count = 0
	height, width = mask.shape
	for y in range(height):
		for x in range(width):
			if not mask[y, x] or seen[y, x]:
				continue
			count += 1
			stack = [(y, x)]
			seen[y, x] = True
			while stack:
				cy, cx = stack.pop()
				for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
					if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not seen[ny, nx]:
						seen[ny, nx] = True
						stack.append((ny, nx))
	return count


def topology(coverage: np.ndarray) -> tuple[int, int]:
	"""(ink components, enclosed holes) at the 50% level."""
	ink = coverage >= 0.5
	padded = np.pad(~ink, 1, constant_values=True)
	# Background components minus the one outside region are the holes.
	return components(ink), max(0, components(padded) - 1)


def compare_traced(face_key: str, face: Face, source: SourceFont) -> list[dict]:
	results = []
	scale = face.upem / source.point_size
	spec = SPECS.get(face_key)
	# Cells the generator deliberately does not trace - damaged art it rebuilds,
	# and console cells that draw another character - have no retail reference.
	rebuilt = set(spec.rebuild) if spec else set()
	remap = dict(spec.cell_remap) if spec else {}
	for slot in source.glyphs:
		if slot.code < 33 or not slot.has_outline:
			continue
		codepoint = byte_to_unicode(slot.code)
		if slot.code in remap:
			codepoint = remap[slot.code]
			if codepoint is None:
				continue
		if codepoint in rebuilt or unicodedata.category(chr(codepoint)) == "Cc":
			continue
		atlas = source.coverage(slot)
		if atlas.size == 0 or atlas.max() < 0.25:
			continue
		entry: dict = {"code": slot.code, "codepoint": codepoint, "char": chr(codepoint)}
		# Retail .fontdat rects start at the ink on the left but keep a texel of
		# space on the other three sides, so ink lying on the right, top or
		# bottom edge means the artwork was cut off when the atlas was made - a
		# defect a faithful trace reproduces. (Grid cells are measured tight on
		# every side, so the test means nothing there.) Left-side clipping cannot
		# be told from the normal case this way and needs the specimen sheets.
		if not FACES.get(face_key, "").endswith(".tga"):
			clipped = [side for side, edge in (("right", atlas[:, -1]), ("top", atlas[0, :]),
			                                   ("bottom", atlas[-1, :]))
			           if int((edge > 0.5).sum()) >= 3]
			if clipped:
				entry["clipped"] = clipped
		rendered = render_in_atlas_space(face, codepoint, source, slot, atlas.shape)
		if rendered is None:
			entry.update({"missing": True, "flag": True})
			results.append(entry)
			continue
		diff = rendered - atlas
		inter = float(np.minimum(rendered, atlas).sum())
		union = float(np.maximum(rendered, atlas).sum())
		atlas_topo = topology(atlas)
		ttf_topo = topology(rendered)
		_, advance_units = face.outline(codepoint)
		advance_px = advance_units / scale
		entry.update({
			"iou": round(inter / union, 4) if union > 0 else 1.0,
			"mae": round(float(np.abs(diff).mean()), 4),
			"lost": int((diff < -0.5).sum()),
			"extra": int((diff > 0.5).sum()),
			"area_ratio": round(float(rendered.sum() / max(atlas.sum(), 1e-6)), 3),
			"atlas_topology": atlas_topo,
			"ttf_topology": ttf_topo,
			"advance_delta": round(advance_px - slot.advance, 3),
		})
		# A 16 pixel console cell is mostly antialiasing: a hairline that dips
		# under half coverage splits the atlas glyph at the 50% level, and the
		# smoothed trace legitimately moves IoU on glyphs a few pixels wide. Only
		# pixels that visibly disagree count there.
		grid = FACES.get(face_key, "").endswith(".tga")
		entry["flag"] = bool(
			"clipped" in entry
			or entry["iou"] < (GRID_IOU_FLAG if grid else IOU_FLAG)
			or entry["lost"] + entry["extra"] >= BAD_PIXEL_FLAG
			or (atlas_topo != ttf_topo and not grid)
			or not (-0.01 <= entry["advance_delta"] <= 1.0 / scale * 2 + 0.01)
		)
		entry["_atlas"] = atlas
		entry["_ttf"] = rendered
		results.append(entry)
	return results


# Combining marks that sit above their letter and should never touch it.
ABOVE_COMBINING = {0x0300, 0x0301, 0x0302, 0x0303, 0x0304, 0x0306, 0x0307, 0x0308,
                   0x0309, 0x030A, 0x030B, 0x030C, 0x030F, 0x0311}
# Accents drawn on the dotless forms, so those are what to count against.
DOTLESS = {0x0069: 0x0131, 0x006A: 0x0237}


def ink_islands(face: Face, codepoint: int, pixels: int = 96) -> int | None:
	"""Connected ink components of a glyph rendered at ``pixels`` per em."""
	result = face.outline(codepoint)
	if result is None or not result[0].contours:
		return None
	path = result[0]
	bounds = path.bounds()
	scale = pixels / face.upem
	local = path.transformed(scale, -scale, 2.0 - bounds[0] * scale, 2.0 + bounds[3] * scale)
	width = int(math.ceil((bounds[2] - bounds[0]) * scale)) + 5
	height = int(math.ceil((bounds[3] - bounds[1]) * scale)) + 5
	return components(rasterize(local, width, height) >= 0.5)


def _decompose(codepoint: int) -> list[int]:
	"""Full canonical decomposition: the bare letter, then every mark on it."""
	decomposition = unicodedata.decomposition(chr(codepoint))
	if not decomposition or decomposition.startswith("<"):
		return [codepoint]
	parts = [int(part, 16) for part in decomposition.split()]
	return _decompose(parts[0]) + parts[1:]


def fused_accent(face: Face, codepoint: int) -> bool:
	"""True when a letter's accent runs into the letter (no ink island of its own).

	Only letters whose every mark sits above are judged: an ogonek or cedilla
	is meant to join its letter, so island counts say nothing about them.
	"""
	parts = _decompose(codepoint)
	base, marks = parts[0], parts[1:]
	if not marks or not all(mark in ABOVE_COMBINING for mark in marks):
		return False
	base = DOTLESS.get(base, base) if DOTLESS.get(base) in face.cmap else base
	# A face that folds accents away (the Strogg runes) draws the bare letter.
	if base not in face.cmap or face.cmap[base] == face.cmap.get(codepoint):
		return False
	base_islands = ink_islands(face, base)
	islands = ink_islands(face, codepoint)
	return base_islands is not None and islands is not None and islands <= base_islands


def structural_checks(face: Face, codepoints: list[int]) -> list[dict]:
	"""Faults that need no reference: specks, empty outlines, out-of-band ink, fused accents."""
	issues = []
	band_low = -face.descender - 0.15 * face.upem
	band_high = face.ascender + 0.15 * face.upem
	for codepoint in codepoints:
		result = face.outline(codepoint)
		if result is None:
			continue
		path, advance = result
		category = unicodedata.category(chr(codepoint))
		if not path.contours:
			if category[0] in "LNPS" and codepoint not in (0x20, 0xA0) and not (0x2000 <= codepoint <= 0x200F):
				issues.append({"codepoint": codepoint, "issue": "empty outline for a visible character"})
			continue
		areas = [abs(c.signed_area()) for c in path.contours]
		biggest = max(areas)
		for area in areas:
			if area < 0.0004 * face.upem * face.upem and area < 0.02 * biggest:
				issues.append({"codepoint": codepoint, "issue": f"speck contour (area {area:.0f})"})
				break
		bounds = path.bounds()
		if bounds and (bounds[1] < band_low or bounds[3] > band_high):
			issues.append({"codepoint": codepoint, "issue": f"ink outside the line band ({bounds[1]:.0f}..{bounds[3]:.0f})"})
		# Combining marks and format controls (the bidi marks) are zero-width.
		if advance <= 0 and category[0] != "M" and category != "Cf":
			issues.append({"codepoint": codepoint, "issue": "zero advance"})
		if codepoint < 0x0500 and fused_accent(face, codepoint):
			issues.append({"codepoint": codepoint, "issue": "accent runs into its letter"})
	return issues


# ---------------------------------------------------------------- sheets

def _tile(atlas: np.ndarray, ttf: np.ndarray, zoom: int) -> Image.Image:
	"""atlas | ttf | difference (red = lost ink, blue = extra ink)."""
	height, width = atlas.shape
	tile = Image.new("RGB", ((width * 3 + 4) * zoom, height * zoom), (40, 40, 40))
	a = Image.fromarray((255 - atlas * 255).astype(np.uint8)).resize((width * zoom, height * zoom), Image.NEAREST)
	t = Image.fromarray((255 - ttf * 255).astype(np.uint8)).resize((width * zoom, height * zoom), Image.NEAREST)
	diff = ttf - atlas
	rgb = np.full((height, width, 3), 255, dtype=np.uint8)
	rgb[..., 1] = (255 - np.abs(diff) * 255).astype(np.uint8)
	rgb[..., 0] = np.where(diff > 0, 255 - diff * 255, 255).astype(np.uint8)
	rgb[..., 2] = np.where(diff < 0, 255 + diff * 255, 255).astype(np.uint8)
	d = Image.fromarray(rgb).resize((width * zoom, height * zoom), Image.NEAREST)
	tile.paste(a.convert("RGB"), (0, 0))
	tile.paste(t.convert("RGB"), ((width + 2) * zoom, 0))
	tile.paste(d, ((width * 2 + 4) * zoom, 0))
	return tile


def contact_sheet(entries: list[dict], path: Path, zoom: int, columns: int = 6) -> None:
	tiles = []
	for entry in entries:
		if "_atlas" not in entry:
			continue
		tile = _tile(entry["_atlas"], entry["_ttf"], zoom)
		label = Image.new("RGB", (tile.width, 14), (0, 0, 0))
		ImageDraw.Draw(label).text(
			(2, 1), f"U+{entry['codepoint']:04X} iou {entry['iou']:.2f} -{entry['lost']}/+{entry['extra']}", fill=(255, 255, 0))
		framed = Image.new("RGB", (tile.width, tile.height + 14), (0, 0, 0))
		framed.paste(label, (0, 0))
		framed.paste(tile, (0, 14))
		tiles.append(framed)
	if not tiles:
		return
	cell_w = max(t.width for t in tiles) + 6
	cell_h = max(t.height for t in tiles) + 6
	rows = math.ceil(len(tiles) / columns)
	sheet = Image.new("RGB", (cell_w * columns, cell_h * rows), (20, 20, 20))
	for index, tile in enumerate(tiles):
		sheet.paste(tile, ((index % columns) * cell_w, (index // columns) * cell_h))
	sheet.save(path)


def specimen_sheet(face: Face, codepoints: list[int], path: Path, pixels: int = 56, columns: int = 16,
                   reference: str = "HOAnoxg") -> None:
	"""Glyphs drawn at one size on a common baseline, with cap/x-height guides,
	led by a few traced reference letters so style mismatches stand out."""
	scale = pixels / face.upem
	ascent = face.ascender * scale
	descent = face.descender * scale
	cell_h = int(math.ceil(ascent + descent)) + 22
	cell_w = int(pixels * 1.25)
	items = [ord(c) for c in reference] + [cp for cp in codepoints if cp in face.cmap]
	rows = math.ceil(len(items) / columns)
	sheet = Image.new("L", (cell_w * columns, cell_h * rows), 255)
	draw = ImageDraw.Draw(sheet)
	for index, codepoint in enumerate(items):
		x0 = (index % columns) * cell_w
		y0 = (index // columns) * cell_h
		baseline = y0 + 14 + ascent
		draw.line([(x0, baseline), (x0 + cell_w - 2, baseline)], fill=200)
		draw.line([(x0, baseline - face.cap_height * scale), (x0 + cell_w - 2, baseline - face.cap_height * scale)], fill=225)
		draw.line([(x0, baseline - face.x_height * scale), (x0 + cell_w - 2, baseline - face.x_height * scale)], fill=235)
		draw.text((x0 + 2, y0 + 1), f"{codepoint:04X}", fill=120)
		result = face.outline(codepoint)
		if result is None or not result[0].contours:
			continue
		outline, _ = result
		local = outline.transformed(scale, -scale, x0 + 0.1 * pixels, baseline)
		bounds = local.bounds()
		if bounds is None:
			continue
		ox, oy = int(math.floor(bounds[0])) - 1, int(math.floor(bounds[1])) - 1
		w = int(math.ceil(bounds[2])) - ox + 2
		h = int(math.ceil(bounds[3])) - oy + 2
		coverage = rasterize(local.transformed(1.0, 1.0, -ox, -oy), w, h)
		ink = Image.fromarray((255 - coverage * 255).astype(np.uint8))
		region = sheet.crop((ox, oy, ox + w, oy + h))
		sheet.paste(Image.fromarray(np.minimum(np.asarray(region), np.asarray(ink))), (ox, oy))
	sheet.save(path)


BLOCKS = {
	"latin1": list(range(0xA0, 0x100)),
	"latin_ext_a": list(range(0x100, 0x180)),
	"latin_ext_b": list(range(0x180, 0x250)),
	"cyrillic": list(range(0x400, 0x460)) + [0x490, 0x491],
	"greek": list(range(0x370, 0x400)),
	"punctuation": list(range(0x2000, 0x2070)) + list(range(0x20A0, 0x20C0)) + list(range(0x2100, 0x2150)),
	"symbols": list(range(0x2190, 0x2200)) + list(range(0x25A0, 0x2600)) + [0x2605, 0x2606],
}


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--source", type=Path, required=True)
	parser.add_argument("--fonts", type=Path, default=ROOT / "content/baseoq4/pak0/fonts")
	parser.add_argument("--output", type=Path, required=True)
	parser.add_argument("--faces", default="")
	parser.add_argument("--sheets", action="store_true", help="also write specimen sheets per block")
	args = parser.parse_args()
	try:
		sys.stdout.reconfigure(encoding="utf-8")
	except AttributeError:
		pass

	keys = [k for k in args.faces.split(",") if k] or list(FACES)
	args.output.mkdir(parents=True, exist_ok=True)
	required = required_code_points()
	summary = {}
	for key in keys:
		face = Face(args.fonts / f"{key}.ttf")
		atlas_name = FACES[key]
		source = (load_grid_font(args.source / atlas_name, key) if atlas_name.endswith(".tga")
		          else load_source_font(args.source, atlas_name, 48))
		out = args.output / key
		out.mkdir(parents=True, exist_ok=True)

		traced = compare_traced(key, face, source)
		flagged = [e for e in traced if e.get("flag")]
		zoom = 3 if source.point_size >= 40 else 8
		contact_sheet(sorted(traced, key=lambda e: e.get("iou", 0.0))[:48], out / "worst_traced.png", zoom)
		contact_sheet([e for e in traced if "_atlas" in e], out / "all_traced.png", zoom, columns=8)

		traced_codepoints = {e["codepoint"] for e in traced}
		others = sorted(cp for cp in face.cmap if cp not in traced_codepoints and cp >= 0x20)
		structural = structural_checks(face, others)

		coverage = {}
		if key not in LATIN_ONLY:
			for group, codepoints in required.items():
				missing = sorted(cp for cp in codepoints if cp not in face.cmap and unicodedata.category(chr(cp))[0] != "C")
				if missing:
					coverage[group] = [f"U+{cp:04X} {chr(cp)}" for cp in missing]

		if args.sheets:
			for block, codepoints in BLOCKS.items():
				specimen_sheet(face, codepoints, out / f"specimen_{block}.png")

		ious = [e["iou"] for e in traced if "iou" in e]
		summary[key] = {
			"traced": len(traced),
			"mean_iou": round(float(np.mean(ious)), 4) if ious else None,
			"min_iou": round(float(np.min(ious)), 4) if ious else None,
			"flagged": [
				{k: v for k, v in e.items() if not k.startswith("_")} for e in flagged
			],
			"structural": [
				{"codepoint": f"U+{i['codepoint']:04X} {chr(i['codepoint'])}", "issue": i["issue"]} for i in structural
			],
			"missing": coverage,
			"glyphs": len(face.cmap),
		}
		print(f"{key:9s} traced={len(traced):3d} mean_iou={summary[key]['mean_iou']} min_iou={summary[key]['min_iou']} "
		      f"flagged={len(flagged)} structural={len(structural)} "
		      f"missing={sum(len(v) for v in coverage.values())} cmap={len(face.cmap)}")
	(args.output / "audit.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
