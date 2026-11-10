"""Minimal md5mesh (bind pose) importer for headless Blender inspection.

Usage inside Blender:  import blender_md5; objs = blender_md5.load(path)
Each md5 mesh becomes one object named after its shader's last path segment,
with a UV map (V flipped to Blender's convention) and the joints as empties.
"""
import math
import re

import bpy
import mathutils


def _quat(x, y, z):
    t = 1.0 - (x * x + y * y + z * z)
    w = 0.0 if t < 0.0 else -math.sqrt(t)
    return mathutils.Quaternion((w, x, y, z))


def parse(path):
    text = open(path, encoding="latin-1").read()
    joints = []
    jblock = re.search(r"joints\s*\{(.*?)\}", text, re.S).group(1)
    for m in re.finditer(r'"([^"]*)"\s+(-?\d+)\s*\(\s*(\S+)\s+(\S+)\s+(\S+)\s*\)\s*\(\s*(\S+)\s+(\S+)\s+(\S+)\s*\)', jblock):
        name, parent = m.group(1), int(m.group(2))
        pos = mathutils.Vector((float(m.group(3)), float(m.group(4)), float(m.group(5))))
        q = _quat(float(m.group(6)), float(m.group(7)), float(m.group(8)))
        joints.append((name, parent, pos, q))
    meshes = []
    for m in re.finditer(r"\nmesh\s*\{(.*?)\n\}", text, re.S):
        body = m.group(1)
        shader = re.search(r'shader\s+"([^"]*)"', body).group(1)
        verts = [(float(a), float(b), int(c), int(d)) for a, b, c, d in
                 re.findall(r"vert\s+\d+\s+\(\s*(\S+)\s+(\S+)\s*\)\s+(\d+)\s+(\d+)", body)]
        tris = [(int(a), int(b), int(c)) for a, b, c in re.findall(r"tri\s+\d+\s+(\d+)\s+(\d+)\s+(\d+)", body)]
        weights = [(int(j), float(b), mathutils.Vector((float(x), float(y), float(z)))) for j, b, x, y, z in
                   re.findall(r"weight\s+\d+\s+(\d+)\s+(\S+)\s*\(\s*(\S+)\s+(\S+)\s+(\S+)\s*\)", body)]
        meshes.append((shader, verts, tris, weights))
    return joints, meshes


def load(path, collection=None):
    joints, meshes = parse(path)
    col = collection or bpy.context.scene.collection
    objs = []
    for shader, verts, tris, weights in meshes:
        positions = []
        uvs = []
        for u, v, start, count in verts:
            p = mathutils.Vector((0.0, 0.0, 0.0))
            for wi in range(start, start + count):
                j, bias, wpos = weights[wi]
                jpos, jq = joints[j][2], joints[j][3]
                p += (jpos + jq @ wpos) * bias
            positions.append(p)
            uvs.append((u, 1.0 - v))
        me = bpy.data.meshes.new(shader.split("/")[-1])
        # md5 winds clockwise seen from outside; reverse for Blender
        me.from_pydata([tuple(p) for p in positions], [], [(a, c, b) for a, b, c in tris])
        uvl = me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            for li in poly.loop_indices:
                uvl.data[li].uv = uvs[me.loops[li].vertex_index]
        me.update()
        for poly in me.polygons:
            poly.use_smooth = True
        ob = bpy.data.objects.new(me.name, me)
        ob["md5_shader"] = shader
        col.objects.link(ob)
        objs.append(ob)
    for name, parent, pos, q in joints:
        e = bpy.data.objects.new("joint_" + name, None)
        e.empty_display_size = 2.0
        e.location = pos
        e.rotation_mode = "QUATERNION"
        e.rotation_quaternion = q
        col.objects.link(e)
    return objs
