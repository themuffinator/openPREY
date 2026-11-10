#!/usr/bin/env python3
"""Capture authored ambient lighting on native PBR and its GL reference.

The white projection/falloff fixture makes radiance constant over the specimen.
The companion comparison checks its absolute diffuse response, alpha composition,
material invariants and complete rollback, independently of renderer counters.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

import renderer_pbr_laboratory as lab


def configure(manifest: dict, samples: int) -> dict:
    lab.BASE.update({'r_vkPBRPrepareFailure': '0', 'r_vkPBRPrepareFailureAfter': '0'})
    profile = {}

    def add(name, material='data_scalar', lights=1, debug=0, enabled=True,
            double=False, hidden=False, rotated=False, boundary=None, fault=0):
        name = 'ambient-' + name
        settings = {'r_pbrMaterials': str(int(enabled)), 'r_pbrDebug': str(debug),
                    'r_pbrIBL': '0', 'r_rendererReflectionProbes': '0',
                    'r_lightScale': '1', 'r_multiSamples': str(samples),
                    'r_hdrToneMap': '0', 'r_useLightGrid': '0',
                    'r_vkPBRPrepareFailure': str(fault), 'r_vkPBRPrepareFailureAfter': '0'}
        commands = ['g_stopTime 0']
        if not profile:
            commands += [f'script "${s["name"]}.hide()"' for s in manifest['stations']]
            commands += [f'script "${light}.Off()"' for light in
                         ('key', 'blue_fill', 'warm_fill', 'lab_projector')]
            commands += ['script "$probe_warm.remove(); $probe_cool.remove()"', 'wait 3']
            for i, origin in enumerate(('-120 -1000 540', '120 -900 540', '-120 -1000 540')):
                shader = 'ambient_double' if i == 2 else 'ambient'
                commands += [f'spawn light name ambient_light_{i} origin "{origin}" angle 0 '
                             f'light_radius "2000 2000 2000" texture "lights/openq4/pbr_lab/{shader}" '
                             '_color "1 0.5 0.25" noshadows 1']
        else:
            commands += ['script "$ambient_specimen.remove()"', 'wait 3']
        for i in range(3):
            on = i == 2 if double else i < lights
            commands += [f'script "$ambient_light_{i}.{"On" if on else "Off"}()"']
        transform = ' rotation "1 0 0 0 0 1 0 -1 0"' if rotated else ' angle 0'
        commands += [f'spawn func_static name ambient_specimen model "{lab.lab.MODEL}" '
                     f'shader "{lab.lab.PREFIX}/{material}" origin "0 -700 380" solid 0' + transform]
        if hidden:
            commands += ['script "$ambient_specimen.hide()"']
        commands += ['wait 30', 'g_stopTime 1']
        if boundary:
            commands += lab.CASE_COMMANDS[boundary]
        lab.CASES[name] = settings
        lab.CASE_COMMANDS[name] = commands
        lab.CASE_CAMERAS[name] = 'sampling'
        if not enabled:
            lab.LEGACY_CASES.add(name)
        if hidden:
            lab.HIDDEN_SPECIMEN_CASES.add(name)
        profile[name] = dict(material=material, lights=lights, debug=debug, enabled=enabled,
                             double=double, hidden=hidden, rotated=rotated, boundary=boundary,
                             fault=fault, settings=settings, commands=commands)

    add('owned-dark', lights=0, debug=7)
    add('owned', debug=7)
    add('owned-two', lights=2, debug=7)
    add('dark', lights=0)
    add('scalar')
    add('packed', 'data_packed')
    add('separate', 'data_separate')
    add('ao-zero', 'ao_zero')
    add('two', lights=2)
    add('two-stages', double=True)
    for kind in ('dielectric', 'metal'):
        for roughness in (0, 5):
            add(f'{kind}-{roughness}', f'{kind}_{roughness}')
    for encoding in ('xyz', 'rg', 'agb', 'zero'):
        add('normal-' + encoding, 'baked_normal_' + encoding)
    add('rotated', 'baked_normal_xyz', rotated=True)
    add('cutout-owned', 'cutout', debug=7)
    add('cutout', 'cutout')
    add('emission-dark', 'emissive', lights=0, debug=6)
    add('emission', 'emissive', debug=6)
    add('emission-two', 'emissive', lights=2, debug=6)
    for suffix, lights, double in (('dark', 0, False), ('one', 1, False),
                                    ('two', 2, False), ('stages', 1, True)):
        add('background-' + suffix, 'source_alpha', lights=lights, double=double, hidden=True)
        add('alpha-' + suffix, 'source_alpha', lights=lights, double=double)
    add('alpha-owned', 'source_alpha', debug=7)
    add('alpha-classic', 'source_alpha', enabled=False)
    add('alpha-fault', 'source_alpha', fault=8)
    add('alpha-restored', 'source_alpha')
    for boundary in ('image-reload', 'partial-restart', 'full-restart'):
        add('alpha-' + boundary, 'source_alpha', boundary=boundary)
    add('classic', enabled=False)
    add('restored')
    return profile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--basepath', type=Path, required=True)
    parser.add_argument('--backend', choices=('gl', 'vk'), required=True)
    parser.add_argument('--samples', choices=(0, 4), type=int, default=0)
    parser.add_argument('--gl-native', action='store_true',
                        help='OpenGL with the classic light loop owning PBR (draw_pbr.cpp)')
    parser.add_argument('--production', action='store_true', help='Vulkan with the laboratory linear scene off: every PBR draw composes into the display-referred frame, as shipped')
    args = parser.parse_args()
    profile = configure(json.loads((args.runtime_root / 'pbr-lab.json').read_text()), args.samples)
    # Fault injection is a native preflight contract. GL has no corresponding
    # rejected draw; every other capture remains a paired rendering control.
    if args.backend == 'gl':
        profile.pop('ambient-alpha-fault')
    if args.gl_native and args.backend != 'gl':
        parser.error('--gl-native selects the classic OpenGL owner')
    source_hash = lab.digest(Path(__file__))
    sys.argv = [__file__, '--runtime-root', str(args.runtime_root), '--output-dir', str(args.output_dir),
                '--basepath', str(args.basepath), '--backend', args.backend, '--camera', 'sampling',
                '--cases', ','.join(profile), '--batch', '--timeout', '600']
    if args.backend == 'gl':
        sys.argv.append('--gl-debug')
    if args.gl_native:
        sys.argv.append('--gl-native')
    if args.production:
        sys.argv.append('--production')
    code = lab.main()
    report_path = args.output_dir / 'report.json'
    report = json.loads(report_path.read_text())
    if source_hash != lab.digest(Path(__file__)):
        raise RuntimeError('capture harness changed during execution')
    shutil.copy2(Path(__file__), args.output_dir / 'harness' / Path(__file__).name)
    report.update(ambientProfile=profile, ambientHarnessSHA256=source_hash,
                  requestedSamples=args.samples, qualification='Capture only; run renderer_pbr_ambient_parity.py')
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
