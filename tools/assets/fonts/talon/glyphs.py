"""Talon: openPREY's body face, drawn parametrically.

Talon takes Impact's condensed frame and very tall x-height and gives it the
squared bowls of the PREY wordmark, at a lighter stem than the traced retail
face it replaces (stem 0.19 of the capital height against 0.215). Every
glyph is built on a 1000-unit grid from the parts in ``geometry``.

``GLYPHS`` maps a code point to (body width, builder). A builder draws the
glyph's ink from x = 0 to the body width; the side bearings are added when the
face is assembled. ``MARKS`` holds the combining accents, drawn with their
foot (above marks) or head (below marks) on y = 0; the face builder seats them.
"""
from __future__ import annotations

from .geometry import (
	BIG, box, clip, diag, flip, mirror, move, poly, rect, ring, rotate, rrect, scale, stroke, turn, union,
)

# -- vertical metrics ----------------------------------------------------------
CAP = 700.0
XH = 560.0
ASC = 730.0
DESC = -150.0

# -- weights -------------------------------------------------------------------
S = 132.0    # capital stem: 0.189 of the capital height
T = 108.0    # capital horizontal
s = 124.0    # lower-case stem
t = 100.0    # lower-case horizontal

# -- corners -------------------------------------------------------------------
RO = 150.0   # capital bowl radius
RL = 130.0   # lower-case bowl radius
RS = 58.0    # soft turn

SB = 32.0    # side bearing
FW = 345.0   # tabular figure width
SPACE = 150.0

GLYPHS: dict[int, tuple[float, object]] = {}
MARKS: dict[int, object] = {}
# Glyphs that are another glyph unchanged (Cyrillic u is Latin y).
ALIASES: dict[int, int] = {}


def glyph(ch, width):
	cp = ord(ch) if isinstance(ch, str) else ch

	def deco(fn):
		GLYPHS[cp] = (float(width), fn)
		return fn

	return deco


def draw(ch):
	"""Geometry of an already defined glyph (to build another from it)."""
	return GLYPHS[ord(ch) if isinstance(ch, str) else ch][1]()


def width(ch):
	return GLYPHS[ord(ch) if isinstance(ch, str) else ch][0]


class M:
	"""The size a letter is drawn at: capital or lower case."""

	def __init__(self, h, st, hs, r):
		self.h, self.st, self.hs, self.r = h, st, hs, r


CAPS = M(CAP, S, T, RO)
LOWER = M(XH, s, t, RL)


# ---------------------------------------------------------------------------
# shared builders
# ---------------------------------------------------------------------------


def s_shape(w, h, st, hs, r, ap_top, ap_bot, upper_inset=0.0):
	"""Squared S: two stacked bowls sharing a straight spine."""
	ym = h * 0.52
	r1 = ring(upper_inset, ym - hs / 2, w - upper_inset * 0.3, h, r * 0.9, st, hs)
	r2 = ring(0, 0, w, ym + hs / 2, r, st, hs)
	r1 = r1.difference(rect(w / 2, ym - hs / 2 - 1, w + 1, ap_top))
	r2 = r2.difference(rect(-1, ap_bot, w / 2, ym + hs / 2 + 1))
	return union(r1, r2)


def c_shape(w, h, st, hs, r, ap_lo, ap_hi):
	return ring(0, 0, w, h, r, st, hs).difference(rect(w / 2, ap_lo, w + 1, ap_hi))


def arch(x0, x1, top, st, hs, r, square_left=True):
	"""The n shoulder: a bowl's upper half on straight legs."""
	g = clip(ring(x0, -BIG / 10, x1, top, r, st, hs), -BIG, 0, BIG, BIG)
	if square_left:
		g = union(g, rect(x0, 0, x0 + st, top))
	return g


def cup(x0, x1, bot, top, st, hs, r):
	return clip(ring(x0, bot, x1, top + BIG / 10, r, st, hs), -BIG, -BIG, BIG, top)


def dot(x, y, size, r=None):
	return rect(x, y, x + size, y + size, r if r is not None else size * 0.2)


def k_arms(x_stem, w, h, st, join=0.3):
	"""K's arm and leg, branching from a stem whose right edge is x_stem."""
	p0, p1 = (x_stem - st * 0.4, h * join), (w - st * 0.5, h)
	f = 0.4
	pj = (p0[0] + f * (p1[0] - p0[0]), p0[1] + f * (p1[1] - p0[1]))
	arm = stroke(p0, p1, st * 0.94, 0, h, x_stem - st * 0.5, w)
	leg = stroke(pj, (w - st * 0.52, 0), st, 0, pj[1] + 60, x_stem - st * 0.5, w)
	return clip(union(arm, leg), 0, 0, w, h)


def tail_down(x0, x1, depth):
	"""A descender spur under a baseline bar (Cyrillic de, tse, shcha)."""
	return rect(x0, depth, x1, 1, (0, 0, RS * 0.5, 0))


def chevron(w, h, mid, st):
	"""An angle bracket pointing left, cut flat top and bottom."""
	up = stroke((w, mid + h / 2), (st * 0.3, mid), st, mid, mid + h / 2, 0, w)
	dn = stroke((w, mid - h / 2), (st * 0.3, mid), st, mid - h / 2, mid, 0, w)
	return clip(union(up, dn), 0, mid - h / 2, w, mid + h / 2)


# -- letter builders shared by the two cases --------------------------------


def b_shape(w, m, waist=0.535):
	h, st, hs, r = m.h, m.st, m.hs, m.r
	ym = h * waist
	up = ring(0, ym - hs / 2, w - w * 0.06, h, r * 0.85, st, hs, square=("tl", "bl"))
	lo = ring(0, 0, w, ym + hs / 2, r * 0.9, st, hs, square=("tl", "bl"))
	return union(up, lo, rect(0, 0, st, h, (RS, 0, 0, RS)))


def e_bars(w, m, mid=0.446):
	h, st, hs = m.h, m.st, m.hs
	return union(
		rect(0, 0, st, h, (RS, 0, 0, RS)),
		rect(0, h - hs, w, h, (RS, 0, 0, 0)),
		rect(0, 0, w, hs, (0, 0, 0, RS)),
		rect(0, h * mid, w - w * 0.1, h * mid + hs * 0.95),
	)


def gamma(w, m):
	return union(rect(0, 0, m.st, m.h, (RS, 0, 0, 0)), rect(0, m.h - m.hs, w, m.h, (RS, 0, 0, 0)))


def pi_shape(w, m):
	h, st, hs = m.h, m.st, m.hs
	return union(rect(0, 0, st, h, (RS, 0, 0, 0)), rect(w - st, 0, w, h, (0, RS, 0, 0)), rect(0, h - hs, w, h, (RS, RS, 0, 0)))


def h_shape(w, m):
	h, st, hs = m.h, m.st, m.hs
	return union(rect(0, 0, st, h), rect(w - st, 0, w, h), rect(0, h * 0.446, w, h * 0.446 + hs * 0.95))


def n_reversed(w, m):
	"""Cyrillic I: N with its diagonal rising."""
	h, st = m.h, m.st
	d = stroke((st * 0.5, 0), (w - st * 0.5, h), st * 0.98, 0, h, st * 0.5, w - st * 0.5)
	return union(rect(0, 0, st, h), rect(w - st, 0, w, h), d)


def m_shape(w, m, vy=None):
	h, st = m.h, m.st
	dh = st * 1.02
	vy = h * 0.215 if vy is None else vy
	left = poly([(st - dh * 0.55, h), (st + dh * 0.45, h), (w / 2 + dh / 2, vy), (w / 2 - dh / 2, vy)])
	return clip(union(rect(0, 0, st, h), rect(w - st, 0, w, h), left, mirror(left, w)), 0, 0, w, h)


def t_shape(w, m):
	return union(rect(0, m.h - m.hs, w, m.h), rect(w / 2 - m.st / 2, 0, w / 2 + m.st / 2, m.h))


