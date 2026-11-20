#!/usr/bin/env python3
"""Recover, capture and stage openPREY's loading-screen recaptures.

    levelshots.py solve <slot> <map> ...       find each map's retail loading-screen camera
    levelshots.py capture <slot> [<set> ...]   five-tile captures at the cameras in poses.json
    levelshots.py stage [<set> ...]            copy captured sets into content/basepr/pak2

<slot> is a, b, c or d: each slot is its own savepath and port, so up to four
clients can run at once. Needs a staged package (.install), Python with
OpenCV, NumPy and Pillow, `unzip` on PATH, and OPENPREY_RETAIL_BASE set to the
retail install's base folder. Work files go to .tmp/levelshots/.
See docs/dev/levelshot-capture.md.
"""
import json
import sys

import capture
import pose_solve


def main(argv):
    if len(argv) < 2 or argv[1] not in ("solve", "capture", "stage"):
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "stage":
        capture.stage(argv[2:] or None)
        return 0
    slot, names = argv[2], argv[3:]
    if cmd == "solve":
        for m in names:
            sol = pose_solve.solve_map(slot, m)
            if sol:
                print(json.dumps({m: {"camera": pose_solve.snap(sol["pose"]), "solve": {
                    "inliers": sol["inliers"], "median_px": round(sol["err"], 3),
                    "similarity": round(sol["similarity"], 3)}}}))
        return 0
    names = names or [n for n, e in capture.table().items() if e["status"] == "shipped"]
    failed = [n for n in names if not capture.capture(slot, n)]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
