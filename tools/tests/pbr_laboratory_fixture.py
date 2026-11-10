#!/usr/bin/env python3
"""Exercise the PBR laboratory's original data and non-vacuous proof gates."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import struct
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/validation'))
import generate_pbr_validation_map as lab
import renderer_pbr_laboratory as runner
import renderer_pbr_environment_parity as environment_parity


def test_material_data_and_geometry() -> None:
    files, stations = lab.payloads()
    assert files == lab.payloads()[0], 'fixture must be deterministic'
    assert len(stations)==24 and len({s['name'] for s in stations})==24
    for metal in ('metal','dielectric'):
        ramp=[s['roughness'] for s in stations if s['name'].startswith(metal+'_')]
        assert ramp==sorted(ramp) and ramp[0]==0.045 and ramp[-1]==1
    def texel(name: str) -> tuple:
        raw=files[f'baseoq4/{lab.PREFIX}/{name}.tga']
        assert struct.unpack_from('<HH',raw,12)==(64,64)
        return tuple(raw[18+c] for c in (2,1,0))
    ao,rough,metal=texel('orm')
    assert (metal,rough,ao)==(102,128,192)
    assert texel('metallic')==(metal,)*3 and texel('roughness')==(rough,)*3 and texel('ao')==(ao,)*3
    scalar=next(s for s in stations if s['name']=='data_scalar')['parameters']
    assert (scalar['metallic'],scalar['roughness'],scalar['ao'])==(metal/255,rough/255,ao/255)
    cutout=files[f'baseoq4/{lab.PREFIX}/cutout.tga'][21::4]
    assert cutout.count(0)==cutout.count(255)==2048
    assert set(files[f'baseoq4/{lab.PREFIX}/translucent.tga'][21::4])=={112}
    ase=files['baseoq4/'+lab.MODEL].decode()
    vertices={int(i):(float(x),float(y),float(z)) for i,x,y,z in re.findall(r'\*MESH_VERTEX (\d+) ([^ ]+) ([^ ]+) ([^\n]+)',ase)}
    faces=re.findall(r'\*MESH_FACE (\d+): A: (\d+) B: (\d+) C: (\d+)',ase)
    assert len(faces)==48*46
    for _,a,b,c in faces:
        va,vb,vc=(vertices[int(k)] for k in (a,b,c))
        u=[vb[i]-va[i] for i in range(3)]; v=[vc[i]-va[i] for i in range(3)]
        cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        assert sum(cross[i]*va[i] for i in range(3))>0, 'degenerate or inverted source sphere face'
    level=files['baseoq4/'+lab.MAP+'.map'].decode()
    assert 'classic_floor' in level and 'coverage_backplate' in level and '"light_target"' in level
    assert '"mtr_local_global_test"' in level
    assert 'noSelfShadow' in files['baseoq4/materials/openq4_pbr_lab.mtr'].decode()
    checker=files[f'baseoq4/{lab.PREFIX}/checker.tga'][18::3]
    assert checker.count(0)==checker.count(255)==2048
    assert '*MESH_TVERT 0 2.37500000 2.37500000 0' in files['baseoq4/'+lab.SAMPLING_MODEL].decode()
    plane = files['baseoq4/'+lab.BACKFACE_MODEL].decode()
    plane_vertices = {int(i):(float(x),float(y),float(z)) for i,x,y,z in re.findall(r'\*MESH_VERTEX (\d+) ([^ ]+) ([^ ]+) ([^\n]+)',plane)}
    plane_faces = re.findall(r'\*MESH_FACE (\d+): A: (\d+) B: (\d+) C: (\d+)',plane)
    assert len(plane_vertices) == 4 and len(plane_faces) == 2
    for _,a,b,c in plane_faces:
        va,vb,vc = (plane_vertices[int(k)] for k in (a,b,c))
        u = [vb[i]-va[i] for i in range(3)]; v = [vc[i]-va[i] for i in range(3)]
        normal = (u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        assert normal[0] == normal[2] == 0 and normal[1] < 0
        # The retained camera sees the -Y side; the regression's rear light
        # sits at local Y=10, so both geometric faces must reject that light.
        assert all(point[1] == 0 for point in (va,vb,vc))
        assert normal[1] * 10 < 0
    mesh=files['baseoq4/models/openq4/pbr_lab/skinned.md5mesh'].decode()
    weights=[(int(j),float(w)) for j,w in re.findall(r'weight \d+ (\d+) ([^ ]+) ',mesh)]
    assert {j for j,_ in weights}=={0,1}
    blended=0
    for first,count in re.findall(r'vert \d+ \( [^\n]+ \) (\d+) (\d+)',mesh):
        selected=weights[int(first):int(first)+int(count)]
        assert 1<=len(selected)<=2 and abs(sum(w for _,w in selected)-1)<1e-7
        blended+=len(selected)==2
    assert blended>64, 'the specimen must deform with blended joints'


def test_proof_rejects_fallback_and_missing_channels(root: Path) -> None:
    manifest=lab.generate(root)
    args=argparse.Namespace(runtime_root=root,backend='gl',tier='gl45',camera='overview')
    shot=root/'proof.tga'
    header=struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,1280,800,24,0x20)
    shot.write_bytes(header+bytes([0,0,0])*(1280*800))
    telemetry='\n'.join(('PBR material resources: records=25 fallback=0',
                         'Modern visible frame: exec=1 blocked=0',
                         'Modern forward+: fallback=0',
                         'Modern clustered specular probes: uploaded=2 frameReady=1'))
    for case in ('ownership','metallic','roughness','ao','emissive','direct'):
        result=runner.inspect_capture(args,case,telemetry,shot)
        assert result['failures'], f'a black {case} image cannot prove PBR'
    ownership=runner.inspect_capture(args,'ownership',telemetry.replace('exec=1','exec=0'),shot)
    assert 'PBR did not own the visible frame' in ownership['failures']
    missing=runner.inspect_capture(args,'lit',telemetry.replace('uploaded=2','uploaded=0'),shot)
    assert 'both authored probes were not consumed' in missing['failures']
    omitted=runner.inspect_capture(args,'lit',telemetry.replace('forward+: fallback=0','forward+: fallback=1'),shot)
    assert 'PBR forward draw omitted' in omitted['failures']
    missing_shadows=runner.inspect_capture(args,'shadows',telemetry,shot)
    assert 'complete current point and projected shadow maps were not consumed' in missing_shadows['failures']
    maps='\nModern current shadow map: light=0 point=1 ready=1 dynamic=1 firstTile=0 columns=4\nModern current shadow map: light=1 point=0 ready=1 dynamic=0 firstTile=0 columns=2'
    valid_shadows=runner.inspect_capture(args,'shadows',telemetry+maps,shot)
    assert not valid_shadows['failures']
    production=runner.inspect_capture(args,'production',telemetry,shot)
    assert 'production admission relied on a parity override or lacked its material contract' in production['failures']
    production_telemetry=telemetry+'\nmodernLightingOwnership override=0 requested=1 materialContract=1 interaction(pass=1 lights=4)'
    production=runner.inspect_capture(args,'production',production_telemetry,shot)
    assert not production['failures']
    forced=runner.inspect_capture(args,'production',production_telemetry.replace('override=0','override=15'),shot)
    assert forced['failures'], 'a diagnostic parity override is not production proof'
    environment=runner.inspect_capture(args,'environment-only',production_telemetry,shot)
    assert 'environment-only control still requested direct lighting' in environment['failures']
    stale=runner.inspect_capture(args,'shadows',telemetry+maps.replace('ready=1','ready=0'),shot)
    assert stale['failures'], 'a previously rendered but stale map cannot prove current shadows'
    aliased=runner.inspect_capture(args,'multi-shadows',telemetry+maps+'\nModern current shadow map: light=2 point=1 ready=1 dynamic=0 firstTile=0 columns=4\nModern current shadow map: light=3 point=1 ready=1 dynamic=0 firstTile=12 columns=4',shot)
    assert 'three point lights did not consume distinct complete maps' in aliased['failures']
    false_msaa=runner.inspect_capture(args,'msaa',telemetry+'\nRenderer AA: MSAA requested=4 effective=0',shot)
    assert 'four-sample MSAA was requested but is not effective' in false_msaa['failures']
    undefined=runner.inspect_capture(args,'lit',telemetry+'\nGL debug callback [source=api type=undefined severity=medium] invalid sampler',shot)
    assert undefined['diagnostics']
    assert not runner.diagnostic_lines('GL debug callback [source=api type=performance severity=medium] Program/shader state performance warning: recompiled')
    startup={**runner.BASE,'fs_game':'baseoq4','fs_savepath':str(root),'fs_basepath':'stock','fs_devpath':str(root),'r_renderApi':'gl','r_glTier':'gl45'}
    command=runner.startup_args(startup,root)
    assert command.count('+set')+1<64
    autoexec=(root/'baseoq4/autoexec.cfg').read_text()
    assert all(f'set {k} "{v}"' in autoexec for k,v in startup.items())
    assert len(manifest['sha256'])>=26


def test_differential_proof(root: Path) -> None:
    def sample(case: str, name: str, rgb: list[float]) -> dict:
        return {'case':case,'backend':'gl','tier':'gl45','image':{'stationRGB':{name:rgb}},'failures':[]}
    # A second legacy alpha pass changes the expected one-blend green response.
    good=[sample('ownership','source_alpha',[38,142,28]),sample('emissive','source_alpha',[38,30,28])]
    runner.compare_transparency_captures(good)
    assert not good[0]['failures']
    good[0]['image']['stationRGB']['source_alpha'][1]=93
    runner.compare_transparency_captures(good)
    assert good[0]['failures']
    # Without its emission control the pair proves nothing, and the report has
    # to say so rather than passing quietly.
    lonely=[sample('ownership','source_alpha',[38,142,28])]
    runner.compare_transparency_captures(lonely)
    assert not lonely[0]['failures']
    assert lonely[0]['materialComparisons']['emissive/source_alpha']['status']=='not measured'
    bad=[sample('lit','ao_zero',[0,0,0]),sample('direct','ao_zero',[100,100,100])]
    runner.compare_material_captures(bad)
    assert bad[0]['failures'], 'material AO must not multiply direct light'
    # Counters cannot prove fog/blend composition. Catch a no-op stage, double
    # application and even one depth-equality hole within a receiver patch.
    for kind in ('fog','blend'):
        source=[0.06,0.9,3.0]
        target=[x*0.6+c*0.4 for x,c in zip(source,(0.18,0.32,0.48))] if kind=='fog' else [x*c for x,c in zip(source,(0.4,0.7,0.2))]
        controls=[]
        for suffix,color in (('-clear',source),('',target)):
            row=sample(f'{kind}-pbr{suffix}','unused',[0,0,0])
            row['linearImage']={'stationRGB':{f'specimen{i}':color[:] for i in range(22)},
                                'stationPatches':{f'specimen{i}':[color[:] for _ in range(49)] for i in range(22)}}
            controls.append(row)
        runner.compare_material_captures(controls)
        assert not controls[1]['failures'], 'a valid linear overlay must pass'
        controls[1]['linearImage']['stationPatches']['specimen0'][24]=source[:]
        runner.compare_material_captures(controls)
        assert controls[1]['failures'], 'one uncovered opaque pixel must fail'
        controls[1]['failures']=[]
        controls[1]['linearImage']['stationRGB']['specimen1']=source[:]
        runner.compare_material_captures(controls)
        assert any('specimen1' in failure for failure in controls[1]['failures']), 'a no-op overlay must fail'
        if kind=='blend':
            controls[1]['failures']=[]
            controls[1]['linearImage']['stationRGB']['specimen2']=[x*c for x,c in zip(target,(0.4,0.7,0.2))]
            runner.compare_material_captures(controls)
            assert any('specimen2' in failure for failure in controls[1]['failures']), 'double modulation must fail'
    # Baked-light counters are insufficient too: reject no illumination,
    # metallic diffuse, ignored AO and nonlinear intensity in the float image.
    grids=[]
    names=[f'dielectric_{i}' for i in range(20)]+['metal_0','ao_zero']
    for suffix,scale in (('-clear',0),('',1),('-double',2)):
        row=sample('lightgrid-pbr'+suffix,'unused',[0,0,0])
        row['linearImage']={'stationRGB':{name:[0.2+(0 if name in ('metal_0','ao_zero') else 0.1*scale)]*3 for name in names}}
        grids.append(row)
    runner.compare_material_captures(grids)
    assert not any(row['failures'] for row in grids)
    for name,value,message in (('dielectric_0',0.2,'ignored baked light'),('metal_0',0.3,'metallic diffuse'),('ao_zero',0.3,'ignored AO')):
        original=grids[1]['linearImage']['stationRGB'][name]
        grids[1]['linearImage']['stationRGB'][name]=[value]*3
        runner.compare_material_captures(grids)
        assert any(name in error for error in grids[1]['failures']), message
        grids[1]['linearImage']['stationRGB'][name]=original
        for row in grids: row['failures']=[]
    grids[2]['linearImage']['stationRGB']['dielectric_0']=[0.5]*3
    runner.compare_material_captures(grids)
    assert grids[2]['failures'], 'nonlinear baked intensity'
    hdr=[sample('hdr-emissive','emissive',[61,248,253]),sample('hdr-half-exposure','emissive',[34,236,246])]
    runner.compare_material_captures(hdr)
    assert not any(r['failures'] for r in hdr)
    hdr[0]['image']['stationRGB']['emissive']=[13,255,255]
    runner.compare_material_captures(hdr)
    assert 'incorrect linear HDR tone-map/output transfer' in hdr[0]['failures']
    # Identical normal debug surfaces are insufficient: an ignored normal map
    # would trivially satisfy all encoding comparisons.
    shot=root/'flat-normal.tga'
    shot.write_bytes(struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,1280,800,24,0x20)+bytes([255,128,128])*(1280*800))
    normals=[{'case':case,'screenshot':str(shot),'failures':[]} for case in ('normal-xyz','normal-rg','normal-agb','normal-flat','normal-zero')]
    runner.compare_normal_captures(normals)
    assert normals[0]['failures'], 'normal evidence needs a visible perturbation'
    shadows=[{'case':case,'screenshot':str(shot),'failures':[]} for case in ('lit','shadows','shadow-moved','shadow-restored','multi-shadows','multi-unshadowed')]
    runner.compare_shadow_captures(shadows)
    assert shadows[1]['failures'], 'shadow telemetry alone cannot prove visible shadows'
    assert shadows[2]['failures'], 'a frozen cached shadow cannot prove a moving caster'
    assert not shadows[3]['failures'], 'restoring a caster must restore the reference image'
    assert shadows[4]['failures'], 'multiple shadow textures must actually affect lighting'
    poisoned=bytearray(shot.read_bytes())
    # A single darkened texel on an unoccluded wall must fail the acne gate,
    # independently of the broad shadow-response differential.
    poisoned[18+(40*1280+500)*3:18+(40*1280+500)*3+3]=bytes([0,0,0])
    acne=root/'acne.tga'; acne.write_bytes(poisoned)
    bad_shadow=[{'case':'lit','screenshot':str(shot),'failures':[]},
                {'case':'shadows','screenshot':str(acne),'failures':[]}]
    runner.compare_shadow_captures(bad_shadow)
    assert 'shadow acne on an unoccluded planar receiver' in bad_shadow[1]['failures']
    classic=[{'case':case,'backend':'gl','tier':'gl45','screenshot':str(path),'failures':[]}
             for case,path in (('production',acne),('production-native',shot))]
    runner.compare_material_captures(classic)
    assert 'classic backdrop differs from the native lighting reference' in classic[0]['failures']
    overlays=[{'case':case,'backend':'gl','tier':'gl45','screenshot':str(path),'failures':[]}
              for case,path in (('fog-native',shot),('fog-off',shot),('fog-clear',shot),('fog-restored',acne))]
    runner.compare_material_captures(overlays)
    assert overlays[0]['failures'], 'a missing fog overlay cannot prove composition'
    assert overlays[3]['failures'], 'removing fog must restore the original PBR frame'
    env=[sample('environment-only','metal_3',[80,50,30]),sample('environment-off','metal_3',[0,0,0])]
    runner.compare_material_captures(env)
    assert not env[0]['failures']
    env[0]['image']['stationRGB']['metal_3']=[0,0,0]
    runner.compare_material_captures(env)
    assert env[0]['failures'], 'zero direct lights must not silently disable IBL'
    post=[{'case':case,'backend':'gl','tier':'gl45','screenshot':str(shot),'failures':[]}
          for case in ('hdr','hdr-half','hdr-hud','hdr-hud-half','bloom','hdr-auto')]
    runner.compare_post_captures(post)
    assert post[2]['failures'], 'an absent HUD cannot establish exposure-independent UI'
    assert post[4]['failures'], 'bloom must produce a visible change'
    assert post[5]['failures'], 'auto exposure needs an actual luminance sample'
    same_msaa=[{'case':case,'screenshot':str(shot),'failures':[]} for case in ('ownership','msaa-ownership')]
    runner.compare_msaa_captures(same_msaa)
    assert 'MSAA did not resolve fractional geometry coverage' in same_msaa[1]['failures']
    same_cutout=[{'case':case,'screenshot':str(shot),'failures':[]} for case in ('msaa-cutout','msaa-cutout-hard')]
    runner.compare_msaa_captures(same_cutout)
    assert 'alpha-to-coverage did not smooth interior cutout boundaries' in same_cutout[0]['failures']
    samplers=[{'case':f'sampler-{name}','screenshot':str(shot),'failures':[]} for name in ('nearest','linear','clamp','mips')]
    runner.compare_sampler_captures(samplers)
    assert all(r['failures'] for r in samplers), 'a shared overridden sampler cannot prove authored sampling'
    skinning=[{'case':f'skin-{backend}{suffix}','screenshot':str(shot),'failures':[]}
              for backend in ('cpu','gpu') for suffix in ('','-bent','-ownership')]
    runner.compare_skinning_captures(skinning)
    assert all(r['failures'] for r in skinning if r['case'].endswith(('-bent','-ownership'))), 'a frozen or absent specimen cannot prove skinning'
    reference=root/'msaa-reference.pfm'; changed=root/'msaa-restart.pfm'
    header=b'PF\n1280 800\n-1.0\n'
    values=bytearray(struct.pack('<fff',0.25,0.5,1.0)*(1280*800))
    reference.write_bytes(header+values)
    struct.pack_into('<f',values,0,0.25+1/4096)
    changed.write_bytes(header+values)
    restarted=[{'case':'msaa','screenshot':str(shot),'linearScreenshot':str(reference),'failures':[]},
               {'case':'msaa-partial-restart','screenshot':str(shot),'linearScreenshot':str(changed),'failures':[]}]
    runner.compare_msaa_captures(restarted)
    assert not restarted[1]['failures'], 'one half-float rounding step is allowed'
    struct.pack_into('<f',values,0,0.25+2/4096)
    changed.write_bytes(header+values)
    runner.compare_msaa_captures(restarted)
    assert 'MSAA restart changed the scene beyond FP16 rounding' in restarted[1]['failures']
    restarted[0]['case']='blend-pbr-msaa-clear'
    restarted[1]['case']='blend-pbr-msaa-restored'
    restarted[1]['failures']=[]
    runner.compare_msaa_captures(restarted)
    assert 'MSAA overlay restore changed the scene beyond FP16 rounding' in restarted[1]['failures']


def test_classic_float_reference(root: Path) -> None:
    from array import array
    width,height=1280,800
    display=bytearray(width*height*3)
    linear=array('f',[0])*(width*height*3)
    for y in range(296,385):
        for x in range(663,752):
            value=30+(x-663)
            encoded=value/255
            radiance=encoded/12.92 if encoded<=0.04045 else ((encoded+0.055)/1.055)**2.4
            for c in range(3):
                display[(y*width+x)*3+c]=value
                linear[((height-1-y)*width+x)*3+c]=radiance
    native=root/'classic-native.tga'
    native.write_bytes(struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,width,height,24,0x20)+display)
    pfm=root/'classic-linear.pfm'
    def write(values):
        pfm.write_bytes(b'PF\n1280 800\n-1.0\n'+values.tobytes())
    def check():
        rows=[{'case':'production-fixed','backend':'gl','tier':'gl45','linearScreenshot':str(pfm),'failures':[]},
              {'case':'production-fixed-native','backend':'gl','tier':'gl45','screenshot':str(native),'failures':[]}]
        runner.compare_material_captures(rows)
        return rows[0]['failures']
    write(linear)
    assert not check(), 'unclipped encoded native reference must match its linear radiance'
    offset=((height-1-340)*width+707)*3
    original=linear[offset]
    linear[offset]=0
    write(linear)
    assert check(), 'a single missing classic lighting sample must fail'
    linear[offset]=original
    write(array('f',[0])*(width*height*3))
    assert check(), 'no-op lighting must fail'
    write(array('f',[1])*(width*height*3))
    native.write_bytes(native.read_bytes()[:18]+bytes([255])*(width*height*3))
    assert check(), 'matching clipped highlights are not compatibility proof'


def test_classic_display_shoulder(root: Path) -> None:
    from array import array
    settings={**runner.BASE,**runner.CASES['production-fixed-native']}
    def transfer(value: float) -> float:
        return runner.stock_display_transfer(value,settings)
    # BASE pins exposure 1 and white point 6: identity below the 0.5 shoulder,
    # and the 0.782 classic highlight measured on 2026-10-04 displays as 175.
    assert transfer(0.4)==0.4
    assert abs(255*transfer(199.4/255)-175)<0.5
    try: runner.stock_display_transfer(0.6,{**settings,'r_hdrGain':'2'})
    except ValueError: pass
    else: raise AssertionError('an unmodelled display adjustment was accepted')
    width,height=1280,800
    unshouldered=bytearray(width*height*3)
    shouldered=bytearray(width*height*3)
    linear=array('f',[0])*(width*height*3)
    for y in range(296,385):
        for x in range(663,752):
            value=100+(x-663)
            encoded=value/255
            radiance=((encoded+0.055)/1.055)**2.4
            for c in range(3):
                unshouldered[(y*width+x)*3+c]=value
                shouldered[(y*width+x)*3+c]=round(255*transfer(encoded))
                linear[((height-1-y)*width+x)*3+c]=radiance
    header=struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,width,height,24,0x20)
    native=root/'classic-shoulder-native.tga'
    pfm=root/'classic-shoulder-linear.pfm'
    pfm.write_bytes(b'PF\n1280 800\n-1.0\n'+linear.tobytes())
    def check(image: bytearray) -> list[str]:
        native.write_bytes(header+image)
        rows=[{'case':'production-fixed','backend':'gl','tier':'gl45','linearScreenshot':str(pfm),'failures':[]},
              {'case':'production-fixed-native','backend':'gl','tier':'gl45','screenshot':str(native),'failures':[]}]
        runner.compare_material_captures(rows)
        return rows[0]['failures']
    assert not check(shouldered), 'a highlight through the stock shoulder must match its linear radiance'
    assert check(unshouldered), 'a native highlight that skipped the stock shoulder must fail'


def test_native_msaa_rounding(root: Path) -> None:
    header=struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,1280,800,24,0x20)
    values=bytearray([100])*(1280*800*3)
    native=root/'native-msaa.tga'
    native.write_bytes(header+values)
    fallback=root/'fallback-msaa.tga'
    def check():
        fallback.write_bytes(header+values)
        rows=[{'case':'production-fixed-msaa-fallback','screenshot':str(fallback),'failures':[]},
              {'case':'production-fixed-msaa-native','screenshot':str(native),'failures':[]}]
        runner.compare_msaa_captures(rows)
        return rows[0]['failures']
    values[0]=101
    assert not check(), 'one UNORM8 resolve step is permitted'
    values[0]=102
    assert check(), 'two UNORM8 steps cannot pass as rounding'
    values[:17]=bytes([101])*17
    assert check(), 'more than the existing 16-channel MSAA display budget must fail'


def test_vulkan_backend_evidence() -> None:
    identity = 'Renderer API: requested=vulkan active=vulkan disposition=module'
    validation = 'Vulkan: validation enabled (VK_LAYER_KHRONOS_validation, debug messenger active)'
    assert not runner.vulkan_backend_failures(identity + '\n' + validation)
    assert runner.vulkan_backend_failures(identity), 'requested validation is not active-layer proof'
    assert runner.vulkan_backend_failures(validation), 'a debug messenger alone does not prove the renderer owner'
    assert runner.vulkan_backend_failures(identity + '\n' + validation +
        '\nRenderer API: requested=vulkan active=gl disposition=fallback'), 'a later fallback cannot qualify Vulkan'


def test_vulkan_direct_evidence(root: Path) -> None:
    header=struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,1280,800,24,0x20)
    paths={}
    for name,color in (('grey',(100,100,100)),('changed',(102,102,102)),
                       ('green',(0,255,0)),('black',(0,0,0)),('white',(255,255,255))):
        paths[name]=root/f'vk-direct-{name}.tga'
        paths[name].write_bytes(header+bytes(color)*(1280*800))
    def check(assignments,telemetry=()):
        rows=[{'case':'vk-direct-'+case,'screenshot':str(paths[image]),'failures':[],'telemetry':list(telemetry)}
              for case,image in assignments]
        runner.compare_vulkan_direct_captures(rows)
        return rows
    equal=check([('scalar','grey'),('packed','grey'),('separate','grey'),('ao-zero','grey')])
    assert not any(row['failures'] for row in equal), 'equal, nonclipped data layouts must compare'
    different=check([('scalar','grey'),('packed','changed'),('ao-zero','changed')])
    assert all(row['failures'] for row in different[1:]), 'data decoding and direct-AO errors must fail'
    assert check([('ownership-separate','grey')])[0]['failures'], 'classic fallback is not native ownership'
    assert not check([('ownership-separate','green')])[0]['failures']
    for image in ('black','white'):
        assert check([('scalar',image)])[0]['failures'], 'dark or clipped matches are not material proof'
    for left,right in (('normal-xyz','flat'),('rough-low','rough-high'),('scalar','master-off')):
        rows=check([(left,'grey'),(right,'grey')])
        assert rows[0]['failures'], 'a no-op material control must fail'
    for image in ('grey','green'):
        assert check([('cutout-owned',image)])[0]['failures'], 'cutout requires native material and holes'
    assert check([('cutout-lit','grey'),('cutout-legacy','grey')])[0]['failures'], 'classic fallback cannot prove native cutout shading'
    rows=check([('emission-mismatch-fallback','grey'),('emission-mismatch-native','changed')])
    assert rows[1]['failures'], 'partial PBR emission promotion must fail exact classic fallback'
    assert check([('emission-half','grey')])[0]['failures'], 'emission needs an independent linear color reference'
    assert check([('emission-extreme','grey')])[0]['failures'], 'extreme emission must preserve the faint channel'
    # A committed linear HDR scene maps the unclipped red channel through the
    # filmic curve and one sRGB encode, 178 instead of production's 3.
    paths['filmic']=root/'vk-direct-filmic.tga'
    paths['filmic'].write_bytes(header+bytes((255,255,178))*(1280*800))
    linear=['Vulkan HDR: sceneRequested=1 sceneFormat=RGBA16F linearScene=1']
    assert not check([('emission-extreme','filmic')],linear)[0]['failures'], 'linear extreme emission must match its filmic reference'
    assert check([('emission-extreme','filmic')],[linear[0].replace('linearScene=1','linearScene=0')])[0]['failures'], \
        'the stock-domain reference must reject a filmic display value'
    assert check([('emission-dark','grey')])[0]['failures'], 'disabled emission must not retain radiance'
    for shape in ('geometric','normal'):
        rows=check([('aa-'+shape,'grey'),('aa-'+shape+'-off','grey'),('aa-'+shape+'-owned','green')])
        assert rows[0]['failures'], 'a no-op specular filter must fail its owned-surface effect check'
    rows=check([('aa-constant','grey'),('aa-constant-off','changed')])
    assert rows[1]['failures'], 'specular AA must preserve constant shading normals'
    rows=check([('aa-rough','grey'),('aa-rough-off','changed')])
    assert rows[1]['failures'], 'specular AA must preserve the roughness ceiling'
    args=argparse.Namespace(backend='vk',tier='gl45',camera='sampling',runtime_root=root)
    def mapped(text):
        return runner.inspect_capture(args,'vk-direct-shadow-point',
            'Renderer AA: MSAA requested=0 effective=0\n'+text,paths['grey'])['failures']
    for counts in ('static=1 dynamic=0','static=0 dynamic=1'):
        assert not mapped(f"SM pass light[6] 'fixture' type=point GLOBAL=reuse casters({counts})")
    for invalid in ('', "SM pass light[6] 'fixture' type=point GLOBAL=unmapped casters(static=1 dynamic=0)",
                    "SM pass light[6] 'fixture' type=point GLOBAL=reuse casters(static=0 dynamic=0)",
                    "SM pass light[6] 'fixture' type=projected GLOBAL=reuse casters(static=1 dynamic=0)"):
        assert mapped(invalid), 'missing, wrong-kind or incomplete shadow maps must fail'
    complete="SM pass light[6] 'fixture' type=point GLOBAL=reuse casters(static=1 dynamic=0)"
    assert runner.inspect_capture(args,'vk-direct-shadow-point',complete,paths['grey'])['failures'], 'missing actual AA evidence must fail'


def test_vulkan_msaa_coverage_evidence(root: Path) -> None:
    header=struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,1280,800,24,0x20)
    pixels=bytearray(1280*800*3)
    for y in range(300,500):
        for x in range(500,700):
            pixels[(y*1280+x)*3+1]=255
    reports=[]
    for samples in (0,4):
        shot=root/f'vk-edge-{samples}.tga'
        log=root/f'vk-edge-{samples}.log'
        log.write_text(f'Renderer AA: MSAA requested={samples} effective={samples}\n')
        if samples==4:
            for x in range(500,700): pixels[(300*1280+x)*3+1]=128
        shot.write_bytes(header+pixels)
        reports.append({'complete':True,'runtimeSHA256':{'vk':'same'},'fixture':{'id':'same'},
                        'compiledMapSHA256':'same','results':[{'case':'vk-direct-ownership-scalar',
                        'backend':'vk','camera':'sampling','failures':[],
                        'screenshot':str(shot),'log':str(log),
                        'sha256':{'screenshot':runner.digest(shot),'log':runner.digest(log)}}]})
    assert not runner.compare_vulkan_msaa_reports(*reports)['failures']
    def rejected(change):
        pair=json.loads(json.dumps(reports)); change(pair)
        assert runner.compare_vulkan_msaa_reports(*pair)['failures']
    rejected(lambda p:p[1].update(runtimeSHA256={'vk':'other'}))
    rejected(lambda p:p[1].update(compiledMapSHA256='other'))
    rejected(lambda p:p[1]['results'][0].update(failures=['failed']))
    rejected(lambda p:p[1]['results'][0].update(screenshot=p[0]['results'][0]['screenshot']))
    rejected(lambda p:p[1]['results'][0].update(log=p[0]['results'][0]['log']))
    # Even a correctly rehashed no-op image is not antialiasing evidence.
    rejected(lambda p:p[1]['results'][0].update(screenshot=p[0]['results'][0]['screenshot'],
        sha256={**p[1]['results'][0]['sha256'],'screenshot':p[0]['results'][0]['sha256']['screenshot']}))


def test_ibl_proof_gates() -> None:
    original=runner.normal_patch
    def check(values):
        rows=[{'case':'ibl-'+name,'screenshot':name,'failures':[]} for name in values]
        try:
            runner.normal_patch=lambda path: values[str(path)]
            runner.compare_ibl_captures(rows)
        finally:
            runner.normal_patch=original
        return [failure for row in rows for failure in row['failures']]
    lit=bytes([18,24,32])*64
    dark=bytes(len(lit))
    assert not check({'scalar':lit,'restored':lit,'off':dark,'ao-zero':dark})
    assert check({'scalar':dark}), 'zero lighting is not environment evidence'
    assert check({'scalar':b''}), 'missing capture must fail'
    assert check({'scalar':bytes([255])*len(lit)}), 'clipping hides the lobe'
    assert check({'off':lit}) and check({'ao-zero':lit}), 'disabled/occluded lighting must disappear'
    assert check({'alpha-off':lit}), 'unlit transparent material must not retain its classic color stage'
    assert check({'scalar':lit,'restored':bytes([20])*len(lit)}), 'state restoration must be exact'
    assert check({'scalar':lit,'double':lit}), 'intensity control must have an effect'
    assert check({'rough-low':lit,'rough-high':lit}), 'roughness control must have an effect'
    assert check({'alpha':lit,'alpha-off':lit}), 'transparent environment must have an effect'
    mask=bytes([0,0,0,0,255,0])*32
    assert not check({'cutout-coverage':mask,'cutout-hard-coverage':mask})
    assert check({'cutout-coverage':bytes([0,255,0])*64}), 'coverage must retain holes'
    assert check({'cutout-hard-coverage':mask+bytes([0,64,0])*32}), 'hard cutouts must reject partial coverage'


def test_bounded_console_scripts(root: Path) -> None:
    commands=[f'echo "capture_{i:04d}_'+('x'*220)+'"' for i in range(800)]
    cfg=root/'bounded.cfg'
    parts=runner.write_capture_commands(cfg,commands)
    assert len(parts)>1
    restored=[]
    path=cfg
    while True:
        assert path.stat().st_size<64*1024, 'script must fit the actual engine insertion buffer'
        assert runner.digest(path)==parts[path.name]
        lines=path.read_text().splitlines()
        next_path=None
        if lines[-1].startswith('exec '):
            next_path=root/lines.pop().split('"')[1]
        restored+=lines
        if next_path is None: break
        path=next_path
    assert restored==commands, 'chunking must retain the complete command order'


def test_ibl_parity_provenance(root: Path) -> None:
    header=struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,1280,800,24,0x20)
    shots={}
    for value in (0,10,20,22,30,40):
        shot=root/f'ibl-value-{value}.tga'
        shot.write_bytes(header+bytes([value])*(1280*800*3))
        shots[value]=shot
    coverage=root/'ibl-coverage.tga'
    coverage.write_bytes(header+(bytes([0,0,0])*640+bytes([0,255,0])*640)*800)
    log=root/'ibl-proof.log'
    log.write_text('Renderer AA: MSAA requested=0 effective=0\n')
    pair=[]
    for backend in ('gl','vk'):
        rows=[]
        for name in runner.IBL_MATERIALS:
            if backend=='gl' and name=='shared': continue
            value=0 if name in ('off','ao-zero','zero','alpha-off','cutout-off','master-off','legacy','production') else 20
            value={'rough-low':10,'rough-high':30,'double':40}.get(name,value)
            if name.startswith('normal-'): value=22
            shot=coverage if name.endswith('coverage') else shots[value]
            rows.append({'case':'ibl-'+name,'backend':backend,'camera':'sampling','failures':[],
                         'screenshot':str(shot),'log':str(log),
                         'sha256':{'screenshot':runner.digest(shot),'log':runner.digest(log)}})
        pair.append({'complete':True,'runtimeUnchanged':True,'runtimeSHA256':{'engine':'same'},
                     'fixture':{'id':'same'},'compiledMapSHA256':'same','basepath':'same',
                     'harnessSHA256':'same','requestedSamples':0,'results':rows})
    assert not environment_parity.compare(*pair)['failures']
    def rejected(change):
        altered=json.loads(json.dumps(pair)); change(altered)
        assert environment_parity.compare(*altered)['failures']
    rejected(lambda p:p[1].update(complete=False))
    rejected(lambda p:p[1].update(runtimeUnchanged=False))
    for key,value in (('runtimeSHA256',{'engine':'other'}),('compiledMapSHA256','other'),
                      ('harnessSHA256','other'),('requestedSamples',4)):
        rejected(lambda p,k=key,v=value:p[1].update({k:v}))
    for key in ('runtimeSHA256','compiledMapSHA256','fixture','basepath','harnessSHA256','requestedSamples'):
        rejected(lambda p,k=key:[report.pop(k) for report in p])
    rejected(lambda p:p[1]['results'].pop())
    rejected(lambda p:p[1]['results'].append(p[1]['results'][0]))
    rejected(lambda p:p[1]['results'][0].update(backend='gl'))
    rejected(lambda p:p[1]['results'][0].update(failures=['previous failure']))
    rejected(lambda p:p[1]['results'][0]['sha256'].update(screenshot='changed'))
    # A rehashed but unlit specimen also fails after the standalone gate
    # reruns the individual controls; matching backends alone cannot pass it.
    for report in pair:
        report['results'][0].update(screenshot=str(shots[0]))
        report['results'][0]['sha256']['screenshot']=runner.digest(shots[0])
    assert environment_parity.compare(*pair)['failures']


def test_ibl_coverage_lighting() -> None:
    a=bytearray([0]*50+[255]*50); b=bytearray(a); a[49]=64
    def color(mask): return bytes(round(v*c/255) for v in mask for c in (20,30,40))
    ca,cb=color(a),color(b)
    assert not environment_parity.coverage_lighting(ca,cb,a,b)['failures']
    assert environment_parity.coverage_lighting(ca,bytes(len(cb)),a,b)['failures']
    bad=bytearray(cb); bad[0]=20
    assert environment_parity.coverage_lighting(ca,bad,a,b)['failures'], 'a hole cannot emit light'
    bad=bytearray(ca); bad[49*3]=255
    assert environment_parity.coverage_lighting(bad,cb,a,b)['failures'], 'a one-sample edge cannot hide a bright artifact'
    bad=bytearray(b); bad[50]=0
    assert environment_parity.coverage_lighting(ca,color(bad),a,bad)['failures'], 'whole missing pixels are not sample quantization'
    bad=bytearray(b)
    for i in range(50,65): bad[i]=191
    assert environment_parity.coverage_lighting(ca,color(bad),a,bad)['failures'], 'systematic coverage loss must fail'


def test_probe_hard_cutout_lighting() -> None:
    from renderer_pbr_probe_parity import hard_cutout_lighting
    width,height=256,128
    mask=bytes(255 if 64<=x<192 else 0 for y in range(height) for x in range(width))
    def color(values): return bytes(c if value else 0 for value in values for c in (20,30,40))
    baseline=color(mask)
    def check(other, actual=None, reference=baseline):
        return hard_cutout_lighting(reference, color(other) if actual is None else actual,
                                    mask,other,width,height)['failures']
    assert not check(mask)
    edge=64*width+64
    missing=bytearray(mask); missing[edge]=0
    assert not check(missing), 'one measured boundary fragment is permitted'
    missing[65*width+64]=0
    assert check(missing), 'systematic edge erosion must fail the pixel budget'
    missing=bytearray(mask); missing[64*width+128]=0
    assert check(missing), 'an interior hole is not edge quantization'
    wrong=bytearray(baseline); wrong[3*(64*width+128)]+=3
    assert check(mask,wrong), 'covered radiance still has a two-byte limit'
    wrong=bytearray(baseline); wrong[0]=2
    assert check(mask,wrong), 'uncovered pixels cannot carry stray light'
    missing=bytearray(mask); missing[edge]=0
    wrong=bytearray(baseline); wrong[3*edge]=255
    assert check(missing,reference=wrong), 'an unmatched edge cannot conceal a bright artifact'
    partial=bytearray(mask); partial[edge]=128
    assert check(partial), 'single-sample coverage must be binary'
    empty=bytes(len(mask))
    assert hard_cutout_lighting(color(empty),color(empty),empty,empty,width,height)['failures']
    assert hard_cutout_lighting(baseline,b'',mask,mask,width,height)['failures']


def test_probe_specimen_framing() -> None:
    from renderer_pbr_probe_parity import specimen_bounds, specimen_patch, metrics
    report={'fixture':{'cameras':{'sampling':[0,-1100,380,0,90,0]}},'probeProfile':{}}
    def spawn(origin):
        report['probeProfile']['specimen']={'commands':[
            f'spawn func_static name probe_specimen model "sphere" origin "{origin}" solid 0']}
    spawn('0 -700 380')
    assert specimen_bounds(report,'specimen')==(608,368,673,433)
    spawn('60 -700 420')
    bounds=specimen_bounds(report,'specimen')
    assert bounds==(688,315,753,380), 'the shading patch must follow the translated sphere'
    baseline=bytes(1280*800*3)
    wrong=bytearray(baseline); wrong[(347*1280+720)*3]=3
    assert metrics(specimen_patch(baseline,bounds),specimen_patch(wrong,bounds))['maximumError']==3
    for origin in ('0 -1200 380','nan -700 380','0 -700','10000 -700 380','0 -600 380'):
        spawn(origin)
        try: specimen_bounds(report,'specimen')
        except ValueError: pass
        else: raise AssertionError('invalid framing was accepted: '+origin)
    spawn('60 -700 420')
    report['probeProfile']['specimen']['commands']*=2
    try: specimen_bounds(report,'specimen')
    except ValueError: pass
    else: raise AssertionError('ambiguous specimen was accepted')


def main() -> int:
    test_material_data_and_geometry()
    test_vulkan_backend_evidence()
    test_ibl_proof_gates()
    test_ibl_coverage_lighting()
    test_probe_hard_cutout_lighting()
    test_probe_specimen_framing()
    temporary=runner.fixture.validate_runtime_root(ROOT/'.tmp/pbr-laboratory-tests')
    temporary.mkdir(parents=True,exist_ok=True)
    # No links are created by this test. Its known temporary subtree contains
    # only generated files, and TemporaryDirectory removes it on completion.
    with tempfile.TemporaryDirectory(dir=temporary) as name:
        test_proof_rejects_fallback_and_missing_channels(Path(name))
        test_differential_proof(Path(name))
        test_classic_float_reference(Path(name))
        test_classic_display_shoulder(Path(name))
        test_native_msaa_rounding(Path(name))
        test_vulkan_direct_evidence(Path(name))
        test_vulkan_msaa_coverage_evidence(Path(name))
        test_bounded_console_scripts(Path(name))
        test_ibl_parity_provenance(Path(name))
    print('pbr_laboratory_fixture: ok (24 stations, geometry, channels, coverage, proof rejection)')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
