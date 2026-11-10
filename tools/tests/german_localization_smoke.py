#!/usr/bin/env python3
"""Check German gameplay, menu rendering and live language switching (requires Pillow).

The German case of localization_smoke.py, kept under its original name and
evidence folder.
"""
from __future__ import annotations

from pathlib import Path
import sys

from localization_smoke import main as localization_smoke

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    args = sys.argv[1:]
    if not any(arg == "--output-dir" or arg.startswith("--output-dir=") for arg in args):
        args += ["--output-dir", str(ROOT / ".tmp/german-localization-smoke")]
    localization_smoke(["--language", "german", *args])


if __name__ == "__main__":
    main()
