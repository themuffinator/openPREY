"""Pack and map the authored enamel texture onto actual mechanical surfaces."""
from pathlib import Path
import bpy
from remaster_wear import shader
from scene_common import node_key
from remaster_materials import noise,ramp,mix,scaled

ROOT=Path(__file__).resolve().parent

def texture(nt,co,scale=.22):
    image=bpy.data.images.get('RM authored aged olive enamel')
    if not image:
        image=bpy.data.images.load(str(ROOT/'textures'/'aged_olive_enamel.png'));image.name='RM authored aged olive enamel';image.pack()
    transform=nt.nodes.new('ShaderNodeVectorMath');transform.operation='MULTIPLY_ADD';transform.inputs[1].default_value=(scale,scale,scale);transform.inputs[2].default_value=(.5,.5,0);nt.links.new(co,transform.inputs[0])
    node=nt.nodes.new('ShaderNodeTexImage');node.name='Authored enamel albedo';node.image=image;node.projection='BOX';node.projection_blend=.18;node.extension='REPEAT';nt.links.new(transform.outputs[0],node.inputs['Vector'])
    return node.outputs['Color']

def apply():
    for name,gain,size in [('RM | faceplate yellow olive',(1.30,1.70,1.85),.44),('RM | military olive wall',(.71,.88,.95),.25),('RM | shadowed olive armor',(.39,.48,.56),.29)]:
        mat,nt,bs,co=shader(name);tex=texture(nt,co,size)
        col=mix(nt,tex,gain,1,'MULTIPLY')
        grade=nt.nodes.new('ShaderNodeHueSaturation');grade.name='Reference paint chroma';grade.inputs['Saturation'].default_value=.84 if 'faceplate' in name else .75;grade.inputs['Value'].default_value=.90 if 'faceplate' in name else 1.08;nt.links.new(col,grade.inputs['Color']);col=grade.outputs[0]
        if 'faceplate' in name:
            geom=nt.nodes.new('ShaderNodeNewGeometry');sep=nt.nodes.new('ShaderNodeSeparateXYZ');nt.links.new(geom.outputs['Position'],sep.inputs[0])
            grad=nt.nodes.new('ShaderNodeMapRange');grad.inputs['From Min'].default_value=.6;grad.inputs['From Max'].default_value=1.90;grad.inputs['To Min'].default_value=1;grad.inputs['To Max'].default_value=.65;nt.links.new(sep.outputs['Y'],grad.inputs['Value']);col=mix(nt,col,grad.outputs[0],1,'MULTIPLY')
        if 'faceplate' not in name:
            stain=ramp(nt,noise(nt,co,.95,5,'Uneven accumulated oil and dirt'),[(.15,(.23,.25,.21)),(.81,(1,1,1))],'Broad original coating stains')
            col=mix(nt,col,stain,.65,'MULTIPLY')
            geom=nt.nodes.new('ShaderNodeNewGeometry');sep=nt.nodes.new('ShaderNodeSeparateXYZ');nt.links.new(geom.outputs['Position'],sep.inputs[0])
            grad=nt.nodes.new('ShaderNodeMapRange');grad.inputs['From Min'].default_value=1.8;grad.inputs['From Max'].default_value=5.2;grad.inputs['To Min'].default_value=1;grad.inputs['To Max'].default_value=.17;nt.links.new(sep.outputs['Y'],grad.inputs['Value'])
            col=mix(nt,col,grad.outputs[0],1,'MULTIPLY')
        nt.links.new(col,bs.inputs['Base Color']);bs.inputs['Metallic'].default_value=.22
        bw=nt.nodes.new('ShaderNodeRGBToBW');nt.links.new(tex,bw.inputs[0])
        r=ramp(nt,bw.outputs[0],[(.015,(.57,)*3),(.28,(.83,)*3)],'Exposed iron and enamel roughness');nt.links.new(r,bs.inputs['Roughness'])
        b=nt.nodes.new('ShaderNodeBump');b.inputs['Strength'].default_value=.37;b.inputs['Distance'].default_value=.026;nt.links.new(bw.outputs[0],b.inputs['Height']);nt.links.new(b.outputs[0],bs.inputs['Normal'])
    # The same material grain at a different scale describes pitted iron, without
    # reusing any trailer pixels as a projected image of the logo or machinery.
    mat,nt,bs,co=shader('RM | iron emblem');tex=texture(nt,co,.39)
    bw=nt.nodes.new('ShaderNodeRGBToBW');nt.links.new(tex,bw.inputs[0])
    col=ramp(nt,bw.outputs[0],[(.020,(.0003,.0005,.0007)),(.10,(.001,.0015,.002)),(.23,(.014,.017,.020)),(.48,(.031,.038,.045))],'Irregular dark iron pits')
    nt.links.new(col,bs.inputs['Base Color']);nt.links.new(col,bs.inputs['Emission Color']);bs.inputs['Emission Strength'].default_value=.15;bs.inputs['Metallic'].default_value=.16;bs.inputs['Roughness'].default_value=.93
    b=nt.nodes.new('ShaderNodeBump');b.inputs['Strength'].default_value=.7;b.inputs['Distance'].default_value=.06;nt.links.new(bw.outputs[0],b.inputs['Height']);nt.links.new(b.outputs[0],bs.inputs['Normal'])
    bpy.context.scene['texture_note']='Generated enamel albedo is mapped over physical solids and packed into this file. No trailer frame projection.'
    iris()
    print('Packed authored enamel texture and mapped paint/iron roughness and surface relief')


