"""Require real normal-mapped illumination and exact classic/frustum controls."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from PIL import Image, ImageChops

from renderer_pbr_environment_parity import within_encoded_allowance

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--gl-report', type=Path, required=True)
parser.add_argument('--vk-report', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
reports = [json.loads(path.read_text()) for path in (args.gl_report,args.vk_report)]
failures = []
expected = {'backface-'+suffix for suffix in ('front-flat','front-normal','normal','flat','classic',
            'restored','all-faces','precise','outside','outside-all-faces','restored-final')}
for key in ('fixture','compiledMapSHA256','harnessSHA256','backfaceProfile','backfaceHarnessSHA256','requestedSamples','basepath'):
    if reports[0].get(key) is None or reports[0][key] != reports[1].get(key):
        failures.append('mismatched '+key)
for name in set(reports[0]['runtimeSHA256']) | set(reports[1]['runtimeSHA256']):
    if name.startswith('renderer-vk'):
        continue
    if reports[0]['runtimeSHA256'].get(name) != reports[1]['runtimeSHA256'].get(name):
        failures.append('mismatched runtime '+name)
images = []
checks = {}
def above2(a,b):
    histogram = ImageChops.difference(a,b).histogram()
    return sum(n for i,n in enumerate(histogram) if i%256 > 2)/(a.width*a.height*3)
def maximum(a,b):
    histogram = ImageChops.difference(a,b).histogram()
    return max(i%256 for i,n in enumerate(histogram) if n)
for backend,report in zip(('gl','vk'),reports):
    if report.get('requestedSamples') not in (0,4) or report['fixture']['cameras']['sampling'] != [0,-1100,380,0,90,0]:
        failures.append(backend+': unsupported sample count or camera')
    rows = report['results']
    if not report.get('complete') or not report.get('runtimeUnchanged') or len(rows) != len(expected):
        failures.append(backend+': incomplete capture')
    if {r['case'] for r in rows} != expected:
        failures.append(backend+': wrong capture set')
    captures = {}
    for row in rows:
        if row['backend'] != backend or row['failures']:
            failures.append(backend+': capture diagnostics '+row['case'])
        if not re.search(rf'Renderer AA: MSAA requested={report["requestedSamples"]} effective={report["requestedSamples"]}\b', '\n'.join(row['telemetry'])):
            failures.append(backend+': requested MSAA not active '+row['case'])
        for kind in ('screenshot','log'):
            if digest(Path(row[kind])) != row['sha256'][kind]:
                failures.append(backend+': changed '+kind)
        im = Image.open(row['screenshot']).convert('RGB')
        if im.size != (1280,800):
            failures.append(backend+': unexpected extent')
        captures[row['case']] = im
    images.append(captures)
    # These coordinates are inside the fixed plane at the sampling camera.
    # A positive front control and a lit mapped back face prevent empty images
    # from passing, while flat/classic/outside controls must remain black.
    for suffix in ('front-flat','front-normal','normal','flat','classic','outside','outside-all-faces'):
        name = 'backface-'+suffix
        crop = captures[name].crop((570,330,710,470))
        histogram = crop.histogram()
        positive = sum(n for i,n in enumerate(histogram) if i%256 > 2)
        peak = max(i%256 for i,n in enumerate(histogram) if n)
        checks[backend+'-'+suffix] = {'channelsAbove2':positive,'peak':peak}
        if suffix in ('front-flat','front-normal','normal'):
            if positive < 1000:
                failures.append(backend+': missing illuminated '+name)
        elif peak != 0:
            failures.append(backend+': lit rejected '+name)
    for suffix in ('restored','all-faces','precise','restored-final'):
        delta = maximum(captures['backface-normal'],captures['backface-'+suffix])
        checks[backend+'-'+suffix] = {'maximumError':delta}
        if delta != 0:
            failures.append(backend+': different restored/all-face/precise geometry '+suffix)
receiver_failures = list(failures)
# The fixed sampling camera projects the complete 144-unit plane well inside
# this 256-pixel box, including its MSAA boundary. Keep the independent whole
# frame gate: differences on the laboratory's classic walls still fail it.
receiver_bounds = (512,272,768,528)
for case in sorted(expected):
    delta = maximum(images[0][case],images[1][case])
    receiver_delta = maximum(images[0][case].crop(receiver_bounds),images[1][case].crop(receiver_bounds))
    fraction = above2(images[0][case],images[1][case])
    checks[case] = {'maximumError':delta, 'receiverMaximumError':receiver_delta, 'fractionAbove2':fraction}
    # A normal-mapped highlight may use the encoded-frame allowance.
    if not within_encoded_allowance(receiver_delta, fraction):
        receiver_failures.append(case+': complete receiver error above two bytes')
    if not within_encoded_allowance(delta, fraction):
        failures.append(case+': full-frame error above two bytes')
proof = {'status':'fail' if failures else 'pass','failures':failures,'checks':checks,
         'receiverStatus':'fail' if receiver_failures else 'pass',
         'receiverFailures':receiver_failures, 'receiverBounds':receiver_bounds,
         'inputs':{str(path.resolve()):digest(path) for path in (args.gl_report,args.vk_report)},
         'harnessSHA256':digest(Path(__file__)),
         'scope':'Fully back-facing plane with native mapped normals, classic rollback, frustum rejection and restoration; fixed camera, whole-frame <=2 comparison with the encoded-frame allowance.'}
assert not args.output.exists()
args.output.write_text(json.dumps(proof,indent=2)+'\n')
print('PBR backface geometry:',proof['receiverStatus'],'whole frame:',proof['status'],failures)
raise SystemExit(bool(failures))
