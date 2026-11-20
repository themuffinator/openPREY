#!/usr/bin/env python3
# Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
"""Generate openPREY's retained initializing screen.

    python tools/ui/build_retained_initialization.py           write the document and its textures
    python tools/ui/build_retained_initialization.py --check   exit 1 if any is stale

The screen the engine draws while it starts (RetainedUI_DrawInitialization in
src/ui/RetainedUI.cpp), composed in section 12.6 of
docs/dev/prey-ui-visual-design.md: a ball of portal energy low on the screen
sends a beam straight up into a horizontal lens flare, the PREY wordmark sits
on the flare, and a nebula drifts behind them.

Light is drawn as textured quads: initialization_textures.py paints the
nebula, a soft glow, the orb and its limb, spiralling plasma, a plasma arc, a
lens ring and a burst of rays from fixed seeds, and the screen scales, turns
and tints them. A quad costs four
vertices however soft its light, where a vector gradient that soft costs
thousands, and it scales and turns without being compiled again. The edges
that must stay sharp are vectors: the wordmark, traced from openPREY's own
menu face (content/basepr/pak0/fonts/menu.ttf), the beam, the stars and the
progress rule. Nothing comes from the retail archives.

Lengths are dp on the retained interface's 720 dp canvas, measured from the
screen's centre: x runs right and y runs down, so a 16:9 screen spans x -640
to 640 and y -360 to 360.
"""

from __future__ import annotations

import argparse
import io
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_retained_screens as ui  # noqa: E402

OUT = ui.ROOT / "content" / "basepr" / "pak0" / "guis" / "loading" / "initialization.rui"
TEXTURE_DIR = ui.ROOT / "content" / "basepr" / "pak1" / "guis" / "assets" / "initialization"
TEXTURE_VFS = "guis/assets/initialization/"
MENU_FACE = ui.ROOT / "content" / "basepr" / "pak0" / "fonts" / "menu.ttf"

# The stage: a box far larger than any screen, centred on it, so that the
# scene runs full-bleed from 4:3 to 32:9 and on screens taller than wide.
STAGE_W, STAGE_H = 3200, 1800
CX, CY = STAGE_W / 2, STAGE_H / 2

BALL = (0.0, 128.0)       # the energy ball's centre
FLARE = (0.0, -148.0)     # the flare's centre, where the wordmark sits
STATUS_Y = 262.0          # the status line's centre
RULE_Y = 292.0            # the progress rule's top
NEBULA_DP = (2000, 1000)  # the nebula textures' extent (initialization_textures.NEBULA_DP)

# Colours (section 4 of the visual specification). The scene is portal light
# in space: the cool register alone.
PORTAL_BODY = "#2F64DC"   # prey.portal.body
PORTAL_CORE = "#A4F9FE"   # prey.portal.core
PORTAL_PEAK = "#DDFFFF"
EDGE = "#AFFCFF"          # prey.wordmark.edge
STREAK = "#3380B1"        # prey.wordmark.streak
STREAK_CORE = "#CFF6FF"
TEXT = "#B3CCE6"          # prey.text.nav

SNAP = 0.001              # a key just after a timeline's start: where the motion itself begins
HIDDEN = 0.001            # the scale of a light at rest between its appearances
EASE = [0.33, 0, 0.2, 1]
EASE_OUT = [0.16, 0.7, 0.3, 1]
EASE_IN_OUT = [0.45, 0, 0.55, 1]
SOFT = [0.4, 0, 0.6, 1]


# ------------------------------------------------------------------ helpers

def at(x: float, y: float) -> list[float]:
    """A point measured from the screen's centre, in stage dp."""
    return [round(CX + x, 3), round(CY + y, 3)]


def pose(tx: float = 0.0, ty: float = 0.0, sx: float = 1.0, sy: float | None = None, rot: float = 0.0) -> dict:
    return {"type": "transform", "unit": "dp",
            "value": [round(tx, 3), round(ty, 3), round(sx, 4), round(sx if sy is None else sy, 4), round(rot, 3)]}


def box(x: float, y: float, w: float, h: float) -> dict:
    """Absolute placement of a w x h box centred at x, y (screen dp)."""
    return {"position": ui.keyword("absolute"), "left": ui.length(CX + x - w / 2), "top": ui.length(CY + y - h / 2),
            "width": ui.length(w), "height": ui.length(h)}


def sprite(ident: str, texture: str, x: float, y: float, w: float, h: float | None = None, *,
           tint: str = "#FFFFFF", strength: float = 1.0, transform: dict | None = None, **props) -> dict:
    """A texture of light added to the screen, w x h dp about x, y. The tint's
    strength scales its light."""
    return {"id": ident, "type": "image", "properties": {
        "image": ui.image(TEXTURE_VFS + texture + ".png"), "image-fit": ui.keyword("fill"),
        "image-blend": ui.keyword("additive"), "image-color": ui.colour(ui.rgb(tint, round(strength, 4))),
        **box(x, y, w, w if h is None else h), "transform": transform or pose(), **props}}


