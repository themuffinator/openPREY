"""Full 3D reconstruction of the mechanical Quake 4 trailer title.

Construction is driven through Blender MCP. Raster guides are not scene assets.
"""
from pathlib import Path
import json, math, random, sys
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scene_common import *
import remaster_materials

R=random.Random(40405)
PARTS={}


def lathe(name,profile,mat,col,loc=(0,0,0),segments=192,parent=None):
    verts=[];faces=[];n=len(profile)
    for i in range(segments):
        a=math.tau*i/segments
        for r,z in profile:verts.append((r*math.cos(a),r*math.sin(a),z))
    for i in range(segments):
        for j in range(n):faces.append((i*n+j,((i+1)%segments)*n+j,((i+1)%segments)*n+(j+1)%n,i*n+(j+1)%n))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.materials.append(mat);mesh.update()
    o=bpy.data.objects.new(name,mesh);col.objects.link(o);o.location=loc
    if parent:o.parent=parent
    for p in mesh.polygons:p.use_smooth=True
    return o


def bezier_shape(name,paths,mat,col,z=0,depth=.2,edge=.01,transform=lambda x,y:(x,y)):
    data=bpy.data.curves.new(name,'CURVE');data.dimensions='2D';data.fill_mode='BOTH';data.resolution_u=24
    data.extrude=depth/2;data.bevel_depth=edge;data.bevel_resolution=4
    for path in paths:
        points=[]
        def v(x,y):return Vector((*transform(x,y),0))
        for cmd in path:
            if cmd[0] in ['M','L']:
                co=v(cmd[1],cmd[2]);points.append([co,co.copy(),co.copy()])
            elif cmd[0]=='C':
                points[-1][2]=v(cmd[1],cmd[2]);co=v(cmd[5],cmd[6]);points.append([co,v(cmd[3],cmd[4]),co.copy()])
        if len(points)>1 and (points[-1][0]-points[0][0]).length<1e-7:
            points[0][1]=points[-1][1]
            points.pop()
        s=data.splines.new('BEZIER');s.use_cyclic_u=True;s.bezier_points.add(len(points)-1)
        for p,(co,left,right) in zip(s.bezier_points,points):
            p.co=co;p.handle_left_type='FREE';p.handle_right_type='FREE';p.handle_left=left;p.handle_right=right
    o=bpy.data.objects.new(name,data);col.objects.link(o);o.location.z=z;data.materials.append(mat);return o


def setup():
    C.clear();M.clear();PARTS.clear()
    R.seed(40405)
    s=bpy.data.scenes.new('QUAKE 4 | Cinematic remaster');bpy.context.window.scene=s
    s.render.engine='CYCLES';s.cycles.device='GPU';s.cycles.samples=48;s.cycles.use_denoising=True
    s.cycles.adaptive_threshold=.045;s.cycles.max_bounces=6;s.cycles.diffuse_bounces=2;s.cycles.glossy_bounces=3
    pref=bpy.context.preferences.addons['cycles'].preferences
    try:
        pref.compute_device_type='OPTIX';pref.get_devices()
        for d in pref.devices:d.use=d.type=='OPTIX'
        if not any(d.use for d in pref.devices):s.cycles.device='CPU'
    except Exception:s.cycles.device='CPU'
    s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=70
    s.render.fps=30;s.frame_start=1;s.frame_end=180;s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB'
    s.render.use_motion_blur=True;s.render.motion_blur_shutter=.32
    s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast'
    s.world=bpy.data.worlds.new('RM | dark olive ambient');s.world.use_nodes=True
    s.world.node_tree.nodes['Background'].inputs[0].default_value=(.13,.15,.11,1)
    s.world.node_tree.nodes['Background'].inputs[1].default_value=.20
    for name in ['RM 00 / Camera and studio','RM 01 / Segmented bulkhead','RM 02 / Eye carrier and clamps','RM 03 / Iron insignia','RM 04 / Silver letterforms','RM 05 / Surface engraving','RM 06 / Optics']:
        collection(name)
    remaster_materials.palette();PARTS['scene']=s
    return s


