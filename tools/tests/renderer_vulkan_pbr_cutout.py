#!/usr/bin/env python3
"""Check PBR depth coverage against opaque geometry under strong minification.

The original checker alpha averages to 128 in typed PBR mips, above the 0.5
cutoff. Its classic image copy truncates that average to 127. A 256x tiled
version of the existing procedural sphere therefore exposes use of the wrong
image without relying on cross-API edge tolerances. Test assets stay in the
isolated save directory; all captures come from the engine render target.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import sys

import numpy as np
from PIL import Image

import renderer_pbr_laboratory as lab
from renderer_hdr_linear_capture import read_pfm

MODEL = 'models/openq4/pbr_lab/cutout_mip_sphere.ase'
CASES = ('near', 'minified', 'opaque', 'restored', 'image-reload',
         'partial-restart', 'full-restart', 'near-restored')


def prove(report, samples):
    failures, checks, images = [], {}, {}
    rows = {row['case']: row for row in report['results']}
    names = {'cutout-mip-' + name for name in CASES}
    if not report.get('complete') or not report.get('runtimeUnchanged'):
        failures.append('incomplete capture or changed runtime')
    if len(report['results']) != len(names) or set(rows) != names:
        failures.append('unexpected capture set')
    for name, row in rows.items():
        failures += [name + ': ' + f for f in row['failures']]
        telemetry = '\n'.join(row['telemetry'])
        if not re.search(rf'Renderer AA: MSAA requested={samples} effective={samples}\b', telemetry):
            failures.append(name + ': requested sample count inactive')
        if row['backend'] == 'vk':
            hdr = next((line for line in row['telemetry']
                        if line.startswith('Vulkan HDR scene ownership:')), '')
            values = dict(re.findall(r'(\w+)=(\d+)', hdr))
            if values.get('committed') != '1' or int(values.get('samples', '0')) != max(1, samples):
                failures.append(name + ': native HDR ownership missing')
        for kind in ('screenshot', 'linearScreenshot', 'log'):
            path = Path(row.get(kind, ''))
            if not path.is_file() or lab.digest(path) != row['sha256'].get(kind):
                failures.append(name + ': missing or changed ' + kind)
        if 'linearScreenshot' in row and Path(row['linearScreenshot']).is_file():
            values = read_pfm(Path(row['linearScreenshot']))
            if values.shape != (800, 1280, 3) or not np.isfinite(values).all():
                failures.append(name + ': invalid linear capture')
            else:
                images[name] = values
    if set(images) == names:
        opaque = images['cutout-mip-opaque']
        green = opaque[:, :, 1]
        checks['opaquePixels'] = int(np.count_nonzero(green > 0))
        if checks['opaquePixels'] < 1000 or np.any(opaque[:, :, (0, 2)] != 0):
            failures.append('opaque ownership control is empty or has unexpected colors')
        for suffix in ('minified', 'restored', 'image-reload', 'partial-restart', 'full-restart'):
            name = 'cutout-mip-' + suffix
            delta = np.abs(images[name] - opaque)
            checks[suffix] = dict(maximumError=float(delta.max()),
                                  changedChannels=int(np.count_nonzero(delta)))
            if np.any(delta):
                failures.append(name + ': minified cutout differs from opaque coverage')
        fraction = float(images['cutout-mip-near'][:, :, 1].sum() / max(1.0, green.sum()))
        checks['nearCoverageFraction'] = fraction
        if not 0.1 < fraction < 0.9:
            failures.append('near cutout lost its authored holes')
        for left, right in (('near-restored', 'near'), ('restored', 'minified'),
                            ('image-reload', 'minified'), ('partial-restart', 'minified'),
                            ('full-restart', 'minified')):
            for kind in ('screenshot', 'linearScreenshot'):
                a, b = (Path(rows['cutout-mip-' + n][kind]).read_bytes() for n in (left, right))
                if a != b:
                    failures.append(left + ': ' + kind + ' changed after restoration')
    return dict(status='fail' if failures else 'pass', failures=failures, checks=checks)


def compare(report, reference):
    failures, checks = [], {}
    for key in ('fixture', 'compiledMapSHA256', 'cutoutProfile', 'cutoutModelSHA256',
                'harnessSources', 'requestedSamples', 'basepath'):
        if report.get(key) is None or report[key] != reference.get(key):
            failures.append('mismatched ' + key)
    if reference.get('cutoutProof', {}).get('status') != 'pass':
        failures.append('OpenGL reference did not pass independent controls')
    for name in set(report['runtimeSHA256']) | set(reference['runtimeSHA256']):
        if not name.startswith('renderer-vk') and report['runtimeSHA256'].get(name) != reference['runtimeSHA256'].get(name):
            failures.append('mismatched runtime ' + name)
    rows = {row['case']: row for row in reference['results']}
    if set(rows) != {row['case'] for row in report['results']}:
        failures.append('mismatched capture set')
    for row in report['results']:
        other = rows.get(row['case'])
        if other is None:
            continue
        item = {}
        for kind, limit in (('screenshot', 2.0), ('linearScreenshot', 0.003)):
            if any(kind not in r or not Path(r[kind]).is_file()
                   or lab.digest(Path(r[kind])) != r['sha256'].get(kind) for r in (row, other)):
                failures.append(row['case'] + ': missing or changed ' + kind)
                continue
            paths = [Path(r[kind]) for r in (row, other)]
            values = [np.asarray(Image.open(p).convert('RGB')) if kind == 'screenshot'
                      else read_pfm(p) for p in paths]
            delta = np.abs(values[0].astype(np.float64) - values[1].astype(np.float64))
            item[kind] = dict(maximumError=float(delta.max()),
                              channelsOverLimit=int(np.count_nonzero(delta > limit)), limit=limit)
            if np.any(delta > limit):
                failures.append(row['case'] + ': ' + kind + ' exceeds full-frame limit')
        checks[row['case']] = item
    return dict(status='fail' if failures else 'pass', failures=failures, cases=checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--basepath', type=Path, required=True)
    parser.add_argument('--backend', choices=('gl', 'vk'), required=True)
    parser.add_argument('--samples', choices=(0, 4), type=int, default=0)
    parser.add_argument('--compare-gl-report', type=Path)
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    args.runtime_root, args.output_dir = args.runtime_root.resolve(), args.output_dir.resolve()
    source_hash = lab.digest(Path(__file__))
    manifest = json.loads((args.runtime_root / 'pbr-lab.json').read_text())
    lab.BASE.update(image_anisotropy='1')
    profile = {}
    for suffix in CASES:
        name = 'cutout-mip-' + suffix
        settings = dict(r_pbrIBL='0', r_rendererReflectionProbes='0', r_useLightGrid='0',
                        r_pbrDebug='7', r_hdrToneMap='1', r_msaaAlphaToCoverage='0',
                        r_multiSamples=str(args.samples), image_anisotropy='1')
        commands = ['g_stopTime 0']
        if not profile:
            commands += [f'script "${s["name"]}.hide()"' for s in manifest['stations']]
            commands += [f'script "${s}.Off()"' for s in ('key', 'blue_fill', 'warm_fill', 'lab_projector')]
        if suffix in ('near', 'minified', 'opaque', 'restored', 'near-restored'):
            if profile:
                commands += ['script "$cutout_mip_specimen.remove()"', 'wait 3']
            model = lab.lab.MODEL if suffix.startswith('near') else MODEL
            material = 'data_scalar' if suffix == 'opaque' else 'cutout'
            commands += [f'spawn func_static name cutout_mip_specimen model "{model}" '
                         f'shader "{lab.lab.PREFIX}/{material}" origin "0 160 390" angle 0 solid 0']
        commands += {'image-reload': ['reloadImages all'],
                     'partial-restart': ['vid_restart partial'],
                     'full-restart': ['vid_restart']}.get(suffix, [])
        commands += ['wait 60', 'g_stopTime 1']
        lab.CASES[name], lab.CASE_COMMANDS[name] = settings, commands
        profile[name] = dict(settings={**lab.BASE, **settings}, commands=commands)
    model_path = args.output_dir / 'batch/baseoq4' / MODEL
    write = lab.write_capture_commands
    def write_commands(path, commands):
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_text(lab.lab.sphere_ase(uv_scale=256, uv_offset=2.375), encoding='utf-8')
        return write(path, commands)
    lab.write_capture_commands = write_commands
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
    report.update(cutoutProfile=profile, cutoutModelSHA256=lab.digest(model_path),
                  requestedSamples=args.samples)
    report['cutoutProof'] = prove(report, args.samples)
    if args.compare_gl_report:
        report['cutoutComparison'] = compare(report, json.loads(args.compare_gl_report.read_text()))
        report['cutoutReferenceReportSHA256'] = lab.digest(args.compare_gl_report)
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('cutoutProof', 'cutoutComparison') if key in report}, indent=2))
    return int(code or report['cutoutProof']['status'] != 'pass'
               or report.get('cutoutComparison', {}).get('status', 'pass') != 'pass')


if __name__ == '__main__':
    raise SystemExit(main())
