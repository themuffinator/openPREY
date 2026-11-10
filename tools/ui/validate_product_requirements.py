#!/usr/bin/env python3
"""Validate a scoped, unaccepted UI checkpoint against an immutable Git baseline.

This audit preserves normative requirement fields and migration records. It does
not prove implementation completeness or qualify tests, screenshots or artwork.
Hash deferral is explicitly reported as incomplete and is only for preparation.

An implementation increment keeps every requirement and changes only evidence,
remaining scope and explicit pending-to-partial states. A register revision
(--revision) instead appends requirements and records supersessions for a
changed normative source; it cannot edit, remove or accept existing rows.
Both may re-bind document hashes. A binding matches its file in either
line-ending form, so LF and CRLF checkouts of one commit audit alike.

An archive relocation (--archive-relocation) preserves the complete register
and migration records while moving source-document references through a checked
archive manifest and adding the consolidated planning authority. Historical
local captures remain unchanged and are reported separately, never requalified.

None of those modes accepts work. Acceptance has its own, separately reviewed
transition (--acceptance with --accept/--accept-resource, implemented in
acceptance_transition.py): it names every requirement and resource it accepts
and audits each one's committed acceptance records. An implementation increment
keeps earlier acceptance only while its evidence still describes the present
files; otherwise it must withdraw it explicitly (--withdraw/--withdraw-resource),
keeping the records as history.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import types


REQUIREMENT_FIELDS = ("id", "title", "milestone_owner", "implementation_owner", "source_refs", "requirement",
                      "dependencies", "acceptance_evidence_needed", "status", "current_evidence",
                      "acceptance_evidence", "remaining")
SUPERSESSION_FIELDS = ("superseded", "successors", "normative_change", "source_refs", "carried_evidence")


class AuditError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def read_json(text: str):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(AuditError(f"Nonfinite JSON value: {value}")))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def line_ending_digests(path: Path) -> set:
    # Checkouts differ only by text=auto line endings (LF or CRLF), so a
    # binding made on either kind of checkout matches the same content.
    data = path.read_bytes()
    lf = data.replace(b"\r\n", b"\n")
    return {hashlib.sha256(variant).hexdigest() for variant in (data, lf, lf.replace(b"\n", b"\r\n"))}


def repaired_dash(text: str) -> str:
    # Only the observed reversible en-dash encoding defect is admissible in an
    # otherwise immutable normative field. No fuzzy or replacement decoding.
    correct = "–"
    once = correct.encode("utf-8").decode("cp1252")
    twice = once.encode("utf-8").decode("cp1252")
    require(twice.encode("cp1252").decode("utf-8") == once and
            once.encode("cp1252").decode("utf-8") == correct, "Encoding repair is not reversible")
    return text.replace(twice, correct).replace(once, correct)


def require_acyclic(rows: dict) -> None:
    visited = set()
    def visit(name, active):
        require(name not in active, f"Dependency cycle: {name}")
        if name not in visited:
            for dep in rows[name]["dependencies"]:
                visit(dep, active | {name})
            visited.add(name)
    for name in rows:
        visit(name, set())


def check_migration_manifest(root: Path, git, revision: str, current: dict, withdrawn=()):
    manifest_path = root / "docs/dev/ui/migration-manifest.json"
    manifest = manifest_path.read_text(encoding="utf-8")
    baseline_text = git("show", revision + ":docs/dev/ui/migration-manifest.json")
    resources, old_resources = read_json(manifest)["resources"], read_json(baseline_text)["resources"]
    withdrawn = set(withdrawn)
    if not withdrawn:
        require(manifest.replace("\r\n", "\n") == baseline_text.replace("\r\n", "\n"), "Migration source records changed")
    else:
        # Withdrawal returns accepted resources to pending; nothing else moves.
        new_document, old_document = read_json(manifest), read_json(baseline_text)
        require(all(new_document[key] == old_document[key] for key in old_document if key != "resources") and
                new_document.keys() == old_document.keys(), "Migration source records changed")
        require([row["resource_id"] for row in resources] == [row["resource_id"] for row in old_resources], "Migration source records changed")
        require(withdrawn <= {row["resource_id"] for row in old_resources if row["translation_status"] == "accepted"},
                "Only an accepted migration resource can be withdrawn")
        for row, old in zip(resources, old_resources):
            expected = dict(old, translation_status="pending", replacement=None, bitmap_exceptions=None,
                            behavior_evidence=[], visual_evidence=[]) if old["resource_id"] in withdrawn else old
            require(row == expected, f"Migration source records changed: {old['resource_id']}")
    require(len(resources) == current["baseline"]["effective_gui_count"], "Migration inventory denominator changed")
    # Resources accepted by an earlier acceptance transition stay accepted;
    # no checkpoint accepts one.
    require(all(row["translation_status"] == "accepted" or (row["translation_status"] == "pending" and not row["replacement"] and
                not row["behavior_evidence"] and not row["visual_evidence"]) for row in resources), "Checkpoint cannot accept a GUI migration")
    require(current["baseline"].get("translated_or_accepted_resources", 0) == sum(row["translation_status"] == "accepted" for row in resources),
            "Baseline accepted-resource count differs from the manifest")
    return manifest_path, resources


def audit_helpers():
    """The shared checks, handed to the separately reviewed transition module."""
    return types.SimpleNamespace(require=require, read_json=read_json, digest=digest, line_ending_digests=line_ending_digests,
                                 archive_path=archive_path, clean_text=clean_text, require_acyclic=require_acyclic,
                                 check_source_bindings=check_source_bindings, check_markdown=check_markdown,
                                 __file__=str(Path(__file__).resolve()))


def load_sibling(name: str):
    path = Path(__file__).resolve().with_name(name + ".py")
    spec = importlib.util.spec_from_file_location("openq4_ui_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_source_bindings(root: Path, current: dict, previous: dict, defer_hashes: bool):
    files, deferred, historical_unbound = {}, [], []
    for group in ("normative_sources", "evidence"):
        for name, item in current[group].items():
            for path_key, hash_key in (("path", "sha256"), ("local_capture_summary", "local_capture_summary_sha256")):
                if path_key not in item:
                    continue
                source = (root / item[path_key]).resolve()
                require(source.is_relative_to(root) and source.is_file(), f"Missing/outside evidence path: {name}.{path_key}")
                actual = digest(source)
                files[str(source.relative_to(root)).replace("\\", "/")] = actual
                old_item = previous[group].get(name, {})
                if (group == "evidence" and path_key == "local_capture_summary" and
                        old_item.get(path_key) == item[path_key] and hash_key not in old_item and hash_key not in item):
                    # Preserve the historical record exactly. Observing its
                    # present bytes cannot retroactively bind the old capture.
                    historical_unbound.append({"evidence": name, "path": item[path_key],
                        "observed_sha256": actual, "baseline_hash_binding": False})
                    continue
                if item.get(hash_key) not in line_ending_digests(source):
                    require(defer_hashes, f"Missing/stale source binding: {name}.{hash_key}")
                    deferred.append(f"{group}.{name}.{hash_key}")
    return files, deferred, historical_unbound


def check_markdown(root: Path, markdown_path: Path, rows: dict, product_path: str):
    links = 0
    for path in (markdown_path, root / product_path, root / "docs/dev/ui/value-controls.md"):
        content = path.read_text(encoding="utf-8")
        require(repaired_dash(content) == content and "�" not in content, f"Mojibake/replacement characters remain: {path}")
        for link in re.findall(r"\]\(([^)]+)\)", content):
            if "://" in link or link.startswith("#"):
                continue
            require((path.parent / link.split("#")[0]).resolve().exists(), f"Broken local link: {path}: {link}")
            links += 1
    counts = Counter(row["status"] for row in rows.values())
    verified = 'one' if counts['verified'] == 1 else str(counts['verified'])
    count_text = f"{counts['partial']} partial, {counts['pending']} pending and {verified} verified requirement"
    require(count_text in markdown_path.read_text(encoding="utf-8"), "Markdown status totals are stale")
    return links, counts


def validate(args) -> dict:
    root = args.root.resolve()
    def git(*items):
        return subprocess.check_output(["git", "-c", "core.safecrlf=false", *items], cwd=root).decode("utf-8")
    revision = git("rev-parse", "--verify", args.baseline + "^{commit}").strip()
    register_path = (args.register or root / "docs/dev/ui/product-requirements.json").resolve()
    markdown_path = root / "docs/dev/ui/product-requirements.md"
    current = read_json(register_path.read_text(encoding="utf-8"))
    previous = read_json(git("show", revision + ":docs/dev/ui/product-requirements.json"))
    require(current.keys() == previous.keys(), "Register top-level schema changed")
    protected = ("schema_version", "id_namespace", "milestones", "schema_contract", "evidence_policy", "groups", "audit_findings")
    # Supersessions are recorded only by a register revision (--revision).
    protected += ("supersessions",) if "supersessions" in previous else ()
    for key in protected:
        require(current[key] == previous[key], f"Protected register contract changed: {key}")
    withdrawn = set(getattr(args, "withdraw", []))
    withdrawn_resources = set(getattr(args, "withdraw_resource", []))
    for key, value in previous["baseline"].items():
        # A resource withdrawal lowers the accepted-resource count, which the
        # manifest check below recomputes.
        if key != "engine_revision" and not (key == "translated_or_accepted_resources" and withdrawn_resources):
            require(current["baseline"][key] == value, f"Protected baseline field changed: {key}")
    require(current["baseline"].keys() == previous["baseline"].keys(), "Baseline schema changed")
    require(current["baseline"]["engine_revision"] == revision, "Current increment must identify the audited baseline revision")
    require(current["normative_sources"].keys() == previous["normative_sources"].keys(), "Normative source set changed")
    for name, source in previous["normative_sources"].items():
        require({k: v for k, v in source.items() if k != "sha256"} ==
                {k: v for k, v in current["normative_sources"][name].items() if k != "sha256"},
                f"Normative source authority/path changed: {name}")

    before = {row["id"]: row for row in previous["requirements"]}
    rows = {row["id"]: row for row in current["requirements"]}
    require(len(rows) == len(current["requirements"]) == len(before), "Requirement IDs/count changed or duplicated")
    require([row["id"] for row in current["requirements"]] ==
            [row["id"] for row in previous["requirements"]], "Requirement order/identity changed")
    allowed = set(args.partial)
    require(allowed <= rows.keys(), "Unknown --partial requirement")
    require(withdrawn <= rows.keys() and not (withdrawn & allowed), "Unknown or conflicting --withdraw requirement")
    changes, status_changes, repairs = {}, {}, {}
    for name, row in rows.items():
        old = before[name]
        require(row.keys() == old.keys(), f"Requirement schema changed: {name}")
        require(re.fullmatch(r"[A-Z]+-[0-9]{3}", name) is not None and name.split("-")[0] in current["groups"], f"Invalid grouped identity: {name}")
        require(row["milestone_owner"] in current["milestones"], f"Unknown milestone: {name}")
        require(bool(row["remaining"].strip()), f"Missing remaining scope: {name}")
        require(row["status"] in current["schema_contract"]["status_values"], f"Unknown status: {name}")
        require(all(dep in rows for dep in row["dependencies"]), f"Unknown dependency: {name}")
        require(len(row["dependencies"]) == len(set(row["dependencies"])), f"Duplicate dependency: {name}")
        require(all(ref.split(":", 1)[0] in current["normative_sources"] for ref in row["source_refs"]), f"Unknown normative source: {name}")
        for field in ("current_evidence", "acceptance_evidence"):
            require(len(row[field]) == len(set(row[field])) and all(ref in current["evidence"] for ref in row[field]), f"Invalid evidence reference: {name}.{field}")
        require(set(old["current_evidence"]) <= set(row["current_evidence"]), f"Historical requirement evidence removed: {name}")
        if row["status"] == "verified":
            require(bool(row["acceptance_evidence"]), f"Verified requirement lacks acceptance evidence: {name}")
        else:
            require(not row["acceptance_evidence"], f"Unaccepted requirement has acceptance evidence: {name}")
        changed = []
        for field, value in row.items():
            if value == old[field]:
                continue
            changed.append(field)
            if field == "requirement" and isinstance(value, str) and repaired_dash(old[field]) == value:
                repairs[name] = {"before": old[field], "after": value}
            elif field == "status" and name in withdrawn:
                require(old[field] == "verified" and value == "partial", f"Withdrawal returns a verified requirement to partial: {name}")
                status_changes[name] = {"before": old[field], "after": value}
            elif field == "status":
                require(name in allowed and old[field] == "pending" and value == "partial", f"Unauthorized acceptance/status change: {name}")
                status_changes[name] = {"before": old[field], "after": value}
            elif field == "acceptance_evidence":
                require(name in withdrawn and value == [], f"Unauthorized acceptance evidence change: {name}")
            else:
                require(field in ("remaining", "current_evidence"), f"Normative scope/constraints/acceptance changed: {name}.{field}")
        if name in withdrawn:
            # The withdrawn records stay as history of what was claimed.
            history = list(dict.fromkeys(old["current_evidence"] + old["acceptance_evidence"]))
            require(row["current_evidence"][:len(history)] == history, f"Withdrawal must keep the acceptance records as evidence history: {name}")
        if changed:
            changes[name] = changed
        if name.startswith(("GATE-", "FINAL-")):
            # Gates are accepted only by an acceptance transition; a checkpoint
            # keeps their state or withdraws an accepted one.
            require(row["status"] == old["status"] or name in withdrawn, f"Checkpoint cannot accept a product gate: {name}")
    require(allowed | withdrawn == status_changes.keys(), "--partial and --withdraw lists must match actual status changes exactly")

    require_acyclic(rows)
    require(all(name in rows for group in current["audit_findings"].values() for name in group), "Unresolved audit finding")
    require(set(current["audit_findings"]) == {f"UI-{i:02}" for i in range(1, 13)}, "Incomplete audit finding map")
    require(len([name for name in rows if name.startswith("FINAL-")]) == 7, "Incomplete final audit map")
    for name, item in previous["evidence"].items():
        require(name in current["evidence"], f"Historical evidence removed: {name}")
        require({k: v for k, v in item.items() if k != "sha256"} ==
                {k: v for k, v in current["evidence"][name].items() if k != "sha256"}, f"Historical evidence scope/result/binding changed: {name}")

    manifest_path, resources = check_migration_manifest(root, git, revision, current, withdrawn_resources)
    # Earlier acceptance stays only while its records describe the present files.
    transition = load_sibling("acceptance_transition")
    stale = transition.accepted_record_problems(transition.Repository(audit_helpers(), root, revision), current,
                                                {row["resource_id"]: row for row in resources}, rows)
    require(not stale, "Accepted scope has stale evidence; withdraw it (--withdraw/--withdraw-resource) or accept it again: " +
            "; ".join(f"{key}: {', '.join(value)}" for key, value in sorted(stale.items())))
    files, deferred, historical_unbound = check_source_bindings(root, current, previous, args.defer_hashes)
    links, counts = check_markdown(root, markdown_path, rows, current["normative_sources"]["product"]["path"])
    gates = [name for name in rows if name.startswith(("GATE-", "FINAL-"))]
    return {
        "schema_version": 1, "status": "structure_valid_hashes_deferred" if args.defer_hashes else "structural_source_audit_passed",
        "product_acceptance": False, "baseline_engine_revision": revision,
        "companion_revision": current["baseline"]["companion_revision"],
        "register_sha256": digest(register_path), "markdown_sha256": digest(markdown_path),
        "plan_sha256": digest(root / current["normative_sources"]["product"]["path"]),
        "validator_sha256": digest(Path(__file__).resolve()),
        "requirements": len(rows), "status_counts": dict(counts), "status_changes": status_changes,
        "withdrawn_requirements": sorted(withdrawn), "withdrawn_resources": sorted(withdrawn_resources),
        "requirement_field_changes": changes, "strict_roundtrip_text_repairs": repairs,
        "scope_constraints_owners_dependencies_and_acceptance_preserved": True,
        "dependency_cycles": 0, "all_milestone_and_final_gates_pending": all(rows[name]["status"] == "pending" for name in gates),
        "earlier_acceptance_current": True,
        "historical_evidence_preserved_except_document_hashes": True,
        "migration_manifest_unchanged": not withdrawn_resources, "migration_manifest_sha256": digest(manifest_path),
        "migration_entries": len(resources),
        "accepted_migration_entries": sum(row["translation_status"] == "accepted" for row in resources),
        "required_source_bindings_valid": not args.defer_hashes,
        "source_paths_and_hashes_valid": not args.defer_hashes and not historical_unbound,
        "historical_unbound_references": historical_unbound, "deferred_hash_bindings": deferred,
        "source_hashes": files, "local_links_checked": links,
        "limitations": "Structural/source-binding audit only; no build, test, runtime, artwork or product acceptance is inferred from linked evidence. Historical unbound summary pointers are preserved and explicitly reported; their observed current bytes do not establish a historical capture hash."
    }


def clean_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip()) and repaired_dash(value) == value and "�" not in value


def validate_revision(args) -> dict:
    root = args.root.resolve()
    def git(*items):
        return subprocess.check_output(["git", "-c", "core.safecrlf=false", *items], cwd=root).decode("utf-8")
    revision = git("rev-parse", "--verify", args.baseline + "^{commit}").strip()
    register_path = (args.register or root / "docs/dev/ui/product-requirements.json").resolve()
    markdown_path = root / "docs/dev/ui/product-requirements.md"
    current = read_json(register_path.read_text(encoding="utf-8"))
    previous = read_json(git("show", revision + ":docs/dev/ui/product-requirements.json"))
    require(not args.partial and not getattr(args, "withdraw", []) and not getattr(args, "withdraw_resource", []),
            "A register revision cannot change requirement status; audit status changes as an increment")

    # Contract: keep every existing entry; only additions are admissible.
    require(set(previous) <= set(current) and set(current) - set(previous) <= {"supersessions"},
            "Register top-level schema changed beyond a supersession record")
    require(isinstance(current["schema_version"], int) and current["schema_version"] >= previous["schema_version"], "Register schema version decreased")
    for key in ("id_namespace", "milestones"):
        require(current[key] == previous[key], f"Protected register contract changed: {key}")
    for key in ("groups", "schema_contract"):
        require(all(current[key].get(name) == value for name, value in previous[key].items()),
                f"A register revision cannot edit an existing {key} entry")
    old_policy, new_policy = previous["evidence_policy"], current["evidence_policy"]
    require(new_policy.keys() == old_policy.keys() and
            new_policy["per_acceptance_record_required"] == old_policy["per_acceptance_record_required"] and
            new_policy["constraints"][:len(old_policy["constraints"])] == old_policy["constraints"],
            "A register revision may only append evidence policy constraints")
    require(all(clean_text(text) for text in new_policy["constraints"]), "Invalid evidence policy constraint text")
    for key, value in previous["baseline"].items():
        if key != "engine_revision":
            require(current["baseline"][key] == value, f"Protected baseline field changed: {key}")
    require(current["baseline"]["engine_revision"] == revision, "Current revision must identify the audited baseline revision")
    require(current["normative_sources"].keys() == previous["normative_sources"].keys(), "Normative source set changed")
    for name, source in previous["normative_sources"].items():
        require({k: v for k, v in source.items() if k != "sha256"} ==
                {k: v for k, v in current["normative_sources"][name].items() if k != "sha256"},
                f"Normative source authority/path changed: {name}")
    # As in an increment, evidence records keep their scope and result; only a
    # document hash may be re-bound, and the binding check below verifies it.
    require(current["evidence"].keys() == previous["evidence"].keys(), "A register revision cannot add or remove evidence records")
    for name, item in previous["evidence"].items():
        require({k: v for k, v in item.items() if k != "sha256"} ==
                {k: v for k, v in current["evidence"][name].items() if k != "sha256"}, f"Historical evidence scope/result/binding changed: {name}")
    rebound = {f"{group}.{name}": {"before": item.get("sha256"), "after": current[group][name].get("sha256")}
               for group in ("normative_sources", "evidence") for name, item in previous[group].items()
               if item.get("sha256") != current[group][name].get("sha256")}

    # Existing requirements stay byte-identical and in order; new ones append.
    old_rows = previous["requirements"]
    require([row["id"] for row in current["requirements"][:len(old_rows)]] == [row["id"] for row in old_rows],
            "Existing requirement order/identity changed")
    for old, row in zip(old_rows, current["requirements"]):
        require(row == old, f"A register revision cannot edit an existing requirement: {old['id']}")
    rows = {row["id"]: row for row in current["requirements"]}
    require(len(rows) == len(current["requirements"]), "Duplicate requirement ID")
    added = current["requirements"][len(old_rows):]
    added_ids = [row["id"] for row in added]
    last_number = {}
    for row in old_rows:
        group, number = row["id"].split("-")
        last_number[group] = max(last_number.get(group, 0), int(number))
    for row in added:
        name = row["id"]
        require(isinstance(name, str) and re.fullmatch(r"[A-Z]+-[0-9]{3}", name) is not None and name.split("-")[0] in current["groups"],
                f"Invalid grouped identity: {name}")
        group, number = name.split("-")
        require(int(number) == last_number.get(group, 0) + 1, f"Appended IDs must continue their group sequence: {name}")
        last_number[group] = int(number)
        require(tuple(row)[:len(REQUIREMENT_FIELDS)] == REQUIREMENT_FIELDS and set(row) <= set(REQUIREMENT_FIELDS) | {"constraints"},
                f"Requirement schema differs: {name}")
        owner = current["groups"][group]
        require(row["implementation_owner"] == owner["implementation_owner"], f"Implementation owner differs from its group: {name}")
        require(all(ref in row["source_refs"] for ref in owner["source_refs"]) and
                all(ref.split(":", 1)[0] in current["normative_sources"] for ref in row["source_refs"]),
                f"Source references must include the group references and known sources: {name}")
        require(row["milestone_owner"] in current["milestones"], f"Unknown milestone: {name}")
        require(all(clean_text(row[field]) for field in ("title", "requirement", "remaining")), f"Invalid requirement text: {name}")
        require(bool(row["acceptance_evidence_needed"]) and all(clean_text(text) for text in row["acceptance_evidence_needed"]),
                f"Missing acceptance evidence description: {name}")
        require(row["status"] in ("pending", "partial"), f"A register revision cannot accept a requirement: {name}")
        require(not row["acceptance_evidence"], f"Unaccepted requirement has acceptance evidence: {name}")
        require(row["status"] == "pending" or bool(row["current_evidence"]), f"Partial requirement needs current evidence: {name}")
        require(len(row["current_evidence"]) == len(set(row["current_evidence"])) and
                all(ref in current["evidence"] for ref in row["current_evidence"]), f"Invalid evidence reference: {name}.current_evidence")
        require(all(dep in rows and dep != name for dep in row["dependencies"]) and
                len(row["dependencies"]) == len(set(row["dependencies"])), f"Invalid dependency: {name}")
        require("constraints" not in row or (isinstance(row["constraints"], dict) and row["constraints"]), f"Empty constraints: {name}")
    require_acyclic(rows)
    require(len([name for name in rows if name.startswith("FINAL-")]) == 7, "Incomplete final audit map")

    # Supersessions link replaced requirements to successors appended here.
    old_records = previous.get("supersessions", [])
    records = current.get("supersessions", [])
    require(isinstance(records, list) and records[:len(old_records)] == old_records, "Recorded supersessions changed")
    superseded = [record["superseded"] for record in old_records]
    new_records = records[len(old_records):]
    for record in new_records:
        require(tuple(record) == SUPERSESSION_FIELDS, f"Supersession schema differs: {record}")
        name = record["superseded"]
        require(name in {row["id"] for row in old_rows}, f"Only an existing requirement can be superseded: {name}")
        require(name not in superseded, f"Requirement superseded twice: {name}")
        superseded.append(name)
        successors = record["successors"]
        require(bool(successors) and len(successors) == len(set(successors)) and all(item in added_ids for item in successors),
                f"Successors must be requirements appended by this revision: {name}")
        require(clean_text(record["normative_change"]), f"Missing normative change: {name}")
        require(bool(record["source_refs"]) and all(ref.split(":", 1)[0] in current["normative_sources"] for ref in record["source_refs"]),
                f"Invalid supersession source reference: {name}")
        carried = record["carried_evidence"]
        require(all(item in rows[name]["current_evidence"] for item in carried) and
                all(any(item in rows[successor]["current_evidence"] for successor in successors) for item in carried),
                f"Carried evidence must come from the superseded row and reach a successor: {name}")
    # A later revision may supersede an earlier successor, forming a chain; a
    # chain must end in requirements that still define acceptance.
    chain = {record["superseded"]: record["successors"] for record in records}
    def leaves(name, seen=()):
        require(name not in seen, f"Supersession cycle: {name}")
        return [leaf for item in chain[name] for leaf in (leaves(item, seen + (name,)) if item in chain else [item])]
    require(all(leaves(name) for name in chain), "Supersession chain without a successor")
    require(bool(added) or bool(new_records), "A register revision must append requirements or record supersessions")

    # Audit findings keep their mapping; successors may be appended.
    require(current["audit_findings"].keys() == previous["audit_findings"].keys(), "Audit finding set changed")
    for finding, names in previous["audit_findings"].items():
        extension = current["audit_findings"][finding][len(names):]
        require(current["audit_findings"][finding][:len(names)] == names and all(item in added_ids for item in extension),
                f"Audit finding may only append requirements added by this revision: {finding}")
    require(all(name in rows for group in current["audit_findings"].values() for name in group), "Unresolved audit finding")

    manifest_path, resources = check_migration_manifest(root, git, revision, current)
    files, deferred, historical_unbound = check_source_bindings(root, current, previous, args.defer_hashes)
    links, counts = check_markdown(root, markdown_path, rows, current["normative_sources"]["product"]["path"])
    return {
        "schema_version": 1, "status": "revision_hashes_deferred" if args.defer_hashes else "register_revision_audit_passed",
        "product_acceptance": False, "baseline_engine_revision": revision,
        "companion_revision": current["baseline"]["companion_revision"],
        "register_schema_version": current["schema_version"],
        "register_sha256": digest(register_path), "markdown_sha256": digest(markdown_path),
        "validator_sha256": digest(Path(__file__).resolve()),
        "requirements": len(rows), "previous_requirements": len(old_rows), "appended_requirements": added_ids,
        "appended_by_group": dict(Counter(name.split("-")[0] for name in added_ids)),
        "supersessions": {record["superseded"]: record["successors"] for record in new_records},
        "status_counts": dict(counts), "existing_requirements_unchanged": True,
        "evidence_preserved_except_document_hashes": True, "rebound_document_hashes": rebound,
        "dependency_cycles": 0, "all_milestone_and_final_gates_pending": all(
            rows[name]["status"] == "pending" for name in rows if name.startswith(("GATE-", "FINAL-"))),
        "migration_manifest_unchanged": True, "migration_manifest_sha256": digest(manifest_path),
        "migration_entries": len(resources), "accepted_migration_entries": 0,
        "required_source_bindings_valid": not args.defer_hashes,
        "source_paths_and_hashes_valid": not args.defer_hashes and not historical_unbound,
        "historical_unbound_references": historical_unbound, "deferred_hash_bindings": deferred,
        "source_hashes": files, "local_links_checked": links,
        "limitations": "Structural/source-binding audit of a scope revision only; appended requirements are unaccepted and no implementation, artwork or product acceptance is inferred."
    }


def archive_path(root: Path, value: str) -> Path:
    """Require a canonical, project-relative path without link traversal."""
    require(isinstance(value, str) and bool(value) and "\\" not in value and ":" not in value,
            f"Invalid archive path: {value}")
    relative = PurePosixPath(value)
    require(not relative.is_absolute() and relative.as_posix() == value and
            all(part not in (".", "..") for part in relative.parts), f"Noncanonical archive path: {value}")
    path = root / value
    require(path.resolve().is_relative_to(root), f"Archive path leaves project: {value}")
    for parent in (path, *path.parents):
        if parent == root:
            break
        reparse = (parent.exists() and getattr(parent.lstat(), "st_file_attributes", 0) &
                   getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        require(not parent.is_symlink() and not reparse,
                f"Archive path traverses a link: {value}")
    return path


def validate_archive_relocation(args) -> dict:
    """Only relocate document bindings; never revise requirements or accept work."""
    require(not args.revision and not args.partial and not args.defer_hashes and
            not getattr(args, "withdraw", []) and not getattr(args, "withdraw_resource", []),
            "Archive relocation cannot revise scope/status or defer document hashes")
    root = args.root.resolve()

    def git_bytes(*items):
        return subprocess.check_output(["git", "-c", "core.safecrlf=false", *items], cwd=root)

    revision = git_bytes("rev-parse", "--verify", args.baseline + "^{commit}").decode("ascii").strip()
    manifest_path = archive_path(root, "docs/dev/archive/2026-10-18/manifest.json")
    manifest = read_json(manifest_path.read_text(encoding="utf-8"))
    require(set(manifest) == {"schema_version", "archived_on", "source_revision", "roadmap", "documents"},
            "Archive manifest schema changed")
    require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1,
            "Unsupported archive manifest schema")
    require(manifest["source_revision"] == revision, "Archive source revision differs from audited baseline")
    archived_on = manifest["archived_on"]
    require(isinstance(archived_on, str) and date.fromisoformat(archived_on).isoformat() == archived_on and
            manifest_path.parent.name == archived_on, "Archive date/directory mismatch")
    require(manifest["roadmap"] == "docs/dev/roadmap.md", "Archive must name the consolidated roadmap")
    roadmap = archive_path(root, manifest["roadmap"])
    require(roadmap.is_file(), "Consolidated roadmap is missing")
    documents = manifest["documents"]
    require(isinstance(documents, list) and bool(documents), "Archive manifest has no documents")
    relocations, destination_paths = {}, set()
    for entry in documents:
        require(isinstance(entry, dict) and set(entry) == {
            "original_path", "archived_path", "source_sha256", "archived_sha256", "roadmap_sections"},
            "Archive document schema changed")
        original, archived = entry["original_path"], entry["archived_path"]
        original_path, archived_path = archive_path(root, original), archive_path(root, archived)
        require(original.startswith("docs/dev/") and not original.startswith("docs/dev/archive/") and
                original.endswith(".md"), f"Invalid original planning-document path: {original}")
        require(archived == f"docs/dev/archive/{archived_on}/" + original.removeprefix("docs/dev/"),
                f"Archive destination does not preserve source location: {archived}")
        require(original not in relocations and archived not in destination_paths, "Duplicate archive document")
        require(not original_path.exists(), f"Original plan still exists outside archive: {original}")
        require(archived_path.is_file(), f"Archived plan is missing: {archived}")
        sections = entry["roadmap_sections"]
        require(isinstance(sections, list) and bool(sections) and
                all(isinstance(section, str) and bool(section.strip()) for section in sections) and
                len(sections) == len(set(sections)), f"Missing/duplicate roadmap disposition: {original}")
        source = git_bytes("show", revision + ":" + original)
        require(entry["source_sha256"] == hashlib.sha256(source).hexdigest(),
                f"Archived source Git-object hash mismatch: {original}")
        require(entry["archived_sha256"] in line_ending_digests(archived_path),
                f"Archived document hash mismatch: {archived}")
        relocations[original] = archived
        destination_paths.add(archived)

    register_path = (args.register or root / "docs/dev/ui/product-requirements.json").resolve()
    require(register_path.is_relative_to(root), "Candidate register leaves project")
    current = read_json(register_path.read_text(encoding="utf-8"))
    previous = read_json(git_bytes("show", revision + ":docs/dev/ui/product-requirements.json").decode("utf-8"))
    require(set(current) == set(previous) | {"planning_authority"}, "Archive relocation changed register schema")
    require(current["planning_authority"] == manifest["roadmap"], "Incorrect register planning authority")
    if "planning_authority" in previous:
        require(previous["planning_authority"] == current["planning_authority"], "Existing planning authority changed")
    for key, value in previous.items():
        if key not in ("normative_sources", "evidence", "planning_authority"):
            require(current[key] == value, f"Archive relocation changed protected register field: {key}")

    bindings, rebound, relocated, historical = {}, {}, {}, []
    for group in ("normative_sources", "evidence"):
        require(current[group].keys() == previous[group].keys(), f"Archive relocation changed {group} identities")
        for name, old in previous[group].items():
            item = current[group][name]
            require(item.keys() == old.keys(), f"Archive relocation changed source/evidence schema: {name}")
            expected = dict(old)
            old_path = old.get("path")
            is_document = isinstance(old_path, str) and old_path.startswith("docs/")
            if is_document:
                expected["path"] = relocations.get(old_path, old_path)
                # Documents legitimately change their local links and archive notice.
                # Actual bytes are verified below; source authority and every other
                # semantic field remain protected.
                if "sha256" in old:
                    expected["sha256"] = item["sha256"]
            require(item == expected, f"Archive relocation changed source/evidence authority or non-document binding: {name}")
            if is_document:
                path = archive_path(root, item["path"])
                require(path.is_file(), f"Missing relocated/current document: {name}")
                require("sha256" in item and item["sha256"] in line_ending_digests(path),
                        f"Missing/stale document hash: {name}")
                bindings[item["path"]] = digest(path)
                if old_path != item["path"]:
                    relocated[f"{group}.{name}"] = {"before": old_path, "after": item["path"]}
                if old.get("sha256") != item.get("sha256"):
                    rebound[f"{group}.{name}"] = {"before": old.get("sha256"), "after": item.get("sha256")}
            # A source archive cannot recreate or requalify ignored historical
            # captures. Their paths/hashes/scope are preserved exactly above.
            for path_key, hash_key in (("path", "sha256"), ("local_capture_summary", "local_capture_summary_sha256")):
                if path_key not in item or (path_key == "path" and is_document):
                    continue
                path = archive_path(root, item[path_key])
                historical.append({"record": f"{group}.{name}", "field": path_key,
                    "path": item[path_key], "recorded_sha256": item.get(hash_key),
                    "present": path.is_file(), "requalified": False})

    migration_path = archive_path(root, "docs/dev/ui/migration-manifest.json")
    migration_bytes = migration_path.read_bytes().replace(b"\r\n", b"\n")
    previous_migration = git_bytes("show", revision + ":docs/dev/ui/migration-manifest.json").replace(b"\r\n", b"\n")
    require(migration_bytes == previous_migration, "Archive relocation changed migration records")
    rows = {row["id"]: row for row in current["requirements"]}
    require(len(rows) == len(current["requirements"]), "Duplicate requirement identity")
    markdown_path = root / "docs/dev/ui/product-requirements.md"
    links, counts = check_markdown(root, markdown_path, rows, current["normative_sources"]["product"]["path"])
    return {
        "schema_version": 1, "status": "archive_relocation_audit_passed", "product_acceptance": False,
        "archive_source_revision": revision, "archive_manifest_sha256": digest(manifest_path),
        "planning_authority": manifest["roadmap"], "roadmap_sha256": digest(roadmap),
        "register_sha256": digest(register_path), "markdown_sha256": digest(markdown_path),
        "validator_sha256": digest(Path(__file__).resolve()), "archived_documents": len(documents),
        "requirements": len(rows), "status_counts": dict(counts), "requirements_unchanged": True,
        "baseline_metadata_unchanged": True, "source_authority_and_section_references_unchanged": True,
        "evidence_semantics_and_historical_capture_bindings_unchanged": True,
        "migration_manifest_unchanged": True, "migration_manifest_sha256": digest(migration_path),
        "relocated_document_bindings": relocated, "rebound_document_hashes": rebound,
        "source_hashes": bindings, "local_links_checked": links,
        "historical_artifacts_not_requalified": historical,
        "limitations": "Archive/document-binding migration only. Every requirement, acceptance state and migration record is preserved. Archive notices/local links may change document bytes. No implementation, product acceptance or historical capture qualification is inferred; existing increment/revision validation retains its stricter evidence checks."
    }


def validate_inventory_revision(args) -> dict:
    """Source reconciliation may invalidate evidence, never accept product scope."""
    from inventory_revision import validate as validate_inventory
    root = args.root.resolve()
    def git(*items):
        return subprocess.check_output(['git', *items], cwd=root).decode('utf-8')
    revision = git('rev-parse', '--verify', args.baseline + '^{commit}').strip()
    current = read_json((args.register or root / 'docs/dev/ui/product-requirements.json').read_text(encoding='utf-8'))
    previous = read_json(git('show', revision + ':docs/dev/ui/product-requirements.json'))
    evidence_id = args.inventory_evidence_id
    require(re.fullmatch(r'inventory-[a-z0-9-]+', evidence_id) is not None and evidence_id not in previous['evidence'],
            'Choose a new inventory evidence identity; historical evidence cannot be replaced')
    manifest = read_json((root / 'docs/dev/ui/migration-manifest.json').read_text(encoding='utf-8'))
    sources = read_json((root / 'docs/dev/ui/inventory-sources.json').read_text(encoding='utf-8'))
    report = validate_inventory(root, revision, manifest, sources)
    require(current.keys() == previous.keys(), 'Inventory revision changed register schema')
    editable = {'baseline', 'requirements', 'evidence', 'normative_sources', 'date', 'status', 'evidence_policy'}
    for key in previous.keys() - editable:
        require(current[key] == previous[key], f'Inventory revision changed protected field: {key}')
    require(len(current['requirements']) == len(previous['requirements']), 'Inventory revision changed requirement count')
    policy = dict(previous['evidence_policy'])
    policy['constraints'] = [value.replace(
        f"{previous['baseline']['effective_gui_count']} is the current baseline",
        f"{len(manifest['resources'])} is the current baseline") for value in policy['constraints']]
    require(current['evidence_policy'] == policy, 'Inventory revision may only refresh the denominator in evidence policy')
    invalidated = []
    for old, row in zip(previous['requirements'], current['requirements']):
        if row == old:
            continue
        require(row['id'] == old['id'] == 'INV-001', 'Only stale inventory acceptance may be invalidated')
        require({k: v for k, v in row.items() if k not in ('status', 'acceptance_evidence', 'current_evidence', 'remaining')} ==
                {k: v for k, v in old.items() if k not in ('status', 'acceptance_evidence', 'current_evidence', 'remaining')},
                'Inventory revision changed normative inventory requirement')
        require(row['status'] == 'partial' and row['acceptance_evidence'] == [] and clean_text(row['remaining']),
                'Inventory revision cannot accept a requirement')
        require(row['current_evidence'] == old['current_evidence'] + [evidence_id], 'Inventory history was not preserved')
        invalidated.append(row['id'])
    require(invalidated == ['INV-001'], 'Stale inventory verification must be withdrawn')
    expected = dict(previous['baseline'], engine_revision=revision, companion_revision=revision,
                    effective_gui_count=len(manifest['resources']), inventory_refresh_evidence=evidence_id)
    require(current['baseline'] == expected, 'Inventory denominator/source identity differs')
    historical = []
    for group in ('normative_sources', 'evidence'):
        require(set(current[group]) == set(previous[group]) | ({evidence_id} if group == 'evidence' else set()),
                f'Inventory revision changed {group} identities')
        for name, old in previous[group].items():
            item = current[group][name]
            is_document = old.get('path', '').startswith('docs/')
            expected = dict(old)
            if is_document and 'sha256' in old:
                expected['sha256'] = item['sha256']
            require(item == expected, f'Inventory revision changed historical evidence/authority: {name}')
            if is_document:
                path = archive_path(root, item['path'])
                require(path.is_file() and item.get('sha256') in line_ending_digests(path), f'Stale document binding: {name}')
            else:
                historical.append({'evidence': name, 'path': old.get('path'), 'requalified': False})
    item = current['evidence'][evidence_id]
    require(item.get('path') == 'docs/dev/ui/inventory-sources.json' and
            item.get('sha256') in line_ending_digests(root / item['path']), 'Stale inventory snapshot binding')
    require(not args.partial and not args.defer_hashes and not getattr(args, 'withdraw', []) and
            not getattr(args, 'withdraw_resource', []), 'Inventory mode cannot grant partial/deferral exceptions')
    rows = {row['id']: row for row in current['requirements']}
    check_markdown(root, root / 'docs/dev/ui/product-requirements.md', rows, current['normative_sources']['product']['path'])
    report.update(product_acceptance=False, invalidated_requirements=invalidated, historical_evidence=historical)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--baseline", required=True, help="Immutable existing Git commit, normally the increment's starting HEAD")
    parser.add_argument("--partial", action="append", default=[], metavar="ID", help="Explicitly permitted pending-to-partial transition; never accepts a requirement")
    parser.add_argument("--register", type=Path, help="Optional candidate register for review/negative-case validation")
    parser.add_argument("--defer-hashes", action="store_true", help="Preparation only: report unfinalized source bindings, never report full validation")
    parser.add_argument("--revision", action="store_true", help="Audit a register revision: appended requirements and recorded supersessions only")
    parser.add_argument("--archive-relocation", action="store_true", help="Audit only the 2026-10-18 plan archive and consolidated planning authority; preserves all requirement and migration states")
    parser.add_argument("--inventory-revision", action="store_true", help="Reconcile source configurations/denominator and invalidate stale inventory acceptance; cannot accept requirements or resources")
    parser.add_argument("--inventory-evidence-id", default="inventory-stage-one", help="New inventory revision evidence identity; use a new inventory-* ID for each later revision")
    parser.add_argument("--acceptance", action="store_true", help="Audit an evidence-controlled acceptance transition (UI-11); only the requirements and resources it names may be accepted")
    parser.add_argument("--accept", action="append", default=[], metavar="ID", help="Acceptance mode: one requirement this transition marks verified; repeat for each")
    parser.add_argument("--accept-resource", action="append", default=[], metavar="RESOURCE_ID", help="Acceptance mode: one migration resource (path@closure) this transition accepts; repeat for each")
    parser.add_argument("--withdraw", action="append", default=[], metavar="ID", help="Increment mode: return a verified requirement to partial, keeping its acceptance records as evidence history")
    parser.add_argument("--withdraw-resource", action="append", default=[], metavar="RESOURCE_ID", help="Increment mode: return an accepted migration resource to pending")
    parser.add_argument("--output", type=Path, required=True, help="New report path; existing evidence is never overwritten")
    args = parser.parse_args()
    try:
        require(not args.output.exists(), "Preserve existing audit; choose a new output path")
        require(sum((args.archive_relocation, args.revision, args.inventory_revision, args.acceptance)) <= 1, 'Select one revision mode')
        require(args.acceptance or not (args.accept or args.accept_resource), "--accept and --accept-resource need --acceptance")
        report = (load_sibling("acceptance_transition").validate(args, audit_helpers()) if args.acceptance else
                  validate_inventory_revision(args) if args.inventory_revision else
                  validate_archive_relocation(args) if args.archive_relocation else
                  validate_revision(args) if args.revision else validate(args))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        print(f"{report['status']}: {args.output}; SHA256 {digest(args.output)}")
        return 0
    except (AuditError, OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f"Requirement audit failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
