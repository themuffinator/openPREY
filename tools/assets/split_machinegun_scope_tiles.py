#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


TILE_SUFFIXES = {
    "left": (0, 1),
    "right": (2, 1),
    "top": (1, 0),
    "bottom": (1, 2),
}

SOURCE_FILES = {
    "mgun_scope_distort": "mgun_scope_distort.png",
    "mgun_scope_grey": "mgun_scope_grey.tga",
}


def crop_tile(image: Image.Image, tile_x: int, tile_y: int) -> Image.Image:
    if image.width % 3 != 0 or image.height % 3 != 0:
        raise ValueError(f"expected 3x3 source image, got {image.width}x{image.height}")

    tile_width = image.width // 3
    tile_height = image.height // 3
    left = tile_x * tile_width
    top = tile_y * tile_height
    return image.crop((left, top, left + tile_width, top + tile_height))


def write_tiles(input_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for stem, source_name in SOURCE_FILES.items():
        source_path = input_dir / source_name
        if not source_path.is_file():
            raise FileNotFoundError(f"missing expanded source image: {source_path}")

        with Image.open(source_path) as image:
            rgba_image = image.convert("RGBA")
            for suffix, (tile_x, tile_y) in TILE_SUFFIXES.items():
                output_path = output_dir / f"{stem}_{suffix}.tga"
                crop_tile(rgba_image, tile_x, tile_y).save(output_path, format="TGA")
                print(f"wrote {output_path}")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    source_game_dir = repo_root / "content" / "baseoq4"
    staged_game_dir = repo_root / ".install" / "baseoq4"

    parser = argparse.ArgumentParser(
        description="Split the 3x3 machinegun scope expansion masks into side tiles."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=staged_game_dir / "gfx" / "guis" / "hud" / "reticles" / "expanded",
        help="directory containing the expanded 3x3 source images",
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

    for output_dir in output_dirs:
        write_tiles(args.input_dir, output_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
