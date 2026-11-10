#!/usr/bin/env python3
"""Run production AAS area emission with water-jump/swim classification controls."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from mp_lag_compensation_state import block

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    source = (ROOT / "src/tools/compilers/aas/AASBuild_file.cpp").read_text(encoding="utf-8")
    function = block(source, "bool idAASBuild::GetAreaForLeafNode(")
    header = (ROOT / "src/aas/AASFile.h").read_text(encoding="utf-8")
    constants = "\n".join(re.findall(r"^#define (?:AREA_LIQUID|AREA_FLOOR|AREACONTENTS_WATER)\s+[^\n]+", header, re.M))
    harness = r'''
#include <cassert>
#include <cstring>
#include <cstdlib>
#include <vector>
#include <cstdio>
#define BIT(x) (1 << (x))
@CONSTANTS@
template<class T> struct List : std::vector<T> {
    int Num() const { return static_cast<int>(this->size()); }
    void Append(const T &value) { this->push_back(value); }
};
struct aasArea_t {
    int flags, cluster, clusterAreaNum, contents, firstFace, numFaces;
    void *reach, *rev_reach;
};
struct Face { int areas[2] = {}; };
struct idBrushBSPNode;
struct idBrushBSPPortal {
    idBrushBSPNode *node = nullptr;
    idBrushBSPPortal *Next(int) { return nullptr; }
    idBrushBSPNode *GetNode(int side) { return side ? node : nullptr; }
};
struct idBrushBSPNode {
    int number = 0, flags = AREA_FLOOR, contents = 0;
    idBrushBSPPortal portal;
    bool hasFace = true;
    int GetAreaNum() const { return number; }
    void SetAreaNum(int value) { number = value; }
    int GetFlags() const { return flags; }
    int GetContents() const { return contents; }
    idBrushBSPPortal *GetPortals() { portal.node = this; return hasFace ? &portal : nullptr; }
};
struct File { List<aasArea_t> areas; List<int> faceIndex; Face faces[2]; };
struct idAASBuild {
    File storage, *file = &storage;
    idAASBuild() { storage.areas.Append({}); }
    bool GetAreaForLeafNode(idBrushBSPNode *, int *);
    bool GetFaceForPortal(idBrushBSPPortal *, int, int *face) { *face = 1; return true; }
};
void DisplayRealTimeString(const char *, int) {}
@PRODUCTION@
int main() {
    for (int wet = 0; wet != 2; ++wet) {
        for (int floor = 0; floor != 2; ++floor) {
            idAASBuild build;
            idBrushBSPNode node;
            node.flags = floor ? AREA_FLOOR : 0;
            node.contents = wet ? AREACONTENTS_WATER : 0;
            int number = 42;
            assert(build.GetAreaForLeafNode(&node, &number) && number == -1);
            const auto &area = build.file->areas[1];
            assert(!!(area.flags & AREA_LIQUID) == !!wet);
            assert(!!(area.flags & AREA_FLOOR) == !!floor);
            assert(!!(area.contents & AREACONTENTS_WATER) == !!wet);
            assert(area.numFaces == 1 && area.firstFace == 0);
            assert(build.GetAreaForLeafNode(&node, &number) && number == -1);
            assert(build.file->areas.Num() == 2);
        }
    }
    idAASBuild empty;
    idBrushBSPNode noFaces;
    noFaces.contents = AREACONTENTS_WATER;
    noFaces.hasFace = false;
    int number = 42;
    assert(!empty.GetAreaForLeafNode(&noFaces, &number) && number == 0);
    assert(empty.file->areas.Num() == 1);
    puts("AAS liquid areas: PASS (wet/dry, floor/no floor, reused and empty nodes)");
}
'''.replace("@CONSTANTS@", constants)
    compiler = os.environ.get("CXX") or shutil.which("clang++") or shutil.which("g++")
    if not compiler:
        raise RuntimeError("a C++ compiler is required")
    task_tmp = ROOT / ".tmp"
    task_tmp.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="aas-liquid-", dir=task_tmp) as name:
        directory = Path(name)
        cpp, exe = directory / "fixture.cpp", directory / ("fixture.exe" if os.name == "nt" else "fixture")
        command = [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(exe)]
        for control in (False, True):
            production = function.replace("area.flags |= AREA_LIQUID;", "/* lost water-jump classification */") if control else function
            if control and production == function:
                raise AssertionError("missing liquid-classification control anchor")
            cpp.write_text(harness.replace("@PRODUCTION@", production), encoding="utf-8")
            subprocess.run(command, cwd=directory, check=True)
            result = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True)
            if (result.returncode == 0) == control:
                raise AssertionError(f"unexpected {'control' if control else 'production'} result: {result.stdout}{result.stderr}")
            if not control:
                print(result.stdout, end="")
    print("aas_liquid_area_state: PASS (pre-fix control fails)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
