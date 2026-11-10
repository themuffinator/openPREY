#!/usr/bin/env python3
"""Generate a deterministic, licence-safe temporary PBR runtime fixture.

The texture pixels and material declaration are original openQ4 procedural
test data produced entirely by this file; no third-party texture, shader, or
material asset is read or copied.  The fixture is intentionally constrained to
the repository's ignored ``.tmp`` tree and is meant to override stock geometry
on ``maps/tools/mv2`` during opt-in validation.  Generated files remain covered
by the openQ4 repository licence and must not be committed as content assets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import stat
import struct
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPO_TEMP_ROOT = ROOT / ".tmp"
FIXTURE_SCHEMA_VERSION = 1
FIXTURE_ID = "openq4-procedural-pbr-packed-orm"
DEFAULT_TEXTURE_SIZE = 64
MATERIAL_NAME = "materials/openq4/pbr_test/procedural_packed"
STOCK_MAP = "maps/tools/mv2"
BENCHMARK_CASE = "sp-mv2-interaction"
TEXTURE_PREFIX = "textures/openq4/pbrtest/procedural"
MATERIAL_QPATH = "baseoq4/materials/openq4_pbr_procedural_fixture.mtr"
MANIFEST_NAME = "openq4-pbr-procedural-fixture.json"


def is_link_or_junction(path: Path) -> bool:
    """Recognize POSIX links and Windows junction/reparse-point entries."""
    is_junction = getattr(path, "is_junction", None)
    if path.is_symlink() or bool(is_junction and is_junction()):
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def validate_ordinary_ancestry(path: Path, anchor: Path, label: str) -> None:
    """Reject every existing link/reparse entry from anchor through path."""
    anchor_absolute = anchor.absolute()
    candidate = path.absolute()
    try:
        relative = candidate.relative_to(anchor_absolute)
    except ValueError as exc:
        raise ValueError(f"{label} escapes its required root: {candidate}") from exc

    current = anchor_absolute
    if is_link_or_junction(current):
        raise RuntimeError(f"{label} ancestry contains a link or junction: {current}")
    for part in relative.parts:
        current /= part
        if is_link_or_junction(current):
            raise RuntimeError(f"{label} ancestry contains a link or junction: {current}")


def validate_contained_target(runtime_root: Path, target: Path) -> Path:
    """Resolve one output immediately before use and keep it inside runtime_root."""
    root = runtime_root.resolve(strict=False)
    validate_ordinary_ancestry(target, root, "fixture output")
    resolved = target.resolve(strict=False)
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(
            f"fixture output resolves outside runtime root {root}: {resolved}"
        ) from exc
    if not relative.parts:
        raise RuntimeError("fixture output may not replace the runtime root")
    return resolved


def reject_hardlinked_file(path: Path, label: str) -> None:
    if path.exists() and path.stat().st_nlink != 1:
        raise RuntimeError(f"{label} must not be a hard-linked file: {path}")


def validate_runtime_root(runtime_root: Path) -> Path:
    validate_ordinary_ancestry(runtime_root, REPO_TEMP_ROOT, "runtime root")
    temporary_root = REPO_TEMP_ROOT.resolve()
    resolved = runtime_root.resolve(strict=False)
    try:
        relative = resolved.relative_to(temporary_root)
    except ValueError as exc:
        raise ValueError(
            f"--runtime-root must be a child of the repository .tmp directory: {temporary_root}"
        ) from exc
    if not relative.parts:
        raise ValueError("--runtime-root must name a child directory below .tmp, not .tmp itself")
    if resolved.exists() and not resolved.is_dir():
        raise RuntimeError(f"runtime root is not a directory: {resolved}")
    return resolved


def validate_size(size: int) -> None:
    if size < 8 or size > 2048 or size & (size - 1):
        raise ValueError("--size must be a power of two from 8 through 2048")


def fixture_paths(runtime_root: Path) -> dict[str, Path]:
    return {
        "albedo": runtime_root / f"baseoq4/{TEXTURE_PREFIX}_albedo.tga",
        "normal": runtime_root / f"baseoq4/{TEXTURE_PREFIX}_normal.tga",
        "orm": runtime_root / f"baseoq4/{TEXTURE_PREFIX}_orm.tga",
        "material": runtime_root / MATERIAL_QPATH,
        "manifest": runtime_root / MANIFEST_NAME,
    }


def validate_targets(runtime_root: Path, paths: dict[str, Path], force: bool) -> None:
    existing: list[Path] = []
    for path in paths.values():
        resolved = validate_contained_target(runtime_root, path)
        if resolved.exists() and not resolved.is_file():
            raise RuntimeError(f"fixture output is not a regular file: {resolved}")
        reject_hardlinked_file(resolved, "fixture output")
        if resolved.exists() and not force:
            existing.append(resolved)
    if existing:
        listed = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"fixture output already exists: {listed} (pass --force to replace it)")


def tga_bytes(width: int, height: int, pixels: list[tuple[int, int, int]]) -> bytes:
    if width <= 0 or height <= 0 or len(pixels) != width * height:
        raise ValueError("invalid TGA dimensions or pixel count")
    # Uncompressed 24-bit true-colour TGA, top-left origin.  TGA stores BGR.
    header = struct.pack(
        "<BBBHHBHHHHBB",
        0,
        0,
        2,
        0,
        0,
        0,
        0,
        0,
        width,
        height,
        24,
        0x20,
    )
    payload = bytearray()
    for red, green, blue in pixels:
        if not all(0 <= channel <= 255 for channel in (red, green, blue)):
            raise ValueError("TGA channel value is outside 0..255")
        payload.extend((blue, green, red))
    return header + payload


def procedural_pixels(size: int) -> dict[str, list[tuple[int, int, int]]]:
    """Create visibly distinct albedo, tangent-XYZ normal, and RGB ORM maps."""

    validate_size(size)
    tile = max(2, size // 8)
    albedo: list[tuple[int, int, int]] = []
    normal: list[tuple[int, int, int]] = []
    orm: list[tuple[int, int, int]] = []
    for y in range(size):
        for x in range(size):
            checker = ((x // tile) + (y // tile)) & 1
            grain = (x * 17 + y * 31) % 23
            if checker:
                albedo.append((184 + grain, 62 + grain // 2, 24 + grain // 3))
            else:
                albedo.append((30 + grain // 3, 86 + grain, 142 + grain // 2))

            span = tile - 1
            nx = -24 + ((x % tile) * 48 // span)
            ny = -24 + ((y % tile) * 48 // span)
            nz = math.isqrt(max(0, 127 * 127 - nx * nx - ny * ny))
            normal.append((128 + nx, 128 + ny, min(255, 128 + nz)))

            ambient_occlusion = 224 + ((x * 5 + y * 3) % 32)
            roughness = 36 + (x * 184 // (size - 1))
            metallic = 232 if checker else 20
            orm.append((ambient_occlusion, roughness, metallic))
    return {"albedo": albedo, "normal": normal, "orm": orm}


def material_text() -> str:
    return f"""// Original procedural openQ4 validation fixture; no external assets.
