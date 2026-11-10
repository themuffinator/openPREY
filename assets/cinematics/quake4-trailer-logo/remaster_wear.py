"""Material response and localized coating wear following the trailer reference."""
import bpy, math, random
from mathutils import Vector
from scene_common import C,M,material,tube
from remaster_materials import noise,ramp,mix,scaled
from remaster_mechanics import plate


def shader(name):
    mat=bpy.data.materials[name];nt=mat.node_tree;nt.nodes.clear()
    bs=nt.nodes.new('ShaderNodeBsdfPrincipled');out=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(bs.outputs['BSDF'],out.inputs['Surface'])
    tc=nt.nodes.new('ShaderNodeTexCoord');return mat,nt,bs,tc.outputs['Object']


def paint(name,low,high,metal=.24,rough=.7):
    mat,nt,bs,co=shader(name);n,l=nt.nodes,nt.links
    broad=noise(nt,co,1.1,5,'Uneven aged enamel pigmentation')
    pigment=ramp(nt,broad,[(.12,low),(.83,high)],'Faded coating color')
    # Directional abrasion breaks up the broad clouds; the peeling clusters are
    # stretched and interrupted, avoiding the old evenly distributed black dots.
    sc=noise(nt,scaled(nt,co,(21,.7,8)),2.3,3,'Dragged abrasive striations')
    scratch=ramp(nt,sc,[(.26,(.28,.30,.22)),(.53,(.85,.87,.78)),(.71,(1,1,1))],'Soft vertical grain')
    pigment=mix(nt,pigment,scratch,.47,'MULTIPLY')
    cluster=noise(nt,scaled(nt,co,(1.3,.62,1)),4.8,5,'Irregular islands of lifted enamel')
    crust=ramp(nt,cluster,[(.52,(0,0,0)),(.67,(1,1,1))],'Sparse connected coating failures')
    detail=noise(nt,scaled(nt,co,(3.1,1.1,1.5)),21,3,'Ragged chip boundaries')
    chips=ramp(nt,detail,[(.42,(0,0,0)),(.62,(1,1,1))],'Broken chip perimeter')
    mask=mix(nt,crust,chips,1,'MULTIPLY')
    oxide=ramp(nt,noise(nt,co,31,4),[(.17,(.018,.020,.012)),(.8,(.077,.079,.042))],'Dark metal beneath coating')
    col=mix(nt,pigment,oxide,mask)
    l.new(col,bs.inputs['Base Color']);bs.inputs['Metallic'].default_value=metal
    l.new(ramp(nt,broad,[(.1,(rough-.05,)*3),(.85,(min(.92,rough+.1),)*3)],'Paint roughness'),bs.inputs['Roughness'])
    fine=noise(nt,co,175,3,'Fine cast surface under paint')
    bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.35;bump.inputs['Distance'].default_value=.010;l.new(fine,bump.inputs['Height'])
    layer=n.new('ShaderNodeBump');layer.inputs['Strength'].default_value=.4;layer.inputs['Distance'].default_value=.019;l.new(mask,layer.inputs['Height']);l.new(bump.outputs[0],layer.inputs['Normal']);l.new(layer.outputs[0],bs.inputs['Normal'])
    mat.diffuse_color=(*high,1)


