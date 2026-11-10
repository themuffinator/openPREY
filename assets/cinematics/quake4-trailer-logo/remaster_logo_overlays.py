"""Controlled iron logo silhouette and animated technical overlay geometry.

All graphic elements are native Blender meshes or curves. Reference images are
measurement guides only; neither the trailer nor stock graphics are projected.
"""
import math
import random
import bpy
import bmesh
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
from scene_common import C, M, collection, empty, tube, key, node_key
from remaster_scene import EMBLEM_PATH, PARTS


def trailer_outline():
    # The cinematic has shorter, inward-curving horns than the menu insignia.
    # Matching these endpoints also preserves a curved taper instead of a wedge.
    path = list(EMBLEM_PATH)
    path[0] = ('M',177,41)
    path[1] = ('C',118,66,78,106,78,157)
    path[24] = ('C',432,106,392,66,333,41)
    path[25] = ('C',378,63,411,105,411,151)
    path[-1] = ('C',99,105,132,63,177,41)
    return path


def sample_outline():
    """Evaluate the authored cubic outline without a 2D curve bevel offset."""
    points = []
    for command in trailer_outline():
        if command[0] in {'M', 'L'}:
            points.append(Vector((command[1], command[2])))
        else:
            a = points[-1]
            b, c, d = [Vector(command[i:i + 2]) for i in (1, 3, 5)]
            steps = max(12, int(((b-a).length + (c-b).length + (d-c).length)/2))
            for j in range(1, steps + 1):
                t = j / steps
                points.append((1-t)**3*a + 3*(1-t)**2*t*b + 3*(1-t)*t*t*c + t**3*d)
    if (points[-1]-points[0]).length < .0001:
        points.pop()
    return [Vector(((p.x-255)*.0182, (171-p.y)*.0182, 0)) for p in points]


def extrude_outline(name, points, depth):
    """Closed, outward-facing mesh with exact 2D bounds and no miter spikes."""
    n = len(points)
    vertices = [(p.x, p.y, z) for z in (-depth/2, depth/2) for p in points]
    indices = {tuple(p): i for i, p in enumerate(points)}
    triangles = [[v if isinstance(v, int) else indices[tuple(v)] for v in tri]
                 for tri in tessellate_polygon([points])]
    faces = [tuple(reversed(t)) for t in triangles]
    faces += [tuple(i+n for i in t) for t in triangles]
    faces += [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh); bm.free()
    for p in mesh.polygons:
        p.use_smooth = len(p.vertices) == 4
    return mesh


