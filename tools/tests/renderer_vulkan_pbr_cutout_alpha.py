#!/usr/bin/env python3
"""Require a fully opaque PBR texture to survive an inclusive 1.0 cutoff.

The cutout and opaque controls use identical geometry and texture alpha. This
detects precision loss from interpolating constant primary alpha, independently
of cross-API anisotropic filtering or alpha-to-coverage conversion. All generated
material data stays in the isolated test save directory.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import sys

import numpy as np

import renderer_pbr_laboratory as lab
from renderer_hdr_linear_capture import read_pfm

CASES = ('opaque', 'threshold', 'image-reload', 'partial-restart', 'full-restart', 'opaque-restored')
MATERIAL = 'cutout_alpha_unity'


def prove(report, samples):
    failures, checks, images = [], {}, {}
    rows = {row['case']: row for row in report['results']}
    expected = {'cutout-alpha-' + name for name in CASES}
    if not report.get('complete') or not report.get('runtimeUnchanged') or set(rows) != expected:
        failures.append('incomplete or changed capture set/runtime')
    for name, row in rows.items():
        failures += [name + ': ' + error for error in row['failures']]
        telemetry = '\n'.join(row['telemetry'])
        if not re.search(rf'Renderer AA: MSAA requested={samples} effective={samples}\b', telemetry):
            failures.append(name + ': requested sample count inactive')
        if row['backend'] == 'vk':
            hdr = next((line for line in row['telemetry'] if line.startswith('Vulkan HDR scene ownership:')), '')
            values = dict(re.findall(r'(\w+)=(\d+)', hdr))
            if values.get('committed') != '1' or int(values.get('samples', '0')) != max(1, samples):
                failures.append(name + ': native HDR ownership missing')
        valid = True
        for kind in ('screenshot', 'linearScreenshot', 'log'):
            path = Path(row.get(kind, ''))
            if not path.is_file() or lab.digest(path) != row['sha256'].get(kind):
                failures.append(name + ': missing or changed ' + kind)
                valid = False
        if valid:
            log_text = Path(row['log']).read_text(encoding='utf-8', errors='replace')
            if not (re.search(r'\balphaTest\s+1\b', log_text)
                    and re.search(r'\balbedoMap\s+textures/openq4/pbr_lab/grey\b', log_text)):
                failures.append(name + ': constant-alpha material was not loaded')
        if valid:
            values = read_pfm(Path(row['linearScreenshot']))
            if values.shape != (800, 1280, 3) or not np.isfinite(values).all():
                failures.append(name + ': invalid linear capture')
            else:
                images[name] = values
    if set(images) == expected:
        opaque = images['cutout-alpha-opaque']
        checks['opaquePixels'] = int(np.count_nonzero(opaque[:, :, 1] > 0))
        if checks['opaquePixels'] < 1000 or np.any(opaque[:, :, (0, 2)] != 0):
            failures.append('opaque control lacks non-vacuous native material ownership')
        for suffix in CASES[1:]:
            name = 'cutout-alpha-' + suffix
            delta = np.abs(images[name] - opaque)
            display_equal = Path(rows[name]['screenshot']).read_bytes() == Path(rows['cutout-alpha-opaque']['screenshot']).read_bytes()
            checks[suffix] = dict(maximumError=float(delta.max()),
                                  differingPixels=int(np.count_nonzero(np.max(delta, axis=2))),
                                  displayExact=display_equal)
            if np.any(delta) or not display_equal:
                failures.append(name + ': constant-alpha cutoff differs from opaque coverage')
    return dict(status='fail' if failures else 'pass', failures=failures, checks=checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--basepath', type=Path, required=True)
    parser.add_argument('--backend', choices=('gl', 'vk'), required=True)
    parser.add_argument('--samples', choices=(0, 4), type=int, default=4)
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    args.runtime_root, args.output_dir = args.runtime_root.resolve(), args.output_dir.resolve()
    source_hash = lab.digest(Path(__file__))
    manifest = json.loads((args.runtime_root / 'pbr-lab.json').read_text())
    lab.BASE.update(image_anisotropy='1')
    profile = {}
    for suffix in CASES:
        name = 'cutout-alpha-' + suffix
        settings = dict(r_pbrIBL='0', r_rendererReflectionProbes='0', r_useLightGrid='0',
                        r_pbrDebug='7', r_hdrToneMap='1', r_msaaAlphaToCoverage='0',
                        r_multiSamples=str(args.samples), image_anisotropy='1')
        commands = ['g_stopTime 0']
        if not profile:
            commands += [f'printMaterial {lab.lab.PREFIX}/{MATERIAL}']
            commands += [f'script "${s["name"]}.hide()"' for s in manifest['stations']]
            commands += [f'script "${s}.Off()"' for s in ('key', 'blue_fill', 'warm_fill', 'lab_projector')]
        if suffix in ('opaque', 'threshold', 'opaque-restored'):
            if profile:
                commands += ['script "$cutout_alpha_specimen.remove()"', 'wait 3']
            material = 'data_scalar' if suffix.startswith('opaque') else MATERIAL
            commands += [f'spawn func_static name cutout_alpha_specimen model "{lab.lab.MODEL}" '
                         f'shader "{lab.lab.PREFIX}/{material}" origin "100 160 120" angle 0 solid 0']
        commands += {'image-reload': ['reloadImages all'], 'partial-restart': ['vid_restart partial'],
                     'full-restart': ['vid_restart']}.get(suffix, [])
        commands += ['wait 60', 'g_stopTime 1']
        lab.CASES[name], lab.CASE_COMMANDS[name] = settings, commands
        profile[name] = dict(settings={**lab.BASE, **settings}, commands=commands)
    material_path = args.output_dir / 'batch/baseoq4/materials/openq4_cutout_alpha_test.mtr'
    threshold_cutout = lab.lab.material(MATERIAL, roughness=0.25, coverage='cutout').replace('alphaTest 0.5', 'alphaTest 1')
    write = lab.write_capture_commands

    def write_commands(path, commands):
        material_path.parent.mkdir(parents=True, exist_ok=True)
        material_path.write_text(threshold_cutout, encoding='utf-8')
        return write(path, commands)

    lab.write_capture_commands = write_commands
    startup = lab.startup_args

    def startup_args(cvars, save):
        args = startup(cvars, save)
        # autoexec runs after declaration discovery and before initialization
        # finishes. Touch this unique test material there so it is retained
        # across level loading and spawning does not need a late precache.
        with (save / 'baseoq4/autoexec.cfg').open('a', encoding='utf-8') as config:
            config.write(f'touch material {lab.lab.PREFIX}/{MATERIAL}\n')
        return args

    lab.startup_args = startup_args
    sys.argv = [__file__, '--runtime-root', str(args.runtime_root), '--output-dir', str(args.output_dir),
                '--basepath', str(args.basepath), '--backend', args.backend, '--cases', ','.join(profile),
                '--batch', '--linear', '--timeout', str(args.timeout)]
    if args.backend == 'gl':
        sys.argv += ['--gl-debug']
    code = lab.main()
    path = args.output_dir / 'report.json'
    report = json.loads(path.read_text())
    assert lab.digest(Path(__file__)) == source_hash, 'capture harness changed during run'
    shutil.copy2(__file__, args.output_dir / 'harness' / Path(__file__).name)
    report['harnessSources'][Path(__file__).name] = source_hash
    report.update(cutoutAlphaProfile=profile, cutoutAlphaMaterialSHA256=lab.digest(material_path), requestedSamples=args.samples)
    report['cutoutAlphaProof'] = prove(report, args.samples)
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report['cutoutAlphaProof'], indent=2))
    return int(code or report['cutoutAlphaProof']['status'] != 'pass')


if __name__ == '__main__':
    raise SystemExit(main())
