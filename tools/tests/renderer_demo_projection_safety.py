#!/usr/bin/env python3
"""Guard finite render-demo payloads and fail-closed decal projection."""

from __future__ import annotations

import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def require(source: str, token: str, label: str) -> None:
    if token not in source:
        raise AssertionError(f"{label} is missing {token!r}")


def dot(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def finite_vec3(value: tuple[float, float, float]) -> bool:
    return all(math.isfinite(component) for component in value)


def project_texture_point(
    position: tuple[float, float, float],
    projection_origin: tuple[float, float, float],
    plane_normal: tuple[float, float, float],
    plane_distance: float,
    parallel: bool,
) -> tuple[float, float, float] | None:
    if not finite_vec3(position):
        return None
    if parallel:
        return position
    direction = tuple(position[index] - projection_origin[index] for index in range(3))
    denominator = dot(plane_normal, direction)
    numerator = -(dot(plane_normal, position) + plane_distance)
    if not math.isfinite(denominator) or denominator == 0.0:
        return None
    scale = numerator / denominator
    if not math.isfinite(scale):
        return None
    projected = tuple(position[index] + scale * direction[index] for index in range(3))
    return projected if finite_vec3(projected) else None


def validate_projection_model() -> None:
    projected = project_texture_point((1.0, 2.0, 3.0), (0.0, 0.0, 10.0), (0.0, 0.0, 1.0), 0.0, False)
    if projected is None or abs(projected[2]) > 1e-6:
        raise AssertionError("decal projection model failed a finite plane intersection")
    if project_texture_point((1.0, 2.0, 3.0), (0.0, 0.0, 3.0), (0.0, 0.0, 1.0), 0.0, False) is not None:
        raise AssertionError("decal projection model accepted a parallel ray")
    if project_texture_point((math.nan, 2.0, 3.0), (0.0, 0.0, 10.0), (0.0, 0.0, 1.0), 0.0, True) is not None:
        raise AssertionError("parallel decal projection accepted a non-finite point")
    if project_texture_point((1.0, 2.0, math.inf), (0.0, 0.0, 10.0), (0.0, 0.0, 1.0), 0.0, False) is not None:
        raise AssertionError("perspective decal projection accepted a non-finite point")
    if project_texture_point((1.0, 2.0, 3.0), (0.0, 0.0, 10.0), (0.0, 0.0, 1.0), 0.0, True) != (1.0, 2.0, 3.0):
        raise AssertionError("parallel decal projection changed a finite source point")


def validate_source_contract() -> None:
    decal = read("src/renderer/ModelDecal.cpp")
    packed = read("src/renderer/Model_md5r.cpp")
    gui = read("src/renderer/GuiModel.cpp")

    for token in (
        "bool R_IsFiniteDecalDemoDrawVert",
        "memset( vert.color2, 0, sizeof( vert.color2 ) );",
        "R_IsFiniteDecalDemoDrawVert( decal->tri.verts[vertIndex] )",
        "std::isfinite( decal->vertDepthFade[vertIndex] )",
        "std::isfinite( decal->vertLifeSpan[vertIndex] )",
        "const idVec3 position",
        "R_IsFiniteDecalProjectionPoint( position )",
        "idVec3 texturePoint = position;",
        "if ( !localInfo.parallel )",
        ".RayIntersection( position, dir, scale )",
        "!std::isfinite( scale )",
        "R_IsFiniteDecalProjectionPoint( texturePoint )",
        "!std::isfinite( fw[j].s ) || !std::isfinite( fw[j].t )",
        "if ( !projectionValid )",
    ):
        require(decal, token, "classic decal safety")

    for token in (
        "const idVec3 position",
        "!std::isfinite( position.x )",
        "idVec3 texturePoint = position;",
        "if ( !localInfo.parallel )",
        ".RayIntersection( position, dir, scale )",
        "!std::isfinite( scale )",
        "!std::isfinite( texturePoint.x )",
        "!std::isfinite( fw[pointNum].s ) || !std::isfinite( fw[pointNum].t )",
        "if ( !projectionValid )",
        "decodedMaterialFlags.AssureSize( meshCount, static_cast<byte>( 0 ) );",
    ):
        require(packed, token, "packed decal/cache safety")

    for token in (
        "static bool R_IsFiniteGuiDemoDrawVert",
        "static bool R_IsFiniteGuiDemoColor",
        "verts[j].color2[0] = verts[j].color2[1] = verts[j].color2[2] = verts[j].color2[3] = 255;",
        "R_IsFiniteGuiDemoDrawVert( verts[j] )",
        "R_IsFiniteGuiDemoColor( surf->color )",
        'R_RejectGuiModelDemo( demo, "non-finite vertex payload" )',
        'R_RejectGuiModelDemo( demo, "non-finite surface color" )',
    ):
        require(gui, token, "GUI render-demo safety")


def main() -> None:
    validate_projection_model()
    validate_source_contract()
    require(read("tools/validation/openq4_validate.py"), "renderer_demo_projection_safety.py", "renderer safety validation wiring")
    print("renderer demo/projection safety: ok")


if __name__ == "__main__":
    main()
