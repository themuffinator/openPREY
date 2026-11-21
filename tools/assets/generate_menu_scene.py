#!/usr/bin/env python3
# Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
"""The main menu's 3D backdrop: the Sphere and Earth of section 12.2 of
docs/dev/prey-ui-visual-design.md, as meshes, textures and a material file.

The scene reinterprets the stock painting in 3D. The Sphere is what the
painting shows: a hollow shell of dark wet rock, holed all over, through whose
gaps the lit ice of its inside wall shows, with a small sun hanging inside it.
Its gaps lie where the painting has them: the Interface Atlas's measured table
of the painting's gaps, read from the atlas page, is cast from the rest camera
onto the shell, and the far side is holed in the same manner from the atlas's
seeded generator. Every Sphere texture is raster art painted here from fixed
seeds (fractal noise, Voronoi ice); nothing is drawn as vector shapes.

Earth is the game's own: its material shows Prey's outro Earth map
(textures/outro/earthcomp4096) and the Sphere's sun the stock `sol` stages,
both read from the installed game at run time. Nothing from the retail
archives is written here.

Outputs (edit this script, never them; --check reports any that is stale):

| File | Holds |
| --- | --- |
| pak1 models/menu/scene/backdrop.ase | Earth, its limb haze and its glow, which never move |
| pak1 models/menu/scene/surface.ase | The Sphere's shell and its inside wall, which turn |
| pak1 models/menu/scene/sun.ase | The sun's quad, a billboard the renderDef keeps at the Sphere's centre |
| pak1 guis/assets/menu/scene/*.tga | The shell's rock and gaps, its green glows, the inside ice, Earth's haze and glow |
| pak0 materials/menu_scene.mtr | Their materials |
| pak0 guis/mainmenu/mainmenu_scene.guifragment | The renderDef: camera curve, models and lights |

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
from PIL import Image, ImageDraw, ImageFilter
from scipy.spatial import cKDTree

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
SUN_SIZE = 0.17                  # the sun's radius against the Sphere's
CLOUD_DRIFT = 1.5                # u a second along the limb
INSIDE = 0.955                   # the inside wall's radius against the shell's

# Earth's turn: the point beneath the rest camera, and north toward the limb.
EARTH_SUBCAMERA = (-38.0, -150.0)   # latitude, longitude in degrees: the cloudy South Pacific
EARTH_MAP = "textures/outro/earthcomp4096"


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
    """The atlas's SPHERE_MODEL: each part is (kind, centre, ring, tone, painted) in the
    body frame. Kind 0 is a gap through the shell (the atlas calls the ice seen
    through it a plate), 1 a green patch, 2 a crater."""
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
        out.append((kind, lift(n, t, cx, cy), pts, R(), False))

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
        out.append((kind, cast(x, y), pts, R(), True))

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


def ramp_array(stops, t):
    """Per-element linear interpolation through (offset, '#rrggbb') stops."""
    offsets = np.array([o for o, _ in stops])
    colours = np.array([hex_rgb(c) for _, c in stops])
    t = np.clip(t, offsets[0], offsets[-1])
    return np.stack([np.interp(t, offsets, colours[:, k]) for k in range(3)], axis=-1)


# ---------------------------------------------------------------- raster noise

class Noise3:
    """Value noise in three dimensions on a hashed lattice, quintic smoothing.
    Sampling directions on the sphere gives seamless, pole-free textures."""

    def __init__(self, seed):
        gen = np.random.Generator(np.random.PCG64(seed))
        self.perm = gen.permutation(256).astype(np.int64)
        self.values = gen.random(256)

    def _hash(self, x, y, z):
        p = self.perm
        return self.values[p[(p[(p[x & 255] + y) & 255] + z) & 255]]

    def __call__(self, pts):
        x, y, z = pts[..., 0], pts[..., 1], pts[..., 2]
        xi, yi, zi = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64), np.floor(z).astype(np.int64)
        fx, fy, fz = x - xi, y - yi, z - zi
        u = fx * fx * fx * (fx * (fx * 6 - 15) + 10)
        v = fy * fy * fy * (fy * (fy * 6 - 15) + 10)
        w = fz * fz * fz * (fz * (fz * 6 - 15) + 10)
        out = 0.0
        for dx in (0, 1):
            wx = u if dx else 1 - u
            for dy in (0, 1):
                wy = v if dy else 1 - v
                for dz in (0, 1):
                    wz = w if dz else 1 - w
                    out = out + wx * wy * wz * self._hash(xi + dx, yi + dy, zi + dz)
        return out

    def fbm(self, pts, octaves, scale, gain=0.5, ridged=False):
        total, amp, norm_ = 0.0, 1.0, 0.0
        for o in range(octaves):
            n = self(pts * scale * (2 ** o) + o * 17.31)
            if ridged:
                n = 1 - np.abs(n * 2 - 1)
            total = total + n * amp
            norm_ += amp
            amp *= gain
        return total / norm_


def equirect_dirs(width, height):
    """Body-frame directions for an equirectangular texture whose pole is the
    Sphere's spin axis (body y): u runs round the axis, v from the top pole."""
    lon = (np.arange(width) + 0.5) / width * 2 * math.pi - math.pi
    lat = math.pi / 2 - (np.arange(height) + 0.5) / height * math.pi
    lon, lat = np.meshgrid(lon, lat)
    return np.stack([np.cos(lat) * np.sin(lon), np.sin(lat), np.cos(lat) * np.cos(lon)], axis=-1)


