"""Measured gauge artwork for the Classic presentation catalog.

The catalog renders paths directly, so clip strokes to the gauge at build time
instead of relying on document-node masks that its presentation bridge omits.
All geometry is the project's own vector reconstruction (design section 14.3).
"""
import math

from remastered_hud_status import (BACK, FILL, ST_BACK, ST_FILL, DIVIDERS,
                                    clip_polygon, fill_outline,
                                    polygon_offset, svg_polygon)

EKG_BASE = .58 * 59  # Classic catalog's source-unit baseline.


def polygon(points):
    return 'M' + 'L'.join(f'{x:.5f} {y:.5f}' for x, y in points) + 'Z'


def clipped_stroke(points, width, outline, round_joins=True):
    """Union of round-ended segments intersected with the plate silhouette.

    Each clipper is convex; the subject may include the concave gauge notch.
    One nonzero path unions overlaps before blending, avoiding bright joints.
    """
    pieces = []
    r = width / 2
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if not length:
            continue
        nx, ny = -dy * r / length, dx * r / length
        quad = [(a[0] - nx, a[1] - ny), (b[0] - nx, b[1] - ny),
                (b[0] + nx, b[1] + ny), (a[0] + nx, a[1] + ny)]
        piece = clip_polygon(outline, quad)
        if len(piece) >= 3:
            pieces.append(polygon(piece))
    for x, y in points if round_joins else ():
        disk = [(x + r * math.cos(i * math.pi / 6), y + r * math.sin(i * math.pi / 6)) for i in range(12)]
        piece = clip_polygon(outline, disk)
        if len(piece) >= 3:
            pieces.append(polygon(piece))
    return ' '.join(pieces)


def gauge_art(path, strogg=False):
    w, h = (129, 67) if strogg else (125, 59)
    box = (0, 0, w, h)
    fill = ST_FILL if strogg else FILL
    outline = svg_polygon(fill) if strogg else fill_outline()
    inset = polygon_offset(outline, 1.6) if strogg else fill_outline(3)
    bevel = path(fill + ' ' + polygon(inset), box, fill=[1, 1, 1, 1])
    bevel['fillRule'] = 'evenodd'
    # A texture's tint/alpha still belongs to the stock GUI. Keep its inner
    # face below the bright bevel, with dark cell cuts in the armor variant.
    face = [path(fill, box, fill=[.78, .78, .78, 1]), bevel]
    armor = list(face)
    for x in DIVIDERS:
        x *= w / 125
        piece = clip_polygon(outline, [(x - .75, 0), (x + .75, 0), (x + .75, h), (x - .75, h)])
        if len(piece) >= 3:
            armor.append(path(polygon(piece), box, fill=[0, 0, 0, .8]))
    if strogg:
        # Sixteen segments per short period stay within 0.22 u of the sine.
        # Its gentle joins need no extra circular subpaths at every sample.
        waves = [[(i * w / 64, 33 - amplitude * math.sin(2 * math.pi * i * w / 64 / period))
                  for i in range(65)] for period, amplitude in ((32.25, 11), (64.5, 4.7))]
    else:
        b = EKG_BASE
        beat = [(0, b), (11.2, b), (14.9, b-3.46), (18.6, b), (22.7, b), (23.7, b+2.5),
                (25.8, b-17.5), (27.7, b+6.2), (29.2, b), (37.4, b), (43.5, b-6.22),
                (44.7, b-6.22), (49.6, b), (51.8, b), (55.2, b-3), (58.6, b), (62.5, b)]
        waves = [[(x + repeat * 62.5, y) for repeat in range(2) for x, y in beat]]
    ekg = []
    core, halo = (1.6, 1.7) if strogg else (.95, 3.7)
    for wave in waves:
        # Six faint layers fall from .24 near the core to zero 3.7 u away.
        for width, alpha in [(core + 2*halo*i/6, .04) for i in range(6, 0, -1)] + [(core, 1)]:
            ekg.append(path(clipped_stroke(wave, width, outline, round_joins=not strogg), box,
                            fill=[1, 1, 1, alpha], blend='additive'))
    return face, armor, ekg


def gauge_rim(path, strogg=False):
    box = (0, 0, 129, 67) if strogg else (0, 0, 125, 59)
    outline = svg_polygon(ST_BACK) if strogg else [
        (1, 10.4), (1.35, 9.55), (2.2, 9.2), (122.8, 9.2), (123.65, 9.55), (124, 10.4),
        (124, 54.7), (123.56, 55.76), (122.5, 56.2), (91.7, 56.2), (84.9, 49.3),
        (2.2, 49.3), (1.35, 48.95), (1, 48.1)]
    paths = []
    for i in range(8):
        prev, reach = 17*i/8, 17*(i+1)/8
        alpha = (1-prev/17)**2 - (1-reach/17)**2
        paths.append(path(clipped_stroke(outline + outline[:1], 2*reach, outline), box,
                          fill=[1, 1, 1, alpha], blend='additive'))
    return paths
