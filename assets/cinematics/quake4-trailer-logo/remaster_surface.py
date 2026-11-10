"""Broad structural braces, restrained surface wear and the red-to-amber eye."""
import bpy,math
from scene_common import *
from remaster_scene import PARTS


def apply():
    s=PARTS['scene']
    for name in ['RM | military olive wall','RM | faceplate yellow olive','RM | shadowed olive armor']:
        nt=M[name].node_tree;chip=nt.nodes['Paint delamination'].color_ramp
        chip.elements[0].position=.60;chip.elements[1].position=.72;chip.elements[1].color=(.70,.70,.70,1)
    col=C['RM 01 / Segmented bulkhead']
    receivers=bpy.data.collections['RM light receivers / mechanical surfaces']
    for side in [-1,1]:
        o=box('RM lower diagonal armor brace',(side*3.45,-3.84,.27),(.86,4.85,.22),M['RM | military olive wall'],col,.055)
        o.rotation_euler.z=side*math.radians(45);receivers.objects.link(o)
        rib=box('RM brace inset structural seam',(side*3.81,-3.48,.295),(.052,4.6,.09),M['RM | shadowed olive armor'],col,.01)
        rib.rotation_euler.z=side*math.radians(45);receivers.objects.link(rib)
    red=M['RM | wet crimson lens'].node_tree.nodes['Deep red optical tissue'].color_ramp
    for e in red.elements:e.keyframe_insert('color',frame=1);e.keyframe_insert('color',frame=48)
    red.elements[0].color=(.025,.006,.001,1);red.elements[1].color=(.24,.066,.009,1)
    for e in red.elements:e.keyframe_insert('color',frame=108);e.keyframe_insert('color',frame=180)
    iris=M['RM | fine radial iris'].node_tree.nodes['Crimson and amber iris fibers'].color_ramp
    for e in iris.elements:e.keyframe_insert('color',frame=1);e.keyframe_insert('color',frame=48)
    amber=[(.005,.0004,.0001,1),(.055,.01,.0006,1),(.30,.065,.003,1),(.63,.24,.021,1)]
    for e,c in zip(iris.elements,amber):e.color=c;e.keyframe_insert('color',frame=108);e.keyframe_insert('color',frame=180)
    bs=M['RM | wet crimson lens'].node_tree.nodes.get('Principled BSDF')
    node_key(bs.inputs['Emission Color'],[(1,(.09,.0005,.001,1)),(48,(.09,.0005,.001,1)),(108,(.07,.019,.001,1)),(180,(.07,.019,.001,1))])
    s.frame_set(121)
    print('Added broad lower braces and matching eye color transition')
