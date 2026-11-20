#!/usr/bin/env python3
# Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
"""The light textures of openPREY's retained initializing screen.

build_retained_initialization.py writes these beside the document. Each is
drawn here from fixed seeds with numpy (value noise, fractal sums and domain
warping), so nothing comes from the retail archives and every run gives the
same pixels. They are pictures of light: the screen adds them to what lies
beneath (image-blend additive), so black is transparent and none needs alpha.

| Texture | Size | Use |
| --- | --- | --- |
| nebula_far | 2048x1024 | The nebula's broad gas, its dust lanes and faint stars |
| nebula_near | 2048x1024 | Finer bright wisps that drift against the far gas |
| glow | 256x256 | A soft point of light: halos, cores, streaks, sparks |
| plasma | 512x512 | Turbulent spiralling plasma, turned in two layers inside the ball |
| orb | 512x512 | The ball's inside: filaments wrapped on a sphere, hot at its heart |
| shell | 512x512 | The ball's bright limb and the short corona outside it |
| arc | 256x256 | One bright arc with a fading tail: a loop of plasma |
| ring | 512x512 | A thin soft circle: the flare's lens ring |
| rays | 512x512 | An uneven burst of fine rays |
"""

from __future__ import annotations

import numpy as np

TAU = 2 * np.pi