def replace_logo():
    s = bpy.context.scene
    col = bpy.data.collections['RM 03 / Iron insignia']
    face = bpy.data.objects['RM Q insignia / precise iron silhouette']
    edge = bpy.data.objects['RM Q insignia / subdued green worn perimeter']
    points = sample_outline()
    mesh = extrude_outline('RM Q / exact closed silhouette', points, .34)
    mesh.materials.append(bpy.data.materials['RM | iron emblem'])
    face.modifiers.clear(); face.data = mesh
    bevel = face.modifiers.new('Small clamped iron edge — preserves horn tips', 'BEVEL')
    bevel.width = .012; bevel.segments = 3; bevel.limit_method = 'ANGLE'
    bevel.angle_limit = .65; bevel.use_clamp_overlap = True
    normals = face.modifiers.new('Weighted flat iron face normals', 'WEIGHTED_NORMAL')
    normals.keep_sharp = True; normals.weight = 30
    face['construction'] = 'Watertight solid extrusion of cubic contour. Clamped internal bevel cannot extend the upper tips.'
    face['nominal_top_y'] = max(p.y for p in points)
    face['nominal_width'] = max(p.x for p in points)-min(p.x for p in points)
    PARTS['emblem'] = face
    # A round, swept perimeter has a bounded radius even at an acute cusp.
    # It replaces the old filled curve whose offset generated long needles.
    rim = tube('RM Q / physical worn light-bearing edge',
               [(p.x, p.y, .157) for p in points], .017,
               bpy.data.materials['RM | soft radioactive edge'], col, cyclic=True)
    # Parenting guarantees the edge follows every animated scale of the iron.
    rim.parent = face
    rim.location = (0,0,0)
    old_name = edge.name
    bpy.data.objects.remove(edge, do_unlink=True)
    rim.name = old_name
    rim['construction'] = 'Swept round contour, fixed 0.017 radius; no acute-angle miter extension.'
    # Retain a clean, editable 2D master hidden from the final render.
    masters = bpy.data.collections.get('RM 03b / Editable insignia master')
    if not masters:
        masters = collection('RM 03b / Editable insignia master')
    for ob in list(masters.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    from remaster_scene import bezier_shape
    master = bezier_shape('RM Q / unexpanded cubic authoring master', [trailer_outline()],
                          bpy.data.materials['RM | iron emblem'], masters,
                          1.43, .34, 0, lambda x,y: ((x-255)*.0182,(171-y)*.0182))
    master.hide_render = True; master.hide_viewport = True
    masters.hide_render = True
    s.frame_set(121)
    print('Rebuilt solid logo and bounded round perimeter:', len(points), 'outline samples')


def logo_finish():
    from remaster_wear import shader
    from remaster_materials import noise, ramp, mix, scaled
    mat, nt, bs, co = shader('RM | iron emblem')
    grain = noise(nt, co, 119, 3.1, 'Fine open-pore forged iron')
    color = ramp(nt, grain, [(.16,(.0005,.0008,.001)),
                             (.43,(.003,.004,.005)),
                             (.70,(.026,.028,.029)),
                             (.87,(.055,.058,.057))], 'Black granular iron')
    broad = ramp(nt, noise(nt, co, 7, 4, 'Broad dark iron variation'),
                 [(.22,(.17,.19,.18)),(.77,(.8,.82,.77))], 'Oxidized iron islands')
    color = mix(nt, color, broad, .6, 'MULTIPLY')
    nt.links.new(color, bs.inputs['Base Color'])
    nt.links.new(color, bs.inputs['Emission Color'])
    bs.inputs['Emission Strength'].default_value = .48
    bs.inputs['Metallic'].default_value = .16
    bs.inputs['Roughness'].default_value = .90
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .6
    bump.inputs['Distance'].default_value = .011
    nt.links.new(grain, bump.inputs['Height']); nt.links.new(bump.outputs[0], bs.inputs['Normal'])
    # Fine variation interrupts the light without disturbing the measured outline.
    mat, nt, bs, co = shader('RM | soft radioactive edge')
    mat.node_tree.animation_data_clear()
    color = ramp(nt, noise(nt, co, 62, 2, 'Irregular worn edge phosphor'),
                 [(.22,(.06,.082,.008)),(.8,(.23,.28,.027))], 'Muted yellow-green edge')
    bs.inputs['Base Color'].default_value = (.002,.0025,.0005,1)
    nt.links.new(color, bs.inputs['Emission Color'])
    bs.inputs['Metallic'].default_value = .1; bs.inputs['Roughness'].default_value = .8
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(co, sep.inputs[0])
    fade = nt.nodes.new('ShaderNodeMapRange'); fade.name = 'Upper horn light falloff'
    fade.inputs['From Min'].default_value = .35; fade.inputs['From Max'].default_value = 2.12
    fade.inputs['To Min'].default_value = 1; fade.inputs['To Max'].default_value = .035
    nt.links.new(sep.outputs['Y'], fade.inputs['Value'])
    pulse = nt.nodes.new('ShaderNodeMath'); pulse.operation = 'MULTIPLY'; pulse.name = 'Logo edge reveal'
    nt.links.new(fade.outputs[0], pulse.inputs[0]); nt.links.new(pulse.outputs[0], bs.inputs['Emission Strength'])
    node_key(pulse.inputs[1], [(1,0),(31,.018),(40,.16),(46,.50),(60,.40),(180,.40)])
    s = bpy.context.scene
    # Keep the insignia's glow separate from the fine technical overlays.
    # Blooming every emissive surface made the circuit lines look like neon.
    aov_name = 'RM Emblem rim illumination'
    if not any(a.name==aov_name for a in s.view_layers[0].aovs):
        aov=s.view_layers[0].aovs.add();aov.name=aov_name;aov.type='COLOR'
    mult=nt.nodes.new('ShaderNodeVectorMath');mult.operation='SCALE'
    nt.links.new(color,mult.inputs[0]);nt.links.new(pulse.outputs[0],mult.inputs['Scale'])
    aov=nt.nodes.new('ShaderNodeOutputAOV');aov.aov_name=aov_name
    nt.links.new(mult.outputs[0],aov.inputs['Color'])
    compositor=s.node_tree
    render=next(n for n in compositor.nodes if n.bl_idname=='CompositorNodeRLayers')
    bpy.context.view_layer.update()
    compositor.links.new(render.outputs[aov_name],compositor.nodes['RM soft edge light spill'].inputs['Image'])
    compositor.links.new(render.outputs[aov_name],compositor.nodes['RM diffuse green edge bloom'].inputs['Image'])
    s.node_tree.nodes['RM diffuse green edge bloom'].inputs['Size'].default_value = (26,26)
    s.node_tree.nodes['RM reference soft emblem irradiation'].inputs[0].default_value = 4.2


def silver_finish():
    from remaster_wear import shader
    from remaster_materials import noise, ramp
    mat,nt,bs,co=shader('RM | silver title')
    grain=noise(nt,co,18,3,'Fine machined silver variation')
    col=ramp(nt,grain,[(.2,(.52,.54,.56)),(.8,(.88,.90,.92))], 'Uneven silver polish')
    nt.links.new(col,bs.inputs['Base Color'])
    rough=ramp(nt,grain,[(.2,(.18,)*3),(.8,(.24,)*3)],'Silver micro-roughness')
    nt.links.new(rough,bs.inputs['Roughness'])
    bs.inputs['Metallic'].default_value=.96;bs.inputs['Coat Weight'].default_value=.12
    bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.08;bump.inputs['Distance'].default_value=.0012
    nt.links.new(grain,bump.inputs['Height']);nt.links.new(bump.outputs[0],bs.inputs['Normal'])
    # The actual clamped mesh bevel supplies edge reflections. The optional
    # ray-traced Bevel shader caused an excessive OptiX initialization stall.
    bpy.data.objects['RM white title reflection card'].data.energy=225


def overlay_material(name, color, opacity, reveal=37):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True; nt = mat.node_tree; nt.nodes.clear(); nt.animation_data_clear()
    n, l = nt.nodes, nt.links
    out=n.new('ShaderNodeOutputMaterial'); transparent=n.new('ShaderNodeBsdfTransparent')
    emit=n.new('ShaderNodeEmission'); emit.inputs[0].default_value=(*color,1)
    mix=n.new('ShaderNodeMixShader'); mix.name='Timed overlay visibility'
    l.new(transparent.outputs[0],mix.inputs[1]); l.new(emit.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],out.inputs[0])
    coord=n.new('ShaderNodeTexCoord'); noise=n.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value=14; noise.inputs['Detail'].default_value=3
    l.new(coord.outputs['Object'],noise.inputs[0])
    vary=n.new('ShaderNodeMapRange');vary.inputs['To Min'].default_value=.36;vary.inputs['To Max'].default_value=1
    l.new(noise.outputs['Fac'],vary.inputs[0])
    strength=n.new('ShaderNodeMath'); strength.operation='MULTIPLY';strength.name='Overlay reveal envelope'
    l.new(vary.outputs[0],strength.inputs[0]);l.new(strength.outputs[0],mix.inputs[0])
    node_key(strength.inputs[1],[(1,0),(reveal,0),(reveal+9,opacity*.55),(63,opacity),(121,opacity*.92),(157,opacity),(180,opacity*.65)])
    mat.diffuse_color=(*color,opacity)
    return mat


