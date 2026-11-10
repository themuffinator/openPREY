"""Render a finite, resumable queue in the Blender MCP session."""
from pathlib import Path
import bpy,json,time

ACTIVE=None


def stop():
    global ACTIVE
    if ACTIVE and bpy.app.timers.is_registered(ACTIVE):bpy.app.timers.unregister(ACTIVE)
    ACTIVE=None


def start(directory,frames=None,percentage=100,samples=48):
    global ACTIVE
    stop();out=Path(directory).resolve();out.mkdir(parents=True,exist_ok=True)
    s=bpy.context.scene;s.render.resolution_percentage=percentage;s.cycles.samples=samples;s.render.use_persistent_data=True
    queue=list(frames if frames is not None else range(1,181));total=len(queue);done=[];started=time.time()
    def status(state,f):
        (out/'progress.json').write_text(json.dumps({'status':state,'frame':f,'completed':len(done),'total':total,'elapsed_seconds':round(time.time()-started,2),'frames':done}),encoding='utf-8')
    def render():
        try:
            if not queue:
                s.frame_set(121);s.render.filepath='//renders/frame_';status('complete',done[-1]);return None
            f=queue.pop(0);s.frame_set(f);s.render.filepath=str(out/('frame_%04d.png'%f))
            bpy.ops.render.render(write_still=True);done.append(f);status('rendering',f);return .15
        except Exception as e:
            (out/'error.txt').write_text(str(e));status('failed',s.frame_current);return None
    status('starting',0);ACTIVE=render;bpy.app.timers.register(render,first_interval=.6)
    print('Queued',total,'Cycles frames at',percentage,'percent and',samples,'samples in',out)
