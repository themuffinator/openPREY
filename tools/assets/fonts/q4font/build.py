"""Assemble one openQ4 TrueType face from a retail Quake 4 bitmap font."""
from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, field, replace
from pathlib import Path as FilePath

import numpy as np
from PIL import Image
from fontTools.agl import UV2AGL
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

from .charset import (
	CYRILLIC_HOMOGLYPHS,
	DERIVED_FROM_LATIN,
	GREEK_HOMOGLYPHS,
	NOTO_ARABIC_BLOCKS,
	NOTO_HEBREW_BLOCKS,
	NOTO_SANS_BLOCKS,
	byte_to_unicode,
	unicode_ranges,
)
from .donor import get_face, solve_instance
from .fontdat import SourceFont, load_prey_source_font, load_source_font, slot_stretch
from .grid import load_grid_font
from .path import Contour, Path2D
from .trace import TraceOptions, trace_coverage

UNITS_PER_EM = 2048
# FontBuilder otherwise stamps the current time into the ``head`` table.  These
# runtime assets are generated from fixed retail inputs, so a stable timestamp
# keeps a rebuild byte-for-byte reproducible.
DETERMINISTIC_TTF_TIMESTAMP = 3818534400  # 2025-01-01T00:00:00Z in the Mac epoch
# Effective pixel size a glyph is traced at. Sources at or above this are traced
# as they are; smaller ones are resampled up to roughly this before tracing.
DENSIFY_TARGET_SIZE = 64.0
# The atlas size the tracer's default thresholds are tuned against.
TRACE_REFERENCE_SIZE = 48.0
VENDOR_ID = "DMPR"

# Combining marks, and where they sit relative to the letter they attach to.
ABOVE_MARKS = {0x0300, 0x0301, 0x0302, 0x0303, 0x0304, 0x0306, 0x0307, 0x0308,
               0x0309, 0x030A, 0x030B, 0x030C, 0x030F, 0x0311, 0x0312}
BELOW_MARKS = {0x0323, 0x0326, 0x0327, 0x0328, 0x032E, 0x0331}

# Marks no Latin-1 letter carries, taken from the weight-matched donor rather
# than letting the whole accented letter fall back to it; the cedilla only
# where the face's own could not be lifted.
DONOR_MARKS = (0x0306, 0x0328, 0x0327)
# Round or flat marks keep their proportions when made into a capital accent;
# squashing them would turn a dot oval or thin a macron.
UNFLATTENED_MARKS = {0x0304, 0x0307, 0x0308, 0x030A, 0x0312}
# Ink kept clear of a console cell's edges, so rounding the baseline to a
# whole pixel cannot clip an accent or a descender.
CELL_MARGIN = 16.0

# Decompositions that say cedilla where the letter is written with a comma
# below (Latvian, Livonian), and g, whose comma is turned and sits above.
COMMA_FOR_CEDILLA = {0x0122, 0x0136, 0x0137, 0x013B, 0x013C, 0x0145, 0x0146, 0x0156, 0x0157}
TURNED_COMMA_ABOVE = {0x0123}
# A caron on a letter with an ascender is written as an apostrophe after it
# in Czech and Slovak: d', t', l' and capital L'.
APOSTROPHE_CARON = {0x010F, 0x013D, 0x013E, 0x0165}
# Dotted letters that lose their dot under an accent (i-acute is not i-dot-acute).
DOTTED_BASES = {0x0069: 0x0131, 0x006A: 0x0237, 0x0456: 0x0131, 0x0458: 0x0237}

# Marks the retail Latin-1 range already draws, and the precomposed glyph each
# one can be lifted out of.
MARK_DONORS_UPPER = {0x0300: "À", 0x0301: "Á", 0x0302: "Â", 0x0303: "Ã", 0x0308: "Ä", 0x030A: "Å"}
MARK_DONORS_LOWER = {0x0300: "à", 0x0301: "á", 0x0302: "â", 0x0303: "ã", 0x0308: "ä", 0x030A: "å"}


@dataclass
class FaceSpec:
	source: str
	family: str
	style: str = "Regular"
	extended: bool = True
	all_caps: bool = False
	description: str = ""
	# Set for the fixed-cell console sheet, which has no .fontdat beside it.
	grid_atlas: str | None = None
	# Prey uses a Doom 3-style .dat record and can distribute one face across
	# several atlas images; Quake 4's .fontdat record always has one image.
	prey_format: bool = False
	project_name: str = "openQ4"
	bitmap_attribution: str = "the Quake 4 bitmap fonts by Raven Software / id Software"
	# Code points whose retail artwork is damaged - cut off when the atlas was
	# made, or a missing-glyph box in place of the character - so they are
	# rebuilt from the face's own parts instead of traced.
	rebuild: tuple[int, ...] = ()
	# Retail cells that draw a different character than their byte names, as
	# (byte, code point) pairs; None drops a stray copy of another cell.
	cell_remap: tuple[tuple[int, int | None], ...] = ()
	# Take the accents from the face's spacing characters (^ ` ~ and the
	# degree ring) rather than lifting them off its accented letters.
	marks_from_spacing: bool = False


@dataclass
class GlyphEntry:
	name: str
	path: Path2D | None = None
	advance: int = 0
	components: list[tuple[str, float, float]] = field(default_factory=list)


@dataclass
class FaceMetrics:
	ascender: int
	descender: int
	cap_height: int
	x_height: int
	stem: float
	average_advance: float
	# Thickness of a horizontal stroke (H's crossbar), for synthesized bars.
	bar: float = 0.0
	# Height of the lowercase letters actually drawn: the x-height, or the
	# small-capital height in an all-caps face.
	small_height: float = 0.0


def glyph_name(codepoint: int) -> str:
	name = UV2AGL.get(codepoint)
	if name:
		return name
	return f"uni{codepoint:04X}" if codepoint <= 0xFFFF else f"u{codepoint:06X}"


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------


def scanline(path: Path2D, y: float) -> list[float]:
	hits: list[float] = []
	for polygon in path.flatten(3.0):
		count = len(polygon)
		for index in range(count):
			x0, y0 = polygon[index]
			x1, y1 = polygon[(index + 1) % count]
			if (y0 > y) == (y1 > y):
				continue
			t = (y - y0) / (y1 - y0)
			hits.append(x0 + t * (x1 - x0))
	return sorted(hits)


def _vertical_scanline(path: Path2D, x: float) -> list[float]:
	"""Sorted y positions where the outline crosses a vertical line."""
	hits: list[float] = []
	for polygon in path.flatten(3.0):
		count = len(polygon)
		for index in range(count):
			x0, y0 = polygon[index]
			x1, y1 = polygon[(index + 1) % count]
			if (x0 > x) == (x1 > x):
				continue
			t = (x - x0) / (x1 - x0)
			hits.append(y0 + t * (y1 - y0))
	return sorted(hits)


def contour_bounds(contour: Contour) -> tuple[float, float, float, float]:
	polygon = contour.flatten(1.0)
	xs = [p[0] for p in polygon]
	ys = [p[1] for p in polygon]
	return min(xs), min(ys), max(xs), max(ys)


def split_mark(accented: Path2D, base: Path2D, above: bool) -> Path2D | None:
	"""Lift the diacritic out of a precomposed glyph by discarding the base."""
	base_bounds = base.bounds()
	if base_bounds is None:
		return None
	mark = Path2D()
	for contour in accented.contours:
		x0, y0, x1, y1 = contour_bounds(contour)
		if above and y0 >= base_bounds[3] - 0.02 * UNITS_PER_EM:
			mark.contours.append(contour)
		elif not above and y1 <= base_bounds[1] + 0.02 * UNITS_PER_EM:
			mark.contours.append(contour)
	if not mark.contours:
		return None
	# Outer contours wind with a negative area. When only counters come away,
	# the accent is fused to the letter, and what sits above it is the hole of
	# a ring - ProFont's a-ring - not the ring itself.
	if sum(contour.signed_area() for contour in mark.contours) >= 0.0:
		return None
	return mark


def flip_vertical(path: Path2D) -> Path2D:
	bounds = path.bounds()
	if bounds is None:
		return path
	centre = 0.5 * (bounds[1] + bounds[3])
	flipped = path.transformed(1.0, -1.0, 0.0, 2.0 * centre)
	# Mirroring reverses every contour's winding; put it back.
	return Path2D([contour.reverse() for contour in flipped.contours])


def flip_horizontal(path: Path2D, advance: float) -> Path2D:
	flipped = path.transformed(-1.0, 1.0, advance, 0.0)
	return Path2D([contour.reverse() for contour in flipped.contours])


def rotate_half_turn(path: Path2D) -> Path2D:
	"""Turn a shape over about its own centre (a comma into a turned comma)."""
	bounds = path.bounds()
	if bounds is None:
		return path
	cx = 0.5 * (bounds[0] + bounds[2])
	cy = 0.5 * (bounds[1] + bounds[3])
	# Two mirrors make a rotation, so the winding is already right.
	return path.transformed(-1.0, -1.0, 2.0 * cx, 2.0 * cy)


def scale_about(path: Path2D, factor_x: float, factor_y: float, cx: float, cy: float) -> Path2D:
	return path.transformed(factor_x, factor_y, cx - factor_x * cx, cy - factor_y * cy)


def shifted(path: Path2D, dx: float, dy: float) -> Path2D:
	return path.transformed(1.0, 1.0, dx, dy)


def as_outer(contour: Contour) -> Contour:
	"""Wind a synthesized shape like a traced outer contour.

	TrueType fills by the non-zero rule, so a bar laid over a stem only merges
	with it when both run the same way; opposite windings cancel and punch a
	hole where they overlap. Traced outers are clockwise in font units (y up),
	which is a negative signed area.
	"""
	return contour if contour.signed_area() < 0 else contour.reverse()


