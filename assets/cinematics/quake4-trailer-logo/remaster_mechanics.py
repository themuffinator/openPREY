"""Measured hard-surface replacement for the trailer's mechanical background.

XY is the trailer image plane; positive Z faces the camera. The ocular assembly
is measured at 121.0 s, and the broad housing at 124.0 s. No reference pixels
are used as visible surfaces. Jaws, channels, panel gaps and bearings are solids.
"""
import bpy, math, bmesh
from mathutils import Vector
from scene_common import C, M, box, cylinder, tube, empty, key, bevel, solid_outline
from remaster_scene import PARTS, lathe


def mesh_part(name, vertices, faces, mat, col, edge=.012, parent=None):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    ob=bpy.data.objects.new(name,mesh);col.objects.link(ob);mesh.materials.append(mat)
    if parent:ob.parent=parent
    if edge:bevel(ob,edge,3)
    return ob


def plate(name, points, front, thickness, mat, col, edge=.025, parent=None):
    # Mesh bevels preserve straight machined edges and do not inflate silhouettes.
    ob=solid_outline(name,[{'points':points}],front-thickness/2,thickness,mat,col,0,parent)
    # Conversion acts on every selected object. Isolate this plate so authoring
    # later machinery cannot silently bake the logo or another object's bevel.
    for selected in list(bpy.context.selected_objects):selected.select_set(False)
    bpy.context.view_layer.objects.active=ob;ob.select_set(True)
    bpy.ops.object.convert(target='MESH');ob=bpy.context.object;ob.select_set(False)
    if edge:bevel(ob,edge,3)
    ob['construction']='Closed extruded armor plate with machined edge radius'
    return ob


def arc_points(r,a,b,n=48):
    return [(r*math.cos(math.radians(a+(b-a)*i/n)),r*math.sin(math.radians(a+(b-a)*i/n))) for i in range(n+1)]


def annulus(name,ri,ro,a,b,front,thickness,mat,col,edge=.02,parent=None):
    return plate(name,arc_points(ro,a,b)+arc_points(ri,b,a),front,thickness,mat,col,edge,parent)


def sweep(name,points,width,depth,mat,col,parent=None):
    """Rectangular bent forging, not a round cable pretending to be a rib."""
    verts=[]
    for i,pt in enumerate(points):
        v=Vector(pt);t=Vector(points[min(i+1,len(points)-1)])-Vector(points[max(0,i-1)])
        t.z=0;t.normalize();normal=Vector((-t.y,t.x,0))*width/2
        for d,z in [(-1,-depth/2),(1,-depth/2),(1,depth/2),(-1,depth/2)]:
            q=v+normal*d+Vector((0,0,z));verts.append(tuple(q))
    faces=[(3,2,1,0)]
    for i in range(len(points)-1):
        for j in range(4):faces.append((4*i+j,4*i+(j+1)%4,4*(i+1)+(j+1)%4,4*(i+1)+j))
    faces.append(tuple(range(4*(len(points)-1),4*len(points))))
    return mesh_part(name,verts,faces,mat,col,min(width,depth)*.18,parent)