def de_shape(w, m, depth):
	"""Cyrillic De: a house on a baseline bar with two descending feet."""
	h, st, hs = m.h, m.st, m.hs
	x0, x1 = w * 0.13, w - w * 0.1
	return union(
		rect(x0, 0, x0 + st * 0.95, h, (RS, 0, 0, 0)), rect(x1 - st, 0, x1, h),
		rect(x0, h - hs, x1, h, (RS, 0, 0, 0)), rect(0, 0, w, hs),
		tail_down(0, st * 0.85, depth), tail_down(w - st * 0.85, w, depth),
	)


def el_shape(w, m):
	"""Cyrillic El: a right stem, a top bar, and a left leg that kicks out."""
	h, st, hs = m.h, m.st, m.hs
	xl = w * 0.16
	return union(
		rect(w - st, 0, w, h), rect(xl, h - hs, w, h, (RS, 0, 0, 0)),
		rect(xl, hs * 0.5, xl + st, h, (RS, 0, 0, 0)), rect(0, 0, xl + st, hs * 0.95, (0, 0, RS, 0)),
	)


def zhe_shape(w, m):
	h, st = m.h, m.st
	half = (w + st) / 2
	right = move(k_arms(st, half, h, st, join=0.42), half - st, 0)
	right = union(right, rect(w / 2 - st / 2, 0, w / 2 + st / 2, h))
	return union(right, mirror(right, w))


def ze_shape(w, m):
	"""Cyrillic Ze: the 3 of the figures at letter size."""
	h, st, hs, r = m.h, m.st, m.hs, m.r
	ym = h * 0.52
	r1 = ring(w * 0.03, ym - hs / 2, w - w * 0.02, h, r * 0.9, st, hs)
	r2 = ring(0, 0, w, ym + hs / 2, r, st, hs)
	ap_top, ap_bot = h - h * 0.27, h * 0.27
	g = union(r1.difference(rect(-1, ym - hs / 2 - 1, st + w * 0.03 + 1, ap_top)), r2.difference(rect(-1, ap_bot, st + 1, ym + hs / 2 + 1)))
	return g.difference(rect(-1, ym - hs / 2 - 1, w * 0.3, ym + hs / 2 + 1))


def u_cyr(w, m):
	"""Cyrillic U: a long right diagonal to the baseline, met by a short left arm."""
	h, st = m.h, m.st
	xr0, xr1 = w - st * 0.5, w * 0.22
	right = diag(xr0, xr1, st, h, 0)
	yj = h * 0.36
	xj = xr0 + (xr1 - xr0) * (h - yj) / h
	left = diag(st * 0.5, xj, st * 0.95, h, yj - 40)
	return clip(union(right, clip(left, -BIG, yj, BIG, BIG)), 0, 0, w, h)


def ef_shape(w, m, top, bottom):
	h, st, hs, r = m.h, m.st, m.hs, m.r
	bowl = ring(0, h * 0.14, w, h * 0.86, r * 1.0, st * 0.95, hs * 0.95)
	return union(bowl, rect(w / 2 - st / 2, bottom, w / 2 + st / 2, top))


def tse_shape(w, m, depth):
	h, st, hs = m.h, m.st, m.hs
	x1 = w - st * 0.55
	return union(rect(0, 0, st, h), rect(x1 - st, 0, x1, h), rect(0, 0, w, hs, (0, 0, 0, RS)), tail_down(w - st * 0.8, w, depth))


def che_shape(w, m):
	h, st, hs, r = m.h, m.st, m.hs, m.r
	yb = h * 0.36
	return union(clip(cup(0, w, yb, h, st, hs, r), -BIG, yb, BIG, h), rect(w - st, 0, w, h))


def sha_shape(w, m, depth=None):
	h, st, hs = m.h, m.st, m.hs
	x1 = w if depth is None else w - st * 0.55
	g = union(rect(0, 0, st, h), rect((x1 - st) / 2, 0, (x1 + st) / 2, h), rect(x1 - st, 0, x1, h), rect(0, 0, x1, hs, (0, 0, 0, RS)))
	if depth is not None:
		g = union(g, rect(0, 0, w, hs, (0, 0, 0, RS)), tail_down(w - st * 0.8, w, depth))
	return g


def soft_sign(w, m, x0=0.0, bowl=0.57):
	h, st, hs, r = m.h, m.st, m.hs, m.r
	top = h * bowl
	return union(rect(x0, 0, x0 + st, h), ring(x0, 0, w, top, (0, r * 0.9, r * 0.9, 0), st, hs, square=("tl", "bl")))


def e_rev(w, m):
	"""Cyrillic E: a C turned round with a bar."""
	h, st, hs, r = m.h, m.st, m.hs, m.r
	c = mirror(c_shape(w, h, st, hs, r, h * 0.364, h * 0.636), w)
	return union(c, rect(w * 0.32, h * 0.446, w, h * 0.446 + hs * 0.9))


def yu_shape(w, m):
	h, st, hs, r = m.h, m.st, m.hs, m.r
	xo = st + w * 0.12
	return union(rect(0, 0, st, h), rect(st - 1, h * 0.446, xo + st, h * 0.446 + hs * 0.95), ring(xo, 0, w, h, r * 1.15, st, hs))


def r_shape(w, m, yb=None):
	h, st, hs, r = m.h, m.st, m.hs, m.r
	yb = h * 0.443 if yb is None else yb
	bowl = ring(0, yb, w - w * 0.02, h, (RS, r, r * 0.9, 0), st, hs)
	leg = stroke((w * 0.36, yb + hs * 0.5), (w - st * 0.5, 0), st * 1.02, 0, yb + hs * 0.6, st, w)
	return union(bowl, rect(0, 0, st, h, (RS, 0, 0, 0)), leg)


def ya_shape(w, m):
	return mirror(r_shape(w, m), w)


# ---------------------------------------------------------------------------
# capitals
# ---------------------------------------------------------------------------


@glyph("A", 387)
def _A():
	w = 387
	apex = S * 1.05
	left = diag(w / 2 - apex / 2 + S * 0.35, S * 0.48, S, CAP, 0)
	right = diag(w / 2 + apex / 2 - S * 0.35, w - S * 0.48, S, CAP, 0)
	top = rect(w / 2 - apex / 2 - 10, CAP - T, w / 2 + apex / 2 + 10, CAP)
	bar = rect(60, 150, w - 60, 150 + T * 0.92)
	return clip(union(left, right, top, bar), 0, 0, w, CAP)


@glyph("B", 369)
def _B():
	return b_shape(369, CAPS)


@glyph("C", 356)
def _C():
	return c_shape(356, CAP, S, T, RO, 255, 445)


@glyph("D", 374)
def _D():
	return ring(0, 0, 374, CAP, (RS * 0.6, RO * 1.05, RO * 1.05, RS * 0.6), S, T)


@glyph("E", 310)
def _E():
	return e_bars(310, CAPS)


@glyph("F", 302)
def _F():
	w = 302
	return union(rect(0, 0, S, CAP, (RS, 0, 0, 0)), rect(0, CAP - T, w, CAP, (RS, 0, 0, 0)), rect(0, 300, w - 32, 300 + T * 0.95))


@glyph("G", 364)
def _G():
	w = 364
	g = ring(0, 0, w, CAP, RO, S, T).difference(rect(w / 2, 255, w + 1, 445))
	return union(g, rect(w * 0.48, 300, w, 300 + T * 0.95), rect(w - S, 120, w, 300 + T * 0.95))


@glyph("H", 360)
def _H():
	return h_shape(360, CAPS)


@glyph("I", S)
def _I():
	return rect(0, 0, S, CAP)


@glyph("J", 315)
def _J():
	w = 315
	return union(cup(0, w, 0, CAP, S, T, RO).difference(rect(-1, 215, S, BIG)), rect(w - S, 200, w, CAP))


@glyph("K", 369)
def _K():
	w = 369
	return union(rect(0, 0, S, CAP), k_arms(S, w, CAP, S))


@glyph("L", 297)
def _L():
	return union(rect(0, 0, S, CAP, (0, 0, 0, RS)), rect(0, 0, 297, T, (0, 0, 0, RS)))


@glyph("M", 486)
def _M():
	return m_shape(486, CAPS, 150)


