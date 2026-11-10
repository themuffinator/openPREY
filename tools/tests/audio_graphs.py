#!/usr/bin/env python3
"""Exercise radio graphs using real decoded audio and engine screenshots.

No microphone, host input or OS captures. OpenAL's null output runs the real
decoder and playback clock without sending the fixture tones to speakers.
"""
import argparse
import array
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import wave

ROOT = Path(__file__).resolve().parents[2]

def wav(path, duration, level):
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = array.array('h', (round(32767 * level(i / 24000) * math.sin(i * 2 * math.pi * 400 / 24000))
                               for i in range(round(duration * 24000))))
    if __import__('sys').byteorder != 'little':
        samples.byteswap()
    with wave.open(str(path), 'wb') as output:
        output.setparams((1, 2, 24000, len(samples), 'NONE', 'not compressed'))
        output.writeframes(samples.tobytes())

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--renderer', choices=('gl', 'vulkan'), default='gl')
    parser.add_argument('--map', default='game/airdefense1')
    parser.add_argument('--size', default='1280x720')
    args = parser.parse_args()
    root = args.output.resolve(); game = root / 'save/baseoq4'; game.mkdir(parents=True, exist_ok=True)
    wav(game / 'sound/graph/pattern.wav', 4, lambda t: .4 if .8 <= t < 1.6 else .8 if 2.4 <= t < 3.2 else 0)
    wav(game / 'sound/graph/silence.wav', 4, lambda t: 0)
    wav(game / 'sound/graph/tone.wav', 1, lambda t: .6)
    stages = [
        'notarget', 'testRadioChatter sound/graph/pattern.wav',
        'waitMsec 400', 'testRadioChatter probe', 'screenshot screenshots/radio-silence.tga',
        'waitMsec 800', 'testRadioChatter probe', 'screenshot screenshots/radio-speech.tga',
        'waitMsec 1600', 'testRadioChatter probe', 'screenshot screenshots/radio-loud.tga',
        'testRadioChatter pause', 'testRadioChatter probe', 'waitMsec 300', 'testRadioChatter probe', 'testRadioChatter resume',
        'testRadioChatter sound/graph/silence.wav', 'testRadioChatter distract sound/graph/tone.wav',
        'set s_constantAmplitude 1', 'waitMsec 300', 'testRadioChatter probe', 'set s_constantAmplitude -1',
        'testRadioChatter sound/graph/tone.wav', 'waitMsec 350', 'testRadioChatter probe',
        'set ui_retainedReducedMotion 1', 'screenshot screenshots/radio-reduced.tga',
        'set ui_retainedReducedMotion 0', 'set ui_retained 0', 'screenshot screenshots/radio-classic.tga', 'set ui_retained 1',
        # Finish rebuilding UI resources before starting the timed audio case.
        # waitMsec uses wall time and can expire inside a single cold UI frame,
        # before the sound world's next update advances its playback cursor.
        'wait 2',
        'testRadioChatter stop', 'testRadioChatter probe', 'testRadioChatter sound/graph/tone.wav',
        'waitMsec 1500', 'testRadioChatter probe', 'screenshot screenshots/radio-finished.tga',
        'testRadioChatter vo_1_1_3_55_2', 'waitMsec 700', 'testRadioChatter probe', 'screenshot screenshots/radio-retail.tga',
        'waitMsec 300', 'testRadioChatter probe', 'testRadioChatter stop', 'echo AUDIO_GRAPHS_COMPLETE', 'quit'
    ]
    # Map-script chatter timers can hide the diagnostic display. Show the
    # plate for a capture without restarting or otherwise altering the audio.
    stages = [f'testRadioChatter show\nscreenshot "{line.removeprefix("screenshot ")}"' if line.startswith('screenshot ') else line for line in stages]
    (game / 'audio-graphs.cfg').write_text('\n'.join(stages) + '\n', encoding='utf-8')
    width, height = args.size.split('x')
    cvars = {
        'fs_basepath': str(args.assets.resolve()), 'fs_savepath': str(root / 'save'), 'fs_devpath': str(root / 'save'),
        'fs_game': 'baseoq4', 'com_gameMode': 'SP', 'logFile': '2', 'logFileName': 'logs/openq4.log',
        'r_fullscreen': '0', 'r_fullscreenDesktop': '0', 'r_borderless': '0', 'r_borderlessDefaultMigrated': '1', 'r_hiddenWindow': '1',
        'r_windowWidth': width, 'r_windowHeight': height, 'r_mode': '-1', 'r_customWidth': width, 'r_customHeight': height,
        'r_renderApi': args.renderer, 'r_multiSamples': '0', 'r_swapInterval': '1',
        'in_mouse': '0', 'in_joystick': '0', 'in_joystickRumble': '0', 's_noSound': '0',
        'com_skipLogoVideos': '1', 'g_autoSkipCinematics': '1', 'com_skipLoadingContinue': '1', 'com_maxfps': '60',
        'ui_autoJoin': '0', 'ui_retained': '1', 'ui_retainedReducedMotion': '0',
        'g_autoExecAfterMapLoad': 'audio-graphs.cfg', 'g_autoExecAfterMapLoadDelayMs': '3000'
    }
    command = [str(ROOT / '.install' / ('openQ4-client_x64.exe' if os.name == 'nt' else 'openQ4-client_x64'))]
    for key, value in cvars.items(): command += ['+set', key, value]
    command += ['+map', args.map]
    options = {'env': {**os.environ, 'ALSOFT_DRIVERS': 'null', 'TEMP': str(ROOT / '.tmp'), 'TMP': str(ROOT / '.tmp')}}
    if os.name == 'nt':
        startup = subprocess.STARTUPINFO(); startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW; startup.wShowWindow = 0
        options.update(startupinfo=startup, creationflags=subprocess.CREATE_NO_WINDOW)
    started = time.time()
    with (root / 'process.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=ROOT / '.install', stdout=log, stderr=subprocess.STDOUT, timeout=180, **options)
    log = (game / 'logs/openq4.log').read_text(encoding='utf-8', errors='replace')
    rows = [[float(v) for v in row.split()] for row in re.findall(r'^AUDIO_GRAPH (.*)$', log, re.M)]
    report = {'renderer': args.renderer, 'map': args.map, 'returncode': result.returncode, 'peaks': rows,
              'complete': 'AUDIO_GRAPHS_COMPLETE' in log, 'audio_output': 'OpenAL null', 'microphone': False,
              'host_input': False, 'captures': 'engine screenshot command', 'checks': {}}
    if len(rows) == 11:
        report['checks'] = {
            'silence': max(rows[0]) == 0,
            'speech_level': .35 < max(rows[1]) < .45,
            'louder_phrase': .75 < max(rows[2]) < .85,
            'pause_holds_cursor': rows[3] == rows[4],
            'channel_isolation_and_no_fake_amplitude': max(rows[5]) == 0,
            'new_sample_and_empty_prehistory': .55 < max(rows[6]) < .65 and min(rows[6]) == 0,
            'stop_clears': max(rows[7]) == 0,
            'completion_clears': max(rows[8]) == 0,
            'retail_line_varies': max(rows[9]) > 0 and len(set(rows[9])) > 3 and rows[9] != rows[10]
        }
    from PIL import Image
    shots = [shot for shot in (game / 'screenshots').glob('*.tga') if shot.stat().st_mtime >= started]
    report['checks']['engine_captures'] = len(shots) == 7 and 'screenshot: bad dimensions' not in log
    for shot in shots:
        Image.open(shot).convert('RGB').save(shot.with_suffix('.png'))
    (root / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'peaks'}, indent=2))
    assert result.returncode == 0 and report['complete'] and len(rows) == 11 and all(report['checks'].values()), 'See report and engine log'

if __name__ == '__main__': main()
