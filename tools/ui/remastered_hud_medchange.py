"""The Medical Labs implant activation (ui-visual-design.md 14.19).

guis/vehicles/medchange.gui is the temporary overlay at the end of
stroggification: medlabs.script's nanocyteFade() sends `activate` as the
surgical flash fades. Its gold hexagon field lights cell by cell twice over
under four corner pieces, Strogg readouts and rune streams, on data and static
layers and an orange edge glow, and the whole overlay hides at 4650 ms. `hurt`
pulses a red edge glow over a second and `saveMessage` shows the save notice,
both independent of the activation.

Everything is vector or text. The authored 38 cells keep their stock offsets
on the centered 640x480 u screen, and the lattice continues through every side,
top and bottom band with phases derived from the same sequence (the design
atlas's implant sheet), so nothing stretches at any aspect. The readouts and
rune fields follow the leading screen's bottom and the trailing screen's top,
the corner pieces the view's corners, and the glows and static the view's
edges. The stock textures were measured for the hex and corner rims (bright at
the edge, falling to a 0.26 wash over about 15 u), the edge glow's falloff and
the streaks of the two static layers.
"""
from __future__ import annotations

import math

import build_retained_screens as ui
import hud_svg
from remastered_hud_base import (NOT, S, U, HudDocument, anchor, cancel, gameplay_root, join_events, layout_state, num, op,
                                 play, shadowed, tr, transform_value, u, vec)
from remastered_hud_status import full

GOLD = [1.0, 0.815, 0.435]           # the stock "on" color (1, .815, .435)
ORANGE = [1.0, 0.5, 0.0]             # edgeglow's matcolor
RED = [1.0, 0.0, 0.0]                # the hurt pulse, at 0.6
BAR = [0.976, 0.4, 0.0156]           # t_bar1/t_bar2's matcolor
WASH = 0.26                          # the hex and corner textures' interior
# Each band adds its alpha over [0, width] u inside a lit edge; with the wash
# they step down the measured falloff (1.0 at the edge, 0.26 by about 15 u).
BANDS = ((2.0, 0.45), (7.0, 0.27))

ACTIVE_MS, FADE_AT, CELL_START, CELL_PITCH, CELL_FADE = 4650, 4150, 500, 50, 500
ORDER = [10, 24, 14, 32, 30, 4, 8, 15, 9, 34, 28, 21, 1, 38, 20, 2, 12, 26, 18, 33, 16, 23, 6, 13, 35, 27, 11, 22, 7, 31, 3, 17,
         25, 36, 19, 5, 29]
# The 38 authored cells (medchange.gui hex1-hex38): 86x86 u boxes. Cell 37
# never flashes, so on the additive overlay it is never seen.
CELLS = {1: (67, 118), 2: (67, 198), 3: (67, 278), 4: (137, 0), 5: (137, 78), 6: (137, 158), 7: (137, 238), 8: (137, 318),
         9: (137, 398), 10: (207, -39), 11: (207, 38), 12: (207, 118), 13: (207, 198), 14: (207, 278), 15: (207, 358),
         16: (207, 438), 17: (277, 0), 18: (277, 78), 19: (277, 158), 20: (277, 238), 21: (277, 318), 22: (277, 398),
         23: (347, -39), 24: (347, 38), 25: (347, 118), 26: (347, 198), 27: (347, 278), 28: (347, 358), 29: (347, 438),
         30: (417, 1), 31: (417, 78), 32: (417, 158), 33: (417, 238), 34: (417, 318), 35: (417, 398), 36: (487, 117),
         37: (487, 198), 38: (487, 278)}
HEX = [(1, 43), (22, 7), (64, 7), (85, 43), (64, 79), (22, 79)]
# The lattice beyond the authored cells: the side bands of views up to 32:9
# and the top and bottom bands of portrait views up to 9:19.5. A view is
# only ever wider or taller than 4:3, never both, so the far corners stay empty.
LATTICE_COLUMNS, LATTICE_ROWS = range(-9, 16), range(-6, 11)
WIDE_X, TALL_Y = (-560, 1200), (-460, 940)
# Reduced motion settles every cell here instead of flashing it (14.19).
STEADY = 0.1
# A corner piece in its top-leading 256 u box: the lit edge runs down from
# the top at x 153 to (18, 234), then along y 234 to the view's leading edge.
CORNER = [(0, 0), (153, 0), (18, 234), (0, 234)]
CORNER_LIT = [(153, 0), (18, 234), (0, 234)]
READOUT_VALUES = ["84278.324", "43536.832", "76245.003", "57452.659", "35945.202", "94320.953"]
AXES = (("X", ["834.32", "527.64", "698.30", "932.78", "404.26", "368.45"], 6, 100),
        ("Y", ["602.57", "257.46", "968.03", "392.87", "440.62", "638.54"], 27, 150),
        ("Z", ["438.60", "257.46", "968.03", "392.87", "440.62", "638.54"], 50, 200))
