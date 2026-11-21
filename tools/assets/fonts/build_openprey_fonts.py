"""Rebuild openPREY's TrueType faces.

Usage:
    python build_openprey_fonts.py --source .tmp/prey-fontsrc
        --donors .tmp/fontdonors --output content/basepr/pak0/fonts
        [--faces english,menu,alien,bigchars]

``menu``, ``alien`` and ``bigchars`` are traced from Prey's retail bitmap fonts,
extracted into the source directory by ``extract_source_fonts.py``. ``english``
is Talon, drawn in ``talon/``; it needs no retail source, so ``--source`` may
be left out when only it is built. The output file names deliberately match
the paths used by the renderer after it resolves ``fonts``, ``fonts/menu`` and
``fonts/alien`` through ``fonts/english``.
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from q4font.build import (
    ABOVE_MARKS,
    UNFLATTENED_MARKS,
    UNITS_PER_EM,
    FaceBuilder,
    FaceMetrics,
    FaceSpec,
    GlyphEntry,
    glyph_name,
    scale_about,
)
from q4font.charset import unicode_ranges
from q4font.path import Path2D
from q4font.trace import TraceOptions, trace_coverage

VERSION = "1.100"
TALON_VERSION = "2.000"

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


class TalonFaceBuilder(FaceBuilder):
    """FaceBuilder whose own glyphs are drawn by ``talon`` instead of traced.

    Everything after the source stage is the shared pipeline: accented letters
    are composed from Talon's letters and marks, stroked letters and Latin-1
    symbols are built from its parts, and the scripts Talon does not draw come
    from Noto at Talon's weight and width.
    """

    # The retail default face's line box in font units, kept so text laid out
    # without the retail .dat records keeps its line spacing.
    LINE_ASCENDER = 1920
    LINE_DESCENDER = 299

    def __init__(self, spec: FaceSpec, donor_dir: Path):
        # No FaceBuilder.__init__: it loads a retail atlas, and Talon has none.
        self.spec = spec
        point_size = 48.0
        self.scale = UNITS_PER_EM / point_size
        self.source = SimpleNamespace(
            point_size=point_size,
            ascender=self.LINE_ASCENDER / self.scale,
            descender=self.LINE_DESCENDER / self.scale,
        )
        self.densify = 1
        self.options = TraceOptions()
        self.donor_dir = donor_dir
        self.glyphs = {}
        self.cmap = {}
        self.paths = {}
        self.advances = {}
        self.marks_upper = {}
        self.marks_lower = {}
        self.report = {}
        self.traced = set()
        self.retail = {}
        self.cell_top = None
        self.cell_bottom = None
        self._drawn_marks = {}

    def trace_source(self) -> None:
        import talon

        drawn, aliases, marks = talon.outlines()
        self.glyphs[".notdef"] = GlyphEntry(".notdef", advance=int(round(0.5 * UNITS_PER_EM)))
        for codepoint, (path, advance) in drawn.items():
            name = glyph_name(codepoint)
            self._add(name, codepoint, path if path.contours else None, advance)
            self.traced.add(name)
        for codepoint, target in aliases.items():
            if target in self.cmap:
                self.cmap[codepoint] = self.cmap[target]
        self._drawn_marks = marks
        self.report["drawn"] = len(drawn)

    def extract_marks(self, metrics: FaceMetrics) -> None:
        """Seat Talon's drawn marks over a and A. Capital accents are a fifth
        flatter and sit closer, the usual treatment."""
        lower_ref = self._bounds_of("a")
        upper_ref = self._bounds_of("A")
        lower_gap = 0.042 * UNITS_PER_EM
        upper_gap = 0.03 * UNITS_PER_EM
        for mark_cp, path in self._drawn_marks.items():
            bounds = path.bounds()
            if bounds is None:
                continue
            if mark_cp in ABOVE_MARKS:
                self.marks_lower[mark_cp] = self._sit_above(path, lower_ref, lower_gap)
                flatten = 1.0 if mark_cp in UNFLATTENED_MARKS else 0.8
                capital = scale_about(path, 1.0, flatten, 0.0, bounds[1])
                self.marks_upper[mark_cp] = self._sit_above(capital, upper_ref, upper_gap)
            else:
                # Below marks are drawn hanging from the baseline already.
                self.marks_lower[mark_cp] = path
                self.marks_upper[mark_cp] = path
        self.report["marks"] = len(self.marks_upper) + len(self.marks_lower)

    def emit(self, destination: Path, metrics: FaceMetrics, version: str) -> None:
        super().emit(destination, metrics, version)
        from fontTools.ttLib import TTFont

        font = TTFont(str(destination))
        font.recalcTimestamp = False
        names = font["name"]
        names.setName("(c) 2026 DarkMatter Productions. Talon is part of openPREY.", 0, 3, 1, 0x409)
        names.setName(
            "Talon is original openPREY work, drawn on Impact's proportions with the squared bowls of the "
            "PREY wordmark; no outline is traced from retail art. Licensed under the SIL Open Font License 1.1. "
            "Glyphs for scripts Talon does not draw are derived from the Noto fonts, (c) Google, also licensed "
            "under the SIL Open Font License 1.1.",
            13, 3, 1, 0x409,
        )
        names.setName("https://openfontlicense.org", 14, 3, 1, 0x409)
        font.save(str(destination))


PREY_BITMAP_ATTRIBUTION = "the Prey (2006) bitmap fonts by Human Head Studios and 3D Realms"

FACES: dict[str, FaceSpec] = {
    "english": FaceSpec(
        source="fonts/english",
        family="openPREY Talon",
        description="openPREY's default UI and HUD face, drawn for openPREY.",
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


# Faces drawn for openPREY rather than traced from a retail atlas.
DRAWN_FACES = {"english"}


def build_drawn_face(key: str, spec: FaceSpec, donors: Path, output: Path) -> dict:
    started = time.perf_counter()
    builder = TalonFaceBuilder(spec, donors)

    builder.trace_source()
    metrics = builder.measure()
    builder.extract_marks(metrics)
    builder.extend_marks(metrics)
    builder.synthesize_letters(metrics)
    builder.synthesize_latin1(metrics)
    # A traced face takes Latin-1's accented letters from the retail art;
    # Talon composes them like the rest.
    builder.compose(list(range(0x00C0, 0x0100)) + composable_codepoints())
    builder.alias_homoglyphs()
    builder.compose(composable_codepoints(second_pass=True))
    builder.synthesize_shapes(metrics)
    builder.import_donors(metrics)

    destination = output / f"{key}.ttf"
    builder.emit(destination, metrics, TALON_VERSION)
    return _report(builder, metrics, destination, started)


def _report(builder: FaceBuilder, metrics: FaceMetrics, destination: Path, started: float) -> dict:
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
            "seconds": round(time.perf_counter() - started, 1),
            "bytes": destination.stat().st_size,
        }
    )
    return report


def build_face(key: str, spec: FaceSpec, source: Path, donors: Path, output: Path) -> dict:
    if key in DRAWN_FACES:
        return build_drawn_face(key, spec, donors, output)
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
    return _report(builder, metrics, destination, started)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="retail font extraction; not needed for english")
    parser.add_argument("--donors", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--faces", default="")
    arguments = parser.parse_args()

    keys = [key.strip() for key in arguments.faces.split(",") if key.strip()] or list(FACES)
    unknown = [key for key in keys if key not in FACES]
    if unknown:
        parser.error(f"unknown face(s): {', '.join(unknown)}")

    traced = [key for key in keys if key not in DRAWN_FACES]
    if traced and arguments.source is None:
        parser.error(f"--source is required for traced faces: {', '.join(traced)}")

    arguments.output.mkdir(parents=True, exist_ok=True)
    for key in keys:
        report = build_face(key, FACES[key], arguments.source, arguments.donors, arguments.output)
        summary = " ".join(f"{name}={value}" for name, value in report.items())
        print(f"{key:9s} {summary}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