def wall():
    col=C['RM 01 / Segmented bulkhead'];wall=M['RM | military olive wall'];dark=M['RM | shadowed olive armor'];steel=M['RM | forged clamp steel'];black=M['RM | deep recess']
    root=empty('RM BULKHEAD / layered circular structure',col);PARTS['wall']=root
    cylinder('RM deep bulkhead core',8.6,.65,(0,0,-.8),black,col,192,.03,root)
    # Broad machined sectors, with real dark cavities and staggered panel joints.
    for i in range(12):
        a=i*30+5
        sector('RM large olive radial plate %02d'%i,2.51,6.48,a+.16,a+29.80,-.15,.46,wall if i%4 else dark,col,root,.018)
        sector('RM outer armor segment %02d'%i,6.58,8.30,a+.24,a+29.70,-.34,.54,dark,col,root,.025)
    for radius,z,w in [(6.55,-.12,.062),(6.72,-.07,.11),(7.72,-.25,.08),(8.24,-.29,.04)]:
        arc('RM massive concentric retaining rib',radius,w,z,steel,col,parent=root)
    # The reference's large dark alternating outer recesses.
    for i in range(16):
        a=math.radians(i*22.5+7)
        o=box('RM outer dark radial recess',(7.10*math.cos(a),7.10*math.sin(a),-.06),(.60,1.95,.27),black,col,.025,root);o.rotation_euler.z=a-math.pi/2
        o=box('RM recessed radial structural block',(7.12*math.cos(a),7.12*math.sin(a),-.02),(.37,1.62,.19),steel,col,.03,root);o.rotation_euler.z=a-math.pi/2
    # Unequal access panels cut into the circular wall.
    for side in [-1,1]:
        for j,(y,h,w) in enumerate([(3.5,2.2,1.2),(-2.15,1.35,1.6),(-4.3,2.0,1.32)]):
            x=side*(4.86 if j!=1 else 4.55)
            pts=[(-w/2,-h/2),(w/2-.16,-h/2),(w/2,-h/2+.18),(w/2,h/2),(-w/2+.15,h/2),(-w/2,h/2-.15)]
            p=solid_outline('RM inset service door',[{'points':pts}],.055,.13,dark,col,.012,root);p.location.x=x;p.location.y=y
            for ox,oy in [(-w*.35,-h*.35),(w*.35,h*.35)]:
                cylinder('RM sunk access screw',.041,.018,(x+ox,y+oy,.137),steel,col,12,.004,root)
        # Wide vertical armor lips define the background's straight seam rhythm.
        for x,y,h,w in [(2.37,4.30,4.6,.10),(5.93,-.35,6.5,.16),(4.38,-3.80,3.5,.09)]:
            box('RM long plate join',(side*x,y,.09),(w,h,.13),dark,col,.013,root)
        # Lower central fins and curved hydraulic looms.
        for i in range(5):
            x=side*(1.18+i*.23)
            pts=[(x,-3.22,.12),(x+side*.11,-3.85,.19),(x+side*.25,-4.24,.18),(x+side*.25,-6.2,.14)]
            tube('RM heavy hydraulic conduit',pts,.072 if i%2 else .052,steel,col,root)
            for y in [-3.8,-4.6,-5.4]:
                box('RM cable harness band',(x+side*.15,y,.20),(.19,.08,.10),dark,col,.012,root)
        for j in range(6):
            box('RM bottom intake fins',(side*2.15,-4.1-j*.23,.11),(1.1,.16,.20),steel,col,.025,root)
    # Directional scars complement the shader's much finer surface relief.
    for i in range(100):
        x,y=R.uniform(-6.2,6.2),R.uniform(-5.3,5.3)
        if x*x+y*y<8.9:continue
        length=R.uniform(.09,.65)
        tube('RM rubbed vertical bulkhead scratch',[(x,y,.092),(x+R.uniform(-.03,.03),y+length,.092)],R.uniform(.0015,.004),M['RM | fracture scars'],col,root)


