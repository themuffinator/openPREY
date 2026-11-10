"""Deliberate cubic letterforms, with smooth serif transitions and sharp tips.

The guides establish proportions; these are authored curves rather than noisy
raster boundaries. Coordinates use a nominal 70-unit capital height.
"""
import bpy
from scene_common import C,M,bevel
from remaster_scene import PARTS,bezier_shape

GLYPHS={
'Q':(491,477,1.83,1.80,[[('M',21,0),('C',5,8,0,20,0,33),('C',0,52,12,65,30,69),('L',30,79),('C',30,84,32,92,34.5,98),('C',37,89,39,80,39,69),('C',57,65,69,50,69,32),('C',69,19,62,7,49,0),('C',58,6,65,16,65,29),('C',65,46,55,55,39,59),('L',39,46),('C',39,44,41,43,43,43),('L',26,43),('C',29,44,30,45,30,47),('L',30,59),('C',14,56,3,45,3,30),('C',3,17,9,7,21,0)]]),
'U':(650,477,1.84,1.72,[[('M',0,0),('L',22,0),('C',17,1,16,3,16,6),('L',16,46),('C',16,60,22,69,33,69),('C',44,69,51,60,51,46),('L',51,6),('C',51,3,49,1,45,0),('L',67,0),('C',62,1,61,3,61,6),('L',61,43),('C',61,59,50,71,34,71),('C',16,71,5,59,5,43),('L',5,6),('C',5,3,3,1,0,0)]]),
'A':(794,473,1.85,1.78,[
 [('M',0,70),('C',5,68,7,64,10,57),('L',35,0),('L',62,61),('C',65,67,67,69,70,70),('L',49,70),('C',54,70,55,68,53,63),('C',49,51,44,43,35,43),('C',26,43,21,51,17,59),('C',13,68,13,69,20,70)],
 [('M',29,41),('C',26,41,25,40,27,35),('L',32,23),('C',34,17,35,16,37,22),('L',43,36),('C',45,40,44,41,40,41)]]),
'K':(953,474,1.83,1.74,[[('M',0,0),('L',20,0),('C',16,1,14,3,14,7),('L',14,25),('C',14,29,16,32,22,33),('L',70,-2),('L',43,30),('C',62,35,67,49,67,70),('C',63,50,45,38,22,35),('C',17,35,14,38,14,44),('L',14,64),('C',14,68,16,69,20,70),('L',0,70),('C',5,69,6,67,6,62),('L',6,7),('C',6,3,4,1,0,0)]]),
'E':(1114,475,1.89,1.75,[[('M',0,0),('L',56,0),('L',56,23),('C',54,9,42,1,24,1),('L',14,1),('C',12,1,12,4,12,8),('L',12,26),('C',12,32,17,34,25,34),('C',17,34,12,36,12,43),('L',12,48),('C',12,62,20,69,32,69),('C',43,69,52,57,61,47),('L',61,70),('C',55,68,52,70,46,70),('L',30,70),('C',11,70,3,57,3,42),('L',3,6),('C',3,3,2,1,0,0)]]),
'4':(1298,472,1.90,1.65,[
 [('M',50,0),('L',50,60),('L',65,60),('C',70,60,72,55,74,51),('L',70,69),('L',50,69),('L',50,87),('C',50,93,54,95,59,96),('L',32,96),('C',40,94,42,93,42,88),('L',42,69),('L',0,69)],
 [('M',41,18),('L',12,60),('L',42,60)]])
}


def apply():
    masters=bpy.data.collections.get('RM 04b / Editable letter masters')
    if not masters:
        masters=bpy.data.collections.new('RM 04b / Editable letter masters');PARTS['scene'].collection.children.link(masters)
    for o in PARTS['letters']:
        label=o['character'];dx,dy,sx,sy,paths=GLYPHS[label]
        transform=lambda x,y:((dx+x*sx-960)/105-o.location.x,(540-dy-y*sy)/105)
        temp=bezier_shape('RM master letter curve / '+label,paths,M['RM | silver title'],C['RM 04 / Silver letterforms'],depth=.34,edge=.026,transform=transform)
        data=temp.data;data.resolution_u=32;data.bevel_depth=0
        # Make outer contours and counters explicitly opposed.
        for index,spl in enumerate(data.splines):
            pts=[(p.co.copy(),p.handle_left.copy(),p.handle_right.copy()) for p in spl.bezier_points]
            area=sum(pts[i][0].x*pts[(i+1)%len(pts)][0].y-pts[(i+1)%len(pts)][0].x*pts[i][0].y for i in range(len(pts)))
            if (area<0)!=(index>0):
                for p,(co,right,left) in zip(spl.bezier_points,reversed(pts)):
                    p.co=co;p.handle_left=left;p.handle_right=right
        was_mesh=o.type=='MESH'
        if was_mesh:
            bpy.context.view_layer.update()
            deps=bpy.context.evaluated_depsgraph_get()
            o.data=bpy.data.meshes.new_from_object(temp.evaluated_get(deps),depsgraph=deps)
            o.modifiers.clear()
        else:o.data=data
        o['construction']='Authored cubic serif contours, true solid extrusion, polished chamfers; no raster tracing artifacts.'
        for old in list(masters.objects):
            if old.name.startswith('RM editable master / '+label):bpy.data.objects.remove(old,do_unlink=True)
        master=bpy.data.objects.new('RM editable master / '+label,data.copy());masters.objects.link(master)
        master.location=o.location;master.parent=o.parent;master.hide_render=True;master.hide_viewport=True
        bpy.data.objects.remove(temp,do_unlink=True)
        for selected in bpy.context.selected_objects:selected.select_set(False)
        o.select_set(True);bpy.context.view_layer.objects.active=o
        if not was_mesh:bpy.ops.object.convert(target='MESH')
        bevel(o,.025,3)
        o.modifiers['Machined edge radius'].use_clamp_overlap=True
        o.modifiers['Machined edge radius'].harden_normals=True
        for polygon in o.data.polygons:polygon.use_smooth=abs(polygon.normal.z)<.99
    print('Installed deliberate cubic master letterforms')
