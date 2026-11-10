#!/usr/bin/env python3
"""Qualify engine PFM radiance, orientation, frame preservation and invalidation.

Uses the original PBR laboratory, isolated writable data and engine screenshot
commands. The PFM reader supports scene extents without weakening the laboratory's
existing fixed-size capture contract. No window capture or input control is used.
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


def read_pfm(path):
    header = path.read_bytes().split(b'\n', 3)
    if len(header) != 4 or header[0] != b'PF' or header[2] != b'-1.0':
        raise ValueError('invalid little-endian RGB PFM header')
    width, height = map(int, header[1].split())
    if not (1 <= width <= 8192 and 1 <= height <= 8192) or len(header[3]) != width * height * 12:
        raise ValueError('invalid PFM extent or payload size')
    rgb = np.frombuffer(header[3], dtype='<f4').reshape(height, width, 3)[::-1]
    if not np.isfinite(rgb).all() or np.min(rgb) < 0:
        raise ValueError('nonfinite or negative linear radiance')
    return rgb


def capture_commands(name):
    return [f'echo "LINEAR_CAPTURE_{name}_BEGIN"', 'gfxInfo', 'rendererVulkanHDRInfo',
            f'screenshot linear "screenshots/{name}.pfm"',
            f'echo "LINEAR_CAPTURE_{name}_END"']


def configure(manifest, samples, suite, backend):
    lab.BASE.update(r_screenFraction='100', r_resolutionScaleMode='1', r_vkHDRPrepareFailure='0')
    composition = scene.configure_composition(manifest, samples)
    if suite == 'composition':
        profile = {name: dict(spec, extent=[1280, 800], capture=True, centreY=400)
                   for name, spec in composition.items()}
        profile['linear-composition-extreme_emissive-6-clear'] = dict(
            next(iter(profile.values())), material='extreme_emissive', mode=6, effect='clear',
            settings={**next(iter(profile.values()))['settings'], 'r_pbrDebug': '6'},
            commands=['g_stopTime 0',
                'script "$linear_specimen_19.hide(); $linear_specimen_19.remove(); $linear_overlay_19.remove()"',
                'wait 30', f'spawn func_static name linear_extreme model "{lab.lab.MODEL}" '
                f'shader "{lab.lab.PREFIX}/extreme_emissive" origin "0 -700 380" angle 0 solid 0',
                'wait 30', 'g_stopTime 1'])
        return profile
    base = next(iter(composition.values()))
    profile = {}

    def add(name, settings=None, commands=None, reference=None, capture=True, extent=(1280, 800), centre=400):
        profile['linear-capture-' + name] = dict(settings={**base['settings'], **(settings or {})},
            commands=commands or [], reference='linear-capture-' + reference if reference else None,
            capture=capture, extent=list(extent), centreY=centre)

    def move(z):
        return ['g_stopTime 0', f'script "$linear_specimen_0.setOrigin(\'0 -700 {z}\')"',
                'wait 60', 'g_stopTime 1']

    add('baseline', commands=base['commands'])
    add('quarter-exposure', {'r_hdrExposure': '.25'}, reference='baseline')
    add('bloom', {'r_bloom': '1'}, reference='baseline')
    for asynchronous in (0, 1):
        add('auto-' + str(asynchronous), {'r_hdrAutoExposure': '1', 'r_hdrAutoExposureAsync': str(asynchronous),
            'r_hdrMinExposure': '.25', 'r_hdrMaxExposure': '.25'}, reference='baseline')
    add('above', commands=move(440), centre=318)
    add('above-half', {'r_screenFraction': '50'}, extent=(640, 400), centre=159)
    add('below-three-quarter', {'r_screenFraction': '75'}, commands=move(320), extent=(960, 600), centre=362.25)
    add('large', {'r_screenFraction': '125'}, commands=move(380), extent=(1600, 1000), centre=500)
    add('scale-restored', reference='baseline')
    for boundary in ('image-reload', 'partial-restart', 'full-restart'):
        add(boundary, commands=lab.CASE_COMMANDS[boundary], reference='baseline')
    # The small capture leaves its frame open; immediately restart afterwards.
    add('resize', commands=[
        'r_windowWidth 960', 'r_windowHeight 600', 'vid_restart partial', 'wait 60',
        *capture_commands('linear-capture-small'), 'screenshot "screenshots/linear-capture-small.tga"',
        'r_windowWidth 1280', 'r_windowHeight 800', 'vid_restart partial', 'wait 60'], reference='baseline')
    add('repeat', commands=[*capture_commands('linear-capture-repeat-a'),
        *capture_commands('linear-capture-repeat-b'), 'screenshot "screenshots/linear-capture-interleave.tga"',
        *capture_commands('linear-capture-repeat-c')], reference='baseline')
    add('invalid-paths', commands=['echo LINEAR_PATH_BEGIN',
        'screenshot linear "screenshots/../capture-denied.pfm"',
        'screenshot linear "screenshots/capture-denied.tga"',
        'screenshot linear "capture-denied.pfm"', 'echo LINEAR_PATH_END'], reference='baseline')
    add('ldr', {'r_hdrToneMap': '0'}, capture=False)
    if backend == 'vk':
        add('declined-post', {'r_motionBlur': '1'}, capture=False)
        add('declined-preparation', {'r_vkHDRPrepareFailure': '3'}, capture=False)
    add('restored', reference='baseline')
    return profile


def fields(section, prefix):
    return dict(re.findall(r'(\w+)=([^\s]+)', next((line for line in section.splitlines()
                if line.startswith(prefix)), '')))


def qualify(report, profile, args):
    failures, checks, images = [], {}, {}
    if not report.get('complete') or not report.get('runtimeUnchanged'):
        failures.append('incomplete sequence or changed runtime')
    for row in report['results']:
        name, spec = row['case'], profile[row['case']]
        failures.extend(name + ': ' + error for error in row['failures'])
        log = Path(row['log']).read_text(errors='replace')
        section = log.split(f'LINEAR_CAPTURE_{name}_BEGIN', 1)[-1].split(f'LINEAR_CAPTURE_{name}_END', 1)[0]
        if f'LINEAR_CAPTURE_{name}_END' not in log:
            failures.append(name + ': missing capture markers')
        # The admitted modern scene retains the requested sample coverage at
        # every scale, including supersampling. A lower count is not equivalent.
        if not re.search(rf'Renderer AA: MSAA requested={args.samples} effective={args.samples}\b', section):
            failures.append(name + ': requested sample count not active')
        path = Path(row['screenshot']).with_suffix('.pfm')
        if not spec['capture']:
            checks[name] = dict(rejected=not path.exists() and
                'screenshot linear: no completed modern HDR scene' in section)
            if not checks[name]['rejected']:
                failures.append(name + ': stale or unsupported capture was not rejected')
            continue
        try:
            rgb = read_pfm(path)
        except (OSError, ValueError) as error:
            failures.append(name + ': ' + str(error))
            continue
        images[name] = rgb
        height, width, _ = rgb.shape
        checks[name] = dict(path=str(path), sha256=lab.digest(path), extent=[width, height], peak=float(rgb.max()))
        if [width, height] != spec['extent']:
            failures.append(name + ': unexpected scene capture extent')
        if args.backend == 'vk':
            owner = fields(section, 'Vulkan HDR scene ownership:')
            if owner.get('committed') != '1' or owner.get('reason') != 'complete':
                failures.append(name + ': native scene did not complete ownership')
        if args.suite == 'lifecycle' or spec['effect'] == 'clear':
            key = f'{spec["material"]}-{spec["mode"]}' if args.suite == 'composition' else 'data_scalar-1'
            expected = {'data_scalar-1': [scene.decode(188)] * 3, 'data_scalar-7': [0, 1, 0],
                'emissive-6': [scene.decode(c) * 4 for c in (30, 200, 255)],
                'source_alpha-1': [scene.decode(c) * 112 / 255 for c in (50, 180, 255)],
                'extreme_emissive-6': [min(65504, scene.decode(c) * 1000000) for c in (30, 200, 255)]}[key]
            y = round(spec['centreY'])
            patch = rgb[y-3:y+4, width//2-3:width//2+4]
            error = float(np.max(np.abs(patch - expected)))
            checks[name]['radiance'] = dict(expected=expected, actual=patch.mean(axis=(0, 1)).tolist(), maximumError=error)
            tolerance = np.maximum(.005, np.asarray(expected) * .002) if key == 'extreme_emissive-6' else .005
            if np.any(np.abs(patch - expected) > tolerance):
                failures.append(name + ': incorrect independent linear radiance')
        if args.suite == 'lifecycle':
            ys, _ = np.nonzero(rgb[:, :, 0] > .25)
            centroid = float(ys.mean()) if len(ys) else None
            checks[name]['orientation'] = dict(expectedY=spec['centreY'], actualY=centroid, pixels=len(ys))
            if centroid is None or len(ys) < 1000 or abs(centroid - spec['centreY']) > 3:
                failures.append(name + ': incorrect bottom-up PFM orientation')
        reference = spec.get('reference')
        if reference and (reference not in images or not np.array_equal(rgb, images[reference])):
            failures.append(name + ': linear radiance did not restore exactly')
    if args.suite == 'composition':
        for name, rgb in images.items():
            effect = profile[name]['effect']
            if effect.endswith('-shared'):
                baseline = images.get(name.removesuffix('-shared'))
                # Equivalent fog walks can round one FP16 storage step apart
                # (observed with 4x GL); do not require bit-identical floats.
                # Compare encoded half steps across every nonnegative channel,
                # retaining a tighter bound than the cross-backend radiance gate.
                steps = (np.abs(rgb.astype(np.float16).view(np.uint16).astype(np.int32)
                    - baseline.astype(np.float16).view(np.uint16).astype(np.int32))
                    if baseline is not None else np.array([65535]))
                checks[name]['sharedMaximumHalfFloatSteps'] = int(steps.max())
                if steps.max() > 1:
                    failures.append(name + ': shared fog/blend switch changed radiance beyond one FP16 step')
            elif effect != 'clear':
                baseline = images.get(name.rsplit('-', 1)[0] + '-clear')
                change = float(np.max(np.abs(rgb - baseline))) if baseline is not None else 0
                checks[name]['overlayMaximumChange'] = change
                # Authored blend lights walk opaque local/global interaction
                # chains on both backends, never translucentInteractions.
                transparent_blend = effect == 'blend' and profile[name]['material'] == 'source_alpha'
                if transparent_blend and change != 0:
                    failures.append(name + ': blend light changed excluded translucent surface')
                elif not transparent_blend and change < .01:
                    failures.append(name + ': fog/blend absent from completed scene')
                if effect == 'blend' and not transparent_blend and baseline is not None:
                    error = float(np.max(np.abs(rgb[397:404, 637:644]
                        - baseline[397:404, 637:644] * (.4, .7, .2))))
                    checks[name]['blendMaximumRadianceError'] = error
                    if error > .005:
                        failures.append(name + ': authored blend did not multiply linear radiance once')
    if args.suite == 'lifecycle' and not args.limit:
        shots = Path(report['results'][0]['screenshot']).parent
        baseline = images.get('linear-capture-baseline')
        for suffix in ('repeat-a', 'repeat-b', 'repeat-c', 'small'):
            path = shots / ('linear-capture-' + suffix + '.pfm')
            try:
                rgb = read_pfm(path)
                expected = (600, 960, 3) if suffix == 'small' else baseline.shape
                checks[suffix] = dict(sha256=lab.digest(path), extent=list(rgb.shape[1::-1]))
                if rgb.shape != expected:
                    failures.append(suffix + ': wrong auxiliary capture extent')
                elif suffix != 'small' and not np.array_equal(rgb, baseline):
                    failures.append(suffix + ': repeated capture changed linear scene')
            except (OSError, ValueError) as error:
                failures.append(suffix + ': ' + str(error))
        with Image.open(shots / 'linear-capture-interleave.tga') as a, Image.open(shots / 'linear-capture-repeat.tga') as b:
            if not np.array_equal(np.asarray(a), np.asarray(b)):
                failures.append('float capture changed the ordinary screenshot')
        section = log.split('LINEAR_PATH_BEGIN', 1)[-1].split('LINEAR_PATH_END', 1)[0]
        if section.count('screenshot linear: use screenshots/<name>.pfm') != 3:
            failures.append('invalid screenshot paths were not rejected')
        for path in (shots / 'capture-denied.tga', shots.parent / 'capture-denied.pfm'):
            if path.exists():
                failures.append('invalid path created an output file: ' + str(path))
    return dict(status='fail' if failures else 'pass', checks=checks, failures=failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime-root', 'output-dir', 'basepath'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--backend', choices=('gl', 'vk'), default='vk')
    parser.add_argument('--samples', type=int, choices=(0, 4), default=0)
    parser.add_argument('--suite', choices=('composition', 'lifecycle'), default='composition')
    parser.add_argument('--limit', type=int, help='Explicitly recorded bring-up subset.')
    args = parser.parse_args()
    manifest = json.loads((args.runtime_root / 'pbr-lab.json').read_text())
    profile = configure(manifest, args.samples, args.suite, args.backend)
    if args.limit:
        profile = dict(list(profile.items())[:args.limit])
    for name, spec in profile.items():
        lab.CASES[name] = spec['settings']
        lab.CASE_CAMERAS[name] = 'sampling'
        lab.CASE_COMMANDS[name] = [*spec['commands'], 'wait 30', *capture_commands(name)]
    sys.argv = [__file__, '--runtime-root', str(args.runtime_root), '--output-dir', str(args.output_dir),
                '--basepath', str(args.basepath), '--backend', args.backend, '--camera', 'sampling',
                '--batch', '--cases', ','.join(profile), '--timeout', '900']
    if args.backend == 'gl':
        # HDR info is a native command; gfxInfo carries the GL evidence.
        for name in profile:
            lab.CASE_COMMANDS[name] = [cmd for cmd in lab.CASE_COMMANDS[name] if cmd != 'rendererVulkanHDRInfo']
        sys.argv.append('--gl-debug')
    code = lab.main()
    path = args.output_dir / 'report.json'
    report = json.loads(path.read_text())
    report.update(linearCaptureProfile=profile, requestedSamples=args.samples, limited=args.limit,
                  linearCaptureProof=qualify(report, profile, args))
    for source in (Path(__file__), Path(scene.__file__)):
        shutil.copy2(source, args.output_dir / 'harness' / source.name)
        report['harnessSources'][source.name] = lab.digest(source)
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=report['linearCaptureProof']['status'], cases=len(profile),
                         failures=report['linearCaptureProof']['failures']), indent=2), flush=True)
    return int(bool(code or report['linearCaptureProof']['failures']))


if __name__ == '__main__':
    raise SystemExit(main())
