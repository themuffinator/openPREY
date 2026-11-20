"""Recover a retail loading screen's camera from engine probes.

Every retail Prey loading screen is a 90-degree 4:3 in-game view stretched to a
square. A probe renders the map at a candidate camera with linear depth; RootSIFT
features (after CLAHE) are matched against the retail art, the matched probe
pixels are lifted to world points through the depth, and PnP with RANSAC solves
the retail camera. Probe, match and solve repeat from the new pose until it
settles. Candidates: each player start at its own heading first (retail's
single-player shots are start views), then cube faces (six square 90-degree
views) from the starts and a spread of map entities.
"""
from __future__ import annotations

import json
import math
import multiprocessing
import os

import cv2
import numpy as np

import harness

# a match lifted from this far away (distant sky geometry) cannot fix a position
MAX_DEPTH = float(os.environ.get("OPENPREY_LEVELSHOT_MAX_DEPTH", "1e9"))
SEED_CLASSES = ("info_player_start", "info_player_deathmatch", "info_player_teleport", "info_player_spawn")
SKIP_PREFIX = ("light", "speaker", "trigger", "func_static", "worldspawn", "info_portalsky", "path_", "target_")


def angles_to_axis(pitch, yaw, roll):
    """idAngles::ToMat3: rows forward, left, up."""
    sp, cp = math.sin(math.radians(pitch)), math.cos(math.radians(pitch))
    sy, cy = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    sr, cr = math.sin(math.radians(roll)), math.cos(math.radians(roll))
    fwd = np.array([cp * cy, cp * sy, -sp])
    left = np.array([sr * sp * cy + cr * -sy, sr * sp * sy + cr * cy, sr * cp])
    up = np.array([cr * sp * cy + -sr * -sy, cr * sp * sy + -sr * cy, cr * cp])
    return np.stack([fwd, left, up])


def axis_to_angles(m):
    """idMat3::ToAngles."""
    sp = max(-1.0, min(1.0, m[0][2]))
    theta = -math.asin(sp)
    if math.cos(theta) > 8192 * 1.192092896e-07:
        return math.degrees(theta), math.degrees(math.atan2(m[0][1], m[0][0])) % 360.0, math.degrees(math.atan2(m[1][2], m[2][2]))
    return math.degrees(theta), math.degrees(-math.atan2(m[1][0], m[1][1])) % 360.0, 0.0


_sift = None
_clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))


def features(img_rgb):
    global _sift
    if _sift is None:
        _sift = cv2.SIFT_create(nfeatures=6000, contrastThreshold=0.01)
    g = _clahe.apply(cv2.cvtColor(np.asarray(img_rgb), cv2.COLOR_RGB2GRAY))
    kp, des = _sift.detectAndCompute(g, None)
    if des is None:
        return [], None
    des = des / (des.sum(axis=1, keepdims=True) + 1e-7)
    return kp, np.sqrt(des).astype(np.float32)


def match(desA, desB, ratio=0.8):
    if desA is None or desB is None or len(desA) < 2 or len(desB) < 2:
        return []
    return [p[0] for p in cv2.BFMatcher(cv2.NORM_L2).knnMatch(desA, desB, k=2)
            if len(p) == 2 and p[0].distance < ratio * p[1].distance]


def backproject(u, v, d, pose, w, h):
    org = np.array(pose[:3])
    ax = angles_to_axis(*pose[3:6])
    tx, ty = math.tan(math.radians(pose[6]) / 2), math.tan(math.radians(pose[7]) / 2)
    x = (u + 0.5) / w * 2 - 1
    y = 1 - (v + 0.5) / h * 2
    return org + d[:, None] * (ax[0][None] - (x * tx)[:, None] * ax[1][None] + (y * ty)[:, None] * ax[2][None])


def intrinsics(w, h, fovx=90.0):
    tx = math.tan(math.radians(fovx) / 2)
    ty = tx * h / w
    return np.array([[w / 2 / tx, 0, w / 2], [0, h / 2 / ty, h / 2], [0, 0, 1]], dtype=np.float64)


