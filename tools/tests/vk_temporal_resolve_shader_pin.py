#!/usr/bin/env python3
"""Pin the standalone Vulkan temporal-resolve SPIR-V header to GLSL."""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "tools" / "build" / "spirv_to_header.py"
SHADER_DIR = REPO_ROOT / "src" / "renderer" / "Vulkan" / "shaders"
COMMITTED = SHADER_DIR / "temporal_resolve_spv.h"
SHADERS = [
    SHADER_DIR / "temporal_resolve.vert",
    SHADER_DIR / "temporal_resolve.frag",
    SHADER_DIR / "scene_scale.frag",
]


def main() -> int:
    sys.path.insert(0, str(GENERATOR.parent))
    import spirv_to_header  # noqa: E402

    if spirv_to_header.find_glslang(None) is None:
        print("vk_temporal_resolve_shader_pin: skipped (glslangValidator unavailable)")
        return 0
    if not COMMITTED.is_file():
        print(f"missing committed temporal shader header: {COMMITTED}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as temporary_directory:
        regenerated = pathlib.Path(temporary_directory) / COMMITTED.name
        result = subprocess.run(
            [
                sys.executable,
                str(GENERATOR),
                "--header-out",
                str(regenerated),
                "--guard",
                "__VK_TEMPORAL_RESOLVE_SPV_H__",
                *[str(shader) for shader in SHADERS],
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(
                "temporal shader regeneration failed:\n"
                f"{result.stdout}\n{result.stderr}",
                file=sys.stderr,
            )
            return 1
        normalize = lambda data: data.replace(b"\r\n", b"\n")
        if normalize(regenerated.read_bytes()) != normalize(COMMITTED.read_bytes()):
            shader_args = " ".join(
                shader.relative_to(REPO_ROOT).as_posix() for shader in SHADERS
            )
            print(
                "committed temporal shader header is stale; regenerate with:\n"
                "  python tools/build/spirv_to_header.py --header-out "
                "src/renderer/Vulkan/shaders/temporal_resolve_spv.h --guard "
                "__VK_TEMPORAL_RESOLVE_SPV_H__ "
                f"{shader_args}",
                file=sys.stderr,
            )
            return 1

    print("vk_temporal_resolve_shader_pin: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
