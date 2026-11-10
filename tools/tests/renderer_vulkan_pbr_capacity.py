#!/usr/bin/env python3
"""Prove complete native Vulkan transparency fallback at its record limit."""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

import renderer_pbr_laboratory as lab


# suffix, visible instances, enabled lights, PBR enabled, debug mode, IBL
CASES = [
    ('one', 1, 4, True, 7, False),
    ('below', 63, 4, True, 7, False),
    ('limit', 64, 4, True, 7, False),
    ('over', 65, 4, True, 7, False),
    ('over-native', 65, 4, False, 7, False),
    ('over-lit', 65, 4, True, 0, False),
    ('over-native-lit', 65, 4, False, 0, False),
    ('over-ibl', 65, 4, True, 0, True),
    ('over-native-ibl', 65, 4, False, 0, True),
    ('over-three', 65, 3, True, 7, False),
    ('over-none', 65, 0, True, 7, False),
    ('restored', 64, 4, True, 7, False),
    ('limit-lit', 64, 4, True, 0, False),
    ('limit-native-lit', 64, 4, False, 0, False),
    ('limit-image-reload', 64, 4, True, 0, False),
    ('limit-partial-restart', 64, 4, True, 0, False),
    ('limit-full-restart', 64, 4, True, 0, False),
    ('one-restored', 1, 4, True, 7, False),
]


def configure(manifest: dict, samples: int, ambient_lights: bool = False) -> dict:
    profile = {}
    for suffix, count, lights, enabled, debug, ibl in CASES:
        name = 'capacity-' + suffix
        settings = {'r_pbrIBL': str(int(ibl)), 'r_pbrIBLIntensity': '0.5',
                    'r_rendererReflectionProbes': '0', 'r_lightScale': '0.1',
                    'r_pbrDebug': str(debug), 'r_pbrMaterials': str(int(enabled)),
                    'r_multiSamples': str(samples)}
        commands = ['g_stopTime 0']
        if suffix == 'one':
            commands += [f'script "${s["name"]}.hide()"' for s in manifest['stations']]
            commands += [f'script "${light}.Off()"' for light in
                         ('key', 'blue_fill', 'warm_fill', 'lab_projector')]
            for i in range(65):
                commands += [f'spawn func_static name capacity_{i} model "{lab.lab.MODEL}" '
                             f'shader "{lab.lab.PREFIX}/source_alpha" origin "0 -700 380" solid 0']
            for i, origin in enumerate(('-120 -1000 540', '120 -1000 540',
                                        '-120 -1000 220', '120 -1000 220')):
                commands += [f'spawn light name capacity_light_{i} origin "{origin}" angle 0 '
                             'light_radius "1000 1000 1000" _color "1 1 1" noshadows 1'
                             + (' texture "lights/openq4/pbr_lab/ambient"' if ambient_lights else '')]
        # Separate commands avoid overflowing the engine's console string limit.
        commands += [f'script "$capacity_{i}.{"show" if i < count else "hide"}()"'
                     for i in range(65)]
        commands += [f'script "$capacity_light_{i}.{"On" if i < lights else "Off"}()"'
                     for i in range(4)]
        commands += ['wait 30', 'g_stopTime 1']
        for boundary in ('image-reload', 'partial-restart', 'full-restart'):
            if suffix == 'limit-' + boundary:
                commands += lab.CASE_COMMANDS[boundary]
        lab.CASES[name] = settings
        lab.CASE_COMMANDS[name] = commands
        lab.CASE_CAMERAS[name] = 'sampling'
        if not enabled:
            lab.LEGACY_CASES.add(name)
        profile[name] = {'visibleInstances': count, 'enabledLights': lights,
                         'settings': settings, 'commands': commands}
    return profile


def compare_pair(a: bytes, b: bytes) -> dict:
    if len(a) != len(b):
        raise ValueError('image sizes differ')
    maximum = max(abs(x-y) for x, y in zip(a, b))
    return {'maximumError': maximum, 'changedChannels': sum(x != y for x, y in zip(a, b)),
            'status': 'fail' if maximum else 'pass'}


def image_relations(images: dict[str, bytes], float_targets: dict[str, bool]) -> tuple[dict, list[str]]:
    checks, failures = {}, []
    # A rejected view must match the actual classic renderer over the whole
    # frame, including lighting and alpha, with debug and environment toggles.
    pairs = [('over', 'over-native'), ('over-lit', 'over-native-lit'),
             ('over-ibl', 'over-native-ibl'), ('over-lit', 'over-ibl'),
             ('one', 'one-restored'), ('limit', 'restored')]
    pairs += [('limit-lit', 'limit-' + boundary) for boundary in
              ('image-reload', 'partial-restart', 'full-restart')]
    for left, right in pairs:
        check = compare_pair(images['capacity-' + left], images['capacity-' + right])
        checks[left + '/' + right] = check
        if check['status'] != 'pass':
            failures.append(f'{left}/{right}: whole-frame error {check["maximumError"]}')
    # Non-vacuity: one alpha layer and many admitted layers must actually draw.
    # Repeated 8-bit source-alpha composition converges to 254, not 255. A
    # committed PBR preview composes ordered transparency on its RGBA16F
    # target and quantizes only the finished scene, so many layers reach 255.
    for suffix in ('one', 'below', 'limit', 'over-three', 'over-none'):
        pixels = images['capacity-' + suffix]
        green = 112 if suffix == 'one' else 255 if float_targets.get('capacity-' + suffix) else 254
        count = sum(pixels[i:i+3] == bytes((0, green, 0)) for i in range(0, len(pixels), 3))
        checks[suffix + 'CoveragePixels'] = count
        if count < 10000:
            failures.append(f'{suffix}: insufficient admitted transparent coverage ({count})')
    a, b = images['capacity-limit-lit'], images['capacity-limit-native-lit']
    channels = [(y*1280+x)*3+c for y in range(320,480) for x in range(560,720) for c in range(3)]
    effect = sum(abs(a[i]-b[i]) > 2 for i in channels)
    checks['nativeLightingEffectChannels'] = effect
    if effect < 1000:
        failures.append('the full record table did not retain native lighting')
    return checks, failures


