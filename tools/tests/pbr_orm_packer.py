#!/usr/bin/env python3
"""Dependency-free regression checks for tools/assets/pack_pbr_orm.py."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "assets" / "pack_pbr_orm.py"
TEMP_ROOT = ROOT / ".tmp"
VALIDATOR = ROOT / "tools" / "validation" / "openq4_validate.py"
WORKFLOWS = (
    ROOT / ".github" / "workflows" / "commit-validation.yml",
    ROOT / ".github" / "workflows" / "push-verification.yml",
)
SPEC = importlib.util.spec_from_file_location("pack_pbr_orm", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PACKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKER)


class MemoryImage:
    """Minimal Pillow-compatible image used to keep this gate dependency-free."""

    def __init__(
        self,
        owner: "MemoryImageModule",
        size: tuple[int, int],
        bands: dict[str, tuple[int, ...]],
    ) -> None:
        self.owner = owner
        self.size = size
        self.width, self.height = size
        self.bands = {name: tuple(values) for name, values in bands.items()}
        expected = self.width * self.height
        if not self.bands or any(len(values) != expected for values in self.bands.values()):
            raise ValueError("invalid in-memory image")

    def __enter__(self) -> "MemoryImage":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def getbands(self) -> tuple[str, ...]:
        return tuple(self.bands)

    def getchannel(self, channel: str) -> "MemoryImage":
        return MemoryImage(self.owner, self.size, {"L": self.bands[channel]})

    def copy(self) -> "MemoryImage":
        return MemoryImage(self.owner, self.size, self.bands)

    def pixels(self) -> list[int] | list[tuple[int, ...]]:
        names = tuple(self.bands)
        if names == ("L",):
            return list(self.bands["L"])
        return [tuple(self.bands[name][index] for name in names) for index in range(self.width * self.height)]

    def save(self, path: Path, *, format: str) -> None:
        if format not in {"PNG", "TGA"}:
            raise AssertionError(f"unexpected fake output format {format}")
        resolved = Path(path).resolve()
        self.owner.images[resolved] = self.copy()
        Path(path).write_bytes(b"in-memory-image\n")


class MemoryImageModule:
    """In-memory image backend implementing only the packer's required API."""

    def __init__(self) -> None:
        self.images: dict[Path, MemoryImage] = {}

    def add(
        self,
        path: Path,
        bands: dict[str, list[int]],
        size: tuple[int, int] = (2, 1),
    ) -> None:
        path.write_bytes(b"in-memory-source\n")
        self.images[path.resolve()] = MemoryImage(
            self,
            size,
            {name: tuple(values) for name, values in bands.items()},
        )

    def open(self, path: Path) -> MemoryImage:
        return self.images[Path(path).resolve()].copy()

    def new(self, mode: str, size: tuple[int, int], *, color: int) -> MemoryImage:
        if mode != "L":
            raise AssertionError(f"unexpected fake image mode {mode}")
        return MemoryImage(self, size, {"L": (color,) * (size[0] * size[1])})

    def merge(self, mode: str, images: tuple[MemoryImage, ...]) -> MemoryImage:
        if mode != "RGB" or len(images) != 3:
            raise AssertionError("unexpected fake merge")
        if any(image.size != images[0].size for image in images):
            raise ValueError("size mismatch")
        return MemoryImage(
            self,
            images[0].size,
            {
                "R": images[0].bands["L"],
                "G": images[1].bands["L"],
                "B": images[2].bands["L"],
            },
        )

    def pixels(self, path: Path) -> list[int] | list[tuple[int, ...]]:
        return self.images[path.resolve()].pixels()


def expect_raises(exception: type[Exception], callback: Callable[[], object]) -> str:
    try:
        callback()
    except exception as exc:
        return str(exc)
    raise AssertionError(f"expected {exception.__name__}")


def test_channel_order_and_implicit_ao() -> None:
    TEMP_ROOT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=TEMP_ROOT, prefix="pbr-orm-packer-") as temporary:
        root = Path(temporary)
        images = MemoryImageModule()
        ao = root / "ao.fake"
        roughness = root / "roughness.fake"
        metallic = root / "metallic.fake"
        output = root / "packed.tga"
        images.add(ao, {"L": [3, 13]})
        images.add(roughness, {"L": [7, 17]})
        images.add(metallic, {"L": [11, 19]})

        PACKER.pack_orm(ao, roughness, metallic, output, False, image_module=images)
        assert images.pixels(output) == [(3, 7, 11), (13, 17, 19)]

        white_ao_output = root / "packed-implicit-ao.png"
        PACKER.pack_orm(None, roughness, metallic, white_ao_output, False, image_module=images)
        assert images.pixels(white_ao_output) == [(255, 7, 11), (255, 17, 19)]


