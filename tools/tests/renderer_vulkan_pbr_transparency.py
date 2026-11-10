#!/usr/bin/env python3
"""Windowed Vulkan PBR opacity, partial-light and shared-model instance proof.

Use an immutable runtime prepared by renderer_pbr_laboratory.py --prepare.
Captures use the engine screenshot command, with no mouse/keyboard input.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

import renderer_pbr_laboratory as lab


def light_commands(reverse: bool = False) -> list[str]:
    positions = [('left', -70), ('right', 70)]
    if reverse:
        positions.reverse()
    return [f'spawn light name alpha_{side} origin "{x} -1000 380" angle 0 '
            'texture "lights/openq4/pbr_lab/projected" light_target "0 300 0" '
            'light_right "70 0 0" light_up "0 0 100" light_start "0 1 0" '
            'light_end "0 340 0" _color "1 1 1" noshadows 1' for side, x in positions]


def configure(manifest: dict, samples: int) -> list[str]:
    cases = [(mode, light) for mode in ('owned', 'black', 'lit', 'ibl')
             for light in ('none', 'left', 'right', 'both', 'restored')]
    cases += [('lit', boundary) for boundary in
              ('image-reload', 'partial-restart', 'full-restart', 'reversed', 'reverse-restored')]
    order = []
    for mode, light in cases:
        name = f'alpha-{mode}-{light}'
        order.append(name)
        lab.CASES[name] = {'r_pbrIBL':'1' if mode == 'ibl' else '0', 'r_pbrIBLIntensity':'0.5',
                          'r_rendererReflectionProbes':'0', 'r_lightScale':'0.25',
                          'r_pbrDebug':{'owned':'7', 'black':'6'}.get(mode, '0'),
                          'r_multiSamples':str(samples)}
        commands = ['g_stopTime 0']
        if name == 'alpha-owned-none':
            commands += ['script "'+'; '.join('$'+s['name']+'.hide()' for s in manifest['stations'])+'"']
            commands += [f'script "${source}.Off()"' for source in ('key','blue_fill','warm_fill','lab_projector')]
            # The second instance shares model triangles with the first, but
            # lies wholly outside both projectors' receiver volumes.
            for suffix, x in (('specimen',0), ('instance',240)):
                commands += [f'spawn func_static name alpha_{suffix} model "{lab.lab.MODEL}" '
                             f'shader "{lab.lab.PREFIX}/source_alpha" origin "{x} -700 380" solid 0']
            commands += [f'spawn func_static name alpha_backdrop model "{lab.lab.MODEL}" '
                         f'shader "{lab.lab.PREFIX}/emission_half" origin "0 -480 380" solid 0']
            commands += light_commands()
        if light in ('reversed', 'reverse-restored'):
            commands += ['script "$alpha_left.remove(); $alpha_right.remove()"', 'wait 3']
            commands += light_commands(light == 'reversed')
        commands += [f'script "$alpha_backdrop.{"hide" if mode == "owned" else "show"}()"']
        enabled = {'left','right'} if light not in ('none','left','right','restored') else {light}
        commands += [f'script "$alpha_{side}.{"On" if side in enabled else "Off"}()"' for side in ('left','right')]
        commands += ['wait 30', 'g_stopTime 1']
        if light in ('image-reload','partial-restart','full-restart'):
            commands += lab.CASE_COMMANDS[light]
        lab.CASE_COMMANDS[name] = commands
        lab.CASE_CAMERAS[name] = 'sampling'
    return order


def relations(images: dict[str, bytes]) -> tuple[dict, list[str]]:
    """Independent image equations: coverage is light-independent and light is additive."""
    checks, failures = {}, []
    # The fixed sampling camera projects both spheres inside this rectangle.
    # The room's classic geometry below it legitimately responds to the lights.
    foreground = [((y*1280+x)*3+c) for y in range(280,520)
                  for x in range(520,1105) for c in range(3)]
    owned = images['alpha-owned-none']
    material = [i+c for i in range(0,len(owned),3)
                if owned[i] == 0 and owned[i+2] == 0 and owned[i+1] > 0 for c in range(3)]

    def same(left: str, right: str, tolerance: int = 0, foreground_only: bool = False) -> None:
        a, b = images[left], images[right]
        if foreground_only:
            a, b = bytes(a[i] for i in foreground), bytes(b[i] for i in foreground)
        maximum = max(abs(x-y) for x, y in zip(a, b))
        changed = sum(x != y for x, y in zip(a, b))
        checks[f'{left}/{right}'] = {'maximumError':maximum, 'changedChannels':changed,
                                     'scope':'foreground' if foreground_only else 'whole frame'}
        if maximum > tolerance:
            failures.append(f'{left}/{right}: image changed by {maximum} bytes')

    for mode in ('owned','black','lit','ibl'):
        same(f'alpha-{mode}-none', f'alpha-{mode}-restored')
        if mode in ('owned','black'):
            for light in ('left','right','both'):
                same(f'alpha-{mode}-none', f'alpha-{mode}-{light}', foreground_only=True)
    # The authored texture alpha is 112/255. This is a full-surface mask,
    # not merely a center pixel that both light subsets might happen to cover.
    pixels = sum(owned[i:i+3] == bytes((0,112,0)) for i in range(0,len(owned),3))
    checks['ownedCoveragePixels'] = pixels
    if pixels < 40000:
        failures.append('both complete transparent specimens must be present at authored alpha')

    for mode in ('lit','ibl'):
        dark, left, right, both = [images[f'alpha-{mode}-{name}'] for name in ('none','left','right','both')]
        maximum = max(abs(b-l-r+d) for d,l,r,b in zip(dark,left,right,both))
        checks[mode+'Additivity'] = {'maximumError':maximum}
        if maximum > 2:
            failures.append(f'{mode}: summed lights violate source-alpha composition ({maximum})')
        for name, image in (('left',left),('right',right)):
            changed = sum(abs(image[i]-dark[i])>2 for i in material)
            checks[mode+'-'+name+'EffectChannels'] = changed
            if changed < 1000:
                failures.append(f'{mode}/{name}: the projected light had no meaningful effect')
        # x>=835 contains the unlit instance; the lit sphere ends near x=739.
        # A different object's records must not contribute to this instance.
        for name, image in (('left',left),('right',right),('both',both)):
            errors = [abs(image[(y*1280+x)*3+c]-dark[(y*1280+x)*3+c])
                      for y in range(270,531) for x in range(835,1140) for c in range(3)]
            maximum = max(errors)
            checks[mode+'-'+name+'InstanceMaximum'] = maximum
            if maximum:
                failures.append(f'{mode}/{name}: unrelated instance received another entity\'s light ({maximum})')
    if max(images['alpha-black-none']) < 20:
        failures.append('opacity control needs a visible emissive background')
    effect = sum(abs(images['alpha-ibl-none'][i]-images['alpha-lit-none'][i])>2 for i in material)
    checks['environmentEffectChannels'] = effect
    if effect < 1000:
        failures.append('environment contribution is missing')
    for boundary in ('image-reload','partial-restart','full-restart','reversed','reverse-restored'):
        same('alpha-lit-both', 'alpha-lit-'+boundary, 1 if boundary == 'reversed' else 0)
    return checks, failures


def qualify(report: dict, samples: int) -> dict:
    failures = []
    images = {}
    for row in report['results']:
        path = Path(row['screenshot'])
        if not path.is_file() or lab.digest(path) != row['sha256']['screenshot']:
            failures.append(f'{row["case"]}: capture provenance changed')
            continue
        image = lab.capture_rgb(path)
        if image is None:
            failures.append(f'{row["case"]}: invalid capture')
            continue
        images[row['case']] = image
        if row['failures']:
            failures.append(f'{row["case"]}: capture qualification failed')
        log = Path(row['log'])
        if not log.is_file() or lab.digest(log) != row['sha256']['log']:
            failures.append(f'{row["case"]}: log provenance changed')
        elif samples == 4 and 'Renderer AA: MSAA requested=4 effective=4' not in log.read_text(errors='replace'):
            failures.append(f'{row["case"]}: four-sample MSAA not active')
    if not report.get('complete') or not report.get('runtimeUnchanged'):
        failures.append('runtime changed or capture sequence incomplete')
    checks = {}
    if not failures:
        try:
            checks, failures = relations(images)
        except KeyError as error:
            failures.append(f'missing control {error}')
    return {'status':'fail' if failures else 'pass', 'checks':checks, 'failures':failures}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--basepath', type=Path, required=True)
    parser.add_argument('--samples', type=int, choices=(0,4), default=0)
    parser.add_argument('--timeout', type=int, default=360)
    args = parser.parse_args()
    args.runtime_root = args.runtime_root.resolve()
    args.output_dir = args.output_dir.resolve()
    manifest = json.loads((args.runtime_root/'pbr-lab.json').read_text())
    cases = configure(manifest, args.samples)
    sys.argv = [__file__, '--runtime-root', str(args.runtime_root), '--output-dir', str(args.output_dir),
                '--basepath', str(args.basepath), '--backend', 'vk', '--camera', 'sampling', '--batch',
                '--cases', ','.join(cases), '--timeout', str(args.timeout)]
    code = lab.main()
    path = args.output_dir/'report.json'
    report = json.loads(path.read_text())
    source = Path(__file__)
    shutil.copy2(source, args.output_dir/'harness'/source.name)
    report['harnessSources'][source.name] = lab.digest(source)
    report['requestedSamples'] = args.samples
    report['transparencyProof'] = qualify(report, args.samples)
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Vulkan transparency proof:', report['transparencyProof']['status'],
          report['transparencyProof']['failures'], flush=True)
    return int(bool(code or report['transparencyProof']['failures']))


if __name__ == '__main__':
    raise SystemExit(main())
