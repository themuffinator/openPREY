#!/usr/bin/env python3
"""Pin the console completion wiring and check the popup cap against the name families.

tools/tests/native/ConsoleCompletionTest.cpp runs the matching rules in
src/framework/ConsoleCompletion.h. This contract pins that the engine actually
routes the popup through them, and that every name family still fits the cap.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GAME_LIBS_ROOT = Path(
    os.environ.get("OPENQ4_GAMELIBS_REPO", ROOT)
).resolve()
MAX_EDIT_LINE = 256
FUZZY_STATE_LIMIT = 64 * 1024

CVAR_NAME = re.compile(r'\bidCVar\s+[\w:]+\s*\(\s*"([^"]+)"')
COMMAND_NAME = re.compile(r'\bAddCommand\s*\(\s*"([^"]+)"')
SOURCE_SUFFIXES = {".cpp", ".h", ".inl", ".mm"}


def function_body(text: str, head: str) -> str:
    """Return the definition whose signature starts with head, skipping declarations."""
    match = re.search(re.escape(head) + r"[^;{}]*\{", text)
    if match is None:
        raise AssertionError(f"Missing definition of {head!r}")
    depth = 0
    for index in range(match.end() - 1, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[match.start() : index + 1]
    raise AssertionError(f"Unbalanced body for {head!r}")


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def require(text: str, needle: str, context: str) -> None:
    if needle not in text:
        raise AssertionError(f"{context}: missing {needle!r}")


def forbid(text: str, needle: str, context: str) -> None:
    if needle in text:
        raise AssertionError(f"{context}: still contains {needle!r}")


def header_constant(header: str, name: str) -> int:
    match = re.search(rf"constexpr int {name} = (\d+);", header)
    if match is None:
        raise AssertionError(f"ConsoleCompletion.h: missing constexpr {name}")
    return int(match.group(1))


def registered_names(tree: Path) -> set[str]:
    names: set[str] = set()
    for path in tree.rglob("*"):
        if path.suffix.lower() not in SOURCE_SUFFIXES or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
        names.update(name.lower() for name in CVAR_NAME.findall(text))
        names.update(name.lower() for name in COMMAND_NAME.findall(text))
    return names


def validate_cap(header: str) -> None:
    max_matches = header_constant(header, "MAX_MATCHES")
    max_fuzzy = header_constant(header, "MAX_FUZZY_MATCHES")

    trees = [ROOT / "src"]
    if (GAME_LIBS_ROOT / "src").is_dir():
        trees.append(GAME_LIBS_ROOT / "src")
    names: set[str] = set()
    for tree in trees:
        names |= registered_names(tree)
    if len(names) < 1000:
        raise AssertionError(f"only {len(names)} command and CVar names found; the name scan is broken")

    # Every name prefix selects a subset of the names sharing its first letter,
    # so if the largest first-letter group fits, typing any name prefix lists
    # every match. r_ is the family that grows (219 names in March 2026, 463 in
    # September).
    groups: dict[str, int] = {}
    for name in names:
        groups[name[0]] = groups.get(name[0], 0) + 1
    letter, largest = max(groups.items(), key=lambda item: item[1])
    family = sum(1 for name in names if name.startswith("r_"))
    if largest > max_matches:
        raise AssertionError(
            f"typing {letter!r} matches {largest} names but the console popup keeps "
            f"{max_matches}; raise oq4completion::MAX_MATCHES so every match is listed"
        )
    if family > max_matches:
        raise AssertionError(f"the r_ family ({family} names) no longer fits MAX_MATCHES ({max_matches})")

    # The fuzzy state lives on RefreshCompletionState's stack, one
    # MAX_EDIT_LINE-sized candidate per slot.
    fuzzy_state = max_fuzzy * (MAX_EDIT_LINE + 16)
    if not 0 < max_fuzzy <= max_matches or fuzzy_state > FUZZY_STATE_LIMIT:
        raise AssertionError(
            f"MAX_FUZZY_MATCHES {max_fuzzy} puts ~{fuzzy_state} bytes on the stack; keep it under "
            f"{FUZZY_STATE_LIMIT} bytes and at most MAX_MATCHES"
        )

    print(
        f"console_completion_contract: largest name group {letter!r}={largest}, r_={family}, "
        f"MAX_MATCHES={max_matches}, fuzzy state ~{fuzzy_state} bytes"
    )


def validate_edit_field() -> None:
    source = read("src/framework/EditField.cpp")
    require(source, '#include "ConsoleCompletion.h"', "EditField.cpp")

    query = function_body(source, "static int QueryCompletionInternal(")
    require(
        query,
        "oq4completion::BuildArgumentLinePrefix( normalizedCmd, globalAutoComplete.completionString",
        "QueryCompletionInternal",
    )
    forbid(query, "globalAutoComplete.completionString[0] = '\\0'", "QueryCompletionInternal")

    find_matches = function_body(source, "static void FindMatches( const char *s )")
    require(find_matches, "( prefixMatch || completionQueryCollectAll )", "FindMatches")


def validate_console() -> None:
    source = read("src/framework/Console.cpp")
    require(source, '#include "ConsoleCompletion.h"', "Console.cpp")
    for pattern, label in (
        (r"#define\s+CON_COMPLETION_MAX_MATCHES\s+oq4completion::MAX_MATCHES\b", "the popup cap"),
        (r"#define\s+CON_COMPLETION_MAX_FUZZY_MATCHES\s+oq4completion::MAX_FUZZY_MATCHES\b", "the fuzzy cap"),
        (r"consoleCompletionCandidate_t\s+matches\[CON_COMPLETION_MAX_FUZZY_MATCHES\];", "the fuzzy state size"),
        (r"oq4completion::CandidateIndex<CON_COMPLETION_MAX_MATCHES>\s+completionMatchIndex;", "the candidate index"),
    ):
        if re.search(pattern, source) is None:
            raise AssertionError(f"Console.cpp: {label} is not taken from ConsoleCompletion.h")

    collect = function_body(source, "bool idConsoleLocal::CollectCompletionMatch( const char *match )")
    require(collect, "completionMatchIndex.Add( completionMatches, completionCount, token )", "CollectCompletionMatch")
    forbid(collect, "for ( int i = 0; i < completionCount; ++i )", "CollectCompletionMatch")

    refresh = function_body(source, "void idConsoleLocal::RefreshCompletionState( void )")
    clear = refresh.find("completionMatchIndex.Clear();")
    query = refresh.find("idEditField::QueryCompletionMatches(")
    if clear < 0 or query < 0 or clear > query:
        raise AssertionError("RefreshCompletionState: the candidate index must be cleared before each query")
    require(
        refresh,
        "oq4completion::AllowsFuzzyFallback( completionReplaceArgIndex, currentToken )",
        "RefreshCompletionState",
    )
    require(refresh, "fuzzyState.argIndex = completionReplaceArgIndex;", "RefreshCompletionState")
    require(refresh, "completionPopupChars = MeasureCompletionPopupChars();", "RefreshCompletionState")

    fuzzy = function_body(source, "static bool Con_CollectFuzzyCompletionMatchCallback(")
    require(fuzzy, "Con_ExtractCompletionCandidateToken( match, state->argIndex", "the fuzzy callback")
    require(fuzzy, "state->count < CON_COMPLETION_MAX_FUZZY_MATCHES", "the fuzzy callback")

    extract = function_body(source, "bool idConsoleLocal::ExtractCompletionCandidateToken(")
    require(extract, "Con_ExtractCompletionCandidateToken( candidateLine, completionReplaceArgIndex", "ExtractCompletionCandidateToken")

    geometry = function_body(source, "bool idConsoleLocal::GetCompletionPopupGeometry(")
    require(geometry, "completionPopupChars", "GetCompletionPopupGeometry")
    forbid(geometry, "for ( int i = 0; i < completionCount; ++i )", "GetCompletionPopupGeometry")

    enter = function_body(source, "bool idConsoleLocal::EnterAcceptsCompletion( void )")
    require(enter, "!IsCurrentSegmentCompletionMatch( completionMatches[completionSelection] )", "EnterAcceptsCompletion")

    key_down = function_body(source, "void idConsoleLocal::KeyDownEvent( int key )")
    enter_branch = key_down[key_down.find("if ( key == K_ENTER || key == K_KP_ENTER )"):]
    if not enter_branch.startswith("if ( key == K_ENTER"):
        raise AssertionError("KeyDownEvent: missing the Enter branch")
    accepts = enter_branch.find("if ( EnterAcceptsCompletion() )")
    applies = enter_branch.find("ApplySelectedCompletion( 0 );")
    runs = enter_branch.find("cmdSystem->BufferCommandText( CMD_EXEC_APPEND, consoleField.GetBuffer() );")
    if not 0 <= accepts < applies < runs:
        raise AssertionError("KeyDownEvent: Enter must apply a completion only when EnterAcceptsCompletion() says so")

    input_key_down = function_body(source, "bool idConsoleLocal::InputKeyDownEvent( int key )")
    popup_enter = input_key_down[input_key_down.find("case K_KP_ENTER:"):]
    if not popup_enter.startswith("case K_KP_ENTER:") or not popup_enter.split("ApplySelectedCompletion( 0 );")[0].count(
        "EnterAcceptsCompletion()"
    ):
        raise AssertionError("InputKeyDownEvent: the popup's Enter case must defer to EnterAcceptsCompletion()")


def validate_registration() -> None:
    meson = read("meson.build")
    native_block = meson[meson.find("if get_option('build_native_tests')"):]
    native_block = native_block[: native_block.find("\nendif")]
    require(native_block, "'tools/tests/native/ConsoleCompletionTest.cpp'", "meson.build native tests")
    require(native_block, "'openq4-console-completion'", "meson.build native tests")

    validator = read("tools/validation/openq4_validate.py")
    require(validator, '"console_completion_contract.py"', "openq4_validate.py")


def main() -> None:
    header = read("src/framework/ConsoleCompletion.h")
    validate_edit_field()
    validate_console()
    validate_registration()
    validate_cap(header)


if __name__ == "__main__":
    main()
