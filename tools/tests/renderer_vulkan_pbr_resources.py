#!/usr/bin/env python3
"""Prove whole-view Vulkan PBR fallback and recovery after resource failures.

Uses engine screenshots from a hidden, windowed, input-disabled gameplay run.
Every injected failure is compared against a real classic-renderer control.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

import renderer_pbr_laboratory as lab


REASONS = {step: f'{owner}-{resource}'
           for owner, start in (('coverage', 1), ('direct', 5), ('environment', 9))
           for step, resource in enumerate(('pipeline', 'descriptor', 'uniform', 'geometry'), start)}
REASONS[13] = 'environment-image'


def configure(manifest: dict, samples: int, ambient_lights: bool = False) -> dict:
    profile = {}

    def add(suffix, fault=0, after=0, enabled=True, debug=0, lights=4,
            skip=False, boundary=None, reference='classic', descriptors=False):
        name = 'resources-' + suffix
        settings = {'r_pbrMaterials': str(int(enabled)), 'r_pbrDebug': str(debug),
                    'r_pbrIBL': '1', 'r_pbrIBLIntensity': '0.5',
                    'r_rendererReflectionProbes': '0', 'r_lightScale': '0.1',
                    'r_multiSamples': str(samples), 'r_skipInteractions': str(int(skip)),
                    'r_vkPBRPrepareFailure': str(fault), 'r_vkPBRPrepareFailureAfter': str(after)}
        commands = ['g_stopTime 0']
        if not profile:
            commands += [f'script "${s["name"]}.hide()"' for s in manifest['stations']]
            commands += [f'script "${light}.Off()"' for light in
                         ('key', 'blue_fill', 'warm_fill', 'lab_projector')]
            for i, x in enumerate((-150, 150)):
                commands += [f'spawn func_static name resources_{i} model "{lab.lab.MODEL}" '
                             f'shader "{lab.lab.PREFIX}/source_alpha" origin "{x} -700 380" solid 0']
            for i, origin in enumerate(('-120 -1000 540', '120 -1000 540',
                                        '-120 -1000 220', '120 -1000 220')):
                commands += [f'spawn light name resources_light_{i} origin "{origin}" angle 0 '
                             'light_radius "1000 1000 1000" _color "1 1 1" noshadows 1'
                             + (' texture "lights/openq4/pbr_lab/ambient"' if ambient_lights else '')]
        commands += [f'script "$resources_light_{i}.{"On" if i < lights else "Off"}()"'
                     for i in range(4)]
        commands += ['wait 30', 'g_stopTime 1']
        if boundary:
            commands += lab.CASE_COMMANDS[boundary]
        lab.CASES[name] = settings
        lab.CASE_COMMANDS[name] = commands
        lab.CASE_CAMERAS[name] = 'sampling'
        if not enabled:
            lab.LEGACY_CASES.add(name)
        profile[name] = {'fault': fault, 'after': after, 'enabled': enabled, 'debug': debug,
                         'lights': lights, 'skip': skip, 'reference': reference,
                         'requireDescriptorRollback': descriptors, 'settings': settings,
                         'commands': commands}

    lab.BASE.update({'r_vkPBRPrepareFailure': '0', 'r_vkPBRPrepareFailureAfter': '0',
                     'r_skipInteractions': '0'})
    add('cold-environment', fault=12, descriptors=True)
    add('classic', enabled=False)
    add('native', reference='native')
    add('owned', debug=7, reference='owned')
    for step in range(1, 14):
        add(f'fail-{step}-first', fault=step)
        # Descriptors are checked per set; other steps are per draw. Direct
        # late failures retain earlier lights, not only the surface plans.
        after = 6 if step in (2, 10) else 7 if step == 6 else 3 if 5 <= step <= 8 else 1
        add(f'fail-{step}-late', fault=step, after=after)
    add('restored', reference='native')
    add('cold-direct', fault=8, after=3, boundary='image-reload', descriptors=True)
    add('reload-restored', reference='native')
    for boundary in ('partial-restart', 'full-restart'):
        add(boundary + '-failure', fault=8, after=3, boundary=boundary)
        add(boundary + '-restored', reference='native')
    add('classic-unlit', enabled=False, lights=0, reference='classic-unlit')
    add('unlit-failure', fault=12, after=1, lights=0, reference='classic-unlit')
    add('unlit', lights=0, reference='unlit')
    add('classic-skipped', enabled=False, skip=True, reference='classic-skipped')
    add('skipped-failure', fault=12, after=1, skip=True, reference='classic-skipped')
    add('skipped', skip=True, reference='skipped')
    add('final-restored', reference='native')
    return profile


def qualify(report: dict, profile: dict, samples: int) -> dict:
    failures, images, telemetry, checks = [], {}, {}, {}
    rows = {row['case']: row for row in report['results']}
    if not report.get('complete') or not report.get('runtimeUnchanged'):
        failures.append('runtime changed or capture sequence incomplete')
    for name, spec in profile.items():
        row = rows.get(name)
        if row is None:
            failures.append(f'{name}: missing capture')
            continue
        if row['failures']:
            failures.append(f'{name}: capture qualification failed')
        for kind in ('screenshot', 'log'):
            path = Path(row[kind])
            if not path.is_file() or lab.digest(path) != row['sha256'][kind]:
                failures.append(f'{name}: {kind} provenance changed')
        shot = Path(row['screenshot'])
        if shot.is_file():
            pixels = lab.capture_rgb(shot)
            if len(pixels) == 1280*800*3:
                images[name] = pixels
            else:
                failures.append(f'{name}: invalid screenshot extent')
        text = '\n'.join(row['telemetry'])
        if not re.search(rf'Renderer AA: MSAA requested={samples} effective={samples}\b', text):
            failures.append(f'{name}: requested MSAA not active')
        line = next((line for line in row['telemetry']
                     if line.startswith('Vulkan: native PBR transparency:')), '')
        state = dict(re.findall(r'(\w+)=([^\s]+)', line))
        fault = spec['fault']
        admitted = spec['enabled'] and not fault
        records = 2*spec['lights'] if not spec['skip'] else 0
        expected = {'admitted': str(int(admitted)), 'ready': str(int(admitted)),
                    'reason': REASONS[fault] if fault else 'ready' if admitted else 'disabled',
                    'recorded': str(records if admitted else 0),
                    'surfaces': '2' if admitted else '0',
                    'composites': str(records if admitted and spec['debug'] == 0 else 0),
                    'faultVisits': str(spec['after']+1 if fault else 0)}
        mismatch = {key: {'expected': value, 'actual': state.get(key)}
                    for key, value in expected.items() if state.get(key) != value}
        if mismatch:
            failures.append(f'{name}: admission/rollback telemetry mismatch')
        telemetry[name] = {'observed': state, 'mismatch': mismatch}
        if fault:
            if (fault >= 3 or spec['after']) and int(state.get('restoredUniformBytes', '0')) <= 0:
                failures.append(f'{name}: failed resources did not restore uniform allocations')
            if 5 <= fault <= 8 and spec['after'] and int(state.get('preparedRecords', '0')) <= 0:
                failures.append(f'{name}: failure did not follow earlier prepared direct draws')
            if spec['requireDescriptorRollback'] and int(state.get('restoredDescriptors', '0')) <= 0:
                failures.append(f'{name}: did not free speculative image descriptors')
    if len(images) == len(profile):
        for name, spec in profile.items():
            reference = 'resources-' + spec['reference']
            a, b = images[name], images[reference]
            maximum = max(abs(x-y) for x, y in zip(a, b))
            changed = sum(x != y for x, y in zip(a, b))
            checks[name] = {'reference': reference, 'maximumError': maximum, 'changedChannels': changed}
            if maximum:
                failures.append(f'{name}: full-frame fallback/restoration error {maximum}')
        owned = images['resources-owned']
        covered = [i for i in range(0, len(owned), 3) if owned[i:i+3] == bytes((0,112,0))]
        checks['ownedCoveragePixels'] = len(covered)
        if len(covered) < 30000:
            failures.append('both complete transparent specimens must own their authored alpha')
        for a, b in (('native', 'classic'), ('unlit', 'classic-unlit'), ('skipped', 'classic-skipped')):
            left, right = images['resources-'+a], images['resources-'+b]
            changed = sum(abs(left[i+c]-right[i+c]) > 2 for i in covered for c in range(3))
            checks[a+'EffectChannels'] = changed
            if changed < 1000:
                failures.append(f'{a}: native PBR contribution is vacuous')
    return {'status': 'fail' if failures else 'pass', 'telemetry': telemetry,
            'imageChecks': checks, 'failures': failures}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--basepath', type=Path, required=True)
    parser.add_argument('--samples', type=int, choices=(0,4), default=0)
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--ambient-lights', action='store_true', help='exercise ambient-stage rollback and recovery')
    args = parser.parse_args()
    args.runtime_root, args.output_dir = args.runtime_root.resolve(), args.output_dir.resolve()
    profile = configure(json.loads((args.runtime_root/'pbr-lab.json').read_text()), args.samples, args.ambient_lights)
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
    report['resourceProfile'] = profile
    report['resourceProof'] = qualify(report, profile, args.samples)
    path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('Vulkan transparent resource proof:', report['resourceProof']['status'],
          report['resourceProof']['failures'], flush=True)
    return int(bool(code or report['resourceProof']['failures']))


if __name__ == '__main__':
    raise SystemExit(main())
