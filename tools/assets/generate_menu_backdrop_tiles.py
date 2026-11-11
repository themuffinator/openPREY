#!/usr/bin/env python3
"""Generate the main menu's aspect-expansion tiles from the retail Prey art.

Prey paints its front-end backdrop for a 4:3 screen. openPREY widens the
canvas to the screen's aspect (docs/dev/prey-ui-visual-design.md, sections 3
and 12), and the extra canvas needs art that continues the painting. This tool
synthesises that art from the painting itself:

* ``guis/assets/menu/preymenu/earth_{left,right,bottom}.tga`` continue the main
  menu's Earth layer (``preymenu/background2.tga``, drawn in a 640x150 window
  at 0,330). The main menu draws them as the Earth window's edge slices, after
  the star layer, so Earth keeps covering the stars.
* ``guis/assets/menu/background_{left,right,top,bottom}.tga`` continue the
  flat painting (``guis/assets/menu/background.tga``) that ``restart.gui``
  draws.

Every tile covers the full base window beside its edge (640 units across for
left and right, the window's height for top and bottom) at the texel density
of the art it continues, so the engine shows the inner part of it at any
aspect (``DrawBackgroundExpansionSlice``).

How it works. Each painting's Earth is a disc whose limb is a circle. The
tool resamples the art into polar strips about the disc's centre, where every
row holds one radius: one depth under the limb or one height over it. Along a
row the art therefore continues as it was painted, with its rim, glow and
foreshortening. Each tile is filled along its rows:

* large-scale light from the art mirrored across the join, which is
  continuous and lit as painted (a mirror is not recognisable at that scale);
* fine detail from copies of the art moved along the limb by tens of degrees,
  so the mirror's symmetry does not show in the clouds or stars;
* at the join itself the mirror as it is, fading into the rest;
* radii the art never reaches (deep surface, high sky) from the nearest rows
  of the same zone, and, under the window's foot, from a screen-space
  reflection of the painted surface. The bottom tiles, used only on screens
  taller than 4:3, are plainer than the side tiles.

The Sphere is kept out of the exemplars. The strips are resampled back into
tile textures. Nothing is invented from noise: every texel comes from the
painting.

The retail archives are read in place; nothing is extracted to disk.

    python tools/assets/generate_menu_backdrop_tiles.py [--prey-base DIR]
        [--out content/basepr/pak1] [--preview DIR] [--quick] [--only earth|painting]

``--prey-base`` is the retail ``base`` directory (auto-detected from the usual
install roots when omitted). ``--preview`` writes PNG composites of each
painting with its tiles. ``--quick`` samples the strips at half density, for
iteration. A full run takes a few minutes; the output is deterministic.
"""
from __future__ import annotations

import argparse
import io
import os
import struct
import sys
import warnings
import zipfile
import zlib
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]

KNOWN_PREY_BASES = (
	r"C:\Program Files (x86)\Human Head Studios\Prey\base",
	r"C:\Program Files\Human Head Studios\Prey\base",
	r"C:\Program Files (x86)\2K Games\Prey\base",
	r"C:\Program Files (x86)\R.G. Mechanics\Prey\base",
	r"C:\Program Files (x86)\Steam\steamapps\common\Prey\base",
)

# ---------------------------------------------------------------------------
# Retail archive access
# ---------------------------------------------------------------------------


def find_prey_base(explicit: str | None) -> Path:
	candidates = [explicit] if explicit else []
	if not explicit:
		env = os.environ.get("OPENPREY_RETAIL_BASE")
		if env:
			candidates.append(env)
		candidates.extend(KNOWN_PREY_BASES)
	for candidate in candidates:
		if candidate and Path(candidate).is_dir() and any(Path(candidate).glob("*.pk4")):
			return Path(candidate)
	raise SystemExit("Prey's retail base directory was not found; pass --prey-base.")