@glyph("N", 378)
def _N():
	w = 378
	d = stroke((S * 0.5, CAP), (w - S * 0.5, 0), S * 0.98, 0, CAP, S * 0.5, w - S * 0.5)
	return union(rect(0, 0, S, CAP), rect(w - S, 0, w, CAP), d)


@glyph("O", 378)
def _O():
	return ring(0, 0, 378, CAP, RO * 1.3, S, T)


@glyph("P", 356)
def _P():
	w = 356
	return union(ring(0, 300, w, CAP, (RS, RO, RO * 0.9, 0), S, T), rect(0, 0, S, CAP, (RS, 0, 0, 0)))


@glyph("Q", 378)
def _Q():
	w = 378
	tail = stroke((w * 0.6, 150), (w + 5, -40), S * 0.85, -80, 200, 0, w + 10)
	return union(ring(0, 0, w, CAP, RO * 1.3, S, T), tail)


@glyph("R", 369)
def _R():
	return r_shape(369, CAPS, 310)


@glyph("S", 351)
def _S():
	return s_shape(351, CAP, S, T, RO, 505, 195, upper_inset=8)


@glyph("T", 342)
def _T():
	return t_shape(342, CAPS)


@glyph("U", 364)
def _U():
	return cup(0, 364, 0, CAP, S, T, RO)


@glyph("V", 378)
def _V():
	w = 378
	return clip(union(diag(S * 0.5, w / 2 - S * 0.08, S, CAP, 0), diag(w - S * 0.5, w / 2 + S * 0.08, S, CAP, 0)), 0, 0, w, CAP)


@glyph("W", 531)
def _W():
	w = 531
	d = S * 0.8
	return clip(union(
		diag(d * 0.5, 160, d * 1.05, CAP, 0), diag(w / 2, 160, d * 0.8, CAP * 0.84, 0),
		diag(w / 2, w - 160, d * 0.8, CAP * 0.84, 0), diag(w - d * 0.5, w - 160, d * 1.05, CAP, 0),
	), 0, 0, w, CAP)


@glyph("X", 369)
def _X():
	w = 369
	return clip(union(diag(S * 0.48, w - S * 0.48, S * 0.98, CAP, 0), diag(w - S * 0.48, S * 0.48, S * 0.98, CAP, 0)), 0, 0, w, CAP)


@glyph("Y", 378)
def _Y():
	w = 378
	yj = 300
	arms = clip(union(diag(S * 0.5, w / 2, S * 0.98, CAP, yj - 60), diag(w - S * 0.5, w / 2, S * 0.98, CAP, yj - 60)), 0, yj, w, CAP)
	return union(arms, rect(w / 2 - S / 2, 0, w / 2 + S / 2, yj + 40))


@glyph("Z", 342)
def _Z():
	w = 342
	d = stroke((w - S * 0.6, CAP - T), (S * 0.6, T), S * 1.05, T - 5, CAP - T + 5, 0, w)
	return union(rect(0, CAP - T, w, CAP), rect(0, 0, w, T), d)


# ---------------------------------------------------------------------------
# lower case
# ---------------------------------------------------------------------------


@glyph("a", 338)
def _a():
	w = 338
	hood = arch(0, w, XH, s, t, RL, square_left=False).difference(rect(-1, -1, s, XH - 175))
	bowl = ring(0, 0, w, 318, RL * 0.85, s, t * 0.95, square=("tr", "br"))
	return union(hood, bowl, rect(w - s, 0, w, XH - RL))


@glyph("b", 346)
def _b():
	return union(ring(0, 0, 346, XH, RL, s, t, square=("tl", "bl")), rect(0, 0, s, ASC))


@glyph("c", 320)
def _c():
	return c_shape(320, XH, s, t, RL, 190, 372)


@glyph("d", 346)
def _d():
	return mirror(_b(), 346)


@glyph("e", 338)
def _e():
	w = 338
	g = ring(0, 0, w, XH, RL, s, t).difference(rect(w - s, 165, w + 1, 250))
	return union(g, rect(0, 250, w, 250 + t * 0.92))


@glyph("f", 275)
def _f():
	w = 275
	x0 = 32
	hook = clip(ring(x0, -400, w + 300, ASC, (RL * 0.9, 0, 0, 0), s, t), 0, 0, w, ASC)
	return union(hook, rect(0, XH - t, w - 15, XH))


@glyph("g", 346)
def _g():
	w = 346
	bowl = ring(0, 0, w, XH, RL, s, t, square=("tr", "br"))
	hook = cup(0, w, DESC, 40, s, t * 0.92, RL * 0.85).difference(rect(-1, DESC + 105, s, BIG))
	return union(bowl, hook, rect(w - s, DESC + RL * 0.85, w, XH))


@glyph("h", 342)
def _h():
	return union(arch(0, 342, XH, s, t, RL), rect(0, 0, s, ASC))


@glyph("i", s)
def _i():
	return union(rect(0, 0, s, XH), dot(0, ASC - s, s, 14))


@glyph("j", 210)
def _j():
	w = 210
	hook = clip(ring(-300, DESC, w, XH + 400, (0, 0, RL * 0.85, 0), s, t * 0.92), -40, DESC, w, XH)
	return union(hook, dot(w - s, ASC - s, s, 14))


@glyph("k", 333)
def _k():
	w = 333
	return union(rect(0, 0, s, ASC), k_arms(s, w, XH, s))


@glyph("l", 205)
def _l():
	w = 205
	return clip(ring(0, 0, w + 300, ASC + 300, (0, 0, 0, RL * 0.9), s, t), 0, 0, w, ASC)


@glyph("m", 518)
def _m():
	w = 518
	half = (w + s) / 2
	return union(arch(0, half, XH, s, t, RL * 0.9), arch(half - s, w, XH, s, t, RL * 0.9, square_left=False), rect(0, 0, s, XH))


@glyph("n", 342)
def _n():
	return arch(0, 342, XH, s, t, RL)


@glyph("o", 346)
def _o():
	return ring(0, 0, 346, XH, RL, s, t)


@glyph("p", 346)
def _p():
	return union(ring(0, 0, 346, XH, RL, s, t, square=("tl", "bl")), rect(0, DESC, s, XH))


@glyph("q", 346)
def _q():
	return mirror(_p(), 346)


@glyph("r", 285)
def _r():
	w = 285
	sh = clip(ring(0, -400, w, XH, (0, RL * 0.95, 0, 0), s * 0.92, t), -BIG, XH - 170, BIG, BIG)
	sh = sh.difference(rect(w - s * 0.92, -1, w + 1, XH - 150))
	return union(sh, rect(0, 0, s, XH))


@glyph("s", 315)
def _s():
	return s_shape(315, XH, s, t, RL, 405, 155, upper_inset=6)


@glyph("t", 275)
def _t():
	w = 275
	x0 = 32
	foot = clip(ring(x0, 0, w + 300, XH + 400, (0, 0, 0, RL * 0.9), s, t), x0, 0, w, XH + 120)
	return union(foot, rect(0, XH - t, w - 15, XH))


@glyph("u", 342)
def _u():
	return mirror(turn(arch(0, 342, XH, s, t, RL), 342, XH), 342)


@glyph("v", 342)
def _v():
	w = 342
	return clip(union(diag(s * 0.5, w / 2 - s * 0.08, s, XH, 0), diag(w - s * 0.5, w / 2 + s * 0.08, s, XH, 0)), 0, 0, w, XH)


@glyph("w", 500)
def _w():
	w = 500
	d = s * 0.8
	return clip(union(
		diag(d * 0.5, 150, d * 1.05, XH, 0), diag(w / 2, 150, d * 0.8, XH * 0.84, 0),
		diag(w / 2, w - 150, d * 0.8, XH * 0.84, 0), diag(w - d * 0.5, w - 150, d * 1.05, XH, 0),
	), 0, 0, w, XH)


@glyph("x", 338)
def _x():
	w = 338
	return clip(union(diag(s * 0.48, w - s * 0.48, s * 0.98, XH, 0), diag(w - s * 0.48, s * 0.48, s * 0.98, XH, 0)), 0, 0, w, XH)


