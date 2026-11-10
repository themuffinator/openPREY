#!/usr/bin/env python3
"""Regression check for lossy re-encoding of the 8-bit C++ sources.

Parts of idlib are still authored in the raw 8-bit codepage they shipped in:
``idStr``'s printable/upper/lower tables index a 256-entry array with literal
high bytes, and ``idLexer``'s punctuation table matches the inverted-pling and
inverted-query bytes directly.  Those bytes are not valid UTF-8, so an editor
that "helpfully" saves the file as UTF-8 rewrites every one of them to U+FFFD
(``EF BF BD``) and the original character identity is gone for good.

That has happened twice:

  * ``Str.cpp`` lost all 401 high bytes in the char-signedness commit.  Each
    ``'\\xC0'`` became the three-byte U+FFFD sequence, which in a braced
    initializer is a multi-character literal worth 15712189 - MSVC accepts it
    with a warning, but GCC and Clang reject it as a narrowing conversion, so
    every Linux and macOS release job failed while Windows kept building.
  * ``Lexer.cpp`` lost its six ``\\xA1``/``\\xBF`` literals much earlier.  Those
    are string literals rather than braced initializers, so nothing failed to
    compile - instead both punctuation entries silently became the *same*
    mangled sequence, which made the inverted-query branch dead code.

The first mode breaks the release build on two thirds of the platforms; the
second corrupts the parser with no build signal at all.  Guard both by refusing
to let a U+FFFD sequence exist in a tracked C/C++ source, and pin the two known
high-byte tables so a future re-encode cannot quietly flatten them to ASCII.
"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "src"
SOURCE_SUFFIXES = {".c", ".cpp", ".h", ".hpp", ".inl"}

REPLACEMENT = b"\xef\xbf\xbd"

# idLexer's two Latin-1 punctuation bytes, and the tables in idStr that must
# keep real high bytes rather than being flattened to ASCII.
INVERTED_PLING = 0xA1
INVERTED_QUERY = 0xBF
MINIMUM_STR_HIGH_BYTES = 300


def iter_sources():
    for path in sorted(SOURCE_ROOT.rglob("*")):
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES:
            yield path


def validate_no_replacement_characters() -> None:
    damaged = []
    for path in iter_sources():
        data = path.read_bytes()
        count = data.count(REPLACEMENT)
        if count:
            rel = path.relative_to(ROOT).as_posix()
            line = data[: data.index(REPLACEMENT)].count(b"\n") + 1
            damaged.append(f"{rel}: {count} U+FFFD sequence(s), first at line {line}")

    if damaged:
        raise AssertionError(
            "Tracked C/C++ sources contain the U+FFFD replacement character:\n  "
            + "\n  ".join(damaged)
            + "\n\nThis is what a lossy UTF-8 re-encode of an 8-bit source looks "
            "like - the original high bytes are unrecoverable from the file "
            "itself. Restore the affected lines from the last good revision "
            "(git log -p on the file) rather than hand-retyping them, and save "
            "the file without changing its encoding."
        )


def validate_lexer_punctuation_bytes() -> None:
    """idLexer's two high-byte punctuation literals must stay ASCII escapes.

    These are written ``"\\xa1"`` / ``"\\xbf"`` rather than as raw bytes on
    purpose: the escape compiles to the same one-byte string, but it keeps
    Lexer.cpp valid UTF-8, so an editor cannot lossily re-encode it and the
    tooling that reads this file as strict UTF-8 keeps working.
    """
    path = SOURCE_ROOT / "idlib" / "Lexer.cpp"
    data = path.read_bytes()
    rel = path.relative_to(ROOT).as_posix()

    for byte, name in (
        (INVERTED_PLING, "P_INVERTED_PLING"),
        (INVERTED_QUERY, "P_INVERTED_QUERY"),
    ):
        escape = f'"\\x{byte:02x}"'.encode("ascii")
        if escape + b"," + name.encode("ascii") not in data:
            raise AssertionError(
                f"{rel}: the {name} punctuation entry is no longer the ASCII "
                f'escape {escape.decode("ascii")}. idLexer compares tokens '
                "byte-for-byte against this table, so the entry has to stay a "
                "one-byte literal - write it as an escape, not as a raw "
                f"0x{byte:02X} byte."
            )

        if bytes([byte]) in data:
            raise AssertionError(
                f"{rel}: contains a raw 0x{byte:02X} byte. Write this "
                f'punctuation as {escape.decode("ascii")} so the file stays '
                "valid UTF-8 and cannot be flattened to U+FFFD by an editor."
            )

    # Both entries were once the same mangled sequence, which silently made the
    # second branch unreachable; keep them distinct and in matched pairs.
    pling = data.count(f'"\\x{INVERTED_PLING:02x}"'.encode("ascii"))
    query = data.count(f'"\\x{INVERTED_QUERY:02x}"'.encode("ascii"))
    if pling != query or pling == 0:
        raise AssertionError(
            f"{rel}: inverted-pling appears {pling} time(s) and inverted-query "
            f"{query} time(s). They are written in matched pairs (punctuation "
            "table, WriteBinaryToken, ReadToken); an imbalance means one of "
            "the branches is dead code."
        )


def validate_str_tables_keep_high_bytes() -> None:
    path = SOURCE_ROOT / "idlib" / "Str.cpp"
    data = path.read_bytes()
    rel = path.relative_to(ROOT).as_posix()

    high_bytes = sum(1 for byte in data if byte >= 0x80)
    if high_bytes < MINIMUM_STR_HIGH_BYTES:
        raise AssertionError(
            f"{rel}: only {high_bytes} high bytes remain, expected at least "
            f"{MINIMUM_STR_HIGH_BYTES}. idStr::printableCharacter, "
            "upperCaseCharacter and lowerCaseCharacter are 256-entry tables "
            "indexed by a raw byte; flattening the high half to ASCII or 0 "
            "silently breaks case folding and printability for every accented "
            "character."
        )

    # A multi-character literal is the specific shape that broke the Linux and
    # macOS release builds; a char literal here must be exactly one byte.
    for index, line in enumerate(data.split(b"\n"), start=1):
        stripped = line.strip()
        if not stripped.startswith(b"'") and b", '" not in stripped:
            continue
        cursor = 0
        while True:
            start = line.find(b"'", cursor)
            if start < 0:
                break
            end = line.find(b"'", start + 1)
            if end < 0:
                break
            literal = line[start + 1 : end]
            # skip an escaped quote such as '\''
            if literal.startswith(b"\\"):
                cursor = end + 1
                continue
            if len(literal) > 1:
                raise AssertionError(
                    f"{rel}:{index}: multi-byte character literal "
                    f"{literal!r}. GCC and Clang reject this as a narrowing "
                    "conversion inside the braced table initializers, which is "
                    "how the corrupted tables broke every Linux and macOS "
                    "release job while Windows still built."
                )
            cursor = end + 1


def validate_ci_smoke() -> None:
    for relative_path, context in (
        (".github/workflows/push-verification.yml", "push verification workflow"),
        (".github/workflows/commit-validation.yml", "commit validation workflow"),
        ("tools/validation/openq4_validate.py", "validation runner"),
    ):
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        if "source_charset_integrity.py" not in source:
            raise AssertionError(
                f"Missing 'source_charset_integrity.py' in {context} "
                f"({relative_path})"
            )


def main() -> int:
    validate_no_replacement_characters()
    validate_lexer_punctuation_bytes()
    validate_str_tables_keep_high_bytes()
    validate_ci_smoke()
    print("source_charset_integrity: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
