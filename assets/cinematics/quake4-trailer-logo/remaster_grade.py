"""Reference-matched exposure, optical highlights and surface refinements."""
import bpy
from scene_common import M,C,key,node_key
from remaster_scene import PARTS


def apply():
    s=PARTS['scene']
    lights={o.name:o for o in s.objects if o.type=='LIGHT'}
    lights['RM broad cold overhead reflection'].data.energy=245
    lights['RM soft lower reflected light'].data.energy=70
    lights['RM faded olive central light'].data.energy=130
    lights['RM faded olive central light'].data.color=(.90,1,.44)
    lights['RM eye lens glint'].data.energy=35
    front=lights['RM white title reflection card'];front.data.energy=520;front.data.size_y=2.2
    front.light_linking.receiver_collection=C['RM 04 / Silver letterforms']
    s.world.node_tree.nodes['Background'].inputs[1].default_value=.075
    bs=M['RM | silver title'].node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.24
    # Streaks belong to the brief flash, never the held silver title.
    streak=s.node_tree.nodes['RM horizontal anamorphic transient']
    node_key(streak.inputs['Strength'],[(1,0),(9,.72),(16,.05),(21,0),(36,0),(42,.75),(48,.10),(55,0),(180,0)])
    s.node_tree.nodes['RM restrained photographic halation'].inputs['Strength'].default_value=.19
    s.node_tree.nodes['RM restrained photographic halation'].inputs['Threshold'].default_value=.7
    # Keep the outer wall visible but let it recede into the source's dark periphery.
    s.node_tree.nodes['RM optical vignette'].inputs[0].default_value=.86
    s.view_settings.look='AgX - Medium High Contrast'
    s.frame_set(121)
    print('Applied controlled reflections and reference exposure')
