#!/usr/bin/env python3
"""A renderer module unload must not leave cvar completions pointing into it.

The idCmdSystem::ArgCompletion_* helpers are inline, so every binary carries
its own copy, and registering a static cvar points its value completion at the
declaring binary's copy. A renderer module's GetRenderAPI registers all of its
static cvars, the ones it shares with the engine, the game and the active
renderer included, so it takes over every one of those callbacks. After
rendererVkProbe unloaded renderer-vk under OpenGL, 311 completions (all of
renderer-gl's, plus developer) pointed into the unmapped image, and the console
calls a cvar's completion while its name and a space are typed.

The loader captures the completions after it loads a module and puts them back
before it unloads it. Sys_DLL_Unload therefore has one call site in the
loader, behind the restore, and each function that loads a module captures
before GetRenderAPI.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOADER = "src/renderer/RendererModule.cpp"


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


def validate_snapshot_is_engine_only() -> None:
    """CVarSystem.h is mirrored into openQ4-game and hash-pinned, so the
    snapshot lives in its own header that only engine code includes."""
    header = read("src/framework/CVarCompletionSnapshot.h")
    context = "CVarCompletionSnapshot.h"
    require(header, "class idCVarCompletionSnapshot {", context)
    for pattern in (
        r"\bvoid\s+Capture\( void \);",
        r"\bint\s+Restore\( void \) const;",
        r"\bvoid\s+Clear\( void \);",
        r"idCVarCompletionSnapshot\( void \) : captured\( false \) \{\}",
    ):
        if re.search(pattern, header) is None:
            raise AssertionError(f"Missing {pattern!r} in {context}")
    reject(read("src/framework/CVarSystem.h"), "idCVarCompletionSnapshot", "the mirrored CVarSystem.h")


def validate_restore_semantics() -> None:
    """Restore gives each cvar its captured callback, or none, so a cvar the
    module introduced is cleared too. An uncaptured snapshot must not clear
    every callback in the engine."""
    cvars = read("src/framework/CVarSystem.cpp")

    internal = braced_block(cvars, "class idInternalCVar : public idCVar {")
    require(internal, "friend class idCVarCompletionSnapshot;", "idInternalCVar")
    system = braced_block(cvars, "class idCVarSystemLocal : public idCVarSystem {")
    require(system, "friend class idCVarCompletionSnapshot;", "idCVarSystemLocal")

    capture = braced_block(cvars, "void idCVarCompletionSnapshot::Capture( void ) {")
    require_ordered(
        capture,
        (
            "Clear();",
            "captured = true;",
            "localCVarSystem.cvars.Num()",
            "entry.completion = cvar->valueCompletion;",
        ),
        "idCVarCompletionSnapshot::Capture",
    )

    restore = braced_block(cvars, "int idCVarCompletionSnapshot::Restore( void ) const {")
    require_ordered(
        restore,
        (
            "if ( !captured ) {",
            "return 0;",
            "localCVarSystem.cvars.Num()",
            "argCompletion_t completion = NULL;",
            "completion = saved[j].completion;",
            "cvar->valueCompletion = completion;",
        ),
        "idCVarCompletionSnapshot::Restore",
    )
    # restoring reads and writes pointers; calling one would reach the module
    reject(restore, "valueCompletion(", "idCVarCompletionSnapshot::Restore")

    clear = braced_block(cvars, "void idCVarCompletionSnapshot::Clear( void ) {")
    require(clear, "captured = false;", "idCVarCompletionSnapshot::Clear")


def validate_every_unload_restores() -> None:
    loader = read(LOADER)
    require(loader, '#include "../framework/CVarCompletionSnapshot.h"', LOADER)

    if call_count(loader, "Sys_DLL_Unload") != 1:
        raise AssertionError(
            f"{LOADER} must unload renderer modules only through RM_UnloadModuleBinary, "
            f"found {call_count(loader, 'Sys_DLL_Unload')} Sys_DLL_Unload calls"
        )
    unload = braced_block(
        loader,
        "static void RM_UnloadModuleBinary( intptr_t handle, idCVarCompletionSnapshot &completions ) {",
    )
    require_ordered(
        unload,
        ("completions.Restore();", "completions.Clear();", "Sys_DLL_Unload( handle );"),
        "RM_UnloadModuleBinary",
    )

    # a new load site has to capture before its GetRenderAPI; count them so it
    # cannot appear without this test being revisited
    for function, expected in (("Sys_DLL_Load", 3), ("GetRenderAPI", 2)):
        found = call_count(loader, function)
        if found != expected:
            raise AssertionError(f"expected {expected} {function} calls in {LOADER}, found {found}")

    try_load = braced_block(
        loader,
        "static bool RM_TryLoadModuleApi( rendererModuleApi_t api, rendererModuleStatus_t &status ) {",
    )
    context = "RM_TryLoadModuleApi"
    require_ordered(
        try_load,
        (
            "Sys_DLL_Load( modulePath )",
            "rm_state.moduleCompletions.Capture();",
            "GetRenderAPI( &moduleImport )",
            "RM_PublishActiveModuleInterfaces( rm_state.moduleExport );",
        ),
        context,
    )
    for marker in ("if ( !RM_ExportCanRender( moduleExport, &reason ) ) {", "if ( !deviceReady ) {"):
        require(
            braced_block(try_load, marker),
            "RM_UnloadModuleBinary( handle, rm_state.moduleCompletions );",
            f"{context} {marker}",
        )
    unloads = re.findall(r"RM_UnloadModuleBinary\([^;]*\);", try_load)
    for call in unloads:
        if call != "RM_UnloadModuleBinary( handle, rm_state.moduleCompletions );":
            raise AssertionError(f"{context} unloads with a snapshot it did not capture: {call}")
    # an activated module keeps its snapshot until RM_UnloadModule
    reject(try_load, "rm_state.moduleCompletions.Clear()", context)

    unload_active = braced_block(loader, "static bool RM_UnloadModule( void ) {")
    require(
        unload_active,
        "RM_UnloadModuleBinary( rm_state.moduleHandle, rm_state.moduleCompletions );",
        "RM_UnloadModule",
    )

    probe = braced_block(loader, "bool R_RendererModule_RunVulkanProbe( bool verbose ) {")
    context = "R_RendererModule_RunVulkanProbe"
    require_ordered(
        probe,
        (
            "Sys_DLL_Load( modulePath )",
            "completions.Capture();",
            "GetRenderAPI( &moduleImport )",
            "moduleExport->Shutdown();",
            "RM_UnloadModuleBinary( handle, completions );",
        ),
        context,
    )
    # the active module's snapshot is not the probe's to spend
    reject(probe, "rm_state.moduleCompletions", context)

    inventory = braced_block(loader, "bool R_RendererModule_QueryRenderingDevices(renderDeviceCatalog_t& output) {")
    require_ordered(inventory, ("rm_state.moduleExport.GetRenderingDevices(&output)",
        "Sys_DLL_Load(path)", "completions.Capture();", "entry(&imports)",
        "exports->Shutdown();", "RM_UnloadModuleBinary(handle,completions);"), "device inventory")
    reject(inventory, "rm_state.moduleCompletions", "device inventory")


def validate_loader_is_the_only_module_loader() -> None:
    """Any other code resolving GetRenderAPI would need its own capture."""
    sources = [*(ROOT / "src").rglob("*.cpp"), *(ROOT / "src").rglob("*.mm")]
    for path in sorted(sources):
        relative = path.relative_to(ROOT).as_posix()
        if relative == LOADER:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "RENDER_API_ENTRY_POINT" in text:
            raise AssertionError(f"{relative} resolves the renderer module entry point outside {LOADER}")


def main() -> None:
    validate_snapshot_is_engine_only()
    validate_restore_semantics()
    validate_every_unload_restores()
    validate_loader_is_the_only_module_loader()
    print("renderer_module_completion_safety: ok")


if __name__ == "__main__":
    main()
