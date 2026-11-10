#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageOps


TILE_SUFFIXES = {
    "": (1, 1),
    "_left": (0, 1),
    "_right": (2, 1),
    "_top": (1, 0),
    "_bottom": (1, 2),
}

SOURCE_IMAGES = {
    "railgun_scope": {
        "default": Path(r"E:\rg\railgun_scope_3x3.png"),
        "mode": "RGBA",
        "dds_pixel_format": "DXT5",
    },
    "railgun_scope_glow": {
        "default": Path(r"E:\rg\railgun_scope_glow_3x3.png"),
        "mode": "RGB",
        "dds_pixel_format": "DXT1",
    },
}

DEFAULT_SCOPE_ALPHA_MASK = Path(r"E:\rg\railgun_scope_3x3-alpha.png")


def get_cell_size(image: Image.Image) -> tuple[int, int]:
    if image.width % 3 != 0 or image.height % 3 != 0:
        raise ValueError(f"expected 3x3 source image, got {image.width}x{image.height}")

    return image.width // 3, image.height // 3


def crop_tile(image: Image.Image, tile_x: int, tile_y: int) -> Image.Image:
    cell_width, cell_height = get_cell_size(image)
    left = tile_x * cell_width
    top = tile_y * cell_height
    return image.crop((left, top, left + cell_width, top + cell_height))


def apply_alpha_mask(image: Image.Image, alpha_mask_path: Path) -> Image.Image:
    with Image.open(alpha_mask_path) as alpha_mask_image:
        alpha_mask = alpha_mask_image.convert("L")

    if alpha_mask.size != image.size:
        raise ValueError(
            f"alpha mask size mismatch: expected {image.size[0]}x{image.size[1]}, "
            f"got {alpha_mask.size[0]}x{alpha_mask.size[1]}"
        )

    # The provided mask uses black as opaque and white as transparent.
    inverted_alpha = ImageOps.invert(alpha_mask)
    rgba_image = image.convert("RGBA")
    combined_alpha = ImageChops.multiply(rgba_image.getchannel("A"), inverted_alpha)
    rgba_image.putalpha(combined_alpha)
    return rgba_image


def write_texture_pair(image: Image.Image, output_base: Path, dds_pixel_format: str) -> None:
    output_base.parent.mkdir(parents=True, exist_ok=True)

    tga_path = output_base.with_suffix(".tga")
    dds_path = output_base.with_suffix(".dds")

    image.save(tga_path, format="TGA")
    image.save(dds_path, format="DDS", pixel_format=dds_pixel_format)

    print(f"wrote {tga_path}")
    print(f"wrote {dds_path}")


def export_tiles(
    source_path: Path,
    stem: str,
    mode: str,
    dds_pixel_format: str,
    output_dir: Path,
    alpha_mask_path: Path | None = None,
) -> None:
    if not source_path.is_file():
        raise FileNotFoundError(f"missing source image: {source_path}")

    with Image.open(source_path) as image:
        source_image = image.convert(mode)
        if alpha_mask_path is not None:
            if mode != "RGBA":
                raise ValueError(f"alpha mask requires RGBA output, got {mode}")
            source_image = apply_alpha_mask(source_image, alpha_mask_path)
        for suffix, (tile_x, tile_y) in TILE_SUFFIXES.items():
            tile = crop_tile(source_image, tile_x, tile_y)
            write_texture_pair(tile, output_dir / f"{stem}{suffix}", dds_pixel_format)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    source_game_dir = repo_root / "content" / "baseoq4"
    staged_game_dir = repo_root / ".install" / "baseoq4"

    parser = argparse.ArgumentParser(
        description="Export railgun scope 3x3 source art into center/edge TGA and DDS tiles."
    )
    parser.add_argument(
        "--scope-source",
        type=Path,
        default=SOURCE_IMAGES["railgun_scope"]["default"],
        help="path to the expanded 3x3 railgun scope source image",
    )
    parser.add_argument(
        "--glow-source",
        type=Path,
        default=SOURCE_IMAGES["railgun_scope_glow"]["default"],
        help="path to the expanded 3x3 railgun glow source image",
    )
    parser.add_argument(
        "--scope-alpha-mask",
        type=Path,
        default=DEFAULT_SCOPE_ALPHA_MASK,
        help="optional 3x3 grayscale mask where black is opaque and white is transparent",
    )
    parser.add_argument(
        "--output-dir",
        action="append",
        type=Path,
        default=[],
        help="tile output directory; may be specified more than once",
    )
    args = parser.parse_args()

    output_dirs = args.output_dir or [
        source_game_dir / "gfx" / "guis" / "hud" / "reticles",
        staged_game_dir / "gfx" / "guis" / "hud" / "reticles",
    ]

    source_paths = {
        "railgun_scope": args.scope_source,
        "railgun_scope_glow": args.glow_source,
    }

    for output_dir in output_dirs:
        for stem, settings in SOURCE_IMAGES.items():
            export_tiles(
                source_paths[stem],
                stem,
                settings["mode"],
                settings["dds_pixel_format"],
                output_dir,
                args.scope_alpha_mask if stem == "railgun_scope" else None,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
