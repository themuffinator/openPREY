"""Headless openPREY clients for levelshot work (no input synthesis).

A Client boots a map from the staged package (.install) in a hidden window and
serves levelshotProbe request files until closed. Every client uses its own
savepath slot under the work directory (.tmp/levelshots/save_<slot>), so
several can run at once. See docs/dev/levelshot-capture.md.
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(os.environ.get("OPENPREY_LEVELSHOT_WORK", str(ROOT / ".tmp" / "levelshots")))
INSTALL = Path(os.environ.get("OPENPREY_LEVELSHOT_INSTALL", str(ROOT / ".install")))
EXE = INSTALL / ("openPREY-client_x64.exe" if os.name == "nt" else "openPREY-client_x64")
PORTS = {"a": "28411", "b": "28412", "c": "28413", "d": "28414"}
# probe size: the retail art's 4:3 view
W, H = 1024, 768


def retail_base() -> Path:
    """The retail install's base folder (pak_data.pk4); never guessed from a store layout."""
    base = os.environ.get("OPENPREY_RETAIL_BASE")
    if not base:
        raise SystemExit("set OPENPREY_RETAIL_BASE to the retail Prey install's base folder (it holds pak_data.pk4)")
    return Path(base)


def _unzip(member: str) -> bytes:
    # Prey's pak headers use backslashes, which zipfile rejects; unzip copes (and exits 1 with a warning)
    return subprocess.run(["unzip", "-p", str(retail_base() / "pak_data.pk4"), member], capture_output=True).stdout


def slot_game(slot: str) -> Path:
    return WORK / f"save_{slot}" / "basepr"


def _setup(slot: str) -> Path:
    game = slot_game(slot)
    (game / "lsq").mkdir(parents=True, exist_ok=True)
    # an empty config.spec keeps first-run machine-spec detection from rewriting the renderer cvars
    (game / "config.spec").write_text("")
    (game / "lsq_boot.cfg").write_text("exec lsq/stage.cfg\nexec lsq_poll.cfg\n")
    (game / "lsq_poll.cfg").write_text("exec lsq/cvars.cfg\nlevelshotProbe lsq/req.txt\nwait 10\nexec lsq_poll.cfg\n")
    return game


def map_entities(map_name: str) -> list[dict]:
    cache = WORK / "maps" / f"{map_name}.ents"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        text = _unzip(f"maps/game/{map_name}.map").decode("latin-1", "replace")
        depth, cur, out = 0, None, []
        for line in text.splitlines():
            s = line.strip()
            if s == "{":
                depth += 1
                if depth == 1:
                    cur = []
            elif s == "}":
                if depth == 1 and cur is not None:
                    out.append("{\n" + "\n".join(cur) + "\n}")
                    cur = None
                depth -= 1
            elif depth == 1 and s.startswith('"'):
                cur.append(s)
        cache.write_text("\n".join(out), encoding="latin-1")
    ents = []
    for block in cache.read_text(encoding="latin-1").split("\n}"):
        d = {m.group(1): m.group(2) for m in re.finditer(r'"([^"]*)"\s+"([^"]*)"', block)}
        if d:
            ents.append(d)
    return ents


def retail(name: str, size=(W, H)) -> Image.Image:
    """Retail loading art, squashed back from its square to the 4:3 view it was taken at."""
    path = WORK / "retail" / f"{name}.tga"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_unzip(f"guis/assets/loading/{name}.tga"))
    return Image.open(path).convert("RGB").resize(size, Image.LANCZOS)


