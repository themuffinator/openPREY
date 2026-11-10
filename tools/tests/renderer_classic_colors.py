#!/usr/bin/env python3
"""Qualify classic stage colors, HDR constants, blending and depth coverage.

Uses original laboratory materials, a sphere with exact RGB vertex colors and
engine screenshots. The classic GL route is explicit: the optional modern GL
executor is not an independent fixed-function reference for these materials.
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
GAINS = {'unit': (1, 1, 1, 1), 'high': (4, 3, 2, 2),
         'mixed': (-2, .5, 4, 1.5), 'low': (.5, .75, .25, .5)}


def configure(manifest, samples=0):
    lab.BASE.update(r_screenFraction='100', r_temporalAA='0', r_portalsDistanceCull='0')
    base = next(iter(scene.configure_composition(manifest, samples).values()))
    setup = [cmd for cmd in base['commands'] if not cmd.startswith('spawn func_static')]
    profile, specimen = {}, None
    # MSAA retains an offscreen scene even without HDR/post processing, so
    # those runs qualify the ordinary owner only.
    for shared in ((0, 1) if samples == 0 else (0,)):
        for mode in ('primary', 'vertex', 'inverse'):
            for blend in ('replace', 'alpha', 'mask'):
                for hdr in ((0,) if shared else (0, 1)):
                    # Both shared adapters deliberately decline offscreen
                    # scene ownership. Exercise their admitted direct LDR
                    # path; the ordinary walker covers floating-point targets.
                    gains = GAINS if not shared else {g: GAINS[g] for g in ('unit', 'high')}
                    for gain, rgba in gains.items():
                        commands = list(setup) if not profile else []
                        commands += ['g_stopTime 0']
                        new = f'color_{shared}_{mode}_{blend}'
                        if specimen != new:
                            if specimen:
                                commands += [f'script "${specimen}.hide(); ${specimen}.remove()"', 'wait 30']
                            specimen = new
                            commands += [f'spawn func_static name {specimen} model "{lab.lab.VERTEX_COLOR_MODEL}" '
                                         f'shader "{lab.lab.PREFIX}/classic_stage_{mode}_{blend}" '
                                         'origin "0 -700 380" angle 0 solid 0', 'wait 30']
                        cutoff = .125 if gain == 'low' else .25 if gain == 'unit' else .5
                        commands += [f'script "${specimen}.setShaderParms(' + ','.join(map(str, rgba))
                                     + f'); ${specimen}.setShaderParm(4,{cutoff})"',
                                     'wait 30', 'g_stopTime 1']
                        name = f'classic-{mode}-{blend}-hdr{hdr}-{gain}' + ('-shared' if shared else '')
                        settings = {**base['settings'], 'r_pbrMaterials': '0', 'r_pbrDebug': '0',
                                    'r_rendererModernSubmit': '0', 'r_rendererModernVisible': '0',
                                    'r_rendererSharedWorldAmbient': str(shared), 'r_hdrToneMap': str(hdr),
                                    'g_renderFastNoPostDirect': str(shared), 'g_showHud': '0',
                                    'r_hdrSceneTarget': str(1 - shared), 'r_portalsDistanceCull': '0'}
                        if samples:
                            # Isolate color and alpha-test semantics from the
                            # separately qualified sample-coverage quantizer.
                            settings['r_msaaAlphaToCoverage'] = '0'
                        profile[name] = dict(mode=mode, blend=blend, hdr=hdr, rgba=list(rgba), cutoff=cutoff,
                                             shared=shared, settings=settings, commands=commands)
    return profile


def expected_patch(spec):
    """Analytic texture * primary/environment color, then blend over black.

    The material inputs are independent of either renderer. The stock shoulder
    leaves values through .5 unchanged, joins with slope one, and maps the
    authored reference white (6) to 1. ASE RGB colors imply opaque vertex alpha.
    """
    color = np.asarray(spec['rgba'], dtype=np.float64)
    texture = np.array((30, 200, 255, 255) if spec['blend'] == 'replace' else (50, 180, 255, 112)) / 255
    if spec['blend'] == 'mask' and texture[3] * np.clip(color[3], 0, 1) <= spec['cutoff']:
        return np.zeros(3)
    if spec['mode'] == 'primary' or not spec['hdr']:
        color = np.clip(color, 0, 1)
    vertex = np.array([64, 128, 192, 255]) / 255
    if spec['mode'] == 'primary': vertex[:] = 1
    if spec['mode'] == 'inverse': vertex[:3] = 1 - vertex[:3]
    fragment = texture * color * vertex
    result = fragment[:3]
    if spec['blend'] == 'alpha': result = result * np.clip(fragment[3], 0, 1)
    result = np.maximum(result, 0)
    if spec['hdr']:
        t = np.maximum(result - .5, 0)
        result = np.where(result <= .5, result, .5 + t / (1 + (2 - 1 / 5.5) * t))
    return np.clip(result, 0, 1) * 255


def qualify(report, profile, backend, samples, code, native_samples=False):
    failures, checks = [], {}
    if code or not report.get('complete') or not report.get('runtimeUnchanged'):
        failures.append('laboratory failed, incomplete sequence, or changed runtime')
    if {r['case'] for r in report['results']} != set(profile):
        failures.append('captured case set differs from the requested profile')
    for row in report['results']:
        name, spec = row['case'], profile[row['case']]
        failures.extend(name + ': ' + f for f in row['failures'])
        log = Path(row['log']).read_text(errors='replace')
        if backend == 'vk':
            locations = re.search(r'Vulkan: MSAA sample locations lower-left-standard counts=0x([0-9a-f]+) native-standard=([01])', log)
            if locations is None:
                failures.append(name + ': sample-location capability report missing')
            else:
                mask = int(locations[1], 16)
                checks['sampleLocations'] = dict(compatibleCounts=mask, nativeStandard=bool(int(locations[2])),
                                                compatibleActive=bool(samples and mask & samples))
                if native_samples and mask:
                    failures.append(name + ': native sample-location fallback was not selected')
        section = log.split(f'PBRLAB_{name}_BEGIN', 1)[-1].split(f'PBRLAB_{name}_END', 1)[0]
        if not re.search(rf'Renderer AA: MSAA requested={samples} effective={samples}\b', section):
            failures.append(name + ': requested MSAA was not effective')
        if backend == 'gl' and not re.search(r'Modern visible frame:.*\bexec=0\b', section):
            failures.append(name + ': modern GL intercepted the classic reference')
        if spec['shared']:
            state = next((line for line in section.splitlines() if line.startswith('Renderer shared world ambient:')), '')
            owned = re.search(rf'\b{backend.upper()}=(\d+)/', state)
            if owned is None or int(owned[1]) == 0:
                failures.append(name + ': shared ambient did not own the draw')
        try:
            rgb = np.asarray(Image.open(row['screenshot']).convert('RGB'))
            if rgb.shape != (800, 1280, 3): raise ValueError('wrong screenshot dimensions')
            patch = rgb[384:416, 624:656]
            expected = expected_patch(spec)
            error = float(np.abs(patch.astype(float) - expected).max())
            outside = rgb.copy()
            outside[280:520, 520:760] = 0
            if outside.max() > 1: failures.append(name + ': scene outside the specimen was not black')
            checks[name] = dict(expected=expected.tolist(), median=np.median(patch, axis=(0, 1)).tolist(),
                                maximumError=error, nonBlackPixels=int(np.count_nonzero(rgb.max(axis=2))))
            if error > 2: failures.append(name + ': analytic color/coverage error exceeds two bytes')
            if expected.max() > 20 and checks[name]['nonBlackPixels'] < 20000:
                failures.append(name + ': missing or incorrectly framed specimen')
        except (OSError, ValueError) as exc:
            failures.append(name + ': ' + str(exc))
    return dict(status='fail' if failures else 'pass', checks=checks, failures=failures)


def compare(reference, candidate):
    failures, pairs = [], {}
    for report in (reference, candidate):
        if report.get('classicColorProof', {}).get('status') != 'pass':
            failures.append('comparison requires two independently qualified runs')
    for key in ('colorProfile', 'fixture', 'compiledMapSHA256', 'requestedSamples'):
        if reference.get(key) != candidate.get(key): failures.append('mismatched ' + key)
    rows = {row['case']: row for row in reference['results']}
    for row in candidate['results']:
        name = row['case']
        if name not in rows:
            failures.append(name + ': missing reference capture')
            continue
        a = np.asarray(Image.open(rows[name]['screenshot']).convert('RGB')).astype(np.int16)
        b = np.asarray(Image.open(row['screenshot']).convert('RGB')).astype(np.int16)
        delta = np.abs(a - b)
        pairs[name] = dict(maximum=int(delta.max()), rms=float(np.sqrt(np.mean(delta.astype(float) ** 2))),
                           changedChannels=int(np.count_nonzero(delta)), overTwoChannels=int(np.count_nonzero(delta > 2)))
        if delta.max() > 2: failures.append(name + ': full-frame color difference exceeds two bytes')
    return dict(status='fail' if failures else 'pass', pairs=pairs, failures=failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime-root', 'output-dir', 'basepath'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--backend', choices=('gl', 'vk'), required=True)
    parser.add_argument('--samples', choices=(0, 2, 4, 8), type=int, default=0)
    parser.add_argument('--native-samples', action='store_true', help='disable optional Vulkan sample alignment to qualify its native fallback')
    parser.add_argument('--reference', type=Path, help='qualified report to compare, with identical fixture and profile')
    args = parser.parse_args()
    lab.BASE['r_vkSampleLocations'] = '0' if args.native_samples else '1'
    profile = configure(json.loads((args.runtime_root/'pbr-lab.json').read_text()), args.samples)
    for name, spec in profile.items():
        lab.CASES[name] = spec['settings']
        lab.CASE_COMMANDS[name] = spec['commands']
        lab.LEGACY_CASES.add(name)
    sys.argv = [__file__, '--runtime-root', str(args.runtime_root), '--output-dir', str(args.output_dir),
                '--basepath', str(args.basepath), '--backend', args.backend, '--camera', 'sampling',
                '--batch', '--cases', ','.join(profile), '--timeout', '900']
    if args.backend == 'gl': sys.argv.append('--gl-debug')
    code = lab.main()
    path = args.output_dir/'report.json'
    report = json.loads(path.read_text())
    report.update(colorProfile=profile, requestedSamples=args.samples, nativeSamplesRequested=args.native_samples,
                  classicColorProof=qualify(report, profile, args.backend, args.samples, code, args.native_samples))
    for source in (Path(__file__), Path(scene.__file__)):
        shutil.copy2(source, args.output_dir/'harness'/source.name)
        report['harnessSources'][source.name] = lab.digest(source)
    failed = bool(code or report['classicColorProof']['failures'])
    if args.reference:
        report['classicColorComparison'] = compare(json.loads(args.reference.read_text()), report)
        failed = failed or bool(report['classicColorComparison']['failures'])
    path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(status='fail' if failed else 'pass', cases=len(profile),
                         failures=report['classicColorProof']['failures']), indent=2), flush=True)
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
