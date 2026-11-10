"""Geometry and optical corrections measured at 200 ms trailer checkpoints.

The silver chamfers are real triangulated surfaces bounded by the authored
contours. No raster boundary, reference footage, or image-plane replacement
is used as scene geometry or a visible texture.
"""
import math
import json
from pathlib import Path
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt
from scene_common import C,M,box,cylinder,tube,key,node_key,light,aim
from remaster_scene import PARTS,lathe
from remaster_mechanics import plate,mesh_part,relink_lights
from remaster_materials import noise,ramp,mix,scaled
from remaster_wear import shader


def prepare():
    C.update({c.name:c for c in bpy.data.collections})
    M.update({m.name:m for m in bpy.data.materials})
    PARTS['scene']=bpy.context.scene
    PARTS['letters']=[o for o in C['RM 04 / Silver letterforms'].objects if o.type=='MESH']
    PARTS['title']=bpy.data.objects['RM TITLE / authentic silver silhouettes']
    bpy.context.scene.frame_set(121)


def sampled(paths,transform,spacing=.012):
    result=[]
    for path in paths:
        points=[]
        for cmd in path:
            if cmd[0]=='M':points.append(Vector(transform(cmd[1],cmd[2])))
            elif cmd[0]=='L':
                a=points[-1];b=Vector(transform(cmd[1],cmd[2]));n=max(1,math.ceil((b-a).length/spacing))
                points.extend(a.lerp(b,j/n) for j in range(1,n+1))
            else:
                a=points[-1];b,c,d=[Vector(transform(cmd[i],cmd[i+1])) for i in (1,3,5)]
                n=max(4,math.ceil(((b-a).length+(c-b).length+(d-c).length)/spacing))
                points.extend((1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d for t in [j/n for j in range(1,n+1)])
        if (points[0]-points[-1]).length<1e-5:points.pop()
        else:
            a,b=points[-1],points[0];n=max(1,math.ceil((b-a).length/spacing))
            points.extend(a.lerp(b,j/n) for j in range(1,n))
        result.append(np.array([tuple(p) for p in points]))
    return result


def inside(xy,loops):
    contained=np.zeros(len(xy),dtype=bool);x,y=xy[:,0],xy[:,1]
    for pts in loops:
        a=pts[-1]
        for b in pts:
            if abs(b[1]-a[1])>1e-12:
                contained^=((a[1]>y)!=(b[1]>y))&(x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0])
            a=b
    return contained


def border_distance(xy,loops):
    dist=np.full(len(xy),1e8)
    for pts in loops:
        a=pts[-1]
        for b in pts:
            v=b-a;length=float(v@v)
            if length>1e-14:
                t=np.clip((xy-a)@v/length,0,1)
                delta=xy-a-t[:,None]*v
                dist=np.minimum(dist,np.einsum('ij,ij->i',delta,delta))
            a=b
    return np.sqrt(dist)


