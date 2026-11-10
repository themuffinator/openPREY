"""Lighting, panel detail and nonuniform surface edges for the revised assembly."""
import bpy,math
from mathutils import Vector
from scene_common import C,M,box,cylinder,tube,material,light,node_key,aim

def apply():
    s=bpy.context.scene;col=bpy.data.collections['RM 01 / Segmented bulkhead']
    s.frame_set(121)
    for ob in list(s.objects):
        if ob.name.startswith(('RM lower status','RM low machinery bounce','RM recessed left inspection')):bpy.data.objects.remove(ob,do_unlink=True)
    root=bpy.data.objects.get('RM BULKHEAD / measured armored housing')
    cutter=cylinder('RM inspection bore tool',.925,2,(-5.23,1.93,-.2),None,col,128,0)
    for ob in list(col.objects):
        if ob.type!='MESH' or ob is cutter or 'armor bed' in ob.name:continue
        if not any(word in ob.name for word in ['upper diagonal','large outer side cheek','upper swept']):continue
        bounds=[ob.matrix_world@Vector(v) for v in ob.bound_box]
        if not (min(v.x for v in bounds)<-4.30 and max(v.x for v in bounds)>-6.16 and min(v.y for v in bounds)<2.85 and max(v.y for v in bounds)>1.0):continue
        mod=ob.modifiers.new('Recessed inspection bore','BOOLEAN');mod.operation='DIFFERENCE';mod.object=cutter
        bpy.context.view_layer.objects.active=ob;bpy.ops.object.modifier_move_to_index(modifier=mod.name,index=0);bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
    portmat=bpy.data.materials.get('RM | dark painted inspection cover')
    if not portmat:
        portmat=M['RM | shadowed olive armor'].copy();portmat.name='RM | dark painted inspection cover'
        nt=portmat.node_tree;bs=nt.nodes.get('Principled BSDF');source=bs.inputs['Base Color'].links[0].from_socket
        mul=nt.nodes.new('ShaderNodeMixRGB');mul.blend_type='MULTIPLY';mul.inputs[0].default_value=1;mul.inputs[2].default_value=(.24,.24,.24,1);nt.links.new(source,mul.inputs[1]);nt.links.new(mul.outputs[0],bs.inputs['Base Color'])
    cylinder('RM recessed left inspection port',.923,.13,(-5.23,1.93,-.155),portmat,col,128,.025,root)
    green=bpy.data.materials.get('RM | lower instrument green') or material('RM | lower instrument green',(.008,.048,.013),.15,.54,(.06,.39,.095),1.1)
    orange=bpy.data.materials.get('RM | lower instrument amber') or material('RM | lower instrument amber',(.10,.021,.002),.22,.6,(.18,.027,.002),.23)
    green.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value=.13
    for x,y,w,h,mat in [(-1.04,-3.55,.10,.19,green),(-1.30,-4.72,.057,.21,orange),(1.69,-4.81,.036,.15,green)]:
        box('RM lower status recessed socket',(x,y,.14),(w+.09,h+.11,.15),M['RM | deep recess'],col,.025)
        box('RM lower status indicator',(x,y,.224),(w,h,.021),mat,col,.013)
    lamp=light('RM low machinery bounce','AREA',(-.4,-2.6,6.0),145,(.80,.92,.55),4.5,bpy.data.collections['RM 00 / Camera and studio'],target=(0,-3.5,0))
    lamp.light_linking.receiver_collection=col
    # The source's overlay circuits emerge during the title reveal.
    mat=bpy.data.materials['RM | technical etchings'];nt=mat.node_tree
    out=next(n for n in nt.nodes if n.bl_idname=='ShaderNodeOutputMaterial')
    if not nt.nodes.get('RM circuit reveal'):
        old=out.inputs['Surface'].links[0].from_socket;transparent=nt.nodes.new('ShaderNodeBsdfTransparent');mix=nt.nodes.new('ShaderNodeMixShader');mix.name='RM circuit reveal'
        nt.links.new(transparent.outputs[0],mix.inputs[1]);nt.links.new(old,mix.inputs[2]);nt.links.new(mix.outputs[0],out.inputs['Surface'])
        node_key(mix.inputs[0],[(1,0),(33,0),(43,.50),(65,1),(180,1)])
    # Fine actual edge irregularity prevents the forged emblem reading as a
    # perfectly smooth vector outline when the shot is rendered at 1080p.
    for ob in list(bpy.data.collections['RM 03 / Iron insignia'].objects):
        if ob.active_material and ob.active_material.name=='RM | iron emblem' and ob.type=='CURVE':
            bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.convert(target='MESH');ob=bpy.context.object
            rem=ob.modifiers.new('Fine forged surface tessellation','REMESH');rem.mode='VOXEL';rem.voxel_size=.023;rem.use_smooth_shade=True
            tex=bpy.data.textures.new('RM shallow iron edge pits',type='CLOUDS');tex.noise_scale=.051;tex.noise_depth=2
            dis=ob.modifiers.new('Submillimeter uneven forged edge','DISPLACE');dis.texture=tex;dis.texture_coords='LOCAL';dis.strength=.009;dis.mid_level=.51
    # Keep a sharp editable scene while rendering the fine pore detail reliably.
    s.cycles.samples=96;s.cycles.adaptive_threshold=.035;s.cycles.use_denoising=True
    s.render.use_persistent_data=True;s.cycles.denoising_use_gpu=s.cycles.device=='GPU';s.render.compositor_device='GPU' if s.cycles.device=='GPU' else 'CPU'
    s.render.resolution_percentage=100;s.frame_set(121)
    from remaster_mechanics import relink_lights
    relink_lights()
    print('Finalized mechanical lighting, status details and actual forged edge irregularity')
