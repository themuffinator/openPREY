"""Final measured clamp placement, exposure balance and render setup."""
import bpy, math
from scene_common import *
from remaster_scene import PARTS, ROOT


def apply():
    s=PARTS['scene'];clamps=bpy.data.collections.new('RM light receivers / forged clamps')
    for o in s.objects:
        if o.name.startswith(('RM sculpted clamp jaw','RM jaw raised forged spine')):
            for spl in o.data.splines:
                for p in spl.points:
                    if abs(p.co.x)>.1:p.co.x-=math.copysign(.55,p.co.x)
        if o.name.startswith(('RM clamp pivot socket','RM large bevelled pivot','RM pivot screw slot')):o.location.x=math.copysign(2.80,o.location.x)
        if o.name.startswith(('RM long cooling rail','RM clamp deep support')):
            o.location.x=math.copysign(3.30,o.location.x);o.scale.x=.85
        if o.name.startswith('RM clamp crossbar'):o.location.x=math.copysign(3.26,o.location.x);o.scale.x=.95
        if o.type in ['MESH','CURVE'] and o.name.startswith(('RM clamp','RM long cooling','RM sculpted clamp','RM jaw raised','RM large bevelled pivot','RM pivot screw')):clamps.objects.link(o)
    lamp=light('RM grazing silver on clamp edges','AREA',(-2,4,7),230,(.78,.86,1),5,C['RM 00 / Camera and studio'])
    lamp.light_linking.receiver_collection=clamps
    bpy.data.objects['RM broad wall bounce'].data.energy=410
    bpy.data.objects['RM crimson lens soft illumination'].data.energy=100
    for o in C['RM 03 / Iron insignia'].objects:
        key(o,'scale',[(1,(2.1,2.3,2.1)),(15,(1.90,2.12,1.9)),(31,(1.43,1.59,1.43)),(49,(1.08,1.12,1.08)),(68,(1,1,1)),(180,(1,1,1))])
    s.node_tree.nodes['RM restrained photographic halation'].inputs['Strength'].default_value=.28
    s.node_tree.nodes['RM restrained photographic halation'].inputs['Threshold'].default_value=.60
    # The held shot should have photographic edge bloom rather than a bright drawn line.
    s.node_tree.nodes['RM soft edge light spill'].inputs['Strength'].default_value=2.7
    s.render.use_persistent_data=True;s.cycles.samples=64;s.cycles.adaptive_threshold=.055
    s.cycles.use_denoising=True;s.cycles.denoising_input_passes='RGB_ALBEDO_NORMAL'
    s.cycles.denoising_use_gpu=s.cycles.device=='GPU'
    s.render.compositor_device='GPU' if s.cycles.device=='GPU' else 'CPU'
    s.render.resolution_percentage=100;s.frame_set(121)
    print('Final physical lighting and measured clamp placement applied')


def save(path=None):
    s=PARTS['scene'];s.frame_set(121);s.render.resolution_percentage=100;s.render.filepath='//renders/frame_'
    # Only the completed scene and its dependencies are written to the deliverable.
    # The first construction remains preserved in the task's temporary directory.
    path=str(path or ROOT/'quake4_trailer_logo.blend')
    doc=bpy.data.texts.get('README | QUAKE 4 REMASTER') or bpy.data.texts.new('README | QUAKE 4 REMASTER')
    doc.clear();doc.write((ROOT/'README.md').read_text(encoding='utf-8-sig'))
    bpy.data.libraries.write(path,{s,doc},path_remap='RELATIVE',fake_user=True,compress=True)
    print('Saved standalone remaster scene',path)
