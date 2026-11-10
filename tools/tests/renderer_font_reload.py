#!/usr/bin/env python3
"""Check generated font pixels and HUD text across reload and video restart.

Uses engine screenshot commands in the isolated PBR laboratory, with hidden
windowed rendering and input disabled. Public linear screenshots must remain
unchanged while the HUD is drawn after the completed scene.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

import renderer_hdr_linear_capture as capture

lab = capture.lab
ATLASES = {
    'gui': '_ttfatlas_fonts_english_chain_48',
    'extended': '_ttfatlasx_fonts_english_chain_48',
    'console': '_ttfconsolefont',
}


def atlas_commands(label):
    commands = ['g_showHud 0']
    for kind, image in ATLASES.items():
        commands += [f'testImage {image}', 'wait 3',
                     f'screenshot "screenshots/font-{label}-{kind}.tga"']
    return commands + ['testImage', 'wait 3', 'g_showHud 1']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--basepath', type=Path, required=True)
    parser.add_argument('--backend', choices=('gl', 'vk'), required=True)
    parser.add_argument('--samples', type=int, choices=(0, 4), default=4)
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    args.output_dir = args.output_dir.resolve()
    manifest = json.loads((args.runtime_root / 'pbr-lab.json').read_text())
    base = next(iter(capture.scene.configure_composition(manifest, args.samples).values()))
    profile = {
        'scene': base['commands'],
        'hud': atlas_commands('initial'),
        'reload': ['reloadImages all', 'echo FONT_STALE_BEGIN',
                   'screenshot linear "screenshots/stale-image.pfm"', 'echo FONT_STALE_END',
                   'wait 30', *atlas_commands('reload')],
        'partial': ['vid_restart partial', 'wait 60', *atlas_commands('partial')],
        'full': ['vid_restart', 'wait 60', *atlas_commands('full')],
        'repeat-reload': ['reloadImages all', 'wait 30', *atlas_commands('repeat-reload')],
        'restored': [],
    }
    for name, commands in profile.items():
        key = 'font-reload-' + name
        lab.CASES[key] = {**base['settings'], 'r_useTrueTypeFonts': '1',
                         'g_showHud': '0' if name in ('scene', 'restored') else '1'}
        lab.BASE.setdefault('r_useTrueTypeFonts', '1')
        lab.CASE_COMMANDS[key] = commands
        lab.CASE_CAMERAS[key] = 'sampling'
    sys.argv = [__file__, '--runtime-root', str(args.runtime_root), '--output-dir', str(args.output_dir),
                '--basepath', str(args.basepath), '--backend', args.backend, '--camera', 'sampling',
                '--batch', '--linear', '--cases', ','.join('font-reload-' + name for name in profile),
                '--timeout', str(args.timeout)]
    if args.backend == 'gl':
        sys.argv += ['--gl-debug']
    code = lab.main()
    report_path = args.output_dir / 'report.json'
    report = json.loads(report_path.read_text())
    failures = [error for row in report['results'] for error in row['failures']]
    if code or not report.get('complete') or not report.get('runtimeUnchanged'):
        failures.append('laboratory sequence failed or its runtime changed')
    paths = [Path(row.get('linearScreenshot', '')) for row in report['results']]
    if len(paths) != len(profile) or any(not path.is_file() for path in paths):
        failures.append('public --linear option did not retain all scene captures')
    elif len({lab.digest(path) for path in paths}) != 1:
        failures.append('linear scene changed with the HUD or after a resource boundary')
    log = Path(report['results'][0]['log']).read_text(errors='replace')
    if not re.search(rf'Renderer AA: MSAA requested={args.samples} effective={args.samples}\b', log):
        failures.append('requested sample count was not active')
    if 'TTF font: loaded fonts/chain.ttf' not in log or 'TTF font: console sheet rebuilt' not in log:
        failures.append('TrueType fonts were not used')
    section = log.split('FONT_STALE_BEGIN', 1)[-1].split('FONT_STALE_END', 1)[0]
    screenshots = args.output_dir / 'batch/baseoq4/screenshots'
    # The native capture owns a separate generated image: reload invalidates
    # its completed-frame identity until a new scene has rendered.
    if args.backend == 'vk' and ((screenshots / 'stale-image.pfm').exists() or
            'screenshot linear: no completed modern HDR scene' not in section):
        failures.append('native image-generation guard accepted a stale scene')

    def rgb(path):
        with capture.Image.open(path) as image:
            return capture.np.asarray(image.convert('RGB'))

    comparisons = {}
    try:
        scene = rgb(screenshots / 'font-reload-scene.tga')
        hud = rgb(screenshots / 'font-reload-hud.tga')
        visible = int(capture.np.count_nonzero(capture.np.any(scene != hud, axis=2)))
        if visible < 1000:
            failures.append('HUD control did not draw a visible HUD')
        comparisons['hudVisiblePixels'] = visible
        for label in ('reload', 'partial', 'full', 'repeat-reload'):
            restored = rgb(screenshots / f'font-reload-{label}.tga')
            changed = int(capture.np.count_nonzero(capture.np.any(restored != hud, axis=2)))
            comparisons['hud-' + label] = dict(changedPixels=changed)
            if changed:
                failures.append(label + ': HUD did not restore exactly')
        for kind in ATLASES:
            reference = rgb(screenshots / f'font-initial-{kind}.tga')
            visible = int(capture.np.count_nonzero(capture.np.any(reference != scene, axis=2)))
            comparisons[kind + 'VisiblePixels'] = visible
            if visible < 1000:
                failures.append(kind + ': atlas control has no visible glyph coverage')
            for label in ('reload', 'partial', 'full', 'repeat-reload'):
                path = screenshots / f'font-{label}-{kind}.tga'
                changed = int(capture.np.count_nonzero(capture.np.any(rgb(path) != reference, axis=2)))
                comparisons[kind + '-' + label] = dict(changedPixels=changed, sha256=lab.digest(path))
                if changed:
                    failures.append(kind + '-' + label + ': atlas glyph pixels did not restore exactly')
    except (OSError, ValueError) as error:
        failures.append('font image comparison: ' + str(error))
    proof = dict(status='fail' if failures else 'pass', failures=sorted(set(failures)),
                 comparisons=comparisons, samples=args.samples, backend=args.backend,
                 harnessSha256=lab.digest(Path(__file__)))
    report['fontReloadProof'] = proof
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    shutil.copy2(__file__, args.output_dir / 'harness' / Path(__file__).name)
    print(json.dumps(proof, indent=2), flush=True)
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
