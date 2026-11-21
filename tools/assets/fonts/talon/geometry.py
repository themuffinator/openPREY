"""Construction primitives for the Talon face, and their conversion to curves.

Talon is drawn on a 1000-unit grid from three kinds of part:

* squared bowls: rectangles whose corners are superellipse quarters, a large
  outer radius around a tight inner one (the PREY wordmark's bowls);
* soft turns: a smaller outer radius where a stroke turns a corner;
* straight strokes whose ends are cut square to an axis (Impact's terminals).

Parts are combined with Shapely's boolean operations, which work on polygons,
so corners are sampled densely. ``to_path`` then finds the runs of samples
that came from a curve and fits them with quadratic splines, which is what
the face ships: an outline of straight lines and true curves, not a polygon.
"""
from __future__ import annotations

import math

import numpy as np
from fontTools.cu2qu import curve_to_quadratic
from shapely import affinity
from shapely.geometry import LineString, Polygon, box as _box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from q4font.path import Contour, Path2D

BIG = 5000.0
# Superellipse exponent of every rounded corner: 2 is a circle, higher is
# squarer. The wordmark's bowls sit near 2.6.
EXPONENT = 2.6
CORNER_STEPS = 28

# A polygon vertex belongs to a curve when the outline turns less than this
# there and both edges meeting at it are shorter than CURVE_EDGE. Sampled
# corners turn by a few degrees per step; constructed corners by far more.
CURVE_TURN = math.radians(14.0)
CURVE_EDGE = 40.0
# Fitting tolerances in design units (one unit is 2.048 font units).
CUBIC_TOLERANCE = 0.5
QUADRATIC_TOLERANCE = 0.4


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------


def rrect(x0, y0, x1, y1, r, n=EXPONENT, steps=CORNER_STEPS):
	"""Rounded rectangle. ``r`` is one radius or (tl, tr, br, bl); each entry is
	a radius or an (rx, ry) pair. A zero radius leaves that corner square."""
	if not isinstance(r, (tuple, list)):
		r = (r, r, r, r)
	w, h = x1 - x0, y1 - y0
	pts = []
	corners = (((x1, y1), r[1], 0.0), ((x0, y1), r[0], 90.0), ((x0, y0), r[3], 180.0), ((x1, y0), r[2], 270.0))
	for (cx, cy), rad, a0 in corners:
		rx, ry = rad if isinstance(rad, (tuple, list)) else (rad, rad)
		rx, ry = min(rx, w / 2), min(ry, h / 2)
		if rx <= 0.5 or ry <= 0.5:
			pts.append((cx, cy))
			continue
		sx = -1 if cx == x1 else 1
		sy = -1 if cy == y1 else 1
		ccx, ccy = cx + sx * rx, cy + sy * ry
		for i in range(steps + 1):
			a = math.radians(a0 + 90.0 * i / steps)
			c, s = math.cos(a), math.sin(a)
			pts.append((ccx + rx * math.copysign(abs(c) ** (2 / n), c), ccy + ry * math.copysign(abs(s) ** (2 / n), s)))
	return Polygon(pts)


def inner_radius(r, inset):
	return max(r - inset * 0.9, r * 0.28, 18.0)


def ring(x0, y0, x1, y1, r, sx, sy, square=()):
	"""A bowl: rounded rectangle minus its counter, walls sx thick at the sides
	and sy at top and bottom. ``square`` names corners kept square."""
	names = ("tl", "tr", "br", "bl")
	radii = r if isinstance(r, (tuple, list)) else (r, r, r, r)
	outer = tuple(0 if nm in square else rc for nm, rc in zip(names, radii))
	inner = tuple(
		0 if (nm in square or rc <= 0) else (inner_radius(rc, sx), inner_radius(rc, sy))
		for nm, rc in zip(names, radii)
	)
	return rrect(x0, y0, x1, y1, outer).difference(rrect(x0 + sx, y0 + sy, x1 - sx, y1 - sy, inner))


def rect(x0, y0, x1, y1, r=0):
	return rrect(x0, y0, x1, y1, r) if r else _box(x0, y0, x1, y1)


def box(x0, y0, x1, y1):
	return _box(x0, y0, x1, y1)


def poly(points):
	return Polygon(points)


def stroke(p0, p1, w, lo=-BIG, hi=BIG, xlo=-BIG, xhi=BIG):
	"""A straight stroke of perpendicular width ``w`` through p0 and p1,
	extended past both and clipped to the given band, so its ends are cut
	square to the axes."""
	(ax, ay), (bx, by) = p0, p1
	length = math.hypot(bx - ax, by - ay)
	ux, uy = (bx - ax) / length, (by - ay) / length
	ext = 400.0
	line = LineString([(ax - ux * ext, ay - uy * ext), (bx + ux * ext, by + uy * ext)])
	return line.buffer(w / 2, cap_style=2).intersection(_box(xlo, lo, xhi, hi))