@glyph("y", 342)
def _y():
	w = 342
	left = clip(diag(s * 0.5, w / 2 - s * 0.05, s, XH, 0), 0, 0, w, XH)
	xr0, xr1 = w - s * 0.5, w / 2 + s * 0.05
	slope = (xr1 - xr0) / (0 - XH)
	right = stroke((xr0, XH), (xr0 + slope * (DESC - XH), DESC), s, DESC, XH, -BIG, w)
	return clip(union(left, right), -60, DESC, w, XH)


@glyph("z", 310)
def _z():
	w = 310
	d = stroke((w - s * 0.6, XH - t), (s * 0.6, t), s * 1.05, t - 5, XH - t + 5, 0, w)
	return union(rect(0, XH - t, w, XH), rect(0, 0, w, t), d)


# ---------------------------------------------------------------------------
# figures (tabular)
# ---------------------------------------------------------------------------


@glyph("0", FW)
def _0():
	return ring(0, 0, FW, CAP, RO * 0.62, S, T)


@glyph("1", FW)
def _1():
	x1 = FW * 0.5 + S * 0.5 + 25
	flag = stroke((x1 - S, CAP - T / 2), (x1 - S - 135, CAP - 150), T, CAP - 205, CAP, 20, x1)
	return union(rect(x1 - S, 0, x1, CAP), flag)


@glyph("2", FW)
def _2():
	w = FW
	ym = CAP * 0.52
	up = ring(8, ym - T / 2, w, CAP, RO * 0.9, S, T).difference(rect(-1, ym - T / 2 - 1, w / 2, CAP - 195))
	lo = ring(0, 0, w, ym + T / 2, (RO, RO, 0, RO), S, T).difference(rect(w / 2, T, w + 1, ym + T / 2 + 1))
	return union(up, lo, rect(w / 2, 0, w, T))


@glyph("3", FW)
def _3():
	w = FW
	ym = CAP * 0.52
	r1 = ring(10, ym - T / 2, w - 6, CAP, RO * 0.9, S, T)
	r2 = ring(0, 0, w, ym + T / 2, RO, S, T)
	g = union(r1.difference(rect(-1, ym - T / 2 - 1, S + 10, CAP - 195)), r2.difference(rect(-1, 195, S, ym + T / 2 + 1)))
	return g.difference(rect(-1, ym - T / 2 - 1, w * 0.3, ym + T / 2 + 1))


@glyph("4", FW)
def _4():
	w = FW
	xs = w - S - 15
	d = stroke((xs + S * 0.3, CAP), (S * 0.45, 210 + T), S * 0.95, 210, CAP, 0, xs + S)
	return clip(union(rect(xs, 0, xs + S, CAP), rect(0, 210, w, 210 + T), d), 0, 0, w, CAP)


@glyph("5", FW)
def _5():
	w = FW
	ym = CAP * 0.56
	lo = ring(0, 0, w, ym + T / 2, RO, S, T, square=("tl",)).difference(rect(-1, 195, S, ym - T / 2))
	return union(lo, rect(0, ym - T / 2, S, CAP), rect(0, CAP - T, w - 8, CAP))


@glyph("6", FW)
def _6():
	w = FW
	ym = CAP * 0.56
	lo = ring(0, 0, w, ym + T / 2, RO, S, T)
	up = ring(0, ym - T / 2, w, CAP, RO * 0.95, S, T).difference(rect(S, ym - T / 2 - 1, w + 1, CAP - 195))
	return union(lo, up, rect(0, ym - T / 2 - 20, S, CAP - RO))


@glyph("7", FW)
def _7():
	w = FW
	d = stroke((w - S * 0.55, CAP - T), (w * 0.34, 0), S * 1.02, 0, CAP - T + 5, 0, w)
	return union(rect(0, CAP - T, w, CAP), d)


@glyph("8", FW)
def _8():
	w = FW
	ym = CAP * 0.53
	return union(ring(14, ym - T / 2, w - 14, CAP, RO * 0.85, S, T), ring(0, 0, w, ym + T / 2, RO, S, T))


@glyph("9", FW)
def _9():
	return turn(_6(), FW, CAP)


# ---------------------------------------------------------------------------
# punctuation and symbols (ASCII)
# ---------------------------------------------------------------------------


@glyph(" ", SPACE)
def _space():
	return None


@glyph(".", S)
def _period():
	return dot(0, 0, S, 18)


def comma_shape(x=0.0, y=0.0):
	tail = clip(poly([(S * 0.25, 0), (S, 0), (S * 0.55, -150), (0, -150)]), 0, -150, S, 10)
	return move(union(dot(0, 0, S, 18), tail), x, y)


@glyph(",", S)
def _comma():
	return comma_shape()


@glyph(":", S)
def _colon():
	return union(dot(0, 0, S, 18), dot(0, XH - S, S, 18))


@glyph(";", S)
def _semicolon():
	return union(comma_shape(), dot(0, XH - S, S, 18))


@glyph("!", S)
def _excl():
	return union(rect(0, 210, S, CAP), dot(0, 0, S, 18))


@glyph("?", 324)
def _quest():
	w = 324
	ym = 380
	hood = ring(0, ym - T / 2, w, CAP, RO * 0.9, S, T).difference(rect(-1, ym - T / 2 - 1, S, CAP - 190))
	hood = hood.difference(rect(-1, ym - T / 2 - 1, w * 0.36, ym + T / 2 + 1))
	return union(hood, rect(w * 0.36, 210, w * 0.36 + S, ym + T / 2), dot(w * 0.36, 0, S, 18))


@glyph("-", 260)
def _hyphen():
	return rect(0, 255, 260, 255 + T)


@glyph("_", 360)
def _under():
	return rect(0, -150, 360, -150 + T * 0.9)


@glyph("/", 297)
def _slash():
	return clip(diag(297 - S * 0.45, S * 0.45, S * 0.9, CAP, DESC + 20), 0, DESC + 20, 297, CAP)


@glyph("\\", 297)
def _bslash():
	return mirror(_slash(), 297)


@glyph("'", S)
def _quote():
	return rect(0, CAP - 230, S * 0.9, CAP)


@glyph('"', 290)
def _dquote():
	return union(rect(0, CAP - 230, S * 0.9, CAP), rect(290 - S * 0.9, CAP - 230, 290, CAP))


@glyph("(", 210)
def _lparen():
	g = clip(ring(0, DESC + 20, 500, ASC, RO, S * 0.95, T), -1, -BIG, 210, BIG)
	return g.difference(rect(S * 0.95 + 1, DESC + 20 + T + 1, BIG, ASC - T - 1)).difference(rect(150, -BIG, BIG, BIG))


@glyph(")", 210)
def _rparen():
	return mirror(_lparen(), 210)


@glyph("[", 210)
def _lbrack():
	return union(rect(0, DESC + 20, S * 0.95, ASC), rect(0, DESC + 20, 210, DESC + 20 + T), rect(0, ASC - T, 210, ASC))


@glyph("]", 210)
def _rbrack():
	return mirror(_lbrack(), 210)


@glyph("{", 250)
def _lbrace():
	w = 250
	xs = 70
	st = S * 0.9
	mid = (ASC + DESC + 20) / 2
	return union(
		rect(xs, mid + T / 2, xs + st, ASC, (RS, 0, 0, 0)), rect(xs, ASC - T, w, ASC, (RS, 0, 0, 0)),
		rect(xs, DESC + 20, xs + st, mid - T / 2, (0, 0, 0, RS)), rect(xs, DESC + 20, w, DESC + 20 + T, (0, 0, 0, RS)),
		rect(0, mid - T / 2, xs + st, mid + T / 2),
	)


@glyph("}", 250)
def _rbrace():
	return mirror(_lbrace(), 250)


@glyph("|", S)
def _bar():
	return rect(0, DESC + 20, S * 0.85, ASC)


@glyph("+", 342)
def _plus():
	w = 342
	return union(rect(0, 255, w, 255 + T), rect(w / 2 - S / 2, 120, w / 2 + S / 2, 390 + T))


@glyph("=", 342)
def _equal():
	return union(rect(0, 160, 342, 160 + T), rect(0, 350, 342, 350 + T))