class RetailArchives:
	"""Reads files from the retail pk4s, later archives overriding earlier ones.

	Some retail entries store a backslash name in the local header and a
	forward-slash name in the central directory, which zipfile refuses, so the
	data is read through the local header directly.
	"""

	def __init__(self, base: Path) -> None:
		self.entries: dict[str, tuple[zipfile.ZipFile, zipfile.ZipInfo]] = {}
		for pk4 in sorted(base.glob("*.pk4")):
			archive = zipfile.ZipFile(pk4)
			for info in archive.infolist():
				self.entries[info.filename.replace("\\", "/").lower()] = (archive, info)

	def read(self, name: str) -> bytes:
		key = name.replace("\\", "/").lower()
		if key not in self.entries:
			raise SystemExit(f"{name} is not in the retail archives.")
		archive, info = self.entries[key]
		archive.fp.seek(info.header_offset)
		header = archive.fp.read(30)
		name_length, extra_length = struct.unpack("<HH", header[26:30])
		archive.fp.seek(info.header_offset + 30 + name_length + extra_length)
		raw = archive.fp.read(info.compress_size)
		if info.compress_type == zipfile.ZIP_DEFLATED:
			return zlib.decompress(raw, -15)
		if info.compress_type == zipfile.ZIP_STORED:
			return raw
		raise SystemExit(f"{name} uses an unsupported compression method.")

	def image(self, name: str) -> np.ndarray:
		with Image.open(io.BytesIO(self.read(name))) as im:
			mode = "RGBA" if im.mode in ("RGBA", "LA") else "RGB"
			return np.asarray(im.convert(mode), dtype=np.float32) / 255.0


# ---------------------------------------------------------------------------
# Continuing the art
# ---------------------------------------------------------------------------


