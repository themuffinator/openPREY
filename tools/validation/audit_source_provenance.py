#!/usr/bin/env python3
"""Inventory retained Doom 3 license-header families and verify their notices.

The header is an attribution/license-family signal, not proof that the local
file is byte-identical to a file at the audited upstream commit.  This tool is
offline and deliberately makes no legal-compatibility determination.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "docs" / "dev" / "source-provenance-manifest.json"
ADDITIONAL_TERMS_SIGNAL = "subject to certain additional terms"


def canonical_text_bytes(payload: bytes) -> bytes:
    text = payload.decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != 1:
        raise ValueError(f"unsupported provenance manifest schema: {payload.get('schemaVersion')!r}")
    families = payload.get("families")
    if not isinstance(families, dict) or not families:
        raise ValueError("provenance manifest must define at least one header family")
    return payload


def tracked_files(root: Path = ROOT) -> list[Path]:
    try:
        completed = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("source provenance audit requires a Git worktree") from exc

    paths: list[Path] = []
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        relative = Path(raw.decode("utf-8", errors="surrogateescape"))
        path = root / relative
        if path.is_file():
            paths.append(path)
    return sorted(paths)


def read_header(path: Path, limit: int = 16 * 1024) -> str:
    with path.open("rb") as stream:
        return stream.read(limit).decode("utf-8", errors="replace")


def bfg_official_path(local_path: str) -> str:
    if not local_path.startswith("src/"):
        raise ValueError(f"BFG-marked path is outside src/: {local_path}")
    relative = local_path.removeprefix("src/")
    if relative.startswith("imagetools/"):
        relative = "renderer/" + relative.removeprefix("imagetools/")
    return "neo/" + relative


def bfg_origin(local_path: str, family_spec: dict[str, Any]) -> dict[str, str]:
    intermediate_sources = family_spec.get("intermediateSources", {})
    for source_name, source in intermediate_sources.items():
        path = source.get("pathOverrides", {}).get(local_path)
        if path:
            return {
                "classification": "intermediate-fork-lineage",
                "source": source_name,
                "repository": source["repository"],
                "auditedCommit": source["auditedCommit"],
                "auditedPath": path,
            }
    return {
        "classification": "official-snapshot-path",
        "source": "doom3_bfg_official",
        "repository": family_spec["officialRepository"],
        "auditedCommit": family_spec["auditedCommit"],
        "auditedPath": bfg_official_path(local_path),
    }


def inventory(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    family_specs = manifest["families"]
    family_files: dict[str, list[dict[str, str]]] = {name: [] for name in family_specs}
    unclassified: list[str] = []

    # Match the more specific BFG marker before the Doom 3 marker.
    ordered_families = sorted(
        family_specs.items(), key=lambda item: len(item[1]["headerMarker"]), reverse=True
    )
    for path in tracked_files(root):
        relative = path.relative_to(root).as_posix()
        if not relative.startswith("src/"):
            continue
        try:
            header = read_header(path)
        except OSError:
            continue
        matched = None
        for family_name, spec in ordered_families:
            if spec["headerMarker"].casefold() in header.casefold():
                matched = family_name
                break
        if matched is None:
            if ADDITIONAL_TERMS_SIGNAL.casefold() in header.casefold():
                unclassified.append(relative)
            continue

        entry = {"localPath": relative}
        if matched == "doom3_bfg":
            entry.update(bfg_origin(relative, family_specs[matched]))
        family_files[matched].append(entry)

    return {
        "schemaVersion": 1,
        "manifest": MANIFEST_PATH.relative_to(root).as_posix(),
        "families": {
            name: {
                "displayName": family_specs[name]["displayName"],
                "auditedCommit": family_specs[name]["auditedCommit"],
                "count": len(entries),
                "files": entries,
            }
            for name, entries in family_files.items()
        },
        "unclassifiedAdditionalTermsHeaders": unclassified,
    }


def validate(root: Path, manifest: dict[str, Any], report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if manifest.get("textHashNormalization") != "UTF-8; CRLF and CR normalized to LF":
        failures.append("manifest textHashNormalization is missing or unsupported")
    for family_name, spec in manifest["families"].items():
        actual = report["families"].get(family_name, {})
        if actual.get("count") != spec.get("expectedFileCount"):
            failures.append(
                f"{family_name}: expected {spec.get('expectedFileCount')} marked files, "
                f"found {actual.get('count')}"
            )

        commit = spec.get("auditedCommit", "")
        if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
            failures.append(f"{family_name}: auditedCommit is not a lowercase 40-digit Git object id")
        copying_hash = spec.get("officialCopyingSha256", "")
        if len(copying_hash) != 64 or any(ch not in "0123456789abcdef" for ch in copying_hash):
            failures.append(f"{family_name}: officialCopyingSha256 is not a lowercase SHA-256 digest")

        local_terms_hash = spec.get("localAdditionalTermsSha256", "")
        if len(local_terms_hash) != 64 or any(ch not in "0123456789abcdef" for ch in local_terms_hash):
            failures.append(
                f"{family_name}: localAdditionalTermsSha256 is not a lowercase SHA-256 digest"
            )

        terms_path = root / spec["localAdditionalTerms"]
        if not terms_path.is_file():
            failures.append(f"{family_name}: missing {spec['localAdditionalTerms']}")
        else:
            terms_bytes = terms_path.read_bytes()
            canonical_terms = canonical_text_bytes(terms_bytes)
            actual_terms_hash = hashlib.sha256(canonical_terms).hexdigest()
            if actual_terms_hash != local_terms_hash:
                failures.append(
                    f"{family_name}: {spec['localAdditionalTerms']} SHA-256 differs: "
                    f"expected {local_terms_hash}, got {actual_terms_hash}"
                )
            terms = canonical_terms.decode("utf-8")
            if "ADDITIONAL TERMS APPLICABLE" not in terms:
                failures.append(f"{family_name}: local Additional Terms heading is missing")
            for section in ("Replacement of Section 15", "Replacement of Section 16", "LEGAL NOTICES", "INDEMNIFICATION"):
                if section not in terms:
                    failures.append(f"{family_name}: local Additional Terms omit {section!r}")

        for source_name, source in spec.get("intermediateSources", {}).items():
            source_commit = source.get("auditedCommit", "")
            if len(source_commit) != 40 or any(ch not in "0123456789abcdef" for ch in source_commit):
                failures.append(f"{family_name}/{source_name}: auditedCommit is not a lowercase 40-digit Git object id")
            overrides = source.get("pathOverrides", {})
            inventoried = {item["localPath"] for item in actual.get("files", [])}
            unknown = sorted(set(overrides) - inventoried)
            if unknown:
                failures.append(f"{family_name}/{source_name}: overrides do not identify inventoried files: {', '.join(unknown)}")

    unclassified = report["unclassifiedAdditionalTermsHeaders"]
    if unclassified:
        failures.append(
            "unclassified source headers refer to Additional Terms: " + ", ".join(unclassified)
        )
    return failures


def validate_reference_tree(
    report: dict[str, Any],
    source_name: str,
    source_root: Path | None,
) -> list[str]:
    if source_root is None:
        return []
    failures: list[str] = []
    if not source_root.is_dir():
        return [f"{source_name}: reference root does not exist: {source_root}"]
    for entry in report["families"]["doom3_bfg"]["files"]:
        if entry.get("source") != source_name:
            continue
        path = source_root / Path(entry["auditedPath"])
        if not path.is_file():
            failures.append(
                f"{source_name}: configured audited path is absent: {entry['auditedPath']} "
                f"(for {entry['localPath']})"
            )
    return failures


def validate_official_copying(
    family_name: str,
    family_spec: dict[str, Any],
    source_root: Path | None,
) -> list[str]:
    if source_root is None:
        return []
    if not source_root.is_dir():
        return [f"{family_name}: reference root does not exist: {source_root}"]
    copying = source_root / "COPYING.txt"
    if not copying.is_file():
        return [f"{family_name}: reference root is missing COPYING.txt: {source_root}"]
    actual = hashlib.sha256(copying.read_bytes()).hexdigest()
    expected = family_spec["officialCopyingSha256"]
    if actual != expected:
        return [
            f"{family_name}: official COPYING.txt SHA-256 differs: expected {expected}, got {actual}"
        ]
    return []


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if counts, families, or accompanying terms differ from the audited manifest.")
    parser.add_argument("--family", choices=("all", "doom3", "doom3_bfg"), default="all", help="Limit the displayed inventory; checks always cover every family.")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Inventory output format.")
    parser.add_argument("--output", default="", help="Optional output file. The default is stdout.")
    parser.add_argument("--doom3-source", default="", help="Optional official DOOM-3 checkout used to verify COPYING.txt.")
    parser.add_argument("--doom3-bfg-source", default="", help="Optional official DOOM-3-BFG checkout used to verify configured audited paths.")
    parser.add_argument("--rbdoom3-bfg-source", default="", help="Optional RBDOOM-3-BFG checkout used to verify intermediate-fork audited paths.")
    return parser.parse_args(argv)


def render_text(report: dict[str, Any], family_filter: str) -> str:
    lines = ["openQ4 source provenance inventory"]
    for family_name, family in report["families"].items():
        if family_filter != "all" and family_filter != family_name:
            continue
        lines.append(f"\n{family['displayName']}: {family['count']} files")
        for entry in family["files"]:
            upstream = entry.get("auditedPath")
            source = entry.get("source")
            suffix = f" -> {source}:{upstream}" if upstream else ""
            lines.append(f"  {entry['localPath']}{suffix}")
    if report["unclassifiedAdditionalTermsHeaders"]:
        lines.append("\nUnclassified Additional-Terms headers:")
        lines.extend(f"  {path}" for path in report["unclassifiedAdditionalTermsHeaders"])
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    manifest = load_manifest()
    report = inventory(ROOT, manifest)
    failures = validate(ROOT, manifest, report)
    doom3_source = Path(args.doom3_source).resolve() if args.doom3_source else None
    bfg_source = Path(args.doom3_bfg_source).resolve() if args.doom3_bfg_source else None
    failures += validate_official_copying(
        "doom3", manifest["families"]["doom3"], doom3_source
    )
    failures += validate_official_copying(
        "doom3_bfg", manifest["families"]["doom3_bfg"], bfg_source
    )
    failures += validate_reference_tree(
        report,
        "doom3_bfg_official",
        bfg_source,
    )
    failures += validate_reference_tree(
        report,
        "rbdoom3_bfg",
        Path(args.rbdoom3_bfg_source).resolve() if args.rbdoom3_bfg_source else None,
    )

    if args.format == "json":
        displayed = report
        if args.family != "all":
            displayed = dict(report)
            displayed["families"] = {args.family: report["families"][args.family]}
        output = json.dumps(displayed, indent=2) + "\n"
    else:
        output = render_text(report, args.family)

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)

    if args.check and failures:
        for failure in failures:
            print(f"error: {failure}", file=sys.stderr)
        return 1
    if args.check:
        print("source_provenance: ok", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