@glyph("<", 324)
def _less():
	return chevron(324, 460, 309, T * 1.1)


@glyph(">", 324)
def _greater():
	return mirror(_less(), 324)


@glyph("^", 342)
def _caret():
	w = 342
	apex = S * 0.9
	left = diag(w / 2 - apex / 2 + S * 0.3, S * 0.42, S * 0.9, CAP, CAP * 0.42)
	right = diag(w / 2 + apex / 2 - S * 0.3, w - S * 0.42, S * 0.9, CAP, CAP * 0.42)
	return clip(union(left, right), 0, CAP * 0.42, w, CAP)


@glyph("~", 342)
def _tilde():
	return tilde_shape(342, 300, 230, T * 0.95)


def tilde_shape(w, mid, h, th):
	"""A squared wave: a flat-topped rise, a slope, a flat-bottomed fall."""
	lo, hi = mid - h / 2, mid + h / 2
	left = ring(0, lo, w * 0.56, hi, (h * 0.45, h * 0.45, 0, 0), th, th * 0.95)
	left = clip(left, 0, lo, w * 0.56, hi).difference(rect(w * 0.56 - th, lo - 1, w, mid))
	left = left.difference(rect(-1, lo - 1, th, lo + th * 0.1))
	right = turn(left, w, 2 * mid)
	return union(left, right)


@glyph("`", 220)
def _grave_spacing():
	return move(grave_shape(), 10, CAP - 170)


@glyph("$", 351)
def _dollar():
	w = 351
	return union(_S(), rect(w / 2 - S * 0.36, -90, w / 2 + S * 0.36, CAP + 90))


@glyph("#", 430)
def _hash():
	w = 430
	return clip(union(
		diag(195, 110, S * 0.78, CAP - 40, 0), diag(w - 110, w - 195, S * 0.78, CAP - 40, 0),
		rect(20, 195, w, 195 + T * 0.88), rect(0, 425, w - 20, 425 + T * 0.88),
	), 0, 0, w, CAP - 40)


@glyph("*", 320)
def _star():
	c = (160, CAP - 150)
	arm = rect(160 - T * 0.48, CAP - 150, 160 + T * 0.48, CAP)
	return union(arm, *[rotate(arm, a, c) for a in (72, 144, 216, 288)])


@glyph("%", 540)
def _percent():
	w = 540
	a = ring(0, 380, 200, CAP, 70, S * 0.72, T * 0.72)
	b = ring(w - 200, 0, w, 320, 70, S * 0.72, T * 0.72)
	d = clip(diag(w - 140, 140, S * 0.78, CAP, 0), 0, 0, w, CAP)
	return union(a, b, d)


@glyph("&", 420)
def _amp():
	w = 420
	up = ring(34, 400, 260, CAP, RO * 0.7, S * 0.9, T * 0.9)
	lo = ring(0, 0, 300, 430, (RO * 0.9, 0, RO * 0.9, RO * 0.9), S, T).difference(rect(S, 150, BIG, BIG))
	leg = stroke((34 + S * 0.45, 445), (w - S * 0.5, 0), S * 0.98, 0, 460, 0, w)
	return union(up, lo, leg, rect(250, 245, w, 245 + T * 0.9))


@glyph("@", 600)
def _at():
	w = 600
	st, hs = S * 0.72, T * 0.72
	outer = ring(0, -120, w, CAP, RO * 1.05, st, hs).difference(rect(w * 0.6, -121, w + 1, 40))
	inner = ring(150, 80, 400, 440, 80, st, hs)
	return union(outer, inner, rect(400 - st, 40, 400, 440), rect(400 - st, 40, w, 40 + hs), rect(w - st, 40, w, 330))


# ---------------------------------------------------------------------------
# marks (drawn for lower case; capitals use a flatter copy)
# ---------------------------------------------------------------------------

MARK_STROKE = 92.0


def acute_shape():
	return clip(stroke((40, 0), (150, 170), MARK_STROKE, 0, 170), -BIG, 0, BIG, 170)


def grave_shape():
	return mirror(acute_shape(), 190)


def circumflex_shape():
	w = 250
	apex = MARK_STROKE
	left = diag(w / 2 - apex * 0.3, MARK_STROKE * 0.42, MARK_STROKE, 160, 0)
	right = diag(w / 2 + apex * 0.3, w - MARK_STROKE * 0.42, MARK_STROKE, 160, 0)
	return clip(union(left, right), 0, 0, w, 160)


def mark(cp):
	def deco(fn):
		MARKS[cp] = fn
		return fn

	return deco


@mark(0x0300)
def _m_grave():
	return grave_shape()


@mark(0x0301)
def _m_acute():
	return acute_shape()


@mark(0x0302)
def _m_circumflex():
	return circumflex_shape()


@mark(0x030C)
def _m_caron():
	return flip(circumflex_shape(), 80)


@mark(0x0303)
def _m_tilde():
	return tilde_shape(260, 75, 150, 80)


@mark(0x0308)
def _m_diaeresis():
	d = s * 0.95
	return union(dot(0, 0, d, 14), dot(d + 70, 0, d, 14))


@mark(0x0307)
def _m_dot():
	return dot(0, 0, s * 0.95, 14)


@mark(0x030A)
def _m_ring():
	return ring(0, 0, 190, 180, 72, 56, 52)


@mark(0x0304)
def _m_macron():
	return rect(0, 0, 240, 82)


@mark(0x0306)
def _m_breve():
	return cup(0, 250, 0, 150, 74, 70, 70)


@mark(0x030B)
def _m_double_acute():
	a = acute_shape()
	return union(a, move(a, 120, 0))


@mark(0x0327)
def _m_cedilla():
	# A short neck dropping into a squared hook that turns back left.
	hook = clip(ring(0, -190, 180, -40, (0, 60, 60, 0), 70, 56), 0, -190, 180, -40)
	hook = hook.difference(rect(-1, -190 + 56, 70, -40 + 1))
	return union(hook, rect(40, -60, 110, 0))


@mark(0x0328)
def _m_ogonek():
	# Hangs from the letter's foot, curls down and to the right.
	hook = clip(ring(0, -170, 190, 80, (0, 0, 0, 70), 74, 64), 0, -170, 190, 0)
	return hook.difference(rect(74, -170 + 64, BIG, BIG))


# ---------------------------------------------------------------------------
# Latin-1 and Windows-1252
# ---------------------------------------------------------------------------


@glyph(0x00A1, S)  # inverted exclamation
def _iexcl():
	return move(turn(_excl(), S, CAP), 0, XH - CAP)


@glyph(0x00BF, 324)  # inverted question
def _iquest():
	return move(turn(_quest(), 324, CAP), 0, XH - CAP)


@glyph(0x00A3, 352)  # pound
def _sterling():
	w = 352
	x0 = 40
	hook = clip(ring(x0, -200, w, CAP, (RO * 0.9, RO * 0.8, 0, 0), S, T), x0, CAP - 260, w, CAP)
	hook = hook.difference(rect(w - S, -1, w + 1, CAP - 190))
	return union(hook, rect(x0, T - 2, x0 + S, CAP - 200), rect(0, 0, w, T), rect(0, 300, w * 0.72, 300 + T * 0.9))


@glyph(0x00A5, 378)  # yen
def _yen():
	w = 378
	return union(_Y(), rect(45, 150, w - 45, 150 + T * 0.8), rect(45, 300, w - 45, 300 + T * 0.8))


@glyph(0x00B5, 342)  # micro
def _micro():
	return union(_u(), rect(0, DESC, s, XH))


@glyph(0x00B7, S)  # middle dot
def _middot():
	return dot(0, XH / 2 - S / 2 + 20, S, 18)


@glyph(0x2022, 250)  # bullet
def _bullet():
	return dot(0, XH / 2 - 125 + 20, 250, 60)


@glyph(0x00B0, 240)  # degree
def _degree():
	return ring(0, CAP - 240, 240, CAP, 92, 64, 60)


@glyph(0x00D7, 320)  # multiplication
def _times():
	w = 320
	c = 300
	return clip(union(diag(T * 0.4, w - T * 0.4, T * 0.95, c + w / 2, c - w / 2), diag(w - T * 0.4, T * 0.4, T * 0.95, c + w / 2, c - w / 2)), 0, c - w / 2, w, c + w / 2)