def correspondences(retail_feats, probe_img, depth, pose):
    kr, dr = retail_feats
    kp, dp = features(probe_img)
    ms = match(dr, dp)
    if len(ms) < 6:
        return None, None, len(ms)
    pr = np.array([kr[m.queryIdx].pt for m in ms])
    pp = np.array([kp[m.trainIdx].pt for m in ms])
    h, w = depth.shape
    ui = np.clip(np.round(pp[:, 0] - 0.5).astype(int), 0, w - 1)
    vi = np.clip(np.round(pp[:, 1] - 0.5).astype(int), 0, h - 1)
    d = depth[vi, ui]
    # valid, not too far, and locally stable (not on a silhouette)
    ok = (d > 0) & (d < MAX_DEPTH)
    for du, dv in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        dn = depth[np.clip(vi + dv, 0, h - 1), np.clip(ui + du, 0, w - 1)]
        ok &= (dn > 0) & (np.abs(dn - d) < 0.04 * d + 2)
    if ok.sum() < 6:
        return None, None, len(ms)
    return backproject(pp[ok, 0] - 0.5, pp[ok, 1] - 0.5, d[ok], pose, w, h), pr[ok], len(ms)


def solve(world, img_pts, w, h, fovx=90.0, reproj=4.0):
    K = intrinsics(w, h, fovx)
    ok, rvec, tvec, inl = cv2.solvePnPRansac(world.astype(np.float64), img_pts.astype(np.float64), K, None,
                                             iterationsCount=5000, reprojectionError=reproj, confidence=0.999,
                                             flags=cv2.SOLVEPNP_EPNP)
    if not ok or inl is None or len(inl) < 6:
        return None
    inl = inl[:, 0]
    rvec, tvec = cv2.solvePnPRefineLM(world[inl].astype(np.float64), img_pts[inl].astype(np.float64), K, None, rvec, tvec)
    R, _ = cv2.Rodrigues(rvec)
    C = (-R.T @ tvec).ravel()
    p, y, r = axis_to_angles(np.stack([R[2], -R[0], -R[1]]))
    proj, _ = cv2.projectPoints(world[inl].astype(np.float64), rvec, tvec, K, None)
    err = float(np.median(np.linalg.norm(proj[:, 0] - img_pts[inl], axis=1)))
    return dict(pose=(C[0], C[1], C[2], p, y, r), inliers=int(len(inl)), err=err)


def similarity(a, b):
    """Gradient-magnitude correlation of two views at low resolution: a wrong solve scores near 0."""
    def prep(im):
        g = cv2.GaussianBlur(cv2.cvtColor(np.asarray(im.resize((256, 192))), cv2.COLOR_RGB2GRAY).astype(np.float32), (0, 0), 1.5)
        m = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
        return (m - m.mean()) / (m.std() + 1e-6)
    return float((prep(a) * prep(b)).mean())


def refine(cl, name, seed, iters=7, tag="ref"):
    """Probe, match and solve from a seed until the camera settles."""
    rimg = harness.retail(name)
    rfeat = features(rimg)
    pose, best, probe_fov = tuple(seed), None, 110.0
    for it in range(iters):
        img, depth, ppose = cl.probes(f"{tag}{it}", [("p", pose)], fov=probe_fov)["p"]
        world, pts, _ = correspondences(rfeat, img, depth, ppose)
        sol = solve(world, pts, harness.W, harness.H) if world is not None else None
        if sol is None:
            break
        moved = max(abs(a - b) for a, b in zip(sol["pose"], pose))
        pose, best, probe_fov = sol["pose"], sol, 95.0
        if moved < 0.05 and it >= 2:
            break
    if best is None:
        return None
    img = cl.probes(f"{tag}F", [("p", pose)], depth=False)["p"][0]
    best["similarity"] = similarity(rimg, img)
    best["pose"] = tuple(float(v) for v in pose)
    return best


def seed_points(map_name, n=48):
    starts, others = [], []
    for e in harness.map_entities(map_name):
        cls = e.get("classname", "")
        try:
            x, y, z = (float(v) for v in e.get("origin", "").split()[:3])
        except ValueError:
            continue
        pt = (x, y, z, float(e.get("angle", "0") or 0))
        if cls in SEED_CLASSES:
            starts.append(pt)
        elif cls and not cls.startswith(SKIP_PREFIX):
            others.append(pt)
    chosen, dist = list(starts), [math.inf] * len(others)
    while len(chosen) < n and others:
        ref = chosen[-1] if chosen else others[0]
        for i, p in enumerate(others):
            dist[i] = min(dist[i], sum((p[k] - ref[k]) ** 2 for k in range(3)))
        bi = max(range(len(others)), key=dist.__getitem__)
        if dist[bi] <= 0:
            break
        chosen.append(others[bi])
    return chosen, len(starts)


