#!/usr/bin/env python3
"""Revise GUI source inventory without accepting a translation or requirement.

Inputs are lexical_inventory reports for explicit VFS configurations. Only
metadata is saved; retail source/art stays outside Git. The prior manifest is
bound to an immutable Git object, and changed source/include closures lose
acceptance. This is separate from checkpoint and product acceptance modes.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess

from legacy_inventory import family_hint, qpath


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def snapshot(reports: dict) -> dict:
    configurations = {}
    for name, report in sorted(reports.items()):
        if not name or not report.get('mounts_low_to_high'):
            raise ValueError('Every configuration needs a name and explicit mounts')
        records = {}
        for row in report['resources']:
            path = qpath(row['path'])
            if path in records:
                raise ValueError(f'Duplicate resource: {name}/{path}')
            if len(row['text_sha256']) != 64 or row['sha256'] not in row['line_ending_sha256']:
                raise ValueError(f'Missing source identity: {path}')
            records[path] = {
                'path': path, 'source': row['source'], 'sha256': row['sha256'],
                'text_sha256': row['text_sha256'], 'line_ending_sha256': row['line_ending_sha256'],
                'includes': [item['resolved'] for item in row['includes']],
                'window_types': sorted({w['type'] for w in row['windows']}),
                'source_diagnostics': row['diagnostics'],
            }
        for row in records.values():
            visited = set()
            def visit(path):
                if path is None or path not in records:
                    raise ValueError(f'Unresolved include in {name}/{row["path"]}: {path}')
                if path not in visited:
                    visited.add(path)
                    for include in records[path]['includes']:
                        visit(include)
            visit(row['path'])
            row['closure_sha256'] = fingerprint([(p, records[p]['text_sha256']) for p in sorted(visited)])
        configurations[name] = {
            'mounts_low_to_high': report['mounts_low_to_high'],
            'summary': report['summary'], 'resources': list(records.values()),
        }
    return {'schema_version': 1, 'scope': 'Lexical source/include identity; no reachability, behavior or artwork acceptance.',
            'configurations': configurations}


def revise(previous: dict, sources: dict, revision: str, previous_blob: str) -> dict:
    if 'base' not in sources['configurations']:
        raise ValueError('The base configuration must remain present')
    for name, config in sources['configurations'].items():
        rows = {r['path']: r for r in config['resources']}
        if len(rows) != len(config['resources']):
            raise ValueError(f'Duplicate source identity: {name}')
        for path, row in rows.items():
            if qpath(path) != path or any(re.fullmatch('[0-9a-f]{64}', row[k]) is None
                                         for k in ('sha256', 'text_sha256', 'closure_sha256')):
                raise ValueError(f'Invalid source identity: {name}/{path}')
            if row['sha256'] not in row['line_ending_sha256'] or row['text_sha256'] not in row['line_ending_sha256']:
                raise ValueError(f'Inconsistent text identity: {name}/{path}')
            pending, visited = [path], set()
            while pending:
                dependency = pending.pop()
                if dependency not in rows:
                    raise ValueError(f'Missing dependency: {name}/{dependency}')
                if dependency not in visited:
                    visited.add(dependency)
                    pending.extend(rows[dependency]['includes'])
            expected = fingerprint([(p, rows[p]['text_sha256']) for p in sorted(visited)])
            if expected != row['closure_sha256']:
                raise ValueError(f'Stale dependency identity: {name}/{path}')
    old = previous['resources']
    by_path = {}
    for row in old:
        by_path.setdefault(row['path'], []).append(row)
    resources, configurations, changes = {}, {}, {}
    for name, config in sorted(sources['configurations'].items()):
        ids, added, changed = [], [], []
        paths = {row['path'] for row in config['resources']}
        for row in config['resources']:
            identity = row['path'] + '@' + row['closure_sha256']
            ids.append(identity)
            candidates = by_path.get(row['path'], [])
            same = next((r for r in candidates if r['source_sha256'] in row['line_ending_sha256']), None)
            if not candidates:
                added.append(row['path'])
            elif same is None:
                changed.append({'path': row['path'], 'before': sorted({r['source_sha256'] for r in candidates}),
                                'after': row['sha256']})
            if identity not in resources:
                # A legacy hash did not bind dependencies. It may seed pending
                # metadata, but can never carry old acceptance into a new closure.
                preserved = next((r for r in candidates if r.get('resource_id') == identity), None)
                result = deepcopy(preserved) if preserved else {
                    'path': row['path'], 'family_hint': family_hint(row['path']), 'family_reviewed': False,
                    'replacement': None, 'bitmap_exceptions': None, 'translation_status': 'pending',
                    'behavior_evidence': [], 'visual_evidence': [],
                }
                result.update(resource_id=identity, source=row['source'], source_sha256=row['sha256'],
                              source_closure_sha256=row['closure_sha256'], includes=row['includes'],
                              source_diagnostics=row['source_diagnostics'], configurations=[])
                resources[identity] = result
            resources[identity]['configurations'].append(name)
        configurations[name] = {'mounts_low_to_high': config['mounts_low_to_high'],
                                'effective_gui_count': len(ids), 'resource_ids': sorted(ids)}
        changes[name] = {'added': sorted(added), 'changed': sorted(changed, key=lambda r: r['path']),
                         'absent_previous_paths': sorted(set(by_path) - paths)}
    return {
        'schema_version': 2,
        'status': 'Reconciled lexical inventory; migration acceptance remains governed separately by UI-11.',
        'previous_manifest': {'revision': revision, 'git_blob': previous_blob,
                              'path': 'docs/dev/ui/migration-manifest.json'},
        'source_snapshot_sha256': fingerprint(sources),
        'denominator_policy': 'Unique effective (path, transitive include text identity) variants across named configurations.',
        'configurations': configurations, 'changes': changes,
        'resources': [resources[key] for key in sorted(resources)],
    }


def git_manifest(root: Path, baseline: str):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root).decode('utf-8').strip()
    revision = git('rev-parse', '--verify', baseline + '^{commit}')
    name = revision + ':docs/dev/ui/migration-manifest.json'
    return json.loads(git('show', name)), revision, git('rev-parse', name)


def validate(root: Path, baseline: str, manifest: dict, sources: dict):
    previous, revision, blob = git_manifest(root, baseline)
    if manifest != revise(previous, sources, revision, blob):
        raise ValueError('Inventory differs from the reproducible revision; sources, evidence or acceptance were edited')
    return {'status': 'Inventory revision validated; no product acceptance',
            'baseline': revision, 'source_snapshot_sha256': fingerprint(sources),
            'effective_variants': len(manifest['resources']),
            'configurations': {n: c['effective_gui_count'] for n, c in manifest['configurations'].items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--report', action='append', required=True, metavar='CONFIG=REPORT')
    parser.add_argument('--output-dir', type=Path, required=True, help='New directory for reviewable manifest and source metadata')
    args = parser.parse_args()
    reports = {}
    for argument in args.report:
        name, path = argument.split('=', 1)
        if name in reports:
            raise ValueError(f'Duplicate configuration: {name}')
        reports[name] = json.loads(Path(path).read_text(encoding='utf-8'))
    sources = snapshot(reports)
    previous, revision, blob = git_manifest(args.root, args.baseline)
    manifest = revise(previous, sources, revision, blob)
    result = validate(args.root, args.baseline, manifest, sources)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for filename, data in [('migration-manifest.json', manifest), ('inventory-sources.json', sources), ('inventory-audit.json', result)]:
        (args.output_dir / filename).write_text(json.dumps(data, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
