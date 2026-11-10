#!/usr/bin/env python3
"""Negative controls for the engine roster capture's geometry/readback oracle."""
import re
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
from capture_multiplayer_rosters import VIEWS, qualify, steps


def passing_log():
    lines = []
    for name, _, _, prefix in VIEWS:
        for suffix in ('top', 'end', 'restored', 'mixed', 'short'):
            short = suffix == 'short'
            bottom = suffix in ('end', 'restored', 'mixed')
            last = 's-11' if suffix == 'mixed' else 'a-31' if bottom else 'a-0'
            lines += [f'ROSTER_STAGE {name}-{suffix}',
                      f'RETAINED_GUI_SCROLL id={prefix}-scroll usable={int(not short)} range={0 if short else 100} offset={100 if bottom else 0}',
                      f'RETAINED_GUI_NODE id={prefix}-headings bounds=0,0,100,16',
                      f'RETAINED_GUI_NODE id={prefix}-viewport bounds=0,16,100,100',
                      f'RETAINED_GUI_NODE id={prefix}-{last} bounds=0,{92 if bottom else 16},100,24']
    return '\n'.join(lines)+'\n'


class RosterOracleTests(unittest.TestCase):
    def test_complete_geometry(self):
        self.assertTrue(all(qualify(passing_log()).values()))

    def test_each_missing_stage_is_rejected(self):
        baseline = passing_log()
        for name, _, _, _ in VIEWS:
            for suffix in ('top', 'end', 'restored', 'mixed', 'short'):
                stage = f'{name}-{suffix}'
                with self.subTest(stage=stage):
                    broken = re.sub(rf'ROSTER_STAGE {stage}\n.*?(?=ROSTER_STAGE |\Z)', '', baseline, flags=re.S)
                    self.assertFalse(all(qualify(broken).values()))

    def test_bad_geometry_and_failed_operations_are_rejected(self):
        baseline = passing_log()
        for broken in (baseline.replace('offset=100', 'offset=0', 1),
                       baseline.replace('bounds=0,92,100,24', 'bounds=0,200,100,24', 1),
                       baseline.replace('range=0 offset=0', 'range=0 offset=100', 1),
                       baseline.replace('headings bounds=0,0', 'headings bounds=0,10', 1),
                       baseline+'RETAINED_GUI_OPERATION focus failed\n'):
            self.assertFalse(all(qualify(broken).values()))

    def test_engine_identifiers_are_quoted(self):
        # The engine lexer splits unquoted hyphens; this catches the first
        # capture harness failure without requiring another engine launch.
        for line in steps():
            if line.startswith(('openq4_retainedGui focus ', 'openq4_retainedGui widget ', 'openq4_retainedGui inspect ')):
                self.assertRegex(line, r' "[^"\n]+"$')
            if line.startswith('echo '):
                self.assertRegex(line, r'^echo "ROSTER_STAGE [^"]+"$')


if __name__ == '__main__':
    unittest.main()