RUNES = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
# The static layers traced from the stock tiles (128x128 texels stretched
# over the view): (row, x0, x1, brightness in quarters) for img_static3's
# streaks, and every third of colorstatic's brighter dashes with its color
# in quarters of its brightest channel.
STATIC_STREAKS = [
    (4,110,112,0.25), (4,119,120,0.25), (5,5,6,0.25), (5,18,20,0.25), (5,23,24,0.25), (5,50,51,0.25), (5,52,59,0.5), (5,109,113,0.25),
    (6,52,59,0.25), (6,67,74,0.25), (6,95,96,0.25), (6,99,116,0.25), (7,52,58,0.25), (7,67,76,0.5), (7,88,97,0.5), (7,98,125,0.5),
    (8,51,58,0.25), (8,66,77,0.5), (8,88,96,0.5), (8,98,124,0.5), (25,63,68,0.25), (26,62,75,0.25), (26,76,80,0.25), (29,41,93,0.5),
    (30,32,33,0.25), (30,34,93,0.5), (31,27,99,0.5), (32,31,102,0.75), (33,32,98,0.5), (34,31,97,0.5), (35,6,13,0.25), (35,35,47,0.25),
    (35,51,97,0.5), (36,56,59,0.25), (36,77,93,0.25), (37,81,82,0.25), (37,85,86,0.25), (45,15,20,0.25), (45,103,104,0.25), (46,10,23,0.25),
    (46,101,104,0.25), (46,106,107,0.25), (47,7,24,0.5), (47,29,33,0.25), (47,35,36,0.25), (48,10,24,0.25), (48,25,28,0.25), (48,31,39,0.25),
    (48,89,92,0.25), (49,15,17,0.25), (49,18,20,0.25), (61,7,8,0.25), (61,18,21,0.25), (61,22,24,0.25), (61,29,30,0.25), (61,36,38,0.25),
    (62,18,20,0.25), (62,21,23,0.25), (62,41,43,0.25), (63,5,27,0.25), (63,103,105,0.25), (63,107,108,0.25), (64,17,20,0.25), (64,21,23,0.25),
    (64,92,93,0.25), (64,98,100,0.25), (64,101,108,0.5), (65,17,18,0.25), (65,90,111,0.5), (65,112,124,0.25), (66,72,74,0.25), (66,76,78,0.5),
    (66,80,85,0.5), (66,91,94,0.5), (66,95,102,0.5), (66,103,109,0.5), (66,111,116,0.5), (66,119,124,0.5), (67,69,70,0.25), (67,72,74,0.25),
    (67,75,79,0.25), (67,81,114,0.5), (68,72,120,0.75), (69,52,57,0.5), (69,63,64,0.25), (69,72,75,0.5), (69,79,125,0.75), (70,54,56,0.25),
    (70,72,74,0.25), (70,81,82,0.25), (70,83,98,0.5), (70,110,125,0.5), (71,71,73,0.25), (71,84,92,0.5), (71,107,111,0.25), (71,120,125,0.25),
    (79,7,8,0.25), (79,11,18,0.5), (79,21,29,0.5), (80,12,30,0.5), (80,31,32,0.25), (80,80,81,0.25), (81,12,33,0.5), (81,66,67,0.25),
    (81,70,71,0.25), (81,76,80,0.5), (87,14,17,0.25), (87,18,20,0.25), (87,21,28,0.5), (87,31,32,0.25), (87,71,72,0.25), (87,81,83,0.25),
    (87,92,95,0.25), (87,97,104,0.25), (88,3,6,0.25), (88,7,9,0.25), (88,26,28,0.5), (88,64,66,0.25), (88,88,89,0.25), (88,93,95,0.25),
    (88,97,99,0.5), (88,101,104,0.25), (89,30,35,0.25), (89,51,53,0.25), (89,58,59,0.25), (89,91,100,0.5), (89,101,103,0.25), (94,17,23,0.5),
    (94,29,42,0.25), (94,109,115,0.25), (94,119,121,0.25), (95,18,23,0.5), (95,30,38,0.25), (95,107,115,0.25), (95,118,120,0.25), (95,121,122,0.25),
    (97,33,34,0.25), (97,108,110,0.25), (97,112,115,0.25), (97,117,123,0.5), (98,15,17,0.25), (98,108,114,0.25), (98,116,121,0.25), (99,15,18,0.25),
    (99,110,113,0.25), (99,123,124,0.25), (109,9,26,0.5), (109,60,62,0.25), (110,12,24,0.25), (110,61,66,0.25), (111,16,18,0.25), (111,20,22,0.25),
    (111,62,77,0.25), (112,62,76,0.25), (113,68,79,0.25), (114,63,69,0.25), (114,70,72,0.25), (114,98,100,0.25), (114,101,106,0.25), (115,98,108,0.25),
    (116,17,19,0.25), (116,20,24,0.25), (116,98,100,0.25), (116,101,108,0.5), (118,18,40,0.5), (118,102,108,0.5), (118,113,114,0.25), (119,21,35,0.5),
    (119,92,94,0.25), (119,97,108,0.5), (119,112,116,0.25), (120,102,106,0.25),
]
STATIC_DASHES = [
    (0,14,15,(4,4,2),0.5), (1,22,23,(2,4,2),0.5), (2,72,73,(2,4,3),0.5), (3,17,18,(2,4,1),0.75), (4,24,25,(3,4,2),0.75), (5,58,59,(2,4,2),0.75),
    (6,11,14,(4,4,3),0.75), (7,16,17,(4,4,2),0.75), (7,106,107,(2,4,2),0.5), (8,93,96,(2,4,2),0.75), (9,82,83,(3,4,2),0.75), (10,54,55,(3,4,3),0.5),
    (11,13,14,(3,4,2),0.5), (11,94,95,(2,4,3),0.75), (12,18,19,(2,4,3),0.75), (12,56,58,(1,4,2),0.75), (13,115,119,(2,4,2),0.75), (14,38,41,(4,4,2),0.75),
    (15,98,99,(3,4,2),0.75), (16,21,24,(4,3,4),0.75), (17,0,7,(3,4,2),0.75), (17,120,121,(4,3,2),0.75), (18,88,93,(2,4,3),1.0), (20,30,37,(2,4,2),0.75),
    (20,80,81,(3,4,4),0.5), (21,12,14,(4,3,2),0.5), (21,97,98,(3,4,2),0.75), (22,12,15,(3,4,2),0.75), (22,116,117,(2,4,3),0.75), (23,34,38,(2,4,1),1.0),
    (24,55,56,(4,2,4),0.75), (24,98,99,(2,4,3),0.75), (25,2,9,(2,4,3),0.75), (26,20,23,(2,4,2),0.75), (26,61,62,(2,3,4),0.75), (26,91,92,(3,4,3),0.5),
    (27,22,24,(4,4,3),0.75), (28,67,68,(4,4,3),0.5), (28,93,95,(1,4,2),0.75), (28,114,117,(3,4,2),0.75), (29,10,13,(2,4,2),0.75), (29,78,79,(3,4,1),0.75),
    (31,37,40,(4,4,3),0.75), (31,81,83,(4,3,3),0.75), (32,24,26,(3,4,2),0.75), (32,119,121,(2,4,2),0.5), (33,59,60,(4,3,3),0.5), (34,7,17,(3,4,3),0.75),
    (35,39,40,(1,4,2),0.5), (35,88,89,(4,4,3),0.75), (36,32,35,(2,4,2),1.0), (36,81,82,(2,4,2),0.5), (36,123,124,(3,4,1),0.5), (37,49,50,(1,4,2),0.75),
    (39,30,32,(2,2,4),0.75), (40,9,12,(2,4,2),0.75), (40,108,109,(1,4,3),0.75), (41,44,45,(3,4,3),0.75), (41,123,124,(2,4,3),0.75), (42,27,28,(3,4,2),0.5),
    (43,16,17,(1,4,2),0.5), (44,26,27,(1,4,3),0.75), (44,124,128,(2,4,3),0.75), (45,117,118,(2,4,4),0.5), (47,79,81,(4,2,3),0.5), (48,34,35,(3,4,3),0.75),
    (49,5,6,(3,4,2),0.75), (49,96,97,(4,3,3),0.5), (49,121,123,(2,3,4),0.5), (50,114,115,(2,4,3),0.75), (52,44,45,(3,4,2),0.75), (52,109,110,(3,4,2),0.75),
    (53,40,42,(4,3,1),0.5), (54,82,83,(3,4,2),0.5), (55,87,88,(2,4,3),0.75), (56,108,109,(2,4,1),0.75), (57,48,50,(2,4,3),0.75), (59,35,38,(2,4,3),0.75),
    (60,34,39,(3,4,4),0.75), (61,18,20,(4,3,3),0.75), (61,112,116,(3,4,4),0.75), (63,127,128,(3,4,4),0.75), (64,29,30,(4,2,2),0.75), (64,67,68,(3,4,3),0.75),
    (65,101,102,(1,4,3),0.75), (66,91,92,(4,3,3),0.75), (67,15,16,(4,4,2),0.5), (68,112,113,(3,4,4),0.5), (69,5,9,(4,4,2),0.75), (69,119,121,(4,4,2),0.75),
    (70,44,45,(1,4,2),0.5), (71,6,7,(2,4,3),0.5), (72,35,36,(3,4,3),0.75), (72,102,105,(2,4,1),0.75), (74,84,87,(4,3,1),0.75), (75,3,4,(4,4,3),0.5),
    (75,68,70,(2,4,3),0.75), (75,102,103,(2,4,3),0.75), (76,63,64,(4,4,4),0.5), (77,41,43,(3,4,2),0.75), (78,3,7,(2,4,3),0.75), (79,76,78,(3,4,3),0.75),
    (80,59,61,(3,4,4),0.75), (81,23,31,(4,4,3),0.75), (82,33,35,(2,4,3),0.75), (83,30,31,(4,4,3),0.5), (84,15,20,(1,4,3),0.75), (84,90,91,(1,4,2),0.75),
    (85,3,4,(1,4,2),0.75), (85,114,116,(3,4,3),0.75), (86,96,100,(2,4,1),0.75), (86,126,127,(2,4,3),0.75), (87,90,93,(3,4,3),0.75), (88,19,20,(2,4,2),0.5),
    (88,68,69,(3,4,3),0.75), (89,121,122,(2,4,2),0.75), (91,51,53,(3,4,2),0.75), (92,2,3,(3,4,1),0.75), (92,48,49,(4,3,3),0.75), (92,93,94,(2,4,1),0.75),
    (94,118,119,(1,4,3),0.75), (96,0,1,(3,4,3),0.75), (96,127,128,(3,4,3),1.0), (97,58,64,(4,4,3),0.75), (98,37,44,(3,4,3),0.75), (99,72,77,(4,4,3),0.75),
    (100,4,5,(4,3,1),0.75), (101,57,58,(4,4,2),0.5), (101,100,101,(2,4,2),0.75), (102,38,41,(4,4,3),0.75), (103,88,89,(3,4,3),0.5), (104,55,59,(2,4,2),0.75),
    (105,13,15,(4,4,3),0.75), (105,75,76,(2,4,4),0.75), (106,49,50,(3,4,1),0.5), (107,97,99,(2,4,4),0.5), (108,0,2,(3,4,3),0.75), (108,127,128,(2,4,3),0.75),
    (109,68,70,(2,4,4),0.75), (111,10,12,(2,4,2),0.75), (111,31,33,(2,4,3),0.75), (112,28,31,(2,4,2),0.75), (112,114,115,(3,4,3),0.75), (114,17,18,(4,3,3),0.5),
    (115,18,22,(3,4,2),0.75), (115,84,85,(4,3,3),0.75), (116,111,113,(1,4,2),0.75), (117,39,40,(3,4,3),0.5), (118,58,59,(3,4,3),0.5), (118,124,125,(4,4,2),0.5),
    (120,31,36,(2,4,3),0.75), (121,47,51,(4,4,2),0.75), (121,69,70,(3,4,3),0.75), (123,7,9,(2,4,3),0.75), (123,115,116,(4,3,3),0.75), (124,64,66,(4,3,3),0.75),
    (124,81,83,(1,4,3),0.75), (125,36,37,(2,4,2),0.5), (127,7,9,(4,4,3),0.75), (127,100,101,(2,4,3),0.5),
]