def sculpted_letter(label,paths,transform):
    """Constrained triangulation plus distance chamfer; acute tips stay bounded."""
    loops=sampled(paths,transform)
    points=np.concatenate(loops);edges=[];offset=0
    for pts in loops:
        edges.extend((offset+i,offset+(i+1)%len(pts)) for i in range(len(pts)));offset+=len(pts)
    lo,hi=points.min(axis=0),points.max(axis=0)
    xx,yy=np.meshgrid(np.arange(lo[0]+.006,hi[0],.011),np.arange(lo[1]+.006,hi[1],.011))
    grid=np.column_stack((xx.ravel(),yy.ravel()));grid=grid[inside(grid,loops)]
    # A tiny boundary exclusion prevents near-zero CDT triangles.
    grid=grid[border_distance(grid,loops)>.003]
    points=np.concatenate((points,grid))
    vs,es,fs,*_=delaunay_2d_cdt([Vector(p) for p in points],edges,[],0,1e-7,False)
    xy=np.array([tuple(v) for v in vs]);tri=np.array(fs,dtype=int)
    tri=tri[inside(xy[tri].mean(axis=1),loops)]
    used=sorted(set(tri.ravel()));lookup={v:i for i,v in enumerate(used)}
    tri=np.array([[lookup[v] for v in face] for face in tri]);xy=xy[used]
    d=border_distance(xy,loops)
    t=np.minimum(d/.030,1)
    # Broad 45-degree chamfer with a small eased transition onto the silver face.
    height=.133+.037*(1-(1-t)**1.4)
    verts=[(float(x),float(y),float(z)) for (x,y),z in zip(xy,height)]
    count=len(verts);verts.extend((float(x),float(y),-.17) for x,y in xy)
    faces=[tuple(map(int,f)) for f in tri]+[tuple(int(i)+count for i in reversed(f)) for f in tri]
    usage={}
    for f in tri:
        for a,b in zip(f,np.roll(f,-1)):
            e=tuple(sorted((int(a),int(b))));usage[e]=usage.get(e,0)+1
    for (a,b),n in usage.items():
        if n==1:faces.append((a,b,b+count,a+count))
    mesh=bpy.data.meshes.new('RM '+label+' / bounded sculpted silver chamfer');mesh.from_pydata(verts,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    for p in mesh.polygons:p.use_smooth=p.center.z>0
    mesh.materials.append(M['RM | silver title'])
    return mesh


def letters():
    prepare()
    import remaster_lettering
    glyphs=dict(remaster_lettering.GLYPHS)
    # The held trailer has a substantial lower U bowl and E return; the previous
    # contours left these strokes just one or two nominal units thick.
    glyphs['U']=(650,477,1.84,1.72,[[('M',0,0),('L',22,0),('C',17,1,16,3,16,6),('L',16,46),('C',16,57,22,64,33,64),('C',44,64,51,57,51,46),('L',51,6),('C',51,3,49,1,45,0),('L',67,0),('C',62,1,61,3,61,6),('L',61,43),('C',61,59,50,71,34,71),('C',16,71,5,59,5,43),('L',5,6),('C',5,3,3,1,0,0)]])
    glyphs['E']=(1114,475,1.89,1.75,[[('M',0,0),('L',56,0),('L',56,23),('C',53,11,43,6,24,6),('L',16,6),('C',13,6,12,8,12,11),('L',12,26),('C',12,31,17,33,25,34),('C',17,35,12,38,12,43),('L',12,48),('C',12,59,20,64,32,64),('C',44,64,52,56,61,47),('L',61,70),('C',55,68,52,70,46,70),('L',30,70),('C',11,70,3,57,3,42),('L',3,6),('C',3,3,2,1,0,0)]])
    # The large crop shows slab-like silver faces: the earlier slender stems
    # reproduced only the bright outline, losing the width of the actual metal.
    glyphs['Q']=(491,477,1.83,1.80,[[('M',21,0),('C',5,8,0,20,0,33),('C',0,52,12,65,28,69),('L',28,78),('C',28,84,32,91,34.5,95),('C',38,88,41,79,41,69),('C',57,65,69,50,69,32),('C',69,19,62,7,49,0),('C',56,6,61,16,61,29),('C',61,44,53,53,41,56),('L',41,46),('C',41,44,43,43,45,43),('L',24,43),('C',27,44,28,45,28,47),('L',28,56),('C',15,53,8,44,8,30),('C',8,17,12,7,21,0)]])
    glyphs['U']=(650,477,1.84,1.72,[[('M',0,0),('L',25,0),('C',21,1,20,3,20,6),('L',20,46),('C',20,57,24,62,34,62),('C',44,62,49,57,49,46),('L',49,6),('C',49,3,47,1,43,0),('L',67,0),('C',64,1,63,3,63,6),('L',63,43),('C',63,59,50,71,34,71),('C',16,71,3,59,3,43),('L',3,6),('C',3,3,2,1,0,0)]])
    glyphs['K']=(953,474,1.83,1.74,[[('M',0,0),('L',22,0),('C',18,1,17,3,17,7),('L',17,25),('C',17,29,19,31,24,32),('L',70,-2),('L',43,30),('C',62,35,67,49,67,70),('C',61,51,44,41,24,38),('C',20,37,17,39,17,44),('L',17,64),('C',17,68,19,69,22,70),('L',0,70),('C',3,69,3,67,3,62),('L',3,7),('C',3,3,3,1,0,0)]])
    glyphs['E']=(1114,475,1.89,1.75,[[('M',0,0),('L',56,0),('L',56,23),('C',51,11,43,8,25,8),('L',21,8),('C',18,8,17,9,17,12),('L',17,25),('C',17,30,21,32,29,34),('C',21,36,17,38,17,43),('L',17,48),('C',17,58,22,62,33,62),('C',45,62,52,56,61,47),('L',61,70),('C',55,68,52,70,46,70),('L',30,70),('C',11,70,1.5,57,1.5,42),('L',1.5,6),('C',1.5,3,1,1,0,0)]])
    glyphs['4']=(1298,472,1.90,1.65,[[('M',50,0),('L',50,57),('L',65,57),('C',70,57,72,54,74,51),('L',70,70),('L',50,70),('L',50,87),('C',50,93,54,95,59,96),('L',28,96),('C',35,94,37,93,37,88),('L',37,70),('L',0,70)],[('M',36,24),('L',13,57),('L',37,57)]])
    for ob in PARTS['letters']:
        label=ob['character'];dx,dy,sx,sy,paths=glyphs[label]
        transform=lambda x,y:((dx+x*sx-960)/105-ob.location.x,(540-dy-y*sy)/105)
        ob.modifiers.clear();ob.data=sculpted_letter(label,paths,transform)
        ob.visible_shadow=False
        ob['construction']='Authored cubic outline with bounded real sculpted chamfer, closed back and side walls. 0.030-unit broad bevel; no miter spikes.'
        from remaster_scene import bezier_shape
        master=bpy.data.objects['RM editable master / '+label]
        temporary=bezier_shape('RM parity letter authoring template',[p for p in paths],M['RM | silver title'],C['RM 04b / Editable letter masters'],depth=.34,edge=0,transform=transform)
        master.data=temporary.data;master.data.bevel_depth=0;master.data.resolution_u=32
        bpy.data.objects.remove(temporary,do_unlink=True)
        print('Sculpted',label,len(ob.data.vertices),'vertices')
    bpy.data.objects['RM Q insignia / precise iron silhouette'].visible_shadow=False


def eye():
    prepare();col=C['RM 02 / Eye carrier and clamps'];parent=bpy.data.objects['RM MECHANISM / recessed ocular bearing']
    for name in ['RM steel optical bezel','RM inner brass optical retaining lip','RM recessed optical seat']:
        ob=bpy.data.objects.get(name)
        if ob:bpy.data.objects.remove(ob,do_unlink=True)
    seat=lathe('RM recessed optical seat',[(.70,.81),(.98,.81),(.987,.99),(.947,1.061),(.775,1.088),(.70,1.02)],M['RM | deep recess'],col,parent=parent)
    bezel=lathe('RM steel optical bezel',[(.724,.99),(.926,.99),(.950,1.044),(.939,1.099),(.884,1.132),(.830,1.148),(.778,1.153),(.727,1.12)],M['RM | shadowed olive armor'],col,parent=parent)
    lip=lathe('RM inner brass optical retaining lip',[(.714,1.14),(.747,1.14),(.764,1.161),(.749,1.178),(.723,1.177),(.714,1.157)],M['RM | steel exposed edges'],col,parent=parent)
    for o in [seat,bezel,lip]:o.scale.x=1.10;o.location.y=.025
    for name in ['RM wet red optical lens','RM IRIS / fine crimson radial fibers','RM PUPIL / polished black aperture']:
        o=bpy.data.objects[name]
        if not o.get('parity_aspect_corrected'):
            for v in o.data.vertices:v.co.x*=1.10
            o['parity_aspect_corrected']=True
        o.location.y=.025
    # Reference aperture is smaller and the red transition much less like a
    # hard black ring. Its clear coat still follows the physical convex surface.
    iris=M['RM | fine radial iris'];nt=iris.node_tree;bs=nt.nodes.get('Principled BSDF')
    hue=nt.nodes['Crimson settles to amber'];hue.inputs['Saturation'].default_value=.94;hue.inputs['Value'].default_value=.54
    old=hue.outputs['Color'];tint=mix(nt,old,(.12,.012,.015),.08)
    nt.links.new(tint,bs.inputs['Base Color']);nt.links.new(tint,bs.inputs['Emission Color']);bs.inputs['Emission Strength'].default_value=.16
    node_key(hue.inputs['Hue'],[(1,.49),(31,.49),(43,.525),(55,.555),(180,.555)])
    lens=M['RM | wet crimson lens'];nt=lens.node_tree;bs=nt.nodes.get('Principled BSDF')
    colors=nt.nodes['Deep red optical tissue'].color_ramp.elements
    nt.animation_data_clear()
    for i,e in enumerate(colors):
        e.color=[(.043,.007,.012,1),(.24,.027,.039,1)][min(i,1)]
        e.keyframe_insert('color',frame=1);e.keyframe_insert('color',frame=31)
        e.color=[(.027,.011,.002,1),(.20,.085,.008,1)][min(i,1)]
        e.keyframe_insert('color',frame=58);e.keyframe_insert('color',frame=180)
    bs.inputs['Roughness'].default_value=.29;bs.inputs['Coat Weight'].default_value=.65
    bs.inputs['Coat Roughness'].default_value=.1;bs.inputs['Emission Strength'].default_value=.15
    glint=bpy.data.objects['RM eye lens glint'];glint.location=(-1.4,1.35,4.8);aim(glint,(0,0,1.3));glint.data.energy=65;glint.data.size=.72;glint.data.size_y=.17
    relink_lights();print('Corrected elliptical optical seat and softer crimson cornea')


def jaws():
    prepare();col=C['RM 02 / Eye carrier and clamps'];steel=M['RM | forged clamp steel']
    for side in [-1,1]:
        parent=bpy.data.objects['RM articulated clamp jaw '+str(side)]
        for ob in list(parent.children):
            if not ob.name.startswith('RM clamp back bearing'):bpy.data.objects.remove(ob,do_unlink=True)
        # Broad planar lower casting, two raised lands, and wide slanted top fins.
        stations=[(1.03,2.77,3.94,.65),(.70,2.77,3.98,.87),(.34,2.78,4.025,.96),(-.37,2.79,4.055,.96),(-.61,2.78,4.035,.90),(-1.28,2.69,3.77,.63)]
        across=[(0,-.05),(.13,-.02),(.18,.06),(.34,.065),(.39,-.035),(.66,-.035),(.72,.045),(.87,.06),(1,-.065)]
        verts=[];nr=len(stations);nc=len(across)
        for k,(y,xa,xb,z) in enumerate(stations):
            for j,(t,dz) in enumerate(across):
                yy=y+(.16-.29*t if k==nr-1 else 0)
                if k==0:yy=[.72,.80,1.01,1.10,.77,.77,1.015,1.06,.70][j]
                verts.append((side*(xa+(xb-xa)*t),yy,z+dz))
        n=len(verts);verts.extend((x,y,.28) for x,y,z in verts.copy());faces=[]
        for k in range(nr-1):
            for j in range(nc-1):
                a=k*nc+j;faces.extend([(a,a+1,a+nc+1,a+nc),(a+n,a+nc+n,a+nc+1+n,a+1+n)])
        per=list(range(nc))+[r*nc+nc-1 for r in range(1,nr)]+list(range((nr-1)*nc+nc-2,(nr-1)*nc-1,-1))+[r*nc for r in range(nr-2,0,-1)]
        for i,a in enumerate(per):b=per[(i+1)%len(per)];faces.append((a,b,b+n,a+n))
        ob=mesh_part('RM planar twin-land forged jaw '+str(side),verts,faces,steel,col,.018,parent)
        ob['construction']='Planar lower casting, wide raised lands, slanted broad fin tops, three stepped transverse strap surfaces.'
        # Narrow contact seams replace the exaggerated floating gap.
        strap=[(2.20,.12),(4.045,.12),(4.065,-.13),(3.15,-.13),(3.055,-.23),(2.20,-.23)]
        upper=[(2.18,.43),(3.97,.43),(4.065,.355),(4.065,.18),(2.18,.18)]
        lower=[(2.23,-.265),(4.05,-.265),(4.02,-.41),(2.23,-.41)]
        for name,pts,z,depth in [('upper load strap',upper,1.14,.17),('stepped clamping strap',strap,1.18,.21),('lower rolled strap lip',lower,1.115,.16)]:
            plate('RM '+name+' '+str(side),[(side*x,y) for x,y in pts],z,depth,steel,col,.022,parent)
        cylinder('RM captive pivot counterbore',.194,.026,(side*2.76,-.015,1.19),M['RM | deep recess'],col,64,.01,parent)
        head=cylinder('RM rounded captive pivot',.177,.071,(side*2.76,-.015,1.217),steel,col,64,.022,parent)
        # Both cutter and head use the moving jaw's local coordinates. At the
        # held frame the jaw is 1.88 units outboard; an unparented cutter misses.
        slot=box('RM parity pivot cutting tool',(side*2.76,-.015,1.252),(.222,.032,.095),None,col,0,parent);slot.rotation_euler.z=-side*.47
        mod=head.modifiers.new('Recessed narrow pivot slot','BOOLEAN');mod.operation='DIFFERENCE';mod.object=slot
        bpy.context.view_layer.objects.active=head;bpy.ops.object.modifier_move_to_index(modifier=mod.name,index=0);bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(slot,do_unlink=True)
    relink_lights();print('Rebuilt clamp castings, triple strap relief and rounded captive pins')


def housing():
    prepare();col=C['RM 01 / Segmented bulkhead'];root=bpy.data.objects['RM BULKHEAD / measured armored housing'];wall=M['RM | military olive wall'];dark=M['RM | shadowed olive armor']
    for name in ['RM upper swept sector L','RM upper diagonal stepped armor L','RM large outer side cheek L','RM recessed left inspection port']:
        ob=bpy.data.objects.get(name)
        if ob:bpy.data.objects.remove(ob,do_unlink=True)
    # The trailer contains a narrow vertical machinery pocket beneath a moving
    # circular optical reticle. Its upper edge is out of sight in the darkness.
    contours=[('RM left inboard crown continuation',[(-2.47,7.05),(-3.84,6.56),(-4.34,5.88),(-4.28,2.45),(-3.17,.69),(-2.49,2.00)],-.015),
              ('RM left outer crown continuation',[(-5.63,5.02),(-5.17,4.48),(-5.78,3.54),(-6.14,2.58),(-6.81,1.32),(-6.93,-.40),(-6.42,-2.13),(-5.77,-2.25),(-5.70,-.52),(-5.43,-.46),(-5.45,2.54)],-.01),
              ('RM left lower pocket cheek',[(-4.29,1.04),(-3.15,.69),(-3.08,-.79),(-4.38,-1.09),(-4.80,-.45),(-4.42,-.46)],.005)]
    for name,pts,z in contours:plate(name,pts,z,.43,wall,col,.018,root)
    # Upper recessed vertical well, a soft cast shoulder and the deeper bottom
    # pocket remain separate solids and receive the real camera parallax.
    box('RM left vertical equipment pocket',(-4.92,2.58,-.38),(1.18,5.5,.22),M['RM | deep recess'],col,.05,root)
    plate('RM left pocket beveled outer shoulder',[(-5.54,5.15),(-5.38,5.25),(-5.33,-.55),(-5.49,-.71)],-.01,.25,dark,col,.045,root)
    plate('RM left recessed lower casting',[(-5.34,-.61),(-4.34,-.53),(-4.12,-1.72),(-5.29,-2.03)],-.085,.34,M['RM | forged clamp steel'],col,.026,root)
    # Remove the circular cutout's underlying unbroken annular armor surface.
    bed=bpy.data.objects['RM continuous recessed armor bed']
    cutter=box('RM parity pocket milling tool',(-4.92,2.58,-.35),(1.11,5.5,1.5),None,col,.035)
    mod=bed.modifiers.new('Actual vertical equipment recess','BOOLEAN');mod.operation='DIFFERENCE';mod.object=cutter
    bpy.context.view_layer.objects.active=bed;bpy.ops.object.modifier_move_to_index(modifier=mod.name,index=0);bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)
    # An enclosing bulkhead continues beyond the circular machinery; the old
    # model ended in a crisp silhouette against an empty black world.
    box('RM enclosing recessed bulkhead',(0,0,-2.25),(25,19,.65),dark,col,.05,root)
    for side in [-1,1]:
        for y in [-4.8,-1.5,2.0,5.2]:
            plate('RM outer interrupted casing cover',[(side*7.7,y),(side*10.4,y+.3),(side*10.4,y+3.05),(side*8.05,y+2.6)],-1.35,.35,dark,col,.055,root)
    relink_lights();print('Replaced invented circular bore with layered vertical equipment pocket')


