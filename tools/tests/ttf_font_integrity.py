#!/usr/bin/env python3
"""Guard the shipped TrueType faces against the defects their audit found.

The faces under content/baseoq4/pak0/fonts are generated from the retail bitmap
atlases by tools/assets/fonts/build_openq4_fonts.py; the full audit (tracing
fidelity, fused accents, specimen sheets) needs those proprietary atlases and
lives in tools/assets/fonts/audit_fonts.py. This test checks what the shipped
files alone can prove, with no third-party modules so it runs wherever CI does:

* every extended face draws ASCII, Latin-1, the Windows-1252 extras, Latin
  Extended-A and Cyrillic (the Strogg rune face is Latin-only by design);
* a visible character never maps to an empty outline;
* no C1 control code is mapped - the console relies on an unassigned codepage
  byte drawing as an empty cell, and the console sheet's missing-glyph block
  used to leak in at 0x81;
* the accented Latin-1 letters of one case all have distinct drawings - the
  console sheet slips at 0xDD, which once drew sharp s as a-acute in every
  German word (Roman Strogg draws its lowercase as the capitals, so the cases
  are compared apart);
* the console face keeps all ink inside its 16x16 cell, which the console
  clips to.
"""
from __future__ import annotations

import struct
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FONTS_DIR = ROOT / "content" / "baseoq4" / "pak0" / "fonts"

FACES = ("bigchars", "chain", "lowpixel", "marine", "profont", "r_strogg", "strogg")
LATIN_ONLY_FACES = {"strogg"}
CELL_FACES = {"bigchars"}
# Filled-coverage overlap above which two letters count as one drawing.
SAME_DRAWING = 0.985

CP1252_EXTRAS = {
    0x20AC, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021, 0x02C6, 0x2030, 0x0160,
    0x2039, 0x0152, 0x017D, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2013, 0x2014,
    0x02DC, 0x2122, 0x0161, 0x203A, 0x0153, 0x017E, 0x0178,
}


def required_code_points(face: str) -> set[int]:
    ascii_range = set(range(0x20, 0x7F))
    if face in LATIN_ONLY_FACES:
        # Runes for the letters and digits; the retail sheet has no symbols.
        return {code for code in ascii_range if chr(code).isalnum() or code == 0x20}
    return (
        ascii_range
        | set(range(0xA0, 0x100))
        | CP1252_EXTRAS
        | set(range(0x100, 0x180))
        | set(range(0x400, 0x460))
        | {0x490, 0x491}
    )


