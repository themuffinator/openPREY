#!/usr/bin/env python3
"""Expose production bit-message operations to the dependency-light native test."""
from pathlib import Path
import sys

from async_drop_client_contract import function_body


def generate(header: Path, implementation: Path, output: Path) -> None:
    declarations = header.read_text(encoding="utf-8").split("class idMsgQueue {", 1)[0]
    source = implementation.read_text(encoding="utf-8")
    generated = f'#line 1 "{header.resolve().as_posix()}"\n{declarations}\n#endif\n'
    begin = source.index("const int MAX_DATA_BUFFER")
    generated += source[begin:source.index(";", begin) + 1] + "\n"
    for signature in (
        "idBitMsg::idBitMsg()",
        "bool idBitMsg::CheckOverflow(",
        "byte *idBitMsg::GetByteSpace(",
        "void idBitMsg::WriteBits(",
        "void idBitMsg::WriteString(",
        "void idBitMsg::WriteData(",
        "int idBitMsg::ReadBits(",
        "int idBitMsg::ReadString(",
        "int idBitMsg::ReadData(",
        "void idBitMsgDelta::WriteData(",
        "void idBitMsgDelta::ReadData(",
    ):
        line = source.count("\n", 0, source.index(signature)) + 1
        generated += f'\n#line {line} "{implementation.resolve().as_posix()}"\n'
        generated += function_body(source, signature) + "\n"
    output.write_text(generated, encoding="utf-8")


if __name__ == "__main__":
    generate(*map(Path, sys.argv[1:]))
