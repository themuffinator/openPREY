"""A narrow, tapered cyan anamorphic line during the two optical bursts."""
from scene_common import node_key
from remaster_scene import PARTS


def apply():
    s=PARTS['scene'];nt=s.node_tree;n,l=nt.nodes,nt.links
    ellipse=n.new('CompositorNodeEllipseMask');ellipse.name='RM anamorphic lens streak profile';ellipse.inputs['Size'].default_value=(1.15,.0018)
    blur=n.new('CompositorNodeBlur');blur.filter_type='GAUSS';blur.inputs['Size'].default_value=(180,2);l.new(ellipse.outputs[0],blur.inputs[0])
    color=n.new('CompositorNodeMixRGB');color.blend_type='MULTIPLY';color.inputs[0].default_value=1;color.inputs[2].default_value=(.12,.56,1,1);l.new(blur.outputs[0],color.inputs[1])
    vig=nt.nodes['RM optical vignette'];original=vig.inputs[1].links[0].from_socket
    add=n.new('CompositorNodeMixRGB');add.name='RM narrow cyan optical streak';add.blend_type='ADD';l.new(original,add.inputs[1]);l.new(color.outputs[0],add.inputs[2]);l.new(add.outputs[0],vig.inputs[1])
    node_key(add.inputs[0],[(1,0),(9,.04),(16,1.2),(21,.12),(27,0),(39,0),(46,1.0),(51,.15),(57,0),(180,0)])
    s.frame_set(121)
