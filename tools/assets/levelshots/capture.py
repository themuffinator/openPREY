"""Capture and stage the five-tile loading screens listed in poses.json.

capture: boots each set's map, removes Talon, runs the set's staging commands,
then runs `levelshot 1024 <camera> 90` with shadow maps for every light. The
tiles' own views must show no stencil shadow path (r_shadowMapReport 3) and
come from the pinned source size, or the capture is reported as failed.

stage: copies the shipped sets into content/basepr/pak2 in Prey's layout:
  guis/assets/loading/<set>{,_left,_right,_top,_bottom}.tga   the compositor's sources
  dds/guis/assets/loading/<set>{...}.dds                     overrides retail's dds/ copy by name
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from PIL import Image

import harness

HERE = Path(__file__).resolve().parent
TABLE = HERE / "poses.json"
FINAL = harness.WORK / "final"
PAK2 = harness.ROOT / "content" / "basepr" / "pak2"
VARIANTS = ("", "_left", "_right", "_top", "_bottom")
# A hidden window cannot exceed the desktop (2560x1440 on the capture machine).
# A source larger than it is split into regions, which match a one-pass render
# (docs/dev/levelshot-capture.md); the shipped sets were captured at 1.4x
# (1912x1434, one pass), and SOURCE pins that so a recapture reproduces them.
WINDOW = (2560, 1440)
SOURCE = "1912x1434"
# Shadow maps for every light class at the Ultra recipe, point lights included,
# and no screen-space post effects; antialiasing comes from the supersampling.
PIN_CVARS = (
    ("r_shadows", "1"), ("r_useShadowMap", "1"), ("r_shadowMapPointLights", "1"),
    ("r_shadowMapProgramReceivers", "1"), ("r_shadowMapStencilFallbackViews", "8"),
    ("r_shadowMapSize", "4096"), ("r_shadowMapAtlasSize", "8192"), ("r_shadowMapPointSize", "1024"),
    ("r_shadowMapMaxUpdatesPerView", "0"), ("r_shadowMapFilterTaps", "13"), ("r_shadowMapPointFilterTaps", "9"),
    ("r_shadowMapFilterMode", "2"), ("r_shadowMapPointFilterMode", "0"), ("r_shadowMapCSM", "1"),
    ("r_shadowMapCascadeCount", "4"), ("r_shadowMapProjectedCSM", "0"), ("r_shadowMapHashedAlpha", "1"),
    ("r_shadowMapTranslucentReceivers", "1"), ("r_levelshotSupersample", "1.4"),
    ("r_temporalAA", "0"), ("r_multiSamples", "0"), ("r_postAA", "0"), ("r_bloom", "0"), ("r_ssao", "0"),
    ("r_hdrToneMap", "0"), ("r_motionBlur", "0"), ("r_crt", "0"), ("r_useLightGrid", "0"),
    # Prey's glow overlay at retail's defaults
    ("r_skipGlowOverlay", "0"), ("r_glowStrength", "0.5"), ("r_glowAlpha", "0.55"),
    ("r_glowAlphaChange", "0.85"), ("r_glowSteps", "8"),
    ("image_anisotropy", "16"), ("image_downSize", "0"), ("image_picmip", "0"), ("r_screenFraction", "100"),
)
PINS = tuple(a for k, v in PIN_CVARS for a in ("+set", k, v)) + ("+set", "com_performancePresetCheck", "done")
# set again once the map is up, in case a first-run preset rewrote them
STAGE_PINS = "\n".join(f"set {k} {v}" for k, v in PIN_CVARS)
STENCIL_LINES = ("shadow map pass failed", "restoring stencil", "path=stencil", "result=stencil")


def table() -> dict:
    return json.loads(TABLE.read_text())["sets"]


def remove_talon(cl) -> list[str]:
    """Talon (the hawk) flies about or perches near the player; retail's shots never show him.
    Hidden, he shows himself again when he changes state, so he is removed."""
    cl.run("listEntities", settle=1.0)
    names = sorted(set(re.findall(r"hhTalon\s+(\S+)", cl.log.read_text(encoding="latin-1", errors="replace"))))
    for n in names:
        cl.run(f'script "${n}.remove();"', settle=0.5)
    return names


def capture(slot: str, name: str, log=print) -> bool:
    entry = table()[name]
    if "camera" not in entry:
        log(f"{name}: no camera in poses.json")
        return False
    map_name = entry["map"].split("/", 1)[1]
    x, y, z, p, yw, r = entry["camera"]
    game = harness.slot_game(slot)
    shutil.rmtree(game / "guis" / "assets" / "loading", ignore_errors=True)
    with harness.Client(slot, map_name, extra=PINS, stage=STAGE_PINS, window=WINDOW,
                        game_type=entry.get("gameType", "singleplayer")) as cl:
        removed = remove_talon(cl) if not map_name.startswith("dm") else []
        for cmd in entry.get("commands", []):
            cl.run(cmd, settle=0.5)
        cl.run("r_shadowMapReport 3", settle=0.0)
        cl.request(f"after {entry.get('after', 6000)}\nlevelshot 1024 {x:.3f} {y:.3f} {z:.3f} {p:.4f} {yw:.4f} {r:.4f} 90\n", timeout=600)
        cl.run("r_shadowMapReport 0", settle=0.2)
    text = cl.log.read_text(encoding="latin-1", errors="replace")
    begin = text.rfind("Capturing levelshot ")
    views = text[begin:text.find("Wrote ", begin)] if begin >= 0 else ""
    problems = []
    if f"from {SOURCE} " not in text:
        problems.append(f"the source was not {SOURCE}")
    problems += [line for line in views.splitlines() if any(s in line for s in STENCIL_LINES)][:3]
    if problems:
        log(f"{name}: FAILED {problems}")
        return False
    src, dest = game / "guis" / "assets" / "loading", FINAL / name
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    for v in VARIANTS:
        for ext in (".tga", ".dds"):
            shutil.move(str(src / f"{name}{v}{ext}"), dest / f"{name}{v}{ext}")
    # a side-by-side with retail for review
    cmp = Image.new("RGB", (1024, 384))
    cmp.paste(harness.retail(name, (512, 384)), (0, 0))
    cmp.paste(Image.open(dest / f"{name}.tga").convert("RGB").resize((512, 384)), (512, 0))
    cmp.save(FINAL / f"{name}_cmp.png")
    log(f"{name}: captured (removed {removed or 'nothing'})")
    return True


def stage(names: list[str] | None = None, log=print) -> None:
    names = names or [n for n, e in table().items() if e["status"] == "shipped"]
    tga_dir = PAK2 / "guis" / "assets" / "loading"
    dds_dir = PAK2 / "dds" / "guis" / "assets" / "loading"
    tga_dir.mkdir(parents=True, exist_ok=True)
    dds_dir.mkdir(parents=True, exist_ok=True)
    for n in names:
        for v in VARIANTS:
            shutil.copyfile(FINAL / n / f"{n}{v}.tga", tga_dir / f"{n}{v}.tga")
            shutil.copyfile(FINAL / n / f"{n}{v}.dds", dds_dir / f"{n}{v}.dds")
        log(f"staged {n}")
