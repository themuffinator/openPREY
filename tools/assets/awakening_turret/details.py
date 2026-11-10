"""Panel tones, cables, polished parts and bolts for the turret skin painter.

Everything here works in texture space on top of the bakes. Panel boundaries
come from a watershed over the normal map's creases, so a tone change always
falls on a real seam; cables and polished parts are located from the
expansion's normal map (its integrated height field) inside hand-placed UV
boxes, seeds and circles measured on the model.
"""
from __future__ import annotations

import math

import cv2
import numpy as np
from scipy import ndimage


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def srgb(c):
    return np.array(c, dtype=np.float32) / 255.0


TONES = {
    "steel_light": srgb((112, 114, 111)),   # brushed cover plates
    "khaki": srgb((100, 95, 80)),           # weathered Strogg field grey
    "bone": srgb((128, 120, 101)),          # pale armour blocks
    "chrome": srgb((172, 172, 167)),        # machined, polished
    "rubber": srgb((27, 27, 28)),
    "hose": srgb((40, 39, 38)),
    "tag_amber": srgb((196, 150, 44)),
    "rubber_band": srgb((52, 48, 44)),
    "wire_orange": srgb((178, 84, 26)),
    "wire_red": srgb((132, 36, 26)),
    "brass": srgb((176, 132, 62)),
    "oxblood": srgb((72, 42, 34)),
}


# ---------------------------------------------------------------- fields
def height_field(s):
    """Height integrated from the normal map (Poisson, FFT); cached per surface."""
    if getattr(s, "_height", None) is not None:
        return s._height
    n = s.nmap
    nz = np.clip(n[..., 2], 0.3, 1.0)
    gx = -n[..., 0] / nz
    gy = -n[..., 1] / nz          # id's +G points down the image
    gx = np.where(s.cover, gx, 0)
    gy = np.where(s.cover, gy, 0)
    h, w = gx.shape
    fx = np.fft.fftfreq(w)[None, :]
    fy = np.fft.fftfreq(h)[:, None]
    den = (2j * np.pi * fx) ** 2 + (2j * np.pi * fy) ** 2
    den[0, 0] = 1
    hh = ((2j * np.pi * fx) * np.fft.fft2(gx) + (2j * np.pi * fy) * np.fft.fft2(gy)) / den
    hh[0, 0] = 0
    s._height = np.real(np.fft.ifft2(hh)).astype(np.float32) * (1024.0 / s.res)
    return s._height


def high_pass(s, sigma):
    h = height_field(s)
    k = s.res / 1024.0
    return h - ndimage.gaussian_filter(h, sigma * k)


def crease_map(s):
    n = s.nmap
    nz = np.clip(n[..., 2], 0.25, 1)
    div = np.gradient(n[..., 0] / nz, axis=1) + np.gradient(n[..., 1] / nz, axis=0)
    div = ndimage.gaussian_filter(div, 0.8)
    tilt = np.hypot(n[..., 0], n[..., 1])
    ao_hp = s.ao - ndimage.gaussian_filter(s.ao, 5 * s.res / 1024)
    crease = np.clip(np.abs(div) * 3 + np.clip(-ao_hp * 6, 0, 1) + np.clip((tilt - 0.35) * 2, 0, 1), 0, 1)
    crease[~s.cover] = 1
    return crease


# ---------------------------------------------------------------- masks
def box(s, u0, v0, u1, v1):
    r = s.res
    m = np.zeros((r, r), bool)
    m[int(v0 * r):int(v1 * r), int(u0 * r):int(u1 * r)] = True
    return m


def ring(s, cu, cv, r_in, r_out, soft=0.8):
    r = s.res
    yy, xx = np.mgrid[0:r, 0:r].astype(np.float32)
    d = np.hypot(xx - cu * r, yy - cv * r)
    return smooth(d, r_in * r - soft, r_in * r + soft) * (1 - smooth(d, r_out * r - soft, r_out * r + soft))


def polyline(s, pts, width_px):
    r = s.res
    sup = 4
    img = np.zeros((r * sup, r * sup), np.uint8)
    p = np.array([[u * r * sup, v * r * sup] for u, v in pts], np.int32)
    cv2.polylines(img, [p], False, 255, int(width_px * sup), cv2.LINE_AA)
    return cv2.resize(img, (r, r), interpolation=cv2.INTER_AREA).astype(np.float32) / 255


