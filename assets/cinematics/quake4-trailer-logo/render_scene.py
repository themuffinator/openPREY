"""Render saved scene: blender -b quake4_trailer_logo.blend -P render_scene.py -- stills|animation OUTPUT.

The output argument is required so temporary files cannot escape the project.
"""
from pathlib import Path
import sys
import bpy

args=sys.argv[sys.argv.index('--')+1:]
mode=args[0]
out=Path(args[1]).resolve()
out.mkdir(parents=True,exist_ok=True)
s=bpy.data.scenes['QUAKE 4 | Cinematic remaster']
bpy.context.window.scene=s
s.render.engine='CYCLES'
s.cycles.device='GPU'
preferences=bpy.context.preferences.addons['cycles'].preferences
try:
    preferences.compute_device_type='OPTIX'
    preferences.get_devices()
    for device in preferences.devices:
        device.use=device.type=='OPTIX'
    if not any(d.use for d in preferences.devices):s.cycles.device='CPU'
except Exception:
    s.cycles.device='CPU'
s.render.use_persistent_data=True
s.render.compositor_device='GPU' if s.cycles.device=='GPU' else 'CPU'
s.cycles.denoising_use_gpu=s.cycles.device=='GPU'
s.render.image_settings.file_format='PNG'
s.render.image_settings.color_mode='RGB'
s.render.resolution_percentage=60 if mode=='stills' else 100
s.cycles.samples=32 if mode=='stills' else 96
frames=[121,31,13,37,43,163,181] if mode=='stills' else range(1,181)
for frame in frames:
    s.frame_set(frame)
    s.render.filepath=str(out/('frame_%04d.png'%frame))
    if mode=='animation' and Path(s.render.filepath).exists():
        continue
    bpy.ops.render.render(write_still=True)
    print('FINISHED_FRAME',frame,flush=True)