def continue_art(canvas: np.ndarray, art: np.ndarray, hole: np.ndarray, direction: str,
				 density: tuple[float, float], translate_units: float, zones: np.ndarray | None = None,
				 copies: int = 3, rise_units: tuple[float, ...] = (12.0, 24.0, 40.0),
				 below: np.ndarray | None = None,
				 light_units: float = 14.0, join_units: float = 3.0) -> np.ndarray:
	"""Continue the art in a polar strip into ``hole``.

	Columns run along the limb and rows across it, so every row keeps one
	radius: one depth under the limb or one height over it. The art is
	therefore always continued along its rows; ``direction`` says on which
	side of the art the hole lies in them, "right" or "left". Surface the
	rows never reach takes ``below`` when given (a screen-space continuation
	of the strip's shape); anything else they never reach is filled across
	the rows, from the nearest rows of the same zone.

	Large-scale light comes from the art mirrored across the join: continuous,
	and lit and foreshortened as painted. Fine detail comes from copies of the
	art moved along the limb by multiples of ``translate_units`` either way,
	each at its painted depth, the nearest copies winning, so the mirror's
	symmetry does not show. Rows the art does not reach take copies moved up
	to ``rise_units`` towards the art as well, but only between rows marked in
	rows outside zone 1 of ``zones`` (either way), which keeps the rim and
	glow (zone 1) at their painted radius. Where no
	copy reaches, the mirror's own detail stays. Right at the join the mirror
	is used as it is for ``join_units``, fading into the rest over four times that.
	"""
	flip = direction == "left"

	def orient(a):
		return np.ascontiguousarray(a[:, ::-1]) if flip else a

	canvas, art, hole = orient(canvas), orient(art), orient(hole)
	h, w = hole.shape
	zones = np.zeros(h, int) if zones is None else zones
	open_rows = zones != 1
	across, along = density  # strip texels per unit across and along the limb

	# rows holding less than 60 units of art reflect it only once: bounced,
	# a short stretch repeats into streaks
	mirrored = mirror_columns(canvas, art, hole, 1 << 30, bounce=int(60.0 * along))
	have = art | (hole & (np.abs(mirrored).sum(axis=2) > 0))
	if below is not None:
		# surface under the art: the caller's screen-space continuation, which
		# has no seams between columns; it meets the rows' rim at the zone edge
		take = hole & (zones == 0)[:, None]
		mirrored[take] = orient(below)[take]
		have |= take
	mirrored = fill_vertical(mirrored, have, hole, zones)
	have |= hole & (np.abs(mirrored).sum(axis=2) > 0)
	if (hole & ~have).any():
		_, (iy, ix) = ndimage.distance_transform_edt(~have, return_indices=True)
		gap = hole & ~have
		mirrored[gap] = mirrored[iy[gap], ix[gap]]

	sigma = light_units * along

	def low(img):
		return ndimage.gaussian_filter1d(img, sigma, axis=1, mode="nearest")

	light = low(mirrored)
	detail = mirrored - light
	shift = int(round(translate_units * along))
	soft = max(sigma, 2.0)
	rises = [int(round(units * across)) for units in rise_units]
	moves = [(lift * rise, sign * k * shift) for rise in reversed(rises) for lift in (-1, 1)
			 for k in range(copies, 0, -1) for sign in (-1, 1)]
	moves += [(0, sign * k * shift) for k in range(copies, 0, -1) for sign in (-1, 1)]
	for rise, d in moves:  # least wanted first
		if d == 0 or abs(d) >= w or abs(rise) >= h:
			continue
		# row r takes row r - rise
		source = np.zeros_like(canvas)
		source_ok = np.zeros((h, w), bool)
		rows_ok = np.zeros(h, bool)
		if rise >= 0:
			source[rise:] = canvas[:h - rise]
			source_ok[rise:] = art[:h - rise]
			rows_ok[rise:] = open_rows[:h - rise]
		else:
			source[:rise] = canvas[-rise:]
			source_ok[:rise] = art[-rise:]
			rows_ok[:rise] = open_rows[-rise:]
		if rise:
			# only within a zone, and never in the rim and glow
			same = np.zeros(h, bool)
			if rise > 0:
				same[rise:] = zones[rise:] == zones[:h - rise]
			else:
				same[:rise] = zones[:rise] == zones[-rise:]
			source_ok &= (rows_ok & open_rows & same)[:, None]
		moved = np.zeros_like(canvas)
		valid = np.zeros((h, w), bool)
		if d > 0:
			moved[:, d:] = source[:, :-d]
			valid[:, d:] = source_ok[:, :-d]
		else:
			moved[:, :d] = source[:, -d:]
			valid[:, :d] = source_ok[:, -d:]
		valid &= hole
		if not valid.any():
			continue
		filled = np.where(valid[..., None], moved, mirrored)
		copy_detail = filled - low(filled)
		weight = ndimage.binary_erosion(valid, iterations=max(int(soft * 0.5), 1))
		weight = ndimage.gaussian_filter(weight.astype(np.float32), soft * 0.5)[..., None]
		detail = detail * (1.0 - weight) + copy_detail * weight
	combined = np.clip(light + detail, 0.0, 1.0)

	distance = ndimage.distance_transform_edt(hole, sampling=(1.0 / across, 1.0 / along))
	near = np.clip(1.0 - (distance - join_units) / (4.0 * join_units), 0.0, 1.0)[..., None]
	out = np.where(hole[..., None], mirrored * near + combined * (1.0 - near), canvas)
	return orient(out)


def surface_below(window: Window, disc: Disc, x: np.ndarray, y: np.ndarray, rim: float = 25.0,
				  stretch: float = 1.6, least: float = 30.0) -> np.ndarray:
	"""Continue a painting's Earth surface below its window, in screen space.

	Each column reflects the painted surface above the window's foot (from
	``rim`` units under the limb down to the foot) back and forth, stretched
	by ``stretch`` because the clouds foreshorten less deeper into the disc.
	Columns holding less than ``least`` units of it (where the limb runs off
	the foot) mirror the nearest column that holds enough. This is plainer
	than the strips' continuation: it serves only screens taller than 4:3."""
	foot = window.y + window.h - 0.75

	def surface_top(cx):
		limb_y = disc.cy - np.sqrt(np.maximum(disc.r ** 2 - (cx - disc.cx) ** 2, 0.0))
		return np.maximum(limb_y + rim, window.y + 0.75)

	columns = np.linspace(window.x, window.x + window.w, 2048)
	enough = columns[foot - surface_top(columns) >= least]
	lo, hi = enough.min(), enough.max()
	cx = np.where(x < lo, 2.0 * lo - x, np.where(x > hi, 2.0 * hi - x, x))
	cx = np.clip(cx, lo, hi)
	top = surface_top(cx)
	band = foot - top
	t = np.maximum(y - foot, 0.0) / stretch
	k = np.mod(t, 2.0 * band)
	src_y = np.where(k < band, foot - k, top + (k - band))
	return window.sample(cx, src_y)