def qualify(report: dict, samples: int) -> dict:
    failures, images, telemetry_checks, float_targets = [], {}, {}, {}
    rows = {row['case']: row for row in report['results']}
    if not report.get('complete') or not report.get('runtimeUnchanged'):
        failures.append('runtime changed or capture sequence incomplete')
    for suffix, count, lights, enabled, debug, ibl in CASES:
        name = 'capacity-' + suffix
        if name not in rows:
            failures.append(f'{name}: missing capture')
            continue
        row = rows[name]
        if row['failures']:
            failures.append(f'{name}: capture qualification failed')
        for kind in ('screenshot', 'log'):
            path = Path(row[kind])
            if not path.is_file() or lab.digest(path) != row['sha256'][kind]:
                failures.append(f'{name}: {kind} provenance changed')
        pixels = lab.capture_rgb(Path(row['screenshot'])) if Path(row['screenshot']).is_file() else None
        if pixels is None or len(pixels) != 1280*800*3:
            failures.append(f'{name}: invalid capture extent')
        else:
            images[name] = pixels
        text = '\n'.join(row['telemetry'])
        if not re.search(rf'Renderer AA: MSAA requested={samples} effective={samples}\b', text):
            failures.append(f'{name}: requested MSAA not active')
        float_targets[name] = re.search(r'^Vulkan PBR preview: requested=1 committed=1\b', text, re.M) is not None
        line = next((line for line in row['telemetry']
                     if line.startswith('Vulkan: native PBR transparency:')), '')
        state = dict(re.findall(r'(\w+)=([^\s]+)', line))
        records = count*lights
        admitted = enabled and records <= 256
        expected = {'admitted': str(int(admitted)), 'capacity': '256',
                    'reason': 'disabled' if not enabled else 'ready' if admitted else 'capacity',
                    'requiredAtLeast': str(min(records, 257) if enabled else 0),
                    'recorded': str(records if admitted else 0),
                    'surfaces': str(count if admitted else 0),
                    'composites': str(records if admitted and debug == 0 else 0)}
        mismatch = {key: {'expected': value, 'actual': state.get(key)}
                    for key, value in expected.items() if state.get(key) != value}
        telemetry_checks[name] = {'observed': state, 'mismatch': mismatch}
        if mismatch:
            failures.append(f'{name}: admission/draw telemetry does not prove the boundary')
    checks = {}
    if len(images) == len(CASES):
        checks, image_failures = image_relations(images, float_targets)
        failures += image_failures
    return {'status': 'fail' if failures else 'pass', 'telemetry': telemetry_checks,
            'imageChecks': checks, 'failures': failures}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--basepath', type=Path, required=True)
    parser.add_argument('--samples', type=int, choices=(0,4), default=0)
    parser.add_argument('--timeout', type=int, default=360)
    parser.add_argument('--ambient-lights', action='store_true', help='exercise ambient stages at the same record boundaries')
    args = parser.parse_args()
    args.runtime_root, args.output_dir = args.runtime_root.resolve(), args.output_dir.resolve()
    manifest = json.loads((args.runtime_root/'pbr-lab.json').read_text())
    profile = configure(manifest, args.samples, args.ambient_lights)
    sys.argv = [__file__, '--runtime-root', str(args.runtime_root), '--output-dir', str(args.output_dir),
                '--basepath', str(args.basepath), '--backend', 'vk', '--camera', 'sampling', '--batch',
                '--cases', ','.join(profile), '--timeout', str(args.timeout)]
    code = lab.main()
    path = args.output_dir/'report.json'
    report = json.loads(path.read_text())
    source = Path(__file__)
    shutil.copy2(source, args.output_dir/'harness'/source.name)
    report['harnessSources'][source.name] = lab.digest(source)
    report['requestedSamples'] = args.samples
    report['ambientLights'] = args.ambient_lights
    report['capacityProfile'] = profile
    report['capacityProof'] = qualify(report, args.samples)
    path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('Vulkan transparency capacity proof:', report['capacityProof']['status'],
          report['capacityProof']['failures'], flush=True)
    return int(bool(code or report['capacityProof']['failures']))


if __name__ == '__main__':
    raise SystemExit(main())