def holder(ident: str, x: float, y: float, r: float, children: list[dict], **props) -> dict:
    """A group whose box is the square about x, y (screen dp) of half-width r,
    so its transforms scale and turn about that point. Children placed in
    stage dp keep their places on the screen."""
    left, top = CX + x - r, CY + y - r
    moved = []
    for child in children:
        child = dict(child)
        child["properties"] = dict(child["properties"])
        for edge, offset in (("left", left), ("top", top)):
            child["properties"][edge] = ui.length(child["properties"][edge]["value"] - offset)
        moved.append(child)
    return ui.group(ident, {"position": ui.keyword("absolute"), "left": ui.length(left), "top": ui.length(top),
                            "width": ui.length(2 * r), "height": ui.length(2 * r), **props}, moved)


STAGE_FILL = {"position": ui.keyword("absolute"), "left": ui.length(0), "top": ui.length(0),
              "width": ui.length(STAGE_W), "height": ui.length(STAGE_H)}


def layer(ident: str, children: list[dict], **props) -> dict:
    """A group covering the whole stage: its transforms turn and scale about
    the screen's centre."""
    return ui.group(ident, {**STAGE_FILL, **props}, children)


def loop(doc: ui.Document, ident: str, node: str, period: int, poses: list[tuple[float, dict]]) -> None:
    """A repeating transform: poses at fractions of the period, eased softly,
    returning to the first."""
    keys = [(round(period * t), value, SOFT) for t, value in poses]
    keys.append((period, poses[0][1]))
    doc.timeline(ident, period, [ui.track(node, "transform", keys)], iterations=0)


def spin(doc: ui.Document, node: str, period: int, turns: float, *, sx: float = 1, sy: float = 1, rot: float = 0) -> None:
    """A steady turn, linear, forever, keeping the node's own scale and angle."""
    doc.timeline(f"{node}-turn", period, [ui.track(node, "transform", [
        (0, pose(sx=sx, sy=sy, rot=rot)), (period, pose(sx=sx, sy=sy, rot=rot + 360 * turns))])], iterations=0)


# -------------------------------------------------------------------- space

STAR_TONES = ["#FFFFFF", "#DCE8FF", "#C4D6FF", "#E8F6FF", "#FFF4E8", "#BFE9FF"]


def stars(rng: random.Random, count: int) -> list[dict]:
    """Sharp points of light: small diamonds, antialiased."""
    paths = []
    for i in range(count):
        x, y = at(rng.uniform(-1450, 1450), rng.uniform(-800, 800))
        r = rng.uniform(0.55, 1.25) if rng.random() < 0.85 else rng.uniform(1.25, 1.9)
        alpha = rng.uniform(0.25, 0.7) if r < 1.25 else rng.uniform(0.6, 0.95)
        paths.append(ui.poly(f"s{i}", [(round(x, 2), round(y - r, 2)), (round(x + r, 2), round(y, 2)),
                                       (round(x, 2), round(y + r, 2)), (round(x - r, 2), round(y, 2))],
                             fill=ui.solid(ui.rgb(rng.choice(STAR_TONES), round(alpha, 3)))))
    return paths


# Bright stars with lens spikes: (x, y, size, twinkle period ms).
BRIGHT_STARS = [(-560, -40, 1.0, 3100), (470, -300, 0.8, 4300), (-930, -280, 0.9, 3700),
                (830, 190, 1.1, 5200), (-300, 290, 0.7, 2900), (1080, -120, 0.9, 4700),
                (300, 70, 0.6, 3400), (-1180, 40, 0.8, 4100), (640, -470, 0.7, 3900),
                (-760, 330, 0.6, 3300), (180, -330, 0.55, 4500)]


def bright_star(doc: ui.Document, index: int, x: float, y: float, size: float, period: int) -> dict:
    ident = f"star-{index}"
    parts = [sprite(f"{ident}-halo", "glow", x, y, 40 * size, tint="#8FB8FF", strength=0.55),
             sprite(f"{ident}-core", "glow", x, y, 9 * size, strength=1.0),
             sprite(f"{ident}-h", "glow", x, y, 64 * size, 2.4 * size, tint="#DCEBFF", strength=0.9),
             sprite(f"{ident}-v", "glow", x, y, 2.4 * size, 64 * size, tint="#DCEBFF", strength=0.9)]
    node = holder(ident, x, y, 34 * size, parts, transform=pose())
    loop(doc, f"{ident}-twinkle", ident, period, [(0, pose()), (0.42, pose(sx=0.5)), (0.6, pose(sx=1.15))])
    return node


def space(doc: ui.Document, rng: random.Random) -> dict:
    far = sprite("nebula-far", "nebula_far", 0, 0, *NEBULA_DP)
    near = sprite("nebula-near", "nebula_near", 0, 0, *NEBULA_DP)
    # The nebula drifts: the far gas and the near wisps turn and swell on
    # different slow cycles, so they part a little against each other.
    loop(doc, "nebula-far-drift", "nebula-far", 96000, [(0, pose()), (0.5, pose(sx=1.04, rot=1.2))])
    loop(doc, "nebula-near-drift", "nebula-near", 70000,
         [(0, pose()), (0.5, pose(tx=-18, ty=8, sx=1.07, rot=-1.6))])
    bright = [bright_star(doc, i, *star) for i, star in enumerate(BRIGHT_STARS)]
    return layer("scene", [far, near, *bright], transform=pose())


