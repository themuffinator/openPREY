#!/usr/bin/env python3
"""Regression checks for startup language override ordering."""

import re
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


def require_regex(haystack: str, pattern: str, context: str) -> None:
    if re.search(pattern, haystack) is None:
        raise AssertionError(f"Missing pattern {pattern!r} in {context}")


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


def require_order(haystack: str, first: str, second: str, context: str) -> None:
    first_index = haystack.find(first)
    second_index = haystack.find(second)
    if first_index == -1 or second_index == -1:
        raise AssertionError(f"Missing ordered symbols {first!r} and/or {second!r} in {context}")
    if first_index >= second_index:
        raise AssertionError(f"Expected {first!r} before {second!r} in {context}")


def validate_language_reload_contract() -> None:
    source = read("src/framework/Common.cpp")
    init_language = function_body(source, "void idCommonLocal::InitLanguageDict( bool applyStartupSysLang, bool allowAutoLanguageSelect ) {")
    reload_command = function_body(source, "void Com_ReloadLanguage_f( const idCmdArgs &args ) {")
    init_game = function_body(source, "void idCommonLocal::InitGame( void ) {")

    require_regex(
        source,
        r"void\s+InitLanguageDict\s*\(\s*bool\s+applyStartupSysLang\s*,\s*bool\s+allowAutoLanguageSelect\s*\)\s*;",
        "Common language helper declaration",
    )
    require(init_language, "if ( applyStartupSysLang ) {", "conditional startup sys_lang replay")
    require(init_language, 'StartupVariable( "sys_lang", false );', "early startup sys_lang replay")
    require(init_language, "fileSystem->ListAvailableLanguagePacks( availableLanguagePacks );", "language pack availability discovery")
    require(init_language, "const bool hasStartupSysLang = Common_HasStartupVariable( \"sys_lang\" );", "explicit startup sys_lang detection")
    require(init_language, "Common_ResolveLanguageSelection(", "language pack constrained resolver")
    require(init_language, "allowAutoLanguageSelect && !hasStartupSysLang", "OS language preference only when startup sys_lang is not explicit")
    require(reload_command, "const bool wasFileLoadingAllowed = fileSystem->GetIsFileLoadingAllowed();", "interactive reloadLanguage preserves file-loading flag")
    require(reload_command, "fileSystem->SetIsFileLoadingAllowed( true );", "interactive reloadLanguage enables file loading")
    require(reload_command, "commonLocal.InitLanguageDict( false, false );", "interactive reloadLanguage preserves current sys_lang")
    require(reload_command, "fileSystem->SetIsFileLoadingAllowed( wasFileLoadingAllowed );", "interactive reloadLanguage restores file-loading flag")
    reject(reload_command, "StartupVariable", "interactive reloadLanguage should not replay launch sys_lang")

    require(init_game, "const bool allowStartupLanguageAutoSelect = sysDetect && !Common_HasStartupVariable( \"sys_lang\" );", "first-run language auto-select gate")
    require(init_game, "InitLanguageDict( true, allowStartupLanguageAutoSelect );", "early startup language load")
    require(init_game, "exec autoexec.cfg", "startup autoexec execution")
    require(init_game, "cmdSystem->ExecuteCommandBuffer();", "startup cfg command execution")
    require(init_game, "StartupVariable( NULL, false );", "startup command-line cvar reapply")
    require(init_game, "const bool wasFileLoadingAllowed = fileSystem->GetIsFileLoadingAllowed();", "startup final language reload preserves file-loading flag")
    require(init_game, "fileSystem->SetIsFileLoadingAllowed( true );", "startup final language reload enables file loading")
    require(init_game, "InitLanguageDict( false, false );", "settled startup language reload")
    require(init_game, "fileSystem->SetIsFileLoadingAllowed( wasFileLoadingAllowed );", "startup final language reload restores file-loading flag")
    require(init_game, "repairedUnsetMachineSpec || startupLanguageAutoSelected", "auto-selected startup language persists to config")
    reject(
        init_game,
        'cmdSystem->BufferCommandText( CMD_EXEC_APPEND, "reloadLanguage\\n" );',
        "startup language reload should happen after command-line reapply",
    )
    require_order(init_game, "InitLanguageDict( true, allowStartupLanguageAutoSelect );", "exec autoexec.cfg", "early language load before cfg files")
    require_order(init_game, "exec autoexec.cfg", "// run cfg execution\n\tcmdSystem->ExecuteCommandBuffer();", "cfg files before execution")
    require_order(init_game, "// run cfg execution\n\tcmdSystem->ExecuteCommandBuffer();", "StartupVariable( NULL, false );", "cfg execution before command-line reapply")

    # An installer's q4base/autoexec.cfg must not replace the saved Settings language (#199).
    retail_file = function_body(source, "static bool Common_IsRetailGameDirFile( const char *relativePath ) {")
    require(retail_file, "fileSystem->OpenFileRead( relativePath );", "retail autoexec lookup uses the normal search order")
    require(retail_file, "file->GetFullPath();", "retail autoexec origin from the opened file")
    require(retail_file, "directory.StripFilename();", "retail autoexec directory")
    require(retail_file, "directory.StripPath();", "retail autoexec directory name")
    require(retail_file, "directory.Icmp( BASE_GAMEDIR ) == 0", "only loose files in the retail game directory")
    require(
        init_game,
        'const bool keepSavedLanguage = !sysDetect && !SafeMode() && Common_IsRetailGameDirFile( "autoexec.cfg" );',
        "saved language kept only over an installer autoexec once a config exists",
    )
    require(init_game, 'savedLanguage = cvarSystem->GetCVarString( "sys_lang" );', "saved language sampled after the config")
    require(init_game, 'cvarSystem->SetCVarString( "sys_lang", savedLanguage.c_str() );', "saved language restored after the installer autoexec")
    require_order(init_game, "exec \" CONFIG_FILE", 'savedLanguage = cvarSystem->GetCVarString( "sys_lang" );', "config executed before sampling")
    require_order(init_game, 'savedLanguage = cvarSystem->GetCVarString( "sys_lang" );', "exec autoexec.cfg", "sampled before autoexec")
    require_order(init_game, "exec autoexec.cfg", 'cvarSystem->SetCVarString( "sys_lang", savedLanguage.c_str() );', "restored after autoexec")
    require_order(
        init_game,
        'cvarSystem->SetCVarString( "sys_lang", savedLanguage.c_str() );',
        "StartupVariable( NULL, false );",
        "+set sys_lang still wins over the saved language",
    )
    require_order(init_game, "StartupVariable( NULL, false );", "InitLanguageDict( false, false );", "command-line reapply before final language reload")
    require_order(init_game, "fileSystem->SetIsFileLoadingAllowed( true );", "InitLanguageDict( false, false );", "file loading enabled before final language reload")
    require_order(init_game, "InitLanguageDict( false, false );", "fileSystem->SetIsFileLoadingAllowed( wasFileLoadingAllowed );", "file-loading flag restored after final language reload")


