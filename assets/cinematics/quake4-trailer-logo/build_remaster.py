"""Rebuild the completed cinematic scene in Blender 4.5 LTS.

blender --factory-startup --background --python build_remaster.py
The scene was developed and constructed through Blender MCP.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import remaster_scene,remaster_animation,remaster_grade,remaster_fidelity,remaster_optics,remaster_finish,remaster_lettering,remaster_surface,remaster_timing,remaster_flare
import remaster_mechanics,remaster_wear,remaster_texture,remaster_mechanical_finish
import remaster_logo_overlays
import remaster_parity

remaster_scene.setup()
remaster_scene.geometry()
remaster_animation.finish()
remaster_grade.apply()
remaster_fidelity.apply()
remaster_optics.apply()
remaster_finish.apply()
remaster_lettering.apply()
remaster_surface.apply()
remaster_timing.apply()
remaster_flare.apply()
remaster_mechanics.apply()
remaster_wear.apply()
remaster_texture.apply()
remaster_mechanical_finish.apply()
remaster_logo_overlays.apply()
remaster_parity.apply()
output=Path(sys.argv[sys.argv.index('--')+1]).resolve() if '--' in sys.argv else None
remaster_finish.save(output)