class Client:
    """A running client that serves request files until closed."""

    def __init__(self, slot, map_name, extra=(), stage="", window=(W, H), boot_timeout=300, game_type="singleplayer"):
        self.slot, self.map = slot, map_name
        self.game = _setup(slot)
        self.req = self.game / "lsq" / "req.txt"
        self.log = self.game / "logs" / "lsq.log"
        (self.game / "lsq" / "cvars.cfg").write_text("\n")
        (self.game / "lsq" / "stage.cfg").write_text(stage + "\n")
        for stale in (self.log, self.req):
            if stale.exists():
                stale.unlink()
        # OpenAL Soft's silent backend: lights whose materials read sound stay lit
        env = dict(os.environ, ALSOFT_DRIVERS="null")
        args = [str(EXE),
                "+set", "fs_savepath", str(self.game.parent),
                "+set", "logFile", "2", "+set", "logFileName", "logs/lsq.log",
                "+set", "r_hiddenWindow", "1", "+set", "in_mouse", "0",
                "+set", "r_fullscreen", "0", "+set", "r_borderless", "0", "+set", "r_borderlessDefaultMigrated", "1",
                "+set", "r_windowWidth", str(window[0]), "+set", "r_windowHeight", str(window[1]),
                "+set", "net_port", PORTS[slot], "+set", "win_allowMultipleInstances", "1",
                "+set", "r_renderApi", "gl", "+set", "developer", "0",
                # muted, not s_noSound: map scripts loop on zero-length sounds without the sound system
                "+set", "s_volume", "0", "+set", "s_muteUnfocused", "0", "+set", "s_constantAmplitude", "1",
                "+set", "r_swapInterval", "0", "+set", "com_skipLoadingContinue", "1",
                *extra,
                "+set", "si_gameType", game_type, "+devmap", f"game/{map_name}", "+exec", "lsq_boot.cfg"]
        self.p = subprocess.Popen(args, cwd=str(INSTALL), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            self.request("after 2000\n", timeout=boot_timeout)
        except BaseException:
            # a constructor that raises never reaches close(); don't leave the client running
            self.p.kill()
            self.p.wait()
            raise

    def request(self, text, timeout=300):
        tmp = self.req.with_suffix(".tmp")
        tmp.write_text(text)
        os.replace(tmp, self.req)
        t0 = time.time()
        while self.req.exists():
            if self.p.poll() is not None:
                raise RuntimeError(f"client exited {self.p.returncode}")
            if time.time() - t0 > timeout:
                raise TimeoutError("request not served")
            time.sleep(0.2)

    def run(self, text, settle=2.0):
        """Run console text once through the poll loop."""
        marker = self.game / "lsq" / "ran.flag"
        if marker.exists():
            marker.unlink()
        (self.game / "lsq" / "cvars.cfg").write_text(text + "\nwriteConfig lsq/ran.flag\n")
        t0 = time.time()
        while not marker.exists() and time.time() - t0 < 60:
            time.sleep(0.2)
        (self.game / "lsq" / "cvars.cfg").write_text("\n")
        time.sleep(settle)

    def probes(self, tag, named_poses, fov=90.0, size=(W, H), depth=True, after=None):
        outdir = self.game / "out" / tag
        outdir.mkdir(parents=True, exist_ok=True)
        lines = [f"after {after}"] if after else []
        lines += [probe_line(n, tag, p, size, depth, fov) for n, p in named_poses]
        self.request("\n".join(lines) + "\n")
        return {n: load_probe(outdir / n) for n, _ in named_poses}

    def close(self):
        (self.game / "lsq" / "cvars.cfg").write_text("quit\n")
        try:
            self.p.wait(timeout=60)
        except subprocess.TimeoutExpired:
            self.p.kill()
            self.p.wait()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def probe_line(name, tag, pose, size=(W, H), depth=True, fov=90.0):
    x, y, z, p, yw = pose[:5]
    r = pose[5] if len(pose) > 5 else 0.0
    return (f"out/{tag}/{name} {size[0]} {size[1]} {x:.3f} {y:.3f} {z:.3f} {p:.4f} {yw:.4f} {r:.4f} {fov:.3f}"
            + (" depth" if depth else ""))


def load_probe(stem):
    stem = Path(stem)
    img = Image.open(str(stem) + ".tga").convert("RGB")
    depth = None
    dp = Path(str(stem) + ".depth")
    if dp.exists():
        d = np.fromfile(dp, dtype=np.float32)
        if d.size == img.width * img.height:
            depth = d.reshape(img.height, img.width)
    pose = None
    pp = Path(str(stem) + ".pose")
    if pp.exists():
        pose = [float(v) for v in pp.read_text().split()]
    return img, depth, pose
