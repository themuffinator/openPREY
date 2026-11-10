"""Matched stock Air Defense 1 outdoor cameras, including cache refits.

Uses engine console teleports and render-target screenshots, without OS input.
Each pose freezes simulation before comparing mapped, freshly rendered,
stencil and unshadowed views. Positions cover terrain and real stock casters.
"""

from pathlib import Path
import re

from renderer_shadow_mapping_terrain import validate_shadow_images


OUTDOOR_SCENARIO = "airdefense1-outdoor"
OUTDOOR_VIEWS = {
    # Approach the railing before mode switches can recreate its interaction.
    # Its opening-view LOD rejection used to persist even at close range.
    "entrance_first": (9750, -6180, 80, 8, 240, 0),
    "opening": (10200, -6800, 40, 0, 170, 0),
    "wreckage": (9800, -7200, 80, 8, 230, 0),
    "tank": (9400, -7450, 220, 8, 175, 0),
    "ridge": (9000, -8200, 500, 20, 60, 0),
    "crater": (8400, -9600, 500, 18, 65, 0),
    "reverse": (9700, -8500, 350, 10, 60, 0),
    "entrance": (9750, -6180, 80, 8, 240, 0),
    "vista": (10900, -9000, 550, 12, 175, 0),
    "distant": (8100, -11800, 650, 15, 90, 0),
    "returned": (10200, -6800, 40, 0, 170, 0),
}


def outdoor_commands() -> tuple[list[str], tuple[str, ...]]:
    commands, captures = [], []
    for name, pose in OUTDOOR_VIEWS.items():
        commands += ["r_shadows 1", "r_useShadowMap 1", "r_shadowMapStaticCache 1",
                     "g_stopTime 0", "setviewpos " + " ".join(map(str, pose)),
                     "wait 3", "g_stopTime 1", "wait 12",
                     f"echo OUTDOOR_VIEW_{name}", "viewpos"]
        for kind, setting in (("mapped", None), ("fresh", "r_shadowMapStaticCache 0"),
                              ("stencil", "r_useShadowMap 0"), ("unshadowed", "r_shadows 0")):
            if setting:
                commands += [setting, "wait 5"]
            capture = f"outdoor_{name}_{kind}"
            captures.append(capture)
            commands += [f"screenshot screenshots/{capture}.tga", "wait 3"]
    commands += ["r_shadows 1", "r_useShadowMap 1", "r_shadowMapStaticCache 1"]
    return commands, tuple(captures)


def validate_outdoor_reports(text: str) -> list[str]:
    failures = []
    for name, pose in OUTDOOR_VIEWS.items():
        match = re.search(rf"^OUTDOOR_VIEW_{name}\s*\norigin: \(([-\d. ]+)\) "
                          r"angles: \(([-\d. ]+)\)", text, re.MULTILINE)
        actual = [float(v) for v in " ".join(match.groups()).split()] if match else []
        if len(actual) != 6 or any(abs(a - b) > 1.0 for a, b in zip(actual[:3], pose[:3])) or any(
                abs((a - b + 180.0) % 360.0 - 180.0) > 1.0 for a, b in zip(actual[3:], pose[3:])):
            failures.append(f"Outdoor {name}: requested camera was not confirmed")
    return failures


def validate_outdoor_images(save: Path) -> tuple[list[str], dict]:
    from PIL import Image, ImageChops, ImageStat

    failures, metrics = [], {}
    for name in OUTDOOR_VIEWS:
        paths = [save / f"baseoq4/screenshots/outdoor_{name}_{kind}.tga"
                 for kind in ("mapped", "stencil", "unshadowed")]
        # Exclude the sky and screen boundary; retain both ground and casters.
        box = (0, 160, 960, 525)
        errors, values = validate_shadow_images(paths, box, box)
        failures += [f"Outdoor {name}: {error}" for error in errors]
        if name in ("entrance_first", "entrance"):
            rail_errors, rail_metrics = validate_railing_shadow(paths)
            failures += [f"Outdoor {name}: {error}" for error in rail_errors]
            values.update(rail_metrics)
        fresh = save / f"baseoq4/screenshots/outdoor_{name}_fresh.tga"
        if paths[0].is_file() and fresh.is_file():
            with Image.open(paths[0]) as mapped_image, Image.open(fresh) as fresh_image:
                # Simulation is frozen: cache reuse must preserve the full frame.
                diff = ImageChops.difference(mapped_image.convert("RGB"), fresh_image.convert("RGB"))
                rms = (sum(v * v for v in ImageStat.Stat(diff).rms) / 3.0) ** 0.5
            values["cache_fresh_rms"] = rms
            if rms > 1.0:
                failures.append(f"Outdoor {name}: cached and fresh shadows disagree (RMS {rms:.3f})")
        else:
            failures.append(f"Outdoor {name}: missing cache comparison")
        metrics[name] = values
    return failures, metrics


def validate_railing_shadow(paths: list[Path]) -> tuple[list[str], dict]:
    from PIL import Image, ImageChops, ImageFilter

    if not all(path.is_file() for path in paths):
        return ["Railing comparison needs all three engine captures"], {}
    images = []
    for path in paths:
        with Image.open(path) as image:
            images.append(image.convert("L").crop((0, 320, 560, 480)))
    mapped, stencil, unshadowed = images
    reference = ImageChops.subtract(unshadowed, stencil)
    # Thin filtered shadows may move or soften by a couple of display pixels.
    # Allow that footprint, but require real occlusion where stencil has rails.
    nearby = ImageChops.subtract(unshadowed, mapped).filter(ImageFilter.MaxFilter(5))
    selected = [(r, m) for r, m in zip(reference.getdata(), nearby.getdata()) if r > 15]
    supported = sum(m >= 0.5 * r for r, m in selected) / max(len(selected), 1)
    metrics = {"railing_shadow_pixels": len(selected), "railing_shadow_support": supported}
    failures = []
    if len(selected) < 500:
        failures.append("Railing reference contains too few shadow pixels")
    if supported < 0.9:
        failures.append("Approached railing is missing mapped shadows")
    return failures, metrics