_worker_retail = {}


def _score_probe(args):
    """Pool worker: PnP inliers of the retail view against one saved cube-face probe."""
    name, stem = args
    if name not in _worker_retail:
        r = harness.retail(name, (480, 360))
        _worker_retail[name] = (r, features(r))
    rimg, rfeat = _worker_retail[name]
    img, depth, pose = harness.load_probe(stem)
    if depth is None or pose is None:
        return 0
    world, pts, _ = correspondences(rfeat, img, depth, pose)
    sol = solve(world, pts, rimg.width, rimg.height, reproj=3.0) if world is not None else None
    return sol["inliers"] if sol else 0


def solve_map(slot, map_name, name=None, log=print, min_similarity=0.3, game_type="singleplayer"):
    """The retail camera of one loading screen, or None."""
    name = name or map_name
    points, nstarts = seed_points(map_name)
    with harness.Client(slot, map_name, game_type=game_type) as cl:
        for k, (x, y, z, ang) in enumerate(points[:min(nstarts, 16)]):
            sol = refine(cl, name, (x, y, z + 64.0, 0.0, ang, 0.0), tag=f"start{k}")
            if sol and sol["inliers"] > 150 and sol["err"] < 1.5 and sol["similarity"] >= min_similarity:
                log(f"{name}: start {k} inliers {sol['inliers']} err {sol['err']:.2f} sim {sol['similarity']:.2f}")
                return sol
        faces = ((0.0, 0.0), (0.0, 90.0), (0.0, 180.0), (0.0, 270.0), (-89.9, 0.0), (89.9, 0.0))
        named = [(f"c{k:02d}_{h}_{f}", (x, y, z + lift, p, yw, 0.0))
                 for k, (x, y, z, _) in enumerate(points) for h, lift in enumerate((64.0, 240.0))
                 for f, (p, yw) in enumerate(faces)]
        scored = []
        with multiprocessing.Pool(4) as pool:
            for c in range(0, len(named), 200):
                chunk, tag = named[c:c + 200], f"cube{c}"
                outdir = cl.game / "out" / tag
                outdir.mkdir(parents=True, exist_ok=True)
                cl.request("\n".join(harness.probe_line(n, tag, p, (512, 512), True, 90.0) for n, p in chunk) + "\n")
                scores = pool.map(_score_probe, [(name, str(outdir / n)) for n, _ in chunk])
                scored += [(s, n, p) for s, (n, p) in zip(scores, chunk)]
        scored.sort(key=lambda r: -r[0])
        log(f"{name}: top seeds " + ", ".join(f"{n}:{s}" for s, n, _ in scored[:5]))
        for i, (s, n, pose) in enumerate(scored[:8]):
            if s < 10:
                break
            sol = refine(cl, name, pose, tag=f"seed{i}")
            if sol and sol["err"] < 1.5 and sol["similarity"] >= min_similarity:
                log(f"{name}: seed {n} inliers {sol['inliers']} err {sol['err']:.2f} sim {sol['similarity']:.2f}")
                return sol
    log(f"{name}: no camera")
    return None


def snap(pose):
    """Retail cameras sit on clean values (a start's eye, whole degrees) within the solve's precision."""
    pose = list(pose)
    for i in range(3):
        q = round(pose[i] * 4) / 4
        if abs(pose[i] - q) < 0.08:
            pose[i] = q
    for i in range(3, 6):
        q = float(round(pose[i]))
        if abs(pose[i] - q) < 0.06:
            pose[i] = q
    return [round(v, 3) for v in pose]


if __name__ == "__main__":
    import sys
    slot = sys.argv[1]
    for m in sys.argv[2:]:
        sol = solve_map(slot, m)
        if sol:
            print(json.dumps({m: {"camera": snap(sol["pose"]), "solve": {
                "inliers": sol["inliers"], "median_px": round(sol["err"], 3), "similarity": round(sol["similarity"], 3)}}}))