def validate_config_filename_migration_contract() -> None:
    source = read("src/framework/Common.cpp")
    licensee = read("src/framework/licensee.h")
    exact_name = function_body(
        source,
        "static bool openPREY_SavePathHasExactFilename( const char *relativeFilename ) {",
    )
    exec_config = function_body(
        source,
        "static bool openPREY_ExecConfigFromSavePath( const char *relativeFilename ) {",
    )
    normalize_case = function_body(
        source,
        "static bool openPREY_NormalizeConfigFilenameCase( const char *loadedFilename ) {",
    )
    init_game = function_body(source, "void idCommonLocal::InitGame( void ) {")

    require(licensee, '"openPREYConfig.cfg"', "canonical config filename")
    require(licensee, '"OpenPREYConfig.cfg"', "interim config filename")
    require(licensee, '"OpenPreyConfig.cfg"', "legacy config filename")
    require(exact_name, "Sys_ListFiles( directory.c_str(), \"\", entries )", "case-exact savepath probe")
    require(exact_name, "idStr::Cmp( entries[i].c_str(), filename.c_str() ) == 0", "case-sensitive filename match")
    require(exec_config, "openPREY_SavePathHasExactFilename( relativeFilename )", "config execution case guard")
    require(normalize_case, "rename( loadedOSPath.c_str(), temporaryOSPath.c_str() )", "case-only migration first rename")
    require(normalize_case, "rename( temporaryOSPath.c_str(), canonicalOSPath.c_str() )", "case-only migration canonical rename")
    require(normalize_case, "rename( temporaryOSPath.c_str(), loadedOSPath.c_str() )", "failed migration rollback")
    require(init_game, "legacyConfigNameToMigrate = INTERIM_CONFIG_FILE;", "interim config migration selection")
    require(init_game, "legacyConfigNameToMigrate = LEGACY_CONFIG_FILE;", "legacy config migration selection")
    require(init_game, "openPREY_NormalizeConfigFilenameCase( legacyConfigNameToMigrate );", "runtime filename normalization")
    require_order(
        init_game,
        "cmdSystem->ExecuteCommandBuffer();",
        "openPREY_NormalizeConfigFilenameCase( legacyConfigNameToMigrate );",
        "legacy config executes before its filename is normalized",
    )
    require_order(
        init_game,
        "openPREY_NormalizeConfigFilenameCase( legacyConfigNameToMigrate );",
        "WriteConfigToFile( CONFIG_FILE );",
        "filename normalization precedes canonical config rewrite",
    )


