"""Minimal outline container shared by the tracer, rasteriser and TTF writer."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

Point = tuple[float, float]


@dataclass
class Contour:
	"""One closed subpath: a start point plus line/quadratic segments back to it."""

	start: Point
	segments: list[tuple] = field(default_factory=list)

	def line_to(self, point: Point) -> None:
		self.segments.append(("L", point))

	def quad_to(self, control: Point, point: Point) -> None:
		self.segments.append(("Q", control, point))

	def points(self) -> list[Point]:
		"""Every on-curve point, in order."""
		result = [self.start]
		for segment in self.segments:
			result.append(segment[-1])
		return result

	def flatten(self, flatness: float) -> list[Point]:
		"""Approximate the contour with a polygon."""
		output: list[Point] = [self.start]
		current = self.start
		for segment in self.segments:
			if segment[0] == "L":
				current = segment[1]
				output.append(current)
				continue
			_, control, end = segment
			steps = _quad_steps(current, control, end, flatness)
			for step in range(1, steps + 1):
				t = step / steps
				inv = 1.0 - t
				x = inv * inv * current[0] + 2 * inv * t * control[0] + t * t * end[0]
				y = inv * inv * current[1] + 2 * inv * t * control[1] + t * t * end[1]
				output.append((x, y))
			current = end
		# Drop a duplicated closing point if the last segment landed on the start.
		if len(output) > 1 and _close(output[0], output[-1]):
			output.pop()
		return output

	def signed_area(self) -> float:
		polygon = self.flatten(0.05)
		total = 0.0
		count = len(polygon)
		for index in range(count):
			x0, y0 = polygon[index]
			x1, y1 = polygon[(index + 1) % count]
			total += x0 * y1 - x1 * y0
		return 0.5 * total

	def reverse(self) -> "Contour":
		"""Return this contour with its direction flipped."""
		points = [self.start]
		kinds: list[tuple] = []
		for segment in self.segments:
			if segment[0] == "L":
				kinds.append(("L", None))
				points.append(segment[1])
			else:
				kinds.append(("Q", segment[1]))
				points.append(segment[2])

		# points[i] -> points[i+1] carries kinds[i]; walking backwards swaps ends.
		reversed_contour = Contour(points[-1])
		for index in range(len(kinds) - 1, -1, -1):
			kind, control = kinds[index]
			target = points[index]
			if kind == "L":
				reversed_contour.line_to(target)
			else:
				reversed_contour.quad_to(control, target)
		return reversed_contour

	def transformed(self, scale_x: float, scale_y: float, offset_x: float, offset_y: float) -> "Contour":
		def convert(point: Point) -> Point:
			return (point[0] * scale_x + offset_x, point[1] * scale_y + offset_y)

		return self.mapped(convert)

	def mapped(self, convert) -> "Contour":
		"""Apply ``convert`` to every point, control points included."""
		result = Contour(convert(self.start))
		for segment in self.segments:
			if segment[0] == "L":
				result.line_to(convert(segment[1]))
			else:
				result.quad_to(convert(segment[1]), convert(segment[2]))
		return result


@dataclass
class Path2D:
	contours: list[Contour] = field(default_factory=list)

	def flatten(self, flatness: float = 0.05) -> list[list[Point]]:
		return [contour.flatten(flatness) for contour in self.contours]

	def transformed(self, scale_x: float, scale_y: float, offset_x: float = 0.0, offset_y: float = 0.0) -> "Path2D":
		return Path2D([c.transformed(scale_x, scale_y, offset_x, offset_y) for c in self.contours])

	def mapped(self, convert) -> "Path2D":
		return Path2D([c.mapped(convert) for c in self.contours])

	def bounds(self) -> tuple[float, float, float, float] | None:
		xs: list[float] = []
		ys: list[float] = []
		for polygon in self.flatten(0.05):
			for x, y in polygon:
				xs.append(x)
				ys.append(y)
		if not xs:
			return None
		return min(xs), min(ys), max(xs), max(ys)

	def is_empty(self) -> bool:
		return not self.contours

	def draw(self, pen) -> None:
		"""Emit this path into a fontTools pen (quadratic, TrueType style)."""
		for contour in self.contours:
			pen.moveTo(contour.start)
			for segment in contour.segments:
				if segment[0] == "L":
					pen.lineTo(segment[1])
				else:
					pen.qCurveTo(segment[1], segment[2])
			pen.closePath()


def _close(a: Point, b: Point, epsilon: float = 1e-9) -> bool:
	return abs(a[0] - b[0]) <= epsilon and abs(a[1] - b[1]) <= epsilon


def _quad_steps(start: Point, control: Point, end: Point, flatness: float) -> int:
	"""Pick a subdivision count that keeps the chord error under ``flatness``."""
	dx = start[0] - 2.0 * control[0] + end[0]
	dy = start[1] - 2.0 * control[1] + end[1]
	deviation = math.hypot(dx, dy)
	if deviation <= 1e-12:
		return 1
	steps = int(math.ceil(math.sqrt(deviation / (4.0 * max(flatness, 1e-6)))))
	return max(1, min(96, steps))