def mechanism():
    col=C['RM 02 / Eye carrier and clamps'];steel=M['RM | forged clamp steel'];face=M['RM | faceplate yellow olive'];black=M['RM | deep recess'];root=empty('RM MECHANISM / ocular carrier',col);PARTS['mechanism']=root
    lathe('RM circular armor behind the insignia',[(2.15,.0),(3.23,.0),(3.25,.20),(3.15,.38),(2.73,.42),(2.54,.57),(2.15,.5)],face,col,parent=root)
    lathe('RM rounded teal socket collar',[(2.22,.40),(2.45,.40),(2.52,.56),(2.51,.73),(2.45,.85),(2.30,.87),(2.24,.81)],M['RM | oxidized teal gasket'],col,parent=root)
    lathe('RM chamfered solid olive faceplate',[(.84,.65),(2.21,.65),(2.26,.85),(2.24,1.06),(2.15,1.15),(.94,1.15),(.87,1.03)],face,col,parent=root)
    lathe('RM steel optical bezel',[(.72,.92),(.91,.92),(.96,1.09),(.90,1.20),(.82,1.25),(.755,1.21)],steel,col,parent=root)
    lathe('RM polished inner optical ring',[(.714,1.18),(.747,1.18),(.772,1.23),(.75,1.26),(.716,1.245)],M['RM | steel exposed edges'],col,parent=root)
    for i in range(36):
        a=math.radians(22+i*3.85)
        o=box('RM tiny collar diagnostic tick',(2.405*math.cos(a),2.405*math.sin(a),.852),(.032,.064,.011),M['RM | amber diagnostic'] if i<15 else M['RM | green diagnostic'],col,.004,root);o.rotation_euler.z=a-math.pi/2
    for side in [-1,1]:
        # These are long horizontal clamps, interrupted by broad angled jaws.
        box('RM clamp deep support',(side*3.65,-.12,.35),(3.08,1.64,.57),black,col,.07,root)
        for i,y in enumerate([-.74,-.44,-.14,.16,.46]):
            box('RM long cooling rail',(side*3.61,y,.74),(3.06,.15,.38),steel,col,.038,root)
        pts=[(3.40,-1.10),(4.34,-1.28),(4.71,-1.10),(4.78,-.79),(4.58,.64),(4.47,.84),(3.91,.94),(3.71,.74)]
        p=solid_outline('RM sculpted clamp jaw',[{'points':[(side*x,y) for x,y in pts]}],.87,.43,steel,col,.046,root)
        for x,w in [(3.88,.13),(4.40,.12)]:
            pts=[(side*(x-.1),-.98,1.11),(side*(x+.10),-.55,1.11),(side*(x+.11),.68,1.11)]
            tube('RM jaw raised forged spine',pts,w,steel,col,root)
        box('RM clamp crossbar',(side*3.56,-.12,1.16),(2.44,.38,.22),steel,col,.035,root)
        cylinder('RM clamp pivot socket',.235,.055,(side*3.95,-.13,1.294),black,col,64,.012,root)
        cylinder('RM large bevelled pivot',.195,.085,(side*3.95,-.13,1.327),steel,col,10,.02,root)
        slot=box('RM pivot screw slot',(side*3.95,-.13,1.374),(.23,.031,.010),black,col,.004,root);slot.rotation_euler.z=side*.48
    # The scar at the eye's upper right is a distinctive feature of the source.
    scar=M['RM | fracture scars']
    for pts,r in [([(.45,1.83,1.164),(.43,1.51,1.164),(.55,1.38,1.164),(.55,1.04,1.164),(.43,.86,1.164)],.024),
                  ([(.59,1.42,1.164),(.71,1.33,1.164),(.68,1.02,1.164)],.041),
                  ([(.91,.61,1.16),(1.06,.38,1.16),(1.04,-.10,1.16),(1.23,-.57,1.16)],.014)]:tube('RM deep faceplate fracture',pts,r,scar,col,root)
    for i in range(190):
        a=R.uniform(0,math.tau);r=R.uniform(1.01,2.14);x,y=r*math.cos(a),r*math.sin(a)
        if i<75:x=R.gauss(.58,.22);y=R.uniform(.91,2.0)
        if x*x+y*y>2.15**2:continue
        width=R.uniform(.006,.031);length=R.uniform(.018,.12)
        pts=[(x-width,y),(x,y+length),(x+width*.55,y+length*.65),(x+width,y-length*.13)]
        solid_outline('RM paint flake at scored faceplate',[{'points':pts}],1.155,.003,scar,col,.001,root)


