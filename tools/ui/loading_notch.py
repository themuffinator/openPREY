#!/usr/bin/env python3
# Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
"""The loading screen's name notch: one construction, drawn two ways.

    python tools/ui/loading_notch.py            write the stock screen's textures
    python tools/ui/loading_notch.py --check    exit 1 if any texture is stale

The level's name hangs from the top of the loading screen in a notch made
from Prey's own furniture (docs/dev/prey-ui-visual-design.md, sections 6 and
12.1): the progress bar's outline (`bottombar.tga`) hung from the screen's top
edge and bent into a notch.

- Its two claw ends, turned over so their ears hang down, bolt the notch to
  the top edge beside its shoulders.
- Its rail runs from each claw along the top edge, turns down through a
  concave shoulder, down the slanted side, round the foot's corner and along
  the foot: the progress outline's four bands, the black edge facing the body.
- The sides slant inward toward the foot as the top title bar's ends do and
  round into the foot as a button's leading end does.
- Five groups of three rivets sit on the foot, evenly spaced from end to end.
- The body is black, a little deeper where it hangs from the edge.

The notch fits the level's name: the straight run of its foot is the name's
width plus NAME_PAD on each side, and never less than FOOT_MIN. Every point
below is (fraction, offset, y): x is `fraction` of the notch's width plus
`offset` u, so the same shapes serve any width. The notch's box is END u of
end piece, the foot's straight run, and END u more; BOX_H u tall from the
screen's top edge.

`guis/map/loading.gui` draws it from the textures this tool writes: the end
piece (`namenotch_end`, mirrored for the trailing end), the middle strip
(`namenotch_mid`, stretched) and one rivet group (`namenotch_rivets`), each
placed from the name window's measured `textwidth`. `build_retained_screens.py`
draws the same shapes as one vector in `guis/loading/loading.rui`, sized by
the layout around the name.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXTURES = ROOT / "content" / "basepr" / "pak1" / "guis" / "assets" / "loading"

FOOT = 37.0                 # the body's foot, from the screen's top edge
SLANT = 0.5                 # the sides' inward run per unit of drop, as the top title bar's ends
FILLET = 9.0                # the foot's rounded corners, at the body's edge
SHOULDER = 7.0              # the concave turn from the top edge into the side, at the body's edge
LIP = 6.0                   # the rail's run along the top edge, from the claw to the shoulder
NAME_PAD = 16.0             # clear foot beyond each end of the name
FOOT_MIN = 168.0            # the foot's shortest straight run
RIVET_INSET = 12.0          # the end rivet groups' centres, in from the foot's straight run
BOX_H = 64.0                # the notch's box, from the screen's top edge

# The intro, from the loading screen's first frame (the session's frameIn):
# the notch lowers into view closed, its two ends meeting at the centre, then
# opens to fit the name; the rivets set and the name appears once it is open.
# The progress bar fades in meanwhile. Each part: start and end in ms and its
# easing, a cubic Bezier as the retained timelines take it. The session
# drives the stock screen through the same curves (LOADING_INTRO_PARTS in
# src/framework/Session.cpp), so keep the two in step.
EASE_OUT = [0.33, 1.0, 0.68, 1.0]           # an ease-out cubic
EASE_IN_OUT = [0.65, 0.0, 0.35, 1.0]        # an ease-in-out cubic
EASE_FADE = [0.5, 1.0, 0.89, 1.0]           # an ease-out quadratic
INTRO = {
    "drop": (0, 300, EASE_OUT),             # from BOX_H above the top edge
    "open": (200, 560, EASE_IN_OUT),        # from the ends meeting to the fitted width
    "rivets": (520, 680, EASE_FADE),
    "name": (460, 720, EASE_FADE),          # the name and the author line
    "foot": (100, 500, EASE_FADE),          # the progress bar, its phase and the objectives
}
INTRO_MS = max(end for _, end, _ in INTRO.values())

# The body: black, deeper at the edge it hangs from.
BODY_TOP = [0, 0, 0, 0.68]
BODY_FOOT = [0, 0, 0, 0.5]


def rgb(code: str, alpha: float = 1.0) -> list[float]:
    code = code.lstrip("#")
    return [round(int(code[i:i + 2], 16) / 255, 4) for i in (0, 2, 4)] + [alpha]


# The rail: the progress outline's four bands (section 12.5), from the body
# outward, each with its width.
RAIL = [(1.87, [0, 0, 0, 0.78]),
        (0.94, rgb("#AECCF4", 0.82)),
        (0.94, rgb("#5D6D82", 0.81)),
        (0.94, [0, 0, 0, 0.65])]
RAIL_W = sum(width for width, _ in RAIL)
# The progress outline's rivets, from the rail's inner edge: top, height,
# width and corner radius; three to a group.
RIVET_PITCH = 6.23
RIVET_OUTLINE = (-2.04, 6.7, 4.2, 1.8)
RIVET_STEEL = (-0.54, 3.6, 2.4, 1.1)
RIVET_OUTLINE_TINT = [0, 0, 0, 0.72]
RIVET_STEEL_TINT = rgb("#6F84A0", 0.8)
RIVET_GROUPS = 5
# The claw ends, traced from bottombar.tga in the outline's own units (as
# build_retained_screens.py draws the progress outline).
CLAW_OUTLINE = [(7.4, 3.8), (17.0, 3.8), (19.3, 7.6), (24.1, 7.6), (25.5, 9.8), (25.5, 13.6), (24.3, 16.4),
                (24.3, 17.4), (25.1, 19.6), (27.6, 21.6), (28.4, 21.7), (28.4, 28.1), (12.7, 28.1), (10.3, 26.2),
                (9.2, 24.3), (5.0, 21.5), (3.8, 20.6), (2.4, 18.3), (1.8, 16.5), (1.8, 11.7), (3.0, 8.9), (5.1, 6.0)]
CLAW_STEEL = [(4.8, 7.9), (6.3, 6.6), (8.0, 5.7), (9.5, 4.4), (14.8, 4.2), (17.0, 4.75), (17.8, 6.0), (18.7, 8.5),
              (19.9, 9.4), (23.5, 9.4), (24.3, 10.7), (24.3, 11.8), (23.1, 13.5), (23.1, 15.5), (22.5, 16.2),
              (23.1, 17.3), (23.1, 19.3), (25.2, 22.6), (26.4, 23.5), (27.7, 23.5), (28.4, 24.8), (28.4, 27.1),
              (12.7, 27.1), (11.5, 26.2), (10.4, 24.3), (8.6, 23.4), (5.9, 21.0), (4.2, 19.6), (3.0, 18.3),
              (2.4, 16.5), (2.4, 13.5), (3.0, 12.7), (3.0, 10.7), (3.8, 9.4), (4.7, 9.2)]
CLAW_HOLE = (13.05, 14.5, 4.15, 5.1)     # centre and radii
CLAW_FOOT = 28.1                         # the claw's foot, turned over onto the screen's top edge
CLAW_LEFT = 1.8                          # the claw's outermost point, on the box's edge
CLAW_JOIN = 28.4                         # where the claw meets its rail
CLAW_STEEL_TINT = rgb("#617186", 0.91)
CLAW_RIM_TINT = rgb("#97B2D7", 0.85)
CLAW_RIM_W = 0.6
CLAW_OUTLINE_TINT = [0, 0, 0, 0.72]

# Derived construction, in the leading end's own units (x from the box's edge).
_N = math.hypot(1.0, SLANT)
JOIN_X = CLAW_JOIN - CLAW_LEFT                       # the claw's join
SHOULDER_X = JOIN_X + LIP                            # where the shoulder leaves the top edge
SIDE_X0 = SHOULDER_X - SLANT * SHOULDER + SHOULDER * _N  # the side line at the body's edge: x = SIDE_X0 + SLANT * y
END = SIDE_X0 + SLANT * (FOOT - FILLET) + FILLET * _N    # the foot's straight run begins
FILLET_C = (END, FOOT - FILLET)
SHOULDER_C = (SHOULDER_X, SHOULDER)


def _arc(cx: float, cy: float, r: float, a0: float, a1: float, steps: int) -> list[tuple[float, float]]:
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / steps), cy + r * math.sin(a0 + (a1 - a0) * i / steps))
            for i in range(steps + 1)]


def edge(offset: float, steps: int = 16) -> list[tuple[float, float]]:
    """The leading half of the notch's edge grown outward by `offset` (0 the
    body's edge, RAIL_W the rail's outer edge), in end units: along the top
    edge from the claw's join, round the concave shoulder, down the side and
    round the foot's corner to the start of its straight run."""
    side_angle = math.atan2(SLANT, -1.0)             # the side's outward normal, (-1, SLANT) / n
    points = [(JOIN_X - 2.0, offset)]
    # Shoulder: centre below the top edge, outside the body; radius shrinks outward.
    points += _arc(*SHOULDER_C, SHOULDER - offset, -math.pi / 2, side_angle - math.pi, steps)
    # Foot corner: centre inside the body; radius grows outward.
    points += _arc(*FILLET_C, FILLET + offset, side_angle, math.pi / 2, steps)
    return points


