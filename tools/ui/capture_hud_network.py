#!/usr/bin/env python3
"""Qualify the retained network graph on a real loopback multiplayer client.

Uses the staged dedicated server/client, private profiles and engine screenshots.
No device input or operating-system capture is used.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import capture_retained_screens as capture

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/tests'))
from mp_round_remote_smoke import read_log, verify_runtime_is_current, write_script


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, default=ROOT / '.install')
    parser.add_argument('--renderer', choices=('gl', 'vulkan'), default='gl')
    parser.add_argument('--port', type=int, default=28951)
    args = parser.parse_args()
    output, runtime = args.output.resolve(), args.runtime.resolve()
    if output.exists() or not output.is_relative_to((ROOT / '.tmp').resolve()):
        parser.error('use a fresh output beneath .tmp')
    if not 1024 <= args.port <= 65534:
        parser.error('port must reserve two consecutive unprivileged ports')
    suffix = '.exe' if os.name == 'nt' else ''
    for name in ('openQ4-client_x64', 'openQ4-ded_x64'):
        verify_runtime_is_current(runtime, name + suffix)
    games = {role: output / role / 'baseoq4' for role in ('server', 'client')}
    for game in games.values():
        game.mkdir(parents=True)
    logs = {role: game / 'logs/openq4.log' for role, game in games.items()}
    server_loop = games['server'] / 'hud-network-host.cfg'
    write_script(server_loop, ['echo HUD_NETWORK_HOST_READY', 'waitMsec 250', 'exec "hud-network-host.cfg"'])
    write_script(games['client'] / 'hud-network-client.cfg', [
        'set g_autoExecAfterMapLoad ""', 'set developer 1', 'waitMsec 1500', 'openq4_assertMPClientActive',
        'screenshot "screenshots/network.tga"', 'set ui_retained 0', 'waitMsec 200',
        'screenshot "screenshots/stock.tga"', 'set ui_retained 1', 'waitMsec 300',
        'screenshot "screenshots/restored.tga"', 'echo HUD_NETWORK_COMPLETE', 'quit',
    ])
    common = {
        'win_allowMultipleInstances' if os.name == 'nt' else 'sys_allowMultipleInstances': '1',
        'fs_basepath': str(args.assets.resolve()), 'fs_game': 'baseoq4', 'com_gameMode': 'MP',
        'si_gameType': 'DM', 'com_nextGameModule': 'game_mp',
        'logFile': '2', 'logFileName': 'logs/openq4.log', 'developer': '0', 'ui_retained': '1',
        'r_fullscreen': '0', 'r_fullscreenDesktop': '0', 'r_borderless': '0',
        'r_borderlessDefaultMigrated': '1', 'r_hiddenWindow': '1', 'r_mode': '-1',
        'r_customWidth': '1280', 'r_customHeight': '720', 'r_windowWidth': '1280', 'r_windowHeight': '720',
        'in_mouse': '0', 'in_joystick': '0', 'in_joystickRumble': '0', 's_noSound': '1',
        'r_renderApi': args.renderer, 'com_maxfps': '60', 'r_swapInterval': '0',
        'com_skipLoadingContinue': '1', 'com_skipLogoVideos': '1', 'ui_autoJoin': '1',
        'ui_spectate': 'Play', 'net_allowCheats': '1', 'net_LANServer': '1',
    }
    processes, streams, commands, codes = {}, [], {}, {}
    failures = []
    options = {'env': {**os.environ, 'TEMP': str(ROOT / '.tmp'), 'TMP': str(ROOT / '.tmp')}}
    if os.name == 'nt':
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        options.update(startupinfo=startup, creationflags=subprocess.CREATE_NO_WINDOW)

    def launch(role: str) -> None:
        cvars = dict(common, fs_savepath=str(games[role].parent), fs_devpath=str(games[role].parent),
                     net_port=str(args.port + (role == 'client')))
        if role == 'server':
            cvars.update(net_serverDedicated='1', si_pure='0', si_gameType='DM', si_maxPlayers='4',
                         si_minPlayers='1', si_warmup='0', bot_minPlayers='0')
            command = [str(runtime / ('openQ4-ded_x64' + suffix))]
            actions = ['+spawnServer', 'mp/q4dm1', '+exec', server_loop.name]
        else:
            cvars.update(net_clientLagOMeter='1', net_clientLagOMeterResolution='1',
                         g_autoExecAfterMapLoad='hud-network-client.cfg', g_autoExecAfterMapLoadDelayMs='3000')
            command = [str(runtime / ('openQ4-client_x64' + suffix))]
            actions = ['+connect', f'127.0.0.1:{args.port}']
        for key, value in cvars.items():
            command += ['+set', key, value]
        commands[role] = command + actions
        stream = (output / f'{role}-process.log').open('w', encoding='utf-8')
        streams.append(stream)
        processes[role] = subprocess.Popen(commands[role], cwd=runtime, stdout=stream,
                                           stderr=subprocess.STDOUT, **options)

    started = time.monotonic()
    try:
        launch('server')
        while time.monotonic() - started < 180:
            if 'client' not in processes and 'HUD_NETWORK_HOST_READY' in read_log(logs['server']):
                launch('client')
            if 'client' in processes and processes['client'].poll() is not None:
                break
            if processes['server'].poll() is not None:
                failures.append('dedicated server exited before the client completed')
                break
            time.sleep(.2)
        else:
            failures.append('network HUD capture timed out')
    finally:
        write_script(server_loop, ['quit'])
        for role, process in processes.items():
            try:
                codes[role] = process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()  # Only processes created by this harness.
                process.wait()
                codes[role] = -1
        for stream in streams:
            stream.close()
    client = re.sub(r'\^[0-9]', '', read_log(logs['client']))
    traces = re.findall(r'HUD_COVERAGE .*', client)
    warnings = [line for line in client.splitlines() if 'HUD coverage:' in line or
                ('retained' in line.lower() and ('WARNING' in line or 'ERROR' in line))]
    if set(codes) != {'server', 'client'} or any(codes.values()):
        failures.append(f'unclean exit: {codes}')
    if 'HUD_NETWORK_COMPLETE' not in client or 'OPENQ4_STOCK_BASELINE_MP_CLIENT_ACTIVE' not in client:
        failures.append('client did not finish active gameplay')
    if not any('source=native/lagometer ' in line for line in traces):
        failures.append('client network graph did not submit retained geometry')
    if warnings or 'ERROR:' in client or 'FATAL:' in client:
        failures.append('HUD warning or engine error')
    shots = [str(capture.to_png(path).relative_to(ROOT))
             for path in sorted((games['client'] / 'screenshots').glob('*.tga'))]
    result = {'complete': not failures, 'seconds': round(time.monotonic() - started, 1),
              'renderer': args.renderer, 'codes': codes, 'failures': failures, 'hud_traces': traces,
              'hud_warnings': warnings, 'screenshots': shots, 'commands': commands,
              'logs': {role: str(path.relative_to(ROOT)) for role, path in logs.items()},
              'host_input_injection': False, 'windowed': True, 'hidden_window': True}
    (output / 'report.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('complete', 'codes', 'failures', 'hud_traces', 'hud_warnings')}, indent=2))
    assert not failures, failures


if __name__ == '__main__':
    main()