@glyph(0x00F7, 342)  # division
def _divide():
	w = 342
	return union(rect(0, 255, w, 255 + T), dot(w / 2 - S * 0.45, 420, S * 0.9, 16), dot(w / 2 - S * 0.45, 255 - 45 - S * 0.9, S * 0.9, 16))


@glyph(0x2039, 220)  # single guillemets
def _lsaquo():
	return chevron(220, 300, 280, T)


@glyph(0x203A, 220)
def _rsaquo():
	return mirror(_lsaquo(), 220)


@glyph(0x00AB, 400)
def _laquo():
	return union(_lsaquo(), move(_lsaquo(), 180, 0))


@glyph(0x00BB, 400)
def _raquo():
	return mirror(_laquo(), 400)


@glyph(0x20AC, 380)  # euro
def _euro():
	w = 380
	x0 = 40
	c = move(c_shape(w - x0, CAP, S, T, RO, 255, 445), x0, 0)
	return union(c, rect(0, 245, w * 0.68, 245 + T * 0.78), rect(0, 385, w * 0.68, 385 + T * 0.78))


@glyph(0x0192, 300)  # florin
def _florin():
	w = 300
	x0 = 70
	top = clip(ring(x0, -400, w + 300, ASC, (RL * 0.9, 0, 0, 0), s, t), 0, 200, w, ASC)
	foot = clip(ring(-300, DESC, x0 + s, 400, (0, 0, RL * 0.85, 0), s, t * 0.92), 0, DESC, w, 200)
	return union(top, foot, rect(x0, 0, x0 + s, 400), rect(10, XH - t, w - 15, XH))


@glyph(0x2020, 320)  # dagger
def _dagger():
	w = 320
	return union(rect(w / 2 - S * 0.45, DESC + 40, w / 2 + S * 0.45, CAP), rect(0, CAP - 240, w, CAP - 240 + T * 0.85))


@glyph(0x2021, 320)  # double dagger
def _ddagger():
	w = 320
	return union(_dagger(), rect(0, 60, w, 60 + T * 0.85))


@glyph(0x2026, 3 * S + 2 * 70)  # ellipsis
def _hellip():
	return union(dot(0, 0, S, 18), dot(S + 70, 0, S, 18), dot(2 * (S + 70), 0, S, 18))


@glyph(0x2030, 760)  # per mille
def _permille():
	extra = move(ring(0, 0, 200, 320, 70, S * 0.72, T * 0.72), 760 - 200, 0)
	return union(_percent(), extra)


def quote_comma(turned=False):
	g = comma_shape()
	if turned:
		g = turn(g, S, 0)  # head down, tail up: an opening quote
	return g


@glyph(0x2018, S)  # left single quote
def _lsquo():
	return move(quote_comma(True), 0, CAP)


@glyph(0x2019, S)  # right single quote
def _rsquo():
	return move(quote_comma(), 0, CAP - S)


@glyph(0x201A, S)  # low single quote
def _sbquo():
	return quote_comma()


@glyph(0x201C, 2 * S + 60)
def _ldquo():
	return union(_lsquo(), move(_lsquo(), S + 60, 0))


@glyph(0x201D, 2 * S + 60)
def _rdquo():
	return union(_rsquo(), move(_rsquo(), S + 60, 0))


@glyph(0x201E, 2 * S + 60)
def _bdquo():
	return union(_sbquo(), move(_sbquo(), S + 60, 0))


@glyph(0x2013, 420)  # en dash
def _ndash():
	return rect(0, 255, 420, 255 + T)


@glyph(0x2014, 840)  # em dash
def _mdash():
	return rect(0, 255, 840, 255 + T)


@glyph(0x2122, 560)  # trade mark
def _trade():
	f = 0.42
	tt = scale(_T(), f, f)
	mm = scale(_M(), f, f)
	g = union(tt, move(mm, width("T") * f + 30, 0))
	return move(g, 0, CAP - CAP * f)


@glyph(0x00C6, 540)  # AE
def _AE():
	w = 540
	xs = 230
	diagonal = diag(xs + S * 0.25, S * 0.48, S, CAP, 0)
	return clip(union(
		diagonal, rect(60, 150, xs + 2, 150 + T * 0.92),
		rect(xs, 0, xs + S, CAP), rect(xs - 40, CAP - T, w, CAP), rect(xs, 312, w - 30, 312 + T * 0.95), rect(xs, 0, w, T),
	), 0, 0, w, CAP)


@glyph(0x00E6, 552)  # ae
def _ae():
	a = _a()
	e = move(_e(), width("a") - s, 0)
	return union(a.difference(rect(width("a") - s, 0, BIG, 180)), e)


@glyph(0x0152, 560)  # OE
def _OE():
	w = 560
	xo = 330
	bowl = ring(0, 0, xo + S, CAP, (RO * 1.3, 0, 0, RO * 1.3), S, T)
	return union(bowl, rect(xo, 0, xo + S, CAP), rect(xo, CAP - T, w, CAP), rect(xo, 312, w - 30, 312 + T * 0.95), rect(xo, 0, w, T))


@glyph(0x0153, 560)  # oe
def _oe():
	o = _o()
	return union(o, move(_e(), width("o") - s, 0))


@glyph(0x00DF, 400)  # sharp s
def _szlig():
	# An arch over the stem that folds back at the waist into an open lower
	# bowl; neither the waist nor the foot touches the stem.
	w = 400
	waist = 390
	up = ring(0, waist - t / 2, w - 34, ASC, (RL, RL, RL * 0.8, 0), s, t, square=("bl",))
	up = up.difference(rect(s, waist - t / 2 - 1, w * 0.5, waist + t / 2 + 1))
	lo = ring(w * 0.36, 0, w, waist + t / 2, (0, RL, RL, 0), s, t).difference(rect(w * 0.36 - 1, t, w * 0.36 + s + 1, waist - t / 2))
	lo = lo.difference(rect(-1, -1, s + 90, t + 1)).difference(rect(-1, waist - t / 2 - 1, w * 0.5, BIG))
	return union(up, lo, rect(0, 0, s, ASC - RL))


@glyph(0x00D8, 378)  # O slash
def _Oslash():
	w = 378
	return union(_O(), clip(diag(w + 10, -10, S * 0.75, CAP + 40, -40), -10, -40, w + 10, CAP + 40))


@glyph(0x00F8, 346)  # o slash
def _oslash():
	w = 346
	return union(_o(), clip(diag(w + 10, -10, s * 0.75, XH + 40, -40), -10, -40, w + 10, XH + 40))


@glyph(0x00D0, 414)  # Eth
def _ETH():
	return union(move(_D(), 40, 0), rect(0, 300, 200, 300 + T * 0.9))


@glyph(0x00DE, 356)  # Thorn
def _THORN():
	w = 356
	return union(rect(0, 0, S, CAP), ring(0, 130, w, CAP - 110, (0, RO, RO * 0.9, 0), S, T, square=("tl", "bl")))


@glyph(0x00FE, 346)  # thorn
def _thorn():
	return union(ring(0, 0, 346, XH, RL, s, t, square=("tl", "bl")), rect(0, DESC, s, ASC))


@glyph(0x00F0, 346)  # eth
def _eth():
	# A bowl whose right wall rises and leans back over it, crossed by a bar.
	w = 346
	top = 480
	x0, y0, x1 = w - s * 0.5, top - 100, w * 0.3
	rise = clip(stroke((x0, y0), (x1, ASC), s * 0.95), 0, y0, w, ASC)
	yb = ASC - 150
	xb = x0 + (x1 - x0) * (yb - y0) / (ASC - y0)
	bar = rect(xb - 120, yb - t * 0.4, xb + 120, yb + t * 0.4)
	return union(ring(0, 0, w, top, RL, s, t), rise, bar)


@glyph(0x00A7, 330)  # section
def _sect():
	w = 330
	h = 470
	upper = move(s_shape(w, h, s * 0.95, t * 0.9, RL * 0.9, h - 150, 120, 6), 0, CAP - h)
	lower = move(s_shape(w, h, s * 0.95, t * 0.9, RL * 0.9, h - 150, 120, 6), 0, -100)
	return clip(union(upper, lower), 0, -100, w, CAP)


