#!/usr/bin/env python3
"""Qualify authored GLSL draws using engine captures and observable controls.

Fixture sources live only in the isolated save directory. The existing compiled
laboratory supplies geometry; stock game assets remain read-only. No desktop
capture or input automation is used.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import struct
import sys

import numpy as np
from PIL import Image

import renderer_pbr_laboratory as lab

PREFIX = 'textures/openq4/authored_glsl'
PROGRAM = 'tests/oq4_authored.glsl'
CAPACITY_CASES = ('capacity', 'parameter-last', *('texture-' + str(i) for i in range(8)))
CASES = ('clear', 'base', 'tint', 'offset', 'coordinates', *CAPACITY_CASES,
         'base-restored', 'image-reload', 'shader-reload', 'partial-restart', 'full-restart')
VERTEX = '''#version 120
uniform vec4 Offset;
varying vec2 UV;
void main() {
    vec4 position = gl_Vertex;
    position.x += Offset.x;
    position.z += Offset.y;
    gl_Position = gl_ModelViewProjectionMatrix * position;
    UV = (gl_TextureMatrix[0] * gl_MultiTexCoord0).xy;
}
'''
FRAGMENT = '''#version 120
uniform sampler2D Image;
uniform vec4 Tint;
uniform vec4 Mode;
varying vec2 UV;
void main() {
    vec3 color = texture2D(Image, UV).rgb * Tint.rgb;
    if (Mode.x > 0.5) {
        color = vec3(gl_FragCoord.x / 1280.0, gl_FragCoord.y / 800.0,
                     clamp(0.5 + 20.0 * dFdy(UV.y), 0.0, 1.0));
    }
    gl_FragColor = vec4(color, 1.0);
}
'''
CAPACITY_VERTEX = '''#version 120
uniform vec4 P00;
attribute vec4 attr_Position;
attribute vec3 attr_Normal;
attribute vec3 attr_Tangent, attr_Bitangent;
attribute vec2 attr_TexCoord0;
varying vec2 UV;
varying vec3 Direction;
void main() {
    gl_Position = gl_ModelViewProjectionMatrix * (attr_Position + vec4(P00.xyz, 0.0));
    UV = attr_TexCoord0;
    Direction = attr_Normal * 0.75 + attr_Tangent * 0.15 + attr_Bitangent * 0.1;
}
'''


def capacity_fragment():
    declarations = ['#version 120', 'varying vec2 UV;', 'varying vec3 Direction;']
    types = {1: 'float', 15: 'vec2', 30: 'vec3'}
    for i in range(1, 32):
        declarations.append(f'uniform {types.get(i, "vec4")} P{i:02d};')
    declarations += [f'uniform sampler2D Image{i};' for i in range(7)]
    declarations += ['uniform samplerCube Image7;', 'void main() {', 'vec3 value = vec3(0.0);']
    for i in range(1, 32):
        expression = {1: 'vec3(P01)', 15: 'vec3(P15, 0.0)', 30: 'P30'}.get(i, f'P{i:02d}.rgb')
        declarations.append(f'value += {expression};')
    declarations.append('vec3 sampleValue = vec3(0.0);')
    declarations += [f'sampleValue += texture2D(Image{i}, UV).rgb;' for i in range(7)]
    declarations += ['sampleValue += textureCube(Image7, Direction).rgb;',
                     'gl_FragColor = vec4(sampleValue * (0.75 / 8.0) + value * 0.02, 1.0);', '}']
    return '\n'.join(declarations) + '\n'


def material(name: str, tint='0.7, 0.3, 0.1, 1', offset='0, 0, 0, 0', mode=0):
    return f'''{PREFIX}/{name}
{{
    translucent
    twoSided
    noShadows
    {{
        blend blend
        glslProgram {PROGRAM}
        shaderParm Offset {offset}
        shaderParm Tint {tint}
        shaderParm Mode {mode}, 0, 0, 0
        shaderTexture Image nearest clamp {PREFIX}/pattern
    }}
}}
'''


def capacity_material(name: str):
    lines = [f'{PREFIX}/{name.replace("-", "_")}', '{', 'translucent', 'twoSided', 'noShadows', '{', 'blend blend',
             'glslProgram tests/oq4_capacity.glsl']
    for i in range(32):
        value = {0: '0, 0, 0, 0', 1: '0.05', 15: '0.05, 0.1', 30: '0.1, 0.05, 0.1'}.get(i, '0.05, 0.1, 0.05, 1')
        if i == 31 and name == 'parameter-last':
            value = '8, 2, 4, 1'
        lines.append(f'shaderParm P{i:02d} {value}')
    for i in range(8):
        texture = 'alternate' if name == f'texture-{i}' else f'slot{i}'
        cube = 'cubeMap ' if i == 7 else ''
        if i == 7:
            texture = 'cube_' + texture
        lines.append(f'shaderTexture Image{i} {cube}nearest clamp {PREFIX}/{texture}')
    return '\n'.join(lines + ['}', '}', ''])


def tga(width: int, height: int, pixels: bytes):
    header = bytearray(18)
    header[2] = 2
    struct.pack_into('<HHBB', header, 12, width, height, 32, 8)
    return bytes(header) + pixels


def write_fixture(save: Path):
    files = {
        'glprogs/tests/oq4_authored.glslvp': VERTEX.encode('utf-8'),
        'glprogs/tests/oq4_authored.glslfp': FRAGMENT.encode('utf-8'),
        'materials/openq4_authored_glsl_test.mtr': (
            material('base') + material('tint', tint='0.1, 0.65, 0.4, 1')
            + material('offset', offset='80, 45, 0, 0')
            + material('coordinates', mode=1)
            + ''.join(capacity_material(name) for name in CAPACITY_CASES)).encode('utf-8'),
        'glprogs/tests/oq4_capacity.glslvp': CAPACITY_VERTEX.encode('utf-8'),
        'glprogs/tests/oq4_capacity.glslfp': capacity_fragment().encode('utf-8'),
    }
    # Asymmetric, colored nearest-filtered pattern exposes flipped UVs and
    # incorrect texture binding without anisotropic filtering ambiguity.
    pixels = bytes(component for y in range(32) for x in range(32)
                   for component in (64 + 128 * ((x // 8 + y // 8) % 2),
                                     32 + 7 * y, 32 + 7 * x, 255))
    files[f'{PREFIX}/pattern.tga'] = tga(32, 32, pixels)
    for i in range(7):
        files[f'{PREFIX}/slot{i}.tga'] = tga(4, 4, bytes((20 + 20 * i, 100 - 10 * i, 40 + 10 * i, 255)) * 16)
    files[f'{PREFIX}/alternate.tga'] = tga(4, 4, bytes((220, 200, 240, 255)) * 16)
    for i, face in enumerate(('px', 'nx', 'py', 'ny', 'pz', 'nz')):
        files[f'{PREFIX}/cube_slot7_{face}.tga'] = tga(4, 4, bytes((20 + 20 * i, 60 + 10 * i, 100 - 10 * i, 255)) * 16)
        files[f'{PREFIX}/cube_alternate_{face}.tga'] = tga(4, 4, bytes((220, 200, 240, 255)) * 16)
    hashes = {}
    for name, data in files.items():
        path = save / 'baseoq4' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        hashes[name] = lab.digest(path)
    return hashes


def prove(report):
    failures, checks, images = [], {}, {}
    rows = {row['case'].removeprefix('authored-glsl-'): row for row in report['results']}
    if not report.get('complete') or not report.get('runtimeUnchanged') or set(rows) != set(CASES):
        failures.append('incomplete or changed capture set/runtime')
    if not report.get('authoredSourcesUnchanged'):
        failures.append('authored source files changed during capture')
    for name, row in rows.items():
        failures += [name + ': ' + error for error in row['failures']]
        valid = True
        for kind in ('screenshot', 'log'):
            path = Path(row.get(kind, ''))
            if not path.is_file() or lab.digest(path) != row['sha256'].get(kind):
                failures.append(name + ': missing or changed ' + kind)
                valid = False
        if valid:
            images[name] = np.asarray(Image.open(row['screenshot']).convert('RGB'), dtype=np.int16)
    if report['results'] and report['results'][0]['backend'] == 'vk':
        log = Path(report['results'][0]['log']).read_text(encoding='utf-8', errors='replace')
        if f"Vulkan: drawing authored GLSL '{PROGRAM}'" not in log:
            failures.append('authored program did not reach the Vulkan draw path')
        if "Vulkan: drawing authored GLSL 'tests/oq4_capacity.glsl'" not in log:
            failures.append('capacity program did not reach the Vulkan draw path')
    if set(images) == set(CASES):
        for name, reference in [('base', 'clear'), ('tint', 'base'), ('offset', 'base'), ('coordinates', 'base')]:
            delta = np.abs(images[name] - images[reference]).max(axis=2)
            count = int(np.count_nonzero(delta > 2))
            checks[name] = dict(changedPixels=count, maximumError=int(delta.max()))
            if count < 1000:
                failures.append(name + ': control lacks a visible response')
        for name in CAPACITY_CASES:
            reference = 'base' if name == 'capacity' else 'capacity'
            delta = np.abs(images[name] - images[reference]).max(axis=2)
            count = int(np.count_nonzero(delta > 2))
            checks[name] = dict(changedPixels=count, maximumError=int(delta.max()))
            if count < 1000:
                failures.append(name + ': capacity control lacks a visible response')
        for name in CASES[-5:]:
            delta = np.abs(images[name] - images['base']).max(axis=2)
            checks[name] = dict(differingPixels=int(np.count_nonzero(delta)), maximumError=int(delta.max()))
            if np.any(delta):
                failures.append(name + ': recovery changed the base image')
    return dict(status='fail' if failures else 'pass', failures=failures, checks=checks)


def compare(left: Path, right: Path):
    reports = [json.loads(path.read_text(encoding='utf-8')) for path in (left, right)]
    failures, checks = [], {}
    for report in reports:
        proof = prove(report)
        failures += proof['failures']
    if reports[0].get('authoredSources') != reports[1].get('authoredSources'):
        failures.append('source fixtures differ between renderers')
    if reports[0].get('runtimeSHA256') != reports[1].get('runtimeSHA256'):
        failures.append('renderer comparison used different runtime sets')
    if any(row['backend'] != backend for report, backend in zip(reports, ('gl', 'vk')) for row in report['results']):
        failures.append('comparison requires an OpenGL reference and Vulkan candidate')
    for a, b in zip(reports[0]['results'], reports[1]['results']):
        if a['case'] != b['case']:
            failures.append('case ordering mismatch')
            continue
        if not all(Path(r['screenshot']).is_file() for r in (a, b)):
            continue
        images = [np.asarray(Image.open(r['screenshot']).convert('RGB'), dtype=np.int16) for r in (a, b)]
        delta = np.abs(images[0] - images[1]).max(axis=2)
        checks[a['case']] = dict(maximumError=int(delta.max()), differingPixels=int(np.count_nonzero(delta)),
                                  overTolerancePixels=int(np.count_nonzero(delta > 2)))
        if np.any(delta > 2):
            failures.append(a['case'] + ': cross-renderer error exceeds two display levels')
    return dict(status='fail' if failures else 'pass', failures=failures, checks=checks,
                reports={str(path.resolve()): lab.digest(path) for path in (left, right)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--basepath', type=Path)
    parser.add_argument('--backend', choices=('gl', 'vk'))
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--compare', nargs=2, type=Path, metavar=('GL_REPORT', 'VK_REPORT'))
    args = parser.parse_args()
    args.output_dir = args.output_dir.resolve()
    if args.compare:
        proof = compare(*args.compare)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / 'comparison.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(proof, indent=2))
        return int(proof['status'] != 'pass')
    if not all((args.runtime_root, args.basepath, args.backend)):
        parser.error('capture requires --runtime-root, --basepath and --backend')
    args.runtime_root = args.runtime_root.resolve()
    source_hash = lab.digest(Path(__file__))
    manifest = json.loads((args.runtime_root / 'pbr-lab.json').read_text(encoding='utf-8'))
    lab.BASE.update(image_anisotropy='1')
    profile = {}
    for suffix in CASES:
        name = 'authored-glsl-' + suffix
        settings = dict(r_pbrMaterials='0', r_pbrIBL='0', r_rendererReflectionProbes='0',
                        r_useLightGrid='0', r_pbrDebug='0', r_hdrToneMap='0', image_anisotropy='1')
        commands = ['g_stopTime 0']
        if not profile:
            commands += [f'script "${s["name"]}.hide()"' for s in manifest['stations']]
            commands += [f'script "${s}.Off()"' for s in ('key', 'blue_fill', 'warm_fill', 'lab_projector')]
        if suffix in ('base', 'tint', 'offset', 'coordinates', 'base-restored', *CAPACITY_CASES):
            if suffix != 'base':
                commands += ['script "$authored_specimen.remove()"', 'wait 3']
            mat = 'base' if suffix == 'base-restored' else suffix.replace('-', '_')
            commands += [f'spawn func_static name authored_specimen model "{lab.lab.MODEL}" '
                         f'shader "{PREFIX}/{mat}" origin "100 160 120" angle 0 solid 0']
        commands += {'image-reload': ['reloadImages all'], 'shader-reload': ['reloadARBprograms'],
                     'partial-restart': ['vid_restart partial'], 'full-restart': ['vid_restart']}.get(suffix, [])
        commands += ['wait 60', 'g_stopTime 1']
        lab.CASES[name], lab.CASE_COMMANDS[name] = settings, commands
        lab.LEGACY_CASES.add(name)
        profile[name] = dict(settings={**lab.BASE, **settings}, commands=commands)
    write = lab.write_capture_commands
    source_hashes = {}

    def write_commands(path, commands):
        source_hashes.update(write_fixture(args.output_dir / 'batch'))
        return write(path, commands)

    lab.write_capture_commands = write_commands
    startup = lab.startup_args

    def startup_args(cvars, save):
        options = startup(cvars, save)
        with (save / 'baseoq4/autoexec.cfg').open('a', encoding='utf-8') as config:
            for mat in ('base', 'tint', 'offset', 'coordinates', *CAPACITY_CASES):
                config.write(f'touch material {PREFIX}/{mat.replace("-", "_")}\n')
        return options

    lab.startup_args = startup_args
    sys.argv = [__file__, '--runtime-root', str(args.runtime_root), '--output-dir', str(args.output_dir),
                '--basepath', str(args.basepath), '--backend', args.backend, '--cases', ','.join(profile),
                '--batch', '--camera', 'coverage', '--timeout', str(args.timeout)]
    if args.backend == 'gl':
        sys.argv += ['--gl-debug']
    code = lab.main()
    path = args.output_dir / 'report.json'
    report = json.loads(path.read_text(encoding='utf-8'))
    assert lab.digest(Path(__file__)) == source_hash, 'capture harness changed during run'
    shutil.copy2(__file__, args.output_dir / 'harness' / Path(__file__).name)
    report['harnessSources'][Path(__file__).name] = source_hash
    report.update(authoredProfile=profile, authoredSources=source_hashes)
    report['authoredSourcesUnchanged'] = all(
        lab.digest(args.output_dir / 'batch/baseoq4' / name) == expected for name, expected in source_hashes.items())
    report['authoredProof'] = prove(report)
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report['authoredProof'], indent=2))
    return int(code or report['authoredProof']['status'] != 'pass')


if __name__ == '__main__':
    raise SystemExit(main())