def seeded_tubes(s, region, seeds, core=0.7, grow=4):
    """Raised tubes in the height field, keeping only the ones under a seed."""
    r = s.res
    hp = high_pass(s, 6)
    cores = (hp > core) & region & s.cover
    lab, _ = ndimage.label(cores)
    keep = np.zeros_like(cores)
    for u, v in seeds:
        x, y = int(u * r), int(v * r)
        ids = set(lab[y - 3:y + 4, x - 3:x + 4].ravel().tolist()) - {0}
        for i in ids:
            keep |= lab == i
    grown = ndimage.binary_dilation(keep, iterations=grow) & (hp > -0.1) & s.cover
    grown = ndimage.binary_closing(grown, iterations=2)
    return ndimage.gaussian_filter(grown.astype(np.float32), 0.7)


def raised(s, region, thr, sigma=6, open_it=1):
    hp = high_pass(s, sigma)
    m = (hp > thr) & region & s.cover
    if open_it:
        m = ndimage.binary_opening(m, iterations=open_it)
    return m


def watershed(s, seeds, region):
    """Label each pixel of region with the seed group it floods from along low creases."""
    r = s.res
    img = cv2.cvtColor((crease_map(s) * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    markers = np.zeros((r, r), np.int32)
    markers[~region] = 1
    names = list(seeds)
    for i, name in enumerate(names):
        for u, v in seeds[name]:
            cv2.circle(markers, (int(u * r), int(v * r)), max(2, int(3 * r / 1024)), i + 2, -1)
    cv2.watershed(img, markers)
    # watershed lines (-1) take the label of a neighbour
    lines = markers == -1
    if lines.any():
        _, (iy, ix) = ndimage.distance_transform_edt(lines, return_indices=True)
        markers = markers[iy, ix]
    return {name: (markers == i + 2) & region for i, name in enumerate(names)}


BOLTS = {
    "01": [(0.110, 0.175), (0.145, 0.173), (0.408, 0.165), (0.424, 0.090), (0.211, 0.038),
           (0.241, 0.037), (0.268, 0.036), (0.788, 0.064), (0.812, 0.063), (0.836, 0.062),
           (0.581, 0.221)],
    "03": [(0.587, 0.285), (0.568, 0.447), (0.655, 0.456), (0.664, 0.298), (0.706, 0.598),
           (0.798, 0.533), (0.513, 0.951), (0.676, 0.951), (0.760, 0.945), (0.926, 0.945)],
}


def bolt_heads(s, mid, rad=0.0055):
    """Bolt heads measured on the normal map (automatic detection also caught corners)."""
    out = np.zeros((s.res, s.res), np.float32)
    for cu, cv in BOLTS.get(mid, []):
        out = np.maximum(out, ring(s, cu, cv, -1, rad))
    return out


COLUMN_BANDS = [(0.688, 0.702), (0.798, 0.812), (0.907, 0.919)]


def column_rings(s, mask):
    """The column's three machined bands, measured on its height field."""
    out = np.zeros((s.res, s.res), bool)
    for v0, v1 in COLUMN_BANDS:
        out |= box(s, 0, v0, 1, v1)
    return ndimage.gaussian_filter((out & mask).astype(np.float32), 0.7)


def braid(s, scale=0.0045):
    """A fine crossing weave for hose sheaths."""
    r = s.res
    yy, xx = np.mgrid[0:r, 0:r].astype(np.float32) / r
    a = np.sin((xx + yy) / scale * math.pi)
    b = np.sin((xx - yy) / scale * math.pi)
    return np.clip(0.5 + 0.25 * (a + b) + 0.5 * (a * b), 0, 1)


def brushed(s, n_fine, angle=0.0):
    r = s.res
    rng = np.random.default_rng(7)
    streaks = rng.random((r, max(4, r // 32))).astype(np.float32)
    streaks = cv2.resize(streaks, (r, r), interpolation=cv2.INTER_LINEAR)
    if angle:
        streaks = streaks.T
    return 0.9 + 0.14 * streaks + 0.06 * (n_fine - 0.5)


# ---------------------------------------------------------------- per material layouts
def tone_regions(s, mid):
    """Panels that take a different finish: {tone: (mask, painted, spec)}."""
    out = {}
    if mid == "01":
        gun = s.mask("gun")
        regions = watershed(s, {
            "steel_light": [(0.50, 0.035), (0.62, 0.04), (0.85, 0.12), (0.80, 0.06), (0.92, 0.12)],
            "oxblood": [(0.30, 0.245), (0.18, 0.25), (0.12, 0.08), (0.36, 0.26)],
            "base": [(0.55, 0.17), (0.45, 0.205), (0.25, 0.14), (0.05, 0.12), (0.68, 0.19),
                     (0.60, 0.10), (0.30, 0.10), (0.75, 0.18), (0.40, 0.08)],
        }, gun)
        out["steel_light"] = (regions["steel_light"], False, 0.5)
        out["oxblood"] = (regions["oxblood"], True, 0.22)
        shield = s.mask("shield")
        lower = shield & ~box(s, 0, 0, 1, 0.691)
        out["khaki"] = (lower, True, 0.2)
        out["chrome"] = (s.island == 1, False, 0.85)            # the hinge piston under the gun
    if mid == "02":
        out["oxblood"] = (s.mask("hub") & (s.island == 0), True, 0.22)
        disc = (ring(s, 0.281, 0.262, -1, 0.085) + ring(s, 0.299, 0.751, -1, 0.085)) > 0.5
        out["steel_light"] = (disc & s.mask("drum"), False, 0.5)
    if mid == "03":
        band = s.mask("base") & box(s, 0.49, 0.76, 0.99, 0.99)
        regions = watershed(s, {
            "bone": [(0.60, 0.85), (0.60, 0.90), (0.845, 0.85), (0.845, 0.90)],
            "oxblood": [(0.72, 0.87), (0.52, 0.87), (0.955, 0.87), (0.72, 0.80), (0.60, 0.79),
                        (0.85, 0.79), (0.72, 0.95), (0.60, 0.95), (0.85, 0.95)],
        }, band)
        out["bone"] = (regions["bone"], True, 0.22)
    return out


def accent_layers(s, mid):
    """Finishes painted over the weathered surface: [(mask float, tone, spec, kind)]."""
    layers = []
    if mid == "01":
        hoses = seeded_tubes(s, box(s, 0.195, 0.078, 0.395, 0.135),
                             [(0.233, 0.107), (0.319, 0.107), (0.3658, 0.1186)])
        layers.append((hoses, "hose", 0.32, "hose"))
        # an ID band on each line just behind its ferrule, then the brass ferrule
        tags = ("wire_orange", "tag_amber", "wire_red")
        for (cu, cv), tag in zip(((0.2232, 0.0893), (0.3267, 0.0961), (0.3785, 0.0932)), tags):
            layers.append((ring(s, cu, cv, 0.0095, 0.0145) * hoses, tag, 0.35, "wire"))
            layers.append((ring(s, cu, cv, 0.0035, 0.0085), "brass", 0.75, "metal"))
        sleeve = ((s.island == 4) | (s.island == 10)) & box(s, 0.30, 0.30, 0.445, 0.43)
        layers.append((ndimage.gaussian_filter(sleeve.astype(np.float32), 0.7), "rubber", 0.22, "sleeve"))
        layers.append((ring(s, 0.479, 0.363, 0.016, 0.024), "chrome", 0.85, "metal"))
        layers.append((ring(s, 0.479, 0.363, -1, 0.006), "brass", 0.7, "metal"))
        layers.append((polyline(s, [(0.630, 0.031), (0.658, 0.031)], 3.2), "chrome", 0.85, "metal"))
        layers.append((ring(s, 0.6658, 0.0309, -1, 0.0075), "brass", 0.75, "metal"))
        layers.append((polyline(s, [(0.6996, 0.0420), (0.7146, 0.0448), (0.7276, 0.0488),
                                    (0.7390, 0.0524), (0.7472, 0.0537)], 4.0), "wire_orange", 0.35, "wire"))
        layers.append((bolt_heads(s, mid), "bolt", 0.8, "bolt"))
    if mid == "02":
        layers.append((ring(s, 0.281, 0.262, 0.062, 0.074) + ring(s, 0.299, 0.751, 0.062, 0.074), "chrome", 0.85, "metal"))
        layers.append((ring(s, 0.464, 0.482, -1, 0.03), "chrome", 0.85, "metal"))
    if mid == "03":
        column = s.mask("column")
        layers.append((column_rings(s, column), "chrome", 0.85, "metal"))
        for cu, cv, rad in ((0.343, 0.170, 0.07), (0.083, 0.515, 0.065)):
            layers.append((ring(s, cu, cv, rad * 0.62, rad * 0.86), "chrome", 0.85, "metal"))
            layers.append((ring(s, cu, cv, -1, rad * 0.28), "brass", 0.7, "metal"))
        wires = raised(s, box(s, 0.08, 0.22, 0.17, 0.31), 0.8, sigma=6, open_it=1)
        lab, n = ndimage.label(wires)
        for i in range(1, n + 1):
            comp = ndimage.gaussian_filter((lab == i).astype(np.float32), 0.7)
            layers.append((comp, "wire_orange" if i % 2 else "wire_red", 0.35, "wire"))
        layers.append((bolt_heads(s, mid, 0.006), "bolt", 0.8, "bolt"))
    return layers
