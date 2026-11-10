#!/usr/bin/env python3
"""A game module unload must not leave cvar completions pointing into it.

The idCmdSystem::ArgCompletion_* helpers are inline, so every binary carries
its own copy, and registering a static cvar points its value completion at the
declaring binary's copy. A game module's GetGameAPI registers all of its static
cvars, so it takes over the completion of every cvar it declares, the ones it
shares with the engine and the renderer included, and its ShutdownAfterDecls
clears only the CVAR_GAME ones. After reloadGameModule swapped game_sp for
game_mp, bot_showstate, bot_pathdebug and four g_render* cvars, which game-sp
declares without CVAR_GAME and game-mp does not declare at all, kept
completions inside the unloaded game-sp. The console calls a cvar's completion
while its name and a space are typed.

The engine captures the completions as soon as it has loaded a game module
and puts them back before it unloads it, so a declaration that leaves out
CVAR_GAME is covered however it gets there. Sys_DLL_Unload therefore has one
call site in Common.cpp, behind the restore, and the one load site captures
before GetGameAPI. The restore semantics themselves are pinned by
renderer_module_completion_safety.py.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMMON = "src/framework/Common.cpp"
UNLOAD_CALL = "Com_UnloadGameModuleBinary( gameDLL, gameModuleCompletions );"


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def reject(haystack: str, needle: str, context: str) -> None:
    if needle in haystack:
        raise AssertionError(f"Unexpected {needle!r} in {context}")


def require_ordered(haystack: str, tokens: tuple[str, ...], context: str) -> None:
    position = -1
    for token in tokens:
        next_position = haystack.find(token, position + 1)
        if next_position == -1:
            raise AssertionError(f"Missing ordered token {token!r} in {context}")
        position = next_position


def braced_block(source: str, marker: str) -> str:
    """The marker through the end of the first brace-balanced block after it."""
    start = source.find(marker)
    if start == -1:
        raise AssertionError(f"Missing {marker!r}")

    depth = 0
    for index in range(source.index("{", start), len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]

    raise AssertionError(f"Could not find the end of the block after {marker!r}")


def call_count(source: str, function: str) -> int:
    return len(re.findall(rf"\b{re.escape(function)}\s*\(", source))


def validate_every_unload_restores() -> None:
    common = read(COMMON)
    require(common, '#include "CVarCompletionSnapshot.h"', COMMON)
    local = braced_block(common, "class idCommonLocal : public idCommon {")
    if re.search(r"\bidCVarCompletionSnapshot\s+gameModuleCompletions;", local) is None:
        raise AssertionError("idCommonLocal must keep the loaded game module's completion snapshot")

    if call_count(common, "Sys_DLL_Unload") != 1:
        raise AssertionError(
            f"{COMMON} must unload game modules only through Com_UnloadGameModuleBinary, "
            f"found {call_count(common, 'Sys_DLL_Unload')} Sys_DLL_Unload calls"
        )
    unload = braced_block(
        common,
        "static void Com_UnloadGameModuleBinary( intptr_t handle, idCVarCompletionSnapshot &completions ) {",
    )
    require_ordered(
        unload,
        ("completions.Restore();", "completions.Clear();", "Sys_DLL_Unload( handle );"),
        "Com_UnloadGameModuleBinary",
    )

    # a new load site has to capture before its GetGameAPI; count them so it
    # cannot appear without this test being revisited
    for function, expected in (("DLL_Load", 1), ("Sys_DLL_Load", 0), ("GetGameAPI", 1)):
        found = call_count(common, function)
        if found != expected:
            raise AssertionError(f"expected {expected} {function} calls in {COMMON}, found {found}")

    load = braced_block(common, "void idCommonLocal::LoadGameDLL( void ) {")
    context = "idCommonLocal::LoadGameDLL"
    require_ordered(
        load,
        (
            "gameDLL = sys->DLL_Load( dllPath );",
            "gameModuleCompletions.Capture();",
            'Sys_DLL_GetProcAddress( gameDLL, "GetGameAPI" )',
            "GetGameAPI( &gameImport )",
            "game->Init();",
        ),
        context,
    )
    # nothing was registered when the binary failed to load
    reject(braced_block(load, "if ( !gameDLL ) {"), "gameModuleCompletions", context)
    for marker in (
        "if ( !GetGameAPI ) {",
        "if ( gameExportPtr == NULL ) {",
        "if ( gameExport.version != GAME_API_VERSION ) {",
    ):
        require_ordered(braced_block(load, marker), (UNLOAD_CALL, "gameDLL = NULL;"), f"{context} {marker}")

    unload_dll = braced_block(common, "void idCommonLocal::UnloadGameDLL( void ) {")
    require_ordered(unload_dll, ("if ( gameDLL ) {", UNLOAD_CALL, "gameDLL = NULL;"), "idCommonLocal::UnloadGameDLL")

    calls = re.findall(r"Com_UnloadGameModuleBinary\([^;{]*\);", common)
    for call in calls:
        if call != UNLOAD_CALL:
            raise AssertionError(f"{COMMON} unloads a game module with a snapshot it did not capture: {call}")
    if len(calls) != 4:
        raise AssertionError(f"expected 4 game module unloads (three failed loads and UnloadGameDLL), found {len(calls)}")

    # the snapshot belongs to the loaded module: one capture, spent only by
    # the unload helper
    if common.count("gameModuleCompletions.Capture();") != 1:
        raise AssertionError("the game module snapshot must be captured only in LoadGameDLL")
    for token in ("gameModuleCompletions.Restore()", "gameModuleCompletions.Clear()"):
        reject(common, token, COMMON)


def validate_restore_follows_game_finalization() -> None:
    """ShutdownAfterDecls clears the completion of every CVAR_GAME cvar, and
    flags accumulate across declarations, so that includes engine cvars the
    game declared again with CVAR_GAME. Restoring after it hands those their
    engine callbacks back; restoring first would leave them cleared."""
    shutdown = braced_block(read(COMMON), "void idCommonLocal::ShutdownGame( bool reloading ) {")
    require_ordered(shutdown, ("game->ShutdownAfterDecls();", "UnloadGameDLL();"), "idCommonLocal::ShutdownGame")


def validate_common_is_the_only_game_module_loader() -> None:
    """Any other code resolving GetGameAPI would need its own capture."""
    sources = [*(ROOT / "src").rglob("*.cpp"), *(ROOT / "src").rglob("*.mm")]
    for path in sorted(sources):
        relative = path.relative_to(ROOT).as_posix()
        if relative == COMMON:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if '"GetGameAPI"' in text:
            raise AssertionError(f"{relative} resolves the game module entry point outside {COMMON}")


def main() -> None:
    validate_every_unload_restores()
    validate_restore_follows_game_finalization()
    validate_common_is_the_only_game_module_loader()
    print("game_module_completion_safety: ok")


if __name__ == "__main__":
    main()
