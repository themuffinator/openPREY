"""Talon, openPREY's drawn body face (``fonts/english``).

``outlines()`` returns every drawn glyph as a font-unit Path2D with its
advance, the code points that share another glyph, and the combining marks.
``build_openprey_fonts.py`` hands these to the shared face builder, which
composes the accented letters and fills the remaining scripts from Noto.
"""
from __future__ import annotations

from . import glyphs as _glyphs
from .geometry import to_path

UNITS_PER_EM = 2048
FACTOR = UNITS_PER_EM / 1000.0

DESIGN = {
	"cap": _glyphs.CAP, "x_height": _glyphs.XH, "ascender": _glyphs.ASC, "descender": _glyphs.DESC,
	"stem": _glyphs.S, "side_bearing": _glyphs.SB,
}


def outlines():
	drawn = {}
	for codepoint, (body, builder) in sorted(_glyphs.GLYPHS.items()):
		path = to_path(builder(), FACTOR, dx=_glyphs.SB)
		advance = int(round((body + 2.0 * _glyphs.SB) * FACTOR))
		drawn[codepoint] = (path, advance)
	marks = {codepoint: to_path(builder(), FACTOR) for codepoint, builder in sorted(_glyphs.MARKS.items())}
	return drawn, dict(_glyphs.ALIASES), marks