def diag(x_top, x_bot, w, y_top, y_bot):
	"""A diagonal from (x_top, y_top) to (x_bot, y_bot), cut flat at both."""
	return stroke((x_top, y_top), (x_bot, y_bot), w, y_bot, y_top)


def union(*parts):
	return unary_union([p for p in parts if p is not None and not p.is_empty])


def clip(geom, x0, y0, x1, y1):
	return geom.intersection(_box(x0, y0, x1, y1))


def mirror(geom, width):
	return affinity.scale(geom, xfact=-1, origin=(width / 2, 0))


def flip(geom, y_mid):
	return affinity.scale(geom, yfact=-1, origin=(0, y_mid))


def turn(geom, width, height):
	return affinity.rotate(geom, 180, origin=(width / 2, height / 2))


def move(geom, dx, dy):
	return affinity.translate(geom, dx, dy)


def rotate(geom, degrees, origin):
	return affinity.rotate(geom, degrees, origin=origin)


def scale(geom, fx, fy, ox=0.0, oy=0.0):
	return affinity.scale(geom, xfact=fx, yfact=fy, origin=(ox, oy))


def bounds(geom):
	return geom.bounds


# ---------------------------------------------------------------------------
# polygons to curves
# ---------------------------------------------------------------------------


def _unit(v):
	n = math.hypot(v[0], v[1])
	return (v[0] / n, v[1] / n) if n > 1e-12 else (0.0, 0.0)


def _turn(a, b, c):
	u, v = _unit((b[0] - a[0], b[1] - a[1])), _unit((c[0] - b[0], c[1] - b[1]))
	return abs(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1]))


def _bezier(ctrl, t):
	mt = 1.0 - t
	return (
		mt ** 3 * ctrl[0][0] + 3 * mt * mt * t * ctrl[1][0] + 3 * mt * t * t * ctrl[2][0] + t ** 3 * ctrl[3][0],
		mt ** 3 * ctrl[0][1] + 3 * mt * mt * t * ctrl[1][1] + 3 * mt * t * t * ctrl[2][1] + t ** 3 * ctrl[3][1],
	)


def _fit_cubic(points, t0, t1, depth=0):
	"""Schneider's fit of one cubic with fixed end tangents, split until the
	samples lie within CUBIC_TOLERANCE of it."""
	pts = np.asarray(points, dtype=float)
	p0, p3 = pts[0], pts[-1]
	if len(pts) == 2:
		d = np.linalg.norm(p3 - p0) / 3.0
		return [(tuple(p0), tuple(p0 + np.array(t0) * d), tuple(p3 + np.array(t1) * d), tuple(p3))]
	seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
	u = np.concatenate([[0.0], np.cumsum(seg)]) / max(seg.sum(), 1e-9)
	a0 = np.outer(3 * (1 - u) ** 2 * u, t0)
	a1 = np.outer(3 * (1 - u) * u ** 2, t1)
	c00, c01, c11 = (a0 * a0).sum(), (a0 * a1).sum(), (a1 * a1).sum()
	base = np.outer((1 - u) ** 3 + 3 * (1 - u) ** 2 * u, p0) + np.outer(3 * (1 - u) * u ** 2 + u ** 3, p3)
	tmp = pts - base
	x0, x1 = (a0 * tmp).sum(), (a1 * tmp).sum()
	det = c00 * c11 - c01 * c01
	chord = np.linalg.norm(p3 - p0)
	if abs(det) > 1e-12:
		alpha0, alpha1 = (x0 * c11 - x1 * c01) / det, (c00 * x1 - c01 * x0) / det
	else:
		alpha0 = alpha1 = chord / 3.0
	if alpha0 < 1e-6 * chord or alpha1 < 1e-6 * chord:
		alpha0 = alpha1 = chord / 3.0
	ctrl = (tuple(p0), tuple(p0 + np.array(t0) * alpha0), tuple(p3 + np.array(t1) * alpha1), tuple(p3))
	errors = [math.dist(_bezier(ctrl, ui), tuple(pi)) for ui, pi in zip(u, pts)]
	worst = int(np.argmax(errors))
	if errors[worst] <= CUBIC_TOLERANCE or depth > 8 or len(pts) < 4:
		return [ctrl]
	worst = min(max(worst, 1), len(pts) - 2)
	tm = _unit((pts[worst + 1][0] - pts[worst - 1][0], pts[worst + 1][1] - pts[worst - 1][1]))
	left = _fit_cubic(pts[: worst + 1], t0, (-tm[0], -tm[1]), depth + 1)
	right = _fit_cubic(pts[worst:], tm, t1, depth + 1)
	return left + right


