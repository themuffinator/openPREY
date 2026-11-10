#!/usr/bin/env python3
"""Compare provenance-matched OpenGL and Vulkan authored-probe engine captures."""
import argparse
import json
import math
from pathlib import Path
import re

import renderer_pbr_laboratory as lab
from renderer_pbr_environment_parity import metrics, coverage_lighting, within_encoded_allowance

REQUIRED = {
    'analytic','both','warm','cool','rotated','fade','outside','tinted',
    'priority-low','priority-high','rough-low','rough-high','normal','ao-zero',
    'yaw-90','yaw-180','yaw-270','pitch-up','pitch-down',
    'transparent','transparent-analytic','transparent-classic',
    'cutout','cutout-analytic','cutout-owned','eight','nine','evicted',
    'spatial-x','spatial-x-swapped','spatial-z','spatial-z-swapped','translated','rotated-model',
    'record-overflow','invalid-volume','restored','image-reload','partial-restart','full-restart',
    'box-plain','box','box-mirrored','box-deep','box-fade','box-hard','box-outside','baked',
}


def specimen_bounds(report: dict, name: str) -> tuple[int,int,int,int]:
    """Project the recorded sphere origin instead of assuming screen center."""
    camera=report['fixture']['cameras']['sampling']
    commands=report['probeProfile'][name]['commands']
    spawns=[command for command in commands if command.startswith('spawn func_static name probe_specimen ')]
    if len(camera)!=6 or camera[3:]!=[0,90,0] or len(spawns)!=1:
        raise ValueError('unsupported specimen camera or ambiguous spawn')
    match=re.search(r'\borigin "([^"]+)"',spawns[0])
    origin=list(map(float,match.group(1).split())) if match else []
    if len(origin)!=3 or not all(math.isfinite(v) for v in origin+camera):
        raise ValueError('invalid specimen origin or camera')
    # These controls use the original radius-72 sphere at 400 world units.
    # The 65x65 patch fits well inside its approximately 192-pixel footprint.
    # Reject changed framing rather than silently sampling an object edge.
    depth=origin[1]-camera[1]
    if abs(depth-400)>0.0001:
        raise ValueError('unsupported specimen distance')
    focal=800*(2/3)  # Q4 expands the 90-degree 4:3 FOV horizontally.
    x=round(640+(origin[0]-camera[0])*focal/depth)
    y=round(400-(origin[2]-camera[2])*focal/depth)
    bounds=(x-32,y-32,x+33,y+33)
    if bounds[0]<0 or bounds[1]<0 or bounds[2]>1280 or bounds[3]>800:
        raise ValueError('specimen patch is outside the frame')
    return bounds


def specimen_patch(rgb: bytes, bounds: tuple[int,int,int,int]) -> bytes:
    left,top,right,bottom=bounds
    return b''.join(rgb[(y*1280+left)*3:(y*1280+right)*3] for y in range(top,bottom))


def gl_native(report: dict) -> bool:
    """True when the classic OpenGL owner drew the PBR surfaces (--gl-native)."""
    if report.get('glNative'):
        return True
    for row in report.get('results', []):
        telemetry = row.get('telemetry') or []
        for line in telemetry if isinstance(telemetry, list) else [telemetry]:
            if isinstance(line, str) and line.startswith('OpenGL: native PBR:') and re.search(r'\badmitted=[1-9]', line):
                return True
    return False


