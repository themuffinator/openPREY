"""Capture native PBR material diagnostics with and without direct lighting."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

import renderer_pbr_laboratory as lab


def cases():
    result = {}

    def add(material, mode, lights=0, rotated=False):
        name = f'diagnostic-{material}-{mode}-{lights}' + ('-rotated' if rotated else '')
        result[name] = {'material': material, 'mode': mode, 'lights': lights, 'rotated': rotated}

    for material in ('data_scalar', 'emissive'):
        for mode in range(1, 8):
            for lights in (0, 1):
                add(material, mode, lights)
        add(material, 7, 2)
    for material in ('data_packed', 'data_separate'):
        for mode in (1, 3, 4, 5):
            add(material, mode)
    for encoding in ('xyz', 'rg', 'agb'):
        for rotated in (False, True):
            add('baked_normal_' + encoding, 2, rotated=rotated)
    for mode in (1, 2, 5, 7):
        add('cutout', mode)
    for mode in range(1, 8):
        for lights in (0, 1):
            add('source_alpha', mode, lights)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--basepath', type=Path, required=True)
    parser.add_argument('--backend', choices=('gl', 'vk'), required=True)
    parser.add_argument('--samples', type=int, choices=(0, 4), default=0)
    parser.add_argument('--gl-native', action='store_true', help='OpenGL with the classic light loop owning PBR (draw_pbr.cpp)')
    parser.add_argument('--production', action='store_true', help='Vulkan with the laboratory linear scene off: every PBR draw composes into the display-referred frame, as shipped')
    parser.add_argument('--timeout', type=int, default=1200)
    args = parser.parse_args()
    lab.BASE['image_anisotropy'] = '16'
    source_hash = lab.digest(Path(__file__))
    manifest = json.loads((args.runtime_root / 'pbr-lab.json').read_text())
    profile = {}
    for name, spec in cases().items():
        commands = ['g_stopTime 0']
        if not profile:
            commands += [f'script "${s["name"]}.hide()"' for s in manifest['stations']]
            commands += [f'script "${s}.Off()"' for s in ('key', 'blue_fill', 'warm_fill', 'lab_projector')]
            commands += ['script "$probe_warm.remove(); $probe_cool.remove()"', 'wait 3']
            for i, origin in enumerate(('-120 -1000 540', '160 -960 300')):
                commands += [f'spawn light name diagnostic_light{i} origin "{origin}" angle 0 light_radius "1000 1000 1000" _color "1 1 1" noshadows 1']
        else:
            commands += ['script "$diagnostic_specimen.remove()"', 'wait 3']
        for i in range(2):
            state = 'On' if i < spec['lights'] else 'Off'
            commands += [f'script "$diagnostic_light{i}.{state}()"']
        orientation = 'rotation "1 0 0 0 0 1 0 -1 0"' if spec['rotated'] else 'angle 0'
        commands += [f'spawn func_static name diagnostic_specimen model "{lab.lab.MODEL}" shader "{lab.lab.PREFIX}/{spec["material"]}" origin "0 -700 380" {orientation} solid 0',
                     'wait 30', 'g_stopTime 1']
        settings = {'r_pbrIBL': '0', 'r_rendererReflectionProbes': '0', 'r_pbrMaterials': '1',
                    'r_pbrDebug': str(spec['mode']), 'r_multiSamples': str(args.samples),
                    'image_anisotropy': '16'}
        lab.CASES[name] = settings
        lab.CASE_COMMANDS[name] = commands
        lab.CASE_CAMERAS[name] = 'sampling'
        profile[name] = dict(spec, settings=settings, commands=commands)

    sys.argv = [__file__, '--runtime-root', str(args.runtime_root), '--output-dir', str(args.output_dir),
                '--basepath', str(args.basepath), '--backend', args.backend, '--camera', 'sampling',
                '--cases', ','.join(profile), '--batch', '--timeout', str(args.timeout)]
    if args.backend == 'gl':
        sys.argv.append('--gl-debug')
    if args.gl_native:
        if args.backend != 'gl':
            parser.error('--gl-native selects the classic OpenGL owner')
        sys.argv.append('--gl-native')
    if args.production:
        sys.argv.append('--production')
    code = lab.main()
    path = args.output_dir / 'report.json'
    report = json.loads(path.read_text())
    assert source_hash == lab.digest(Path(__file__)), 'capture harness changed'
    shutil.copy2(Path(__file__), args.output_dir / 'harness' / Path(__file__).name)
    report['harnessSources'][Path(__file__).name] = source_hash
    report.update(diagnosticProfile=profile, diagnosticHarnessSHA256=source_hash,
                  requestedSamples=args.samples, qualification='Capture only; paired image checks required')
    path.write_text(json.dumps(report, indent=2) + '\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
