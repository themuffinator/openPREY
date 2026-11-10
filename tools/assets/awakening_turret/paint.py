#!/usr/bin/env python3
"""Paint openQ4's skin for The Awakening's Strogg chaingun turret.

Reads the texture-space bakes made by blender_bake.py and the expansion's
tangent-space normal maps (used only to place wear, grime and lights; they
stay in the player's copy of The Awakening), and writes colour, specular and
glow masters. With --export it copies them into content/baseoq4/pak0 under
openQ4's own names (models/openq4/awakening/turret_strogg/).

Everything painted here is generated: palette, enamel, wear, grime, rust,
streaks, battle damage, heat tint, stencils, lights and the drum's rounds.
Nothing is taken from the expansion's placeholder colour maps; only the drum
windows' outline is traced from its alpha channel so the cut-outs line up
with the model.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys

os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from scipy import ndimage  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import details  # noqa: E402
import md5mesh  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
MODEL_DIR = "models/mapobjects/q4x/common_turret_strogg"
SHIP = os.path.join(REPO, "content", "baseoq4", "pak0", "models", "openq4", "awakening", "turret_strogg")
RES = {"01": 1024, "02": 512, "03": 1024, "04": 512}
CFG = {}


def configure(awakening, work):
    CFG["drop"] = os.path.join(awakening, MODEL_DIR)
    CFG["mesh"] = os.path.join(CFG["drop"], "common_turret_strogg.md5mesh")
    CFG["bake"] = os.path.join(work, "bake")
    CFG["out"] = os.path.join(work, "out")


def srgb(c):
    return np.array(c, dtype=np.float32) / 255.0


# ---------------------------------------------------------------- palette
PAL = {
    "oxblood": srgb((72, 42, 34)),      # Strogg armour enamel
    "oxblood_dark": srgb((52, 28, 24)),
    "gunmetal": srgb((60, 62, 60)),
    "gunmetal_dark": srgb((40, 42, 42)),
    "blued": srgb((50, 52, 54)),
    "steel_bare": srgb((132, 130, 124)),
    "rust": srgb((92, 50, 28)),
    "rust_dark": srgb((58, 33, 21)),
    "grime": srgb((30, 26, 21)),
    "dust": srgb((112, 102, 88)),
    "brass": srgb((182, 136, 64)),
    "brass_dark": srgb((96, 66, 30)),
    "copper": srgb((150, 86, 50)),
    "stencil": srgb((168, 80, 34)),
    "soot": srgb((16, 15, 14)),
}

# role per material island (islands numbered as md5mesh.components numbers them)
ROLES = {
    "01": {0: "shield", 7: "shield", 2: "gun", 8: "gun", 3: "gun", 9: "gun",
           1: "mech", 4: "mech", 10: "mech", 5: "barrel", 11: "barrel", 6: "barrel", 12: "barrel"},
    "02": {0: "hub", 1: "hub", 2: "drum", 5: "drum", 3: "drumrim", 4: "drumrim"},
    "03": {6: "base", 14: "base", 12: "deck", 20: "deck", 8: "housing", 16: "housing",
           7: "column", 15: "column", 13: "mech", 21: "mech", 0: "yoke", 1: "yoke", 2: "yoke", 3: "yoke"},
    "04": {0: "rounds"},
}
ROLE_DEFAULT = "mech"

ROLE_BASE = {
    "shield": ("oxblood", 0.22), "base": ("oxblood", 0.22), "housing": ("oxblood", 0.22),
    "gun": ("gunmetal", 0.30), "barrel": ("gunmetal_dark", 0.36), "mech": ("gunmetal_dark", 0.40),
    "yoke": ("blued", 0.42), "column": ("blued", 0.45), "deck": ("gunmetal_dark", 0.24),
    "hub": ("blued", 0.42), "drum": ("gunmetal", 0.40), "drumrim": ("gunmetal_dark", 0.42),
    "rounds": ("brass", 0.70),
}
PAINTED = {"shield", "base", "housing"}


# ---------------------------------------------------------------- noise
def _hash3(ix, iy, iz, seed):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return (h & 0xFFFFFF).astype(np.float32) / float(0xFFFFFF)


def vnoise3(p, seed=0):
    """Smooth value noise in [0,1] at points p (N,3)."""
    pi = np.floor(p).astype(np.int64)
    f = p - pi
    f = f * f * (3 - 2 * f)
    out = np.zeros(len(p), np.float32)
    for dx in (0, 1):
        wx = f[:, 0] if dx else 1 - f[:, 0]
        for dy in (0, 1):
            wy = f[:, 1] if dy else 1 - f[:, 1]
            for dz in (0, 1):
                wz = f[:, 2] if dz else 1 - f[:, 2]
                out += wx * wy * wz * _hash3(pi[:, 0] + dx, pi[:, 1] + dy, pi[:, 2] + dz, seed)
    return out


def fbm3(p, scale, octaves=5, seed=0, aniso=(1, 1, 1), gain=0.5):
    q = p * (np.array(aniso, np.float32) / scale)
    amp, tot, norm = 1.0, np.zeros(len(p), np.float32), 0.0
    for o in range(octaves):
        tot += amp * vnoise3(q, seed + o * 101)
        norm += amp
        amp *= gain
        q = q * 2.03 + 17.17
    return tot / norm


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- inputs
class Surface:
    def __init__(self, mid):
        self.mid = mid
        self.name = "common_turret_strogg" + mid
        self.res = RES[mid]
        r = self.res
        self.cover = cv2.imread(os.path.join(CFG["bake"], self.name + "_cover.png"), cv2.IMREAD_GRAYSCALE) > 127
        self.ao = cv2.imread(os.path.join(CFG["bake"], self.name + "_ao.png"), cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255
        on = cv2.imread(os.path.join(CFG["bake"], self.name + "_onormal.png"), cv2.IMREAD_COLOR)[..., ::-1].astype(np.float32)
        self.onormal = on / 127.5 - 1
        pos = cv2.imread(os.path.join(CFG["bake"], self.name + "_pos.exr"), cv2.IMREAD_UNCHANGED)[..., ::-1]
        self.pos = np.nan_to_num(pos.astype(np.float32))
        nm = Image.open(os.path.join(CFG["drop"], self.name + "_local.tga")).convert("RGB").resize((r, r), Image.BILINEAR)
        n = np.asarray(nm).astype(np.float32) / 127.5 - 1
        self.nmap = n  # id convention: +R right, +G image-down, +B out
        self.island = self._raster_islands()
        roles = ROLES[mid]
        rid = np.full((r, r), -1, np.int32)
        names = sorted(set(ROLE_BASE))
        self.role_names = names
        for k, v in roles.items():
            rid[self.island == k] = names.index(v)
        rid[rid < 0] = names.index(ROLE_DEFAULT)
        self.rid = rid
        self.idx = np.nonzero(self.cover)
        self.p = self.pos[self.idx]

    def _raster_islands(self):
        r = self.res
        text = open(CFG["mesh"], encoding="latin-1").read()
        for shader, uvs, tris in md5mesh.parse_meshes(text):
            if shader.endswith(self.name):
                comp = md5mesh.components(len(uvs), tris)
                img = np.full((r, r), -1, np.int32)
                for a, b, c in tris:
                    pts = np.array([[uvs[i][0] * r * 4, uvs[i][1] * r * 4] for i in (a, b, c)], np.int32)
                    cv2.fillPoly(img, [pts], int(comp[a]), lineType=cv2.LINE_8, shift=2)
                # grow islands into the bake margin
                missing = img < 0
                if missing.any():
                    _, (iy, ix) = ndimage.distance_transform_edt(missing, return_indices=True)
                    img = img[iy, ix]
                self.uvs, self.tris, self.comp = uvs, tris, comp
                return img
        raise KeyError(self.name)

    def mask(self, role):
        return self.rid == self.role_names.index(role)

    def field(self, values):
        out = np.zeros((self.res, self.res), np.float32)
        out[self.idx] = values
        return out


def curvature(s):
    """Convexity from the normal map (positive on ridges, negative in creases)."""
    n = s.nmap
    nz = np.clip(n[..., 2], 0.25, 1.0)
    nx, ny = n[..., 0] / nz, n[..., 1] / nz
    k = 1.0 if s.res <= 512 else 0.6
    div = np.gradient(nx, axis=1) + np.gradient(ny, axis=0)
    div = ndimage.gaussian_filter(div, k)
    inner = ndimage.binary_erosion(s.cover, iterations=2)
    div[~inner] = 0
    return div


def geo_edges(s):
    """Geometric creases from the object-space normal bake, split by AO into convex/concave."""
    on = s.onormal
    g = np.zeros(on.shape[:2], np.float32)
    for c in range(3):
        gx = np.abs(np.gradient(on[..., c], axis=1))
        gy = np.abs(np.gradient(on[..., c], axis=0))
        g += gx + gy
    same = (np.abs(np.gradient(s.island.astype(np.float32), axis=1)) + np.abs(np.gradient(s.island.astype(np.float32), axis=0))) == 0
    inner = ndimage.binary_erosion(s.cover, iterations=2) & same
    g[~inner] = 0
    g = ndimage.gaussian_filter(g, 1.2 * s.res / 1024)
    return np.clip(g * 3.0, 0, 1)


def cavity(s, curv):
    ao = s.ao
    ao_hp = ao - ndimage.gaussian_filter(ao, 6 * s.res / 1024)
    cav = np.clip(-curv * 2.2, 0, 1) + np.clip(-ao_hp * 4, 0, 1)
    return np.clip(cav, 0, 1)


def scratches(s, count, length, seed, angle_bias=0.0, spread=math.pi):
    rng = np.random.default_rng(seed)
    big = s.res * 2
    img = np.zeros((big, big), np.uint8)
    for _ in range(count):
        x, y = rng.uniform(0, big, 2)
        ang = angle_bias + rng.normal(0, spread)
        ln = rng.uniform(0.3, 1.0) * length * big / 1024
        x2, y2 = x + math.cos(ang) * ln, y + math.sin(ang) * ln
        w = int(rng.integers(1, 3))
        cv2.line(img, (int(x), int(y)), (int(x2), int(y2)), int(rng.uniform(90, 255)), w, cv2.LINE_AA)
    img = cv2.resize(img, (s.res, s.res), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    return img


# ---------------------------------------------------------------- strogg stencils
def glyph_strokes(rng):
    """One angular rune inside a unit cell: a canted spine with hooks, a notch or a dot.

    Kept deliberately unlike Latin letters: no stacked horizontal bars."""
    strokes = []
    lean = rng.uniform(-0.12, 0.12)
    top, bot = (0.35 + lean, 0.08), (0.35 - lean, 0.92)
    strokes.append([top, bot])
    kind = rng.integers(0, 5)
    if kind == 0:     # forked head
        strokes.append([(top[0], 0.3), (0.8, 0.08)])
    elif kind == 1:   # barbed foot
        strokes.append([(bot[0], 0.7), (0.82, 0.92), (0.82, 0.6)])
    elif kind == 2:   # open triangle off the spine
        strokes.append([(0.35, 0.35), (0.8, 0.5), (0.35, 0.65)])
    elif kind == 3:   # crossing diagonal
        strokes.append([(0.1, 0.62), (0.8, 0.3)])
    else:             # hooked crown
        strokes.append([top, (0.75, 0.2), (0.75, 0.42)])
    if rng.random() < 0.5:
        strokes.append([(0.72, 0.78), (0.72, 0.8)])  # dot
    return strokes


def draw_stencil(img, box, n, seed, thick=0.11):
    """Strogg-like glyph run with a bar frame, drawn as a solid stencil mask."""
    rng = np.random.default_rng(seed)
    x0, y0, x1, y1 = box
    h = y1 - y0
    cell = (x1 - x0) / n
    t = max(1, int(h * thick))
    cv2.line(img, (int(x0), int(y0 - t * 2)), (int(x1), int(y0 - t * 2)), 255, t)
    cv2.line(img, (int(x0), int(y1 + t * 2)), (int(x0 + (x1 - x0) * 0.6), int(y1 + t * 2)), 255, t)
    for i in range(n):
        cx = x0 + i * cell
        for st in glyph_strokes(rng):
            pts = np.array([[cx + px * cell * 0.9, y0 + py * h] for px, py in st], np.int32)
            cv2.polylines(img, [pts], False, 255, t, cv2.LINE_AA)


def chevrons(img, box, n):
    x0, y0, x1, y1 = box
    w = (x1 - x0) / n
    for i in range(n):
        cx = x0 + i * w
        pts = np.array([[cx, y0], [cx + w * 0.5, y0], [cx + w, (y0 + y1) / 2], [cx + w * 0.5, y1], [cx, y1], [cx + w * 0.5, (y0 + y1) / 2]], np.int32)
        cv2.fillPoly(img, [pts], 255, cv2.LINE_AA)


# ---------------------------------------------------------------- painter
def paint(mid, bounds):
    s = Surface(mid)
    r = s.res
    p = s.p
    curv = curvature(s)
    gedge = geo_edges(s)
    cav = cavity(s, curv)
    convex = np.clip(curv * 1.6, 0, 1) ** 1.5
    up = s.onormal[..., 2]

    def F(values):
        return s.field(values)

    # --- shared noise fields (3D, seam free)
    n_macro = F(fbm3(p, 22, 4, seed=1))
    n_mid = F(fbm3(p, 6, 5, seed=2))
    n_fine = F(fbm3(p, 1.2, 4, seed=3))
    n_streak = ndimage.gaussian_filter(F(fbm3(p, 2.2, 2, seed=4, aniso=(1.0, 1.0, 0.08))), 1.0)
    n_chip2 = F(fbm3(p, 0.35, 3, seed=9))
    n_rust = F(fbm3(p, 4.5, 5, seed=5))
    n_chip = F(fbm3(p, 0.9, 4, seed=6))

    base = np.zeros((r, r, 3), np.float32)
    spec = np.zeros((r, r), np.float32)
    for role in s.role_names:
        m = s.mask(role)
        if not m.any():
            continue
        col, sp = ROLE_BASE[role]
        base[m] = PAL[col]
        spec[m] = sp
    painted = np.zeros((r, r), bool)
    for role in PAINTED:
        painted |= s.mask(role)
    oxblood = painted.copy()

    # --- panel tones: light brushed steel plates, field-grey and bone paint,
    # oxblood plates on the gun, polished parts (boundaries follow real seams)
    machined = np.zeros((r, r), bool)
    for tone, (m, is_painted, sp) in details.tone_regions(s, mid).items():
        base[m] = details.TONES[tone]
        spec[m] = sp
        if is_painted:
            painted |= m
        else:
            painted &= ~m
        if tone == "oxblood":
            oxblood |= m
        else:
            oxblood &= ~m
        if tone in ("steel_light", "chrome"):
            machined |= m
    base = np.where(machined[..., None], base * details.brushed(s, n_fine)[..., None], base)

    # --- macro / mid variation of the enamel or metal
    var = 1 + (n_macro - 0.5) * 0.35 + (n_mid - 0.5) * 0.18 + (n_fine - 0.5) * 0.06
    base *= var[..., None]
    # enamel fade: armour panels sun/heat-faded towards a browner tone in patches
    fade = smooth(n_macro + (n_mid - 0.5) * 0.4, 0.55, 0.8) * oxblood
    base = base * (1 - fade[..., None] * 0.35) + PAL["oxblood_dark"] * 0.2 * fade[..., None] + srgb((92, 64, 50)) * fade[..., None] * 0.15

    # --- stencils on the shield and base armour (painted parts only)
    sten = np.zeros((r, r), np.uint8)
    if mid == "01":
        # shield panels: uv x 0.01-0.92, y 0.41-0.98; bracket seam at ~0.69
        draw_stencil(sten, (0.56 * r, 0.47 * r, 0.86 * r, 0.53 * r), 5, 11)
        chevrons(sten, (0.06 * r, 0.88 * r, 0.40 * r, 0.93 * r), 7)
        draw_stencil(sten, (0.08 * r, 0.47 * r, 0.30 * r, 0.51 * r), 4, 12, thick=0.13)
    if mid == "03":
        chevrons(sten, (0.53 * r, 0.875 * r, 0.95 * r, 0.905 * r), 9)
        draw_stencil(sten, (0.80 * r, 0.20 * r, 0.93 * r, 0.24 * r), 3, 21, thick=0.14)
    sten_f = sten.astype(np.float32) / 255
    sten_f *= painted
    sten_wear = smooth(n_chip + (n_chip2 - 0.5) * 0.6 + n_fine * 0.3, 0.5, 0.72)
    sten_f *= (1 - sten_wear * 0.85)
    sten_f = ndimage.gaussian_filter(sten_f, 0.6 * r / 1024)
    base = base * (1 - sten_f[..., None] * 0.62) + PAL["stencil"] * (var[..., None] * 0.9) * sten_f[..., None] * 0.62
    spec += sten_f * 0.05

    # --- grime in cavities and occlusion
    occl = np.clip(1 - s.ao, 0, 1)
    grime = np.clip(cav * 0.9 + occl * 0.8, 0, 1) * (0.65 + 0.35 * n_mid)
    base = base * (1 - grime[..., None] * 0.72) + PAL["grime"] * grime[..., None] * 0.72
    spec *= 1 - grime * 0.6

    # --- vertical grime/rust streaks running down vertical faces
    vert = smooth(1 - np.abs(up), 0.3, 0.8)
    streak = smooth(n_streak, 0.62, 0.88) * vert * smooth(n_macro + (n_mid - 0.5) * 0.5, 0.45, 0.75)
    streak_col = PAL["rust_dark"] * 0.6 + PAL["grime"] * 0.4
    base = base * (1 - streak[..., None] * 0.4) + streak_col * streak[..., None] * 0.4
    spec *= 1 - streak * 0.5

    # --- rust: blooms where paint is old, in creases and low on the mount
    zlo = bounds["lo"][2]
    zn = F((p[:, 2] - zlo) / (bounds["hi"][2] - zlo))
    rust_amt = (n_rust - 0.5) * 1.5 + cav * 0.55 + (1 - zn) * 0.3 + (painted * 0.1)
    rust = smooth(rust_amt, 0.62, 0.92) * s.cover * (0.6 + 0.4 * n_fine) * np.where(painted, 1.0, 0.4)
    rust_tex = PAL["rust"] * (0.75 + 0.5 * n_fine[..., None]) * (1 - 0.3 * n_chip[..., None]) + PAL["rust_dark"] * 0.25
    base = base * (1 - rust[..., None] * 0.85) + rust_tex * rust[..., None] * 0.85
    spec = spec * (1 - rust * 0.85) + rust * 0.04

    # --- dust settling on up-facing surfaces
    dust = smooth(up, 0.45, 0.9) * (0.35 + 0.5 * n_mid) * (1 - cav * 0.3)
    base = base * (1 - dust[..., None] * 0.28) + PAL["dust"] * dust[..., None] * 0.28
    spec *= 1 - dust * 0.4

    # --- edge wear: chipped paint and polished steel on ridges and corners
    edge = np.clip(convex * 1.2 + gedge * s.ao * 0.45, 0, 1)
    chip = smooth(edge * 1.1 + (n_chip - 0.5) * 1.1 + (n_chip2 - 0.5) * 0.7, 0.66, 0.76)
    chip = np.where(painted, chip, chip * 0.8)
    # paint chips show a dark primer ring before bare metal
    primer = smooth(edge * 1.1 + (n_chip - 0.5) * 1.1 + (n_chip2 - 0.5) * 0.7, 0.56, 0.64) * painted * (1 - chip)
    base = base * (1 - primer[..., None] * 0.5) + PAL["grime"] * primer[..., None] * 0.5
    bare = PAL["steel_bare"] * (0.75 + 0.35 * n_fine[..., None])
    chip_k = np.where(painted, 1.0, 0.45)[..., None]
    base = base * (1 - chip[..., None] * chip_k) + bare * chip[..., None] * chip_k
    spec = spec * (1 - chip) + chip * 0.85

    # --- worn edgings: some edges and plate rims rubbed through to bright metal,
    # in patches, so the wear reads at a distance without outlining everything
    n_wear = F(fbm3(p, 4.0, 3, seed=21))
    patch = smooth(n_wear + (n_mid - 0.5) * 0.3, 0.55, 0.66)
    k = r / 1024.0
    border = np.zeros((r, r), np.float32)
    if mid == "01":
        rim = ndimage.distance_transform_edt(s.cover)
        border = (1 - smooth(rim, 1.0 * k, 3.5 * k)) * s.mask("shield")
    plates = (painted | machined).astype(np.float32)
    ridges = smooth(convex, 0.45, 0.85) * plates
    heavy = np.clip(ridges + border, 0, 1) * patch
    worn = smooth(heavy + (n_chip2 - 0.5) * 0.6 + (n_fine - 0.5) * 0.3, 0.5, 0.68) * s.cover
    scuff = smooth(heavy + (n_chip2 - 0.5) * 0.5, 0.35, 0.48) * (1 - worn) * painted
    base = base * (1 - scuff[..., None] * 0.35) + PAL["grime"] * scuff[..., None] * 0.35
    shine = PAL["steel_bare"] * (1.05 + 0.25 * n_fine[..., None])
    base = base * (1 - worn[..., None]) + shine * worn[..., None]
    spec = spec * (1 - worn) + worn * 0.9

    # --- battle damage: bullet dings on the armour
    if mid in ("01", "03"):
        dn, dspec = dings(s, painted, 16 if mid == "01" else 10, seed=int(mid) * 13)
        base = base * (1 - dn[..., 3:4]) + dn[..., :3]
        spec = np.maximum(spec, dspec)

    # --- scratches across exposed faces
    sc = scratches(s, int(900 * (r / 1024) ** 2 * 3.0), 34, seed=int(mid) * 7, angle_bias=0.25, spread=0.6)
    sc *= (1 - cav) * s.cover * smooth(n_mid, 0.3, 0.7) * (1 - 0.55 * smooth(up, 0.5, 0.9))
    base = base * (1 - sc[..., None] * 0.55) + bare * sc[..., None] * 0.55
    spec = spec + sc * 0.35

    # --- cables, hoses, polished fittings and bolt heads
    base, spec = paint_accents(s, mid, base, spec, cav, convex, n_fine, n_chip2, n_macro)

    glow = np.zeros((r, r, 3), np.float32)

    # --- part specific
    if mid == "01":
        mz = np.array([-13.6, -45.5, 59.3], np.float32)
        d = F(np.linalg.norm(p - mz, axis=1))
        barrelish = s.mask("barrel") | s.mask("gun")
        heat = smooth(16 - d, 0, 12) * barrelish
        # tempering bands: straw -> bronze -> purple -> blue
        t = np.clip(heat, 0, 1)
        temper = np.stack([
            0.45 + 0.25 * np.cos(t * 6.0 + 0.3),
            0.33 + 0.18 * np.cos(t * 6.0 + 1.4),
            0.28 + 0.22 * np.cos(t * 6.0 + 2.6),
        ], -1)
        base = base * (1 - t[..., None] * 0.55) + temper * base.mean(-1, keepdims=True) * 2.2 * t[..., None] * 0.55
        soot = smooth(7 - d, 0, 5) * (0.7 + 0.3 * n_fine)
        base = base * (1 - soot[..., None] * 0.85) + PAL["soot"] * soot[..., None] * 0.85
        spec = spec * (1 - soot * 0.8)
        # oily gun body: darker in the action, copper hoses picked out by curvature
        gunm = s.mask("gun")
        oil = smooth(n_mid + cav * 0.5, 0.6, 0.85) * gunm
        base *= (1 - oil[..., None] * 0.25)
        spec = spec + oil * 0.15
    if mid == "02":
        # drum: brass feed lips on the rim slots, hub darker
        rim = s.mask("drumrim")
        brass_hit = smooth(convex * 2.0 + (n_chip - 0.5) * 0.6, 0.5, 0.8) * rim
        base = base * (1 - brass_hit[..., None]) + PAL["brass"] * 0.8 * brass_hit[..., None]
        spec = spec * (1 - brass_hit) + brass_hit * 0.75
    if mid == "03":
        deck = s.mask("deck")
        # boot-polished wear on the deck where the gunner stands
        dd = F(np.hypot(p[:, 1] - 22.5, p[:, 0] * 0.8))
        polish = smooth(12 - dd, 0, 10) * deck * (0.5 + 0.5 * n_fine)
        base = base * (1 - polish[..., None] * 0.25) + PAL["steel_bare"] * 0.75 * polish[..., None] * 0.25
        spec = spec + polish * 0.15
        # grated tread pattern on the deck
        tread = (np.sin(F(p[:, 0]) * 2.2) * np.sin(F(p[:, 1]) * 2.2) > 0.55).astype(np.float32) * deck
        tread = ndimage.gaussian_filter(tread, 0.6)
        base *= (1 - tread[..., None] * 0.25)
        spec += tread * 0.15

    if mid == "04":
        base, spec, glow = paint_rounds(s, p, F, n_fine, n_chip)

    # --- lights
    if mid == "03":
        glow += vent_glow(s, curv)
    if mid == "01":
        glow += sight_glow(s)

    base = np.clip(base, 0, 1)
    spec = np.clip(spec, 0, 1)
    # specular colour: metals tint it, enamel stays neutral-warm
    spec_rgb = np.stack([spec, spec * 0.97, spec * 0.92], -1)
    # brass tints its own highlights; enamel and rust are excluded by their low specular
    brassy = np.clip((base[..., 0] - base[..., 2]) * 3, 0, 1) * smooth(spec, 0.5, 0.7)
    spec_rgb = spec_rgb * (1 - brassy[..., None] * 0.5) + (spec[..., None] * PAL["brass"] * 1.6) * brassy[..., None] * 0.5
    spec_rgb = np.clip(spec_rgb, 0, 1)
    return s, base, spec_rgb, np.clip(glow, 0, 1)


def paint_accents(s, mid, base, spec, cav, convex, n_fine, n_chip2, n_macro):
    """Lay the detail layers over the weathered surface."""
    occl = np.clip(1 - s.ao, 0, 1)
    shade = (1 - occl[..., None] * 0.55) * (1 - cav[..., None] * 0.45)
    weave = None
    for m, tone, sp, kind in details.accent_layers(s, mid):
        m = np.clip(m, 0, 1)[..., None]
        if kind == "bolt":
            # heads alternate brass and steel by region, rims catch grime
            col = np.where((n_macro > 0.5)[..., None], details.TONES["brass"], details.TONES["chrome"] * 0.82)
            col = col * (0.85 + 0.3 * n_fine[..., None])
        elif kind == "hose":
            if weave is None:
                weave = details.braid(s)
            col = details.TONES[tone] * (0.8 + 0.45 * weave[..., None]) * (1 + convex[..., None] * 1.2)
            scuffs = smooth(n_chip2, 0.62, 0.8)[..., None]
            col = col * (1 - scuffs * 0.5) + details.TONES["rubber_band"] * 1.4 * scuffs * 0.5
        elif kind == "sleeve":
            # armoured sleeve: rubber between steel ribs
            ribs = smooth(convex, 0.15, 0.5)[..., None]
            col = details.TONES[tone] * (0.9 + 0.2 * n_fine[..., None])
            col = col * (1 - ribs) + PAL["gunmetal"] * 1.15 * ribs
        elif kind == "wire":
            col = details.TONES[tone] * (0.8 + 0.35 * n_fine[..., None]) * (1 + convex[..., None] * 0.8)
        else:
            col = details.TONES[tone] * (0.85 + 0.25 * n_fine[..., None]) * (1 + convex[..., None] * 0.5)
        col = col * shade
        base = base * (1 - m) + col * m
        if kind == "sleeve":
            spec = spec * (1 - m[..., 0]) + (sp + smooth(convex, 0.15, 0.5) * 0.45) * m[..., 0]
        else:
            spec = spec * (1 - m[..., 0]) + sp * (1 - occl * 0.4) * m[..., 0]
    return base, spec


def dings(s, mask, count, seed):
    """Small bullet strikes: bright gouged centre, dark scorched ring, paint cracks."""
    r = s.res
    sup = 3
    big = r * sup
    rng = np.random.default_rng(seed)
    centre = np.zeros((big, big), np.uint8)
    ring = np.zeros((big, big), np.uint8)
    ys, xs = np.nonzero(ndimage.binary_erosion(mask, iterations=8))
    if len(xs) == 0:
        return np.zeros((r, r, 4), np.float32), np.zeros((r, r), np.float32)
    for _ in range(count):
        i = rng.integers(len(xs))
        cx, cy = xs[i] * sup, ys[i] * sup
        rad = rng.uniform(1.6, 4.0) * sup * r / 1024
        cv2.circle(ring, (int(cx), int(cy)), int(rad * 2.4), 255, -1, cv2.LINE_AA)
        for _k in range(rng.integers(2, 5)):
            a = rng.uniform(0, 2 * math.pi)
            ln = rad * rng.uniform(2.5, 4.5)
            cv2.line(ring, (int(cx), int(cy)), (int(cx + math.cos(a) * ln), int(cy + math.sin(a) * ln)), 200, max(1, sup // 2), cv2.LINE_AA)
        cv2.ellipse(centre, (int(cx), int(cy)), (int(rad), int(rad * rng.uniform(0.6, 1.0))), rng.uniform(0, 180), 0, 360, 255, -1, cv2.LINE_AA)
    c = cv2.resize(centre, (r, r), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    g = cv2.resize(ring, (r, r), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    g = np.clip(g - c, 0, 1)
    out = np.zeros((r, r, 4), np.float32)
    col = PAL["grime"] * g[..., None] * 0.45 + PAL["steel_bare"] * 1.1 * c[..., None]
    out[..., :3] = col
    out[..., 3] = np.clip(g * 0.45 + c, 0, 1)
    return out, c * 0.95


def vent_glow(s, curv):
    """Amber glow inside the base housing's vent ladder slots."""
    r = s.res
    g = np.zeros((r, r, 3), np.float32)
    housing = s.mask("housing")
    # the ladder vents are the recessed slots in the housing's centre-left
    x0, x1, y0, y1 = int(0.63 * r), int(0.72 * r), int(0.28 * r), int(0.44 * r)
    roi = np.zeros((r, r), bool)
    roi[y0:y1, x0:x1] = True
    ao_hp = s.ao - ndimage.gaussian_filter(s.ao, 3 * r / 1024)
    slot = (ao_hp < -0.02) & roi & housing
    slot = ndimage.binary_opening(slot, iterations=1)
    slot = ndimage.gaussian_filter(slot.astype(np.float32), 1.0)
    core = srgb((255, 132, 36))
    g += core * slot[..., None] * 0.95
    halo = ndimage.gaussian_filter(slot, 3.0) * housing
    g += srgb((200, 70, 16)) * halo[..., None] * 0.6
    return g


