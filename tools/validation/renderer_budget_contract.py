#!/usr/bin/env python3
"""Versioned per-map CPU/GPU renderer budget contracts and evidence checks.

This module deliberately owns no renderer implementation.  It validates the
backend-neutral timing marker emitted by ``rendererBenchmarkCapture`` and is
shared by the gameplay benchmark and retail-PK4 evidence harnesses.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


CONTRACT_SCHEMA_VERSION = 1
CONTRACT_KIND = "openq4-renderer-per-map-budgets"
TIME_UNIT = "microseconds"
MARKER_PREFIX = "OPENQ4_FRAME_TIMING_V1"
DEFAULT_CONTRACT_PATH = Path(__file__).with_name("renderer_per_map_budgets.json")
SUPPORTED_BACKENDS = ("opengl", "vulkan")

_ROOT_KEYS = {"schemaVersion", "kind", "contractId", "timeUnit", "budgets"}
_BUDGET_KEYS = {"id", "map", "backend", "profile", "minimumSamples", "cpu", "gpu"}
_MINIMUM_SAMPLE_KEYS = {"cpu", "gpu"}
_CPU_KEYS = {"p95Us", "p99Us"}
_GPU_KEYS = {"required", "p95Us", "p99Us"}
_SAFE_ID = re.compile(r"[a-z0-9][a-z0-9_.-]*")
_SAFE_MAP = re.compile(r"[a-z0-9][a-z0-9_./-]*")
_SAFE_PROFILE = re.compile(r"[a-z0-9][a-z0-9_.-]*")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_MARKER_PATTERN = re.compile(
    rf"^{MARKER_PREFIX} "
    r"map=(?P<map>[a-z0-9][a-z0-9_./-]*) "
    r"backend=(?P<backend>opengl|vulkan) "
    r"profile=(?P<profile>[a-z0-9][a-z0-9_.-]*) "
    r"cpuSamples=(?P<cpuSamples>[0-9]+) "
    r"cpuP50Us=(?P<cpuP50Us>[0-9]+) "
    r"cpuP95Us=(?P<cpuP95Us>[0-9]+) "
    r"cpuP99Us=(?P<cpuP99Us>[0-9]+) "
    r"gpuAvailable=(?P<gpuAvailable>[01]) "
    r"gpuSamples=(?P<gpuSamples>[0-9]+) "
    r"gpuP50Us=(?P<gpuP50Us>-?[0-9]+) "
    r"gpuP95Us=(?P<gpuP95Us>-?[0-9]+) "
    r"gpuP99Us=(?P<gpuP99Us>-?[0-9]+)$"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_map_name(value: str) -> str:
    normalized = value.strip().replace("\\", "/").casefold()
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized.removesuffix(".map")


def _exact_keys(value: dict[str, Any], expected: set[str], context: str) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unknown " + ", ".join(extra))
        raise ValueError(f"{context} fields differ ({'; '.join(details)})")


def _positive_int(value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{context} must be a positive integer")
    return value


def _validate_thresholds(value: Any, expected_keys: set[str], context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    _exact_keys(value, expected_keys, context)
    p95 = _positive_int(value.get("p95Us"), f"{context}.p95Us")
    p99 = _positive_int(value.get("p99Us"), f"{context}.p99Us")
    if p99 < p95:
        raise ValueError(f"{context}.p99Us must be greater than or equal to p95Us")
    return {**value, "p95Us": p95, "p99Us": p99}


def validate_contract(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("budget contract root must be an object")
    _exact_keys(payload, _ROOT_KEYS, "budget contract")
    if payload.get("schemaVersion") != CONTRACT_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported budget contract schema: {payload.get('schemaVersion')!r}"
        )
    if payload.get("kind") != CONTRACT_KIND:
        raise ValueError(f"budget contract kind must be {CONTRACT_KIND!r}")
    contract_id = payload.get("contractId")
    if not isinstance(contract_id, str) or _SAFE_ID.fullmatch(contract_id) is None:
        raise ValueError("budget contract contractId is not a canonical identifier")
    if payload.get("timeUnit") != TIME_UNIT:
        raise ValueError(f"budget contract timeUnit must be {TIME_UNIT!r}")
    budgets = payload.get("budgets")
    if not isinstance(budgets, list) or not budgets:
        raise ValueError("budget contract budgets must be a nonempty array")

    normalized_budgets: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_keys: set[tuple[str, str, str]] = set()
    for index, raw in enumerate(budgets):
        context = f"budget[{index}]"
        if not isinstance(raw, dict):
            raise ValueError(f"{context} must be an object")
        _exact_keys(raw, _BUDGET_KEYS, context)
        budget_id = raw.get("id")
        if not isinstance(budget_id, str) or _SAFE_ID.fullmatch(budget_id) is None:
            raise ValueError(f"{context}.id is not a canonical identifier")
        if budget_id in seen_ids:
            raise ValueError(f"duplicate budget id: {budget_id}")
        seen_ids.add(budget_id)

        map_name = normalize_map_name(str(raw.get("map", "")))
        if _SAFE_MAP.fullmatch(map_name) is None or map_name != raw.get("map"):
            raise ValueError(f"{context}.map is not a canonical lowercase VFS map path")
        backend = raw.get("backend")
        if backend not in SUPPORTED_BACKENDS:
            raise ValueError(f"{context}.backend must be one of {SUPPORTED_BACKENDS}")
        profile = raw.get("profile")
        if not isinstance(profile, str) or _SAFE_PROFILE.fullmatch(profile) is None:
            raise ValueError(f"{context}.profile is not a canonical identifier")
        identity = (map_name, backend, profile)
        if identity in seen_keys:
            raise ValueError(
                "duplicate map/backend/profile budget: " + "/".join(identity)
            )
        seen_keys.add(identity)

        minimum = raw.get("minimumSamples")
        if not isinstance(minimum, dict):
            raise ValueError(f"{context}.minimumSamples must be an object")
        _exact_keys(minimum, _MINIMUM_SAMPLE_KEYS, f"{context}.minimumSamples")
        minimum_cpu = _positive_int(minimum.get("cpu"), f"{context}.minimumSamples.cpu")
        minimum_gpu = _positive_int(minimum.get("gpu"), f"{context}.minimumSamples.gpu")
        cpu = _validate_thresholds(raw.get("cpu"), _CPU_KEYS, f"{context}.cpu")
        gpu = _validate_thresholds(raw.get("gpu"), _GPU_KEYS, f"{context}.gpu")
        if gpu.get("required") is not True:
            raise ValueError(f"{context}.gpu.required must be true for promotion evidence")

        normalized_budgets.append(
            {
                "id": budget_id,
                "map": map_name,
                "backend": backend,
                "profile": profile,
                "minimumSamples": {"cpu": minimum_cpu, "gpu": minimum_gpu},
                "cpu": cpu,
                "gpu": gpu,
            }
        )
    return {
        "schemaVersion": CONTRACT_SCHEMA_VERSION,
        "kind": CONTRACT_KIND,
        "contractId": contract_id,
        "timeUnit": TIME_UNIT,
        "budgets": normalized_budgets,
    }


def load_contract(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"renderer budget contract does not exist: {resolved}")
    raw = resolved.read_bytes()
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"renderer budget contract is not valid UTF-8 JSON: {exc}") from exc
    contract = validate_contract(decoded)
    repository_root = Path(__file__).resolve().parents[2]
    try:
        path_hint = resolved.relative_to(repository_root).as_posix()
    except ValueError:
        path_hint = f"external:{resolved.name}"
    binding = {
        "schemaVersion": CONTRACT_SCHEMA_VERSION,
        "kind": CONTRACT_KIND,
        "contractId": contract["contractId"],
        "path": path_hint,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    return contract, binding


def verify_contract_binding(
    recorded: Any, contract: dict[str, Any], binding: dict[str, Any]
) -> list[str]:
    failures: list[str] = []
    if not isinstance(recorded, dict):
        return ["report does not contain a renderer budget contract binding"]
    if recorded != binding:
        failures.append("renderer budget contract binding differs from the selected contract")
    if recorded.get("schemaVersion") != contract.get("schemaVersion"):
        failures.append("renderer budget contract schema binding differs")
    if _SHA256.fullmatch(str(recorded.get("sha256", ""))) is None:
        failures.append("renderer budget contract SHA-256 is malformed")
    return failures


def _measurement_from_match(match: re.Match[str]) -> dict[str, Any]:
    values = match.groupdict()
    return {
        "map": values["map"],
        "backend": values["backend"],
        "profile": values["profile"],
        "cpu": {
            "samples": int(values["cpuSamples"]),
            "p50Us": int(values["cpuP50Us"]),
            "p95Us": int(values["cpuP95Us"]),
            "p99Us": int(values["cpuP99Us"]),
        },
        "gpu": {
            "available": values["gpuAvailable"] == "1",
            "samples": int(values["gpuSamples"]),
            "p50Us": int(values["gpuP50Us"]),
            "p95Us": int(values["gpuP95Us"]),
            "p99Us": int(values["gpuP99Us"]),
        },
    }


def parse_timing_evidence(sources: Iterable[str]) -> tuple[dict[str, Any] | None, list[str]]:
    marker_lines: set[str] = set()
    failures: list[str] = []
    for source_index, text in enumerate(sources):
        source_markers = [
            line.strip() for line in text.splitlines() if MARKER_PREFIX in line
        ]
        if len(source_markers) > 1:
            failures.append(
                f"source {source_index} contains {len(source_markers)} {MARKER_PREFIX} markers; expected exactly one"
            )
        marker_lines.update(source_markers)
    if not marker_lines:
        return None, [*failures, f"{MARKER_PREFIX} marker is missing"]
    if len(marker_lines) != 1:
        return None, [*failures, f"conflicting {MARKER_PREFIX} markers were recorded"]
    marker = next(iter(marker_lines))
    match = _MARKER_PATTERN.fullmatch(marker)
    if match is None:
        return None, [*failures, f"{MARKER_PREFIX} marker has a malformed or non-versioned shape"]
    measurement = _measurement_from_match(match)
    cpu = measurement["cpu"]
    gpu = measurement["gpu"]
    if not (cpu["p50Us"] <= cpu["p95Us"] <= cpu["p99Us"]):
        failures.append("CPU timing percentiles are not monotonic")
    if gpu["available"]:
        if gpu["samples"] <= 0:
            failures.append("GPU timing is available but gpuSamples is zero")
        if min(gpu["p50Us"], gpu["p95Us"], gpu["p99Us"]) < 0:
            failures.append("available GPU timing contains a negative percentile")
        elif not (gpu["p50Us"] <= gpu["p95Us"] <= gpu["p99Us"]):
            failures.append("GPU timing percentiles are not monotonic")
    elif gpu != {
        "available": False,
        "samples": 0,
        "p50Us": -1,
        "p95Us": -1,
        "p99Us": -1,
    }:
        failures.append(
            "unavailable GPU timing must use zero samples and -1 percentiles"
        )
    return {"marker": marker, "measurement": measurement}, failures


def select_budget(
    contract: dict[str, Any], map_name: str, backend: str, profile: str
) -> dict[str, Any] | None:
    identity = (normalize_map_name(map_name), backend.casefold(), profile.casefold())
    matches = [
        budget
        for budget in contract["budgets"]
        if (budget["map"], budget["backend"], budget["profile"]) == identity
    ]
    return matches[0] if len(matches) == 1 else None


def evaluate_timing_evidence(
    sources: Iterable[str],
    contract: dict[str, Any],
    expected_map: str,
    expected_backend: str,
    expected_profile: str,
) -> tuple[dict[str, Any], list[str]]:
    parsed, failures = parse_timing_evidence(sources)
    if parsed is None:
        return {
            "status": "fail",
            "expected": {
                "map": normalize_map_name(expected_map),
                "backend": expected_backend.casefold(),
                "profile": expected_profile.casefold(),
            },
            "failures": failures,
        }, failures

    measurement = parsed["measurement"]
    expected_map_normalized = normalize_map_name(expected_map)
    expected_backend_normalized = expected_backend.casefold()
    expected_profile_normalized = expected_profile.casefold()
    if measurement["map"] != expected_map_normalized:
        failures.append(
            f"timing map {measurement['map']!r} does not match expected {expected_map_normalized!r}"
        )
    if measurement["backend"] != expected_backend_normalized:
        failures.append(
            "timing backend "
            f"{measurement['backend']!r} does not match expected {expected_backend_normalized!r}"
        )
    if measurement["profile"] != expected_profile_normalized:
        failures.append(
            "timing profile "
            f"{measurement['profile']!r} does not match expected {expected_profile_normalized!r}"
        )
    budget = select_budget(
        contract, measurement["map"], measurement["backend"], measurement["profile"]
    )
    if budget is None:
        failures.append(
            "no exact per-map budget for "
            f"{measurement['map']}/{measurement['backend']}/{measurement['profile']}"
        )
        thresholds: dict[str, Any] = {}
        budget_id = ""
    else:
        budget_id = budget["id"]
        thresholds = {
            "minimumSamples": budget["minimumSamples"],
            "cpu": budget["cpu"],
            "gpu": budget["gpu"],
        }
        cpu = measurement["cpu"]
        gpu = measurement["gpu"]
        if cpu["samples"] < budget["minimumSamples"]["cpu"]:
            failures.append(
                f"CPU samples {cpu['samples']} below required {budget['minimumSamples']['cpu']}"
            )
        for percentile in ("p95Us", "p99Us"):
            if cpu[percentile] > budget["cpu"][percentile]:
                failures.append(
                    f"CPU {percentile} {cpu[percentile]} exceeds {budget['cpu'][percentile]}"
                )
        if budget["gpu"]["required"] and not gpu["available"]:
            failures.append("required GPU frame timing is unavailable")
        if gpu["available"]:
            if gpu["samples"] < budget["minimumSamples"]["gpu"]:
                failures.append(
                    f"GPU samples {gpu['samples']} below required {budget['minimumSamples']['gpu']}"
                )
            for percentile in ("p95Us", "p99Us"):
                if gpu[percentile] > budget["gpu"][percentile]:
                    failures.append(
                        f"GPU {percentile} {gpu[percentile]} exceeds {budget['gpu'][percentile]}"
                    )

    evidence = {
        "status": "pass" if not failures else "fail",
        "budgetId": budget_id,
        "expected": {
            "map": expected_map_normalized,
            "backend": expected_backend_normalized,
            "profile": expected_profile_normalized,
        },
        "marker": parsed["marker"],
        "measurement": measurement,
        "thresholds": thresholds,
        "failures": failures,
    }
    return evidence, failures


def verify_recorded_evidence(
    recorded: Any,
    sources: Iterable[str],
    contract: dict[str, Any],
    expected_map: str,
    expected_backend: str,
    expected_profile: str,
) -> list[str]:
    recomputed, failures = evaluate_timing_evidence(
        sources, contract, expected_map, expected_backend, expected_profile
    )
    if not isinstance(recorded, dict):
        return ["recorded renderer budget evidence is missing or malformed", *failures]
    if recorded != recomputed:
        failures = [*failures, "recorded renderer budget evidence differs from verified diagnostics"]
    if recorded.get("status") != "pass" or recorded.get("failures") != []:
        failures.append("recorded renderer budget evidence is not a clean pass")
    return list(dict.fromkeys(failures))
