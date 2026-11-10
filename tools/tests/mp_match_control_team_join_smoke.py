#!/usr/bin/env python3
"""Windowed, input-free check that Match Control's team join and the player's team agree.

A listen-server human and three bots play Team DM in warm-up, two a side. The
human asks Match Control to join Strogg, which si_autobalance refuses: the
refusal must name the reason and commit nothing, so the player and the session
both stay Marine. A Strogg bot then leaves, the same join becomes legal, and the
player and the session must both move to Strogg.
"""
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
STRINGS = ROOT / "content/baseoq4/pak0/strings/english_openq4.lang"
# Reports, and the two join requests between them, in the order they run.
CHECKPOINTS = ("LOBBY", "OPEN", "REFUSED", "REBALANCED", "JOINED")
MARKERS = ("LOBBY", "OPEN", "REFUSE", "REFUSED", "REBALANCED", "ALLOW", "JOINED")


def checkpoint(name: str) -> list[str]:
    return [f"echo MP_TEAMJOIN_{name.upper()}", "openq4_reportMPState", "openq4_matchControl report"]


def english(key: str) -> str:
    match = re.search(rf'^\s*"{re.escape(key)}"\s+"(.*)"\s*$',
                      STRINGS.read_text(encoding="utf-8"), re.MULTILINE)
    if match is None:
        raise SystemExit(f"{STRINGS.name} lacks {key}")
    return match[1]


def section(log: str, name: str) -> str:
    """The log from one marker to the next, matching whole marker names."""
    marker = re.search(rf"\nMP_TEAMJOIN_{name}\b", log)
    if marker is None:
        return ""
    later = re.search(rf"\nMP_TEAMJOIN_(?:{'|'.join(MARKERS)})\b", log[marker.end():])
    return log[marker.start():marker.end() + later.start()] if later else log[marker.start():]