def _rgba(colour: list, alpha: float) -> list:
    return [colour[0], colour[1], colour[2], round(alpha, 4)]


def _offset_lines(points: list, d: float, closed: bool) -> list:
    """Each edge of a clockwise (screen) polygon or polyline moved d to its
    right-hand side walking the points, which is inward."""
    lines = []
    count = len(points) if closed else len(points) - 1
    for i in range(count):
        (x0, y0), (x1, y1) = points[i], points[(i + 1) % len(points)]
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        lines.append(((x0 - dy / length * d, y0 + dx / length * d), (dx, dy)))
    return lines


def _meet(a, b) -> tuple:
    (p, r), (q, s) = a, b
    cross = r[0] * s[1] - r[1] * s[0]
    t = ((q[0] - p[0]) * s[1] - (q[1] - p[1]) * s[0]) / cross
    return (p[0] + t * r[0], p[1] + t * r[1])


def inset(points: list, d: float) -> list:
    """A convex clockwise polygon moved d inward on every side."""
    lines = _offset_lines(points, d, True)
    return [_meet(lines[i - 1], lines[i]) for i in range(len(lines))]


def _commands(polygons: list, *, scale: float = U, ox: float = 0, oy: float = 0) -> list:
    commands = []
    for polygon in polygons:
        for index, (x, y) in enumerate(polygon):
            commands.append({"id": f"c{len(commands)}", "op": "move" if index == 0 else "line",
                             "points": [[round(ox + x * scale, 1), round(oy + y * scale, 1)]]})
        commands.append({"id": f"c{len(commands)}", "op": "close"})
    return commands


