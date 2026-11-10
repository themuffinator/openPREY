#!/usr/bin/env python3
"""Qualify Voice controls with SDL dummy capture and engine render-target images.

SDL's explicitly selected dummy input supplies silence, never a physical mic.
OpenAL renders local-test playback to a private WAV. Semantic GUI commands
exercise the real settings adapter without host keyboard or mouse input. A
simulated output loss during the local test checks that voice playback stops
with the output and resumes when it returns.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys

import capture_retained_screens as capture

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/tests'))
from mp_round_remote_smoke import verify_runtime_is_current


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--language', default='english')
    parser.add_argument('--size', default='1280x720')
    args = parser.parse_args()
    args.runtime, args.renderer, args.gate, args.timeout, args.set = ROOT / '.install', 'gl', '1', 180, []
    args.output = args.output.resolve()
    if args.output.exists() or not args.output.is_relative_to((ROOT / '.tmp').resolve()):
        parser.error('choose a new output directory under the project .tmp')
    verify_runtime_is_current(args.runtime)
    args.output.mkdir(parents=True)
    config = args.output / 'alsoft.conf'
    config.write_text('[general]\ndrivers=wave\nchannels=stereo\nhrtf=false\n[wave]\nfile=' + str(args.output / 'mix.wav') + '\n')
    os.environ.update(SDL_AUDIO_DRIVER='dummy', ALSOFT_DRIVERS='wave', ALSOFT_CONF=str(config))

    def probe(name):
        return [f'echo VOICE_UI_{name}', 'listVoiceChat']

    def toggle(control):
        return [f'openq4_retainedGui focus "{control}"', 'openq4_retainedGui menu accept 1', 'openq4_retainedGui menu accept 0', 'waitMsec 400']

    steps = ['openq4_assertMenuActivation 4000 game', 'waitMsec 600', 'openq4_retainedGui event tab_voice', 'waitMsec 500',
             *probe('OFF'), 'screenshot "screenshots/voice-off.tga"',
             *toggle('voice-capture'), *probe('READY'), 'screenshot "screenshots/voice-ready.tga"',
             *toggle('voice-test'), 'waitMsec 800', *probe('TEST'), 'screenshot "screenshots/voice-test.tga"',
             # A lost output stops voice playback with every other source; the test carries on.
             *probe('BEFORE_OUTAGE'), 's_testDeviceInterruption 1000', 'waitMsec 500', *probe('OUTAGE'),
             'waitMsec 1500', *probe('RETURNED'),
             'openq4_retainedGui event tab_settings', 'waitMsec 400', *probe('LEFT'),
             'openq4_retainedGui event tab_voice', 'waitMsec 300', *toggle('voice-test'),
             'set s_voiceChatCapture 0', 'waitMsec 400', *probe('REVOKED'),
             'openq4_retainedGui event onBack', 'waitMsec 500', 'set ui_retained 0', 'set ui_retainedMultiplayer 0',
             'openq4_assertMenuActivation 4000 game', 'waitMsec 500', 'openq4_guiAction main_b_voiceconfig',
             'waitMsec 500', *probe('CLASSIC'), 'screenshot "screenshots/voice-classic.tga"']
    capture.SCENARIOS['voice-settings'] = ('mp:mp/q4dm1', steps)
    capture.SCENARIO_CVARS['voice-settings'] = {
        'net_ip': '127.0.0.1', 'net_port': '28981', 'si_minPlayers': '1', 'si_warmup': '0', 'si_useReady': '0',
        's_noSound': '0', 's_muteUnfocused': '0', 's_voiceChatCapture': '0', 's_voiceChatTest': '0',
        's_voiceChatEcho': '1', 'g_voiceChatDebug': '1', 'ui_retainedMultiplayer': '1',
        'win_allowMultipleInstances' if os.name == 'nt' else 'sys_allowMultipleInstances': '1'}
    result = capture.run(args, 'voice-settings')
    log = (ROOT / result['log']).read_text(encoding='utf-8', errors='replace')
    phases = {}
    for name, section in re.findall(r'^VOICE_UI_(\w+)[ \t]*\n(.*?)(?=^VOICE_UI_|\Z)', log, re.M | re.S):
        status = re.search(r'^VOICE_STATUS (.*)', section, re.M)
        if status:
            phases[name] = {key: int(value) for key, value in re.findall(r'(\w+)=(\d+)', status[1])}
            phases[name]['playing_sources'] = len(re.findall(r'^VOICE_PLAYBACK client=-?\d+ generation=\d+ playing=1 ', section, re.M))
    checks = {
        'complete': result['complete'] and result['returncode'] == 0 and not result['errors'],
        'no_automatic_capture': phases.get('OFF', {}).get('capture_opens') == 0,
        'consent_does_not_record': phases.get('READY', {}).get('capture_opens') == 0 and phases.get('READY', {}).get('status') == 2,
        'dummy_callback_and_playback': phases.get('TEST', {}).get('recording') == 1 and phases['TEST']['captured'] > 10 and phases['TEST']['played'] > 10,
        # During the outage frames are dropped, none played; afterwards playback resumes.
        # (The dummy input delivers frames in bursts, so a source is often idle between
        # them; playing_sources is reported, the frame counters are the check.)
        'output_loss_stops_playback': 'played' in phases.get('OUTAGE', {}) and
            phases['OUTAGE']['played'] == phases.get('BEFORE_OUTAGE', {}).get('played') and
            phases['OUTAGE'].get('playback_drops', 0) > phases.get('BEFORE_OUTAGE', {}).get('playback_drops', 0),
        'playback_resumes_after_output_loss': phases.get('RETURNED', {}).get('played', 0) > phases.get('OUTAGE', {}).get('played', 0) and
            phases.get('RETURNED', {}).get('recording') == 1,
        'only_dummy_input': 'VOICE_CAPTURE_DRIVER dummy' in log and re.search(r'VOICE_CAPTURE_DRIVER (?!dummy)', log) is None,
        'test_stops_on_tab_exit': phases.get('LEFT', {}).get('recording') == 0 and phases.get('LEFT', {}).get('status') == 2,
        'consent_revocation_closes': phases.get('REVOKED', {}).get('recording') == 0 and phases.get('REVOKED', {}).get('status') == 1,
        'classic_does_not_record': phases.get('CLASSIC', {}).get('recording') == 0,
        'local_test_not_transmitted': 'VOICE_SEND' not in log,
        'captured_controls': len(result['screenshots']) == 4,
        'semantic_actions_succeeded': re.search(r'RETAINED_GUI_OPERATION .* failed', log) is None,
    }
    result.update(checks=checks, phases=phases, passed=all(checks.values()), capture_driver='SDL dummy', physical_microphone=False,
                  engine_sha256=capture.digest(args.runtime / ('openQ4-client_x64.exe' if os.name == 'nt' else 'openQ4-client_x64')))
    (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': result['passed'], 'checks': checks, 'phases': phases}, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