def pixel_root(name, col, frames, z=2.16):
    """Animate native objects at a real depth using measured image positions."""
    root=empty(name,col);s=bpy.context.scene
    locs=[];scales=[];rots=[]
    for f,x,y,size in frames:
        s.frame_set(f);camera=s.camera
        wu=(camera.location.z-z)*camera.data.sensor_width/(camera.data.lens*1920)
        roll=camera.rotation_euler.z
        vec=Vector(((x-960)*wu,(540-y)*wu,0))
        vec.rotate(camera.rotation_euler)
        locs.append((f,(camera.location.x+vec.x,camera.location.y+vec.y,z)))
        scales.append((f,(wu*100*size,)*3));rots.append((f,(0,0,roll)))
    key(root,'location',locs);key(root,'scale',scales);key(root,'rotation_euler',rots)
    return root


def circuit_overlays(col):
    # Supersede the static background etchings with the moving optical graphics.
    for ob in bpy.data.collections['RM 05 / Surface engraving'].objects:
        ob.hide_render=True;ob.hide_viewport=True
    main=overlay_material('RM | floating circuit pale olive',(.20,.23,.12),.34)
    faint=overlay_material('RM | peripheral circular ghost',(.17,.20,.13),.12,41)
    soft=overlay_material('RM | circuit soft optical fringe',(.20,.23,.12),.035)
    left=pixel_root('RM OVERLAY / descending concentric reticle',col,
        [(1,421,90,1),(37,427,170,1),(46,431,202,1),(61,434,237,1),
         (76,437,271,1),(106,445,336,1),(121,450,367,1),(151,457,421,1),(180,463,468,1)])
    for radius in [91,120,151]:
        angles=[(-21+i*360/240) for i in range(240)]
        pts=[(radius*math.cos(math.radians(a))/100,radius*math.sin(math.radians(a))/100,0) for a in angles]
        tube('RM OVERLAY / left nested circle',pts,.008,main,col,left,True)
        tube('RM OVERLAY / left circle soft fringe',pts,.021,soft,col,left,True)
    for radius in [120,151]:
        a=math.radians(-21);x,y=radius*math.cos(a),radius*math.sin(a)
        pts=[(x/100,y/100,0),((x+65)/100,(y-24)/100,0),((x+367)/100,(y-134)/100,0)]
        tube('RM OVERLAY / parallel oblique signal lead',pts,.009,main,col,left)
        tube('RM OVERLAY / signal lead soft fringe',pts,.021,soft,col,left)
    right=pixel_root('RM OVERLAY / right nested technical glyph',col,
        [(1,1446,391,1.13),(37,1446,391,1.13),(61,1440,401,1.09),
         (76,1430,405,1.065),(121,1400,413,1),(151,1380,418,.96),(180,1364,423,.93)])
    # Coordinate pairs are independently reconstructed from the held shot.
    paths=[[(1209,348),(1274,285),(1380,285),(1380,303),(1569,303),(1569,545)],
           [(1219,362),(1284,301),(1364,301),(1364,315),(1553,315),(1553,544)],
           [(1233,374),(1294,317),(1350,317),(1350,328),(1537,328),(1537,541)],
           [(1324,319),(1324,340),(1359,379),(1374,379),(1374,319)],
           [(1328,391),(1328,412),(1364,451),(1376,451),(1376,393)],
           [(1334,463),(1334,484),(1368,524),(1381,524),(1381,463)],
           [(1391,318),(1391,529)],
           [(1450,329),(1450,354),(1476,386),(1476,530),(1508,530),(1508,318)],
           [(1438,340),(1438,365),(1464,395),(1464,526)]]
    for i,path in enumerate(paths):
        pts=[((x-1400)/100,(413-y)/100,0) for x,y in path]
        tube('RM OVERLAY / right glyph stroke %02d'%i,pts,.0075,main,col,right)
        tube('RM OVERLAY / right glyph soft fringe %02d'%i,pts,.019,soft,col,right)
    outer=pixel_root('RM OVERLAY / slow outer optical arcs',col,
        [(1,960,540,1.07),(37,960,540,1.055),(76,960,540,1.027),(121,960,540,1),(180,960,540,.975)],2.24)
    for radius,a,b in [(901,-39,34),(921,118,239),(859,-100,-63),(837,27,58),(866,134,161)]:
        pts=[(radius*math.cos(math.radians(a+(b-a)*i/240))/100,
              radius*math.sin(math.radians(a+(b-a)*i/240))/100,0) for i in range(241)]
        tube('RM OVERLAY / peripheral arc',pts,.0038,faint,col,outer)


