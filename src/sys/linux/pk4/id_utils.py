#!/usr/bin/env python3
"""Utility helpers for legacy Linux PK4 maintenance scripts."""

from __future__ import annotations

import hashlib
import os
import zipfile
from pathlib import PurePosixPath


def list_paks(path):
    """Return PK4 file names in reverse lexical search order."""
    files = [name for name in os.listdir(path) if name.lower().endswith(".pk4")]
    files.sort()
    files.reverse()
    return files


def list_files_in_pak(pak):
    with zipfile.ZipFile(pak) as archive:
        files = archive.namelist()
    files.sort()
    return files


def list_files_in_paks(path):
    files = []
    for fname in list_paks(path):
        print(fname)
        with zipfile.ZipFile(os.path.join(path, fname)) as archive:
            files += archive.namelist()
    return sorted(set(files))


def md5_in_paks(path):
    ret = {}
    for fname in list_paks(path):
        print(fname)
        with zipfile.ZipFile(os.path.join(path, fname)) as archive:
            for filename in archive.namelist():
                if filename in ret:
                    continue
                digest = hashlib.md5()
                digest.update(archive.read(filename))
                ret[filename] = (fname, digest.hexdigest())
    return ret


def list_updated_files(pak_path, base_path, case_match=False):
    not_found = []
    updated = []
    case_table = {}
    pak_md5 = md5_in_paks(pak_path)
    for filename in pak_md5.keys():
        if filename.endswith("/"):
            continue
        path = os.path.join(base_path, filename)
        if case_match:
            found, cased_path = ifind(base_path, filename)
            if not found:
                not_found.append(filename)
                continue
            case_table[filename] = cased_path
            path = os.path.join(base_path, cased_path)
        try:
            with open(path, "rb") as handle:
                data = handle.read()
        except OSError as exc:
            if case_match:
                raise RuntimeError("internal error: ifind success but later read failed") from exc
            not_found.append(filename)
        else:
            digest = hashlib.md5()
            digest.update(data)
            if digest.hexdigest() != pak_md5[filename][1]:
                print(filename)
                updated.append(filename)
    return (updated, not_found, case_table)


def status_files_for_path(path, infiles):
    files = []
    dirs = []
    missing = []
    for name in infiles:
        test_path = os.path.join(path, name)
        if os.path.isfile(test_path):
            files.append(name)
        elif os.path.isdir(test_path):
            dirs.append(name)
        else:
            missing.append(name)
    return (files, dirs, missing)


def validate_archive_name(name):
    normalized = name.replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    if (
        not normalized
        or normalized != name
        or normalized.startswith("/")
        or "" in normalized.split("/")
        or any(part in ("", ".", "..") for part in parts)
        or ":" in (parts[0] if parts else "")
    ):
        raise ValueError(f"unsafe pak archive path: {name!r}")
    return normalized


def _safe_source_path(base_path, relative_name):
    arcname = validate_archive_name(relative_name)
    source_path = os.path.abspath(os.path.join(base_path, arcname))
    base_real = os.path.abspath(base_path)
    if os.path.commonpath([base_real, source_path]) != base_real:
        raise ValueError(f"pak source escapes base path: {relative_name!r}")
    if os.path.islink(source_path):
        raise ValueError(f"refusing to pack symlinked source file: {relative_name!r}")
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"pak source file not found: {relative_name!r}")
    return source_path, arcname


def build_pak(pak, path, files):
    with zipfile.ZipFile(pak, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            source_path, arcname = _safe_source_path(path, name)
            print(source_path)
            archive.write(source_path, arcname)


def check_files_against_build(files, pak_path):
    pak_list = [name.lower() for name in list_files_in_paks(pak_path)]
    with open(files, encoding="utf-8") as handle:
        check_files = [line.lower().strip() for line in handle]

    bad = []
    missing = []
    for name in check_files:
        if name.startswith("dds/"):
            if name.endswith(".tga"):
                name = name[:-4] + ".dds"
            elif not name.endswith(".dds"):
                print("File not understood: " + name)
                bad.append(name)
                continue
            if name not in pak_list:
                print("Not found: " + name)
                missing.append(name)
        elif name.endswith(".wav"):
            ogg_name = name[:-4] + ".ogg"
            if ogg_name not in pak_list:
                print("Not found: " + ogg_name)
                missing.append(ogg_name)
                missing.append(name)
        elif name.endswith(".tga"):
            if name not in pak_list:
                print("Not found: " + name)
                missing.append(name)
                dds_name = "dds/" + name[:-4] + ".dds"
                print("Add dds  : " + dds_name)
                missing.append(dds_name)
        elif name not in pak_list:
            print("Not found: " + name)
            missing.append(name)
    return (missing, bad)


def ifind(base, path):
    refpath = path
    normalized = os.path.normpath(path)
    if os.path.isabs(normalized) or normalized == ".." or normalized.startswith(".." + os.sep):
        return (False, "")

    components = [part for part in normalized.split(os.sep) if part]
    root = base
    walked = []
    for index, component in enumerate(components):
        try:
            entries = os.listdir(root)
        except OSError:
            return (False, os.path.join(*walked) if walked else "")
        matches = [entry for entry in entries if entry.lower() == component.lower()]
        if not matches:
            return (False, os.path.join(*walked) if walked else "")
        match = matches[0]
        walked.append(match)
        root = os.path.join(root, match)
        if index < len(components) - 1 and not os.path.isdir(root):
            return (False, os.path.join(*walked))

    result = os.path.join(*walked) if walked else refpath
    return (os.path.isfile(os.path.join(base, result)) or os.path.isdir(os.path.join(base, result)), result)


def ifind_list(base, files):
    cased = []
    notfound = []
    for name in files:
        found, cased_name = ifind(base, name)
        if found:
            cased.append(cased_name)
        else:
            notfound.append(name)
    return [cased, notfound]
