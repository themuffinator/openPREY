#!/usr/bin/env python3
"""Prove native transparent ownership survives the intervening Vulkan fog pass."""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

import renderer_vulkan_pbr_capacity as capacity

lab = capacity.lab
ORDER = ('clear-owned', 'fog-background', 'fog-owned', 'fog-owned-shared',
         'fog-lit', 'fog-lit-shared', 'clear-restored')


def configure(manifest: dict, samples: int) -> list[str]:
    # Reuse the same single surface and four lights, with all other instances hidden.
    capacity.configure(manifest, samples)
    base_settings = lab.CASES['capacity-one']
    setup = lab.CASE_COMMANDS['capacity-one']
    cases = []
    for suffix in ORDER:
        name = 'alpha-post-' + suffix
        cases.append(name)
        settings = {**base_settings, 'r_pbrDebug': '0' if 'lit' in suffix else '7',
                    'r_rendererSharedWorldFogBlend': '1' if suffix.endswith('shared') else '0'}
        commands = list(setup) if suffix == 'clear-owned' else []
        commands += ['g_stopTime 0']
        if suffix == 'fog-background':
            commands += ['spawn light name alpha_fog origin "0 0 400" angle 0 '
                         'light_radius "1400 1400 1000" texture "lights/openq4/pbr_lab/fog" noshadows 1']
        if suffix == 'clear-restored':
            # This authored fog stage has constant color registers; Off() only
            # changes light parameters and cannot disable those constants.
            commands += ['script "$alpha_fog.remove()"']
        commands += [f'script "$capacity_0.{"hide" if suffix == "fog-background" else "show"}()"',
                     'wait 30', 'g_stopTime 1']
        lab.CASES[name] = settings
        lab.CASE_COMMANDS[name] = commands
        lab.CASE_CAMERAS[name] = 'sampling'
    return cases


def image_relations(images: dict[str, bytes]) -> tuple[dict, list[str]]:
    checks, failures = {}, []
    for a, b in (('clear-owned', 'clear-restored'), ('fog-owned', 'fog-owned-shared'),
                 ('fog-lit', 'fog-lit-shared')):
        result = capacity.compare_pair(images[a], images[b])
        checks[a + '/' + b] = result
        if result['status'] != 'pass':
            failures.append(f'{a}/{b}: exact restoration or fog-consumer parity failed')
    reference, background, owned = [images[name] for name in ('clear-owned', 'fog-background', 'fog-owned')]
    covered = [i for i in range(0, len(reference), 3) if reference[i:i+3] == bytes((0,112,0))]
    if len(covered) < 10000:
        failures.append('the clear control did not draw a complete native-alpha specimen')
    effect = sum(max(background[i:i+3]) > 2 for i in covered)
    if effect < 10000:
        failures.append('fog did not provide a visible background behind the specimen')
    maximum = max((abs(owned[i+c] - (background[i+c]*143/255 + (112 if c == 1 else 0)))
                   for i in covered for c in range(3)), default=255)
    checks['sourceAlphaOverFog'] = {'coveredPixels': len(covered), 'fogEffectPixels': effect,
                                   'maximumError': maximum}
    if maximum > 1:
        failures.append(f'native transparency lost its source-alpha ownership after fog ({maximum})')
    return checks, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--basepath', type=Path, required=True)
    parser.add_argument('--samples', type=int, choices=(0,4), default=0)
    parser.add_argument('--timeout', type=int, default=240)
    args = parser.parse_args()
    args.runtime_root, args.output_dir = args.runtime_root.resolve(), args.output_dir.resolve()
    cases = configure(json.loads((args.runtime_root/'pbr-lab.json').read_text()), args.samples)
    sys.argv = [__file__, '--runtime-root', str(args.runtime_root), '--output-dir', str(args.output_dir),
                '--basepath', str(args.basepath), '--backend', 'vk', '--camera', 'sampling', '--batch',
                '--cases', ','.join(cases), '--timeout', str(args.timeout)]
    code = lab.main()
    path = args.output_dir/'report.json'
    report = json.loads(path.read_text())
    for source in (Path(__file__), Path(capacity.__file__)):
        shutil.copy2(source, args.output_dir/'harness'/source.name)
        report['harnessSources'][source.name] = lab.digest(source)
    failures, images = [], {}
    if not report.get('complete') or not report.get('runtimeUnchanged'):
        failures.append('runtime changed or capture sequence incomplete')
    for row in report['results']:
        suffix = row['case'].removeprefix('alpha-post-')
        for kind in ('screenshot', 'log'):
            source = Path(row[kind])
            if not source.is_file() or lab.digest(source) != row['sha256'][kind]:
                failures.append(f'{suffix}: {kind} provenance changed')
        if row['failures']:
            failures.append(f'{suffix}: capture qualification failed')
            continue
        image = lab.capture_rgb(Path(row['screenshot']))
        if image is None or len(image) != 1280*800*3:
            failures.append(f'{suffix}: invalid capture extent')
            continue
        images[suffix] = image
        telemetry = '\n'.join(row['telemetry'])
        if not re.search(rf'Renderer AA: MSAA requested={args.samples} effective={args.samples}\b', telemetry):
            failures.append(f'{suffix}: requested MSAA not active')
        records = 0 if suffix == 'fog-background' else 4
        surfaces = 0 if suffix == 'fog-background' else 1
        composites = records if 'lit' in suffix else 0
        expected = (f'admitted=1 reason=ready requiredAtLeast={records} capacity=256 '
                    f'recorded={records} composites={composites} surfaces={surfaces}')
        if expected not in telemetry:
            failures.append(f'{suffix}: native coverage/replay counters did not survive fog')
    checks = {}
    if set(images) == set(ORDER):
        checks, image_failures = image_relations(images)
        failures += image_failures
    else:
        failures.append('missing image controls')
    report['requestedSamples'] = args.samples
    report['postFogProof'] = {'status': 'fail' if failures else 'pass', 'checks': checks, 'failures': failures}
    path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('Vulkan post-fog transparency proof:', report['postFogProof']['status'], failures, flush=True)
    return int(bool(code or failures))


if __name__ == '__main__':
    raise SystemExit(main())