def fill_vertical(canvas: np.ndarray, filled: np.ndarray, target: np.ndarray, zones: np.ndarray) -> np.ndarray:
	"""Fill ``target`` cells that are still empty from the rows above or
	below them: radii the art never reaches. A cell takes only rows of its
	own zone (surface, rim and glow, open sky: ``zones`` per row), mirrored
	back and forth through the nearest filled run of that zone in its column,
	so the limb and the sky never repeat into the surface or each other."""
	out = canvas.copy()
	h, w = filled.shape
	gaps = target & ~filled
	for j in np.nonzero(gaps.any(axis=0))[0]:
		for zone in np.unique(zones[gaps[:, j]]):
			in_zone = zones == zone
			have = np.nonzero(filled[:, j] & in_zone)[0]
			if have.size == 0:
				continue
			rows = np.nonzero(gaps[:, j] & in_zone)[0]
			below, above = rows[rows > have[-1]], rows[rows < have[0]]
			if below.size:
				last = have[-1]
				first = last
				while first > 0 and filled[first - 1, j] and in_zone[first - 1]:
					first -= 1
				span = last - first + 1
				k = (below - first) % (2 * span)
				out[below, j] = out[first + np.where(k < span, k, 2 * span - 1 - k), j]
			if above.size:
				first = have[0]
				last = first
				while last < h - 1 and filled[last + 1, j] and in_zone[last + 1]:
					last += 1
				span = last - first + 1
				k = (last - above) % (2 * span)
				out[above, j] = out[last - np.where(k < span, k, 2 * span - 1 - k), j]
	return out


def _mirror_line(values: np.ndarray, fixed: np.ndarray, band: np.ndarray, width: int, bounce: int) -> None:
	"""Mirror the fixed cells before ``band`` (across a gap of up to four
	cells, and stepping over cells that are not fixed, such as the Sphere)
	into the band. Runs of at least ``bounce`` cells reflect back and forth as
	far as the band goes; shorter ones once, as far as they are long."""
	cells = np.nonzero(band)[0]
	if cells.size == 0:
		return
	edge = cells.min()
	axis = edge
	while axis > 0 and not fixed[axis - 1] and edge - axis < 4:
		axis -= 1
	if axis == 0 or not fixed[axis - 1]:
		return
	run = np.nonzero(fixed[:axis])[0][::-1]  # nearest first
	length = run.size
	stop = values.shape[0] if length >= bounce else axis + length
	positions = np.arange(edge, min(edge + width, stop, values.shape[0]))
	if positions.size == 0:
		return
	m = (positions - axis) % (2 * length)
	values[positions] = values[run[np.where(m < length, m, 2 * length - 1 - m)]]


def mirror_columns(canvas: np.ndarray, fixed: np.ndarray, band: np.ndarray, width: int, bounce: int = 1 << 30) -> np.ndarray:
	"""Mirror each row's fixed pixels into ``band`` to their right."""
	out = canvas.copy()
	for i in range(fixed.shape[0]):
		_mirror_line(out[i], fixed[i], band[i], width, bounce)
	return out


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


class Disc:
	"""An Earth limb: a circle in GUI units (640x480 canvas)."""

	def __init__(self, cx: float, cy: float, radius: float) -> None:
		self.cx, self.cy, self.r = cx, cy, radius

	def polar(self, x, y):
		dx = x - self.cx
		dy = self.cy - y
		return np.arctan2(dx, dy), np.hypot(dx, dy)

	def cartesian(self, theta, rho):
		return self.cx + rho * np.sin(theta), self.cy - rho * np.cos(theta)


