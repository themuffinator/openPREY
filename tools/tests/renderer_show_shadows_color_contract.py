#!/usr/bin/env python3
"""Pin that OpenGL's r_showShadows draws the stencil shadow volumes in color.

RB_T_Shadow picks a color for each volume, but the stock stencil shadow vertex
programs (glprogs/shadow.vp and the md5rshadow family) write only
result.position. While one is bound, the primary color that reaches the
fragment stage is undefined, and on NVIDIA it is black. Modes 1 and 3 drew black
lines, and the additive mode 2 drew nothing at all. RB_StencilShadowPass
therefore binds a fragment program compiled into the renderer whenever
r_showShadows is set, and RB_T_Shadow uploads each volume's color to its
program.local[0], so the color no longer depends on which vertex path drew the
volume. The ordinary stencil pass never binds it.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


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


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text)


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


def validate_program() -> None:
    source = read("src/renderer/draw_arb2.cpp")

    start = source.find("static const char arb2StencilShadowDebugProgram[] =")
    if start < 0:
        raise AssertionError("draw_arb2.cpp: missing the r_showShadows fragment program text")
    program = source[start : source.find(";\n", source.find('"END', start)) + 1]
    require_ordered(
        program,
        (r'"!!ARBfp1.0\n"', r'"MOV result.color, program.local[0];\n"', r'"END\n"'),
        "the r_showShadows program writes the uploaded color",
    )
    # Reading any fragment input would tie the color to the vertex program again.
    forbid(program, "fragment.", "the r_showShadows program reads no vertex-stage output")

    # Material programs take PROG_USER + index for index < MAX_GLPROGS, and the
    # retail fixed ids sit below PROG_USER; the built-in id must clear both.
    require(
        source,
        "static const GLuint\tFPROG_STENCIL_SHADOW_DEBUG = PROG_USER + MAX_GLPROGS;",
        "r_showShadows program id",
    )
    require(source, "prog.ident = PROG_USER + progIndex;", "dynamic ARB program ids")
    require(
        source,
        '{ GL_FRAGMENT_PROGRAM_ARB, FPROG_STENCIL_SHADOW_DEBUG, "stencilShadowDebug.fp", '
        "arb2StencilShadowDebugProgram },",
        "ARB program table",
    )

    load = function_body(source, "void R_LoadARBProgram( int progIndex )")
    require_ordered(
        load,
        (
            'idStr\tfullPath = ( prog.builtinText != NULL ) ? "builtin/" : "glprogs/";',
            "const char *programSource = prog.builtinText;",
            "if ( programSource == NULL ) {",
            "fileSystem->ReadFile( fullPath.c_str(), (void **)&fileBuffer, NULL );",
            "programSource = fileBuffer;",
            "memcpy( programBuffer.Ptr(), programSource, programLength + 1 );",
            "if ( fileBuffer != NULL ) {",
            "fileSystem->FreeFile( fileBuffer );",
            "glProgramStringARB( prog.target, GL_PROGRAM_FORMAT_ASCII_ARB,",
        ),
        "R_LoadARBProgram compiles built-in program text without reading glprogs/",
    )
    path = function_body(source, "static void RB_SetARBProgramPath( progDef_t &prog )")
    require(path, '( prog.builtinText != NULL ) ? "builtin/" : "glprogs/"', "reported path of built-in programs")

    bind = function_body(source, "bool RB_ARB2_BindStencilShadowDebugProgram( void )")
    require_ordered(
        bind,
        (
            "if ( !R_BindARBProgram( GL_FRAGMENT_PROGRAM_ARB, FPROG_STENCIL_SHADOW_DEBUG,",
            "return false;",
            "glEnable( GL_FRAGMENT_PROGRAM_ARB );",
            "return true;",
        ),
        "the r_showShadows program is enabled only after it binds",
    )
    if bind.count("glEnable(") != 1:
        raise AssertionError("RB_ARB2_BindStencilShadowDebugProgram must enable the program exactly once, after binding")
    require(
        read("src/renderer/tr_local.h"),
        "bool\tRB_ARB2_BindStencilShadowDebugProgram( void );",
        "tr_local.h declaration",
    )


def validate_shadow_pass() -> None:
    source = read("src/renderer/draw_common.cpp")

    shadow_pass = function_body(source, "void RB_StencilShadowPass( const drawSurf_t *drawSurfs )")
    require(
        compact(shadow_pass),
        "rb_shadowDebugColorProgramThisPass = r_showShadows.GetInteger() != 0 "
        "&& RB_ARB2_BindStencilShadowDebugProgram();",
        "RB_StencilShadowPass binds the color program only for r_showShadows",
    )
    require_ordered(
        shadow_pass,
        (
            "RB_ARB2_BindStencilShadowDebugProgram()",
            "RB_RenderDrawSurfChainWithFunction( drawSurfs, RB_T_Shadow );",
            "if ( rb_shadowDebugColorProgramThisPass ) {",
            "glDisable( GL_FRAGMENT_PROGRAM_ARB );",
            "rb_shadowDebugColorProgramThisPass = false;",
        ),
        "RB_StencilShadowPass disables the color program after the volumes",
    )

    shadow = function_body(source, "static void RB_T_Shadow( const drawSurf_t *surf )")
    debug = shadow[shadow.find("if ( r_showShadows.GetInteger() ) {") :]
    debug = debug[: debug.find("return;") + len("return;")]
    require_ordered(
        debug,
        (
            "if ( r_showShadows.GetInteger() ) {",
            "color /= backEnd.overBright;",
            "glColor3fv( color.ToFloatPtr() );",
            "if ( rb_shadowDebugColorProgramThisPass ) {",
            "glProgramLocalParameter4fvARB( GL_FRAGMENT_PROGRAM_ARB, 0, programColor.ToFloatPtr() );",
            "RB_DrawShadowElementsWithCounters( surf, numIndexes );",
            "return;",
        ),
        "RB_T_Shadow uploads each volume's color before drawing it",
    )
    forbid(shadow, "RB_ARB2_BindStencilShadowDebugProgram", "RB_T_Shadow leaves binding to the pass")


def validate_registration() -> None:
    validator = read("tools/validation/openq4_validate.py")
    require(validator, '"renderer_show_shadows_color_contract.py"', "openq4_validate.py")
    for workflow in (".github/workflows/commit-validation.yml", ".github/workflows/push-verification.yml"):
        require(
            read(workflow),
            "python tools/tests/renderer_show_shadows_color_contract.py",
            workflow,
        )


def main() -> None:
    validate_program()
    validate_shadow_pass()
    validate_registration()


if __name__ == "__main__":
    main()
