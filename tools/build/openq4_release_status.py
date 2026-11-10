"""Withdrawal policy shared by version selection and release notes.

Git tags remain useful for reproducing withdrawn builds. Their presence does
not make them available releases. Compare numeric versions so 0.14.0 and
0.14.000 have the same status; retain the tags and historical evidence.
"""

from __future__ import annotations


WITHDRAWN_RELEASES: dict[tuple[int, int, int], str] = {
    (0, 14, 0): "Withdrawn after publication because the release was broken.",
}


def is_withdrawn_release(version: tuple[int, int, int]) -> bool:
    return version in WITHDRAWN_RELEASES


def require_available_release(version: tuple[int, int, int]) -> None:
    if is_withdrawn_release(version):
        text = ".".join(str(part) for part in version)
        raise SystemExit(f"release {text} is withdrawn; choose a new version instead of reusing it")
