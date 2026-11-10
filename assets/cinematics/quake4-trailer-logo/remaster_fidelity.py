"""Final surface and silhouette adjustments after reference comparisons."""
import bpy
from scene_common import *
from remaster_scene import PARTS
from remaster_materials import noise,ramp,mix


def apply():
    s=PARTS['scene']
    for o in s.objects:
        if o.name.startswith('RM chamfered solid olive faceplate'):o.scale.y=.89
        if o.name.startswith('RM rounded teal socket collar'):
            o.data.materials.append(M['RM | faceplate yellow olive'])
            for p in o.data.polygons:
                if p.center.y<0:p.material_index=1
        if o.name.startswith(('RM inset service door','RM long plate join')):
            o.data.materials.clear();o.data.materials.append(M['RM | military olive wall'])
    for o in PARTS['letters']:o.data.bevel_depth=.023;o.data.bevel_resolution=1;o.data.extrude=.11
    front=bpy.data.objects.get('RM white title reflection card');front.data.energy=260;front.data.size_y=1.1
    M['RM | silver title'].node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.22
    # A lower diffuse fill exposes the broad background panels without flattening the eye.
    wallfill=light('RM broad wall bounce','AREA',(-3,1.8,8),240,(.81,.88,.66),7,C['RM 00 / Camera and studio'])
    wallfill.light_linking.receiver_collection=C['RM 01 / Segmented bulkhead']
    for name in ['RM | green diagnostic','RM | amber diagnostic']:
        M[name].node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value=.045
    for name in ['RM | military olive wall','RM | faceplate yellow olive','RM | shadowed olive armor']:
        nt=M[name].node_tree;bs=nt.nodes.get('Principled BSDF')
        nt.nodes['Islands of chipped coating'].inputs['Scale'].default_value=20
        # Broad dirt clouds break up the regular fine flecks.
        coord=next(n for n in nt.nodes if n.bl_idname=='ShaderNodeTexCoord').outputs['Object']
        broad=noise(nt,coord,3.2,4,'Accumulated coarse grime')
        dirt=ramp(nt,broad,[(.22,(.12,.14,.09)),(.64,(1,1,1))],'Large irregular dirt patches')
        original=bs.inputs['Base Color'].links[0].from_socket
        col=mix(nt,original,dirt,.62,'MULTIPLY');nt.links.new(col,bs.inputs['Base Color'])
        for n in nt.nodes:
            if n.bl_idname=='ShaderNodeMixRGB' and n.blend_type=='MULTIPLY' and abs(n.inputs[0].default_value-.42)<.01:n.inputs[0].default_value=.20
    mat=M['RM | iron emblem'];nt=mat.node_tree;bs=nt.nodes.get('Principled BSDF')
    coord=next(n for n in nt.nodes if n.bl_idname=='ShaderNodeTexCoord').outputs['Object']
    col=ramp(nt,noise(nt,coord,58,4,'Dense granular forged iron'),[(.18,(.003,.005,.006)),(.76,(.048,.053,.056))],'Pitted blue-black iron')
    nt.links.new(col,bs.inputs['Base Color']);bs.inputs['Metallic'].default_value=.35;bs.inputs['Roughness'].default_value=.79
    nt.links.new(col,bs.inputs['Emission Color']);bs.inputs['Emission Strength'].default_value=.10
    # Emission gets a soft optical halo independently of the silver highlights.
    s.view_layers[0].use_pass_emit=True
    nt=s.node_tree;rl=next(n for n in nt.nodes if n.bl_idname=='CompositorNodeRLayers');original=nt.nodes['RM restrained photographic halation']
    halo=nt.nodes.new('CompositorNodeGlare');halo.name='RM soft edge light spill';halo.glare_type='FOG_GLOW';halo.quality='HIGH';halo.inputs['Threshold'].default_value=.025;halo.inputs['Strength'].default_value=2.2;halo.inputs['Size'].default_value=.68
    nt.links.new(rl.outputs['Emit'],halo.inputs['Image'])
    add=nt.nodes.new('CompositorNodeMixRGB');add.name='RM gentle irradiated edge aura';add.blend_type='ADD';add.inputs[0].default_value=.72
    nt.links.new(rl.outputs['Image'],add.inputs[1]);nt.links.new(halo.outputs['Glare'],add.inputs[2]);nt.links.new(add.outputs[0],original.inputs['Image'])
    s.frame_set(121)
    print('Refined chamfered silver, oval faceplate, layered grime and soft emblem aura')
