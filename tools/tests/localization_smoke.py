#!/usr/bin/env python3
"""Check a translated language's gameplay, menu rendering and live language
switching against the staged runtime (requires Pillow and retail assets).

The expected text comes from the staged string tables themselves, so one
script covers every language with complete tables: the SP case enters
game/airdefense1, runs the real language chooser's command through a temporary
GUI timeline and checks the menu switches language and back; the MP case
enters mp/q4dm1 and checks the translated Match Control view. Captures are
taken only with the engine's own screenshot command - no input is synthesised.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

from mp_round_remote_smoke import verify_runtime_is_current

ROOT = Path(__file__).resolve().parents[2]
ENTRY = re.compile(r'^\s*"(#str_\w+)"\s+"((?:\\.|[^"\\])*)"', re.M)
SETTINGS_LABEL = "#str_200009"     # main_t_b4, the main menu's SETTINGS button
LANGUAGE_NAMES = "#str_229908"     # the language chooser's positional list
WARMUP_PHASE = "#str_42401"        # Match Control's warmup status


def read_staged(runtime: Path, relative: str) -> str | None:
    loose = runtime / "baseoq4" / relative
    if loose.is_file():
        return loose.read_text(encoding="utf-8")
    for archive in sorted((runtime / "baseoq4").glob("*.pk4"), reverse=True):
        with zipfile.ZipFile(archive) as package:
            if relative in package.namelist():
                return package.read(relative).decode("utf-8")
    return None


def read_gui(runtime: Path, relative: str) -> str:
    text = read_staged(runtime, relative)
    if text is None:
        raise AssertionError(f"Missing staged GUI: {relative}")
    return text


def staged_strings(runtime: Path, language: str) -> dict:
    """The language's dictionary as the engine builds it: its tables in load
    order, later definitions winning."""
    table = {}
    for category in ("code", "guis", "lips", "maps", "mappack", "openq4"):
        text = read_staged(runtime, f"strings/{language}_{category}.lang")
        if text is not None:
            table.update(ENTRY.findall(text))
    if not table:
        raise AssertionError(f"No staged {language}_*.lang tables in {runtime}")
    return table


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", default="german", help="sys_lang value with complete tables")
    parser.add_argument("--mode", choices=("SP", "MP"), default="SP")
    parser.add_argument("--renderer", choices=("gl", "vulkan"), default="gl")
    parser.add_argument("--basepath", type=Path, required=True, help="installed retail Quake 4 assets")
    parser.add_argument("--runtime-dir", type=Path, default=ROOT / ".install")
    parser.add_argument("--executable-name")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--timeout", type=int, default=180)
    options = parser.parse_args(argv)
    from PIL import Image, ImageStat

    language = options.language.lower()
    staged = options.runtime_dir.resolve()
    output = (options.output_dir or ROOT / ".tmp/localization-smoke" / language).resolve()
    executable = options.executable_name or ("openQ4-client_x64.exe" if os.name == "nt" else "openQ4-client_x64")
    if not (staged / executable).is_file() or not options.basepath.is_dir():
        parser.error("a staged client and installed Quake 4 assets are required")
    if output == staged or staged in output.parents or output in staged.parents:
        parser.error("output and staged runtime directories must not overlap")
    verify_runtime_is_current(staged, executable)
    english = staged_strings(staged, "english")
    translated = staged_strings(staged, language)
    for key in (SETTINGS_LABEL, LANGUAGE_NAMES, WARMUP_PHASE):
        if translated.get(key, english.get(key)) == english.get(key):
            parser.error(f"{language} does not translate {key}; it is not a complete language")
    mode = options.mode
    backend = "GL" if options.renderer == "gl" else "Vulkan"
    profile = output / f"{mode.lower()}-{options.renderer}"
    game = profile / "baseoq4"
    game.mkdir(parents=True, exist_ok=True)
    runtime = staged
    if mode == "SP":
        # The staged content root precedes fs_savepath. Independently copy its
        # runtime files so the semantic test hooks never modify the real stage.
        # One fixed location serves every language and run, so the copied
        # executable keeps a single firewall identity (AGENTS.md, stable test
        # executable paths); it is refreshed from the stage each time.
        runtime = ROOT / ".tmp" / "runtime" / "localization"
        (runtime / "baseoq4/guis").mkdir(parents=True, exist_ok=True)
        patterns = (executable, "*.dll", "*.so*", "*.dylib", "baseoq4/*.dll",
                    "baseoq4/*.so*", "baseoq4/*.dylib", "baseoq4/*.pk4", "baseoq4/mod.json")
        for pattern in patterns:
            for source in staged.glob(pattern):
                shutil.copy2(source, runtime / source.relative_to(staged))
        built = (staged / executable).stat()
        (runtime / "build-identity.json").write_text(json.dumps(
            {"stage": str(staged), "executable_bytes": built.st_size, "executable_mtime": built.st_mtime}, indent=2),
            encoding="utf-8")
        menu = read_gui(staged, "guis/mainmenu.gui")
        settings = read_gui(staged, "guis/menu/settings/game.gui")
        choice = settings[settings.index("choiceDef set_game_language_value"):]
        action = re.search(r'onActionRelease\s*\{\s*set "cmd" "([^"]+)"', choice)[1]
        # Exercise the actual chooser's command through normal GUI dispatch,
        # without synthesizing keyboard or mouse input.
        hook = '''
    onNamedEvent localizationSmokeReload { resetTime "localizationSmokeTimer" "0"; }
    windowDef localizationSmokeTimer {
        rect 0,0,1,1
        visible 1
        notime 1
        onTime 0 { set "cmd" "ACTION"; }
    }
    onNamedEvent localizationSmokeSettings {
        set "desktop::active" "1";
        set "desktop::dest" "21";
        resetTime "anim_mainOut" "0";
    }
    onNamedEvent localizationSmokeLanguage { set "gui::gui_set_game_scroll" "52"; }
'''.replace("ACTION", action)
        start = menu.index("{") + 1
        fixture = menu[:start] + hook + menu[start:]
        (runtime / "baseoq4/guis/mainmenu.gui").write_text(fixture, encoding="utf-8")
        (profile / "mainmenu-fixture.gui").write_text(fixture, encoding="utf-8")

    launches = json.loads((ROOT / ".vscode/launch.json").read_text(encoding="utf-8"))
    launch = next(c for c in launches["configurations"] if c["name"] == f"({mode}) Main menu — {backend}")
    args = [a.replace("${workspaceFolder}", str(ROOT)) for a in launch["args"]]
    settings = {
        "sys_lang": language, "in_mouse": "0", "in_joystick": "0",
        "r_fullscreen": "0", "r_borderless": "0", "r_borderlessDefaultMigrated": "1",
        "r_hiddenWindow": "1", "r_windowWidth": "1280", "r_windowHeight": "720",
        "r_mode": "-1", "r_customWidth": "1280", "r_customHeight": "720",
        "r_swapInterval": "0", "com_maxfps": "60",
        "win_allowMultipleInstances" if os.name == "nt" else "sys_allowMultipleInstances": "1",
        "fs_basepath": str(options.basepath.resolve()),
        "fs_savepath": str(profile), "fs_devpath": str(profile),
        "g_autoExecAfterMapLoad": "localization_smoke.cfg", "g_autoExecAfterMapLoadDelayMs": "1000",
        "g_autoSkipCinematics": "1", "com_skipLoadingContinue": "1",
        "com_loadingContinueAutoAdvance": "1", "com_allowConsole": "1", "sv_cheats": "1",
        "ui_autoJoin": "1", "ui_retained": "0", "net_serverDedicated": "0", "si_pure": "0",
        "si_map": "mp/q4dm1", "net_port": "28231", "ui_name": "LocalizationTest",
    }
    for key, value in settings.items():
        args += ["+set", key, value]
    commands = ["waitMsec 3000", "echo LOCALIZATION_GAMEPLAY_ACTIVE", "sys_lang",
                "screenshot screenshots/gameplay.tga"]
    captures = ["gameplay"]
    if mode == "MP":
        args += ["+spawnServer"]
        captures += ["match_control"]
        commands += ["openq4_reportMPState", "openq4_assertMPClientActive",
                     "openq4_assertMenuActivation 4000 game", "waitMsec 1500",
                     "openq4_guiSet desktop::active 1", "openq4_guiSet desktop::dest 21",
                     "GuiEvent hideMain", "GuiEvent chooseCurr", "GuiEvent resetMain0",
                     "waitMsec 1500", "openq4_guiSet desktop::match_tab 0",
                     "waitMsec 350", "openq4_guiGet match_status_values::text",
                     "screenshot screenshots/match_control.tga"]
    else:
        args += ["+map", "game/airdefense1"]
        captures += ["menu", "reloaded", "settings", "language"]
        # File reparsing can consume the wall-clock wait. Yield frames afterward
        # so the newly activated menu can run its fade-in before the capture.
        settle = ["waitMsec 1500", "wait 2", "waitMsec 750"]
        commands += ["openq4_assertMenuActivation 4000", "waitMsec 1000",
                     "openq4_guiGet main_t_b4::text", "screenshot screenshots/menu.tga",
                     "set sys_lang english", "GuiEvent localizationSmokeReload", *settle,
                     "echo ENGLISH_RELOAD", "sys_lang", "openq4_guiGet main_t_b4::text",
                     f"set sys_lang {language}", "GuiEvent localizationSmokeReload", *settle,
                     "echo LANGUAGE_RELOAD", "sys_lang", "openq4_guiGet main_t_b4::text",
                     "openq4_guiGet set_game_language_value::choices",
                     "openq4_guiGet set_game_language_value::values",
                     "screenshot screenshots/reloaded.tga",
                     "GuiEvent localizationSmokeSettings", "waitMsec 1500",
                     "screenshot screenshots/settings.tga",
                     "GuiEvent localizationSmokeLanguage", "waitMsec 500",
                     "screenshot screenshots/language.tga"]
    commands += ["echo LOCALIZATION_SMOKE_COMPLETE", "quit"]
    (game / "localization_smoke.cfg").write_text("\n".join(commands) + "\n", encoding="utf-8")
    for name in captures:
        (game / f"screenshots/{name}.tga").unlink(missing_ok=True)
        (game / f"screenshots/{name}.png").unlink(missing_ok=True)
    command = [str(runtime / executable), *args]
    (profile / "command.json").write_text(json.dumps(command, indent=2), encoding="utf-8")
    startup = None
    if os.name == "nt":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
    with (profile / "process.log").open("w", encoding="utf-8") as log:
        result = subprocess.run(command, cwd=runtime, stdout=log, stderr=subprocess.STDOUT,
                                startupinfo=startup, timeout=options.timeout)
    text = (game / "logs/openq4.log").read_text(encoding="utf-8", errors="replace")
    assert result.returncode == 0, result.returncode
    assert "LOCALIZATION_SMOKE_COMPLETE" in text, "script did not complete"
    assert "LOCALIZATION_GAMEPLAY_ACTIVE" in text, "gameplay not reached"
    assert not re.search(r"FATAL|ERROR:|Unknown string id|Unknown command|No language files found|openq4_gui(?:Get|Set): unknown", text)
    if mode == "SP":
        english_part = text.partition("ENGLISH_RELOAD")[2].partition("LANGUAGE_RELOAD")[0]
        language_part = text.partition("LANGUAGE_RELOAD")[2]
        assert f"GUI_VALUE main_t_b4::text={english[SETTINGS_LABEL]}" in english_part
        assert f"GUI_VALUE main_t_b4::text={translated[SETTINGS_LABEL]}" in language_part
        assert translated[LANGUAGE_NAMES] in language_part
    else:
        assert "OPENQ4_STOCK_BASELINE_MP_CLIENT_ACTIVE" in text
        assert f"GUI_VALUE match_status_values::text={translated[WARMUP_PHASE]}" in text
    for name in captures:
        shot = game / f"screenshots/{name}.tga"
        with Image.open(shot) as captured:
            assert max(ImageStat.Stat(captured.convert("RGB")).stddev) > 10, f"blank engine capture: {shot}"
            captured.save(shot.with_suffix(".png"))
    print(f"{language} {mode} {backend}: PASS; evidence={profile}")


if __name__ == "__main__":
    main()