def airborne_overlays(col):
    mat=overlay_material('RM | drifting pale hairline',(.59,.64,.43),.57,45)
    dust=overlay_material('RM | out of focus motes',(.16,.20,.14),.17,36)
    subtle=overlay_material('RM | faint vertical filament',(.22,.25,.17),.15,42)
    signature=pixel_root('RM OVERLAY / signature lower diagonal filament',col,
        [(1,930,802,1),(46,930,802,1),(76,918,773,1),(121,880,744,1),(151,861,724,1),(180,842,701,1)],2.25)
    line=tube('RM OVERLAY / bright tapered drifting hairline',
              [(-.080,-.218,0),(-.025,-.06,.008),(.065,.165,.002),(.105,.25,0)],.008,mat,col,signature)
    for p,r in zip(line.data.splines[0].points,[.1,.7,1,.07]):p.radius=r
    # Slower, faint streaks have individual depth and slant, avoiding a flat noise card.
    rng=random.Random(40406)
    for i,(x,y,length) in enumerate([(1132,829,67),(1057,919,49),(1160,644,82),(398,806,105),
                                    (699,295,119),(1657,618,94),(297,541,60),(1271,785,87)]):
        root=pixel_root('RM OVERLAY / fine filament %02d'%i,col,
            [(1,x+18,y+55,1),(46,x+18,y+55,1),(121,x,y,1),(180,x-23,y-32,1)],2.22+i*.007)
        pts=[(-.03,-length/200,0),(rng.uniform(-.015,.025),0,.015),(.03,length/200,0)]
        ob=tube('RM OVERLAY / hairline ghost %02d'%i,pts,.0038,subtle,col,root)
        for p,r in zip(ob.data.splines[0].points,[.02,1,.02]):p.radius=r
    root=pixel_root('RM OVERLAY / suspended fine dust',col,
        [(1,950,582,1.01),(46,950,578,1.01),(121,960,540,1),(180,971,507,.99)],2.29)
    for i in range(42):
        x=rng.uniform(-8.9,8.9);y=rng.uniform(-4.7,4.7)
        if abs(x)<2.3 and abs(y)<1:continue
        size=rng.uniform(.007,.029)
        ob=tube('RM OVERLAY / drifting dust fragment %02d'%i,
                [(x-size*.2,y-size,0),(x,y,rng.uniform(-.02,.02)),(x+size*.35,y+size,0)],
                size*.44,dust,col,root)
        for p,r in zip(ob.data.splines[0].points,[.05,1,.08]):p.radius=r