class Font:
    """Just enough of a TrueType reader: cmap, glyph boxes and glyph bytes."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data = path.read_bytes()
        self.tables: dict[bytes, tuple[int, int]] = {}
        count = struct.unpack_from(">H", self.data, 4)[0]
        for index in range(count):
            tag, _checksum, offset, length = struct.unpack_from(">4sIII", self.data, 12 + index * 16)
            self.tables[tag] = (offset, length)
        for tag in (b"head", b"hhea", b"maxp", b"loca", b"glyf", b"cmap"):
            if tag not in self.tables:
                raise AssertionError(f"{path.name} has no {tag.decode()} table")
        head = self.tables[b"head"][0]
        self.units_per_em = struct.unpack_from(">H", self.data, head + 18)[0]
        long_offsets = struct.unpack_from(">h", self.data, head + 50)[0] == 1
        hhea = self.tables[b"hhea"][0]
        self.ascent, self.descent = struct.unpack_from(">hh", self.data, hhea + 4)
        glyphs = struct.unpack_from(">H", self.data, self.tables[b"maxp"][0] + 4)[0]
        loca = self.tables[b"loca"][0]
        if long_offsets:
            self.offsets = list(struct.unpack_from(f">{glyphs + 1}I", self.data, loca))
        else:
            self.offsets = [value * 2 for value in struct.unpack_from(f">{glyphs + 1}H", self.data, loca)]
        self.cmap = self._read_cmap()

    def _read_cmap(self) -> dict[int, int]:
        base = self.tables[b"cmap"][0]
        mapping: dict[int, int] = {}
        subtables = struct.unpack_from(">H", self.data, base + 2)[0]
        for index in range(subtables):
            _platform, _encoding, offset = struct.unpack_from(">HHI", self.data, base + 4 + index * 8)
            table = base + offset
            fmt = struct.unpack_from(">H", self.data, table)[0]
            if fmt == 4:
                segments = struct.unpack_from(">H", self.data, table + 6)[0] // 2
                ends = table + 14
                starts = ends + segments * 2 + 2
                deltas = starts + segments * 2
                ranges = deltas + segments * 2
                for seg in range(segments):
                    end = struct.unpack_from(">H", self.data, ends + seg * 2)[0]
                    start = struct.unpack_from(">H", self.data, starts + seg * 2)[0]
                    delta = struct.unpack_from(">h", self.data, deltas + seg * 2)[0]
                    range_offset = struct.unpack_from(">H", self.data, ranges + seg * 2)[0]
                    if start == 0xFFFF:
                        continue
                    for code in range(start, end + 1):
                        if range_offset == 0:
                            glyph = (code + delta) & 0xFFFF
                        else:
                            address = ranges + seg * 2 + range_offset + 2 * (code - start)
                            glyph = struct.unpack_from(">H", self.data, address)[0]
                            if glyph:
                                glyph = (glyph + delta) & 0xFFFF
                        if glyph:
                            mapping.setdefault(code, glyph)
            elif fmt == 12:
                groups = struct.unpack_from(">I", self.data, table + 12)[0]
                for group in range(groups):
                    start, end, first = struct.unpack_from(">III", self.data, table + 16 + group * 12)
                    for code in range(start, end + 1):
                        mapping.setdefault(code, first + code - start)
        if not mapping:
            raise AssertionError(f"{self.path.name}: no usable cmap subtable")
        return mapping

    def glyph_bytes(self, glyph: int) -> bytes:
        glyf = self.tables[b"glyf"][0]
        return self.data[glyf + self.offsets[glyph]: glyf + self.offsets[glyph + 1]]

    def glyph_box(self, glyph: int) -> tuple[int, int, int, int, int] | None:
        """(contours, xMin, yMin, xMax, yMax), or None for an empty glyph."""
        data = self.glyph_bytes(glyph)
        if len(data) < 10:
            return None
        return struct.unpack_from(">hhhhh", data, 0)

    def glyph_contours(self, glyph: int) -> list[list[tuple[int, int, bool]]]:
        """A simple glyph's contours as (x, y, on-curve) points, in font units."""
        data = self.glyph_bytes(glyph)
        if len(data) < 10:
            return []
        contours = struct.unpack_from(">h", data, 0)[0]
        if contours <= 0:
            return []
        ends = struct.unpack_from(f">{contours}H", data, 10)
        count = ends[-1] + 1
        cursor = 10 + 2 * contours
        cursor += 2 + struct.unpack_from(">H", data, cursor)[0]
        flags: list[int] = []
        while len(flags) < count:
            flag = data[cursor]
            cursor += 1
            flags.append(flag)
            if flag & 0x08:
                flags.extend([flag] * data[cursor])
                cursor += 1
        axes: list[list[int]] = []
        for short, same in ((0x02, 0x10), (0x04, 0x20)):
            value, values = 0, []
            for flag in flags[:count]:
                if flag & short:
                    step = data[cursor]
                    cursor += 1
                    value += step if flag & same else -step
                elif not flag & same:
                    value += struct.unpack_from(">h", data, cursor)[0]
                    cursor += 2
                values.append(value)
            axes.append(values)
        points = [(x, y, bool(flag & 0x01)) for x, y, flag in zip(axes[0], axes[1], flags)]
        result, first = [], 0
        for end in ends:
            result.append(points[first:end + 1])
            first = end + 1
        return result

    def coverage(self, glyph: int, size: int = 48) -> list[list[bool]]:
        """The glyph filled (non-zero) on a size x size grid spanning one em."""
        edges: list[tuple[float, float, float, float]] = []
        scale = size / self.units_per_em
        for contour in self.glyph_contours(glyph):
            polyline = _flatten(contour)
            for (x0, y0), (x1, y1) in zip(polyline, polyline[1:] + polyline[:1]):
                edges.append((x0 * scale, (self.ascent - y0) * scale, x1 * scale, (self.ascent - y1) * scale))
        grid = []
        for row in range(size):
            y = row + 0.5
            crossings = []
            for x0, y0, x1, y1 in edges:
                if (y0 <= y) != (y1 <= y):
                    crossings.append((x0 + (y - y0) * (x1 - x0) / (y1 - y0), 1 if y1 > y0 else -1))
            crossings.sort()
            filled = [False] * size
            winding, index = 0, 0
            for column in range(size):
                x = column + 0.5
                while index < len(crossings) and crossings[index][0] <= x:
                    winding += crossings[index][1]
                    index += 1
                filled[column] = winding != 0
            grid.append(filled)
        return grid