def box(x0: float, y0: float, x1: float, y1: float) -> Contour:
	contour = Contour((x0, y0))
	contour.line_to((x0, y1))
	contour.line_to((x1, y1))
	contour.line_to((x1, y0))
	return as_outer(contour)


def quad(points: list[tuple[float, float]]) -> Contour:
	contour = Contour(points[0])
	for point in points[1:]:
		contour.line_to(point)
	return as_outer(contour)


def drop_contours_above(path: Path2D, level: float) -> Path2D:
	"""Remove every contour lying wholly above ``level`` - an i or j's dot."""
	kept = [c for c in path.contours if contour_bounds(c)[1] < level]
	return Path2D(kept)


# ---------------------------------------------------------------------------
# builder
# ---------------------------------------------------------------------------


class FaceBuilder:
	def __init__(self, spec: FaceSpec, source_dir: FilePath, donor_dir: FilePath, options: TraceOptions | None = None):
		self.spec = spec
		if spec.grid_atlas is not None:
			self.source: SourceFont = load_grid_font(source_dir / spec.grid_atlas, spec.source)
		elif spec.prey_format:
			self.source = load_prey_source_font(source_dir / spec.source, 48, spec.source)
		else:
			self.source = load_source_font(source_dir, spec.source, 48)
		# Small sources are densified before tracing.  The tracer places an edge
		# from the coverage value itself, treating a sample as the area of a
		# pixel cut by one edge.  That holds at 48 point, where a stem spans
		# several pixels, but not on the 16 pixel console cells where a single
		# pixel is usually cut by both sides of a stem at once - there the
		# assumption breaks down and contours come out lumpy.  Resampling first
		# separates the two edges into different pixels and restores it.
		self.densify = max(1, int(round(DENSIFY_TARGET_SIZE / max(self.source.point_size, 1.0))))
		# Distance thresholds in the tracer are source pixels standing in for
		# fractions of an em, so they follow the size actually being traced.
		self.options = (options or TraceOptions()).for_point_size(self.source.point_size * self.densify)
		if self.densify > 1:
			# The geometric thresholds above are fractions of an em, but the
			# fitting tolerances absorb antialiasing noise, which is a fraction
			# of a *source* pixel at any size. Scaled as distances they shrank to
			# a twenty-fifth of a console pixel, so every kink the bilinear
			# resample leaves at a pixel boundary was traced as a notch and the
			# console's bevels came out stepped. Hold them at their reference
			# value in source pixels instead, and smooth the resampled contour.
			noise = TRACE_REFERENCE_SIZE / self.source.point_size
			self.options = replace(
				self.options,
				line_tolerance=self.options.line_tolerance * noise,
				curve_tolerance=self.options.curve_tolerance * noise,
				axis_cluster=self.options.axis_cluster * noise,
				smoothing_passes=2,
			)
		self.donor_dir = donor_dir
		self.scale = UNITS_PER_EM / self.source.point_size
		self.glyphs: dict[str, GlyphEntry] = {}
		self.cmap: dict[int, str] = {}
		self.paths: dict[str, Path2D] = {}
		self.advances: dict[str, int] = {}
		self.marks_upper: dict[int, Path2D] = {}
		self.marks_lower: dict[int, Path2D] = {}
		self.report: dict[str, int] = {}
		# Glyphs drawn straight from the retail atlas, as opposed to built here.
		self.traced: set[str] = set()
		# Retail drawings of the rebuilt code points, consulted only for marks.
		self.retail: dict[int, Path2D] = {}
		# The console clips every glyph to its cell, so a fixed-cell face has
		# to keep all ink between these; set when the face is measured.
		self.cell_top: float | None = None
		self.cell_bottom: float | None = None

	# -- stage 1: the retail bitmaps ---------------------------------------

	def trace_source(self) -> None:
		notdef = GlyphEntry(".notdef", advance=int(round(0.5 * UNITS_PER_EM)))
		self.glyphs[".notdef"] = notdef

		remap = dict(self.spec.cell_remap)
		for slot in self.source.glyphs:
			if slot.code < 32:
				continue
			codepoint = byte_to_unicode(slot.code)
			if slot.code in remap:
				codepoint = remap[slot.code]
				if codepoint is None:
					continue
			if unicodedata.category(chr(codepoint)) == "Cc":
				# The bytes Windows-1252 leaves unassigned are C1 control codes,
				# and the console sheet fills one with a solid missing-glyph
				# block. The console relies on no face covering them, so an
				# unassigned byte draws as an empty cell.
				continue
			name = glyph_name(codepoint)
			# Round advances up rather than to nearest.  The engine measures
			# text with Ceil() on the advance, so an advance that lands a
			# fraction below the retail value loses a whole unit per glyph and
			# strings come out a pixel short of the layout the GUIs expect.
			# Overshoot is at most one font unit, or 0.02 of a point.
			advance = int(math.ceil(slot.advance * self.scale - 1e-6))

			if slot.code == 32:
				# Space occupies a small blank patch in the atlas, so it passes
				# the has-outline test; it is always emitted blank.  The retail
				# chain font also ships a zero advance for it at all three point
				# sizes, which collapses every gap in a line of text.  Every
				# other face uses exactly half an em, so fall back to that.
				if advance <= 0:
					advance = UNITS_PER_EM // 2
					self.report["space_repaired"] = 1
				self._add(name, codepoint, None, advance)
				continue

			if codepoint in self.spec.rebuild:
				# Kept out of the character map, but still traced: a letter
				# squeezed out of shape can keep a usable mark, such as the
				# console's C-cedilla, which is shortened yet keeps its cedilla.
				if slot.has_outline:
					retail = self._trace_slot(slot)
					if retail.contours:
						self.retail[codepoint] = retail
				continue

			if not slot.has_outline:
				# A blank cell is a character the retail art never drew, not a
				# space. Recording it as an empty glyph used to stop every later
				# stage from filling it - the console face drew S-caron and the
				# curly quotes as nothing at all - so leave the slot open.
				if self.spec.grid_atlas is None and advance > 0:
					self._add(name, codepoint, None, advance)
				continue

			traced = self._trace_slot(slot)
			if not traced.contours:
				# Some Prey slots (notably non-breaking space) serialize a useful
				# advance and UV rectangle even though their source page has no ink.
				# Preserve the blank advancing glyph: omitting it makes legacy
				# Windows-1252 text fall through to .notdef and changes layout.
				if advance > 0:
					self._add(name, codepoint, None, advance)
					self.report["blank_advancing_slots"] = self.report.get("blank_advancing_slots", 0) + 1
					continue
				# Other empty reserved slots have no layout meaning. Leaving those
				# absent lets a donor supply a real glyph where one is available.
				self.report["blank_slots"] = self.report.get("blank_slots", 0) + 1
				continue
			self._add(name, codepoint, traced, advance)
			self.traced.add(name)

		self.report["traced"] = len(self.paths)

	def _trace_slot(self, slot) -> Path2D:
		"""Trace one retail slot and place it in font units on the pen.

		The bitmap renderer draws a glyph's atlas block across its recorded
		image rect, so where the two differ the ink is stretched to fill the
		rect. Prey's menu face records every image 3 units taller than its
		atlas block at 48 point (1 unit at 24); tracing the block 1:1 squashed
		those letters and lifted them off the baseline. Map the trace onto the
		image rect exactly as the bitmap path draws it.
		"""
		coverage = self.source.coverage(slot)
		traced = self._trace(coverage)
		if not traced.contours:
			return traced
		# Grid sheets (bigchars) are sliced by cell, not by a recorded rect.
		stretch_x, stretch_y = (1.0, 1.0) if self.spec.grid_atlas is not None else slot_stretch(slot, coverage.shape)
		# Pixel space (y down, glyph-local) -> font units (y up, on the pen).
		return traced.transformed(
			self.scale * stretch_x,
			-self.scale * stretch_y,
			slot.bearing_x * self.scale,
			slot.bearing_y * self.scale,
		)

	def _trace(self, coverage) -> Path2D:
		"""Trace one glyph, resampling first when the source is small."""
		if self.densify <= 1:
			return trace_coverage(coverage, self.options)
		height, width = coverage.shape
		if height == 0 or width == 0:
			return Path2D()
		# Bilinear is the right reconstruction here: the sheet is antialiased,
		# so the coverage ramp already encodes where the edge sits and the
		# resample just spreads it over enough samples for the tracer to use.
		big = np.asarray(
			Image.fromarray((np.clip(coverage, 0.0, 1.0) * 255.0).astype(np.uint8)).resize(
				(width * self.densify, height * self.densify), Image.BILINEAR
			),
			dtype=np.float32,
		) / 255.0
		traced = trace_coverage(big, self.options)
		return traced.transformed(1.0 / self.densify, 1.0 / self.densify)

	def _add(self, name: str, codepoint: int | None, path: Path2D | None, advance: int) -> None:
		entry = self.glyphs.get(name)
		if entry is None:
			entry = GlyphEntry(name, path, advance)
			self.glyphs[name] = entry
			if path is not None:
				self.paths[name] = path
			self.advances[name] = advance
		if codepoint is not None:
			self.cmap.setdefault(codepoint, name)

	# -- stage 2: measurements ---------------------------------------------

	def measure(self) -> FaceMetrics:
		cap = self._top_of("H") or self._top_of("A") or 0.62 * UNITS_PER_EM
		x_height = self._top_of("x") or self._top_of("o") or 0.48 * UNITS_PER_EM
		if self.spec.all_caps:
			x_height = cap

		stem = self._stem_of("I") or self._stem_of("H") or self._stem_of("l") or 0.1 * UNITS_PER_EM

		widths = [self.advances[glyph_name(ord(c))] for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if glyph_name(ord(c)) in self.advances]
		average = sum(widths) / len(widths) if widths else 0.6 * UNITS_PER_EM

		ascender = int(round(self.source.ascender * self.scale))
		descender = int(round(self.source.descender * self.scale))
		# Some retail faces report a zero descender because they are all caps;
		# fall back to what the outlines actually reach so the line box is sane.
		lowest = min((p.bounds()[1] for p in self.paths.values() if p.bounds()), default=0.0)
		highest = max((p.bounds()[3] for p in self.paths.values() if p.bounds()), default=cap)
		ascender = max(ascender, int(round(highest)))
		descender = max(descender, int(round(-lowest)))

		bar = self._bar_of("H") or self._bar_of("e") or 0.8 * stem
		small = self._top_of("x") or self._top_of("o") or x_height
		if self.spec.grid_atlas is not None:
			self.cell_top = float(ascender)
			self.cell_bottom = -float(descender)

		return FaceMetrics(ascender, descender, int(round(cap)), int(round(x_height)), stem, average, bar, small)

	def _bar_of(self, character: str) -> float | None:
		"""Thickness of the horizontal stroke crossing the glyph's centre line."""
		path = self.paths.get(glyph_name(ord(character)))
		if path is None:
			return None
		bounds = path.bounds()
		if bounds is None:
			return None
		x = 0.5 * (bounds[0] + bounds[2])
		hits = _vertical_scanline(path, x)
		# Pair the crossings into ink spans and take the one nearest mid-height.
		spans = [(hits[i], hits[i + 1]) for i in range(0, len(hits) - 1, 2)]
		if not spans:
			return None
		middle = 0.5 * (bounds[1] + bounds[3])
		low, high = min(spans, key=lambda s: abs(0.5 * (s[0] + s[1]) - middle))
		return high - low

	def _top_of(self, character: str) -> float | None:
		path = self.paths.get(glyph_name(ord(character)))
		if path is None:
			return None
		bounds = path.bounds()
		return bounds[3] if bounds else None

	def _stem_of(self, character: str) -> float | None:
		path = self.paths.get(glyph_name(ord(character)))
		if path is None:
			return None
		bounds = path.bounds()
		if bounds is None:
			return None
		hits = scanline(path, 0.5 * (bounds[1] + bounds[3]))
		if len(hits) < 2:
			return None
		return hits[1] - hits[0]

	# -- stage 3: diacritics ------------------------------------------------

	def extract_marks(self, metrics: FaceMetrics) -> None:
		if self.spec.marks_from_spacing:
			self._spacing_marks(metrics)
		else:
			for table, target, base_char in (
				(MARK_DONORS_UPPER, self.marks_upper, "A"),
				(MARK_DONORS_LOWER, self.marks_lower, "a"),
			):
				base = self.paths.get(glyph_name(ord(base_char)))
				if base is None:
					continue
				for mark_cp, accented_char in table.items():
					accented = self.paths.get(glyph_name(ord(accented_char)))
					if accented is None:
						continue
					mark = split_mark(accented, base, above=True)
					if mark is not None:
						target[mark_cp] = mark

		cedilla_base = self.paths.get(glyph_name(ord("C")))
		cedilla = self.paths.get(glyph_name(ord("Ç"))) or self.retail.get(ord("Ç"))
		if cedilla_base is not None and cedilla is not None:
			extracted = split_mark(cedilla, cedilla_base, above=False)
			bounds = extracted.bounds() if extracted is not None else None
			# A cedilla fused to its letter comes away as a sliver (the console
			# C-cedilla's); the donor's, matched to the face, stands in for that.
			if bounds and bounds[3] - bounds[1] >= 0.07 * UNITS_PER_EM and bounds[2] - bounds[0] >= 0.05 * UNITS_PER_EM:
				self.marks_upper[0x0327] = extracted
				self.marks_lower[0x0327] = extracted

		# A ring that could not be lifted cleanly is the face's degree sign,
		# brought down to the size of an accent.
		degree = self.paths.get(glyph_name(0x00B0))
		lower_ref = self._bounds_of("a")
		degree_bounds = degree.bounds() if degree is not None else None
		if 0x030A not in self.marks_lower and degree_bounds and lower_ref is not None:
			height = 0.36 * float(metrics.small_height or metrics.x_height)
			factor = min(1.0, height / max(degree_bounds[3] - degree_bounds[1], 1.0))
			ring = scale_about(degree, factor, factor, degree_bounds[0], degree_bounds[1])
			self.marks_lower[0x030A] = self._sit_above(ring, lower_ref, self._mark_gap(self.marks_lower, lower_ref))

		# Caron is a circumflex turned over; macron is a plain bar at the same
		# width.  Both are better derived from the face than imported.
		for target in (self.marks_upper, self.marks_lower):
			circumflex = target.get(0x0302)
			if circumflex is not None:
				target.setdefault(0x030C, flip_vertical(circumflex))
				bounds = circumflex.bounds()
				if bounds:
					thickness = max(metrics.stem * 0.8, 0.02 * UNITS_PER_EM)
					target.setdefault(0x0304, Path2D([box(bounds[0], bounds[3] - thickness, bounds[2], bounds[3])]))
			acute = target.get(0x0301)
			if acute is not None:
				bounds = acute.bounds()
				if bounds:
					# Set side by side, a shallow acute's strokes run together
					# into a zigzag, so one wider than it is tall is first
					# narrowed into a steeper stroke.
					narrow = min(1.0, (bounds[3] - bounds[1]) / max(bounds[2] - bounds[0], 1.0))
					stroke = scale_about(acute, narrow, 1.0, bounds[0], 0.0)
					offset = (bounds[2] - bounds[0]) * narrow * (0.75 if narrow >= 1.0 else 1.0)
					doubled = Path2D(list(stroke.contours) + list(stroke.transformed(1.0, 1.0, offset, 0.0).contours))
					target.setdefault(0x030B, doubled)
			diaeresis = target.get(0x0308)
			if diaeresis is not None and len(diaeresis.contours) >= 2:
				single = Path2D([diaeresis.contours[0]])
				bounds_all = diaeresis.bounds()
				bounds_one = single.bounds()
				if bounds_all and bounds_one:
					shift = 0.5 * (bounds_all[0] + bounds_all[2]) - 0.5 * (bounds_one[0] + bounds_one[2])
					target.setdefault(0x0307, single.transformed(1.0, 1.0, shift, 0.0))

		self._repair_capital_marks()
		self.report["marks"] = len(self.marks_upper) + len(self.marks_lower)

	def _bounds_of(self, character: str) -> tuple[float, float, float, float] | None:
		path = self.paths.get(glyph_name(ord(character)))
		return path.bounds() if path is not None else None

	def _spacing_marks(self, metrics: FaceMetrics) -> None:
		"""Lowercase accents taken from the face's spacing characters.

		The console sheet squeezes every accented letter into its 16 pixel
		cell - the letter shortened by a row, the accent drawn straight onto
		it - so neither part can be reused. Its spacing circumflex, grave,
		tilde and degree ring are drawn whole in the face's own stroke, and the
		i supplies the dot. They are sized here as lowercase accents; the
		capitals' are derived from them.
		"""
		reference = self._bounds_of("a")
		o = self._bounds_of("o")
		if reference is None or o is None:
			return
		x_height = float(metrics.x_height)
		height = 0.33 * x_height
		width = 0.85 * (o[2] - o[0])
		gap = 0.12 * x_height

		def seat(mark_cp: int, path: Path2D | None, keep_shape: bool = False) -> None:
			bounds = path.bounds() if path is not None else None
			if not bounds:
				return
			sx = min(1.0, width / max(bounds[2] - bounds[0], 1.0))
			sy = min(1.0, height / max(bounds[3] - bounds[1], 1.0))
			if keep_shape:
				sx = sy = min(sx, sy)
			self.marks_lower[mark_cp] = self._sit_above(scale_about(path, sx, sy, bounds[0], bounds[1]), reference, gap)

		def spacing(character: str) -> Path2D | None:
			return self.paths.get(glyph_name(ord(character)))

		grave = spacing("`")
		seat(0x0300, grave, keep_shape=True)
		seat(0x0301, flip_horizontal(grave, 0.0) if grave is not None else None, keep_shape=True)
		seat(0x0302, spacing("^"))
		seat(0x0303, spacing("~"))
		seat(0x030A, spacing("°"), keep_shape=True)
		i = spacing("i")
		if i is not None:
			dot = Path2D([c for c in i.contours if contour_bounds(c)[1] >= 0.9 * x_height])
			bounds = dot.bounds()
			if bounds:
				self.marks_lower[0x0307] = self._sit_above(dot, reference, gap)
				pair = Path2D(list(dot.contours) + list(shifted(dot, 2.0 * (bounds[2] - bounds[0]), 0.0).contours))
				self.marks_lower[0x0308] = self._sit_above(pair, reference, gap)

	def _repair_capital_marks(self) -> None:
		"""Re-seat capital accents the retail art squeezed onto the letter.

		Neither the 48 point ProFont atlas nor the 16 pixel console cells left
		room above a capital, so Raven set those accents right on the letter
		or ran them into it. Lifted out, such a mark comes away as a sliver
		fused to a piece of the letter, or not at all, and composing with it
		repeats the collision. It is replaced by the face's lowercase accent at
		half the lowercase clearance, the angular ones a fifth flatter - the
		usual treatment of capital accents.
		"""
		upper_ref = self._bounds_of("A")
		lower_ref = self._bounds_of("a")
		if upper_ref is None or lower_ref is None:
			return
		clearances = []
		for mark_cp in (0x0300, 0x0301, 0x0302, 0x0303):
			mark = self.marks_lower.get(mark_cp)
			bounds = mark.bounds() if mark is not None else None
			if bounds:
				clearances.append(bounds[1] - lower_ref[3])
		if not clearances:
			return
		clearances.sort()
		gap = min(max(0.5 * clearances[len(clearances) // 2], 0.025 * UNITS_PER_EM), 0.08 * UNITS_PER_EM)
		repaired = 0
		for mark_cp, mark in self.marks_lower.items():
			lower = mark.bounds() if mark_cp in ABOVE_MARKS else None
			if not lower:
				continue
			current = self.marks_upper.get(mark_cp)
			upper = current.bounds() if current is not None else None
			if (
				upper
				and upper[3] - upper[1] >= 0.6 * (lower[3] - lower[1])
				and upper[1] - upper_ref[3] >= 0.015 * UNITS_PER_EM
			):
				continue
			flatten = 1.0 if mark_cp in UNFLATTENED_MARKS else 0.8
			shape = scale_about(mark, 1.0, flatten, 0.0, lower[1])
			self.marks_upper[mark_cp] = shifted(shape, 0.0, upper_ref[3] + gap - lower[1])
			repaired += 1
		if repaired:
			self.report["marks_repaired"] = repaired

	def extend_marks(self, metrics: FaceMetrics) -> None:
		"""Marks the Latin-1 letters cannot give, so accented letters stay on
		the face's own base letters instead of coming whole from the donor.

		The comma below, the dot below and the turned comma are the face's own
		comma and dot. The breve and the ogonek appear on no Latin-1 letter, so
		they come from the donor instance that already matches the face's stem
		weight; a mark is small, and the letter under it stays authentic.
		"""
		if not self.spec.extended:
			return
		comma = self.paths.get(glyph_name(ord(",")))
		comma_bounds = comma.bounds() if comma is not None else None
		depth = self._descender_depth(metrics)
		donor = self._donor(metrics)
		added = 0
		for target, reference in ((self.marks_upper, "A"), (self.marks_lower, "a")):
			ref = self.paths.get(glyph_name(ord(reference)))
			ref_bounds = ref.bounds() if ref is not None else None
			if ref_bounds is None:
				continue
			gap = self._mark_gap(target, ref_bounds)
			# Under the baseline a mark sits closer than an accent floats above.
			below_gap = min(gap, 0.05 * UNITS_PER_EM)
			dot = target.get(0x0307)
			if dot is not None and 0x0323 not in target:
				target[0x0323] = self._sit_below(dot, ref_bounds, below_gap)
				added += 1
			if comma is not None and comma_bounds:
				# Sized to end at the face's descender depth, as Noto's comma below
				# does. A fixed share of the comma sent ProFont's, which is half
				# an em tall, a quarter of an em past its descenders.
				height = comma_bounds[3] - comma_bounds[1]
				factor = min(0.8, max(0.3, (depth - below_gap) / max(height, 1.0)))
				small = scale_about(comma, factor, factor, 0.0, 0.0)
				if 0x0326 not in target:
					target[0x0326] = self._sit_below(small, ref_bounds, below_gap)
					added += 1
				if 0x0312 not in target:
					target[0x0312] = self._sit_above(rotate_half_turn(small), ref_bounds, gap)
					added += 1
			if donor is None:
				continue
			face, scale = donor
			for mark_cp in DONOR_MARKS:
				if mark_cp in target:
					continue
				result = face.outline(mark_cp)
				if result is None or not result[0].contours:
					continue
				mark = result[0].transformed(scale, scale)
				if mark_cp in BELOW_MARKS:
					# The ogonek is drawn to hook onto the baseline, so it keeps the
					# donor's own height; only its size follows the face.
					target[mark_cp] = mark
				else:
					target[mark_cp] = self._sit_above(mark, ref_bounds, gap)
				added += 1
		self.report["marks_extended"] = added

	def _descender_depth(self, metrics: FaceMetrics) -> float:
		"""How far the face's descenders reach below the baseline.

		An all-caps face draws its lowercase as small capitals with nothing
		below the line, so its cedilla stands in, then the line metrics.
		"""
		for character in "pgq":
			bounds = self._bounds_of(character)
			if bounds and -bounds[1] >= 0.1 * UNITS_PER_EM:
				return -bounds[1]
		cedilla = self.marks_lower.get(0x0327)
		bounds = cedilla.bounds() if cedilla is not None else None
		if bounds and -bounds[1] >= 0.1 * UNITS_PER_EM:
			return -bounds[1]
		return float(metrics.descender)

	def _mark_gap(self, marks: dict[int, Path2D], ref_bounds: tuple[float, float, float, float]) -> float:
		"""How far the face's own acute floats above its letter."""
		acute = marks.get(0x0301)
		bounds = acute.bounds() if acute is not None else None
		gap = bounds[1] - ref_bounds[3] if bounds else 0.05 * UNITS_PER_EM
		return min(max(gap, 0.02 * UNITS_PER_EM), 0.12 * UNITS_PER_EM)

	@staticmethod
	def _sit_above(mark: Path2D, ref_bounds: tuple[float, float, float, float], gap: float) -> Path2D:
		bounds = mark.bounds()
		return shifted(mark, 0.0, ref_bounds[3] + gap - bounds[1]) if bounds else mark

	@staticmethod
	def _sit_below(mark: Path2D, ref_bounds: tuple[float, float, float, float], gap: float) -> Path2D:
		bounds = mark.bounds()
		return shifted(mark, 0.0, ref_bounds[1] - gap - bounds[3]) if bounds else mark

	def _donor(self, metrics: FaceMetrics, small_caps: bool = False):
		"""The NotoSans instance matched to this face, and its scale to the face.

		``small_caps`` matches it to the lowercase letters of an all-caps face
		instead: those are small capitals, so an uppercase donor letter scaled
		to their height is the right shape, and the instance is chosen so its
		stems land at the small capitals' weight after that scaling.
		"""
		cache = getattr(self, "_donor_cache", None)
		if cache is None:
			cache = self._donor_cache = {}
		if small_caps in cache:
			return cache[small_caps]
		path = self.donor_dir / "NotoSans-var.ttf"
		result = None
		if path.exists():
			height = float(metrics.cap_height)
			stem = metrics.stem
			advance = metrics.average_advance
			if small_caps:
				height = float(metrics.small_height) or height
				stem = self._stem_of("l") or self._stem_of("i") or stem * height / max(metrics.cap_height, 1)
				widths = [self.advances[glyph_name(ord(c))] for c in "abcdefghijklmnopqrstuvwxyz"
				          if glyph_name(ord(c)) in self.advances]
				advance = sum(widths) / len(widths) if widths else advance * height / max(metrics.cap_height, 1)
			weight, width = solve_instance(stem / max(height, 1.0), advance / max(height, 1.0), path)
			face = get_face(path, weight, width)
			donor_cap = face.metrics.cap_height or 0.7 * face.upm
			result = (face, height / donor_cap)
			self.report["instance_NotoSans" + ("_smallcaps" if small_caps else "")] = f"{weight:.0f}/{width:.0f}"
		cache[small_caps] = result
		return result

	def _place_mark(self, base_name: str, mark_cp: int, uppercase: bool) -> tuple[Path2D, float, float] | None:
		marks = self.marks_upper if uppercase else self.marks_lower
		mark = marks.get(mark_cp)
		reference = self.paths.get(glyph_name(ord("A" if uppercase else "a")))
		base = self.paths.get(base_name)
		if mark is None or reference is None or base is None:
			return None
		mark_bounds = mark.bounds()
		base_bounds = base.bounds()
		reference_bounds = reference.bounds()
		if not (mark_bounds and base_bounds and reference_bounds):
			return None

		dx = 0.5 * (base_bounds[0] + base_bounds[2]) - 0.5 * (mark_bounds[0] + mark_bounds[2])
		if mark_cp == 0x0328 and base_name not in (glyph_name(c) for c in (0x49, 0x69, 0x131, 0x4F, 0x6F)):
			# An ogonek hooks onto the right foot of a, e and u (and their
			# capitals); only i and o carry it centred.
			dx = base_bounds[2] - 0.06 * (base_bounds[2] - base_bounds[0]) - mark_bounds[2]
		if mark_cp in BELOW_MARKS:
			dy = base_bounds[1] - reference_bounds[1]
		else:
			# Riding the base's own top means marks clear ascenders automatically.
			dy = base_bounds[3] - reference_bounds[3]
		return mark, dx, dy

	def _fit_marks_to_cell(
		self, base_bounds: tuple[float, float, float, float], placements: list[tuple[int, Path2D]]
	) -> list[tuple[int, Path2D]]:
		"""Press a composite's accents into the console cell.

		Only two of a cell's sixteen pixel rows lie above a capital and two
		below the baseline, and the console clips at the cell edge. The
		accents on each side are compressed towards the letter, clearance and
		mark together, until they clear that edge.
		"""
		top_limit = self.cell_top - CELL_MARGIN
		bottom_limit = self.cell_bottom + CELL_MARGIN
		above = [mark.bounds()[3] for mark_cp, mark in placements if mark_cp not in BELOW_MARKS]
		below = [mark.bounds()[1] for mark_cp, mark in placements if mark_cp in BELOW_MARKS]
		above_factor = below_factor = 1.0
		if above and max(above) > top_limit and max(above) > base_bounds[3]:
			above_factor = max(0.2, (top_limit - base_bounds[3]) / (max(above) - base_bounds[3]))
		if below and min(below) < bottom_limit and min(below) < base_bounds[1]:
			below_factor = max(0.2, (base_bounds[1] - bottom_limit) / (base_bounds[1] - min(below)))
		fitted = []
		for mark_cp, mark in placements:
			if mark_cp in BELOW_MARKS:
				mark = scale_about(mark, 1.0, below_factor, 0.0, base_bounds[1])
			else:
				mark = scale_about(mark, 1.0, above_factor, 0.0, base_bounds[3])
			fitted.append((mark_cp, mark))
		return fitted

	def _apostrophe_caron(self, codepoint: int, base_name: str) -> bool:
		"""d', t', l' and L': the caron becomes an apostrophe after the stem.

		Riding the ascender like an ordinary caron is the classic defect here -
		Czech and Slovak readers see a wrong letter - so the face's own comma is
		set beside the stem top instead, the way their typography writes it.
		"""
		comma = self.paths.get(glyph_name(ord(",")))
		base = self.paths.get(base_name)
		comma_bounds = comma.bounds() if comma is not None else None
		if not comma_bounds or base is None:
			return False
		base_bounds = base.bounds()
		# At most four tenths of a capital tall: ProFont's comma is half an em.
		cap = self._bounds_of("H")
		limit = 0.4 * cap[3] if cap else 0.3 * UNITS_PER_EM
		factor = min(0.85, limit / max(comma_bounds[3] - comma_bounds[1], 1.0))
		mark = scale_about(comma, factor, factor, 0.0, 0.0)
		mark_bounds = mark.bounds()
		if not (base_bounds and mark_bounds):
			return False
		gap = 0.04 * UNITS_PER_EM
		if codepoint == 0x013D:
			# Capital L: beside its stem, inside the space over the arm.
			stem = self._stem_of("L") or self._stem_of("l") or 0.1 * UNITS_PER_EM
			left = base_bounds[0] + stem + gap
		else:
			left = base_bounds[2] + gap
		placed = shifted(mark, left - mark_bounds[0], base_bounds[3] - mark_bounds[3])
		advance = self.advances.get(base_name, 0)
		right_side = advance - base_bounds[2]
		placed_bounds = placed.bounds()
		if placed_bounds is not None:
			advance = max(advance, int(round(placed_bounds[2] + right_side)))
		combined = Path2D(list(base.contours) + list(placed.contours))
		self._add(glyph_name(codepoint), codepoint, combined, advance)
		return True

	# -- stage 4: composites ------------------------------------------------

	def compose(self, codepoints: list[int]) -> set[int]:
		"""Build precomposed letters out of traced bases and extracted marks."""
		built: set[int] = set()
		for codepoint in codepoints:
			if codepoint in self.cmap:
				continue
			parts = _canonical_parts(codepoint)
			if not parts:
				continue
			base_cp, marks = parts[0], parts[1:]
			if codepoint in COMMA_FOR_CEDILLA:
				marks = [0x0326 if m == 0x0327 else m for m in marks]
			elif codepoint in TURNED_COMMA_ABOVE:
				marks = [0x0312 if m == 0x0327 else m for m in marks]
			base_name = self.cmap.get(base_cp)
			if base_name is None or not marks:
				continue
			if codepoint in APOSTROPHE_CARON:
				if self._apostrophe_caron(codepoint, base_name):
					built.add(codepoint)
				continue
			if not all(m in ABOVE_MARKS or m in BELOW_MARKS for m in marks):
				continue
			dotless = DOTTED_BASES.get(base_cp)
			if dotless is not None and any(m in ABOVE_MARKS for m in marks) and dotless in self.cmap:
				base_name = self.cmap[dotless]

			uppercase = unicodedata.category(chr(base_cp)) == "Lu"
			base = self.paths[base_name]
			base_bounds = base.bounds()
			placements: list[tuple[int, Path2D]] = []
			above_top: float | None = None
			below_bottom: float | None = None
			for mark_cp in marks:
				placed = self._place_mark(base_name, mark_cp, uppercase)
				if placed is None:
					break
				mark, dx, dy = placed
				mark = mark.transformed(1.0, 1.0, dx, dy)
				bounds = mark.bounds()
				if bounds is None:
					break
				# A second accent on the same side stacks on the first instead of
				# landing on it (Pinyin u-diaeresis-acute, Livonian a-diaeresis-
				# macron), parted by half the clearance it keeps from a letter.
				if mark_cp in BELOW_MARKS:
					if below_bottom is not None:
						clearance = max(0.5 * (base_bounds[1] - bounds[3]), 0.015 * UNITS_PER_EM)
						mark = shifted(mark, 0.0, below_bottom - clearance - bounds[3])
					below_bottom = mark.bounds()[1]
				else:
					if above_top is not None:
						clearance = max(0.5 * (bounds[1] - base_bounds[3]), 0.015 * UNITS_PER_EM)
						mark = shifted(mark, 0.0, above_top + clearance - bounds[1])
					above_top = mark.bounds()[3]
				placements.append((mark_cp, mark))
			if len(placements) != len(marks):
				continue
			if self.cell_top is not None:
				placements = self._fit_marks_to_cell(base_bounds, placements)

			name = glyph_name(codepoint)
			combined = Path2D(list(base.contours))
			for _, mark in placements:
				combined.contours.extend(mark.contours)
			self._add(name, codepoint, combined, self.advances.get(base_name, 0))
			built.add(codepoint)
		self.report["composed"] = self.report.get("composed", 0) + len(built)
		return built

	# -- stage 4b: letters built from the face's own letters ----------------

	def _stem_span(self, path: Path2D, y: float, which: str) -> tuple[float, float] | None:
		"""The leftmost or rightmost ink span a horizontal line crosses."""
		hits = scanline(path, y)
		spans = [(hits[i], hits[i + 1]) for i in range(0, len(hits) - 1, 2)]
		if not spans:
			return None
		return spans[0] if which == "left" else spans[-1]

	def synthesize_letters(self, metrics: FaceMetrics) -> None:
		"""Letters that are a face letter plus a stroke, or a face letter minus
		its dot, built here so they keep the face's drawing rather than coming
		whole from the donor: Turkish dotless i, Polish L-stroke, Croatian
		d-stroke, and the rest of Latin Extended-A's stroked letters."""
		if not self.spec.extended:
			return
		count = 0
		stroke = max(metrics.bar * 0.8, 0.035 * UNITS_PER_EM)

		def put(codepoint: int, path: Path2D | None, advance: float) -> None:
			nonlocal count
			if codepoint in self.cmap or path is None or not path.contours:
				return
			self._add(glyph_name(codepoint), codepoint, path, int(round(advance)))
			count += 1

		def source(character: str) -> tuple[str, Path2D, tuple[float, float, float, float]] | None:
			name = self.cmap.get(ord(character))
			path = self.paths.get(name) if name else None
			bounds = path.bounds() if path is not None else None
			return (name, path, bounds) if bounds else None

		# Dotless i and j: the letter without its dot. An all-caps face's i is a
		# small capital with no dot to remove, so it is shared as it stands.
		for codepoint, character in ((0x0131, "i"), (0x0237, "j")):
			found = source(character)
			if found is None:
				continue
			name, path, _ = found
			dotless = drop_contours_above(path, metrics.small_height + 0.02 * UNITS_PER_EM)
			if dotless.contours and len(dotless.contours) < len(path.contours):
				put(codepoint, dotless, self.advances[name])
			elif self.spec.all_caps and codepoint not in self.cmap:
				self.cmap[codepoint] = name
				count += 1

		# Slashed L and l: a stroke rising left to right through the stem.
		for codepoint, character, height in ((0x0141, "L", 0.45), (0x0142, "l", 0.5)):
			found = source(character)
			if found is None:
				continue
			name, path, bounds = found
			cy = bounds[1] + height * (bounds[3] - bounds[1])
			span = self._stem_span(path, cy, "left")
			if span is None:
				continue
			cx = 0.5 * (span[0] + span[1])
			reach = 1.25 * max(span[1] - span[0], metrics.stem)
			rise = 0.55 * reach
			half = 0.5 * stroke
			slash = quad([(cx - reach, cy - rise - half), (cx + reach, cy + rise - half),
			              (cx + reach, cy + rise + half), (cx - reach, cy - rise + half)])
			put(codepoint, Path2D(list(path.contours) + [slash]), self.advances[name])

		# Eth-like D-stroke: the face's own Eth where it has one.
		if 0x0110 not in self.cmap and 0x00D0 in self.cmap:
			self.cmap[0x0110] = self.cmap[0x00D0]
			count += 1
		if self.spec.all_caps and 0x0111 not in self.cmap and 0x00F0 in self.cmap:
			# An all-caps face's eth is a small-capital D-stroke already.
			self.cmap[0x0111] = self.cmap[0x00F0]
			count += 1

		# Bars across an ascender stem: d-stroke, h-bar, and the T/t bars.
		def barred(codepoint: int, character: str, level: float, which: str, left: float, right: float) -> None:
			found = source(character)
			if found is None:
				return
			name, path, bounds = found
			cy = bounds[1] + level * (bounds[3] - bounds[1])
			span = self._stem_span(path, cy, which)
			if span is None:
				return
			width = max(span[1] - span[0], 1.0)
			bar = box(span[0] - left * width, cy - 0.5 * stroke, span[1] + right * width, cy + 0.5 * stroke)
			put(codepoint, Path2D(list(path.contours) + [bar]), self.advances[name])

		barred(0x0111, "d", 0.82, "right", 1.0, 0.45)
		barred(0x0127, "h", 0.82, "left", 0.45, 1.0)
		barred(0x0166, "T", 0.45, "left", 1.1, 1.1)
		barred(0x0167, "t", 0.35, "left", 0.9, 0.9)
		found = source("H")
		if found is not None and 0x0126 not in self.cmap:
			name, path, bounds = found
			cy = bounds[1] + 0.78 * (bounds[3] - bounds[1])
			overhang = 0.25 * metrics.stem
			bar = box(bounds[0] - overhang, cy - 0.5 * stroke, bounds[2] + overhang, cy + 0.5 * stroke)
			put(0x0126, Path2D(list(path.contours) + [bar]), self.advances[name])

		# IJ and ij: the two letters side by side.
		for codepoint, first, second in ((0x0132, "I", "J"), (0x0133, "i", "j")):
			a, b = source(first), source(second)
			if a is None or b is None:
				continue
			shift = self.advances[a[0]]
			put(codepoint, Path2D(list(a[1].contours) + list(shifted(b[1], shift, 0.0).contours)),
			    shift + self.advances[b[0]])

		# n preceded by apostrophe, and the Catalan middle-dot L.
		comma = source(",")
		n = source("n")
		if comma is not None and n is not None:
			mark = scale_about(comma[1], 0.85, 0.85, 0.0, 0.0)
			mark_bounds = mark.bounds()
			side = self._sidebearing()
			mark = shifted(mark, side - mark_bounds[0], metrics.cap_height - mark_bounds[3])
			lead = mark.bounds()[2] + 0.5 * side
			put(0x0149, Path2D(list(mark.contours) + list(shifted(n[1], lead, 0.0).contours)),
			    lead + self.advances[n[0]])
		dot = source("·")
		for codepoint, character in ((0x013F, "L"), (0x0140, "l")):
			found = source(character)
			if found is None or dot is None:
				continue
			name, path, bounds = found
			dot_bounds = dot[2]
			span = self._stem_span(path, bounds[1] + 0.5 * (bounds[3] - bounds[1]), "left")
			if span is None:
				continue
			gap = 0.6 * (dot_bounds[2] - dot_bounds[0])
			placed = shifted(dot[1], span[1] + gap - dot_bounds[0], 0.0)
			advance = self.advances[name]
			if codepoint == 0x0140:
				advance = max(advance, placed.bounds()[2] + self._sidebearing())
			put(codepoint, Path2D(list(path.contours) + list(placed.contours)), advance)

		self.report["letters"] = count

	def _sidebearing(self) -> float:
		"""The face's usual side bearing, from its o."""
		name = self.cmap.get(ord("o"))
		path = self.paths.get(name) if name else None
		bounds = path.bounds() if path is not None else None
		if not bounds:
			return 0.06 * UNITS_PER_EM
		return max(0.02 * UNITS_PER_EM, 0.5 * (bounds[0] + self.advances[name] - bounds[2]))

	# -- stage 5: shared shapes and donors ----------------------------------

	def alias_homoglyphs(self) -> None:
		count = 0
		for table in (CYRILLIC_HOMOGLYPHS, GREEK_HOMOGLYPHS):
			for codepoint, latin in table.items():
				if codepoint in self.cmap:
					continue
				name = latin if latin in self.glyphs else glyph_name(ord(latin)) if len(latin) == 1 else None
				if name and name in self.glyphs:
					self.cmap[codepoint] = name
					count += 1

		for codepoint, (source, operation) in DERIVED_FROM_LATIN.items():
			if codepoint in self.cmap:
				continue
			name = source if source in self.glyphs else (glyph_name(ord(source)) if len(source) == 1 else None)
			if not name or name not in self.paths:
				continue
			advance = self.advances.get(name, 0)
			path = flip_horizontal(self.paths[name], advance) if operation == "flip_x" else self.paths[name]
			self._add(glyph_name(codepoint), codepoint, path, advance)
			count += 1
		self.report["homoglyphs"] = count

	def synthesize_latin1(self, metrics: FaceMetrics) -> None:
		"""Fill the Latin-1 and Windows-1252 slots the retail art left blank,
		and rebuild the ones it drew wrong, out of the face's own parts.

		The retail atlases leave a run of Latin-1 symbols blank in every face -
		ordinal indicators, superscripts, fractions, plus-minus and the spacing
		accents among them - and the donor only covers the blocks above
		Latin-1, so those characters were simply missing: a Portuguese "1º" or
		a French "n°" table entry drew a question mark. They are all a face
		glyph rescaled or combined with a mark the face already has, so they
		are built here in its own style.
		"""
		if not self.spec.extended:
			return
		cap = float(metrics.cap_height)
		count = 0
		side = self._sidebearing()

		def get(character: str) -> tuple[str, Path2D, tuple[float, float, float, float]] | None:
			name = self.cmap.get(ord(character))
			path = self.paths.get(name) if name else None
			bounds = path.bounds() if path is not None else None
			return (name, path, bounds) if bounds else None

		def put(codepoint: int, path: Path2D | None, advance: float | None = None) -> None:
			"""Add a glyph, spaced with the face's side bearings unless given."""
			nonlocal count
			if codepoint in self.cmap or path is None or not path.contours:
				return
			bounds = path.bounds()
			if advance is None:
				path = shifted(path, side - bounds[0], 0.0)
				advance = (bounds[2] - bounds[0]) + 2.0 * side
			self._add(glyph_name(codepoint), codepoint, path, int(round(advance)))
			count += 1

		def blank(codepoint: int, advance: float) -> None:
			nonlocal count
			if codepoint not in self.cmap:
				self._add(glyph_name(codepoint), codepoint, None, int(round(advance)))
				count += 1

		space = self.cmap.get(0x20)
		if space is not None:
			blank(0x00A0, self.advances.get(space, UNITS_PER_EM // 4))
		hyphen = get("-")
		if hyphen is not None:
			put(0x00AD, hyphen[1], self.advances[hyphen[0]])

		# Exclamation mark: the face's full stop under a stem of the same width.
		period = get(".")
		if period is not None and 0x21 not in self.cmap:
			_, path, bounds = period
			width = bounds[2] - bounds[0]
			height = bounds[3] - bounds[1]
			stem = box(bounds[0], bounds[3] + 0.75 * height, bounds[2], cap)
			if width > 0 and cap > bounds[3] + 1.5 * height:
				put(0x21, Path2D(list(path.contours) + [stem]))

		# Spacing accents are the face's own marks at their natural height.
		for codepoint, mark_cp in ((0x00A8, 0x0308), (0x00AF, 0x0304), (0x00B4, 0x0301), (0x00B8, 0x0327),
		                           (0x02C6, 0x0302), (0x02DC, 0x0303), (0x02C7, 0x030C), (0x02D8, 0x0306),
		                           (0x02D9, 0x0307), (0x02DA, 0x030A), (0x02DB, 0x0328), (0x02DD, 0x030B)):
			put(codepoint, self.marks_lower.get(mark_cp))

		# Superscript digits and the vulgar fractions, from the face's digits.
		def raised(character: str, factor: float) -> Path2D | None:
			found = get(character)
			return scale_about(found[1], factor, factor, 0.0, cap) if found else None

		def lowered(character: str, factor: float) -> Path2D | None:
			found = get(character)
			return scale_about(found[1], factor, factor, 0.0, 0.0) if found else None

		for codepoint, digit in ((0x00B9, "1"), (0x00B2, "2"), (0x00B3, "3")):
			put(codepoint, raised(digit, 0.62))
		slash = get("/")
		for codepoint, top, bottom in ((0x00BC, "1", "4"), (0x00BD, "1", "2"), (0x00BE, "3", "4")):
			numerator, denominator = raised(top, 0.5), lowered(bottom, 0.5)
			if numerator is None or denominator is None or slash is None:
				continue
			nb, db = numerator.bounds(), denominator.bounds()
			fraction = scale_about(slash[1], 0.85, 0.85, 0.5 * (slash[2][0] + slash[2][2]), 0.5 * cap)
			fb = fraction.bounds()
			numerator = shifted(numerator, -nb[0], 0.0)
			x = (nb[2] - nb[0]) - 0.2 * (fb[2] - fb[0])
			fraction = shifted(fraction, x - fb[0], 0.5 * cap - 0.5 * (fb[1] + fb[3]))
			x = fraction.bounds()[2] - 0.2 * (fb[2] - fb[0])
			denominator = shifted(denominator, x - db[0], 0.0)
			put(codepoint, Path2D(list(numerator.contours) + list(fraction.contours) + list(denominator.contours)))

		# Ordinal indicators: a raised small a or o over a rule, as Spanish and
		# Portuguese write them.
		for codepoint, letter in ((0x00AA, "a"), (0x00BA, "o")):
			small = raised(letter, 0.62)
			if small is None:
				continue
			sb = small.bounds()
			thickness = max(0.6 * metrics.bar, 0.03 * UNITS_PER_EM)
			rule_top = sb[1] - 0.06 * cap
			rule = box(sb[0], rule_top - thickness, sb[2], rule_top)
			put(codepoint, Path2D(list(small.contours) + [rule]))

		# Plus-minus, not sign, broken bar and cent, from the plus, bar and c.
		plus = get("+")
		if plus is not None:
			_, path, pb = plus
			hits = _vertical_scanline(path, pb[0] + 0.08 * (pb[2] - pb[0]))
			thickness = (hits[1] - hits[0]) if len(hits) >= 2 else max(metrics.bar, 0.04 * UNITS_PER_EM)
			centre = 0.5 * (hits[0] + hits[1]) if len(hits) >= 2 else 0.5 * (pb[1] + pb[3])
			gap = 0.8 * thickness
			lift = 0.5 * (thickness + gap)
			lifted = shifted(path, 0.0, lift)
			bar_top = pb[1] + lift - gap
			put(0x00B1, Path2D(list(lifted.contours) + [box(pb[0], bar_top - thickness, pb[2], bar_top)]),
			    self.advances[plus[0]])
			arm = box(pb[0], centre - 0.5 * thickness, pb[2], centre + 0.5 * thickness)
			drop = box(pb[2] - thickness, centre - 0.33 * (pb[2] - pb[0]), pb[2], centre + 0.5 * thickness)
			put(0x00AC, Path2D([arm, drop]), self.advances[plus[0]])
		bar = get("|")
		if bar is not None:
			_, path, bb = bar
			middle = 0.5 * (bb[1] + bb[3])
			gap = 0.06 * (bb[3] - bb[1]) + 0.5 * metrics.bar
			put(0x00A6, Path2D([box(bb[0], bb[1], bb[2], middle - gap), box(bb[0], middle + gap, bb[2], bb[3])]),
			    self.advances[bar[0]])
		c = get("c")
		if c is not None:
			_, path, cb = c
			thickness = max(0.75 * metrics.bar, 0.035 * UNITS_PER_EM)
			cx = 0.5 * (cb[0] + cb[2])
			reach = 0.16 * (cb[3] - cb[1])
			stroke = box(cx - 0.5 * thickness, cb[1] - reach, cx + 0.5 * thickness, cb[3] + reach)
			put(0x00A2, Path2D(list(path.contours) + [stroke]), self.advances[c[0]])

		# Rebuilt retail glyphs. A bullet: the face's middle dot, enlarged to
		# Noto's proportion of 0.31 cap heights. Chain and Marine already draw a
		# bullet-sized middle dot, so theirs is used as it stands.
		middle_dot = get("·")
		if middle_dot is not None:
			_, path, db = middle_dot
			factor = max(1.0, 0.31 * cap / max(db[2] - db[0], 1.0))
			put(0x2022, scale_about(path, factor, factor, 0.5 * (db[0] + db[2]), 0.5 * (db[1] + db[3])))

		ring_thickness = max(0.6 * metrics.stem, 0.04 * UNITS_PER_EM)
		for codepoint, letter in ((0x00A9, "C"), (0x00AE, "R")):
			found = get(letter)
			if found is None or codepoint in self.cmap:
				continue
			radius = 0.52 * cap
			ring = _ring(radius, 0.5 * cap, radius, ring_thickness)
			_, path, lb = found
			inner = scale_about(path, 0.5, 0.5, 0.5 * (lb[0] + lb[2]), 0.5 * (lb[1] + lb[3]))
			ib = inner.bounds()
			inner = shifted(inner, radius - 0.5 * (ib[0] + ib[2]), 0.5 * cap - 0.5 * (ib[1] + ib[3]))
			put(codepoint, Path2D(list(ring.contours) + list(inner.contours)))
		zero, solidus = get("o"), get("/")
		if zero is not None and solidus is not None and 0x25 not in self.cmap:
			upper = scale_about(zero[1], 0.55, 0.55, zero[2][0], 0.0)
			ub = upper.bounds()
			upper = shifted(upper, 0.0, cap - ub[3])
			slant = scale_about(solidus[1], 1.0, cap / max(solidus[2][3] - solidus[2][1], 1.0),
			                    0.5 * (solidus[2][0] + solidus[2][2]), solidus[2][1])
			sb = slant.bounds()
			slant = shifted(slant, ub[2] - 0.3 * (sb[2] - sb[0]) - sb[0], -sb[1])
			lower = scale_about(zero[1], 0.55, 0.55, zero[2][0], 0.0)
			lb = lower.bounds()
			lower = shifted(lower, slant.bounds()[2] - 0.3 * (sb[2] - sb[0]) - lb[0], -lb[1])
			put(0x25, Path2D(list(upper.contours) + list(slant.contours) + list(lower.contours)))

		# Sharp s in an all-caps face: its lowercase slots are small capitals, and
		# a small-capital sharp s is written SS - the retail art drew a B.
		if self.spec.all_caps and 0x00DF not in self.cmap:
			found = get("s")
			if found is not None:
				name, path, _ = found
				advance = self.advances[name]
				put(0x00DF, Path2D(list(path.contours) + list(shifted(path, advance, 0.0).contours)), 2 * advance)

		self.report["latin1"] = count

	def synthesize_shapes(self, metrics: FaceMetrics) -> None:
		"""Draw the geometric and arrow symbols the Noto donor does not carry.

		Noto Sans ships almost nothing from the arrows, geometric-shape and
		misc-symbol blocks, yet those are exactly the characters a HUD reaches
		for.  They are pure geometry, so they are constructed here at the
		face's own weight rather than pulled from a fourth donor.
		"""
		if not self.spec.extended:
			return

		cap = float(metrics.cap_height)
		mid = 0.5 * (cap - metrics.stem)  # vertical centre of a symbol band
		size = 0.62 * cap
		low = mid - 0.5 * size
		high = mid + 0.5 * size
		left = 0.16 * cap
		right = left + size
		centre_x = 0.5 * (left + right)
		advance = int(round(size + 2.0 * left))
		count = 0

		def emit(codepoint: int, path: Path2D) -> None:
			nonlocal count
			if codepoint in self.cmap or not path.contours:
				return
			self._add(glyph_name(codepoint), codepoint, path, advance)
			count += 1

		def polygon(points: list[tuple[float, float]]) -> Path2D:
			contour = Contour(points[0])
			for point in points[1:]:
				contour.line_to(point)
			return Path2D([contour])

		def ellipse(cx: float, cy: float, rx: float, ry: float, reverse: bool = False) -> Contour:
			# Four quadratic arcs; the control offset is the standard circular
			# approximation for a quadratic quarter-arc.
			k = 0.5523
			contour = Contour((cx + rx, cy))
			contour.quad_to((cx + rx, cy + ry * k * 1.2), (cx, cy + ry))
			contour.quad_to((cx - rx * k * 1.2, cy + ry), (cx - rx, cy))
			contour.quad_to((cx - rx, cy - ry * k * 1.2), (cx, cy - ry))
			contour.quad_to((cx + rx * k * 1.2, cy - ry), (cx + rx, cy))
			return contour.reverse() if reverse else contour

		def ring(cx: float, cy: float, radius: float) -> Path2D:
			inner = radius - max(metrics.stem * 0.7, 0.03 * cap)
			shape = Path2D([ellipse(cx, cy, radius, radius)])
			if inner > 0.1 * radius:
				shape.contours.append(ellipse(cx, cy, inner, inner, reverse=True))
			return shape

		def frame(points: list[tuple[float, float]], inset: float) -> Path2D:
			outer = polygon(points)
			cx = sum(p[0] for p in points) / len(points)
			cy = sum(p[1] for p in points) / len(points)
			scale = 1.0 - inset
			shrunk = [(cx + (x - cx) * scale, cy + (y - cy) * scale) for x, y in points]
			inner = Contour(shrunk[0])
			for point in shrunk[1:]:
				inner.line_to(point)
			outer.contours.append(inner.reverse())
			return outer

		square = [(left, low), (right, low), (right, high), (left, high)]
		up = [(centre_x, high), (right, low), (left, low)]
		down = [(centre_x, low), (left, high), (right, high)]
		lefty = [(left, mid), (right, high), (right, low)]
		righty = [(right, mid), (left, low), (left, high)]

		emit(0x25A0, polygon(square))                       # black square
		emit(0x25A1, frame(square, 0.32))                   # white square
		emit(0x25AA, polygon(_scaled(square, 0.65)))        # small black square
		emit(0x25B2, polygon(up))
		emit(0x25B3, frame(up, 0.42))
		emit(0x25BC, polygon(down))
		emit(0x25BD, frame(down, 0.42))
		emit(0x25C0, polygon(lefty))
		emit(0x25C1, frame(lefty, 0.42))
		emit(0x25B6, polygon(righty))
		emit(0x25B7, frame(righty, 0.42))
		emit(0x25CF, Path2D([ellipse(centre_x, mid, 0.5 * size, 0.5 * size)]))
		emit(0x25CB, ring(centre_x, mid, 0.5 * size))
		emit(0x2022, Path2D([ellipse(centre_x, mid, 0.22 * size, 0.22 * size)]))
		emit(0x2605, polygon(_star(centre_x, mid, 0.55 * size, 0.24 * size)))
		emit(0x2606, frame(_star(centre_x, mid, 0.55 * size, 0.24 * size), 0.3))

		bar = max(metrics.stem * 0.85, 0.035 * cap)
		head = 0.34 * size
		for codepoint, direction in ((0x2190, "left"), (0x2192, "right"), (0x2191, "up"), (0x2193, "down")):
			emit(codepoint, _arrow(left, right, low, high, mid, centre_x, bar, head, direction))

		self.report["synthesized"] = count

	def import_donors(self, metrics: FaceMetrics) -> None:
		if not self.spec.extended:
			return

		ranges = unicode_ranges()
		targets: list[tuple[str, tuple[str, ...]]] = [
			("NotoSans-var.ttf", NOTO_SANS_BLOCKS),
			("NotoSansArabic-var.ttf", NOTO_ARABIC_BLOCKS),
			("NotoSansHebrew-var.ttf", NOTO_HEBREW_BLOCKS),
		]

		stem_ratio = metrics.stem / max(metrics.cap_height, 1)
		width_ratio = metrics.average_advance / max(metrics.cap_height, 1)
		imported = 0
		# An all-caps face draws its lowercase as small capitals. A donor
		# lowercase letter - a Cyrillic be with its ascender, a Latin eng -
		# would be the only true lowercase among them, so the donor's capital is
		# used instead, at the small capitals' height and weight.
		small_caps = self._donor(metrics, small_caps=True) if self.spec.all_caps else None

		for filename, blocks in targets:
			path = self.donor_dir / filename
			if not path.exists():
				continue
			codepoints = [cp for block in blocks for cp in range(ranges[block][0], ranges[block][1] + 1)]
			if filename == "NotoSans-var.ttf":
				face, scale = self._donor(metrics)
				# Whatever ASCII or Latin-1 the face could not draw or build from
				# its own parts comes last from here (the pilcrow, for one).
				codepoints = list(range(0x21, 0x7F)) + list(range(0xA1, 0x100)) + codepoints
			else:
				weight, width = solve_instance(stem_ratio, width_ratio, path)
				face = get_face(path, weight, width)
				self.report[f"instance_{filename.split('-')[0]}"] = f"{weight:.0f}/{width:.0f}"
				scale = metrics.cap_height / (face.metrics.cap_height or 0.7 * face.upm)

			for codepoint in codepoints:
				if codepoint in self.cmap:
					continue
				glyph_face, glyph_scale, source_cp = face, scale, codepoint
				if small_caps is not None and filename == "NotoSans-var.ttf" and unicodedata.category(chr(codepoint)) == "Ll":
					upper = chr(codepoint).upper()
					if len(upper) == 1 and small_caps[0].has(ord(upper)):
						glyph_face, glyph_scale = small_caps
						source_cp = ord(upper)
				if not glyph_face.has(source_cp):
					continue
				result = glyph_face.outline(source_cp)
				if result is None:
					continue
				outline, advance = result
				name = glyph_name(codepoint)
				if name in self.glyphs:
					self.cmap[codepoint] = name
					continue
				scaled = outline.transformed(glyph_scale, glyph_scale) if outline.contours else Path2D()
				self._add(name, codepoint, scaled if scaled.contours else None, int(round(advance * glyph_scale)))
				imported += 1

		self.report["donor"] = imported

	def fit_to_cell(self, metrics: FaceMetrics) -> None:
		"""Keep every glyph of a fixed-cell face inside the cell.

		Donor letters arrive with the donor's room for accents and tails - the
		breve of a Cyrillic short i, the legs of a de - which the console cell
		does not have, and the console clips at its edges. Whatever rises past
		the top is compressed towards the cap height, and whatever drops past
		the bottom towards the baseline.
		"""
		if self.cell_top is None or self.cell_bottom is None:
			return
		cap = float(metrics.cap_height)
		top_limit = self.cell_top - CELL_MARGIN
		bottom_limit = self.cell_bottom + CELL_MARGIN
		fitted = 0
		for entry in self.glyphs.values():
			if entry.path is None or entry.name in self.traced:
				continue
			bounds = entry.path.bounds()
			if bounds is None or (bounds[3] <= top_limit and bounds[1] >= bottom_limit):
				continue
			above = (top_limit - cap) / (bounds[3] - cap) if bounds[3] > top_limit else 1.0
			below = bottom_limit / bounds[1] if bounds[1] < bottom_limit else 1.0

			def squeeze(point: tuple[float, float], above: float = above, below: float = below) -> tuple[float, float]:
				x, y = point
				if y > cap:
					return (x, cap + (y - cap) * above)
				if y < 0.0:
					return (x, y * below)
				return point

			entry.path = entry.path.mapped(squeeze)
			self.paths[entry.name] = entry.path
			fitted += 1
		self.report["cell_fitted"] = fitted

	def force_monospace(self) -> None:
		"""Give every glyph the cell advance, for a fixed-cell source.

		The console and the loading screen step a fixed cell per character and
		ignore font advances entirely, so a proportional advance would be
		fiction.  It matters for the imported scripts, which arrive carrying the
		donor's proportional metrics.
		"""
		if self.spec.grid_atlas is None:
			return
		cell = int(round(self.source.point_size * self.scale))
		margin = 0.08 * cell
		condensed = 0
		for entry in self.glyphs.values():
			if entry.name == ".notdef":
				continue
			entry.advance = cell
			if entry.name in self.traced or entry.path is None:
				continue
			# The retail cells were drawn centred; a built or donor glyph arrives
			# on its own proportional side bearings, so centre it in the cell -
			# and condense it if it is wider than the cell, or a W-wide letter
			# would spill into its neighbours in a console line.
			bounds = entry.path.bounds()
			if bounds is None:
				continue
			width = bounds[2] - bounds[0]
			room = cell - 2.0 * margin
			path = entry.path
			if width > room:
				path = scale_about(path, room / width, 1.0, bounds[0], 0.0)
				width = room
				condensed += 1
			path = shifted(path, 0.5 * (cell - width) - path.bounds()[0], 0.0)
			entry.path = path
			self.paths[entry.name] = path
		for name in self.advances:
			self.advances[name] = cell
		self.report["monospaced"] = cell
		self.report["condensed"] = condensed

	def fold_to_base(self) -> None:
		"""For faces with no extended coverage, point accents at their base rune."""
		if self.spec.extended:
			return
		count = 0
		for codepoint in range(0x00C0, 0x2000):
			if codepoint in self.cmap:
				continue
			parts = _canonical_parts(codepoint)
			if not parts:
				continue
			base = self.cmap.get(parts[0])
			if base:
				self.cmap[codepoint] = base
				count += 1
		self.report["folded"] = count

	# -- stage 6: emit ------------------------------------------------------

	def emit(self, destination: FilePath, metrics: FaceMetrics, version: str) -> None:
		order = [".notdef"] + sorted(name for name in self.glyphs if name != ".notdef")
		builder = FontBuilder(UNITS_PER_EM, isTTF=True)
		builder.setupGlyphOrder(order)
		builder.setupCharacterMap(self.cmap)

		pen_glyphs = {}
		hmtx = {}
		for name in order:
			entry = self.glyphs[name]
			pen = TTGlyphPen(None)
			if entry.path is not None:
				entry.path.draw(pen)
			glyph = pen.glyph()
			pen_glyphs[name] = glyph
			left = 0
			bounds = entry.path.bounds() if entry.path else None
			if bounds:
				left = int(round(bounds[0]))
			hmtx[name] = (max(0, entry.advance), left)

		builder.setupGlyf(pen_glyphs)
		builder.setupHorizontalMetrics(hmtx)
		builder.setupHorizontalHeader(ascent=metrics.ascender, descent=-metrics.descender, lineGap=0)

		full = f"{self.spec.family} {self.spec.style}"
		builder.setupNameTable({
			"familyName": self.spec.family,
			"styleName": self.spec.style,
			"uniqueFontIdentifier": f"DarkMatter Productions: {full}: {self.spec.project_name} {version}",
			"fullName": full,
			"version": f"Version {version}",
			"psName": f"{self.spec.family.replace(' ', '')}-{self.spec.style}",
			"designer": "DarkMatter Productions",
			"description": self.spec.description,
			"manufacturer": "DarkMatter Productions",
			"licenseDescription": (
				f"Latin outlines are traced from {self.spec.bitmap_attribution}. "
				"Glyphs for scripts outside that source are "
				"derived from the Noto fonts, (c) Google, licensed under the SIL Open Font License 1.1."
			),
		})
		builder.setupOS2(
			sTypoAscender=metrics.ascender,
			sTypoDescender=-metrics.descender,
			sTypoLineGap=0,
			usWinAscent=metrics.ascender,
			usWinDescent=metrics.descender,
			sCapHeight=metrics.cap_height,
			sxHeight=metrics.x_height,
			achVendID=VENDOR_ID,
			fsType=0,
		)
		builder.setupPost()
		builder.font["head"].created = DETERMINISTIC_TTF_TIMESTAMP
		builder.font["head"].modified = DETERMINISTIC_TTF_TIMESTAMP
		builder.font.recalcTimestamp = False
		destination.parent.mkdir(parents=True, exist_ok=True)
		builder.save(str(destination))


def _circle(cx: float, cy: float, radius: float) -> Contour:
	"""A circle from eight quadratic arcs (error under 0.03% of the radius)."""
	step = math.pi / 4.0
	reach = radius / math.cos(step / 2.0)
	contour = Contour((cx + radius, cy))
	for index in range(8):
		middle = (index + 0.5) * step
		end = (index + 1) * step
		contour.quad_to((cx + reach * math.cos(middle), cy + reach * math.sin(middle)),
		                (cx + radius * math.cos(end), cy + radius * math.sin(end)))
	return contour


def _ring(cx: float, cy: float, radius: float, thickness: float) -> Path2D:
	outer = as_outer(_circle(cx, cy, radius))
	inner = as_outer(_circle(cx, cy, max(radius - thickness, 0.1 * radius))).reverse()
	return Path2D([outer, inner])


def _scaled(points: list[tuple[float, float]], factor: float) -> list[tuple[float, float]]:
	cx = sum(p[0] for p in points) / len(points)
	cy = sum(p[1] for p in points) / len(points)
	return [(cx + (x - cx) * factor, cy + (y - cy) * factor) for x, y in points]


def _star(cx: float, cy: float, outer: float, inner: float) -> list[tuple[float, float]]:
	import math

	points: list[tuple[float, float]] = []
	for index in range(10):
		radius = outer if index % 2 == 0 else inner
		angle = math.pi / 2.0 + index * math.pi / 5.0
		points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
	return points


def _arrow(
	left: float,
	right: float,
	low: float,
	high: float,
	mid: float,
	centre_x: float,
	bar: float,
	head: float,
	direction: str,
) -> Path2D:
	"""A shafted arrow built as one closed outline."""
	half = 0.5 * bar
	wing = 0.55 * (high - low)
	if direction in ("left", "right"):
		sign = -1.0 if direction == "left" else 1.0
		tip = right if direction == "right" else left
		tail = left if direction == "right" else right
		base = tip - sign * head
		points = [
			(tip, mid),
			(base, mid + wing * 0.5),
			(base, mid + half),
			(tail, mid + half),
			(tail, mid - half),
			(base, mid - half),
			(base, mid - wing * 0.5),
		]
	else:
		sign = 1.0 if direction == "up" else -1.0
		tip = high if direction == "up" else low
		tail = low if direction == "up" else high
		base = tip - sign * head
		points = [
			(centre_x, tip),
			(centre_x + wing * 0.5, base),
			(centre_x + half, base),
			(centre_x + half, tail),
			(centre_x - half, tail),
			(centre_x - half, base),
			(centre_x - wing * 0.5, base),
		]

	contour = Contour(points[0])
	for point in points[1:]:
		contour.line_to(point)
	path = Path2D([contour])
	# Winding depends on the direction the points were emitted in; normalise.
	if contour.signed_area() < 0:
		path = Path2D([contour.reverse()])
	return path


def _canonical_parts(codepoint: int) -> list[int]:
	"""Fully decompose a codepoint, keeping only canonical decompositions."""
	decomposition = unicodedata.decomposition(chr(codepoint))
	if not decomposition or decomposition.startswith("<"):
		return []
	parts = [int(token, 16) for token in decomposition.split()]
	result: list[int] = []
	for index, part in enumerate(parts):
		if index == 0:
			nested = _canonical_parts(part)
			result.extend(nested if nested else [part])
		else:
			result.append(part)
	return result
