"""Bake per-material texture-space maps for the turret skin painter.

blender -b --factory-startup --python blender_bake.py -- --mesh M --tex T.json --out DIR --res "name=1024,..."

For every md5 mesh (material) writes into DIR:
  <name>_ao.png        ambient occlusion with the normal map applied
  <name>_onormal.png   object-space normal with the normal map applied (8-bit, 0.5 = 0)
  <name>_pos.exr       object-space position (float)
  <name>_cover.png     UV coverage (white where triangles are)
Normal maps are id's green-down tangent space, so green is flipped for Blender.
"""
import argparse
import json
import os
import sys

import bpy
import mathutils

sys.path.insert(0, os.path.dirname(__file__))
import blender_md5 as md5import  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
ap = argparse.ArgumentParser()
ap.add_argument("--mesh", required=True)
ap.add_argument("--tex", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--res", default="")
ap.add_argument("--samples", type=int, default=96)
ap.add_argument("--aodist", type=float, default=6.0)
ap.add_argument("--only", default="")
args = ap.parse_args(argv)
os.makedirs(args.out, exist_ok=True)

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
objs = md5import.load(args.mesh)
tex = json.load(open(args.tex))
res = {}
for item in filter(None, args.res.split(",")):
    k, v = item.split("=")
    res[k] = int(v)

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = args.samples
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "OPTIX"
    scene.cycles.device = "GPU"
except Exception as exc:
    print("CPU bake", exc)
world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
scene.world = world

pts = [ob.matrix_world @ mathutils.Vector(c) for ob in objs for c in ob.bound_box]
lo = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
json.dump({"lo": list(lo), "hi": list(hi)}, open(os.path.join(args.out, "bounds.json"), "w"))


def normal_map_node(nt, path):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = bpy.data.images.load(path, check_existing=True)
    n.image.colorspace_settings.name = "Non-Color"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    comb = nt.nodes.new("ShaderNodeCombineColor")
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(n.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Red"], comb.inputs["Red"])
    nt.links.new(sep.outputs["Green"], inv.inputs[1])
    nt.links.new(inv.outputs[0], comb.inputs["Green"])
    nt.links.new(sep.outputs["Blue"], comb.inputs["Blue"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(comb.outputs["Color"], nm.inputs["Color"])
    return nm


def bake(ob, kind, image):
    mat = ob.data.materials[0]
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    t = tex.get(ob["md5_shader"], {})
    nm = normal_map_node(nt, t["normal"]) if "normal" in t else None
    target = nt.nodes.new("ShaderNodeTexImage")
    target.image = image
    nt.nodes.active = target
    if kind == "ao":
        ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
        ao.samples = 32
        ao.inputs["Distance"].default_value = args.aodist
        if nm:
            nt.links.new(nm.outputs["Normal"], ao.inputs["Normal"])
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(ao.outputs["AO"], em.inputs["Color"])
        nt.links.new(em.outputs["Emission"], outn.inputs["Surface"])
        scene.cycles.bake_type = "EMIT"
    elif kind == "pos":
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(geo.outputs["Position"], em.inputs["Color"])
        nt.links.new(em.outputs["Emission"], outn.inputs["Surface"])
        scene.cycles.bake_type = "EMIT"
    elif kind == "cover":
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (1, 1, 1, 1)
        nt.links.new(em.outputs["Emission"], outn.inputs["Surface"])
        scene.cycles.bake_type = "EMIT"
    elif kind == "onormal":
        bsdf = nt.nodes.new("ShaderNodeBsdfDiffuse")
        if nm:
            nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
        nt.links.new(bsdf.outputs["BSDF"], outn.inputs["Surface"])
        scene.cycles.bake_type = "NORMAL"
        scene.render.bake.normal_space = "OBJECT"
        scene.render.bake.normal_r = "POS_X"
        scene.render.bake.normal_g = "POS_Y"
        scene.render.bake.normal_b = "POS_Z"
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    scene.render.bake.margin = 0 if kind == "cover" else 6
    scene.render.bake.use_clear = True
    # data bakes take one sample at each texel centre: summing several samples
    # on the GPU differs in the last float bits from run to run, which the
    # painter's noise lattice would turn into a few changed texels
    scene.cycles.samples = args.samples if kind == "ao" else 1
    scene.cycles.filter_width = 1.5 if kind == "ao" else 0.01
    bpy.ops.object.bake(type=scene.cycles.bake_type)


for ob in objs:
    name = ob["md5_shader"].split("/")[-1]
    if args.only and not name.endswith(args.only):
        continue
    ob.data.materials.append(bpy.data.materials.new(name))
    ob.data.materials[0].use_nodes = True
    size = res.get(name[-2:], 1024)
    for kind in ("cover", "ao", "onormal", "pos"):
        is_float = kind == "pos"
        img = bpy.data.images.new("%s_%s" % (name, kind), size, size, float_buffer=is_float, alpha=False)
        # every bake is data: a float image left in linear colour space is
        # written through the sRGB curve, which mangled the positions
        img.colorspace_settings.name = "Non-Color"
        bake(ob, kind, img)
        path = os.path.join(args.out, "%s_%s.%s" % (name, kind, "exr" if is_float else "png"))
        img.filepath_raw = path
        img.file_format = "OPEN_EXR" if is_float else "PNG"
        img.save()
        print("BAKED", path)