# Edge coverage costs geometry along every edge pixel, so only the bright
# rims keep it: the washes, the wide bands, the glows, the static and the
# faint runes draw hard pixel edges ("antialias": false), where it never shows.
def _fill(ident: str, polygons: list, colour: list, alpha: float, **kw) -> dict:
    return {"id": ident, "commands": _commands(polygons, **kw), "fill": ui.solid(_rgba(colour, alpha)), "blend": "additive",
            "antialias": False}


def _rim(ident: str, polygons: list, colour: list, alpha: float, width: float, smooth: bool, **kw) -> dict:
    return {"id": ident, "commands": _commands(polygons, **kw), "fill": {"type": "none"}, "blend": "additive", "antialias": smooth,
            "stroke": {"paint": ui.solid(_rgba(colour, alpha)), "widthDp": round(width * U, 3), "minimumPixels": 0, "join": "miter",
                       "cap": "butt"}}


def hex_paths(prefix: str, origins: list, *, gain: float = 1.0, bands=BANDS) -> list:
    """The measured hex cell at each origin (u, on the center screen): the
    interior wash and the rim bands, each layer one path for every cell."""
    shapes = [[(x + px, y + py) for px, py in HEX] for x, y in origins]
    paths = [_fill(prefix + "-wash", shapes, GOLD, WASH * gain)]
    for index, (width, alpha) in enumerate(bands):
        paths.append(_rim(f"{prefix}-rim{index}", [inset(shape, width / 2) for shape in shapes], GOLD, alpha * gain, width,
                          smooth=index == 0))
    return paths


def lattice() -> dict:
    """Every cell by flash phase: the authored cells at their phase in the
    stock order, and the lattice beyond them, which the atlas continues with
    phases derived from the same sequence (x = 67 + 70c, y = 38 + 80r, odd
    columns 40 u lower)."""
    phases = {p: [] for p in range(len(ORDER))}
    for cell, origin in CELLS.items():
        if cell in ORDER:
            phases[ORDER.index(cell)].append(origin)
    for column in LATTICE_COLUMNS:
        x = 67 + column * 70
        for row in LATTICE_ROWS:
            y = 38 + (40 if abs(column) % 2 else 0) + row * 80
            if x >= 0 and x + 86 <= 640 and -40 <= y <= 438:
                continue
            wide = WIDE_X[0] < x + 86 and x < WIDE_X[1] and 0 < y + 86 and y < 480
            tall = 0 < x + 86 and x < 640 and TALL_Y[0] < y + 86 and y < TALL_Y[1]
            if wide or tall:
                phases[((column * 11 + row * 7) % 37 + 37) % 37].append((x, y))
    return phases


def flash_keys(phase: int) -> list:
    """Two passes: lit at 500 + 50 p ms and again 37 steps later, each fading
    to black over 500 ms. The last key, at the overlay's 4650 ms end, is the
    steady value reduced motion settles on; with motion it never draws."""
    keys = [(0, num(0))]
    for start in (CELL_START + CELL_PITCH * phase, CELL_START + CELL_PITCH * (phase + len(ORDER))):
        # The last cell's fade ends with the overlay; the steady key follows it.
        keys += [(start - 1, num(0)), (start, num(1)), (min(start + CELL_FADE, ACTIVE_MS - 1), num(0))]
    if keys[-1][0] < ACTIVE_MS - 1:
        keys.append((ACTIVE_MS - 1, num(0)))
    keys.append((ACTIVE_MS, num(STEADY)))
    return keys


