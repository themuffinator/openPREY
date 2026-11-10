"""Original procedural scene helpers. Blender 4.5 LTS; no external textures."""
import bpy
import math
import random
from mathutils import Vector

RNG = random.Random(405)
C = {}
M = {}


def collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    C[name] = col
    return col


def put(obj, col, material=None, parent=None):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    col.objects.link(obj)
    if material:
        obj.data.materials.append(material)
    if parent:
        obj.parent = parent
    return obj


def empty(name, col):
    o = bpy.data.objects.new(name, None)
    col.objects.link(o)
    o.empty_display_size = .5
    return o


def bevel(o, width=.03, segments=3):
    b = o.modifiers.new('Machined edge radius', 'BEVEL')
    b.width = width
    b.segments = segments
    b.limit_method = 'ANGLE'
    n = o.modifiers.new('Weighted surface normals', 'WEIGHTED_NORMAL')
    n.keep_sharp = True
    return o


def box(name, loc, size, mat, col, edge=.025, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    put(o, col, mat, parent)
    if edge:
        bevel(o, edge, 3)
    return o


def cylinder(name, radius, depth, loc, mat, col, vertices=96, edge=.018, parent=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    o = bpy.context.object
    o.name = name
    put(o, col, mat, parent)
    if edge:
        bevel(o, edge, 3)
    for p in o.data.polygons:
        p.use_smooth = len(p.vertices) == 4
    return o


def sphere(name, loc, scale, mat, col, parent=None, segments=48):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=24, radius=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    put(o, col, mat, parent)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def tube(name, points, radius, mat, col, parent=None, cyclic=False):
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.resolution_u = 2
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    curve.resolution_u = 12
    spl = curve.splines.new('POLY')
    spl.points.add(len(points)-1)
    for p, co in zip(spl.points, points):
        p.co = (*co, 1)
    spl.use_cyclic_u = cyclic
    o = bpy.data.objects.new(name, curve)
    col.objects.link(o)
    o.data.materials.append(mat)
    if parent:
        o.parent = parent
    return o


def arc(name, radius, tube_radius, z, mat, col, start=0, end=360, center=(0, 0), parent=None):
    count = max(12, int(abs(end-start)/2))
    points = []
    for i in range(count+1):
        a = math.radians(start+(end-start)*i/count)
        points.append((center[0]+radius*math.cos(a), center[1]+radius*math.sin(a), z))
    return tube(name, points, tube_radius, mat, col, parent)


def sector(name, ri, ro, a0, a1, z, depth, mat, col, parent=None, edge=.02):
    steps = max(4, int(abs(a1-a0)/2))
    points = []
    for radius, reverse in [(ro, False), (ri, True)]:
        seq = range(steps, -1, -1) if reverse else range(steps+1)
        for i in seq:
            a = math.radians(a0+(a1-a0)*i/steps)
            points.append((radius*math.cos(a), radius*math.sin(a)))
    return solid_outline(name, [{'points': points, 'hole': False}], z, depth, mat, col, edge, parent)


def solid_outline(name, loops, z, depth, mat, col, edge=.012, parent=None):
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '2D'
    curve.resolution_u = 12
    curve.fill_mode = 'BOTH'
    curve.extrude = depth / 2
    curve.bevel_depth = edge
    curve.bevel_resolution = 3
    for loop in loops:
        points = list(loop['points'])
        area = sum(points[i][0]*points[(i+1)%len(points)][1] - points[(i+1)%len(points)][0]*points[i][1] for i in range(len(points)))
        if (area < 0) != bool(loop.get('hole', False)):
            points.reverse()
        spl = curve.splines.new('POLY')
        spl.points.add(len(points)-1)
        for p, (x, y) in zip(spl.points, points):
            p.co = (x, y, 0, 1)
        spl.use_cyclic_u = True
    o = bpy.data.objects.new(name, curve)
    col.objects.link(o)
    o.location.z = z
    o.data.materials.append(mat)
    if parent:
        o.parent = parent
    return o


def material(name, color, metal=0, rough=.5, emission=None, strength=0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bs = mat.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Metallic'].default_value = metal
    bs.inputs['Roughness'].default_value = rough
    if emission:
        bs.inputs['Emission Color'].default_value = (*emission, 1)
        bs.inputs['Emission Strength'].default_value = strength
    mat.diffuse_color = (*color, 1)
    M[name] = mat
    return mat


def weathered(name, low, high, rough=.8, metal=.45, scale=5, bump=.055):
    mat = material(name, high, metal, rough)
    nt = mat.node_tree
    n, l = nt.nodes, nt.links
    bs = n.get('Principled BSDF')
    coord = n.new('ShaderNodeTexCoord')
    coord.location = (-950, 100)
    noise = n.new('ShaderNodeTexNoise')
    noise.name = 'Oxidation / mottled worn paint'
    noise.inputs['Scale'].default_value = scale
    noise.inputs['Detail'].default_value = 5
    noise.inputs['Roughness'].default_value = .8
    noise.location = (-700, 230)
    l.new(coord.outputs['Object'], noise.inputs['Vector'])
    ramp = n.new('ShaderNodeValToRGB')
    ramp.location = (-460, 250)
    ramp.color_ramp.elements[0].position = .23
    ramp.color_ramp.elements[0].color = (*low, 1)
    ramp.color_ramp.elements[1].position = .78
    ramp.color_ramp.elements[1].color = (*high, 1)
    l.new(noise.outputs['Fac'], ramp.inputs[0])
    chips = n.new('ShaderNodeTexNoise')
    chips.location = (-700, -50)
    chips.inputs['Scale'].default_value = 44
    chips.inputs['Detail'].default_value = 3.7
    chips.inputs['Roughness'].default_value = .8
    l.new(coord.outputs['Object'], chips.inputs[0])
    chipramp = n.new('ShaderNodeValToRGB')
    chipramp.location = (-460, -70)
    chipramp.color_ramp.elements[0].position = .35
    chipramp.color_ramp.elements[0].color = (.012, .017, .009, 1)
    chipramp.color_ramp.elements[1].position = .48
    chipramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    l.new(chips.outputs['Fac'], chipramp.inputs[0])
    mix = n.new('ShaderNodeMixRGB')
    mix.blend_type = 'MULTIPLY'
    mix.inputs[0].default_value = .9
    mix.location = (-180, 250)
    l.new(ramp.outputs[0], mix.inputs[1])
    l.new(chipramp.outputs[0], mix.inputs[2])
    l.new(mix.outputs[0], bs.inputs['Base Color'])
    b = n.new('ShaderNodeBump')
    b.location = (-170, -80)
    b.inputs['Strength'].default_value = .48
    b.inputs['Distance'].default_value = bump
    l.new(chips.outputs['Fac'], b.inputs['Height'])
    l.new(b.outputs[0], bs.inputs['Normal'])
    return mat


def aim(o, target):
    o.rotation_euler = (Vector(target)-o.location).to_track_quat('-Z', 'Y').to_euler()


def light(name, kind, loc, energy, color, size, col, target=(0, 0, 0)):
    data = bpy.data.lights.new(name, kind)
    data.energy = energy
    data.color = color
    if kind == 'AREA':
        data.shape = 'DISK'
        data.size = size
    else:
        data.shadow_soft_size = size
    o = bpy.data.objects.new(name, data)
    col.objects.link(o)
    o.location = loc
    aim(o, target)
    return o


def key(o, path, values):
    for frame, value in values:
        setattr(o, path, value)
        o.keyframe_insert(data_path=path, frame=frame)


def node_key(socket, values):
    for frame, value in values:
        socket.default_value = value
        socket.keyframe_insert('default_value', frame=frame)