class Window:
	"""A texture drawn into a GUI rectangle."""

	def __init__(self, image: np.ndarray, x: float, y: float, w: float, h: float) -> None:
		self.image = image
		self.x, self.y, self.w, self.h = x, y, w, h
		self.th, self.tw = image.shape[:2]

	@property
	def density(self):
		return self.tw / self.w, self.th / self.h

	def to_texel(self, x, y):
		return (x - self.x) * self.tw / self.w - 0.5, (y - self.y) * self.th / self.h - 0.5

	def inside(self, x, y, margin_texels=0.0):
		tx, ty = self.to_texel(x, y)
		m = margin_texels
		return (tx >= m - 0.5) & (tx <= self.tw - 0.5 - m) & (ty >= m - 0.5) & (ty <= self.th - 0.5 - m)

	def sample(self, x, y, order=3):
		tx, ty = self.to_texel(x, y)
		out = np.empty(x.shape + (self.image.shape[2],), np.float32)
		for c in range(self.image.shape[2]):
			out[..., c] = ndimage.map_coordinates(self.image[..., c], [ty, tx], order=order, mode="nearest")
		return np.clip(out, 0.0, 1.0)


def tile_grid(base: Window, edge: str):
	"""GUI coordinates of every texel centre of the tile beside ``edge``."""
	tw, th = base.tw, base.th
	u = (np.arange(tw) + 0.5) / tw
	v = (np.arange(th) + 0.5) / th
	x = base.x + u * base.w
	y = base.y + v * base.h
	if edge == "art":
		pass
	elif edge == "left":
		x = x - base.w
	elif edge == "right":
		x = x + base.w
	elif edge == "top":
		y = y - base.h
	elif edge == "bottom":
		y = y + base.h
	return np.meshgrid(x, y)


class Strip:
	"""A polar resampling of a band around a disc's limb.

	Columns step along the limb by ``1 / density_x`` units of arc at the limb,
	rows step down in radius by ``1 / density_y`` units, starting ``above``
	units over the limb.
	"""

	def __init__(self, disc: Disc, theta0: float, theta1: float, above: float, below: float,
				 density_x: float, density_y: float, rho_ref: float | None = None) -> None:
		self.disc = disc
		self.theta0 = theta0
		# the along-limb step is set at rho_ref (default: the limb), so no row
		# of the strip is sampled more coarsely than the art
		self.dtheta = 1.0 / (density_x * (rho_ref if rho_ref else disc.r))
		self.rho0 = disc.r + above
		self.drho = 1.0 / density_y
		self.w = int(np.ceil((theta1 - theta0) / self.dtheta)) + 1
		self.h = int(np.ceil((above + below) / self.drho)) + 1
		cols = theta0 + np.arange(self.w) * self.dtheta
		rows = self.rho0 - np.arange(self.h) * self.drho
		self.theta, self.rho = np.meshgrid(cols, rows)
		self.x, self.y = disc.cartesian(self.theta, self.rho)

	def to_strip(self, x, y):
		theta, rho = self.disc.polar(x, y)
		return (self.rho0 - rho) / self.drho, (theta - self.theta0) / self.dtheta

	def height_above_limb(self):
		return self.rho - self.disc.r


def sample_strip(strip: Strip, image: np.ndarray, x, y, order=3):
	row, col = strip.to_strip(x, y)
	out = np.empty(x.shape + (image.shape[2],), np.float32)
	for c in range(image.shape[2]):
		out[..., c] = ndimage.map_coordinates(image[..., c], [row, col], order=order, mode="nearest")
	return np.clip(out, 0.0, 1.0)


# ---------------------------------------------------------------------------
# The main menu's Earth layer
# ---------------------------------------------------------------------------

# preymenu/background2.tga in guis/mainmenu.gui's Earth window.
EARTH_WINDOW = (0.0, 330.0, 640.0, 150.0)
# Fitted to the layer's solid edge (alpha >= 250): residual under 1.6 units.
EARTH_DISC = (688.07, 2061.94, 1687.67)


