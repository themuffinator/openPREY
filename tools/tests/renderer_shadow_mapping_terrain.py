"""Check stock terrain brightness and real occlusion against same-run controls.

Consumes engine screenshots from renderer_shadow_mapping_maps.py. The lit mask
comes from stencil/shadows-off agreement, not from the implementation under
test; the separate shadow mask prevents an unshadowed image from passing.
"""

import argparse
import json
from pathlib import Path


TERRAIN_REGIONS = {
    "q4dm2": ((450, 330, 930, 520), (160, 300, 440, 450)),
    "airdefense1": ((490, 330, 940, 510), (490, 330, 940, 535)),
}


def validate_terrain_images(save: Path, map_name: str) -> tuple[list[str], dict]:
    paths = [save / f"baseoq4/screenshots/{kind}.tga"
             for kind in ("mapped", "stencil", "unshadowed")]
    return validate_shadow_images(paths, *TERRAIN_REGIONS[map_name])


def validate_shadow_images(paths: list[Path], lit_box: tuple,
                           shadow_box: tuple) -> tuple[list[str], dict]:
    from PIL import Image

    if not all(path.is_file() for path in paths):
        return ["Terrain comparison needs all three engine captures"], {}
    images = []
    for path in paths:
        with Image.open(path) as image:
            images.append(image.convert("RGB"))
    if any(image.size != (960, 540) for image in images):
        return ["Terrain comparison requires the fixed 960x540 camera"], {}
    lit_count = dark_count = 0
    delta_sum = square_sum = 0.0
    for mapped, stencil, unshadowed in zip(*(image.crop(lit_box).getdata() for image in images)):
        if max(abs(s - u) for s, u in zip(stencil, unshadowed)) >= 3 or sum(stencil) <= 60:
            continue
        delta = sum(m - s for m, s in zip(mapped, stencil)) / 3.0
        delta_sum += delta
        square_sum += sum((m - s) ** 2 for m, s in zip(mapped, stencil)) / 3.0
        dark_count += delta < -6.0
        lit_count += 1
    shadow_count = 0
    mapped_occlusion = stencil_occlusion = 0.0
    for mapped, stencil, unshadowed in zip(*(image.crop(shadow_box).getdata() for image in images)):
        reference = sum(u - s for u, s in zip(unshadowed, stencil)) / 3.0
        if reference <= 15.0:
            continue
        shadow_count += 1
        stencil_occlusion += reference
        mapped_occlusion += sum(u - m for u, m in zip(unshadowed, mapped)) / 3.0
    metrics = {
        "lit_pixels": lit_count,
        "lit_mean_delta": delta_sum / max(lit_count, 1),
        "lit_rms": (square_sum / max(lit_count, 1)) ** 0.5,
        "dark_pixel_fraction": dark_count / max(lit_count, 1),
        "shadow_pixels": shadow_count,
        "retained_shadow_contrast": mapped_occlusion / max(stencil_occlusion, 1.0),
    }
    failures = []
    if lit_count < 1000 or shadow_count < 100:
        failures.append("Terrain reference masks contain too few lit/shadowed pixels")
    if metrics["lit_mean_delta"] < -2.0 or metrics["dark_pixel_fraction"] > 0.1:
        failures.append("Mapped terrain has excess self-shadow darkening/lines")
    if metrics["retained_shadow_contrast"] < 0.8:
        failures.append("Mapped terrain loses too much of the reference shadow contrast")
    return failures, metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map", choices=tuple(TERRAIN_REGIONS))
    parser.add_argument("save", type=Path)
    args = parser.parse_args()
    failures, metrics = validate_terrain_images(args.save, args.map)
    print(json.dumps({"failures": failures, "metrics": metrics}, indent=2))
    raise SystemExit(bool(failures))
