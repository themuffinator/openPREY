#!/usr/bin/env python3
"""Custom crosshair picker: the production lookup and the menu wiring that reaches it.

The Game Options preview row draws gui::crossImage. Clicking it sends
"chooseCrosshair 1" and right-clicking it "chooseCrosshair -1"; the retail
engine answered by stepping g_crosshairCustomFile through the mtr_crosshair
keys of the multiplayer player def, wrapping at both ends, and it published the
current entry whenever it built the main menu. This compiles the production
MainMenuFindCrosshair against the stock list and pins the rest of the path: the
menu build publishes the current entry, the command handler consumes its step,
and a right-click press runs onBackAction. No window, input device or running
game is used. A C++ compiler is required.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TEST_PATH = "tools/tests/crosshair_picker_contract.py"
SESSION_MENU = "src/framework/Session_menu.cpp"
WINDOW = "src/ui/Window.cpp"
GAME_GUI = "content/baseoq4/pak0/guis/menu/settings/game.gui"
GAME_HOVERS_GUI = "content/baseoq4/pak0/guis/menu/settings/game_hovers.gui"

# player_marine_mp_ui's mtr_crosshair1..20, in file order (def/player.def in the
# retail paks, not in this repository).
STOCK_CROSSHAIRS = [
    "gfx/guis/crosshairs/crosshair_" + name + ".tga"
    for name in (
        "blaster", "grenadelauncher", "lightninggun", "machinegun", "nailgun", "railgun",
        "rocketlauncher", "shotgun", "q3_1", "q3_2", "q3_3", "q3_4", "q3_5", "q3_6", "q3_7",
        "q3_8", "q3_9", "q3_10", "gauntlet", "napalm",
    )
]

HARNESS = r'''
#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

static int CompareNoCase( const char *a, const char *b, size_t n ) {
    for ( size_t i = 0; i < n; ++i ) {
        const int ca = std::tolower( static_cast<unsigned char>( a[i] ) );
        const int cb = std::tolower( static_cast<unsigned char>( b[i] ) );
        if ( ca != cb || ca == 0 ) {
            return ca - cb;
        }
    }
    return 0;
}

struct idStr : std::string {
    idStr( const char *text ) : std::string( text ) {}
    int Icmp( const char *text ) const { return CompareNoCase( c_str(), text, size() + 1 ); }
};

struct idKeyValue {
    idStr key;
    idStr value;
    const idStr &GetKey() const { return key; }
    const idStr &GetValue() const { return value; }
};

// Mirrors idDict::MatchPrefix: the next key, in insertion order, that starts
// with the prefix (case-insensitive).
struct idDict {
    std::vector<idKeyValue> args;
    void Set( const char *key, const char *value ) { args.push_back( idKeyValue{ key, value } ); }
    const idKeyValue *MatchPrefix( const char *prefix, const idKeyValue *lastMatch = NULL ) const {
        const size_t len = std::strlen( prefix );
        size_t start = 0;
        if ( lastMatch != NULL ) {
            start = static_cast<size_t>( lastMatch - args.data() ) + 1;
        }
        for ( size_t i = start; i < args.size(); ++i ) {
            if ( CompareNoCase( args[i].GetKey().c_str(), prefix, len ) == 0 ) {
                return &args[i];
            }
        }
        return NULL;
    }
};
'''

TESTS = r'''
static int failures = 0;

static void Expect( const idKeyValue *actual, const char *expected, const char *what ) {
    const char *got = actual != NULL ? actual->GetValue().c_str() : "(null)";
    if ( expected == NULL ? actual != NULL : ( actual == NULL || std::strcmp( got, expected ) != 0 ) ) {
        std::printf( "FAIL %s: expected %s, got %s\n", what, expected != NULL ? expected : "(null)", got );
        ++failures;
    }
}

int main() {
    static const char *const stock[] = { STOCK_LIST };
    const int count = static_cast<int>( sizeof( stock ) / sizeof( stock[0] ) );

    idDict dict;
    dict.Set( "joint_head", "chest" );
    dict.Set( "def_default_model", "model_player_marine" );
    for ( int i = 0; i < count; ++i ) {
        char key[32];
        std::snprintf( key, sizeof( key ), "mtr_crosshair%d", i + 1 );
        dict.Set( key, stock[i] );
    }
    dict.Set( "spawnclass", "idPlayer" );
    dict.Set( "model", "model_player_marine_ui" );

    for ( int i = 0; i < count; ++i ) {
        char what[96];
        std::snprintf( what, sizeof( what ), "entry %d, step 0", i + 1 );
        Expect( MainMenuFindCrosshair( dict, stock[i], 0 ), stock[i], what );
        std::snprintf( what, sizeof( what ), "entry %d, forward", i + 1 );
        Expect( MainMenuFindCrosshair( dict, stock[i], 1 ), stock[( i + 1 ) % count], what );
        std::snprintf( what, sizeof( what ), "entry %d, back", i + 1 );
        Expect( MainMenuFindCrosshair( dict, stock[i], -1 ), stock[( i + count - 1 ) % count], what );
    }

    // The cvar's default names no entry: the menu build shows the first, and a
    // step goes to the first or, backwards, the last.
    Expect( MainMenuFindCrosshair( dict, "0", 0 ), stock[0], "default, step 0" );
    Expect( MainMenuFindCrosshair( dict, "0", 1 ), stock[0], "default, forward" );
    Expect( MainMenuFindCrosshair( dict, "0", -1 ), stock[count - 1], "default, back" );
    Expect( MainMenuFindCrosshair( dict, "", 1 ), stock[0], "empty, forward" );

    // File names compare as the file system does, ignoring case.
    Expect( MainMenuFindCrosshair( dict, "GFX/GUIS/CROSSHAIRS/CROSSHAIR_Q3_6.TGA", 1 ), stock[14], "upper case, forward" );

    // A def without the keys yields nothing to publish.
    idDict empty;
    empty.Set( "model", "model_player_marine_ui" );
    Expect( MainMenuFindCrosshair( empty, stock[0], 0 ), NULL, "no keys, step 0" );
    Expect( MainMenuFindCrosshair( empty, stock[0], -1 ), NULL, "no keys, back" );

    if ( failures != 0 ) {
        std::printf( "%d crosshair picker check(s) failed\n", failures );
        return 1;
    }
    std::printf( "crosshair picker: %d entries step and wrap both ways\n", count );
    return 0;
}
'''


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def require_order(body: str, needles: tuple[str, ...], context: str) -> None:
    cursor = -1
    for needle in needles:
        index = body.find(needle, cursor + 1)
        if index < 0:
            raise AssertionError(f"Missing ordered token {needle!r} in {context}")
        cursor = index


def extract(source: str, signature: str, context: str) -> str:
    start = source.find(signature)
    if start < 0:
        raise AssertionError(f"Missing {signature!r} in {context}")
    opening = source.index("{", start + len(signature))
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Unterminated {signature!r} in {context}")


def window_def(source: str, name: str, context: str) -> str:
    match = re.search(r"windowDef\s+" + re.escape(name) + r"\s*\{", source)
    if match is None:
        raise AssertionError(f"Missing windowDef {name} in {context}")
    return extract(source[match.start() :], "windowDef", context)


def check_session_menu() -> str:
    source = read(SESSION_MENU).replace("\r\n", "\n")
    lookup = extract(source, "static const idDict *MainMenuCrosshairDict( void )", SESSION_MENU)
    # Resolved without media caching, as retail did; the UI def first.
    require_order(
        lookup,
        (
            'FindType( DECL_ENTITYDEF, "player_marine_mp_ui", false, true )',
            'FindType( DECL_ENTITYDEF, "player_marine_mp", false, true )',
        ),
        "MainMenuCrosshairDict",
    )

    publish = extract(source, "static void MainMenuPublishCrosshair( idUserInterface *gui, int step )", SESSION_MENU)
    require_order(
        publish,
        (
            'MainMenuFindCrosshair( *dict, cvarSystem->GetCVarString( "g_crosshairCustomFile" ), step )',
            'gui->SetStateString( "crossImage", materialName );',
            "material->SetSort( SS_GUI );",
            'cvarSystem->SetCVarString( "g_crosshairCustomFile", materialName );',
        ),
        "MainMenuPublishCrosshair",
    )

    gui_vars = extract(source, "void idSessionLocal::SetMainMenuGuiVars( bool refreshCatalogs )", SESSION_MENU)
    require(gui_vars, "MainMenuPublishCrosshair( guiMainMenu, 0 );", "SetMainMenuGuiVars (every menu build)")

    commands = extract(source, "void idSessionLocal::HandleMainMenuCommands( const char *menuCommand )", SESSION_MENU)
    require_order(
        commands,
        (
            'if ( !idStr::Icmp( cmd, "chooseCrosshair" ) ) {',
            "int step = 1;",
            'if ( icmd < args.Argc() && idStr::Cmp( args.Argv( icmd ), ";" ) ) {',
            "step = atoi( args.Argv( icmd++ ) ) >= 1 ? 1 : -1;",
            "MainMenuPublishCrosshair( guiMainMenu, step );",
            "continue;",
            "game->HandleMainMenuCommands( cmd, guiActive );",
        ),
        "HandleMainMenuCommands",
    )

    prefix = 'static const char *MAINMENU_CROSSHAIR_PREFIX = "mtr_crosshair";'
    require(source, prefix, SESSION_MENU)
    finder = extract(
        source,
        "static const idKeyValue *MainMenuFindCrosshair( const idDict &dict, const char *current, int step )",
        SESSION_MENU,
    )
    return prefix + "\n" + finder + "\n"


def check_window() -> None:
    source = read(WINDOW).replace("\r\n", "\n")
    handler = extract(source, "const char *idWindow::HandleEvent(const sysEvent_t *event, bool *updateVisuals)", WINDOW)
    start = handler.find("} else if (event->evValue == K_MOUSE2) {")
    end = handler.find("} else if (event->evValue == K_MOUSE3) {", start)
    if start < 0 or end < 0:
        raise AssertionError(f"Missing the K_MOUSE2 branch of idWindow::HandleEvent in {WINDOW}")
    # Retail runs script slot 3, onBackAction, on a right-click press.
    require_order(
        handler[start:end],
        (
            "child->HandleEvent(event, updateVisuals);",
            "if ( event->evValue2 && !actionDownRun ) {",
            "actionDownRun = RunScript( ON_BACKACTION );",
        ),
        "idWindow::HandleEvent right-click press",
    )


def check_guis() -> None:
    hovers = read(GAME_HOVERS_GUI).replace("\r\n", "\n")
    preview = window_def(hovers, "set_game_previewxhair_hover", GAME_HOVERS_GUI)
    require(extract(preview, "onAction", GAME_HOVERS_GUI), 'set "cmd" "chooseCrosshair" "1" ;', "preview onAction")
    require(extract(preview, "onBackAction", GAME_HOVERS_GUI), 'set "cmd" "chooseCrosshair" "-1" ;', "preview onBackAction")

    game = read(GAME_GUI).replace("\r\n", "\n")
    row = window_def(game, "set_game_previewxhair", GAME_GUI)
    for size in (16, 24, 32, 40, 48):
        preview_size = window_def(row, f"set_game_previewxhair_size_{size}", GAME_GUI)
        if re.search(r'background\s+"gui::crossImage"', preview_size) is None:
            raise AssertionError(f"Preview size {size} in {GAME_GUI} no longer draws gui::crossImage")


def run_lookup(finder: str) -> None:
    build = ROOT / ".tmp/crosshair-picker-contract"
    build.mkdir(parents=True, exist_ok=True)
    stock = ", ".join(f'"{path}"' for path in STOCK_CROSSHAIRS)
    cpp = build / "test.cpp"
    cpp.write_text(HARNESS + finder + TESTS.replace("STOCK_LIST", stock), encoding="utf-8")
    compiler = os.environ.get("CXX") or shutil.which("clang++") or shutil.which("g++") or shutil.which("cl")
    if not compiler:
        raise RuntimeError("Set CXX to a C++ compiler or run from a developer shell.")
    exe = build / ("test.exe" if os.name == "nt" else "test")
    if Path(compiler).stem.lower() == "cl":
        args = [compiler, "/nologo", "/EHsc", "/std:c++17", str(cpp), f"/Fe:{exe}", f"/Fo:{build}/"]
    else:
        args = [compiler, "-std=c++17", "-Wall", "-Wextra", str(cpp), "-o", str(exe)]
    subprocess.run(args, check=True, cwd=build)
    subprocess.run([str(exe)], check=True, cwd=build)


def check_ci_wiring() -> None:
    validator = read("tools/validation/openq4_validate.py")
    if validator.count("crosshair_picker_contract.py") != 1:
        raise AssertionError("Local validation must register the crosshair picker contract exactly once")
    for workflow_path in (".github/workflows/commit-validation.yml", ".github/workflows/push-verification.yml"):
        workflow = read(workflow_path)
        if workflow.count(TEST_PATH) != 2:
            raise AssertionError(f"{workflow_path} must compile and run {TEST_PATH}")
        require(workflow, f"python {TEST_PATH}", workflow_path)


def main() -> None:
    finder = check_session_menu()
    check_window()
    check_guis()
    check_ci_wiring()
    run_lookup(finder)
    print("crosshair_picker_contract: ok")


if __name__ == "__main__":
    main()
