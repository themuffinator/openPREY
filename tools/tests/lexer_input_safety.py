#!/usr/bin/env python3
"""Regression checks for deterministic tokens and fail-closed lexer file reads."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GAME_ROOT = Path(os.environ.get("OPENQ4_GAMELIBS_REPO", ROOT)).resolve()


def read(path: Path) -> str:
    # The SDK lexer intentionally retains Windows-1252 inverted punctuation
    # literals. This single-byte decoder also preserves every ASCII contract
    # checked below in the UTF-8 engine copy.
    return path.read_text(encoding="windows-1252")


def section(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin + len(start))
    return source[begin:finish]


def validate_repository(repo: Path) -> tuple[str, str]:
    token_path = repo / "src" / "idlib" / "Token.h"
    lexer_path = repo / "src" / "idlib" / "Lexer.cpp"
    if not token_path.is_file() or not lexer_path.is_file():
        raise AssertionError(f"lexer inputs are missing from {repo}")

    token_source = read(token_path)
    constructor = section(
        token_source,
        "ID_INLINE idToken::idToken( void ) :",
        "ID_INLINE idToken::idToken( const idToken *token )",
    )
    for initializer in (
        "type( 0 )",
        "subtype( 0 )",
        "line( 0 )",
        "linesCrossed( 0 )",
        "flags( 0 )",
        "intvalue( 0 )",
        "floatvalue( 0.0 )",
        "whiteSpaceStart_p( NULL )",
        "whiteSpaceEnd_p( NULL )",
        "next( NULL )",
    ):
        if initializer not in constructor:
            raise AssertionError(f"{token_path} does not initialize {initializer}")
    whitespace_guard = (
        "whiteSpaceStart_p != NULL && whiteSpaceEnd_p != NULL && "
        "whiteSpaceEnd_p > whiteSpaceStart_p"
    )
    if whitespace_guard not in token_source:
        raise AssertionError(f"{token_path} compares token whitespace pointers without null guards")

    lexer_source = read(lexer_path)
    load_file = section(lexer_source, "int idLexer::LoadFile( const char *filename, bool OSPath )", "int idLexer::LoadMemory(")
    for guard in (
        "length < 0 || length == idMath::INT_MAX",
        "idLib::fileSystem->CloseFile( fp );",
        "const int bytesRead = fp->Read( buf, length );",
        "if ( bytesRead != length )",
        "Mem_Free( buf );",
        "buf[length] = '\\0';",
    ):
        if guard not in load_file:
            raise AssertionError(f"{lexer_path} is missing file-read guard {guard!r}")
    if load_file.index("length < 0 || length == idMath::INT_MAX") > load_file.index("Mem_Alloc( length + 1"):
        raise AssertionError(f"{lexer_path} validates the length after allocation arithmetic")
    if load_file.index("if ( bytesRead != length )") > load_file.index("buf[length] = '\\0';"):
        raise AssertionError(f"{lexer_path} terminates a buffer before validating the complete read")
    allocation_failure = section(load_file, "if( !buf )", "// RAVEN END")
    if allocation_failure.index("CloseFile( fp )") > allocation_failure.index("FatalError"):
        raise AssertionError(f"{lexer_path} leaks its file handle on allocation failure")
    if "FatalError( \"Memory system failure : out of memory\" );\n\t}" in allocation_failure:
        raise AssertionError(f"{lexer_path} can continue after a returning fatal-error callback")
    return constructor, load_file


def main() -> None:
    engine_contract = validate_repository(ROOT)
    game_contract = validate_repository(GAME_ROOT)
    if engine_contract != game_contract:
        raise AssertionError("engine and GameLib lexer/token safety contracts diverged")

    validation = (ROOT / "tools" / "validation" / "openq4_validate.py").read_text(encoding="utf-8")
    if "lexer_input_safety.py" not in validation:
        raise AssertionError("lexer input-safety regression is not wired into validation")
    print("lexer input safety: ok")


if __name__ == "__main__":
    main()
