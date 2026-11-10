"""Compatibility entry point for the completed cinematic remaster."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().with_name('build_remaster.py')),run_name='__main__')
