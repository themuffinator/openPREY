#!/usr/bin/env python3
"""Read and validate a game-library layer manifest (layer.json).

A game layer is a companion repository that extends openQ4-game into a
separate mod game directory without replacing any of its files. The layer
contributes whole new sources only; openQ4 links them together with the
unchanged openQ4-game objects, so a layer build is always "the current openQ4
game plus the layer". openQ4-game-awakening, which targets the Quake 4: The
Awakening expansion (q4xbase), is the first layer.

layer.json:

    {
      "format": 1,
      "id": "awakening",                   identifier, [a-z][a-z0-9_]*
      "gameDir": "q4xbase",                mod game directory the modules serve
      "sources": {                         repository-relative source roots
        "shared": "src/shared",            compiled into both game modules
        "game": "src/game",                single-player module only
        "mpgame": "src/mpgame"             multiplayer module only
      },
      "mod": {                             mod.json identity for gameDir
        "name": "...", "version": "x.y.z", "releaseDate": "YYYY-MM-DD",
        "website": "...", "author": "..."
      }
    }

usage:
    game_layer.py field <layer-root> <gameDir|id|name|version>
    game_layer.py mod-json <layer-root> --openq4-version <x.y.z> --out <path>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


LAYER_MANIFEST_NAME = "layer.json"
LAYER_FORMAT = 1
LAYER_SOURCE_TREES = ("shared", "game", "mpgame")
# which staged game trees each layer source tree is compiled into
LAYER_TREE_MODULES = {
    "shared": ("game", "mpgame"),
    "game": ("game",),
    "mpgame": ("mpgame",),
}
MOD_FIELDS = ("name", "version", "releaseDate", "website", "author")
RESERVED_GAME_DIRS = {"q4base", "baseoq4", "q4mp", "base"}
# Game directories that packages carry beside baseoq4 when their layer was built. Each holds
# exactly its two game modules (plus their Windows .pdb files) and the mod.json below.
# Awakening SP is compiled into the canonical game_sp. Its user-supplied
# campaign assets and obsolete layer DLLs are never package collateral.
PACKAGED_LAYER_GAME_DIRS = ()
RETIRED_LAYER_GAME_DIRS = ("q4xbase",)
LAYER_MOD_JSON_FIELDS = ("layer", "version", "requiredopenQ4Version")

_IDENTIFIER = re.compile(r"[a-z][a-z0-9_]*\Z")
_GAME_DIR = re.compile(r"[a-z0-9][a-z0-9_\-]*\Z")
_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")


class LayerError(RuntimeError):
    pass


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def load_layer(layer_root: Path) -> dict:
    """Load layer.json and return it with resolved absolute source roots."""
    if layer_root.is_symlink():
        raise LayerError(f"layer root must not be a symlink: {layer_root}")
    layer_root = layer_root.resolve()
    manifest_path = layer_root / LAYER_MANIFEST_NAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise LayerError(f"layer manifest not found: {manifest_path}")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LayerError(f"cannot read {manifest_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise LayerError(f"{manifest_path} must hold a JSON object")

    if data.get("format") != LAYER_FORMAT:
        raise LayerError(f"{manifest_path}: unsupported format {data.get('format')!r} (expected {LAYER_FORMAT})")

    layer_id = data.get("id")
    if not isinstance(layer_id, str) or not _IDENTIFIER.match(layer_id):
        raise LayerError(f"{manifest_path}: 'id' must match [a-z][a-z0-9_]*")

    game_dir = data.get("gameDir")
    if not isinstance(game_dir, str) or not _GAME_DIR.match(game_dir) or game_dir in RESERVED_GAME_DIRS:
        raise LayerError(f"{manifest_path}: 'gameDir' must be one lower-case directory name other than {sorted(RESERVED_GAME_DIRS)}")

    sources = data.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise LayerError(f"{manifest_path}: 'sources' must map at least one of {LAYER_SOURCE_TREES}")
    resolved_sources: dict[str, Path] = {}
    for tree, rel in sources.items():
        if tree not in LAYER_SOURCE_TREES:
            raise LayerError(f"{manifest_path}: unknown source tree '{tree}' (expected {LAYER_SOURCE_TREES})")
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute():
            raise LayerError(f"{manifest_path}: source tree '{tree}' must be a repository-relative path")
        raw = layer_root / rel
        if raw.is_symlink():
            raise LayerError(f"{manifest_path}: source tree '{tree}' must not be a symlink")
        path = raw.resolve()
        if not _is_relative_to(path, layer_root) or path == layer_root:
            raise LayerError(f"{manifest_path}: source tree '{tree}' escapes the layer repository")
        if not path.is_dir():
            raise LayerError(f"{manifest_path}: source tree '{tree}' not found: {path}")
        resolved_sources[tree] = path

    mod = data.get("mod")
    if not isinstance(mod, dict):
        raise LayerError(f"{manifest_path}: 'mod' must be an object with {MOD_FIELDS}")
    for field in MOD_FIELDS:
        value = mod.get(field)
        if not isinstance(value, str) or not value.strip():
            raise LayerError(f"{manifest_path}: mod.{field} must be a non-empty string")
    if not _VERSION.match(mod["version"]):
        raise LayerError(f"{manifest_path}: mod.version must be major.minor.patch")

    return {
        "root": layer_root,
        "id": layer_id,
        "gameDir": game_dir,
        "sources": resolved_sources,
        "mod": {field: mod[field] for field in MOD_FIELDS},
    }


def render_mod_json(layer: dict, openq4_version: str) -> str:
    if not _VERSION.match(openq4_version):
        raise LayerError(f"openQ4 version must be major.minor.patch, got '{openq4_version}'")
    manifest = dict(layer["mod"])
    # the layer is rebuilt with each engine, so it needs exactly this engine
    manifest["requiredopenQ4Version"] = openq4_version
    manifest["layer"] = layer["id"]
    return json.dumps(manifest, indent=2) + "\n"


def read_layer_mod_json(path: Path) -> dict:
    """Read the mod.json that render_mod_json wrote into a layer's game directory.

    Its "version" is the layer's own; "requiredopenQ4Version" is the engine the layer was
    built with. A base game's mod.json, which has no "layer", is not a layer's.
    """
    if path.is_symlink() or not path.is_file():
        raise LayerError(f"{path}: a layer mod.json must be a regular file")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LayerError(f"{path}: unreadable layer mod.json") from exc
    if not isinstance(manifest, dict):
        raise LayerError(f"{path}: a layer mod.json must be an object")
    for field in LAYER_MOD_JSON_FIELDS:
        value = manifest.get(field)
        if not isinstance(value, str) or not value.strip():
            raise LayerError(f"{path}: a layer mod.json needs a non-empty {field!r}")
    if not _VERSION.match(manifest["requiredopenQ4Version"]):
        raise LayerError(f"{path}: requiredopenQ4Version must be major.minor.patch")
    return manifest


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="openQ4 game-library layer manifests")
    sub = parser.add_subparsers(dest="command", required=True)
    field = sub.add_parser("field", help="print one manifest field")
    field.add_argument("layer_root", type=Path)
    field.add_argument("name", choices=("gameDir", "id", "name", "version"))
    mod_json = sub.add_parser("mod-json", help="write the mod.json for the layer's game directory")
    mod_json.add_argument("layer_root", type=Path)
    mod_json.add_argument("--openq4-version", required=True)
    mod_json.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv[1:])

    try:
        layer = load_layer(args.layer_root)
        if args.command == "field":
            value = layer["mod"][args.name] if args.name in ("name", "version") else layer[args.name]
            print(value)
        else:
            text = render_mod_json(layer, args.openq4_version)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            if not args.out.is_file() or args.out.read_text(encoding="utf-8") != text:
                args.out.write_text(text, encoding="utf-8")
    except LayerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