def housing(col):
    wall=M['RM | military olive wall'];dark=M['RM | shadowed olive armor'];steel=M['RM | forged clamp steel'];black=M['RM | deep recess']
    root=empty('RM BULKHEAD / measured armored housing',col);PARTS['wall']=root
    cylinder('RM housing deep casting',8.45,.95,(0,0,-1.10),black,col,192,.06,root)
    annulus('RM continuous recessed armor bed',2.72,7.13,0,360,-.32,.43,dark,col,.025,root)
    # Actual wide bays; the previous uniformly divided wheel was not in the shot.
    for a,b in [(-24,19),(22,49),(52,76),(79,105),(108,131),(134,162),(165,202),(205,233),(236,262),(265,291),(294,321),(324,333)]:
        annulus('RM outer shroud bay',6.92,8.38,a,b,-.49,.51,dark,col,.04,root)
    for a,b in [(-22,19),(53,76),(108,131),(166,201),(238,261),(294,320)]:
        annulus('RM deep interleaved shroud shoulder',7.25,8.46,a,b,-.30,.46,steel,col,.04,root)
    # Broad contiguous crown, with a true circular opening rather than spoke lines.
    crown=[(-2.44,7.20),(2.44,7.20),(2.44,2.04)]+arc_points(3.18,40,140)+[(-2.44,2.04)]
    plate('RM uninterrupted central crown armor',crown,.02,.45,wall,col,.028,root)
    for side in [-1,1]:
        def p(name,points,z=.015,t=.43,mat=wall,e=.024):
            return plate('RM '+name+(' L' if side<0 else ' R'),[(side*x,y) for x,y in points],z,t,mat,col,e,root)
        p('upper swept sector',[(2.47,7.05),(3.85,6.56),(4.91,5.36),(5.15,4.50),(2.47,2.02)],-.015,e=.012)
        p('upper diagonal stepped armor',[(2.49,2.00),(5.17,4.48),(5.92,3.54),(6.14,2.58),(3.15,.69)],.005,e=.012)
        p('large outer side cheek',[(3.165,.675),(6.155,2.565),(6.81,1.32),(6.93,-.40),(6.42,-2.13),(5.77,-2.25),(5.70,-.52),(4.80,-.45),(4.38,-1.09),(3.08,-.79)],-.01,e=.012)
        # Long upright cover with clipped toes, integrated into the outer housing.
        p('vertical side cover',[(5.92,2.95),(6.57,2.53),(6.72,1.56),(6.70,-2.43),(6.55,-2.64),(6.11,-2.64),(5.95,-2.46)],.18,.27)
        p('lower side armor',[(6.64,-2.71),(6.65,-3.80),(5.70,-5.24),(4.95,-5.79),(4.65,-3.15),(5.02,-2.62)],-.055,.48)
        p('wide lower diagonal load arm',[(2.29,-2.01),(3.06,-1.50),(5.11,-3.70),(5.28,-4.55),(4.72,-5.46),(4.12,-5.55),(1.54,-2.91)],.14,.52)
        # Inset chamfer follows the same forging. No arbitrary overlaid brace boxes.
        p('load arm inner landing',[(2.28,-2.18),(2.83,-1.88),(4.71,-3.95),(4.79,-4.55),(4.35,-5.04),(1.90,-2.93)],.205,.12)
        p('lower corner cast filler',[(5.48,-4.66),(5.44,-5.50),(4.33,-6.38),(3.52,-6.80),(3.36,-5.15),(4.42,-4.70)],-.23,.45,dark)
        # The cover seam turns horizontally and then diagonally at the foot.
        p('stepped service hatch',[(5.14,-.40),(5.73,-.45),(5.74,-1.69),(5.53,-1.83),(4.85,-1.83),(4.73,-1.64),(4.73,-.84)],.075,.20)
        p('lower vertical return flange',[(5.65,-1.87),(5.77,-2.01),(5.75,-3.88),(5.53,-4.11),(4.93,-3.77),(4.87,-2.02)],-.015,.32)
    # Unequal low machinery visible between the diagonal arms, not mirror looms.
    for side,x,y,w,h,count in [(-1,1.90,-4.72,1.52,1.90,8),(1,2.48,-4.87,.90,2.15,10)]:
        box('RM recessed radiator block',(side*x,y,-.25),(w,h,.50),black,col,.075,root)
        for i in range(count):
            yy=y+h*.42-i*h*.84/(count-1)
            box('RM broad cast radiator vane',(side*x,yy,.015),(w*.94,.145,.25),steel,col,.045,root)
    for i,(x,y0,y1) in enumerate([(1.04,-2.95,-6.10),(1.29,-2.96,-5.65),(1.51,-3.1,-6.22),(1.80,-3.25,-5.7),(2.03,-3.48,-6.0)]):
        xx=x+(i%2)*.035
        sweep('RM right lower stepped utility channel',[(xx,y0,.045),(xx,-3.76,.045),(xx+.10,-3.94,.045),(xx+.10,y1,.045)],.11,.15,steel,col,root)
    for i in range(3):
        x=-.95-i*.16
        tube('RM lower braided hydraulic line',[(x,-3.12,.09),(x-.06,-3.52,.16),(x-.20,-4.08,.19),(x-.42,-4.60,.13),(x-.40,-5.77,.07)],.052,black,col,root)
    # Lower bulkhead longitudinal beams disappear into shadow at the aperture.
    for x in [-3.08,3.08]:
        box('RM lower longitudinal beam',(x,-5.13,-.21),(.38,3.6,.56),dark,col,.045,root)
    root['reference']='Broad panel boundaries and load-arm silhouettes from trailer 124.0 s'
    key(root,'scale',[(1,(1.12,1.12,1)),(31,(1.12,1.12,1)),(61,(1,1,1)),(180,(1,1,1))])


