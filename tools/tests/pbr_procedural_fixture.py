#!/usr/bin/env python3
"""Regression checks for the licence-safe procedural PBR fixture generator."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "validation" / "generate_pbr_fixture.py"
TEMP_ROOT = ROOT / ".tmp"
VALIDATOR = ROOT / "tools" / "validation" / "openq4_validate.py"
WORKFLOWS = (
    ROOT / ".github" / "workflows" / "commit-validation.yml",
    ROOT / ".github" / "workflows" / "push-verification.yml",
)
EXPECTED_HASHES_16 = {
    "baseoq4/materials/openq4_pbr_procedural_fixture.mtr": (
        "ea096bcd6990dc9e690e036365965d69143ddc308de159ced363ad0910adfade"
    ),
    "baseoq4/textures/openq4/pbrtest/procedural_albedo.tga": (
        "c1eaa28c9aa511199bd03fee41d933816e384d15bbcc92fda570c6ebd5f6d9aa"
    ),
    "baseoq4/textures/openq4/pbrtest/procedural_normal.tga": (
        "81420b2a13bb77b45770917ccba12f7f048e3cc16e38338982deaee8d331f0b1"
    ),
    "baseoq4/textures/openq4/pbrtest/procedural_orm.tga": (
        "d6cc68d91332cfedd1cbd4ca51db72fbfe183468ead812f9b17f5a28967596c2"
    ),
}
SPEC = importlib.util.spec_from_file_location("generate_pbr_fixture", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


def expect_raises(exception: type[Exception], callback: Callable[[], object]) -> str:
    try:
        callback()
    except exception as exc:
        return str(exc)
    raise AssertionError(f"expected {exception.__name__}")


def decode_tga(path: Path) -> tuple[int, int, list[tuple[int, int, int]]]:
    data = path.read_bytes()
    assert len(data) >= 18
    assert data[0] == 0
    assert data[1] == 0
    assert data[2] == 2
    width = int.from_bytes(data[12:14], "little")
    height = int.from_bytes(data[14:16], "little")
    assert data[16] == 24
    assert data[17] == 0x20
    payload = data[18:]
    assert len(payload) == width * height * 3
    pixels = [
        (payload[index + 2], payload[index + 1], payload[index])
        for index in range(0, len(payload), 3)
    ]
    return width, height, pixels


def relative_file_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_generator_is_stdlib_and_original() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
    assert imports <= {
        "__future__",
        "argparse",
        "hashlib",
        "json",
        "math",
        "pathlib",
        "stat",
        "struct",
        "typing",
    }
    assert "no third-party texture, shader, or" in source
    assert "no external assets" in source
    assert "PIL" not in source
    assert "urllib" not in source
    assert "requests" not in source


def test_deterministic_fixture_and_manifest() -> None:
    TEMP_ROOT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=TEMP_ROOT, prefix="pbr-procedural-fixture-") as temporary:
        temporary_root = Path(temporary)
        first_root = temporary_root / "runtime-a"
        second_root = temporary_root / "runtime-b"
        first = FIXTURE.generate_fixture(first_root, size=16)
        second = FIXTURE.generate_fixture(second_root, size=16)

        assert relative_file_bytes(first_root) == relative_file_bytes(second_root)
        assert set(relative_file_bytes(first_root)) == {
            "baseoq4/materials/openq4_pbr_procedural_fixture.mtr",
            "baseoq4/textures/openq4/pbrtest/procedural_albedo.tga",
            "baseoq4/textures/openq4/pbrtest/procedural_normal.tga",
            "baseoq4/textures/openq4/pbrtest/procedural_orm.tga",
            "openq4-pbr-procedural-fixture.json",
        }

        manifest = json.loads(first["manifest"].read_text(encoding="utf-8"))
        assert manifest["stockMap"] == "maps/tools/mv2"
        assert manifest["benchmarkCase"] == "sp-mv2-interaction"
        assert manifest["materialOverride"] == "materials/openq4/pbr_test/procedural_packed"
        assert manifest["textureSize"] == [16, 16]
        assert "no third-party assets" in manifest["provenance"]
        assert "GNU GPL v3" in manifest["license"]
        assert ".tmp" in manifest["generatedAssetsPolicy"]
        assert manifest["files"] == EXPECTED_HASHES_16
        for relative, expected_hash in manifest["files"].items():
            actual_hash = hashlib.sha256((first_root / relative).read_bytes()).hexdigest()
            assert actual_hash == expected_hash
        binding = FIXTURE.verify_fixture(first_root, expected_size=16)
        assert binding["fixture"] == FIXTURE.FIXTURE_ID
        assert binding["materialOverride"] == FIXTURE.MATERIAL_NAME
        assert binding["textureSize"] == [16, 16]
        assert {record["path"] for record in binding["files"]} == set(EXPECTED_HASHES_16)

        original_orm = first["orm"].read_bytes()
        first["orm"].write_bytes(original_orm[:-1] + bytes((original_orm[-1] ^ 1,)))
        expect_raises(
            RuntimeError,
            lambda: FIXTURE.verify_fixture(first_root, expected_size=16),
        )
        first["orm"].write_bytes(original_orm)

        original_manifest = first["manifest"].read_bytes()
        changed_manifest = json.loads(original_manifest.decode("utf-8"))
        changed_manifest["benchmarkCase"] = "sp-storage1"
        first["manifest"].write_text(
            json.dumps(changed_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        expect_raises(
            RuntimeError,
            lambda: FIXTURE.verify_fixture(first_root, expected_size=16),
        )
        first["manifest"].write_bytes(original_manifest)
        first["manifest"].write_bytes(original_manifest + b"\n")
        expect_raises(
            RuntimeError,
            lambda: FIXTURE.verify_fixture(first_root, expected_size=16),
        )
        first["manifest"].write_bytes(original_manifest)
        assert FIXTURE.verify_fixture(first_root, expected_size=16) == binding

        material = first["material"].read_text(encoding="utf-8")
        assert "Original procedural openQ4 validation fixture" in material
        assert "bumpmap _flat" in material
        assert "diffusemap textures/openq4/pbrtest/procedural_albedo" in material
        assert "specularmap _black" in material
        assert "workflow metallicRoughness" in material
        assert "normalFormat tangentXYZ" in material
        assert "ormMap textures/openq4/pbrtest/procedural_orm" in material

        width, height, albedo = decode_tga(first["albedo"])
        assert (width, height) == (16, 16)
        assert len(set(albedo)) > 32
        _, _, normal = decode_tga(first["normal"])
        assert min(pixel[2] for pixel in normal) >= 250
        assert len({(pixel[0], pixel[1]) for pixel in normal}) >= 4
        _, _, orm = decode_tga(first["orm"])
        assert min(pixel[0] for pixel in orm) == 224
        assert max(pixel[0] for pixel in orm) == 255
        assert min(pixel[1] for pixel in orm) == 36
        assert max(pixel[1] for pixel in orm) == 220
        assert {pixel[2] for pixel in orm} == {20, 232}

        baseline_albedo = first["albedo"].read_bytes()
        expect_raises(FileExistsError, lambda: FIXTURE.generate_fixture(first_root, size=16))
        first["albedo"].write_bytes(b"modified")
        FIXTURE.generate_fixture(first_root, size=16, force=True)
        assert first["albedo"].read_bytes() == baseline_albedo


def test_output_scope_and_size_fail_closed() -> None:
    TEMP_ROOT.mkdir(exist_ok=True)
    expect_raises(ValueError, lambda: FIXTURE.generate_fixture(ROOT / "builddir" / "pbr-fixture"))
    expect_raises(ValueError, lambda: FIXTURE.generate_fixture(TEMP_ROOT))
    with tempfile.TemporaryDirectory(dir=TEMP_ROOT, prefix="pbr-procedural-fixture-") as temporary:
        root = Path(temporary) / "runtime"
        expect_raises(ValueError, lambda: FIXTURE.generate_fixture(root, size=12))


def test_nested_links_and_junctions_fail_closed() -> None:
    TEMP_ROOT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        dir=TEMP_ROOT, prefix="pbr-procedural-fixture-links-"
    ) as temporary:
        temporary_root = Path(temporary)
        hardlink_runtime = temporary_root / "runtime-hardlink"
        hardlink_runtime.mkdir()
        hardlink_outside = temporary_root / "outside-hardlink.tga"
        hardlink_outside.write_bytes(b"outside-hardlink-sentinel")
        hardlink_target = FIXTURE.fixture_paths(hardlink_runtime)["albedo"]
        hardlink_target.parent.mkdir(parents=True)
        try:
            os.link(hardlink_outside, hardlink_target)
        except (NotImplementedError, OSError):
            pass
        else:
            message = expect_raises(
                RuntimeError,
                lambda: FIXTURE.generate_fixture(
                    hardlink_runtime, size=16, force=True
                ),
            )
            assert "hard-linked" in message
            assert hardlink_outside.read_bytes() == b"outside-hardlink-sentinel"

        outside = temporary_root / "outside-symlink"
        outside.mkdir()
        sentinel = outside / "sentinel.txt"
        sentinel.write_text("unchanged", encoding="utf-8")
        runtime = temporary_root / "runtime-symlink"
        runtime.mkdir()
        nested_link = runtime / "baseoq4"
        try:
            os.symlink(outside, nested_link, target_is_directory=True)
        except (NotImplementedError, OSError):
            pass
        else:
            try:
                message = expect_raises(
                    RuntimeError,
                    lambda: FIXTURE.generate_fixture(runtime, size=16),
                )
                assert "link or junction" in message
                assert sentinel.read_text(encoding="utf-8") == "unchanged"
                assert list(outside.iterdir()) == [sentinel]
            finally:
                nested_link.unlink(missing_ok=True)

        if os.name != "nt":
            return
        junction_outside = temporary_root / "outside-junction"
        junction_outside.mkdir()
        junction_sentinel = junction_outside / "sentinel.txt"
        junction_sentinel.write_text("unchanged", encoding="utf-8")
        junction_runtime = temporary_root / "runtime-junction"
        junction_runtime.mkdir()
        junction = junction_runtime / "baseoq4"
        created = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(junction_outside)],
            capture_output=True,
            text=True,
            check=False,
        )
        if created.returncode != 0:
            return
        try:
            assert FIXTURE.is_link_or_junction(junction)
            message = expect_raises(
                RuntimeError,
                lambda: FIXTURE.generate_fixture(junction_runtime, size=16),
            )
            assert "link or junction" in message
            assert junction_sentinel.read_text(encoding="utf-8") == "unchanged"
            assert list(junction_outside.iterdir()) == [junction_sentinel]
        finally:
            os.rmdir(junction)


def test_validation_wiring() -> None:
    validator = VALIDATOR.read_text(encoding="utf-8")
    assert validator.count('root / "tools" / "tests" / "pbr_procedural_fixture.py"') == 1
    for workflow_path in WORKFLOWS:
        workflow = workflow_path.read_text(encoding="utf-8")
        assert workflow.count("tools/tests/pbr_procedural_fixture.py") == 2
        assert workflow.count("tools/validation/generate_pbr_fixture.py") == 1


def main() -> int:
    test_generator_is_stdlib_and_original()
    test_deterministic_fixture_and_manifest()
    test_output_scope_and_size_fail_closed()
    test_nested_links_and_junctions_fail_closed()
    test_validation_wiring()
    print("pbr_procedural_fixture: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
