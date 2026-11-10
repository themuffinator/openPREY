"""Headless turnaround renders of an md5mesh with Doom-3 style texture sets.

blender -b --factory-startup --python blender_preview.py -- --mesh M --tex T.json --out DIR
    [--res 640] [--engine eevee|cycles|workbench] [--views front,left,...]
    [--samples N] [--uvcheck]

T.json maps a shader name to {"diffuse":..., "normal":..., "specular":...,
"glow":..., "alphatest":0.5}; missing entries render as mid-grey clay.
"""
import argparse
import json
import math
import os
import sys

import bpy
import mathutils

sys.path.insert(0, os.path.dirname(__file__))
import blender_md5 as md5import  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--mesh", required=True)
ap.add_argument("--tex", default="")
ap.add_argument("--out", required=True)
ap.add_argument("--res", type=int, default=640)
ap.add_argument("--engine", default="eevee")
ap.add_argument("--samples", type=int, default=32)
ap.add_argument("--views", default="front34,back34,left,right,top,low34")
ap.add_argument("--uvcheck", action="store_true")
ap.add_argument("--islands", action="store_true")
ap.add_argument("--only", default="")
ap.add_argument("--flipgreen", action="store_true")
ap.add_argument("--blend", default="")
args = ap.parse_args(argv)

os.makedirs(args.out, exist_ok=True)
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)

objs = md5import.load(args.mesh)
tex = json.load(open(args.tex)) if args.tex else {}


def img(path, colour=True):
    im = bpy.data.images.load(path, check_existing=True)
    if not colour:
        im.colorspace_settings.name = "Non-Color"
    return im


