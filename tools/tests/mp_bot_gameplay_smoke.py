#!/usr/bin/env python3
"""Observe autonomous stock-map bots with a hidden, windowed listen-server client."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

from mp_round_remote_smoke import verify_runtime_is_current

ROOT = Path(__file__).resolve().parents[2]
NAMES = ("Cortez", "Rhodes", "Sledge", "Voss", "Strauss", "Kane", "Morris", "Tetzlaff")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, default=ROOT / ".install")
    parser.add_argument("--executable-name", default="openQ4-client_x64.exe" if os.name == "nt" else "openQ4-client_x64")
    parser.add_argument("--basepath", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".tmp/mp-bot-gameplay")
    parser.add_argument("--gametype", choices=("DM", "Team DM", "CTF"), default="DM")
    parser.add_argument("--map", dest="map_name")
    parser.add_argument("--bots", type=int, choices=range(2, 9), default=4)
    parser.add_argument("--seconds", type=int, default=45)
    parser.add_argument("--port", type=int, default=28971)
    parser.add_argument("--timeout", type=int, default=150)
    args = parser.parse_args()
    if args.seconds < 10 or args.timeout <= args.seconds or not 1024 <= args.port <= 65535:
        parser.error("use at least 10 seconds, a longer timeout and an unprivileged port")
    runtime, output = args.runtime_dir.resolve(), args.output_dir.resolve()
    verify_runtime_is_current(runtime, args.executable_name)
    exe = runtime / args.executable_name
    if not exe.is_file() or not (args.basepath / "q4base").is_dir():
        parser.error("the staged client and retail q4base assets are required")
    save = output / "save"
    game = save / "baseoq4"
    game.mkdir(parents=True, exist_ok=True)
    map_name = args.map_name or ("mp/q4ctf1" if args.gametype == "CTF" else "mp/q4dm1")
    # Public matches require one active human. The local client supplies that
    # participant without taking keyboard/mouse input or distracting the bots.
    script = ["notarget", "god", *[f"addbot {name} 4 exact" for name in NAMES[:args.bots]],
              "waitMsec 3000", "botlist", "echo MP_BOT_SAMPLE_BEGIN"]
    for _ in range(args.seconds // 2):
        script += ["waitMsec 2000", "openq4_reportMPState"]
    script += ["echo MP_BOT_SAMPLE_END", "quit"]
    (game / "bot_gameplay_smoke.cfg").write_text("\n".join(script) + "\n", encoding="utf-8")
    cvars = {
        "win_allowMultipleInstances" if os.name == "nt" else "sys_allowMultipleInstances": "1",
        "sys_consoleWindow": "0", "in_tty": "0", "in_mouse": "0", "in_joystick": "0",
        "r_fullscreen": "0", "r_borderless": "0", "r_fullscreenDesktop": "0",
        "r_borderlessDefaultMigrated": "1", "r_hiddenWindow": "1", "s_noSound": "1",
        "r_mode": "-1", "r_customWidth": "640", "r_customHeight": "480", "r_renderApi": "gl",
        "r_swapInterval": "0", "com_maxfps": "60",
        "fs_basepath": str(args.basepath.resolve()), "fs_savepath": str(save), "fs_devpath": str(save),
        "fs_game": "baseoq4", "com_gameMode": "MP", "logFile": "2", "logFileName": "logs/openq4.log",
        "developer": "1", "ui_autoJoin": "1", "ui_spectate": "Play", "ui_name": "BotAuditObserver",
        "net_serverDedicated": "0", "net_LANServer": "1",
        "net_allowCheats": "1", "sv_cheats": "1",
        "net_port": str(args.port), "si_pure": "0", "si_gameType": args.gametype,
        "si_maxPlayers": str(args.bots + 1), "si_minPlayers": "2", "si_warmup": "0", "si_useReady": "0",
        "si_fragLimit": "999", "si_captureLimit": "999", "si_timeLimit": "0",
        "g_matchProfile": "casual", "bot_enable": "1", "bot_minPlayers": "0", "bot_pause": "0",
        "bot_characters": "1", "bot_skillVariance": "0", "bot_chat": "0", "bot_debug": "2",
        "bot_debugAim": "1",
        "com_skipLoadingContinue": "1", "g_autoExecAfterMapLoad": "bot_gameplay_smoke.cfg",
        "g_autoExecAfterMapLoadDelayMs": "500",
    }
    command = [str(exe)]
    for name, value in cvars.items():
        command += ["+set", name, value]
    command += ["+spawnServer", map_name]
    assert len(cvars) + 1 <= 64, "engine startup command capacity exceeded"
    (output / "launch.json").write_text(json.dumps(command, indent=2), encoding="utf-8")
    log_path = game / "logs/openq4.log"
    started = time.time()
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (output / "console.log").open("w", encoding="utf-8") as console:
        process = subprocess.Popen(command, cwd=runtime, stdout=console, stderr=subprocess.STDOUT,
                                   creationflags=creationflags)
        try:
            code = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            code = -1
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    sample = log.partition("\nMP_BOT_SAMPLE_BEGIN")[2].partition("\nMP_BOT_SAMPLE_END")[0]
    failures = []
    if code != 0 or "\nMP_BOT_SAMPLE_END" not in log:
        failures.append(f"server failed to complete (exit {code})")
    if not log_path.is_file() or log_path.stat().st_mtime < started:
        failures.append("missing fresh engine log")
    errors = re.findall(r"^.*(?:ERROR:|FATAL:|Unknown command|Assertion failed|not valid in multiplayer mode).*$", log, re.M)
    failures.extend(errors)
    if "unreliable batch full" in sample:
        failures.append("unreliable message batches are accumulating for bots")
    live = set(re.findall(r"MP_PLAYER slot=(\d+) bot=1 .*spectating=0 wantSpectate=0 ingame=1", sample))
    if len(live) != args.bots:
        failures.append(f"only {len(live)}/{args.bots} bots reached gameplay")
    if not re.search(r"MP_STATE .*phase=3 ", sample):
        failures.append("no live match phase")
    poses: dict[str, list[tuple[float, ...]]] = {}
    for slot, coordinates in re.findall(r"MP_POSE slot=(\d+) entity=\S+ origin=([^\r\n]+?) hidden=", sample):
        poses.setdefault(slot, []).append(tuple(map(float, coordinates.split())))
    displacement = {}
    for slot in live:
        positions = poses.get(slot, [])
        distance = max((sum((a-b)**2 for a, b in zip(p, positions[0]))**0.5 for p in positions), default=0)
        displacement[slot] = round(distance, 1)
        if len(set(positions)) < 3 or distance < 128:
            failures.append(f"bot {slot} did not demonstrate sustained movement")
    shots = len(re.findall(r"^bot .*: (?:fire|suppress) at ", sample, re.M))
    scores = [int(x) for x in re.findall(r"MP_PLAYER .* score=(-?\d+)", sample)]
    damaged = bool(re.search(r"MP_PLAYER .*bot=1 .*health=(?:[1-9]\d?|0|-\d+) ", sample))
    if not shots or not (damaged or any(score > 0 for score in scores)):
        failures.append("no firing and damage/scoring evidence")
    objectives = sorted(set(re.findall(r"goal objective:(\w+)", sample)))
    if args.gametype == "CTF" and not objectives:
        failures.append("no CTF objective decisions")
    report = {"gametype": args.gametype, "map": map_name, "bots": args.bots, "exit_code": code,
              "elapsed_seconds": round(time.time()-started, 1), "displacement": displacement,
              "fire_events": shots, "max_score": max(scores, default=0), "objectives": objectives,
              "warnings": sorted(set(re.findall(r"^.*WARNING:.*$", log, re.M))), "failures": failures,
              "log": str(log_path)}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**report, "warnings": len(report["warnings"]), "report": str(output / "report.json")}, indent=2))
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