EMBLEM_PATH=[('M',185,5),('C',113,40,78,95,78,157),('C',77,188,85,221,98,246),
 ('L',92,259),('C',100,274,109,287,120,296),('L',134,294),('L',151,309),('L',153,324),
 ('C',165,332,180,340,194,344),('L',206,337),('C',216,340,227,342,238,342),('L',238,387),
 ('C',238,428,245,470,255,506),('C',265,470,272,428,272,387),('L',272,342),
 ('C',283,342,294,340,304,337),('L',316,344),('C',330,340,345,332,357,324),('L',359,309),
 ('L',376,294),('L',390,296),('C',401,287,410,274,418,259),('L',412,246),
 ('C',425,221,433,188,432,157),('C',432,95,397,40,325,5),
 ('C',384,39,411,90,411,151),('C',411,221,382,286,272,298),('L',272,260),
 ('C',272,244,263,225,255,215),('C',247,225,238,244,238,260),('L',238,298),
 ('C',128,286,99,221,99,151),('C',99,90,126,39,185,5)]


def emblem_title():
    col=C['RM 03 / Iron insignia']
    trans=lambda x,y:((x-255)*.0182,(171-y)*.0182)
    edge=bezier_shape('RM Q insignia / subdued green worn perimeter',[EMBLEM_PATH],M['RM | soft radioactive edge'],col,1.35,.25,.039,trans)
    face=bezier_shape('RM Q insignia / precise iron silhouette',[EMBLEM_PATH],M['RM | iron emblem'],col,1.43,.32,.019,trans)
    PARTS['emblem']=face
    face['construction']='Authored symmetric Bezier arcs, sharp gear shoulders and a tapered central blade; solid extruded iron.'
    col=C['RM 04 / Silver letterforms'];root=empty('RM TITLE / authentic silver silhouettes',col);root.location.z=2.60;PARTS['title']=root;letters=[]
    for glyph in json.loads((ROOT/'remaster_glyphs.json').read_text()):
        loops=glyph['loops'];xs=[p[0] for loop in loops for p in loop['points']];center=(max(xs)+min(xs))/2
        local=[{'hole':p['hole'],'points':[(x-center,y) for x,y in p['points']]} for p in loops]
        o=solid_outline('RM LETTER / '+glyph['name'],local,0,.16,M['RM | silver title'],col,.014,root);o.location.x=center
        # Controlled local handles remove raster steps without moving extrema.
        old=o.data;data=bpy.data.curves.new(o.name+' / refined outlines','CURVE');data.dimensions='2D';data.fill_mode='BOTH';data.resolution_u=12;data.extrude=.08;data.bevel_depth=.014;data.bevel_resolution=4;data.materials.append(M['RM | silver title'])
        for loop in local:
            pts=[Vector((x,y,0)) for x,y in loop['points']]
            area=sum(pts[i].x*pts[(i+1)%len(pts)].y-pts[(i+1)%len(pts)].x*pts[i].y for i in range(len(pts)))
            if (area<0)!=loop['hole']:pts.reverse()
            spl=data.splines.new('BEZIER');spl.bezier_points.add(len(pts)-1);spl.use_cyclic_u=True
            for i,(p,v) in enumerate(zip(spl.bezier_points,pts)):
                prev,nxt=pts[i-1],pts[(i+1)%len(pts)];a=v-prev;b=nxt-v
                p.co=v;p.handle_left_type='FREE';p.handle_right_type='FREE';p.handle_left=v;p.handle_right=v
                if a.length and b.length and a.normalized().dot(b.normalized())>.70:
                    tangent=(a.normalized()+b.normalized()).normalized();p.handle_left=v-tangent*a.length*.29;p.handle_right=v+tangent*b.length*.29
        o.data=data;o['character']=glyph['name'];o['construction']='Clean reconstructed outline, solid silver extrusion and fine optical bevel.';letters.append(o)
    PARTS['letters']=letters


