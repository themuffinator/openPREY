#!/usr/bin/env python3
"""Verify a fail-closed CPU/GPU renderer benchmark evidence pair.

The two inputs must be real ``renderer_gameplay_benchmark.py`` JSON reports
captured from the same clean checkout, staged runtime, backend, cases, and
windowed display contract.  The first report is the ``r_gpuSkinning 0`` CPU
reference and the second is the ``r_gpuSkinning 1`` run.  This verifier reads
the retained engine logs and screenshots instead of trusting summary fields.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# Must equal renderer_gameplay_benchmark.REPORT_SCHEMA_VERSION; the static
# contract in tools/tests/renderer_gpu_skinning.py fails when the two drift.
REPORT_SCHEMA_VERSION = 5
EVIDENCE_SCHEMA_VERSION = 1
EVIDENCE_KIND = "openq4-gpu-skinning-paired-evidence"
DEFAULT_MINIMUM_CPU_P95_IMPROVEMENT = 1.0
DEFAULT_IMAGE_RMS_THRESHOLD = 2.0
DEFAULT_IMAGE_MAX_THRESHOLD = 24

FALLBACK_NAMES = (
    "disabled",
    "backendUnavailable",
    "missingBindPose",
    "missingSkinVertices",
    "vertexCount",
    "residualWeights",
    "jointCount",
    "jointIndex",
    "malformedWeights",
    "skinScale",
    "unsupportedMaterial",
    "unsupportedPass",
    "stencilVolume",
    "decalOverlay",
    "paletteAllocation",
    "stalePalette",
)
SKINNING_COUNTER_NAMES = (
    "enabled",
    "generation",
    "packed",
    "exact",
    "attempts",
    "admitted",
    "prepared",
    "cpuSkinVerts",
    "cpuSkinUs",
    "positionOnlyVerts",
    "positionOnlyUs",
    "preparedVertices",
    "paletteUploads",
    "paletteJoints",
    "paletteBytes",
    "cumulative",
)

SKINNING_MARKER = re.compile(
    r"^GPU skinning:\s*(?P<counters>[^\r\n]+)$", re.MULTILINE
)
FALLBACK_MARKER = re.compile(
    r"^GPU skinning fallbacks:\s*(?P<counters>[^\r\n]+)$", re.MULTILINE
)
COUNTER = re.compile(r"(?P<name>[A-Za-z][A-Za-z0-9]*)=(?P<value>\d+)")
TIMING_MARKER = re.compile(
    r"^OPENQ4_FRAME_TIMING_V1\s+map=(?P<map>\S+)\s+"
    r"backend=(?P<backend>\S+)\s+profile=(?P<profile>\S+)\s+"
    r"cpuSamples=(?P<cpuSamples>\d+)\s+cpuP50Us=(?P<cpuP50Us>\d+)\s+"
    r"cpuP95Us=(?P<cpuP95Us>\d+)\s+cpuP99Us=(?P<cpuP99Us>\d+)\s+"
    r"gpuAvailable=(?P<gpuAvailable>[01])\s+gpuSamples=(?P<gpuSamples>\d+)\s+"
    r"gpuP50Us=(?P<gpuP50Us>-?\d+)\s+gpuP95Us=(?P<gpuP95Us>-?\d+)\s+"
    r"gpuP99Us=(?P<gpuP99Us>-?\d+)$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class RoleRecord:
    result: dict[str, Any]
    role: dict[str, Any]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def current_sha256(path: Path) -> str | None:
    try:
        return sha256(path)
    except OSError:
        return None


def load_report(
    path: Path, label: str, failures: list[str]
) -> tuple[dict[str, Any], str | None]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        failures.append(f"{label}: cannot read UTF-8 JSON report: {exc}")
        return {}, None
    digest = hashlib.sha256(raw).hexdigest()
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        failures.append(f"{label}: cannot read UTF-8 JSON report: {exc}")
        return {}, digest
    if not isinstance(decoded, dict):
        failures.append(f"{label}: report root is not an object")
        return {}, digest
    return decoded, digest


def require_clean_report(report: dict[str, Any], label: str, failures: list[str]) -> None:
    if report.get("schemaVersion") != REPORT_SCHEMA_VERSION:
        failures.append(
            f"{label}: unsupported renderer benchmark schema {report.get('schemaVersion')!r}"
        )
    if report.get("status") != "pass":
        failures.append(f"{label}: report status is not pass")
    if report.get("dryRun") is not False:
        failures.append(f"{label}: dry-run/planned evidence is not admissible")
    if report.get("runtimeVerificationFailures") != []:
        failures.append(f"{label}: staged runtime changed during capture")
    if report.get("budgetEnforced") is not True:
        failures.append(f"{label}: per-map CPU/GPU budget was not enforced")
    git = report.get("git")
    if not isinstance(git, dict):
        failures.append(f"{label}: Git provenance is missing")
    else:
        if re.fullmatch(r"[0-9a-fA-F]{40,64}", str(git.get("revision", ""))) is None:
            failures.append(f"{label}: Git revision is missing or malformed")
        if git.get("dirty") is not False:
            failures.append(f"{label}: evidence must come from a clean checkout")
    runtime = report.get("runtime")
    if not isinstance(runtime, dict) or not isinstance(runtime.get("files"), list) or not runtime["files"]:
        failures.append(f"{label}: staged runtime inventory is missing")
    else:
        paths: set[str] = set()
        for record in runtime["files"]:
            if not isinstance(record, dict):
                failures.append(f"{label}: malformed staged runtime file record")
                continue
            raw_path = record.get("path")
            if (
                not isinstance(raw_path, str)
                or not raw_path
                or Path(raw_path).is_absolute()
                or ".." in Path(raw_path).parts
                or raw_path in paths
                or not isinstance(record.get("size"), int)
                or isinstance(record.get("size"), bool)
                or record["size"] < 0
                or re.fullmatch(r"[0-9a-f]{64}", str(record.get("sha256", ""))) is None
            ):
                failures.append(f"{label}: malformed/duplicate staged runtime file record")
                continue
            paths.add(raw_path)


def normalized_launch_cvars(
    report: dict[str, Any], label: str, failures: list[str]
) -> tuple[dict[str, str], str | None]:
    metadata = report.get("metadata")
    if not isinstance(metadata, dict):
        return {}, None
    raw = metadata.get("launchCvars")
    if not isinstance(raw, dict):
        return {}, None
    normalized: dict[str, str] = {}
    for key, value in raw.items():
        folded = str(key).casefold()
        if folded in normalized:
            failures.append(f"{label}: duplicate case-insensitive launch CVar {key!r}")
        normalized[folded] = str(value)
    skinning = normalized.pop("r_gpuskinning", None)
    return normalized, skinning


def require_pair_identity(
    cpu: dict[str, Any], gpu: dict[str, Any], failures: list[str]
) -> None:
    for key, label in (
        ("git", "Git provenance"),
        ("runtime", "staged runtime inventory"),
        ("budgetContract", "renderer budget contract"),
    ):
        if cpu.get(key) != gpu.get(key):
            failures.append(f"pair: {label} differs")

    cpu_metadata = cpu.get("metadata")
    gpu_metadata = gpu.get("metadata")
    if not isinstance(cpu_metadata, dict) or not isinstance(gpu_metadata, dict):
        failures.append("pair: benchmark metadata is missing")
        return
    cpu_identity = dict(cpu_metadata)
    gpu_identity = dict(gpu_metadata)
    for identity in (cpu_identity, gpu_identity):
        identity.pop("generated", None)
        identity.pop("launchCvars", None)
    for key in sorted(set(cpu_identity) | set(gpu_identity)):
        if cpu_identity.get(key) != gpu_identity.get(key):
            failures.append(f"pair: metadata identity differs for {key}")
    render_api = cpu_metadata.get("renderApi")
    if render_api not in ("gl", "vk"):
        failures.append(f"pair: unsupported renderer API identity {render_api!r}")

    cpu_cvars, cpu_skinning = normalized_launch_cvars(cpu, "CPU", failures)
    gpu_cvars, gpu_skinning = normalized_launch_cvars(gpu, "GPU", failures)
    if cpu_cvars != gpu_cvars:
        failures.append("pair: non-skinning launch CVar identity differs")
    if cpu_skinning != "0":
        failures.append("CPU report must record launchCvars.r_gpuSkinning=0")
    if gpu_skinning != "1":
        failures.append("GPU report must record launchCvars.r_gpuSkinning=1")


def collect_roles(
    report: dict[str, Any], label: str, failures: list[str]
) -> dict[tuple[str, str], RoleRecord]:
    results = report.get("results")
    if not isinstance(results, list) or not results:
        failures.append(f"{label}: results are missing or empty")
        return {}
    records: dict[tuple[str, str], RoleRecord] = {}
    for result in results:
        if not isinstance(result, dict):
            failures.append(f"{label}: malformed result")
            continue
        case_id = result.get("id")
        if not isinstance(case_id, str) or not case_id:
            failures.append(f"{label}: result case id is missing")
            continue
        if result.get("status") != "pass":
            failures.append(f"{label}/{case_id}: result is not a pass")
        if result.get("display") != "windowed":
            failures.append(f"{label}/{case_id}: capture was not windowed")
        display_contract = result.get("displayContract")
        if (
            not isinstance(display_contract, dict)
            or display_contract.get("width") != 1280
            or display_contract.get("height") != 720
            or display_contract.get("contractId") != "bordered-window-1280x720-v1"
        ):
            failures.append(f"{label}/{case_id}: canonical display contract is missing")
        roles = result.get("roles")
        if not isinstance(roles, list) or not roles:
            failures.append(f"{label}/{case_id}: role evidence is missing")
            continue
        for role in roles:
            if not isinstance(role, dict) or not isinstance(role.get("role"), str):
                failures.append(f"{label}/{case_id}: malformed role evidence")
                continue
            role_name = role["role"]
            key = (case_id, role_name)
            if key in records:
                failures.append(f"{label}/{case_id}/{role_name}: duplicate role evidence")
                continue
            if role.get("status") != "pass" or role.get("missing") != []:
                failures.append(f"{label}/{case_id}/{role_name}: role is not a clean pass")
            if role.get("failureDiagnostics") != []:
                failures.append(f"{label}/{case_id}/{role_name}: failure diagnostics were retained")
            if role.get("exitCode") != 0 or role.get("timedOut") is not False:
                failures.append(f"{label}/{case_id}/{role_name}: process did not exit cleanly")
            warnings = role.get("warnings")
            if (
                not isinstance(warnings, dict)
                or not warnings
                or any(
                    not isinstance(value, int) or isinstance(value, bool) or value != 0
                    for value in warnings.values()
                )
            ):
                failures.append(f"{label}/{case_id}/{role_name}: warning counters are not clean")
            budget = role.get("budgetEvidence")
            if (
                not isinstance(budget, dict)
                or budget.get("status") != "pass"
                or budget.get("failures") != []
            ):
                failures.append(f"{label}/{case_id}/{role_name}: timing budget evidence is not a pass")
            records[key] = RoleRecord(result, role)
    return records


def require_result_identity(
    key: tuple[str, str], cpu: RoleRecord, gpu: RoleRecord, failures: list[str]
) -> None:
    identity_fields = (
        "id",
        "mode",
        "map",
        "budgetMap",
        "expectedBackend",
        "renderApi",
        "displayContract",
        "tier",
        "maxfps",
        "swapInterval",
        "display",
        "shadowPreset",
        "renderer",
    )
    for field in identity_fields:
        if cpu.result.get(field) != gpu.result.get(field):
            failures.append(f"{key[0]}/{key[1]}: result identity differs for {field}")
    backend = cpu.result.get("expectedBackend")
    api = cpu.result.get("renderApi")
    expected = "opengl" if api == "gl" else "vulkan" if api == "vk" else None
    if backend != expected:
        failures.append(f"{key[0]}/{key[1]}: backend/renderApi binding is inconsistent")


def verified_artifact(
    report_path: Path,
    role: dict[str, Any],
    kind: str,
    label: str,
    failures: list[str],
) -> Path | None:
    raw_artifacts = role.get("artifacts")
    if not isinstance(raw_artifacts, list):
        failures.append(f"{label}: artifact inventory is missing")
        return None
    matches = [
        item
        for item in raw_artifacts
        if isinstance(item, dict) and item.get("kind") == kind
    ]
    if len(matches) != 1:
        failures.append(f"{label}: expected exactly one {kind} artifact")
        return None
    record = matches[0]
    raw_path = record.get("path")
    if not isinstance(raw_path, str) or not raw_path or Path(raw_path).is_absolute():
        failures.append(f"{label}: {kind} artifact path is not a safe relative path")
        return None
    report_dir = report_path.parent.resolve()
    candidate = (report_dir / raw_path).resolve()
    try:
        candidate.relative_to(report_dir)
    except ValueError:
        failures.append(f"{label}: {kind} artifact escapes the report directory")
        return None
    if not candidate.is_file() or candidate.is_symlink():
        failures.append(f"{label}: {kind} artifact is missing or linked")
        return None
    actual_size = candidate.stat().st_size
    actual_hash = sha256(candidate)
    if record.get("size") != actual_size or record.get("sha256") != actual_hash:
        failures.append(f"{label}: {kind} artifact hash/size differs from its report")
        return None
    return candidate


def unique_marker(
    pattern: re.Pattern[str], text: str, name: str, label: str, failures: list[str]
) -> re.Match[str] | None:
    matches = list(pattern.finditer(text))
    unique = {match.group(0) for match in matches}
    if not matches:
        failures.append(f"{label}: {name} marker is missing")
        return None
    if len(unique) != 1:
        failures.append(f"{label}: conflicting {name} markers were retained")
        return None
    return matches[-1]


def parse_skinning_log(
    text: str, enabled: bool, label: str, failures: list[str]
) -> dict[str, Any] | None:
    skin_match = unique_marker(SKINNING_MARKER, text, "GPU skinning", label, failures)
    fallback_match = unique_marker(
        FALLBACK_MARKER, text, "GPU skinning fallback", label, failures
    )
    timing_match = unique_marker(TIMING_MARKER, text, "frame timing", label, failures)
    if skin_match is None or fallback_match is None or timing_match is None:
        return None
    counters = parse_counter_inventory(
        skin_match.group("counters"), SKINNING_COUNTER_NAMES, "skinning", label, failures
    )
    if counters is None:
        return None
    if counters["enabled"] != int(enabled):
        failures.append(f"{label}: runtime skinning enabled marker does not match the report")
    if counters["cumulative"] != 1:
        failures.append(f"{label}: runtime marker is not the cumulative evidence contract")
    if counters["generation"] <= 0:
        failures.append(f"{label}: runtime contract generation is invalid")
    if counters["exact"] > counters["packed"]:
        failures.append(f"{label}: exact packed-vertex count exceeds pack attempts")
    if counters["cpuSkinVerts"] < counters["positionOnlyVerts"]:
        failures.append(f"{label}: position-only vertices exceed total CPU-skinned vertices")
    if enabled:
        if counters["attempts"] <= 0 or counters["admitted"] <= 0 or counters["prepared"] <= 0:
            failures.append(f"{label}: GPU work was not attempted, admitted, and prepared")
        if counters["admitted"] != counters["prepared"]:
            failures.append(f"{label}: admitted/prepared surface counters differ")
        if (
            counters["preparedVertices"] <= 0
            or counters["paletteUploads"] <= 0
            or counters["paletteJoints"] <= 0
            or counters["paletteBytes"] <= 0
        ):
            failures.append(f"{label}: GPU vertices/joint-palette upload counters are empty")
        if counters["paletteUploads"] != counters["prepared"]:
            failures.append(f"{label}: prepared/palette-upload counters differ")
        if counters["paletteBytes"] != counters["paletteJoints"] * 12 * 4:
            failures.append(f"{label}: joint-palette byte accounting is inconsistent")
        if counters["exact"] <= 0:
            failures.append(f"{label}: exact four-weight work was not observed")
        if counters["positionOnlyVerts"] <= 0:
            failures.append(f"{label}: retained CPU position work was not observed")
    else:
        if counters["admitted"] != 0 or counters["prepared"] != 0:
            failures.append(f"{label}: disabled CPU reference admitted GPU work")
        if any(
            counters[name] != 0
            for name in (
                "preparedVertices",
                "paletteUploads",
                "paletteJoints",
                "paletteBytes",
                "positionOnlyVerts",
                "positionOnlyUs",
            )
        ):
            failures.append(f"{label}: disabled CPU reference retained GPU/position-only work")
        if counters["cpuSkinVerts"] <= 0:
            failures.append(f"{label}: CPU reference did not observe skeletal work")

    fallback_values = parse_counter_inventory(
        fallback_match.group("counters"), FALLBACK_NAMES, "fallback", label, failures
    )
    if fallback_values is None:
        return None

    timing = {name: value for name, value in timing_match.groupdict().items()}
    for name in (
        "cpuSamples",
        "cpuP50Us",
        "cpuP95Us",
        "cpuP99Us",
        "gpuAvailable",
        "gpuSamples",
        "gpuP50Us",
        "gpuP95Us",
        "gpuP99Us",
    ):
        timing[name] = int(timing[name])
    if not (
        timing["cpuSamples"] > 0
        and timing["cpuP50Us"] >= 0
        and timing["cpuP50Us"] <= timing["cpuP95Us"] <= timing["cpuP99Us"]
    ):
        failures.append(f"{label}: CPU timing marker is invalid")
    if timing["gpuAvailable"]:
        if not (
            timing["gpuSamples"] > 0
            and timing["gpuP50Us"] >= 0
            and timing["gpuP50Us"] <= timing["gpuP95Us"] <= timing["gpuP99Us"]
        ):
            failures.append(f"{label}: available GPU timing marker is invalid")
    elif not (
        timing["gpuSamples"] == 0
        and timing["gpuP50Us"] == -1
        and timing["gpuP95Us"] == -1
        and timing["gpuP99Us"] == -1
    ):
        failures.append(f"{label}: unavailable GPU timing marker is invalid")
    if enabled:
        if fallback_values["disabled"] != 0:
            failures.append(f"{label}: enabled run recorded disabled fallbacks")
    return {"counters": counters, "fallbacks": fallback_values, "timing": timing}


def parse_counter_inventory(
    raw: str,
    expected_names: tuple[str, ...],
    inventory_name: str,
    label: str,
    failures: list[str],
) -> dict[str, int] | None:
    tokens = raw.split()
    pairs: list[tuple[str, str]] = []
    for token in tokens:
        match = COUNTER.fullmatch(token)
        if match is None:
            failures.append(f"{label}: malformed {inventory_name} counter token {token!r}")
            continue
        pairs.append((match.group("name"), match.group("value")))
    values = {name: int(value) for name, value in pairs}
    duplicate = len(pairs) != len(values)
    if duplicate:
        failures.append(f"{label}: duplicate {inventory_name} counter")
    missing = sorted(set(expected_names) - set(values))
    unknown = sorted(set(values) - set(expected_names))
    if missing or unknown:
        failures.append(
            f"{label}: {inventory_name} inventory differs (missing={missing}, unknown={unknown})"
        )
    return values if not missing and not unknown and not duplicate else None


def budget_measurement(
    role: dict[str, Any], label: str, failures: list[str]
) -> dict[str, Any] | None:
    budget = role.get("budgetEvidence")
    measurement = budget.get("measurement") if isinstance(budget, dict) else None
    if not isinstance(measurement, dict):
        failures.append(f"{label}: recorded timing measurement is missing")
        return None
    return measurement


def marker_measurement(parsed: dict[str, Any]) -> dict[str, Any]:
    timing = parsed["timing"]
    return {
        "map": timing["map"],
        "backend": timing["backend"],
        "profile": timing["profile"],
        "cpu": {
            "samples": timing["cpuSamples"],
            "p50Us": timing["cpuP50Us"],
            "p95Us": timing["cpuP95Us"],
            "p99Us": timing["cpuP99Us"],
        },
        "gpu": {
            "available": timing["gpuAvailable"] == 1,
            "samples": timing["gpuSamples"],
            "p50Us": timing["gpuP50Us"],
            "p95Us": timing["gpuP95Us"],
            "p99Us": timing["gpuP99Us"],
        },
    }


def load_tga_rgb(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    if len(data) < 18:
        raise ValueError("TGA header is truncated")
    id_length, color_map_type, image_type = data[0], data[1], data[2]
    if color_map_type != 0 or image_type not in (2, 3):
        raise ValueError("only uncompressed true-color/grayscale TGA is supported")
    width = struct.unpack_from("<H", data, 12)[0]
    height = struct.unpack_from("<H", data, 14)[0]
    bits = data[16]
    if width <= 0 or height <= 0 or bits not in (24, 32):
        raise ValueError(f"invalid TGA dimensions/depth {width}x{height}x{bits}")
    pixel_size = bits // 8
    start = 18 + id_length
    end = start + width * height * pixel_size
    if end > len(data):
        raise ValueError("TGA pixel payload is truncated")
    source = data[start:end]
    rgb = bytearray(width * height * 3)
    for pixel in range(width * height):
        src = pixel * pixel_size
        dst = pixel * 3
        if image_type == 3:
            rgb[dst : dst + 3] = source[src : src + 1] * 3
        else:
            rgb[dst : dst + 3] = bytes((source[src + 2], source[src + 1], source[src]))
    return width, height, bytes(rgb)


def compare_images(cpu_path: Path, gpu_path: Path) -> dict[str, Any]:
    cpu_width, cpu_height, cpu_pixels = load_tga_rgb(cpu_path)
    gpu_width, gpu_height, gpu_pixels = load_tga_rgb(gpu_path)
    if (cpu_width, cpu_height) != (gpu_width, gpu_height):
        return {
            "status": "dimension-mismatch",
            "cpuSize": f"{cpu_width}x{cpu_height}",
            "gpuSize": f"{gpu_width}x{gpu_height}",
        }
    total_squared = 0
    maximum = 0
    differing = 0
    for cpu_value, gpu_value in zip(cpu_pixels, gpu_pixels):
        delta = abs(cpu_value - gpu_value)
        if delta:
            differing += 1
            total_squared += delta * delta
            maximum = max(maximum, delta)
    return {
        "status": "compared",
        "size": f"{cpu_width}x{cpu_height}",
        "rms": round(math.sqrt(total_squared / max(1, len(cpu_pixels))), 6),
        "maxDelta": maximum,
        "differingChannels": differing,
        "cpuSha256": sha256(cpu_path),
        "gpuSha256": sha256(gpu_path),
    }


def verify_pair(
    cpu_path: Path,
    gpu_path: Path,
    minimum_improvement: float,
    image_rms_threshold: float,
    image_max_threshold: int,
) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    cpu_report, cpu_digest = load_report(cpu_path, "CPU", failures)
    gpu_report, gpu_digest = load_report(gpu_path, "GPU", failures)
    require_clean_report(cpu_report, "CPU", failures)
    require_clean_report(gpu_report, "GPU", failures)
    require_pair_identity(cpu_report, gpu_report, failures)
    cpu_roles = collect_roles(cpu_report, "CPU", failures)
    gpu_roles = collect_roles(gpu_report, "GPU", failures)
    if set(cpu_roles) != set(gpu_roles):
        failures.append(
            "pair: case/role inventory differs "
            f"(CPU-only={sorted(set(cpu_roles) - set(gpu_roles))}, "
            f"GPU-only={sorted(set(gpu_roles) - set(cpu_roles))})"
        )

    comparisons: list[dict[str, Any]] = []
    observed_stencil_fallbacks = 0
    for key in sorted(set(cpu_roles) & set(gpu_roles)):
        cpu_record = cpu_roles[key]
        gpu_record = gpu_roles[key]
        label = f"{key[0]}/{key[1]}"
        require_result_identity(key, cpu_record, gpu_record, failures)

        cpu_log_path = verified_artifact(
            cpu_path, cpu_record.role, "engineLog", f"CPU/{label}", failures
        )
        gpu_log_path = verified_artifact(
            gpu_path, gpu_record.role, "engineLog", f"GPU/{label}", failures
        )
        cpu_shot = verified_artifact(
            cpu_path, cpu_record.role, "screenshot", f"CPU/{label}", failures
        )
        gpu_shot = verified_artifact(
            gpu_path, gpu_record.role, "screenshot", f"GPU/{label}", failures
        )

        cpu_skin = None
        gpu_skin = None
        if cpu_log_path is not None:
            cpu_skin = parse_skinning_log(
                cpu_log_path.read_text(encoding="utf-8", errors="replace"),
                False,
                f"CPU/{label}",
                failures,
            )
        if gpu_log_path is not None:
            gpu_skin = parse_skinning_log(
                gpu_log_path.read_text(encoding="utf-8", errors="replace"),
                True,
                f"GPU/{label}",
                failures,
            )
        if gpu_skin is not None:
            observed_stencil_fallbacks += gpu_skin["fallbacks"].get("stencilVolume", 0)

        expected_map = str(cpu_record.result.get("budgetMap", "")).casefold()
        expected_backend = str(cpu_record.result.get("expectedBackend", "")).casefold()
        cpu_metadata = cpu_report.get("metadata", {})
        expected_profile = str(cpu_metadata.get("benchmarkPreset", "")).casefold()
        for parsed, run_label in ((cpu_skin, "CPU"), (gpu_skin, "GPU")):
            if parsed is None:
                continue
            timing = parsed["timing"]
            if timing["map"].casefold() != expected_map:
                failures.append(f"{run_label}/{label}: timing marker map identity differs")
            if timing["backend"].casefold() != expected_backend:
                failures.append(f"{run_label}/{label}: timing marker backend identity differs")
            if timing["profile"].casefold() != expected_profile:
                failures.append(f"{run_label}/{label}: timing marker profile identity differs")

        cpu_measurement = budget_measurement(
            cpu_record.role, f"CPU/{label}", failures
        )
        gpu_measurement = budget_measurement(
            gpu_record.role, f"GPU/{label}", failures
        )
        for parsed, recorded, run_label in (
            (cpu_skin, cpu_measurement, "CPU"),
            (gpu_skin, gpu_measurement, "GPU"),
        ):
            if parsed is not None and recorded is not None:
                retained = marker_measurement(parsed)
                if retained != recorded:
                    failures.append(
                        f"{run_label}/{label}: retained timing marker disagrees with report measurement"
                    )

        cpu = cpu_measurement.get("cpu") if isinstance(cpu_measurement, dict) else None
        gpu = gpu_measurement.get("cpu") if isinstance(gpu_measurement, dict) else None
        cpu_p95 = cpu.get("p95Us") if isinstance(cpu, dict) else None
        gpu_p95 = gpu.get("p95Us") if isinstance(gpu, dict) else None
        for value, run_label in ((cpu_p95, "CPU"), (gpu_p95, "GPU")):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                failures.append(f"{run_label}/{label}: recorded CPU P95 is missing or invalid")
        improvement = None
        if (
            isinstance(cpu_p95, int)
            and not isinstance(cpu_p95, bool)
            and cpu_p95 > 0
            and isinstance(gpu_p95, int)
            and not isinstance(gpu_p95, bool)
            and gpu_p95 > 0
        ):
            improvement = 100.0 * (cpu_p95 - gpu_p95) / cpu_p95
            if improvement + 1e-9 < minimum_improvement:
                failures.append(
                    f"{label}: CPU P95 improvement {improvement:.3f}% is below "
                    f"the required {minimum_improvement:.3f}%"
                )

        image = None
        if cpu_shot is not None and gpu_shot is not None:
            try:
                image = compare_images(cpu_shot, gpu_shot)
            except (OSError, ValueError) as exc:
                failures.append(f"{label}: screenshot comparison failed: {exc}")
            else:
                if image.get("status") != "compared":
                    failures.append(f"{label}: screenshot dimensions differ")
                elif (
                    image["rms"] > image_rms_threshold
                    or image["maxDelta"] > image_max_threshold
                ):
                    failures.append(
                        f"{label}: screenshot delta rms={image['rms']} max={image['maxDelta']} "
                        f"exceeds {image_rms_threshold}/{image_max_threshold}"
                    )
                display = cpu_record.result.get("displayContract", {})
                expected_size = f"{display.get('width')}x{display.get('height')}"
                if image.get("status") == "compared" and image.get("size") != expected_size:
                    failures.append(
                        f"{label}: screenshot size {image.get('size')} differs from {expected_size}"
                    )

        comparisons.append(
            {
                "case": key[0],
                "role": key[1],
                "backend": cpu_record.result.get("expectedBackend"),
                "cpuP95Us": cpu_p95,
                "gpuP95Us": gpu_p95,
                "cpuP95ImprovementPercent": (
                    round(improvement, 6) if improvement is not None else None
                ),
                "cpuSkinning": cpu_skin,
                "gpuSkinning": gpu_skin,
                "image": image,
            }
        )

    if comparisons and observed_stencil_fallbacks <= 0:
        failures.append("pair: no classified CPU stencil-volume fallback was observed")

    for path, recorded_digest, label in (
        (cpu_path, cpu_digest, "CPU"),
        (gpu_path, gpu_digest, "GPU"),
    ):
        if recorded_digest is not None and current_sha256(path) != recorded_digest:
            failures.append(f"{label}: report changed during verification")

    payload = {
        "schemaVersion": EVIDENCE_SCHEMA_VERSION,
        "kind": EVIDENCE_KIND,
        "status": "pass" if not failures else "fail",
        "cpuReport": {"path": str(cpu_path), "sha256": cpu_digest},
        "gpuReport": {"path": str(gpu_path), "sha256": gpu_digest},
        "requirements": {
            "minimumCpuP95ImprovementPercent": minimum_improvement,
            "imageRmsThreshold": image_rms_threshold,
            "imageMaxThreshold": image_max_threshold,
        },
        "comparisons": comparisons,
        "failures": failures,
    }
    return payload, failures


def artifact_record(path: Path, root: Path, kind: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "path": path.relative_to(root).as_posix(),
        "size": path.stat().st_size,
        "sha256": sha256(path),
    }


def write_test_tga(
    path: Path, pixel: tuple[int, int, int], width: int = 1280, height: int = 720
) -> None:
    if width <= 0 or height <= 0 or any(value < 0 or value > 255 for value in pixel):
        raise ValueError("invalid self-test TGA parameters")
    header = bytearray(18)
    header[2] = 2
    struct.pack_into("<HH", header, 12, width, height)
    header[16] = 24
    red, green, blue = pixel
    bgr = bytes((blue, green, red)) * (width * height)
    path.write_bytes(header + bgr)


def build_test_report(root: Path, enabled: bool, cpu_p95: int) -> Path:
    root.mkdir()
    log = root / "engine.log"
    screenshot = root / "frame.tga"
    fallback_values = {name: 0 for name in FALLBACK_NAMES}
    fallback_values["stencilVolume"] = 1
    skin_line = (
        "GPU skinning: enabled=%d cumulative=1 generation=2 packed=100 exact=100 attempts=%d "
        "admitted=%d prepared=%d preparedVertices=%d paletteUploads=%d paletteJoints=%d "
        "paletteBytes=%d cpuSkinVerts=1000 cpuSkinUs=%d "
        "positionOnlyVerts=%d positionOnlyUs=%d"
        % (
            int(enabled),
            10 if enabled else 0,
            8 if enabled else 0,
            8 if enabled else 0,
            1000 if enabled else 0,
            8 if enabled else 0,
            64 if enabled else 0,
            3072 if enabled else 0,
            2000 if enabled else 9000,
            1000 if enabled else 0,
            1500 if enabled else 0,
        )
    )
    fallback_line = "GPU skinning fallbacks: " + " ".join(
        f"{name}={fallback_values[name]}" for name in FALLBACK_NAMES
    )
    timing_line = (
        "OPENQ4_FRAME_TIMING_V1 map=game/airdefense2 backend=opengl profile=baseline "
        f"cpuSamples=600 cpuP50Us=7000 cpuP95Us={cpu_p95} cpuP99Us={cpu_p95 + 2000} "
        "gpuAvailable=1 gpuSamples=598 gpuP50Us=5000 gpuP95Us=7000 gpuP99Us=8000"
    )
    log.write_text(f"{skin_line}\n{fallback_line}\n{timing_line}\n", encoding="utf-8")
    write_test_tga(screenshot, (10, 20, 30))

    role = {
        "role": "sp",
        "status": "pass",
        "exitCode": 0,
        "timedOut": False,
        "missing": [],
        "failureDiagnostics": [],
        "warnings": {"rendererError": 0},
        "budgetEvidence": {
            "status": "pass",
            "failures": [],
            "measurement": {
                "map": "game/airdefense2",
                "backend": "opengl",
                "profile": "baseline",
                "cpu": {
                    "samples": 600,
                    "p50Us": 7000,
                    "p95Us": cpu_p95,
                    "p99Us": cpu_p95 + 2000,
                },
                "gpu": {
                    "available": True,
                    "samples": 598,
                    "p50Us": 5000,
                    "p95Us": 7000,
                    "p99Us": 8000,
                },
            },
        },
        "artifacts": [
            artifact_record(log, root, "engineLog"),
            artifact_record(screenshot, root, "screenshot"),
        ],
    }
    result = {
        "id": "sp-airdefense2-auto-fps240-vsync0-windowed-shadowstencil-gl",
        "mode": "SP",
        "map": "game/airdefense2",
        "budgetMap": "game/airdefense2",
        "expectedBackend": "opengl",
        "renderApi": "gl",
        "displayContract": {
            "contractId": "bordered-window-1280x720-v1",
            "width": 1280,
            "height": 720,
        },
        "purpose": "self-test",
        "tier": "auto",
        "maxfps": "240",
        "swapInterval": "0",
        "display": "windowed",
        "shadowPreset": "stencil",
        "renderer": "best",
        "status": "pass",
        "roles": [role],
    }
    report = {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "dryRun": False,
        "git": {"policy": "current-openq4-head-and-dirty-state-v1", "revision": "a" * 40, "dirty": False},
        "runtime": {"path": ".install", "executable": "openQ4-client_x64.exe", "files": [{"path": "openQ4-client_x64.exe", "size": 1, "sha256": "0" * 64}]},
        "runtimeVerificationFailures": [],
        "budgetContract": {"contractId": "self-test", "sha256": "1" * 64},
        "budgetEnforced": True,
        "metadata": {
            "profile": "smoke",
            "benchmarkPreset": "baseline",
            "renderApi": "gl",
            "autoexecDelayMs": 1000,
            "settleFrames": 360,
            "sampleFrames": 600,
            "sampleMsec": 0,
            "profileCvars": {},
            "profileExecCommands": [],
            "execCommands": [],
            "budgetDisplayContract": {"contractId": "bordered-window-1280x720-v1"},
            "launchCvars": {"r_gpuSkinning": "1" if enabled else "0"},
        },
        "results": [result],
    }
    path = root / "renderer_gameplay_benchmark_report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def run_self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="openq4-gpu-skinning-evidence-") as raw:
        root = Path(raw)
        cpu = build_test_report(root / "cpu", False, 10000)
        gpu = build_test_report(root / "gpu", True, 8500)
        payload, failures = verify_pair(cpu, gpu, 10.0, 0.0, 0)
        if failures or payload["status"] != "pass":
            raise AssertionError(f"valid synthetic pair failed: {failures}")

        decoded = json.loads(gpu.read_text(encoding="utf-8"))
        decoded["git"]["dirty"] = True
        gpu.write_text(json.dumps(decoded), encoding="utf-8")
        _, dirty_failures = verify_pair(cpu, gpu, 10.0, 0.0, 0)
        if not any("clean checkout" in failure for failure in dirty_failures):
            raise AssertionError("dirty synthetic evidence did not fail closed")
    print("GPU skinning paired evidence self-test: PASS")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cpu_report", nargs="?", help="r_gpuSkinning=0 benchmark JSON")
    parser.add_argument("gpu_report", nargs="?", help="r_gpuSkinning=1 benchmark JSON")
    parser.add_argument(
        "--minimum-cpu-p95-improvement",
        type=float,
        default=DEFAULT_MINIMUM_CPU_P95_IMPROVEMENT,
        help="Minimum required reduction for every paired CPU P95 (percent).",
    )
    parser.add_argument(
        "--image-rms-threshold",
        type=float,
        default=DEFAULT_IMAGE_RMS_THRESHOLD,
        help="Maximum backend-local CPU/GPU screenshot RMS channel delta.",
    )
    parser.add_argument(
        "--image-max-threshold",
        type=int,
        default=DEFAULT_IMAGE_MAX_THRESHOLD,
        help="Maximum backend-local CPU/GPU screenshot channel delta.",
    )
    parser.add_argument("--output", help="Optional path for the verification JSON payload.")
    parser.add_argument("--self-test", action="store_true", help="Run dependency-free synthetic fixtures.")
    args = parser.parse_args(argv)
    if args.minimum_cpu_p95_improvement < 0 or not math.isfinite(args.minimum_cpu_p95_improvement):
        parser.error("--minimum-cpu-p95-improvement must be finite and non-negative")
    if args.image_rms_threshold < 0 or not math.isfinite(args.image_rms_threshold):
        parser.error("--image-rms-threshold must be finite and non-negative")
    if not (0 <= args.image_max_threshold <= 255):
        parser.error("--image-max-threshold must be in the range 0..255")
    if not args.self_test and (not args.cpu_report or not args.gpu_report):
        parser.error("cpu_report and gpu_report are required unless --self-test is used")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        run_self_test()
        if not args.cpu_report and not args.gpu_report:
            return 0
    if not args.cpu_report or not args.gpu_report:
        return 0
    cpu_path = Path(args.cpu_report).resolve()
    gpu_path = Path(args.gpu_report).resolve()
    payload, failures = verify_pair(
        cpu_path,
        gpu_path,
        args.minimum_cpu_p95_improvement,
        args.image_rms_threshold,
        args.image_max_threshold,
    )
    encoded = json.dumps(payload, indent=2) + "\n"
    if args.output:
        Path(args.output).resolve().write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    for failure in failures:
        print(f"error: {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
