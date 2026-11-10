#!/usr/bin/env python3
"""Regression checks for idStr malformed-input handling.

The engine and companion GameLibs repository each build their own idlib copy.
These checks keep the two implementations aligned, pin the source-level bounds
guards, and exercise the legacy matching contract with a small independent
model so safety fixes do not accidentally change valid filter behavior.
"""

from __future__ import annotations

import os
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
GAME_LIBS_ROOT = Path(
    os.environ.get("OPENQ4_GAMELIBS_REPO", ROOT)
).resolve()


def read_legacy_source(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Required source file not found: {path}")
    # Str.cpp intentionally contains raw 8-bit lookup-table entries. Latin-1
    # is a lossless byte-to-code-point view; decoding as UTF-8 would corrupt or
    # reject the table before this test could inspect the ASCII function bodies.
    return path.read_bytes().decode("latin-1")


def function_body(source: str, signature: str, context: str) -> str:
    start = source.find(signature)
    if start < 0:
        raise AssertionError(f"Missing {signature!r} in {context}")

    brace_start = source.find("{", start + len(signature))
    if brace_start < 0:
        raise AssertionError(f"Missing body for {signature!r} in {context}")

    depth = 0
    for index in range(brace_start, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[brace_start : index + 1]

    raise AssertionError(f"Unterminated body for {signature!r} in {context}")


def compact(source: str) -> str:
    return re.sub(r"\s+", " ", source).strip()


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def require_before(haystack: str, first: str, second: str, context: str) -> None:
    first_index = haystack.find(first)
    second_index = haystack.find(second)
    if first_index < 0 or second_index < 0:
        raise AssertionError(
            f"Missing ordered safety checks {first!r} and/or {second!r} in {context}"
        )
    if first_index >= second_index:
        raise AssertionError(f"Expected {first!r} before {second!r} in {context}")


def strip_quotes_contract(value: str) -> str:
    """Model the established idStr::StripQuotes behavior safely."""
    if not value.startswith('"'):
        return value
    if len(value) == 1:
        return ""
    if value.endswith('"'):
        value = value[:-1]
    return value[1:]


def char_at(value: str, index: int) -> str:
    return value[index] if index < len(value) else "\0"


def chars_equal(left: str, right: str, case_sensitive: bool) -> bool:
    if case_sensitive:
        return left == right
    return left.upper() == right.upper()


def filter_contract(pattern: str, name: str, case_sensitive: bool) -> bool:
    """Bounded model of idStr::Filter, including its legacy prefix semantics."""
    filter_index = 0
    name_index = 0

    while char_at(pattern, filter_index) != "\0":
        current = char_at(pattern, filter_index)

        if current == "*":
            filter_index += 1
            literal: list[str] = []
            while char_at(pattern, filter_index) != "\0":
                current = char_at(pattern, filter_index)
                if (
                    current in {"*", "?"}
                    or current == "["
                    and char_at(pattern, filter_index + 1) != "["
                ):
                    break
                literal.append(current)
                if current == "[":
                    filter_index += 1
                filter_index += 1

            if literal:
                needle = "".join(literal)
                remainder = name[name_index:]
                if case_sensitive:
                    found_index = remainder.find(needle)
                else:
                    found_index = remainder.upper().find(needle.upper())
                if found_index < 0:
                    return False
                name_index += found_index + len(needle)
            continue

        if current == "?":
            if char_at(name, name_index) == "\0":
                return False
            filter_index += 1
            name_index += 1
            continue

        if current == "[":
            if char_at(pattern, filter_index + 1) == "[":
                if char_at(name, name_index) != "[":
                    return False
                filter_index += 2
                name_index += 1
                continue

            if char_at(name, name_index) == "\0":
                return False
            filter_index += 1
            found = False
            while char_at(pattern, filter_index) != "\0" and not found:
                current = char_at(pattern, filter_index)
                if current == "]" and char_at(pattern, filter_index + 1) != "]":
                    break

                range_end = char_at(pattern, filter_index + 2)
                is_range = (
                    char_at(pattern, filter_index + 1) == "-"
                    and range_end != "\0"
                    and (range_end != "]" or char_at(pattern, filter_index + 3) == "]")
                )
                if is_range:
                    candidate = char_at(name, name_index)
                    if not case_sensitive:
                        current = current.upper()
                        candidate = candidate.upper()
                        range_end = range_end.upper()
                    found = current <= candidate <= range_end
                    filter_index += 3
                else:
                    found = chars_equal(current, char_at(name, name_index), case_sensitive)
                    filter_index += 1

            if not found:
                return False

            while char_at(pattern, filter_index) != "\0":
                if (
                    char_at(pattern, filter_index) == "]"
                    and char_at(pattern, filter_index + 1) != "]"
                ):
                    break
                filter_index += 1
            if char_at(pattern, filter_index) == "\0":
                return False
            filter_index += 1
            name_index += 1
            continue

        if not chars_equal(current, char_at(name, name_index), case_sensitive):
            return False
        filter_index += 1
        name_index += 1

    return True


def validate_source_guards() -> None:
    sources = (
        (ROOT / "src" / "idlib" / "Str.cpp", "engine idStr"),
        (GAME_LIBS_ROOT / "src" / "idlib" / "Str.cpp", "GameLibs idStr"),
    )
    bodies: dict[str, tuple[str, str, str]] = {}

    for path, context in sources:
        source = read_legacy_source(path)
        filter_body = compact(function_body(source, "bool idStr::Filter(", context))
        strip_body = compact(function_body(source, "idStr& idStr::StripQuotes", context))
        numeric_body = compact(function_body(source, "bool idStr::IsNumeric(", context))
        bodies[context] = (filter_body, strip_body, numeric_body)

        question_guard = (
            "else if (*filter == '?') { if ( *name == '\\0' ) { return false; } "
            "filter++; name++; }"
        )
        require(filter_body, question_guard, f"{context} single-character wildcard guard")
        if filter_body.count("if ( *name == '\\0' )") != 2:
            raise AssertionError(
                f"{context} must guard both '?' and character classes before consuming a name byte"
            )
        require(
            filter_body,
            "else { if ( *name == '\\0' ) { return false; } filter++; "
            "found = false; while(*filter && !found)",
            f"{context} character-class name guard",
        )
        require(
            filter_body,
            "while(*filter) { if ( *filter == ']' && *(filter+1) != ']' ) { "
            "break; } filter++; } if ( *filter == '\\0' ) { return false; } "
            "filter++; name++;",
            f"{context} malformed character-class guard",
        )

        require(strip_body, "if ( len == 1 )", f"{context} single-quote guard")
        require(strip_body, "Empty();", f"{context} single-quote empty result")
        require_before(
            strip_body,
            "if ( len == 1 )",
            "data[len-1]",
            f"{context} quote-removal bounds order",
        )
        require(
            numeric_body,
            "return idNumericString::IsDecimal( s );",
            f"{context} shared numeric grammar",
        )

    if bodies["engine idStr"] != bodies["GameLibs idStr"]:
        raise AssertionError("Engine and GameLibs idStr safety implementations have drifted")


def validate_allocation_guards() -> None:
    sources = (
        (
            ROOT / "src" / "idlib" / "Str.cpp",
            ROOT / "src" / "idlib" / "Str.h",
            "engine idStr",
        ),
        (
            GAME_LIBS_ROOT / "src" / "idlib" / "Str.cpp",
            GAME_LIBS_ROOT / "src" / "idlib" / "Str.h",
            "GameLibs idStr",
        ),
    )
    bodies: dict[str, tuple[str, str, str, str]] = {}

    for source_path, header_path, context in sources:
        source = read_legacy_source(source_path)
        header = header_path.read_text(encoding="utf-8")
        reallocate = compact(function_body(source, "void idStr::ReAllocate(", context))
        assignment = compact(
            function_body(source, "void idStr::operator=( const char *text )", context)
        )
        replace = compact(function_body(source, "int idStr::Replace(", context))
        append_path = compact(function_body(source, "void idStr::AppendPath(", context))
        bodies[context] = (reallocate, assignment, replace, append_path)

        require(header, "ReAllocate( size_t amount", f"{context} allocation API")
        require(header, "EnsureAlloced( size_t amount", f"{context} allocation API")
        require(
            header,
            "amount > static_cast<size_t>( alloced )",
            f"{context} allocation-width comparison",
        )
        require(reallocate, "TryRoundUpToInt( amount, STR_ALLOC_GRAN, newsize )", context)
        require(assignment, "SaturatingAdd( textLength, 1 )", context)
        require(replace, "if ( oldLen == 0 )", f"{context} empty replacement pattern")
        require(replace, "SaturatingMultiply", f"{context} replacement sizing")
        require(append_path, "SaturatingAdd", f"{context} path sizing")
        require(header, 'idLib::Error( "idStr::Append: negative length" )', context)
        require(header, 'idLib::Error( "idStr::Fill: negative length" )', context)

        combined = header + "\n" + source
        for expression in (
            "EnsureAlloced( l + 1",
            "EnsureAlloced( len + 2",
            "EnsureAlloced( newLen + 1",
            "EnsureAlloced( len + l + 1",
            "EnsureAlloced( newlen + 1",
            "newLen = len + text.Length()",
            "newLen = len + l",
            "len + ( ( newLen - oldLen ) * count )",
        ):
            if expression in combined:
                raise AssertionError(
                    f"{context} retains overflow-prone allocation expression {expression!r}"
                )

    if bodies["engine idStr"] != bodies["GameLibs idStr"]:
        raise AssertionError("Engine and GameLibs idStr allocation implementations have drifted")

    # Source parity is textual.  Universal-newline decoding avoids treating a
    # Windows CRLF checkout and a Linux LF checkout as different helpers.
    engine_helper = (ROOT / "src" / "idlib" / "StrAllocation.h").read_text(encoding="utf-8")
    gamelibs_helper = (GAME_LIBS_ROOT / "src" / "idlib" / "StrAllocation.h").read_text(
        encoding="utf-8"
    )
    if engine_helper != gamelibs_helper:
        raise AssertionError("Engine and GameLibs string-allocation helpers have drifted")


def validate_numeric_helpers() -> None:
    engine_header = (ROOT / "src" / "idlib" / "NumericString.h").read_text(encoding="utf-8")
    gamelibs_header = (GAME_LIBS_ROOT / "src" / "idlib" / "NumericString.h").read_text(
        encoding="utf-8"
    )
    if engine_header != gamelibs_header:
        raise AssertionError("Engine and GameLibs numeric-string helpers have drifted")

    decimal = compact(function_body(engine_header, "inline bool IsDecimal(", "numeric helper"))
    bounded = compact(
        function_body(engine_header, "inline bool ParseUnsignedBounded(", "numeric helper")
    )
    for token in ("text == nullptr", "text[ 0 ] == '\\0'", "sawDigit", "sawDot"):
        require(decimal, token, "numeric decimal grammar")
    require(decimal, "return sawDigit;", "numeric grammar requires at least one digit")
    for token in (
        "maximum < 0",
        "parsed > maximum / 10",
        "digit > maximum % 10",
        "value = parsed;",
    ):
        require(bounded, token, "bounded unsigned parser")

    usercmd = (ROOT / "src" / "framework" / "UsercmdGen.cpp").read_text(encoding="utf-8")
    impulse = compact(function_body(usercmd, "static bool ParseImpulseCommand(", "impulse parser"))
    require(
        impulse,
        "idNumericString::ParseUnsignedBounded( impulseSuffix, IMPULSE_127, impulseNum )",
        "bounded impulse parsing",
    )
    if "atoi" in impulse:
        raise AssertionError("Impulse command parsing must not use overflow-prone atoi")


def validate_strip_quotes_behavior() -> None:
    cases = (
        ("", ""),
        ("plain", "plain"),
        ('plain"', 'plain"'),
        ('"', ""),
        ('""', ""),
        ('"quoted"', "quoted"),
        ('"unterminated', "unterminated"),
    )
    for value, expected in cases:
        actual = strip_quotes_contract(value)
        if actual != expected:
            raise AssertionError(
                f"StripQuotes contract failed for {value!r}: expected {expected!r}, got {actual!r}"
            )


def validate_filter_behavior() -> None:
    cases = (
        ("", "anything", True, True, "empty filter keeps legacy prefix semantics"),
        ("abc", "abcdef", True, True, "literal filter keeps legacy prefix semantics"),
        ("abc", "ab", True, False, "literal filter cannot overrun the name"),
        ("*bar", "fooBarTail", False, True, "case-insensitive wildcard search"),
        ("a?c", "abc", True, True, "question mark consumes one character"),
        ("?", "", True, False, "question mark does not match an empty name"),
        ("??a", "", True, False, "repeated question marks stay in bounds"),
        ("[ab]", "b", True, True, "valid character class"),
        ("[ab]", "c", True, False, "character class rejection"),
        ("[a-z]", "Q", False, True, "case-insensitive character range"),
        ("[[", "[", True, True, "escaped opening bracket"),
        ("[a]", "", True, False, "character class does not consume an empty name"),
        ("[a", "a", True, False, "unterminated matching class fails closed"),
        ("[a", "b", True, False, "unterminated nonmatching class fails closed"),
    )
    for pattern, name, case_sensitive, expected, context in cases:
        actual = filter_contract(pattern, name, case_sensitive)
        if actual != expected:
            raise AssertionError(
                f"Filter contract failed ({context}): pattern={pattern!r}, name={name!r}, "
                f"expected {expected}, got {actual}"
            )


def validate_runner_wiring() -> None:
    validator = (ROOT / "tools" / "validation" / "openq4_validate.py").read_text(
        encoding="utf-8"
    )
    require(validator, "idstr_input_safety.py", "validation runner")

    meson = (ROOT / "meson.build").read_text(encoding="utf-8")
    options = (ROOT / "meson_options.txt").read_text(encoding="utf-8")
    native_test = (ROOT / "tools" / "tests" / "native" / "CoreSafetyTest.cpp").read_text(
        encoding="utf-8"
    )
    require(options, "'build_native_tests'", "native test option")
    require(meson, "'openq4-core-safety-test'", "native test executable")
    require(meson, "'openq4-core-safety'", "native Meson test")
    require(meson, "tools/tests/native/CoreSafetyTest.cpp", "native test source wiring")
    require(native_test, "idNumericString::IsDecimal", "native decimal test")
    require(native_test, "idNumericString::ParseUnsignedBounded", "native bounded parser test")
    require(native_test, "TryRoundUpToInt", "native string-allocation boundary test")
    require(native_test, "maximumRoundedAllocation + 1", "native rounded-int boundary test")


def main() -> None:
    validate_source_guards()
    validate_allocation_guards()
    validate_numeric_helpers()
    validate_strip_quotes_behavior()
    validate_filter_behavior()
    validate_runner_wiring()
    print("idstr_input_safety: ok")


if __name__ == "__main__":
    main()