def body_edge(steps: int = 16) -> list[tuple[float, float]]:
    """The body's outline in end units, from the top edge at the shoulder."""
    side_angle = math.atan2(SLANT, -1.0)
    points = _arc(*SHOULDER_C, SHOULDER, -math.pi / 2, side_angle - math.pi, steps)
    points += _arc(*FILLET_C, FILLET, side_angle, math.pi / 2, steps)
    return points


def lead(points):
    return [(0.0, x, y) for x, y in points]


def trail(points):
    return [(1.0, -x, y) for x, y in reversed(points)]


def claw_rings(mirror: bool, steps: int = 32) -> list[list[tuple[float, float, float]]]:
    def place(x: float, y: float) -> tuple[float, float, float]:
        px, py = x - CLAW_LEFT, CLAW_FOOT - y
        return (1.0, -px, py) if mirror else (0.0, px, py)
    cx, cy, rx, ry = CLAW_HOLE
    hole = [place(cx + rx * math.cos(2 * math.pi * i / steps), cy + ry * math.sin(2 * math.pi * i / steps)) for i in range(steps)]
    return [[place(*p) for p in CLAW_OUTLINE]], [[place(*p) for p in CLAW_STEEL], hole]


def rounded_rect(fx: float, x: float, y: float, w: float, h: float, r: float, steps: int = 6):
    points = []
    for cx, cy, a0 in ((x + w - r, y + r, -90), (x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180)):
        for step in range(steps + 1):
            angle = math.radians(a0 + 90 * step / steps)
            points.append((fx, cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return points


def rivet_centres() -> list[tuple[float, float]]:
    """Each group's centre as (fraction, offset): evenly spaced between the
    two end groups, RIVET_INSET in from the foot's straight run."""
    first, last = END + RIVET_INSET, -(END + RIVET_INSET)
    result = []
    for index in range(RIVET_GROUPS):
        t = index / (RIVET_GROUPS - 1)
        result.append((t, first * (1 - t) + last * t))
    return result


def rivet_group(fx: float, centre: float, prefix: str, steps: int = 6) -> list[dict]:
    shapes = []
    for offset in (-1, 0, 1):
        x = centre + offset * RIVET_PITCH
        ident = f"{prefix}-{offset + 1}"
        for part, (top, h, w, r), tint in (("outline", RIVET_OUTLINE, RIVET_OUTLINE_TINT), ("steel", RIVET_STEEL, RIVET_STEEL_TINT)):
            shapes.append({"id": f"{ident}-{part}", "rings": [rounded_rect(fx, x - w / 2, FOOT + top, w, h, r, steps)],
                           "fill": tint, "stroke": None})
    return shapes


def shapes(rivets: bool = True, steps: int = 16) -> list[dict]:
    """Every shape in drawing order. `rings` are closed contours of
    (fraction, offset, y) points filled even-odd; `fill` is a colour or
    ("linear", y0, y1, colour0, colour1); `stroke` is (colour, width) or None."""
    result = [{"id": "body", "rings": [[(0.0, SHOULDER_X - 2.0, 0.0)] + lead(body_edge(steps)) + trail(body_edge(steps))
                                       + [(1.0, -(SHOULDER_X - 2.0), 0.0)]],
               "fill": ("linear", 0.0, FOOT, BODY_TOP, BODY_FOOT), "stroke": None}]
    inner = 0.0
    for index, (width, tint) in enumerate(RAIL):
        outer = inner + width
        ring = (lead(edge(inner, steps)) + trail(edge(inner, steps))
                + list(reversed(lead(edge(outer, steps)) + trail(edge(outer, steps)))))
        result.append({"id": f"rail-{index}", "rings": [ring], "fill": tint, "stroke": None})
        inner = outer
    for side, mirror in (("lead", False), ("trail", True)):
        outline, steel = claw_rings(mirror, steps * 2)
        result.append({"id": f"claw-{side}-outline", "rings": outline, "fill": CLAW_OUTLINE_TINT, "stroke": None})
        result.append({"id": f"claw-{side}-steel", "rings": steel, "fill": CLAW_STEEL_TINT,
                       "stroke": (CLAW_RIM_TINT, CLAW_RIM_W)})
    if rivets:
        result += rivet_shapes(steps)
    return result


def rivet_shapes(steps: int = 16) -> list[dict]:
    """The five rivet groups alone."""
    result = []
    for index, (fx, centre) in enumerate(rivet_centres()):
        result += rivet_group(fx, centre, f"rivet-{index}", max(2, steps // 3))
    return result


def resolve(shape_list: list[dict], width: float) -> list[dict]:
    """The shapes with every point placed for a notch `width` u wide."""
    out = []
    for shape in shape_list:
        out.append({**shape, "rings": [[(fx * width + dx, y) for fx, dx, y in ring] for ring in shape["rings"]]})
    return out


# ----------------------------------------------------------------- textures

def rasterise(shape_list: list[dict], size: tuple[int, int], to_px, supersample: int = 4):
    """Straight-alpha RGBA of resolved shapes; `to_px` maps (x, y) in u to texels."""
    import numpy as np
    from PIL import Image, ImageDraw

    w, h = size[0] * supersample, size[1] * supersample
    colour = np.zeros((h, w, 3))
    alpha = np.zeros((h, w))
    rows = np.arange(h) + 0.5

    def ss(point):
        x, y = to_px(*point)
        return (x * supersample, y * supersample)

    def mask_of(rings) -> np.ndarray:
        result = np.zeros((h, w), dtype=bool)
        for ring in rings:
            layer = Image.new("1", (w, h), 0)
            ImageDraw.Draw(layer).polygon([ss(p) for p in ring], fill=1)
            result ^= np.asarray(layer, dtype=bool)
        return result

    def over(mask, paint) -> None:
        if isinstance(paint, tuple):
            _, y0, y1, c0, c1 = paint
            t0, t1 = ss((0, y0))[1], ss((0, y1))[1]
            t = np.clip((rows - t0) / (t1 - t0), 0, 1)[:, None]
            tint = np.array(c0)[None, :] * (1 - t) + np.array(c1)[None, :] * t
            src_rgb = np.broadcast_to(tint[:, None, :3], (h, w, 3))
            src_a = np.broadcast_to(tint[:, None, 3], (h, w)) * mask
        else:
            src_rgb = np.broadcast_to(np.array(paint[:3], dtype=float), (h, w, 3))
            src_a = mask * paint[3]
        keep = alpha * (1 - src_a)
        colour[:] = src_rgb * src_a[..., None] + colour * (1 - src_a)[..., None]
        alpha[:] = src_a + keep

    for shape in shape_list:
        over(mask_of(shape["rings"]), shape["fill"])
        if shape["stroke"] is not None:
            tint, stroke_w = shape["stroke"]
            layer = Image.new("1", (w, h), 0)
            draw = ImageDraw.Draw(layer)
            scale = ss((1, 0))[0] - ss((0, 0))[0]
            for ring in shape["rings"]:
                pts = [ss(p) for p in ring]
                draw.line(pts + [pts[0]], fill=1, width=max(1, round(stroke_w * scale)), joint="curve")
            over(np.asarray(layer, dtype=bool), tint)

    colour = colour.reshape(size[1], supersample, size[0], supersample, 3).mean(axis=(1, 3))
    alpha = alpha.reshape(size[1], supersample, size[0], supersample).mean(axis=(1, 3))
    straight = np.where(alpha[..., None] > 1e-6, colour / np.maximum(alpha, 1e-6)[..., None], 0)
    # Transparent texels take their neighbours' colour, so filtering never
    # darkens a pale edge.
    known = alpha > 1e-6
    for _ in range(8):
        total = np.zeros_like(straight)
        count = np.zeros(alpha.shape)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            shifted = np.roll(known, (dy, dx), axis=(0, 1))
            total += np.roll(straight, (dy, dx), axis=(0, 1)) * shifted[..., None]
            count += shifted
        grow = ~known & (count > 0)
        straight[grow] = total[grow] / count[grow][:, None]
        known = known | grow
    rgba = np.dstack([np.clip(straight, 0, 1), alpha])
    return Image.fromarray(np.round(rgba * 255).astype("uint8"))


TEXEL = 4                                # texels per u down the textures
END_TEXTURE = (256, 256)                 # END u by BOX_H u
MID_TEXTURE = (4, 256)                   # 1 u by BOX_H u
RIVET_BOX = (32.0, 16.0, FOOT - 8.0)     # the rivet group's texture: width and height in u, and its top
RIVET_TEXTURE = (128, 64)


def textures() -> dict[str, object]:
    """The stock screen's three textures, by file name."""
    reference = 2 * END + 2 * FOOT_MIN
    plain = resolve(shapes(rivets=False), reference)
    sx = END_TEXTURE[0] / END
    end = rasterise(plain, END_TEXTURE, lambda x, y: (x * sx, y * TEXEL))
    mid_x = END + FOOT_MIN / 2
    mid = rasterise(plain, MID_TEXTURE, lambda x, y: ((x - mid_x) * TEXEL + MID_TEXTURE[0] / 2, y * TEXEL))
    group = resolve(rivet_group(0.0, 0.0, "rivet"), 0.0)
    rw, rh, rtop = RIVET_BOX
    rivets = rasterise(group, RIVET_TEXTURE, lambda x, y: ((x + rw / 2) * TEXEL, (y - rtop) * TEXEL))
    return {"namenotch_end.tga": end, "namenotch_mid.tga": mid, "namenotch_rivets.tga": rivets}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="exit 1 if any texture is stale")
    args = parser.parse_args()
    from PIL import Image, ImageChops
    stale = 0
    for name, image in textures().items():
        path = TEXTURES / name
        if args.check:
            if not path.exists():
                print(f"missing: {path.relative_to(ROOT)}")
                stale += 1
                continue
            with Image.open(path) as current:
                current = current.convert("RGBA")
                if current.size != image.size or ImageChops.difference(current, image).getbbox():
                    print(f"stale: {path.relative_to(ROOT)}")
                    stale += 1
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
        print(f"wrote {path.relative_to(ROOT)}")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