class Noise:
    """Value noise on a periodic 256x256 lattice with quintic smoothing."""

    def __init__(self, seed: int, size: int = 256):
        self.size = size
        self.lattice = np.random.Generator(np.random.PCG64(seed)).random((size, size))

    def sample(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        x0 = np.floor(x)
        y0 = np.floor(y)
        fx, fy = x - x0, y - y0
        fx = fx * fx * fx * (fx * (fx * 6 - 15) + 10)
        fy = fy * fy * fy * (fy * (fy * 6 - 15) + 10)
        ix = x0.astype(np.int64) % self.size
        iy = y0.astype(np.int64) % self.size
        jx, jy = (ix + 1) % self.size, (iy + 1) % self.size
        g = self.lattice
        top = g[iy, ix] * (1 - fx) + g[iy, jx] * fx
        bottom = g[jy, ix] * (1 - fx) + g[jy, jx] * fx
        return top * (1 - fy) + bottom * fy

    def fbm(self, x: np.ndarray, y: np.ndarray, octaves: int = 6, gain: float = 0.5) -> np.ndarray:
        total = np.zeros_like(x)
        amplitude, norm = 1.0, 0.0
        # Each octave turns and shifts, so the lattice's axes never line up.
        c, s = np.cos(0.6435), np.sin(0.6435)
        for octave in range(octaves):
            total += amplitude * self.sample(x + 17.3 * octave, y - 9.1 * octave)
            norm += amplitude
            x, y = (c * x - s * y) * 2.02, (s * x + c * y) * 2.02
            amplitude *= gain
        return total / norm


def smoothstep(a: float, b: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def ramp(value: np.ndarray, stops: list[tuple[float, tuple[float, float, float]]]) -> np.ndarray:
    """Map 0-1 values through colour stops."""
    out = np.zeros(value.shape + (3,))
    positions = [p for p, _ in stops]
    for channel in range(3):
        out[..., channel] = np.interp(value, positions, [c[channel] for _, c in stops])
    return out


def hex_colour(code: str) -> tuple[float, float, float]:
    code = code.lstrip("#")
    return tuple(int(code[i:i + 2], 16) / 255 for i in (0, 2, 4))


def to_bytes(rgb: np.ndarray) -> np.ndarray:
    """Linear 0-1 light to 8-bit, with a little ordered dither so that the
    long gentle ramps do not band."""
    h, w = rgb.shape[:2]
    bayer = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16 - 0.5
    dither = np.tile(bayer, (h // 4 + 1, w // 4 + 1))[:h, :w][..., None]
    return np.clip(np.floor(rgb * 255 + 0.5 + dither * 0.9), 0, 255).astype(np.uint8)


def polar(size: int) -> tuple[np.ndarray, np.ndarray]:
    """Radius (1 at the square's inscribed edge) and angle of each pixel centre."""
    c = (np.arange(size) + 0.5) / size * 2 - 1
    x, y = np.meshgrid(c, c)
    return np.hypot(x, y), np.arctan2(y, x)


# ------------------------------------------------------------------- sprites

def glow(size: int = 256) -> np.ndarray:
    r, _ = polar(size)
    edge = np.clip(1 - r, 0, 1)
    light = edge ** 2.4 * (0.42 + 0.58 * np.exp(-r * r * 16))
    return to_bytes(np.repeat(light[..., None], 3, axis=2))


def plasma(size: int = 512) -> np.ndarray:
    r, a = polar(size)
    noise = Noise(4006)
    # Sampling on circles keeps the shell seamless round the turn; the
    # coordinates also wind with the radius, so filaments spiral.
    twist = a + 2.1 * r
    radius = 2.6 + 3.5 * r
    x, y = np.cos(twist) * radius, np.sin(twist) * radius
    warp = noise.fbm(x * 0.8 + 11, y * 0.8 - 3, 4)
    ridge = 1 - np.abs(2 * noise.fbm(x + 3 * warp, y - 3 * warp, 6) - 1)
    strands = ridge ** 7
    shell = np.exp(-((r - 0.34) / 0.16) ** 2) + 0.55 * np.exp(-(r / 0.24) ** 2)
    fade = np.clip(1 - r, 0, 1) ** 1.5
    light = shell * fade * (0.18 + 1.5 * strands)
    colour = ramp(np.clip(light, 0, 1.2) / 1.2, [(0, (0, 0, 0)), (0.18, hex_colour("#1B3FA8")),
                                                  (0.45, hex_colour("#3C9CF0")), (0.72, hex_colour("#A4F9FE")),
                                                  (1, (1, 1, 1))])
    return to_bytes(colour * np.clip(light * 1.3, 0, 1)[..., None] ** 0.15)


ORB_R = 0.62              # the orb's disc in its textures, as a fraction of their half-width


def orb(size: int = 512) -> np.ndarray:
    """The inside of the ball: plasma filaments wrapped on a sphere, hot at
    the heart and brightening again toward the limb. It turns in the screen,
    so it is radially symmetric in all but its filaments."""
    r, a = polar(size)
    c = (np.arange(size) + 0.5) / size * 2 - 1
    x, y = np.meshgrid(c, c)
    s = np.clip(r / ORB_R, 0, 1)
    z = np.sqrt(np.clip(1 - s * s, 0, 1))
    # Project the filaments onto the sphere: they crowd toward the limb.
    depth = 0.35 + z
    px, py = x / ORB_R / depth * 2.2, y / ORB_R / depth * 2.2
    noise = Noise(6061)
    wx = noise.fbm(px * 0.9 + 5, py * 0.9 - 2, 4) - 0.5
    wy = noise.fbm(px * 0.9 - 3, py * 0.9 + 7, 4) - 0.5
    ridge = 1 - np.abs(2 * noise.fbm(px + 2.4 * wx, py + 2.4 * wy, 6) - 1)
    strands = smoothstep(0.7, 0.98, ridge) ** 1.8
    limb = (1 - z) ** 2.2
    heart = np.exp(-(s / 0.5) ** 2)
    inside = smoothstep(1.0, 0.94, s)
    light = inside * (0.1 + 0.7 * strands * (0.45 + 0.55 * z) + 0.5 * limb + 0.95 * heart)
    colour = ramp(np.clip(light, 0, 1.3) / 1.3, [(0, (0, 0, 0)), (0.2, hex_colour("#1D4FC8")),
                                                 (0.45, hex_colour("#3FA2F4")), (0.7, hex_colour("#A4F9FE")),
                                                 (1, (1, 1, 1))])
    return to_bytes(colour * np.clip(light * 1.4, 0, 1)[..., None] ** 0.35)


def shell(size: int = 512) -> np.ndarray:
    """The ball's limb: a bright edge at the disc's rim with a short corona
    outside it, fading to nothing before the texture's edge."""
    r, _ = polar(size)
    edge = r - ORB_R
    rim = np.exp(-(edge / 0.01) ** 2) * 0.7 + np.exp(-(edge / 0.03) ** 2) * 0.32
    corona = np.where(edge > 0, np.exp(-edge / 0.09) * 0.38, 0.0)
    fresnel = np.where(edge < 0, np.clip(1 - np.sqrt(np.clip(1 - (r / ORB_R) ** 2, 0, 1)), 0, 1) ** 3 * 0.5, 0.0)
    light = (rim + corona + fresnel) * np.clip((1 - r) / 0.2, 0, 1)
    colour = ramp(np.clip(light, 0, 1), [(0, hex_colour("#2F64DC")), (0.4, hex_colour("#5AB4FF")),
                                         (0.75, hex_colour("#A4F9FE")), (1, (1, 1, 1))])
    return to_bytes(colour * np.clip(light * 1.2, 0, 1)[..., None])


def ring(size: int = 512) -> np.ndarray:
    """A lens ring: a thin soft circle of light at 0.9 of the half-width."""
    r, _ = polar(size)
    light = np.exp(-((r - 0.9) / 0.012) ** 2) * 0.8 + np.exp(-((r - 0.9) / 0.045) ** 2) * 0.35
    light *= np.clip((1 - r) / 0.04, 0, 1)
    return to_bytes(np.repeat(light[..., None], 3, axis=2))


def arc(size: int = 256) -> np.ndarray:
    r, a = polar(size)
    ring = 0.8
    # The head sits at angle 0 (the texture's right); the tail trails behind
    # it against the turn, which runs toward rising angles.
    behind = np.mod(-a, TAU) / TAU
    tail = np.clip(1 - behind / 0.45, 0, 1) ** 2.2
    lead = np.exp(-(np.mod(a, TAU) / 0.05) ** 2) * (np.mod(a, TAU) < 1)
    along = np.maximum(tail, lead)
    profile = np.exp(-((r - ring) / 0.018) ** 2) + 0.3 * np.exp(-((r - ring) / 0.06) ** 2)
    head_x, head_y = ring, 0.0
    c = (np.arange(size) + 0.5) / size * 2 - 1
    gx, gy = np.meshgrid(c, c)
    head = np.exp(-((gx - head_x) ** 2 + (gy - head_y) ** 2) / 0.004)
    light = profile * along + 0.9 * head
    light *= np.clip((1 - r) / 0.08, 0, 1)
    colour = ramp(np.clip(light, 0, 1), [(0, (0, 0, 0)), (0.3, hex_colour("#3C9CF0")), (0.7, hex_colour("#A4F9FE")),
                                         (1, (1, 1, 1))])
    return to_bytes(colour * np.clip(light * 1.6, 0, 1)[..., None] ** 0.2)


def rays(size: int = 512) -> np.ndarray:
    r, a = polar(size)
    rng = np.random.Generator(np.random.PCG64(1606))
    light = np.zeros_like(r)
    for _ in range(64):
        angle = rng.random() * TAU
        width = 0.003 + 0.012 * rng.random()
        length = 0.35 + 0.65 * rng.random()
        strength = 0.25 + 0.75 * rng.random()
        offset = np.angle(np.exp(1j * (a - angle)))
        light += strength * np.exp(-(offset / width) ** 2) * np.clip(1 - r / length, 0, 1) ** 1.8
    light = light * (1 - np.exp(-(r / 0.05) ** 2)) + 0.35 * np.exp(-(r / 0.18) ** 2)
    light *= np.clip(1 - r, 0, 1)
    return to_bytes(np.repeat(np.clip(light, 0, 1)[..., None], 3, axis=2))


# -------------------------------------------------------------------- nebula
# The nebula textures are drawn over 2000x1000 dp centred on the screen, so a
# pixel's screen position in dp is (u - 0.5) * 2000, (v - 0.5) * 1000.

NEBULA_W, NEBULA_H = 2048, 1024
NEBULA_DP = (2000, 1000)


def nebula_coordinates() -> tuple[np.ndarray, np.ndarray]:
    u = (np.arange(NEBULA_W) + 0.5) / NEBULA_W
    v = (np.arange(NEBULA_H) + 0.5) / NEBULA_H
    uu, vv = np.meshgrid(u, v)
    return (uu - 0.5) * NEBULA_DP[0], (vv - 0.5) * NEBULA_DP[1]


def masses(x: np.ndarray, y: np.ndarray, clouds: list[tuple]) -> np.ndarray:
    """A composition field: anisotropic Gaussian clouds (x, y, rx, ry, turn, weight)."""
    field = np.zeros_like(x)
    for cx, cy, rx, ry, turn, weight in clouds:
        c, s = np.cos(np.radians(turn)), np.sin(np.radians(turn))
        dx, dy = x - cx, y - cy
        u, v = (c * dx + s * dy) / rx, (-s * dx + c * dy) / ry
        field += weight * np.exp(-(u * u + v * v))
    return field


# Where the gas gathers: a violet-blue mass to the upper left, a teal one to
# the right, a fainter bridge between them above the wordmark, and wisps low
# on either side. The middle of the lower half stays dark for the energy and
# the status line.
CLOUDS = [(-560, -190, 430, 230, -24, 1.0), (-860, 120, 300, 170, 35, 0.55),
          (600, -70, 400, 210, 18, 0.95), (880, -330, 300, 160, -12, 0.55),
          (40, -350, 520, 100, 4, 0.3), (-260, 330, 360, 90, -10, 0.28),
          (420, 300, 330, 90, 12, 0.3)]
WISP_CLOUDS = [(-520, -230, 380, 190, -30, 1.0), (560, -110, 380, 190, 22, 1.0),
               (110, -330, 420, 110, 0, 0.6), (-820, 180, 260, 140, 40, 0.5), (860, 160, 240, 120, -20, 0.45)]


def blur(field: np.ndarray, sigma: float) -> np.ndarray:
    """A Gaussian blur of `sigma` pixels, through the Fourier transform."""
    h, w = field.shape
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.rfftfreq(w)[None, :]
    kernel = np.exp(-2 * (np.pi * sigma) ** 2 * (fx * fx + fy * fy))
    return np.fft.irfft2(np.fft.rfft2(field) * kernel, s=field.shape)


def billows(noise: Noise, x: np.ndarray, y: np.ndarray, octaves: int) -> np.ndarray:
    """Turbulence: a sum of folded octaves, rounded like rolling gas."""
    total = np.zeros_like(x)
    amplitude, norm = 1.0, 0.0
    c, s = np.cos(0.5236), np.sin(0.5236)
    for octave in range(octaves):
        total += amplitude * np.abs(2 * noise.sample(x + 31.7 * octave, y + 5.3 * octave) - 1)
        norm += amplitude
        x, y = (c * x - s * y) * 2.03, (s * x + c * y) * 2.03
        amplitude *= 0.52
    return total / norm


def rim_fade(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """1 inside, falling to 0 at the texture's rim, so it never shows an edge."""
    edge = np.maximum((x / (NEBULA_DP[0] / 2)) ** 2, (y / (NEBULA_DP[1] / 2)) ** 2)
    return smoothstep(1.0, 0.55, edge)


def nebula_far() -> np.ndarray:
    x, y = nebula_coordinates()
    noise = Noise(2006)
    px, py = x / 300, y / 300
    wx = noise.fbm(px * 0.7 + 3.1, py * 0.7 - 1.7, 5) - 0.5
    wy = noise.fbm(px * 0.7 - 6.2, py * 0.7 + 4.4, 5) - 0.5
    gas = billows(noise, px + 1.5 * wx, py + 1.5 * wy, 7)
    soft = noise.fbm(px * 0.55 + 2.4 * wx, py * 0.55 + 2.4 * wy, 5)
    shape = masses(x, y, CLOUDS)
    # Rolling clouds inside the composition, brightest where both the
    # large-scale field and the billows agree.
    density = shape * (0.35 + 0.9 * smoothstep(0.25, 0.75, soft)) * (0.45 + 0.8 * smoothstep(0.18, 0.62, gas))
    # Dust: thin dark lanes where a ridged field peaks, strongest in the gas.
    lane_field = 1 - np.abs(2 * Noise(77).fbm(px * 1.4 + 2.2 * wx, py * 1.4 + 2.2 * wy, 6) - 1)
    lanes = smoothstep(0.8, 0.97, lane_field)
    density *= 1 - 0.72 * lanes * smoothstep(0.15, 0.6, shape)
    # Light scattered through the gas: a wide soft glow under the detail.
    scatter = blur(density, 26) * 0.9 + blur(density, 70) * 0.6
    hue_noise = Noise(1120)
    hue = np.clip(0.5 + x / 1600 + 0.6 * (hue_noise.fbm(px * 0.5 + 4, py * 0.5 - 2, 4) - 0.5), 0, 1)
    gas_colour = ramp(hue, [(0, hex_colour("#7A2FA8")), (0.18, hex_colour("#5530B8")), (0.38, hex_colour("#2F48C8")),
                            (0.58, hex_colour("#1F6AD0")), (0.8, hex_colour("#1497B8")), (1, hex_colour("#1FB9A6"))])
    glow_colour = ramp(hue, [(0, hex_colour("#3A1E78")), (0.5, hex_colour("#1A2C8C")), (1, hex_colour("#0E5A6E"))])
    lit = smoothstep(0.55, 1.1, density)
    gas_colour = gas_colour * (1 - 0.5 * lit[..., None]) + np.array(hex_colour("#D6E2FF")) * 0.5 * lit[..., None]
    light = gas_colour * (0.3 * density ** 1.25)[..., None] + glow_colour * (0.36 * scatter)[..., None]
    # A faint scatter of unresolved stars, densest in the gas.
    rng = np.random.Generator(np.random.PCG64(3011))
    stars = np.zeros_like(x)
    count = 7000
    sx = rng.integers(0, NEBULA_W, count)
    sy = rng.integers(0, NEBULA_H, count)
    sb = rng.random(count) ** 3 * 0.3
    np.add.at(stars, (sy, sx), sb)
    stars = blur(stars, 0.6) * 2.2
    stars *= 0.3 + 0.7 * smoothstep(0.0, 0.6, shape)
    rgb = (light + stars[..., None] * np.array([0.85, 0.9, 1.0])) * rim_fade(x, y)[..., None]
    return to_bytes(rgb)


def nebula_near() -> np.ndarray:
    x, y = nebula_coordinates()
    noise = Noise(5150)
    px, py = x / 190, y / 190
    wx = noise.fbm(px * 0.8, py * 0.8, 4) - 0.5
    wy = noise.fbm(px * 0.8 - 7.1, py * 0.8 + 3.3, 4) - 0.5
    ridge = 1 - np.abs(2 * noise.fbm(px + 1.8 * wx, py + 1.8 * wy, 7) - 1)
    wisps = smoothstep(0.7, 0.97, ridge) ** 1.5
    veil = smoothstep(0.45, 0.8, noise.fbm(px * 0.5 + 9, py * 0.5 + 2, 5))
    shape = np.clip(masses(x, y, WISP_CLOUDS), 0, 1.2)
    light = (0.32 * wisps * (0.4 + 0.6 * veil) + 0.06 * blur(wisps, 12)) * shape ** 1.1
    hue = np.clip(0.5 + x / 1500 + 0.4 * (Noise(909).fbm(px * 0.5, py * 0.5, 3) - 0.5), 0, 1)
    colour = ramp(hue, [(0, hex_colour("#B08CFF")), (0.45, hex_colour("#80A8FF")), (1, hex_colour("#7FF0E0"))])
    return to_bytes(colour * (light * rim_fade(x, y))[..., None])


TEXTURES = {
    "nebula_far.png": nebula_far,
    "nebula_near.png": nebula_near,
    "glow.png": glow,
    "plasma.png": plasma,
    "orb.png": orb,
    "shell.png": shell,
    "arc.png": arc,
    "ring.png": ring,
    "rays.png": rays,
}