// Generated below .tmp by tools/validation/generate_pbr_fixture.py. Do not ship.
{MATERIAL_NAME}
{{
    bumpmap _flat
    diffusemap {TEXTURE_PREFIX}_albedo
    specularmap _black

    pbr {{
        workflow metallicRoughness
        albedoMap {TEXTURE_PREFIX}_albedo
        normalMap {TEXTURE_PREFIX}_normal
        normalFormat tangentXYZ
        ormMap {TEXTURE_PREFIX}_orm
        metallic 1.0
        roughness 1.0
        ao 1.0
        normalScale 1.0
    }}
}}
"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_payloads(size: int) -> dict[str, bytes]:
    """Return the complete canonical generated payload for one texture size."""
    pixels = procedural_pixels(size)
    return {
        "albedo": tga_bytes(size, size, pixels["albedo"]),
        "normal": tga_bytes(size, size, pixels["normal"]),
        "orm": tga_bytes(size, size, pixels["orm"]),
        "material": material_text().encode("utf-8"),
    }


def canonical_file_hashes(size: int) -> dict[str, str]:
    paths = fixture_paths(Path("."))
    payloads = fixture_payloads(size)
    return {
        paths[name].as_posix(): hashlib.sha256(payload).hexdigest()
        for name, payload in payloads.items()
    }


def fixture_manifest(size: int, files: dict[str, str]) -> dict[str, Any]:
    return {
        "schemaVersion": FIXTURE_SCHEMA_VERSION,
        "fixture": FIXTURE_ID,
        "provenance": (
            "Original deterministic pixels and material text generated only by "
            "tools/validation/generate_pbr_fixture.py; no third-party assets are incorporated."
        ),
        "license": "Covered by the openQ4 repository GNU GPL v3 licence.",
        "generatedAssetsPolicy": "Temporary validation output below .tmp; do not commit as content.",
        "stockMap": STOCK_MAP,
        "benchmarkCase": BENCHMARK_CASE,
        "materialOverride": MATERIAL_NAME,
        "textureSize": [size, size],
        "files": dict(sorted(files.items())),
    }