def jaw(side,parent,col):
    steel=M['RM | forged clamp steel']
    # Across each station, varying Z creates two raised webs and three channels.
    stations=[(.73,2.78,3.92,.66),(.59,2.77,3.96,.85),(.38,2.77,4.01,.94),(.12,2.79,4.07,.98),(-.18,2.80,4.10,.985),(-.55,2.83,4.08,.93),(-.98,2.81,3.97,.77),(-1.30,2.71,3.76,.66)]
    across=[(0,-.07),(.075,0),(.17,0),(.21,.085),(.29,.09),(.34,.005),(.56,.005),(.61,.080),(.70,.09),(.77,.02),(.92,-.025),(1,-.10)]
    verts=[];cols=len(across);rows=len(stations)
    for k,(y,xa,xb,z) in enumerate(stations):
        for j,(t,dz) in enumerate(across):
            yy=y+(.20-.35*t if k==len(stations)-1 else 0)
            if k==0:yy=[.71,.73,.79,1.045,.86,.73,.75,.99,.87,.73,.70,.65][j]
            verts.append((side*(xa+(xb-xa)*t),yy,z+dz))
    frontn=len(verts)
    verts.extend([(x,y,.28) for x,y,z in verts])
    faces=[]
    for row in range(rows-1):
        for j in range(cols-1):
            a=row*cols+j;faces.append((a,a+1,a+cols+1,a+cols));faces.append((frontn+a+cols,frontn+a+cols+1,frontn+a+1,frontn+a))
    perimeter=list(range(cols))+[r*cols+cols-1 for r in range(1,rows)]+list(range((rows-1)*cols+cols-2,(rows-1)*cols-1,-1))+[r*cols for r in range(rows-2,0,-1)]
    for i,a in enumerate(perimeter):b=perimeter[(i+1)%len(perimeter)];faces.append((a,b,b+frontn,a+frontn))
    if side<0:faces=[tuple(reversed(f)) for f in faces]
    ob=mesh_part('RM curved twin-web forged jaw '+str(side),verts,faces,steel,col,.028,parent)
    ob['construction']='Closed variable-section casting; integrated rectangular ribs and recessed channels'
    # A thick stepped strap bridges the channels; its rounded captive pin is inset.
    strap=[(2.22,.07),(3.94,.07),(4.04,.025),(4.04,-.25),(3.25,-.25),(3.06,-.32),(2.22,-.32)]
    plate('RM stepped jaw clamping strap '+str(side),[(side*x,y) for x,y in strap],1.18,.25,steel,col,.028,parent)
    upper=[(2.18,.44),(4.00,.44),(4.08,.35),(4.08,.16),(2.18,.16)]
    plate('RM upper jaw load strap '+str(side),[(side*x,y) for x,y in upper],1.15,.22,steel,col,.021,parent)
    cylinder('RM captive pivot counterbore',.222,.04,(side*2.76,-.015,1.191),M['RM | deep recess'],col,64,.008,parent)
    head=cylinder('RM rounded captive pivot',.196,.086,(side*2.76,-.015,1.212),steel,col,12,.025,parent)
    slot=box('RM pivot slot cutting tool',(side*2.76,-.015,1.26),(.27,.036,.09),None,col,0)
    slot.rotation_euler.z=side*-.47
    mod=head.modifiers.new('Actual recessed screwdriver slot','BOOLEAN');mod.operation='DIFFERENCE';mod.object=slot
    bpy.context.view_layer.objects.active=head
    bpy.ops.object.modifier_move_to_index(modifier=mod.name,index=0)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(slot,do_unlink=True)