def validate_language_media_diagnostic() -> None:
    source = read("src/framework/FileSystem.cpp")
    startup = function_body(source, "void idFileSystemLocal::Startup( void ) {")
    parser = function_body(
        source,
        "static bool FS_ParseLanguagePackName( const char *pakFilename, idStr &language, bool allowPatchArchives = true ) {",
    )
    base_media = function_body(source, "bool idFileSystemLocal::HasBaseLanguageMediaPack( void ) {")
    available_media = function_body(source, "void idFileSystemLocal::ListAvailableLanguagePacks( idStrList &languages ) {")

    require(
        available_media,
        "FS_ParseLanguagePackName( search->pack->pakFilename.c_str(), language )",
        "language selection continues to recognize numbered patch archives",
    )

    require(
        parser,
        "if ( !allowPatchArchives )",
        "numbered language-patch rejection",
    )
    require(
        base_media,
        "FS_ParseLanguagePackName( search->pack->pakFilename.c_str(), language, false )",
        "base language-media discovery excludes patch archives",
    )
    require(
        startup,
        "if ( !HasBaseLanguageMediaPack() )",
        "missing base language-media guard",
    )
    require(
        startup,
        "No recognized base Quake 4 language media archive (zpak_<language>.pk4, without a numeric suffix)",
        "actionable language-media warning",
    )
    require(
        startup,
        "character dialogue will be incomplete or silent",
        "language-media warning symptom",
    )
    require(
        startup,
        "Numbered patch archives such as zpak_english_01.pk4 do not replace the base archive",
        "patch-only install guidance",
    )
    require_regex(
        startup,
        r"if\s*\(\s*fs_validateOfficialPaks\.GetBool\(\)\s*\)\s*\{[\s\S]*"
        r"#ifndef\s+ID_DEDICATED[\s\S]*"
        r"HasBaseLanguageMediaPack\(\)[\s\S]*"
        r"#endif[\s\S]*\n\s*\}",
        "official-media and client-only warning gates",
    )
    require_order(
        startup,
        "ValidateRequiredOfficialPaks( validationErrors )",
        "HasBaseLanguageMediaPack()",
        "required core validation before optional language-media diagnostic",
    )


def validate_ci_smoke() -> None:
    push = read(".github/workflows/push-verification.yml")
    commit = read(".github/workflows/commit-validation.yml")
    runner = read("tools/validation/openq4_validate.py")

    for source, context in (
        (push, "push verification workflow"),
        (commit, "commit validation workflow"),
        (runner, "validation runner"),
    ):
        require(source, "startup_language_override.py", context)


def main() -> None:
    validate_language_reload_contract()
    validate_config_filename_migration_contract()
    validate_language_media_diagnostic()
    validate_ci_smoke()
    print("startup_language_override: ok")


if __name__ == "__main__":
    main()
