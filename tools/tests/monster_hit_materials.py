#!/usr/bin/env python3
"""Trace stock monster flesh and armour in a hidden windowed SP map.

Uses the installed PK4s, staged runtime, testHitMaterials and engine logging;
does not synthesize mouse/keyboard input or capture the desktop.
"""
import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/ui'))
import capture_retained_screens as capture

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets',type=Path,required=True)
    parser.add_argument('--runtime',type=Path,default=ROOT/'.install')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--renderer',choices=('gl','vulkan'),default='gl')
    args=parser.parse_args()
    args.output=args.output.resolve()
    if args.output.exists() or not args.output.is_relative_to((ROOT/'.tmp').resolve()):
        parser.error('choose a new output directory under the project .tmp')
    args.size='1280x720';args.gate='1';args.language='english';args.timeout=180
    stages=['god','notarget','set ai_disable 1']
    monsters=('berserker','strogg_marine','gladiator')
    for name in monsters:
        stages += [f'spawn monster_{name} name hit_{name}', 'waitMsec 500', f'testHitMaterials hit_{name}']
    capture.SCENARIOS['monster-materials']=('game/airdefense1',stages)
    result=capture.run(args,'monster-materials')
    log=(ROOT/result['log']).read_text(encoding='utf-8',errors='replace')
    samples=re.findall(r'HIT_MATERIALS entity=(\S+) samples=(\d+) material=(\S+) type=(\S+) effect=(\S+)',log)
    assert result['complete'] and result['returncode']==0 and not result['errors'], result
    for name in monsters:
        flesh=[row for row in samples if row[0]=='hit_'+name and row[3]=='flesh']
        assert flesh and all('impact_flesh' in row[4] for row in flesh), f'{name}: flesh did not select its flesh effect: {samples}'
    assert any(row[3]=='monstermetal' and 'monstermetal' in row[4] for row in samples), 'armour lost its material-specific effect'
    # Confirm what the selected retail FX plays, using effective PK4 precedence.
    effect=None
    for pack in sorted((args.assets/'q4base').glob('*.pk4')):
        with zipfile.ZipFile(pack) as archive:
            key=next((n for n in archive.namelist() if n.lower()=='effects/weapons/machinegun/impact_flesh.fx'),None)
            if key: effect=archive.read(key).decode('utf-8',errors='replace')
    assert effect and 'bullet_impact_flesh' in effect and 'bullet_impact_metal' not in effect, 'retail flesh sound selection changed'
    result['material_samples']=samples
    (args.output/'report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    for entity,count,material,kind,effect_name in samples:
        print(f'{entity}: {count} {kind} samples -> {effect_name}')
    print('stock monster flesh and armour impacts passed; flesh FX selects bullet_impact_flesh')

if __name__=='__main__':
    main()
