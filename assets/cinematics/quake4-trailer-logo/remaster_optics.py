"""Close-up corrections: iris fibers, chipped enamel and emblem recession."""
import bpy,math,random
from scene_common import *
from remaster_scene import PARTS
from remaster_materials import noise,ramp,mix


def apply():
    s=PARTS['scene'];r=random.Random(927)
    for o in list(s.objects):
        if o.name.startswith('RM paint flake at scored faceplate'):bpy.data.objects.remove(o,do_unlink=True)
        elif o.name.startswith('RM deep faceplate fracture'):o.data.bevel_depth*=.48
    # Small irregular islands follow coating wear, replacing conspicuous triangular flakes.
    col=C['RM 02 / Eye carrier and clamps']
    for i in range(115):
        a=r.uniform(0,math.tau);rr=r.uniform(1.0,2.03);x=rr*math.cos(a);y=rr*math.sin(a)*.89
        if i<65:x=r.gauss(.57,.14);y=r.uniform(.87,1.88)
        if (x/2.12)**2+(y/1.91)**2>1:continue
        w=r.uniform(.004,.019);h=r.uniform(.009,.064)
        pts=[]
        for j in range(11):
            angle=math.tau*j/11;v=r.uniform(.60,1.1);pts.append((x+w*math.cos(angle)*v,y+h*math.sin(angle)*v))
        solid_outline('RM irregular weathered paint island',[{'points':pts}],1.153,.001,M['RM | fracture scars'],col,.0005)
    # Different apparent scaling is visible between the close-up and final logo.
    for o in C['RM 03 / Iron insignia'].objects:
        key(o,'scale',[(1,(2.1,2.1,2.1)),(15,(1.90,1.90,1.90)),(31,(1.43,1.43,1.43)),(49,(1.08,1.08,1.08)),(68,(1,1,1)),(180,(1,1,1))])
    edge=M['RM | soft radioactive edge'].node_tree.nodes.get('Principled BSDF');edge.inputs['Base Color'].default_value=(.11,.14,.018,1)
    edge.inputs['Emission Color'].default_value=(.24,.30,.022,1)
    iron=M['RM | iron emblem'].node_tree.nodes['Pitted blue-black iron'].color_ramp
    iron.elements[0].color=(.001,.002,.003,1);iron.elements[1].color=(.017,.022,.024,1)
    # Remove the enormous softbox reflections from the ocular close-up.
    receivers=bpy.data.collections.new('RM light receivers / mechanical surfaces')
    for o in s.objects:
        if o.type in ['MESH','CURVE'] and o.name not in C['RM 06 / Optics'].objects and o.name not in C['RM 04 / Silver letterforms'].objects:receivers.objects.link(o)
    for name in ['RM broad cold overhead reflection','RM soft lower reflected light','RM faded olive central light']:
        bpy.data.objects[name].light_linking.receiver_collection=receivers
    glint=bpy.data.objects['RM eye lens glint'];glint.light_linking.receiver_collection=C['RM 06 / Optics'];glint.data.energy=85;glint.data.size=.45;glint.data.size_y=.25
    pupil=PARTS['pupil'];pupil.animation_data_clear();pupil.scale=(.197,.197,.006);pupil.location.z=1.52
    bs=M['RM | pupil'].node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.20;bs.inputs['Specular IOR Level'].default_value=.16
    bs=M['RM | wet crimson lens'].node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.20;bs.inputs['Coat Weight'].default_value=.60;bs.inputs['Coat Roughness'].default_value=.10
    bs.inputs['Emission Color'].default_value=(.09,.0005,.001,1);bs.inputs['Emission Strength'].default_value=.13
    iris=M['RM | fine radial iris'];nt=iris.node_tree
    for n in nt.nodes:
        if n.bl_idname=='ShaderNodeVectorMath' and n.operation=='MULTIPLY':n.inputs[1].default_value=(52,.25,1)
    colors=[(.006,.0001,.0002,1),(.060,.001,.0005,1),(.29,.013,.001,1),(.65,.09,.008,1)]
    for e,color in zip(nt.nodes['Crimson and amber iris fibers'].color_ramp.elements,colors):e.color=color
    # Broad dark crypts sit over the fine radial striations.
    bs=nt.nodes.get('Principled BSDF');tex=next(n for n in nt.nodes if n.bl_idname=='ShaderNodeTexCoord')
    shade=ramp(nt,noise(nt,tex.outputs['UV'],15,3,'Irregular dark iris crypts'),[(.20,(.15,.05,.02)),(.7,(1,1,1))],'Broken iris crypts')
    old=bs.inputs['Base Color'].links[0].from_socket;col=mix(nt,old,shade,.64,'MULTIPLY');nt.links.new(col,bs.inputs['Base Color']);nt.links.new(col,bs.inputs['Emission Color'])
    node_key(bs.inputs['Emission Strength'],[(1,.50),(50,.6),(121,.52),(180,.40)])
    # A single quiet reflection fills the near-black eye without introducing giant glare cards.
    eye_fill=light('RM crimson lens soft illumination','AREA',(0,.5,6.5),28,(1,.75,.55),3,C['RM 00 / Camera and studio'])
    eye_fill.light_linking.receiver_collection=C['RM 06 / Optics'];eye_fill.data.specular_factor=0
    s.frame_set(121)
    print('Close-up surfaces and differential emblem animation corrected')
