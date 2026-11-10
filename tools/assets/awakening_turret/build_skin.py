#!/usr/bin/env python3
"""Rebuild openQ4's skin for The Awakening's Strogg chaingun turret.

    python tools/assets/awakening_turret/build_skin.py --awakening <...>/q4xbase
        [--blender <blender executable>] [--preview] [--export]

1. blender_bake.py bakes ambient occlusion, object-space normals, positions
   and UV coverage per material from the expansion's model (Blender 4.x,
   Cycles).
2. paint.py paints the colour, specular and glow masters from those bakes.
3. --preview renders a turnaround with blender_preview.py for inspection.
4. --export copies the masters into content/baseoq4/pak0.

Work files go to .tmp/awakening_turret. Nothing from the expansion is written
into the repository.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
MODEL_DIR = "models/mapobjects/q4x/common_turret_strogg"
SHADER_DIR = "models/mapobjects/q4x/common_turret_strogg/common_turret_strogg"


def find_blender(explicit):
    if explicit:
        return explicit
    for candidate in ("blender", r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"):
        path = shutil.which(candidate) or (candidate if os.path.isfile(candidate) else None)
        if path:
            return path
    raise SystemExit("Blender 4.x not found; pass --blender")


def texture_sets(drop, out, painted):
    sets = {}
    for mid in ("01", "02", "03", "04"):
        name = "common_turret_strogg" + mid
        entry = {"normal": os.path.join(drop, name + "_local.tga"), "flipgreen": True}
        if painted:
            entry["diffuse"] = os.path.join(out, name + ("_d.tga" if mid == "02" else "_d.jpg"))
            entry["specular"] = os.path.join(out, name + "_s.jpg")
            if mid == "02":
                entry["alphatest"] = 0.5
            glow = os.path.join(out, name + "_glow.jpg")
            if os.path.exists(glow):
                entry["glow"] = glow
        sets[SHADER_DIR + mid] = entry
    return sets


def run(cmd):
    print(">", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--awakening", required=True, help="the Awakening's q4xbase directory")
    ap.add_argument("--blender", default="")
    ap.add_argument("--work", default=os.path.join(REPO, ".tmp", "awakening_turret"))
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--export", action="store_true")
    args = ap.parse_args()
    # Blender runs from its own directory, so every path it sees must be absolute
    args.work = os.path.abspath(args.work)
    args.awakening = os.path.abspath(args.awakening)

    drop = os.path.join(args.awakening, MODEL_DIR)
    mesh = os.path.join(drop, "common_turret_strogg.md5mesh")
    if not os.path.isfile(mesh):
        raise SystemExit(f"turret model not found: {mesh}")
    blender = find_blender(args.blender)
    os.makedirs(args.work, exist_ok=True)
    out = os.path.join(args.work, "out")

    bake_sets = os.path.join(args.work, "bake_textures.json")
    json.dump(texture_sets(drop, out, False), open(bake_sets, "w"), indent=1)
    run([blender, "-b", "--factory-startup", "--python", os.path.join(HERE, "blender_bake.py"), "--",
         "--mesh", mesh, "--tex", bake_sets, "--out", os.path.join(args.work, "bake"),
         "--res", "01=1024,02=512,03=1024,04=512", "--samples", "128"])

    paint = [sys.executable, os.path.join(HERE, "paint.py"), "--awakening", args.awakening, "--work", args.work]
    run(paint + (["--export"] if args.export else []))

    if args.preview:
        preview_sets = os.path.join(args.work, "preview_textures.json")
        json.dump(texture_sets(drop, out, True), open(preview_sets, "w"), indent=1)
        run([blender, "-b", "--factory-startup", "--python", os.path.join(HERE, "blender_preview.py"), "--",
             "--mesh", mesh, "--tex", preview_sets, "--out", os.path.join(args.work, "preview"),
             "--engine", "cycles", "--samples", "48", "--res", "720",
             "--views", "front34,back34,f2,b2,custom:270:15:2.6:-15:-12:56,custom:60:25:2.4:-6:-10:48"])


if __name__ == "__main__":
    main()
