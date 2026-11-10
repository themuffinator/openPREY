#!/usr/bin/env python3
"""Run recovered in-tree game regressions, failing on missing tests or compilers."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]


class RegressionTemporaryDirectory(tempfile.TemporaryDirectory):
    """Allow Windows to release a completed fixture executable before removal."""

    def cleanup(self):
        for attempt in range(21):
            try:
                super().cleanup()
                return
            except (PermissionError, NotADirectoryError) as error:
                # A completed child can retain a short-lived image lock on
                # Windows. Never suppress persistent errors or retry tests.
                # Older tempfile versions wrap a sharing violation while
                # trying to treat the still-locked file as a directory.
                sharing = isinstance(error, PermissionError) or isinstance(error.__context__, PermissionError)
                if os.name != 'nt' or not sharing or attempt == 20:
                    raise
                time.sleep(0.1)


def discover():
    mapping = json.loads((ROOT / 'docs/dev/game-test-coverage.json').read_text(encoding='utf-8'))
    rows = mapping['tests']
    if len({r['historical'] for r in rows}) != len(rows) or len(rows) != 83:
        raise RuntimeError('Imported game-history inventory changed; review coverage explicitly')
    for row in rows:
        if not row['current'] or not (ROOT / row['current']).is_file():
            raise RuntimeError(f'Missing current coverage: {row}')
    # The historical competitive aggregator maps to this broader suite; do not
    # recursively launch the runner as one of its own member checks.
    tests = sorted({r['current'] for r in rows if r['current'].endswith('.py')
                    and r['current'] != 'tools/tests/game_regression_suite.py'})
    meson = (ROOT / 'meson.build').read_text(encoding='utf-8')
    profile = (ROOT / 'tools/validation/openq4_validate.py').read_text(encoding='utf-8')
    workflow = (ROOT / '.github/workflows/commit-validation.yml').read_text(encoding='utf-8')
    if 'game_regression_suite.py' not in meson or 'game_regression_suite.py' not in profile or 'validate_push' not in workflow:
        raise RuntimeError('Game regression suite is disconnected from native/profile/CI discovery')
    return tests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-discovery', action='store_true')
    parser.add_argument('--log-dir', type=Path, default=ROOT / '.tmp/game-regressions')
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    tests = discover()
    if args.check_discovery:
        print(f'game regressions: {len(tests)} Python checks plus platform-specific native probes registered')
        return 0
    if not any(shutil.which(name) for name in ('clang++', 'g++', 'c++')):
        raise RuntimeError('A C++ fixture compiler is required; executable coverage cannot be silently skipped')
    args.log_dir.mkdir(parents=True, exist_ok=True)
    temporary = args.log_dir.resolve() / 'tmp'
    temporary.mkdir(exist_ok=True)
    env = dict(os.environ, OPENQ4_GAMELIBS_REPO=str(ROOT),
               TMP=str(temporary), TEMP=str(temporary), TMPDIR=str(temporary))
    def run(name):
        try:
            completed = subprocess.run([sys.executable, str(ROOT / name)], cwd=ROOT, env=env,
                                       capture_output=True, text=True, errors='replace', timeout=180)
            output = completed.stdout + completed.stderr
            code = completed.returncode
        except subprocess.TimeoutExpired as error:
            output = f'Test exceeded 180 seconds: {error}\n'
            code = 124
        log = args.log_dir / (Path(name).stem + '.log')
        log.write_text(output, encoding='utf-8')
        passed = code == 0 and 'skipped (no' not in output.lower()
        return {'test': name, 'passed': passed, 'exit': code, 'log': str(log)}
    with ThreadPoolExecutor(max_workers=max(1, min(args.jobs, 4))) as executor:
        results = list(executor.map(run, tests))
    (args.log_dir / 'results.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    for result in results:
        if not result['passed']:
            print(f'FAILED {result["test"]}: {result["log"]}')
            # Keep the actual compiler/runtime error in the job log even when
            # the platform fails before it can publish a staged package.
            output = Path(result['log']).read_text(encoding='utf-8', errors='replace')
            if len(output) > 12000:
                print('[last 12000 characters; complete output is in the test log]')
            print(output[-12000:], flush=True)
    print(f'game regressions: {sum(r["passed"] for r in results)}/{len(results)} passed')
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
