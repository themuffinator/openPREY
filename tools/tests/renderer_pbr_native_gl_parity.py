#!/usr/bin/env python3
"""Compare the classic OpenGL PBR owner (--gl-native) with native Vulkan.

Both reports must capture the same laboratory controls from one runtime. The
specimen patch (the fixed sampling camera's sphere) must agree within two
bytes; the whole frame must meet the encoded-frame allowance shared with the
other PBR parity tools after two documented exclusions:

- Classic surfaces. A control may name a PBR-off baseline of the same scene.
  A pixel that PBR changed on neither backend belongs to the classic renderer
  (for example its shadow filter on the laboratory walls) and is reported,
  never judged, here.
- One-pixel edge shifts. Alpha tests and silhouettes are discontinuous, so
  the last bit of interpolation can move an edge by one pixel. A difference
  beyond the encoded allowance counts as a shift only when each backend's
  value lies within the range of the other capture's 3x3 neighbourhood; at
  most 0.05% of the frame may shift.
- Alpha-tested silhouettes. Where an alpha-tested specimen turns edge-on, its
  coverage texture is read at the coarsest mips, averaged to the threshold,
  and single pixels can flip with no covered neighbour. Classic cutouts show
  the same flips (vk-direct-cutout-legacy). Up to sixteen such pixels are
  reported, never judged, for those controls only.

Controls that exercise a capability only one owner has are listed with the
reason and are reported, never silently skipped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import renderer_pbr_laboratory as lab
from renderer_pbr_environment_parity import metrics, within_encoded_allowance

WIDTH, HEIGHT = 1280, 800

# Capabilities only native Vulkan has. Each listed control is still compared
# and recorded, but cannot fail the run.
VULKAN_ONLY = {
    'vk-direct-aa-geometric-off': 'r_vkPBRSpecularAA 0 (OpenGL always filters roughness)',
    'vk-direct-aa-normal-off': 'r_vkPBRSpecularAA 0 (OpenGL always filters roughness)',
    'vk-direct-aa-constant-off': 'r_vkPBRSpecularAA 0 (OpenGL always filters roughness)',
    'vk-direct-aa-rough-off': 'r_vkPBRSpecularAA 0 (OpenGL always filters roughness)',
    'vk-direct-emission-extreme': 'float-HDR auto exposure (OpenGL auto exposure follows the modern visible post path)',
}

# PBR-off captures of the same scene, lights and shadows.
CLASSIC_BASELINE = {
    'vk-direct-shadow-projected': 'vk-direct-shadow-projected-native',
    'vk-direct-shadow-projected-owned': 'vk-direct-shadow-projected-native',
    'vk-direct-emission-many-lights': 'vk-direct-emission-many-lights-native',
}

# The baselines are classic renderings on both backends: recorded, not judged.
CLASSIC_REFERENCES = {name: 'classic baseline with PBR off; its differences belong to the classic renderer'
                      for name in (*CLASSIC_BASELINE.values(), 'ssao-classic', 'ssao-debug-classic')}

EDGE_SHIFT_LIMIT = 0.0005
COVERAGE_FLIP_LIMIT = 16

# Overview controls of the baked light grid and of SSAO are judged per
# station: each of the 24 specimen means within one byte. Their frames also hold the classic
# room, whose texture filtering differs by a byte or two between the APIs, and
# the laboratory's four-probe DXT1 grid samples differently along thin bands of
# normal directions on OpenGL (modern and native alike) and Vulkan. Both are
# recorded, not judged.
STATION_JUDGED_PREFIXES = ('lightgrid-', 'ssao-')
STATION_LIMIT = 1.0
# Since the light-grid bake captures whole cube faces (55abaa03, 2026-10-05)
# the laboratory grid varies more with direction, so the DXT1 band difference
# reaches 1.12 bytes on one station mean (1.33 with the doubled grid), all of
# it in those bands on dielectric and material-data stations.
BAKED_STATION_LIMIT = 1.5


def station_limit(name: str) -> float:
    return BAKED_STATION_LIMIT if name.startswith('lightgrid-') else STATION_LIMIT


def alpha_tested(name: str) -> bool:
    return 'cutout' in name


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def specimen(rgb: bytes) -> bytes:
    """The lab's central 65x65 specimen patch (normal_patch), from capture_rgb bytes."""
    patch = bytearray()
    for y in range(HEIGHT // 2 - 32, HEIGHT // 2 + 33):
        start = (y * WIDTH + WIDTH // 2 - 32) * 3
        patch.extend(rgb[start:start + 65 * 3])
    return bytes(patch)


def pixel_error(a: bytes, i: int, b: bytes, j: int) -> int:
    return max(abs(a[i] - b[j]), abs(a[i + 1] - b[j + 1]), abs(a[i + 2] - b[j + 2]))


def within_neighbourhood(value: bytes, i: int, other: bytes, x: int, y: int) -> bool:
    """Each channel of value[i] lies within two bytes of other's 3x3 range."""
    for channel in range(3):
        samples = [other[(ny * WIDTH + nx) * 3 + channel]
                   for ny in range(max(y - 1, 0), min(y + 2, HEIGHT))
                   for nx in range(max(x - 1, 0), min(x + 2, WIDTH))]
        if not min(samples) - 2 <= value[i + channel] <= max(samples) + 2:
            return False
    return True


def local_contrast(image: bytes, x: int, y: int) -> int:
    """The largest per-channel range of the 3x3 neighbourhood."""
    contrast = 0
    for channel in range(3):
        samples = [image[(ny * WIDTH + nx) * 3 + channel]
                   for ny in range(max(y - 1, 0), min(y + 2, HEIGHT))
                   for nx in range(max(x - 1, 0), min(x + 2, WIDTH))]
        contrast = max(contrast, max(samples) - min(samples))
    return contrast


def edge_shift(gl: bytes, vk: bytes, i: int, error: int) -> bool:
    """A silhouette or coverage edge that moved, or that shades its partial
    pixel slightly differently: either each value lies in the other's 3x3
    range, or the pixel sits on a real edge (contrast of at least 24) and
    differs by no more than half that contrast. Near-black edge pixels need
    the second form: the sRGB curve turns a tiny linear difference into
    several bytes there."""
    x, y = (i // 3) % WIDTH, (i // 3) // WIDTH
    if within_neighbourhood(gl, i, vk, x, y) and within_neighbourhood(vk, i, gl, x, y):
        return True
    contrast = max(local_contrast(gl, x, y), local_contrast(vk, x, y))
    return contrast >= 24 and error * 2 <= contrast


def judged(gl: bytes, vk: bytes, baseline: tuple[bytes, bytes] | None,
           coverage_flips: int = 0) -> tuple[bytes, dict]:
    """The OpenGL capture with excluded pixels replaced by Vulkan's values."""
    result = bytearray(gl)
    classic = shifted = 0
    isolated = []
    for i in range(0, len(gl), 3):
        error = pixel_error(gl, i, vk, i)
        if error <= 2:
            continue
        if baseline is not None and pixel_error(gl, i, baseline[0], i) <= 1 and pixel_error(vk, i, baseline[1], i) <= 1:
            classic += 1
        elif error > 4:
            # Small differences stay with the encoded allowance; only a step
            # beyond it can be an edge.
            if edge_shift(gl, vk, i, error):
                shifted += 1
            else:
                isolated.append(i)
                continue
        else:
            continue
        result[i:i + 3] = vk[i:i + 3]
    flips = isolated if len(isolated) <= coverage_flips else []
    for i in flips:
        result[i:i + 3] = vk[i:i + 3]
    return bytes(result), {'classicPixels': classic, 'edgeShiftedPixels': shifted,
                           'edgeShiftedFraction': shifted / (WIDTH * HEIGHT),
                           'isolatedPixels': [((i // 3) % WIDTH, (i // 3) // WIDTH) for i in isolated[:32]],
                           'coverageFlips': len(flips)}


def compare(gl: dict, vk: dict) -> dict:
    failures, cases = [], {}
    for key in ('fixture', 'compiledMapSHA256', 'basepath', 'runtimeSHA256'):
        if gl.get(key) != vk.get(key):
            failures.append(f'{key}: the two captures do not share their inputs')
    for name, report in (('gl', gl), ('vk', vk)):
        if not report.get('complete') or not report.get('runtimeUnchanged'):
            failures.append(f'{name}: incomplete or changed runtime')
    rows = [{row['case']: row for row in report.get('results', [])} for report in (gl, vk)]
    common = sorted(set(rows[0]) & set(rows[1]))
    if not common:
        failures.append('no common controls')
    images = {}
    for name in common:
        a_row, b_row = rows[0][name], rows[1][name]
        if a_row.get('backend') != 'gl' or b_row.get('backend') != 'vk':
            failures.append(f'{name}: wrong backend order')
            continue
        images[name] = tuple(lab.capture_rgb(Path(row['screenshot'])) for row in (a_row, b_row))
    for name in common:
        if name not in images:
            continue
        a, b = images[name]
        if a is None or b is None or len(a) != len(b) or len(a) != WIDTH * HEIGHT * 3:
            failures.append(f'{name}: missing or mismatched captures')
            continue
        baseline_name = CLASSIC_BASELINE.get(name)
        baseline = images.get(baseline_name) if baseline_name else None
        if baseline_name and (baseline is None or None in baseline):
            failures.append(f'{name}: classic baseline {baseline_name} is missing')
            continue
        judged_gl, exclusions = judged(a, b, baseline, COVERAGE_FLIP_LIMIT if alpha_tested(name) else 0)
        raw, full, patch = metrics(a, b), metrics(judged_gl, b), metrics(specimen(a), specimen(b))
        exempt = VULKAN_ONLY.get(name) or CLASSIC_REFERENCES.get(name)
        stations = None
        if name.startswith(STATION_JUDGED_PREFIXES):
            means = [row.get('image', {}).get('stationRGB', {}) for row in (rows[0][name], rows[1][name])]
            errors = {station: max(abs(x - y) for x, y in zip(rgb, means[1][station]))
                      for station, rgb in means[0].items() if station in means[1]}
            stations = {'maximumError': max(errors.values(), default=None), 'stations': len(errors),
                        'limit': station_limit(name), 'errors': errors}
            ok = len(errors) == 24 and stations['maximumError'] <= station_limit(name)
        else:
            ok = (patch['maximumError'] <= 2 and within_encoded_allowance(full['maximumError'], full['fractionAbove2'])
                  and exclusions['edgeShiftedFraction'] <= EDGE_SHIFT_LIMIT)
        cases[name] = {'fullFrame': full, 'rawFullFrame': raw, 'specimen': patch, 'exclusions': exclusions,
                       'stations': stations, 'classicBaseline': baseline_name, 'pass': ok, 'exemption': exempt,
                       'captureFailures': [rows[0][name].get('failures'), rows[1][name].get('failures')]}
        if not ok and exempt is None:
            detail = (f'stations {stations["maximumError"]} over {stations["stations"]}' if stations is not None else
                      f'specimen {patch["maximumError"]}, frame {full["maximumError"]}, '
                      f'edge shifts {exclusions["edgeShiftedPixels"]}')
            failures.append(f'{name}: OpenGL native PBR differs from Vulkan ({detail})')
    return {'status': 'fail' if failures else 'pass', 'failures': failures, 'cases': cases,
            'compared': len(cases),
            'exempt': sorted(name for name in cases if name in VULKAN_ONLY or name in CLASSIC_REFERENCES),
            'edgeShiftLimit': EDGE_SHIFT_LIMIT, 'coverageFlipLimit': COVERAGE_FLIP_LIMIT,
            'scope': 'Classic OpenGL light-loop PBR (draw_pbr.cpp) against native Vulkan on the same laboratory runtime, '
                     'Vulkan in its laboratory or production (--production) composition.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gl-report', type=Path, required=True)
    parser.add_argument('--vk-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reports = [json.loads(path.read_text()) for path in (args.gl_report, args.vk_report)]
    proof = compare(*reports)
    proof['inputs'] = {str(path.resolve()): digest(path) for path in (args.gl_report, args.vk_report)}
    proof['harnessSHA256'] = digest(Path(__file__))
    args.output.write_text(json.dumps(proof, indent=2) + '\n')
    print('OpenGL native PBR parity:', proof['status'], f"{proof['compared']} controls",
          proof['failures'][:12])
    return int(proof['status'] != 'pass')


if __name__ == '__main__':
    raise SystemExit(main())
