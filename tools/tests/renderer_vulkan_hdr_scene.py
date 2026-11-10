#!/usr/bin/env python3
"""Qualify native linear-scene admission and the ordinary engine capture path.

Uses the reusable PBR runtime, windowed with no input or OS capture. Composition
controls can also be captured on GL; the ambient controls use scalar radiance
oracles because GL does not admit that complete mixed scene.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

import numpy as np
from PIL import Image

import pbr_reference as reference
import renderer_pbr_laboratory as lab
import renderer_vulkan_pbr_ambient as ambient


def decode(byte):
    x = byte / 255
    return x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4


def output(x, exposure=1):
    def film(v):
        return v * (2.51 * v + .03) / (v * (2.43 * v + .59) + .14)
    x = min(1, max(0, film(max(0, x) * exposure) / film(6)))
    return 255 * (12.92 * x if x <= .0031308 else 1.055 * x ** (1 / 2.4) - .055)


def configure_composition(manifest, samples):
    profile = {}
    overlay = None
    specimen = None
    for material, mode in (('data_scalar', 1), ('data_scalar', 7), ('emissive', 6), ('source_alpha', 1)):
        for effect in ('clear', 'fog', 'fog-shared', 'blend', 'blend-shared'):
            name = f'linear-composition-{material}-{mode}-{effect}'
            commands = ['g_stopTime 0']
            if not profile:
                commands += [f'script "${s["name"]}.hide()"' for s in manifest['stations']]
                commands += [f'script "${light}.Off()"' for light in ('key', 'blue_fill', 'warm_fill', 'lab_projector')]
                commands += ['script "$probe_warm.remove(); $probe_cool.remove()"', 'wait 3']
            else:
                commands += [f'script "${specimen}.hide(); ${specimen}.remove()"', 'wait 30']
            if overlay:
                commands += [f'script "${overlay}.remove()"', 'wait 30']
            # Removal is serviced on a game tick, while console wait counts
            # render frames; the laboratory runs one tick per frame. Unique
            # names remain a second guard against respawning a name before
            # its predecessor's deferred removal has completed.
            specimen = f'linear_specimen_{len(profile)}'
            overlay = f'linear_overlay_{len(profile)}' if effect != 'clear' else None
            if overlay:
                commands += [f'spawn light name {overlay} origin "0 0 400" angle 0 '
                             f'light_radius "1400 1400 1000" texture "lights/openq4/pbr_lab/{effect.split("-")[0]}" noshadows 1']
            commands += [f'spawn func_static name {specimen} model "{lab.lab.MODEL}" '
                         f'shader "{lab.lab.PREFIX}/{material}" origin "0 -700 380" angle 0 solid 0',
                         'wait 30', 'g_stopTime 1']
            settings = {'r_pbrIBL': '0', 'r_rendererReflectionProbes': '0', 'r_pbrMaterials': '1',
                        'r_pbrDebug': str(mode), 'r_multiSamples': str(samples), 'r_hdrToneMap': '1',
                        'r_rendererSharedWorldFogBlend': str(int(effect.endswith('shared')))}
            profile[name] = dict(material=material, mode=mode, effect=effect, settings=settings,
                                 commands=commands, committed=True)
    return profile


def configure_ambient(manifest, samples):
    source = ambient.configure(manifest, samples)
    profile = {}
    for name, spec in source.items():
        spec = dict(spec)
        spec['settings'] = {**spec['settings'], 'r_hdrToneMap': '1'}
        spec['committed'] = bool(spec['enabled'] and not spec['fault'])
        profile['linear-' + name] = spec
    # Bloom is admitted by the prepared HDR output chain. Keep an unsupported
    # post combination as a separate complete-view fallback control.
    last = source['ambient-restored']
    for name, bloom in (('bloom-enabled', '1'), ('bloom-restored', '0')):
        profile['linear-' + name] = dict(last, settings={**last['settings'], 'r_hdrToneMap': '1',
            'r_bloom': bloom}, committed=True)
    for name, motion in (('post-declined', '1'), ('post-restored', '0')):
        profile['linear-' + name] = dict(last, settings={**last['settings'], 'r_hdrToneMap': '1',
            'r_motionBlur': motion}, committed=motion == '0', rejection='post-combination')
    return profile


def configure_recovery(manifest, samples):
    # Keep one static specimen alive while storage sizes and the device change.
    # The intermediate capture is immediately followed by partial restart, so
    # an extra wait cannot hide in-flight screenshot/resource lifetime defects.
    lab.BASE.setdefault('r_screenFraction', '100')
    base = next(iter(configure_composition(manifest, samples).values()))
    resize = [
        'r_customWidth 960', 'r_customHeight 600', 'r_windowWidth 960', 'r_windowHeight 600',
        'vid_restart partial', 'wait 60', 'echo HDR_RECOVERY_SMALL_BEGIN', 'gfxInfo',
        'rendererVulkanHDRInfo', 'screenshot "screenshots/linear-recovery-small.tga"',
        'echo HDR_RECOVERY_SMALL_END',
        'r_customWidth 1280', 'r_customHeight 800', 'r_windowWidth 1280', 'r_windowHeight 800',
        'vid_restart partial', 'wait 60']
    profile = {}
    for suffix, scale, commands in (
            ('baseline', 100, base['commands']), ('scaled', 75, []),
            ('scale-restored', 100, []), ('resize-restored', 100, resize),
            ('full-restart', 100, ['vid_restart', 'wait 60'])):
        profile['linear-recovery-' + suffix] = dict(base,
            settings={**base['settings'], 'r_screenFraction': str(scale)},
            commands=[*commands, 'wait 20', f'echo "HDR_RECOVERY_{suffix}_BEGIN"',
                      'rendererVulkanHDRInfo', f'echo "HDR_RECOVERY_{suffix}_END"'])
    return profile


def qualify_recovery(report, images, checks, failures, samples):
    target = output(decode(188))
    baseline = images.get('linear-recovery-baseline')
    for name, rgb in images.items():
        centre = rgb[(400 * 1280 + 640) * 3: (400 * 1280 + 640) * 3 + 3]
        error = max(abs(c - target) for c in centre)
        checks[name + '/tone'] = dict(expected=target, actual=list(centre), maximumError=error)
        if error > 1:
            failures.append(name + ': resized scene lost linear radiance')
        if name.endswith(('restored', 'restart')):
            checks[name + '/restoration'] = dict(equal=rgb == baseline)
            if rgb != baseline:
                failures.append(name + ': full-image restoration failed')
    for row in report['results']:
        suffix = row['case'].removeprefix('linear-recovery-')
        text = Path(row['log']).read_text(errors='replace')
        match = re.search(rf'(?m)^HDR_RECOVERY_{suffix}_BEGIN\s*$([\s\S]*?)^HDR_RECOVERY_{suffix}_END\s*$', text)
        section = match[1] if match else ''
        state = dict(re.findall(r'(\w+)=([^\s]+)', next((line for line in section.splitlines()
            if line.startswith('Vulkan HDR:')), '')))
        expected = dict(sceneFormat='RGBA16F', samples=str(samples),
                        extent='960x600' if suffix == 'scaled' else '1280x800')
        checks[row['case'] + '/storage'] = dict(expected=expected, actual=state)
        if any(state.get(k) != v for k, v in expected.items()):
            failures.append(row['case'] + ': actual HDR scene storage differs from the requested control')
    row = next((row for row in report['results'] if row['case'] == 'linear-recovery-resize-restored'), None)
    if row is None:
        failures.append('missing intermediate resize case')
        return
    path = Path(row['screenshot']).with_name('linear-recovery-small.tga')
    text = Path(row['log']).read_text(errors='replace')
    match = re.search(r'(?m)^HDR_RECOVERY_SMALL_BEGIN\s*$([\s\S]*?)^HDR_RECOVERY_SMALL_END\s*$', text)
    section = match[1] if match else ''
    state = dict(re.findall(r'(\w+)=([^\s]+)', next((line for line in section.splitlines()
        if line.startswith('Vulkan HDR scene ownership:')), '')))
    extent = re.search(r'Vulkan HDR: .*sceneFormat=RGBA16F .*extent=960x600\b', section)
    expected = dict(requested='1', committed='1', linearActive='0', reason='complete', samples=str(max(1, samples)))
    check = dict(screenshot=str(path), sha256=lab.digest(path) if path.is_file() else None,
                 expectedOwnership=expected, actualOwnership=state, fp16Extent=bool(extent))
    checks['intermediate-resize'] = check
    if not extent or any(state.get(k) != v for k, v in expected.items()):
        failures.append('intermediate resize did not complete native FP16 linear ownership')
    if not re.search(rf'Renderer AA: MSAA requested={samples} effective={samples}\b', section):
        failures.append('intermediate resize did not retain effective MSAA')
    if not path.is_file():
        failures.append('intermediate resize engine capture missing')
        return
    with Image.open(path) as raw:
        rgb = raw.convert('RGB')
        check['extent'] = list(rgb.size)
        if rgb.size != (960, 600):
            failures.append('intermediate resize engine capture has wrong dimensions')
            return
        # Use a fully covered interior, independent of either API rasterizer.
        interior = list(rgb.crop((470, 290, 490, 310)).getdata())
        check['maximumToneError'] = max(abs(c - target) for pixel in interior for c in pixel)
        if check['maximumToneError'] > 1:
            failures.append('intermediate resize lost expected linear radiance')


def qualify(report, profile, backend, samples, suite):
    failures, checks, images = [], {}, {}
    if not report.get('complete') or not report.get('runtimeUnchanged'):
        failures.append('capture sequence incomplete or runtime changed')
    for row in report['results']:
        name = row['case']
        for kind in ('screenshot', 'log'):
            path = Path(row[kind])
            if not path.is_file() or lab.digest(path) != row['sha256'][kind]:
                failures.append(f'{name}: changed {kind}')
        if row['failures']:
            failures.append(f'{name}: {row["failures"]}')
            continue
        rgb = lab.capture_rgb(Path(row['screenshot']))
        if rgb is None or len(rgb) != 1280 * 800 * 3:
            failures.append(f'{name}: missing full-sized engine capture')
            continue
        images[name] = rgb
        telemetry = '\n'.join(row['telemetry'])
        if not re.search(rf'Renderer AA: MSAA requested={samples} effective={samples}\b', telemetry):
            failures.append(f'{name}: requested MSAA did not become active')
        if backend == 'vk':
            state = dict(re.findall(r'(\w+)=([^\s]+)', next((s for s in row['telemetry']
                if s.startswith('Vulkan HDR scene ownership:')), '')))
            spec = profile[name]
            expected = {'requested': spec['settings']['r_pbrMaterials'],
                        'committed': str(int(spec['committed'])), 'linearActive': '0'}
            if spec['committed']:
                expected.update(reason='complete', samples=str(max(1, samples)))
            elif spec.get('rejection'):
                expected['reason'] = spec['rejection']
            checks[name + '/ownership'] = dict(expected=expected, actual=state)
            if any(state.get(k) != v for k, v in expected.items()):
                failures.append(f'{name}: incorrect complete scene ownership {state}')
        if suite == 'composition' and profile[name]['effect'] == 'clear':
            spec = profile[name]
            values = {'data_scalar-1': [decode(188)] * 3, 'data_scalar-7': [0, 1, 0],
                      'emissive-6': [decode(c) * 4 for c in (30, 200, 255)],
                      'source_alpha-1': [decode(c) * 112 / 255 for c in (50, 180, 255)]}
            target = [output(v) for v in values[f'{spec["material"]}-{spec["mode"]}']]
            centre = rgb[(400 * 1280 + 640) * 3: (400 * 1280 + 640) * 3 + 3]
            error = max(abs(c - t) for c, t in zip(centre, target))
            checks[name + '/tone'] = dict(expected=target, actual=list(centre), maximumError=error)
            if error > 1:
                failures.append(f'{name}: incorrect linear tone curve ({error})')
    if set(images) != set(profile):
        failures.append('missing or duplicate qualified captures')
    if suite == 'recovery':
        qualify_recovery(report, images, checks, failures, samples)
    for name, rgb in images.items():
        if name.endswith('-shared'):
            base = images.get(name.removesuffix('-shared'))
            checks[name + '/shared-setting'] = dict(equal=rgb == base)
            if rgb != base:
                failures.append(name + ': shared-setting toggle changed the image')
    if suite == 'ambient':
        # An authored ambient light is a uniform environment with an
        # independent analytic response (pbr_reference); use the fully covered
        # centre, where N.V is one and no edge samples mix. The classic light
        # term (1, .5, .25) reaches PBR as pi times its decoded value
        # (PBRClassicLightIrradiance); the data specimens carry metallic
        # 102/255, roughness 128/255 and AO 192/255, and ao_zero has none.
        nov, variance = reference.sampling_sphere()
        centre_roughness = reference.filtered_roughness(128 / 255, variance[400, 640])
        light = reference.decode(np.asarray((1, .5, .25)))
        for suffix, lights, ao in (('scalar', 1, 192 / 255), ('packed', 1, 192 / 255),
                                   ('separate', 1, 192 / 255), ('ao-zero', 1, 0),
                                   ('two', 2, 192 / 255), ('two-stages', 2, 192 / 255),
                                   ('restored', 1, 192 / 255)):
            name = 'linear-ambient-' + suffix
            if name not in images:
                continue
            radiance = reference.uniform_environment(light, reference.byte_decode((188, 188, 188)), 102 / 255,
                                                     centre_roughness, ao, nov[400, 640]) * lights
            target = [output(float(v)) for v in radiance]
            centre = images[name][(400 * 1280 + 640) * 3: (400 * 1280 + 640) * 3 + 3]
            error = max(abs(c - t) for c, t in zip(centre, target))
            checks[name + '/radiance'] = dict(expected=target, actual=list(centre), maximumError=error)
            if error > 1:
                failures.append(f'{name}: incorrect ambient HDR radiance ({error})')
        for left, right in (('linear-ambient-scalar', 'linear-ambient-restored'),
                            ('linear-ambient-restored', 'linear-bloom-restored'),
                            ('linear-ambient-restored', 'linear-post-restored')):
            if left in images and right in images and images[left] != images[right]:
                failures.append(f'{left}/{right}: exact restoration failed')
    return dict(status='fail' if failures else 'pass', checks=checks, failures=failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--basepath', type=Path, required=True)
    parser.add_argument('--backend', choices=('gl', 'vk'), default='vk')
    parser.add_argument('--samples', type=int, choices=(0, 4), default=0)
    parser.add_argument('--suite', choices=('composition', 'ambient', 'recovery'), default='composition')
    parser.add_argument('--scene-scale', type=int, choices=(50, 75, 100, 125), default=100,
                        help='Scene resolution for the composition suite; presentation stays 1280x800.')
    parser.add_argument('--limit', type=int, help='A bring-up subset, recorded explicitly in the report.')
    args = parser.parse_args()
    manifest = json.loads((args.runtime_root / 'pbr-lab.json').read_text())
    configure = {'composition': configure_composition, 'ambient': configure_ambient,
                 'recovery': configure_recovery}[args.suite]
    if args.suite == 'recovery' and args.backend != 'vk':
        parser.error('recovery qualification requires Vulkan ownership telemetry')
    if args.scene_scale != 100 and args.suite != 'composition':
        parser.error('--scene-scale applies to the composition suite')
    if args.suite == 'composition':
        lab.BASE.update(r_screenFraction='100', r_resolutionScaleMode='1')
    profile = configure(manifest, args.samples)
    if args.limit:
        profile = dict(list(profile.items())[:args.limit])
    for name, spec in profile.items():
        if args.suite == 'composition':
            spec['settings'].update(r_screenFraction=str(args.scene_scale), r_resolutionScaleMode='1')
        lab.CASES[name] = spec['settings']
        commands = list(spec['commands'])
        if args.suite == 'composition' and args.backend == 'vk':
            commands += ['wait 20', f'echo HDR_SCENE_{name}_BEGIN', 'rendererVulkanHDRInfo',
                         f'echo HDR_SCENE_{name}_END']
        lab.CASE_COMMANDS[name] = commands
        lab.CASE_CAMERAS[name] = 'sampling'
    sys.argv = [__file__, '--runtime-root', str(args.runtime_root), '--output-dir', str(args.output_dir),
                '--basepath', str(args.basepath), '--backend', args.backend, '--camera', 'sampling',
                '--batch', '--cases', ','.join(profile), '--timeout', '900']
    if args.backend == 'gl':
        sys.argv.append('--gl-debug')
    code = lab.main()
    path = args.output_dir / 'report.json'
    report = json.loads(path.read_text())
    report.update(linearSceneProfile=profile, requestedSamples=args.samples, limited=args.limit,
                  linearSceneProof=qualify(report, profile, args.backend, args.samples, args.suite))
    if args.suite == 'composition':
        proof = report['linearSceneProof']
        extent = f'{1280 * args.scene_scale // 100}x{800 * args.scene_scale // 100}'
        for row in report['results']:
            name = row['case']
            text = Path(row['log']).read_text(errors='replace')
            marker = f'PBRLAB_{name}' if args.backend == 'gl' else f'HDR_SCENE_{name}'
            section = text.split(marker + '_BEGIN', 1)[-1].split(marker + '_END', 1)[0]
            prefix = 'Renderer graph extent:' if args.backend == 'gl' else 'Vulkan HDR:'
            state = dict(re.findall(r'(\w+)=([^\s]+)', next((line for line in section.splitlines()
                if line.startswith(prefix)), '')))
            actual = state.get('scene' if args.backend == 'gl' else 'extent')
            proof['checks'][name + '/scene-extent'] = dict(expected=extent, actual=actual)
            if actual != extent:
                proof['failures'].append(name + ': scene allocation did not match the requested scale')
        proof['status'] = 'fail' if proof['failures'] else 'pass'
    for source in (Path(__file__), Path(ambient.__file__)):
        shutil.copy2(source, args.output_dir / 'harness' / source.name)
        report['harnessSources'][source.name] = lab.digest(source)
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report['linearSceneProof'], indent=2), flush=True)
    return int(bool(code or report['linearSceneProof']['failures']))


if __name__ == '__main__':
    raise SystemExit(main())