def _ring_to_contour(coords, factor):
	pts = [tuple(p) for p in coords[:-1]]
	# Drop repeated points and points on a straight line.
	clean = []
	for p in pts:
		if clean and math.dist(clean[-1], p) < 1e-6:
			continue
		clean.append(p)
	if len(clean) > 1 and math.dist(clean[0], clean[-1]) < 1e-6:
		clean.pop()
	changed = True
	while changed and len(clean) > 3:
		changed = False
		for i in range(len(clean)):
			a, b, c = clean[i - 1], clean[i], clean[(i + 1) % len(clean)]
			if _turn(a, b, c) < 1e-4:
				del clean[i]
				changed = True
				break
	pts = clean
	n = len(pts)
	if n < 3:
		return None

	def edge(i, j):
		return math.dist(pts[i % n], pts[j % n])

	smooth = [
		_turn(pts[i - 1], pts[i], pts[(i + 1) % n]) < CURVE_TURN and edge(i - 1, i) < CURVE_EDGE and edge(i, i + 1) < CURVE_EDGE
		for i in range(n)
	]
	if all(smooth):
		# A closed curve with no corner: start anywhere.
		smooth[0] = False
	start = smooth.index(False)
	order = [(start + k) % n for k in range(n)] + [start]

	def scaled(p):
		return (p[0] * factor, p[1] * factor)

	contour = Contour(scaled(pts[start]))
	k = 0
	while k < n:
		i = order[k]
		j = order[k + 1]
		if not smooth[j]:
			contour.line_to(scaled(pts[j]))
			k += 1
			continue
		# A run of curve samples: from corner i through to the next corner.
		run = [i]
		m = k + 1
		while smooth[order[m]]:
			run.append(order[m])
			m += 1
		run.append(order[m])
		samples = [pts[r] for r in run]
		prev = pts[(run[0] - 1) % n]
		nxt = pts[(run[-1] + 1) % n]
		# Leave a corner along the edge that reaches it when that edge is a
		# straight line running into the curve; the curve meets it smoothly.
		t_in = _unit((samples[1][0] - samples[0][0], samples[1][1] - samples[0][1]))
		line_in = _unit((samples[0][0] - prev[0], samples[0][1] - prev[1]))
		if _turn(prev, samples[0], samples[1]) < CURVE_TURN:
			t_in = line_in
		t_out = _unit((samples[-2][0] - samples[-1][0], samples[-2][1] - samples[-1][1]))
		line_out = _unit((samples[-1][0] - nxt[0], samples[-1][1] - nxt[1]))
		if _turn(samples[-2], samples[-1], nxt) < CURVE_TURN:
			t_out = line_out
		for cubic in _fit_cubic(samples, t_in, t_out):
			quad = curve_to_quadratic([scaled(p) for p in cubic], QUADRATIC_TOLERANCE * factor)
			offs = quad[1:-1]
			for idx, off in enumerate(offs):
				end = quad[-1] if idx == len(offs) - 1 else ((off[0] + offs[idx + 1][0]) / 2, (off[1] + offs[idx + 1][1]) / 2)
				contour.quad_to(tuple(off), tuple(end))
		k = m
	# The walk ends back on the start point; a closing line there is implicit.
	if contour.segments and contour.segments[-1][0] == "L":
		contour.segments.pop()
	return contour


def to_path(geom, factor, dx=0.0):
	"""Shapely geometry in design units -> Path2D in font units, outer
	contours clockwise (TrueType), counters anticlockwise."""
	path = Path2D()
	if geom is None or geom.is_empty:
		return path
	if dx:
		geom = affinity.translate(geom, dx, 0)
	polygons = getattr(geom, "geoms", [geom])
	for polygon in polygons:
		if polygon.geom_type == "GeometryCollection" or polygon.geom_type == "MultiPolygon":
			for sub in to_path(polygon, factor).contours:
				path.contours.append(sub)
			continue
		if polygon.geom_type != "Polygon" or polygon.area < 1.0:
			continue
		polygon = orient(polygon, sign=-1.0)
		for line in [polygon.exterior, *polygon.interiors]:
			contour = _ring_to_contour(list(line.coords), factor)
			if contour is not None:
				path.contours.append(contour)
	return path