@glyph(0x00B6, 380)  # pilcrow
def _para():
	w = 380
	return union(
		ring(0, CAP * 0.45, w - S * 0.75, CAP, (RO, 0, 0, RO), S, T, square=("tr", "br")).difference(rect(S, CAP * 0.45 + T, w, CAP - T)),
		rect(0, CAP * 0.45, w * 0.6, CAP * 0.45 + T),
		rect(w * 0.42, DESC + 40, w * 0.42 + S * 0.75, CAP), rect(w - S * 0.75, DESC + 40, w, CAP), rect(w * 0.42, CAP - T, w, CAP),
	)


@glyph(0x00A4, 380)  # currency sign
def _curren():
	w = 380
	c = 300
	r = ring(60, c - 130, w - 60, c + 130, 90, S * 0.75, T * 0.75)
	stubs = [stroke((60, c - 130), (0, c - 190), T * 0.75), stroke((w - 60, c - 130), (w, c - 190), T * 0.75),
	         stroke((60, c + 130), (0, c + 190), T * 0.75), stroke((w - 60, c + 130), (w, c + 190), T * 0.75)]
	stubs = [clip(x, 0, c - 190, w, c + 190) for x in stubs]
	return union(r, *[x.difference(rect(90, c - 110, w - 90, c + 110)) for x in stubs])


# ---------------------------------------------------------------------------
# Greek
# ---------------------------------------------------------------------------


@glyph(0x0393, 302)  # Gamma
def _Gamma():
	return gamma(302, CAPS)


@glyph(0x0394, 400)  # Delta
def _Delta():
	w = 400
	apex = S * 1.05
	left = diag(w / 2 - apex / 2 + S * 0.35, S * 0.48, S, CAP, 0)
	right = diag(w / 2 + apex / 2 - S * 0.35, w - S * 0.48, S, CAP, 0)
	return clip(union(left, right, rect(w / 2 - apex / 2 - 10, CAP - T, w / 2 + apex / 2 + 10, CAP), rect(0, 0, w, T)), 0, 0, w, CAP)


@glyph(0x0398, 378)  # Theta
def _Theta():
	w = 378
	return union(_O(), rect(S - 1, 312, w - S + 1, 312 + T * 0.9))


@glyph(0x039B, 387)  # Lambda
def _Lambda():
	w = 387
	apex = S * 1.05
	left = diag(w / 2 - apex / 2 + S * 0.35, S * 0.48, S, CAP, 0)
	right = diag(w / 2 + apex / 2 - S * 0.35, w - S * 0.48, S, CAP, 0)
	return clip(union(left, right, rect(w / 2 - apex / 2 - 10, CAP - T, w / 2 + apex / 2 + 10, CAP)), 0, 0, w, CAP)


@glyph(0x039E, 330)  # Xi
def _Xi():
	w = 330
	return union(rect(0, CAP - T, w, CAP), rect(30, 312, w - 30, 312 + T * 0.95), rect(0, 0, w, T))


@glyph(0x03A0, 360)  # Pi
def _Pi():
	return pi_shape(360, CAPS)


@glyph(0x03A3, 342)  # Sigma
def _Sigma():
	w = 342
	mid = CAP / 2
	upper = stroke((S * 0.5, CAP - T), (w * 0.56, mid), S * 1.02, mid, CAP - T + 5, 0, w)
	lower = stroke((S * 0.5, T), (w * 0.56, mid), S * 1.02, T - 5, mid, 0, w)
	return clip(union(rect(0, CAP - T, w, CAP), rect(0, 0, w, T), upper, lower), 0, 0, w, CAP)


@glyph(0x03A6, 440)  # Phi
def _Phi():
	return ef_shape(440, CAPS, CAP, 0)


@glyph(0x03A8, 430)  # Psi
def _Psi():
	w = 430
	return union(cup(0, w, 240, CAP, S, T, RO), rect(w / 2 - S / 2, 0, w / 2 + S / 2, CAP))


@glyph(0x03A9, 430)  # Omega
def _Omega():
	# The squared Omega: an arch on two legs with feet turned out.
	w = 430
	x0, x1 = 52, w - 52
	arch_ = ring(x0, 0, x1, CAP, (RO * 1.2, RO * 1.2, 0, 0), S, T).difference(rect(x0 + S, -1, x1 - S, T + 1))
	return union(arch_, rect(0, 0, x0 + S, T * 0.92, (0, 0, 0, 0)), rect(x1 - S, 0, w, T * 0.92))


@glyph(0x03B1, 352)  # alpha
def _alpha():
	w = 352
	bowl = ring(0, 0, w - 26, XH, RL, s, t, square=("tr", "br"))
	return union(bowl, rect(w - 26 - s, 0, w - 26, XH), rect(w - 26 - s, 0, w, t * 0.9))


@glyph(0x03B2, 352)  # beta
def _beta():
	w = 352
	waist = 400
	up = ring(0, waist - t / 2, w - 30, ASC, (RL, RL, RL * 0.8, 0), s, t, square=("bl",))
	lo = ring(0, 0, w, waist + t / 2, (0, RL, RL, 0), s, t, square=("tl", "bl"))
	return union(up, lo, rect(0, DESC, s, ASC - RL))


@glyph(0x03B3, 342)  # gamma
def _gamma_l():
	w = 342
	v = clip(union(diag(s * 0.5, w / 2 - s * 0.08, s, XH, 0), diag(w - s * 0.5, w / 2 + s * 0.08, s, XH, 0)), 0, 0, w, XH)
	return union(v, rect(w / 2 - s * 0.45, DESC, w / 2 + s * 0.45, 40))


@glyph(0x03B4, 346)  # delta
def _delta_l():
	w = 346
	bowl = ring(0, 0, w, 470, RL, s, t)
	neck = clip(stroke((s * 0.6, 420), (w * 0.62, ASC - t * 0.5), s * 0.95), 0, 380, w, ASC)
	return union(bowl, neck, rect(w * 0.42, ASC - t, w, ASC, (0, RS * 0.6, 0, 0)))


@glyph(0x03B5, 310)  # epsilon
def _epsilon():
	w = 310
	ym = XH * 0.5
	up = ring(12, ym - t / 2, w - 4, XH, RL * 0.8, s, t).difference(rect(w / 2, ym - t / 2 - 1, w + 1, XH - 140))
	lo = ring(0, 0, w, ym + t / 2, RL * 0.85, s, t).difference(rect(w / 2, 140, w + 1, ym + t / 2 + 1))
	return union(up, lo).difference(rect(w * 0.7, ym - t / 2 - 1, w + 1, ym + t / 2 + 1))


@glyph(0x03B6, 300)  # zeta
def _zeta():
	w = 300
	d = stroke((w - s * 0.6, ASC - t), (s * 0.55, t * 1.2), s * 1.02, t - 5, ASC - t + 5, 0, w)
	bottom = clip(ring(0, DESC, w, t + 300, (0, 0, RL * 0.8, 0), s * 0.95, t), 0, DESC, w, t)
	bottom = bottom.difference(rect(-1, DESC - 1, w - s * 0.95, 0))
	return union(rect(0, ASC - t, w, ASC), d, rect(0, 0, w - RL * 0.5, t), bottom)


@glyph(0x03B7, 342)  # eta
def _eta():
	w = 342
	return union(arch(0, w, XH, s, t, RL), rect(w - s, DESC, w, XH - RL))


@glyph(0x03B8, 346)  # theta
def _theta():
	w = 346
	return union(ring(0, 0, w, ASC, RL, s, t), rect(s - 1, ASC / 2 - t * 0.45, w - s + 1, ASC / 2 + t * 0.45))


@glyph(0x03B9, 205)  # iota
def _iota():
	w = 205
	return clip(ring(0, 0, w + 300, XH + 300, (0, 0, 0, RL * 0.9), s, t), 0, 0, w, XH)


