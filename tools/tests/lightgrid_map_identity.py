#!/usr/bin/env python3
"""A baked light grid only lights the build of the map it was baked from.

A mod can ship its own build of a map under a stock name. The Awakening's mp/q4xdm13 has
10 areas where retail's has 14, and openQ4's pak1 carries a grid baked for retail's. The
pack loader refused that grid on its area count, but the text fallback from the same bake
then stopped the map load with a fatal ParseLightGridPoints error. A mod build with the
same area count took the stock grid and was lit from the wrong geometry.

SetupLightGrid now ignores a grid found lower in the game-directory stack than the map's
own .proc, which covers a build that even keeps the stock areas (the Awakening's
mp/q4xctf6). The loaders also recompute each area's layout with the helper the bake lays
grids out with and ignore a grid that does not fit, and text parse errors are no longer
fatal.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "renderer" / "RenderWorld_lightgrid.cpp"

HARNESS = r"""
#include <cmath>
#include <cstdio>

struct idMath {
	static float Ceil( float f ) { return std::ceil( f ); }
	static float Floor( float f ) { return std::floor( f ); }
	static int FtoiFast( float f ) { return static_cast<int>( f ); }
};
template<class T> static T Max( T a, T b ) { return a > b ? a : b; }

@ALIGN_AXIS@

static int failures = 0;
static void Expect( float lo, float hi, float center, float size, float origin, int count ) {
	float gotOrigin = -1.0f;
	int gotCount = -1;
	LightGrid_AlignAxis( lo, hi, center, size, gotOrigin, gotCount );
	if ( gotOrigin != origin || gotCount != count ) {
		std::printf( "LightGrid_AlignAxis( %g, %g, %g, %g ) = %g x%d, expected %g x%d\n",
			lo, hi, center, size, gotOrigin, gotCount, origin, count );
		failures++;
	}
}

int main() {
	Expect( -100.0f, 50.0f, -25.0f, 64.0f, -64.0f, 2 );          // probes at -64 and 0
	Expect( 0.0f, 128.0f, 64.0f, 64.0f, 0.0f, 3 );               // both ends on the lattice
	Expect( 10.0f, 20.0f, 15.0f, 64.0f, 0.0f, 1 );               // thinner than a cell: the multiple below the centre
	Expect( -20.0f, -10.0f, -15.0f, 64.0f, -64.0f, 1 );
	Expect( -1000.5f, 3000.25f, 999.875f, 80.0f, -960.0f, 50 );  // a cell size the bake grew by 16
	return failures ? 1 : 0;
}
"""


def fail(message: str) -> None:
    raise AssertionError(message)


def block(source: str, signature: str) -> str:
    """The text of a function, from its signature to its closing brace."""
    start = source.find(signature)
    if start < 0:
        fail(f"RenderWorld_lightgrid.cpp is missing {signature}")
    depth = 0
    for index in range(source.index("{", start), len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    fail(f"unbalanced braces after {signature}")
    return ""


def check_contract(source: str) -> str:
    align = block(source, "static void LightGrid_AlignAxis(")
    setup = block(source, "void LightGrid::SetupGrid(")
    if "LightGrid_AlignAxis(" not in setup or "idMath::Ceil" in setup:
        fail("SetupGrid must lay grids out with LightGrid_AlignAxis, the helper the loaders check against")
    fits = block(source, "static bool LightGrid_BakedForThisMap(")
    if "LightGrid_AlignAxis(" not in fits:
        fail("LightGrid_BakedForThisMap must recompute layouts with LightGrid_AlignAxis")
    pack = block(source, "bool idRenderWorldLocal::LoadLightGridPackFile(")
    if "LightGrid_BakedForThisMap( this )" not in pack:
        fail("the pack loader must refuse a grid baked for another build of the map")
    text = block(source, "bool idRenderWorldLocal::LoadLightGridFile(")
    for token in ("LEXFL_NOFATALERRORS", "src->HadError()", "LightGrid_BakedForThisMap( this )", "LightGrid_ClearAreas( this )"):
        if token not in text:
            fail(f"the text loader must ignore a grid it cannot use, not stop the map load ({token!r})")
    for name in ("ParseLightGridPoints", "ParseLightGridVisibility"):
        parse = block(source, f"bool idRenderWorldLocal::{name}(")
        if "areaIndex >= numPortalAreas ) {\n\t\treturn false;" not in parse:
            fail(f"{name} must report an area this map lacks as a mismatch, not an error")
    if "light-grid areas, but map has" in source:
        fail("a mod's own build of a map is not a fault; the loaders say so as a developer print")
    rank = block(source, "static int LightGrid_GameDirRank(")
    order = [rank.find(token) for token in ('"fs_game"', '"fs_game_base"', "OPENQ4_GAMEDIR", "dirs.Append( BASE_GAMEDIR )")]
    if -1 in order or order != sorted(order):
        fail("LightGrid_GameDirRank must rank game directories as the filesystem stacks them: fs_game, fs_game_base, openQ4, q4base")
    setup_world = block(source, "void idRenderWorldLocal::SetupLightGrid(")
    if "LightGrid_GameDirRank( procName )" not in setup_world:
        fail("SetupLightGrid must find which game directory the map's .proc comes from")
    for loader in ("LoadLightGridPackFile( filename )", "LoadLightGridFile( filename )"):
        if f"!LightGrid_LayeredBelowMap( filename, mapRank, mapName ) && {loader}" not in setup_world:
            fail(f"SetupLightGrid must not load a grid from below the map ({loader})")
    return align


def run_harness(align: str) -> None:
    compiler = shutil.which("clang++") or shutil.which("g++") or shutil.which("c++")
    if compiler is None:
        fail("no C++ compiler found for the LightGrid_AlignAxis harness")
    (ROOT / ".tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lightgrid-identity-", dir=ROOT / ".tmp") as work:
        cpp = Path(work) / "align_axis.cpp"
        exe = Path(work) / ("align_axis.exe" if sys.platform == "win32" else "align_axis")
        cpp.write_text(HARNESS.replace("@ALIGN_AXIS@", align), encoding="utf-8")
        built = subprocess.run([compiler, "-std=c++17", str(cpp), "-o", str(exe)], capture_output=True, text=True)
        if built.returncode:
            fail(f"LightGrid_AlignAxis harness did not compile:\n{built.stdout}{built.stderr}")
        ran = subprocess.run([str(exe)], capture_output=True, text=True)
        if ran.returncode:
            fail(f"LightGrid_AlignAxis lays grids out wrongly:\n{ran.stdout}{ran.stderr}")


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8").replace("\r\n", "\n")
    run_harness(check_contract(source))
    print("lightgrid_map_identity: ok")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as error:
        print(f"lightgrid_map_identity: FAIL: {error}", file=sys.stderr)
        sys.exit(1)
