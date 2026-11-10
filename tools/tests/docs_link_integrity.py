#!/usr/bin/env python3
"""Validate documentation layout, local Markdown links, and generated docs links."""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import sys
import uuid
from html.parser import HTMLParser
from pathlib import Path
from types import ModuleType
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
WORK_BASE = ROOT / ".tmp" / "docs-link-integrity"

SKIP_DIR_NAMES = {
    # .claude holds untracked scratch worktrees; auditing them reports stale
    # copies of files that were already fixed in the real checkout.
    ".claude",
    ".git",
    ".home",
    ".install",
    ".tmp",
    ".vs",
    "__pycache__",
    "subprojects",
}

TEXT_SUFFIXES = {
    ".bat",
    ".cmd",
    ".cfg",
    ".html",
    ".ini",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".txt",
    ".yaml",
    ".yml",
}

ROOT_MARKDOWN = (
    "README.md",
    "BUILDING.md",
    "TECHNICAL.md",
    "LICENSING.md",
    "AGENTS.md",
)

SOURCE_HTML = (
    Path("assets") / "docs" / "README.html",
)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if key.lower() in {"href", "src"} and value:
                self.links.append(value)


def load_module(name: str, path: Path) -> ModuleType:
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def rendered_relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def should_skip(path: Path, root: Path = ROOT) -> bool:
    for part in path.relative_to(root).parts:
        if part in SKIP_DIR_NAMES or part.startswith("builddir"):
            return True
    return False


def iter_text_files(root: Path = ROOT) -> list[Path]:
    files: list[Path] = []
    for parent, dir_names, file_names in os.walk(root):
        parent_path = Path(parent)
        dir_names[:] = [
            name
            for name in dir_names
            if name not in SKIP_DIR_NAMES
            and not name.startswith("builddir")
            and not (parent_path / name).is_symlink()
        ]
        if should_skip(parent_path, root):
            dir_names[:] = []
            continue
        for name in file_names:
            path = parent_path / name
            if path.suffix.lower() in TEXT_SUFFIXES or path.name in ROOT_MARKDOWN:
                if path.is_symlink():
                    raise AssertionError(f"text documentation wiring file must not be a symlink: {path}")
                files.append(path)
    return sorted(files)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise AssertionError(f"text documentation wiring file is not UTF-8: {path}") from exc


def validate_docs_layout() -> None:
    expected_roots = (ROOT / "docs" / "dev", ROOT / "docs" / "user")
    for path in expected_roots:
        if not path.is_dir():
            raise AssertionError(f"expected documentation directory is missing: {path}")

    legacy_roots = (ROOT / ("docs" + "-dev"), ROOT / ("docs" + "-user"))
    for path in legacy_roots:
        if path.exists():
            raise AssertionError(f"legacy documentation directory still exists: {path}")


def validate_no_legacy_path_tokens() -> None:
    legacy_tokens = (
        "docs" + "-dev",
        "docs" + "-user",
        "docs" + "\\" + "dev",
        "docs" + "\\" + "user",
    )
    hits: list[str] = []
    for path in iter_text_files():
        # A valid external reference may preserve an upstream repository's old
        # directory name.  The migration guard owns only local paths and prose,
        # so remove URL targets before looking for legacy openQ4 wiring.
        local_data = re.sub(rb"https?://[^\s)>]+", b"", path.read_bytes())
        for token in legacy_tokens:
            if token.encode("ascii") in local_data:
                hits.append(f"{path.relative_to(ROOT).as_posix()}: contains {token!r}")

    if hits:
        raise AssertionError("legacy documentation path tokens remain:\n" + "\n".join(hits))


def markdown_sources(root: Path = ROOT) -> list[Path]:
    files = [root / name for name in ROOT_MARKDOWN if (root / name).is_file()]
    docs_root = root / "docs"
    if docs_root.is_symlink():
        raise AssertionError(f"documentation root must not be a symlink: {docs_root}")
    if docs_root.is_dir():
        files.extend(sorted(docs_root.rglob("*.md")))
    for path in files:
        if path.is_symlink():
            raise AssertionError(f"symlinked Markdown source is not allowed: {path}")
        if not is_relative_to(path.resolve(), root.resolve()):
            raise AssertionError(f"Markdown source escapes documentation root: {path}")
    return files


def strip_fenced_code(text: str) -> str:
    lines: list[str] = []
    in_fence = False
    for line in text.replace("\r\n", "\n").splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines.append(line)
    return "\n".join(lines)


def is_external_link(target: str) -> bool:
    parsed = urlsplit(target)
    return bool(parsed.scheme or parsed.netloc) or target.startswith(("#", "mailto:", "data:"))