def sharp_stars(rng: random.Random) -> dict:
    """The sharp stars hold still: antialiased edges would be compiled again
    at every step of a turn or a zoom."""
    return ui.vector("stars", dict(STAGE_FILL), stars(rng, 300))


# ------------------------------------------------------------------- energy

def orbit(doc: ui.Document, k: int, radius: float, tilt: float, squash: float, period: int, turns: int,
          strength: float) -> dict:
    """A loop of plasma round the ball: an arc turns on a ring that is
    flattened and then tilted, so it runs round an ellipse seen at an angle."""
    x, y = BALL
    ident = f"orbit-{k}"
    size = radius / 0.8 * 2          # the arc texture's ring lies at 0.8 of its half-width
    arc = sprite(ident, "arc", x, y, size, strength=strength, transform=pose(sy=squash))
    spin(doc, ident, period, turns, sy=squash)
    return holder(f"{ident}-tilt", x, y, size / 2, [arc], transform=pose(rot=tilt))


ORB_R = 0.62              # the orb's disc in its textures (initialization_textures.ORB_R)
BALL_R = 56               # the ball's radius in dp


def energy_ball(doc: ui.Document) -> dict:
    """A sphere of portal energy: a turning inside of plasma filaments under a
    bright limb, spiralling plasma at its heart, loops of plasma on tilted
    orbits, rays, and a halo that lights the space about it."""
    x, y = BALL
    orb_size = 2 * BALL_R / ORB_R
    parts = [
        sprite("ball-halo", "glow", x, y, 720, tint=PORTAL_BODY, strength=0.6),
        sprite("ball-corona", "glow", x, y, 320, tint="#5AB4FF", strength=0.6),
        sprite("ball-rays-a", "rays", x, y, 420, tint=PORTAL_CORE, strength=0.5),
        sprite("ball-rays-b", "rays", x, y, 320, tint="#7FD0FF", strength=0.4, transform=pose(rot=40)),
        sprite("ball-orb", "orb", x, y, orb_size, strength=1.0),
        sprite("ball-plasma-a", "plasma", x, y, 170, strength=0.38),
        sprite("ball-plasma-b", "plasma", x, y, 130, strength=0.3, transform=pose(rot=120)),
        sprite("ball-shell", "shell", x, y, orb_size, strength=1.0),
        orbit(doc, 0, 74, -22, 0.30, 2700, 1, 0.9),
        orbit(doc, 1, 86, 33, 0.24, 3900, -1, 0.75),
        orbit(doc, 2, 68, 80, 0.36, 3300, 1, 0.7),
        orbit(doc, 3, 102, -62, 0.20, 5600, -1, 0.55),
        sprite("ball-core", "glow", x, y, 62, tint="#E6FCFF", strength=0.55),
        sprite("ball-hot", "glow", x, y, 26, strength=0.75),
    ]
    spin(doc, "ball-orb", 14000, -1)
    loop(doc, "ball-shell-breathe", "ball-shell", 1900, [(0, pose()), (0.45, pose(sx=1.025))])
    spin(doc, "ball-rays-a", 26000, 1)
    spin(doc, "ball-rays-b", 41000, -1, rot=40)
    spin(doc, "ball-plasma-a", 9000, 1)
    spin(doc, "ball-plasma-b", 6500, -1, rot=120)
    loop(doc, "ball-halo-breathe", "ball-halo", 4200, [(0, pose()), (0.5, pose(sx=1.08))])
    loop(doc, "ball-corona-breathe", "ball-corona", 2300, [(0, pose()), (0.4, pose(sx=1.12))])
    loop(doc, "ball-core-pulse", "ball-core", 1300, [(0, pose()), (0.4, pose(sx=1.08))])
    loop(doc, "ball-hot-flicker", "ball-hot", 940, [(0, pose()), (0.18, pose(sx=1.16)), (0.35, pose(sx=0.92)),
                                                    (0.65, pose(sx=1.08))])
    return holder("ball", x, y, 360, parts, transform=pose())


BEAM_TOP = -980           # the beam runs off the top of the tallest screen
BEAM_W = 180


def shaft(ident: str, width: float, stops: list) -> dict:
    """A vertical band of the beam with a horizontal gradient: one quad split
    at each stop."""
    x, y = BALL
    left, top = CX + x - width / 2, CY + BEAM_TOP
    height = y - BEAM_TOP
    paint = ui.linear((0, 0), (width, 0), [(t, ui.rgb(c, a)) for t, c, a in stops])
    path = {"id": "light", "commands": [
        {"id": "p0", "op": "move", "points": [[0, 0]]}, {"id": "p1", "op": "line", "points": [[width, 0]]},
        {"id": "p2", "op": "line", "points": [[width, height]]}, {"id": "p3", "op": "line", "points": [[0, height]]},
        {"id": "p4", "op": "close"}], "fill": paint, "blend": "additive", "antialias": False}
    return ui.vector(ident, {"position": ui.keyword("absolute"), "left": ui.length(left), "top": ui.length(top),
                             "width": ui.length(width), "height": ui.length(height), "transform": pose()}, [path])