def corner_paths() -> list:
    """The four corner pieces in one view-sized node: the wash and the rim
    bands along the lit edge, mirrored to each corner of the view."""
    bands = []
    for width, alpha in BANDS:
        # The band between the lit edge and its copy `width` inward: from the
        # top edge, round the bend, to the view's leading edge.
        lines = _offset_lines(CORNER_LIT, width, False)
        inner = [_meet(lines[0], ((0, 0), (1, 0))), _meet(lines[0], lines[1]), (0, CORNER_LIT[2][1] - width)]
        bands.append((width, alpha, CORNER_LIT + inner[::-1]))

    def place(polygon, right, bottom):
        result = []
        for x, y in polygon:
            px = {"fraction": 1, "dp": round(-x * U, 2)} if right else round(x * U, 2)
            py = {"fraction": 1, "dp": round(-y * U, 2)} if bottom else round(y * U, 2)
            result.append([px, py])
        return result

    def path(ident, polygons_alpha):
        commands = []
        for polygon in polygons_alpha:
            for index, point in enumerate(polygon):
                commands.append({"id": f"c{len(commands)}", "op": "move" if index == 0 else "line", "points": [point]})
            commands.append({"id": f"c{len(commands)}", "op": "close"})
        return commands
    corners = [(False, False), (True, False), (False, True), (True, True)]
    paths = [{"id": "wash", "commands": path("wash", [place(CORNER, r, b) for r, b in corners]),
              "fill": ui.solid(_rgba(GOLD, WASH)), "blend": "additive", "antialias": False}]
    for index, (width, alpha, polygon) in enumerate(bands):
        paths.append({"id": f"rim{index}", "commands": path(f"rim{index}", [place(polygon, r, b) for r, b in corners]),
                      "fill": ui.solid(_rgba(GOLD, alpha)), "blend": "additive", "antialias": index == 0})
    return paths


def glow_paths(colour: list, side: float, end: float) -> list:
    """add_box2 over the view: each edge brightest at the edge and gone
    `side` u (leading and trailing) or `end` u (top and bottom) inward; the
    corners, where two edges meet, add up as the stock's do."""
    falloff = [(0.0, 0.97), (0.143, 0.85), (0.286, 0.63), (0.429, 0.44), (0.571, 0.28), (0.714, 0.15), (0.857, 0.05), (1.0, 0.0)]
    stops = [{"at": at, "color": ui.colour(_rgba(colour, value))} for at, value in falloff]
    w, h = round(side * U, 2), round(end * U, 2)
    one = {"fraction": 1}

    def rect(ident, a, b, start, stop):
        return {"id": ident, "commands": [{"id": "m", "op": "move", "points": [[a[0], a[1]]]},
                                          {"id": "l1", "op": "line", "points": [[b[0], a[1]]]},
                                          {"id": "l2", "op": "line", "points": [[b[0], b[1]]]},
                                          {"id": "l3", "op": "line", "points": [[a[0], b[1]]]},
                                          {"id": "z", "op": "close"}],
                "fill": {"type": "linear", "from": start, "to": stop, "stops": stops}, "blend": "additive", "antialias": False}
    trailing = {"fraction": 1, "dp": -w}
    bottom = {"fraction": 1, "dp": -h}
    return [rect("leading", (0, 0), (w, one), [0, 0], [w, 0]),
            rect("trailing", (trailing, 0), (one, one), [one, 0], [trailing, 0]),
            rect("top", (0, 0), (one, h), [0, 0], [0, h]),
            rect("bottom", (0, bottom), (one, one), [0, one], [0, bottom])]


def static_paths(prefix: str, runs: list) -> list:
    """Streaks at the tile's places as fractions of the view, each one texel
    row (3.75 u) tall, grouped by color and brightness into few paths.
    `runs` holds (row, x0, x1, (r, g, b), level)."""
    groups = {}
    for y, x0, x1, colour, level in runs:
        groups.setdefault((tuple(colour), level), []).append((y, x0, x1))
    paths = []
    row_h = round(480 / 128 * U, 3)
    for index, ((colour, level), items) in enumerate(sorted(groups.items())):
        commands = []
        for y, x0, x1 in items:
            fy, left, right = round(y / 128, 5), round(x0 / 128, 5), round(x1 / 128, 5)
            corners = [({"fraction": left}, {"fraction": fy}), ({"fraction": right}, {"fraction": fy}),
                       ({"fraction": right}, {"fraction": fy, "dp": row_h}), ({"fraction": left}, {"fraction": fy, "dp": row_h})]
            for k, (px, py) in enumerate(corners):
                commands.append({"id": f"c{len(commands)}", "op": "move" if k == 0 else "line", "points": [[px, py]]})
            commands.append({"id": f"c{len(commands)}", "op": "close"})
        paths.append({"id": f"{prefix}{index}", "commands": commands, "fill": ui.solid([*colour, level]), "antialias": False})
    return paths


class Lcg:
    """A fixed generator, so the document rebuilds identically everywhere."""

    def __init__(self, seed: int):
        self.state = seed * 2654435761 % 2 ** 32

    def below(self, n: int) -> int:
        self.state = (self.state * 1664525 + 1013904223) % 2 ** 32
        return (self.state >> 8) % n


