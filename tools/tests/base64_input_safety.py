#!/usr/bin/env python3
"""Regression checks for bounded, deterministic Base64 handling in both repositories."""

from __future__ import annotations

import base64
import os
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GAME_ROOT = Path(os.environ.get("OPENQ4_GAMELIBS_REPO", ROOT)).resolve()
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
DECODE = {character: index for index, character in enumerate(ALPHABET)}
WHITESPACE = " \n\r\t"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"required Base64 source is missing: {path}")
    return path.read_text(encoding="windows-1252")


def between(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin + len(start))
    return source[begin:finish]


def require(source: str, token: str, label: str) -> None:
    if token not in source:
        raise AssertionError(f"{label} is missing {token!r}")


def validate_repository(repo: Path) -> None:
    cpp_path = repo / "src" / "idlib" / "Base64.cpp"
    header_path = repo / "src" / "idlib" / "Base64.h"
    cpp = read(cpp_path)
    header = read(header_path)
    label = f"{repo.name} Base64"

    encode = between(cpp, "void idBase64::Encode( const byte *from, int size )", "int idBase64::DecodeLength")
    for token in (
        "if ( from == NULL || size <= 0 )",
        "encodedSize = 4ULL",
        "encodedSize >",
        "idMath::INT_MAX",
        "EnsureAlloced( (int)encodedSize )",
        "if ( data == NULL )",
        "w = 0;",
        "len = (int)( to - data - 1 );",
    ):
        require(encode, token, f"{label} encoder")
    if encode.index("if ( from == NULL || size <= 0 )") > encode.index("encodedSize = 4ULL"):
        raise AssertionError(f"{label} performs size arithmetic before validating its input")
    if encode.index("encodedSize >") > encode.index("EnsureAlloced( (int)encodedSize )"):
        raise AssertionError(f"{label} validates encoded allocation size after narrowing it")
    if encode.index("if ( data == NULL )") > encode.index("to = data;"):
        raise AssertionError(f"{label} publishes an allocation before checking it")
    if encode.index("w = 0;") > encode.index("while (size > 0)"):
        raise AssertionError(f"{label} reads the encoder accumulator before initialization")

    decode_length = between(cpp, "int idBase64::DecodeLength( void ) const", "int idBase64::Decode( byte *to ) const")
    for token in (
        "if ( data == NULL || len <= 0 )",
        "Base64_IsWhiteSpace( *from )",
        "Base64_DecodeSixtet( *from ) < 0",
        "digits * 6ULL",
        "idMath::INT_MAX",
    ):
        require(decode_length, token, f"{label} decoded-length calculation")

    decode = between(cpp, "int idBase64::Decode( byte *to ) const", "void idBase64::Encode( const idStr &src )")
    for token in (
        "if ( to == NULL || from == NULL )",
        "byte in[4] = {0,0,0,0};",
        "Base64_IsWhiteSpace( *from )",
        "Base64_DecodeSixtet( *from )",
        "if ( sixtet < 0 )",
        "memset( in, 0, sizeof( in ) );",
        "if ( i > 1 )",
        'idLib::SizeToInt( n, "idBase64::Decode" )',
    ):
        require(decode, token, f"{label} decoder")
    if "static char base64_to_sixtet" in decode or "static int tab_init" in decode:
        raise AssertionError(f"{label} retains the racy permissive lazy decode table")

    file_decode = between(cpp, "void idBase64::Decode( idFile *dest ) const", "#if 0")
    require(file_decode, "if ( dest == NULL )", f"{label} file decoder")
    require(file_decode, "if ( out > 0 )", f"{label} file decoder")

    for token in (
        'return ( data != NULL ) ? (const char *)data : "";',
        "if ( size <= alloced )",
        "if ( size <= 0 )",
        "if ( data != NULL )",
        "memcpy( data, s.c_str(), len + 1 );",
    ):
        require(header, token, f"{label} storage")


def decoded_length_model(text: str) -> int:
    digits = 0
    for character in text:
        if character in WHITESPACE:
            continue
        if character == "=" or character not in DECODE:
            break
        digits += 1
    return digits * 6 // 8


def decode_model(text: str) -> bytes:
    pending: list[int] = []
    output = bytearray()
    for character in text:
        if character == "=":
            break
        if character in WHITESPACE:
            continue
        sixtet = DECODE.get(character)
        if sixtet is None:
            return bytes(output)
        pending.append(sixtet)
        if len(pending) == 4:
            value = (pending[0] << 18) | (pending[1] << 12) | (pending[2] << 6) | pending[3]
            output.extend(((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF))
            pending.clear()
    if len(pending) > 1:
        padded = pending + [0] * (4 - len(pending))
        value = (padded[0] << 18) | (padded[1] << 12) | (padded[2] << 6) | padded[3]
        output.extend(((value >> 16) & 0xFF, (value >> 8) & 0xFF)[: len(pending) * 6 // 8])
    return bytes(output)


def validate_decode_model() -> None:
    vectors = (
        (b"", ""),
        (b"f", "Zg=="),
        (b"fo", "Zm8="),
        (b"foo", "Zm9v"),
        (b"foob", "Zm9vYg=="),
        (b"fooba", "Zm9vYmE="),
        (b"foobar", "Zm9vYmFy"),
    )
    for payload, encoded in vectors:
        if decode_model(encoded) != payload or decoded_length_model(encoded) != len(payload):
            raise AssertionError(f"Base64 model failed vector {encoded!r}")

    if decode_model(" Zm9v\r\nYmFy\t") != b"foobar":
        raise AssertionError("Base64 model does not accept bounded ASCII whitespace")
    if decode_model("Zm9v!YmFy") != b"foo" or decode_model("Zg!") != b"":
        raise AssertionError("Base64 model does not stop safely at invalid alphabet bytes")
    if decode_model("Zg==ignored") != b"f":
        raise AssertionError("Base64 model does not stop at padding")

    generator = random.Random(0x0B64)
    for size in (*range(65), 127, 255, 256, 257):
        payload = bytes(generator.randrange(256) for _ in range(size))
        encoded = base64.b64encode(payload).decode("ascii")
        decorated = "".join(
            character + (WHITESPACE[generator.randrange(len(WHITESPACE))] if generator.randrange(7) == 0 else "")
            for character in encoded
        )
        if decode_model(decorated) != payload:
            raise AssertionError(f"Base64 whitespace round trip failed at {size} bytes")
        if len(decode_model(decorated)) > decoded_length_model(decorated):
            raise AssertionError("Base64 decoded-length model under-allocated a valid payload")

    alphabet_and_noise = ALPHABET + "=!?@#$%^&*()[]{}" + WHITESPACE
    for _ in range(5000):
        text = "".join(generator.choice(alphabet_and_noise) for _ in range(generator.randrange(80)))
        if len(decode_model(text)) > decoded_length_model(text):
            raise AssertionError(f"Base64 decoded-length model under-allocated malformed input {text!r}")


def main() -> None:
    validate_repository(ROOT)
    validate_repository(GAME_ROOT)
    validate_decode_model()
    validation = read(ROOT / "tools" / "validation" / "openq4_validate.py")
    require(validation, "base64_input_safety.py", "Base64 validation wiring")
    print("base64 input safety: ok")


if __name__ == "__main__":
    main()