def mechanism(col):
    face=M['RM | faceplate yellow olive'];steel=M['RM | forged clamp steel'];black=M['RM | deep recess']
    root=empty('RM MECHANISM / recessed ocular bearing',col);PARTS['mechanism']=root
    lathe('RM deep ocular bearing socket',[(.81,-.10),(3.14,-.10),(3.17,.11),(3.11,.28),(2.43,.35),(.81,.28)],M['RM | shadowed olive armor'],col,parent=root)
    # Broad outer bearing interrupted by two dark lower keyways.
    for a,b in [(0,183),(184,230),(250,287),(309,360)]:
        annulus('RM interrupted bearing flange',2.37,3.11,a,b,.36,.30,M['RM | military olive wall'] if a==0 else face,col,.021,root)
    for a,b in [(231,249),(288,308)]:
        annulus('RM deep lower bearing keyway',2.34,3.12,a,b,.29,.26,black,col,.015,root)
        annulus('RM keyway inner machined shoulder',2.34,2.46,a+.5,b-.5,.43,.24,steel,col,.014,root)
    # A broad dark groove separates the collar and removable oval front disk.
    lathe('RM collar deep annular separation',[(2.13,.50),(2.50,.50),(2.51,.69),(2.47,.79),(2.19,.76),(2.13,.70)],black,col,parent=root)
    collar=lathe('RM rounded teal socket collar',[(2.24,.53),(2.42,.50),(2.51,.60),(2.515,.70),(2.47,.84),(2.37,.89),(2.27,.81),(2.24,.72)],M['RM | oxidized teal gasket'],col,parent=root)
    collar.data.materials.append(face)
    for p in collar.data.polygons:
        if p.center.y<0:p.material_index=1
    disk=lathe('RM chamfered solid olive faceplate',[(.89,.65),(2.17,.65),(2.22,.77),(2.24,.91),(2.22,1.025),(2.17,1.085),(.99,1.085),(.93,1.045),(.89,.95)],face,col,parent=root,segments=256)
    disk.scale.y=.89
    # The eye opening remains circular; ellipse distortion of the original ring
    # would otherwise squeeze the bore. This insert masks that transition.
    lathe('RM recessed optical seat',[(.71,.79),(.93,.79),(.99,.96),(.985,1.02),(.91,1.08),(.80,1.08)],black,col,parent=root)
    lathe('RM steel optical bezel',[(.71,.96),(.88,.96),(.92,1.025),(.924,1.085),(.887,1.17),(.83,1.225),(.776,1.238),(.736,1.20)],steel,col,parent=root)
    lathe('RM inner brass optical retaining lip',[(.705,1.16),(.741,1.16),(.765,1.215),(.748,1.253),(.719,1.252),(.705,1.226)],M['RM | steel exposed edges'],col,parent=root)
    # Tick marks occupy only the upper-right quadrant in the close-up.
    for i in range(23):
        a=math.radians(24+i*2.65);r=2.408
        ob=box('RM recessed collar diagnostic graduation',(r*math.cos(a),r*math.sin(a),.87),(.046,.039,.009),M['RM | green diagnostic'] if i<11 else M['RM | amber diagnostic'],col,.003,root);ob.rotation_euler.z=a-math.pi/2
    # Rigid jaws travel outward; rail lengths grow between the fixed center and jaw.
    for side in [-1,1]:
        jawroot=empty('RM articulated clamp jaw '+str(side),col);jaw(side,jawroot,col)
        motion=[(1,0),(31,0),(35,.08),(43,.88),(52,1.75),(63,1.88),(121,1.88),(180,1.88)]
        key(jawroot,'location',[(f,(side*x,0,0)) for f,x in motion])
        backing=empty('RM telescoping clamp bed '+str(side),col);backing.location=(side*2.0,-.1,.38)
        box('RM dark recessed clamp backing',(side*.5,0,0),(1,1.50,.26),steel,col,.025,backing)
        key(backing,'scale',[(f,(2.18+x,1,1)) for f,x in motion])
        for j,(y,h,z) in enumerate([(.67,.18,.59),(.36,.15,.67),(-.34,.18,.65),(-.68,.17,.57),(-.86,.14,.43)]):
            # Each U channel has a solid web and rolled top and bottom lips.
            beam=empty('RM telescoping rail '+str(side)+' '+str(j),col);beam.location=(side*2.0,y,z)
            for yy,hh,zz,dd in [(0,h,.0,.12),(-h*.45,.045,.075,.15),(h*.45,.045,.075,.15)]:
                box('RM telescoping rail section',(side*.5,yy,zz),(1,hh,dd),steel,col,.015,beam)
            key(beam,'scale',[(f,(2.06+x,1,1)) for f,x in motion])
        cylinder('RM clamp back bearing',.71,.25,(side*3.4,-.13,.17),black,col,96,.02,jawroot)
    root['reference']='Faceplate, upper collar and swept clamp jaw cross-sections measured at 121.0 s'