def iris():
    mat,nt,bs,co=shader('RM | fine radial iris');mat.node_tree.animation_data_clear()
    image=bpy.data.images.get('RM authored biological iris')
    if not image:
        image=bpy.data.images.load(str(ROOT/'textures'/'crimson_iris.png'));image.name='RM authored biological iris';image.pack()
    tc=next(n for n in nt.nodes if n.bl_idname=='ShaderNodeTexCoord')
    sep=nt.nodes.new('ShaderNodeSeparateXYZ');nt.links.new(tc.outputs['UV'],sep.inputs[0])
    def mathnode(op,a,b=None):
        n=nt.nodes.new('ShaderNodeMath');n.operation=op
        for sock,value in [(n.inputs[0],a),(n.inputs[1],b)]:
            if value is None:continue
            if isinstance(value,(int,float)):sock.default_value=value
            else:nt.links.new(value,sock)
        return n.outputs[0]
    angle=mathnode('MULTIPLY',sep.outputs['X'],6.283185307)
    radial=mathnode('ADD',mathnode('MULTIPLY',sep.outputs['Y'],.347),.143)
    x=mathnode('ADD',mathnode('MULTIPLY',mathnode('COSINE',angle),radial),.5)
    y=mathnode('ADD',mathnode('MULTIPLY',mathnode('SINE',angle),radial),.5)
    comb=nt.nodes.new('ShaderNodeCombineXYZ');nt.links.new(x,comb.inputs['X']);nt.links.new(y,comb.inputs['Y'])
    tex=nt.nodes.new('ShaderNodeTexImage');tex.name='Natural crypts and stromal fibers';tex.image=image;nt.links.new(comb.outputs[0],tex.inputs['Vector'])
    hue=nt.nodes.new('ShaderNodeHueSaturation');hue.name='Crimson settles to amber';hue.inputs['Saturation'].default_value=1.1;hue.inputs['Value'].default_value=.48;nt.links.new(tex.outputs['Color'],hue.inputs['Color'])
    node_key(hue.inputs['Hue'],[(1,.495),(38,.495),(61,.515),(108,.545),(180,.545)])
    nt.links.new(hue.outputs['Color'],bs.inputs['Base Color']);nt.links.new(hue.outputs['Color'],bs.inputs['Emission Color']);bs.inputs['Emission Strength'].default_value=.08
    bs.inputs['Metallic'].default_value=0;bs.inputs['Roughness'].default_value=.3;bs.inputs['Coat Weight'].default_value=.65;bs.inputs['Coat Roughness'].default_value=.07
    bw=nt.nodes.new('ShaderNodeRGBToBW');nt.links.new(tex.outputs['Color'],bw.inputs[0]);b=nt.nodes.new('ShaderNodeBump');b.inputs['Strength'].default_value=.28;b.inputs['Distance'].default_value=.002;nt.links.new(bw.outputs[0],b.inputs['Height']);nt.links.new(b.outputs[0],bs.inputs['Normal'])
    bpy.data.objects['RM crimson lens soft illumination'].data.color=(.90,.93,1)