def earth_layer_tiles(archives: RetailArchives, quick: bool, log) -> dict[str, np.ndarray]:
	art = archives.image("guis/assets/menu/preymenu/background2.tga")
	window = Window(art, *EARTH_WINDOW)
	disc = Disc(*EARTH_DISC)
	dx, dy = window.density
	scale = 0.5 if quick else 1.0
	sx, sy = dx * scale, dy * scale  # strip texels per unit along and across the limb
	bottom = EARTH_WINDOW[1] + EARTH_WINDOW[3]

	# The glow above the limb is a flat colour under a radial alpha ramp that
	# the art keeps along the whole limb; continue the ramp measured beside the
	# right edge, where the right tile joins.
	heights = np.arange(-2.0, 200.0, 0.25)
	thetas = np.radians(np.linspace(-8.0, -1.8, 64))
	tt, hh = np.meshgrid(thetas, heights)
	gx, gy = disc.cartesian(tt, disc.r + hh)
	inside = window.inside(gx, gy, 2.0)
	samples = window.sample(gx, gy, order=1)
	with np.errstate(all="ignore"), warnings.catch_warnings():
		warnings.simplefilter("ignore", RuntimeWarning)
		ramp = np.nanmedian(np.where(inside, samples[..., 3], np.nan), axis=1)
		glow_colour = np.nanmedian(np.where(inside[..., None] & (hh[..., None] > 8), samples[..., :3], np.nan), axis=(0, 1))
	ramp = np.where(np.isnan(ramp), 0.0, ramp)
	ramp[heights > 120] = 0.0
	ramp = np.minimum.accumulate(np.where(heights >= 6.0, ramp, 1.0))  # monotone fade
	glow_from = 6.0  # units over the limb from which the ramp takes over

	def glow(height):
		out = np.empty(height.shape + (4,), np.float32)
		out[..., :3] = glow_colour
		out[..., 3] = np.interp(height, heights, ramp, left=1.0, right=0.0)
		return out


	translate_units = 10.0 * np.pi / 180.0 * disc.r  # 10 degrees of limb

	def solve(name, theta0, theta1, depth, hole_of, mirror, under=False):
		strip = Strip(disc, theta0, theta1, glow_from + 12.0, depth, sx, sy)
		height = strip.height_above_limb()
		known = window.inside(strip.x, strip.y, 1.5)
		canvas = window.sample(strip.x, strip.y)
		above = height > glow_from
		canvas[above & ~known] = glow(height)[above & ~known]
		fixed = known | above
		hole = hole_of(strip) & ~fixed
		canvas[~fixed] = 0.0
		log(f"  {name}: strip {strip.w}x{strip.h}, {int(hole.sum())} texels to fill")
		zones = np.where(height[:, 0] < -20.0, 0, 1)  # surface, then rim and glow
		below = surface_below(window, disc, strip.x, strip.y) if under else None
		done = continue_art(canvas, known, hole, mirror, (sy, sx), translate_units, zones=zones, below=below,
							copies=0 if under else 3)
		if os.environ.get("MENU_TILES_DEBUG"):
			dbg = Path(os.environ["MENU_TILES_DEBUG"])
			dbg.mkdir(parents=True, exist_ok=True)
			_rgb(done).save(dbg / f"{name}_done.png")
		return strip, done

	def angle(x, y):
		return float(disc.polar(np.array(float(x)), np.array(float(y)))[0])

	def depth_at(x, y):
		return float(disc.r - disc.polar(np.array(float(x)), np.array(float(y)))[1])

	right_edge = EARTH_WINDOW[0] + EARTH_WINDOW[2]
	# Right tile: the surface beside the art down to the window's foot. The
	# strip reaches back over all of the art so every painted cloud can serve.
	right_strip, right_done = solve(
		"earth_right", angle(-1.0, bottom), angle(2 * right_edge + 1.0, bottom + 1.0),
		depth_at(disc.cx, bottom) + 6.0,
		lambda s: s.x > right_edge - 1.0, "right")
	# Bottom tile, for screens taller than 4:3: the surface under the window.
	low = bottom + EARTH_WINDOW[3]
	bottom_strip, bottom_done = solve(
		"earth_bottom", angle(-1.0, low + 1.0), angle(right_edge + 1.0, bottom),
		depth_at(right_edge, low + 1.0) + 6.0,
		lambda s: s.y > bottom - 1.0, "left", under=True)

	tiles = {}
	for edge, strip, done in (("left", None, None), ("right", right_strip, right_done),
							  ("bottom", bottom_strip, bottom_done)):
		x, y = tile_grid(window, edge)
		h = disc.polar(x, y)[1] - disc.r
		out = glow(h)
		if strip is not None:
			row, col = strip.to_strip(x, y)
			in_strip = (row >= 0) & (row <= strip.h - 1) & (col >= 0) & (col <= strip.w - 1)
			surface = sample_strip(strip, done, x, y)
			blend = (np.clip((glow_from + 2.0 - h) / 2.0, 0.0, 1.0) * in_strip)[..., None]
			out = out * (1.0 - blend) + surface * blend
		tiles[edge] = out
	return tiles