@glyph(0x03BA, 333)  # kappa
def _kappa():
	w = 333
	return union(rect(0, 0, s, XH), k_arms(s, w, XH, s))


@glyph(0x03BB, 352)  # lambda
def _lambda_l():
	w = 352
	long_ = clip(diag(s * 0.5, w - s * 0.5, s, ASC, 0), 0, 0, w, ASC)
	yj = XH * 0.62
	xj = s * 0.5 + (w - s) * (ASC - yj) / ASC
	short = clip(diag(xj, s * 0.5, s * 0.95, yj + 40, 0), 0, 0, w, yj)
	return union(long_, short)


@glyph(0x03BC, 342)  # mu
def _mu():
	return _micro()


@glyph(0x03BD, 342)  # nu
def _nu():
	return _v()


@glyph(0x03C0, 380)  # pi
def _pi_l():
	w = 380
	return union(rect(0, XH - t, w, XH), rect(40, 0, 40 + s, XH), rect(w - 40 - s, 0, w - 40, XH, (0, 0, 0, 0)))


@glyph(0x03C1, 346)  # rho
def _rho():
	return union(ring(0, 0, 346, XH, RL, s, t, square=("bl",)), rect(0, DESC, s, XH - RL))


@glyph(0x03C2, 320)  # final sigma
def _sigma_final():
	w = 320
	c = c_shape(w, XH, s, t, RL, 190, 372).difference(rect(w / 2, -1, w + 1, 120))
	hook = clip(ring(0, DESC, w, 220, (0, 0, RL * 0.7, 0), s * 0.95, t), w * 0.3, DESC, w, t)
	hook = hook.difference(rect(-1, DESC - 1, w - s * 0.95, 0))
	return union(c, rect(s * 0.5, 0, w - RL * 0.6, t), hook)


@glyph(0x03C3, 380)  # sigma
def _sigma_l():
	w = 380
	return union(ring(0, 0, w - 34, XH, RL, s, t, square=("tr",)), rect(w - 34 - s, XH - t, w, XH))


@glyph(0x03C4, 300)  # tau
def _tau():
	w = 300
	x0 = w / 2 - s / 2
	foot = clip(ring(x0, 0, w + 300, XH + 400, (0, 0, 0, RL * 0.85), s, t), x0, 0, w - 20, XH)
	return union(rect(0, XH - t, w, XH), foot)


@glyph(0x03C5, 342)  # upsilon
def _upsilon():
	return cup(0, 342, 0, XH, s, t, RL)


@glyph(0x03C6, 440)  # phi
def _phi():
	return ef_shape(440, LOWER, XH + 30, DESC)


@glyph(0x03C7, 352)  # chi
def _chi():
	w = 352
	return clip(union(diag(s * 0.48, w - s * 0.48, s * 0.98, XH, DESC), diag(w - s * 0.48, s * 0.48, s * 0.98, XH, DESC)), 0, DESC, w, XH)


@glyph(0x03C8, 420)  # psi
def _psi():
	w = 420
	return union(cup(0, w, 120, XH, s, t, RL), rect(w / 2 - s / 2, DESC, w / 2 + s / 2, ASC))


@glyph(0x03C9, 500)  # omega
def _omega():
	w = 500
	left = cup(0, w / 2 + s / 2, 0, XH, s, t, RL)
	right = cup(w / 2 - s / 2, w, 0, XH, s, t, RL)
	return union(left, right).difference(rect(w / 2 - s / 2 - 1, XH * 0.7, w / 2 + s / 2 + 1, BIG))


# ---------------------------------------------------------------------------
# Cyrillic (capitals, then their lower-case small-capital forms)
# ---------------------------------------------------------------------------


def be_shape(w, m):
	h, st, hs, r = m.h, m.st, m.hs, m.r
	bowl_top = h * 0.57
	return union(
		rect(0, 0, st, h, (RS, 0, 0, 0)), rect(0, h - hs, w - w * 0.06, h, (RS, 0, 0, 0)),
		ring(0, 0, w, bowl_top, (0, r * 0.9, r * 0.9, 0), st, hs, square=("tl", "bl")),
	)


def ghe_up(w, m):
	return union(gamma(w, m), rect(w - m.st * 0.85, m.h - m.hs, w, m.h + m.h * 0.17, (0, RS * 0.6, 0, 0)))


def hard_sign(w, m):
	x0 = w * 0.24
	return union(soft_sign(w, m, x0), rect(0, m.h - m.hs, x0 + m.st, m.h))


def yeru(w, m):
	bowl_w = w * 0.68
	return union(soft_sign(bowl_w, m), rect(w - m.st, 0, w, m.h))


def cyr_pair(cap_cp, lower_cp, cap_w, lower_w, fn, *args, lower_args=None):
	@glyph(cap_cp, cap_w)
	def _cap():
		return fn(cap_w, CAPS, *args)

	@glyph(lower_cp, lower_w)
	def _low():
		return fn(lower_w, LOWER, *(lower_args if lower_args is not None else args))


cyr_pair(0x0411, 0x0431, 356, 0, be_shape)  # Be (lower case drawn separately)
cyr_pair(0x0413, 0x0433, 302, 280, gamma)  # Ghe
cyr_pair(0x0490, 0x0491, 302, 280, ghe_up)  # Ghe with upturn
cyr_pair(0x0414, 0x0434, 420, 390, de_shape, -120, lower_args=(-110,))  # De
cyr_pair(0x0416, 0x0436, 600, 540, zhe_shape)  # Zhe
cyr_pair(0x0417, 0x0437, 335, 300, ze_shape)  # Ze
cyr_pair(0x0418, 0x0438, 378, 342, n_reversed)  # I
cyr_pair(0x041B, 0x043B, 372, 340, el_shape)  # El
cyr_pair(0x041F, 0x043F, 360, 342, pi_shape)  # Pe
cyr_pair(0x0423, 0x0443, 380, 342, u_cyr)  # U (lower case replaced below)
cyr_pair(0x0424, 0x0444, 440, 440, ef_shape, CAP, 0, lower_args=(ASC, DESC))  # Ef
cyr_pair(0x0426, 0x0446, 400, 372, tse_shape, -120, lower_args=(-110,))  # Tse
cyr_pair(0x0427, 0x0447, 350, 320, che_shape)  # Che
cyr_pair(0x0428, 0x0448, 540, 500, sha_shape)  # Sha
cyr_pair(0x0429, 0x0449, 580, 540, sha_shape, -120, lower_args=(-110,))  # Shcha
cyr_pair(0x042A, 0x044A, 440, 410, hard_sign)  # Hard sign
cyr_pair(0x042B, 0x044B, 500, 460, yeru)  # Yeru
cyr_pair(0x042C, 0x044C, 350, 320, soft_sign)  # Soft sign
cyr_pair(0x042D, 0x044D, 356, 320, e_rev)  # E
cyr_pair(0x0404, 0x0454, 356, 320, lambda w, m: mirror(e_rev(w, m), w))  # Ukrainian Ie
cyr_pair(0x042E, 0x044E, 540, 500, yu_shape)  # Yu
cyr_pair(0x042F, 0x044F, 369, 340, ya_shape)  # Ya

# Lower-case forms that are not small capitals: u is the Latin y, ka the
# small-capital K of the Greek kappa.
del GLYPHS[0x0443]
ALIASES[0x0443] = ord("y")
ALIASES[0x043A] = 0x03BA


@glyph(0x0431, 346)  # be: a bowl under a flag
def _be_l():
	w = 346
	bowl = ring(0, 0, w, 470, RL, s, t)
	return union(bowl, rect(0, 300, s, ASC - RL * 0.6), rect(0, ASC - t, w - 15, ASC, (RL * 0.6, 0, 0, 0)))


@glyph(0x0432, 330)  # ve
def _ve():
	return b_shape(330, LOWER)


@glyph(0x043C, 450)  # em
def _em():
	return m_shape(450, LOWER, 120)


@glyph(0x043D, 342)  # en
def _en():
	return h_shape(342, LOWER)


@glyph(0x0442, 320)  # te
def _te():
	return t_shape(320, LOWER)


def glyph_codepoints():
	return sorted(set(GLYPHS) | set(ALIASES))
