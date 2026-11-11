"""Rebuild openPREY's TrueType faces from retail Prey bitmap fonts.

Usage:
    python build_openprey_fonts.py --source .tmp/prey-fontsrc
        --donors .tmp/fontdonors --output content/basepr/pak0/fonts
        [--faces english,menu,alien,bigchars]

The source directory is populated by ``extract_source_fonts.py``.  The output
file names deliberately match the paths used by the renderer after it resolves
``fonts``, ``fonts/menu`` and ``fonts/alien`` through ``fonts/english``.
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from q4font.build import FaceBuilder, FaceSpec
from q4font.charset import unicode_ranges
from q4font.path import Path2D
from q4font.trace import TraceOptions, trace_coverage

VERSION = "1.100"

# Prey's 48 point atlases are small for what they carry: the menu face's capitals
# are 18 pixels tall and the alien digits are pixel-art diagonals. Traced at that
# resolution, a curve is only a few samples long and the fitter reproduces the
# sampling noise as lumps. The 48 point faces are therefore resampled before
# tracing: bicubic reconstruction, then a light Gaussian that removes the 1/255
# quantisation and staircase noise. The tracer still finds corners and snaps
# stems on the denser field, so sharp geometry survives.
SMOOTH_FACTOR = 6
SMOOTH_SIGMA = 0.32          # source pixels
SMOOTH_CURVE_TOLERANCE = 0.07  # source pixels
SMOOTH_LINE_TOLERANCE = 0.11   # source pixels
SMOOTH_PASSES = 10
SMOOTH_CURVE_DEPTH = 4
SMOOTH_MIN_POINT_SIZE = 32.0


def _gaussian(field: np.ndarray, sigma: float) -> np.ndarray:
    radius = int(np.ceil(3.0 * sigma))
    taps = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-0.5 * (taps / sigma) ** 2)
    kernel /= kernel.sum()
    field = np.apply_along_axis(lambda row: np.convolve(row, kernel, mode="same"), 1, field)
    return np.apply_along_axis(lambda column: np.convolve(column, kernel, mode="same"), 0, field)


class PreyFaceBuilder(FaceBuilder):
    """FaceBuilder whose 48 point traces come from a smoothed, resampled field."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.smooth = self.source.point_size >= SMOOTH_MIN_POINT_SIZE and self.densify <= 1
        if self.smooth:
            k = SMOOTH_FACTOR
            self.smooth_options = replace(
                TraceOptions().for_point_size(self.source.point_size * k),
                curve_tolerance=SMOOTH_CURVE_TOLERANCE * k,
                line_tolerance=SMOOTH_LINE_TOLERANCE * k,
                smoothing_passes=SMOOTH_PASSES,
                max_curve_depth=SMOOTH_CURVE_DEPTH,
            )

    def _trace(self, coverage) -> Path2D:
        if not self.smooth:
            return super()._trace(coverage)
        height, width = coverage.shape
        if height == 0 or width == 0:
            return Path2D()
        k, pad = SMOOTH_FACTOR, 2
        field = np.pad(np.clip(coverage, 0.0, 1.0).astype(np.float32), pad)
        big = Image.fromarray(field).resize(((width + 2 * pad) * k, (height + 2 * pad) * k), Image.BICUBIC)
        big = np.clip(_gaussian(np.asarray(big, dtype=np.float64), SMOOTH_SIGMA * k), 0.0, 1.0).astype(np.float32)
        traced = trace_coverage(big, self.smooth_options)
        return traced.transformed(1.0 / k, 1.0 / k, -pad, -pad)
PREY_BITMAP_ATTRIBUTION = "the Prey (2006) bitmap fonts by Human Head Studios and 3D Realms"

FACES: dict[str, FaceSpec] = {
    "english": FaceSpec(
        source="fonts/english",
        family="openPREY Default",
        description="Prey's default UI and HUD face.",
        prey_format=True,
        project_name="openPREY",
        bitmap_attribution=PREY_BITMAP_ATTRIBUTION,
    ),
    "menu": FaceSpec(
        source="fonts/english/menu",
        family="openPREY Menu",
        description="Prey's menu face.",
        prey_format=True,
        project_name="openPREY",
        bitmap_attribution=PREY_BITMAP_ATTRIBUTION,
    ),
    "alien": FaceSpec(
        source="fonts/english/alien",
        family="openPREY Alien",
        all_caps=True,
        extended=False,
        description="Prey's alien glyph face; Latin characters map to its retail symbols.",
        prey_format=True,
        project_name="openPREY",
        bitmap_attribution=PREY_BITMAP_ATTRIBUTION,
    ),
    "bigchars": FaceSpec(
        source="textures/gfx/bigchars",
        family="openPREY BigChars",
        grid_atlas="textures/gfx/bigchars.tga",
        description="Prey's fixed-cell console and loading-screen face.",
        project_name="openPREY",
        bitmap_attribution=PREY_BITMAP_ATTRIBUTION,
    ),
}


def composable_codepoints(second_pass: bool = False) -> list[int]:
    """Everything worth attempting as base plus mark, in a stable order."""
    ranges = unicode_ranges()
    blocks = ("greek", "cyrillic", "cyrillic_supp") if second_pass else ("latin_ext_a", "latin_ext_b", "latin_ext_add")
    wanted: list[int] = []
    for block in blocks:
        low, high = ranges[block]
        wanted.extend(range(low, high + 1))
    return wanted


def build_face(key: str, spec: FaceSpec, source: Path, donors: Path, output: Path) -> dict:
    started = time.perf_counter()
    builder = PreyFaceBuilder(spec, source, donors, TraceOptions())

    builder.trace_source()
    metrics = builder.measure()
    builder.extract_marks(metrics)
    builder.compose(composable_codepoints())
    builder.alias_homoglyphs()
    builder.compose(composable_codepoints(second_pass=True))
    builder.synthesize_shapes(metrics)
    builder.import_donors(metrics)
    builder.force_monospace()
    builder.fold_to_base()

    destination = output / f"{key}.ttf"
    builder.emit(destination, metrics, VERSION)

    elapsed = time.perf_counter() - started
    report = dict(builder.report)
    report.update(
        {
            "file": destination.name,
            "glyphs": len(builder.glyphs),
            "mapped": len(builder.cmap),
            "cap": metrics.cap_height,
            "xheight": metrics.x_height,
            "ascender": metrics.ascender,
            "descender": metrics.descender,
            "seconds": round(elapsed, 1),
            "bytes": destination.stat().st_size,
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--donors", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--faces", default="")
    arguments = parser.parse_args()

    keys = [key.strip() for key in arguments.faces.split(",") if key.strip()] or list(FACES)
    unknown = [key for key in keys if key not in FACES]
    if unknown:
        parser.error(f"unknown face(s): {', '.join(unknown)}")

    arguments.output.mkdir(parents=True, exist_ok=True)
    for key in keys:
        report = build_face(key, FACES[key], arguments.source, arguments.donors, arguments.output)
        summary = " ".join(f"{name}={value}" for name, value in report.items())
        print(f"{key:9s} {summary}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
