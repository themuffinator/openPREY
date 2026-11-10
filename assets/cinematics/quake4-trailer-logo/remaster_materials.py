"""Layered, physically shaded materials for the cinematic reconstruction."""
import bpy
from scene_common import material, M


def ramp(nt, source, values, name):
    n=nt.nodes.new('ShaderNodeValToRGB'); n.name=name
    for e in list(n.color_ramp.elements)[2:]: n.color_ramp.elements.remove(e)
    for i,(p,c) in enumerate(values):
        e=n.color_ramp.elements[i] if i<2 else n.color_ramp.elements.new(p)
        e.position=p; e.color=(*c,1)
    nt.links.new(source,n.inputs[0])
    return n.outputs[0]


def noise(nt, vector, scale, detail=3, name='Noise'):
    n=nt.nodes.new('ShaderNodeTexNoise'); n.name=name
    n.inputs['Scale'].default_value=scale; n.inputs['Detail'].default_value=detail
    n.inputs['Roughness'].default_value=.72
    nt.links.new(vector,n.inputs['Vector'])
    return n.outputs['Fac']


def mix(nt,a,b,fac,mode='MIX'):
    n=nt.nodes.new('ShaderNodeMixRGB');n.blend_type=mode
    if isinstance(fac,(int,float)):n.inputs[0].default_value=fac
    else:nt.links.new(fac,n.inputs[0])
    for sock,val in [(n.inputs[1],a),(n.inputs[2],b)]:
        if isinstance(val,tuple):sock.default_value=(*val,1)
        else:nt.links.new(val,sock)
    return n.outputs[0]


def scaled(nt,vec,xyz):
    n=nt.nodes.new('ShaderNodeVectorMath');n.operation='MULTIPLY'
    n.inputs[1].default_value=xyz;nt.links.new(vec,n.inputs[0]);return n.outputs[0]


def paint(name,low,high,metal=.45,rough=.58,chip=.57):
    mat=material(name,high,metal,rough)
    nt=mat.node_tree; n,l=nt.nodes,nt.links;bs=n.get('Principled BSDF')
    coord=n.new('ShaderNodeTexCoord').outputs['Object']
    broad=noise(nt,coord,1.5,4,'Large oxidation clouds')
    col=ramp(nt,broad,[(.18,low),(.80,high)],'Faded olive paint')
    scratchcoord=scaled(nt,coord,(38,.42,15))
    streak=noise(nt,scratchcoord,3.0,2,'Vertical rubbed metal and rain marks')
    stain=ramp(nt,streak,[(.22,(.18,.17,.13)),(.66,(1,1,1))],'Long surface scuffs')
    col=mix(nt,col,stain,.42,'MULTIPLY')
    mid=noise(nt,coord,10.2,3,'Islands of chipped coating')
    chipmask=ramp(nt,mid,[(chip,(0,0,0)),(chip+.075,(1,1,1))],'Paint delamination')
    substrate=ramp(nt,noise(nt,coord,43,2),[(.23,(.012,.014,.009)),(.78,(.073,.080,.047))],'Oxidized substrate')
    col=mix(nt,col,substrate,chipmask)
    l.new(col,bs.inputs['Base Color'])
    roughcol=ramp(nt,broad,[(.15,(rough-.10,)*3),(.8,(rough+.17,)*3)],'Uneven surface roughness')
    l.new(roughcol,bs.inputs['Roughness'])
    micro=noise(nt,coord,135,2,'Fine sandblasted surface')
    b1=n.new('ShaderNodeBump');b1.inputs['Strength'].default_value=.23;b1.inputs['Distance'].default_value=.009
    l.new(micro,b1.inputs['Height'])
    b2=n.new('ShaderNodeBump');b2.inputs['Strength'].default_value=.31;b2.inputs['Distance'].default_value=.014
    l.new(chipmask,b2.inputs['Height']);l.new(b1.outputs[0],b2.inputs['Normal']);l.new(b2.outputs[0],bs.inputs['Normal'])
    return mat


