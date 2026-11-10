#!/usr/bin/env python3
"""Check HDR map images against independent radiance and optional GL captures."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

import pbr_reference as reference
import renderer_vulkan_hdr_scene as capture


def tone(radiance):
    x = np.maximum(0, np.asarray(radiance, dtype=np.float64))
    film = lambda v: v * (2.51 * v + .03) / (v * (2.43 * v + .59) + .14)
    x = np.clip(film(x) / film(6), 0, 1)
    return 255 * np.where(x <= .0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - .055)


def inverse_tone(encoded):
    x = np.clip(np.asarray(encoded, dtype=np.float64) / 255, 0, 1)
    y = np.where(x <= .04045, x / 12.92, ((x + .055) / 1.055) ** 2.4)
    y *= 6 * (2.51 * 6 + .03) / (6 * (2.43 * 6 + .59) + .14)
    a, b = 2.51 - 2.43 * y, .03 - .59 * y
    return (-b + np.sqrt(b * b + 4 * a * .14 * y)) / (2 * a)


def load(path):
    report = json.loads(path.read_text())
    assert report['complete'] and report['runtimeUnchanged'] and not report['limited']
    assert report['linearSceneProof']['status'] == 'pass'
    images = {}
    for row in report['results']:
        assert not row['failures']
        for kind in ('screenshot', 'log'):
            assert capture.lab.digest(Path(row[kind])) == row['sha256'][kind]
        image = np.asarray(Image.open(row['screenshot']).convert('RGB'), dtype=np.float64)
        assert image.shape == (800, 1280, 3)
        images[row['case']] = image
    assert len(images) == len(report['results']) == len(report['linearSceneProfile'])
    return report, images


def compare_ambient(path):
    report, named = load(path)
    images = {name.removeprefix('linear-ambient-'): image for name, image in named.items()}
    checks, failures = {}, []
    green = round(capture.output(1))

    def interior(image):
        mask = np.all(image == (0, green, 0), axis=2)
        return np.asarray(Image.fromarray(np.uint8(mask) * 255).filter(ImageFilter.MinFilter(7))) == 255

    mask = interior(images['owned-dark'])
    assert np.count_nonzero(mask) > 10000

    def check(name, expected, area=mask, high=None):
        low = np.asarray(expected)
        upper = low if high is None else np.asarray(high)
        if low.ndim == 3:
            low, upper = low[area], upper[area]
        values = images[name][area]
        error = float(np.maximum(np.maximum(low - values, values - upper), 0).max())
        checks[name] = dict(pixels=len(values), maximumByteError=error)
        if error > 1.1:
            failures.append(f'{name}: independent radiance/composition error {error}')

    # An authored ambient light is a uniform environment (pbr_reference): view
    # dependent, so it is predicted per pixel of the specimen sphere where
    # N.V is at least 0.6. The data specimens carry AO 192/255.
    nov, variance = reference.sampling_sphere()
    nov = np.nan_to_num(nov, nan=-1.0)
    variance = np.nan_to_num(variance)
    flat = mask & (nov >= 0.6)
    light = reference.decode(np.asarray((1, .5, .25)))

    def radiance(rgb=(188, 188, 188), metallic=0.0, rough=0.5, ao=1.0, stages=1):
        return reference.uniform_environment(light, reference.byte_decode(rgb), metallic,
                                             reference.filtered_roughness(rough, variance), ao, nov) * stages

    data = dict(metallic=102 / 255, rough=128 / 255, ao=192 / 255)
    for name, count in (('scalar', 1), ('packed', 1), ('separate', 1), ('two', 2), ('two-stages', 2), ('restored', 1)):
        check(name, tone(radiance(stages=count, **data)), flat)
    for name in ('ao-zero', 'dark'):
        check(name, (0, 0, 0))
    for name in ('owned', 'owned-two'):
        check(name, tone((0, 1, 0)))
    for kind in ('dielectric', 'metal'):
        for index, rough in ((0, 0.045), (5, 1.0)):
            check(f'{kind}-{index}', tone(radiance((245, 160, 105) if kind == 'metal' else (188, 188, 188),
                                                   metallic=float(kind == 'metal'), rough=rough)), flat)
    check('normal-zero', tone(radiance()), flat)
    for name in ('emission-dark', 'emission', 'emission-two'):
        check(name, tone([capture.decode(c) * 4 for c in (30, 200, 255)]))
    cutout = interior(images['cutout-owned']) & flat
    assert np.count_nonzero(cutout) > 1000
    check('cutout', tone(radiance(rough=0.25)), cutout)
    alpha = 112 / 255
    for suffix, stages in (('dark', 0), ('one', 1), ('two', 2), ('stages', 2), ('owned', -1)):
        background = images['background-' + ('one' if stages < 0 else suffix)]
        # The captured background has already been quantized. Propagate its
        # complete half-byte interval through the inverse curve; do not treat
        # an encoded screenshot value as a linear blend operand.
        assert np.max(background[mask]) < 255
        foreground = np.asarray((0, 1, 0)) if stages < 0 else radiance((50, 180, 255), rough=0.2, stages=stages)
        low = tone(inverse_tone(background - .5) * (1 - alpha) + foreground * alpha)
        high = tone(inverse_tone(background + .5) * (1 - alpha) + foreground * alpha)
        check('alpha-' + suffix, low, flat, high=high)
    pairs = [('scalar', name) for name in ('packed', 'separate', 'restored')]
    pairs += [('normal-xyz', 'normal-agb')]
    pairs += [('alpha-one', 'alpha-' + name) for name in ('restored', 'image-reload', 'partial-restart', 'full-restart')]
    pairs += [('two', 'two-stages'), ('alpha-classic', 'alpha-fault'), ('restored', 'linear-bloom-restored')]
    for left, right in pairs:
        error = int(np.abs(images[left] - images[right]).max())
        checks[left + '/' + right] = dict(maximumByteError=error)
        if error:
            failures.append(f'{left}/{right}: exact restoration/rollback changed ({error})')
    return dict(status='fail' if failures else 'pass', scope='Independent native HDR ambient radiance, alpha composition and complete fallback; no GL ambient parity claim',
                requestedSamples=report['requestedSamples'], checks=checks, failures=failures)


def compare_pair(gl_path, vk_path):
    gl, a = load(gl_path)
    vk, b = load(vk_path)
    for key in ('fixture', 'compiledMapSHA256', 'harnessSHA256', 'harnessSources',
                'linearSceneProfile', 'requestedSamples', 'runtimeSHA256', 'basepath'):
        assert gl[key] == vk[key], key
    assert gl['requestedSamples'] == 0 and a.keys() == b.keys()
    checks = {}
    for name in a:
        delta = np.abs(a[name] - b[name])
        checks[name] = dict(maximumByteError=int(delta.max()), pixelsAbove2=int(np.count_nonzero(delta.max(axis=2) > 2)))
    return dict(status='pass' if all(v['maximumByteError'] <= 2 for v in checks.values()) else 'fail',
                scope='Twenty diagnostic/fog/blend/alpha full-frame pairs at 0x; shared-setting toggles do not establish shared-consumer execution', comparisons=checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vk', type=Path, required=True)
    parser.add_argument('--gl', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    proof = compare_pair(args.gl, args.vk) if args.gl else compare_ambient(args.vk)
    proof['inputs'] = {str(p.resolve()): capture.lab.digest(p) for p in (args.vk, args.gl) if p}
    proof['harnessSHA256'] = capture.lab.digest(Path(__file__))
    args.output.write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(proof, indent=2))
    return int(proof['status'] != 'pass')


if __name__ == '__main__':
    raise SystemExit(main())
