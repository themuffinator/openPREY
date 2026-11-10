"""Exercise fully back-facing classic geometry without losing the native receiver."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/tests'))
import renderer_pbr_laboratory as lab
lab.BASE.update(r_lightAllBackFaces='0', r_usePreciseTriangleInteractions='0')

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runtime-root', type=Path, required=True)
parser.add_argument('--output-dir', type=Path, required=True)
parser.add_argument('--basepath', type=Path, required=True)
parser.add_argument('--backend', choices=('gl','vk'), required=True)
parser.add_argument('--samples', type=int, choices=(0,4), default=0)
parser.add_argument('--gl-native', action='store_true', help='OpenGL with the classic light loop owning PBR (draw_pbr.cpp)')
parser.add_argument('--production', action='store_true', help='Vulkan with the laboratory linear scene off: every PBR draw composes into the display-referred frame, as shipped')
parser.add_argument('--timeout', type=int, default=600)
args = parser.parse_args()
source_hash = lab.digest(Path(__file__))
manifest = json.loads((args.runtime_root/'pbr-lab.json').read_text())
if 'baseoq4/models/openq4/pbr_lab/backface_receiver.ase' not in manifest['sha256']:
    parser.error('prepare or update the PBR laboratory fixture to include the backface receiver')
profile = {}

def add(name, material='baked_normal_xyz', origin='-120 -690 540', pbr=True,
        all_faces=False, radius='1000 1000 1000', precise=False):
    name = 'backface-'+name
    commands = ['g_stopTime 0']
    if not profile:
        commands += [f'script "${s["name"]}.hide()"' for s in manifest['stations']]
        commands += [f'script "${s}.Off()"' for s in ('key','blue_fill','warm_fill','lab_projector')]
        commands += ['script "$probe_warm.remove(); $probe_cool.remove()"']
    else:
        commands += ['script "$backface_specimen.remove(); $backface_light.remove()"']
    commands += ['wait 3', f'spawn light name backface_light origin "{origin}" angle 0 light_radius "{radius}" _color "1 1 1" noshadows 1',
                 f'spawn func_static name backface_specimen model "models/openq4/pbr_lab/backface_receiver.ase" shader "{lab.lab.PREFIX}/{material}" origin "0 -700 380" angle 0 solid 0',
                 'wait 30','g_stopTime 1']
    settings = {'r_pbrIBL':'0', 'r_rendererReflectionProbes':'0', 'r_pbrMaterials':str(int(pbr)),
                'r_pbrDebug':'0', 'r_multiSamples':str(args.samples),
                'r_lightAllBackFaces':str(int(all_faces)), 'r_usePreciseTriangleInteractions':str(int(precise))}
    lab.CASES[name] = settings
    lab.CASE_COMMANDS[name] = commands
    lab.CASE_CAMERAS[name] = 'sampling'
    if not pbr:
        lab.LEGACY_CASES.add(name)
    profile[name] = {'settings':settings, 'commands':commands}

add('front-flat', material='data_scalar', origin='-120 -1000 540')
add('front-normal', origin='-120 -1000 540')
add('normal')
add('flat', material='data_scalar')
add('classic', pbr=False)
add('restored')
add('all-faces', all_faces=True)
add('precise', precise=True)
add('outside', radius='4 4 4')
add('outside-all-faces', radius='4 4 4', all_faces=True)
add('restored-final')

sys.argv = [__file__, '--runtime-root',str(args.runtime_root), '--output-dir',str(args.output_dir),
            '--basepath',str(args.basepath), '--backend',args.backend, '--camera','sampling',
            '--cases',','.join(profile), '--batch','--timeout',str(args.timeout)]
if args.backend == 'gl':
    sys.argv.append('--gl-debug')
if args.gl_native:
    if args.backend != 'gl':
        parser.error('--gl-native selects the classic OpenGL owner')
    sys.argv.append('--gl-native')
if args.production:
    sys.argv.append('--production')
code = lab.main()
path = args.output_dir/'report.json'
report = json.loads(path.read_text())
assert source_hash == lab.digest(Path(__file__))
shutil.copy2(Path(__file__), args.output_dir/'harness'/Path(__file__).name)
report['harnessSources'][Path(__file__).name] = source_hash
report.update(backfaceProfile=profile, backfaceHarnessSHA256=source_hash, requestedSamples=args.samples,
              qualification='Capture only; image and negative-control checks still required')
path.write_text(json.dumps(report,indent=2)+'\n')
print('Capture complete; run renderer_pbr_geometry_parity.py against the other backend to qualify these images.', flush=True)
raise SystemExit(code)