def metals():
    mat,nt,bs,co=shader('RM | forged clamp steel')
    col=ramp(nt,noise(nt,co,4.6,4),[(.12,(.036,.041,.047)),(.83,(.101,.113,.127))],'Oxidized gunmetal casting')
    grain=noise(nt,scaled(nt,co,(4,36,5)),3,2,'Tooling and scoured machining grain')
    tint=ramp(nt,grain,[(.12,(.47,.49,.5)),(.8,(1,1,1))],'Broad rubbed bands')
    col=mix(nt,col,tint,.26,'MULTIPLY');nt.links.new(col,bs.inputs['Base Color']);bs.inputs['Metallic'].default_value=.57;bs.inputs['Roughness'].default_value=.61
    b=nt.nodes.new('ShaderNodeBump');b.inputs['Strength'].default_value=.28;b.inputs['Distance'].default_value=.011
    nt.links.new(noise(nt,co,110,3,'Minute casting porosity'),b.inputs['Height']);nt.links.new(b.outputs[0],bs.inputs['Normal'])
    mat,nt,bs,co=shader('RM | oxidized teal gasket')
    col=ramp(nt,noise(nt,co,8.5,4),[(.14,(.017,.051,.044)),(.86,(.055,.16,.132))],'Aged blue-green collar finish')
    nt.links.new(col,bs.inputs['Base Color']);bs.inputs['Metallic'].default_value=.27;bs.inputs['Roughness'].default_value=.54
    b=nt.nodes.new('ShaderNodeBump');b.inputs['Strength'].default_value=.22;b.inputs['Distance'].default_value=.008
    nt.links.new(noise(nt,co,145,3),b.inputs['Height']);nt.links.new(b.outputs[0],bs.inputs['Normal'])
    mat,nt,bs,co=shader('RM | iron emblem')
    grain=noise(nt,co,67,4,'Pitted irregular iron grain')
    col=ramp(nt,grain,[(.25,(.0017,.0022,.0027)),(.56,(.012,.016,.019)),(.75,(.060,.069,.075))],'Charcoal forging with exposed gray pits')
    nt.links.new(col,bs.inputs['Base Color']);nt.links.new(col,bs.inputs['Emission Color']);bs.inputs['Emission Strength'].default_value=.28
    bs.inputs['Metallic'].default_value=.28;bs.inputs['Roughness'].default_value=.92
    b=nt.nodes.new('ShaderNodeBump');b.inputs['Strength'].default_value=.65;b.inputs['Distance'].default_value=.035;nt.links.new(grain,b.inputs['Height']);nt.links.new(b.outputs[0],bs.inputs['Normal'])


def scars():
    col=C['RM 02 / Eye carrier and clamps']
    for ob in list(col.objects):
        if ob.name.startswith('RM reference coating'):bpy.data.objects.remove(ob,do_unlink=True)
    name='RM | exposed dark coating substrate'
    if name not in bpy.data.materials:material(name,(.025,.028,.012),.25,.86)
    mat,nt,bs,co=shader(name)
    fac=noise(nt,co,39,4,'Rough torn paint substrate');color=ramp(nt,fac,[(.12,(.009,.014,.007)),(.8,(.062,.066,.022))],'Exposed oxidized iron')
    nt.links.new(color,bs.inputs['Base Color']);bs.inputs['Metallic'].default_value=.32;bs.inputs['Roughness'].default_value=.83
    b=nt.nodes.new('ShaderNodeBump');b.inputs['Strength'].default_value=.50;b.inputs['Distance'].default_value=.017;nt.links.new(fac,b.inputs['Height']);nt.links.new(b.outputs[0],bs.inputs['Normal'])
    # The branching dark abrasion immediately above and to the right of the eye.
    outlines=[[(1085,309),(1100,316),(1108,329),(1129,334),(1119,361),(1111,385),(1104,406),(1093,416),(1097,395),(1103,375),(1107,357),(1095,346),(1090,334)],
      [(1112,392),(1121,409),(1127,421),(1117,414),(1110,413),(1106,428),(1099,423),(1103,410)],
      [(1057,272),(1064,279),(1066,296),(1058,301),(1053,289)],
      [(1128,416),(1137,429),(1142,445),(1151,451),(1144,455),(1130,446),(1124,432)],
      [(1160,453),(1170,459),(1175,471),(1188,477),(1184,483),(1170,476),(1159,467)]]
    rng=random.Random(121124)
    def make(points,name):
        coords=[((x-960)/176,(535-y)/176) for x,y in points]
        return plate(name,coords,1.086,.002,mat,col,.0008)
    for pts in outlines:
        jagged=[]
        for j,p in enumerate(pts):
            q=pts[(j+1)%len(pts)];jagged.append(p)
            jagged.append(((p[0]+q[0])/2+rng.uniform(-2.4,2.4),(p[1]+q[1])/2+rng.uniform(-2.4,2.4)))
        make(jagged,'RM reference coating torn central scar')
    # Clusters are concentrated around the original damaged quadrant and rim.
    for i in range(145):
        if i<80:x=rng.gauss(1070,23);y=rng.uniform(231,391)
        else:
            a=rng.uniform(0,math.tau);rr=rng.uniform(235,337);x=960+rr*math.cos(a);y=535+rr*math.sin(a)*.89
        if ((x-960)/373)**2+((y-535)/328)**2>.93:continue
        w=rng.uniform(.6,2.4);h=rng.uniform(1.2,5.4)
        pts=[(x+math.cos(j*math.tau/9)*w*rng.uniform(.5,1.4),y+math.sin(j*math.tau/9)*h*rng.uniform(.5,1.4)) for j in range(9)]
        make(pts,'RM reference coating small ragged loss')
    for pts,r in [([(1140,574),(1144,626),(1158,668),(1163,707),(1185,744)],.0019), ([(958,214),(957,239),(953,267)],.0018), ([(804,770),(811,790),(835,805)],.0015)]:
        tube('RM reference coating hairline scoring',[((x-960)/176,(535-y)/176,1.087) for x,y in pts],r,mat,col)