def make_material(shader):
    mat = bpy.data.materials.new(shader.split("/")[-1])
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    t = tex.get(shader, {})
    if args.islands and args.only and not shader.endswith(args.only):
        bsdf.inputs["Base Color"].default_value = (0.08, 0.08, 0.08, 1)
        return mat
    if args.islands:
        n = nt.nodes.new("ShaderNodeVertexColor")
        n.layer_name = "island"
        nt.links.new(n.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.8
        return mat
    if args.uvcheck:
        n = nt.nodes.new("ShaderNodeTexChecker")
        n.inputs["Scale"].default_value = 32
        nt.links.new(n.outputs["Color"], bsdf.inputs["Base Color"])
        return mat
    if "diffuse" in t:
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = img(t["diffuse"])
        nt.links.new(n.outputs["Color"], bsdf.inputs["Base Color"])
        if "alphatest" in t:
            nt.links.new(n.outputs["Alpha"], bsdf.inputs["Alpha"])
            try:
                mat.blend_method = "CLIP"
                mat.alpha_threshold = t["alphatest"]
            except Exception:
                pass
    else:
        bsdf.inputs["Base Color"].default_value = (0.35, 0.35, 0.35, 1)
    if "normal" in t:
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = img(t["normal"], False)
        src = n.outputs["Color"]
        if args.flipgreen or t.get("flipgreen"):
            sep = nt.nodes.new("ShaderNodeSeparateColor")
            comb = nt.nodes.new("ShaderNodeCombineColor")
            inv = nt.nodes.new("ShaderNodeMath")
            inv.operation = "SUBTRACT"
            inv.inputs[0].default_value = 1.0
            nt.links.new(src, sep.inputs["Color"])
            nt.links.new(sep.outputs["Red"], comb.inputs["Red"])
            nt.links.new(sep.outputs["Green"], inv.inputs[1])
            nt.links.new(inv.outputs[0], comb.inputs["Green"])
            nt.links.new(sep.outputs["Blue"], comb.inputs["Blue"])
            src = comb.outputs["Color"]
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(src, nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if "specular" in t:
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = img(t["specular"], False)
        bw = nt.nodes.new("ShaderNodeRGBToBW")
        nt.links.new(n.outputs["Color"], bw.inputs["Color"])
        rough = nt.nodes.new("ShaderNodeMath")
        rough.operation = "MULTIPLY_ADD"
        rough.inputs[1].default_value = -0.75
        rough.inputs[2].default_value = 0.85
        nt.links.new(bw.outputs["Val"], rough.inputs[0])
        nt.links.new(rough.outputs[0], bsdf.inputs["Roughness"])
        key = "Specular IOR Level" if "Specular IOR Level" in bsdf.inputs else "Specular"
        nt.links.new(bw.outputs["Val"], bsdf.inputs[key])
    else:
        bsdf.inputs["Roughness"].default_value = 0.6
    if "glow" in t:
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = img(t["glow"])
        key = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
        nt.links.new(n.outputs["Color"], bsdf.inputs[key])
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = 2.0
    return mat


if args.islands:
    import md5mesh as isl  # noqa: E402
    for ob in objs:
        me = ob.data
        tris = [tuple(p.vertices) for p in me.polygons]
        comp = isl.components(len(me.vertices), tris)
        ca = me.color_attributes.new("island", "FLOAT_COLOR", "POINT")
        for i, k in enumerate(comp):
            r_, g_, b_ = isl.colour(k)
            ca.data[i].color = (r_ ** 2.2, g_ ** 2.2, b_ ** 2.2, 1.0)

for ob in objs:
    ob.data.materials.append(make_material(ob["md5_shader"]))

# bounds
pts = [ob.matrix_world @ mathutils.Vector(c) for ob in objs for c in ob.bound_box]
lo = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
centre = (lo + hi) / 2
radius = (hi - lo).length / 2
print("BOUNDS", tuple(lo), tuple(hi))

scene = bpy.context.scene
eng = {"eevee": None, "cycles": "CYCLES", "workbench": "BLENDER_WORKBENCH"}[args.engine]
if eng is None:
    for cand in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = cand
            break
        except TypeError:
            continue
else:
    scene.render.engine = eng
if scene.render.engine == "CYCLES":
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
            try:
                prefs.compute_device_type = backend
            except TypeError:
                continue
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == backend]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == backend
                scene.cycles.device = "GPU"
                print("CYCLES DEVICE", backend, [d.name for d in gpus])
                break
    except Exception as exc:  # CPU fallback
        print("CYCLES CPU", exc)
elif scene.render.engine.startswith("BLENDER_EEVEE"):
    scene.eevee.taa_render_samples = args.samples
scene.render.resolution_x = args.res
scene.render.resolution_y = args.res
scene.render.film_transparent = False
scene.view_settings.view_transform = "Standard"

world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.055, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
scene.world = world


def add_light(name, kind, loc, energy, colour=(1, 1, 1), size=None):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = colour
    if size is not None and hasattr(ld, "shadow_soft_size"):
        ld.shadow_soft_size = size
    lo_ = bpy.data.objects.new(name, ld)
    lo_.location = loc
    scene.collection.objects.link(lo_)
    tr = lo_.constraints.new("TRACK_TO")
    tgt = bpy.data.objects.new(name + "_t", None)
    tgt.location = centre
    scene.collection.objects.link(tgt)
    tr.target = tgt
    return lo_


r = radius * 3
add_light("key", "AREA", centre + mathutils.Vector((r, -r * 0.6, r * 0.9)), 9000 * (radius / 50) ** 2 * 12, (1.0, 0.92, 0.82), None)
add_light("fill", "AREA", centre + mathutils.Vector((-r, -r * 0.5, r * 0.3)), 2500 * (radius / 50) ** 2 * 12, (0.75, 0.85, 1.0))
add_light("rim", "AREA", centre + mathutils.Vector((-r * 0.2, r, r * 0.6)), 6000 * (radius / 50) ** 2 * 12, (1.0, 0.8, 0.6))

cam_data = bpy.data.cameras.new("cam")
cam_data.lens = 50
cam_data.clip_end = radius * 50
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
VIEWS = {
    # name: (azimuth deg about Z measured from +X, elevation deg)
    "front": (0, 5), "front34": (35, 20), "back34": (215, 20), "back": (180, 5),
    "left": (90, 10), "right": (270, 10), "top": (0, 85), "low34": (320, -20),
    "f2": (-35, 20), "b2": (145, 25),
}
dist = radius / math.tan(cam_data.angle / 2) * 1.1
for v in args.views.split(","):
    if v.startswith("custom:"):
        _, az, el, zoom, ox, oy, oz = v.split(":")
        az, el, zoom = float(az), float(el), float(zoom)
        tgt = mathutils.Vector((float(ox), float(oy), float(oz)))
        name = "custom_%d_%d_%s" % (az, el, zoom)
    else:
        az, el = VIEWS[v]
        zoom, tgt, name = 1.0, centre, v
    d = dist / zoom
    a, e = math.radians(az), math.radians(el)
    cam.location = tgt + mathutils.Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))) * d
    direction = tgt - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(args.out, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", scene.render.filepath)

if args.blend:
    bpy.ops.wm.save_as_mainfile(filepath=args.blend)
