"""Working copies of retail maps that stage one scene for a levelshot.

A loading screen can show a moment no level reaches on its own: feedingtowera's
is the ending of roadhouse, the ship over the torn-off roof. A scene in
poses.json names the retail map to copy, entity edits and a staging script:

    "scene": {"from": "game/roadhouse", "name": "levelshot_feedingtowera",
              "edit": {"rhEndLevel": {"classname": "info_null"}},
              "call": "levelshot_scene::stage",
              "script": "namespace levelshot_scene { void stage() { ... } }"}

The copy is written from the user's own retail pak into a slot's savepath
(maps/game/<name>.map, .proc, .cm, .aas48 and the staging script), so no retail
data is redistributed. The level's own map script keeps running: Prey compiles
every map script at startup, and the copy keeps the worldspawn's `call` keys.
Its staging function is added as one more `call`.
"""
from __future__ import annotations

import re

import harness

EXTENSIONS = (".proc", ".cm", ".aas48")


def _edit_entities(text: str, edits: dict, call: str | None) -> str:
    """Apply key edits to the top-level entities named in `edits` (and `call` to worldspawn)."""
    out, block, depth, start = [], [], 0, 0
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if depth == 0 and s == "{":
            # collect one top-level entity
            j, d = i, 0
            while True:
                t = lines[j].strip()
                if t == "{":
                    d += 1
                elif t == "}":
                    d -= 1
                    if d == 0:
                        break
                j += 1
            ent = lines[i:j + 1]
            keys = {m.group(1): m.group(2) for l in ent if (m := re.match(r'\s*"([^"]*)"\s+"([^"]*)"', l))}
            target = edits.get(keys.get("name", "")) or {}
            if keys.get("classname") == "worldspawn" and call:
                target = dict(target, call_levelshot=call)
            if target:
                body = []
                done = set()
                for l in ent:
                    m = re.match(r'(\s*)"([^"]*)"\s+"([^"]*)"', l)
                    if m and m.group(2) in target and l.count('"') == 4:
                        k = m.group(2)
                        if target[k] is not None:
                            body.append(f'"{k}" "{target[k]}"\n')
                        done.add(k)
                    else:
                        body.append(l)
                extra = [f'"{k}" "{v}"\n' for k, v in target.items() if k not in done and v is not None]
                body[1:1] = extra
                ent = body
            out += ent
            i = j + 1
            continue
        out.append(line)
        i += 1
    return "".join(out)


def prepare(slot: str, scene: dict) -> str:
    """Write the scene's map copy into the slot's savepath; returns the map name to load."""
    src = scene["from"].split("/", 1)[1]
    name = scene["name"]
    maps = harness.slot_game(slot) / "maps" / "game"
    maps.mkdir(parents=True, exist_ok=True)
    text = harness._unzip(f"maps/game/{src}.map").decode("latin-1")
    (maps / f"{name}.map").write_bytes(_edit_entities(text, scene.get("edit", {}), scene.get("call")).encode("latin-1"))
    for ext in EXTENSIONS:
        data = harness._unzip(f"maps/game/{src}{ext}")
        if data:
            (maps / f"{name}{ext}").write_bytes(data)
    if scene.get("script"):
        (maps / f"{name}.script").write_text(scene["script"] + "\n", encoding="latin-1")
    return name
