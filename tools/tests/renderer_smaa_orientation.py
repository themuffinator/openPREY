#!/usr/bin/env python3
"""Check SMAA orientation in real classic/PBR scenes and after resource changes.

The off-centre emissive specimen makes a vertically inverted world observable.
Engine screenshots only; windowed, hidden and with mouse/joystick input disabled.
Use the original PBR laboratory's reusable runtime and isolated writable data.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

import numpy as np
from PIL import Image

import renderer_vulkan_hdr_scene as scene

lab = scene.lab


def configure(manifest, samples):
    # Freeze from startup, then advance a fixed number of simulation tics for
    # fixture setup. HUD animations must use the same time on both backends.
    lab.BASE.update(r_screenFraction='100', r_temporalAA='0', com_fixedTic='1', g_stopTime='1')
    base = next(iter(scene.configure_composition(manifest, samples).values()))
    setup = [cmd.replace('/data_scalar', '/emissive').replace('0 -700 380', '0 -700 440')
             if cmd.startswith('spawn func_static ') else cmd for cmd in base['commands']]
    profile = {}

    def add(name, settings, commands=None, extent=(1280, 800), centre=317.57, reference=None):
        profile[name] = dict(settings=settings, commands=commands or [], extent=list(extent),
                             centreY=centre, reference=reference)

    for pbr in (0, 1):
        for hdr in (0, 1):
            for aa in range(5):
                settings = {**base['settings'], 'r_pbrMaterials': str(pbr),
                    'r_rendererModernSubmit': str(pbr), 'r_pbrDebug': '6' if pbr else '0',
                    'r_hdrToneMap': str(hdr), 'r_postAA': str(aa),
                    'g_renderFastNoPostDirect': '0', 'r_screenFraction': '100',
                    'r_temporalAA': '0', 'g_showHud': '0'}
                add(f'smaa-material{pbr}-hdr{hdr}-aa{aa}', settings, setup if not profile else [])
    reference = 'smaa-material1-hdr1-aa4'
    base = profile[reference]['settings']
    for scale in (50, 75, 125, 150, 200):
        add('smaa-scale-' + str(scale), {**base, 'r_screenFraction': str(scale)})
    add('smaa-scale-restored', dict(base), reference=reference)
    for boundary in ('image-reload', 'partial-restart', 'full-restart'):
        add('smaa-' + boundary, dict(base), lab.CASE_COMMANDS[boundary], reference=reference)
    add('smaa-hud', {**base, 'g_showHud': '1'})
    add('smaa-hud-restored', dict(base), reference=reference)
    return profile


def qualify(report, profile, backend, samples, code):
    failures, checks, images = [], {}, {}
    if code or not report.get('complete') or not report.get('runtimeUnchanged'):
        failures.append('laboratory failed, incomplete sequence, or changed runtime')
    if {row['case'] for row in report['results']} != set(profile):
        failures.append('captured case set differs from requested profile')
    for row in report['results']:
        name, spec = row['case'], profile[row['case']]
        failures.extend(name + ': ' + f for f in row['failures'])
        log = Path(row['log']).read_text(errors='replace')
        section = log.split(f'PBRLAB_{name}_BEGIN', 1)[-1].split(f'PBRLAB_{name}_END', 1)[0]
        if not re.search(rf'Renderer AA: MSAA requested={samples} effective={samples}\b', section):
            failures.append(name + ': effective MSAA differs from requested policy')
        aa = int(spec['settings']['r_postAA'])
        if not re.search(rf'PostAA={aa}\([^)]*\) postAAEffective={int(aa > 0)}\b', section):
            failures.append(name + ': effective SMAA was not reported')
        try:
            with Image.open(row['screenshot']) as im:
                rgb = np.asarray(im.convert('RGB'))
            height, width = rgb.shape[:2]
            if [width, height] != spec['extent']:
                raise ValueError('wrong engine screenshot extent')
        except (OSError, ValueError) as exc:
            failures.append(name + ': ' + str(exc))
            continue
        images[name] = rgb
        # Ignore the HUD margins; the specimen must remain above centre.
        mask = rgb.max(axis=2) > 64
        mask[:, :400] = False
        mask[:, 880:] = False
        mask[:100] = False
        mask[680:] = False
        ys, xs = np.where(mask)
        centroid = [float(xs.mean()), float(ys.mean())] if len(xs) else None
        upright = bool(centroid and len(xs) > 10000 and abs(centroid[1] - spec['centreY']) < 4)
        checks[name] = dict(pixels=int(len(xs)), centroid=centroid, upright=upright)
        if not upright:
            failures.append(name + ': specimen disappeared or changed orientation')
        if spec['reference']:
            equal = np.array_equal(rgb, images.get(spec['reference']))
            checks[name]['restoredExactly'] = equal
            if not equal:
                failures.append(name + ': image changed across a resource boundary')
    for pbr in (0, 1):
        for hdr in (0, 1):
            off = images.get(f'smaa-material{pbr}-hdr{hdr}-aa0')
            for aa in range(1, 5):
                name = f'smaa-material{pbr}-hdr{hdr}-aa{aa}'
                if name in images and off is not None:
                    changed = int(np.count_nonzero(images[name] != off))
                    checks[name]['changedChannelsFromOff'] = changed
                    if changed < 100:
                        failures.append(name + ': no visible SMAA effect')
    hud = images.get('smaa-hud')
    restored = images.get('smaa-hud-restored')
    if hud is not None and restored is not None:
        changed = int(np.count_nonzero(hud != restored))
        checks['smaa-hud']['changedChannelsFromHidden'] = changed
        if changed < 100:
            failures.append('stock HUD was not visible')
    return dict(status='fail' if failures else 'pass', checks=checks, failures=failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime-root', 'output-dir', 'basepath'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--backend', choices=('gl', 'vk'), default='vk')
    parser.add_argument('--samples', type=int, choices=(0, 4, 8), default=0)
    args = parser.parse_args()
    manifest = json.loads((args.runtime_root / 'pbr-lab.json').read_text())
    profile = configure(manifest, args.samples)
    for name, spec in profile.items():
        lab.CASES[name] = spec['settings']
        lab.CASE_CAMERAS[name] = 'sampling'
        lab.CASE_COMMANDS[name] = [*spec['commands'], 'wait 30']
        if spec['settings']['r_pbrMaterials'] == '0':
            lab.LEGACY_CASES.add(name)
    sys.argv = [__file__, '--runtime-root', str(args.runtime_root), '--output-dir', str(args.output_dir),
                '--basepath', str(args.basepath), '--backend', args.backend, '--camera', 'sampling',
                '--batch', '--cases', ','.join(profile), '--timeout', '900']
    if args.backend == 'gl':
        sys.argv.append('--gl-debug')
    code = lab.main()
    path = args.output_dir / 'report.json'
    report = json.loads(path.read_text())
    report.update(smaaProfile=profile, requestedSamples=args.samples,
                  smaaProof=qualify(report, profile, args.backend, args.samples, code))
    for source in (Path(__file__), Path(scene.__file__)):
        shutil.copy2(source, args.output_dir / 'harness' / source.name)
        report['harnessSources'][source.name] = lab.digest(source)
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=report['smaaProof']['status'], cases=len(profile),
                         failures=report['smaaProof']['failures']), indent=2), flush=True)
    return int(bool(code or report['smaaProof']['failures']))


if __name__ == '__main__':
    raise SystemExit(main())
