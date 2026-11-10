"""Measured camera timing, controlled metal reflections and optical finishing."""
import bpy, math
from pathlib import Path
from scene_common import *
from remaster_scene import PARTS, ROOT


def finish():
    s=PARTS['scene'];col=C['RM 00 / Camera and studio']
    camdata=bpy.data.cameras.new('RM 50mm cinema lens');camdata.lens=50;camdata.sensor_width=36;camdata.clip_start=.02;camdata.clip_end=100
    cam=bpy.data.objects.new('RM CAMERA / matching trailer pullback',camdata);col.objects.link(cam);s.camera=cam
    key(cam,'location',[(1,(0,0,5)),(9,(0,0,7.0)),(16,(0,0,9.9)),(24,(0,0,13.9)),(31,(0,0,16.30)),(43,(0,0,21.00)),(61,(0,0,24.2)),(91,(0,0,26.3)),(121,(0,0,28.0)),(151,(0,0,29.6)),(180,(0,0,31.1))])
    key(cam,'rotation_euler',[(1,(0,0,math.radians(-3.8))),(31,(0,0,math.radians(.3))),(61,(0,0,0)),(180,(0,0,math.radians(-.4)))])
    title=PARTS['title']
    key(title,'location',[(1,(0,0,22)),(34,(0,0,22)),(38,(0,0,14)),(43,(0,0,5.6)),(49,(0,0,2.25)),(58,(0,0,2.60)),(180,(0,0,2.60))])
    key(title,'scale',[(1,(1.8,1.8,1.8)),(34,(1.8,1.8,1.8)),(40,(1.12,1.12,1.12)),(49,(.989,.989,.989)),(58,(1,1,1)),(180,(1,1,1))])
    for o in PARTS['letters']:
        key(o,'hide_render',[(1,True),(34,True),(35,False)]);key(o,'hide_viewport',[(1,True),(34,True),(35,False)])
    # Subtle contraction adds life without turning the iris into a mechanical fan.
    key(PARTS['pupil'],'scale',[(1,(.226,.226,.049)),(20,(.187,.187,.049)),(43,(.204,.204,.049)),(70,(.201,.201,.049)),(180,(.205,.205,.049))])
    key(PARTS['eye'],'rotation_euler',[(1,(0,0,0)),(180,(0,0,.10))])
    keylight=light('RM broad cold overhead reflection','AREA',(-3.7,5.8,8.0),1200,(.83,.89,1),6,col)
    keylight.data.shape='RECTANGLE';keylight.data.size=7;keylight.data.size_y=3
    fill=light('RM soft lower reflected light','AREA',(4.6,-3.2,6.0),450,(.77,.83,.73),5,col)
    fill.data.shape='RECTANGLE';fill.data.size=3;fill.data.size_y=6
    front=light('RM white title reflection card','AREA',(0,.3,12),1350,(1,.98,.94),11,col)
    front.data.shape='RECTANGLE';front.data.size=11;front.data.size_y=5
    pool=light('RM faded olive central light','AREA',(-.3,1.7,5.5),340,(.90,1,.64),5,col)
    pool.data.specular_factor=.25
    lower=light('RM eye lens glint','AREA',(-1.9,2.5,5.3),120,(.80,.91,1),.85,col)
    lower.data.shape='RECTANGLE';lower.data.size=1.4;lower.data.size_y=.45
    optical=light('RM blue flash illumination','POINT',(0,0,2.8),0,(.12,.62,1),.24,col)
    key(optical.data,'energy',[(1,0),(9,1600),(14,60),(20,0),(36,0),(42,1800),(47,80),(53,0),(180,0)])
    bs=M['RM | flash'].node_tree.nodes.get('Principled BSDF')
    node_key(bs.inputs['Emission Strength'],[(1,0),(9,700),(14,20),(20,0),(36,0),(42,1100),(46,35),(53,0),(180,0)])
    key(PARTS['flash'],'scale',[(1,(.02,.02,.012)),(9,(.14,.14,.04)),(20,(.002,.002,.002)),(36,(.002,.002,.002)),(42,(.16,.16,.04)),(53,(.002,.002,.002)),(180,(.002,.002,.002))])
    # A slight warm shift in the iris settles after the cold reveal.
    iris=M['RM | fine radial iris'].node_tree.nodes.get('Principled BSDF')
    node_key(iris.inputs['Emission Strength'],[(1,.22),(47,.32),(121,.30),(180,.18)])
    s.use_nodes=True;nt=s.node_tree;nt.nodes.clear();n,l=nt.nodes,nt.links
    render=n.new('CompositorNodeRLayers');render.location=(-800,160)
    glare=n.new('CompositorNodeGlare');glare.name='RM restrained photographic halation';glare.glare_type='FOG_GLOW';glare.quality='HIGH';glare.inputs['Threshold'].default_value=.85;glare.inputs['Strength'].default_value=.34;glare.inputs['Size'].default_value=.45;glare.location=(-590,160);l.new(render.outputs['Image'],glare.inputs['Image'])
    streak=n.new('CompositorNodeGlare');streak.name='RM horizontal anamorphic transient';streak.glare_type='STREAKS';streak.quality='HIGH';streak.streaks=2;streak.angle_offset=0;streak.fade=.96;streak.inputs['Threshold'].default_value=3.0;streak.inputs['Strength'].default_value=.38;streak.location=(-380,160);l.new(glare.outputs['Image'],streak.inputs['Image'])
    ellipse=n.new('CompositorNodeEllipseMask');ellipse.inputs['Size'].default_value=(.86,.63);ellipse.location=(-770,-160)
    blur=n.new('CompositorNodeBlur');blur.filter_type='GAUSS';blur.inputs['Size'].default_value=(300,240);blur.location=(-560,-160);l.new(ellipse.outputs[0],blur.inputs[0])
    vig=n.new('CompositorNodeMixRGB');vig.name='RM optical vignette';vig.blend_type='MULTIPLY';vig.inputs[0].default_value=.78;vig.location=(-160,160);l.new(streak.outputs['Image'],vig.inputs[1]);l.new(blur.outputs[0],vig.inputs[2])
    bars=n.new('CompositorNodeBoxMask');bars.name='RM 2.00 aspect trailer aperture';bars.inputs['Size'].default_value=(1.1,.50625);bars.location=(-360,-200)
    mask=n.new('CompositorNodeMixRGB');mask.blend_type='MULTIPLY';mask.inputs[0].default_value=1;mask.location=(60,160);l.new(vig.outputs[0],mask.inputs[1]);l.new(bars.outputs[0],mask.inputs[2])
    fade=n.new('CompositorNodeMixRGB');fade.name='RM opening and closing fade';fade.blend_type='MULTIPLY';fade.inputs[0].default_value=1;fade.location=(280,160);l.new(mask.outputs[0],fade.inputs[1])
    node_key(fade.inputs[2],[(1,(.0,.0,.0,1)),(6,(1,1,1,1)),(156,(1,1,1,1)),(167,(.40,.40,.40,1)),(176,(.015,.015,.015,1)),(180,(0,0,0,1))])
    output=n.new('CompositorNodeComposite');output.location=(510,160);l.new(fade.outputs[0],output.inputs[0])
    for f,label in [(1,'120.0 / opening iris'),(9,'White-blue optical flash'),(31,'121.0 / eye close-up'),(35,'Silver letterforms rush in'),(42,'Title reveal flash'),(58,'Wordmark settles'),(121,'124.0 / reference match'),(156,'Fade begins'),(180,'126.0 / black')]:s.timeline_markers.new(label,frame=f)
    s['reference']='https://www.youtube.com/watch?v=jHkjMqZJGuU — 2:00 to 2:06'
    s['construction']='Solid 3D segmented bulkhead, forged clamps, revolved lens housing, curved radial iris, extruded Bezier insignia and individual silver glyphs. Original procedural materials; no footage cards.'
    s['revision']='Second construction: measured trailer proportions, new letter silhouettes, symmetric authored emblem, Cycles lighting.'
    s.render.filepath='//renders/frame_';s.frame_set(121)
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.shading.type='SOLID';area.spaces.active.overlay.show_overlays=False
    print('Camera, animation and photographic finishing ready')


def preview(path,frame=121,percent=70,samples=48):
    s=PARTS['scene'];s.frame_set(frame);s.render.resolution_percentage=percent;s.cycles.samples=samples;s.render.filepath=str(Path(path).resolve())
    def render():
        bpy.ops.render.render(write_still=True)
        return None
    bpy.app.timers.register(render,first_interval=.5)
    print('Queued Cycles preview',frame,s.render.filepath)
