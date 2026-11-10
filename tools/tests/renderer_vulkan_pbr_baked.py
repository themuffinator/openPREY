#!/usr/bin/env python3
"""Qualify native baked HDR lighting against one provenance-bound GL bake.

Uses engine captures, a hidden window and isolated writable data. The supplied
GL laboratory report provides the bake; neither renderer rebakes during these
comparisons. Complete receiver submission is required in addition to images.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

import numpy as np
from PIL import Image

import renderer_pbr_laboratory as lab
from renderer_hdr_linear_capture import read_pfm


def configure(suite, samples, backend):
    lab.BASE.update(r_vkPBRBakedFailure='0', r_vkPBRBakedFailureAfter='0')
    for suffix in ('-clear', '', '-double', '-zero', '-off', '-restored'):
        lab.CASES.setdefault('lightgrid-pbr-ibl'+suffix,
                            {**lab.CASES['lightgrid-pbr'+suffix], 'r_pbrIBL':'1'})
    if suite in ('composition','isolated'):
        cases = ['lightgrid-pbr'+suffix for suffix in
                 ('-clear', '', '-double', '-zero', '-off', '-restored',
                  '-ibl-clear', '-ibl', '-ibl-double', '-ibl-zero', '-ibl-off', '-ibl-restored')]
        if suite == 'isolated':
            lab.CASE_COMMANDS[cases[0]] = ['g_stopTime 0',
                *[f'script "${name}.Off()"' for name in ('key','blue_fill','warm_fill','lab_projector')],
                'wait 30','g_stopTime 1']
    elif suite == 'normals':
        cases = ['lightgrid-pbr-normal-'+name for name in ('xyz','rg','agb','zero')]
    elif suite == 'recovery':
        cases = ['lightgrid-pbr'+suffix for suffix in
                 ('', '-image-reload', '-shader-reload', '-partial-restart', '-full-restart',
                  '-master-off', '-native', '-master-restored')]
        # This command reloads the internal GL program library only. Native
        # shader/pipeline recreation is exercised by full vid_restart below;
        # do not present a GL-only command as a Vulkan shader reload test.
        if backend == 'vk':
            cases.remove('lightgrid-pbr-shader-reload')
    elif suite == 'overlays':
        cases = ['lightgrid-pbr-'+kind+suffix for kind in ('fog','blend')
                 for suffix in ('-clear', '', '-hidden-clear', '-hidden', '-shared', '-off', '-restored')]
    elif suite == 'preview':
        cases = []
        for suffix in ('-clear', '', '-double', '-zero', '-off', '-restored', '-ibl-clear', '-ibl', '-ibl-zero'):
            name = 'baked-preview'+suffix
            lab.CASES[name] = {**lab.CASES['lightgrid-pbr'+suffix], 'r_hdrToneMap':'0'}
            cases.append(name)
    else:
        if backend != 'vk':
            raise ValueError('admission failure controls require Vulkan')
        cases = ['baked-admission-before']
        lab.CASES[cases[0]] = dict(lab.CASES['lightgrid-pbr'])
        for fault, after in ((1,0),(1,2),(2,2),(3,2),(4,2),(5,2)):
            name = f'baked-admission-fault{fault}-after{after}'
            lab.CASES[name] = {**lab.CASES['lightgrid-pbr'],
                             'r_vkPBRBakedFailure':str(fault), 'r_vkPBRBakedFailureAfter':str(after)}
            lab.LINEAR_UNAVAILABLE_CASES.add(name)
            cases.append(name)
        lab.CASES['baked-admission-restored'] = dict(lab.CASES['lightgrid-pbr'])
        cases.append('baked-admission-restored')
    for name in cases:
        lab.CASES[name]['r_multiSamples'] = str(samples)
    if suite == 'preview':
        lab.LINEAR_UNAVAILABLE_CASES.update(cases)
        if backend == 'gl':
            lab.FALLBACK_CASES.update(name for name in cases if lab.CASES[name]['r_useLightGrid'] == '1')
        lab.CASE_COMMANDS[cases[0]] = ['g_stopTime 0',
            *[f'script "${name}.Off()"' for name in ('key','blue_fill','warm_fill','lab_projector')],
            'wait 30','g_stopTime 1']
    return cases


def prove(report, suite, settings):
    failures, evidence = [], {}
    rows = {r['case']:r for r in report['results']}
    if suite == 'isolated':
        stations = rows['lightgrid-pbr-clear'].get('linearImage',{}).get('stationRGB',{})
        if len(stations) != 24 or any(max(abs(c) for c in rgb) > 0.000001
                                     for name,rgb in stations.items() if name != 'emissive'):
            failures.append('isolated control retained direct/environment light or omitted material samples')
    if suite == 'preview':
        # An enabled grid declines the entire modern preview on both APIs,
        # even at zero intensity. That fallback need not equal grid-disabled PBR.
        for a,b in (('baked-preview-off','baked-preview-clear'),('baked-preview-restored','baked-preview')):
            if Path(rows[a]['screenshot']).read_bytes() != Path(rows[b]['screenshot']).read_bytes():
                failures.append(a+'/'+b+': equivalent preview controls differ')
    for name, row in rows.items():
        failures += [name+': '+failure for failure in row['failures']]
        if row['backend'] != 'vk':
            continue
        text = Path(row['log']).read_text(errors='replace')
        section = text.split(f'PBRLAB_{name}_BEGIN',1)[-1].split(f'PBRLAB_{name}_END',1)[0]
        matches = re.findall(r'^Vulkan baked lighting: (.*)$',section,re.M)
        values = dict(re.findall(r'(\w+)=(\d+)',matches[-1])) if matches else {}
        values = {key:int(value) for key,value in values.items()}
        evidence[name] = values
        controls = settings[name]
        fault = int(controls.get('r_vkPBRBakedFailure','0'))
        modern = all(controls.get(key,'0') == '1' for key in ('r_rendererModernQuality','r_pbrMaterials'))
        preview_fallback = modern and controls['r_hdrToneMap'] == '0' and controls['r_useLightGrid'] == '1'
        if modern and not fault:
            hdr = re.findall(r'^Vulkan HDR scene ownership: (.*)$',section,re.M)
            hdr_values = dict(re.findall(r'(\w+)=(\d+)',hdr[-1])) if hdr else {}
            samples = max(1,int(controls['r_multiSamples']))
            if controls['r_hdrToneMap'] == '1' and int(hdr_values.get('samples','0')) != samples:
                failures.append(name+': actual scene sample count differs from the requested control')
            if controls['r_hdrToneMap'] == '1' and hdr_values.get('committed') != '1':
                failures.append(name+': native HDR scene did not commit')
            if suite == 'preview':
                preview = re.findall(r'^Vulkan PBR preview: (.*)$',section,re.M)
                preview_values = dict(re.findall(r'(\w+)=(\d+)',preview[-1])) if preview else {}
                if preview_values.get('committed') != ('0' if preview_fallback else '1'):
                    failures.append(name+': preview ownership does not match the bounded baked scope')
                if Path(row['screenshot']).with_suffix('.pfm').exists() or 'screenshot linear: no completed modern HDR scene' not in section:
                    failures.append(name+': HDR-off preview must refuse a public linear capture')
            if not preview_fallback and controls.get('r_pbrIBL') == '1' and controls.get('r_rendererReflectionProbes') == '1':
                probes = re.findall(r'^Vulkan PBR probes: (.*)$',section,re.M)
                probe_values = dict(re.findall(r'(\w+)=(\d+)',probes[-1])) if probes else {}
                if probe_values.get('records') != '2' or probe_values.get('ready') != '1' or int(probe_values.get('references','0')) <= 0:
                    failures.append(name+': both authored reflection probes were not published')
        expected = all(controls.get(key,'0') == '1' for key in
                       ('r_useLightGrid','r_rendererModernQuality','r_pbrMaterials','r_hdrToneMap'))
        if not matches:
            failures.append(name+': missing baked ownership telemetry')
        elif fault:
            if values.get('submitted') != 0:
                failures.append(name+': declined baked view submitted native receivers')
            if fault < 5 and (values.get('ready') != 0 or values.get('prepared') != 0):
                failures.append(name+': failed preparation retained receiver ownership')
            if fault < 5 and int(controls['r_vkPBRBakedFailureAfter']) > 0:
                if values.get('rejectedPrepared') != 2 or values.get('restoredUniform',0) <= 0:
                    failures.append(name+': late failure did not roll back prepared receivers and uniform slices')
            pfm = Path(row['screenshot']).with_suffix('.pfm')
            if pfm.exists() or 'screenshot linear: no completed modern HDR scene' not in section:
                failures.append(name+': declined view must refuse a linear capture')
        elif preview_fallback:
            if values.get('ready') != 0 or values.get('prepared') != 0 or values.get('submitted') != 0:
                failures.append(name+': unsupported baked preview retained native receiver ownership')
        elif expected:
            counts = [values.get(key,0) for key in ('requested','prepared','submitted')]
            if values.get('ready') != 1 or min(counts) <= 0 or len(set(counts)) != 1:
                failures.append(name+': baked receivers were not all prepared and submitted exactly once')
        elif values.get('submitted',0):
            failures.append(name+': disabled baked control still submitted receivers')
    if suite == 'admission':
        names = list(rows)
        if Path(rows[names[0]]['screenshot']).read_bytes() != Path(rows[names[-1]]['screenshot']).read_bytes():
            failures.append('restored image differs after rejected preparations')
        a,b = (Path(rows[name]['linearScreenshot']).read_bytes() for name in (names[0],names[-1]))
        if a != b:
            failures.append('restored linear radiance differs after rejected preparations')
        reference = Path(rows[names[1]]['screenshot']).read_bytes()
        if any(Path(rows[name]['screenshot']).read_bytes() != reference for name in names[2:-1]):
            failures.append('late failures changed the complete fallback image')
    return dict(status='fail' if failures else 'pass', failures=failures, receivers=evidence)


def compare(report, reference):
    failures, comparisons = [], {}
    if reference.get('bakedProof',{}).get('status') != 'pass':
        failures.append('OpenGL reference has not passed its independent controls')
    if report['bakeSHA256'] != reference.get('bakeSHA256') or report['compiledMapSHA256'] != reference.get('compiledMapSHA256'):
        failures.append('bake or compiled fixture differs between renderers')
    if report['bakedSettings'] != reference.get('bakedSettings'):
        failures.append('control settings differ between renderers')
    if report['bakedSuite'] != reference.get('bakedSuite'):
        failures.append('renderer reports use different scene setups')
    expected = {row['case']:row for row in reference['results']}
    if set(expected) != {row['case'] for row in report['results']}:
        failures.append('renderer reports cover different cases')
    for row in report['results']:
        name = row['case']
        if name not in expected: continue
        other = expected[name]
        item = {}
        for key in ('screenshot','linearScreenshot'):
            if key not in row and key not in other: continue
            if key not in row or key not in other:
                failures.append(name+': missing matched '+key)
                continue
            a,b = (Path(r[key]) for r in (row,other))
            if any(lab.digest(p) != r['sha256'][key] for p,r in ((a,row),(b,other))):
                failures.append(name+': capture provenance changed')
                continue
            if key == 'screenshot':
                x,y = (np.asarray(Image.open(p).convert('RGB'),dtype=np.float64) for p in (a,b))
                limit = 2.0
            else:
                x,y = (read_pfm(p).astype(np.float64) for p in (a,b))
                limit = 0.003
            delta = np.abs(x-y)
            item[key] = dict(maximumError=float(delta.max()), channelsOverLimit=int(np.count_nonzero(delta>limit)), limit=limit)
            if np.any(delta>limit): failures.append(name+': '+key+' exceeds the full-frame comparison limit')
        comparisons[name] = item
    return dict(status='fail' if failures else 'pass', failures=failures, cases=comparisons)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime-root',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--basepath',type=Path,required=True)
    p.add_argument('--bake-report',type=Path,required=True,help='completed GL laboratory report whose isolated maps directory contains the reference bake')
    p.add_argument('--backend',choices=('gl','vk'),default='vk')
    p.add_argument('--suite',choices=('composition','isolated','normals','recovery','overlays','preview','admission'),default='composition')
    p.add_argument('--samples',type=int,choices=(0,4,8),default=0)
    p.add_argument('--compare-gl-report',type=Path)
    args=p.parse_args()
    args.output_dir=args.output_dir.resolve()
    args.runtime_root=args.runtime_root.resolve()
    source_report=json.loads(args.bake_report.read_text())
    assert source_report['complete'] and source_report['runtimeUnchanged']
    assert all(row['backend']=='gl' and not row['failures'] for row in source_report['results'])
    game_dir=Path(source_report['results'][0]['log']).parent.parent
    sources={name:game_dir/(lab.lab.MAP+name) for name in ('.lightgrid','.lightgridpack')}
    bake_hashes={name:lab.digest(path) for name,path in sources.items()}
    cases=configure(args.suite,args.samples,args.backend)
    settings={name:{**lab.BASE,**lab.CASES[name]} for name in cases}
    write=lab.write_capture_commands
    def write_commands(path,commands):
        target=args.output_dir/'batch/baseoq4'
        for name,source in sources.items():
            dest=target/(lab.lab.MAP+name)
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,dest)
            assert lab.digest(dest)==bake_hashes[name]
        output=[]
        for command in commands:
            if command.startswith('bakeLightGrids '): continue
            output.append(command)
            if command.startswith(('screenshot "screenshots/baked-admission-fault','screenshot "screenshots/baked-preview')):
                output.append(command.replace('screenshot ','screenshot linear ').replace('.tga','.pfm'))
        return write(path,output)
    lab.write_capture_commands=write_commands
    sys.argv=[__file__,'--runtime-root',str(args.runtime_root),'--output-dir',str(args.output_dir),
              '--basepath',str(args.basepath),'--backend',args.backend,'--batch','--linear','--cases',','.join(cases),'--timeout','600']
    if args.backend=='gl':sys.argv+=['--gl-debug']
    code=lab.main()
    path=args.output_dir/'report.json'
    report=json.loads(path.read_text())
    report.update(bakedSuite=args.suite,bakedSettings=settings,bakeSHA256=bake_hashes,
                  bakeReportSHA256=lab.digest(args.bake_report))
    if args.backend == 'vk' and args.suite == 'recovery':
        report['bakedUnavailableControls'] = {
            'lightgrid-pbr-shader-reload':
                'rendererShaderLibraryReload is an OpenGL-only command; full vid_restart tests native pipeline recreation'}
    report['bakedProof']=prove(report,args.suite,settings)
    if args.compare_gl_report:
        report['bakedComparison']=compare(report,json.loads(args.compare_gl_report.read_text()))
        report['bakedReferenceReportSHA256']=lab.digest(args.compare_gl_report)
    shutil.copy2(__file__,args.output_dir/'harness'/Path(__file__).name)
    report['harnessSources'][Path(__file__).name]=lab.digest(Path(__file__))
    path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:report[key] for key in ('bakedProof','bakedComparison') if key in report},indent=2))
    return int(code or report['bakedProof']['status']!='pass' or report.get('bakedComparison',{}).get('status','pass')!='pass')


if __name__=='__main__':
    raise SystemExit(main())