def sight_glow(s):
    """Red sensor lens: the round boss on the gun body's flank."""
    r = s.res
    g = np.zeros((r, r, 3), np.float32)
    # boss centre measured on the gun body island (uv ~0.762, 0.118)
    cx, cy, rad = 0.762 * r, 0.118 * r, 0.011 * r
    yy, xx = np.mgrid[0:r, 0:r].astype(np.float32)
    d = np.hypot(xx - cx, yy - cy)
    lens = smooth(rad - d, -1.0, 1.5)
    ring = smooth(rad * 2.2 - d, 0, rad * 1.2) * (1 - lens)
    g += srgb((255, 40, 18)) * lens[..., None]
    g += srgb((150, 20, 8)) * ring[..., None] * 0.35
    return g


def paint_rounds(s, p, F, n_fine, n_chip):
    """Cartridge heads behind the drum windows, placed on the normal map's rings."""
    r = s.res
    n = s.nmap
    mag = np.hypot(n[..., 0], n[..., 1])
    m8 = np.clip(mag * 255 * 2, 0, 255).astype(np.uint8)
    m8 = cv2.GaussianBlur(m8, (3, 3), 0)
    circles = cv2.HoughCircles(m8, cv2.HOUGH_GRADIENT, dp=1, minDist=r * 0.035,
                               param1=60, param2=14, minRadius=int(r * 0.016), maxRadius=int(r * 0.03))
    yy, xx = np.mgrid[0:r, 0:r].astype(np.float32)
    base = np.zeros((r, r, 3), np.float32) + PAL["gunmetal_dark"] * 0.55
    spec = np.zeros((r, r), np.float32) + 0.2
    glow = np.zeros((r, r, 3), np.float32)
    heads = np.zeros((r, r), np.float32)
    primer = np.zeros((r, r), np.float32)
    found = [] if circles is None else circles[0]
    rng = np.random.default_rng(4)
    for cx, cy, rad in found:
        d = np.hypot(xx - cx, yy - cy)
        head = smooth(rad * 1.12 - d, -0.8, 0.8)
        pr = smooth(rad * 0.42 - d, -0.6, 0.6)
        heads = np.maximum(heads, head * rng.uniform(0.85, 1.0))
        primer = np.maximum(primer, pr)
    print("rounds found", len(found))
    tarn = 0.95 + 0.35 * n_fine + 0.15 * (n_chip - 0.5)
    brass = PAL["brass"] * tarn[..., None]
    base = base * (1 - heads[..., None]) + brass * heads[..., None]
    base = base * (1 - primer[..., None]) + PAL["copper"] * 0.9 * primer[..., None]
    occl = np.clip(1 - s.ao, 0, 1)
    base *= (1 - occl[..., None] * 0.4)
    spec = spec * (1 - heads) + heads * 0.75
    hub = smooth(np.hypot(xx - r / 2, yy - r / 2) - r * 0.22, -6, 6)
    base *= (0.55 + 0.45 * hub[..., None])
    return base, spec, glow


