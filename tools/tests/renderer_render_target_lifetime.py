#!/usr/bin/env python3
"""Exercise real PBR frames beyond the OpenGL render-target cache capacity.

Uses engine screenshots, a hidden window, no input injection, and the existing
PBR fixture. Both object allocation paths must survive size/HDR changes, restore
the original image exactly, and retain the requested multisample coverage.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

import numpy as np
from PIL import Image

import renderer_smaa_orientation as smaa

lab = smaa.lab


def configure(manifest, samples):
    source = smaa.configure(manifest, samples)
    setup = next(iter(source.values()))['commands']
    base = source['smaa-material1-hdr1-aa4']['settings']
    profile = {}

    def add(name, scale=100, hdr=1, commands=None, reference=None):
        profile[name] = dict(settings={**base, 'r_screenFraction': str(scale),
            'r_hdrToneMap': str(hdr)}, commands=commands or [], reference=reference)

    add('targets-baseline', commands=setup)
    for hdr, label, scales in ((1, 'hdr', range(50, 201, 10)),
                               (0, 'preview', range(200, 49, -10))):
        for scale in scales:
            add(f'targets-{label}-{scale}', scale=scale, hdr=hdr)
        add(f'targets-{label}-restored', hdr=hdr,
            reference='targets-baseline' if hdr else 'targets-preview-100')
    add('targets-baseline-restored', reference='targets-baseline')
    for boundary in ('image-reload', 'partial-restart', 'full-restart'):
        add('targets-' + boundary, commands=lab.CASE_COMMANDS[boundary],
            reference='targets-baseline')
    return profile


def qualify(report, profile, samples, code):
    failures, checks, images = [], {}, {}
    if code or not report.get('complete') or not report.get('runtimeUnchanged'):
        failures.append('incomplete run or changed runtime')
    if {r['case'] for r in report['results']} != set(profile):
        failures.append('captured case set differs from requested profile')
    for row in report['results']:
        name = row['case']
        spec = profile[name]
        failures.extend(name + ': ' + f for f in row['failures'])
        text = Path(row['log']).read_text(errors='replace')
        if (f'TARGET_LIFETIME_{name}_BEGIN' not in text
                or f'TARGET_LIFETIME_{name}_END' not in text):
            failures.append(name + ': resource dump markers missing')
            continue
        graph = text.split(f'TARGET_LIFETIME_{name}_BEGIN', 1)[-1].split(
            f'TARGET_LIFETIME_{name}_END', 1)[0]
        section = text.split(f'PBRLAB_{name}_BEGIN', 1)[-1].split(f'PBRLAB_{name}_END', 1)[0]
        match = re.search(r'RenderGraphResource dump: prepared=1 .*?physical=(\d+) '
            r'.*?revision=(\d+) .*?failures=0 overflow=0 ', graph)
        if not match:
            failures.append(name + ': graph allocation or lifetime failed')
            continue
        count, revision = map(int, match.groups())
        checks[name] = dict(physicalAllocations=count, allocationRevision=revision)
        if not 1 <= count <= 64:
            failures.append(name + ': render-target cache exceeded its bound')
        if not re.search(rf'Renderer AA: MSAA requested={samples} effective={samples}\b', section):
            failures.append(name + ': requested multisample coverage was lost')
        try:
            with Image.open(row['screenshot']) as im:
                rgb = np.asarray(im.convert('RGB'))
            if rgb.shape != (800, 1280, 3):
                raise ValueError('wrong screenshot extent')
            mask = rgb[100:680, 400:880].max(axis=2) > 64
            if int(mask.sum()) < 10000:
                raise ValueError('PBR specimen disappeared')
            images[name] = rgb
        except (OSError, ValueError) as exc:
            failures.append(name + ': ' + str(exc))
            continue
        reference = spec['reference']
        if reference:
            equal = np.array_equal(rgb, images.get(reference))
            checks[name]['restoredExactly'] = equal
            if not equal:
                failures.append(name + ': restored image differs')
    start = checks.get('targets-baseline', {})
    end = checks.get('targets-baseline-restored', {})
    retired = end.get('allocationRevision', 0) - start.get('allocationRevision', 0)
    if retired < 64:
        failures.append('run did not recycle at least one full cache before restart')
    return dict(status='fail' if failures else 'pass', retiredAllocations=retired,
                checks=checks, failures=failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime-root', 'output-dir', 'basepath'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--tier', choices=('gl33', 'gl45'), default='gl45')
    parser.add_argument('--samples', type=int, choices=(0, 4, 8), default=4)
    args = parser.parse_args()
    manifest = json.loads((args.runtime_root / 'pbr-lab.json').read_text())
    profile = configure(manifest, args.samples)
    for name, spec in profile.items():
        lab.CASES[name] = spec['settings']
        lab.CASE_CAMERAS[name] = 'sampling'
        lab.CASE_COMMANDS[name] = [*spec['commands'], 'wait 30',
            f'echo "TARGET_LIFETIME_{name}_BEGIN"', 'rendererRenderGraphResourceDump',
            f'echo "TARGET_LIFETIME_{name}_END"']
    sys.argv = [__file__, '--runtime-root', str(args.runtime_root), '--output-dir', str(args.output_dir),
        '--basepath', str(args.basepath), '--backend', 'gl', '--tier', args.tier,
        '--camera', 'sampling', '--batch', '--gl-debug', '--cases', ','.join(profile), '--timeout', '900']
    code = lab.main()
    path = args.output_dir / 'report.json'
    report = json.loads(path.read_text())
    report.update(renderTargetProfile=profile, requestedSamples=args.samples,
        renderTargetProof=qualify(report, profile, args.samples, code))
    for source in (Path(__file__), Path(smaa.__file__), Path(smaa.scene.__file__)):
        shutil.copy2(source, args.output_dir / 'harness' / source.name)
        report['harnessSources'][source.name] = lab.digest(source)
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=report['renderTargetProof']['status'], cases=len(profile),
        retiredAllocations=report['renderTargetProof']['retiredAllocations'],
        failures=report['renderTargetProof']['failures']), indent=2), flush=True)
    return int(bool(code or report['renderTargetProof']['failures']))


if __name__ == '__main__':
    raise SystemExit(main())
