#!/usr/bin/env python3
"""Contract checks for the in-game Difficulty option and the level restart it drives.

In a single-player game the main menu gains DIFFICULTY, which opens the New
Game page in a restart mode. Two properties are easy to break:

- The page must never change the live g_skill. Loading or keeping a game at a
  half-applied difficulty is what the restart exists to avoid, and backing out
  of the page must change nothing.
- The restart command must come from a timeline. A `set "cmd"` inside a named
  event is cleared by that window's next event without ever reaching the
  session, so a button that routes through a named event would do nothing.
"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SESSION = "src/framework/Session.cpp"
SESSION_MENU = "src/framework/Session_menu.cpp"
SESSION_LOCAL = "src/framework/Session_local.h"
MAIN_MENU = "content/baseoq4/pak0/guis/mainmenu.gui"
RESTART_LEVEL_STRING = "#str_229983"
LANGUAGES = ("english", "german", "french", "italian", "polish", "russian", "spanish",
             "brazilian", "czech", "hungarian", "turkish", "ukrainian")
START_LABEL_MAX_CHARS = 16  # new_t_bstart is 198px wide at textscale .33


def read(relative_path: str) -> str:
    data = (ROOT / relative_path).read_bytes()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def block(source: str, opener: str) -> str:
    """The brace block starting at the first occurrence of opener.

    A "windowDef NAME" opener must match the whole name, so main_b_return does
    not find main_b_returnmp.
    """
    if opener.startswith("windowDef "):
        match = re.search(re.escape(opener) + r"[ \t]*\r?\n", source)
        start = match.start() if match else -1
    else:
        start = source.find(opener)
    if start == -1:
        raise AssertionError(f"Missing {opener!r}")
    depth = 0
    for index in range(start, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Unterminated block {opener!r}")


def validate_engine() -> None:
    session = read(SESSION)
    restart = block(session, "bool idSessionLocal::RestartLevelAtSkill( int skill ) {")
    for needle, why in (
        ("IsMultiplayer()", "multiplayer is refused"),
        ("IsDemoPlaybackActive()", "demo playback is refused"),
        ("GetAutoSaveName( mapName.c_str() )", "the loadout comes from the level's start autosave"),
        ("Session_ReadSaveGameLoadout(", "only the header is read, not the saved world"),
        ('cvarSystem->SetCVarInteger( "g_skill", skill );', "the new difficulty is applied"),
        ("lastCheckPoint = -1;", "a death does not reload an old-difficulty checkpoint"),
        ("MoveToNewMap( mapName.c_str() );", "the map respawns fresh at the new difficulty"),
    ):
        require(restart, needle, f"RestartLevelAtSkill ({why})")
    if restart.index("SetCVarInteger") > restart.index("MoveToNewMap"):
        raise AssertionError("RestartLevelAtSkill must set g_skill before the map respawns")

    loadout = block(session, "static bool Session_ReadSaveGameLoadout(")
    require(loadout, "Session_ReadSaveGameDict( file, loadout[i]", "Session_ReadSaveGameLoadout")
    require(loadout, "normalizedSaveMap.Icmp( normalizedExpectedMap ) == 0",
            "Session_ReadSaveGameLoadout (a save for another map is never used)")
    require(session, 'AddCommand( "restartLevel", Session_RestartLevel_f, CMD_FL_SYSTEM,', "session commands")
    require(read(SESSION_LOCAL), "bool				RestartLevelAtSkill( int skill );", "idSessionLocal")

    menu = read(SESSION_MENU)
    command = block(menu, 'if ( !idStr::Icmp( cmd, "restartLevel" ) ) {')
    require(command, '"desktop::skill"', "restartLevel menu command (the page's choice)")
    require(command, "RestartLevelAtSkill( skill );", "restartLevel menu command")
    require(menu, 'guiMainMenu->SetStateInt( "currentSkill",', "SetMainMenuGuiVars (the page opens on the current skill)")


def validate_menu() -> None:
    gui = read(MAIN_MENU)
    lines = gui.splitlines()

    # The page never changes the live difficulty: every g_skill console command
    # sits in a branch that only runs outside restart mode.
    skill_commands = [i for i, line in enumerate(lines) if re.search(r'consoleCMD "g_skill \d" ;', line)]
    if len(skill_commands) != 6:
        raise AssertionError(f"expected six g_skill console commands (anim_newIn + five buttons), found {len(skill_commands)}")
    for i in skill_commands:
        guard = next((lines[k].strip() for k in range(i - 1, max(i - 8, -1), -1) if "difficultyRestart" in lines[k]), "")
        if guard not in ('if ("desktop::difficultyRestart" == 0) {', 'if ("desktop::difficultyRestart" == 1) {'):
            raise AssertionError(f"mainmenu.gui line {i + 1}: g_skill console command is not guarded by restart mode")
        if guard.endswith("== 1) {") and not any(lines[k].strip() == "} else {" for k in range(i - 1, max(i - 8, -1), -1)):
            raise AssertionError(f"mainmenu.gui line {i + 1}: g_skill console command runs in restart mode")

    # The restart command comes from a timeline, and only from there.
    timeline = block(gui, "windowDef anim_restartLevel")
    require(timeline, "onTime 0 {", "anim_restartLevel")
    require(timeline, 'set "cmd" "play main_menu_selection ; restartLevel" ;', "anim_restartLevel")
    issued = [line for line in lines if re.search(r'set "cmd" "[^"]*\brestartLevel\b', line)]
    if len(issued) != 1:
        raise AssertionError(f"restartLevel must be issued only by anim_restartLevel, found {len(issued)} senders")
    restart_event = block(gui, "onNamedEvent restartAtDifficulty {")
    require(restart_event, 'namedevent "p_btns::leaveDifficultyForRestart" ;', "restartAtDifficulty (reset the page first)")
    require(restart_event, 'resettime "anim_restartLevel" "0" ;', "restartAtDifficulty")
    start = block(gui, "windowDef new_b_start")
    require(start, 'namedevent "p_btns::restartAtDifficulty" ;', "new_b_start in restart mode")
    require(start, 'set "cmd" "play main_menu_selection ; startMap game/airdefense1" ;', "new_b_start (Mission start unchanged)")

    # Rows: DIFFICULTY takes slot 5 in a single-player game, RETURN TO GAME moves to slot 6.
    require(block(gui, "windowDef main_b_difficulty"), "rect\t24,334,333,26", "main_b_difficulty (slot 5)")
    require(block(gui, "windowDef main_b_difficulty"), 'namedevent "p_btns::openDifficulty" ;', "main_b_difficulty")
    require(block(gui, "windowDef main_b_return"), "rect\t24,364,333,26", "main_b_return (slot 6)")
    require(block(gui, "windowDef main_t_b10"), "rect\t44,364,314,23", "main_t_b10 (slot 6 label)")
    in_game = block(gui, "onNamedEvent ingameCheck {")
    require(in_game, 'set "main_t_b9::text" "#str_42009" ;', "ingameCheck (DIFFICULTY label)")
    require(in_game, 'set "main_t_b10::text" "#str_200005" ;', "ingameCheck (RETURN TO GAME label)")

    # The page opens on the current skill with its own title and button label.
    new_in = block(gui, "windowDef anim_newIn")
    for needle in ('set "desktop::skill" "$gui::currentSkill" ;', 'set "t_new_title::text" "#str_42009" ;',
                   f'set "new_t_bstart::text" "{RESTART_LEVEL_STRING}" ;'):
        require(new_in, needle, "anim_newIn restart mode")

    # Back and Escape return to the in-game main page, not the Single Player selector.
    require(block(gui, "windowDef new_b_back"), 'set "desktop::dest" "0" ;', "new_b_back in restart mode")
    escape = block(gui, "onESC {")
    require(escape, 'set "desktop::dest" "0" ;', "onESC in restart mode")


def validate_strings() -> None:
    for language in LANGUAGES:
        path = f"content/baseoq4/pak0/strings/{language}_openq4.lang"
        match = re.search(rf'"{RESTART_LEVEL_STRING}"\s+"([^"]*)"', read(path))
        if match is None:
            raise AssertionError(f"Missing {RESTART_LEVEL_STRING} in {path}")
        if not match.group(1) or len(match.group(1)) > START_LABEL_MAX_CHARS:
            raise AssertionError(f"{path}: {match.group(1)!r} does not fit the {START_LABEL_MAX_CHARS}-character Start label")


def main() -> None:
    validate_engine()
    validate_menu()
    validate_strings()
    print("in-game difficulty restart: ok")


if __name__ == "__main__":
    main()