def dilate(img, cover):
    _, (iy, ix) = ndimage.distance_transform_edt(~cover, return_indices=True)
    return img[iy, ix]


def save(arr, path, alpha=None, quality=95):
    a = np.clip(arr * 255 + 0.5, 0, 255).astype(np.uint8)
    if alpha is not None:
        a = np.dstack([a, alpha])
        Image.fromarray(a).save(path)
    elif path.endswith(".jpg"):
        Image.fromarray(a).save(path, quality=quality, subsampling=0, optimize=True)
    else:
        Image.fromarray(a).save(path)


def drum_alpha(s):
    """Window cut-outs, redrawn as clean polygons from the drum's window outline."""
    r = s.res
    src = np.asarray(Image.open(os.path.join(CFG["drop"], s.name + "_d.tga")).convert("RGBA").resize((r, r), Image.NEAREST))[..., 3]
    holes = (src < 128).astype(np.uint8)
    cnts, _ = cv2.findContours(holes, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    big = np.full((r * 4, r * 4), 255, np.uint8)
    for c in cnts:
        if cv2.contourArea(c) < 4:
            continue
        approx = cv2.approxPolyDP(c, 1.0, True)
        cv2.fillPoly(big, [approx * 4], 0, cv2.LINE_AA)
    a = cv2.resize(big, (r, r), interpolation=cv2.INTER_AREA)
    print("drum windows", len(cnts))
    return a


def export():
    """Copy the masters into the pak0 tree under openQ4's own names."""
    os.makedirs(SHIP, exist_ok=True)
    for mid in RES:
        src = os.path.join(CFG["out"], "common_turret_strogg" + mid)
        dst = os.path.join(SHIP, "turret_strogg" + mid)
        for suffix in ("_d.jpg", "_d.tga", "_s.jpg", "_glow.jpg"):
            if os.path.exists(src + suffix):
                shutil.copyfile(src + suffix, dst + suffix)
                print("exported", os.path.relpath(dst + suffix, REPO))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--awakening", required=True, help="the Awakening's q4xbase directory")
    ap.add_argument("--work", default=os.path.join(REPO, ".tmp", "awakening_turret"))
    ap.add_argument("--only", nargs="*", default=list(RES), help="materials to paint (01 02 03 04)")
    ap.add_argument("--export", action="store_true", help="copy the masters into content/baseoq4/pak0")
    args = ap.parse_args()
    configure(args.awakening, args.work)
    os.makedirs(CFG["out"], exist_ok=True)
    bounds = json.load(open(os.path.join(CFG["bake"], "bounds.json")))
    for mid in args.only:
        s, base, spec, glow = paint(mid, bounds)
        cov = s.cover
        base, spec, glow = dilate(base, cov), dilate(spec, cov), dilate(glow, cov)
        stem = os.path.join(CFG["out"], s.name)
        if mid == "02":
            save(base, stem + "_d.tga", alpha=drum_alpha(s))
        else:
            save(base, stem + "_d.jpg")
        save(spec, stem + "_s.jpg")
        if glow.max() > 0.01:
            save(glow, stem + "_glow.jpg")
        print("painted", mid)
    if args.export:
        export()


if __name__ == "__main__":
    main()
