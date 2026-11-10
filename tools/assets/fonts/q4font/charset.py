"""Target coverage and the shape-sharing tables used when building a face."""
from __future__ import annotations

# The retail atlases are indexed by Windows-1252 byte, not Latin-1, so the
# 0x80..0x9F band holds real typographic characters rather than control codes.
CP1252_HIGH: dict[int, int] = {
	0x80: 0x20AC, 0x82: 0x201A, 0x83: 0x0192, 0x84: 0x201E, 0x85: 0x2026,
	0x86: 0x2020, 0x87: 0x2021, 0x88: 0x02C6, 0x89: 0x2030, 0x8A: 0x0160,
	0x8B: 0x2039, 0x8C: 0x0152, 0x8E: 0x017D, 0x91: 0x2018, 0x92: 0x2019,
	0x93: 0x201C, 0x94: 0x201D, 0x95: 0x2022, 0x96: 0x2013, 0x97: 0x2014,
	0x98: 0x02DC, 0x99: 0x2122, 0x9A: 0x0161, 0x9B: 0x203A, 0x9C: 0x0153,
	0x9E: 0x017E, 0x9F: 0x0178,
}


def byte_to_unicode(code: int) -> int:
	"""Map a retail atlas slot index to the codepoint it actually draws."""
	return CP1252_HIGH.get(code, code)


# Cyrillic and Greek letters whose shapes are identical to a Latin letter the
# Quake 4 artists already drew.  Reusing those keeps most of any Cyrillic or
# Greek run in the authentic face instead of the donor.
CYRILLIC_HOMOGLYPHS: dict[int, str] = {
	0x0405: "S", 0x0406: "I", 0x0408: "J", 0x0410: "A", 0x0412: "B",
	0x0415: "E", 0x041A: "K", 0x041C: "M", 0x041D: "H", 0x041E: "O",
	0x0420: "P", 0x0421: "C", 0x0422: "T", 0x0425: "X",
	0x0430: "a", 0x0435: "e", 0x043E: "o", 0x0440: "p",
	0x0441: "c", 0x0445: "x", 0x0455: "s", 0x0456: "i",
	0x0458: "j", 0x04C0: "I", 0x0501: "d",
}

# Deliberately not shared: Cyrillic PE is a pi shape rather than an N, and both
# cases of U carry a descending tail no Latin Y has.  Those come from the donor.

GREEK_HOMOGLYPHS: dict[int, str] = {
	0x0391: "A", 0x0392: "B", 0x0395: "E", 0x0396: "Z", 0x0397: "H",
	0x0399: "I", 0x039A: "K", 0x039C: "M", 0x039D: "N", 0x039F: "O",
	0x03A1: "P", 0x03A4: "T", 0x03A5: "Y", 0x03A7: "X", 0x03BF: "o",
	0x03F3: "j",
}

# Homoglyphs that are a Latin letter turned upside down or mirrored, which the
# donor draws differently enough to be worth deriving from the face instead.
DERIVED_FROM_LATIN: dict[int, tuple[str, str]] = {
	0x018E: ("E", "flip_x"),      # LATIN CAPITAL LETTER REVERSED E
	0x0258: ("e", "flip_x"),      # LATIN SMALL LETTER REVERSED E
	0x1D19: ("R", "flip_x"),      # small capital reversed R
	0x2035: ("quotesingle", "flip_x"),
}


def unicode_ranges() -> dict[str, tuple[int, int]]:
	"""Blocks the extended faces aim to cover, beyond the retail Latin-1."""
	return {
		"latin_ext_a": (0x0100, 0x017F),
		"latin_ext_b": (0x0180, 0x024F),
		"ipa": (0x0250, 0x02AF),
		"modifiers": (0x02B0, 0x02FF),
		"combining": (0x0300, 0x036F),
		"greek": (0x0370, 0x03FF),
		"cyrillic": (0x0400, 0x04FF),
		"cyrillic_supp": (0x0500, 0x052F),
		"hebrew": (0x0590, 0x05FF),
		"arabic": (0x0600, 0x06FF),
		"arabic_supp": (0x0750, 0x077F),
		"latin_ext_add": (0x1E00, 0x1EFF),
		"punctuation": (0x2000, 0x206F),
		"superscripts": (0x2070, 0x209F),
		"currency": (0x20A0, 0x20BF),
		"letterlike": (0x2100, 0x214F),
		"numberforms": (0x2150, 0x218F),
		"arrows": (0x2190, 0x21FF),
		"math": (0x2200, 0x22FF),
		"technical": (0x2300, 0x23FF),
		"box": (0x2500, 0x257F),
		"blocks": (0x2580, 0x259F),
		"geometric": (0x25A0, 0x25FF),
		"misc_symbols": (0x2600, 0x26FF),
		"dingbats": (0x2700, 0x27BF),
		"arabic_pres_a": (0xFB50, 0xFDFF),
		"arabic_pres_b": (0xFE70, 0xFEFF),
	}


# Blocks each donor is allowed to supply.
NOTO_SANS_BLOCKS = (
	"latin_ext_a", "latin_ext_b", "ipa", "modifiers", "combining", "greek",
	"cyrillic", "cyrillic_supp", "latin_ext_add", "punctuation", "superscripts",
	"currency", "letterlike", "numberforms", "arrows", "math", "technical",
	"box", "blocks", "geometric", "misc_symbols", "dingbats",
)
NOTO_ARABIC_BLOCKS = ("arabic", "arabic_supp", "arabic_pres_a", "arabic_pres_b")
NOTO_HEBREW_BLOCKS = ("hebrew",)