def surfaces():
    prepare()
    for name,low,high in [('RM | faceplate yellow olive',(.181,.221,.040),(.302,.352,.080)),('RM | military olive wall',(.054,.065,.020),(.184,.211,.063)),('RM | shadowed olive armor',(.026,.033,.014),(.095,.112,.037))]:
        mat,nt,bs,co=shader(name)
        broad=noise(nt,co,1.3,4,'Broad uneven military coating')
        col=ramp(nt,broad,[(.15,low),(.82,high)],'Measured olive pigment')
        stripes=noise(nt,scaled(nt,co,(28,.5,5)),2.1,2,'Long rubbed vertical coating')
        streak=ramp(nt,stripes,[(.16,(.34,.38,.24)),(.72,(1,1,1))],'Subtle directional scuffing')
        col=mix(nt,col,streak,.28,'MULTIPLY')
        mottled=ramp(nt,noise(nt,co,31,4,'Fine irregular weathering'),[(.32,(.16,.19,.10)),(.66,(1,1,1))],'Broken fine coating grain')
        col=mix(nt,col,mottled,.60,'MULTIPLY')
        patches=noise(nt,scaled(nt,co,(2.4,.7,1)),7.2,4,'Localized worn coating islands')
        mask=ramp(nt,patches,[(.56,(0,0,0)),(.74,(1,1,1))],'Sparse clustered coating failures')
        col=mix(nt,col,(.041,.046,.014),mask)
        geom=nt.nodes.new('ShaderNodeNewGeometry');sep=nt.nodes.new('ShaderNodeSeparateXYZ');nt.links.new(geom.outputs['Position'],sep.inputs[0])
        grad=nt.nodes.new('ShaderNodeMapRange');grad.name='Upper coating light falloff'
        grad.inputs['From Min'].default_value=.6 if 'faceplate' in name else 1.8;grad.inputs['From Max'].default_value=1.9 if 'faceplate' in name else 5.2
        grad.inputs['To Min'].default_value=1;grad.inputs['To Max'].default_value=.82 if 'faceplate' in name else .28
        nt.links.new(sep.outputs['Y'],grad.inputs['Value']);col=mix(nt,col,grad.outputs[0],1,'MULTIPLY')
        nt.links.new(col,bs.inputs['Base Color']);bs.inputs['Metallic'].default_value=.18;bs.inputs['Roughness'].default_value=.78
        nt.links.new(col,bs.inputs['Emission Color']);bs.inputs['Emission Strength'].default_value=.075 if 'faceplate' in name else .020
        bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.26;bump.inputs['Distance'].default_value=.008
        nt.links.new(noise(nt,co,165,3,'Fine cast enamel tooth'),bump.inputs['Height']);nt.links.new(bump.outputs[0],bs.inputs['Normal'])
    mat,nt,bs,co=shader('RM | forged clamp steel')
    col=ramp(nt,noise(nt,scaled(nt,co,(2,8,2)),3.4,4),[(.15,(.028,.029,.037)),(.8,(.095,.097,.120))],'Scoured blue-gray cast steel')
    nt.links.new(col,bs.inputs['Base Color']);bs.inputs['Metallic'].default_value=.42;bs.inputs['Roughness'].default_value=.66
    bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.25;bump.inputs['Distance'].default_value=.007;nt.links.new(noise(nt,co,85,3),bump.inputs['Height']);nt.links.new(bump.outputs[0],bs.inputs['Normal'])
    nt.links.new(col,bs.inputs['Emission Color']);bs.inputs['Emission Strength'].default_value=.018
    mat,nt,bs,co=shader('RM | iron emblem')
    grain=noise(nt,co,46,3,'Visible granular charcoal forging')
    col=ramp(nt,grain,[(.28,(.0001,.0002,.0003)),(.48,(.0005,.0008,.001)),(.61,(.009,.010,.012)),(.73,(.023,.025,.027))],'Uneven charcoal pits')
    nt.links.new(col,bs.inputs['Base Color']);nt.links.new(col,bs.inputs['Emission Color']);bs.inputs['Emission Strength'].default_value=.42;bs.inputs['Metallic'].default_value=.04;bs.inputs['Roughness'].default_value=.97
    bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.73;bump.inputs['Distance'].default_value=.017;nt.links.new(grain,bump.inputs['Height']);nt.links.new(bump.outputs[0],bs.inputs['Normal'])
    edge=bpy.data.materials['RM | soft radioactive edge'];nt=edge.node_tree
    nt.nodes['Irregular worn edge phosphor'].inputs['Scale'].default_value=37
    nt.nodes['Upper horn light falloff'].inputs['To Max'].default_value=.10
    node_key(nt.nodes['Logo edge reveal'].inputs[1],[(1,0),(31,.009),(37,.09),(43,.33),(55,.43),(180,.43)])
    rim=bpy.data.objects['RM Q insignia / subdued green worn perimeter'];rim.data.bevel_depth=.022
    for spl in rim.data.splines:
        for i,p in enumerate(spl.points):p.radius=.77+.23*math.sin(i*1.74)+.10*math.sin(i*.49)
    rim.visible_shadow=False
    s=bpy.context.scene;s.node_tree.nodes['RM diffuse green edge bloom'].inputs['Size'].default_value=(15,15)
    s.node_tree.nodes['RM reference soft emblem irradiation'].inputs[0].default_value=3.4
    s.node_tree.nodes['RM soft edge light spill'].inputs['Strength'].default_value=.38
    s.node_tree.nodes['RM soft edge light spill'].inputs['Size'].default_value=.46
    silver=M['RM | silver title'];nt=silver.node_tree;bs=nt.nodes.get('Principled BSDF')
    source=bs.inputs['Base Color'].links[0].from_socket
    nt.links.new(source,bs.inputs['Emission Color']);bs.inputs['Emission Strength'].default_value=.10;bs.inputs['Metallic'].default_value=.85
    bpy.data.objects['RM white title reflection card'].data.energy=750
    for name,loc,power,size in [('RM silver chamfer left reflection',(-8,3,7),600,9),('RM silver chamfer right reflection',(8,-1,6),700,9),('RM silver chamfer lower reflection',(0,-7,5),450,8)]:
        old=bpy.data.objects.get(name)
        if old:bpy.data.objects.remove(old,do_unlink=True)
        lamp=light(name,'AREA',loc,power,(.86,.90,1),size,C['RM 00 / Camera and studio'],target=(0,0,2.6));lamp.light_linking.receiver_collection=C['RM 04 / Silver letterforms']
    bpy.data.objects['RM low machinery bounce'].data.energy=110
    bpy.data.objects['RM broad wall bounce'].data.energy=560
    for ob in PARTS['letters']:ob.visible_shadow=False
    bpy.data.objects['RM Q insignia / precise iron silhouette'].visible_shadow=False
    for ob in C['RM 01 / Segmented bulkhead'].objects:
        if ob.name.startswith('RM deep interleaved shroud shoulder'):
            ob.data.materials.clear();ob.data.materials.append(M['RM | shadowed olive armor'])
    collar=bpy.data.objects['RM rounded teal socket collar']
    collar.data.materials[1]=M['RM | military olive wall']
    print('Replaced evenly speckled paint with fine grain, directional scuffs and localized wear')


