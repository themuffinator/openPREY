#!/usr/bin/env python3
"""Validate Android libraries for the phone and diagnostic emulator packages."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import struct


@dataclass(frozen=True)
class AndroidAbi:
    triple: str
    cpu_family: str
    machine: int
    label: str
    module_arch: str


# The cross compiler, dependency builder and APK verifier share this mapping.
# x86_64 is a diagnostic emulator target, not a second release ABI.
ANDROID_ABIS = {
    "arm64-v8a": AndroidAbi("aarch64-linux-android", "aarch64", 183, "AArch64", "arm64"),
    "x86_64": AndroidAbi("x86_64-linux-android", "x86_64", 62, "x86-64", "x64"),
}
DEFAULT_ABI = "arm64-v8a"


def android_abi(name: str) -> AndroidAbi:
    try:
        return ANDROID_ABIS[name]
    except KeyError:
        raise ValueError(f"Unsupported Android ABI {name!r}; expected one of {', '.join(ANDROID_ABIS)}") from None


def validate_library(path: Path, api: int, abi: str = DEFAULT_ABI) -> int:
    target = android_abi(abi)
    data = path.read_bytes()
    if len(data) < 64 or data[:6] != b"\x7fELF\x02\x01":
        raise ValueError(f"{path}: expected a little-endian ELF64 library")
    elf_type, machine = struct.unpack_from("<HH", data, 16)
    if elf_type != 3 or machine != target.machine:
        raise ValueError(f"{path}: expected an {target.label} shared library")
    ph_offset = struct.unpack_from("<Q", data, 32)[0]
    ph_size, ph_count = struct.unpack_from("<HH", data, 54)
    if ph_size < 56 or not ph_count or ph_offset + ph_size * ph_count > len(data):
        raise ValueError(f"{path}: invalid ELF program headers")
    loads = 0
    android_api = None
    for index in range(ph_count):
        kind, _, offset, address, _, file_size, memory_size, alignment = struct.unpack_from(
            "<IIQQQQQQ", data, ph_offset + index * ph_size)
        if offset + file_size > len(data):
            raise ValueError(f"{path}: truncated ELF segment")
        if kind == 1:  # PT_LOAD
            loads += 1
            if file_size > memory_size or alignment < 16384 or alignment & (alignment - 1) or offset % alignment != address % alignment:
                raise ValueError(f"{path}: load segment does not support 16 KiB pages")
        elif kind == 4:  # PT_NOTE: NDK crtbegin records the compiled target API.
            end = offset + file_size
            while offset < end:
                if end - offset < 12:
                    raise ValueError(f"{path}: truncated ELF note")
                name_size, desc_size, note_type = struct.unpack_from("<III", data, offset)
                name_start = offset + 12
                desc_start = name_start + ((name_size + 3) & ~3)
                next_note = desc_start + ((desc_size + 3) & ~3)
                if next_note > end:
                    raise ValueError(f"{path}: truncated ELF note data")
                if data[name_start:name_start + name_size].rstrip(b"\0") == b"Android" and note_type == 1 and desc_size >= 4:
                    value = struct.unpack_from("<I", data, desc_start)[0]
                    android_api = max(android_api or 0, value)
                offset = next_note
    if not loads or android_api is None or android_api < 1:
        raise ValueError(f"{path}: missing Android load segments or target API note")
    if android_api > api:
        raise ValueError(f"{path}: targets Android API {android_api}, above the configured API {api}")
    return android_api


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", type=int, required=True)
    parser.add_argument("--abi", choices=sorted(ANDROID_ABIS), default=DEFAULT_ABI)
    parser.add_argument("libraries", nargs="+", type=Path)
    args = parser.parse_args()
    try:
        for path in args.libraries:
            native_api = validate_library(path, args.api, args.abi)
            print(f"{path.name}: Android {args.abi} API {native_api}, 16 KiB load alignment")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