# ---------------------------------------------------------------------------
# The flat painting
# ---------------------------------------------------------------------------

PAINTING_WINDOW = (0.0, 0.0, 640.0, 480.0)
# Fitted to the brightness edge of the limb outside the Sphere: residual 0.9.
PAINTING_DISC = (753.8, 2073.7, 1729.9)
# The Sphere and its sun flare, kept out of the exemplars.
PAINTING_SPHERE = (361.0, 216.0, 204.0, 196.0)


def painting_tiles(archives: RetailArchives, quick: bool, log) -> dict[str, np.ndarray]:
	art_image = archives.image("guis/assets/menu/background.tga")[..., :3]
	window = Window(art_image, *PAINTING_WINDOW)
	disc = Disc(*PAINTING_DISC)
	# Sample the strips at the art's finer density in both directions: the
	# painting is squeezed into its window, and the strips turn with the limb.
	density = max(window.density) * (0.5 if quick else 1.0)
	sphere_x, sphere_y, sphere_rx, sphere_ry = PAINTING_SPHERE
	translate_units = 10.0 * np.pi / 180.0 * disc.r
	ax, ay = tile_grid(window, "art")
	theta_art, rho_art = disc.polar(ax, ay)
	right, bottom = window.x + window.w, window.y + window.h
	holes = {
		"right": lambda s: s.x > right - 1.0,
		"left": lambda s: s.x < window.x + 1.0,
		"top": lambda s: s.y < window.y + 1.0,
		"bottom": lambda s: s.y > bottom - 1.0,
	}
	# which side of the art the hole lies on along each row of the strip
	directions = {"right": "right", "left": "left", "top": "right", "bottom": "left"}

	tiles = {}
	for edge in ("right", "left", "top", "bottom"):
		x, y = tile_grid(window, edge)
		theta_tile, rho_tile = disc.polar(x, y)
		theta0 = float(min(theta_tile.min(), theta_art.min()))
		theta1 = float(max(theta_tile.max(), theta_art.max()))
		rho_max = float(max(rho_tile.max(), rho_art.max())) + 2.0
		rho_min = float(min(rho_tile.min(), rho_art.min())) - 2.0
		strip = Strip(disc, theta0, theta1, rho_max - disc.r, disc.r - rho_min, density, density, rho_ref=rho_max)
		known = window.inside(strip.x, strip.y, 1.5)
		canvas = window.sample(strip.x, strip.y)
		canvas[~known] = 0.0
		height = strip.height_above_limb()[:, 0]
		# Earth is painted over the Sphere's foot: only the Sphere above the
		# limb is kept out of the exemplars
		sphere = ((strip.x - sphere_x) / sphere_rx) ** 2 + ((strip.y - sphere_y) / sphere_ry) ** 2 <= 1.0
		sphere &= height[:, None] > 2.0
		art = known & ~sphere
		hole = holes[edge](strip) & ~known
		# surface, rim and glow, open sky: the rim and the glow keep their
		# painted radius; surface and sky borrow only within themselves
		zones = np.where(height < -20.0, 0, np.where(height > 90.0, 2, 1))
		log(f"  painting {edge}: strip {strip.w}x{strip.h}, {int(hole.sum())} texels to fill")
		done = continue_art(canvas, art, hole, directions[edge], (density, density), translate_units,
							zones=zones, rise_units=(12.0, 24.0, 40.0, 80.0, 160.0, 320.0),
							below=surface_below(window, disc, strip.x, strip.y) if edge == "bottom" else None,
							copies=0 if edge == "bottom" else 3)
		if os.environ.get("MENU_TILES_DEBUG"):
			dbg = Path(os.environ["MENU_TILES_DEBUG"])
			dbg.mkdir(parents=True, exist_ok=True)
			_rgb(done).save(dbg / f"painting_{edge}_done.png")
		tiles[edge] = sample_strip(strip, done, x, y)
	return tiles


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_tga(path: Path, pixels: np.ndarray) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	data = np.clip(pixels * 255.0 + 0.5, 0, 255).astype(np.uint8)
	Image.fromarray(data).save(path, format="TGA", compression=None)


