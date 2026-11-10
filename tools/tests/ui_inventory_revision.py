#!/usr/bin/env python3
"""Behavioral tests for source revision, closure invalidation and acceptance isolation."""
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/ui'))
from inventory_revision import revise, snapshot, validate


def report(files):
    rows = []
    for path, (data, includes) in files.items():
        digest = hashlib.sha256(data.encode()).hexdigest()
        rows.append(dict(path=path, source='fixture/loose', sha256=digest, text_sha256=digest,
                         line_ending_sha256=[digest], includes=[{'resolved': p} for p in includes],
                         windows=[{'type': 'windowDef'}], diagnostics=[]))
    return dict(mounts_low_to_high=[{'name': 'fixture'}], summary={}, resources=rows)


class InventoryRevisionTest(unittest.TestCase):
    def setUp(self):
        self.files = {'guis/main.gui': ('root', ['guis/part.inc']), 'guis/part.inc': ('part', [])}
        self.sources = snapshot({'base': report(self.files)})
        self.seed = {'resources': []}
        self.first = revise(self.seed, self.sources, 'a' * 40, 'b' * 40)

    def test_distinct_variants_and_shared_identity(self):
        changed = dict(self.files, **{'guis/main.gui': ('expansion root', ['guis/part.inc'])})
        sources = snapshot({'base': report(self.files), 'awakening': report(changed), 'retail': report(self.files)})
        manifest = revise(self.first, sources, 'a' * 40, 'b' * 40)
        self.assertEqual(len(manifest['resources']), 3)
        self.assertEqual(len(manifest['configurations']['base']['resource_ids']), 2)
        shared = next(r for r in manifest['resources'] if r['path'] == 'guis/part.inc')
        self.assertEqual(shared['configurations'], ['awakening', 'base', 'retail'])

    def test_changed_include_invalidates_parent_acceptance(self):
        for row in self.first['resources']:
            row.update(translation_status='verified', behavior_evidence=['old-run'], visual_evidence=['old-image'])
        changed = dict(self.files, **{'guis/part.inc': ('new behavior', [])})
        manifest = revise(self.first, snapshot({'base': report(changed)}), 'a' * 40, 'b' * 40)
        self.assertTrue(all(r['translation_status'] == 'pending' and not r['behavior_evidence']
                            and not r['visual_evidence'] for r in manifest['resources']))
        self.assertEqual(self.first['resources'][0]['translation_status'], 'verified')
        self.assertEqual(manifest['previous_manifest']['git_blob'], 'b' * 40)

    def test_added_removed_changed_are_explicit(self):
        changed = {'guis/new.gui': ('new', []), 'guis/main.gui': ('changed', [])}
        manifest = revise(self.first, snapshot({'base': report(changed)}), 'a' * 40, 'b' * 40)
        delta = manifest['changes']['base']
        self.assertEqual(delta['added'], ['guis/new.gui'])
        self.assertEqual(delta['absent_previous_paths'], ['guis/part.inc'])
        self.assertEqual(delta['changed'][0]['path'], 'guis/main.gui')

    def test_stale_dependency_binding_fails(self):
        changed = deepcopy(self.sources)
        changed['configurations']['base']['resources'][1]['text_sha256'] = 'c' * 64
        with self.assertRaises(ValueError):
            revise(self.first, changed, 'a' * 40, 'b' * 40)

    def test_duplicate_and_missing_include_fail(self):
        duplicate = report(self.files)
        duplicate['resources'].append(deepcopy(duplicate['resources'][0]))
        with self.assertRaises(ValueError):
            snapshot({'base': duplicate})
        with self.assertRaises(ValueError):
            snapshot({'base': report({'guis/main.gui': ('root', ['missing.inc'])})})

    def test_legacy_acceptance_cannot_gain_unbound_closure(self):
        old = deepcopy(self.first)
        for row in old['resources']:
            del row['resource_id']
            row.update(translation_status='verified', behavior_evidence=['unbound'])
        result = revise(old, self.sources, 'a' * 40, 'b' * 40)
        self.assertTrue(all(r['translation_status'] == 'pending' for r in result['resources']))

    def test_revision_validator_rejects_acceptance_and_denominator_edits(self):
        with patch('inventory_revision.git_manifest', return_value=(self.seed, 'a' * 40, 'b' * 40)):
            self.assertEqual(validate(ROOT, 'baseline', self.first, self.sources)['effective_variants'], 2)
            accepted = deepcopy(self.first)
            accepted['resources'][0]['translation_status'] = 'verified'
            omitted = deepcopy(self.first)
            omitted['resources'].pop()
            stale = deepcopy(self.first)
            stale['source_snapshot_sha256'] = '0' * 64
            for candidate in (accepted, omitted, stale):
                with self.assertRaises(ValueError):
                    validate(ROOT, 'baseline', candidate, self.sources)


if __name__ == '__main__':
    unittest.main()
