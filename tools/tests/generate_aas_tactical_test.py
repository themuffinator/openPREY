#!/usr/bin/env python3
"""Compile the SP and MP tactical search implementations in a controlled graph."""
from pathlib import Path
import sys

from async_drop_client_contract import function_body


def generate(source_path: Path, output: Path) -> None:
    source = source_path.read_text(encoding="utf-8")
    result = ""
    for signature in ("struct rvSortReach", "ID_INLINE int rvSortFeature(", "void rvAASTacticalSensorLocal::Search()"):
        line = source.count("\n", 0, source.index(signature)) + 1
        result += f'#line {line} "{source_path.resolve().as_posix()}"\n'
        result += function_body(source, signature) + (";\n" if signature.startswith("struct") else "\n")
    output.write_text(result, encoding="utf-8")


if __name__ == "__main__":
    generate(*map(Path, sys.argv[1:]))