def _rgb(img: np.ndarray) -> Image.Image:
	return Image.fromarray(np.clip(img[..., :3] * 255 + 0.5, 0, 255).astype(np.uint8))


def _over_space(img: np.ndarray, size) -> Image.Image:
	rgba = Image.fromarray(np.clip(img * 255 + 0.5, 0, 255).astype(np.uint8)).resize(size, Image.LANCZOS)
	base = Image.new("RGBA", size, (5, 5, 8, 255))
	base.alpha_composite(rgba)
	return base.convert("RGB")


def preview_painting(out_dir: Path, archives: RetailArchives, tiles: dict) -> None:
	out_dir.mkdir(parents=True, exist_ok=True)
	art = archives.image("guis/assets/menu/background.tga")[..., :3]
	size = (640, 480)
	wide = Image.new("RGB", (640 * 3, 480))
	for i, img in enumerate((tiles["left"], art, tiles["right"])):
		wide.paste(_rgb(img).resize(size, Image.LANCZOS), (640 * i, 0))
	wide.save(out_dir / "painting_wide.png")
	tall = Image.new("RGB", (640, 480 * 3))
	for i, img in enumerate((tiles["top"], art, tiles["bottom"])):
		tall.paste(_rgb(img).resize(size, Image.LANCZOS), (0, 480 * i))
	tall.save(out_dir / "painting_tall.png")


def preview_earth(out_dir: Path, archives: RetailArchives, tiles: dict) -> None:
	"""The Earth window and its slices at twice GUI scale, over near-black."""
	out_dir.mkdir(parents=True, exist_ok=True)
	layer = archives.image("guis/assets/menu/preymenu/background2.tga")
	wide = np.concatenate([tiles["left"], layer, tiles["right"]], axis=1)
	_over_space(wide, (1280 * 3, 300)).save(out_dir / "earth_wide.png")
	tall = np.concatenate([layer, tiles["bottom"]], axis=0)
	_over_space(tall, (1280, 600)).save(out_dir / "earth_tall.png")


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
	parser.add_argument("--prey-base", help="retail Prey base directory holding the pk4s")
	parser.add_argument("--out", default=str(ROOT / "content" / "basepr" / "pak1"),
						help="root to write the tiles under (default: content/basepr/pak1)")
	parser.add_argument("--preview", help="directory for PNG composites")
	parser.add_argument("--quick", action="store_true", help="reduced quality, for iteration")
	parser.add_argument("--only", choices=("earth", "painting"), help="generate one set only")
	args = parser.parse_args()

	base = find_prey_base(args.prey_base)
	print(f"retail art: {base}")
	archives = RetailArchives(base)
	out = Path(args.out)
	log = lambda message: print(message, flush=True)

	earth = painting = None
	if args.only in (None, "earth"):
		log("Earth layer tiles")
		earth = earth_layer_tiles(archives, args.quick, log)
		for edge, img in earth.items():
			write_tga(out / "guis" / "assets" / "menu" / "preymenu" / f"earth_{edge}.tga", img)
	if args.only in (None, "painting"):
		log("Flat painting tiles")
		painting = painting_tiles(archives, args.quick, log)
		for edge, img in painting.items():
			write_tga(out / "guis" / "assets" / "menu" / f"background_{edge}.tga", img)
	if args.preview and earth is not None:
		preview_earth(Path(args.preview), archives, earth)
	if args.preview and painting is not None:
		preview_painting(Path(args.preview), archives, painting)
	return 0


if __name__ == "__main__":
	sys.exit(main())
