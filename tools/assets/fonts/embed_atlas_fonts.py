"""Embed openPREY's traced Prey faces into the Interface Atlas.

Usage:
    python tools/assets/fonts/embed_atlas_fonts.py

Subsets ``content/basepr/pak0/fonts/{menu,english,alien}.ttf`` to the Latin
range the atlas draws, packs each as WOFF and rewrites the ``@font-face`` block
between the ``openprey-atlas-fonts`` markers in
``docs/dev/prey-ui/atlas/prey-interface-atlas.html``. Run it after rebuilding
the faces with ``build_openprey_fonts.py`` so the atlas never drifts from what
the engine ships. The retail atlases are not read here.
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
ATLAS = ROOT / "docs" / "dev" / "prey-ui" / "atlas" / "prey-interface-atlas.html"
START = "/* openprey-atlas-fonts-start */"
END = "/* openprey-atlas-fonts-end */"

# CSS family name -> shipped face
FACES = {
    "openPREY Menu": "menu.ttf",
    "openPREY Default": "english.ttf",
    "openPREY Alien": "alien.ttf",
}

# Basic Latin, Latin-1, general punctuation, arrows, multiplication and minus.
UNICODES = (
    list(range(0x20, 0x7F))
    + list(range(0xA0, 0x100))
    + list(range(0x2010, 0x2028))
    + list(range(0x2190, 0x2194))
    + [0x2212]
)


def packed(path: Path) -> tuple[str, int]:
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
    data = buffer.getvalue()
    return base64.b64encode(data).decode("ascii"), len(data)


def main() -> int:
    rules = [START]
    for family, filename in FACES.items():
        encoded, size = packed(FONTS / filename)
        rules.append(
            f'@font-face{{font-family:"{family}";src:url(data:font/woff;base64,{encoded}) format("woff");'
            f"font-weight:400;font-style:normal;font-display:block}}"
        )
        print(f"{family}: {filename} -> {size} bytes woff")
    rules.append(END)
    block = "\n".join(rules)

    text = ATLAS.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        print(f"{ATLAS}: markers not found", file=sys.stderr)
        return 1
    ATLAS.write_text(pattern.sub(lambda _: block, text, count=1), encoding="utf-8", newline="\n")
    print(f"updated {ATLAS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
