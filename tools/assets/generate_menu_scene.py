#!/usr/bin/env python3
# Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
"""The main menu's 3D backdrop: the Sphere and Earth of section 12.2 of
docs/dev/prey-ui-visual-design.md, as meshes, textures and a material file.

The scene is the Interface Atlas's (docs/dev/prey-ui/atlas/
prey-interface-atlas.html) made solid. Its numbers, its seeded random
generator and its measured plate table are read or ported from the atlas, so
the menu and the sheet that specifies it draw the same Sphere: the rest frame
lays over the stock painting, every painted plate is cast from the rest
camera onto the Sphere at its painted place, and the far side is filled with
clusters in the same manner. Nothing comes from the retail archives; the
plate table is a set of measurements, not art. The sun flare reuses the stock
`sol` stages at run time.

Outputs (edit this script, never them; --check reports any that is stale):

| File | Holds |
| --- | --- |
| pak1 models/menu/scene/backdrop.ase | The static bodies: the Sphere's shell, Earth, its cloud deck and its glow |
| pak1 models/menu/scene/surface.ase | The Sphere's plates, green patches and craters, which turn |
| pak1 models/menu/scene/sun.ase | The sun flare's quad, a billboard the renderDef keeps on the shell |
| pak1 guis/assets/menu/scene/*.tga | The shell's light, the plates' ice, Earth's colour, clouds and glow |
| pak0 materials/menu_scene.mtr | Their materials: all unlit |
| pak0 guis/mainmenu/mainmenu_scene.guifragment | The renderDef with the camera's curve |

Frames: the atlas's (x toward the trailing edge, y up, z into the screen, one
unit the Sphere's radius R) become the engine's (x forward, y left, z up) at
SCALE units to R.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ATLAS = ROOT / "docs/dev/prey-ui/atlas/prey-interface-atlas.html"
PAK0 = ROOT / "content/basepr/pak0"
PAK1 = ROOT / "content/basepr/pak1"
MODEL_DIR = "models/menu/scene"
TEXTURE_DIR = "guis/assets/menu/scene"

SCALE = 64.0                     # engine units to the Sphere's radius
FOCAL = 240.0 / math.tan(math.radians(15.0))   # 30 degree vertical field: 895.7 u

# The atlas's scene (SCN), section 12.2's "Scene" table.
CAM_REST = (-0.1949, -0.0948, -4.9206)
START_DIR = (-0.6403, -0.0872, -0.7631)
START_RADIUS = 900.0
START_OFFSET = (-80.0, 60.0)
EARTH_AT = (0.755, -4.776, -3.442)
EARTH_R = 4.4143
LIGHT = (0.09, -0.85, -0.52)
TILT = math.radians(20.0)
TURN_SECONDS = 240.0
ENTRANCE_MS = 1200
ACCEL, DECEL = 0.15, 0.85
SUN_SIZE = 0.17                  # the flare's radius against the Sphere's
CLOUD_DRIFT = 1.5                # u a second along the limb


# ---------------------------------------------------------------- vectors

def norm(v):
    v = np.asarray(v, dtype=np.float64)
    length = np.linalg.norm(v)
    return v / length if length else v


def to_engine(v, scale=SCALE):
    """Atlas frame to the engine's: forward = z, left = -x, up = y."""
    v = np.asarray(v, dtype=np.float64)
    return np.array([v[2], -v[0], v[1]]) * scale


def look_along(forward):
    """Rows right, up, forward with the atlas's y up (its lookAlong)."""
    fw = norm(forward)
    right = norm(np.cross([0.0, 1.0, 0.0], fw))
    up = np.cross(fw, right)
    return right, up, fw


def turn_matrix(spin):
    """Body to world: turn about the body's own axis, then tilt it (row-major)."""
    cs, sn, ct, st = math.cos(spin), math.sin(spin), math.cos(TILT), math.sin(TILT)
    return np.array([[ct * cs, -st, ct * sn], [st * cs, ct, st * sn], [-sn, 0.0, cs]])


# ---------------------------------------------------------------- the atlas