def optical_finish():
    # Put the pupil above the convex sclera. The previous nearly coplanar pupil
    # intersected the globe and exposed a gray disk in the center of the eye.
    pupil=bpy.data.objects.get('RM black pupil')
    if pupil is None:pupil=next(o for o in C['RM 06 / Optics'].objects if 'pupil' in o.name.lower())
    pupil.location.z=1.548;pupil.scale=(.215,.215,.013)
    bs=bpy.data.materials['RM | pupil'].node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=(.0004,.0007,.001,1);bs.inputs['Roughness'].default_value=.16;bs.inputs['Specular IOR Level'].default_value=.025;bs.inputs['Metallic'].default_value=0
    glint=bpy.data.objects['RM eye lens glint'];glint.location=(-1.4,1.35,4.8)
    glint.rotation_euler=(Vector((0,0,1.3))-glint.location).to_track_quat('-Z','Y').to_euler()
    glint.data.energy=90;glint.data.size=.26;glint.data.size_y=.15
    # A subtle clear coat supplies the concentrated lens reflection.
    lens=bpy.data.materials['RM | wet crimson lens'].node_tree.nodes.get('Principled BSDF');lens.inputs['Roughness'].default_value=.26;lens.inputs['Coat Weight'].default_value=.8;lens.inputs['Coat Roughness'].default_value=.055
    # Low-frequency crypts interrupt the too-uniform radial fan pattern.
    iris=bpy.data.materials['RM | fine radial iris'];nt=iris.node_tree;bs=nt.nodes.get('Principled BSDF')
    tc=next(n for n in nt.nodes if n.bl_idname=='ShaderNodeTexCoord')
    if not nt.nodes.get('Uneven radial stromal lobes'):
        f=noise(nt,scaled(nt,tc.outputs['UV'],(7,.8,1)),3.4,4,'Uneven radial stromal lobes')
        dark=ramp(nt,f,[(.18,(.12,.07,.02)),(.45,(.50,.39,.18)),(.73,(1,1,1))],'Broad interrupted iris structure')
        old=bs.inputs['Base Color'].links[0].from_socket;out=mix(nt,old,dark,.55,'MULTIPLY');nt.links.new(out,bs.inputs['Base Color']);nt.links.new(out,bs.inputs['Emission Color'])
    s=bpy.context.scene;nt=s.node_tree
    if not nt.nodes.get('RM diffuse green edge bloom'):
        render=next(n for n in nt.nodes if n.bl_idname=='CompositorNodeRLayers')
        blur=nt.nodes.new('CompositorNodeBlur');blur.name='RM diffuse green edge bloom';blur.filter_type='GAUSS';blur.inputs['Size'].default_value=(18,18);nt.links.new(render.outputs['Emit'],blur.inputs['Image'])
        add=nt.nodes.new('CompositorNodeMixRGB');add.name='RM reference soft emblem irradiation';add.blend_type='ADD';add.inputs[0].default_value=2.8
        target=nt.nodes['RM restrained photographic halation'];old=target.inputs['Image'].links[0].from_socket;nt.links.new(old,add.inputs[1]);nt.links.new(blur.outputs[0],add.inputs[2]);nt.links.new(add.outputs[0],target.inputs['Image'])


def apply():
    C.update({c.name:c for c in bpy.data.collections});M.update({m.name:m for m in bpy.data.materials})
    paint('RM | military olive wall',(.061,.068,.037),(.179,.189,.099),.28,.77)
    paint('RM | faceplate yellow olive',(.238,.271,.076),(.474,.506,.186),.20,.69)
    paint('RM | shadowed olive armor',(.030,.037,.023),(.120,.133,.072),.36,.77)
    metals();scars();optical_finish()
    bpy.data.objects['RM faded olive central light'].data.color=(.91,1,.80)
    bpy.data.objects['RM broad wall bounce'].data.energy=420
    bpy.data.objects['RM grazing silver on clamp edges'].data.energy=160
    bpy.data.objects['RM grazing silver on clamp edges'].data.size=7
    bpy.context.scene.world.node_tree.nodes['Background'].inputs[1].default_value=.11
    from remaster_mechanics import relink_lights
    relink_lights()
    bpy.context.scene.frame_set(121)
    print('Applied aged paint, reference-positioned coating damage, cast gunmetal and softened optical response')