def eye():
    col=C['RM 06 / Optics'];root=empty('RM EYE / articulated optical assembly',col);PARTS['eye']=root
    sphere('RM wet red optical lens',(0,0,1.24),(.714,.714,.285),M['RM | wet crimson lens'],col,root,96)
    # UV-mapped curved annulus follows the front dome; each fiber is shaded in radial coordinates.
    verts=[];uvs=[];faces=[];count=384;rings=24
    for j in range(rings+1):
        r=.197+(.427-.197)*j/rings
        for i in range(count+1):
            a=math.tau*i/count;z=1.24+.285*math.sqrt(1-(r/.714)**2)+.006
            verts.append((r*math.cos(a),r*math.sin(a),z));uvs.append((i/count,j/rings))
    for j in range(rings):
        for i in range(count):
            k=j*(count+1)+i;faces.append((k,k+1,k+count+2,k+count+1))
    mesh=bpy.data.meshes.new('RM sculpted radial iris');mesh.from_pydata(verts,[],faces);mesh.materials.append(M['RM | fine radial iris']);mesh.update();uv=mesh.uv_layers.new()
    for poly in mesh.polygons:
        poly.use_smooth=True
        for li in poly.loop_indices:uv.data[li].uv=uvs[mesh.loops[li].vertex_index]
    iris=bpy.data.objects.new('RM IRIS / fine crimson radial fibers',mesh);col.objects.link(iris);iris.parent=root;PARTS['iris']=iris
    pupil=sphere('RM PUPIL / polished black aperture',(0,0,1.519),(.201,.201,.049),M['RM | pupil'],col,root,64);PARTS['pupil']=pupil
    flash=sphere('RM FLASH / transient optical core',(0,0,1.61),(.018,.018,.008),M['RM | flash'],col,root,32);PARTS['flash']=flash


def engraving():
    col=C['RM 05 / Surface engraving'];mat=M['RM | technical etchings']
    for r in [.93,1.22,1.50]:arc('RM left concentric circuit engraving',r,.009,.127,mat,col,center=(-5.02,1.75))
    for off in [-.11,.10]:
        tube('RM long parallel circuit leads',[(-3.89,1.20+off,.127),(-3.18,.91+off,.127),(-1.71,.49+off,.127)],.01,mat,col)
    # The squared, sloped and stepped right-hand glyph in the original composition.
    path=[(2.42,1.86),(3.39,2.55),(4.21,2.55),(4.21,2.33),(5.61,2.33),(5.61,.16)]
    for j in range(3):
        tube('RM nested right technical marking',[(x+j*.15,y-j*.13,.13) for x,y in path],.01,mat,col)
    for j in range(2):
        tube('RM internal angular Strogg glyph',[(3.54+j*.18,2.21,.13),(3.50+j*.18,1.86,.13),(3.80+j*.18,1.53,.13),(3.83+j*.18,.57,.13),(3.54+j*.18,.76,.13),(3.18+j*.18,1.16,.13),(3.17+j*.18,.79,.13),(3.51+j*.18,.30,.13),(4.03+j*.18,.30,.13)],.01,mat,col)
    tube('RM inner right zigzag',[(4.38,2.08,.13),(4.37,1.78,.13),(4.66,1.40,.13),(4.66,.31,.13)],.013,mat,col)


def geometry():
    wall();mechanism();emblem_title();eye();engraving()
    print('Remaster geometry:',len(PARTS['scene'].objects),'objects')
