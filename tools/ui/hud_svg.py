#!/usr/bin/env python3
"""Convert the design atlas's SVG drawings into retained vector nodes.

The atlas (visual specification sections 14.15 and 14.16) authors every HUD
symbol as first-party SVG markup. Retained documents need native vector paths
in dp, so this module reads that markup: the complete path grammar (absolute
and relative commands, smooth curves, elliptical arcs), the basic shapes,
nested transforms, inherited presentation attributes, linear and radial
gradients, and masks and clip paths, which become node masks. No retail image
is read; the drawings come from tools/ui/hud_atlas_symbols.json.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
import xml.etree.ElementTree as ET

import build_retained_screens as ui

HERE = Path(__file__).resolve().parent
SYMBOLS = json.loads((HERE / "hud_atlas_symbols.json").read_text(encoding="utf-8"))

Matrix = tuple  # (a, b, c, d, e, f): x' = a x + c y + e, y' = b x + d y + f
IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def multiply(m: Matrix, n: Matrix) -> Matrix:
    """m applied after n."""
    a, b, c, d, e, f = m
    p, q, r, s, t, u = n
    return (a * p + c * q, b * p + d * q, a * r + c * s, b * r + d * s, a * t + c * u + e, b * t + d * u + f)


def apply(m: Matrix, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


def scale_of(m: Matrix) -> float:
    """The geometric mean scale, for stroke widths."""
    a, b, c, d, _, _ = m
    return math.sqrt(abs(a * d - b * c))


def parse_transform(text: str | None) -> Matrix:
    result = IDENTITY
    if not text:
        return result
    for kind, args in re.findall(r"([a-zA-Z]+)\s*\(([^)]*)\)", text):
        v = [float(x) for x in re.split(r"[\s,]+", args.strip()) if x]
        if kind == "translate":
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif kind == "scale":
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif kind == "rotate":
            r = math.radians(v[0])
            t = (math.cos(r), math.sin(r), -math.sin(r), math.cos(r), 0, 0)
            if len(v) == 3:
                t = multiply(multiply((1, 0, 0, 1, v[1], v[2]), t), (1, 0, 0, 1, -v[1], -v[2]))
        elif kind == "matrix":
            t = tuple(v[:6])
        elif kind == "skewX":
            t = (1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif kind == "skewY":
            t = (1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        else:
            raise ValueError(f"unsupported transform {kind}")
        result = multiply(result, t)
    return result


# ------------------------------------------------------------------ path data

TOKEN = re.compile(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def _arc_to_cubics(x0, y0, rx, ry, rotation, large, sweep, x1, y1):
    """SVG elliptical arc as cubic segments of at most 90 degrees."""
    if rx == 0 or ry == 0:
        return [("L", (x1, y1))]
    rx, ry = abs(rx), abs(ry)
    phi = math.radians(rotation)
    c, s = math.cos(phi), math.sin(phi)
    dx, dy = (x0 - x1) / 2, (y0 - y1) / 2
    xp, yp = c * dx + s * dy, -s * dx + c * dy
    lam = xp * xp / (rx * rx) + yp * yp / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * yp * yp - ry * ry * xp * xp
    den = rx * rx * yp * yp + ry * ry * xp * xp
    f = math.sqrt(max(0.0, num / den)) if den else 0.0
    if bool(large) == bool(sweep):
        f = -f
    cxp, cyp = f * rx * yp / ry, -f * ry * xp / rx
    cx, cy = c * cxp - s * cyp + (x0 + x1) / 2, s * cxp + c * cyp + (y0 + y1) / 2

    def angle(ux, uy, vx, vy):
        return math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
    start = angle(1, 0, (xp - cxp) / rx, (yp - cyp) / ry)
    delta = angle((xp - cxp) / rx, (yp - cyp) / ry, (-xp - cxp) / rx, (-yp - cyp) / ry)
    if not sweep and delta > 0:
        delta -= math.tau
    elif sweep and delta < 0:
        delta += math.tau
    steps = max(1, math.ceil(abs(delta) / (math.pi / 2) - 1e-9))

    def point(t):
        return (cx + c * rx * math.cos(t) - s * ry * math.sin(t), cy + s * rx * math.cos(t) + c * ry * math.sin(t))

    def tangent(t):
        return (-c * rx * math.sin(t) - s * ry * math.cos(t), -s * rx * math.sin(t) + c * ry * math.cos(t))
    out = []
    for k in range(steps):
        a = start + delta * k / steps
        b = start + delta * (k + 1) / steps
        k4 = 4 / 3 * math.tan((b - a) / 4)
        p0, p1 = point(a), point(b)
        t0, t1 = tangent(a), tangent(b)
        out.append(("C", (p0[0] + k4 * t0[0], p0[1] + k4 * t0[1]), (p1[0] - k4 * t1[0], p1[1] - k4 * t1[1]), p1))
    if out:
        last = out[-1]
        out[-1] = (last[0], last[1], last[2], (x1, y1))  # land exactly on the endpoint
    return out


def parse_path(data: str) -> list:
    """Absolute segments: ('M',p) ('L',p) ('C',c1,c2,p) ('Q',c,p) ('Z',)."""
    tokens = TOKEN.findall(data)
    out = []
    i = 0
    cmd = ""
    x = y = sx = sy = 0.0
    last_control = None   # for S/T reflection
    last_kind = ""

    def num():
        nonlocal i
        value = float(tokens[i])
        i += 1
        return value
    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                out.append(("Z",))
                x, y = sx, sy
                last_kind = "Z"
                last_control = None
                continue
        elif not cmd:
            raise ValueError("path data does not start with a command")
        rel = cmd.islower()
        kind = cmd.upper()
        if kind == "M":
            px, py = num(), num()
            if rel:
                px, py = px + x, py + y
            out.append(("M", (px, py)))
            x, y = sx, sy = px, py
            cmd = "l" if rel else "L"   # following pairs are line-tos
            last_control = None
        elif kind == "L":
            px, py = num(), num()
            if rel:
                px, py = px + x, py + y
            out.append(("L", (px, py)))
            x, y = px, py
            last_control = None
        elif kind == "H":
            px = num()
            x = px + x if rel else px
            out.append(("L", (x, y)))
            last_control = None
        elif kind == "V":
            py = num()
            y = py + y if rel else py
            out.append(("L", (x, y)))
            last_control = None
        elif kind in ("C", "S"):
            if kind == "C":
                c1 = (num(), num())
                if rel:
                    c1 = (c1[0] + x, c1[1] + y)
            else:
                c1 = (2 * x - last_control[0], 2 * y - last_control[1]) if last_kind in ("C", "S") and last_control else (x, y)
            c2 = (num(), num())
            p = (num(), num())
            if rel:
                c2 = (c2[0] + x, c2[1] + y)
                p = (p[0] + x, p[1] + y)
            out.append(("C", c1, c2, p))
            last_control = c2
            x, y = p
        elif kind in ("Q", "T"):
            if kind == "Q":
                c = (num(), num())
                if rel:
                    c = (c[0] + x, c[1] + y)
            else:
                c = (2 * x - last_control[0], 2 * y - last_control[1]) if last_kind in ("Q", "T") and last_control else (x, y)
            p = (num(), num())
            if rel:
                p = (p[0] + x, p[1] + y)
            out.append(("Q", c, p))
            last_control = c
            x, y = p
        elif kind == "A":
            rx, ry, rot, large, sweep = num(), num(), num(), num(), num()
            px, py = num(), num()
            if rel:
                px, py = px + x, py + y
            out.extend(_arc_to_cubics(x, y, rx, ry, rot, large, sweep, px, py))
            x, y = px, py
            last_control = None
        else:
            raise ValueError(f"unsupported path command {cmd}")
        last_kind = kind
    return out


def shape_path(el: ET.Element) -> str | None:
    tag = el.tag.split("}")[-1]
    a = el.attrib

    def n(key, default=0.0):
        value = a.get(key)
        return float(value) if value not in (None, "") else default
    if tag == "path":
        return a.get("d")
    if tag == "line":
        return f"M{n('x1')} {n('y1')}L{n('x2')} {n('y2')}"
    if tag in ("polygon", "polyline"):
        values = [float(v) for v in re.split(r"[\s,]+", a.get("points", "").strip()) if v]
        if len(values) < 4:
            return None
        pts = list(zip(values[::2], values[1::2]))
        return "M" + "L".join(f"{px} {py}" for px, py in pts) + ("Z" if tag == "polygon" else "")
    if tag in ("circle", "ellipse"):
        cx, cy = n("cx"), n("cy")
        rx, ry = (n("r"), n("r")) if tag == "circle" else (n("rx"), n("ry"))
        if rx <= 0 or ry <= 0:
            return None
        return f"M{cx + rx} {cy}A{rx} {ry} 0 1 1 {cx - rx} {cy}A{rx} {ry} 0 1 1 {cx + rx} {cy}Z"
    if tag == "rect":
        x, y, w, h = n("x"), n("y"), n("width"), n("height")
        if w <= 0 or h <= 0:
            return None
        rx = a.get("rx")
        ry = a.get("ry")
        rx = float(rx) if rx else (float(ry) if ry else 0.0)
        ry = float(ry) if ry else rx
        rx, ry = min(rx, w / 2), min(ry, h / 2)
        if rx <= 0 or ry <= 0:
            return f"M{x} {y}H{x + w}V{y + h}H{x}Z"
        return (f"M{x + rx} {y}H{x + w - rx}A{rx} {ry} 0 0 1 {x + w} {y + ry}V{y + h - ry}"
                f"A{rx} {ry} 0 0 1 {x + w - rx} {y + h}H{x + rx}A{rx} {ry} 0 0 1 {x} {y + h - ry}"
                f"V{y + ry}A{rx} {ry} 0 0 1 {x + rx} {y}Z")
    return None


def commands(data: str, m: Matrix, prefix: str = "c") -> list:
    """Document path commands in dp under transform m."""
    result = []

    def pt(p):
        px, py = apply(m, *p)
        return [round(px, 4), round(py, 4)]
    for seg in parse_path(data):
        ident = f"{prefix}{len(result)}"
        if seg[0] == "M":
            result.append({"id": ident, "op": "move", "points": [pt(seg[1])]})
        elif seg[0] == "L":
            result.append({"id": ident, "op": "line", "points": [pt(seg[1])]})
        elif seg[0] == "C":
            result.append({"id": ident, "op": "cubic", "points": [pt(seg[1]), pt(seg[2]), pt(seg[3])]})
        elif seg[0] == "Q":
            result.append({"id": ident, "op": "quadratic", "points": [pt(seg[1]), pt(seg[2])]})
        else:
            result.append({"id": ident, "op": "close"})
    return result


# ---------------------------------------------------------------- paint/color

NAMED = {"white": "#FFFFFF", "black": "#000000", "red": "#FF0000", "none": None}


def parse_colour(value: str | None, tint: list | None, alpha: float) -> list | None:
    """An SVG colour as a premultiplication-free RGBA list. White and
    currentColor take the tint for tintable art."""
    if value is None or value == "none":
        return None
    value = value.strip()
    if value == "currentColor":
        base = tint or [1, 1, 1, 1]
        return [base[0], base[1], base[2], base[3] * alpha]
    value = NAMED.get(value.lower(), value)
    if value is None:
        return None
    if value.startswith("rgb"):
        parts = [float(v) for v in re.findall(r"[\d.]+", value)]
        rgbv = [parts[0] / 255, parts[1] / 255, parts[2] / 255]
        a = parts[3] if len(parts) > 3 else 1
        return [*rgbv, a * alpha]
    if not value.startswith("#"):
        raise ValueError(f"unsupported colour {value}")
    h = value[1:]
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    rgbv = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    if tint is not None and h.upper() == "FFFFFF":
        return [tint[0], tint[1], tint[2], tint[3] * alpha]
    return [*rgbv, alpha]


class Drawing:
    """One atlas drawing converted at a placement: x, y, height (dp) and an
    optional uniform scale origin. Produces vector nodes."""

    def __init__(self, name: str, family: str = "icons"):
        entry = SYMBOLS[family].get(name)
        if entry is None:
            raise KeyError(f"atlas has no {family[:-1]} '{name}'")
        self.name = name
        self.entry = entry
        # Crosshairs are authored on the 64x64 master centred on the aim point.
        self.vb = [float(v) for v in entry.get("vb", "0 0 64 64").split()]
        self.multi = bool(entry.get("multi"))
        self.add = bool(entry.get("add"))
        self.glow = entry.get("glow")
        self.root = ET.fromstring('<svg xmlns="http://www.w3.org/2000/svg">' + entry["svg"] + "</svg>")
        self.defs = {}
        for el in self.root.iter():
            ident = el.get("id")
            if ident:
                self.defs[ident] = el

    @property
    def aspect(self) -> float:
        return self.vb[2] / self.vb[3]

    def placement(self, x: float, y: float, h: float) -> Matrix:
        s = h / self.vb[3]
        return (s, 0, 0, s, x - self.vb[0] * s, y - self.vb[1] * s)

    # -- paints
    def paint(self, value, alpha, tint, m: Matrix):
        if value is None or value == "none":
            return None
        if value.startswith("url("):
            ref = value[value.index("#") + 1:value.index(")")]
            g = self.defs[ref]
            stops = []
            for stop in g:
                if stop.tag.split("}")[-1] != "stop":
                    continue
                off = stop.get("offset", "0")
                off = float(off[:-1]) / 100 if off.endswith("%") else float(off)
                style = dict(item.split(":", 1) for item in stop.get("style", "").split(";") if ":" in item)
                colour = stop.get("stop-color", style.get("stop-color", "#FFFFFF"))
                opacity = float(stop.get("stop-opacity", style.get("stop-opacity", "1")))
                rgba = parse_colour(colour, tint if not self.multi else None, alpha * opacity)
                stops.append([min(1.0, max(0.0, off)), rgba])
            # strictly increasing stops, including 0 and 1
            stops.sort(key=lambda s: s[0])
            cleaned = []
            for at, rgba in stops:
                if cleaned and at <= cleaned[-1][0]:
                    at = min(1.0, cleaned[-1][0] + 1e-4)
                    if at <= cleaned[-1][0]:
                        continue
                cleaned.append([at, rgba])
            if cleaned[0][0] > 0:
                cleaned.insert(0, [0.0, cleaned[0][1]])
            if cleaned[-1][0] < 1:
                cleaned.append([1.0, cleaned[-1][1]])
            gm = multiply(m, parse_transform(g.get("gradientTransform")))
            tag = g.tag.split("}")[-1]
            if tag == "linearGradient":
                x1 = float(g.get("x1", "0").rstrip("%")) / (100 if g.get("x1", "").endswith("%") else 1)
                y1 = float(g.get("y1", "0").rstrip("%")) / (100 if g.get("y1", "").endswith("%") else 1)
                x2 = float(g.get("x2", "1").rstrip("%")) / (100 if g.get("x2", "").endswith("%") else 1)
                y2 = float(g.get("y2", "0").rstrip("%")) / (100 if g.get("y2", "").endswith("%") else 1)
                if g.get("gradientUnits") != "userSpaceOnUse":
                    raise ValueError(f"{self.name}: objectBoundingBox gradients are not supported")
                p1, p2 = apply(gm, x1, y1), apply(gm, x2, y2)
                return {"type": "linear", "from": [round(p1[0], 4), round(p1[1], 4)], "to": [round(p2[0], 4), round(p2[1], 4)],
                        "stops": [{"at": round(at, 5), "color": ui.colour([round(c, 5) for c in rgba])} for at, rgba in cleaned]}
            cx, cy, r = (float(g.get(k, "0.5")) for k in ("cx", "cy", "r"))
            if g.get("gradientUnits") != "userSpaceOnUse":
                raise ValueError(f"{self.name}: objectBoundingBox gradients are not supported")
            c0 = apply(gm, cx, cy)
            rr = r * scale_of(gm)
            return {"type": "radial", "from": [round(c0[0], 4), round(c0[1], 4)], "to": [round(c0[0] + rr, 4), round(c0[1], 4)],
                    "stops": [{"at": round(at, 5), "color": ui.colour([round(c, 5) for c in rgba])} for at, rgba in cleaned]}
        rgba = parse_colour(value, None if self.multi else tint, alpha)
        if rgba is None:
            return None
        return ui.solid([round(c, 5) for c in rgba])

    # -- conversion
    def nodes(self, ident: str, x: float, y: float, h: float, *, tint=None, opacity: float = 1.0,
              blend: str | None = None, props: dict | None = None) -> list:
        """Vector nodes drawing the symbol with its viewBox top-left at (x, y)
        and height h (dp). Tintable art takes `tint` where it is white or
        currentColor; multi-colour art keeps its colours."""
        m = self.placement(x, y, h)
        blend = blend or ("additive" if self.add else None)
        groups = []          # (mask paths or None, paths)
        current = {"mask": None, "paths": []}
        groups.append(current)

        def visit(el, inherited, transform, alpha, mask_paths):
            nonlocal current
            tag = el.tag.split("}")[-1]
            if tag in ("defs", "mask", "clipPath", "linearGradient", "radialGradient", "style", "title"):
                return
            style = dict(inherited)
            for key, value in el.attrib.items():
                if key in ("style",):
                    for item in value.split(";"):
                        if ":" in item:
                            k2, v2 = item.split(":", 1)
                            style[k2.strip()] = v2.strip()
                elif key not in ("id", "class", "transform", "d", "points", "x", "y", "width", "height", "cx", "cy", "r",
                                 "rx", "ry", "x1", "y1", "x2", "y2", "opacity", "mask", "clip-path"):
                    style[key] = value
            alpha = alpha * float(el.get("opacity", "1"))
            transform = multiply(transform, parse_transform(el.get("transform")))
            mask_ref = el.get("mask") or el.get("clip-path")
            if mask_ref:
                ref = mask_ref[mask_ref.index("#") + 1:mask_ref.index(")")]
                mask_paths = self.mask_paths(self.defs[ref], transform)
                # A masked subtree is its own node; following siblings resume
                # the unmasked node.
                current = {"mask": mask_paths, "paths": []}
                groups.append(current)
                own = dict(el.attrib)
                own.pop("mask", None)
                own.pop("clip-path", None)
                own.pop("transform", None)
                own.pop("opacity", None)
                if shape_path(el):
                    # The masked element is itself a shape: draw it inside.
                    clone = ET.Element(el.tag, own)
                    visit(clone, style, transform, alpha, mask_paths)
                for child in el:
                    visit(child, style, transform, alpha, mask_paths)
                current = {"mask": None, "paths": []}
                groups.append(current)
                return
            data = shape_path(el)
            if data:
                index = len(current["paths"])
                path = {"id": f"p{index}", "commands": commands(data, transform),
                        "fillRule": style.get("fill-rule", "nonzero")}
                fill_value = style.get("fill", "#000000" if self.multi else "#FFFFFF")
                fill = self.paint(fill_value, alpha * float(style.get("fill-opacity", "1")), tint, transform)
                path["fill"] = fill if fill else {"type": "none"}
                stroke_value = style.get("stroke")
                if stroke_value and stroke_value != "none":
                    stroke_paint = self.paint(stroke_value, alpha * float(style.get("stroke-opacity", "1")), tint, transform)
                    width = float(style.get("stroke-width", "1")) * scale_of(transform)
                    if stroke_paint:
                        path["stroke"] = {"paint": stroke_paint, "widthDp": round(width, 4), "minimumPixels": 0,
                                          "join": style.get("stroke-linejoin", "miter"),
                                          "cap": style.get("stroke-linecap", "butt")}
                        if "stroke-miterlimit" in style:
                            path["stroke"]["miterLimit"] = max(1.0, float(style["stroke-miterlimit"]))
                if blend:
                    path["blend"] = blend
                if path["fill"].get("type") != "none" or "stroke" in path:
                    current["paths"].append(path)
            for child in el:
                visit(child, style, transform, alpha, mask_paths)

        for child in self.root:
            visit(child, {}, m, 1.0, None)
        nodes = []
        box = {**ui.FULL, "display": ui.keyword("block")}
        if props:
            box.update(props)
        if opacity != 1:
            box["opacity"] = ui.number(round(opacity, 4))
        for index, group in enumerate(g for g in groups if g["paths"]):
            node = ui.vector(f"{ident}-{index}" if index else ident, dict(box), group["paths"])
            if group["mask"] is not None:
                node["mask"] = {"paths": group["mask"]}
            nodes.append(node)
        return nodes

    def mask_paths(self, el: ET.Element, transform: Matrix) -> list:
        """A luminance mask (white field, black cut-outs) or a clip path as
        coverage paths: one even-odd path whose black shapes become holes."""
        tag = el.tag.split("}")[-1]
        keep, cut = [], []

        def collect(node, m):
            for child in node:
                m2 = multiply(m, parse_transform(child.get("transform")))
                data = shape_path(child)
                if data:
                    fill = child.get("fill", "#FFFFFF" if tag == "mask" else "#000000")
                    rgba = parse_colour(fill, None, 1) if fill != "none" else None
                    lum = 0 if rgba is None else 0.2126 * rgba[0] + 0.7152 * rgba[1] + 0.0722 * rgba[2]
                    if tag == "clipPath" or lum > 0.5:
                        keep.append(commands(data, m2))
                    else:
                        cut.append(commands(data, m2))
                collect(child, m2)
        collect(el, transform)
        if not keep:
            return []
        merged = []
        for part in keep + cut:
            for cmd in part:
                merged.append({**cmd, "id": f"m{len(merged)}"})
        return [{"id": "mask", "commands": merged, "fillRule": "evenodd" if cut else "nonzero", "fill": ui.solid([1, 1, 1, 1])}]


def icon_nodes(name: str, ident: str, x: float, y: float, h: float, *, tint=None, opacity: float = 1.0,
               anchor: str = "start", family: str = "icons", blend: str | None = None, props: dict | None = None,
               glow: bool = False) -> list:
    """Nodes for an atlas symbol at (x, y) with height h, all in dp. `anchor`
    places x at the drawing's start, middle or end, like the atlas's A.icon."""
    drawing = Drawing(name, family)
    w = h * drawing.aspect
    ox = -w / 2 if anchor == "middle" else -w if anchor == "end" else 0
    nodes = []
    if glow and drawing.glow:
        nodes.extend(glow_nodes(drawing, ident + "-glow", x + ox, y, h, opacity))
    nodes.extend(drawing.nodes(ident, x + ox, y, h, tint=tint, opacity=opacity, blend=blend, props=props))
    return nodes


def glow_nodes(drawing: Drawing, ident: str, x: float, y: float, h: float, opacity: float) -> list:
    """The emblem's separate soft layer (section 14.16): its silhouette
    blurred with sigma 1.3 u, nothing within 0.6 u, added in its colour. A
    blur is not a vector primitive, so three additive outline rings of rising
    width approximate the falloff beyond the 0.6 u gap."""
    colour = drawing.glow["color"]
    gain = float(drawing.glow.get("gain", 1.8))
    sigma = float(drawing.glow.get("sigma", 1.3)) * h / 24
    base = ui.rgb(colour)
    rings = []
    plain = drawing.nodes(ident + "-src", x, y, h, tint=[1, 1, 1, 1])
    outline = [p for node in plain for p in node["paths"]]
    peak = min(1.0, gain * 0.35) * 0.25
    for index, (width, alpha) in enumerate(((1.2 + 2 * 0.6, 0.55), (1.2 + 4 * sigma, 0.3), (1.2 + 7 * sigma, 0.15))):
        for p in outline:
            ring = {"id": f"r{index}-{p['id']}-{len(rings)}", "commands": p["commands"], "fillRule": p.get("fillRule", "nonzero"),
                    "fill": {"type": "none"},
                    "stroke": {"paint": ui.solid([*base[:3], round(peak * alpha, 4)]), "widthDp": round(width * h / 24, 4),
                               "minimumPixels": 0, "join": "round", "cap": "round"},
                    "blend": "additive"}
            rings.append(ring)
    if not rings:
        return []
    props = {**ui.FULL, "display": ui.keyword("block")}
    if opacity != 1:
        props["opacity"] = ui.number(round(opacity, 4))
    return [ui.vector(ident, props, rings)]


def symbol_width(name: str, h: float, family: str = "icons") -> float:
    return h * Drawing(name, family).aspect
