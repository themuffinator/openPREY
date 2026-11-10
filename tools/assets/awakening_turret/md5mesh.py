"""md5mesh helpers for the Awakening turret skin tools (no Blender needed).

An md5 mesh splits its vertices at UV seams, so the connected components of
its triangle graph are exactly its UV islands.
"""
from __future__ import annotations

import colorsys
import math
import re


def parse_meshes(text):
    """[(shader, uvs, tris)] for every mesh block."""
    out = []
    for m in re.finditer(r"\nmesh\s*\{(.*?)\n\}", text, re.S):
        body = m.group(1)
        shader = re.search(r'shader\s+"([^"]*)"', body).group(1)
        uvs = [(float(a), float(b)) for a, b in re.findall(r"vert\s+\d+\s+\(\s*(\S+)\s+(\S+)\s*\)", body)]
        tris = [(int(a), int(b), int(c)) for a, b, c in re.findall(r"tri\s+\d+\s+(\d+)\s+(\d+)\s+(\d+)", body)]
        out.append((shader, uvs, tris))
    return out


def components(nverts, tris):
    """Island index per vertex."""
    parent = list(range(nverts))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b, c in tris:
        for u, v in ((a, b), (b, c)):
            ru, rv = find(u), find(v)
            if ru != rv:
                parent[ru] = rv
    roots = {}
    return [roots.setdefault(find(i), len(roots)) for i in range(nverts)]


def colour(i):
    """A distinct preview colour per island index."""
    r, g, b = colorsys.hsv_to_rgb((i * 0.61803398875) % 1.0, 0.75, 0.95)
    return (r, g, b)


def _quat(x, y, z):
    # id's compressed quaternion; with w negative the standard rotation
    # q v q* gives the bind pose (id's matrices are the transpose)
    t = 1.0 - (x * x + y * y + z * z)
    return (-math.sqrt(t) if t > 0 else 0.0, x, y, z)


def _rotate(q, v):
    w, x, y, z = q
    ix = w * v[0] + y * v[2] - z * v[1]
    iy = w * v[1] + z * v[0] - x * v[2]
    iz = w * v[2] + x * v[1] - y * v[0]
    iw = -x * v[0] - y * v[1] - z * v[2]
    return (ix * w - iw * x - iy * z + iz * y,
            iy * w - iw * y - iz * x + ix * z,
            iz * w - iw * z - ix * y + iy * x)


def load_bind_pose(text):
    """(joints, meshes): joints [(name, pos, quat)], meshes [(shader, uvs, positions, tris)]."""
    jb = re.search(r"joints\s*\{(.*?)\}", text, re.S).group(1)
    joints = []
    for m in re.finditer(r'"([^"]*)"\s+(-?\d+)\s*\(\s*(\S+)\s+(\S+)\s+(\S+)\s*\)\s*\(\s*(\S+)\s+(\S+)\s+(\S+)\s*\)', jb):
        joints.append((m.group(1), tuple(map(float, m.group(3, 4, 5))), _quat(*map(float, m.group(6, 7, 8)))))
    meshes = []
    for m in re.finditer(r"\nmesh\s*\{(.*?)\n\}", text, re.S):
        body = m.group(1)
        shader = re.search(r'shader\s+"([^"]*)"', body).group(1)
        verts = [(float(a), float(b), int(c), int(d)) for a, b, c, d in
                 re.findall(r"vert\s+\d+\s+\(\s*(\S+)\s+(\S+)\s*\)\s+(\d+)\s+(\d+)", body)]
        tris = [tuple(map(int, t)) for t in re.findall(r"tri\s+\d+\s+(\d+)\s+(\d+)\s+(\d+)", body)]
        weights = [(int(j), float(b), (float(x), float(y), float(z))) for j, b, x, y, z in
                   re.findall(r"weight\s+\d+\s+(\d+)\s+(\S+)\s*\(\s*(\S+)\s+(\S+)\s+(\S+)\s*\)", body)]
        positions = []
        for _u, _v, start, count in verts:
            p = [0.0, 0.0, 0.0]
            for wi in range(start, start + count):
                j, bias, wp = weights[wi]
                r = _rotate(joints[j][2], wp)
                for k in range(3):
                    p[k] += (joints[j][1][k] + r[k]) * bias
            positions.append(tuple(p))
        meshes.append((shader, [(u, v) for u, v, _, _ in verts], positions, tris))
    return joints, meshes