def test_explicit_stored_channel_not_luminance() -> None:
    TEMP_ROOT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=TEMP_ROOT, prefix="pbr-orm-packer-") as temporary:
        root = Path(temporary)
        images = MemoryImageModule()
        roughness = root / "roughness-rgb.fake"
        metallic = root / "metallic-rgb.fake"
        images.add(
            roughness,
            {"R": [5, 15], "G": [105, 115], "B": [205, 215]},
        )
        images.add(
            metallic,
            {"R": [7, 17], "G": [107, 117], "B": [207, 217]},
        )

        red_output = root / "packed-red.tga"
        PACKER.pack_orm(None, roughness, metallic, red_output, False, image_module=images)
        assert images.pixels(red_output) == [(255, 5, 7), (255, 15, 17)]

        green_output = root / "packed-green.tga"
        PACKER.pack_orm(
            None,
            roughness,
            metallic,
            green_output,
            False,
            input_channel="g",
            image_module=images,
        )
        assert images.pixels(green_output) == [(255, 105, 107), (255, 115, 117)]
        message = expect_raises(
            ValueError,
            lambda: PACKER.pack_orm(
                None,
                roughness,
                metallic,
                root / "packed-alpha.tga",
                False,
                input_channel="a",
                image_module=images,
            ),
        )
        assert "does not contain stored A data" in message

        palette = root / "roughness-palette.fake"
        images.add(palette, {"P": [1, 2]})
        message = expect_raises(
            ValueError,
            lambda: PACKER.pack_orm(
                None,
                palette,
                metallic,
                root / "packed-palette.tga",
                False,
                image_module=images,
            ),
        )
        assert "does not contain stored R data" in message


def test_fail_closed_inputs_and_output() -> None:
    TEMP_ROOT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=TEMP_ROOT, prefix="pbr-orm-packer-") as temporary:
        root = Path(temporary)
        images = MemoryImageModule()
        roughness = root / "roughness.fake"
        metallic = root / "metallic.fake"
        output = root / "packed.png"
        images.add(roughness, {"L": [7, 17]})
        images.add(metallic, {"L": [11]}, (1, 1))

        expect_raises(
            ValueError,
            lambda: PACKER.pack_orm(None, roughness, metallic, output, False, image_module=images),
        )
        images.add(metallic, {"L": [11, 19]})
        output.write_bytes(b"existing")
        expect_raises(
            FileExistsError,
            lambda: PACKER.pack_orm(None, roughness, metallic, output, False, image_module=images),
        )
        expect_raises(ValueError, lambda: PACKER.validate_output(root / "packed.dds", False))
        expect_raises(ValueError, lambda: PACKER.normalize_data_channel("luminance"))


def test_module_load_does_not_require_pillow() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "image.convert(\"L\")" not in source
    assert "image.convert('L')" not in source
    # Pillow must remain a function-local, optional command-line dependency.
    assert source.index("def pillow_image_module()") < source.index("from PIL import Image")


def test_optional_pillow_backend_when_available() -> None:
    try:
        images = PACKER.pillow_image_module()
    except RuntimeError:
        return
    TEMP_ROOT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=TEMP_ROOT, prefix="pbr-orm-pillow-") as temporary:
        root = Path(temporary)
        roughness = root / "roughness.png"
        metallic = root / "metallic.png"
        output = root / "packed.tga"
        roughness_image = images.new("RGB", (2, 1))
        roughness_image.putdata([(5, 105, 205), (15, 115, 215)])
        roughness_image.save(roughness, format="PNG")
        metallic_image = images.new("RGB", (2, 1))
        metallic_image.putdata([(7, 107, 207), (17, 117, 217)])
        metallic_image.save(metallic, format="PNG")

        PACKER.pack_orm(None, roughness, metallic, output, False, image_module=images)
        with images.open(output) as packed:
            assert list(packed.getdata()) == [(255, 5, 7), (255, 15, 17)]


def test_validation_wiring() -> None:
    validator = VALIDATOR.read_text(encoding="utf-8")
    assert validator.count('root / "tools" / "tests" / "pbr_orm_packer.py"') == 1
    for workflow_path in WORKFLOWS:
        workflow = workflow_path.read_text(encoding="utf-8")
        # Once in py_compile and once as an executed dependency-free gate.
        assert workflow.count("tools/tests/pbr_orm_packer.py") == 2
        assert workflow.count("tools/assets/pack_pbr_orm.py") == 1


def main() -> int:
    test_channel_order_and_implicit_ao()
    test_explicit_stored_channel_not_luminance()
    test_fail_closed_inputs_and_output()
    test_module_load_does_not_require_pillow()
    test_optional_pillow_backend_when_available()
    test_validation_wiring()
    print("pbr_orm_packer: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
