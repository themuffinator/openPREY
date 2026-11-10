#!/usr/bin/env python3
"""Render every gameplay HUD family over a loaded map without host input.

Uses native named events and presentation setters, plus the engine screenshot
command. testGUI exercises the actual installed GUI definitions and renderer.
"""
import argparse
import json
import re
from pathlib import Path
import capture_retained_screens as capture

ROOT=Path(__file__).resolve().parents[2]

def state(root, **values):
    return [f'ui_hudTest "{root}" state "{key}" "{value}"' for key,value in values.items()]

def events(root, *names):
    return [f'ui_hudTest "{root}" event "{name}"' for name in names]

def family(root):
    """Publish real GUI keys/events, without synthesizing user input."""
    stages=[f'testGUI "{root}"','waitMsec 100']
    if root.endswith(('hud.gui','hud_strogg.gui','turretplayerhud.gui')) or root=='guis/q4x_cannon_hud.gui':
        stages+=state(root,player_health=75,player_healthpct=.75,player_armor=60,player_armorpct=.6,
            player_ammo=32,player_totalammo=160,player_clip_size=50,player_ammopct=.64,
            ammoicon='gfx/guis/hud/icons/ammo_machinegun',weapicon='gfx/guis/hud/icons/gun_machinegun',
            itemicon='gfx/guis/hud/icons/item_healthmega_colored',itemtext='Mega Health',
            boss_health=65,boss_maxhealth=100,boss_shield_percent=.4,vehicle_health=.7,vehicle_shield=.6,
            vehicle_weaponammo=.5,vehicle_weaponcharge=.3,rhinochatter=1,hitdir=1,missiledir=45,
            tram_heatpct=.65,tram_healthpct=.7,bracket_left=280,bracket_top=200,bracket_width=80,bracket_height=80,
            powerup0_visible=1,powerup0_time=24,powerup0_icon='gfx/guis/hud/icons/item_quaddamage')
        stages+=events(root,'updateHealth','updateArmor','updateAmmo','radioChatterUp','showBossBar','showBossShieldBar','showBrackets','itemPickup')
        if root=='guis/q4xhud.gui':stages+=events(root,'aa_showShipStatusOn','showCompass','showCompassBeacon')
        if 'airassault' in root:stages+=events(root,'ship_target_01_on','ship_health_02_on','warning_NE')
        if 'speeder' in root:
            stages+=state(root,currenttime='01:24.350',currenttime2='01:27.600',boost_active=1)
            stages+=events(root,'showspeedertimer','showspeedertimer2','showprogress50','event_anim_booston')
    if root=='guis/mphud.gui':
        stages+=state(root,gametype=4,playerteam=0,marine_score=4,strogg_score=3,timeleft='08:32',
            main_notice_text='Capture the flag',main_notice_duration=5000,frag_notice_text='You fragged Strogg',
            frag_notice_duration=5000,chattext='^2Rhino:^7 Hold this position.',audio_name='Rhino',
            aim_text='Rhino',aim_teammate_health=75,ig_award='gfx/mp/awards/excellent',ig_award_num=2)
        stages+=events(root,'InitHud','TeamChange','addChatLine','main_notice','frag_notice','aim_text','show_transmit_self','show_transmit','giveIGA')
    if 'wristcomm' in root:
        stages+=state(root,objective1=1,objective2=1,objectivetitle='Reach the hangar',
            objectivetitle1='Reach the hangar',objectivetitle2='Find the medic',
            objectivetext1='Regroup with Rhino squad at the hangar entrance.',objectivetext2='Escort the medic to the wounded marine.',
            objectiveshot1='gfx/objectives/airdefense_obj_1',objectiveshot2='gfx/objectives/airdefense_obj_2',screenshot='gfx/objectives/airdefense_obj_1')
        stages+=events(root,'wristcommShow')
    if root in ('guis/scoreboard.gui','guis/summary.gui'):
        stages+=state(root,gametype=4,playerteam=0,num_players=2,num_total_players=2,num_marine_players=1,num_strogg_players=1,
            servername='openQ4 HUD verification',servermap='Bloodwork',servergametype='Capture the Flag',
            serverlimit='Capture limit: 8',servertimelimit='Time limit: 20',marine_score=4,strogg_score=3,timeleft='08:32',
            team_0_scores_item_0='Rhino\t42\t12\t8\t24',team_1_scores_item_0='Strogg\t35\t10\t12\t38',
            summary_names_item_0='Rhino',summary_marine_names_item_0='Rhino',summary_strogg_names_item_0='Strogg',
            eg_award0=1,eg_award0_text='Accuracy')
        if root.endswith('summary.gui'):stages+=events(root,'marine_wins','showBtns')
    if root=='guis/cursor.gui':
        stages+=state(root,visible=1,mp=0,g_crosshairSize=32,crossColor='1 1 1 1',crossImage='gfx/guis/crosshairs/crosshair_blaster',npc='Rhino',npcdesc='Marine')
        stages+=events(root,'showCrossTalk')
    if root=='guis/mpmsgmode.gui':stages+=state(root,chattext='Squad, move to the flag.')
    if root=='guis/vehicles/medchange.gui':stages+=events(root,'activate')
    if root=='guis/vehicles/mdisp.gui':stages+=events(root,'warning_hazard')
    if root=='guis/vehicles/strogg_noise.gui':stages+=events(root,'show')
    if root=='guis/vehicles/blank.gui':stages+=events(root,'saveMessage')
    if root=='guis/cinematic.gui':stages+=events(root,'logoStart')
    if root=='guis/e3cinematic.gui':stages+=events(root,'logoStart')
    if root=='guis/introcinematic.gui':stages+=events(root,'show_text01')
    if root.endswith(('dropshiphealth.gui','mcchealth.gui','cannonplayerhud.gui')):stages+=state(root,shealth=75,mcchealth=65)
    name=root.removeprefix('guis/').removesuffix('.gui').replace('/','-')
    stages+=['waitMsec 1200']
    if root=='guis/vehicles/medchange.gui':
        # The first presentation can load artwork. Restart the short activation
        # after that load so the capture samples the animation, not its end.
        stages+=events(root,'activate')+['waitMsec 300']
    stages+=[f'ui_hudTest "{root}" report',f'screenshot "screenshots/{name}.tga"']
    if root=='guis/scoreboard.gui':
        stages+=state(root,gametype=2,name1_round1_bracket1='Rhino',name2_round1_bracket1='Strogg',score1_round1_bracket1=12,score2_round1_bracket1=9)
        stages+=['waitMsec 200',f'screenshot "screenshots/{name}-tourney.tga"']
    return stages

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--runtime',type=Path,default=ROOT/'.install');p.add_argument('--renderer',choices=('gl','vulkan'),default='gl')
    p.add_argument('--size',default='1280x720');p.add_argument('--scenario',choices=('live','families','mp','awakening','lifecycle','strogg','fallback'),default='live')
    p.add_argument('--awakening',type=Path,help='Read-only content root containing q4xbase')
    a=p.parse_args();a.output=a.output.resolve();a.language='english';a.gate='1';a.timeout=300
    if a.output.exists() or not a.output.is_relative_to((ROOT/'.tmp').resolve()):p.error('use a fresh output beneath .tmp')
    stages=['set g_autoExecAfterMapLoad ""','set developer 1','god','notarget','give all','waitMsec 800','testStatusBar probe',
        'screenshot "screenshots/live.tga"']
    if a.scenario=='mp':
        stages+=['set hud_showInput 1','set net_clientLagOMeter 1','set hud_damageNumbers 1',
            'testHudOverlays 75','waitMsec 16','screenshot "screenshots/native-overlays.tga"','waitMsec 500']
    else:
        stages+=['testHitMarker 75','waitMsec 16','screenshot "screenshots/hit-marker.tga"']
    if a.scenario=='lifecycle':
        stages+=['saveGame "hud-coverage"','waitMsec 300','loadGame "hud-coverage"','waitMsec 1000',
            'screenshot "screenshots/save-restored.tga"','vid_restart','waitMsec 1200',
            'screenshot "screenshots/video-restored.tga"','ui_hudTest guis/hud.gui report']
    if a.scenario=='fallback':
        capture.OVERRIDES[a.scenario]={'guis/hud/coverage.json':lambda _:json.dumps({'version':1,'materials':{},'images':[]})}
        # Keep a nonempty GUI layer visible while checking same-frame stock
        # fallback. An empty idle HUD can validly present without any artwork.
        stages+=events('guis/hud.gui','showBossBar')+['waitMsec 200','ui_hudTest guis/hud.gui report',
            'screenshot "screenshots/fallback-active.tga"']
    roots=[]
    if a.scenario in ('families','awakening'):
        registry=json.loads((ROOT/'content/baseoq4/pak0/guis/hud/coverage.json').read_text())
        roots=registry['expansionRoots' if a.scenario=='awakening' else 'roots']
        stages+=['set ui_testGuiInGame 1','set g_showHud 0']
        for root in roots:stages+=family(root)
        stages+=['testGUI ""','set g_showHud 1']
    main_root='guis/q4xhud.gui' if a.scenario=='awakening' else 'guis/hud_strogg.gui' if a.scenario=='strogg' else 'guis/hud.gui'
    stages+=[f'ui_hudTest "{main_root}" report','set ui_retained 0','waitMsec 200','screenshot "screenshots/stock.tga"',
        'set ui_retained 1','waitMsec 300',f'ui_hudTest "{main_root}" report','screenshot "screenshots/restored.tga"']
    if a.scenario=='awakening':
        if not a.awakening:p.error('--awakening is required for the expansion scenario')
        a.game_dir='q4xbase'
        capture.SCENARIO_CVARS[a.scenario]={'fs_awakeningpath':str(a.awakening.resolve()),'fs_game_base':'baseoq4',
            'com_gameMode':'SP','si_gameType':'singleplayer','com_nextGameModule':'game_sp'}
    capture.SCENARIOS[a.scenario]=('mp:mp/q4dm1' if a.scenario=='mp' else 'game/m03_airassault' if a.scenario=='awakening' else 'game/recomp' if a.scenario=='strogg' else 'game/airdefense1',stages)
    result=capture.run(a,a.scenario)
    log=(ROOT/result['log']).read_text(errors='replace') if result['log'] else ''
    result['hud_traces']=re.findall(r'HUD_COVERAGE .*',log)
    result['hud_warnings']=[line for line in log.splitlines() if 'HUD coverage:' in line]
    result['hud_reports']=re.findall(r'HUD_REPORT source=(\S+) drawn=(\d)',log)
    result['expected_roots']=roots
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('complete','returncode','hud_traces','hud_warnings','retained_warnings','errors')},indent=2))
    assert result['complete'] and result['returncode']==0
    assert not result['errors'] and not result['retained_warnings']
    if a.scenario=='fallback':
        assert result['hud_warnings'] and ('guis/hud.gui','0') in result['hud_reports']
        assert not result['hud_traces']
    else:
        assert not result['hud_warnings']
        # An idle on-foot HUD can contain only the separate retained gauges.
        # Its empty frame still needs a successful retained draw receipt.
        assert (main_root,'1') in result['hud_reports']
        if a.scenario=='mp':
            for root in ('native/hit-marker','native/damage-numbers','native/movement-input'):
                assert any('source='+root+' ' in line for line in result['hud_traces']),root
    assert all((root,'1') in result['hud_reports'] for root in roots),result['hud_reports']

if __name__=='__main__':main()
