#!/usr/bin/env python3
"""Guards openPREY's unified game-module selection contract.

Prey uses one game module for both single-player and multiplayer.  The gameplay
mode selected by ``si_gameType`` must therefore never choose a different binary.
This test also pins the in-tree game library default to single-player, keeps the
guarded reload path covered, and pins the engine-side game-module shutdown
lifecycle and the font reload contracts that a module reload depends on.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GAME_LIBS_ROOT = Path(os.environ.get("OPENQ4_GAMELIBS_REPO", ROOT)).resolve()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def reject(haystack: str, needle: str, context: str) -> None:
    if needle in haystack:
        raise AssertionError(f"Unexpected {needle!r} in {context}")


def function_body(source: str, signature: str, context: str) -> str:
    start = source.find(signature)
    if start < 0:
        raise AssertionError(f"Missing {signature!r} in {context}")
    opening = source.find("{", start + len(signature))
    if opening < 0:
        raise AssertionError(f"Missing body for {signature!r} in {context}")
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Unbalanced body for {signature!r} in {context}")


def cxx_function_body(source: str, signature: str) -> str:
    start = source.find(signature)
    if start == -1:
        raise AssertionError(f"Missing function {signature!r}")
    open_brace = source.index("{", start)
    depth = 0
    for index in range(open_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[open_brace + 1 : index]
    raise AssertionError(f"Unclosed function {signature!r}")


def validate_shutdown_lifecycle_contract(common: str) -> None:
    unload = function_body(common, "void idCommonLocal::UnloadGameDLL( void )", "game DLL unload")
    shutdown = function_body(common, "void idCommonLocal::ShutdownGame( bool reloading )", "game shutdown")
    load = function_body(common, "void idCommonLocal::LoadGameDLL( void )", "game DLL load")

    reject(unload, "game->Shutdown();", "binary-only game module unload")
    reject(unload, "game->ShutdownAfterDecls();", "binary-only game module unload")
    if common.count("game->Shutdown();") != 1:
        raise AssertionError("game module must receive exactly one engine-driven early shutdown")
    if common.count("game->ShutdownAfterDecls();") != 1:
        raise AssertionError("game module must receive exactly one engine-driven late finalization")

    for token in (
        "gameShutdownCalled = false;",
        "gameShutdownAfterDeclsCalled = false;",
    ):
        require(load, token, "game module lifecycle reset")

    false_store = shutdown.index(
        "openQ4_singleplayerGameModuleReady.store( false, std::memory_order_release );"
    )
    session_shutdown = shutdown.index("session->Shutdown();")
    early_shutdown = shutdown.index("game->Shutdown();")
    decl_shutdown = shutdown.index("declManager->Shutdown();")
    collision_shutdown = shutdown.index("collisionModelManager->Shutdown();")
    renderer_shutdown = shutdown.index("renderSystem->Shutdown();")
    if not early_shutdown < collision_shutdown < renderer_shutdown < decl_shutdown:
        raise AssertionError("collision caches must retire after game clips and before renderer/material declarations")
    late_shutdown = shutdown.index("game->ShutdownAfterDecls();")
    unload_dll = shutdown.index("UnloadGameDLL();")
    if false_store > early_shutdown:
        raise AssertionError("single-player module state is cleared after game shutdown begins")
    if session_shutdown > early_shutdown:
        raise AssertionError("game shutdown runs before session map teardown")
    for service_shutdown in (
        "uiManager->Shutdown();",
        "soundSystem->Shutdown();",
        "idAsyncNetwork::Shutdown();",
        "usercmdGen->Shutdown();",
        "eventLoop->Shutdown();",
        "renderSystem->Shutdown();",
    ):
        service = shutdown.index(service_shutdown)
        if early_shutdown > service:
            raise AssertionError(f"game shutdown runs after {service_shutdown}")
        if service > decl_shutdown:
            raise AssertionError(f"declaration shutdown runs before {service_shutdown}")
    if not decl_shutdown < late_shutdown < unload_dll:
        raise AssertionError("late game finalization must run after declarations and before DLL unload")

    early_guard = function_body(
        shutdown,
        "if ( game != NULL && !gameShutdownCalled )",
        "one-shot early game shutdown",
    )
    require(early_guard, "gameShutdownCalled = true;", "one-shot early game shutdown")
    require(early_guard, "game->Shutdown();", "one-shot early game shutdown")
    if early_guard.index("gameShutdownCalled = true;") > early_guard.index("game->Shutdown();"):
        raise AssertionError("early game shutdown publishes its one-shot state after crossing into module code")

    late_guard = function_body(
        shutdown,
        "if ( game != NULL && !gameShutdownAfterDeclsCalled )",
        "one-shot late game finalization",
    )
    require(late_guard, "gameShutdownAfterDeclsCalled = true;", "one-shot late game finalization")
    require(late_guard, "game->ShutdownAfterDecls();", "one-shot late game finalization")
    if late_guard.index("gameShutdownAfterDeclsCalled = true;") > late_guard.index("game->ShutdownAfterDecls();"):
        raise AssertionError("late game finalization publishes its one-shot state after crossing into module code")


def validate_font_resource_reset_contract(font_source: str, font_header: str) -> None:
    register = function_body(
        font_source,
        "bool idRenderSystemLocal::RegisterFont",
        "renderer font registration",
    )
    done = function_body(font_source, "void R_DoneFreeType( bool preserveAtlasImages )", "renderer font shutdown")
    refresh = function_body(
        font_source,
        "void R_RefreshConsoleFontAtlas( void )",
        "console font refresh",
    )

    require(
        font_source[: font_source.index("bool idRenderSystemLocal::RegisterFont")],
        "static bool consoleFontChecked = false;",
        "renderer-lifetime console font guard",
    )
    if font_source.count("static bool consoleFontChecked = false;") != 1:
        raise AssertionError("console font lifecycle guard must have one file-scope definition")
    reject(register, "static bool consoleFontChecked", "function-static console font guard")
    # The console sheet is byte-indexed, so besides the once-per-renderer guard it
    # also has to rebuild when sys_lang moves the string tables between the
    # Western and Central European codepages.
    for token in (
        "if ( !consoleFontChecked || consoleFontCodePageGeneration != codePageGeneration )",
        "consoleFontChecked = true;",
        "R_BuildConsoleFontAtlas();",
    ):
        require(register, token, "once-per-renderer console font rebuild")
    require(register, "LangDict_GetCodePageGeneration()", "codepage-aware console font rebuild")
    for token in ("consoleFontChecked = true;", "R_BuildConsoleFontAtlas();"):
        require(refresh, token, "console font refresh")
    if not (
        register.index("if ( !consoleFontChecked ||")
        < register.index("consoleFontChecked = true;")
        < register.index("R_BuildConsoleFontAtlas();")
        and refresh.index("consoleFontChecked = true;") < refresh.index("R_BuildConsoleFontAtlas();")
    ):
        raise AssertionError("RegisterFont must arm and rebuild the console atlas exactly once per font lifecycle")

    require(done, "R_ShutdownTrueTypeFonts( preserveAtlasImages );", "TrueType renderer shutdown")
    require(done, "consoleFontChecked = false;", "console font lifecycle reset")
    if done.index("R_ShutdownTrueTypeFonts( preserveAtlasImages );") > done.index("consoleFontChecked = false;"):
        raise AssertionError("console atlas guard resets before cached TrueType fonts shut down")
    require(font_header, "void R_RefreshConsoleFontAtlas( void );", "console font refresh declaration")


def validate_full_vid_restart_font_contract(renderer_source: str) -> None:
    restart = function_body(
        renderer_source,
        "static void R_PerformFullVidRestart( bool forceWindow )",
        "full video restart",
    )
    teardown = function_body(renderer_source, "static void R_ShutdownDeviceForRestart( void )", "restart teardown")
    require(restart, "R_ShutdownDeviceForRestart();", "shared restart teardown")
    restart = restart.replace("R_ShutdownDeviceForRestart();", teardown)
    for token in (
        "R_DoneFreeType( true );",
        "globalImages->PurgeAllImages();",
        "tr.InitOpenGL();",
        "R_InitFreeType();",
        "R_RefreshConsoleFontAtlas();",
    ):
        require(restart, token, "full video restart font lifecycle")
    if not (
        restart.index("R_DoneFreeType( true );")
        < restart.index("globalImages->PurgeAllImages();")
        < restart.index("tr.InitOpenGL();")
        < restart.index("R_InitFreeType();")
        < restart.index("R_RefreshConsoleFontAtlas();")
    ):
        raise AssertionError("Full vid_restart must release fonts before purge and rebuild them after image reload")
    reject(restart, "R_InitOpenGL();", "backend-aware device restart")
    reject(restart, "globalImages->ReloadImages", "single image reload owned by device startup")

    renderer_shutdown = function_body(
        renderer_source,
        "void idRenderSystemLocal::Shutdown( void )",
        "full renderer shutdown",
    )
    require(renderer_shutdown, "R_DoneFreeType( );", "full renderer font shutdown")
    if renderer_shutdown.index("R_DoneFreeType( );") > renderer_shutdown.index("globalImages->PurgeAllImages();"):
        raise AssertionError("Full renderer shutdown purges images before releasing cached TrueType fonts")

    vid_restart = function_body(renderer_source, "void R_VidRestart_f", "video restart command")
    full_branch = function_body(vid_restart, "if ( full )", "full video restart selection")
    require(full_branch, "R_PerformFullVidRestart( forceWindow );", "requested full video restart")
    reject(full_branch, "GLimp_SetScreenParms", "requested full video restart")
    if vid_restart.count("R_PerformFullVidRestart( forceWindow );") != 2:
        raise AssertionError("Full restart must cover the requested path and failed partial fallback")
    reject(vid_restart, "R_DoneFreeType", "successful partial video restart font preservation")

    partial_failure = function_body(
        vid_restart,
        "if ( !GLimp_SetScreenParms( parms ) )",
        "failed partial video restart",
    )
    require(partial_failure, "R_PerformFullVidRestart( forceWindow );", "failed partial full-restart fallback")
    failure_end = vid_restart.index(partial_failure) + len(partial_failure)
    partial_tail = vid_restart[failure_end:].lstrip()
    if not partial_tail.startswith("else {"):
        raise AssertionError("Successful partial video restart must be the failed-mode-change else path")
    partial_success = function_body(partial_tail, "else", "successful partial video restart")
    require(partial_success, "R_RefreshConsoleFontAtlas();", "partial console atlas refresh")
    for token in (
        "R_PerformFullVidRestart",
        "R_DoneFreeType",
        "R_InitFreeType",
        "globalImages->PurgeAllImages",
        "globalImages->ReloadImages",
    ):
        reject(partial_success, token, "partial font face/image preservation")

    generation = "if ( tr.videoRestartCount < 0x7fffffff )"
    require(vid_restart, generation, "video-restart font generation")
    require(vid_restart, "tr.videoRestartCount++;", "video-restart font generation")
    if vid_restart.index(generation) < failure_end + partial_tail.index(partial_success) + len(partial_success):
        raise AssertionError("Renderer restart generation advances before the full/partial font work finishes")


def validate_ui_font_reload_contract(
    device_source: str,
    device_header: str,
    public_header: str,
) -> None:
    reload_fonts = function_body(device_source, "bool idDeviceContext::ReloadFonts()", "UI font reload")
    for token in (
        "if ( fonts.Num() == 0 )",
        "int activeFontIndex = 0;",
        "int useFontSlot = -1;",
        "if ( activeFont != &fonts[i] )",
        "fontLang = cvarSystem->GetCVarString( \"sys_lang\" );",
        "openQ4_NormalizeFontLanguage( fontLang );",
        "for ( int i = 0; i < fonts.Num(); ++i )",
        "idStr::Copynz( logicalName, fonts[i].name, sizeof( logicalName ) );",
        # registration goes through the helper so a language without its own font
        # artwork falls back to English instead of failing every font
        "openQ4_RegisterFontForLanguage( logicalName, fontLang, replacement, fileName )",
        "fontInfoEx_t replacement;",
        "idStr::Copynz( replacement.name, logicalName, sizeof( replacement.name ) );",
        "fonts[i] = replacement;",
        "SetFont( activeFontIndex );",
        "useFont = &activeFont->fontInfoSmall;",
        "useFont = &activeFont->fontInfoMedium;",
        "useFont = &activeFont->fontInfoLarge;",
        "return allFontsReloaded;",
    ):
        require(reload_fonts, token, "UI font reload")
    reject(reload_fonts, "fonts.Append", "stable UI font indices across vid_restart")
    if not (
        reload_fonts.index("idStr::Copynz( logicalName, fonts[i].name")
        < reload_fonts.index("openQ4_RegisterFontForLanguage( logicalName, fontLang, replacement, fileName )")
        < reload_fonts.index("fonts[i] = replacement;")
        < reload_fonts.index("SetFont( activeFontIndex );")
    ):
        raise AssertionError("UI font reload must replace cached entries in place before restoring selection")

    register_for_language = function_body(
        device_source,
        "static bool openQ4_RegisterFontForLanguage(",
        "language font fallback",
    )
    for token in (
        "openQ4_ResolveFontFileName( logicalName, language, resolvedFileName );",
        "renderSystem->RegisterFont( resolvedFileName, font )",
        "idStr::Icmp( language.c_str(), \"english\" ) == 0",
        "openQ4_ResolveFontFileName( logicalName, idStr( \"english\" ), englishFileName );",
    ):
        require(register_for_language, token, "language font fallback")
    if not (
        register_for_language.index("renderSystem->RegisterFont( resolvedFileName, font )")
        < register_for_language.index("openQ4_ResolveFontFileName( logicalName, idStr( \"english\" ), englishFileName );")
    ):
        raise AssertionError(
            "the language-specific font must be tried before the English fallback, so a "
            "localised release keeps its own atlases"
        )

    ensure = function_body(device_source, "void idDeviceContext::EnsureFontsCurrent()", "lazy UI font refresh")
    for token in (
        "!initialized || renderSystem == NULL || !renderSystem->IsOpenGLRunning()",
        "const int currentRestartCount = renderSystem->GetVideoRestartCount();",
        # a sys_lang change that swaps the 8-bit codepage invalidates every glyph
        # atlas even though the renderer never restarted
        "const int currentCodePageGeneration = LangDict_GetCodePageGeneration();",
        "if ( fontsVideoRestartCount == currentRestartCount &&",
        "fontsCodePageGeneration == currentCodePageGeneration )",
        "fontsVideoRestartCount = currentRestartCount;",
        "fontsCodePageGeneration = currentCodePageGeneration;",
        "if ( !ReloadFonts() )",
    ):
        require(ensure, token, "lazy UI font refresh")
    if not (
        ensure.index("if ( fontsVideoRestartCount == currentRestartCount &&")
        < ensure.index("fontsVideoRestartCount = currentRestartCount;")
        < ensure.index("if ( !ReloadFonts() )")
    ):
        raise AssertionError("UI font refresh must record the generation before its recursive registration paths")

    for signature, context in (
        ("int idDeviceContext::FindFont", "font lookup refresh"),
        ("void idDeviceContext::SetFont( int num )", "font selection refresh"),
        ("void idDeviceContext::SetFontByScale", "font scale refresh"),
    ):
        caller = function_body(device_source, signature, context)
        require(caller, "EnsureFontsCurrent();", context)

    require(device_source, "int idDeviceContext::fontsVideoRestartCount = -1;", "UI font restart generation")
    init = function_body(device_source, "void idDeviceContext::Init()", "UI device-context initialization")
    require(init, "fontsVideoRestartCount = renderSystem->GetVideoRestartCount();", "initial UI font generation")
    shutdown = function_body(device_source, "void idDeviceContext::Shutdown()", "UI device-context shutdown")
    require(shutdown, "fontsVideoRestartCount = -1;", "UI font generation reset")

    # activeFont and useFont point into the fonts list, which reallocates on
    # every append because its granularity is 1. Registering a face a later map
    # is the first to name would otherwise leave the current selection reading a
    # freed allocation, which is a font that lays text out from garbage metrics.
    find_font = function_body(device_source, "int idDeviceContext::FindFont", "device-context font lookup")
    require(find_font, "fonts.Append( fontInfo )", "device-context font lookup")
    for token in (
        "activeFont = ( selectedFont >= 0 ) ? &fonts[selectedFont] : NULL;",
        "useFont = ( selectedSize == 0 ) ? &sized.fontInfoSmall",
    ):
        require(find_font, token, "font selection reseat across list growth")
    if find_font.index("fonts.Append( fontInfo )") > find_font.index("activeFont = ( selectedFont >= 0 )"):
        raise AssertionError("font selection must be reseated after the fonts list grows, not before")

    require(device_header, "bool\t\t\t\tReloadFonts();", "device-context font reload declaration")
    require(device_header, "void\t\t\t\tEnsureFontsCurrent();", "lazy UI font refresh declaration")
    require(device_header, "static int\t\t\tfontsVideoRestartCount;", "UI font restart generation declaration")
    reject(public_header, "ReloadFonts", "cross-module UI interface font reload")


def validate_ttf_persistent_atlas_contract(ttf_source: str) -> None:
    # The GUI upload lives in R_TTFPackAtlas rather than R_TTFBuildSlot: the base
    # Latin-1 slots and the extended code-point pages are two atlases now, and
    # both go through the one packer so they cannot diverge.
    slot = function_body(ttf_source, "static bool R_TTFPackAtlas", "GUI TrueType atlas")
    console = function_body(ttf_source, "bool R_BuildConsoleFontAtlas", "console TrueType atlas")
    for body, context in ((slot, "GUI TrueType atlas"), (console, "console TrueType atlas")):
        require(body, "R_TTFUploadAtlasImage(", context)
    upload = function_body(ttf_source, "static idImage *R_TTFUploadAtlasImage", "TrueType atlas registration")
    require(upload, "globalImages->ImageFromFunction( name, R_TTFGenerateAtlasImage )", "reloadable TrueType atlas")
    generate = function_body(ttf_source, "static void R_TTFGenerateAtlasImage", "TrueType atlas regeneration")
    require(generate, "opts.isPersistant = true;", "TrueType atlas residency")
    require(generate, "image->SubImageUpload(", "TrueType atlas pixel restoration")

    for token in (
        "static idMaterial *ttfConsoleMaterial = NULL;",
        "static idImage *ttfConsoleOriginalImage = NULL;",
    ):
        require(ttf_source, token, "authored console image preservation")
    shutdown = function_body(ttf_source, "void R_ShutdownTrueTypeFonts( bool preserveAtlasImages )", "TrueType font shutdown")
    for token in (
        "ttfConsoleMaterial->OverrideStageImageForRuntime( 0, ttfConsoleOriginalImage )",
        "ttfConsoleMaterial = NULL;",
        "ttfConsoleOriginalImage = NULL;",
        "ttfFonts.Shutdown();",
    ):
        require(shutdown, token, "authored console image restoration")
    if not (
        shutdown.index("OverrideStageImageForRuntime")
        < shutdown.index("ttfConsoleMaterial = NULL;")
        < shutdown.index("ttfConsoleOriginalImage = NULL;")
        < shutdown.index("ttfFonts.Shutdown();")
    ):
        raise AssertionError("TrueType shutdown must restore the authored console image before releasing state")

    # The generated atlas materials have no file behind them. If a declaration
    # purge is ever allowed to reset one, the implicit text the manager
    # regenerates maps an image that does not exist, so every glyph samples the
    # transparent default and GUI text silently disappears for the rest of the
    # session. Two things keep that from happening: the declaration carries the
    # generated source itself, and the level-load purge is followed by a restore.
    install = function_body(
        ttf_source, "static void R_TTFInstallAtlasStage", "TrueType atlas stage install"
    )
    for token in ("SetText(", "FreeData();", "Parse(", "SetSort( SS_GUI );"):
        require(install, token, "TrueType atlas stage install")
    if install.index("SetText(") > install.index("Parse("):
        raise AssertionError("TrueType atlas material must carry its source text before it is parsed")

    create = function_body(
        ttf_source, "static const idMaterial *R_TTFCreateAtlasMaterial", "TrueType atlas material creation"
    )
    require(create, "R_TTFInstallAtlasStage(", "TrueType atlas material creation")
    require(create, "ttfAtlasMaterials.Append(", "TrueType atlas material registry")
    reject(
        create,
        "if ( !R_TTFMaterialSamplesAtlas(",
        "unconditional TrueType atlas material source install",
    )

    # FindMaterial parses a newly created implicit material before this module
    # can replace its source. Its default stage maps an image named after the
    # material, so the generated material must share the already-uploaded
    # intrinsic atlas identity. A separate openq4/ttffont name probes a file
    # which can never exist and emits one warning/default image per atlas.
    for signature, context in (
        ("static void R_TTFBuildExtendedPages", "extended TrueType atlas identity"),
        ("static bool R_TTFBuildSlot", "base TrueType atlas identity"),
    ):
        atlas = function_body(ttf_source, signature, context)
        require(atlas, "const idStr materialName = imageName;", context)
        reject(atlas, "openq4/ttffont", context)

    restore = function_body(
        ttf_source, "void R_TTFRestoreAtlasMaterials( void )", "TrueType atlas material restore"
    )
    require(restore, "FindDeclWithoutParsing(", "TrueType atlas material restore")
    require(restore, "R_TTFInstallAtlasStage(", "TrueType atlas material restore")
    require(
        function_body(ttf_source, "void R_ShutdownTrueTypeFonts( bool preserveAtlasImages )", "TrueType font shutdown"),
        "ttfAtlasMaterials.DeleteContents( true );",
        "TrueType atlas material registry release",
    )


def validate_ttf_level_load_restore_contract() -> None:
    render_init = read(ROOT / "src" / "renderer" / "RenderSystem_init.cpp")
    begin = function_body(
        render_init, "void idRenderSystemLocal::BeginLevelLoad( void )", "renderer level-load begin"
    )
    require(begin, "R_TTFRestoreAtlasMaterials();", "renderer level-load begin")
    if begin.index("R_TTFRestoreAtlasMaterials();") > begin.index("globalImages->BeginLevelLoad();"):
        raise AssertionError(
            "purged glyph atlas materials must be restored before the level-load image purge runs"
        )
    require(
        read(ROOT / "src" / "renderer" / "tr_local.h"),
        "void R_TTFRestoreAtlasMaterials( void );",
        "TrueType atlas restore declaration",
    )


def validate_font_restart_documentation() -> None:
    documentation = read(ROOT / "docs" / "dev" / "ttf-font-system.md")
    for token in (
        "A full `vid_restart`\nreleases cached TrueType faces before image purge",
        "A successful partial restart keeps the context,\nfaces, and images alive",
        "Cached GUI fonts notice the renderer restart generation on their next\nlookup or selection and re-register in place",
        "preserving the integer indices\nstored by parsed GUIs as well as the active font and size selection",
    ):
        require(documentation, token, "TrueType renderer-restart documentation")


def validate_unified_module_selection() -> None:
    common = read(ROOT / "src" / "framework" / "Common.cpp")
    selector = cxx_function_body(
        common, "static const char *openPREY_SelectGameModuleBaseName( void )"
    )
    require(selector, 'return "game";', "unified game-module selector")
    reject(selector, "si_gameType", "unified game-module selector")

    candidates = cxx_function_body(
        common, "static void openPREY_BuildGameModuleCandidateList( idStrList &candidates )"
    )
    require(
        candidates,
        'va( "game_%s", OPENPREY_MODULE_ARCH_TAG )',
        "unified game-module candidate list",
    )
    require(candidates, '"game_universal2"', "unified macOS module compatibility")
    require(candidates, '"game"', "unified untagged module compatibility")
    reject(candidates, '"game_sp', "unified game-module candidate list")
    reject(candidates, '"game_mp', "unified game-module candidate list")

    loader = cxx_function_body(common, "void idCommonLocal::LoadGameDLL( void )")
    require(
        loader,
        "openPREY_SelectGameModuleBaseName()",
        "unified game-module loader",
    )
    require(
        loader,
        "openPREY_BuildGameModuleCandidateList( gameModuleCandidates )",
        "unified game-module loader",
    )
    require(
        loader,
        "couldn't find unified game dynamic library",
        "unified game-module loader diagnostic",
    )


def validate_game_type_default() -> None:
    sys_cvar = GAME_LIBS_ROOT / "src" / "game" / "gamesys" / "SysCvar.cpp"
    if not sys_cvar.is_file():
        print(
            "game_type_module_selection: skipped GameLibs default cross-check "
            f"(no canonical source at {sys_cvar})"
        )
        return

    source = read(sys_cvar)
    match = re.search(
        r"^const char \*si_gameTypeArgs\[\]\s*=\s*\{([^}]*)\};",
        source,
        re.MULTILINE,
    )
    if match is None:
        raise AssertionError("active in-tree Prey game si_gameTypeArgs declaration is missing")
    game_types = re.findall(r'"([^"]*)"', match.group(1))
    if not game_types or game_types[0] != "singleplayer":
        raise AssertionError(
            f"in-tree Prey game si_gameTypeArgs starts with {game_types[:1]!r}, "
            "expected 'singleplayer'"
        )
    require(
        source,
        'idCVar si_gameType(\t\t\t\t\t"si_gameType",\t\t\t\tsi_gameTypeArgs[ 0 ]',
        "in-tree Prey game default gametype",
    )


def validate_unified_build_contract() -> None:
    meson = read(ROOT / "meson.build")
    basepr_meson = read(ROOT / "content" / "basepr" / "meson.build")
    require(meson, "game_binary_name = 'game_' + binary_arch", "unified module name")
    require(
        meson,
        "Prey uses one unified game module for both single-player and multiplayer.",
        "unified module source contract",
    )
    require(basepr_meson, "game_module_target =", "unified basepr module target")


def validate_swap_guard() -> None:
    common = read(ROOT / "src" / "framework" / "Common.cpp")
    start = common.index("void Com_ReloadGameModule_f( const idCmdArgs &args ) {")
    end = common.index("idCommonLocal::GetLanguageDict", start)
    body = common[start:end]
    for token in (
        "try {",
        "commonLocal.ShutdownGame( true );",
        "commonLocal.InitGame();",
        "catch( idException &ex ) {",
        "swapFailed = true;",
        "failedPhase = Com_GetGameModuleLoadPhase();",
        "Com_GameModuleLoadPhaseName( failedPhase )",
        "============= ReloadGameModule failed ============",
        "session->StartMenu();",
    ):
        require(body, token, "game module swap exception guard")


def validate_async_module_state() -> None:
    common = read(ROOT / "src" / "framework" / "Common.cpp")
    validate_shutdown_lifecycle_contract(common)
    helper_start = common.index(
        "static bool openQ4_ShouldUseSmoothSingleplayerSlowTime( float effectiveTimeScale ) {"
    )
    helper_end = common.index("\n}\n", helper_start)
    helper = common[helper_start:helper_end]

    # The async thread runs while game DLL initialization registers static
    # CVars. A name-based lookup here races the registry's backing array, and a
    # direct idStr read still has a phase-check/read timing gap during unload.
    if "cvarSystem->" in helper or "GetCVarString" in helper or "com_activeGameModule" in helper:
        raise AssertionError("async slow-time helper still reads mutable CVar/module strings")
    require(
        common,
        "static std::atomic<bool> openQ4_singleplayerGameModuleReady( false );",
        "async-safe game module state",
    )
    require(
        helper,
        "openQ4_singleplayerGameModuleReady.load( std::memory_order_acquire )",
        "async-safe game module state",
    )
    require(
        helper,
        "return effectiveTimeScale < 0.999f;",
        "composed single-player slow-time detection",
    )

    load_start = common.index("void idCommonLocal::LoadGameDLL( void ) {")
    unload_start = common.index("void idCommonLocal::UnloadGameDLL( void ) {", load_start)
    load_body = common[load_start:unload_start]
    require(
        load_body,
        "openQ4_singleplayerGameModuleReady.store( false, std::memory_order_release );",
        "game module load transition",
    )
    require(
        load_body,
        "openQ4_NormalizeGameTypeForModule( gameModuleBaseName );",
        "game type normalization before module load",
    )
    if load_body.index("openQ4_NormalizeGameTypeForModule") > load_body.index("sys->DLL_Load"):
        raise AssertionError("game type is normalized after the module starts loading")

    init_start = common.index("void idCommonLocal::InitGame( void ) {")
    init_end = common.index("void idCommonLocal::ShutdownGame( bool reloading ) {", init_start)
    init_body = common[init_start:init_end]
    for token in (
        "const idStr pendingGameModule = openPREY_SelectGameModuleBaseName();",
        "openQ4_NormalizeGameTypeForModule( pendingGameModule.c_str() );",
    ):
        require(init_body, token, "game type normalization before declaration initialization")
    if not (
        init_body.index("const idStr pendingGameModule")
        < init_body.index("openQ4_NormalizeGameTypeForModule( pendingGameModule.c_str() );")
        < init_body.index("declManager->Init")
    ):
        raise AssertionError("game type is normalized after declarations initialize")

    reject(common, "openQ4_StartupRequiresMultiplayerModule", "startup command preselection")
    common_init_start = common.index("void idCommonLocal::Init( int argc")
    common_init_end = common.index("void idCommonLocal::Shutdown( void ) {", common_init_start)
    common_init = common[common_init_start:common_init_end]
    for token in (
        'SetCVarString( "com_nextGameModule", "game_mp" )',
        'openQ4_NormalizeGameTypeForModule( "game_mp" );',
    ):
        reject(common_init, token, "startup command preselection")

    validate_font_resource_reset_contract(
        read(ROOT / "src" / "renderer" / "tr_font.cpp"),
        read(ROOT / "src" / "renderer" / "tr_local.h"),
    )
    validate_full_vid_restart_font_contract(read(ROOT / "src" / "renderer" / "RenderSystem_init.cpp"))
    validate_ui_font_reload_contract(
        read(ROOT / "src" / "ui" / "DeviceContext.cpp"),
        read(ROOT / "src" / "ui" / "DeviceContext.h"),
        read(ROOT / "src" / "ui" / "UserInterface.h"),
    )
    validate_ttf_persistent_atlas_contract(read(ROOT / "src" / "renderer" / "tr_fontTTF.cpp"))
    validate_ttf_level_load_restore_contract()


def validate_decl_source_scanner_contract() -> None:
    source = read(ROOT / "src" / "framework" / "DeclManager.cpp")
    require(
        source,
        "declDefinition = finalPreprocessedBuffer.Mid( startMarker, sourceSize );",
        "loose decl exact-source scanner",
    )
    require(
        source,
        "declDefinition = packedText.Mid( startMarker, sourceSize );",
        "packed decl exact-source scanner",
    )
    reject(
        source,
        "src.ParseBracedSectionExact( declDefinition, -1 );",
        "comment-safe decl source scanners",
    )


def validate_renderer_module_fail_closed_contract() -> None:
    api = read(ROOT / "src" / "renderer" / "RenderModuleAPI.h")
    require(api, "#define RENDER_API_VERSION\t\t\t34", "current renderer ABI")

    loader = read(ROOT / "src" / "renderer" / "RendererModule.cpp")
    require(
        loader,
        "moduleExport->version != RENDER_API_VERSION",
        "stale renderer-module rejection",
    )
    require(
        loader,
        '"module render API version mismatch"',
        "stale renderer-module diagnostic",
    )

    session = read(ROOT / "src" / "framework" / "Session.cpp")
    unload = cxx_function_body(session, "void idSessionLocal::UnloadMap()")
    require(
        unload,
        "if ( soundSystem && sw )",
        "renderer-ABI early-fatal sound-world guard",
    )


def main() -> int:
    validate_unified_module_selection()
    validate_game_type_default()
    validate_unified_build_contract()
    validate_font_restart_documentation()
    validate_swap_guard()
    validate_async_module_state()
    validate_decl_source_scanner_contract()
    validate_renderer_module_fail_closed_contract()
    print("game_type_module_selection: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
