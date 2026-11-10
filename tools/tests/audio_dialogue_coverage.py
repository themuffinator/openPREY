#!/usr/bin/env python3
"""Audit which installed speech reaches the Dialogue Volume control, and how.

Reads one or more game directories in filesystem order (base first, then an
expansion such as q4xbase), finds every reference to a speech-bearing sound
shader in entity definitions, maps, scripts, BSE effects and GUIs, and
classifies each reference with the production classifier from
src/sound/SoundDialogue.h, compiled into a small helper. Speech is a shader with
a same-name lip-sync declaration, a radio line (voForPlayer) or a sample under
sound/vo. A reference is covered when every sample it can select is dialogue to
the mixer for the way that reference plays it (an NPC lip-sync key plays with
SSF_IS_VO; other call sites rely on the shader and the sample path).

The report holds identifiers, reference kinds and counts only: no transcript
text and no audio leave the installed assets.
"""
import argparse
from collections import Counter, defaultdict
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
TOKEN = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|[{}()]|[^\s{}()"]+', re.S)
LITERAL = re.compile(rb'"([^"\\\r\n]{1,256})"')
MAP_PAIR = re.compile(rb'"([^"\r\n]{1,128})"[ \t]+"([^"\r\n]{1,256})"')
KINDS = ('npc_lipsync', 'definition', 'map', 'script', 'effect', 'gui')


def classifier():
    """The production SoundIsDialogue(), compiled from the engine header."""
    (ROOT / '.tmp').mkdir(exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix='dialogue-coverage-', dir=ROOT / '.tmp'))
    source = scratch / 'classify.cpp'
    source.write_text('#include "src/sound/SoundDialogue.h"\n'
                      '#if defined(_WIN32)\n#define EXPORT __declspec(dllexport)\n#else\n#define EXPORT\n#endif\n'
                      'extern "C" EXPORT bool is_dialogue(bool music, bool authored, const char* path) {\n'
                      '    return SoundIsDialogue(music, authored, path);\n}\n', encoding='utf-8')
    library = scratch / ('classify.dll' if os.name == 'nt' else 'classify.so')
    compiler = os.environ.get('CXX') or shutil.which('clang++') or shutil.which('g++')
    if not compiler:
        raise RuntimeError('A C++17 compiler (clang++ or g++) is required for the production classifier')
    subprocess.run([compiler, '-std=c++17', '-shared', '-O1', *([] if os.name == 'nt' else ['-fPIC']),
                    '-I', str(ROOT), str(source), '-o', str(library)], cwd=scratch, check=True)
    helper = ctypes.CDLL(str(library))
    helper.is_dialogue.argtypes = [ctypes.c_bool, ctypes.c_bool, ctypes.c_char_p]
    helper.is_dialogue.restype = ctypes.c_bool
    return lambda music, authored, path: bool(helper.is_dialogue(music, authored, path.encode('utf-8', 'replace')))


def declarations(text):
    """(keyword, name, body tokens) for each top-level declaration."""
    tokens = [m[0] for m in TOKEN.finditer(text) if not m[0].startswith(('//', '/*'))]
    i = 0
    while i < len(tokens):
        start = i
        while i < len(tokens) and tokens[i] != '{':
            i += 1
        if i == len(tokens):
            break
        name = tokens[i - 1].strip('"') if i > start else ''
        keyword = tokens[i - 2].lower() if i - 2 >= start else ''
        i += 1
        begin, depth = i, 1
        while i < len(tokens) and depth:
            depth += (tokens[i] == '{') - (tokens[i] == '}')
            i += 1
        if depth:
            return  # an unterminated last declaration; the engine's parser stops there too
        yield keyword, name.lower(), tokens[begin:i - 1]


class Assets:
    """The virtual filesystem view: later directories and loose files override."""

    def __init__(self, directories, extensions):
        self.entries, self.packages = {}, []
        for directory in directories:
            for pak in sorted(directory.glob('*.pk4'), key=lambda p: p.name.lower()):
                with zipfile.ZipFile(pak) as archive:
                    self.packages.append({'name': f'{directory.name}/{pak.name}', 'size': pak.stat().st_size})
                    for info in archive.infolist():
                        name = info.filename.replace('\\', '/').lower()
                        if name.endswith(extensions):
                            self.entries[name] = (pak, info.filename)
            for path in directory.rglob('*'):
                if path.is_file() and path.suffix.lower() in extensions and path.suffix.lower() != '.pk4':
                    self.entries[path.relative_to(directory).as_posix().lower()] = (None, path)
        self.archives = {}

    def read(self, name):
        pak, original = self.entries[name]
        if pak is None:
            return original.read_bytes()
        if pak not in self.archives:
            self.archives[pak] = zipfile.ZipFile(pak)
        return self.archives[pak].read(original)

    def names(self, *suffixes):
        return sorted(n for n in self.entries if n.endswith(suffixes))