def equirect_uv(d):
    d = norm(d)
    lon = math.atan2(d[0], d[2])
    lat = math.asin(max(-1.0, min(1.0, d[1])))
    return (lon + math.pi) / (2 * math.pi), (math.pi / 2 - lat) / math.pi


def polygon_mask(parts, kinds, width, height, grow=1.0):
    """The parts' outlines rasterised onto an equirectangular mask (body
    frame), supersampled four times and filtered down."""
    ss = 4
    image = Image.new("L", (width * ss, height * ss), 0)
    draw = ImageDraw.Draw(image)
    for kind, centre, ring, *_ in parts:
        if kind not in kinds:
            continue
        pts = []
        for p in ring:
            q = norm(centre + (np.asarray(p) - centre) * grow)
            u, v = equirect_uv(q)
            pts.append([u * width * ss, v * height * ss])
        pts = np.array(pts)
        cu, _ = equirect_uv(centre)
        cx = cu * width * ss
        # keep the outline on the centre's side of the seam
        pts[:, 0] = np.where(pts[:, 0] - cx > width * ss / 2, pts[:, 0] - width * ss, pts[:, 0])
        pts[:, 0] = np.where(cx - pts[:, 0] > width * ss / 2, pts[:, 0] + width * ss, pts[:, 0])
        for shift in (-width * ss, 0, width * ss):
            draw.polygon([(float(x + shift), float(y)) for x, y in pts], fill=255)
    return np.asarray(image.resize((width, height), Image.LANCZOS), dtype=np.float64) / 255.0


def blur(field, radius):
    image = Image.fromarray(np.clip(field * 255, 0, 255).astype(np.uint8))
    return np.asarray(image.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float64) / 255.0


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- the Sphere

SHELL_SIZE = (2048, 1024)
INSIDE_SIZE = (2048, 1024)


