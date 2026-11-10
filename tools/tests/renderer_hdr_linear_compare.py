#!/usr/bin/env python3
"""Compare qualified OpenGL/Vulkan linear-scene composition captures."""
import argparse
import json
from pathlib import Path

import numpy as np

from renderer_hdr_linear_capture import lab, read_pfm


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gl', type=Path, required=True)
    parser.add_argument('--vk', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reports = [json.loads(path.read_text()) for path in (args.gl, args.vk)]
    failures, pairs = [], []
    for expected, report in zip(('gl', 'vk'), reports):
        if (not report.get('complete') or not report.get('runtimeUnchanged') or report.get('limited')
                or report.get('linearCaptureProof', {}).get('status') != 'pass'
                or any(row['backend'] != expected or row['failures'] for row in report['results'])):
            failures.append(expected + ': input is not a complete qualified capture set')
    for key in ('fixture', 'compiledMapSHA256', 'requestedSamples', 'linearCaptureProfile', 'harnessSources'):
        if reports[0].get(key) != reports[1].get(key):
            failures.append('input mismatch: ' + key)
    rows = [{row['case']: row for row in report['results']} for report in reports]
    if not rows[0] or set(rows[0]) != set(rows[1]):
        failures.append('missing or mismatched capture cases')
    if not failures:
        for name in rows[0]:
            files = [Path(row[name]['screenshot']).with_suffix('.pfm') for row in rows]
            proof = [report['linearCaptureProof']['checks'][name] for report in reports]
            if any(lab.digest(path) != p['sha256'] for path, p in zip(files, proof)):
                failures.append(name + ': changed PFM capture')
                continue
            a, b = [read_pfm(path) for path in files]
            if a.shape != b.shape:
                failures.append(name + ': extent mismatch')
                continue
            error = np.abs(a.astype(np.float64) - b)
            # Absolute tolerance covers dark sRGB/FP16 rounding; relative
            # tolerance covers extreme finite emission. No pixels are masked.
            tolerance = .005 + np.maximum(np.abs(a), np.abs(b)) * .002
            failed = int(np.count_nonzero(error > tolerance))
            pairs.append(dict(case=name, extent=list(a.shape[1::-1]),
                maximumAbsoluteError=float(error.max()), maximumToleranceRatio=float((error / tolerance).max()),
                failingChannels=failed, paths=[str(p) for p in files]))
            if failed:
                failures.append(name + ': linear images differ beyond FP16/sRGB tolerance')
    result = dict(status='fail' if failures else 'pass', absoluteTolerance=.005, relativeTolerance=.002,
        reports={str(path.resolve()): lab.digest(path) for path in (args.gl, args.vk)},
        pairs=pairs, failures=failures)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=result['status'], pairs=len(pairs), failures=failures)), flush=True)
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