def rnd(seed):
    """The atlas's rnd(): mulberry32."""
    state = seed & 0xFFFFFFFF

    def imul(a, b):
        return (a * b) & 0xFFFFFFFF

    def draw():
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        t = state
        t = imul(t ^ (t >> 15), t | 1)
        t = (t ^ ((t + imul(t ^ (t >> 7), t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return draw


def atlas_table(name):
    text = ATLAS.read_text(encoding="utf-8")
    match = re.search(r"const %s = (\[\[.*?\]\]);" % name, text)
    if not match:
        raise SystemExit(f"{ATLAS}: no {name} table")
    return json.loads(match.group(1))


class Scene:
    def __init__(self):
        self.cam_rest = np.array(CAM_REST)
        self.d1 = float(np.linalg.norm(self.cam_rest))
        self.n1 = self.cam_rest / self.d1
        self.r1 = FOCAL / math.sqrt(self.d1 * self.d1 - 1.0)
        self.d0 = math.sqrt(1.0 + (FOCAL / START_RADIUS) ** 2)
        self.start_dir = np.array(START_DIR)
        self.aim1 = self.cam_rest + np.array([0.0, 0.0, self.d1])
        right, up, _ = look_along(-self.start_dir)
        kx = START_OFFSET[0] / FOCAL * self.d0
        ky = START_OFFSET[1] / FOCAL * self.d0
        self.aim0 = kx * right + ky * up
        self.light = norm(LIGHT)
        self.earth = np.array(EARTH_AT)

    def project(self, point, camera=None):
        """A point to the 4:3 canvas from the rest camera (looking along +z)."""
        c = self.cam_rest if camera is None else camera
        p = np.asarray(point) - c
        if p[2] <= 1e-9:
            return float("nan"), float("nan")
        return 320.0 + FOCAL * p[0] / p[2], 240.0 - FOCAL * p[1] / p[2]


def sphere_model(scene):
    """The atlas's SPHERE_MODEL: each part is (kind, centre, ring, tone) in the
    body frame; kind 0 a plate, 1 a green patch, 2 a crater."""
    R = rnd(1906)
    out = []

    def frame(n):
        t1 = norm(np.cross([0.0, 1.0, 0.0] if abs(n[1]) < 0.9 else [1.0, 0.0, 0.0], n))
        return t1, np.cross(n, t1)

    def lift(n, t, a, b):
        return norm(n + a * t[0] + b * t[1])

    def patch(kind, n, t, cx, cy, rad, long_, rot, k):
        pts = []
        cr, sr = math.cos(rot), math.sin(rot)
        for i in range(k):
            a = i / k * math.pi * 2
            rr = rad * (0.52 + R() * 0.62)
            x = math.cos(a) * rr * long_
            y = math.sin(a) * rr / long_
            pts.append(lift(n, t, cx + x * cr - y * sr, cy + x * sr + y * cr))
        out.append((kind, lift(n, t, cx, cy), pts, R()))

    def anywhere():
        a = R() * 2 - 1
        b = R() * 2 - 1
        c = R() * 2 - 1
        return norm([a, b, c])

    for _ in range(90):
        n = anywhere()
        rad = 0.014 + R() * 0.034
        long_ = 1 + R() * 0.3
        rot = R() * 3.14
        patch(2, n, frame(n), 0, 0, rad, long_, rot, 8)

    C = scene.cam_rest
    m = turn_matrix(0.0)
    sc = (320 + FOCAL * C[0] / C[2], 240 - FOCAL * C[1] / C[2])
    lim = FOCAL / math.sqrt(C @ C - 1) - 1.5

    def cast(x, y):
        dx, dy = x - sc[0], y - sc[1]
        q = math.hypot(dx, dy)
        if q > lim:
            x, y = sc[0] + dx * lim / q, sc[1] + dy * lim / q
        d = norm([(x - 320) / FOCAL, (240 - y) / FOCAL, 1.0])
        b = C @ d
        t = -b - math.sqrt(max(0.0, b * b - C @ C + 1))
        w = norm(C + d * t)
        return m.T @ w

    def painted(kind, entry):
        x, y, a, b, deg = entry
        rot = math.radians(deg)
        cr, sr = math.cos(rot), math.sin(rot)
        k = 11 if a > 10 else 9 if a > 5 else 7
        pts = []
        for i in range(k):
            t = (i + (R() - 0.5) * 0.5) / k * math.pi * 2
            j = 0.8 + R() * 0.42
            ex = math.cos(t) * a * j
            ey = math.sin(t) * max(b, 0.9) * j
            pts.append(cast(x + ex * cr - ey * sr, y + ex * sr + ey * cr))
        out.append((kind, cast(x, y), pts, R()))

    for entry in atlas_table("STOCK_PLATES"):
        painted(0, entry)
    for entry in atlas_table("STOCK_GREEN"):
        painted(1, entry)

    to_cam = norm(C)
    count = 34
    for i in range(count):
        y = 1 - (i + 0.5) * 2 / count
        q = math.sqrt(1 - y * y)
        th = i * 2.39996 + (R() - 0.5) * 0.6
        a_ = math.cos(th) * q + (R() - 0.5) * 0.14
        b_ = y + (R() - 0.5) * 0.14
        c_ = math.sin(th) * q + (R() - 0.5) * 0.14
        n = norm([a_, b_, c_])
        t = frame(n)
        ring = 4 + math.floor(R() * 4)
        spread = 0.11 + R() * 0.04
        a0 = R() * 6.283
        far = (m @ n) @ to_cam < -0.05
        if not far:
            for _ in range(12 + ring * 9):
                R()
            continue
        rad = 0.045 + R() * 0.03
        long_ = 1.4 + R() * 0.8
        rot = R() * 3.14
        patch(0, n, t, 0, 0, rad, long_, rot, 9)
        for j in range(ring):
            a = a0 + j / ring * 6.283 + (R() - 0.5) * 0.3
            d = spread * (0.95 + R() * 0.25)
            rad = 0.028 + R() * 0.028
            long_ = 1.5 + R() * 0.9
            rot = a + 1.571 + (R() - 0.5) * 0.5
            patch(0, n, t, math.cos(a) * d, math.sin(a) * d, rad, long_, rot, 8)
        if i % 6 == 0:
            a = R() * 6.283
            rad = 0.03 + R() * 0.02
            rot = R() * 3.14
            patch(1, n, t, math.cos(a) * spread * 2, math.sin(a) * spread * 2, rad, 1.6, rot, 7)
    return out


# ---------------------------------------------------------------- colour

def hex_rgb(code):
    code = code.lstrip("#")
    return np.array([int(code[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float64)


def ramp(stops, t):
    """Linear interpolation through (offset, '#rrggbb' or (r, g, b), alpha) stops."""
    t = float(np.clip(t, stops[0][0], stops[-1][0]))
    for (o0, c0, a0), (o1, c1, a1) in zip(stops, stops[1:]):
        if t <= o1:
            p = 0.0 if o1 == o0 else (t - o0) / (o1 - o0)
            c0 = hex_rgb(c0) if isinstance(c0, str) else np.asarray(c0, float)
            c1 = hex_rgb(c1) if isinstance(c1, str) else np.asarray(c1, float)
            return c0 + (c1 - c0) * p, a0 + (a1 - a0) * p
    last = stops[-1]
    return (hex_rgb(last[1]) if isinstance(last[1], str) else np.asarray(last[1], float)), last[2]


PLATE_RAMP = [(18, 30, 54), (44, 67, 102), (94, 116, 158), (175, 197, 227)]


def plate_rgb(b):
    x = max(0.0, min(0.9999, b)) * 3
    i = int(math.floor(x))
    p = x - i
    a, c = np.array(PLATE_RAMP[i], float), np.array(PLATE_RAMP[i + 1], float)
    return a + (c - a) * p


# ---------------------------------------------------------------- meshes

class Mesh:
    def __init__(self, name, material):
        self.name, self.material = name, material
        self.verts, self.uvs, self.faces, self.colours = [], [], [], []

    def vertex(self, position, uv, colour=None):
        self.verts.append(np.asarray(position, float))
        self.uvs.append((float(uv[0]), float(uv[1])))
        if colour is not None:
            self.colours.append(tuple(float(c) for c in colour))
        return len(self.verts) - 1

    def face(self, a, b, c, outward):
        """A triangle wound counter-clockwise seen from `outward`, as ASE wants."""
        va, vb, vc = self.verts[a], self.verts[b], self.verts[c]
        if np.cross(vb - va, vc - va) @ np.asarray(outward) < 0:
            b, c = c, b
        self.faces.append((a, b, c))


def write_ase(path, meshes):
    materials = []
    for mesh in meshes:
        if mesh.material not in materials:
            materials.append(mesh.material)
    out = io.StringIO()
    out.write("*3DSMAX_ASCIIEXPORT\t200\n")
    out.write("*COMMENT \"Generated by tools/assets/generate_menu_scene.py; do not edit.\"\n")
    out.write("*MATERIAL_LIST {\n\t*MATERIAL_COUNT %d\n" % len(materials))
    for i, material in enumerate(materials):
        out.write("\t*MATERIAL %d {\n\t\t*MATERIAL_NAME \"%s\"\n\t\t*MAP_DIFFUSE {\n"
                  "\t\t\t*BITMAP \"//base/%s\"\n\t\t}\n\t}\n" % (i, material.rsplit("/", 1)[-1], material))
    out.write("}\n")
    for mesh in meshes:
        out.write("*GEOMOBJECT {\n\t*NODE_NAME \"%s\"\n\t*MESH {\n\t\t*TIMEVALUE 0\n" % mesh.name)
        out.write("\t\t*MESH_NUMVERTEX %d\n\t\t*MESH_NUMFACES %d\n" % (len(mesh.verts), len(mesh.faces)))
        out.write("\t\t*MESH_VERTEX_LIST {\n")
        for i, v in enumerate(mesh.verts):
            out.write("\t\t\t*MESH_VERTEX %d\t%.3f\t%.3f\t%.3f\n" % (i, v[0], v[1], v[2]))
        out.write("\t\t}\n\t\t*MESH_FACE_LIST {\n")
        for i, (a, b, c) in enumerate(mesh.faces):
            # The loader reads the rest of a face's line; with nothing left on
            # it, that read takes the next face. Exporters always write these.
            out.write("\t\t\t*MESH_FACE %d: A: %d B: %d C: %d AB: 1 BC: 1 CA: 1 *MESH_SMOOTHING 1 *MESH_MTLID 0\n"
                      % (i, a, b, c))
        out.write("\t\t}\n\t\t*MESH_NUMTVERTEX %d\n\t\t*MESH_TVERTLIST {\n" % len(mesh.uvs))
        for i, (u, v) in enumerate(mesh.uvs):
            # ASE's v runs up; the engine flips it on load.
            out.write("\t\t\t*MESH_TVERT %d\t%.5f\t%.5f\t0.0000\n" % (i, u, 1.0 - v))
        out.write("\t\t}\n\t\t*MESH_NUMTVFACES %d\n\t\t*MESH_TFACELIST {\n" % len(mesh.faces))
        for i, (a, b, c) in enumerate(mesh.faces):
            out.write("\t\t\t*MESH_TFACE %d\t%d\t%d\t%d\n" % (i, a, b, c))
        out.write("\t\t}\n")
        if mesh.colours:
            out.write("\t\t*MESH_NUMCVERTEX %d\n\t\t*MESH_CVERTLIST {\n" % len(mesh.colours))
            for i, (r, g, b) in enumerate(mesh.colours):
                out.write("\t\t\t*MESH_VERTCOL %d\t%.4f\t%.4f\t%.4f\n" % (i, r, g, b))
            out.write("\t\t}\n\t\t*MESH_NUMCVFACES %d\n\t\t*MESH_CFACELIST {\n" % len(mesh.faces))
            for i, (a, b, c) in enumerate(mesh.faces):
                out.write("\t\t\t*MESH_CFACE %d\t%d\t%d\t%d\n" % (i, a, b, c))
            out.write("\t\t}\n")
        out.write("\t}\n\t*MATERIAL_REF %d\n}\n" % materials.index(mesh.material))
    return out.getvalue().encode("ascii")


def grid(mesh, rows, cols, position, uv, outward):
    """A rows x cols vertex grid as triangles; position(r, c) in engine units."""
    index = [[mesh.vertex(position(r, c), uv(r, c)) for c in range(cols)] for r in range(rows)]
    for r in range(rows - 1):
        for c in range(cols - 1):
            a, b, d, e = index[r][c], index[r][c + 1], index[r + 1][c], index[r + 1][c + 1]
            mid = (mesh.verts[a] + mesh.verts[e]) * 0.5
            out = outward(mid)
            mesh.face(a, b, e, out)
            mesh.face(a, e, d, out)


# ---------------------------------------------------------------- the Sphere

SHELL_STOPS = [(0.0, "#2F4551", 1), (0.1, "#2A3D48", 1), (0.24, "#17232A", 1), (0.4, "#0F171B", 1),
               (0.7, "#0B1013", 1), (0.9, "#040608", 1), (1.0, "#010202", 1)]


def shell_texture():
    """The shell's light by its angle from the point facing the key light. The
    atlas grades the shell from that point out to 1.8 apparent radii; on the
    sphere that is a chord of 2 sin( angle / 2 ) radii."""
    width = 512
    pixels = np.zeros((4, width, 4), np.uint8)
    for x in range(width):
        angle = (x + 0.5) / width * math.pi
        rgb, _ = ramp(SHELL_STOPS, 2 * math.sin(angle / 2) / 1.8)
        pixels[:, x, :3] = np.round(rgb)
        pixels[:, x, 3] = 255
    return pixels


def shell_mesh(scene):
    """A sphere of radius R whose pole faces the key light, so the shell's
    light is a function of latitude alone."""
    mesh = Mesh("shell", f"{MODEL_DIR}/shell")
    pole = scene.light
    t1 = norm(np.cross(pole, [0.0, 1.0, 0.0]))
    t2 = np.cross(pole, t1)
    rows, cols = 65, 129

    def direction(r, c):
        lat = r / (rows - 1) * math.pi
        lon = c / (cols - 1) * 2 * math.pi
        return pole * math.cos(lat) + (t1 * math.cos(lon) + t2 * math.sin(lon)) * math.sin(lat)

    grid(mesh, rows, cols, lambda r, c: to_engine(direction(r, c)),
         lambda r, c: (r / (rows - 1), 0.5), lambda p: p)
    return mesh


ICE_MEAN = 0.8            # the ice texture's mean, which vertex colours divide out
ICE_REPEAT = 0.06         # Sphere radii to one repeat of the ice texture


def ice_texture():
    """The plates' tiling detail: fractal value noise with fine cracks, about
    ICE_MEAN on average, brightening to 1 and darkening to about 0.55."""
    size = 512
    gen = np.random.Generator(np.random.PCG64(4242))

    def octave(cells):
        lattice = gen.random((cells, cells))
        x = np.arange(size) * cells / size
        x0 = np.floor(x).astype(int)
        f = x - x0
        f = f * f * (3 - 2 * f)
        a = lattice[np.ix_(x0 % cells, x0 % cells)]
        b = lattice[np.ix_(x0 % cells, (x0 + 1) % cells)]
        c = lattice[np.ix_((x0 + 1) % cells, x0 % cells)]
        d = lattice[np.ix_((x0 + 1) % cells, (x0 + 1) % cells)]
        fy, fx = f[:, None], f[None, :]
        return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy

    noise = sum(octave(c) * w for c, w in ((4, 0.45), (8, 0.25), (16, 0.15), (32, 0.1), (64, 0.05)))
    cracks = np.minimum(np.abs(octave(6) - 0.5), np.abs(octave(12) - 0.5) * 1.3)
    crack = np.clip(1 - cracks / 0.012, 0, 1)
    value = 0.55 + 0.45 * np.clip((noise - noise.min()) / (noise.max() - noise.min()), 0, 1) ** 1.3
    value = value * (1 - 0.35 * crack) + 0.25 * np.clip(noise - 0.62, 0, 1)
    value = value * (ICE_MEAN / value.mean())
    pixels = np.zeros((size, size, 4), np.uint8)
    pixels[..., :3] = np.round(np.clip(value, 0, 1) * 255)[..., None]
    pixels[..., 3] = 255
    return pixels


def surface_meshes(parts):
    """The plates, green patches and craters as fans of small triangles just
    above the shell. The plates and patches, with their rims beneath them,
    are one blended surface: each polygon's colour is its vertices' colour
    over the tiling ice texture, laid flat on the polygon at a random offset.
    The craters are a second surface that darkens the shell (a multiply)."""
    mesh = Mesh("surface", f"{MODEL_DIR}/surface")
    craters = Mesh("craters", f"{MODEL_DIR}/craters")
    R = rnd(31)
    state = {}

    def expand(centre, ring, amount):
        out = []
        for p in ring:
            tangent = p - centre * (p @ centre)
            out.append(norm(p + norm(tangent) * amount))
        return out

    def fan(target, centre, ring, altitude, colour, steps=3):
        k = len(ring)
        shared = {}
        t1 = norm(np.cross([0.0, 1.0, 0.0] if abs(centre[1]) < 0.9 else [1.0, 0.0, 0.0], centre))
        t2 = np.cross(centre, t1)
        offset = (R(), R())

        def uv_of(w):
            return (offset[0] + (w @ t1) / ICE_REPEAT, offset[1] + (w @ t2) / ICE_REPEAT)
        mesh = target

        def point(i, s, t):
            # A spoke's points are shared by the triangles either side of it:
            # (i, s, 0) lies on spoke i, and (i, 0, t) on spoke i + 1.
            if s == 0 and t == 0:
                key = "centre"
            elif s == 0:
                key = ((i + 1) % k, t)
            elif t == 0:
                key = (i, s)
            else:
                key = (i, s, t)
            if key not in shared:
                w = norm(centre * (steps - s - t) + ring[i] * s + ring[(i + 1) % k] * t)
                shared[key] = mesh.vertex(to_engine(w * altitude), uv_of(w), colour)
            return shared[key]

        for i in range(k):
            rows = {}
            for s in range(steps + 1):
                for t in range(steps + 1 - s):
                    rows[s, t] = point(i, s, t)
            for s in range(steps):
                for t in range(steps - s):
                    p0, p1, p2 = rows[s, t], rows[s + 1, t], rows[s, t + 1]
                    mesh.face(p0, p1, p2, mesh.verts[p0])
                    if t + s + 1 < steps:
                        mesh.face(p1, rows[s + 1, t + 1], p2, mesh.verts[p1])

    world = turn_matrix(0.0)
    light = norm(LIGHT)
    shell = hex_rgb("#0F171B")

    def lit(rgb):
        """A colour as the vertex carries it: the ice texture's mean divided out."""
        return tuple(float(np.clip(v / 255.0 / ICE_MEAN, 0, 1)) for v in rgb)

    layers = {k: [] for k in range(5)}
    for kind, centre, ring, tone in parts:
        c = world @ centre
        r = [world @ p for p in ring]
        lam = max(0.0, c @ light)
        if kind == 2:
            # 0.3 * lam black over the shell, as the atlas draws a crater
            layers[0].append((craters, c, r, (1 - 0.3 * lam,) * 3))
        elif kind == 0:
            layers[1].append((mesh, c, expand(c, r, 0.003), lit(hex_rgb("#05090C"))))
            layers[2].append((mesh, c, r, lit(plate_rgb(0.3 + 0.08 * lam + (tone - 0.5) * 0.26))))
        else:
            rim = hex_rgb("#4CD08E") * 0.55 + shell * 0.45
            layers[3].append((mesh, c, expand(c, r, 0.004), lit(rim)))
            layers[4].append((mesh, c, r, lit(hex_rgb("#20724F" if lam > 0.6 else "#145D3C"))))
    for layer in range(5):
        for target, c, r, colour in layers[layer]:
            fan(target, c, r, 1.0015 + 0.0003 * layer, colour)
    return [craters, mesh]


def sun_mesh():
    """A unit quad facing the camera along the engine's -x; the renderDef
    places and sizes it each frame (modelFacing2)."""
    mesh = Mesh("sun", f"{MODEL_DIR}/sun")
    corners = [(0, 1, 1), (0, -1, 1), (0, -1, -1), (0, 1, -1)]
    uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]
    index = [mesh.vertex(p, uv) for p, uv in zip(corners, uvs)]
    mesh.face(index[0], index[1], index[2], (-1, 0, 0))
    mesh.face(index[0], index[2], index[3], (-1, 0, 0))
    return mesh


# ---------------------------------------------------------------- Earth

class EarthFrame:
    """Polar coordinates about the axis from Earth's centre to the rest
    camera: theta from the point beneath the camera, phi round the axis from
    the side facing up. The rest camera sees theta below the limb angle."""

    def __init__(self, scene, radius=EARTH_R):
        self.scene, self.radius = scene, radius
        to_cam = scene.cam_rest - scene.earth
        self.distance = float(np.linalg.norm(to_cam))
        self.axis = to_cam / self.distance
        up = np.array([0.0, 1.0, 0.0])
        self.up = norm(up - self.axis * (up @ self.axis))
        self.side = np.cross(self.axis, self.up)
        self.limb = math.acos(radius / self.distance)

    def point(self, theta, phi, radius=None):
        r = self.radius if radius is None else radius
        d = self.axis * math.cos(theta) + (self.up * math.cos(phi) + self.side * math.sin(phi)) * math.sin(theta)
        return self.scene.earth + d * r


def calibrate_depth(scene, earth):
    """Canvas units below the limb for each theta, measured along the phi whose
    limb point the rest camera draws at x 350 (the stock limb passes 350,408)."""
    target = 350.0
    best = None
    for phi in np.linspace(-EARTH_PHI, EARTH_PHI, 4001):
        x, y = scene.project(earth.point(earth.limb, phi))
        if math.isfinite(x) and 0 < y < 480 and (best is None or abs(x - target) < best[0]):
            best = (abs(x - target), phi)
    phi = best[1]
    limb_y = scene.project(earth.point(earth.limb, phi))[1]

    def depth(theta):
        return scene.project(earth.point(theta, phi))[1] - limb_y
    return phi, depth


EARTH_STOPS = [(0.0, "#DBE0ED", 1), (24.0, "#D0D4E4", 1), (36.0, "#94A2C8", 1), (59.0, "#78889B", 1),
               (110.0, "#7E8CA0", 1), (170.0, "#6E7E94", 1)]
GLOW = [(0.0, 0.75), (3.0, 0.60), (10.0, 0.35), (17.0, 0.19), (28.0, 0.09), (45.0, 0.0)]
EARTH_PHI = math.radians(100.0)


def glow_at(units):
    units = abs(units)
    for (o0, g0), (o1, g1) in zip(GLOW, GLOW[1:]):
        if units <= o1:
            return g0 + (g1 - g0) * (units - o0) / (o1 - o0)
    return 0.0


def theta_rings(limb, below, above, count):
    """Ring angles, dense at the limb: `below` radians under it, `above` over it."""
    s = np.linspace(-1.0, 1.0, count)
    return [limb + (above if v > 0 else below) * (abs(v) ** 2.2) * (1 if v > 0 else -1) for v in s]


def limb_circle(scene, earth):
    """The circle the rest camera draws Earth's limb on (the stock one has
    radius 1695 about 689,2069), through three limb points."""
    (ax, ay), (bx, by), (qx, qy) = [scene.project(earth.point(earth.limb, phi)) for phi in (-0.5, -0.2, 0.05)]
    dd = 2 * (ax * (by - qy) + bx * (qy - ay) + qx * (ay - by))
    cx = ((ax * ax + ay * ay) * (by - qy) + (bx * bx + by * by) * (qy - ay) + (qx * qx + qy * qy) * (ay - by)) / dd
    cy = ((ax * ax + ay * ay) * (qx - bx) + (bx * bx + by * by) * (ax - qx) + (qx * qx + qy * qy) * (bx - ax)) / dd
    return cx, cy, math.hypot(ax - cx, ay - cy)


EARTH_DEPTH = 400.0      # canvas units of Earth's colour texture beneath the limb
CLOUD_DEPTH = 120.0      # and of its cloud deck
GLOW_SPAN = (-50.0, 50.0)


def earth_meshes(scene):
    """Earth, its cloud deck and its glow. Each is graded by how far beneath
    (or above) the limb the rest camera draws its vertex, measured radially
    from the limb circle as the atlas grades it, so the bands keep their
    depth all along the limb. The camera is at rest, or nearly, whenever
    Earth is in view."""
    earth = EarthFrame(scene)
    circle = limb_circle(scene, earth)
    phi_cal, depth = calibrate_depth(scene, earth)
    cols = 193
    phis = np.linspace(-EARTH_PHI, EARTH_PHI, cols)
    # The limb as the rest camera draws it, finely.
    limb_xy = np.array([scene.project(earth.point(earth.limb, phi))
                        for phi in np.linspace(-EARTH_PHI, EARTH_PHI, 4001)])
    limb_xy = limb_xy[np.isfinite(limb_xy).all(axis=1)]

    def hits_earth(point):
        ray = norm(np.asarray(point) - scene.cam_rest)
        to_centre = scene.earth - scene.cam_rest
        return np.linalg.norm(to_centre - ray * (to_centre @ ray)) < EARTH_R and to_centre @ ray > 0

    def beneath(point):
        """Canvas units from the drawn limb: positive over Earth, negative above it."""
        x, y = scene.project(point)
        if not math.isfinite(x):
            return EARTH_DEPTH
        distance = float(np.min(np.hypot(limb_xy[:, 0] - x, limb_xy[:, 1] - y)))
        return distance if hits_earth(point) else -distance

    def v_of(point, lo, hi):
        return float(np.clip((beneath(point) - lo) / (hi - lo), 0.0, 1.0))

    # The body: theta from beneath the camera to a little past the limb.
    rings = theta_rings(earth.limb, earth.limb, math.radians(8.0), 61)
    body = Mesh("earth", f"{MODEL_DIR}/earth")
    grid(body, len(rings), cols, lambda r, c: to_engine(earth.point(rings[r], phis[c])),
         lambda r, c: (c / (cols - 1), v_of(earth.point(min(rings[r], earth.limb), phis[c]), 0.0, EARTH_DEPTH)),
         lambda p: p - to_engine(scene.earth))
    texture = np.zeros((1024, 4, 4), np.uint8)
    for y in range(1024):
        rgb, _ = ramp(EARTH_STOPS, (y + 0.5) / 1024 * EARTH_DEPTH)
        texture[y, :, :3] = np.round(rgb)
        texture[y, :, 3] = 255

    # The cloud deck: streaks laid along the limb, down to CLOUD_DEPTH beneath it.
    deck_r = EARTH_R * 1.0003
    deck_frame = EarthFrame(scene, deck_r)
    lo = earth.limb
    while depth(lo) < CLOUD_DEPTH * 1.6:
        lo -= math.radians(0.05)
    deck_rings = [lo + (deck_frame.limb - lo) * (i / 30) ** 0.7 for i in range(31)]
    clouds = Mesh("clouds", f"{MODEL_DIR}/clouds")
    repeat = 5.0
    grid(clouds, len(deck_rings), cols, lambda r, c: to_engine(deck_frame.point(deck_rings[r], phis[c])),
         lambda r, c: ((phis[c] + EARTH_PHI) / (2 * EARTH_PHI) * repeat,
                       v_of(deck_frame.point(min(deck_rings[r], deck_frame.limb), phis[c]), 0.0, CLOUD_DEPTH)),
         lambda p: p - to_engine(scene.earth))
    cloud_tex, drift = cloud_texture(repeat)

    # The glow: a shell above Earth, bright by how far from the limb the rest
    # camera draws each point, out and in (section 12.2's profile).
    halo = EarthFrame(scene, EARTH_R + 0.16)
    # Near its own limb the shell's angle barely moves its drawn place, so
    # its rings are placed by drawn distance above Earth's limb, every 2.5 u
    # through the glow's span, then out to the shell's limb.
    def ring_at(above):
        lo, hi = 0.0, halo.limb
        for _ in range(60):
            mid = (lo + hi) / 2
            if -beneath(halo.point(mid, phi_cal)) < above:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    targets = np.arange(GLOW_SPAN[0] - 10.0, GLOW_SPAN[1] + 2.5, 2.5)
    halo_rings = [ring_at(a) for a in targets] + [halo.limb - math.radians(0.05), halo.limb,
                                                   halo.limb + math.radians(0.5)]
    glow = Mesh("glow", f"{MODEL_DIR}/glow")
    grid(glow, len(halo_rings), cols, lambda r, c: to_engine(halo.point(halo_rings[r], phis[c])),
         lambda r, c: (c / (cols - 1), 1.0 - v_of(halo.point(min(halo_rings[r], halo.limb), phis[c]),
                                                -GLOW_SPAN[1], -GLOW_SPAN[0])),
         lambda p: p - to_engine(scene.earth))
    glow_tex = np.zeros((512, 4, 4), np.uint8)
    colour = hex_rgb("#E4ECFA")
    for y in range(512):
        above = GLOW_SPAN[0] + (y + 0.5) / 512 * (GLOW_SPAN[1] - GLOW_SPAN[0])
        glow_tex[y, :, :3] = np.round(colour * glow_at(above))
        glow_tex[y, :, 3] = 255
    return [body, clouds, glow], texture, cloud_tex, glow_tex, drift, earth, circle


def cloud_texture(repeat):
    """The atlas's CLOUD_MODEL streaks: white strokes along the limb, deeper
    ones longer and wider, on one tile of the deck that repeats `repeat`
    times round its 200 degrees. Rows run from the limb down to CLOUD_DEPTH."""
    R = rnd(77)
    width, height = 1024, 128
    span = 2 * EARTH_PHI / repeat
    units_per_radian = 1695.0          # the stock limb circle's radius
    tile_units = span * units_per_radian
    alpha = np.zeros((height, width), np.float64)
    xs = np.arange(width)[None, :]
    ys = np.arange(height)[:, None]
    rows_per_unit = height / CLOUD_DEPTH
    for _ in range(int(96 * tile_units / (28.8 / 180 * math.pi * units_per_radian))):
        dp = R() ** 1.7
        at, d = R(), 3 + 104 * dp
        length = 26 + R() * 130
        w = (0.5 + dp * 7) * (0.5 + R())
        opacity = 0.07 + R() * 0.2
        cx = at * width
        cy = d * rows_per_unit
        half_len = length / 2 / tile_units * width
        half_w = max(0.6, w / 2 * rows_per_unit)
        for shift in (-width, 0, width):
            dx = (xs - cx - shift) / half_len
            dy = (ys - cy) / half_w
            stroke = np.clip(1 - dx * dx, 0, 1) ** 0.5 * np.exp(-dy * dy * 1.6)
            alpha = 1 - (1 - alpha) * (1 - stroke * opacity)
    pixels = np.zeros((height, width, 4), np.uint8)
    pixels[..., :3] = 255
    pixels[..., 3] = np.round(np.clip(alpha, 0, 1) * 255)
    drift = CLOUD_DRIFT / tile_units   # tile widths a second
    return pixels, drift


def sun_and_flare_check(scene):
    """The rest frame's checks against section 12.2's targets."""
    lines = []
    cx, cy = scene.project(np.zeros(3))
    d = scene.d1
    r = FOCAL / math.sqrt(d * d - 1)
    lines.append(f"Sphere at rest: centre {cx:.1f},{cy:.1f} radius {r:.1f} (target 357,222 r 186)")
    return lines


# ---------------------------------------------------------------- outputs

def tga(pixels):
    out = io.BytesIO()
    Image.fromarray(pixels).save(out, format="TGA", compression=None)
    return out.getvalue()


def material_text(drift):
    return f"""// Generated by tools/assets/generate_menu_scene.py; do not edit.
// The main menu's 3D backdrop (docs/dev/prey-ui-visual-design.md section
// 12.2). Every surface is unlit: the key light is baked into the shell's
// texture, the plates are self-lit as the painting shows them, and Earth's
// limb, cloud deck and glow are graded for the rest camera, which is where
// the camera is whenever Earth is in view.

{MODEL_DIR}/shell
{{
	noShadows
	{{
		map {TEXTURE_DIR}/shell.tga
		clamp
		linear
	}}
}}

{MODEL_DIR}/earth
{{
	noShadows
	{{
		map {TEXTURE_DIR}/earth.tga
		clamp
		linear
	}}
}}

// The stock sun flare's stage (guis/assets/menu/preymenu/sol), on a billboard
// the renderDef keeps on the shell's camera side: over the shell, under the
// plates.
{MODEL_DIR}/sun
{{
	noShadows
	translucent
	sort far
	{{
		blend add
		map models/mapobjects/skybox/sun1.tga
		rotate time*0.01
		rgb solsurge[time*0.17]*1
		linear
		clamp
	}}
}}

// The craters darken the shell before the plates draw over it.
{MODEL_DIR}/craters
{{
	noShadows
	translucent
	sort 3.5
	{{
		blend filter
		map _white
		vertexColor
	}}
}}

// Each plate's colour is its vertices', over the tiling ice.
{MODEL_DIR}/surface
{{
	noShadows
	translucent
	sort medium
	{{
		blend blend
		map {TEXTURE_DIR}/ice.tga
		vertexColor
	}}
}}

// Drifts {CLOUD_DRIFT:g} u a second along the limb.
{MODEL_DIR}/clouds
{{
	noShadows
	translucent
	sort close
	{{
		blend blend
		map {TEXTURE_DIR}/clouds.tga
		scroll time*{drift:.6f}, 0
	}}
}}

{MODEL_DIR}/glow
{{
	noShadows
	translucent
	sort 6
	{{
		blend add
		map {TEXTURE_DIR}/glow.tga
		clamp
		linear
	}}
}}
"""


def fragment_text(scene):
    def vec(v, w=0.0):
        return "%.4f, %.4f, %.4f, %.4f" % (v[0], v[1], v[2], w)

    spin_axis = to_engine(turn_matrix(0.0) @ np.array([0.0, 1.0, 0.0]), 1.0)
    from_dir = to_engine(scene.start_dir, 1.0)
    to_dir = to_engine(scene.n1, 1.0)
    return f"""// Generated by tools/assets/generate_menu_scene.py; do not edit.
// The main menu's 3D backdrop (docs/dev/prey-ui-visual-design.md section
// 12.2): the Sphere and Earth under one camera with a 30 degree vertical
// field, drawn across the whole screen. orbitPlay starts the entrance's
// camera curve, orbitSkip ends it; at rest the camera is the stock painting's.
// The renderDef keeps gui::menuscene_ok, _motion, _moving, _x and _y.

			renderDef MenuScene {{
				rect		0, 0, 640, 480
				canvasfill	1
				backcolor	0, 0, 0, 0
				visible		( "gui::menuscene_ok" == 1 )
				notime		1
				sceneKey	"menuscene"
				fovY		30
				model		"{MODEL_DIR}/backdrop.ase"
				model1		"{MODEL_DIR}/surface.ase"
				modelSpin1	{vec(spin_axis, TURN_SECONDS)}
				model2		"{MODEL_DIR}/sun.ase"
				modelFacing2	{SCALE * 1.001:.4f}, {SUN_SIZE}, 0, 0
				lightOrigin	100000, 0, 0, 0
				lightColor	0, 0, 0, 0
				orbitCenter	0, 0, 0, 0
				orbitFrom	{vec(from_dir, scene.d0 * SCALE)}
				orbitTo		{vec(to_dir, scene.d1 * SCALE)}
				orbitAimFrom	{vec(to_engine(scene.aim0))}
				orbitAimTo	{vec(to_engine(scene.aim1))}
				orbitShape	{SCALE:.4f}, {ENTRANCE_MS}, {ACCEL}, {DECEL}
			}}
"""


def build():
    scene = Scene()
    parts = sphere_model(scene)
    shell = shell_mesh(scene)
    surface = surface_meshes(parts)
    earth_parts, earth_tex, cloud_tex, glow_tex, drift, earth, depth = earth_meshes(scene)
    files = {
        PAK1 / MODEL_DIR / "backdrop.ase": write_ase(None, [shell] + earth_parts),
        PAK1 / MODEL_DIR / "surface.ase": write_ase(None, surface),
        PAK1 / MODEL_DIR / "sun.ase": write_ase(None, [sun_mesh()]),
        PAK1 / TEXTURE_DIR / "shell.tga": tga(shell_texture()),
        PAK1 / TEXTURE_DIR / "ice.tga": tga(ice_texture()),
        PAK1 / TEXTURE_DIR / "earth.tga": tga(earth_tex),
        PAK1 / TEXTURE_DIR / "clouds.tga": tga(cloud_tex),
        PAK1 / TEXTURE_DIR / "glow.tga": tga(glow_tex),
        PAK0 / "materials/menu_scene.mtr": material_text(drift).encode("ascii"),
        PAK0 / "guis/mainmenu/mainmenu_scene.guifragment": fragment_text(scene).encode("ascii"),
    }
    report = sun_and_flare_check(scene)
    limb = [scene.project(earth.point(earth.limb, phi)) for phi in np.linspace(-0.6, 0.1, 8)]
    report.append("Earth's limb at rest: " + " ".join(f"{x:.0f},{y:.0f}" for x, y in limb if -300 < x < 950))
    report.append(f"parts {len(parts)}, surface vertices {sum(len(m.verts) for m in surface)}")
    return files, report


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report stale outputs and write nothing")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    files, report = build()
    stale = []
    for path, data in files.items():
        if not path.exists() or path.read_bytes() != data:
            stale.append(path)
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
    if args.verbose:
        print("\n".join(report))
    if args.check and stale:
        for path in stale:
            print(f"stale: {path.relative_to(ROOT).as_posix()}", file=sys.stderr)
        print("run tools/assets/generate_menu_scene.py", file=sys.stderr)
        return 1
    if not args.check:
        print(f"wrote {len(stale)} of {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
