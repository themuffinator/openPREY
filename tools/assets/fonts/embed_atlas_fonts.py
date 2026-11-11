"""Embed openPREY's traced Prey faces into the Interface Atlas and the release pages.

Usage:
    python tools/assets/fonts/embed_atlas_fonts.py

Subsets ``content/basepr/pak0/fonts/{menu,english,alien}.ttf`` to the Latin
range the pages draw and packs each as WOFF. It then rewrites the ``@font-face``
block between each target's markers:

- ``docs/dev/prey-ui/atlas/prey-interface-atlas.html`` (all three faces,
  ``openprey-atlas-fonts`` markers);
- ``assets/release/README.html`` (display and body faces,
  ``openprey-release-fonts`` markers);

and writes the display and body faces to ``assets/docs/fonts/`` for the
packaged documentation portal and project overview, which load them by URL.
Run it after rebuilding the faces with ``build_openprey_fonts.py`` so no page
drifts from what the engine ships. The retail atlases are not read here.
"""
from __future__ import annotations

import base64
import io
import re
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[3]
FONTS = ROOT / "content" / "basepr" / "pak0" / "fonts"
WOFF_DIR = ROOT / "assets" / "docs" / "fonts"

# CSS family name -> (shipped face, file written to WOFF_DIR or None)
FACES = {
    "openPREY Menu": ("menu.ttf", "openprey-menu.woff"),
    "openPREY Default": ("english.ttf", "openprey-default.woff"),
    "openPREY Alien": ("alien.ttf", None),
}

# page -> (marker name, families embedded in it)
TARGETS = (
    (ROOT / "docs" / "dev" / "prey-ui" / "atlas" / "prey-interface-atlas.html", "openprey-atlas-fonts",
     ("openPREY Menu", "openPREY Default", "openPREY Alien")),
    (ROOT / "assets" / "release" / "README.html", "openprey-release-fonts",
     ("openPREY Menu", "openPREY Default")),
)

# Basic Latin, Latin-1, general punctuation, arrows, multiplication and minus.
UNICODES = (
    list(range(0x20, 0x7F))
    + list(range(0xA0, 0x100))
    + list(range(0x2010, 0x2028))
    + list(range(0x2190, 0x2194))
    + [0x2212]
)


def packed(path: Path) -> bytes:
    font = TTFont(path)
    options = subset.Options()
    options.flavor = "woff"
    options.layout_features = ["kern"]
    options.name_IDs = ["*"]
    options.name_legacy = True
    options.notdef_outline = True
    options.hinting = False
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=UNICODES)
    subsetter.subset(font)
    buffer = io.BytesIO()
    font.flavor = "woff"
    font.save(buffer)
    return buffer.getvalue()


def font_face(family: str, data: bytes) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return (
        f'@font-face{{font-family:"{family}";src:url(data:font/woff;base64,{encoded}) format("woff");'
        f"font-weight:400;font-style:normal;font-display:block}}"
    )


def main() -> int:
    packs: dict[str, bytes] = {}
    for family, (filename, woff_name) in FACES.items():
        packs[family] = packed(FONTS / filename)
        print(f"{family}: {filename} -> {len(packs[family])} bytes woff")
        if woff_name:
            WOFF_DIR.mkdir(parents=True, exist_ok=True)
            (WOFF_DIR / woff_name).write_bytes(packs[family])
            print(f"wrote {(WOFF_DIR / woff_name).relative_to(ROOT)}")

    status = 0
    for page, marker, families in TARGETS:
        start, end = f"/* {marker}-start */", f"/* {marker}-end */"
        block = "\n".join([start, *(font_face(family, packs[family]) for family in families), end])
        text = page.read_text(encoding="utf-8")
        pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
        if not pattern.search(text):
            print(f"{page}: markers not found", file=sys.stderr)
            status = 1
            continue
        page.write_text(pattern.sub(lambda _: block, text, count=1), encoding="utf-8", newline="\n")
        print(f"updated {page.relative_to(ROOT)}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
