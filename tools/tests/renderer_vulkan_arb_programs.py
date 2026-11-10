#!/usr/bin/env python3
"""Qualify authored ARB assembly material programs against OpenGL.

OpenGL executes ARB_vertex_program/ARB_fragment_program natively; Vulkan
translates them to GLSL (src/renderer/materialprogram/ARBTranslator.cpp).
Every fixture program here is original and lives only in the isolated save
directory. The compiled PBR laboratory supplies geometry; stock assets stay
read-only. Captures use the engine's screenshot command; no desktop capture
or input automation is used.

    renderer_vulkan_arb_programs.py --runtime-root R --basepath B --backend gl --output-dir out/gl
    renderer_vulkan_arb_programs.py --runtime-root R --basepath B --backend vk --output-dir out/vk
    renderer_vulkan_arb_programs.py --compare out/gl/report.json out/vk/report.json --output-dir out/cmp
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

PREFIX = 'textures/openq4/authored_arb'

# Scroll and tint: vertexParm feeds both programs' locals.
BASIC = '''!!ARBvp1.0
OPTION ARB_position_invariant;
# local[0] scroll, local[1] tint (shared with the fragment program)
ADD result.texcoord[0], vertex.texcoord[0], program.local[0];
MOV result.color, vertex.color;
END

!!ARBfp1.0
TEMP c;
TEX c, fragment.texcoord[0], texture[0], 2D;
MUL result.color.rgb, c, program.local[1];
MOV result.color.a, 1.0;
END
'''

# fragmentParm replaces the shared locals for the fragment program only.
SPLIT = '''!!ARBvp1.0
OPTION ARB_position_invariant;
MOV result.texcoord[0], vertex.texcoord[0];
END

!!ARBfp1.0
TEMP c;
TEX c, fragment.texcoord[0], texture[0], 2D;
MAD result.color.rgb, c, program.local[0], program.local[1];
MOV result.color.a, 1.0;
END
'''

# A deterministic color from the texture coordinates through most ALU
# instructions. Every temporary is written before it is read (ARB leaves
# temporaries undefined), selections use constant conditions, and visible
# outputs stay continuous so the comparison never sits on a discontinuity.
MATH = '''!!ARBvp1.0
OPTION ARB_position_invariant;
PARAM half = 0.5;
TEMP t, u;
MOV t, vertex.texcoord[0];
MUL u, t, half;
FRC u, u;
EXP t, u.x;
LOG t.y, u.y;
SGE u.z, half, half;
SLT u.w, half, half;
DST t, u, u.yxwz;
MOV result.texcoord[0], vertex.texcoord[0];
MAD result.texcoord[1], t, 0.001, u;
END

!!ARBfp1.0
PARAM k = { 6.2831853, 0.25, 4.0, 0.5 };
PARAM table[3] = { { 0.9, 0.2, 0.1, 1 }, { 0.1, 0.8, 0.3, 1 }, program.local[0] };
TEMP uv, a, b, c, d, e, f, r;
MOV uv, fragment.texcoord[0];
MOV b, 0;
MOV c, 0;
MUL a, uv, k.x;
SIN b.x, a.x;
COS b.y, a.y;
SCS c.xy, a.x;
MAD b, b, k.w, k.w;
MAD c, c, k.w, k.w;
POW r.x, uv.x, k.z;
EX2 r.y, uv.y;
MUL r.y, r.y, 0.5;
LG2 r.z, k.z;
MUL r.z, r.z, k.y;
ADD a, uv, 0.25;
RSQ r.w, a.x;
RCP a.w, a.y;
MUL a.w, a.w, 0.2;
LRP a.xyz, uv.x, table[0], table[2];
XPD d, b, c;
ABS d, d;
DP3 d.w, b, c;
CMP f.x, -k.y, b.x, b.y;
CMP f.y, k.y, b.x, b.y;
SGE f.z, k.y, k.y;
SLT f.w, k.w, k.y;
MAD e, uv, 0.5, 0.25;
FRC e.xy, e;
FLR e.zw, a;
MAX d, d, 0.05;
MIN d, d, 0.95;
LIT c, b;
SWZ a, a, z, -x, 1, 0;
ADD a.y, a.y, 1;
MAD_SAT r, r, 0.5, a;
MOV_SAT c.rgb, c;
ADD r.rgb, r, c;
MAD r.rgb, d, 0.25, r;
MAD r.rgb, e, 0.1, r;
MAD r.rgb, f, 0.2, r;
DP4 e.w, uv, k;
MUL result.color.rgb, r, 0.38;
MOV result.color.a, 1.0;
END
'''

# Fragment window coordinates and the fragment program environment.
WINDOW = '''!!ARBvp1.0
OPTION ARB_position_invariant;
END

!!ARBfp1.0
TEMP p;
MUL p, fragment.position, program.env[1];
MUL p.xy, p, { 3, 2, 0, 0 };
FRC p.xy, p;
MOV p.z, program.env[0].x;
MOV result.color.rgb, p;
MOV result.color.a, 1.0;
END
'''

# The vertex program environment: global eye, local eye and model rows.
EYE = '''!!ARBvp1.0
OPTION ARB_position_invariant;
TEMP v, g;
SUB v, program.env[5], vertex.position;
DP3 g.x, v, program.env[6];
DP3 g.y, v, program.env[7];
DP3 g.z, v, program.env[8];
DP3 v.w, g, g;
RSQ v.w, v.w;
MUL g, g, v.w;
MAD result.texcoord[1], g, 0.5, 0.5;
SUB v, program.env[1], vertex.position;
DP3 v.w, v, v;
RSQ v.w, v.w;
MUL v, v, v.w;
MAD result.texcoord[2], v, 0.5, 0.5;
END

!!ARBfp1.0
TEMP c;
LRP c.rgb, 0.75, fragment.texcoord[1], fragment.texcoord[2];
MOV result.color.rgb, c;
MOV result.color.a, 1.0;
END
'''

# Explicit (non-invariant) transform through matrix state, relative
# addressing and matrix modifiers.
MATRIX = '''!!ARBvp1.0
PARAM mvp[4] = { state.matrix.mvp };
PARAM colors[] = { { 0.9, 0.1, 0.1, 1 }, { 0.1, 0.9, 0.1, 1 }, { 0.1, 0.1, 0.9, 1 } };
PARAM rowT = state.matrix.modelview.transpose.row[3];
PARAM rowI = state.matrix.projection.inverse.row[2];
ADDRESS a;
TEMP t;
DP4 result.position.x, mvp[0], vertex.position;
DP4 result.position.y, mvp[1], vertex.position;
DP4 result.position.z, mvp[2], vertex.position;
DP4 result.position.w, mvp[3], vertex.position;
ARL a.x, program.local[0].x;
MOV t, colors[a.x + 1];
MUL t.w, rowT.w, rowI.w;
MOV result.texcoord[0], vertex.texcoord[0];
MOV result.texcoord[1], t;
END

!!ARBfp1.0
TEMP c;
TEX c, fragment.texcoord[0], texture[0], 2D;
MUL result.color.rgb, c, fragment.texcoord[1];
MOV result.color.a, 1.0;
END
'''

# Cube and projective sampling, and KIL.
SAMPLING = '''!!ARBvp1.0
OPTION ARB_position_invariant;
TEMP d;
MAD d, vertex.texcoord[0], 2, -1;
MOV d.z, 3.0;
MOV result.texcoord[0], d;
MUL d, vertex.texcoord[0], 2;
MOV d.w, 2;
MOV result.texcoord[1], d;
MOV result.texcoord[2], vertex.texcoord[0];
END

!!ARBfp1.0
TEMP a, b, k;
SUB k, fragment.texcoord[2].x, 0.1;
KIL k;
TEX a, fragment.texcoord[0], texture[1], CUBE;
TXP b, fragment.texcoord[1], texture[0], 2D;
LRP result.color.rgb, 0.5, a, b;
MOV result.color.a, 1.0;
END
'''

# A fragment program with the fixed-function vertex stage it replaces.
FIXED_VERTEX = '''!!ARBfp1.0
TEMP c;
TEX c, fragment.texcoord[0], texture[0], 2D;
MUL result.color.rgb, c.bgra, { 1, 0.6, 0.8, 1 };
MOV result.color.a, 1.0;
END
'''

# The laboratory renders through the fast no-post path, so _currentRender
# consumers are covered by the stock heat-haze comparison instead.
PROGRAMS = {
    'basic': BASIC, 'split': SPLIT, 'math': MATH, 'window': WINDOW, 'eye': EYE,
    'matrix': MATRIX, 'sampling': SAMPLING, 'fixed_vertex': FIXED_VERTEX,
}

# name: (stage body, reference case for the visible-response check)
CONTROLS = {
    'basic': ('program tests/oq4_arb_basic.vfp\n'
              'vertexParm 0 0.125, 0.25, 0, 0\nvertexParm 1 0.7, 0.3, 0.1, 1\n'
              'fragmentMap 0 nearest clamp ' + PREFIX + '/pattern', 'clear'),
    'basic_tint': ('program tests/oq4_arb_basic.vfp\n'
                   'vertexParm 0 0.125, 0.25, 0, 0\nvertexParm 1 0.1, 0.65, 0.4, 1\n'
                   'fragmentMap 0 nearest clamp ' + PREFIX + '/pattern', 'basic'),
    'split': ('vertexProgram tests/oq4_arb_split.vfp\nfragmentProgram tests/oq4_arb_split.vfp\n'
              'vertexParm 0 9, 9, 9, 9\nfragmentParm 0 0.5, 0.25, 0.75, 1\nfragmentParm 1 0.1, 0.2, 0, 0\n'
              'fragmentMap 0 nearest clamp ' + PREFIX + '/pattern', 'basic'),
    'math': ('program tests/oq4_arb_math.vfp\nvertexParm 0 0.3, 0.6, 0.9, 1', 'basic'),
    'window': ('program tests/oq4_arb_window.vfp', 'basic'),
    'eye': ('program tests/oq4_arb_eye.vfp', 'basic'),
    'matrix': ('program tests/oq4_arb_matrix.vfp\nvertexParm 0 1, 0, 0, 0\n'
               'fragmentMap 0 nearest clamp ' + PREFIX + '/pattern', 'basic'),
    'sampling': ('program tests/oq4_arb_sampling.vfp\n'
                 'fragmentMap 0 nearest clamp ' + PREFIX + '/pattern\n'
                 'fragmentMap 1 cubeMap nearest clamp ' + PREFIX + '/cube', 'basic'),
    'fixed_vertex': ('fragmentProgram tests/oq4_arb_fixed_vertex.vfp\n'
                     'fragmentMap 0 nearest clamp ' + PREFIX + '/pattern', 'basic'),
}
RECOVERY = ('base-restored', 'image-reload', 'shader-reload', 'partial-restart', 'full-restart')
CASES = ('clear', *CONTROLS, *RECOVERY)


def material(name: str, body: str) -> str:
    return f'''{PREFIX}/{name}
{{
    translucent
    twoSided
    noShadows
    {{
        blend blend
        {body.replace(chr(10), chr(10) + '        ')}
    }}
}}
'''


def tga(width: int, height: int, pixels: bytes) -> bytes:
    header = bytearray(18)
    header[2] = 2
    struct.pack_into('<HHBB', header, 12, width, height, 32, 8)
    return bytes(header) + pixels


def write_fixture(save: Path) -> dict:
    files = {f'glprogs/tests/oq4_arb_{name}.vfp': text.encode('utf-8') for name, text in PROGRAMS.items()}
    files['materials/openq4_authored_arb_test.mtr'] = ''.join(
        material(name, body) for name, (body, _) in CONTROLS.items()).encode('utf-8')
    # The asymmetric nearest-filtered pattern exposes flipped or offset
    # coordinates and wrong texture binding.
    pixels = bytes(component for y in range(32) for x in range(32)
                   for component in (64 + 128 * ((x // 8 + y // 8) % 2), 32 + 7 * y, 32 + 7 * x, 255))
    files[f'{PREFIX}/pattern.tga'] = tga(32, 32, pixels)
    # Every sampling direction points into +Z, so only that face is
    # distinct: a wrong face or target is visible and no face edge crosses.
    for face in ('px', 'nx', 'py', 'ny', 'pz', 'nz'):
        color = (230, 120, 40, 255) if face == 'pz' else (30, 60, 200, 255)
        files[f'{PREFIX}/cube_{face}.tga'] = tga(4, 4, bytes(color) * 16)
    hashes = {}
    for name, data in files.items():
        path = save / 'baseoq4' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        hashes[name] = lab.digest(path)
    return hashes


def load_images(report: dict, failures: list) -> dict:
    images = {}
    for row in report['results']:
        name = row['case'].removeprefix('authored-arb-')
        failures.extend(name + ': ' + error for error in row['failures'])
        valid = True
        for kind in ('screenshot', 'log'):
            path = Path(row.get(kind, ''))
            if not path.is_file() or lab.digest(path) != row['sha256'].get(kind):
                failures.append(name + ': missing or changed ' + kind)
                valid = False
        if valid:
            images[name] = np.asarray(Image.open(row['screenshot']).convert('RGB'), dtype=np.int16)
    return images


def prove(report: dict) -> dict:
    failures, checks = [], {}
    rows = {row['case'].removeprefix('authored-arb-') for row in report['results']}
    if not report.get('complete') or not report.get('runtimeUnchanged') or rows != set(CASES):
        failures.append('incomplete or changed capture set/runtime')
    if not report.get('authoredSourcesUnchanged'):
        failures.append('authored source files changed during capture')
    images = load_images(report, failures)
    if report['results'] and report['results'][0]['backend'] == 'vk':
        log = Path(report['results'][0]['log']).read_text(encoding='utf-8', errors='replace')
        for name in PROGRAMS:
            if f"Vulkan: drawing authored ARB 'tests/oq4_arb_{name}.vfp'" not in log:
                failures.append(f'{name}: program did not reach the Vulkan ARB draw path')
        if 'authored ARB material program stage skipped' in log or '; the stage is skipped' in log:
            failures.append('an authored ARB program was skipped')
    if set(images) == set(CASES):
        for name, (_, reference) in CONTROLS.items():
            delta = np.abs(images[name] - images[reference]).max(axis=2)
            count = int(np.count_nonzero(delta > 2))
            checks[name] = dict(changedPixels=count, maximumError=int(delta.max()))
            if count < 1000:
                failures.append(name + ': control lacks a visible response')
        for name in RECOVERY:
            delta = np.abs(images[name] - images['basic']).max(axis=2)
            checks[name] = dict(differingPixels=int(np.count_nonzero(delta)), maximumError=int(delta.max()))
            if np.any(delta):
                failures.append(name + ': recovery changed the basic image')
    return dict(status='fail' if failures else 'pass', failures=failures, checks=checks)


def compare(left: Path, right: Path) -> dict:
    reports = [json.loads(path.read_text(encoding='utf-8')) for path in (left, right)]
    failures, checks = [], {}
    for report in reports:
        failures += prove(report)['failures']
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
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
        name = 'authored-arb-' + suffix
        settings = dict(r_pbrMaterials='0', r_pbrIBL='0', r_rendererReflectionProbes='0',
                        r_useLightGrid='0', r_pbrDebug='0', r_hdrToneMap='0', image_anisotropy='1')
        commands = ['g_stopTime 0']
        if not profile:
            commands += [f'script "${s["name"]}.hide()"' for s in manifest['stations']]
            commands += [f'script "${s}.Off()"' for s in ('key', 'blue_fill', 'warm_fill', 'lab_projector')]
        if suffix in CONTROLS or suffix == 'base-restored':
            if suffix != 'basic':
                commands += ['script "$authored_specimen.remove()"', 'wait 3']
            mat = 'basic' if suffix == 'base-restored' else suffix
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
    # Spawning parses the fixture materials during the map, which the engine
    # reports as a non-precached decl. Only that notice, for these fixture
    # materials, is excused; every other diagnostic still fails the capture.
    diagnostics = lab.diagnostic_lines

    def fixture_diagnostics(text):
        return [line for line in diagnostics(text)
                if f'Loading non pre-cached material decl {PREFIX}/' not in line]

    lab.diagnostic_lines = fixture_diagnostics
    # Unlike the GLSL laboratory, the fixture materials are not touched from
    # autoexec.cfg: OpenGL assigns ARB program handles only once its context
    # exists, so a material parsed earlier would lose its programs there.
    # Spawning the specimen parses each material after renderer start.
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