def beam(doc: ui.Document) -> dict:
    x, y = BALL
    glow_shaft = shaft("beam-glow", BEAM_W, [(0, PORTAL_BODY, 0), (0.22, PORTAL_BODY, 0.04), (0.36, PORTAL_BODY, 0.1),
                                             (0.45, "#3E86F0", 0.2), (0.5, "#4C98F5", 0.26), (0.55, "#3E86F0", 0.2),
                                             (0.64, PORTAL_BODY, 0.1), (0.78, PORTAL_BODY, 0.04), (1, PORTAL_BODY, 0)])
    body = shaft("beam-body", 40, [(0, "#5AB4FF", 0), (0.2, "#5AB4FF", 0.12), (0.38, "#7FD0FF", 0.34),
                                   (0.5, PORTAL_CORE, 0.55), (0.62, "#7FD0FF", 0.34), (0.8, "#5AB4FF", 0.12),
                                   (1, "#5AB4FF", 0)])
    core = shaft("beam-core", 9, [(0, PORTAL_PEAK, 0), (0.25, PORTAL_PEAK, 0.45), (0.5, "#FFFFFF", 1.0),
                                  (0.75, PORTAL_PEAK, 0.45), (1, PORTAL_PEAK, 0)])
    loop(doc, "beam-body-shimmer", "beam-body", 1700, [(0, pose()), (0.25, pose(sx=1.16, sy=1)), (0.62, pose(sx=0.9, sy=1))])
    loop(doc, "beam-glow-shimmer", "beam-glow", 3100, [(0, pose()), (0.42, pose(sx=1.1, sy=1))])
    loop(doc, "beam-core-shimmer", "beam-core", 610, [(0, pose()), (0.38, pose(sx=1.3, sy=1))])
    # Pulses of energy climbing the beam, each on its own cycle so they never
    # fall into step. They travel from the ball past the flare and fade with
    # the beam; between climbs they rest at no size.
    pulses = []
    rise = -(y - FLARE[1]) - 420
    for k, (period, travel, size) in enumerate(((2300, 1500, 1.0), (2900, 1700, 0.8), (3700, 1400, 1.15),
                                                (4300, 1900, 0.7), (5300, 1600, 0.9))):
        ident = f"pulse-{k}"
        rest = pose(sx=HIDDEN, sy=HIDDEN)
        pulses.append(holder(ident, x, y - 10, 40, [
            sprite(f"{ident}-glow", "glow", x, y - 10, 80, tint="#7FD0FF", strength=0.7),
            sprite(f"{ident}-core", "glow", x, y - 10, 26, strength=0.95)], transform=rest))
        doc.timeline(f"{ident}-climb", period, [ui.track(ident, "transform", [
            (0, rest),
            (SNAP, pose(sx=0.2 * size, sy=0.8 * size), EASE_OUT),
            (travel * 0.18, pose(ty=rise * 0.1, sx=0.42 * size, sy=2.2 * size)),
            (travel * 0.82, pose(ty=rise * 0.8, sx=0.36 * size, sy=2.6 * size), [0.5, 0, 0.9, 0.6]),
            (travel, pose(ty=rise, sx=HIDDEN, sy=1.2 * size)),
            (travel + 1, pose(ty=rise, sx=HIDDEN, sy=HIDDEN)),
            (period, pose(ty=rise, sx=HIDDEN, sy=HIDDEN))])], iterations=0)
    # The beam's front, which leads it out of the ball in the entrance.
    tip = holder("beam-tip", x, y, 120, [sprite("beam-tip-glow", "glow", x, y, 240, tint="#7FD0FF", strength=0.8),
                                         sprite("beam-tip-core", "glow", x, y, 60, strength=1.0)],
                 transform=pose(sx=HIDDEN, sy=HIDDEN))
    shaft_group = layer("beam-shaft", [glow_shaft, body, core], transform=pose())
    group = layer("beam", [shaft_group, *pulses, tip])
    # The beam fades as it climbs: full from the ball to the flare, then away
    # toward the top. Nothing shows below the ball's centre.
    m0x, m0y = at(-STAGE_W / 2, BEAM_TOP)
    m1x, m1y = at(STAGE_W / 2, y)
    mask_paint = ui.linear((m0x, at(0, -620)[1]), (m0x, m1y), [
        (0, [1, 1, 1, 0]), (0.25, [1, 1, 1, 0.22]), (0.52, [1, 1, 1, 0.8]), (0.62, [1, 1, 1, 1]), (1, [1, 1, 1, 1])])
    group["mask"] = {"paths": [{"id": "fade", "commands": [
        {"id": "p0", "op": "move", "points": [[m0x, m0y]]}, {"id": "p1", "op": "line", "points": [[m1x, m0y]]},
        {"id": "p2", "op": "line", "points": [[m1x, m1y]]}, {"id": "p3", "op": "line", "points": [[m0x, m1y]]},
        {"id": "p4", "op": "close"}], "fill": mask_paint}]}
    return group


