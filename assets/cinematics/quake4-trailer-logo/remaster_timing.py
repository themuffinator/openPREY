"""Final timing measured against the trailer's two optical flashes."""
import bpy,math
from scene_common import *
from remaster_scene import PARTS


def shift_keys(owner,offset,path=None):
    action=owner.animation_data.action if owner.animation_data else None
    if not action:return
    for fc in action.fcurves:
        if path is not None and fc.data_path!=path:continue
        for p in fc.keyframe_points:
            f=p.co.x
            delta=0 if f>=179 else (offset(f) if callable(offset) else offset)
            p.co.x+=delta;p.handle_left.x+=delta;p.handle_right.x+=delta
        fc.update()


def apply():
    s=PARTS['scene']
    # The first burst peaks at 120.5 s, the title burst at 121.5 s.
    timing=lambda f:7 if f<30 else 4
    shift_keys(bpy.data.objects['RM blue flash illumination'].data,timing)
    shift_keys(M['RM | flash'].node_tree,timing)
    shift_keys(PARTS['flash'],timing)
    strength=s.node_tree.nodes['RM horizontal anamorphic transient'].inputs['Strength']
    shift_keys(s.node_tree,timing,strength.path_from_id('default_value'))
    key(bpy.data.objects['RM blue flash illumination'].data,'energy',[(16,700),(46,950)])
    node_key(M['RM | flash'].node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'],[(16,180),(46,360)])
    streak=s.node_tree.nodes['RM horizontal anamorphic transient']
    streak.inputs['Iterations'].default_value=5
    streak.inputs['Fade'].default_value=.965
    streak.inputs['Color Modulation'].default_value=0
    streak.inputs['Tint'].default_value=(.35,.76,1,1)
    shift_keys(PARTS['title'],4)
    for letter in PARTS['letters']:shift_keys(letter,4)
    key(s.camera,'location',[(1,(0,0,5)),(9,(0,0,9)),(16,(0,0,12.3)),(24,(0,0,14.7)),(31,(0,0,16.3)),(43,(0,0,21)),(61,(0,0,24.2)),(91,(0,0,26.3)),(121,(0,0,28)),(151,(0,0,29.6)),(180,(0,0,31.1))])
    edge=M['RM | soft radioactive edge'];nt=edge.node_tree;bs=nt.nodes.get('Principled BSDF')
    source=bs.inputs['Emission Strength'].links[0].from_socket
    mul=nt.nodes.new('ShaderNodeMath');mul.name='Emblem light appears with title';mul.operation='MULTIPLY';nt.links.new(source,mul.inputs[0]);nt.links.new(mul.outputs[0],bs.inputs['Emission Strength'])
    node_key(mul.inputs[1],[(1,0),(31,.025),(40,.20),(46,.75),(60,.65),(180,.65)])
    node_key(bs.inputs['Base Color'],[(1,(.005,.007,.003,1)),(31,(.005,.007,.003,1)),(46,(.065,.082,.012,1)),(180,(.065,.082,.012,1))])
    wall=bpy.data.objects['RM broad wall bounce'];wall.location=(0,.7,9);aim(wall,(0,0,0));wall.data.type='SPOT';wall.data.energy=600;wall.data.spot_size=1.20;wall.data.spot_blend=.88;wall.data.shadow_soft_size=1.2
    # Optical zoom blur appears only during the two fast reveals.
    nt=s.node_tree;blur=nt.nodes.get('RM transient radial lens smear') or nt.nodes.new('CompositorNodeDBlur');blur.name='RM transient radial lens smear'
    blur.inputs['Samples'].default_value=32;blur.inputs['Center'].default_value=(.5,.5)
    node_key(blur.inputs['Scale'],[(1,1),(9,1.04),(16,1.60),(24,1),(35,1),(40,1.03),(46,1.25),(54,1),(180,1)])
    glow=nt.nodes['RM restrained photographic halation'];image=glow.inputs['Image'].links[0].from_socket
    nt.links.new(image,blur.inputs['Image']);nt.links.new(blur.outputs[0],glow.inputs['Image'])
    for marker in s.timeline_markers:
        if marker.name=='White-blue optical flash':marker.frame=16
        elif marker.name=='Title reveal flash':marker.frame=46
        elif marker.name=='Silver letterforms rush in':marker.frame=39
        elif marker.name=='Wordmark settles':marker.frame=62
    s.frame_set(121)
    print('Matched both flash peaks and the darker opening emblem')