# Strogg runes as editable strokes on a 6x8 cell (y down), as the atlas's
# implant sheet draws its rune fields: angular bars, hooks and cuts after the
# Strogg face. The overlay's readouts and data are runes, not text, so they
# need no language keys; the save notice stays a localized message.
RUNE_STROKES = [
    "M1 0V8L5 6", "M5 0L1 3V8M1 5H4", "M0 1L3 0L6 1V5L3 8", "M1 0V5L5 8M5 0V3", "M0 8L2 0H6L4 4",
    "M3 0V8M0 3L3 5L6 3", "M0 0L4 2V8M6 3L4 5", "M5 0H1V4L5 8", "M0 2L3 0L6 2M3 0V8M0 8H3", "M1 8V2L4 0L6 2V5",
    "M0 0V4L6 8M3 2L6 0", "M6 0L0 4L6 8M3 6V8", "M2 0V3L6 5V8M0 8L2 6", "M1 0L5 4L1 8M5 6V8", "M0 0H4L6 2V8M0 4H3",
    "M6 0V5L3 8L0 6M0 0L3 2",
]
RUNE_DOT = "M2 7H4V8H2Z"


def rune_commands(text_lines: list, *, x: float, y: float, height: float, pitch: float, advance: float) -> list:
    """Stroke commands for lines of rune text, each glyph `height` u tall
    from its line's top at (x, y + row * pitch), `advance` u apart. A
    character picks its rune by code; spaces stay empty."""
    commands = []
    scale = height / 8 * U
    for row, line in enumerate(text_lines):
        for column, ch in enumerate(line):
            if ch == ' ':
                continue
            shape = RUNE_DOT if ch == '.' else RUNE_STROKES[(ord(ch) * 7 + 3) % len(RUNE_STROKES)]
            matrix = (scale, 0, 0, scale, round((x + column * advance) * U, 2), round((y + row * pitch) * U, 2))
            for command in hud_svg.commands(shape, matrix):
                command["id"] = f"c{len(commands)}"
                command["points"] = [[round(px, 1), round(py, 1)] for px, py in command.get("points", [])]
                if not command["points"]:
                    del command["points"]
                commands.append(command)
    return commands


def rune_path(ident: str, commands: list, colour: list, height: float) -> dict:
    return {"id": ident, "commands": commands, "fill": {"type": "none"}, "antialias": False,
            "stroke": {"paint": ui.solid(colour), "widthDp": round(height / 7 * U, 3), "minimumPixels": 0, "join": "miter",
                       "cap": "square"}}


def rune_lines(seed: int, lines: int, width: int, *, spaced: bool = False) -> list:
    """Strogg data: rows of rune codes, deterministic."""
    rng = Lcg(seed + 1)
    rows = []
    for _ in range(lines):
        if spaced:
            words = [''.join(RUNES[rng.below(len(RUNES))] for _ in range(2 + rng.below(5))) for _ in range(1 + rng.below(3))]
            rows.append(' '.join(words)[:width])
        else:
            rows.append(''.join(RUNES[rng.below(len(RUNES))] for _ in range(width)))
    return rows


def readout_cycle(doc: HudDocument, ident: str, values: list, cycle: int, *, size: float, x: float, top: float) -> tuple:
    """One stock readout: its values stacked, each shown for `cycle` ms in
    turn (white at 0.2, in runes as the stock's Strogg face drew them).
    Reduced motion ends the loop on the first value."""
    nodes, tracks = [], []
    period = cycle * len(values)
    height = size * 0.72
    for k, value in enumerate(values):
        commands = rune_commands([value], x=x, y=top + (size - height) / 2, height=height, pitch=0, advance=height * 0.95)
        node = vec(f"{ident}-v{k}", [rune_path("r", commands, [1, 1, 1, 0.2], height)], {"opacity": num(1 if k == 0 else 0)})
        nodes.append(node)
        start, stop = cycle * k, cycle * (k + 1)
        if k == 0:
            keys = [(0, num(1)), (stop - 1, num(1)), (stop, num(0)), (period - 1, num(0)), (period, num(1))]
        else:
            keys = [(0, num(0)), (start - 1, num(0)), (start, num(1)), (stop - 1, num(1)), (stop, num(0))]
            if stop < period:
                keys.append((period, num(0)))
        tracks.append(tr(node["id"], "opacity", keys))
    doc.timeline(ident + "-cycle", period, tracks, iterations=0)
    return nodes, ident + "-cycle"


def rune_field(doc: HudDocument, ident: str, edges: dict, width: float, height: float, rate: float, seed: int) -> tuple:
    """A stock scrolltext window: lines of runes rising through a clipped
    window (white at 0.2), as fast as the stock material scrolls. The window
    sits on the view's edges by the HUD's insets (`edges` maps left, right,
    top or bottom to u), outside the scaled anchors: a clip under a transform
    would cut every vertex of the moving runes on the CPU each frame."""
    glyph, pitch, lines = 3.6, 5.5, 16
    period = lines * pitch
    rows = rune_lines(seed, lines, 8, spaced=True)
    commands = rune_commands(rows + rows, x=1, y=0.5, height=glyph, pitch=pitch, advance=glyph * 1.05)
    column = vec(ident + "-runes", [rune_path("r", commands, [1, 1, 1, 0.2], glyph)],
                 {**ui.absolute(left=0, top=0, width=u(width), height=u(period * 2)), "transform": ui.transform()})
    window = ui.group(ident, {**ui.absolute(**{side: u(value) for side, value in edges.items()}, width=u(width), height=u(height)),
                              "display": ui.keyword("block"), "overflow": ui.keyword("hidden")}, [column])
    for side, value in edges.items():
        doc.bind(f"{ident}.{side}", ident, side, op("+", S("hud." + side), u(value)))
    duration = round(period / rate * 1000)
    doc.timeline(ident + "-scroll", duration,
                 [tr(column["id"], "transform", [(0, transform_value(0, 0)), (duration, transform_value(0, u(-period)))])], iterations=0)
    return window, ident + "-scroll"


