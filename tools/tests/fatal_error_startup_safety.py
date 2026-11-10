#!/usr/bin/env python3
"""Static checks for issue #96 fatal-error-during-startup safety.

A renderer that fails to bring up its device calls common->FatalError, which
runs the full engine teardown. FatalError can fire from anywhere in startup,
including before idSessionLocal::Init has allocated the sound worlds that the
teardown path walks -- so the teardown has to tolerate a half-built engine, and
the fatal message has to survive a fault in it.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


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


def function_body(source: str, signature: str) -> str:
    start = source.find(signature)
    if start == -1:
        raise AssertionError(f"Missing function signature {signature!r}")

    depth = 0
    for index in range(start, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]

    raise AssertionError(f"Could not find end of function {signature!r}")


def validate_startup_order() -> None:
    """The ordering that makes a NULL sound world reachable in the first place.

    soundSystem is live well before the renderer starts, but the sound worlds
    are not: session->Init() runs after InitRenderSystem(). A renderer failure
    therefore tears down with soundSystem non-NULL and session->sw NULL, which
    is why guarding the system pointer alone never fixed this.
    """
    common = read("src/framework/Common.cpp")
    init_game = function_body(common, "void idCommonLocal::InitGame( void ) {")

    require_ordered(
        init_game,
        (
            "soundSystem->Init();",
            "InitRenderSystem();",
            "session->Init();",
        ),
        "idCommonLocal::InitGame startup order",
    )

    snd_system = read("src/sound/snd_system.cpp")
    get_world = function_body(
        snd_system, "idSoundWorld* idSoundSystemLocal::GetSoundWorldFromId(int worldId) {"
    )
    require(get_world, "return session->sw;", "GetSoundWorldFromId game world source")

    require(
        snd_system,
        "idSoundSystem* soundSystem = &soundSystemLocal;",
        "soundSystem global is statically bound and never NULL in the engine",
    )


def validate_sound_world_guards() -> None:
    """Every idSoundSystem helper that forwards through GetSoundWorldFromId."""
    sound = read("src/sound/sound.h")

    helpers = (
        "idSoundEmitter* EmitterForIndex(int worldId, int index) {",
        "void			FadeSoundClasses(int worldId, const int soundClass, const float to, const float over) {",
        "void			PlayShaderDirectly(int worldId, const char* name, int channel = -1) {",
        "virtual int				AllocSoundEmitter(int worldId) {",
        "virtual void StopAllSounds(int worldId) {",
        "virtual void			WriteToSaveGame(int worldId, idFile* savefile) {",
        "virtual void			ReadFromSaveGame(int worldId, idFile* savefile) {",
        "void			PlaceListener(const idVec3& origin, const idMat3& axis, const int listenerId, const int gameTime, const idStr& areaName) {",
    )

    for helper in helpers:
        body = function_body(sound, helper)
        require_ordered(
            body,
            (
                "idSoundWorld* soundWorld = GetSoundWorldFromId(",
                "if (soundWorld == NULL) {",
            ),
            f"idSoundSystem helper {helper.strip()!r}",
        )

    # the original unguarded shape: a call chained straight off the accessor
    for line in sound.splitlines():
        code = line.split("//", 1)[0]
        for unguarded in (
            "GetSoundWorldFromId(worldId)->",
            "GetSoundWorldFromId(SOUNDWORLD_GAME)->",
        ):
            if unguarded in code:
                raise AssertionError(
                    f"Unguarded {unguarded!r} in src/sound/sound.h: {line.strip()!r}"
                )

    require(
        sound,
        "// index 0 is the reserved \"no emitter\" handle",
        "AllocSoundEmitter invalid-handle sentinel is documented",
    )

    # the accessor is documented as nullable by an existing caller
    snd_system = read("src/sound/snd_system.cpp")
    free_emitter = function_body(
        snd_system,
        "void idSoundSystemLocal::FreeSoundEmitter(int worldId, int handle, bool immediate)",
    )
    require(free_emitter, "if( soundWorld == NULL )", "existing NULL-world precedent")


def validate_teardown_call_site() -> None:
    """The call that crashed, and the guards around it that already existed."""
    session = read("src/framework/Session.cpp")

    unload_map = function_body(session, "void idSessionLocal::UnloadMap() {")
    require_ordered(
        unload_map,
        (
            "if ( soundSystem ) {",
            "soundSystem->StopAllSounds( SOUNDWORLD_GAME );",
        ),
        "idSessionLocal::UnloadMap sound teardown",
    )
    require(unload_map, "if ( game ) {", "UnloadMap game-module guard")
    require(unload_map, "if ( rw ) {", "UnloadMap render-world guard")

    stop_internal = function_body(session, "void idSessionLocal::StopInternal( bool preserveWipe ) {")
    require(stop_internal, "if ( sw ) {", "idSessionLocal::StopInternal sound-world guard")

    shutdown = function_body(session, "void idSessionLocal::Shutdown() {")
    for token in ("if ( sw ) {", "if ( menuSoundWorld ) {", "if ( rw ) {"):
        require(shutdown, token, "idSessionLocal::Shutdown teardown guards")

    common = read("src/framework/Common.cpp")
    shutdown_game = function_body(common, "void idCommonLocal::ShutdownGame( bool reloading ) {")
    for token in ("if ( renderSystem ) {", "if ( bse ) {"):
        require(shutdown_game, token, "idCommonLocal::ShutdownGame teardown guards")


def validate_fatal_output_flush() -> None:
    """Buffered stdout must reach the terminal before teardown can fault."""
    common = read("src/framework/Common.cpp")

    flush = function_body(common, "static void Com_FlushBufferedOutput( void ) {")
    require(flush, "fflush( NULL );", "Com_FlushBufferedOutput body")

    fatal_error = function_body(common, "void idCommonLocal::FatalError( const char *fmt, ... ) {")
    require_ordered(
        fatal_error,
        (
            'Printf( "********************\\nFATAL: %s\\n********************\\n", errorMessage );',
            "Com_FlushBufferedOutput();",
            "Shutdown();",
            'Sys_Error( "%s", errorMessage );',
        ),
        "idCommonLocal::FatalError flush before teardown",
    )

    error = function_body(common, "void idCommonLocal::Error( const char *fmt, ... ) {")
    require_ordered(
        error,
        (
            "Com_FlushBufferedOutput();",
            "Shutdown();",
            'Sys_Error( "%s", errorMessage );',
        ),
        "idCommonLocal::Error flush before teardown",
    )


def validate_posix_fatal_signal_report() -> None:
    """A signal death during teardown must still name the fatal error."""
    signal_source = read("src/sys/posix/posix_signal.cpp")

    set_fatal = function_body(signal_source, "void Sys_SetFatalError( const char *error ) {")
    require(set_fatal, "strncpy( fatalError, error, sizeof( fatalError ) - 1 );", "Sys_SetFatalError parks the message")

    handler = function_body(
        signal_source, "static void sig_handler( int signum, siginfo_t *info, void *context ) {"
    )
    require_ordered(
        handler,
        (
            'Posix_WriteSignalText( "openQ4: fatal signal " );',
            'Posix_WriteSignalText( "), exiting without unsafe engine shutdown\\n" );',
            "if ( fatalError[0] != '\\0' ) {",
            'Posix_WriteSignalText( "openQ4: fatal error being reported: " );',
            "Posix_WriteSignalText( fatalError );",
            'Posix_WriteSignalText( "openQ4: last renderer startup phase: " );',
            "Posix_RendererStartupPhaseName()",
            'Posix_WriteSignalText( "openQ4: last game module phase: " );',
            "Com_GameModuleLoadPhaseSignalName()",
            "Posix_AppendFatalBreadcrumbRaw( breadcrumb );",
            'strcpy( fatalBreadcrumb, "fatal error being reported: " );',
            "Posix_AppendFatalBreadcrumbRaw( fatalBreadcrumb );",
            "_exit( 128 + signum );",
        ),
        "POSIX fatal signal handler report order",
    )

    # the durable breadcrumb copy must stay bounded: fatalError is 4096 bytes
    require(handler, "char fatalBreadcrumb[ 512 ];", "bounded fatal breadcrumb buffer")
    require(
        handler,
        "strncat( fatalBreadcrumb, fatalError,",
        "bounded fatal breadcrumb append",
    )
    reject(handler, "strcat( fatalBreadcrumb, fatalError )", "unbounded fatal breadcrumb append")


def validate_renderer_failure_entry_points() -> None:
    """Startup retries Vulkan failures; later restarts retain durable recovery.

    The ordinary InitGame owner teardown must finish while the failed module
    remains loaded. Only then may the loader remove its callbacks and code.
    A later vid_restart still cannot unload the module on its own call stack.
    """
    renderer = read("src/renderer/RenderSystem_init.cpp")

    init_opengl = function_body(renderer, "static bool R_InitRendererDevice( bool legacyPolicy, bool forceWindow, char *error, int errorSize ) {")
    require_ordered(
        init_opengl,
        (
            "if ( !VK_InitRenderDevice() ) {",
            "if ( legacyPolicy ) {",
            "const bool nextLaunchUsesGL = R_RendererModule_ResetApiAfterDeviceFailure();",
            'common->FatalError( "Vulkan renderer device initialization failed; %s",',
            '"r_renderApi has been reset to gl, so the next launch uses OpenGL"',
            '"launch with +set r_renderApi gl to use OpenGL"',
        ),
        "Vulkan device bring-up failure path",
    )
    require(
        renderer,
        'return R_RendererRestartError( error, errorSize, "Unable to initialize OpenGL" );',
        "OpenGL bring-up failure path",
    )

    loader = read("src/renderer/RendererModule.cpp")
    common = read("src/framework/Common.cpp")
    startup = function_body(common, "void idCommonLocal::InitGame( void ) {")
    require_ordered(startup, (
        "!R_RendererModule_PrepareStartupDevice()",
        "ShutdownGame( true );",
        "!R_RendererModule_RetryFailedStartup()",
        "InitGame();",
        "InitRenderSystem();",
        "uiManager->Init();",
        "LoadGameDLL();",
    ), "startup recovery returns through module code before owner teardown")
    retry = function_body(loader, "bool R_RendererModule_RetryFailedStartup( void ) {")
    require_ordered(retry, (
        "!rm_state.startupDeviceFailed",
        "cmdSystem->RemoveFlaggedCommands( CMD_FL_RENDERER );",
        "RM_UnloadModule();",
        "rm_state.startupRetryPending = true;",
    ), "failed startup retires command callbacks before unloading")
    try_load = function_body(
        loader,
        "static bool RM_TryLoadModuleApi( rendererModuleApi_t api, rendererModuleStatus_t &status ) {",
    )
    require_ordered(
        try_load,
        (
            "if ( !RM_ExportCanRender( moduleExport, &reason ) ) {",
            "const bool deviceReady = RM_ExportDeviceReady( moduleExport, deviceSummary, sizeof( deviceSummary ) );",
            "if ( !deviceReady ) {",
            "RM_UnloadModuleBinary( handle, rm_state.moduleCompletions );",
            '"device probe failed: %s"',
            "return false;",
            "RM_PublishActiveModuleInterfaces( rm_state.moduleExport );",
        ),
        "renderer module device probe runs before activation",
    )
    device_ready = function_body(
        loader,
        "static bool RM_ExportDeviceReady( const renderExport_t *moduleExport, char *outSummary, int summaryLength ) {",
    )
    require(device_ready, "moduleExport->diagnostics->RunDeviceSelfTest( outSummary, summaryLength )", "device probe gate")

    reset = function_body(loader, "bool R_RendererModule_ResetApiAfterDeviceFailure( void ) {")
    require_ordered(
        reset,
        (
            "RM_PeekConfigRenderApi( configValue, sizeof( configValue ) )",
            "configApi != RENDER_MODULE_API_VULKAN",
            'fileSystem->RelativePathToOSPath( CONFIG_FILE, "fs_savepath" )',
            'fileSystem->OpenFileAppend( CONFIG_FILE, false, "fs_savepath" );',
            'seta r_renderApi \\"gl\\"',
        ),
        "device-failure reset appends a gl selection to the saved config",
    )
    # the whole-config writer drops every game-module cvar this early in startup
    reject(reset, "WriteConfigToFile", "device-failure reset")

    api = read("src/renderer/RenderModuleAPI.h")
    require(api, "bool\t\t\t( *ResetRenderApiAfterDeviceFailure )( void );", "renderer module services")
    module_glue = read("src/renderer/RendererGLModule.cpp")
    require(
        module_glue,
        "return rgm_services->ResetRenderApiAfterDeviceFailure();",
        "module forwards the device-failure reset to the loader",
    )


def validate_ci_wiring() -> None:
    local_runner = read("tools/validation/openq4_validate.py")
    commit = read(".github/workflows/commit-validation.yml")
    push = read(".github/workflows/push-verification.yml")

    require(local_runner, "fatal_error_startup_safety.py", "local validation runner")
    for source, context in (
        (commit, "commit validation workflow"),
        (push, "push verification workflow"),
    ):
        require(source, "tools/tests/fatal_error_startup_safety.py", context)
        require(source, "python tools/tests/fatal_error_startup_safety.py", context)


def main() -> None:
    validate_startup_order()
    validate_sound_world_guards()
    validate_teardown_call_site()
    validate_fatal_output_flush()
    validate_posix_fatal_signal_report()
    validate_renderer_failure_entry_points()
    validate_ci_wiring()
    print("fatal_error_startup_safety: ok")


if __name__ == "__main__":
    main()