def technical_marks(col):
    mat=M['RM | technical etchings']
    # Three shallow pressed traces, each with an offset seam. These are part of
    # the broad face panel; they do not float above all of the housing layers.
    for r in [.94,1.23,1.53]:
        pts=[(-5.23+x,1.93+y,.060) for x,y in arc_points(r,0,360,180)]
        tube('RM concentric pressed circuit trace',pts,.009,mat,col,cyclic=True)
    for dy in [-.08,.07]:
        tube('RM diagonal circuit branch',[(-4.03,1.00+dy,.060),(-3.55,.80+dy,.060),(-2.57,.32+dy,.060)],.009,mat,col)
    pts=[(2.45,1.89),(3.33,2.64),(4.46,2.64),(4.46,2.43),(5.90,2.43),(5.90,-.04)]
    for dx,dy in [(0,0),(.16,-.13),(.33,-.28)]:tube('RM nested right angular circuit',[(x+dx,y+dy,.062) for x,y in pts],.009,mat,col)
    for x in [3.83,4.09,4.56]:
        tube('RM returning circuit leg',[(x,2.24,.062),(x,1.93,.062),(x+.22,1.62,.062),(x+.22,-.02,.062),(x+.35,-.23,.062)],.009,mat,col)
    for o in col.objects:o.parent=PARTS['wall']


def relink_lights():
    mechanical=bpy.data.collections.get('RM light receivers / mechanical surfaces')
    clamps=bpy.data.collections.get('RM light receivers / forged clamps')
    for c in [mechanical,clamps]:
        if c:
            for o in list(c.objects):c.objects.unlink(o)
    for cname in ['RM 01 / Segmented bulkhead','RM 02 / Eye carrier and clamps','RM 03 / Iron insignia','RM 05 / Surface engraving']:
        for o in C[cname].objects:
            if o.type in {'MESH','CURVE'} and mechanical:mechanical.objects.link(o)
            if cname=='RM 02 / Eye carrier and clamps' and o.type in {'MESH','CURVE'} and clamps and any(w in o.name for w in ['jaw','pivot','rail','clamp']):clamps.objects.link(o)


def apply():
    s=bpy.context.scene;PARTS['scene']=s
    C.update({c.name:c for c in bpy.data.collections});M.update({m.name:m for m in bpy.data.materials})
    bpy.ops.object.select_all(action='DESELECT')
    for cname in ['RM 01 / Segmented bulkhead','RM 02 / Eye carrier and clamps','RM 05 / Surface engraving']:
        for ob in list(C[cname].objects):bpy.data.objects.remove(ob,do_unlink=True)
    housing(C['RM 01 / Segmented bulkhead'])
    mechanism(C['RM 02 / Eye carrier and clamps'])
    technical_marks(C['RM 05 / Surface engraving']);relink_lights()
    s.frame_set(121)
    s['revision']='Third construction: measured panel geometry, swept twin-web clamps, recessed bearing and articulated telescoping rails.'
    print('Replaced mechanical background:',len(C['RM 01 / Segmented bulkhead'].objects),'housing parts;',len(C['RM 02 / Eye carrier and clamps'].objects),'carrier and clamp parts')