def snapshot(text: str) -> dict:
    players = {int(slot): (int(team), int(spectating))
               for slot, team, spectating in re.findall(
                   r"MP_PLAYER slot=(\d+) bot=\d+ team=(-?\d+) health=-?\d+ spectating=(\d+)", text)}
    view = re.search(r"MP_VIEW slot=0 side=(-?\d+) roles=\d+ active=(\d+) phase=(\d+) .*?revision=(\d+)", text)
    result = re.search(r"MP_CONTROL match_result_message=([^\r\n]*)", text)
    return {"players": players,
            "side": int(view[1]) if view else None, "active": int(view[2]) if view else None,
            "phase": int(view[3]) if view else None, "revision": int(view[4]) if view else None,
            "result": result[1] if result else None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, default=ROOT / ".install")
    parser.add_argument("--executable-name", help="runtime executable basename for an isolated test copy")
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".tmp/mp-match-control-team-join-smoke")
    parser.add_argument("--basepath", type=Path, default=Path(r"C:\Program Files (x86)\Steam\steamapps\common\Quake 4"))
    parser.add_argument("--timeout", type=int, default=150)
    args = parser.parse_args()
    runtime, output = args.runtime_dir.resolve(), args.output_dir.resolve()
    suffix = ".exe" if os.name == "nt" else ""
    executable = args.executable_name or f"openQ4-client_x64{suffix}"
    verify_runtime_is_current(runtime, executable)
    exe = runtime / executable
    if not exe.is_file() or not args.basepath.is_dir():
        parser.error("the runtime executable and installed Quake 4 assets are required")
    savepath = output / "save"
    gamepath = savepath / "baseoq4"
    gamepath.mkdir(parents=True, exist_ok=True)
    # Each bot takes the side with fewer players: Strogg, Marine, Strogg. The
    # human (slot 0) and Rhodes (slot 2) are Marine; Cortez and Sledge Strogg.
    script = [
        "addbot Cortez 3 exact", "waitMsec 400", "addbot Rhodes 3 exact", "waitMsec 400",
        "addbot Sledge 3 exact", "waitMsec 3000",
        *checkpoint("lobby"),
        "openq4_matchControl open", "waitMsec 1500",
        *checkpoint("open"),
        "echo MP_TEAMJOIN_REFUSE", "openq4_matchControl action team_join_strogg", "waitMsec 3000",
        *checkpoint("refused"),
        "kick 3", "waitMsec 2500",
        *checkpoint("rebalanced"),
        "echo MP_TEAMJOIN_ALLOW", "openq4_matchControl action team_join_strogg", "waitMsec 3000",
        *checkpoint("joined"),
        "quit",
    ]
    (gamepath / "mp_team_join_smoke.cfg").write_text("\n".join(script) + "\n", encoding="utf-8")
    cvars = {
        "win_allowMultipleInstances" if os.name == "nt" else "sys_allowMultipleInstances": "1",
        "fs_basepath": str(args.basepath.resolve()), "fs_savepath": str(savepath),
        "fs_devpath": str(savepath), "fs_game": "baseoq4", "com_gameMode": "MP",
        "r_fullscreen": "0", "r_borderless": "0", "r_fullscreenDesktop": "0",
        "r_borderlessDefaultMigrated": "1", "r_mode": "-1", "r_customWidth": "960",
        "r_customHeight": "540", "r_windowWidth": "960", "r_windowHeight": "540",
        "r_hiddenWindow": "1", "in_mouse": "0", "in_joystick": "0", "s_noSound": "1",
        "r_renderApi": "gl", "com_maxfps": "60", "r_swapInterval": "0",
        "logFile": "2", "logFileName": "logs/openq4.log", "developer": "1",
        "net_port": "28851", "net_ip": "127.0.0.1", "net_enableIPv6": "0",
        "net_serverDedicated": "0", "net_LANServer": "1", "si_pure": "0",
        "si_maxPlayers": "8", "si_gameType": "Team DM", "si_warmup": "1", "si_useReady": "1",
        "si_minPlayers": "2", "si_timeLimit": "10", "si_fragLimit": "999", "si_autoBalance": "1",
        "bot_pause": "1", "bot_minPlayers": "0", "g_matchProfile": "casual",
        "ui_autoJoin": "1", "ui_spectate": "Play", "ui_ready": "Not Ready", "ui_team": "Marine",
        # The stock in-match menu, which the retained Escape card would cover.
        "ui_retained": "0", "ui_retainedMultiplayer": "0", "net_allowCheats": "1", "com_skipLoadingContinue": "1",
        "g_autoExecAfterMapLoad": "mp_team_join_smoke.cfg", "g_autoExecAfterMapLoadDelayMs": "1000",
    }
    command = [str(exe)]
    for name, value in cvars.items():
        command += ["+set", name, value]
    command += ["+spawnServer", "mp/q4dm1"]
    assert len(cvars) + 1 <= 64, "engine startup command capacity exceeded"
    (output / "launch.json").write_text(json.dumps(command, indent=2), encoding="utf-8")
    with (output / "console.log").open("w", encoding="utf-8") as console:
        started = time.time()
        process = subprocess.Popen(command, cwd=runtime, stdout=console, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            process.kill()  # Only the process launched by this test.
            process.wait()
            code = -1

    log_path = gamepath / "logs/openq4.log"
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
    states = {name: snapshot(section(log, name)) for name in CHECKPOINTS}
    team_join = english("#str_42313")
    refused = " | ".join((team_join, english("#str_42620"), english("#str_42391")))
    committed = " | ".join((team_join, english("#str_42621"), english("#str_42360")))
    failures = []
    if not log_path.is_file() or log_path.stat().st_mtime < started:
        failures.append("missing fresh engine log")
    for name, state in states.items():
        if state["side"] is None or not state["players"]:
            failures.append(f"{name}: missing player or accepted-view report")
    lobby, opened, refusal, rebalanced, joined = (states[name] for name in CHECKPOINTS)
    if lobby["players"] != {0: (0, 0), 1: (1, 0), 2: (0, 0), 3: (1, 0)}:
        failures.append(f"the fixture is not two a side: {lobby['players']}")
    if opened["phase"] != 1 or opened["side"] != 0 or opened["active"] != 1:
        failures.append(f"the human is not an active Marine in warm-up: {opened}")
    if refusal["players"].get(0) != (0, 0) or refusal["side"] != 0:
        failures.append(f"a refused join moved the player or the session: {refusal}")
    if refusal["revision"] != opened["revision"]:
        failures.append("a refused join changed the session "
                        f"(revision {opened['revision']} -> {refusal['revision']})")
    if refusal["result"] != refused:
        failures.append(f"the refusal does not name its reason: {refusal['result']!r} != {refused!r}")
    if re.search(r"joined Strogg team", "".join(
            section(log, name) for name in ("REFUSE", "REFUSED", "REBALANCED"))):
        failures.append("the player joined Strogg although the join was refused")
    if rebalanced["players"] != {0: (0, 0), 1: (1, 0), 2: (0, 0)}:
        failures.append(f"the kick did not leave one Strogg bot: {rebalanced['players']}")
    if joined["players"].get(0, (None,))[0] != 1 or joined["side"] != 1 or joined["active"] != 1:
        failures.append(f"an allowed join left the player and session apart: {joined}")
    if joined["result"] != committed:
        failures.append(f"the allowed join was not committed: {joined['result']!r}")
    if not re.search(r"joined Strogg team", section(log, "ALLOW") + section(log, "JOINED")):
        failures.append("the player's own team never changed to Strogg")
    if re.search(r"FATAL ERROR|ERROR:|Unknown command|MP_CONTROL action requires|MP_CONTROL rejected|"
                 r"rejected match (?:round )?transition", log, re.IGNORECASE):
        failures.append("engine log contains an error, an unknown command or a rejected control action")
    if code != 0:
        failures.append(f"engine exit code {code}")
    report = {"status": "fail" if failures else "pass", "states": states,
              "failures": failures, "log": str(log_path)}
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
