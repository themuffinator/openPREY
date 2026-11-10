"""Style-matched glyph import from the OFL Noto donor faces.

Scripts that the Quake 4 bitmaps never covered - Greek, Cyrillic, Arabic,
Hebrew - have to come from somewhere, and the Noto family is both permissively
licensed and available as variable fonts.  That variability is what makes the
match work: instead of thickening or thinning a fixed outline after the fact,
each donor is instantiated at the weight and width whose stems already match
the Quake 4 face, so the imported glyphs are properly drawn at the right
colour rather than distorted into it.

Only letters that genuinely differ are imported.  Cyrillic A, B, E, K, M, H, O,
P, C, T, X and their Greek equivalents are the same shapes as the Latin ones,
so those reuse the traced Quake 4 outlines and the majority of any Cyrillic or
Greek run stays authentic.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

from .path import Contour, Path2D, Point


@dataclass
class DonorMetrics:
	"""What a donor instance measures, used to align it with the target face."""

	upm: float
	cap_height: float
	x_height: float
	stem: float


class DonorFace:
	"""One variable donor font, instantiated at a chosen weight and width."""

	def __init__(self, path: Path, weight: float, width: float) -> None:
		self.source_path = path
		base = TTFont(path)
		axes = {axis.axisTag: axis for axis in base["fvar"].axes} if "fvar" in base else {}
		location: dict[str, float] = {}
		if "wght" in axes:
			location["wght"] = _clamp(weight, axes["wght"].minValue, axes["wght"].maxValue)
		if "wdth" in axes:
			location["wdth"] = _clamp(width, axes["wdth"].minValue, axes["wdth"].maxValue)
		self.location = location
		self.font = instancer.instantiateVariableFont(base, location, inplace=False) if location else base
		self.glyph_set = self.font.getGlyphSet()
		self.cmap = self.font.getBestCmap()
		self.upm = float(self.font["head"].unitsPerEm)
		self.metrics = self._measure()

	def has(self, codepoint: int) -> bool:
		return codepoint in self.cmap

	def outline(self, codepoint: int) -> tuple[Path2D, float] | None:
		"""Return the donor outline in its own units, plus its advance."""
		name = self.cmap.get(codepoint)
		if name is None:
			return None
		# Most accented donor glyphs are components referencing a base and a
		# mark; a plain recording pen would capture the references and leave the
		# outline empty, so decompose against the glyph set.
		pen = DecomposingRecordingPen(self.glyph_set)
		self.glyph_set[name].draw(pen)
		advance = float(self.font["hmtx"][name][0])
		return _record_to_path(pen.value), advance

	def _measure(self) -> DonorMetrics:
		cap = _glyph_top(self, ord("H")) or 0.7 * self.upm
		x_height = _glyph_top(self, ord("x")) or 0.52 * self.upm
		stem = _stem_width(self, ord("I")) or _stem_width(self, ord("H")) or 0.09 * self.upm
		return DonorMetrics(self.upm, cap, x_height, stem)


def _clamp(value: float, low: float, high: float) -> float:
	return max(low, min(high, value))


def _record_to_path(records) -> Path2D:
	"""Convert a fontTools pen recording into a Path2D.

	TrueType contours may run several off-curve points together, with an
	implied on-curve point at each midpoint; those are made explicit here.
	"""
	path = Path2D()
	contour: Contour | None = None
	current: Point = (0.0, 0.0)

	for operator, args in records:
		if operator == "moveTo":
			current = tuple(args[0])
			contour = Contour(current)
			path.contours.append(contour)
		elif operator == "lineTo":
			if contour is None:
				continue
			current = tuple(args[0])
			contour.line_to(current)
		elif operator == "qCurveTo":
			if contour is None:
				continue
			points = [tuple(p) if p is not None else None for p in args]
			current = _emit_quadratics(contour, current, points)
		elif operator == "curveTo":
			if contour is None:
				continue
			# Cubic donors are rare here, but approximate rather than drop them.
			points = [tuple(p) for p in args]
			current = _emit_cubic(contour, current, points)
		elif operator == "closePath" or operator == "endPath":
			contour = None

	return path


def _emit_quadratics(contour: Contour, start: Point, points: list) -> Point:
	if not points:
		return start
	if points[-1] is None:
		# A contour made entirely of off-curve points; close it on the midpoint.
		off = [p for p in points if p is not None]
		if not off:
			return start
		implied = _midpoint(off[-1], off[0])
		points = off + [implied]

	current = start
	off_curve = points[:-1]
	end = points[-1]
	for index, control in enumerate(off_curve):
		if index + 1 < len(off_curve):
			target = _midpoint(control, off_curve[index + 1])
		else:
			target = end
		contour.quad_to(control, target)
		current = target
	if not off_curve:
		contour.line_to(end)
		current = end
	return current


def _emit_cubic(contour: Contour, start: Point, points: list, steps: int = 8) -> Point:
	c1, c2, end = points[-3], points[-2], points[-1]
	previous = start
	for step in range(1, steps + 1):
		t = step / steps
		inv = 1.0 - t
		x = inv**3 * start[0] + 3 * inv**2 * t * c1[0] + 3 * inv * t**2 * c2[0] + t**3 * end[0]
		y = inv**3 * start[1] + 3 * inv**2 * t * c1[1] + 3 * inv * t**2 * c2[1] + t**3 * end[1]
		# Midpoint control keeps the sampled curve smooth without a full cu2qu.
		control = (0.5 * (previous[0] + x), 0.5 * (previous[1] + y))
		contour.quad_to(control, (x, y))
		previous = (x, y)
	return end


def _midpoint(a: Point, b: Point) -> Point:
	return (0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]))


def _glyph_top(face: DonorFace, codepoint: int) -> float | None:
	result = face.outline(codepoint)
	if result is None:
		return None
	bounds = result[0].bounds()
	return bounds[3] if bounds else None


def _stem_width(face: DonorFace, codepoint: int) -> float | None:
	"""Width of the vertical stem, measured across the middle of the glyph."""
	result = face.outline(codepoint)
	if result is None:
		return None
	path = result[0]
	bounds = path.bounds()
	if bounds is None:
		return None
	y = 0.5 * (bounds[1] + bounds[3])
	crossings = _scanline(path, y)
	if len(crossings) < 2:
		return None
	return crossings[1] - crossings[0]


def _scanline(path: Path2D, y: float) -> list[float]:
	"""Sorted x positions where the outline crosses a horizontal line."""
	hits: list[float] = []
	for polygon in path.flatten(2.0):
		count = len(polygon)
		for index in range(count):
			x0, y0 = polygon[index]
			x1, y1 = polygon[(index + 1) % count]
			if (y0 > y) == (y1 > y):
				continue
			t = (y - y0) / (y1 - y0)
			hits.append(x0 + t * (x1 - x0))
	return sorted(hits)


_FACE_CACHE: dict[tuple[str, float, float], DonorFace] = {}


def get_face(path: Path, weight: float, width: float) -> DonorFace:
	"""Instantiating a variable font is expensive, so reuse the instances."""
	key = (str(path), round(weight, 2), round(width, 2))
	face = _FACE_CACHE.get(key)
	if face is None:
		face = DonorFace(path, weight, width)
		_FACE_CACHE[key] = face
	return face


def _solve_axis(samples: list[tuple[float, float]], target: float, low: float, high: float) -> float:
	"""Invert a sampled, monotonic axis response by linear interpolation."""
	samples = sorted(samples, key=lambda s: s[1])
	if not samples:
		return 0.5 * (low + high)
	if target <= samples[0][1]:
		return samples[0][0]
	if target >= samples[-1][1]:
		return samples[-1][0]
	for index in range(len(samples) - 1):
		(a_value, a_response), (b_value, b_response) = samples[index], samples[index + 1]
		if a_response <= target <= b_response:
			span = b_response - a_response
			t = 0.0 if abs(span) < 1e-12 else (target - a_response) / span
			return _clamp(a_value + t * (b_value - a_value), low, high)
	return samples[-1][0]


def solve_instance(target_stem_ratio: float, target_width_ratio: float, path: Path) -> tuple[float, float]:
	"""Pick the donor weight/width whose proportions match the target face.

	``target_stem_ratio`` is the face's stem width over its cap height and
	``target_width_ratio`` its average advance over cap height, so both are
	scale free.  Each axis responds close to monotonically, which means a few
	probes and an interpolation beat searching the whole grid - and the probe
	points are shared between faces, so they are only ever built once.
	"""
	weight_samples: list[tuple[float, float]] = []
	for weight in (200.0, 400.0, 600.0, 800.0):
		face = get_face(path, weight, 100.0)
		if face.metrics.cap_height <= 0:
			continue
		weight_samples.append((weight, face.metrics.stem / face.metrics.cap_height))
	weight = _solve_axis(weight_samples, target_stem_ratio, 100.0, 900.0)

	width_samples: list[tuple[float, float]] = []
	for width in (62.5, 80.0, 100.0):
		face = get_face(path, weight, width)
		if face.metrics.cap_height <= 0:
			continue
		advance = face.outline(ord("H"))
		if advance is None:
			continue
		width_samples.append((width, advance[1] / face.metrics.cap_height))
	width = _solve_axis(width_samples, target_width_ratio, 62.5, 100.0)

	return weight, width
