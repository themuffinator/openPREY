#!/usr/bin/env python3
"""Generate .vscode/launch.json, the VS Code launch configurations.

The JSON is generated: edit the tables here and rerun this script.
tools/tests/vscode_fast_build.py fails while launch.json holds anything else
(formatting aside, so reformatting it in the editor is harmless).

Every configuration runs the client that the VS Code build task stages into
.install, with .home as the savepath, and pins the archived CVars that decide
what a launch exercises, so a value left in .home/<game>/openQ4Config.cfg
cannot change it: r_renderApi (each launch is a GL and Vulkan pair),
ui_retained 1 for the retained RmlUi interface (only the "Stock UI" entries
turn it off), r_fullscreen, g_autoSkipCinematics in single player and
ui_autoJoin 0 in multiplayer, which opens at the join screen.

fs_basepath is left unset: the engine finds the installed Quake 4 through
Steam or GOG, or OPENQ4_QUAKE4_PATH, so no machine's path is baked in.

Each group gets a separator in the Run and Debug list. VS Code orders the
groups by name, so every name starts with its position.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LAUNCH_JSON = ROOT / ".vscode" / "launch.json"

GL = ("GL", "gl")
VULKAN = ("Vulkan", "vulkan")
RENDERERS = (GL, VULKAN)

# Set first on every launch. A launch's own value replaces one in place.
COMMON_CVARS = (
    ("logFile", "2"),
    ("logFileName", "logs/openq4.log"),
    ("developer", "1"),
    ("r_fullscreen", "0"),
    ("fs_savepath", "${workspaceFolder}\\.home"),
    ("fs_devpath", "${workspaceFolder}\\.install"),
)
SINGLE_PLAYER_CVARS = (
    ("si_gameType", "singleplayer"),
    ("com_skipLoadingContinue", "1"),
    ("g_autoSkipCinematics", "0"),
)
# A listen server; si_gameType comes from the launch.
MULTIPLAYER_CVARS = (
    ("net_serverDedicated", "0"),
    ("net_serverAllowServerMod", "1"),
    ("si_pure", "0"),
    ("sv_cheats", "1"),
    ("ui_autoJoin", "0"),
)


@dataclass(frozen=True)
class Launch:
    """One launch, written as one configuration per renderer."""

    name: str
    game_type: str = "singleplayer"
    game: str = "baseoq4"
    command: tuple[str, ...] = ()
    cvars: tuple[tuple[str, str], ...] = ()
    retained: bool = True
    renderers: tuple[tuple[str, str], ...] = RENDERERS

    @property
    def multiplayer(self) -> bool:
        return self.game_type != "singleplayer"


def campaign(maps: tuple[tuple[str, str], ...], game: str = "baseoq4", prefix: str = "") -> tuple[Launch, ...]:
    # A second word in the label is the visit for maps played twice.
    launches = []
    for label, title in maps:
        map_name, *visit = label.split()
        launches.append(Launch(f"{prefix}{label} '{title}'", game=game, command=("+map", f"game/{map_name}", *visit)))
    return tuple(launches)


def servers(
    maps: tuple[tuple[str, str], ...], game_type: str, game: str = "baseoq4", prefix: str = ""
) -> tuple[Launch, ...]:
    return tuple(
        Launch(f"{prefix}{map_name} '{title}'", game_type, game, ("+spawnServer", f"mp/{map_name}"))
        for map_name, title in maps
    )


QUAKE4_CAMPAIGN = (
    ("airdefense1", "AIR DEFENSE BUNKER"),
    ("airdefense2", "AIR DEFENSE TRENCHES"),
    ("hangar1", "HANGAR PERIMETER"),
    ("hangar2", "INTERIOR HANGAR"),
    ("mcc_landing", "MCC LANDING SITE"),
    ("mcc_1", "OPERATION: ADVANTAGE"),
    ("convoy1", "CANYON"),
    ("building_b", "PERIMETER DEFENSE STATION"),
    ("convoy2", "AQUEDUCTS"),
    ("convoy2b", "AQUEDUCTS ANNEX"),
    ("hub1", "NEXUS HUB TUNNELS"),
    ("hub2", "NEXUS HUB"),
    ("medlabs", "STROGG MEDICAL FACILITIES"),
    ("walker", "CONSTRUCTION ZONE"),
    ("dispersal", "DISPERSAL FACILITY"),
    ("recomp", "RECOMPOSITION CENTER"),
    ("putra", "PUTRIFICATION CENTER"),
    ("waste", "WASTE PROCESSING FACILITY"),
    ("mcc_2", "OPERATION: LAST HOPE"),
    ("storage1 first", "DATA STORAGE TERMINAL"),
    ("storage2", "DATA STORAGE SECURITY"),
    ("storage1 second", "DATA STORAGE TERMINAL"),
    ("tram1", "TRAM HUB STATION"),
    ("tram1b", "TRAM RAIL"),
    ("process1 first", "DATA PROCESSING TERMINAL"),
    ("process2", "DATA PROCESSING SECURITY"),
    ("process1 second", "DATA PROCESSING TERMINAL"),
    ("network1", "DATA NETWORKING TERMINAL"),
    ("network2", "DATA NETWORKING SECURITY"),
    ("core1", "NEXUS CORE"),
    ("core2", "THE NEXUS"),
)

QUAKE4_CAMPAIGN_TESTS = (
    Launch(
        "airdefense1 'AIR DEFENSE BUNKER' - Loading Continue Gate",
        cvars=(
            ("logFileName", "logs/phase02_loading_continue_clean.log"),
            ("com_skipLoadingContinue", "0"),
            ("com_loadingContinueAutoAdvance", "1000"),
            ("com_showFramePacing", "2"),
            ("r_swapInterval", "0"),
            ("com_maxfps", "240"),
        ),
        command=("+map", "game/airdefense1", "+wait", "240", "+quit"),
    ),
    Launch(
        "airdefense2 'AIR DEFENSE TRENCHES' - Door Test",
        command=("+map", "game/airdefense2", "+wait", "120", "+setviewpos", "-352", "1776", "256", "0"),
    ),
    Launch(
        "mcc_landing 'MCC LANDING SITE' - Borked Lift Test",
        cvars=(("logFileName", "logs/openq4_borkedlift.log"), ("sv_cheats", "1")),
        command=("+map", "game/mcc_landing", "+wait", "240", "+god", "+notarget", "+mccLandingBorkedLiftTest"),
    ),
    Launch(
        "convoy2b 'AQUEDUCTS ANNEX' - Unlocked Hovertank",
        cvars=(("g_openQ4Convoy2bUnlockedHovertank", "1"), ("g_openQ4Convoy2bNoActors", "1")),
        command=("+map", "game/convoy2b"),
    ),
    Launch(
        "storage1 first 'DATA STORAGE TERMINAL' - No Drop Pod",
        cvars=(("g_openQ4Storage1NoDropPodState", "1"),),
        command=("+map", "game/storage1", "first"),
    ),
)

# Titles are the expansion's mapDef names.
AWAKENING_CAMPAIGN = (
    ("m01_stranarus_trench1", "STRANARUS TRENCH"),
    ("m01_stranarus_trench2", "STRANARUS TRENCH"),
    ("m02_trianfac", "TRIANTHINIDE FACILITY"),
    ("m03_airassault", "AIRBORNE ASSAULT"),
    ("m04_prison", "PRISON"),
    ("m05_bio", "BIO PROCESSING"),
    ("m06_mcc", "MOBILE COMMAND CENTER"),
    ("m06_mcc_invasion", "MOBILE COMMAND CENTER"),
    ("m07_race", "RACE 1: MCC DEPARTURE"),
    ("m07_race1", "RACE 2: AQUEDUCTS"),
    ("m07_race2", "RACE 3: CRYOGENICS APPROACH"),
    ("m08_cryofac", "CRYOGENIC FACILITY"),
    ("m09_valkaryne", "VALKARYNE"),
)

# The q4x maps here are the retail patch's (pak019), not the expansion's.
DEATHMATCH = (
    ("q4dm1", "THE FRAGGING YARD"),
    ("q4dm2", "SANDSTORM"),
    ("q4dm3", "THE LOST FLEET"),
    ("q4dm4", "BLOODWORK"),
    ("q4dm5", "THE ROSE"),
    ("q4dm6", "NO DOCTORS"),
    ("q4dm7", "OVER THE EDGE"),
    ("q4dm8", "THE LONGEST DAY"),
    ("q4dm9", "CAMPGROUNDS REDUX"),
    ("q4dm10", "OUTPATIENT"),
    ("q4dm11", "SKELETON CREW"),
    ("q4xdm10", "CENTRAL INDUSTRIAL"),
    ("q4xdm11", "WARFORGED"),
    ("q4xdm13", "STROYENT RED"),
    ("q4xdm14", "RETROPHOBOPOLIS"),
    ("q4xdm15", "FIREWALL"),
)
TOURNEY = (
    ("q4dm11v1", "THE FRAGGING YARD 1v1"),
    ("q4tourney1", "RAILED"),
    ("q4xtourney1", "STROGGENOMENON"),
    ("q4xtourney2", "VERTICON"),
)
CAPTURE_THE_FLAG = (
    ("q4ctf1", "HEARTLESS"),
    ("q4ctf2", "DEATH BEFORE DISHONOR"),
    ("q4ctf3", "SPEED TRAP"),
    ("q4ctf4", "RELATIVITY"),
    ("q4ctf5", "XAERO GRAVITY"),
    ("q4ctf6", "MIND THE GAP"),
    ("q4ctf7", "TREMORS"),
    ("q4ctf8", "DOUBLE EDGED"),
    ("q4xctf6", "CAVERNOUS CRYONICS"),
)
DEADZONE = (
    ("q4dz1", "HEARTLESS"),
    ("q4dz2", "DEATH BEFORE DISHONOR"),
    ("q4dz3", "SPEED TRAP"),
    ("q4dz4", "THE ROSE"),
)
# q4cmp_pak001.pk4
COMMUNITY_DEATHMATCH = (
    ("q4cmp1", "SPIRAL"),
    ("q4cmp2", "GRINDER"),
    ("q4cmp3", "PHRANTIC"),
    ("q4cmp4", "CITY HEAT"),
    ("q4cmp5", "RAVAGE"),
    ("q4cmp6", "PENETRATION"),
    ("q4cmp7", "CAUSTIC BURN"),
    ("q4cmp8", "BETTER THAN NOTHING"),
    ("q4cmp9", "WALLS OF HATE"),
    ("q4cmp10", "ARID WASTES"),
    ("q4cmp11", "SYSTEMATIC LOCKDOWN"),
    ("q4cmp12", "KAT FIGHT!"),
    ("q4cmp13", "LEARNING CURVE"),
)
COMMUNITY_CAPTURE_THE_FLAG = (
    ("q4cmp14", "ATOMS FOR PEACE"),
    ("q4cmp15", "CLINT EASTWOOD"),
)
# The expansion's multiplayer mapDefs reuse retail string ids, so these titles
# repeat stock ones, as they do in the game.
AWAKENING_CAPTURE_THE_FLAG = (
    ("q4xctf1", "HEARTLESS"),
    ("q4xctf2", "DEATH BEFORE DISHONOR"),
    ("q4xctf3", "SPEED TRAP"),
    ("q4xctf4", "RELATIVITY"),
    ("q4xctf5", "XAERO GRAVITY"),
    ("q4xctf6", "CAVERNOUS CRYONICS"),
)
AWAKENING_DEATHMATCH = (
    ("q4xdm1", "THE FRAGGING YARD"),
    ("q4xdm2", "SANDSTORM"),
    ("q4xdm3", "THE LOST FLEET"),
    ("q4xdm4", "BLOODWORK"),
    ("q4xdm5", "THE ROSE"),
    ("q4xdm6", "NO DOCTORS"),
    ("q4xdm10", "CENTRAL INDUSTRIAL"),
    ("q4xdm11", "WARFORGED"),
    ("q4xdm12", "METAL FIST MEAT"),
    ("q4xdm13", "STROYENT RED"),
    ("q4xdm14", "CLAUSTRO"),
    ("q4xdm15", "CAMPGROUNDS"),
)
AWAKENING_TOURNEY = (
    ("q4xtourney1", "STROGGENOMENON"),
)

# The Awakening's launches expect its content in .home/q4xbase/.
GROUPS = (
    ("01 Main menus", (
        Launch("Main menu"),
        Launch("Main menu", "DM"),
        Launch("Awakening main menu", game="q4xbase"),
        Launch("Awakening main menu", "DM", "q4xbase"),
    )),
    ("02 Main menu variants", (
        Launch("Main menu - Stock UI", retained=False),
        Launch("Main menu - Stock UI", "DM", retained=False),
        Launch("Main menu - Validation Layers", cvars=(("r_vkValidation", "1"),), renderers=(VULKAN,)),
    )),
    ("03 Quake 4 campaign", campaign(QUAKE4_CAMPAIGN)),
    ("04 Quake 4 campaign tests", QUAKE4_CAMPAIGN_TESTS),
    ("05 Awakening campaign", campaign(AWAKENING_CAMPAIGN, "q4xbase", "Awakening ")),
    ("06 Multiplayer: Deathmatch", servers(DEATHMATCH, "DM")),
    ("07 Multiplayer: Tourney", servers(TOURNEY, "Tourney")),
    ("08 Multiplayer: Capture the Flag", servers(CAPTURE_THE_FLAG, "CTF")),
    ("09 Multiplayer: DeadZone", servers(DEADZONE, "DeadZone")),
    ("10 Multiplayer: Community Map Pack",
     servers(COMMUNITY_DEATHMATCH, "DM") + servers(COMMUNITY_CAPTURE_THE_FLAG, "CTF")),
    ("11 Awakening multiplayer",
     servers(AWAKENING_CAPTURE_THE_FLAG, "CTF", "q4xbase", "Awakening ")
     + servers(AWAKENING_DEATHMATCH, "DM", "q4xbase", "Awakening ")
     + servers(AWAKENING_TOURNEY, "Tourney", "q4xbase", "Awakening ")),
)


def configuration(launch: Launch, renderer: tuple[str, str], group: str, order: int) -> dict[str, object]:
    renderer_name, render_api = renderer
    cvars = dict(COMMON_CVARS)
    cvars["fs_game"] = launch.game
    # r_renderApi has to precede the map command: the module loads at startup.
    cvars["r_renderApi"] = render_api
    cvars["ui_retained"] = "1" if launch.retained else "0"
    if launch.multiplayer:
        cvars["si_gameType"] = launch.game_type
        cvars.update(MULTIPLAYER_CVARS)
    else:
        cvars.update(SINGLE_PLAYER_CVARS)
    cvars.update(launch.cvars)
    args = [token for key, value in cvars.items() for token in ("+set", key, value)]
    mode = "MP" if launch.multiplayer else "SP"
    return {
        "name": f"({mode}) {launch.name} — {renderer_name}",
        "type": "cppvsdbg",
        "request": "launch",
        "presentation": {"group": group, "order": order},
        "program": "${workspaceFolder}\\.install\\openQ4-client_x64.exe",
        "args": args + list(launch.command),
        "cwd": "${workspaceFolder}\\.install",
        "console": "integratedTerminal",
    }


def build() -> dict[str, object]:
    configurations = []
    for group, launches in GROUPS:
        order = 0
        for launch in launches:
            for renderer in launch.renderers:
                order += 1
                configurations.append(configuration(launch, renderer, group, order))
    names = [config["name"] for config in configurations]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError("duplicate launch configuration names: " + ", ".join(duplicates))
    return {"version": "0.2.0", "configurations": configurations}


def argument_rows(args: list[str]) -> list[list[str]]:
    # One +set per row; any other command keeps its arguments on its row.
    rows: list[list[str]] = []
    index = 0
    while index < len(args):
        if args[index] in ("+set", "+seta"):
            rows.append(args[index:index + 3])
            index += 3
            continue
        row = [args[index]]
        index += 1
        while index < len(args) and not args[index].startswith("+"):
            row.append(args[index])
            index += 1
        rows.append(row)
    return rows


def render(launch: dict[str, object]) -> str:
    def value(item: object) -> str:
        return json.dumps(item, ensure_ascii=False)

    blocks = []
    for config in launch["configurations"]:
        members = []
        for key, item in config.items():
            if key == "args":
                rows = ",\n".join(" " * 16 + ", ".join(value(token) for token in row) for row in argument_rows(item))
                text = "[\n" + rows + "\n" + " " * 12 + "]"
            else:
                text = value(item)
            members.append(" " * 12 + value(key) + ": " + text)
        blocks.append(" " * 8 + "{\n" + ",\n".join(members) + "\n" + " " * 8 + "}")
    text = "{\n    \"version\": " + value(launch["version"]) + ",\n    \"configurations\": [\n"
    text += ",\n".join(blocks) + "\n    ]\n}\n"
    if json.loads(text) != launch:
        raise AssertionError("rendered launch.json does not round-trip")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if the file differs from the generated configurations")
    parser.add_argument("--output", type=Path, default=LAUNCH_JSON, help="launch.json to write or check")
    options = parser.parse_args(argv)
    launch = build()
    count = len(launch["configurations"])
    if options.check:
        current = json.loads(options.output.read_text(encoding="utf-8-sig"))
        if current != launch:
            print(f"{options.output} is stale; run python tools/debug/generate_vscode_launch.py", file=sys.stderr)
            return 1
        print(f"{options.output}: {count} configurations, up to date")
        return 0
    options.output.write_text(render(launch), encoding="utf-8")
    print(f"Wrote {count} configurations in {len(GROUPS)} groups to {options.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
