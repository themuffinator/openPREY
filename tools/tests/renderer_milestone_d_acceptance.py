#!/usr/bin/env python3
"""Run deterministic Milestone D nested dynamic renderer acceptance evidence.

This tool deliberately delegates each capture to renderer_gameplay_benchmark.py
so the launch, windowing, engine screenshot, isolated savepath, warning scan, and
runtime-package checks retain one implementation.  It adds the Milestone D
six-case matrix, fail-closed renderer-domain diagnostics, exact image parity,
and controlled normal-versus-skip image-difference requirements.

Only named runtime packages directly below .tmp/stock-runtime are accepted.
Every generated artifact stays below a fresh named directory under
.tmp/renderer-milestone-d.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Iterable

# Importing the shared benchmark helper must not create a repository-local
# __pycache__; acceptance writes are restricted to the selected .tmp root.
sys.dont_write_bytecode = True
import renderer_gameplay_benchmark as benchmark
import renderer_milestone_d_fixture as fixture_builder


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_PARENT = ROOT / ".tmp" / "stock-runtime"
OUTPUT_PARENT = ROOT / ".tmp" / "renderer-milestone-d"
BENCHMARK_SCRIPT = Path(benchmark.__file__).resolve()
REPORT_JSON_NAME = "renderer_milestone_d_acceptance_report.json"
REPORT_MD_NAME = "renderer_milestone_d_acceptance_report.md"
BENCHMARK_REPORT_JSON = "renderer_gameplay_benchmark_report.json"
BENCHMARK_REPORT_MD = "renderer_gameplay_benchmark_report.md"
SCHEMA_VERSION = 1
FIXTURE_MANIFEST_NAME = "fixture_manifest.json"
FIXTURE_PURPOSE = (
    "temporary Milestone D nested special-view cinematic/post qualification"
)
FIXTURE_MAP = "maps/tools/milestone_d_nested_dynamic"
FIXTURE_CAMERA = "setviewpos 0 -384 96 0 90 0"
BENCHMARK_RESULT_ID = (
    "sp-milestone-d-nested-dynamic_auto_fps240_vsync0_windowed_default_best"
)
BENCHMARK_PURPOSE = (
    "temporary stock-derived mirror fixture with an authored post/video tail "
    "visible only in the captured child view"
)
FIXTURE_RETRIEVED_SHA256 = {
    "maps/tools/mv2.map": (
        "412fc796e569660c92dca5d55359e5c4eb3d572754bd1cdff8ce994b0b802fe2"
    ),
    "video/idlogo.roq": (
        "375c9641c96359c2e0d49cdd3905cc2cdc66a7b067c9a8910d80bf36fb06c8f4"
    ),
}
FIXTURE_GENERATED_PATHS = {
    "maps/tools/milestone_d_nested_dynamic.map",
    "materials/milestone_d_validation.mtr",
    "video/milestone_d_idlogo.roq",
    "maps/tools/milestone_d_nested_dynamic.proc",
    "maps/tools/milestone_d_nested_dynamic.cm",
}


class EvidenceError(RuntimeError):
    """Raised when an artifact or renderer diagnostic is missing or ambiguous."""


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    description: str
    shared_subview: int
    shared_cinematic_post: int
    skip_post_process: int

    @property
    def cvars(self) -> dict[str, str]:
        return {
            "r_rendererSharedSubview": str(self.shared_subview),
            "r_rendererSharedCinematicPost": str(self.shared_cinematic_post),
            "r_skipPostProcess": str(self.skip_post_process),
        }


CASES: tuple[CaseSpec, ...] = (
    CaseSpec(
        "classic-normal",
        "classic subview and cinematic/post paths, normal post processing",
        0,
        0,
        0,
    ),
    CaseSpec(
        "subview-only-normal",
        "shared subview only, with cinematic/post domain disabled",
        1,
        0,
        0,
    ),
    CaseSpec(
        "cinematic-only-normal",
        "shared cinematic/post only; nested authored post remains vacuous",
        0,
        1,
        0,
    ),
    CaseSpec(
        "both-normal",
        "shared subview plus nested cinematic/post ownership",
        1,
        1,
        0,
    ),
    CaseSpec(
        "classic-skip",
        "classic paths with r_skipPostProcess forced",
        0,
        0,
        1,
    ),
    CaseSpec(
        "both-skip",
        "shared domains requested with deterministic nested post fallback",
        1,
        1,
        1,
    ),
)

CASE_BY_ID = {case.case_id: case for case in CASES}


CINEMATIC_PATTERN = re.compile(
    r"^Renderer shared cinematic/post: "
    r"requested=(?P<requested>\d+) prepared=(?P<prepared>\d+) "
    r"valid=(?P<valid>\d+) overflow=(?P<overflow>\d+) "
    r"scenes=(?P<scenes>\d+) views=(?P<views>\d+)"
    r"\(root=(?P<root>\d+) post=(?P<post>\d+) "
    r"nested=(?P<nested_views>\d+)/(?P<nested_transactions>\d+) "
    r"nestedCinematic=(?P<nested_cinematic>\d+)\) "
    r"ready=(?P<ready>\d+) fallback=(?P<fallback>\d+) "
    r"cinematicStages=(?P<cinematic_stages>\d+) "
    r"currentRender=(?P<current_render>\d+) "
    r"currentDepth=(?P<current_depth>\d+) "
    r"hash=(?P<hash>[0-9A-Fa-f]{16}) status=(?P<status>\S+) "
    r"GL=(?P<gl_owned>\d+)/(?P<gl_fallback>\d+)/"
    r"(?P<gl_mismatch>\d+)/(?P<gl_duplicate>\d+) "
    r"VK=(?P<vk_owned>\d+)/(?P<vk_fallback>\d+)/"
    r"(?P<vk_mismatch>\d+)/(?P<vk_duplicate>\d+)\r?$",
    re.MULTILINE,
)

SUBVIEW_PATTERN = re.compile(
    r"^classicSubviewDomain "
    r"requested=(?P<requested>\d+) prepared=(?P<prepared>\d+) "
    r"frameValid=(?P<valid>\d+) overflow=(?P<overflow>\d+) "
    r"status=(?P<status>\S+) scenes=(?P<scenes>\d+) "
    r"subviews=(?P<subviews>\d+) captures=(?P<captures>\d+) "
    r"ready=(?P<ready>\d+) fallback=(?P<fallback>\d+) "
    r"nested=(?P<nested>\d+) "
    r"nestedTransactions=(?P<nested_transactions>\d+) "
    r"maxNestingDepth=(?P<max_depth>\d+) "
    r"directMirror=(?P<direct_mirror>\d+) remote=(?P<remote>\d+) "
    r"mirror=(?P<mirror>\d+) reflection=(?P<reflection>\d+) "
    r"refraction=(?P<refraction>\d+) xray=(?P<xray>\d+) "
    r"colorCubemap=(?P<color_cubemap>\d+) "
    r"depth2D=(?P<depth_2d>\d+) "
    r"depthCubemap=(?P<depth_cubemap>\d+) "
    r"hash=(?P<hash>[0-9A-Fa-f]{16})\r?$",
    re.MULTILINE,
)

SUBVIEW_BACKEND_PATTERN = re.compile(
    r"^classicSubviewDomain backend=(?P<backend>GL|Vulkan) "
    r"ownedViews=(?P<owned>\d+) fallbackViews=(?P<fallback>\d+) "
    r"nestedOwned=(?P<nested_owned>\d+) "
    r"nestedTransactions=(?P<nested_transactions>\d+) "
    r"nestedFallback=(?P<nested_fallback>\d+) "
    r"nestedFallbackTransactions=(?P<nested_fallback_transactions>\d+) "
    r"directMirror=(?P<direct_mirror>\d+) remote=(?P<remote>\d+) "
    r"mirror=(?P<mirror>\d+) reflection=(?P<reflection>\d+) "
    r"refraction=(?P<refraction>\d+) xray=(?P<xray>\d+) "
    r"colorCubemap=(?P<color_cubemap>\d+) "
    r"depth2D=(?P<depth_2d>\d+) "
    r"depthCubemap=(?P<depth_cubemap>\d+) "
    r"mismatches=(?P<mismatches>\d+) duplicate=(?P<duplicate>\d+) "
    r"untracked=(?P<untracked>\d+)\r?$",
    re.MULTILINE,
)

SUBVIEW_VIEW_PREFIX = "classicSubviewDomain view["
CINEMATIC_PREFIX = "Renderer shared cinematic/post: "
SUBVIEW_PREFIX = "classicSubviewDomain requested="
SUBVIEW_BACKEND_PREFIX = "classicSubviewDomain backend="


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-dir",
        required=True,
        help="Existing named runtime package directly below .tmp/stock-runtime.",
    )
    parser.add_argument(
        "--fixture-manifest",
        required=True,
        help=(
            "fixture_manifest.json from the matching fresh fixture evidence "
            "directory below .tmp/renderer-milestone-d."
        ),
    )
    parser.add_argument(
        "--render-api",
        choices=("gl", "vk", "all"),
        default="all",
        help="Backend matrix to execute. 'all' runs GL then Vulkan.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help=(
            "Fresh output name or path directly below .tmp/renderer-milestone-d. "
            "Defaults to acceptance-<timestamp>."
        ),
    )
    parser.add_argument(
        "--basepath",
        default=benchmark.default_basepath(),
        help="Quake 4 installation/base path passed to the benchmark harness.",
    )
    parser.add_argument(
        "--settle-frames",
        type=int,
        default=60,
        help="Deterministic post-load settle frames for each engine capture.",
    )
    parser.add_argument(
        "--sample-frames",
        type=int,
        default=5,
        help="Pacing-only sample frames before gfxInfo and engine screenshot.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Per-case engine timeout forwarded to the benchmark harness.",
    )
    parser.add_argument(
        "--difference-min-rms",
        type=float,
        default=0.1,
        help="Minimum RMS RGB delta required between normal and skip captures.",
    )
    parser.add_argument(
        "--difference-min-channels",
        type=int,
        default=1000,
        help="Minimum changed RGB-channel count for normal versus skip.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate paths and print the exact six-case command plan without writing or launching.",
    )
    args = parser.parse_args(argv)
    if args.settle_frames < 1:
        parser.error("--settle-frames must be positive")
    if args.sample_frames < 1:
        parser.error("--sample-frames must be positive")
    if args.timeout < 10:
        parser.error("--timeout must be at least 10 seconds")
    if not math.isfinite(args.difference_min_rms) or args.difference_min_rms <= 0.0:
        parser.error("--difference-min-rms must be finite and greater than zero")
    if args.difference_min_channels < 1:
        parser.error("--difference-min-channels must be positive")
    return args


def _relative_to(path: Path, parent: Path, description: str) -> Path:
    try:
        return path.relative_to(parent)
    except ValueError as exc:
        raise ValueError(f"{description} must stay below {parent}: {path}") from exc


def _reject_link_ancestry(path: Path, stop: Path, description: str) -> None:
    relative = _relative_to(path, stop, description)
    current = stop
    if current.exists() and benchmark.is_link_or_junction(current):
        raise ValueError(f"{description} ancestry is a link or junction: {current}")
    for part in relative.parts:
        current /= part
        if current.exists() and benchmark.is_link_or_junction(current):
            raise ValueError(f"{description} ancestry is a link or junction: {current}")


def validate_runtime_dir(raw: str) -> Path:
    root = ROOT.absolute()
    parent = RUNTIME_PARENT.absolute()
    candidate_input = Path(raw)
    if candidate_input.is_absolute():
        candidate = candidate_input.absolute()
    elif len(candidate_input.parts) == 1:
        candidate = (parent / candidate_input).absolute()
    else:
        candidate = (root / candidate_input).absolute()
    if candidate.parent != parent or not candidate.name:
        raise ValueError(
            "runtime directory must be a named direct child of "
            f"{parent}: {candidate}"
        )
    _reject_link_ancestry(candidate, root, "runtime directory")
    resolved_parent = parent.resolve()
    resolved = candidate.resolve()
    if resolved.parent != resolved_parent:
        raise ValueError(
            "resolved runtime directory must remain a direct child of "
            f"{resolved_parent}: {resolved}"
        )
    candidate = resolved
    if not candidate.is_dir():
        raise FileNotFoundError(f"runtime directory does not exist: {candidate}")
    benchmark.find_client_executable(candidate)
    return candidate


def select_output_dir(raw: str) -> Path:
    root = ROOT.absolute()
    parent = OUTPUT_PARENT.absolute()
    if raw:
        candidate_input = Path(raw)
        if candidate_input.is_absolute():
            candidate = candidate_input.absolute()
        elif len(candidate_input.parts) == 1:
            candidate = (parent / candidate_input).absolute()
        else:
            candidate = (root / candidate_input).absolute()
    else:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        candidate = (parent / f"acceptance-{stamp}").absolute()
    if candidate.parent != parent or not candidate.name:
        raise ValueError(
            "output directory must be a named direct child of "
            f"{parent}: {candidate}"
        )
    _reject_link_ancestry(candidate, root, "output directory")
    resolved_parent = parent.resolve()
    resolved = candidate.resolve()
    if resolved.parent != resolved_parent:
        raise ValueError(
            "resolved output directory must remain a direct child of "
            f"{resolved_parent}: {resolved}"
        )
    if candidate.exists():
        raise FileExistsError(f"acceptance output directory already exists: {candidate}")
    return candidate


def prepare_output_dir(output_dir: Path) -> None:
    root = ROOT.absolute()
    parent = OUTPUT_PARENT.absolute()
    candidate = output_dir.absolute()
    if candidate.parent != parent:
        raise ValueError(f"output directory escaped {parent}: {candidate}")
    _reject_link_ancestry(candidate, root, "output directory")
    parent.mkdir(parents=True, exist_ok=True)
    _reject_link_ancestry(candidate, root, "output directory")
    output_dir.mkdir(exist_ok=False)


def selected_apis(value: str) -> tuple[str, ...]:
    return ("gl", "vk") if value == "all" else (value,)


def command_display(command: Iterable[str]) -> str:
    values = list(command)
    return subprocess.list2cmdline(values) if os.name == "nt" else shlex.join(values)


def build_benchmark_command(
    args: argparse.Namespace,
    runtime_dir: Path,
    output_dir: Path,
    api: str,
    case: CaseSpec,
) -> list[str]:
    command = [
        sys.executable,
        "-B",
        str(BENCHMARK_SCRIPT),
        "--profile",
        "milestone-d-nested-dynamic",
        "--render-api",
        api,
        "--runtime-dir",
        str(runtime_dir),
        "--output-dir",
        str(output_dir),
        "--pacing-only",
        "--no-gpu-timers",
        "--display-modes",
        "windowed",
        "--width",
        "1280",
        "--height",
        "720",
        "--settle-frames",
        str(args.settle_frames),
        "--sample-frames",
        str(args.sample_frames),
        "--timeout",
        str(args.timeout),
        "--basepath",
        args.basepath,
    ]
    for name, value in case.cvars.items():
        command.extend(("--set-cvar", f"{name}={value}"))
    return command


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    encoded = json.dumps(
        records,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    return {
        "fileCount": len(records),
        "totalBytes": sum(int(record["size"]) for record in records),
        "manifestSha256": hashlib.sha256(encoded).hexdigest(),
        "files": records,
    }


def path_hint(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def validate_fixture_manifest_path(raw: str) -> Path:
    root = ROOT.absolute()
    parent = OUTPUT_PARENT.absolute()
    manifest_input = Path(raw)
    candidate = (
        manifest_input.absolute()
        if manifest_input.is_absolute()
        else (root / manifest_input).absolute()
    )
    if (
        candidate.name != FIXTURE_MANIFEST_NAME
        or candidate.parent.parent != parent
        or not candidate.parent.name
    ):
        raise ValueError(
            "fixture manifest must be <run>/fixture_manifest.json directly below "
            f"{parent}: {candidate}"
        )
    _reject_link_ancestry(candidate, root, "fixture manifest")
    resolved_parent = parent.resolve()
    resolved = candidate.resolve()
    if resolved.parent.parent != resolved_parent:
        raise ValueError(
            "resolved fixture manifest must remain in a direct child of "
            f"{resolved_parent}: {resolved}"
        )
    if not resolved.is_file():
        raise FileNotFoundError(f"fixture manifest does not exist: {resolved}")
    return resolved


def _validated_fixture_records(
    value: Any,
    expected_paths: set[str],
    roots: tuple[Path, ...],
    description: str,
    expected_hashes: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[Path]]:
    if not isinstance(value, list):
        raise EvidenceError(f"fixture {description} records are missing or malformed")
    records: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict):
            raise EvidenceError(f"fixture {description} record is not an object")
        relative = item.get("path")
        size = item.get("size")
        digest = item.get("sha256")
        if (
            not isinstance(relative, str)
            or type(size) is not int
            or size <= 0
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9A-Fa-f]{64}", digest) is None
        ):
            raise EvidenceError(f"fixture {description} record is malformed: {item!r}")
        if relative in records:
            raise EvidenceError(f"duplicate fixture {description} path: {relative}")
        records[relative] = {
            "path": relative,
            "size": size,
            "sha256": digest.lower(),
        }
    if set(records) != expected_paths:
        raise EvidenceError(
            f"fixture {description} paths={sorted(records)!r}; "
            f"expected {sorted(expected_paths)!r}"
        )
    if expected_hashes is not None:
        for relative, expected in expected_hashes.items():
            if records[relative]["sha256"] != expected:
                raise EvidenceError(
                    f"fixture {description} hash mismatch for {relative}: "
                    f"{records[relative]['sha256']} != {expected}"
                )

    verified_paths: list[Path] = []
    for root in roots:
        raw_root = root.absolute()
        resolved_root = raw_root.resolve()
        for relative in sorted(expected_paths):
            raw_path = (raw_root / Path(relative)).absolute()
            _reject_link_ancestry(raw_path, ROOT.absolute(), f"fixture {description}")
            path = raw_path.resolve()
            _relative_to(path, resolved_root, f"fixture {description}")
            if not path.is_file():
                raise EvidenceError(
                    f"fixture {description} file is missing from {resolved_root}: {relative}"
                )
            actual = benchmark.file_record(path, resolved_root)
            if actual != records[relative]:
                raise EvidenceError(
                    f"fixture {description} file does not match its manifest: "
                    f"{path}"
                )
            verified_paths.append(path)
    return [records[path] for path in sorted(records)], verified_paths


def validate_fixture_manifest(
    raw: str, runtime_dir: Path, basepath: Path
) -> dict[str, Any]:
    manifest_path = validate_fixture_manifest_path(raw)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"fixture manifest is unreadable: {exc}") from exc
    if not isinstance(manifest, dict):
        raise EvidenceError("fixture manifest top-level value is not an object")
    for field, expected in (
        ("schemaVersion", 1),
        ("purpose", FIXTURE_PURPOSE),
        ("shippingContent", False),
        ("map", FIXTURE_MAP),
        ("cameraCommand", FIXTURE_CAMERA),
    ):
        if manifest.get(field) != expected:
            raise EvidenceError(
                f"fixture manifest {field}={manifest.get(field)!r}; expected {expected!r}"
            )
    manifest_runtime = manifest.get("runtimeDir")
    if not isinstance(manifest_runtime, str) or Path(manifest_runtime).resolve() != runtime_dir:
        raise EvidenceError(
            "fixture manifest runtimeDir does not identify the selected runtime: "
            f"{manifest_runtime!r}"
        )
    manifest_basepath = manifest.get("basepath")
    if (
        not isinstance(manifest_basepath, str)
        or Path(manifest_basepath).resolve() != basepath
    ):
        raise EvidenceError(
            "fixture manifest basepath does not identify the selected stock root: "
            f"{manifest_basepath!r}"
        )
    stock_dependencies = fixture_builder.stock_dependency_inventory(basepath)
    if manifest.get("stockDependencies") != stock_dependencies:
        raise EvidenceError(
            "selected stock basepath dependencies do not match the fixture manifest"
        )
    runtime_components = fixture_builder.validate_runtime_components(runtime_dir)
    if manifest.get("runtimeComponents") != runtime_components:
        raise EvidenceError(
            "selected runtime components do not match the fixture manifest"
        )

    evidence_root = manifest_path.parent
    retrieved, retrieved_paths = _validated_fixture_records(
        manifest.get("retrieved"),
        set(FIXTURE_RETRIEVED_SHA256),
        (evidence_root / "retrieved/baseoq4",),
        "retrieved",
        FIXTURE_RETRIEVED_SHA256,
    )
    generated, generated_paths = _validated_fixture_records(
        manifest.get("generated"),
        FIXTURE_GENERATED_PATHS,
        (evidence_root / "compile/baseoq4", runtime_dir / "baseoq4"),
        "generated",
    )
    generated_by_path = {record["path"]: record for record in generated}
    if (
        generated_by_path["video/milestone_d_idlogo.roq"]["sha256"]
        != FIXTURE_RETRIEVED_SHA256["video/idlogo.roq"]
    ):
        raise EvidenceError("staged fixture video does not match the pinned retail ROQ")

    runtime_game = runtime_dir / "baseoq4"
    text_contracts = {
        "maps/tools/milestone_d_nested_dynamic.map": (
            "shaderDemos/transparentMirror",
            "milestoneD/nestedCinematicPost",
        ),
        "materials/milestone_d_validation.mtr": (
            "milestoneD/nestedCinematicPost",
            "sort postProcess",
            "videoMap loop video/milestone_d_idlogo.roq",
            "map _currentRender",
        ),
        "maps/tools/milestone_d_nested_dynamic.proc": (
            "shaderDemos/transparentMirror",
            "milestoneD/nestedCinematicPost",
        ),
    }
    for relative, tokens in text_contracts.items():
        try:
            text = (runtime_game / relative).read_text(
                encoding="utf-8", errors="strict"
            )
        except (OSError, UnicodeError) as exc:
            raise EvidenceError(f"fixture contract file is unreadable: {relative}: {exc}") from exc
        folded = text.casefold()
        for token in tokens:
            if token.casefold() not in folded:
                raise EvidenceError(
                    f"fixture contract file {relative} lacks {token!r}"
                )

    evidence_files = [manifest_path, *retrieved_paths, *generated_paths]
    evidence_inventory = inventory_summary(
        sorted(
            (
                benchmark.file_record(path, evidence_root)
                for path in evidence_files
                if path.is_relative_to(evidence_root)
            ),
            key=lambda record: record["path"],
        )
    )
    return {
        "manifestPath": path_hint(manifest_path),
        "manifestSha256": sha256_file(manifest_path),
        "manifestArtifact": {
            "kind": "fixtureManifest",
            "path": path_hint(manifest_path),
            "size": manifest_path.stat().st_size,
            "sha256": sha256_file(manifest_path),
        },
        "purpose": FIXTURE_PURPOSE,
        "shippingContent": False,
        "runtimeDir": path_hint(runtime_dir),
        "basepath": str(basepath),
        "stockDependencies": stock_dependencies,
        "runtimeComponents": runtime_components,
        "map": FIXTURE_MAP,
        "cameraCommand": FIXTURE_CAMERA,
        "retrieved": retrieved,
        "generated": generated,
        "evidenceInventory": evidence_inventory,
    }


def _record_artifact(path: Path, output_root: Path, kind: str) -> dict[str, Any]:
    resolved = path.resolve()
    _relative_to(resolved, output_root.resolve(), "evidence artifact")
    if not resolved.is_file():
        raise EvidenceError(f"required {kind} artifact is missing: {resolved}")
    record = benchmark.file_record(resolved, output_root.resolve())
    return {"kind": kind, **record}


def _resolve_role_artifact(value: Any, case_dir: Path, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise EvidenceError(f"benchmark role has no {label} path")
    path = Path(value).resolve()
    _relative_to(path, case_dir.resolve(), f"benchmark {label}")
    if not path.is_file():
        raise EvidenceError(f"benchmark {label} is missing: {path}")
    return path


def _converted_match(match: re.Match[str], textual: set[str]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for name, value in match.groupdict().items():
        record[name] = value if name in textual else int(value)
    if "hash" in record:
        record["hash"] = str(record["hash"]).lower()
    return record


def _single_match(
    pattern: re.Pattern[str],
    text: str,
    description: str,
    textual: set[str],
    prefix: str,
) -> tuple[dict[str, Any], str]:
    prefix_count = sum(line.startswith(prefix) for line in text.splitlines())
    matches = list(pattern.finditer(text))
    if prefix_count != 1 or len(matches) != prefix_count:
        raise EvidenceError(
            f"expected exactly one well-formed {description} diagnostic, "
            f"found prefixes={prefix_count} parsed={len(matches)}"
        )
    match = matches[0]
    return _converted_match(match, textual), match.group(0).rstrip("\r")


def parse_renderer_diagnostics(text: str) -> dict[str, Any]:
    """Parse the exact gfxInfo diagnostics used by Milestone D acceptance."""
    cinematic, cinematic_line = _single_match(
        CINEMATIC_PATTERN,
        text,
        "shared cinematic/post",
        {"hash", "status"},
        CINEMATIC_PREFIX,
    )
    subview, subview_line = _single_match(
        SUBVIEW_PATTERN,
        text,
        "classic subview summary",
        {"hash", "status"},
        SUBVIEW_PREFIX,
    )
    backend_prefix_count = sum(
        line.startswith(SUBVIEW_BACKEND_PREFIX) for line in text.splitlines()
    )
    backend_matches = list(SUBVIEW_BACKEND_PATTERN.finditer(text))
    if backend_prefix_count != 2 or len(backend_matches) != backend_prefix_count:
        raise EvidenceError(
            "expected exactly two well-formed classic subview backend diagnostics, "
            f"found prefixes={backend_prefix_count} parsed={len(backend_matches)}"
        )
    backends: dict[str, dict[str, Any]] = {}
    backend_lines: dict[str, str] = {}
    for match in backend_matches:
        record = _converted_match(match, {"backend"})
        key = "gl" if record.pop("backend") == "GL" else "vulkan"
        if key in backends:
            raise EvidenceError(f"duplicate classic subview backend diagnostic: {key}")
        backends[key] = record
        backend_lines[key] = match.group(0).rstrip("\r")
    if set(backends) != {"gl", "vulkan"}:
        raise EvidenceError("classic subview diagnostics do not cover GL and Vulkan")
    view_lines = [
        line.rstrip("\r")
        for line in text.splitlines()
        if line.startswith(SUBVIEW_VIEW_PREFIX)
    ]
    return {
        "cinematicPost": cinematic,
        "subview": subview,
        "subviewBackends": backends,
        "subviewViewLines": view_lines,
        "sourceLines": {
            "cinematicPost": cinematic_line,
            "subview": subview_line,
            "subviewBackends": backend_lines,
            "subviewViews": view_lines,
        },
    }


def _expect_equal(
    failures: list[str],
    record: dict[str, Any],
    field: str,
    expected: Any,
    label: str,
) -> None:
    actual = record.get(field)
    if actual != expected:
        failures.append(f"{label} {field}={actual!r}; expected {expected!r}")


def _expect_positive(
    failures: list[str], record: dict[str, Any], field: str, label: str
) -> None:
    actual = record.get(field)
    if not isinstance(actual, int) or actual <= 0:
        failures.append(f"{label} {field}={actual!r}; expected a positive count")


def _expect_zero_fields(
    failures: list[str],
    record: dict[str, Any],
    fields: Iterable[str],
    label: str,
) -> None:
    for field in fields:
        _expect_equal(failures, record, field, 0, label)


def validate_case_diagnostics(
    case: CaseSpec, api: str, diagnostics: dict[str, Any]
) -> list[str]:
    failures: list[str] = []
    cinematic = diagnostics["cinematicPost"]
    subview = diagnostics["subview"]
    backends = diagnostics["subviewBackends"]
    active_key = "gl" if api == "gl" else "vulkan"
    inactive_key = "vulkan" if api == "gl" else "gl"
    active_label = "GL" if api == "gl" else "Vulkan"
    inactive_label = "Vulkan" if api == "gl" else "GL"
    active = backends[active_key]
    inactive = backends[inactive_key]

    _expect_equal(failures, cinematic, "overflow", 0, "cinematic/post")
    _expect_equal(failures, subview, "overflow", 0, "subview")
    _expect_equal(
        failures,
        cinematic,
        "status",
        "prepared" if case.shared_cinematic_post else "reset",
        "cinematic/post",
    )
    _expect_equal(
        failures,
        subview,
        "status",
        "ready" if case.shared_subview else "empty",
        "subview",
    )
    for prefix in ("gl", "vk"):
        _expect_zero_fields(
            failures,
            cinematic,
            (f"{prefix}_mismatch", f"{prefix}_duplicate"),
            f"cinematic/post {prefix}",
        )
    for backend_name, backend in backends.items():
        _expect_zero_fields(
            failures,
            backend,
            ("mismatches", "duplicate", "untracked"),
            f"subview {backend_name}",
        )
    _expect_zero_fields(
        failures,
        inactive,
        (
            "owned",
            "fallback",
            "nested_owned",
            "nested_transactions",
            "nested_fallback",
            "nested_fallback_transactions",
            "direct_mirror",
            "remote",
            "mirror",
            "reflection",
            "refraction",
            "xray",
            "color_cubemap",
            "depth_2d",
            "depth_cubemap",
        ),
        f"subview inactive {inactive_key}",
    )
    inactive_prefix = "vk" if api == "gl" else "gl"
    _expect_equal(
        failures,
        cinematic,
        f"{inactive_prefix}_owned",
        0,
        "cinematic/post inactive backend",
    )
    _expect_equal(
        failures,
        cinematic,
        f"{inactive_prefix}_fallback",
        0,
        "cinematic/post inactive backend",
    )

    disabled_cinematic_fields = (
        "requested",
        "prepared",
        "valid",
        "scenes",
        "views",
        "root",
        "post",
        "nested_views",
        "nested_transactions",
        "nested_cinematic",
        "ready",
        "fallback",
        "cinematic_stages",
        "current_render",
        "current_depth",
        "gl_owned",
        "gl_fallback",
        "vk_owned",
        "vk_fallback",
    )
    disabled_subview_fields = (
        "requested",
        "prepared",
        "valid",
        "scenes",
        "subviews",
        "captures",
        "ready",
        "fallback",
        "nested",
        "nested_transactions",
        "max_depth",
        "direct_mirror",
        "remote",
        "mirror",
        "reflection",
        "refraction",
        "xray",
        "color_cubemap",
        "depth_2d",
        "depth_cubemap",
    )

    if not case.shared_cinematic_post:
        _expect_zero_fields(
            failures, cinematic, disabled_cinematic_fields, "cinematic/post disabled"
        )
    elif case.case_id == "cinematic-only-normal":
        for field in ("requested", "prepared", "valid"):
            _expect_equal(failures, cinematic, field, 1, "cinematic-only")
        _expect_positive(failures, cinematic, "scenes", "cinematic-only")
        _expect_zero_fields(
            failures,
            cinematic,
            (
                "views",
                "root",
                "post",
                "nested_views",
                "nested_transactions",
                "nested_cinematic",
                "ready",
                "fallback",
                "cinematic_stages",
                "current_render",
                "current_depth",
                "gl_owned",
                "gl_fallback",
                "vk_owned",
                "vk_fallback",
            ),
            "cinematic-only vacuous nested authored post",
        )
    else:
        for field in ("requested", "prepared", "valid"):
            _expect_equal(failures, cinematic, field, 1, "cinematic/post enabled")
        _expect_positive(failures, cinematic, "scenes", "cinematic/post enabled")
        for field, expected in (
            ("views", 1),
            ("root", 0),
            ("post", 1),
            ("nested_views", 1),
            ("nested_transactions", 1),
            ("ready", 1),
            ("fallback", 0),
            ("current_depth", 0),
        ):
            _expect_equal(failures, cinematic, field, expected, "cinematic/post enabled")
        _expect_positive(
            failures, cinematic, "nested_cinematic", "cinematic/post enabled"
        )
        _expect_positive(
            failures, cinematic, "cinematic_stages", "cinematic/post enabled"
        )
        _expect_positive(
            failures, cinematic, "current_render", "cinematic/post enabled"
        )
        if cinematic.get("hash") == "0000000000000000":
            failures.append("cinematic/post enabled hash is zero")
        prefix = "gl" if api == "gl" else "vk"
        expected_owned = 0 if case.skip_post_process else 1
        expected_fallback = 1 if case.skip_post_process else 0
        _expect_equal(
            failures,
            cinematic,
            f"{prefix}_owned",
            expected_owned,
            "cinematic/post active backend",
        )
        _expect_equal(
            failures,
            cinematic,
            f"{prefix}_fallback",
            expected_fallback,
            "cinematic/post active backend",
        )

    if not case.shared_subview:
        _expect_zero_fields(
            failures, subview, disabled_subview_fields, "subview disabled"
        )
        _expect_zero_fields(
            failures,
            active,
            (
                "owned",
                "fallback",
                "nested_owned",
                "nested_transactions",
                "nested_fallback",
                "nested_fallback_transactions",
                "direct_mirror",
                "remote",
                "mirror",
                "reflection",
                "refraction",
                "xray",
                "color_cubemap",
                "depth_2d",
                "depth_cubemap",
            ),
            "subview disabled active backend",
        )
    else:
        for field in ("requested", "prepared", "valid"):
            _expect_equal(failures, subview, field, 1, "subview enabled")
        _expect_positive(failures, subview, "scenes", "subview enabled")
        for field, expected in (
            ("subviews", 1),
            ("captures", 1),
            ("ready", 1),
            ("fallback", 0),
            ("nested", 0),
            ("nested_transactions", 0),
            ("max_depth", 0),
            ("direct_mirror", 0),
            ("remote", 0),
            ("mirror", 1),
            ("reflection", 0),
            ("refraction", 0),
            ("xray", 0),
            ("color_cubemap", 0),
            ("depth_2d", 0),
            ("depth_cubemap", 0),
        ):
            _expect_equal(failures, subview, field, expected, "subview enabled")
        if subview.get("hash") == "0000000000000000":
            failures.append("subview enabled hash is zero")
        expected_owned = 0 if case.skip_post_process else 1
        expected_fallback = 1 if case.skip_post_process else 0
        _expect_equal(
            failures, active, "owned", expected_owned, "subview active backend"
        )
        _expect_equal(
            failures,
            active,
            "fallback",
            expected_fallback,
            "subview active backend",
        )
        _expect_equal(
            failures,
            active,
            "mirror",
            expected_owned,
            "subview active backend",
        )
        _expect_zero_fields(
            failures,
            active,
            (
                "nested_owned",
                "nested_transactions",
                "nested_fallback",
                "nested_fallback_transactions",
                "direct_mirror",
                "remote",
                "reflection",
                "refraction",
                "xray",
                "color_cubemap",
                "depth_2d",
                "depth_cubemap",
            ),
            "subview active backend",
        )

    view_lines = diagnostics["subviewViewLines"]
    if case.shared_subview:
        if len(view_lines) != 1:
            failures.append(
                f"expected exactly one prepared subview view diagnostic, found {len(view_lines)}"
            )
        else:
            view_line = view_lines[0]
            required_tokens = (
                "parentView=-1 root=0 depth=0 subtree=1",
                "kind=mirror captureType=color2D ready=1 failure=none",
                "captureImage=_scratch rect=0,0 1024x256",
            )
            for token in required_tokens:
                if token not in view_line:
                    failures.append(f"subview view diagnostic is missing {token!r}")
            inactive_outcome = f"{inactive_label}=0/none/0"
            if inactive_outcome not in view_line:
                failures.append(
                    "subview view diagnostic lacks inactive backend outcome "
                    f"{inactive_outcome!r}"
                )
            if case.skip_post_process:
                outcome_prefix = (
                    f"{active_label}=2/nestedCinematicPostFallback/"
                )
                outcome_match = re.search(
                    rf"{re.escape(outcome_prefix)}([1-9][0-9]*)(?:\s|$)",
                    view_line,
                )
                if outcome_match is None:
                    failures.append(
                        "both-on skip lacks a named nestedCinematicPostFallback "
                        "diagnostic with a positive backend detail"
                    )
            else:
                outcome = f"{active_label}=1/none/0"
                if outcome not in view_line:
                    failures.append(
                        f"subview view diagnostic lacks active backend outcome {outcome!r}"
                    )
    elif view_lines:
        failures.append(
            f"disabled shared subview unexpectedly emitted {len(view_lines)} view diagnostic(s)"
        )

    return failures


def _verify_recorded_artifacts(
    report: dict[str, Any], case_dir: Path, failures: list[str]
) -> None:
    results = report.get("results")
    if not isinstance(results, list) or len(results) != 1:
        return
    roles = results[0].get("roles")
    if not isinstance(roles, list) or len(roles) != 1:
        return
    artifacts = roles[0].get("artifacts")
    if not isinstance(artifacts, list):
        failures.append("benchmark role artifact manifest is missing or malformed")
        return
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
            failures.append("benchmark role artifact record is malformed")
            continue
        path = (case_dir / artifact["path"]).resolve()
        try:
            _relative_to(path, case_dir.resolve(), "benchmark recorded artifact")
        except ValueError as exc:
            failures.append(str(exc))
            continue
        if not path.is_file():
            failures.append(f"benchmark recorded artifact is missing: {artifact['path']}")
            continue
        actual = benchmark.file_record(path, case_dir.resolve())
        for field in ("path", "size", "sha256"):
            if actual.get(field) != artifact.get(field):
                failures.append(
                    f"benchmark artifact {artifact['path']} has mismatched {field}"
                )


def inspect_benchmark_output(
    case_dir: Path,
    output_root: Path,
    runtime_records: list[dict[str, Any]],
    api: str,
    case: CaseSpec,
    process_returncode: int,
    command: list[str],
    expected_basepath: Path,
) -> dict[str, Any]:
    failures: list[str] = []
    artifacts: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] | None = None
    screenshot_path: Path | None = None
    log_path: Path | None = None
    engine_stdout_path: Path | None = None
    engine_stderr_path: Path | None = None
    capture_script_path: Path | None = None
    capture_script: dict[str, Any] | None = None
    display_evidence: dict[str, Any] | None = None
    report_path = case_dir / BENCHMARK_REPORT_JSON
    report_md_path = case_dir / BENCHMARK_REPORT_MD
    report: dict[str, Any] = {}

    if process_returncode != 0:
        failures.append(f"benchmark process exited with code {process_returncode}")
    if not report_path.is_file():
        failures.append(f"benchmark JSON report is missing: {report_path}")
    else:
        try:
            loaded = json.loads(report_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError("top-level JSON value is not an object")
            report = loaded
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            failures.append(f"benchmark JSON report is unreadable: {exc}")

    if report:
        if report.get("schemaVersion") != benchmark.REPORT_SCHEMA_VERSION:
            failures.append(
                f"benchmark schemaVersion={report.get('schemaVersion')!r}; "
                f"expected {benchmark.REPORT_SCHEMA_VERSION}"
            )
        if report.get("status") != "pass":
            failures.append(f"benchmark report status={report.get('status')!r}; expected 'pass'")
        if report.get("dryRun") is not False:
            failures.append("benchmark report is not real-run evidence")
        if report.get("budgetEnforced") is not False:
            failures.append("benchmark report is not pacing-only evidence")
        if report.get("runtimeVerificationFailures") != []:
            failures.append(
                "benchmark detected runtime mutation: "
                f"{report.get('runtimeVerificationFailures')!r}"
            )
        runtime = report.get("runtime")
        report_runtime_files = runtime.get("files") if isinstance(runtime, dict) else None
        runtime_differences = benchmark.compare_file_records(
            runtime_records, report_runtime_files, "benchmark runtime file"
        ) if isinstance(report_runtime_files, list) else [
            "benchmark runtime file inventory is missing or malformed"
        ]
        failures.extend(runtime_differences)
        metadata = report.get("metadata")
        if not isinstance(metadata, dict):
            failures.append("benchmark metadata is missing or malformed")
        else:
            for field, expected in (
                ("profile", "milestone-d-nested-dynamic"),
                ("renderApi", api),
                ("dryRun", False),
                ("basepath", str(expected_basepath)),
            ):
                if metadata.get(field) != expected:
                    failures.append(
                        f"benchmark metadata {field}={metadata.get(field)!r}; "
                        f"expected {expected!r}"
                    )
        results = report.get("results")
        if not isinstance(results, list) or len(results) != 1:
            failures.append("benchmark report must contain exactly one result")
        else:
            result = results[0]
            if result.get("status") != "pass":
                failures.append(
                    f"benchmark result status={result.get('status')!r}; expected 'pass'"
                )
            expected_backend = "opengl" if api == "gl" else "vulkan"
            for field, expected in (
                ("id", BENCHMARK_RESULT_ID),
                ("mode", "SP"),
                ("map", FIXTURE_MAP),
                ("budgetMap", FIXTURE_MAP),
                ("purpose", BENCHMARK_PURPOSE),
                ("renderApi", api),
                ("expectedBackend", expected_backend),
                ("display", "windowed"),
            ):
                if result.get(field) != expected:
                    failures.append(
                        f"benchmark result {field}={result.get(field)!r}; "
                        f"expected {expected!r}"
                    )
            display_contract = result.get("displayContract")
            display_cvars = (
                display_contract.get("cvars")
                if isinstance(display_contract, dict)
                else None
            )
            if not isinstance(display_cvars, dict):
                failures.append("benchmark display contract is missing")
            else:
                for name, expected in (
                    ("r_fullscreen", "0"),
                    ("r_borderless", "0"),
                    ("r_windowWidth", "1280"),
                    ("r_windowHeight", "720"),
                ):
                    if display_cvars.get(name) != expected:
                        failures.append(
                            f"benchmark display contract {name}="
                            f"{display_cvars.get(name)!r}; expected {expected!r}"
                        )
            roles = result.get("roles")
            if not isinstance(roles, list) or len(roles) != 1:
                failures.append("benchmark result must contain exactly one role")
            else:
                role = roles[0]
                if (
                    role.get("id") != BENCHMARK_RESULT_ID
                    or role.get("role") != "sp"
                    or role.get("status") != "pass"
                ):
                    failures.append(
                        "benchmark role must be a passing SP capture; "
                        f"got id={role.get('id')!r} role={role.get('role')!r} "
                        f"status={role.get('status')!r}"
                    )
                if role.get("timedOut") is not False or role.get("exitCode") != 0:
                    failures.append(
                        "benchmark engine process did not exit cleanly: "
                        f"exit={role.get('exitCode')!r} timedOut={role.get('timedOut')!r}"
                    )
                warnings = role.get("warnings")
                if not isinstance(warnings, dict):
                    failures.append("benchmark warning buckets are missing")
                else:
                    nonzero_warnings = {
                        name: value for name, value in warnings.items() if value != 0
                    }
                    if nonzero_warnings:
                        failures.append(
                            f"benchmark fatal/error warning buckets are nonzero: {nonzero_warnings}"
                        )
                if role.get("missing") != []:
                    failures.append(f"benchmark role reports missing evidence: {role.get('missing')!r}")
                if role.get("failureDiagnostics") != []:
                    failures.append(
                        "benchmark role reports failure diagnostics: "
                        f"{role.get('failureDiagnostics')!r}"
                    )
                try:
                    log_path = _resolve_role_artifact(role.get("log"), case_dir, "engine log")
                    screenshot_path = _resolve_role_artifact(
                        role.get("screenshot"), case_dir, "engine screenshot"
                    )
                    engine_stdout_path = _resolve_role_artifact(
                        role.get("stdout"), case_dir, "engine process stdout"
                    )
                    engine_stderr_path = _resolve_role_artifact(
                        role.get("stderr"), case_dir, "engine process stderr"
                    )
                except EvidenceError as exc:
                    failures.append(str(exc))
                if role.get("screenshotRequest") != "screenshots/renderer-bench/sp_0.tga":
                    failures.append(
                        "benchmark did not request the canonical engine TGA screenshot"
                    )
                image = role.get("image")
                image_status = image.get("status") if isinstance(image, dict) else None
                if image_status not in ("not-requested", "compared"):
                    failures.append(
                        "benchmark image status is neither an unreferenced engine capture "
                        "nor a completed comparison"
                    )
                elif image_status == "not-requested":
                    if screenshot_path is not None and image.get("sha256") != sha256_file(
                        screenshot_path
                    ):
                        failures.append(
                            "benchmark image SHA-256 does not match engine screenshot"
                        )
                elif not (
                    image.get("pass") is True
                    and image.get("rms") == 0.0
                    and image.get("maxDelta") == 0
                    and image.get("differingChannels") == 0
                ):
                    failures.append("benchmark's pre-existing image comparison is not exact")

        metadata = report.get("metadata")
        if isinstance(metadata, dict):
            expected_commands = ["g_stopTime 1", "noclip", FIXTURE_CAMERA]
            if metadata.get("profileExecCommands") != expected_commands:
                failures.append(
                    "benchmark profile commands do not match the fixed-clock camera contract"
                )
            launch_cvars = metadata.get("launchCvars")
            if not isinstance(launch_cvars, dict):
                failures.append("benchmark launch CVar contract is missing")
            else:
                for name, expected in (("in_mouse", "0"), ("g_stopTime", "1")):
                    if launch_cvars.get(name) != expected:
                        failures.append(
                            f"benchmark launch CVar {name}={launch_cvars.get(name)!r}; "
                            f"expected {expected!r}"
                        )
        _verify_recorded_artifacts(report, case_dir, failures)

    diagnostic_sources: list[str] = []
    if log_path is not None:
        try:
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
            diagnostic_sources.append(log_text)
            diagnostics = parse_renderer_diagnostics(log_text)
            failures.extend(validate_case_diagnostics(case, api, diagnostics))
        except (OSError, EvidenceError) as exc:
            failures.append(f"renderer diagnostic parse failed: {exc}")

        capture_script_path = log_path.parent.parent / "renderer-bench" / "sp_0.cfg"
        if not capture_script_path.is_file():
            failures.append(f"generated capture script is missing: {capture_script_path}")
        else:
            try:
                script_text = capture_script_path.read_text(
                    encoding="utf-8", errors="strict"
                )
                final_cvars: dict[str, str] = {}
                expected_cvars = {
                    **case.cvars,
                    "r_rendererMetrics": "0",
                    "r_rendererGpuTimers": "0",
                }
                for name, expected in expected_cvars.items():
                    values = re.findall(
                        rf"^{re.escape(name)}\s+(\S+)\s*$",
                        script_text,
                        flags=re.MULTILINE,
                    )
                    if not values:
                        failures.append(f"capture script does not set {name}")
                        continue
                    final_cvars[name] = values[-1]
                    if values[-1] != expected:
                        failures.append(
                            f"capture script final {name}={values[-1]!r}; expected {expected!r}"
                        )
                required_commands = (
                    "g_stopTime 1",
                    "noclip",
                    FIXTURE_CAMERA,
                    "viewpos",
                    "gfxInfo",
                    'screenshot "screenshots/renderer-bench/sp_0.tga"',
                )
                for required in required_commands:
                    if required not in script_text.splitlines():
                        failures.append(
                            f"capture script lacks required engine command {required!r}"
                        )
                capture_script = {
                    "path": capture_script_path.resolve().relative_to(
                        output_root.resolve()
                    ).as_posix(),
                    "sha256": sha256_file(capture_script_path),
                    "finalCvars": final_cvars,
                    "commands": list(required_commands),
                }
            except (OSError, UnicodeError) as exc:
                failures.append(f"generated capture script is unreadable: {exc}")

    screenshot: dict[str, Any] | None = None
    if screenshot_path is not None:
        try:
            width, height, _ = benchmark.load_tga_rgb(screenshot_path)
            screenshot = {
                "path": screenshot_path.resolve().relative_to(output_root.resolve()).as_posix(),
                "width": width,
                "height": height,
                "sha256": sha256_file(screenshot_path),
            }
            if (width, height) != (1280, 720):
                failures.append(
                    f"engine screenshot is {width}x{height}; expected 1280x720"
                )
        except (OSError, ValueError) as exc:
            failures.append(f"engine screenshot is not a valid supported TGA: {exc}")

    for description, path in (
        ("engine process stdout", engine_stdout_path),
        ("engine process stderr", engine_stderr_path),
    ):
        if path is None:
            continue
        try:
            diagnostic_sources.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            failures.append(f"{description} is unreadable for display evidence: {exc}")
    display_evidence, display_failures = benchmark.evaluate_display_evidence(
        diagnostic_sources, screenshot_path, 1280, 720
    )
    failures.extend(f"actual display evidence: {failure}" for failure in display_failures)

    artifact_candidates = (
        (report_path, "benchmarkReportJson"),
        (report_md_path, "benchmarkReportMarkdown"),
        (log_path, "engineLog"),
        (engine_stdout_path, "engineProcessStdout"),
        (engine_stderr_path, "engineProcessStderr"),
        (screenshot_path, "engineScreenshot"),
        (capture_script_path, "generatedCaptureScript"),
        (case_dir / "acceptance_benchmark_process.out.txt", "benchmarkProcessStdout"),
        (case_dir / "acceptance_benchmark_process.err.txt", "benchmarkProcessStderr"),
    )
    for path, kind in artifact_candidates:
        if path is None or not path.is_file():
            continue
        try:
            artifacts.append(_record_artifact(path, output_root, kind))
        except EvidenceError as exc:
            failures.append(str(exc))

    return {
        "id": case.case_id,
        "description": case.description,
        "cvars": case.cvars,
        "command": command,
        "commandDisplay": command_display(command),
        "benchmarkExitCode": process_returncode,
        "status": "pass" if not failures else "fail",
        "failures": failures,
        "diagnostics": diagnostics,
        "screenshot": screenshot,
        "displayEvidence": display_evidence,
        "captureScript": capture_script,
        "artifacts": artifacts,
    }


def run_case(
    args: argparse.Namespace,
    runtime_dir: Path,
    output_root: Path,
    runtime_records: list[dict[str, Any]],
    api: str,
    case: CaseSpec,
) -> dict[str, Any]:
    case_dir = output_root / api / case.case_id
    command = build_benchmark_command(args, runtime_dir, case_dir, api, case)
    print(f"running {api} {case.case_id}...", flush=True)
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except OSError as exc:
        returncode = 127
        stdout = ""
        stderr = f"{type(exc).__name__}: {exc}\n"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "acceptance_benchmark_process.out.txt").write_text(
        stdout, encoding="utf-8", newline="\n"
    )
    (case_dir / "acceptance_benchmark_process.err.txt").write_text(
        stderr, encoding="utf-8", newline="\n"
    )
    try:
        result = inspect_benchmark_output(
            case_dir,
            output_root,
            runtime_records,
            api,
            case,
            returncode,
            command,
            Path(args.basepath).resolve(),
        )
    except Exception as exc:  # Keep a report even for an unexpected parser failure.
        result = {
            "id": case.case_id,
            "description": case.description,
            "cvars": case.cvars,
            "command": command,
            "commandDisplay": command_display(command),
            "benchmarkExitCode": returncode,
            "status": "fail",
            "failures": [f"unexpected evidence inspection failure: {type(exc).__name__}: {exc}"],
            "diagnostics": None,
            "screenshot": None,
            "captureScript": None,
            "artifacts": [],
        }
    print(f"  {result['status']}", flush=True)
    return result


def compare_images(
    api: str,
    comparison_id: str,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    output_root: Path,
    expectation: str,
    min_rms: float,
    min_channels: int,
) -> dict[str, Any]:
    failures: list[str] = []
    baseline_image = baseline.get("screenshot")
    candidate_image = candidate.get("screenshot")
    comparison: dict[str, Any] | None = None
    if not isinstance(baseline_image, dict) or not isinstance(candidate_image, dict):
        failures.append("one or both engine screenshots are unavailable")
    else:
        try:
            first = (output_root / baseline_image["path"]).resolve()
            second = (output_root / candidate_image["path"]).resolve()
            _relative_to(first, output_root.resolve(), "comparison screenshot")
            _relative_to(second, output_root.resolve(), "comparison screenshot")
            comparison = benchmark.compare_tga(second, first)
        except (KeyError, OSError, ValueError) as exc:
            failures.append(f"TGA comparison failed: {exc}")
    if comparison is not None:
        if comparison.get("status") != "compared":
            failures.append(
                f"image comparison status={comparison.get('status')!r}; expected 'compared'"
            )
        elif expectation == "exact":
            for field, expected in (
                ("rms", 0.0),
                ("maxDelta", 0),
                ("differingChannels", 0),
            ):
                if comparison.get(field) != expected:
                    failures.append(
                        f"exact parity {field}={comparison.get(field)!r}; expected {expected!r}"
                    )
        elif expectation == "different":
            rms = comparison.get("rms")
            channels = comparison.get("differingChannels")
            if not isinstance(rms, (int, float)) or rms < min_rms:
                failures.append(
                    f"normal-vs-skip RMS={rms!r}; required at least {min_rms}"
                )
            if not isinstance(channels, int) or channels < min_channels:
                failures.append(
                    "normal-vs-skip differingChannels="
                    f"{channels!r}; required at least {min_channels}"
                )
        else:
            failures.append(f"unknown comparison expectation: {expectation}")
    return {
        "id": comparison_id,
        "api": api,
        "baselineCase": baseline["id"],
        "candidateCase": candidate["id"],
        "expectation": expectation,
        "minimums": (
            {"rms": min_rms, "differingChannels": min_channels}
            if expectation == "different"
            else None
        ),
        "result": comparison,
        "status": "pass" if not failures else "fail",
        "failures": failures,
    }


def build_comparisons(
    api: str,
    cases: list[dict[str, Any]],
    output_root: Path,
    min_rms: float,
    min_channels: int,
) -> list[dict[str, Any]]:
    by_id = {case["id"]: case for case in cases}
    specs = (
        (
            "classic-normal-vs-subview-only-normal",
            "classic-normal",
            "subview-only-normal",
            "exact",
        ),
        (
            "classic-normal-vs-cinematic-only-normal",
            "classic-normal",
            "cinematic-only-normal",
            "exact",
        ),
        ("classic-normal-vs-both-normal", "classic-normal", "both-normal", "exact"),
        ("classic-skip-vs-both-skip", "classic-skip", "both-skip", "exact"),
        (
            "classic-normal-vs-classic-skip",
            "classic-normal",
            "classic-skip",
            "different",
        ),
        ("both-normal-vs-both-skip", "both-normal", "both-skip", "different"),
    )
    comparisons = [
        compare_images(
            api,
            comparison_id,
            by_id[baseline_id],
            by_id[candidate_id],
            output_root,
            expectation,
            min_rms,
            min_channels,
        )
        for comparison_id, baseline_id, candidate_id, expectation in specs
    ]
    return comparisons


def markdown_escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def diagnostic_summary(case: dict[str, Any]) -> tuple[str, str]:
    diagnostics = case.get("diagnostics")
    if not isinstance(diagnostics, dict):
        return "unavailable", "unavailable"
    cinematic = diagnostics["cinematicPost"]
    subview = diagnostics["subview"]
    cinematic_text = (
        f"req/prep/valid={cinematic['requested']}/{cinematic['prepared']}/{cinematic['valid']} "
        f"post={cinematic['post']} nested={cinematic['nested_views']}/"
        f"{cinematic['nested_transactions']} cin={cinematic['nested_cinematic']} "
        f"GL={cinematic['gl_owned']}/{cinematic['gl_fallback']}/"
        f"{cinematic['gl_mismatch']}/{cinematic['gl_duplicate']} "
        f"VK={cinematic['vk_owned']}/{cinematic['vk_fallback']}/"
        f"{cinematic['vk_mismatch']}/{cinematic['vk_duplicate']}"
    )
    backends = diagnostics["subviewBackends"]
    subview_text = (
        f"req/prep/valid={subview['requested']}/{subview['prepared']}/{subview['valid']} "
        f"views/captures={subview['subviews']}/{subview['captures']} "
        f"GL={backends['gl']['owned']}/{backends['gl']['fallback']} "
        f"VK={backends['vulkan']['owned']}/{backends['vulkan']['fallback']}"
    )
    return cinematic_text, subview_text


def render_markdown(report: dict[str, Any], json_sha256: str) -> str:
    lines = [
        "# Renderer Milestone D Acceptance",
        "",
        f"- Status: `{report['status']}`",
        f"- Generated: `{report['generated']}`",
        f"- Render APIs: `{', '.join(report['renderApis'])}`",
        f"- Runtime: `{report['runtime']['path']}`",
        f"- Runtime file count: `{report['runtime']['fileCount']}`",
        f"- Runtime manifest SHA-256: `{report['runtime']['manifestSha256']}`",
        f"- Runtime remained immutable: `{str(not report['runtimeVerificationFailures']).lower()}`",
        f"- Fixture manifest: `{report['fixture']['manifestPath']}`",
        f"- Fixture manifest SHA-256: `{report['fixture']['manifestSha256']}`",
        f"- Fixture evidence remained immutable: `{str(not report['fixtureVerificationFailures']).lower()}`",
        f"- JSON evidence SHA-256: `{json_sha256}`",
        "- Capture contract: `pacing-only, GPU timers off, bordered windowed 1280x720, engine TGA screenshot`",
        (
            "- Normal-vs-skip minimum: "
            f"`RMS >= {report['differenceMinimums']['rms']}, "
            f"differing channels >= {report['differenceMinimums']['differingChannels']}`"
        ),
        "",
    ]
    if report["failures"]:
        lines.extend(("## Failures", ""))
        lines.extend(f"- {failure}" for failure in report["failures"])
        lines.append("")

    for api_result in report["apis"]:
        lines.extend(
            (
                f"## {api_result['api'].upper()}",
                "",
                f"API status: `{api_result['status']}`",
                "",
                "| Case | Status | Cinematic/post | Subview | Screenshot SHA-256 |",
                "|---|---|---|---|---|",
            )
        )
        for case in api_result["cases"]:
            cinematic, subview = diagnostic_summary(case)
            screenshot = case.get("screenshot") or {}
            lines.append(
                "| "
                + " | ".join(
                    markdown_escape(value)
                    for value in (
                        case["id"],
                        case["status"],
                        cinematic,
                        subview,
                        screenshot.get("sha256", "missing"),
                    )
                )
                + " |"
            )
        lines.extend(("", "### Comparisons", ""))
        lines.extend(
            (
                "| Comparison | Expectation | Status | RMS | Max delta | Differing channels |",
                "|---|---|---|---:|---:|---:|",
            )
        )
        for comparison in api_result["comparisons"]:
            values = comparison.get("result") or {}
            lines.append(
                "| "
                + " | ".join(
                    markdown_escape(value)
                    for value in (
                        comparison["id"],
                        comparison["expectation"],
                        comparison["status"],
                        values.get("rms", "n/a"),
                        values.get("maxDelta", "n/a"),
                        values.get("differingChannels", "n/a"),
                    )
                )
                + " |"
            )
        lines.extend(("", "### Commands", ""))
        for case in api_result["cases"]:
            lines.extend(
                (
                    f"#### {case['id']}",
                    "",
                    "```text",
                    case["commandDisplay"],
                    "```",
                    "",
                )
            )
            if case["failures"]:
                lines.extend(f"- Failure: {failure}" for failure in case["failures"])
                lines.append("")
        lines.extend(("### Artifact manifest", ""))
        lines.extend(("| Kind | Relative path | Bytes | SHA-256 |", "|---|---|---:|---|"))
        for case in api_result["cases"]:
            for artifact in case["artifacts"]:
                lines.append(
                    "| "
                    + " | ".join(
                        markdown_escape(value)
                        for value in (
                            artifact["kind"],
                            artifact["path"],
                            artifact["size"],
                            artifact["sha256"],
                        )
                    )
                    + " |"
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def dry_run_plan(
    args: argparse.Namespace,
    runtime_dir: Path,
    output_dir: Path,
    fixture: dict[str, Any],
) -> dict[str, Any]:
    apis = selected_apis(args.render_api)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "plan",
        "dryRun": True,
        "runtime": path_hint(runtime_dir),
        "fixture": {
            "manifestPath": fixture["manifestPath"],
            "manifestSha256": fixture["manifestSha256"],
            "map": fixture["map"],
        },
        "output": path_hint(output_dir),
        "renderApis": list(apis),
        "casesPerApi": len(CASES),
        "commands": [
            {
                "api": api,
                "case": case.case_id,
                "command": build_benchmark_command(
                    args, runtime_dir, output_dir / api / case.case_id, api, case
                ),
            }
            for api in apis
            for case in CASES
        ],
    }


def run_acceptance(args: argparse.Namespace) -> int:
    basepath = Path(args.basepath).resolve() if args.basepath else None
    if basepath is None or not basepath.is_dir():
        raise FileNotFoundError("--basepath must identify an installed Quake 4 root")
    args.basepath = str(basepath)
    runtime_dir = validate_runtime_dir(args.runtime_dir)
    fixture_info = validate_fixture_manifest(
        args.fixture_manifest, runtime_dir, basepath
    )
    output_dir = select_output_dir(args.output_dir)
    if args.dry_run:
        print(
            json.dumps(
                dry_run_plan(args, runtime_dir, output_dir, fixture_info),
                indent=2,
                allow_nan=False,
            )
        )
        return 0

    prepare_output_dir(output_dir)
    runtime_before = benchmark.collect_runtime_files(runtime_dir)
    runtime_info = inventory_summary(runtime_before)
    runtime_info["path"] = path_hint(runtime_dir)
    api_results: list[dict[str, Any]] = []
    top_failures: list[str] = []

    for api in selected_apis(args.render_api):
        cases = [
            run_case(args, runtime_dir, output_dir, runtime_before, api, case)
            for case in CASES
        ]
        comparisons = build_comparisons(
            api,
            cases,
            output_dir,
            args.difference_min_rms,
            args.difference_min_channels,
        )
        api_failures = [
            f"{api}/{case['id']}: {failure}"
            for case in cases
            for failure in case["failures"]
        ] + [
            f"{api}/{comparison['id']}: {failure}"
            for comparison in comparisons
            for failure in comparison["failures"]
        ]
        api_results.append(
            {
                "api": api,
                "status": "pass" if not api_failures else "fail",
                "failures": api_failures,
                "cases": cases,
                "comparisons": comparisons,
            }
        )
        top_failures.extend(api_failures)

    try:
        runtime_after = benchmark.collect_runtime_files(runtime_dir)
        runtime_verification_failures = benchmark.compare_file_records(
            runtime_before, runtime_after, "runtime file"
        )
    except Exception as exc:
        runtime_verification_failures = [
            f"runtime post-run inventory failed: {type(exc).__name__}: {exc}"
        ]
    top_failures.extend(
        f"runtime immutability: {failure}"
        for failure in runtime_verification_failures
    )
    try:
        fixture_after = validate_fixture_manifest(
            args.fixture_manifest, runtime_dir, basepath
        )
        fixture_verification_failures = (
            []
            if fixture_after == fixture_info
            else ["fixture manifest, evidence, or bound runtime records changed during acceptance"]
        )
    except Exception as exc:
        fixture_verification_failures = [
            f"fixture post-run verification failed: {type(exc).__name__}: {exc}"
        ]
    top_failures.extend(
        f"fixture immutability: {failure}"
        for failure in fixture_verification_failures
    )

    report: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "status": "pass" if not top_failures else "fail",
        "dryRun": False,
        "generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "profile": "milestone-d-nested-dynamic",
        "renderApis": list(selected_apis(args.render_api)),
        "casesPerApi": len(CASES),
        "captureContract": {
            "pacingOnly": True,
            "gpuTimers": False,
            "display": "windowed",
            "width": 1280,
            "height": 720,
            "screenshotSource": "engine screenshot command",
            "screenshotFormat": "TGA",
            "settleFrames": args.settle_frames,
            "sampleFrames": args.sample_frames,
        },
        "differenceMinimums": {
            "rms": args.difference_min_rms,
            "differingChannels": args.difference_min_channels,
        },
        "runtime": runtime_info,
        "runtimeVerificationFailures": runtime_verification_failures,
        "fixture": fixture_info,
        "fixtureVerificationFailures": fixture_verification_failures,
        "outputRoot": path_hint(output_dir),
        "reports": {
            "json": REPORT_JSON_NAME,
            "markdown": REPORT_MD_NAME,
        },
        "failures": top_failures,
        "apis": api_results,
    }
    json_path = output_dir / REPORT_JSON_NAME
    md_path = output_dir / REPORT_MD_NAME
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    json_sha = sha256_file(json_path)
    md_path.write_text(
        render_markdown(report, json_sha), encoding="utf-8", newline="\n"
    )
    print(f"wrote {md_path}")
    print(f"wrote {json_path}")
    print(f"renderer Milestone D acceptance: {report['status']}")
    return 0 if report["status"] == "pass" else 1


def main(argv: list[str]) -> int:
    try:
        args = parse_args(argv)
        return run_acceptance(args)
    except (EvidenceError, FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