def flare(doc: ui.Document) -> dict:
    x, y = FLARE
    rays = []
    for k, (angle, length, strength) in enumerate(((90, 620, 0.5), (14, 640, 0.28), (-14, 640, 0.28),
                                                    (38, 420, 0.18), (-38, 420, 0.18), (63, 340, 0.13),
                                                    (-63, 340, 0.13))):
        ray = sprite(f"flare-ray-{k}", "glow", x, y, length, 6, tint="#BCE6FF", strength=strength)
        rays.append(holder(f"flare-ray-{k}-turn", x, y, length / 2, [ray], transform=pose(rot=angle)))
    # The lens ring is a texture: as vector strokes it compiled again at
    # every frame of the flare's entrance.
    ring = sprite("flare-ring", "ring", x, y, 2 * 182 / 0.9, tint="#8FD0FF", strength=0.13)
    parts = [
        sprite("flare-bloom", "glow", x, y, 560, tint="#4C98F5", strength=0.42),
        ring,
        holder("flare-rays", x, y, 330, rays, transform=pose()),
        sprite("flare-burst", "rays", x, y, 300, tint="#BCE6FF", strength=0.4),
        sprite("streak-wide", "glow", x, y, 2600, 90, tint=STREAK, strength=0.9),
        sprite("streak-core", "glow", x, y, 1900, 16, tint=STREAK_CORE, strength=1.0),
        sprite("streak-hot", "glow", x, y, 860, 6, strength=1.0),
        sprite("flare-hot", "glow", x, y, 150, tint="#E6FCFF", strength=1.0),
        sprite("flare-flash", "glow", x, y, 900, tint="#CFF6FF", strength=0.9, transform=pose(sx=HIDDEN, sy=HIDDEN)),
    ]
    loop(doc, "flare-bloom-breathe", "flare-bloom", 5200, [(0, pose()), (0.5, pose(sx=1.08))])
    loop(doc, "streak-wide-breathe", "streak-wide", 6400, [(0, pose()), (0.5, pose(sx=1.06, sy=1.12))])
    loop(doc, "streak-core-breathe", "streak-core", 2900, [(0, pose()), (0.38, pose(sx=1.08, sy=1.15))])
    loop(doc, "flare-rays-sway", "flare-rays", 14000, [(0, pose()), (0.5, pose(rot=4))])
    spin(doc, "flare-burst", 60000, 1)
    return holder("flare", x, y, 1300, parts, transform=pose())


# ----------------------------------------------------------------- wordmark

def glyph_contours() -> dict:
    """P, R, E and Y from the menu face, as move/line/quadratic commands in
    font units (y up)."""
    from fontTools.pens.basePen import BasePen
    from fontTools.ttLib import TTFont

    class Recorder(BasePen):
        def __init__(self, glyphs):
            super().__init__(glyphs)
            self.out: list[tuple] = []

        def _moveTo(self, pt):
            self.out.append(("move", [pt]))

        def _lineTo(self, pt):
            self.out.append(("line", [pt]))

        def _qCurveToOne(self, pt1, pt2):
            self.out.append(("quadratic", [pt1, pt2]))

        def _curveToOne(self, pt1, pt2, pt3):
            self.out.append(("cubic", [pt1, pt2, pt3]))

        def _closePath(self):
            self.out.append(("close", []))

    font = TTFont(str(MENU_FACE))
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    result = {}
    for ch in "PREY":
        pen = Recorder(glyphs)
        glyphs[cmap[ord(ch)]].draw(pen)
        xs = [p[0] for _, pts in pen.out for p in pts]
        result[ch] = (pen.out, min(xs), max(xs))
    return result


CAP_DP = 54               # the capitals' height
WIDEN = 1.6               # the wordmark's extension, as the Interface Atlas draws it
WORD_W = 700              # from the P's stem to the Y's arm
CAPS = (129, 1026)        # the menu face's capitals, in font units


def wordmark_paths() -> list[dict]:
    """The letters as one path each, in stage dp."""
    glyphs = glyph_contours()
    scale = CAP_DP / (CAPS[1] - CAPS[0])
    widths = [(hi - lo) * scale * WIDEN for _, lo, hi in glyphs.values()]
    gap = (WORD_W - sum(widths)) / 3
    fx, fy = at(*FLARE)
    cursor = fx - WORD_W / 2
    letters = []
    for (ch, (ops, lo, _)), width in zip(glyphs.items(), widths):
        def out(pt, lo=lo, left=cursor):
            return [round(left + (pt[0] - lo) * scale * WIDEN, 3), round(fy - (pt[1] - sum(CAPS) / 2) * scale, 3)]
        commands = []
        for op, pts in ops:
            command = {"id": f"p{len(commands)}", "op": op}
            if pts:
                command["points"] = [out(p) for p in pts]
            commands.append(command)
        letters.append({"id": f"letter-{ch}", "commands": commands})
        cursor += width + gap
    return letters