def hard_cutout_lighting(a: bytes, b: bytes, mask_a: bytes, mask_b: bytes,
                         width: int, height: int, classic_coverage: bool = False) -> dict:
    """Bound isolated binary edge differences without relaxing radiance checks."""
    failures=[]
    result={'failures':failures}
    count=width*height
    if count<=0 or len(a)!=3*count or len(b)!=len(a) or len(mask_a)!=count or len(mask_b)!=count:
        failures.append('invalid color/coverage image'); return result
    if any(value not in (0,255) for value in mask_a+mask_b):
        failures.append('single-sample coverage is not binary'); return result
    common=[i for i,(x,y) in enumerate(zip(mask_a,mask_b)) if x==255 and y==255]
    if len(common)<1024:
        failures.append('insufficient common covered pixels'); return result
    unmatched=[i for i,(x,y) in enumerate(zip(mask_a,mask_b)) if x!=y]
    # A threshold can cross one fragment after API interpolation/texture
    # rounding. Permit at most 0.01% of covered pixels, capped at four pixels
    # in the entire frame; every such fragment must touch its owner's edge.
    limit=min(4,min(mask_a.count(255),mask_b.count(255))//10000)
    if classic_coverage:
        # The classic OpenGL owner keeps the classic depth fill's alpha test,
        # the coverage a classic material has on OpenGL. It differs from
        # Vulkan's at isolated edge fragments (20 on the classic cutout
        # control), so allow 0.25% of covered pixels, still edge-only.
        limit=min(mask_a.count(255),mask_b.count(255))//400
    interior=[]
    for i in unmatched:
        x,y=i%width,i//width
        owner=mask_a if mask_a[i] else mask_b
        if not any(owner[ny*width+nx]==0
                   for ny in range(max(0,y-1),min(height,y+2))
                   for nx in range(max(0,x-1),min(width,x+2))):
            interior.append(i)
    common_error=max(abs(a[3*i+c]-b[3*i+c]) for i in common for c in range(3))
    peak=max(max(a[3*i+c],b[3*i+c]) for i in common for c in range(3))
    leak=max((color[3*i+c] for color,mask in ((a,mask_a),(b,mask_b))
              for i,value in enumerate(mask) if value==0 for c in range(3)),default=0)
    unmatched_peak=max((max(a[3*i+c],b[3*i+c]) for i in unmatched for c in range(3)),default=0)
    result.update(commonCoveredPixels=len(common), commonMaximumError=common_error,
                  unmatchedPixels=len(unmatched), unmatchedPixelLimit=limit,
                  unmatchedCoordinates=[[i%width,i//width] for i in unmatched],
                  interiorMismatches=len(interior), zeroCoverageMaximumColor=leak,
                  unmatchedMaximumColor=unmatched_peak, commonPeakColor=peak)
    if len(unmatched)>limit or interior:
        failures.append('binary coverage differs beyond isolated boundary quantization')
    if common_error>2 or leak>1 or unmatched_peak>peak+2:
        failures.append('cutout lighting error is not explained by measured coverage')
    return result


def compare(gl: dict, vk: dict) -> dict:
    failures=[]; checks={}
    for key in ('runtimeSHA256','compiledMapSHA256','fixture','basepath','harnessSHA256',
                'probeHarnessSHA256','requestedSamples'):
        if not gl.get(key) and key!='requestedSamples': failures.append(f'{key}: missing provenance')
        if gl.get(key)!=vk.get(key): failures.append(f'{key}: backend inputs differ')
    rows=[]
    for backend,report in (('gl',gl),('vk',vk)):
        if not report.get('complete') or not report.get('runtimeUnchanged') or report.get('probeProof',{}).get('status')!='pass':
            failures.append(f'{backend}: probe proof incomplete or failed')
        data={row['case']:row for row in report.get('results',[])}
        if {'probes-'+name for name in REQUIRED} - data.keys(): failures.append(f'{backend}: required controls missing')
        if len(data)!=len(report.get('results',[])): failures.append(f'{backend}: duplicate captures')
        for name,row in data.items():
            if row.get('backend')!=backend or row.get('camera')!='sampling' or row.get('failures'):
                failures.append(f'{backend}/{name}: wrong context or failed capture')
            for kind in ('screenshot','log'):
                p=Path(row.get(kind,''))
                if not p.is_file() or lab.digest(p)!=row.get('sha256',{}).get(kind):
                    failures.append(f'{backend}/{name}: {kind} provenance changed')
        rows.append(data)
    if failures: return {'status':'fail','failures':failures,'cases':checks}
    left,right=rows
    masks=[lab.capture_rgb(Path(r['probes-cutout-owned']['screenshot']))[1::3] for r in rows]
    if not left or set(left)-set(right): failures.append('missing common controls')
    for name in sorted(set(left)&set(right)):
        a,b=lab.capture_rgb(Path(left[name]['screenshot'])),lab.capture_rgb(Path(right[name]['screenshot']))
        if len(a)!=1280*800*3 or len(a)!=len(b):
            failures.append(f'{name}: invalid full-frame dimensions'); continue
        try:
            bounds=specimen_bounds(gl,name)
            if bounds!=specimen_bounds(vk,name): raise ValueError('backend specimen origins differ')
        except (KeyError,TypeError,ValueError) as error:
            failures.append(f'{name}: invalid specimen framing: {error}'); continue
        patch_a,patch_b=specimen_patch(a,bounds),specimen_patch(b,bounds)
        full,patch=metrics(a,b),metrics(patch_a,patch_b)
        checks[name]={'fullFrame':full,'specimen':patch,'specimenBounds':list(bounds)}
        if gl['requestedSamples']==0:
            if name in ('probes-cutout','probes-cutout-analytic','probes-cutout-owned'):
                proof=hard_cutout_lighting(a,b,*masks,1280,800,classic_coverage=gl_native(gl))
                checks[name]['coverageLighting']=proof
                if proof['failures']: failures.append(f'{name}: coverage/lighting mismatch')
            elif not within_encoded_allowance(full['maximumError'],full['fractionAbove2']) or patch['maximumError']>2:
                # Grazing silhouette pixels may use the encoded-frame allowance;
                # the specimen interior must still agree within two bytes.
                failures.append(f'{name}: full-frame color differs beyond two bytes')
        else:
            # The specimen interior isolates shading from edge rasterization.
            # Bound total MSAA edge disagreement independently as well.
            if full['meanError']>0.2 or full['fractionAbove2']>0.01:
                failures.append(f'{name}: MSAA full-frame disagreement exceeds bounds')
            if name in ('probes-cutout','probes-cutout-analytic'):
                patch_masks=[specimen_patch(lab.capture_rgb(Path(r['probes-cutout-owned']['screenshot'])),bounds)[1::3] for r in rows]
                proof=coverage_lighting(patch_a,patch_b,*patch_masks)
                checks[name]['coverageLighting']=proof
                if proof['failures']: failures.append(f'{name}: coverage/lighting mismatch')
            elif name!='probes-cutout-owned' and patch['maximumError']>2:
                failures.append(f'{name}: specimen shading differs beyond two bytes')
    return {'status':'fail' if failures else 'pass','failures':failures,'cases':checks,
            'scope':'Original authored-probe fixtures on one physical GPU; not full HDR, baked diffuse or platform qualification.'}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gl-report',type=Path,required=True)
    parser.add_argument('--vk-report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=compare(json.loads(args.gl_report.read_text()),json.loads(args.vk_report.read_text()))
    report['inputs']={str(p.resolve()):lab.digest(p) for p in (args.gl_report,args.vk_report)}
    report['harnessSHA256']=lab.digest(Path(__file__))
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print('Authored probe GL/Vulkan parity:',report['status'],report['failures'])
    return int(report['status']!='pass')


if __name__=='__main__': raise SystemExit(main())