def optical_flashes():
    """Continuous soft flare kernels avoid rectangular streak-glare artifacts."""
    s=bpy.context.scene;nt=s.node_tree;n,l=nt.nodes,nt.links
    name='RM Optical core illumination'
    if not any(a.name==name for a in s.view_layers[0].aovs):
        a=s.view_layers[0].aovs.add();a.name=name;a.type='COLOR'
    mat=bpy.data.materials['RM | flash'];mt=mat.node_tree;bs=mt.nodes.get('Principled BSDF')
    av=mt.nodes.get('RM optical source AOV')
    if not av:
        av=mt.nodes.new('ShaderNodeOutputAOV');av.name='RM optical source AOV';av.aov_name=name
        color=mt.nodes.new('ShaderNodeRGB');color.outputs[0].default_value=(.20,.65,1,1)
        gain=mt.nodes.new('ShaderNodeVectorMath');gain.operation='SCALE';gain.name='RM optical source radiance'
        mt.links.new(color.outputs[0],gain.inputs[0]);mt.links.new(gain.outputs[0],av.inputs['Color'])
        node_key(gain.inputs['Scale'],[(1,0),(9,0),(16,180),(21,20),(27,0),(40,0),(46,360),(50,35),(57,0),(180,0)])
    bpy.context.view_layer.update()
    render=next(node for node in n if node.bl_idname=='CompositorNodeRLayers')
    # Rebuild only this group's nodes so applying the module is deterministic.
    for node in list(n):
        if node.name.startswith('RM smooth flare /'):n.remove(node)
    source=n['RM restrained photographic halation'].outputs['Image']
    for label,size,amount in [('core diffusion',(90,90),.20),
                              ('horizontal spread',(800,20),.10),
                              ('broad veil',(220,160),.15)]:
        blur=n.new('CompositorNodeBlur');blur.name='RM smooth flare / '+label
        blur.filter_type='GAUSS';blur.inputs['Size'].default_value=size
        l.new(render.outputs[name],blur.inputs['Image'])
        add=n.new('CompositorNodeMixRGB');add.name='RM smooth flare / add '+label
        add.blend_type='ADD';add.inputs[0].default_value=amount
        l.new(source,add.inputs[1]);l.new(blur.outputs[0],add.inputs[2]);source=add.outputs[0]
    l.new(source,n['RM narrow cyan optical streak'].inputs[1])
    profile=n['RM anamorphic lens streak profile'];profile.inputs['Size'].default_value=(1.15,.004)
    profile.outputs[0].links[0].to_node.inputs['Size'].default_value=(180,7)
    node_key(n['RM narrow cyan optical streak'].inputs[0],
             [(1,0),(9,.02),(16,.36),(21,.06),(27,0),(39,0),(46,.40),(51,.07),(57,0),(180,0)])


def apply():
    C.update({c.name:c for c in bpy.data.collections})
    M.update({m.name:m for m in bpy.data.materials})
    PARTS['scene'] = bpy.context.scene
    replace_logo()
    logo_finish()
    silver_finish()
    col=bpy.data.collections.get('RM 07 / Animated optical overlays')
    if col:
        for ob in list(col.objects):bpy.data.objects.remove(ob,do_unlink=True)
    else:col=collection('RM 07 / Animated optical overlays')
    circuit_overlays(col);airborne_overlays(col)
    for ob in col.objects:
        if ob.type in {'MESH','CURVE'}:
            ob.visible_shadow=False;ob.visible_diffuse=False;ob.visible_glossy=False
            ob.visible_transmission=False;ob.visible_volume_scatter=False
    from remaster_mechanics import relink_lights
    relink_lights()
    optical_flashes()
    s=bpy.context.scene;s.frame_set(121)
    s['revision']='Fourth construction: bounded solid logo horns and measured, animated native 3D optical overlays.'
    print('Added native floating circuit graphics, peripheral arcs and drifting filaments:',len(col.objects),'objects')
