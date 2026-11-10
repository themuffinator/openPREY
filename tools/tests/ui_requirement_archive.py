#!/usr/bin/env python3
"""Exercise the production UI register archive audit against real Git fixtures.

Only disposable project-local repositories are created. These checks qualify
archive integrity and protected requirement state, not any UI implementation.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("ui_requirement_validator", ROOT / "tools/ui/validate_product_requirements.py")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class ArchiveRelocationTests(unittest.TestCase):
    def setUp(self):
        self.temp_parent = VALIDATOR.archive_path(ROOT.resolve(), ".tmp/ui-requirement-archive-tests")
        self.temp_parent.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="case-", dir=self.temp_parent)).resolve()
        self.addCleanup(self.clean_fixture)
        self.old_product = "docs/dev/plans/ui-product-completion.md"
        self.old_original = "docs/dev/plans/idtech5-ui.md"
        self.archive_prefix = "docs/dev/archive/2026-10-18/"
        self.visual = "docs/dev/ui-visual-design.md"
        self.write(self.old_product, "# Product scope\n\nFull UI and editor requirements.\n")
        self.write(self.old_original, "# Original scope\n\nAll interfaces remain required.\n")
        self.write(self.visual, "# Visual contract\n\n[Delivery](plans/ui-product-completion.md).\n")
        self.write("docs/dev/ui/value-controls.md", "# Value controls\n")
        self.write("docs/dev/ui/product-requirements.md", "# Requirements\n\n1 partial, 1 pending and one verified requirement\n")
        self.write_json("docs/dev/ui/migration-manifest.json", {"resources": [
            {"path": "guis/main.gui", "translation_status": "pending", "replacement": None}]})
        self.previous = {
            "schema_version": 18, "date": "2026-10-09", "id_namespace": "openq4.ui.product",
            "status": "Implementation incomplete", "baseline": {"engine_revision": "earlier-checkpoint"},
            "normative_sources": {
                "product": {"path": self.old_product, "sha256": self.hash(self.old_product), "authority": "completion scope"},
                "original": {"path": self.old_original, "sha256": self.hash(self.old_original), "authority": "original scope"},
                "visual": {"path": self.visual, "sha256": self.hash(self.visual), "authority": "visual contract"}},
            "evidence": {
                "review": {"path": self.old_product, "sha256": self.hash(self.old_product), "scope": "historical audit"},
                "capture": {"path": ".tmp/old-capture.json", "sha256": "a" * 64, "scope": "historical capture"},
                "bound-summary": {"path": self.visual, "sha256": self.hash(self.visual),
                    "local_capture_summary": ".tmp/bound-summary.json", "local_capture_summary_sha256": "b" * 64},
                "unbound-summary": {"path": self.visual, "sha256": self.hash(self.visual),
                    "local_capture_summary": ".tmp/unbound-summary.json"}},
            "requirements": [
                {"id": "FLOW-001", "status": "partial", "requirement": "Complete flow",
                    "source_refs": ["product:1"], "dependencies": []},
                {"id": "FINAL-001", "status": "pending", "requirement": "Full product gate",
                    "source_refs": ["original:scope"], "dependencies": ["FLOW-001"]},
                {"id": "INV-001", "status": "verified", "requirement": "Inventory evidence",
                    "source_refs": ["visual:1"], "dependencies": []}]
        }
        self.write_json("docs/dev/ui/product-requirements.json", self.previous)
        self.git("init", "--quiet")
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "Immutable archive fixture")
        self.revision = self.git("rev-parse", "HEAD").decode("ascii").strip()
        self.manifest = {"schema_version": 1, "archived_on": "2026-10-18",
            "source_revision": self.revision, "roadmap": "docs/dev/roadmap.md", "documents": []}
        for old in (self.old_product, self.old_original):
            archived = self.archive_prefix + old.removeprefix("docs/dev/")
            source = self.git("show", self.revision + ":" + old)
            self.write(archived, "> Archived; use the roadmap.\n\n" + source.decode("utf-8"))
            (self.root / old).unlink()
            self.manifest["documents"].append({"original_path": old, "archived_path": archived,
                "source_sha256": hashlib.sha256(source).hexdigest(), "archived_sha256": self.hash(archived),
                "roadmap_sections": ["ui"]})
        self.write(self.visual, "# Visual contract\n\n[Delivery](archive/2026-10-18/plans/ui-product-completion.md).\n")
        self.write("docs/dev/roadmap.md", "# Consolidated roadmap\n\n## UI\n\nAll UI requirements survive.\n")
        self.current = copy.deepcopy(self.previous)
        self.current["planning_authority"] = "docs/dev/roadmap.md"
        mappings = {row["original_path"]: row["archived_path"] for row in self.manifest["documents"]}
        for group in ("normative_sources", "evidence"):
            for item in self.current[group].values():
                item["path"] = mappings.get(item["path"], item["path"])
                if item["path"].startswith("docs/"):
                    item["sha256"] = self.hash(item["path"])
        self.args = argparse.Namespace(root=self.root, baseline=self.revision, register=None,
            revision=False, partial=[], defer_hashes=False)

    def clean_fixture(self):
        # Never traverse links or clean any target outside this exact task area.
        target = self.root.resolve()
        if target.parent != self.temp_parent or not target.name.startswith("case-"):
            raise RuntimeError(f"Unsafe test cleanup target: {target}")
        paths = (target, *target.rglob("*"))
        for path in paths:
            reparse = getattr(path.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            if path.is_symlink() or reparse:
                raise RuntimeError(f"Refusing cleanup through a link: {path}")
        # Git object files are read-only on Windows; only this verified fixture
        # is made writable, after the complete link/target check.
        for path in paths:
            if path.is_file():
                path.chmod(path.stat().st_mode | stat.S_IWUSR)
        shutil.rmtree(target)

    def git(self, *args):
        return subprocess.check_output(["git", "-c", "core.autocrlf=false",
            "-c", "core.hooksPath=" + str(self.root / ".no-hooks"),
            "-c", "user.name=Archive test", "-c", "user.email=archive-test@example.invalid",
            "-c", "commit.gpgsign=false", *args], cwd=self.root, stderr=subprocess.PIPE)

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")

    def write_json(self, path, value):
        self.write(path, json.dumps(value, indent=2) + "\n")

    def hash(self, path):
        return hashlib.sha256((self.root / path).read_bytes()).hexdigest()

    def audit(self):
        self.write_json("docs/dev/ui/product-requirements.json", self.current)
        self.write_json(self.archive_prefix + "manifest.json", self.manifest)
        return VALIDATOR.validate_archive_relocation(self.args)

    def test_valid_relocation_preserves_states_and_unavailable_captures(self):
        result = self.audit()
        self.assertEqual(result["status"], "archive_relocation_audit_passed")
        self.assertFalse(result["product_acceptance"])
        self.assertTrue(result["requirements_unchanged"])
        self.assertEqual(result["status_counts"], {"partial": 1, "pending": 1, "verified": 1})
        self.assertEqual(len(result["relocated_document_bindings"]), 3)
        self.assertIn("normative_sources.visual", result["rebound_document_hashes"])
        captures = result["historical_artifacts_not_requalified"]
        self.assertEqual(len(captures), 3)
        self.assertTrue(all(not row["present"] and not row["requalified"] for row in captures))
        self.assertEqual(self.current["baseline"], self.previous["baseline"])

    def test_accepts_git_line_ending_conversion_without_rebinding_archive(self):
        for entry in self.manifest["documents"]:
            path = self.root / entry["archived_path"]
            path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        report = self.audit()
        self.assertEqual(report["status"], "archive_relocation_audit_passed")

    def test_rejects_requirement_content_status_identity_dependencies_and_section_changes(self):
        unchanged = copy.deepcopy(self.current)
        for field, value in (("requirement", "Reduced scope"), ("status", "verified"),
                             ("id", "FLOW-099"), ("dependencies", ["INV-001"]),
                             ("source_refs", ["product:another-section"])):
            with self.subTest(field=field):
                self.current = copy.deepcopy(unchanged)
                self.current["requirements"][0][field] = value
                with self.assertRaisesRegex(VALIDATOR.AuditError, "protected register field: requirements"):
                    self.audit()

    def test_rejects_source_authority_changes(self):
        self.current["normative_sources"]["product"]["authority"] = "historical only, scope removed"
        with self.assertRaisesRegex(VALIDATOR.AuditError, "source/evidence authority"):
            self.audit()

    def test_rejects_arbitrary_register_destination_even_with_a_matching_hash(self):
        self.write("docs/dev/other.md", "# Arbitrary destination\n")
        self.current["normative_sources"]["product"]["path"] = "docs/dev/other.md"
        self.current["normative_sources"]["product"]["sha256"] = self.hash("docs/dev/other.md")
        with self.assertRaisesRegex(VALIDATOR.AuditError, "source/evidence authority"):
            self.audit()

    def test_rejects_arbitrary_manifest_destination(self):
        self.manifest["documents"][0]["archived_path"] = self.archive_prefix + "wrong.md"
        with self.assertRaisesRegex(VALIDATOR.AuditError, "destination does not preserve"):
            self.audit()

    def test_rejects_manifest_source_and_archive_hash_mismatches(self):
        for key, error in (("source_sha256", "Git-object hash mismatch"),
                           ("archived_sha256", "Archived document hash mismatch")):
            with self.subTest(key=key):
                old = self.manifest["documents"][0][key]
                self.manifest["documents"][0][key] = "0" * 64
                with self.assertRaisesRegex(VALIDATOR.AuditError, error):
                    self.audit()
                self.manifest["documents"][0][key] = old

    def test_rejects_document_hash_mismatches_including_unchanged_paths(self):
        for name in ("product", "visual"):
            with self.subTest(name=name):
                old = self.current["normative_sources"][name]["sha256"]
                self.current["normative_sources"][name]["sha256"] = "0" * 64
                with self.assertRaisesRegex(VALIDATOR.AuditError, "Missing/stale document hash"):
                    self.audit()
                self.current["normative_sources"][name]["sha256"] = old

    def test_rejects_historical_capture_rebinding_or_fabricated_hash(self):
        for name, key in (("capture", "sha256"), ("bound-summary", "local_capture_summary_sha256"),
                          ("unbound-summary", "local_capture_summary_sha256")):
            with self.subTest(name=name):
                old = copy.deepcopy(self.current["evidence"][name])
                self.current["evidence"][name][key] = "c" * 64
                with self.assertRaisesRegex(VALIDATOR.AuditError, "source/evidence"):
                    self.audit()
                self.current["evidence"][name] = old

    def test_rejects_migration_changes(self):
        self.write_json("docs/dev/ui/migration-manifest.json", {"resources": []})
        with self.assertRaisesRegex(VALIDATOR.AuditError, "changed migration records"):
            self.audit()

    def test_rejects_unarchived_original(self):
        self.write(self.old_product, "# Still active\n")
        with self.assertRaisesRegex(VALIDATOR.AuditError, "Original plan still exists"):
            self.audit()

    def test_rejects_baseline_or_planning_authority_changes(self):
        self.manifest["source_revision"] = "0" * 40
        with self.assertRaisesRegex(VALIDATOR.AuditError, "source revision differs"):
            self.audit()
        self.manifest["source_revision"] = self.revision
        self.current["planning_authority"] = self.old_original
        with self.assertRaisesRegex(VALIDATOR.AuditError, "Incorrect register planning authority"):
            self.audit()

    def test_rejects_mixed_validation_modes(self):
        for key, value in (("revision", True), ("partial", ["FLOW-001"]), ("defer_hashes", True)):
            with self.subTest(key=key):
                old = getattr(self.args, key)
                setattr(self.args, key, value)
                with self.assertRaisesRegex(VALIDATOR.AuditError, "cannot revise scope/status or defer"):
                    self.audit()
                setattr(self.args, key, old)

    def test_normal_modes_still_reject_archive_governance_changes(self):
        self.write_json("docs/dev/ui/product-requirements.json", self.current)
        for validate in (VALIDATOR.validate, VALIDATOR.validate_revision):
            with self.subTest(mode=validate.__name__):
                with self.assertRaisesRegex(VALIDATOR.AuditError, "Register top-level schema changed"):
                    validate(self.args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