def _flatten(contour: list[tuple[int, int, bool]]) -> list[tuple[float, float]]:
    """TrueType quadratic contour to a polyline (implied on-curve midpoints)."""
    if not contour:
        return []
    points = [(float(x), float(y), on) for x, y, on in contour]
    start = next((i for i, p in enumerate(points) if p[2]), None)
    if start is None:
        first = ((points[0][0] + points[-1][0]) / 2, (points[0][1] + points[-1][1]) / 2, True)
        points.insert(0, first)
        start = 0
    points = points[start:] + points[:start]
    polyline = [(points[0][0], points[0][1])]
    current = points[0]
    for index in range(1, len(points) + 1):
        point = points[index % len(points)]
        if point[2]:
            if not current[2]:
                continue
            polyline.append((point[0], point[1]))
            current = point
            continue
        following = points[(index + 1) % len(points)]
        end = following if following[2] else ((point[0] + following[0]) / 2, (point[1] + following[1]) / 2, True)
        anchor = polyline[-1]
        for step in range(1, 5):
            t = step / 4
            u = 1 - t
            polyline.append((u * u * anchor[0] + 2 * u * t * point[0] + t * t * end[0],
                             u * u * anchor[1] + 2 * u * t * point[1] + t * t * end[1]))
        current = (end[0], end[1], True)
    return polyline


def overlap(a: list[list[bool]], b: list[list[bool]]) -> float:
    inter = sum(x and y for row_a, row_b in zip(a, b) for x, y in zip(row_a, row_b))
    union = sum(x or y for row_a, row_b in zip(a, b) for x, y in zip(row_a, row_b))
    return inter / union if union else 1.0


def visible(code_point: int) -> bool:
    category = unicodedata.category(chr(code_point))
    return category[0] in "LNPS"


def check_face(name: str) -> list[str]:
    path = FONTS_DIR / f"{name}.ttf"
    if not path.is_file():
        return [f"{path.relative_to(ROOT).as_posix()} is missing"]
    font = Font(path)
    problems: list[str] = []

    missing = sorted(required_code_points(name) - set(font.cmap))
    if missing:
        listed = " ".join(f"U+{code:04X}" for code in missing[:12])
        problems.append(f"{name}: {len(missing)} required code points unmapped: {listed}")

    empty = [code for code, glyph in font.cmap.items() if visible(code) and font.glyph_box(glyph) is None]
    if empty:
        listed = " ".join(f"U+{code:04X}" for code in sorted(empty)[:12])
        problems.append(f"{name}: {len(empty)} visible characters draw nothing: {listed}")

    controls = sorted(code for code in font.cmap if 0x80 <= code <= 0x9F)
    if controls:
        listed = " ".join(f"U+{code:04X}" for code in controls)
        problems.append(f"{name}: C1 control codes are mapped ({listed}); an unassigned "
                        "codepage byte has to draw as an empty cell")

    if name not in LATIN_ONLY_FACES:
        # Two cells of a sheet can hold the same letter drawn twice, and their
        # traces then differ by a hair, so the drawings are compared filled on a
        # 48 pixel em. Distinct letters stay under 0.97 (a capital whose accent
        # is pressed into the console cell is the closest); a copy scores 1.
        for low, high in ((0xC0, 0xDF), (0xDF, 0x100)):
            seen: list[tuple[int, list[list[bool]]]] = []
            for code in range(low, high):
                decomposition = unicodedata.decomposition(chr(code))
                if code not in font.cmap or (code != 0xDF and (not decomposition or decomposition.startswith("<"))):
                    continue
                cover = font.coverage(font.cmap[code])
                for other, other_cover in seen:
                    if overlap(cover, other_cover) >= SAME_DRAWING:
                        problems.append(f"{name}: U+{code:04X} {unicodedata.name(chr(code))} draws the "
                                        f"same letter as U+{other:04X} {unicodedata.name(chr(other))}")
                        break
                seen.append((code, cover))

    if name in CELL_FACES:
        if font.ascent + abs(font.descent) != font.units_per_em:
            problems.append(f"{name}: ascent {font.ascent} + descent {abs(font.descent)} is not one "
                            f"em ({font.units_per_em}); the console maps one em to one cell")
        spill = []
        for code, glyph in font.cmap.items():
            box = font.glyph_box(glyph)
            if box is not None and (box[4] > font.ascent or box[2] < font.descent):
                spill.append(code)
        if spill:
            listed = " ".join(f"U+{code:04X}" for code in sorted(spill)[:12])
            problems.append(f"{name}: {len(spill)} glyphs reach outside the console cell, which "
                            f"clips them: {listed}")
    return problems


def main() -> int:
    problems: list[str] = []
    for name in FACES:
        problems.extend(check_face(name))
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1
    print(f"ttf_font_integrity: {len(FACES)} faces OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