def palette():
    paint('RM | military olive wall',(.055,.067,.023),(.235,.265,.080),.42,.67,.56)
    paint('RM | faceplate yellow olive',(.17,.20,.035),(.40,.45,.095),.46,.57,.57)
    paint('RM | shadowed olive armor',(.024,.033,.018),(.125,.146,.071),.56,.60,.61)
    paint('RM | forged clamp steel',(.019,.025,.028),(.078,.093,.105),.78,.42,.66)
    paint('RM | iron emblem',(.002,.003,.003),(.013,.017,.016),.58,.76,.63)
    paint('RM | oxidized teal gasket',(.008,.025,.023),(.036,.115,.103),.56,.46,.70)
    material('RM | steel exposed edges',(.12,.14,.13),.86,.35)
    material('RM | deep recess',(.002,.003,.002),.35,.84)
    material('RM | fracture scars',(.018,.021,.009),.40,.78)
    material('RM | technical etchings',(.24,.28,.12),.45,.57,(.12,.15,.044),.08)
    material('RM | silver title',(.83,.85,.85),.93,.17)
    silver=M['RM | silver title'];bs=silver.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Coat Weight'].default_value=.3;bs.inputs['Coat Roughness'].default_value=.11
    material('RM | soft radioactive edge',(.23,.28,.028),.25,.5,(.38,.49,.045),.85)
    # The upper horns disappear gently into the dark plate, as in the trailer.
    mat=M['RM | soft radioactive edge'];nt=mat.node_tree
    geom=nt.nodes.new('ShaderNodeNewGeometry');sep=nt.nodes.new('ShaderNodeSeparateXYZ');nt.links.new(geom.outputs['Position'],sep.inputs[0])
    mp=nt.nodes.new('ShaderNodeMapRange');mp.inputs['From Min'].default_value=-1.6;mp.inputs['From Max'].default_value=2.6
    mp.inputs['To Min'].default_value=1.0;mp.inputs['To Max'].default_value=.035;nt.links.new(sep.outputs['Y'],mp.inputs['Value'])
    nt.links.new(mp.outputs['Result'],nt.nodes.get('Principled BSDF').inputs['Emission Strength'])
    material('RM | green diagnostic',(.12,.22,.036),.4,.4,(.21,.45,.052),.38)
    material('RM | amber diagnostic',(.30,.15,.025),.4,.45,(.55,.27,.045),.38)
    material('RM | pupil',(.001,.0015,.002),0,.075)
    material('RM | flash',(.45,.8,1),0,.1,(.20,.65,1),0)
    # A glossy crimson sclera and an independently modeled fiber iris.
    red=material('RM | wet crimson lens',(.22,.006,.008),.15,.115)
    nt=red.node_tree;bs=nt.nodes.get('Principled BSDF');coord=nt.nodes.new('ShaderNodeTexCoord').outputs['Object']
    col=ramp(nt,noise(nt,coord,16,5),[(.22,(.034,.0007,.002)),(.8,(.28,.015,.019))],'Deep red optical tissue')
    nt.links.new(col,bs.inputs['Base Color']);bs.inputs['Coat Weight'].default_value=.9;bs.inputs['Coat Roughness'].default_value=.065
    iris=material('RM | fine radial iris',(.38,.016,.003),.1,.22)
    nt=iris.node_tree;n,l=nt.nodes,nt.links;bs=n.get('Principled BSDF')
    tex=n.new('ShaderNodeTexCoord');sep=n.new('ShaderNodeSeparateXYZ');l.new(tex.outputs['UV'],sep.inputs[0])
    comb=n.new('ShaderNodeCombineXYZ');l.new(sep.outputs['X'],comb.inputs['X']);l.new(sep.outputs['Y'],comb.inputs['Y'])
    detail=noise(nt,scaled(nt,comb.outputs[0],(160,2.8,1)),3,3,'Hundreds of irregular radial fibers')
    col=ramp(nt,detail,[(.2,(.022,.0004,.001)),(.42,(.18,.004,.001)),(.62,(.56,.042,.006)),(.81,(.85,.17,.022))],'Crimson and amber iris fibers')
    limbus=ramp(nt,sep.outputs['Y'],[(0,(.10,.07,.06)),(.18,(1,1,1)),(.8,(1,1,1)),(1,(.025,.016,.015))],'Iris dark inner and outer margins')
    col=mix(nt,col,limbus,1,'MULTIPLY');l.new(col,bs.inputs['Base Color']);l.new(col,bs.inputs['Emission Color'])
    bs.inputs['Emission Strength'].default_value=.23;bs.inputs['Coat Weight'].default_value=.9;bs.inputs['Coat Roughness'].default_value=.08
    b=n.new('ShaderNodeBump');b.inputs['Distance'].default_value=.006;b.inputs['Strength'].default_value=.25;l.new(detail,b.inputs['Height']);l.new(b.outputs[0],bs.inputs['Normal'])
    return M