def verify_fixture(runtime_root: Path, expected_size: int = DEFAULT_TEXTURE_SIZE) -> dict[str, Any]:
    """Verify the canonical fixture identity and every generated byte before use."""
    root = validate_runtime_root(runtime_root)
    if not root.is_dir():
        raise FileNotFoundError(f"fixture runtime root does not exist: {root}")
    validate_size(expected_size)
    paths = fixture_paths(root)
    resolved_paths: dict[str, Path] = {}
    for name, path in paths.items():
        resolved = validate_contained_target(root, path)
        if not resolved.is_file():
            raise FileNotFoundError(f"fixture file is missing or not regular: {resolved}")
        reject_hardlinked_file(resolved, "fixture file")
        resolved_paths[name] = resolved

    try:
        manifest_bytes = resolved_paths["manifest"].read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"fixture manifest is unreadable or malformed: {resolved_paths['manifest']}"
        ) from exc
    if not isinstance(manifest, dict):
        raise RuntimeError("fixture manifest root must be an object")

    expected_payloads = fixture_payloads(expected_size)
    expected_hashes = {
        paths[name].relative_to(root).as_posix(): hashlib.sha256(payload).hexdigest()
        for name, payload in expected_payloads.items()
    }
    expected_manifest = fixture_manifest(expected_size, expected_hashes)
    if manifest != expected_manifest:
        raise RuntimeError("fixture manifest identity or canonical file inventory differs")
    expected_manifest_bytes = (
        json.dumps(expected_manifest, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    if manifest_bytes != expected_manifest_bytes:
        raise RuntimeError("fixture manifest bytes differ from the canonical manifest")

    file_records: list[dict[str, Any]] = []
    for name in sorted(expected_payloads):
        path = validate_contained_target(root, paths[name])
        relative = path.relative_to(root).as_posix()
        actual_bytes = path.read_bytes()
        actual_hash = hashlib.sha256(actual_bytes).hexdigest()
        expected_hash = expected_hashes[relative]
        if actual_hash != expected_hash or actual_bytes != expected_payloads[name]:
            raise RuntimeError(f"fixture file differs from canonical generated bytes: {relative}")
        file_records.append(
            {"path": relative, "size": len(actual_bytes), "sha256": actual_hash}
        )

    return {
        "schemaVersion": FIXTURE_SCHEMA_VERSION,
        "fixture": FIXTURE_ID,
        "materialOverride": MATERIAL_NAME,
        "stockMap": STOCK_MAP,
        "benchmarkCase": BENCHMARK_CASE,
        "textureSize": [expected_size, expected_size],
        "manifest": {
            "path": MANIFEST_NAME,
            "size": len(manifest_bytes),
            "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        },
        "files": file_records,
    }


def generate_fixture(
    runtime_root: Path, size: int = DEFAULT_TEXTURE_SIZE, force: bool = False
) -> dict[str, Path]:
    root = validate_runtime_root(runtime_root)
    validate_size(size)
    paths = fixture_paths(root)
    validate_targets(root, paths, force)
    for path in paths.values():
        resolved = validate_contained_target(root, path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        validate_contained_target(root, resolved)

    payloads = fixture_payloads(size)
    for name, payload in payloads.items():
        path = validate_contained_target(root, paths[name])
        reject_hardlinked_file(path, "fixture output")
        path.write_bytes(payload)

    files = {
        path.relative_to(root).as_posix(): sha256(path)
        for name, path in paths.items()
        if name != "manifest"
    }
    manifest = fixture_manifest(size, files)
    manifest_path = validate_contained_target(root, paths["manifest"])
    reject_hardlinked_file(manifest_path, "fixture output")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-root",
        required=True,
        type=Path,
        help="existing or new runtime root below the repository .tmp directory",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=DEFAULT_TEXTURE_SIZE,
        help=f"power-of-two texture size (default: {DEFAULT_TEXTURE_SIZE})",
    )
    parser.add_argument("--force", action="store_true", help="replace only this generator's existing files")
    args = parser.parse_args()
    outputs = generate_fixture(args.runtime_root, args.size, args.force)
    print(f"wrote procedural PBR fixture: {outputs['manifest']}")
    print(f"stock map: {STOCK_MAP}")
    print(f"material override: {MATERIAL_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