def data_layers(doc: HudDocument) -> tuple:
    """strogg/data's three layers of rune columns over the whole view, each
    falling at its material's rate (one 480 u view height per second for the
    first, 1.5 and 0.5 for the others), the columns sparse as the stock's."""
    groups, timelines = [], []
    # Each column repeats every 480 u, the distance a layer falls before its
    # loop restarts, and spans 1920 u so the view stays covered from 9:16's
    # top band to its bottom band throughout the fall.
    fall, span = 480, 1920
    for index, (glyph, pitch, speed, shift) in enumerate(((26, 60, 480, 0), (17, 48, 720, 47), (38, 96, 240, 93))):
        commands = []
        rng = Lcg(500 + index)
        for x in range(-560 + shift, 1200, 190):
            # Columns keep the stock's gaps: about half the places are empty.
            period = [RUNES[rng.below(len(RUNES))] if rng.below(2) else ' ' for _ in range(fall // pitch)]
            for row in range(span // pitch):
                ch = period[row % len(period)]
                if ch == ' ':
                    continue
                for command in rune_commands([ch], x=x, y=row * pitch, height=glyph, pitch=0, advance=0):
                    command["id"] = f"c{len(commands)}"
                    commands.append(command)
        layer = vec(f"med-data{index}", [rune_path("r", commands, [1, 1, 1, 1], glyph)],
                    {**ui.absolute(left=0, top=u(-480 - fall), width=u(640), height=u(span)), "transform": ui.transform()})
        duration = round(fall / speed * 1000)
        doc.timeline(f"med-data{index}-fall", duration,
                     [tr(layer["id"], "transform", [(0, transform_value(0, 0)), (duration, transform_value(0, u(fall)))])], iterations=0)
        groups.append(layer)
        timelines.append(f"med-data{index}-fall")
    return groups, timelines


def medchange_document() -> dict:
    """guis/vehicles/medchange.gui (14.19)."""
    doc = HudDocument("openq4.hud.remastered.medchange")
    layout_state(doc)
    doc.boolean("oq4.medActive")
    doc.boolean("oq4.medHurt")
    doc.boolean("oq4.medSaved")
    reduced = S("oq4.reduced")
    loops = []

    # The hexagon field on the centered 640x480 u screen.
    phases = lattice()
    cells, flash = [], []
    for phase, origins in phases.items():
        node = vec(f"med-p{phase}", hex_paths(f"p{phase}", origins), {"opacity": num(0)})
        cells.append(node)
        flash.append(tr(node["id"], "opacity", flash_keys(phase)))
    # The cells fade with the corner pieces from 4150 ms, which is the gentle
    # fade of the steady cells reduced motion keeps (the flashes' last key).
    center = ui.group("med-center", {"position": ui.keyword("absolute"), "left": ui.length(50, "%"), "margin-left": ui.length(-480),
                                     "top": ui.length(50, "%"), "margin-top": ui.length(-360), "width": ui.length(960),
                                     "height": ui.length(720), "display": ui.keyword("block"), "opacity": num(1)}, cells)
    doc.timeline("med-flash", ACTIVE_MS, flash)

    # The data and static layers and the orange edge glow, over the view.
    data, falls = data_layers(doc)
    data_root = ui.group("med-data", {**ui.absolute(left=0, top=0), "width": ui.length(100, "%"), "height": ui.length(100, "%"),
                                      "display": ui.keyword("block"), "opacity": num(0.1)},
                         [ui.group("med-data-c", {"position": ui.keyword("absolute"), "left": ui.length(50, "%"),
                                                   "margin-left": ui.length(-480), "top": ui.length(50, "%"), "margin-top": ui.length(-360),
                                                   "width": ui.length(960), "height": ui.length(720), "display": ui.keyword("block")}, data)])
    # Travelling noise goes under reduced motion.
    doc.show(data_root["id"], NOT(reduced))
    loops += falls
    # img_static3 under its pink matcolor, and colorstatic in its own colors.
    pink = vec("med-static1", static_paths("s", [(y, x0, x1, (1.0, 0.741, 0.741), level) for y, x0, x1, level in STATIC_STREAKS]),
               {"opacity": num(0.6)})
    colour = vec("med-static2", static_paths("c", [(y, x0, x1, tuple(c / 4 for c in rgb4), level)
                                                   for y, x0, x1, rgb4, level in STATIC_DASHES[::2]]), {"opacity": num(0.2)})
    glow = vec("med-glow", glow_paths(ORANGE, 140, 105), {"opacity": num(1)})

    # The corner pieces, readouts and rune fields, which fade together at 4150 ms.
    corners = vec("med-corners", corner_paths())
    proc, proc_loops = [], []
    for index, (top, cycle) in enumerate(((437, 100), (455, 200))):
        nodes, loop = readout_cycle(doc, f"med-proc{index}", READOUT_VALUES, cycle, size=11.52, x=54, top=top + (19 - 11.52) / 2)
        proc += nodes
        proc_loops.append(loop)
        # The segmented processor bar: nine segments over 49x12 u at x 3,
        # the last lit as the stock texture's end cap.
        segments = []
        for k in range(9):
            sx = 3 + k * 5.5
            fill = ui.solid(_rgba(BAR, 0.4)) if k == 8 else ui.linear((0, u(top)), (0, u(top + 12)),
                                                                     [(0, _rgba(BAR, 0.2)), (1, _rgba(BAR, 0.13))])
            segments.append({"id": f"s{k}", "commands": _commands([[(sx, top), (sx + 3.4, top), (sx + 3.4, top + 12), (sx, top + 12)]]),
                             "fill": fill, "antialias": False})
        proc.append(vec(f"med-bar{index}", segments))
    axes, axis_loops = [], []
    for name, values, top, cycle in AXES:
        nodes, loop = readout_cycle(doc, f"med-{name.lower()}", [f"{name}> {v}" for v in values], cycle, size=19.2, x=542,
                                    top=top + (22 - 19.2) / 2)
        axes += nodes
        axis_loops.append(loop)
    # scrolltext1 (574, 70, 58x72) at the trailing screen's top, scrolltext2
    # (2, 350, 67x81) at the leading screen's bottom.
    field1, scroll1 = rune_field(doc, "med-runes1", {"right": 640 - 574 - 58, "top": 70}, 58, 72, 0.35 * 72, 7)
    field2, scroll2 = rune_field(doc, "med-runes2", {"left": 2, "bottom": 480 - 350 - 81}, 67, 81, 0.12 * 81, 11)
    loops += proc_loops + axis_loops + [scroll1, scroll2]
    frame = full("med-frame", [corners, anchor(doc, "bl", proc, ident="med-bl"), anchor(doc, "tr", axes, ident="med-tr"), field1, field2],
                 opacity=num(1))

    overlay = full("med-all", [data_root, pink, colour, glow, center, frame], display=ui.keyword("none"))
    doc.show(overlay["id"], S("oq4.medActive"))
    doc.timeline("med-activate", ACTIVE_MS, [
        tr("med-frame", "opacity", [(0, num(1)), (FADE_AT, num(1)), (ACTIVE_MS, num(0))]),
        tr("med-center", "opacity", [(0, num(1)), (FADE_AT, num(1)), (ACTIVE_MS, num(0))]),
        tr("med-glow", "opacity", [(0, num(1)), (ACTIVE_MS, num(round(1 - ACTIVE_MS / 6000, 4)))]),
        tr("med-static1", "opacity", [(0, num(0.6)), (ACTIVE_MS, num(round(0.6 * (1 - ACTIVE_MS / 5000), 4)))]),
        tr("med-static2", "opacity", [(0, num(0.2)), (ACTIVE_MS, num(round(0.2 * (1 - ACTIVE_MS / 5000), 4)))]),
        tr("med-data", "opacity", [(0, num(0.1)), (ACTIVE_MS, num(round(0.1 * (1 - ACTIVE_MS / 5000), 4)))]),
    ], complete="medDone", essential=True)
    # Every activate restarts the clocks; the overlay hides at 4650 ms.
    doc.on("activate", {"op": "setState", "values": {"oq4.medActive": True}}, play("med-activate"), play("med-flash"),
           *[play(loop) for loop in loops])
    doc.on("medDone", {"op": "setState", "values": {"oq4.medActive": False}}, *[cancel(loop) for loop in loops])

    # Hurt: a red edge pulse from 0.6 over a second, with or without the activation.
    hurt = vec("med-hurt", glow_paths(RED, 140, 105), {"display": ui.keyword("none"), "opacity": num(0.6)})
    doc.show(hurt["id"], S("oq4.medHurt"))
    doc.timeline("med-hurt-run", 1000, [tr("med-hurt", "opacity", [(0, num(0.6)), (1000, num(0))])], complete="medHurtDone",
                 essential=True)
    doc.on("hurt", {"op": "setState", "values": {"oq4.medHurt": True}}, play("med-hurt-run"))
    doc.on("medHurtDone", {"op": "setState", "values": {"oq4.medHurt": False}})

    # The save notice, centered near the top: 2000 ms, then fading over 1000 ms.
    saved = full("med-saved", shadowed("med-saved-text", "#str_200908", face="lowpixel", size=18, colour=[1, 1, 1, 1], baseline=u(80),
                                       center=u(320), width=u(600)), display=ui.keyword("none"), opacity=num(1))
    doc.show(saved["id"], S("oq4.medSaved"))
    doc.timeline("med-saved-run", 3000, [tr("med-saved", "opacity", [(0, num(1)), (2000, num(1)), (3000, num(0))])],
                 complete="medSavedDone", essential=True)
    doc.on("saveMessage", {"op": "setState", "values": {"oq4.medSaved": True}}, play("med-saved-run"))
    doc.on("medSavedDone", {"op": "setState", "values": {"oq4.medSaved": False}})
    doc.on("hudJoin", {"op": "setState", "values": {"oq4.medActive": False}})

    root = gameplay_root(doc, "hud-root", [overlay, hurt, anchor(doc, "tc", [saved], ident="med-tc")])
    joins = join_events(doc, [("all::visible", "activate"), ("quicksave_msg::visible", "saveMessage")])
    return doc.build(root, {"canvas": {"height": 720, "minWidth": 960},
                            "extensions": {"openq4": {"reference": "ui-visual-design.md 14.19", "stock": "guis/vehicles/medchange.gui",
                                                      "joinEvents": joins}}})