def wordmark(doc: ui.Document) -> dict:
    """PREY as the specification's wordmark: very wide capitals with a dark
    fill and a thin cyan-white edge, sitting on the flare's streak."""
    letters = wordmark_paths()
    fx, fy = at(*FLARE)
    top, bottom = fy - CAP_DP / 2, fy + CAP_DP / 2
    fill = ui.linear((fx, top), (fx, bottom), [(0, ui.rgb("#16304C")), (0.42, ui.rgb("#050B12")), (0.5, ui.rgb("#010204")),
                                               (0.58, ui.rgb("#050B12")), (1, ui.rgb("#10243A"))])
    glows = []
    for n, (width, alpha) in enumerate(((22, 0.03), (13, 0.05), (7, 0.08), (3.4, 0.14))):
        for letter in letters:
            glows.append({**letter, "id": f"glow-{n}-{letter['id']}", "fill": {"type": "none"},
                          "stroke": ui.stroke(ui.solid(ui.rgb("#5FD2FF", alpha)), width, minimum=0, join="round", cap="round"),
                          "blend": "additive", "antialias": False})
    solid_letters = [{**letter, "fill": fill, "stroke": ui.stroke(ui.solid(ui.rgb(EDGE, 0.95)), 1.5, minimum=1, join="round")}
                     for letter in letters]
    halo = ui.vector("wordmark-halo", dict(STAGE_FILL), glows)
    body = ui.vector("wordmark-letters", dict(STAGE_FILL), solid_letters)
    # A narrow light that crosses the lettering, clipped to its outlines.
    span = WORD_W + 400
    sweep_l = fx - span / 2
    light = [{"id": "light", "commands": [
        {"id": "p0", "op": "move", "points": [[sweep_l - 60, top - 20]]},
        {"id": "p1", "op": "line", "points": [[sweep_l + 60, top - 20]]},
        {"id": "p2", "op": "line", "points": [[sweep_l + 20, bottom + 20]]},
        {"id": "p3", "op": "line", "points": [[sweep_l - 100, bottom + 20]]},
        {"id": "p4", "op": "close"}],
        "fill": ui.linear((sweep_l - 80, fy), (sweep_l + 40, fy), [(0, [0.85, 0.97, 1, 0]), (0.5, [0.85, 0.97, 1, 0.55]),
                                                                   (1, [0.85, 0.97, 1, 0])]),
        "blend": "additive", "antialias": False}]
    glint_light = ui.vector("glint-light", {**STAGE_FILL, "transform": pose(tx=-200)}, light)
    glint = ui.group("wordmark-glint", {**STAGE_FILL, "display": ui.keyword("block")}, [glint_light])
    glint["mask"] = {"paths": [{**letter, "fill": ui.solid([1, 1, 1, 1])} for letter in letters]}
    doc.bind("wordmark-glint", "display", {"op": "select", "args": [{"state": "motion_reduced"}, "none", "block"]})
    # The first pass follows the entrance; then one every 9 s.
    doc.timeline("glint-pass", 9000, [ui.track("glint-light", "transform", [
        (0, pose(tx=-200)), (1150, pose(tx=-200), EASE_IN_OUT), (2150, pose(tx=span + 200)), (9000, pose(tx=span + 200))])],
        iterations=0)
    return layer("wordmark", [halo, body, glint], opacity=ui.number(1))


# ------------------------------------------------------------------- status

STEP_KEYS = 7             # LOADING..., then Prey's six startup steps (#str_04346 to #str_04351)
SEGMENT_W, SEGMENT_PITCH = 34, 40


