#!/usr/bin/env python3
"""Compare authored per-light GLSL through input-free engine captures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

import numpy as np
from PIL import Image

import renderer_pbr_laboratory as lab
from renderer_vulkan_material_programs import tga

PREFIX = 'textures/openq4/authored_lighting'
PROGRAM = 'tests/oq4_lighting.glsl'
CASES = ('clear', 'base', 'lights_off', 'second_light', 'tint', 'matrix', 'vertex', 'inverse',
         'condition_off', 'double_stage', 'diagnostics', 'rotated', 'projected',
         'projected_texture', 'falloff_texture', 'occluder_off', 'stencil', 'mapped',
         'projected_occluder_off', 'projected_stencil', 'projected_mapped',
         'base_restored', 'image_reload', 'shader_reload', 'partial_restart', 'full_restart')
VERTEX = '''#version 120
uniform vec4 LightOrigin, ViewOrigin, ProjectS, ProjectT, ProjectQ, FalloffS;
uniform vec4 BumpS, BumpT, DiffuseS, DiffuseT, SpecularS, SpecularT;
uniform vec4 ColorMod, ColorAdd, WorldView, Model0, Model1, Model2;
uniform vec4 Projection0, Projection1, Projection2, Projection3, Options;
varying vec4 LightCoord, VertexColor;
varying vec3 ToLight, ToView, Normal, Diagnostic;
varying vec2 UV;
void main() {
    vec4 p = gl_Vertex;
    vec4 eye = gl_ModelViewMatrix * p;
    gl_Position = ftransform();
    vec4 clip = vec4(dot(Projection0, eye), dot(Projection1, eye),
                     dot(Projection2, eye), dot(Projection3, eye));
    vec4 uv = vec4(gl_MultiTexCoord0.xy, 0.0, 1.0);
    UV = vec2(dot(BumpS + DiffuseS + SpecularS, uv),
              dot(BumpT + DiffuseT + SpecularT, uv)) / 3.0;
    LightCoord = vec4(dot(ProjectS, p), dot(ProjectT, p), dot(ProjectQ, p), dot(FalloffS, p));
    ToLight = LightOrigin.xyz - p.xyz;
    ToView = ViewOrigin.xyz - p.xyz;
    Normal = gl_Normal;
    VertexColor = gl_Color * ColorMod + ColorAdd;
    vec3 world = vec3(dot(Model0, p), dot(Model1, p), dot(Model2, p));
    Diagnostic = (world + WorldView.xyz) * 0.001 + vec3(0.2) + 0.05 * clip.xyz / clip.w;
}
'''
FRAGMENT = '''#version 120
uniform sampler2D DiffuseMap, ProjectionImage, FalloffImage;
uniform vec4 DiffuseColor, SpecularColor, Color0, Color1, Color2, Options;
varying vec4 LightCoord, VertexColor;
varying vec3 ToLight, ToView, Normal, Diagnostic;
varying vec2 UV;
void main() {
    vec3 n = normalize(Normal);
    vec3 l = normalize(ToLight);
    vec3 v = normalize(ToView);
    float diffuse = 0.15 + 0.85 * max(dot(n, l), 0.0);
    float specular = pow(max(dot(n, normalize(l + v)), 0.0), 12.0) * 0.2;
    vec3 projected = texture2D(ProjectionImage, LightCoord.xy / LightCoord.z).rgb;
    vec3 falloff = texture2D(FalloffImage, vec2(LightCoord.w, 0.5)).rgb;
    vec3 color = (texture2D(DiffuseMap, UV).rgb * DiffuseColor.rgb * diffuse
                  + SpecularColor.rgb * specular) * projected * falloff * VertexColor.rgb;
    if (Options.x > 0.5) { color = Diagnostic * DiffuseColor.rgb; }
    vec4 c = vec4(color, 1.0);
    gl_FragColor = vec4(dot(Color0, c), dot(Color1, c), dot(Color2, c), 1.0);
}
'''
SEMANTICS = dict(LightOrigin='localLightOrigin', ViewOrigin='localViewOrigin',
                 ProjectS='lightProjectS', ProjectT='lightProjectT', ProjectQ='lightProjectQ',
                 FalloffS='lightFalloffS', BumpS='bumpMatrixS', BumpT='bumpMatrixT',
                 DiffuseS='diffuseMatrixS', DiffuseT='diffuseMatrixT',
                 SpecularS='specularMatrixS', SpecularT='specularMatrixT',
                 DiffuseColor='diffuseColor', SpecularColor='specularColor',
                 ColorMod='colorModulate', ColorAdd='colorAdd', WorldView='viewOrigin',
                 Model0='modelRow0', Model1='modelRow1', Model2='modelRow2',
                 Projection0='projectionRow0', Projection1='projectionRow1',
                 Projection2='projectionRow2', Projection3='projectionRow3',
                 Color0='colorMatrix0', Color1='colorMatrix1', Color2='colorMatrix2')


def material(name):
    lines = [f'{PREFIX}/{name}', '{', 'forceOpaque', 'noShadows']
    stage = ['{', 'customLighting', f'glslProgram {PROGRAM}',
             'color ' + ('0.25, 0.75, 0.45, 1' if name == 'tint' else '0.7, 0.45, 0.2, 1')]
    stage += [f'shaderParm {key} {binding}' for key, binding in SEMANTICS.items()]
    stage += [f'shaderParm Options {1 if name == "diagnostics" else 0}, 0, 0, 0',
              f'shaderTexture DiffuseMap nearest noclamp {PREFIX}/pattern',
              'shaderTexture FalloffImage linear clamp lightFalloffImage',
              'shaderTexture ProjectionImage linear clamp lightImage']
    if name == 'matrix': stage += ['scale 0.7, 1.3', 'scroll 0.17, 0.23']
    if name == 'vertex': stage += ['vertexColor']
    if name == 'inverse': stage += ['inverseVertexColor']
    if name == 'condition_off': stage += ['if 0']
    stage += ['}']
    return '\n'.join(lines + stage * (2 if name == 'double_stage' else 1) + ['}', ''])


MATERIALS = ('base', 'tint', 'matrix', 'vertex', 'inverse', 'condition_off', 'double_stage', 'diagnostics')


def write_fixture(save):
    materials = ''.join(material(name) for name in MATERIALS)
    for name, image, falloff in (('plain', '_white', '_white'),
                                  ('pattern', PREFIX + '/projected', '_white'),
                                  ('falloff', PREFIX + '/projected', PREFIX + '/falloff')):
        materials += (f'lights/openq4/authored_lighting/{name}\n{{\nlightFalloffImage {falloff}\n'
                      f'{{\nmap {image}\ncolored\n}}\n}}\n')
    files = {'glprogs/tests/oq4_lighting.glslvp': VERTEX.encode(),
             'glprogs/tests/oq4_lighting.glslfp': FRAGMENT.encode(),
             'materials/openq4_authored_lighting_test.mtr': materials.encode()}
    for name in ('pattern', 'projected', 'falloff'):
        pixels = []
        for y in range(32):
            for x in range(32):
                rgb = ((48 + 5 * x, 48 + 5 * y, 48 + 144 * ((x // 8 + y // 8) % 2))
                       if name == 'pattern' else (32 + 6 * x, 200 - 4 * y, 64 + 3 * y)
                       if name == 'projected' else (16 + 7 * x,) * 3)
                pixels += [rgb[2], rgb[1], rgb[0], 255]
        files[f'{PREFIX}/{name}.tga'] = tga(32, 32, bytes(pixels))
    hashes = {}
    for name, data in files.items():
        target = save / 'baseoq4' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        hashes[name] = lab.digest(target)
    return hashes


def prove(report):
    failures, checks, images = [], {}, {}
    rows = {row['case'].removeprefix('authored-lighting-'): row for row in report['results']}
    if not report.get('complete') or not report.get('runtimeUnchanged') or set(rows) != set(CASES):
        failures.append('incomplete or changed capture set/runtime')
    if not report.get('authoredSourcesUnchanged'): failures.append('source fixtures changed during capture')
    for name, row in rows.items():
        failures += [name + ': ' + error for error in row['failures']]
        valid = True
        for kind in ('screenshot', 'log'):
            path = Path(row.get(kind, ''))
            if not path.is_file() or lab.digest(path) != row['sha256'].get(kind):
                failures.append(name + ': missing or changed ' + kind)
                valid = False
        if valid: images[name] = np.asarray(Image.open(row['screenshot']).convert('RGB'), dtype=np.int16)
    if rows and next(iter(rows.values()))['backend'] == 'vk':
        log = Path(next(iter(rows.values()))['log']).read_text(encoding='utf-8', errors='replace')
        if f"Vulkan: drawing authored GLSL lighting '{PROGRAM}'" not in log:
            failures.append('no authored lighting draw evidence')
        for kind in ('point', 'projected'):
            if not any('authored lighting stencil receivers' in line and f'type={kind}' in line for line in log.splitlines()):
                failures.append(kind + ': no mapped-request stencil ownership evidence')
    if set(images) == set(CASES):
        receiver = np.abs(images['base'] - images['condition_off']).max(axis=2) > 2
        checks['receiverCoverage'] = dict(pixels=int(np.count_nonzero(receiver)))
        if np.count_nonzero(receiver) < 1000: failures.append('authored receiver is not visibly distinct from the inactive stage')
        controls = {name: 'base' for name in ('second_light', 'tint', 'matrix', 'vertex', 'inverse',
                                            'condition_off', 'double_stage', 'diagnostics', 'rotated', 'projected')}
        controls.update(base='clear', projected_texture='projected', falloff_texture='projected_texture',
                        stencil='occluder_off', projected_stencil='projected_occluder_off')
        for name, reference in controls.items():
            delta = np.abs(images[name] - images[reference]).max(axis=2)
            count = int(np.count_nonzero((delta > 2) & receiver))
            checks[name] = dict(changedPixels=count, maximumError=int(delta.max()))
            if count < 100: failures.append(name + ': control lacks a visible response')
        recovery = dict(lights_off='clear', **{name: 'base' for name in CASES[-5:]})
        for name, reference in recovery.items():
            delta = np.abs(images[name] - images[reference]).max(axis=2)
            checks[name] = dict(differingPixels=int(np.count_nonzero(delta)), maximumError=int(delta.max()))
            if np.any(delta): failures.append(name + ': expected exact recovery/fallback image')
        for name, reference in (('mapped', 'stencil'), ('projected_mapped', 'projected_stencil')):
            delta = np.abs(images[name] - images[reference]).max(axis=2)[receiver]
            checks[name] = dict(receiverPixels=int(receiver.sum()), differingPixels=int(np.count_nonzero(delta)),
                               maximumError=int(delta.max(initial=0)))
            if np.any(delta): failures.append(name + ': authored receiver changed when requesting mapped shadows')
    return dict(status='fail' if failures else 'pass', failures=failures, checks=checks)


def compare(left, right):
    reports = [json.loads(path.read_text(encoding='utf-8')) for path in (left, right)]
    failures, checks = [], {}
    for report in reports: failures += prove(report)['failures']
    for field in ('authoredSources', 'runtimeSHA256', 'compiledMapSHA256'):
        if reports[0].get(field) != reports[1].get(field): failures.append(field + ': comparison inputs differ')
    for backend, report in zip(('gl', 'vk'), reports):
        if any(row['backend'] != backend for row in report['results']): failures.append('backend ordering mismatch')
    for a, b in zip(reports[0]['results'], reports[1]['results']):
        if a['case'] != b['case']: failures.append('case ordering mismatch'); continue
        if not all(Path(row['screenshot']).is_file() for row in (a, b)): continue
        images = [np.asarray(Image.open(row['screenshot']).convert('RGB'), dtype=np.int16) for row in (a, b)]
        delta = np.abs(images[0] - images[1]).max(axis=2)
        checks[a['case']] = dict(maximumError=int(delta.max()), differingPixels=int(np.count_nonzero(delta)),
                                  overTolerancePixels=int(np.count_nonzero(delta > 2)))
        if np.any(delta > 2): failures.append(a['case'] + ': error exceeds two display levels')
    return dict(status='fail' if failures else 'pass', failures=failures, checks=checks,
                reports={str(path.resolve()): lab.digest(path) for path in (left, right)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--basepath', type=Path)
    parser.add_argument('--backend', choices=('gl', 'vk'))
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--compare', nargs=2, type=Path)
    args = parser.parse_args()
    args.output_dir = args.output_dir.resolve()
    if args.compare:
        proof = compare(*args.compare)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / 'comparison.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(proof, indent=2))
        return int(proof['status'] != 'pass')
    if not all((args.runtime_root, args.basepath, args.backend)): parser.error('capture needs runtime, basepath and backend')
    args.runtime_root = args.runtime_root.resolve()
    manifest = json.loads((args.runtime_root / 'pbr-lab.json').read_text(encoding='utf-8'))
    source_hash = lab.digest(Path(__file__))
    lab.BASE.update(image_anisotropy='1', r_shadowMapSkipStencilShadows='1', r_shadowMapPointLights='1',
                    r_shadowMapCustomGLSLReceiverWrapper='0')
    profile = {}
    specimen = ''
    occluder = False
    projector = ''
    for suffix in CASES:
        name = 'authored-lighting-' + suffix
        settings = dict(r_pbrMaterials='0', r_pbrIBL='0', r_rendererReflectionProbes='0', r_useLightGrid='0',
                        r_rendererModernVisible='1', g_showPlayerShadow='0',
                        r_hdrToneMap='0', image_anisotropy='1', r_lightScale='0.4', r_shadows='0',
                        r_useShadowMap='0', r_shadowMapReport='2')
        commands = ['g_stopTime 0']
        if not profile:
            commands += [f'script "${s["name"]}.hide()"' for s in manifest['stations']]
        commands += [f'script "${light}.Off()"' for light in ('key', 'blue_fill', 'warm_fill', 'lab_projector')]
        if projector:
            commands += [f'script "${projector}.remove()"', 'wait 10']
            projector = ''
        if suffix not in ('image_reload', 'shader_reload', 'partial_restart', 'full_restart'):
            if specimen: commands += [f'script "${specimen}.remove()"', 'wait 10']
            if suffix != 'clear':
                mat = suffix if suffix in MATERIALS else 'base'
                angle = 65 if suffix == 'rotated' else 0
                specimen = 'lighting_specimen_' + suffix
                commands += [f'spawn func_static name {specimen} model "{lab.lab.VERTEX_COLOR_MODEL}" '
                             f'shader "{PREFIX}/{mat}" origin "100 160 120" angle {angle} solid 0']
        if occluder and suffix not in ('stencil', 'mapped', 'projected_stencil', 'projected_mapped'):
            commands += ['script "$lighting_occluder.remove()"', 'wait 10']
            occluder = False
        if suffix in ('occluder_off', 'projected_occluder_off'):
            origin = '100 -170 260' if suffix.startswith('projected') else '60 -30 350'
            commands += [f'spawn func_static name lighting_occluder model "{lab.lab.MODEL}" '
                         f'shader "{lab.lab.PREFIX}/classic_floor" origin "{origin}" angle 0 solid 0']
            occluder = True
        if suffix not in ('clear', 'lights_off'):
            projected = suffix.startswith('projected') or suffix == 'falloff_texture'
            light = 'lab_projector' if projected else 'key'
            if projected:
                texture = 'pattern' if suffix == 'projected_texture' else 'falloff' if suffix == 'falloff_texture' else 'plain'
                projector = 'lighting_projector_' + suffix
                commands += [f'spawn light name {projector} origin "100 -500 400" angle 0 '
                             f'light_target "0 660 -280" light_right "400 0 0" light_up "0 180 425" '
                             f'light_start "0 15 -6.36" light_end "0 1000 -424.24" _color "1.5 1.3 1" '
                             f'texture "lights/openq4/authored_lighting/{texture}"']
            else:
                commands += [f'script "${light}.On()"']
            if suffix == 'second_light': commands += ['script "$blue_fill.On()"']
        if suffix in ('stencil', 'mapped', 'projected_stencil', 'projected_mapped'):
            settings['r_shadows'] = '1'
            settings['r_useShadowMap'] = '1' if suffix.endswith('mapped') else '0'
        commands += {'image_reload': ['reloadImages all'], 'shader_reload': ['reloadGLSLprograms'],
                     'partial_restart': ['vid_restart partial'], 'full_restart': ['vid_restart']}.get(suffix, [])
        commands += ['wait 60', 'g_stopTime 1']
        lab.CASES[name], lab.CASE_COMMANDS[name] = settings, commands
        lab.LEGACY_CASES.add(name)
        profile[name] = dict(settings={**lab.BASE, **settings}, commands=commands)
    write, startup = lab.write_capture_commands, lab.startup_args
    source_hashes = {}

    def write_commands(path, commands):
        source_hashes.update(write_fixture(args.output_dir / 'batch'))
        return write(path, commands)

    def startup_args(cvars, save):
        options = startup(cvars, save)
        with (save / 'baseoq4/autoexec.cfg').open('a', encoding='utf-8') as config:
            for mat in MATERIALS: config.write(f'touch material {PREFIX}/{mat}\n')
            for mat in ('plain', 'pattern', 'falloff'): config.write(f'touch material lights/openq4/authored_lighting/{mat}\n')
        return options

    lab.write_capture_commands, lab.startup_args = write_commands, startup_args
    sys.argv = [__file__, '--runtime-root', str(args.runtime_root), '--output-dir', str(args.output_dir),
                '--basepath', str(args.basepath), '--backend', args.backend, '--cases', ','.join(profile),
                '--batch', '--camera', 'coverage', '--timeout', str(args.timeout)]
    if args.backend == 'gl': sys.argv += ['--gl-debug']
    code = lab.main()
    path = args.output_dir / 'report.json'
    report = json.loads(path.read_text(encoding='utf-8'))
    assert lab.digest(Path(__file__)) == source_hash, 'harness changed during capture'
    shutil.copy2(__file__, args.output_dir / 'harness' / Path(__file__).name)
    report['harnessSources'][Path(__file__).name] = source_hash
    report.update(authoredProfile=profile, authoredSources=source_hashes)
    report['authoredSourcesUnchanged'] = all(lab.digest(args.output_dir / 'batch/baseoq4' / name) == value
                                           for name, value in source_hashes.items())
    report['lightingProof'] = prove(report)
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report['lightingProof'], indent=2))
    return int(code or report['lightingProof']['status'] != 'pass')


if __name__ == '__main__':
    raise SystemExit(main())
