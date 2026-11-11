#!/usr/bin/env python3
"""Keep Prey's Video options pages wired to settings the engine really has.

The stock Prey menu binds rows straight to cvars and GUI state. Three kinds of
drift have shipped before and are silent at run time:

  * a row bound to a cvar nothing registers or reads (High Particle Detail);
  * a choice whose labels and values no longer agree with the engine (the stock
    resolution list named 640x480 for an r_mode that now means 1920x1080);
  * a preset the engine has and the menu cannot reach (three of nine).

This check reads the menu fragment, the string tables and the engine sources.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRAGMENT = ROOT / "content/basepr/pak0/guis/mainmenu/mainmenu_options.guifragment"
STRINGS_DIR = ROOT / "content/basepr/pak0/strings"
SOURCE_DIRS = (ROOT / "src/framework", ROOT / "src/renderer", ROOT / "src/sys", ROOT / "src/game")

SIDE_TABS = (
    "Options_Video_Normal",
    "Options_Video_Display",
    "Options_Video_Advanced",
    "Options_Video_Advanced2",
    "Options_Video_PostFX",
    "Options_Video_PostFXAdvanced",
)

# GUI state the pages read, and the session code that publishes it.
GUI_STATE = (
    "display_mode_choices",
    "display_mode_values",
    "display_mode_choice",
    "display_names",
    "display_values",
    "display_refresh_choices",
    "display_refresh_values",
    "display_maxfps_choices",
    "display_maxfps_values",
    "r_skipNewAmbient",
    "r_shaderLevelUnavailable",
)

# Menu commands the pages send, handled in idSessionLocal::HandleMainMenuCommands.
MENU_COMMANDS = (
    "applyPerformancePreset",
    "autoDetectPerformancePreset",
    "applyDisplayModeChoice",
    "applyCustomDisplaySize",
    "refreshDisplayChoices",
)

# Registered so retail configurations load, but read by nothing: a row bound
# to one of these would be a control that does nothing.
UNREAD_CVARS = ("r_lowParticleDetail",)


def fail(message: str) -> None:
    raise AssertionError(message)


def video_section(text: str) -> str:
    start = text.index("tabContainerDef Options_Video_Container")
    end = text.index("tabDef Options_Audio {", start)
    return text[start:end]


def engine_sources() -> str:
    parts = []
    for directory in SOURCE_DIRS:
        for path in directory.rglob("*"):
            if path.suffix in (".cpp", ".h"):
                parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def choice_lists(section: str):
    """Yield (window, choices, values) for every choiceDef with literal lists."""
    for match in re.finditer(r"choiceDef\s+(\w+)\s*\{(.*?)\n\t+\}", section, re.S):
        body = match.group(2)
        choices = re.search(r'^\s*choices\s+"([^"]*)"', body, re.M)
        values = re.search(r'^\s*values\s+"([^"]*)"', body, re.M)
        yield match.group(1), choices.group(1) if choices else None, values.group(1) if values else None


def main() -> int:
    text = FRAGMENT.read_text(encoding="utf-8")
    if "\r" in text:
        fail("the options fragment must keep LF line endings (content/basepr is packed byte for byte)")
    if text.count("{") != text.count("}"):
        fail("unbalanced braces in the options fragment")

    section = video_section(text)
    tabs = tuple(re.findall(r"^\t{5}tabDef (\w+) \{", section, re.M))
    if tabs != SIDE_TABS:
        fail(f"Video side tabs are {tabs}, expected {SIDE_TABS}")

    sources = engine_sources()

    # Every bound cvar exists, and none is a registered-but-unread placeholder.
    for cvar in sorted(set(re.findall(r'^\s*cvar\s+"(\w+)"', section, re.M))):
        if not re.search(r'idCVar\s+\w+(?:::\w+)?\s*\(\s*"' + re.escape(cvar) + r'"', sources, re.I):
            fail(f"Video page binds cvar '{cvar}', which no source registers")
        if cvar in UNREAD_CVARS:
            fail(f"Video page binds cvar '{cvar}', which the engine never reads")
    if re.search(r'^\s*cvar\s+"r_mode"', section, re.M):
        fail("Video Resolution must use the engine's display-mode list, not a fixed r_mode list")

    # The preset row offers exactly the engine's presets, in the engine's order.
    preset_source = (ROOT / "src/framework/PerformancePreset.cpp").read_text(encoding="utf-8")
    engine_presets = re.findall(r'^\t\{ "(\w+)", \d+, "', preset_source, re.M)
    preset_values = None
    string_ids = {}
    for window, choices, values in choice_lists(section):
        if window == "OVN_PresetChoice":
            preset_values = values.split(";") if values else None
        if choices and values and not choices.startswith("gui::"):
            string_ids[window] = (choices, values)
    if not engine_presets:
        fail("could not read the preset names from PerformancePreset.cpp")
    if preset_values != engine_presets:
        fail(f"Quality Preset offers {preset_values}, engine has {engine_presets}")

    # Published GUI state and handled commands.
    session_menu = (ROOT / "src/framework/Session_menu.cpp").read_text(encoding="utf-8", errors="replace")
    for key in GUI_STATE:
        if f'gui::{key}"' not in section and f'gui\t\t\t"{key}"' not in section:
            fail(f"Video pages no longer read GUI state '{key}'; drop it from this check")
        if f'"{key}"' not in session_menu:
            fail(f"Session_menu.cpp does not publish GUI state '{key}'")
    for command in MENU_COMMANDS:
        if command not in section:
            fail(f"Video pages no longer send '{command}'; drop it from this check")
        if f'"{command}"' not in session_menu:
            fail(f"Session_menu.cpp does not handle menu command '{command}'")
    for key in re.findall(r'"gui::(\w+)"', section):
        if key not in GUI_STATE:
            fail(f"Video pages read GUI state '{key}', which this check does not know is published")

    # openPREY's own strings exist in every shipped table, with as many
    # choices as the row has values.
    tables = {}
    for path in sorted(STRINGS_DIR.glob("*_openprey.lang")):
        table_text = path.read_text(encoding="utf-8")
        tables[path.name] = dict(re.findall(r'^\t"(#str_\d+)"\t"([^"]*)"', table_text, re.M))
    if not tables:
        fail("no *_openprey.lang tables found")
    used = sorted(set(re.findall(r"#str_122\d+", section)) | {"#str_122035"})
    for name, table in tables.items():
        for string_id in used:
            if string_id not in table:
                fail(f"{name} lacks {string_id}, which the Video pages use")
        for window, (choices, values) in string_ids.items():
            if choices in table and len(table[choices].split(";")) != len(values.split(";")):
                fail(f"{name}: {choices} has {len(table[choices].split(';'))} choices, "
                     f"{window} has {len(values.split(';'))} values")

    # Presets drive Prey's own quality cvars, and a change of shader detail
    # reparses materials instead of asking for a restart.
    common = (ROOT / "src/framework/Common.cpp").read_text(encoding="utf-8", errors="replace")
    for needle in ("Common_ApplyPreyPerformancePresetExtras", '"r_shaderLevel"'):
        if needle not in common:
            fail(f"Common.cpp lost {needle}")
    material = (ROOT / "src/renderer/Material.cpp").read_text(encoding="utf-8", errors="replace")
    for needle in ("R_CheckShaderLevelCvars", "R_EffectiveShaderLevel", "OPENQ4_RENDERER_VK_MODULE"):
        if needle not in material:
            fail(f"Material.cpp lost {needle}")
    if "AnimMustRestart_Up" in re.search(r"buttonDef OVA_ShaderDetail \{.*?\n\t{7}\}", section, re.S).group(0):
        fail("Shader Detail applies live; it must not raise the restart notice")

    print("Prey video menu contract checks passed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as error:
        print(f"prey_video_menu_contract: {error}", file=sys.stderr)
        sys.exit(1)