def status(doc: ui.Document) -> dict:
    sx, sy = at(-450, STATUS_Y - 15)
    line = {"id": "status", "type": "text", "properties": {
        "text": ui.text("#str_04343"), "position": ui.keyword("absolute"),
        "left": ui.length(sx), "top": ui.length(sy), "width": ui.length(900), "height": ui.length(30),
        "font-family": ui.font(ui.BODY), "font-size": ui.length(20), "line-height": ui.length(30),
        "letter-spacing": ui.length(1.5), "text-align": ui.keyword("center"), "white-space": ui.keyword("nowrap"),
        "color": ui.colour(ui.rgb(TEXT, 0.9)), "opacity": ui.number(1), "transform": pose(), **ui.PASSIVE}}
    doc.bind("status", "text", {"state": "message"})
    # Each step's line rises softly into place instead of replacing the last.
    doc.timeline("status-arrive", 320, [
        ui.track("status", "opacity", [(0, ui.number(1)), (SNAP, ui.number(0), EASE), (280, ui.number(1))]),
        ui.track("status", "transform", [(0, pose()), (SNAP, pose(ty=7), EASE_OUT), (320, pose())])])
    total = SEGMENT_PITCH * (STEP_KEYS - 1) + SEGMENT_W
    left0 = -total / 2
    nodes = []

    def segment(ident: str, i: int, tint: list[float], **props) -> dict:
        lx, ly = at(left0 + i * SEGMENT_PITCH, RULE_Y)
        return ui.vector(ident, {"position": ui.keyword("absolute"), "left": ui.length(lx), "top": ui.length(ly),
                                 "width": ui.length(SEGMENT_W), "height": ui.length(2), **props},
                         [ui.poly("bar", [(0, 0), (SEGMENT_W, 0), (SEGMENT_W, 2), (0, 2)], fill=ui.solid(tint))])

    # The rule fills left to right behind a marker that glides to the current
    # step; several steps between two repaints cascade.
    for i in range(STEP_KEYS):
        nodes.append(segment(f"progress-{i}", i, ui.rgb(TEXT, 0.16)))
        done = f"progress-{i}-done"
        nodes.append(segment(done, i, ui.rgb(TEXT, 0.85), opacity=ui.number(1), display=ui.keyword("none")))
        doc.bind(done, "display", {"op": "select", "args": [{"op": "<=", "args": [i, {"state": "step"}]}, "block", "none"]})
    marker_x = left0 + SEGMENT_W / 2
    marker = holder("progress-marker", marker_x, RULE_Y + 1, 30, [
        sprite("progress-marker-glow", "glow", marker_x, RULE_Y + 1, 60, 22, tint=PORTAL_CORE, strength=0.75),
        sprite("progress-marker-line", "glow", marker_x, RULE_Y + 1, 52, 3, strength=1.0)],
        transform=pose(), display=ui.keyword("block"))
    doc.bind("progress-marker", "display", {"op": "select", "args": [{"state": "motion_reduced"}, "none", "block"]})
    nodes.append(marker)
    doc.state["shown"] = {"type": "number", "initial": -1}
    arrivals = []
    for step in range(STEP_KEYS):
        doc.timeline(f"marker-{step}", 440, [ui.track("progress-marker", "transform",
                                                      [(0, pose(), EASE), (440, pose(tx=SEGMENT_PITCH * step))])])
        arrivals.append({"op": "if", "condition": {"op": "==", "args": [{"state": "step"}, step]},
                         "then": [{"op": "playTimeline", "timeline": f"marker-{step}"}]})
        for shown in range(-1, step):
            tracks = []
            for i in range(shown + 1, step + 1):
                delay = 70 * (i - shown - 1)
                keys = [(0, ui.number(1)), (SNAP, ui.number(0))] + ([(delay, ui.number(0))] if delay > SNAP else [])
                tracks.append(ui.track(f"progress-{i}-done", "opacity",
                                       keys[:-1] + [(keys[-1][0], keys[-1][1], EASE), (delay + 300, ui.number(1))]))
            doc.timeline(f"fill-{shown + 1}-{step}", 70 * (step - shown - 1) + 300, tracks)
            arrivals.append({"op": "if", "condition": {"op": "&&", "args": [
                {"op": "==", "args": [{"state": "shown"}, shown]}, {"op": "==", "args": [{"state": "step"}, step]}]},
                "then": [{"op": "playTimeline", "timeline": f"fill-{shown + 1}-{step}"}]})
    doc.events["stepChanged"] = [
        {"op": "if", "condition": {"op": "!", "args": [{"state": "motion_reduced"}]},
         "then": [{"op": "playTimeline", "timeline": "status-arrive"}, *arrivals]},
        {"op": "setState", "values": {"shown": {"state": "step"}}}]
    return layer("status-block", [line, *nodes], opacity=ui.number(1), transform=pose())


# ----------------------------------------------------------------- document