def resolve_markdown_target(source: Path, raw_target: str) -> Path | None:
    target = raw_target.strip()
    if not target or is_external_link(target):
        return None

    target = target.split("#", 1)[0].strip()
    if not target:
        return None

    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]

    return (source.parent / unquote(target)).resolve()


def validate_markdown_links_for_sources(sources: list[Path], root: Path) -> None:
    pattern = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
    missing: list[str] = []
    root = root.resolve()

    for path in sources:
        text = strip_fenced_code(read_text(path))
        for match in pattern.finditer(text):
            candidate = resolve_markdown_target(path, match.group(1))
            if candidate is None:
                continue

            if not is_relative_to(candidate, root):
                missing.append(
                    f"{rendered_relative(path, root)}: {match.group(1).strip()} -> "
                    f"{candidate} (escapes documentation root)"
                )
                continue

            if candidate.exists():
                continue

            missing.append(
                f"{rendered_relative(path, root)}: {match.group(1).strip()} -> "
                f"{rendered_relative(candidate, root)}"
            )

    if missing:
        raise AssertionError("invalid local Markdown links:\n" + "\n".join(missing))


def validate_markdown_links() -> None:
    validate_markdown_links_for_sources(markdown_sources(), ROOT)


def validate_source_html_links() -> None:
    missing: list[str] = []
    checked = 0
    for relative in SOURCE_HTML:
        path = ROOT / relative
        if not path.is_file():
            raise AssertionError(f"source HTML documentation page is missing: {relative.as_posix()}")

        parser = LinkParser()
        parser.feed(path.read_text(encoding="utf-8"))
        for link in parser.links:
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc or link.startswith("#") or not parsed.path:
                continue

            candidate = (path.parent / unquote(parsed.path)).resolve()
            try:
                candidate.relative_to(ROOT)
            except ValueError:
                continue

            checked += 1
            if not candidate.exists():
                missing.append(
                    f"{relative.as_posix()}: {link} -> {candidate.relative_to(ROOT).as_posix()}"
                )

    if missing:
        raise AssertionError("missing source HTML links:\n" + "\n".join(missing))
    if checked == 0:
        raise AssertionError("source HTML link check did not inspect any in-root links")


def make_work_root() -> Path:
    return WORK_BASE / f"{os.getpid()}-{uuid.uuid4().hex}"


def validate_generated_docs_links(work: Path) -> None:
    docs_module = load_module(
        "release_docs_link_integrity_under_test",
        ROOT / "tools" / "build" / "generate_release_docs.py",
    )

    try:
        docs_module.require_markdown_module()
    except RuntimeError as exc:
        print(f"generated docs link check skipped: {exc}", flush=True)
        return

    output_root = work / "generated"
    shutil.rmtree(output_root, ignore_errors=True)
    docs_module.generate_release_docs_site(
        source_root=ROOT,
        output_root=output_root,
        version="0.0.0",
        platform="test",
        arch="test",
    )

    validate_html_tree_links(output_root, output_root)

    package_root = work / "package"
    shutil.rmtree(package_root, ignore_errors=True)
    package_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "assets" / "release" / "README.html", package_root / "README.html")
    shutil.copytree(output_root, package_root / "docs")
    validate_html_tree_links(package_root, package_root)

    shutil.rmtree(output_root, ignore_errors=True)
    shutil.rmtree(package_root, ignore_errors=True)


def validate_html_tree_links(root: Path, boundary: Path) -> None:
    missing: list[str] = []
    checked = 0
    for path in sorted(root.rglob("*.html")):
        parser = LinkParser()
        parser.feed(path.read_text(encoding="utf-8"))
        for link in parser.links:
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc or link.startswith("#") or not parsed.path:
                continue

            candidate = (path.parent / unquote(parsed.path)).resolve()
            try:
                candidate.relative_to(boundary)
            except ValueError:
                continue

            checked += 1
            if not candidate.exists():
                missing.append(
                    f"{path.relative_to(root).as_posix()}: {link} -> "
                    f"{candidate.relative_to(boundary).as_posix()}"
                )

    if missing:
        raise AssertionError("missing generated documentation links:\n" + "\n".join(missing))
    if checked == 0:
        raise AssertionError(f"HTML link check did not inspect any in-root links under {root}")


def main() -> None:
    work = make_work_root()
    try:
        validate_docs_layout()
        validate_no_legacy_path_tokens()
        validate_markdown_links()
        validate_source_html_links()
        validate_generated_docs_links(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("docs_link_integrity: ok")


if __name__ == "__main__":
    main()
