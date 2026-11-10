#!/usr/bin/env python3
"""Keep packed-decl network identity independent of lazy client rendering."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "framework" / "DeclManager.cpp"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    stub = text.index('if ( idStr::Icmpn( parseText, "{ STUB:", 7 ) == 0 )')
    end = text.index("\n\tconst bool generatedRetainedResource", stub)
    block = text[stub:end]

    require(
        "const int packedStubChecksum = checksum;" in block,
        "packed declaration expansion must retain its transport checksum",
    )
    require(
        block.index("checksum = packedStubChecksum;")
        > block.index("SetTextLocal( definition.c_str(), definition.Length() );"),
        "the packed checksum must be restored after lazy source expansion",
    )
    require(
        "decl->sourceFile == &implicitDecls" in text,
        "implicit renderer/UI declarations must remain excluded from GetChecksum",
    )

    print("decl checksum stability contract: PASS")


if __name__ == "__main__":
    main()