def overlays():
    prepare()
    for ob in C['RM 07 / Animated optical overlays'].objects:
        if ob.type!='CURVE':continue
        if any(w in ob.name for w in ['nested circle','oblique signal','glyph stroke']):ob.data.bevel_depth=.013
        elif 'soft fringe' in ob.name:ob.data.bevel_depth=.04
        if 'left nested circle' in ob.name or 'left circle soft fringe' in ob.name:
            spl=ob.data.splines[0]
            radius=math.hypot(spl.points[0].co.x,spl.points[0].co.y)
            # The two outer contours turn into parallel leads. Their small
            # lower-right opening is visible in the source's held frames.
            if radius>1.05:
                spl.use_cyclic_u=False
                for i,p in enumerate(spl.points):
                    a=math.radians(-21+336*i/(len(spl.points)-1))
                    p.co=(radius*math.cos(a),radius*math.sin(a),0,1)
    for name,opacity,color in [('RM | floating circuit pale olive',.19,(.17,.20,.095)),('RM | circuit soft optical fringe',.030,(.17,.20,.095))]:
        nt=bpy.data.materials[name].node_tree
        emit=next(n for n in nt.nodes if n.bl_idname=='ShaderNodeEmission');emit.inputs[0].default_value=(*color,1)
        replace_socket(nt.nodes['Overlay reveal envelope'].inputs[1],[(1,0),(39,0),(49,opacity*.26),(55,opacity*.73),(61,opacity),(121,opacity),(151,opacity*.90),(180,opacity*.75)])
    print('Softened and widened moving technical overlays')


