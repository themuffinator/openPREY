"""Verify PBR diagnostic values, ownership and paired GL/Vulkan captures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from PIL import Image, ImageChops
from renderer_vulkan_pbr_diagnostics import cases


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def maximum(left, right):
    histogram = ImageChops.difference(left, right).histogram()
    return max(i % 256 for i, count in enumerate(histogram) if count)


def color_byte(value):
    encoded = value / 255.0
    linear = encoded / 12.92 if encoded <= 0.04045 else ((encoded + 0.055) / 1.055) ** 2.4
    return linear * 255.0


def encoded_byte(radiance):
    """255 x sRGB encode of linear radiance, white-limited (PBRLinearToSRGBExtended)."""
    x = max(radiance, 0.0)
    return min(255.0, 255.0 * (x * 12.92 if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gl-report', type=Path, required=True)
    parser.add_argument('--vk-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = (args.gl_report, args.vk_report)
    reports = [json.loads(path.read_text()) for path in paths]
    expected = cases()
    failures = []
    checks = {}
    for key in ('fixture', 'compiledMapSHA256', 'harnessSHA256', 'diagnosticProfile',
                'diagnosticHarnessSHA256', 'requestedSamples', 'basepath'):
        if reports[0].get(key) is None or reports[0].get(key) != reports[1].get(key):
            failures.append('mismatched ' + key)
    for name in set(reports[0]['runtimeSHA256']) | set(reports[1]['runtimeSHA256']):
        if name.startswith('renderer-vk'):
            continue  # Permit a previous native binary as a negative control.
        if reports[0]['runtimeSHA256'].get(name) != reports[1]['runtimeSHA256'].get(name):
            failures.append('mismatched runtime ' + name)
    images = []
    patch = (616, 376, 664, 424)
    for backend, report in zip(('gl', 'vk'), reports):
        rows = report['results']
        if not report.get('complete') or not report.get('runtimeUnchanged'):
            failures.append(backend + ': incomplete capture or changed runtime')
        if len(rows) != len(expected) or {row['case'] for row in rows} != set(expected):
            failures.append(backend + ': unexpected capture set')
        if report.get('requestedSamples') not in (0, 4) or report['fixture']['cameras']['sampling'] != [0, -1100, 380, 0, 90, 0]:
            failures.append(backend + ': unsupported camera or sample count')
        captures = {}
        for row in rows:
            name = row['case']
            if row.get('backend') != backend or row['failures']:
                failures.append(backend + ': failed capture ' + name)
            if not re.search(rf'Renderer AA: MSAA requested={report["requestedSamples"]} effective={report["requestedSamples"]}\b', '\n'.join(row['telemetry'])):
                failures.append(backend + ': inactive requested MSAA ' + name)
            for kind in ('screenshot', 'log'):
                if digest(Path(row[kind])) != row['sha256'][kind]:
                    failures.append(backend + ': changed ' + kind + ' ' + name)
            im = Image.open(row['screenshot']).convert('RGB')
            if im.size != (1280, 800):
                failures.append(backend + ': unexpected extent ' + name)
            captures[name] = im
        images.append(captures)
        if set(captures) != set(expected):
            continue

        # Independent constant-value oracle for the generated fixture, on a
        # fully covered central patch. The unlit room is black, so transparent
        # diagnostics must equal their material value times authored alpha.
        values = {
            'data_scalar': {1: (color_byte(188),) * 3, 3: (102,) * 3, 4: (128,) * 3,
                            5: (192,) * 3, 6: (0,) * 3, 7: (0, 255, 0)},
            'emissive': {1: tuple(color_byte(c) for c in (30, 200, 255)), 3: (0,) * 3,
                         4: (127.5,) * 3, 5: (255,) * 3,
                         # The emission view shows emission as it reaches the
                         # display-referred frame: linear radiance, encoded.
                         6: tuple(encoded_byte(color_byte(c) * 4 / 255) for c in (30, 200, 255)),
                         7: (0, 255, 0)},
            'source_alpha': {1: tuple(color_byte(c) * 112 / 255 for c in (50, 180, 255)),
                             3: (0,) * 3, 4: (22.4,) * 3, 5: (112,) * 3,
                             6: (0,) * 3, 7: (0, 112, 0)},
        }
        values['data_packed'] = values['data_separate'] = values['data_scalar']
        for name, spec in expected.items():
            target = values.get(spec['material'], {}).get(spec['mode'])
            if target is None or spec['lights'] != 0:
                continue
            error = max(abs(channel - value) for rgb in captures[name].crop(patch).getdata()
                        for channel, value in zip(rgb, target))
            checks[backend + '-value-' + name] = {'maximumError': error, 'expected': target}
            if error > 2:
                failures.append(backend + ': wrong diagnostic value ' + name)

        # Fully covered opaque pixels cannot depend on direct light count.
        # Edge samples and transparent pixels legitimately retain background.
        mask_image = captures['diagnostic-data_scalar-7-0']
        mask = [i for i, rgb in enumerate(mask_image.getdata()) if rgb == (0, 255, 0)]
        if len(mask) < 20000:
            failures.append(backend + ': empty or incomplete ownership mask')
        for material in ('data_scalar', 'emissive'):
            for mode in range(1, 8):
                prefix = f'diagnostic-{material}-{mode}-'
                left = list(captures[prefix + '0'].getdata())
                for lights in ((1, 2) if mode == 7 else (1,)):
                    right = list(captures[prefix + str(lights)].getdata())
                    error = max((abs(a - b) for i in mask for a, b in zip(left[i], right[i])), default=255)
                    checks[backend + '-light-independent-' + prefix + str(lights)] = {'maximumError': error}
                    if error != 0:
                        failures.append(backend + ': diagnostic changes with lights ' + prefix + str(lights))
        for material in ('data_packed', 'data_separate'):
            for mode in (1, 3, 4, 5):
                error = maximum(captures[f'diagnostic-{material}-{mode}-0'],
                                captures[f'diagnostic-data_scalar-{mode}-0'])
                checks[backend + f'-layout-{material}-{mode}'] = {'maximumError': error}
                if error > 1:
                    failures.append(backend + ': inconsistent data layout ' + material + ' mode ' + str(mode))

    semantics_failures = list(failures)
    paired_failures = []
    for name in sorted(expected):
        if any(name not in captures for captures in images):
            continue
        error = maximum(images[0][name], images[1][name])
        checks[name] = {'maximumError': error}
        if error > 2:
            paired_failures.append(name)
    failures += [name + ': whole-frame error above two bytes' for name in paired_failures]
    proof = {'status': 'fail' if failures else 'pass', 'failures': failures,
             'semanticsStatus': 'fail' if semantics_failures else 'pass',
             'semanticsFailures': semantics_failures, 'pairedFailures': paired_failures,
             'checks': checks, 'inputs': {str(p.resolve()): digest(p) for p in paths},
             'harnessSHA256': digest(Path(__file__)),
             'scope': 'Independent channel values, exact opaque light independence, shared data layouts and strict whole-frame GL/Vulkan <=2 comparison.'}
    assert not args.output.exists()
    args.output.write_text(json.dumps(proof, indent=2) + '\n')
    print('PBR diagnostics:', proof['status'], 'semantics:', proof['semanticsStatus'], failures)
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