def document() -> dict:
    rng = random.Random(2006)
    doc = ui.Document("openprey.initialization")
    doc.state["message"] = {"type": "string", "initial": "#str_04343"}
    doc.state["step"] = {"type": "number", "initial": 0}
    doc.state["motion_reduced"] = {"type": "boolean", "initial": False, "cvar": "ui_retainedReducedMotion"}

    full = [(0, 0), ({"fraction": 1}, 0), ({"fraction": 1}, {"fraction": 1}), (0, {"fraction": 1})]
    field = ui.vector("field", dict(ui.FULL), [ui.poly("space", full, fill=ui.linear(
        (0, 0), (0, {"fraction": 1}), [(0, ui.rgb("#010207")), (0.6, ui.rgb("#02040C")), (1, ui.rgb("#040915"))]))])
    star_field = sharp_stars(rng)
    scene = space(doc, rng)
    beam_group = beam(doc)
    ball = energy_ball(doc)
    flare_group = flare(doc)
    mark = wordmark(doc)
    status_block = status(doc)
    stage = ui.group("stage", {"position": ui.keyword("absolute"), "left": ui.length(50, "%"), "top": ui.length(50, "%"),
                               "margin-left": ui.length(-STAGE_W / 2), "margin-top": ui.length(-STAGE_H / 2),
                               "width": ui.length(STAGE_W), "height": ui.length(STAGE_H)},
                     [star_field, scene, beam_group, ball, flare_group, mark, status_block])

    loops = [t["id"] for t in doc.timelines if t.get("iterations") == 0 and t["id"] != "glint-pass"]
    veil = ui.vector("veil", {**ui.FULL, "opacity": ui.number(1), "display": ui.keyword("block")},
                     [ui.poly("black", full, fill=ui.solid([0, 0, 0, 1]))])
    doc.bind("veil", "display", {"op": "select", "args": [{"state": "motion_reduced"}, "none", "block"]})

    # The entrance, after the first veiled frame. The ball ignites from a point
    # and overshoots its size; its beam shoots up out of it, led by a bright
    # front; the front strikes the flare, which flashes and stretches out to
    # either side; the wordmark resolves on the flare, the status line rises
    # into place and the glint crosses the lettering. Space eases back behind it.
    rise = BALL[1] - BEAM_TOP
    launch, arrive = 220, 680
    reach = BALL[1] - FLARE[1]
    strike = launch + int((arrive - launch) * (reach / rise) ** 0.6)
    hidden = pose(sx=HIDDEN, sy=HIDDEN)
    doc.timeline("enter", 1400, [
        ui.track("veil", "opacity", [(0, ui.number(1)), (SNAP, ui.number(1), [0.25, 0.1, 0.25, 1]), (220, ui.number(0))]),
        ui.track("scene", "transform", [(0, pose()), (SNAP, pose(sx=1.1), [0.2, 0.7, 0.3, 1]), (1400, pose())]),
        ui.track("ball", "transform", [(0, pose()), (SNAP, pose(sx=0.02), [0.3, 0, 0.6, 1]),
                                       (70, pose(sx=0.05), EASE_OUT), (300, pose(sx=1.16), [0.45, 0, 0.55, 1]),
                                       (480, pose(sx=0.97), SOFT), (620, pose())]),
        ui.track("beam-shaft", "transform", [(0, pose()), (SNAP, pose(ty=rise)), (launch, pose(ty=rise), [0.5, 0.1, 0.85, 0.6]),
                                             (arrive, pose())]),
        ui.track("beam-tip", "transform", [(0, hidden), (SNAP, hidden), (launch, pose(sx=0.5, sy=1.2), [0.5, 0.1, 0.85, 0.6]),
                                           (arrive, pose(ty=-rise, sx=0.5, sy=2.4)), (arrive + 70, hidden)]),
        ui.track("flare", "transform", [(0, pose()), (SNAP, pose(sx=0.02, sy=0.3)), (strike - 20, pose(sx=0.02, sy=0.3), EASE_OUT),
                                        (strike + 300, pose(sx=1.18, sy=1.05), SOFT), (strike + 540, pose())]),
        ui.track("flare-flash", "transform", [(0, hidden), (SNAP, hidden), (strike - 20, pose(sx=0.1, sy=0.1), EASE_OUT),
                                              (strike + 110, pose(sx=1.25, sy=0.8), SOFT), (strike + 520, hidden)]),
        # The lettering appears under the flash's peak, in 120 ms: a longer
        # fade compiles its glow again at every frame of it. It rests barely
        # above nothing until then, since a transparent node is not compiled
        # and this way it compiles in the veiled first frame.
        ui.track("wordmark", "opacity", [(0, ui.number(1)), (SNAP, ui.number(0.002)), (strike + 40, ui.number(0.002), EASE),
                                         (strike + 160, ui.number(1))]),
        ui.track("status-block", "opacity", [(0, ui.number(1)), (SNAP, ui.number(0)), (strike + 260, ui.number(0), EASE),
                                             (strike + 560, ui.number(1))]),
        ui.track("status-block", "transform", [(0, pose()), (SNAP, pose(ty=8)), (strike + 260, pose(ty=8), EASE_OUT),
                                               (strike + 600, pose())])])
    entrance = [{"op": "playTimeline", "timeline": "enter"}, {"op": "playTimeline", "timeline": "glint-pass"}]
    # onInit starts the loops and the entrance for any host; startup plays the
    # entrance again from onEnter once its first, veiled frame (which pays for
    # the document's creation) is on screen. Reduced motion keeps the rest
    # pose: every node's base value is its place at rest.
    doc.events["onInit"] = [{"op": "if", "condition": {"op": "!", "args": [{"state": "motion_reduced"}]},
                             "then": [*[{"op": "playTimeline", "timeline": t} for t in loops], *entrance]}]
    doc.events["onEnter"] = [{"op": "if", "condition": {"op": "!", "args": [{"state": "motion_reduced"}]}, "then": entrance}]
    return doc.build(ui.group("screen", {**ui.FULL, "overflow": ui.keyword("hidden"), **ui.PASSIVE}, [field, stage, veil]))


# ------------------------------------------------------------------ output

def texture_stale(path: Path, pixels) -> bool:
    """A texture is current when its decoded pixels match: PNG bytes may
    differ between zlib builds."""
    if not path.exists():
        return True
    from PIL import Image
    import numpy as np
    with Image.open(path) as image:
        return not np.array_equal(np.asarray(image.convert("RGB")), pixels)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report stale output instead of writing it")
    args = parser.parse_args()
    import initialization_textures as textures
    from PIL import Image
    stale = []
    built = document()
    ui.check_ids(OUT.name, built)
    rendered = ui.render(built).replace("build_retained_screens.py", "build_retained_initialization.py")
    current = OUT.read_bytes().decode("utf-8").replace("\r\n", "\n") if OUT.exists() else None
    if current != rendered.replace("\r\n", "\n"):
        stale.append(OUT)
        if not args.check:
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_bytes(rendered.encode("utf-8"))
    for name, paint in textures.TEXTURES.items():
        path = TEXTURE_DIR / name
        pixels = paint()
        if texture_stale(path, pixels):
            stale.append(path)
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                buffer = io.BytesIO()
                Image.fromarray(pixels).save(buffer, "PNG", optimize=True)
                path.write_bytes(buffer.getvalue())
    for path in stale:
        verb = "stale" if args.check else "wrote"
        print(f"{verb} {path.relative_to(ui.ROOT).as_posix()}")
    if args.check and stale:
        print("run tools/ui/build_retained_initialization.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