def secondary_geometry():
    """Reduce invented trim and give the lower machinery the observed mass."""
    prepare();col=C['RM 01 / Segmented bulkhead'];root=bpy.data.objects['RM BULKHEAD / measured armored housing']
    for ob in list(col.objects):
        if ob.name.startswith('RM load arm inner landing'):
            bpy.data.objects.remove(ob,do_unlink=True)
        elif ob.name.startswith('RM wide lower diagonal load arm') and not ob.get('measured_arm_width'):
            side=-1 if ob.name.endswith(' L') else 1
            for v in ob.data.vertices:
                x=side*v.co.x;y=v.co.y;cross=(x+y)*.5
                v.co.x-=side*cross*.18;v.co.y-=cross*.18
            ob['measured_arm_width']=True
    mat=bpy.data.materials.get('RM | recessed utility steel')
    if not mat:
        mat=M['RM | forged clamp steel'].copy();mat.name='RM | recessed utility steel'
    M[mat.name]=mat
    _,nt,bs,co=shader(mat.name)
    color=ramp(nt,noise(nt,scaled(nt,co,(4,1,2)),13,4),[(.28,(.022,.027,.022)),(.68,(.062,.069,.049))],'Weathered low equipment')
    nt.links.new(color,bs.inputs['Base Color']);bs.inputs['Metallic'].default_value=.12;bs.inputs['Roughness'].default_value=.89
    for ob in col.objects:
        if any(w in ob.name for w in ['radiator vane','stepped utility channel']):
            ob.data.materials.clear();ob.data.materials.append(mat)
    # The left recess has broad bent ribs rather than a bright regular grille.
    for ob in list(col.objects):
        if ob.name.startswith('RM broad cast radiator vane') and ob.location.x<0:
            bpy.data.objects.remove(ob,do_unlink=True)
        elif ob.name.startswith('RM broad bent lower cooling rib'):
            bpy.data.objects.remove(ob,do_unlink=True)
    from remaster_mechanics import sweep
    for i in range(6):
        y=-3.88-i*.32
        sweep('RM broad bent lower cooling rib',[(-2.59,y-.09,-.005),(-2.35,y+.05,.04),(-1.84,y+.04,.06),(-1.40,y-.015,.01)],.22,.26,mat,col,root)
    relink_lights()


def clear_property(owner,path):
    target=owner if hasattr(owner,'animation_data') else owner.id_data
    fullpath=path if target is owner else owner.path_from_id(path)
    action=target.animation_data.action if target.animation_data else None
    if action:
        for fc in list(action.fcurves):
            if fc.data_path==fullpath:action.fcurves.remove(fc)


def replace_keys(owner,path,values,linear=False):
    clear_property(owner,path);key(owner,path,values)
    if linear:
        for fc in owner.animation_data.action.fcurves:
            if fc.data_path==path:
                for p in fc.keyframe_points:p.interpolation='LINEAR'


def replace_socket(socket,values,linear=False):
    owner=socket.id_data;path=socket.path_from_id('default_value');clear_property(owner,path);node_key(socket,values)
    if linear:
        for fc in owner.animation_data.action.fcurves:
            if fc.data_path==path:
                for p in fc.keyframe_points:p.interpolation='LINEAR'


