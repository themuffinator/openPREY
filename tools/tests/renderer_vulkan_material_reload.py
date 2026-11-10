#!/usr/bin/env python3
"""Qualify authored source selection, live GLSL reload and failed-source repair.

Shader edits are confined to the isolated save directory. An engine-scripted
marker gives the file watcher time to edit before the registered reload command.
Rendering evidence comes only from engine screenshots; no input is injected.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import threading
import time

import numpy as np
from PIL import Image

import renderer_pbr_laboratory as lab
import renderer_vulkan_material_programs as authored

PREFIX = 'textures/openq4/authored_reload'
PROGRAMS = {'namespace': 'tests/Displacement.glsl',
            'canonical': 'glsl/Displacement.glsl', 'partial': 'glsl/Water.glsl'}
CASES = ('clear', 'namespace', 'canonical', 'fragment_edit', 'vertex_edit',
         'invalid', 'still_invalid', 'repaired', 'partial_pair',
         'partial_still_invalid', 'partial_repaired', 'partial_restart',
         'full_restart', 'arb_reload', 'restored', 'namespace_restored')
FRAGMENT_EDIT = authored.FRAGMENT.replace('texture2D(Image, UV).rgb * Tint.rgb',
                                         'texture2D(Image, UV).bgr * Tint.gbr')
VERTEX_EDIT = authored.VERTEX.replace('position.x += Offset.x;', 'position.x += Offset.x + 80.0;').replace(
    'position.z += Offset.y;', 'position.z += Offset.y + 45.0;')
INVALID_FRAGMENT = authored.FRAGMENT.replace('texture2D(Image, UV).rgb * Tint.rgb', 'missingShaderIdentifier')


def source_path(program: str, fragment: bool) -> str:
    return 'glprogs/' + program.removesuffix('.glsl') + ('.glslfp' if fragment else '.glslvp')


EDITS = {
    'fragment_edit': {source_path(PROGRAMS['canonical'], True): FRAGMENT_EDIT},
    'vertex_edit': {source_path(PROGRAMS['canonical'], False): VERTEX_EDIT},
    'invalid': {source_path(PROGRAMS['canonical'], True): INVALID_FRAGMENT},
    'repaired': {source_path(PROGRAMS['canonical'], False): authored.VERTEX,
                 source_path(PROGRAMS['canonical'], True): authored.FRAGMENT},
    'partial_repaired': {source_path(PROGRAMS['partial'], False): authored.VERTEX},
    'arb_reload': {source_path(PROGRAMS['partial'], True): FRAGMENT_EDIT},
    'restored': {source_path(PROGRAMS['partial'], True): authored.FRAGMENT},
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def material(name: str) -> str:
    return f'''{PREFIX}/{name}
{{
    translucent
    twoSided
    noShadows
    {{
        blend blend
        glslProgram {PROGRAMS[name]}
        shaderParm Offset 0, 0, 0, 0
        shaderParm Tint 0.7, 0.3, 0.1, 1
        shaderParm Mode 0, 0, 0, 0
        shaderTexture Image nearest clamp {PREFIX}/pattern
    }}
}}
'''


def write_fixture(save: Path) -> dict[str, str]:
    files = {'materials/openq4_authored_reload_test.mtr': ''.join(material(n) for n in PROGRAMS).encode('utf-8')}
    for name, program in PROGRAMS.items():
        files[source_path(program, True)] = authored.FRAGMENT.encode('utf-8')
        if name != 'partial':
            files[source_path(program, False)] = authored.VERTEX.encode('utf-8')
    pixels = bytes(component for y in range(32) for x in range(32)
                   for component in (64 + 128 * ((x // 8 + y // 8) % 2), 32 + 7 * y, 32 + 7 * x, 255))
    files[f'{PREFIX}/pattern.tga'] = authored.tga(32, 32, pixels)
    for name, data in files.items():
        path = save / 'baseoq4' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return {name: sha(data) for name, data in files.items()}


def expected_diagnostic(section: str | None, line: str) -> bool:
    """Allow only the deliberate shader failures, inside explicit log bounds."""
    line = re.sub(r'\^[0-9]', '', line).strip()
    if re.search(r'VUID-|GL_INVALID|source=api\b', line):
        return False
    if section == 'SYNTAX':
        if line in ("WARNING: GLSL fragment shader compile error in 'glsl/Displacement.glsl':",
                    "WARNING: Vulkan authored GLSL 'glsl/Displacement.glsl': glprogs/glsl/Displacement.glslfp: authored GLSL compilation failed"):
            return True
        if re.match(r'GL debug callback \[source=shader\b.*missingShaderIdentifier', line):
            return True
        compiler = re.fullmatch(r'ERROR: glprogs/glsl/Displacement\.glslfp:7: (.*)', line)
        if compiler:
            return bool(re.fullmatch(
                r"'missingShaderIdentifier' : undeclared identifier|'' : compilation terminated|"
                r"'=' :\s+cannot convert from ' temp float' to ' temp 3-component vector of float'", compiler[1]))
        return bool(re.fullmatch(r'ERROR: \d+ compilation errors\.\s+No code generated\.', line))
    if section == 'PAIR':
        return line in ("WARNING: Couldn't find GLSL sources for program 'glsl/Water.glsl'",
                        "WARNING: Vulkan authored GLSL 'glsl/Water.glsl': could not find a complete vertex/fragment source pair")
    return False


def diagnostic_partition(text: str) -> tuple[list[str], list[str]]:
    unexpected, expected, section = [], [], None
    for line in text.splitlines():
        marker = re.fullmatch(r'MATERIAL_NEGATIVE_(SYNTAX|PAIR)_(BEGIN|END)', line.strip())
        if marker:
            section = marker[1] if marker[2] == 'BEGIN' else None
        if lab.DIAGNOSTIC.search(line) and not re.search(r'GL debug callback \[.*type=(?:performance|notification)\b', line):
            (expected if expected_diagnostic(section, line) else unexpected).append(line)
    return unexpected, expected


def diagnostic_proof(text: str, backend: str) -> dict:
    failures, sections = [], {}
    unexpected, expected = diagnostic_partition(text)
    if unexpected:
        failures.append('unexpected engine diagnostics')
    needles = {
        'SYNTAX': ("GLSL fragment shader compile error in 'glsl/Displacement.glsl'" if backend == 'gl'
                   else "Vulkan authored GLSL 'glsl/Displacement.glsl': glprogs/glsl/Displacement.glslfp: authored GLSL compilation failed"),
        'PAIR': ("Couldn't find GLSL sources for program 'glsl/Water.glsl'" if backend == 'gl'
                 else "Vulkan authored GLSL 'glsl/Water.glsl': could not find a complete vertex/fragment source pair"),
    }
    for section, needle in needles.items():
        begin, end = (f'MATERIAL_NEGATIVE_{section}_{suffix}' for suffix in ('BEGIN', 'END'))
        if text.count(begin) != 1 or text.count(end) != 1 or text.find(end) < text.find(begin):
            failures.append(section + ': negative diagnostic bounds missing or repeated')
            continue
        bounded = text.split(begin, 1)[1].split(end, 1)[0]
        count = sum(needle in line and 'WARNING:' in line for line in bounded.splitlines())
        sections[section] = dict(primaryFailures=count)
        if count != 1:
            failures.append(section + ': expected exactly one compile attempt before explicit repair/reload')
        if section == 'SYNTAX' and 'missingShaderIdentifier' not in bounded:
            failures.append('deliberately invalid identifier absent from compiler diagnostic')
    return dict(failures=failures, sections=sections, expected=expected, unexpected=unexpected)


def prove(report: dict) -> dict:
    failures, checks, images = [], {}, {}
    rows = {row['case'].removeprefix('authored-reload-'): row for row in report['results']}
    if not report.get('complete') or not report.get('runtimeUnchanged') or set(rows) != set(CASES):
        failures.append('incomplete or changed capture set/runtime')
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
    edits = report.get('sourceEdits', [])
    if [entry['edit'] for entry in edits] != list(EDITS) or report.get('sourceEditErrors'):
        failures.append('live source edits incomplete or out of order')
    state = dict(report.get('initialSources', {}))
    for entry in edits:
        intended = EDITS.get(entry['edit'], {})
        if set(entry['files']) != set(intended):
            failures.append('source edit file set mismatch: ' + entry['edit'])
        for name, hashes in entry['files'].items():
            if hashes['before'] != state.get(name) or hashes['after'] != sha(intended.get(name, '').encode('utf-8')):
                failures.append('source edit content mismatch: ' + name)
            state[name] = hashes['after']
    if state != report.get('finalSources'):
        failures.append('final fixture source set does not match recorded edits')
    if report['results']:
        row = report['results'][0]
        path = Path(row['log'])
        if path.is_file():
            text = path.read_text(encoding='utf-8', errors='replace')
            diagnostics = diagnostic_proof(text, row['backend'])
            failures += diagnostics['failures']
            checks['diagnostics'] = diagnostics
            if row['backend'] == 'vk':
                for program in ('smaa_edge.fs', 'smaa_weights.fs', 'smaa_blend.fs'):
                    if f"Vulkan: GLSL source selection '{program}': verified native source" not in text:
                        failures.append('reviewed native source selection missing: ' + program)
                for program in PROGRAMS.values():
                    if f"Vulkan: drawing authored GLSL '{program}'" not in text:
                        failures.append('authored draw missing: ' + program)
                for program in (PROGRAMS['canonical'], PROGRAMS['partial']):
                    if f"Vulkan: GLSL source selection '{program}': authored source" not in text:
                        failures.append('canonical source override selection missing: ' + program)
                    if re.search(rf"GLSL source selection '{re.escape(program)}': (?:verified native|built-in default)", text):
                        failures.append('authored override selected a native default: ' + program)
    if set(images) == set(CASES):
        for name, reference in [('namespace', 'clear'), ('fragment_edit', 'canonical'), ('vertex_edit', 'fragment_edit')]:
            delta = np.abs(images[name] - images[reference]).max(axis=2)
            count = int(np.count_nonzero(delta > 2))
            checks[name] = dict(changedPixels=count, maximumError=int(delta.max()))
            if count < 1000:
                failures.append(name + ': control lacks a visible response')
        references = {name: 'namespace' for name in ('canonical', 'repaired', 'partial_repaired',
                      'partial_restart', 'full_restart', 'restored', 'namespace_restored')}
        references.update({name: 'clear' for name in ('invalid', 'still_invalid', 'partial_pair', 'partial_still_invalid')})
        references['arb_reload'] = 'fragment_edit'
        for name, reference in references.items():
            delta = np.abs(images[name] - images[reference]).max(axis=2)
            checks[name] = dict(reference=reference, differingPixels=int(np.count_nonzero(delta)), maximumError=int(delta.max()))
            if np.any(delta):
                failures.append(name + ': image differs from its exact recovery/failure reference')
    return dict(status='fail' if failures else 'pass', failures=failures, checks=checks)


def compare(left: Path, right: Path) -> dict:
    reports = [json.loads(path.read_text(encoding='utf-8')) for path in (left, right)]
    failures, checks = [], {}
    for report in reports:
        failures += prove(report)['failures']
    for field in ('initialSources', 'finalSources', 'runtimeSHA256', 'compiledMapSHA256'):
        if reports[0].get(field) != reports[1].get(field):
            failures.append('renderer comparison inputs differ: ' + field)
    if any(row['backend'] != backend for report, backend in zip(reports, ('gl', 'vk')) for row in report['results']):
        failures.append('comparison requires an OpenGL reference and Vulkan candidate')
    for a, b in zip(reports[0]['results'], reports[1]['results']):
        if a['case'] != b['case']:
            failures.append('case ordering mismatch')
            continue
        if not all(Path(row['screenshot']).is_file() for row in (a, b)):
            continue
        images = [np.asarray(Image.open(row['screenshot']).convert('RGB'), dtype=np.int16) for row in (a, b)]
        delta = np.abs(images[0] - images[1]).max(axis=2)
        checks[a['case']] = dict(maximumError=int(delta.max()), differingPixels=int(np.count_nonzero(delta)),
                                overTolerancePixels=int(np.count_nonzero(delta > 2)))
        if np.any(delta > 2):
            failures.append(a['case'] + ': cross-renderer error exceeds two display levels')
    return dict(status='fail' if failures else 'pass', failures=failures, checks=checks,
                reports={str(path.resolve()): lab.digest(path) for path in (left, right)})


def main() -> int:
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
    sources = {Path(__file__): lab.digest(Path(__file__)), Path(authored.__file__): lab.digest(Path(authored.__file__))}
    manifest = json.loads((args.runtime_root / 'pbr-lab.json').read_text(encoding='utf-8'))
    lab.BASE.update(image_anisotropy='1')
    profile = {}
    for suffix in CASES:
        name = 'authored-reload-' + suffix
        settings = dict(r_pbrMaterials='0', r_pbrIBL='0', r_rendererReflectionProbes='0',
                        r_useLightGrid='0', r_pbrDebug='0', r_hdrToneMap='0', image_anisotropy='1')
        commands = ['g_stopTime 0']
        if not profile:
            commands += [f'script "${station["name"]}.hide()"' for station in manifest['stations']]
            commands += [f'script "${light}.Off()"' for light in ('key', 'blue_fill', 'warm_fill', 'lab_projector')]
        if suffix in ('invalid', 'partial_pair'):
            commands += ['echo MATERIAL_NEGATIVE_' + ('SYNTAX' if suffix == 'invalid' else 'PAIR') + '_BEGIN']
        if suffix in ('repaired', 'partial_repaired'):
            commands += ['echo MATERIAL_NEGATIVE_' + ('SYNTAX' if suffix == 'repaired' else 'PAIR') + '_END']
        if suffix in ('namespace', 'canonical', 'partial_pair', 'namespace_restored'):
            if suffix != 'namespace':
                commands += ['script "$reload_specimen.remove()"', 'wait 3']
            material_name = {'partial_pair': 'partial', 'namespace_restored': 'namespace'}.get(suffix, suffix)
            commands += [f'spawn func_static name reload_specimen model "{lab.lab.MODEL}" '
                         f'shader "{PREFIX}/{material_name}" origin "100 160 120" angle 0 solid 0']
        if suffix in EDITS:
            commands += [f'echo MATERIAL_EDIT_{suffix}', 'wait 180',
                         'reloadARBprograms' if suffix == 'arb_reload' else 'reloadGLSLprograms']
        commands += {'partial_restart': ['vid_restart partial'], 'full_restart': ['vid_restart']}.get(suffix, [])
        commands += ['wait 60', 'g_stopTime 1']
        lab.CASES[name], lab.CASE_COMMANDS[name] = settings, commands
        lab.LEGACY_CASES.add(name)
        profile[name] = dict(settings={**lab.BASE, **settings}, commands=commands)
    write, startup, run = lab.write_capture_commands, lab.startup_args, lab.run
    source_hashes, journal, errors = {}, [], []
    save = args.output_dir / 'batch'

    def write_commands(path, commands):
        source_hashes.update(write_fixture(save))
        return write(path, commands)

    def startup_args(cvars, directory):
        options = startup(cvars, directory)
        with (directory / 'baseoq4/autoexec.cfg').open('a', encoding='utf-8') as config:
            for name in PROGRAMS:
                config.write(f'touch material {PREFIX}/{name}\n')
        return options

    def run_with_edits(command, cwd, output, timeout):
        stop = threading.Event()

        def watch():
            log = save / 'baseoq4/logs/openq4.log'
            pending = list(EDITS)
            started = time.monotonic()
            try:
                while pending and not stop.wait(0.02):
                    if time.monotonic() - started > timeout:
                        raise TimeoutError('source edit watcher deadline expired')
                    text = log.read_text(encoding='utf-8', errors='replace') if log.is_file() else ''
                    edit = pending[0]
                    if not re.search(rf'(?m)^MATERIAL_EDIT_{re.escape(edit)}\s*$', text):
                        continue
                    entry = dict(edit=edit, seconds=time.monotonic() - started, files={})
                    for name, content in EDITS[edit].items():
                        path = save / 'baseoq4' / name
                        before = lab.digest(path) if path.is_file() else None
                        temporary = path.with_suffix(path.suffix + '.pending')
                        temporary.write_bytes(content.encode('utf-8'))
                        temporary.replace(path)
                        entry['files'][name] = dict(before=before, after=lab.digest(path))
                    journal.append(entry)
                    (args.output_dir / 'source-edits.json').write_text(json.dumps(journal, indent=2) + '\n', encoding='utf-8')
                    pending.pop(0)
            except Exception as error:
                errors.append(str(error))

        watcher = threading.Thread(target=watch, name='material-source-edits', daemon=True)
        watcher.start()
        try:
            return run(command, cwd, output, timeout)
        finally:
            stop.set()
            watcher.join(timeout=5)
            if watcher.is_alive():
                errors.append('source edit watcher did not stop')

    lab.write_capture_commands, lab.startup_args, lab.run = write_commands, startup_args, run_with_edits
    lab.diagnostic_lines = lambda text: diagnostic_partition(text)[0]
    sys.argv = [__file__, '--runtime-root', str(args.runtime_root), '--output-dir', str(args.output_dir),
                '--basepath', str(args.basepath), '--backend', args.backend, '--cases', ','.join(profile),
                '--batch', '--camera', 'coverage', '--timeout', str(args.timeout)]
    if args.backend == 'gl':
        sys.argv += ['--gl-debug']
    code = lab.main()
    path = args.output_dir / 'report.json'
    report = json.loads(path.read_text(encoding='utf-8'))
    for source, digest in sources.items():
        assert lab.digest(source) == digest, 'capture harness changed during run'
        shutil.copy2(source, args.output_dir / 'harness' / source.name)
        report['harnessSources'][source.name] = digest
    names = set(source_hashes) | {name for edits in EDITS.values() for name in edits}
    final_sources = {name: lab.digest(save / 'baseoq4' / name) if (save / 'baseoq4' / name).is_file() else None
                     for name in sorted(names)}
    report.update(reloadProfile=profile, initialSources=source_hashes, finalSources=final_sources,
                  sourceEdits=journal, sourceEditErrors=errors)
    report['reloadProof'] = prove(report)
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report['reloadProof'], indent=2))
    return int(code or report['reloadProof']['status'] != 'pass')


if __name__ == '__main__':
    raise SystemExit(main())
