#!/usr/bin/env python3
"""Pin that the ARB light interaction programs load with a zero floor on their colour.

The stock interaction programs never saturate N.L. Retail's RGBA8 framebuffer
clamped the negative colour a light behind a surface writes; openQ4's RGBA16F
scene target keeps it, so without the floor that light subtracts (q4xctf6's
green cryo liquid turned magenta with SSAO on). The rewrite lives in
src/renderer/ARBColorZeroFloor.h, and tools/tests/native/ARBColorZeroFloorTest.cpp
checks what it computes. This contract pins the engine side: which programs get
the floor, that R_LoadARBProgram submits the rewrite and falls back to the
shipped text, and that the header still compiles inside the engine, where
idlib's Str.h turns several C string functions into errors.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


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


def require_ordered(text: str, needles: tuple[str, ...], context: str) -> None:
    position = 0
    for needle in needles:
        found = text.find(needle, position)
        if found < 0:
            raise AssertionError(f"{context}: missing {needle!r} after offset {position}")
        position = found + len(needle)


def strip_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.S)
    return re.sub(r"//[^\n]*", " ", source)


def idlib_banned_functions() -> list[str]:
    """The C library names Str.h redefines so that engine code cannot call them."""
    header = read("src/idlib/Str.h")
    start = header.find("these library functions should not be used")
    if start < 0:
        raise AssertionError("src/idlib/Str.h: the banned-function block moved; update this contract")
    names = []
    for line in header[start:].splitlines()[1:]:
        match = re.match(r"#define\s+(\w+)\s+(use_idStr_\w+|idStr::\w+)", line.strip())
        if match is None:
            break
        names.append(match.group(1))
    if "strncmp" not in names or "strcmp" not in names:
        raise AssertionError(f"src/idlib/Str.h: expected strcmp and strncmp in the banned block, found {names}")
    return names


def validate_header() -> None:
    header = read("src/renderer/ARBColorZeroFloor.h")
    code = strip_comments(header)
    for name in idlib_banned_functions():
        if re.search(rf"\b{re.escape(name)}\s*\(", code):
            raise AssertionError(
                f"ARBColorZeroFloor.h calls {name}(), which idlib's Str.h redefines inside the engine"
            )
    # The native test compiles the header on its own, so it must not need idlib.
    for needle in ('#include "../idlib', '#include "idlib', "idStr", "idList"):
        forbid(code, needle, "ARBColorZeroFloor.h stays idlib-free")
    for needle in (
        "inline rewriteResult_t RewriteWithZeroFloor( const char *program, char *out, std::size_t outSize )",
        "inline std::size_t RewriteBufferSize( const char *program )",
        'writer.Append( ", 0.0;" );',
    ):
        require(header, needle, "ARBColorZeroFloor.h")


def validate_engine_wiring() -> None:
    source = read("src/renderer/draw_arb2.cpp")
    require(source, '#include "ARBColorZeroFloor.h"', "draw_arb2.cpp")

    needs = function_body(source, "static bool RB_ARBProgramNeedsColorZeroFloor( const progDef_t &prog )")
    for needle in (
        "prog.target == GL_FRAGMENT_PROGRAM_ARB",
        "prog.ident == FPROG_INTERACTION",
        "prog.ident == FPROG_SIMPLE_INTERACTION",
        "prog.ident == FPROG_TEST",
    ):
        require(needs, needle, "RB_ARBProgramNeedsColorZeroFloor covers every interaction fragment program")

    load = function_body(source, "void R_LoadARBProgram( int progIndex )")
    require_ordered(
        load,
        (
            "end[3] = 0;",
            "if ( RB_ARBProgramNeedsColorZeroFloor( prog ) ) {",
            "oq4arbfloor::RewriteBufferSize( start )",
            "oq4arbfloor::RewriteWithZeroFloor( start,",
            "programText = zeroFloorProgram.Ptr();",
            "glProgramStringARB( prog.target, GL_PROGRAM_FORMAT_ASCII_ARB,",
            "(unsigned char *)programText );",
            "if ( programText != start && ( err == GL_INVALID_OPERATION || ofs != -1 ) ) {",
            "programText = start;",
            "glProgramStringARB( prog.target, GL_PROGRAM_FORMAT_ASCII_ARB,",
            "if ( err == GL_INVALID_OPERATION ) {",
            "prog.valid = true;",
        ),
        "R_LoadARBProgram submits the floored program and falls back to the shipped text",
    )
    forbid(load, "(unsigned char *)start", "R_LoadARBProgram must submit programText, not the raw program")
    require(load, "programText + ofs", "R_LoadARBProgram reports error offsets into the text it submitted")
    forbid(load, "start + ofs", "R_LoadARBProgram reports error offsets into the text it submitted")


def validate_registration() -> None:
    meson = read("meson.build")
    native_block = meson[meson.find("if get_option('build_native_tests')"):]
    native_block = native_block[: native_block.find("\nendif")]
    require(native_block, "'tools/tests/native/ARBColorZeroFloorTest.cpp'", "meson.build native tests")
    require(native_block, "'openq4-arb-color-zero-floor'", "meson.build native tests")

    validator = read("tools/validation/openq4_validate.py")
    require(validator, '"arb_color_zero_floor_contract.py"', "openq4_validate.py")


def main() -> None:
    validate_header()
    validate_engine_wiring()
    validate_registration()


if __name__ == "__main__":
    main()
