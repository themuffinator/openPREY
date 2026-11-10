#!/usr/bin/env python3
"""Pack separate ambient-occlusion, roughness, and metallic maps into glTF ORM.

openQ4 PBR declarations consume packed ORM data as R = ambient occlusion,
G = roughness, B = metallic.  Input data is read from the explicitly selected
stored channel (R by default), never from an RGB-to-luminance conversion.  The
command-line image backend is optional Pillow and writes PNG or TGA according
to the output extension.  The packing core accepts an injected Pillow-compatible
backend so repository validation does not need Pillow installed.
"""

from __future__ import annotations

import argparse
from pathlib import Path


DATA_CHANNELS = ("R", "G", "B", "A")


def normalize_data_channel(channel: str) -> str:
    normalized = channel.upper()
    if normalized not in DATA_CHANNELS:
        raise ValueError(f"input channel must be one of {', '.join(DATA_CHANNELS)}")
    return normalized


def select_data_channel(image: object, channel: str, label: str) -> object:
    """Return one stored 8-bit data band without deriving RGB luminance.

    Pillow exposes an 8-bit grayscale image as an ``L`` band.  Treat that band
    as R for the default single-channel-map case.  All other requested channels
    must exist verbatim; in particular, palette and CMYK inputs fail closed
    instead of undergoing an implicit colour-space conversion.
    """

    normalized = normalize_data_channel(channel)
    bands = tuple(str(band).upper() for band in image.getbands())
    selected = "L" if normalized == "R" and "R" not in bands and "L" in bands else normalized
    if selected not in bands:
        available = ", ".join(bands) if bands else "none"
        raise ValueError(
            f"{label} map does not contain stored {normalized} data "
            f"(available bands: {available})"
        )
    # Pillow's getchannel() returns an independent single-band image.  copy()
    # also keeps injected validation backends independent of the source image's
    # context-manager lifetime.
    return image.getchannel(selected).copy()


def load_data_channel(path: Path, label: str, image_module: object, channel: str = "R") -> object:
    if not path.is_file():
        raise FileNotFoundError(f"{label} map is not a regular file: {path}")
    if path.is_symlink():
        raise RuntimeError(f"{label} map must not be a symlink: {path}")

    with image_module.open(path) as image:
        return select_data_channel(image, channel, label)


def pillow_image_module() -> object:
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Pillow is required for command-line PBR image I/O. "
            "Install it with `python -m pip install Pillow`."
        ) from exc
    return Image


def validate_output(output: Path, force: bool) -> None:
    if output.suffix.lower() not in {".png", ".tga"}:
        raise ValueError("--output must end in .png or .tga")
    if output.is_symlink():
        raise RuntimeError(f"ORM output must not be a symlink: {output}")
    if output.exists() and not output.is_file():
        raise RuntimeError(f"ORM output is not a regular file: {output}")
    if output.exists() and not force:
        raise FileExistsError(f"ORM output already exists: {output} (pass --force to replace it)")


def pack_orm(
    ao_path: Path | None,
    roughness_path: Path,
    metallic_path: Path,
    output: Path,
    force: bool,
    *,
    input_channel: str = "R",
    image_module: object | None = None,
) -> None:
    channel = normalize_data_channel(input_channel)
    Image = image_module if image_module is not None else pillow_image_module()

    validate_output(output, force)
    roughness = load_data_channel(roughness_path, "roughness", Image, channel)
    metallic = load_data_channel(metallic_path, "metallic", Image, channel)
    if roughness.size != metallic.size:
        raise ValueError(
            f"roughness and metallic sizes differ: {roughness.size[0]}x{roughness.size[1]} vs "
            f"{metallic.size[0]}x{metallic.size[1]}"
        )

    if ao_path is None:
        ao = Image.new("L", roughness.size, color=255)
    else:
        ao = load_data_channel(ao_path, "ambient-occlusion", Image, channel)
        if ao.size != roughness.size:
            raise ValueError(
                f"ambient-occlusion and roughness sizes differ: {ao.size[0]}x{ao.size[1]} vs "
                f"{roughness.size[0]}x{roughness.size[1]}"
            )

    packed = Image.merge("RGB", (ao, roughness, metallic))
    output.parent.mkdir(parents=True, exist_ok=True)
    packed.save(output, format="PNG" if output.suffix.lower() == ".png" else "TGA")
    print(
        f"wrote {output} (R=AO, G=roughness, B=metallic; "
        f"input={channel}; {packed.width}x{packed.height})"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roughness", required=True, type=Path, help="linear roughness map (output green)")
    parser.add_argument("--metallic", required=True, type=Path, help="linear metallic map (output blue)")
    parser.add_argument("--ao", type=Path, help="optional linear ambient-occlusion map (output red; white when omitted)")
    parser.add_argument(
        "--input-channel",
        choices=("r", "g", "b", "a"),
        default="r",
        help="stored input band to read from every map (default: r; grayscale L is accepted as r)",
    )
    parser.add_argument("--output", required=True, type=Path, help="packed .png or .tga output path")
    parser.add_argument("--force", action="store_true", help="allow replacement of an existing output file")
    args = parser.parse_args()
    pack_orm(
        args.ao,
        args.roughness,
        args.metallic,
        args.output,
        args.force,
        input_channel=args.input_channel,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