def timing():
    prepare();s=bpy.context.scene;nt=s.node_tree;n,l=nt.nodes,nt.links
    camera=s.camera
    replace_keys(camera,'location',[(1,(0,0,5)),(9,(0,0,5.2)),(10,(0,0,5.8)),(13,(0,0,8.4)),(19,(0,0,15.0)),(25,(0,0,15.8)),(31,(0,0,16.3)),(37,(0,0,18.563)),(43,(0,0,21)),(61,(0,0,24.2)),(91,(0,0,26.3)),(121,(0,0,28)),(151,(0,0,29.6)),(181,(0,0,31.15))])
    title=PARTS['title']
    # At 121.20 s the white stem spans about x994–1374 at y120. Reposition
    # the now-broader solid K so the near-camera crossing keeps that width.
    replace_keys(title,'location',[(1,(0,0,22)),(33,(0,0,22)),(37,(.14,0,14.3)),(40,(.02,0,15.0)),(43,(0,0,11.66)),(46,(0,0,6.74)),(49,(0,0,3.79)),(55,(0,0,2.294)),(62,(0,0,2.6)),(181,(0,0,2.6))])
    replace_keys(title,'scale',[(1,(1.8,)*3),(33,(1.8,)*3),(37,(1.8,)*3),(40,(1.64,)*3),(43,(1.16,)*3),(46,(1.051,)*3),(49,(1.001,)*3),(55,(.99,)*3),(62,(1,)*3),(181,(1,)*3)])
    for ob in PARTS['letters']:
        # At the crossing the source contains the K's bright vertical stem.
        # The remaining characters enter just afterwards, during the retreat.
        reveal=34 if ob['character']=='K' else 39
        for path in ['hide_render','hide_viewport']:replace_keys(ob,path,[(1,True),(reveal-1,True),(reveal,False)],True)
    replace_socket(M['RM | silver title'].node_tree.nodes['Principled BSDF'].inputs['Emission Strength'],[(1,.16),(33,.16),(37,65),(40,12),(43,.7),(49,.16),(181,.16)])
    core=bpy.data.objects['RM FLASH / transient optical core']
    replace_keys(core,'location',[(1,(-.16,.14,1.61)),(31,(-.16,.14,1.61)),(34,(0,.06,1.61)),(181,(0,.06,1.61))])
    replace_keys(core,'scale',[(1,(.001,)*3),(9,(.001,)*3),(10,(.13,.13,.025)),(13,(.12,.12,.025)),(19,(.06,.06,.010)),(25,(.014,.014,.008)),(31,(.001,)*3),(34,(.001,)*3),(37,(.22,.22,.035)),(40,(.19,.19,.03)),(43,(.14,.14,.03)),(49,(.065,.065,.015)),(55,(.024,.024,.006)),(61,(.002,)*3),(181,(.002,)*3)])
    flash_values=[(1,0),(9,0),(10,500),(13,280),(19,90),(25,2),(31,0),(34,0),(37,650),(40,420),(43,200),(49,35),(55,3),(61,0),(181,0)]
    mt=M['RM | flash'].node_tree;replace_socket(mt.nodes['Principled BSDF'].inputs['Emission Strength'],flash_values)
    replace_socket(mt.nodes['RM optical source radiance'].inputs['Scale'],[(f,v*(3 if f<=31 else 4)) for f,v in flash_values])
    replace_socket(mt.nodes['Principled BSDF'].inputs['Emission Color'],[(1,(.90,.55,.74,1)),(31,(.90,.55,.74,1)),(34,(.20,.65,1,1)),(181,(.20,.65,1,1))])
    source_color=mt.nodes['RM optical source radiance'].inputs[0].links[0].from_socket
    replace_socket(source_color,[(1,(.85,.30,.55,1)),(31,(.85,.30,.55,1)),(34,(.20,.65,1,1)),(181,(.20,.65,1,1))])
    lamp=bpy.data.objects['RM blue flash illumination'];replace_keys(lamp.data,'energy',[(f,v*(.25 if f<=31 else 1.9)) for f,v in flash_values])
    replace_keys(lamp.data,'color',[(1,(.55,.67,1)),(31,(.55,.67,1)),(34,(.12,.62,1)),(181,(.12,.62,1))])
    replace_socket(n['RM transient radial lens smear'].inputs['Scale'],[(1,1),(9,1),(10,1.85),(13,1.70),(19,1.18),(25,1.025),(31,1),(34,1),(37,1.40),(43,1.43),(49,1.24),(55,1.07),(61,1.008),(67,1),(181,1)])
    replace_socket(n['RM narrow cyan optical streak'].inputs[0],[(1,0),(9,0),(10,2.8),(13,2.5),(19,1.3),(25,.16),(31,0),(34,0),(37,3.0),(40,2.4),(43,2.2),(49,.6),(55,.12),(61,.015),(67,0),(181,0)])
    # Spreading a finite bright disk horizontally creates a thick bar. Keep
    # only the narrow continuous anamorphic profile and round halo diffusion.
    n['RM smooth flare / add horizontal spread'].inputs[0].default_value=0
    n['RM smooth flare / core diffusion'].inputs['Size'].default_value=(155,155)
    n['RM smooth flare / broad veil'].inputs['Size'].default_value=(260,220)
    n['RM smooth flare / add broad veil'].inputs[0].default_value=.10
    replace_socket(n['RM anamorphic lens streak profile'].inputs['Position'],[(1,(.5,.565)),(19,(.5,.535)),(31,(.5,.5)),(181,(.5,.5))])
    replace_socket(n['RM anamorphic lens streak profile'].inputs['Size'],[(1,(1.15,.004)),(181,(1.15,.004))])
    n['RM anamorphic lens streak profile'].outputs[0].links[0].to_node.inputs['Size'].default_value=(230,24)
    replace_socket(n['RM optical vignette'].inputs[0],[(1,.86),(9,.86),(10,.42),(13,.48),(19,.86),(181,.86)])
    # The physical title crosses the lens during the white-blue rush. A broad
    # additive optical veil models the observed flare scattering during that
    # crossing; all machinery and letters remain the 3D render beneath it.
    for node in list(n):
        if node.name.startswith('RM parity optical '):n.remove(node)
    # Derive the pupil's brief preserved dark-blue core from its actual 3D AOV.
    # This is an optical bloom occlusion mask, not a replacement eye image.
    pupil_pass='RM Pupil optical occlusion'
    if not any(a.name==pupil_pass for a in s.view_layers[0].aovs):
        a=s.view_layers[0].aovs.add();a.name=pupil_pass;a.type='COLOR'
    pnt=M['RM | pupil'].node_tree
    aov=pnt.nodes.get('RM pupil physical mask') or pnt.nodes.new('ShaderNodeOutputAOV');aov.name='RM pupil physical mask';aov.aov_name=pupil_pass;aov.inputs['Color'].default_value=(1,1,1,1)
    # Continue the same projected aperture mask through the small flare source
    # that passes in front of it, avoiding an artificial crescent-shaped pupil.
    for old in list(mt.nodes):
        if old.name.startswith('RM pupil mask through flare'):mt.nodes.remove(old)
    geom=mt.nodes.new('ShaderNodeNewGeometry');geom.name='RM pupil mask through flare coordinates'
    offset=mt.nodes.new('ShaderNodeVectorMath');offset.name='RM pupil mask through flare offset';offset.operation='SUBTRACT';offset.inputs[1].default_value=(0,.025,1.61);mt.links.new(geom.outputs['Position'],offset.inputs[0])
    scale=mt.nodes.new('ShaderNodeVectorMath');scale.name='RM pupil mask through flare aspect';scale.operation='MULTIPLY';scale.inputs[1].default_value=(1/.2365,1/.215,0);mt.links.new(offset.outputs[0],scale.inputs[0])
    length=mt.nodes.new('ShaderNodeVectorMath');length.name='RM pupil mask through flare radius';length.operation='LENGTH';mt.links.new(scale.outputs[0],length.inputs[0])
    limit=mt.nodes.new('ShaderNodeMath');limit.name='RM pupil mask through flare boundary';limit.operation='LESS_THAN';limit.inputs[1].default_value=1;mt.links.new(length.outputs['Value'],limit.inputs[0])
    av=mt.nodes.new('ShaderNodeOutputAOV');av.name='RM pupil mask through flare output';av.aov_name=pupil_pass;mt.links.new(limit.outputs[0],av.inputs['Color'])
    # Diffraction rays come from a compact physical point on the flash surface.
    # A material AOV avoids dilating the full glowing disk into wide petals.
    point_pass='RM Optical diffraction point'
    if not any(a.name==point_pass for a in s.view_layers[0].aovs):
        a=s.view_layers[0].aovs.add();a.name=point_pass;a.type='COLOR'
    for old in list(mt.nodes):
        if old.name.startswith('RM diffraction point'):mt.nodes.remove(old)
    po=mt.nodes.new('ShaderNodeVectorMath');po.name='RM diffraction point center';po.operation='SUBTRACT';mt.links.new(geom.outputs['Position'],po.inputs[0])
    replace_socket(po.inputs[1],[(1,(-.16,.14,1.61)),(31,(-.16,.14,1.61)),(34,(0,.06,1.61)),(181,(0,.06,1.61))])
    ps=mt.nodes.new('ShaderNodeVectorMath');ps.name='RM diffraction point plane';ps.operation='MULTIPLY';ps.inputs[1].default_value=(1,1,0);mt.links.new(po.outputs[0],ps.inputs[0])
    pl=mt.nodes.new('ShaderNodeVectorMath');pl.name='RM diffraction point radius';pl.operation='LENGTH';mt.links.new(ps.outputs[0],pl.inputs[0])
    pm=mt.nodes.new('ShaderNodeMath');pm.name='RM diffraction point compact aperture';pm.operation='LESS_THAN';pm.inputs[1].default_value=.03;mt.links.new(pl.outputs['Value'],pm.inputs[0])
    pr=mt.nodes.new('ShaderNodeVectorMath');pr.name='RM diffraction point radiance';pr.operation='SCALE';mt.links.new(mt.nodes['RM optical source radiance'].outputs[0],pr.inputs[0]);mt.links.new(pm.outputs[0],pr.inputs['Scale'])
    pa=mt.nodes.new('ShaderNodeOutputAOV');pa.name='RM diffraction point output';pa.aov_name=point_pass;mt.links.new(pr.outputs[0],pa.inputs['Color'])
    bpy.context.view_layer.update()
    render=next(node for node in n if node.bl_idname=='CompositorNodeRLayers')
    star=n.new('CompositorNodeGlare');star.name='RM parity optical short radial star';star.glare_type='STREAKS';star.quality='HIGH';star.streaks=11;star.angle_offset=.22
    star.inputs['Iterations'].default_value=3;star.inputs['Fade'].default_value=.85;star.inputs['Color Modulation'].default_value=.3;star.inputs['Threshold'].default_value=1;star.inputs['Strength'].default_value=1.5
    star.inputs['Tint'].default_value=(1,.33,.27,1)
    # Diffraction is a low-frequency optical pass. Evaluate it at quarter
    # resolution, then restore full size; the 3D beauty remains full resolution.
    small=n.new('CompositorNodeScale');small.name='RM parity optical diffraction working resolution';small.space='RELATIVE';small.inputs[1].default_value=.25;small.inputs[2].default_value=.25
    l.new(render.outputs[point_pass],small.inputs[0]);l.new(small.outputs[0],star.inputs['Image'])
    full=n.new('CompositorNodeScale');full.name='RM parity optical diffraction full frame';full.space='RELATIVE';full.inputs[1].default_value=4;full.inputs[2].default_value=4;l.new(star.outputs['Glare'],full.inputs[0])
    diffuse=n.new('CompositorNodeBlur');diffuse.name='RM parity optical diffraction diffusion';diffuse.filter_type='GAUSS';diffuse.inputs['Size'].default_value=(18,18);l.new(full.outputs[0],diffuse.inputs[0])
    staradd=n.new('CompositorNodeMixRGB');staradd.name='RM parity optical short radial add';staradd.blend_type='ADD'
    l.new(n['RM narrow cyan optical streak'].outputs[0],staradd.inputs[1]);l.new(diffuse.outputs[0],staradd.inputs[2])
    replace_socket(staradd.inputs[0],[(1,0),(9,0),(10,.55),(13,.45),(19,.1),(25,0),(181,0)])
    switch=n.new('CompositorNodeSwitch');switch.name='RM parity optical diffraction interval'
    l.new(n['RM narrow cyan optical streak'].outputs[0],switch.inputs[0]);l.new(staradd.outputs[0],switch.inputs[1])
    replace_keys(switch,'check',[(1,False),(9,False),(10,True),(24,True),(25,False),(181,False)])
    erode=n.new('CompositorNodeDilateErode');erode.name='RM parity optical reduced pupil core';erode.mode='DISTANCE';l.new(render.outputs[pupil_pass],erode.inputs['Mask'])
    replace_socket(erode.inputs['Size'],[(1,-55),(13,-48),(19,-12),(25,-3),(31,0),(181,0)])
    smooth=n.new('CompositorNodeBlur');smooth.name='RM parity optical pupil fringe';smooth.filter_type='GAUSS';smooth.inputs['Size'].default_value=(12,12);l.new(erode.outputs[0],smooth.inputs['Image'])
    mask=n.new('CompositorNodeMath');mask.name='RM parity optical pupil hold';mask.operation='MULTIPLY';l.new(smooth.outputs[0],mask.inputs[0])
    replace_socket(mask.inputs[1],[(1,0),(9,0),(10,1),(13,1),(19,.91),(25,.10),(31,0),(181,0)])
    preserve=n.new('CompositorNodeMixRGB');preserve.name='RM parity optical preserved pupil';preserve.inputs[2].default_value=(.025,.55,1,1)
    l.new(mask.outputs[0],preserve.inputs[0]);l.new(switch.outputs[0],preserve.inputs[1])
    veil=n.new('CompositorNodeMixRGB');veil.name='RM parity optical title veil';veil.blend_type='ADD';veil.inputs[2].default_value=(.10,.56,1.0,1)
    original=preserve.outputs[0];l.new(original,veil.inputs[1]);l.new(veil.outputs[0],n['RM optical vignette'].inputs[1])
    replace_socket(veil.inputs[0],[(1,0),(34,0),(37,.64),(40,.29),(43,.10),(49,.015),(55,0),(181,0)])
    tint=n.new('CompositorNodeMixRGB');tint.name='RM parity optical cyan scattering';tint.blend_type='MULTIPLY';tint.inputs[0].default_value=1;tint.inputs[2].default_value=(.012,.70,1.20,1)
    l.new(veil.outputs[0],tint.inputs[1])
    level=n.new('CompositorNodeRGBToBW');level.name='RM parity optical white crossing luminance';l.new(veil.outputs[0],level.inputs[0])
    white=n.new('CompositorNodeMapRange');white.name='RM parity optical retain white crossing';white.inputs['From Min'].default_value=2;white.inputs['From Max'].default_value=8;white.use_clamp=True;l.new(level.outputs[0],white.inputs[0])
    merge=n.new('CompositorNodeMixRGB');merge.name='RM parity optical cyan with white highlights';l.new(white.outputs[0],merge.inputs[0]);l.new(tint.outputs[0],merge.inputs[1]);l.new(veil.outputs[0],merge.inputs[2])
    envelope=n.new('CompositorNodeMixRGB');envelope.name='RM parity optical cyan burst envelope';l.new(veil.outputs[0],envelope.inputs[1]);l.new(merge.outputs[0],envelope.inputs[2]);l.new(envelope.outputs[0],n['RM optical vignette'].inputs[1])
    replace_socket(envelope.inputs[0],[(1,0),(34,0),(37,1),(40,.62),(43,.10),(49,0),(181,0)])
    fade=n['RM opening and closing fade']
    # The requested range includes 0.3 seconds from the preceding gameplay shot.
    # Keep those frames black in this title-only scene, with the exact title cut.
    replace_socket(fade.inputs[2],[(f,(v,v,v,1)) for f,v in [(1,0),(9,0),(10,1),(181,1)]],True)
    source=fade.outputs[0]
    # A source-video fade attenuates displayed brightness, not scene radiance.
    # Measured view-response curves keep a white silver highlight and a dim
    # background fading together instead of letting the highlight hang on.
    table=np.array(json.loads((Path(__file__).parent/'display_transfer.json').read_text())['samples'])
    linear,display=table[:,0],table[:,1]
    knots=[0]+np.geomspace(.0001,128,65).tolist()
    for previous,frame,alpha in [(145,151,.89),(151,157,.67),(157,163,.45),(163,169,.23),(169,175,.008),(175,181,0)]:
        curve=n.new('CompositorNodeCurveRGB');curve.name='RM parity optical display fade '+str(frame)
        mapping=curve.mapping;mapping.use_clip=False;mapping.clip_min_x=0;mapping.clip_max_x=128;mapping.clip_min_y=0;mapping.clip_max_y=128
        master=mapping.curves[3]
        for p in list(master.points)[2:]:master.points.remove(p)
        mapped=np.interp(np.interp(knots,linear,display)*alpha,display,linear)
        master.points[0].location=(0,0);master.points[1].location=(128,float(mapped[-1]))
        for x,y in zip(knots[1:-1],mapped[1:-1]):master.points.new(float(x),float(y))
        for p in master.points:p.handle_type='VECTOR'
        mapping.update();l.new(fade.outputs[0],curve.inputs['Image'])
        blend=n.new('CompositorNodeMixRGB');blend.name='RM parity optical display transition '+str(frame)
        l.new(source,blend.inputs[1]);l.new(curve.outputs[0],blend.inputs[2])
        replace_socket(blend.inputs[0],[(1,0),(previous,0),(frame,1),(181,1)],True)
        source=blend.outputs[0]
    # Subtle low-end olive veiling is present through the source's dark frames.
    lift=n.get('RM parity optical dark floor') or n.new('CompositorNodeMixRGB');lift.name='RM parity optical dark floor';lift.blend_type='ADD';lift.inputs[0].default_value=1;lift.inputs[2].default_value=(.0089,.0089,.0065,1)
    l.new(source,lift.inputs[1]);l.new(lift.outputs[0],n['Composite'].inputs[0])
    camera.data.dof.use_dof=True;camera.data.dof.aperture_fstop=.35
    s.render.motion_blur_shutter=.60
    camera.data.dof.focus_object=None
    focus=[]
    for f in [1,9,10,13,19,25,31,37,43,61,91,121,151,181]:
        s.frame_set(f);focus.append((f,camera.location.z-(1.5 if f<=31 else 2.6)))
    replace_keys(camera.data.dof,'focus_distance',focus)
    for marker in s.timeline_markers:
        if marker.name=='White-blue optical flash':marker.frame=10
        elif marker.name=='Title reveal flash':marker.frame=37
        elif marker.name=='Silver letterforms rush in':marker.frame=34
        elif marker.name=='Fade begins':marker.frame=145
    s.frame_set(121);print('Aligned cut, two distinct flash envelopes, title rush and closing attenuation')


def apply():
    letters();eye();jaws();housing();surfaces();secondary_geometry();overlays();timing()
    bpy.context.scene['revision']='Fifth construction: 31-point 200 ms reference audit; sculpted silver bevels, revised optical seat, layered clamps and vertical background recess.'
    bpy.context.scene.frame_set(121)