def shell_textures(parts, scene):
    """The shell: wet dark rock with relief, organic gaps (alpha 0, cut by the
    material's alpha test) with raised lips, shallow craters, and green glows.
    On the face the rest camera sees, the gaps are the painting's, cast from
    the atlas's table; elsewhere they are cut from warped noise in the same
    manner, and the two meet across a band about the face's edge. Returns the
    RGBA rock (its luminance is also the shell's height map) and the additive
    green glow map."""
    w, h = SHELL_SIZE
    dirs = equirect_dirs(w, h)
    n = Noise3(9001)
    painted = [p for p in parts if p[0] == 0 and p[4]]
    gaps = blur(polygon_mask(painted, {0}, w, h, grow=1.0), 2.0)
    # Gaps elsewhere: blobs from domain-warped noise, about as much of the
    # shell as the painted face shows.
    warp = np.stack([Noise3(101 + k).fbm(dirs, 3, 4.0) - 0.5 for k in range(3)], axis=-1)
    blobs = Noise3(303).fbm(dirs + warp * 0.22, 4, 7.0)
    cut = np.quantile(blobs, 0.75)
    blobs = smoothstep(cut - 0.03, cut + 0.03, blobs)
    face = turn_matrix(0.0).T @ norm(scene.cam_rest)
    facing = dirs @ face
    weight = smoothstep(math.cos(math.radians(78)), math.cos(math.radians(62)), facing)
    field = weight * gaps + (1 - weight) * blobs
    rough = n.fbm(dirs, 4, 9.0) - 0.5
    edge = field + rough * 0.35
    hole = edge > 0.5
    soft = blur(hole.astype(np.float64), 6.0)
    lip = smoothstep(0.0, 0.25, soft) * (1 - smoothstep(0.35, 0.5, soft))
    craters = blur(polygon_mask(parts, {2}, w, h), 3.0)
    green = blur(polygon_mask(parts, {1}, w, h, grow=1.1), 1.2)

    # Rock: broad swells, ridged veins and fine grit, with the lips raised and
    # the crater floors sunk.
    swell = n.fbm(dirs, 3, 2.5)
    veins = Noise3(77).fbm(dirs, 6, 9.0, ridged=True)
    ripples = Noise3(91).fbm(dirs, 4, 40.0, ridged=True)
    grit = Noise3(5).fbm(dirs, 3, 140.0)
    height = 0.34 * swell + 0.30 * veins ** 2 + 0.16 * ripples + 0.14 * grit + 0.12 * lip - 0.25 * craters
    height = (height - height.min()) / (height.max() - height.min())

    stops = [(0.0, "#0A0F13"), (0.35, "#1B262D"), (0.6, "#33434C"), (0.85, "#5A6C76"), (1.0, "#7F929C")]
    rgb = ramp_array(stops, height)
    # a cold blue cast in the hollows, as the painting's shell has
    rgb = rgb * (1 - 0.12 * (1 - height))[..., None] + np.array([6, 12, 20]) * (1 - height)[..., None]
    # the gaps' edges are in shadow, as the painting draws them
    rgb = rgb * (1 - 0.7 * smoothstep(0.0, 0.3, soft) * (1 - smoothstep(0.42, 0.5, soft)))[..., None]
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., :3] = np.clip(np.round(rgb), 0, 255)
    # Alpha is a soft ramp across each gap's edge, not a step: filtered and
    # alpha-tested at 0.5 it cuts a smooth edge however close the camera comes.
    rgba[..., 3] = np.round(np.clip(0.5 - (edge - 0.5) / 0.12, 0, 1) * 255)

    glow = np.zeros((h, w, 4), np.uint8)
    g = np.clip(green * (0.75 + 0.5 * Noise3(41).fbm(dirs, 3, 30.0)), 0, 1)
    glow[..., :3] = np.round(np.stack([g * 16, g * 96, g * 54], axis=-1))
    glow[..., 3] = 255
    glow = np.asarray(Image.fromarray(glow).resize((w // 2, h // 2), Image.LANCZOS))
    return rgba, glow


def inside_texture():
    """The inside wall: blue ice in faceted crystals, bright along their
    seams and glittering, as the painting shows it through the gaps."""
    w, h = INSIDE_SIZE
    dirs = equirect_dirs(w, h).reshape(-1, 3)
    gen = np.random.Generator(np.random.PCG64(2718))
    seeds = gen.normal(size=(2600, 3))
    seeds /= np.linalg.norm(seeds, axis=1)[:, None]
    tree = cKDTree(seeds)
    dist, index = tree.query(dirs, k=2)
    cell = gen.random(len(seeds))[index[:, 0]]
    edge = 1 - smoothstep(0.0, 0.01, dist[:, 1] - dist[:, 0])
    # Crystal faces catch the light unevenly: a shade across each face.
    tilt = gen.normal(size=(len(seeds), 3))[index[:, 0]]
    facet = 0.5 + 0.5 * np.tanh(np.sum((dirs - seeds[index[:, 0]]) * tilt, axis=1) * 25.0)
    cloud = Noise3(31).fbm(dirs, 4, 3.0)
    streaks = Noise3(47).fbm(dirs * np.array([1.0, 3.5, 1.0]), 4, 6.0, ridged=True) ** 3
    grain = Noise3(11).fbm(dirs, 2, 90.0)
    sparkle = smoothstep(0.74, 0.80, Noise3(17).fbm(dirs, 2, 260.0))
    value = (0.12 + 0.16 * cell + 0.14 * facet + 0.38 * cloud + 0.32 * streaks
             + 0.08 * grain + 0.12 * edge + 0.5 * sparkle)
    stops = [(0.0, "#050B17"), (0.3, "#10244A"), (0.55, "#264A8A"), (0.8, "#5B86CF"), (1.0, "#DCE8FA")]
    rgb = ramp_array(stops, np.clip(value, 0, 1)).reshape(h, w, 3)
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = np.clip(np.round(rgb), 0, 255)
    out[..., 3] = 255
    return out


# ---------------------------------------------------------------- meshes

class Mesh:
    def __init__(self, name, material):
        self.name, self.material = name, material
        self.verts, self.uvs, self.faces = [], [], []

    def vertex(self, position, uv):
        self.verts.append(np.asarray(position, float))
        self.uvs.append((float(uv[0]), float(uv[1])))
        return len(self.verts) - 1

    def face(self, a, b, c, outward):
        """A triangle wound counter-clockwise seen from `outward`, as ASE wants."""
        va, vb, vc = self.verts[a], self.verts[b], self.verts[c]
        if np.cross(vb - va, vc - va) @ np.asarray(outward) < 0:
            b, c = c, b
        self.faces.append((a, b, c))


def write_ase(meshes):
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
        out.write("\t\t}\n\t}\n\t*MATERIAL_REF %d\n}\n" % materials.index(mesh.material))
    return out.getvalue().encode("ascii")


def grid(mesh, rows, cols, position, uv, outward):
    """A rows x cols vertex grid as triangles; position(r, c) in engine units."""
    index = [[mesh.vertex(position(r, c), uv(r, c)) for c in range(cols)] for r in range(rows)]
    for r in range(rows - 1):
        for c in range(cols - 1):
            a, b, d, e = index[r][c], index[r][c + 1], index[r + 1][c], index[r + 1][c + 1]
            mid = (mesh.verts[a] + mesh.verts[e]) * 0.5
            out = outward(mid)
            if np.linalg.norm(mesh.verts[a] - mesh.verts[b]) > 1e-6:
                mesh.face(a, b, e, out)
            if np.linalg.norm(mesh.verts[d] - mesh.verts[e]) > 1e-6:
                mesh.face(a, e, d, out)


def sphere_meshes():
    """The shell (outward, radius R) and the inside wall (inward, a little
    smaller), both mapped round the Sphere's spin axis, in the body frame at
    its painted face; the renderDef turns them."""
    world = turn_matrix(0.0)
    rows, cols = 97, 193

    def direction(r, c):
        lat = math.pi / 2 - r / (rows - 1) * math.pi
        lon = c / (cols - 1) * 2 * math.pi - math.pi
        return np.array([math.cos(lat) * math.sin(lon), math.sin(lat), math.cos(lat) * math.cos(lon)])

    uv = lambda r, c: (c / (cols - 1), r / (rows - 1))
    shell = Mesh("shell", f"{MODEL_DIR}/shell")
    grid(shell, rows, cols, lambda r, c: to_engine(world @ direction(r, c)), uv, lambda p: p)
    inside = Mesh("inside", f"{MODEL_DIR}/inside")
    grid(inside, rows, cols, lambda r, c: to_engine(world @ direction(r, c) * INSIDE), uv, lambda p: -p)
    return [shell, inside]


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


class Geography:
    """Earth's own frame: the point beneath the rest camera at
    EARTH_SUBCAMERA, north toward the limb the camera sees."""

    def __init__(self, earth):
        lat0, lon0 = (math.radians(v) for v in EARTH_SUBCAMERA)
        a, up = earth.axis, earth.up
        self.north = math.sin(lat0) * a + math.cos(lat0) * up
        equator = norm(a - self.north * (a @ self.north))
        east = np.cross(self.north, equator)
        # longitude lon0 at `equator`: the prime meridian lies lon0 west of it
        self.prime = equator * math.cos(lon0) - east * math.sin(lon0)
        self.east = np.cross(self.north, self.prime)

    def uv(self, d):
        d = norm(d)
        lat = math.asin(max(-1.0, min(1.0, d @ self.north)))
        lon = math.atan2(d @ self.east, d @ self.prime)
        return (lon + math.pi) / (2 * math.pi), (math.pi / 2 - lat) / math.pi


def calibrate_phi(scene, earth):
    """The phi whose limb point the rest camera draws at x 350 (the stock
    limb passes 350,408)."""
    best = None
    for phi in np.linspace(-EARTH_PHI, EARTH_PHI, 4001):
        x, y = scene.project(earth.point(earth.limb, phi))
        if math.isfinite(x) and 0 < y < 480 and (best is None or abs(x - 350.0) < best[0]):
            best = (abs(x - 350.0), phi)
    return best[1]


GLOW = [(0.0, 0.75), (3.0, 0.60), (10.0, 0.35), (17.0, 0.19), (28.0, 0.09), (45.0, 0.0)]
# Earth's air, added over the map: white at the limb, blue beneath it.
HAZE = [(0.0, (0.86, 0.88, 0.95)), (8.0, (0.62, 0.68, 0.82)), (22.0, (0.36, 0.44, 0.62)),
        (45.0, (0.16, 0.22, 0.36)), (120.0, (0.06, 0.09, 0.16)), (400.0, (0.03, 0.05, 0.09))]
EARTH_PHI = math.radians(100.0)
HAZE_DEPTH = 400.0
GLOW_SPAN = (-50.0, 50.0)
# The model loader welds texture coordinates closer than r_slopTexCoord (0.001).
# Earth's rings near the limb are closer than that across a whole-globe map,
# so its coordinates (and the haze's) are written this many times larger and
# the materials scale them back.
UV_SPREAD = 1000.0


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


def earth_meshes(scene):
    """Earth, its haze and its glow. Earth carries the outro's map in its own
    frame. The haze and the glow are graded by how far beneath (or above) the
    limb the rest camera draws each vertex, so each band keeps its depth all
    along the limb; the camera is at rest, or nearly, whenever Earth is in view."""
    earth = EarthFrame(scene)
    geo = Geography(earth)
    phi_cal = calibrate_phi(scene, earth)
    cols = 193
    phis = np.linspace(-EARTH_PHI, EARTH_PHI, cols)
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
            return HAZE_DEPTH
        distance = float(np.min(np.hypot(limb_xy[:, 0] - x, limb_xy[:, 1] - y)))
        return distance if hits_earth(point) else -distance

    def v_of(point, lo, hi):
        return float(np.clip((beneath(point) - lo) / (hi - lo), 0.0, 1.0))

    outward = lambda p: p - to_engine(scene.earth)
    rings = theta_rings(earth.limb, earth.limb, math.radians(8.0), 61)
    body = Mesh("earth", f"{MODEL_DIR}/earth")
    grid(body, len(rings), cols, lambda r, c: to_engine(earth.point(rings[r], phis[c])),
         lambda r, c: tuple(v * UV_SPREAD for v in geo.uv(earth.point(rings[r], phis[c]) - scene.earth)), outward)

    haze = Mesh("haze", f"{MODEL_DIR}/haze")
    haze_r = EARTH_R * 1.0004
    grid(haze, len(rings), cols, lambda r, c: to_engine(earth.point(rings[r], phis[c], haze_r)),
         lambda r, c: (0.5 * UV_SPREAD, UV_SPREAD * v_of(earth.point(min(rings[r], earth.limb), phis[c]), 0.0, HAZE_DEPTH)), outward)
    haze_tex = np.zeros((1024, 4, 4), np.uint8)
    offsets = [o for o, _ in HAZE]
    for y in range(1024):
        d = (y + 0.5) / 1024 * HAZE_DEPTH
        rgb = [np.interp(d, offsets, [c[k] for _, c in HAZE]) for k in range(3)]
        haze_tex[y, :, :3] = np.round(np.array(rgb) * 255)
        haze_tex[y, :, 3] = 255

    # The glow: a shell above Earth, its rings placed by drawn distance above
    # the limb, every 2.5 u through the glow's span (near its own limb the
    # shell's angle barely moves its drawn place).
    halo = EarthFrame(scene, EARTH_R + 0.16)

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
         lambda r, c: (0.5, 1.0 - v_of(halo.point(min(halo_rings[r], halo.limb), phis[c]),
                                     -GLOW_SPAN[1], -GLOW_SPAN[0])), outward)
    glow_tex = np.zeros((512, 4, 4), np.uint8)
    colour = hex_rgb("#E4ECFA")
    for y in range(512):
        above = GLOW_SPAN[0] + (y + 0.5) / 512 * (GLOW_SPAN[1] - GLOW_SPAN[0])
        glow_tex[y, :, :3] = np.round(colour * glow_at(above))
        glow_tex[y, :, 3] = 255

    # Earth turns under its clouds at CLOUD_DRIFT along the limb: in map
    # widths a second at the limb's latitude.
    limb_point = earth.point(earth.limb, phi_cal) - scene.earth
    limb_lat = math.asin(norm(limb_point) @ geo.north)
    radians_per_second = CLOUD_DRIFT / 1695.0 / max(0.2, math.cos(limb_lat))
    drift = radians_per_second / (2 * math.pi)
    return [body, haze, glow], haze_tex, glow_tex, drift, earth


# ---------------------------------------------------------------- outputs

def tga(pixels):
    out = io.BytesIO()
    Image.fromarray(pixels).save(out, format="TGA", compression=None)
    return out.getvalue()


def material_text(drift):
    return f"""// Generated by tools/assets/generate_menu_scene.py; do not edit.
// The main menu's 3D backdrop (docs/dev/prey-ui-visual-design.md section
// 12.2). The Sphere is a hollow shell of lit rock, cut by its gaps (alpha
// test), over an inside wall of ice that the sun inside it lights; Earth is
// the game's own map, under its air and its glow.

// The shell: lit by the renderDef's key light (from below, Earth's side) and
// its fill (from the front), relief from its own luminance, wet sheen, and
// the green glows. A faint ambient keeps its dark side from going black.
{MODEL_DIR}/shell
{{
	noShadows
	noSelfShadow
	bumpmap heightmap( {TEXTURE_DIR}/shell, 9 )
	{{
		blend diffusemap
		map {TEXTURE_DIR}/shell.tga
		alphatest 0.5
	}}
	{{
		blend specularmap
		map {TEXTURE_DIR}/shell.tga
		rgb 0.45
	}}
	{{
		blend add
		map {TEXTURE_DIR}/shell.tga
		rgb 0.035
		alphatest 0.5
	}}
	{{
		blend add
		map {TEXTURE_DIR}/shell_glow.tga
	}}
}}

// The inside wall, lit evenly by the sun at the centre: unlit.
{MODEL_DIR}/inside
{{
	noShadows
	{{
		map {TEXTURE_DIR}/inside.tga
		rgb 0.9
	}}
}}

// The stock sun (guis/assets/menu/preymenu/sol) on a billboard the renderDef
// keeps at the Sphere's centre: seen only through the gaps.
{MODEL_DIR}/sun
{{
	noShadows
	translucent
	sort far
	{{
		blend add
		map models/mapobjects/skybox/sun1.tga
		rotate time*0.01
		rgb solsurge[time*0.17]*1.0
		linear
		clamp
	}}
}}

// Prey's outro Earth map, shown unlit; it turns at {CLOUD_DRIFT:g} u a second along the limb.
{MODEL_DIR}/earth
{{
	noShadows
	{{
		map {EARTH_MAP}
		rgb 1.12
		scale {1 / UV_SPREAD:g}, {1 / UV_SPREAD:g}
		scroll time*{drift:.7f}, 0
		highres
	}}
}}

{MODEL_DIR}/haze
{{
	noShadows
	translucent
	sort close
	{{
		blend add
		map {TEXTURE_DIR}/haze.tga
		scale {1 / UV_SPREAD:g}, {1 / UV_SPREAD:g}
		clamp
		linear
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


KEY_COLOUR = (0.60, 0.66, 0.74)
SPILL_COLOUR = (0.56, 0.60, 0.64)


def fragment_text(scene):
    def vec(v, w=0.0):
        return "%.4f, %.4f, %.4f, %.4f" % (v[0], v[1], v[2], w)

    spin_axis = to_engine(turn_matrix(0.0) @ np.array([0.0, 1.0, 0.0]), 1.0)
    from_dir = to_engine(scene.start_dir, 1.0)
    to_dir = to_engine(scene.n1, 1.0)
    # The key light from below, on Earth's side, and a soft fill from the
    # front and a little above: far enough to fall nearly evenly on the Sphere.
    key = to_engine(scene.light * 14.0)
    # The sun's light spilling out of the gaps: a small light just outside
    # the shell's centre that brightens the face about the sun.
    fill = to_engine(norm(scene.n1 + np.array([0.0, -0.08, 0.0])) * 1.55)
    spill_radius = 1.15 * SCALE
    radius = 30.0 * SCALE
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
				modelFacing2	0, {SUN_SIZE}, 0, 0
				lightOrigin0	{vec(key)}
				lightColor0	{vec(KEY_COLOUR)}
				lightRadius0	{radius:.1f}, {radius:.1f}, {radius:.1f}, 0
				lightOrigin1	{vec(fill)}
				lightColor1	{vec(SPILL_COLOUR)}
				lightRadius1	{spill_radius:.1f}, {spill_radius:.1f}, {spill_radius:.1f}, 0
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
    shell_rgba, shell_glow = shell_textures(parts, scene)
    earth_parts, haze_tex, glow_tex, drift, earth = earth_meshes(scene)
    files = {
        PAK1 / MODEL_DIR / "backdrop.ase": write_ase(earth_parts),
        PAK1 / MODEL_DIR / "surface.ase": write_ase(sphere_meshes()),
        PAK1 / MODEL_DIR / "sun.ase": write_ase([sun_mesh()]),
        PAK1 / TEXTURE_DIR / "shell.tga": tga(shell_rgba),
        PAK1 / TEXTURE_DIR / "shell_glow.tga": tga(shell_glow),
        PAK1 / TEXTURE_DIR / "inside.tga": tga(inside_texture()),
        PAK1 / TEXTURE_DIR / "haze.tga": tga(haze_tex),
        PAK1 / TEXTURE_DIR / "glow.tga": tga(glow_tex),
        PAK0 / "materials/menu_scene.mtr": material_text(drift).encode("ascii"),
        PAK0 / "guis/mainmenu/mainmenu_scene.guifragment": fragment_text(scene).encode("ascii"),
    }
    cx, cy = scene.project(np.zeros(3))
    report = [f"Sphere at rest: centre {cx:.1f},{cy:.1f} radius {scene.r1:.1f} (target 357,222 r 186)"]
    limb = [scene.project(earth.point(earth.limb, phi)) for phi in np.linspace(-0.6, 0.1, 8)]
    report.append("Earth's limb at rest: " + " ".join(f"{x:.0f},{y:.0f}" for x, y in limb if -300 < x < 950))
    gaps = sum(1 for p in parts if p[0] == 0)
    report.append(f"gaps {gaps}, gap coverage {1 - shell_rgba[..., 3].mean() / 255:.1%} of the shell")
    return files, report


# Outputs earlier versions wrote that this one does not.
RETIRED = [PAK1 / TEXTURE_DIR / name for name in ("shell_light.tga", "ice.tga", "earth.tga", "clouds.tga", "surface.tga")]


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report stale outputs and write nothing")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    files, report = build()
    stale = [path for path in files if not path.exists() or path.read_bytes() != files[path]]
    retired = [path for path in RETIRED if path.exists()]
    if args.verbose:
        print("\n".join(report))
    if args.check:
        for path in stale + retired:
            print(f"stale: {path.relative_to(ROOT).as_posix()}", file=sys.stderr)
        if stale or retired:
            print("run tools/assets/generate_menu_scene.py", file=sys.stderr)
            return 1
        return 0
    for path in stale:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(files[path])
    for path in retired:
        path.unlink()
    print(f"wrote {len(stale)} of {len(files)} files, removed {len(retired)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
