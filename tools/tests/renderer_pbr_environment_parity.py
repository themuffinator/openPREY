#!/usr/bin/env python3
"""Compare frozen GL/Vulkan IBL specimens from the same laboratory package."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import renderer_pbr_laboratory as laboratory


# Production composition encodes every PBR light into the display-referred
# frame (Stage C of the PBR production-readiness plan). The same small relative
# GL/Vulkan evaluation difference, in a normal-mapped highlight or at a grazing
# silhouette, is then a few bytes rather than one: calibrated surfaces are about
# three times brighter in linear light. A whole-frame gate of two bytes admits
# at most this many channels, by at most ENCODED_ALLOWANCE_BYTES.
ENCODED_ALLOWANCE_FRACTION = 0.0001
ENCODED_ALLOWANCE_BYTES = 4


def within_encoded_allowance(maximum_error: float, fraction_above2: float) -> bool:
    return maximum_error <= 2 or (maximum_error <= ENCODED_ALLOWANCE_BYTES
                                  and fraction_above2 <= ENCODED_ALLOWANCE_FRACTION)


def metrics(a: bytes, b: bytes) -> dict:
    errors = [abs(x-y) for x, y in zip(a, b)]
    return {'meanError': sum(errors)/len(errors), 'maximumError': max(errors),
            'fractionAbove2': sum(error > 2 for error in errors)/len(errors)}


def coverage_lighting(a: bytes, b: bytes, mask_a: bytes, mask_b: bytes) -> dict:
    """Separate radiance error from measured, bounded MSAA coverage differences."""
    failures = []
    result = {'failures': failures}
    if not mask_a or len(mask_a) != len(mask_b) or len(a) != len(b) or len(a) != 3*len(mask_a):
        failures.append('invalid color/coverage patch')
        return result
    coverage = metrics(mask_a, mask_b)
    result['coverage'] = coverage
    # The API permits coordinate-dependent alpha-to-coverage conversion.
    # Admit at most one of four samples, with <=1% aggregate coverage error
    # and <=5% affected pixels. Hard-mask and same-backend controls stay exact.
    if coverage['maximumError'] > 65 or coverage['meanError'] > 2.55 or coverage['fractionAbove2'] > 0.05:
        failures.append('cutout coverage differs beyond bounded sample quantization')
    full = [i for i,(x,y) in enumerate(zip(mask_a,mask_b)) if x==255 and y==255]
    if len(full) < len(mask_a)*0.15:
        failures.append('insufficient common fully covered pixels')
        return result
    full_errors = [abs(a[3*i+c]-b[3*i+c]) for i in full for c in range(3)]
    peak = max(max(a[3*i+c],b[3*i+c]) for i in full for c in range(3))
    zero_max = weighted_bad = weighted_count = unmatched_bad = 0
    for i,(x,y) in enumerate(zip(mask_a,mask_b)):
        ca,cb = x/255,y/255
        for c in range(3):
            va,vb = a[3*i+c],b[3*i+c]
            if not x: zero_max=max(zero_max,va)
            if not y: zero_max=max(zero_max,vb)
            if x and y:
                weighted_count+=1
                # Compare premultiplied color with measured coverage removed,
                # allowing byte quantization and two bytes of radiance error.
                weighted_bad+=abs(va*cb-vb*ca)>0.5*(ca+cb)+2*ca*cb
            elif bool(x)!=bool(y):
                unmatched_bad+=max(va,vb)>(peak+2)*max(ca,cb)+1
    result.update(commonFullPixels=len(full), commonFullMaximumError=max(full_errors),
                  zeroCoverageMaximumColor=zero_max, weightedSamples=weighted_count,
                  weightedFailures=weighted_bad, unmatchedOverbrightChannels=unmatched_bad)
    if max(full_errors)>2 or zero_max>1 or weighted_bad>weighted_count*0.005 or unmatched_bad:
        failures.append('cutout lighting error is not explained by its measured coverage')
    return result


def compare(reference: dict, candidate: dict) -> dict:
    failures: list[str] = []
    result = {'scope': 'Analytic IBL specimen patches; no authored-probe, baked-light or full HDR parity claim.',
              'failures': failures, 'cases': {}}
    for label, report in (('OpenGL', reference), ('Vulkan', candidate)):
        if not report.get('complete') or not report.get('runtimeUnchanged'):
            failures.append(f'{label} report is incomplete or runtime inputs changed')
        for key in ('runtimeSHA256', 'compiledMapSHA256', 'fixture', 'basepath', 'harnessSHA256'):
            if not report.get(key):
                failures.append(f'{label} {key} provenance is missing')
        if report.get('requestedSamples') not in (0, 4):
            failures.append(f'{label} sample count is missing or unsupported')
    for key in ('runtimeSHA256', 'compiledMapSHA256', 'fixture', 'basepath', 'harnessSHA256', 'requestedSamples'):
        if reference.get(key) != candidate.get(key):
            failures.append(f'{key} differs between the two runs')
    expected = {'ibl-'+name for name in laboratory.IBL_MATERIALS if name != 'shared'}
    groups = []
    for backend, report in (('gl', reference), ('vk', candidate)):
        rows = [row for row in report.get('results', []) if row.get('case', '').startswith('ibl-')]
        by_name = {row['case']: row for row in rows}
        if len(by_name) != len(rows):
            failures.append(f'{backend} repeats a case')
        if expected - by_name.keys():
            failures.append(f'{backend} required cases missing: {sorted(expected - by_name.keys())}')
        groups.append(by_name)
        for row in rows:
            if row.get('backend') != backend or row.get('camera') != 'sampling' or row.get('failures'):
                failures.append(f'{backend}/{row["case"]} is failed or uses the wrong backend/camera')
            for field in ('screenshot', 'log'):
                path = Path(row.get(field, ''))
                if not path.is_file() or laboratory.digest(path) != row.get('sha256', {}).get(field):
                    failures.append(f'{backend}/{row["case"]} {field} no longer matches its recorded hash')
    if failures:
        result['status'] = 'fail'
        return result
    patches = [{name:laboratory.normal_patch(Path(row['screenshot'])) for name,row in group.items()}
               for group in groups]
    for backend, group, images in zip(('gl', 'vk'), groups, patches):
        controls = copy.deepcopy(list(group.values()))
        laboratory.compare_ibl_captures(controls, {name.removeprefix('ibl-'):p for name,p in images.items()})
        failures.extend(f'{backend}/{row["case"]}: {failure}'
                        for row in controls for failure in row['failures'])
    for name in sorted(expected):
        a, b = [images[name] for images in patches]
        if not a or len(a) != len(b):
            failures.append(f'{name} has an invalid comparison patch')
            continue
        if name.endswith('coverage'):
            a,b=a[1::3],b[1::3]
        measured = metrics(a,b)
        result['cases'][name] = measured
        if name=='ibl-cutout-hard-coverage':
            if measured['maximumError']:
                failures.append('hard cutout masks differ between backends')
            continue
        if name=='ibl-cutout-coverage' and reference['requestedSamples']==4:
            if measured['meanError']>2.55 or measured['maximumError']>65 or measured['fractionAbove2']>0.05:
                failures.append(f'{name} exceeds bounded sample quantization')
            continue
        if name in ('ibl-cutout','ibl-cutout-restored') and reference['requestedSamples']==4:
            proof=coverage_lighting(a,b,patches[0]['ibl-cutout-coverage'][1::3],
                                    patches[1]['ibl-cutout-coverage'][1::3])
            measured['coverageLighting']=proof
            failures.extend(f'{name}: {failure}' for failure in proof['failures'])
            if measured['meanError']>1:
                failures.append(f'{name} exceeds the controlled mean image tolerance')
            continue
        # Bound both the typical error and sparse disagreements at cutout/MSAA
        # boundaries. A small mean alone can hide an omitted local feature.
        if measured['meanError'] > 1 or measured['fractionAbove2'] > 0.005:
            failures.append(f'{name} exceeds the controlled image tolerance')
    result['status'] = 'pass' if not failures else 'fail'
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gl-report', type=Path, required=True)
    parser.add_argument('--vk-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = laboratory.fixture.validate_runtime_root(args.output)
    reports = [json.loads(path.read_text(encoding='utf-8')) for path in (args.gl_report, args.vk_report)]
    result = compare(*reports)
    result['validatorSHA256'] = laboratory.digest(Path(__file__))
    result['reports'] = {str(path.resolve()): laboratory.digest(path) for path in (args.gl_report, args.vk_report)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(f'PBR environment parity: {result["status"]} ({len(result["cases"])} controls)')
    for failure in result['failures']:
        print(failure)
    return int(bool(result['failures']))


if __name__ == '__main__':
    raise SystemExit(main())
