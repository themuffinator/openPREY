#!/usr/bin/env python3
"""Shared Linux launcher and desktop-entry metadata helpers."""

from __future__ import annotations

import shlex
from pathlib import Path


class LinuxMetadataError(RuntimeError):
    """Raised when Linux package metadata is malformed."""


def desktop_entry_exec(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LinuxMetadataError(f"Linux desktop entry is unreadable: {path}") from exc

    if "\x00" in text:
        raise LinuxMetadataError(f"Linux desktop entry contains NUL data: {path}")

    in_desktop_entry = False
    exec_seen = False
    exec_line = ""
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if line_number == 1:
            line = line.lstrip("\ufeff")
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_desktop_entry = line == "[Desktop Entry]"
            continue
        if not in_desktop_entry:
            continue
        if line.startswith("Exec="):
            if exec_seen:
                raise LinuxMetadataError(f"Linux desktop entry has more than one Exec key in [Desktop Entry]: {path}")
            exec_seen = True
            exec_line = line[5:].strip()
    return exec_line


def desktop_exec_command(exec_line: str) -> str:
    if not exec_line:
        return ""
    if "\x00" in exec_line or "\n" in exec_line or "\r" in exec_line:
        raise LinuxMetadataError("Exec line contains control data")
    try:
        parts = shlex.split(exec_line, posix=True)
    except ValueError as exc:
        raise LinuxMetadataError(str(exc)) from exc
    if not parts:
        return ""
    if parts[0].startswith("%"):
        raise LinuxMetadataError("Exec command starts with a desktop-entry field code")
    return parts[0]