def shader_flags(body):
    lowered = [t.strip('"').lower() for t in body]
    samples = [t.strip('"').replace('\\', '/') for t in body if t.strip('"').lower().startswith('sound/')]
    sound_class = 0
    for i, token in enumerate(lowered[:-1]):
        if token == 'soundclass':
            try:
                sound_class = int(float(lowered[i + 1]))
            except ValueError:
                pass
    music = 'music' in lowered or sound_class == 3 or any(s.lower().startswith('sound/music/') for s in samples)
    return {'samples': samples, 'vo_for_player': 'voforplayer' in lowered, 'music': music}


def audit(directories, is_dialogue):
    assets = Assets(directories, ('.sndshd', '.lipsync', '.def', '.script', '.fx', '.gui', '.map', '.lang'))
    shaders, lips, texts = {}, set(), set()
    for name in assets.names('.sndshd', '.lipsync', '.lang'):
        text = assets.read(name).decode('utf-8', 'replace')
        if name.endswith('.lang'):
            texts.update(re.findall(r'"(#str_\d+)"', text))
            continue
        for keyword, decl, body in declarations(text):
            if name.endswith('.sndshd'):
                shaders[decl] = shader_flags(body)
            elif keyword == 'lipsync' or name.endswith('.lipsync'):
                lips.add(decl)
    speech = {name for name, shader in shaders.items() if name in lips or shader['vo_for_player'] or
              any(re.match(r'(?i)^sound/vo(?:/|_[^/]+/)', sample) for sample in shader['samples'])}
    references = defaultdict(lambda: defaultdict(set))  # shader -> kind -> sources

    def add(value, kind, source):
        value = value.lower()
        if value in speech:
            references[value][kind].add(source)

    for name in assets.names('.def'):
        text = assets.read(name).decode('utf-8', 'replace')
        for keyword, decl, body in declarations(text):
            if keyword != 'entitydef':
                continue
            values = [t.strip('"') for t in body]
            for i in range(0, len(values) - 1, 2):
                key = values[i].lower()
                add(values[i + 1], 'npc_lipsync' if key.startswith('lipsync') else 'definition', decl)
    for name in assets.names('.map'):
        for key, value in MAP_PAIR.findall(assets.read(name)):
            key = key.decode('latin-1').lower()
            add(value.decode('latin-1'), 'npc_lipsync' if key.startswith('lipsync') else 'map', name)
    for suffix, kind in (('.script', 'script'), ('.fx', 'effect'), ('.gui', 'gui')):
        for name in assets.names(suffix):
            for value in LITERAL.findall(assets.read(name)):
                add(value.decode('latin-1'), kind, name)

    rows, gaps = {}, []
    totals = Counter()
    for name in sorted(speech):
        shader = shaders[name]
        kinds = references.get(name, {})
        per_kind = {}
        for kind in KINDS:
            if kind not in kinds:
                continue
            authored = shader['vo_for_player'] or kind == 'npc_lipsync'
            covered = bool(shader['samples']) and all(is_dialogue(shader['music'], authored, s) for s in shader['samples'])
            per_kind[kind] = {'covered': covered, 'sources': len(kinds[kind])}
            totals[(kind, covered)] += 1
            if not covered:
                gaps.append({'shader': name, 'kind': kind, 'sources': sorted(kinds[kind])[:8],
                             'sample_directories': sorted({'/'.join(s.lower().split('/')[:2]) for s in shader['samples']}),
                             'music': shader['music']})
        by_path = bool(shader['samples']) and all(is_dialogue(False, False, s) for s in shader['samples'])
        rows[name] = {'lip_sync': name in lips, 'vo_for_player': shader['vo_for_player'], 'music': shader['music'],
                      'path_classified': by_path, 'referenced': per_kind}
        totals['path_classified' if by_path else 'flag_dependent'] += 1
        if not per_kind:
            totals['unreferenced'] += 1
    summary = {
        'speech_shaders': len(speech),
        'path_classified': totals['path_classified'],
        'flag_dependent': totals['flag_dependent'],
        'unreferenced_by_scanned_sources': totals['unreferenced'],
        'references': {kind: {'covered': totals[(kind, True)], 'gaps': totals[(kind, False)]} for kind in KINDS},
        'gap_references': len(gaps),
    }
    hashes = {name: hashlib.sha256(assets.read(name)).hexdigest()
              for name in assets.names('.sndshd', '.lipsync', '.def')}
    return {'directories': [str(d) for d in directories], 'packages': assets.packages, 'summary': summary,
            'gaps': gaps, 'speech': rows, 'decl_sha256': hashes,
            'limitations': ['Static references: scripts, effects and GUIs are matched by string literals equal to a speech '
                            'shader name, so a computed name is not seen and an unused literal is counted.',
                            'Classification follows the production rules for the way each reference plays its shader; '
                            'it does not establish that a scene is audible or that a line is ever played.',
                            'Speech without a lip-sync declaration, a radio flag or a sound/vo sample (for example '
                            'non-verbal effort sounds) is outside this audit.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, action='append', required=True,
                        help='A game directory with PK4s; repeat for layered directories, base first')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    directories = [d.resolve(strict=True) for d in args.assets]
    report = audit(directories, classifier())
    report['harness_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['classifier_sha256'] = hashlib.sha256((ROOT / 'src/sound/SoundDialogue.h').read_bytes()).hexdigest()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(output), 'summary': report['summary']}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
