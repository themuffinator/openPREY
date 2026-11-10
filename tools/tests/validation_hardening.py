#!/usr/bin/env python3
"""Regression checks for validation-runner input and staging hardening."""

from __future__ import annotations

import argparse
import configparser
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from types import ModuleType
from zipfile import ZIP_STORED, ZipFile


ROOT = Path(__file__).resolve().parents[2]
WORK_BASE = ROOT / ".tmp" / "validation-hardening-test"


def make_work_root() -> Path:
    return WORK_BASE / f"{os.getpid()}-{uuid.uuid4().hex}"


WORK = make_work_root()


def load_module(name: str, path: Path) -> ModuleType:
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_module("openprey_validation_hardening_test", ROOT / "tools" / "validation" / "openq4_validate.py")


def write_file(path: Path, data: bytes = b"x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_pk4(path: Path, entries: tuple[str, ...] = ("manifest.txt",)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w", compression=ZIP_STORED) as archive:
        for entry in entries:
            archive.writestr(entry, b"x\n")


def expect_validation_error(callback, text: str, label: str) -> None:
    try:
        callback()
    except VALIDATOR.ValidationError as exc:
        if text not in str(exc):
            raise AssertionError(f"{label} raised {exc!r}, expected text {text!r}") from exc
        return
    raise AssertionError(f"{label} unexpectedly succeeded")


def expect_argument_error(callback, text: str, label: str) -> None:
    try:
        callback()
    except argparse.ArgumentTypeError as exc:
        if text not in str(exc):
            raise AssertionError(f"{label} raised {exc!r}, expected text {text!r}") from exc
        return
    raise AssertionError(f"{label} unexpectedly succeeded")


def with_host_flags(windows: bool, linux: bool, macos: bool, callback) -> None:
    original_windows = VALIDATOR.host_is_windows
    original_linux = VALIDATOR.host_is_linux
    original_macos = VALIDATOR.host_is_macos
    VALIDATOR.host_is_windows = lambda: windows
    VALIDATOR.host_is_linux = lambda: linux
    VALIDATOR.host_is_macos = lambda: macos
    try:
        callback()
    finally:
        VALIDATOR.host_is_windows = original_windows
        VALIDATOR.host_is_linux = original_linux
        VALIDATOR.host_is_macos = original_macos


def validate_positive_integer_arguments() -> None:
    if VALIDATOR.positive_int("4") != 4:
        raise AssertionError("positive_int returned the wrong value")

    for value in ("0", "-1", "not-a-number"):
        expect_argument_error(
            lambda value=value: VALIDATOR.positive_int(value),
            "positive integer" if value != "not-a-number" else "not an integer",
            f"positive_int({value!r})",
        )

    source = (ROOT / "tools" / "validation" / "openq4_validate.py").read_text(encoding="utf-8")
    for token in (
        'parser.add_argument("--jobs", "-j", type=positive_int',
        'parser.add_argument("--runtime-timeout", type=positive_int',
    ):
        if token not in source:
            raise AssertionError(f"validation runner is missing argument hardening token {token!r}")


def validate_source_and_build_dir_guards() -> None:
    VALIDATOR.validate_source_root(ROOT)

    source_link = WORK / "source-root-link"
    try:
        os.symlink(ROOT, source_link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pass
    else:
        expect_validation_error(
            lambda: VALIDATOR.validate_source_root(source_link),
            "must not be a symlink",
            "symlink source root",
        )

    fake_root = WORK / "not-openprey"
    fake_root.mkdir(parents=True, exist_ok=True)
    expect_validation_error(
        lambda: VALIDATOR.validate_source_root(fake_root),
        "missing required openPREY files",
        "invalid source root",
    )

    expect_validation_error(lambda: VALIDATOR.validate_build_dir(ROOT, ROOT), "source root", "source-root build dir")
    expect_validation_error(
        lambda: VALIDATOR.validate_build_dir(ROOT, ROOT.parent),
        "contain the source root",
        "ancestor build dir",
    )
    expect_validation_error(
        lambda: VALIDATOR.validate_build_dir(ROOT, ROOT / "docs/dev" / "validation-build"),
        "must live under .tmp/ or use a builddir* name",
        "source-controlled build dir",
    )

    file_build_dir = WORK / "build-file"
    write_file(file_build_dir)
    expect_validation_error(
        lambda: VALIDATOR.validate_build_dir(ROOT, file_build_dir),
        "not a directory",
        "file build dir",
    )

    symlink_target = WORK / "build-target"
    symlink_build_dir = WORK / "build-link"
    symlink_target.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(symlink_target, symlink_build_dir)
    except (OSError, NotImplementedError):
        pass
    else:
        expect_validation_error(
            lambda: VALIDATOR.validate_build_dir(ROOT, symlink_build_dir),
            "must not be a symlink",
            "symlink build dir",
        )

    VALIDATOR.validate_build_dir(ROOT, ROOT / "builddir-validation-hardening")
    VALIDATOR.validate_build_dir(ROOT, ROOT / ".tmp" / "validation-hardening" / "build")


def validate_game_libs_repo_guards() -> None:
    game_libs_target = WORK / "OpenPrey-game-real"
    game_libs_link = WORK / "OpenPrey-game-link"
    write_file(game_libs_target / "src" / "game" / "Game_local.cpp")

    expect_validation_error(
        lambda: VALIDATOR.ensure_game_libs_repo({"OPENPREY_GAMELIBS_REPO": str(game_libs_target)}),
        "Prey gameplay",
        "missing Prey GameLibs source tree",
    )
    write_file(game_libs_target / "src" / "Prey" / "game_local.cpp")
    expect_validation_error(
        lambda: VALIDATOR.ensure_game_libs_repo({"OPENPREY_GAMELIBS_REPO": str(game_libs_target)}),
        "Prey engine-support",
        "missing preyengine GameLibs source tree",
    )
    write_file(game_libs_target / "src" / "preyengine" / "prey_public.h")
    VALIDATOR.ensure_game_libs_repo({"OPENPREY_GAMELIBS_REPO": str(game_libs_target)})

    alias_args = argparse.Namespace(game_libs_repo="", build_gamelibs=True, skip_icon_sync=True)
    original_primary = os.environ.get("OPENPREY_GAMELIBS_REPO")
    original_legacy = os.environ.get("OPENQ4_GAMELIBS_REPO")
    try:
        os.environ.pop("OPENPREY_GAMELIBS_REPO", None)
        os.environ["OPENQ4_GAMELIBS_REPO"] = str(game_libs_target)
        alias_env = VALIDATOR.validation_env(alias_args, ROOT)
        expected_repo = str(game_libs_target.resolve())
        if alias_env.get("OPENPREY_GAMELIBS_REPO") != expected_repo:
            raise AssertionError("legacy GameLibs override was not canonicalized")
        if alias_env.get("OPENQ4_GAMELIBS_REPO") != expected_repo:
            raise AssertionError("legacy GameLibs compatibility alias did not mirror the canonical path")
        if alias_env.get("OPENPREY_SKIP_ICON_SYNC") != "1":
            raise AssertionError("canonical icon-sync switch was not set")
    finally:
        if original_primary is None:
            os.environ.pop("OPENPREY_GAMELIBS_REPO", None)
        else:
            os.environ["OPENPREY_GAMELIBS_REPO"] = original_primary
        if original_legacy is None:
            os.environ.pop("OPENQ4_GAMELIBS_REPO", None)
        else:
            os.environ["OPENQ4_GAMELIBS_REPO"] = original_legacy

    try:
        os.symlink(game_libs_target, game_libs_link, target_is_directory=True)
    except (OSError, NotImplementedError):
        return

    expect_validation_error(
        lambda: VALIDATOR.ensure_game_libs_repo({"OPENPREY_GAMELIBS_REPO": str(game_libs_link)}),
        "must not be a symlink",
        "symlink GameLibs repository",
    )

    args = argparse.Namespace(game_libs_repo=str(game_libs_link), build_gamelibs=False, skip_icon_sync=False)
    expect_validation_error(
        lambda: VALIDATOR.validation_env(args, ROOT),
        "must not be a symlink",
        "symlink GameLibs CLI argument",
    )

    default_root = WORK / "default-gamelibs" / "openPREY"
    default_target = WORK / "default-gamelibs" / "OpenPrey-game-real"
    default_link = WORK / "default-gamelibs" / "OpenPrey-game"
    write_file(default_root / "meson.build")
    write_file(default_target / "src" / "game" / "Game_local.cpp")
    try:
        os.symlink(default_target, default_link, target_is_directory=True)
    except (OSError, NotImplementedError):
        return

    default_args = argparse.Namespace(game_libs_repo="", build_gamelibs=False, skip_icon_sync=False)
    original_primary = os.environ.get("OPENPREY_GAMELIBS_REPO")
    original_legacy = os.environ.get("OPENQ4_GAMELIBS_REPO")
    try:
        os.environ.pop("OPENPREY_GAMELIBS_REPO", None)
        os.environ.pop("OPENQ4_GAMELIBS_REPO", None)
        env = VALIDATOR.validation_env(default_args, default_root)
        if Path(env["OPENQ4_GAMELIBS_REPO"]) != default_root.resolve():
            raise AssertionError("the canonical default must ignore a linked companion checkout")
    finally:
        if original_primary is None:
            os.environ.pop("OPENPREY_GAMELIBS_REPO", None)
        else:
            os.environ["OPENPREY_GAMELIBS_REPO"] = original_primary
        if original_legacy is None:
            os.environ.pop("OPENQ4_GAMELIBS_REPO", None)
        else:
            os.environ["OPENQ4_GAMELIBS_REPO"] = original_legacy


def validate_staged_symlink_guard() -> None:
    install_root_link_root = WORK / "symlink-install-root"
    install_root_target = WORK / "symlink-install-target"
    install_root_link_root.mkdir(parents=True, exist_ok=True)
    install_root_target.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(install_root_target, install_root_link_root / ".install", target_is_directory=True)
    except (OSError, NotImplementedError):
        pass
    else:
        expect_validation_error(
            lambda: VALIDATOR.validate_staged_payload(install_root_link_root, dry_run=False),
            "Install root must not be a symlink",
            "symlink install root",
        )

    game_dir_link_root = WORK / "symlink-game-root"
    game_dir_target = WORK / "symlink-game-target"
    (game_dir_link_root / ".install").mkdir(parents=True, exist_ok=True)
    game_dir_target.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(game_dir_target, game_dir_link_root / ".install" / "basepr", target_is_directory=True)
    except (OSError, NotImplementedError):
        pass
    else:
        expect_validation_error(
            lambda: VALIDATOR.validate_staged_payload(game_dir_link_root, dry_run=False),
            "Staged game directory must not be a symlink",
            "symlink staged game root",
        )

    root = WORK / "symlink-payload"
    install_root = root / ".install"
    target = root / "outside.txt"
    link = install_root / "basepr" / "linked.txt"
    write_file(target)
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        return

    expect_validation_error(
        lambda: VALIDATOR.validate_no_staged_symlinks(root, install_root),
        "symlink entries",
        "staged symlink guard",
    )


def validate_recursive_non_runtime_scan() -> None:
    root = WORK / "non-runtime"
    install_root = root / ".install"
    game_dir = install_root / "basepr"
    write_file(game_dir / "nested" / "debug.lib")
    expect_validation_error(
        lambda: VALIDATOR.validate_no_non_runtime_artifacts(
            root,
            (install_root, game_dir),
            VALIDATOR.NON_RUNTIME_PATTERNS,
            "Non-runtime artifacts remain staged",
        ),
        "nested/debug.lib",
        "recursive non-runtime artifact scan",
    )


def validate_staged_casefold_collision_guard() -> None:
    collision = VALIDATOR.first_staged_casefold_path_collision(
        ["baseoq4/pak0.pk4", "OpenQ4.icns", "openQ4.icns"]
    )
    if collision != ("OpenQ4.icns", "openQ4.icns"):
        raise AssertionError(f"unexpected casefold collision result: {collision!r}")

    root = WORK / "casefold-payload"
    install_root = root / ".install"
    write_file(install_root / "OpenQ4.icns")
    if not (install_root / "openQ4.icns").exists():
        write_file(install_root / "openQ4.icns")
        expect_validation_error(
            lambda: VALIDATOR.validate_no_staged_casefold_path_collisions(root, install_root),
            "case-insensitive duplicate paths",
            "staged casefold collision guard",
        )


def validate_engine_architecture_mismatch() -> None:
    root = WORK / "engine-arch"
    install_root = root / ".install"
    game_dir = install_root / "basepr"
    client = install_root / "openPREY-client_x64.exe"
    dedicated = install_root / "openPREY-ded_arm64.exe"
    write_file(client)
    write_file(dedicated)

    with_host_flags(
        True,
        False,
        False,
        lambda: expect_validation_error(
            lambda: VALIDATOR.validate_staged_architecture_set(root, game_dir, [client], [dedicated]),
            "engine binary architecture mismatch",
            "engine architecture mismatch",
        ),
    )


def validate_game_module_suffix_guard() -> None:
    root = WORK / "module-suffix"
    install_root = root / ".install"
    game_dir = install_root / "basepr"
    client = install_root / "openPREY-client_x64.exe"
    dedicated = install_root / "openPREY-ded_x64.exe"
    write_file(client)
    write_file(dedicated)
    write_file(game_dir / "game_x64.so")

    with_host_flags(
        True,
        False,
        False,
        lambda: expect_validation_error(
            lambda: VALIDATOR.validate_staged_architecture_set(root, game_dir, [client], [dedicated]),
            "wrong platform suffix",
            "game module suffix mismatch",
        ),
    )


def validate_game_module_architecture_match() -> None:
    root = WORK / "module-arch"
    install_root = root / ".install"
    game_dir = install_root / "basepr"
    client = install_root / "openPREY-client_x64.exe"
    dedicated = install_root / "openPREY-ded_x64.exe"
    write_file(client)
    write_file(dedicated)
    write_file(game_dir / "game_arm64.dll")

    with_host_flags(
        True,
        False,
        False,
        lambda: expect_validation_error(
            lambda: VALIDATOR.validate_staged_architecture_set(root, game_dir, [client], [dedicated]),
            "game module architecture mismatch",
            "game module architecture mismatch",
        ),
    )

    (game_dir / "game_arm64.dll").unlink()
    write_file(game_dir / "game_x64.dll")

    def assert_valid_arch_set() -> None:
        arches = VALIDATOR.validate_staged_architecture_set(root, game_dir, [client], [dedicated])
        if arches != {"x64"}:
            raise AssertionError(f"unexpected staged architecture set: {arches!r}")

    with_host_flags(True, False, False, assert_valid_arch_set)


def validate_split_game_module_guard() -> None:
    game_dir = WORK / "module-split" / ".install" / "basepr"
    split_module = game_dir / "game_sp_x64.dll"
    write_file(split_module)
    if VALIDATOR.find_legacy_split_game_modules(game_dir) != [split_module]:
        raise AssertionError("legacy split game module was not rejected")


def validate_linux_runtime_dependency_guards() -> None:
    root = WORK / "linux-dedicated-dependencies"
    client_x64 = root / ".install" / "openPREY-client_x64"
    client_arm64 = root / ".install" / "openPREY-client_arm64"
    dedicated_x64 = root / ".install" / "openPREY-ded_x64"
    dedicated_arm64 = root / ".install" / "openPREY-ded_arm64"
    game_x64 = root / ".install" / "basepr" / "game_x64.so"
    game_arm64 = root / ".install" / "basepr" / "game_arm64.so"
    original_readelf_output = VALIDATOR.readelf_output
    dynamic_section = ""

    def fake_readelf_output(path: Path, args: list[str], source_root: Path) -> str:
        if args != ["-W", "-d"]:
            raise AssertionError(f"unexpected Linux dependency readelf arguments: {args!r}")
        if path not in (
            client_x64,
            client_arm64,
            dedicated_x64,
            dedicated_arm64,
            game_x64,
            game_arm64,
        ) or source_root != root:
            raise AssertionError(f"unexpected Linux dependency path: {path}")
        return dynamic_section

    try:
        VALIDATOR.readelf_output = fake_readelf_output
        dynamic_section = """
 0x0000000000000001 (NEEDED)             Shared library: [libstdc++.so.6]
 0x0000000000000001 (NEEDED)             Shared library: [libgcc_s.so.1]
 0x0000000000000001 (NEEDED)             Shared library: [libm.so.6]
 0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]
"""
        VALIDATOR.validate_linux_client_runtime_dependencies(
            root,
            [client_x64, client_arm64],
        )
        VALIDATOR.validate_linux_dedicated_runtime_dependencies(
            root,
            [
                (dedicated_x64, "x64"),
                (dedicated_arm64, "arm64"),
                (game_x64, "x64"),
                (game_arm64, "arm64"),
            ],
        )

        dynamic_section = """
 0x0000000000000001 (NEEDED)             Shared library: [ld-linux-x86-64.so.2]
 0x0000000000000001 (NEEDED)             Shared library: [libc++.so.1]
 0x0000000000000001 (NEEDED)             Shared library: [libc++abi.so.1]
 0x0000000000000001 (NEEDED)             Shared library: [libunwind.so.1]
"""
        VALIDATOR.validate_linux_dedicated_runtime_dependencies(
            root,
            [(dedicated_x64, "x64"), (game_x64, "x64")],
        )

        dynamic_section = """
 0x0000000000000001 (NEEDED)             Shared library: [ld-linux-aarch64.so.1]
 0x0000000000000001 (NEEDED)             Shared library: [libatomic.so.1]
 0x0000000000000001 (NEEDED)             Shared library: [libgcc_s.so.1]
"""
        VALIDATOR.validate_linux_dedicated_runtime_dependencies(
            root,
            [(dedicated_arm64, "arm64"), (game_arm64, "arm64")],
        )

        dynamic_section = (
            " 0x0000000000000001 (NEEDED)             "
            "Shared library: [libpipewire-0.3.so.0]\n"
        )
        expect_validation_error(
            lambda: VALIDATOR.validate_linux_client_runtime_dependencies(
                root,
                [client_x64],
            ),
            "libpipewire-0.3.so.0",
            "Linux client direct PipeWire dependency guard",
        )

        for forbidden_library in (
            "libopenal.so.1",
            "libOpenGL.so.0",
            "libGL.so.1",
            "libGLX.so.0",
            "libEGL.so.1",
            "libGLESv2.so.2",
            "libvulkan.so.1",
            "libSDL3.so.0",
            "libpipewire-0.3.so.0",
            "libwayland-client.so.0",
            "libdecor-0.so.0",
            "libX11.so.6",
            "libXext.so.6",
            "libxcb.so.1",
            "libfuture-client-runtime.so.1",
        ):
            dynamic_section = (
                " 0x0000000000000001 (NEEDED)             "
                f"Shared library: [{forbidden_library}]\n"
            )
            expect_validation_error(
                lambda: VALIDATOR.validate_linux_dedicated_runtime_dependencies(
                    root,
                    [(game_x64, "x64")],
                ),
                forbidden_library,
                f"Linux dedicated dependency guard for {forbidden_library}",
            )

        dynamic_section = (
            " 0x0000000000000001 (NEEDED)             "
            "Shared library: [ld-linux-aarch64.so.1]\n"
        )
        expect_validation_error(
            lambda: VALIDATOR.validate_linux_dedicated_runtime_dependencies(
                root,
                [(dedicated_x64, "x64")],
            ),
            "ld-linux-aarch64.so.1",
            "cross-architecture dedicated loader dependency",
        )
        expect_validation_error(
            lambda: VALIDATOR.validate_linux_dedicated_runtime_dependencies(
                root,
                [(dedicated_x64, "riscv64")],
            ),
            "riscv64",
            "unsupported dedicated dependency architecture",
        )
    finally:
        VALIDATOR.readelf_output = original_readelf_output


def validate_windows_pdb_architecture_match() -> None:
    root = WORK / "windows-pdb"
    install_root = root / ".install"
    game_dir = install_root / "basepr"
    write_file(install_root / "OpenAL32.dll")
    write_file(install_root / "openPREY-client_arm64.pdb")

    with_host_flags(
        True,
        False,
        False,
        lambda: expect_validation_error(
            lambda: VALIDATOR.validate_windows_symbols(root, install_root, game_dir, {"x64"}),
            "missing architecture-matched diagnostic PDB",
            "missing exact PDB architecture",
        ),
    )

    for path in (
        install_root / "openPREY-client_x64.pdb",
        install_root / "openPREY-ded_x64.pdb",
        game_dir / "game_x64.pdb",
    ):
        write_file(path)

    with_host_flags(
        True,
        False,
        False,
        lambda: expect_validation_error(
            lambda: VALIDATOR.validate_windows_symbols(root, install_root, game_dir, {"x64"}),
            "stale or architecture-mismatched PDB",
            "stale PDB architecture",
        ),
    )

    (install_root / "openPREY-client_arm64.pdb").unlink()
    with_host_flags(True, False, False, lambda: VALIDATOR.validate_windows_symbols(root, install_root, game_dir, {"x64"}))


def validate_windows_unified_staged_payload() -> None:
    root = WORK / "windows-unified-payload"
    install_root = root / ".install"
    game_dir = install_root / "basepr"
    for path in (
        install_root / "OpenAL32.dll",
        install_root / "openPREY-client_x64.exe",
        install_root / "openPREY-client_x64.pdb",
        install_root / "openPREY-ded_x64.exe",
        install_root / "openPREY-ded_x64.pdb",
        game_dir / "game_x64.dll",
        game_dir / "game_x64.pdb",
        game_dir / "mod.json",
    ):
        write_file(path)
    write_pk4(game_dir / "pak0.pk4")
    write_pk4(game_dir / "pak1.pk4")

    with_host_flags(True, False, False, lambda: VALIDATOR.validate_staged_payload(root, dry_run=False))

    write_pk4(game_dir / "pak0.pk4", ("script/map_roadhouse_quick.script",))
    with_host_flags(
        True,
        False,
        False,
        lambda: expect_validation_error(
            lambda: VALIDATOR.validate_staged_payload(root, dry_run=False),
            "development-only roadhouse_quick fixture",
            "roadhouse_quick fixture in staged PK4",
        ),
    )
    write_pk4(game_dir / "pak0.pk4")

    split_module = game_dir / "game-mp_x64.dll"
    write_file(split_module)
    with_host_flags(
        True,
        False,
        False,
        lambda: expect_validation_error(
            lambda: VALIDATOR.validate_staged_payload(root, dry_run=False),
            "obsolete split game modules",
            "split module in unified Windows payload",
        ),
    )
    split_module.unlink()

    legacy_game_dir = install_root / "baseoq4"
    write_file(legacy_game_dir / "pak0.pk4")
    with_host_flags(
        True,
        False,
        False,
        lambda: expect_validation_error(
            lambda: VALIDATOR.validate_staged_payload(root, dry_run=False),
            "obsolete OpenQ4/retail runtime layout",
            "legacy OpenQ4 game directory in unified Windows payload",
        ),
    )
    shutil.rmtree(legacy_game_dir)

    legacy_executable = install_root / "openQ4-client_x64.exe"
    write_file(legacy_executable)
    with_host_flags(
        True,
        False,
        False,
        lambda: expect_validation_error(
            lambda: VALIDATOR.validate_staged_payload(root, dry_run=False),
            "obsolete OpenQ4/retail runtime layout",
            "legacy OpenQ4 executable in unified Windows payload",
        ),
    )
    legacy_executable.unlink()

    legacy_game_alias = game_dir / "gamex64.dll"
    write_file(legacy_game_alias)
    with_host_flags(
        True,
        False,
        False,
        lambda: expect_validation_error(
            lambda: VALIDATOR.validate_staged_payload(root, dry_run=False),
            "obsolete OpenQ4/retail runtime layout",
            "retail game-module alias in unified Windows payload",
        ),
    )
    legacy_game_alias.unlink()

    import_library = game_dir / "game_x64.lib"
    write_file(import_library)
    with_host_flags(
        True,
        False,
        False,
        lambda: expect_validation_error(
            lambda: VALIDATOR.validate_staged_payload(root, dry_run=False),
            "Non-runtime artifacts remain staged",
            "import library in unified Windows payload",
        ),
    )


def validate_python_test_failure_aggregation() -> None:
    original_run_command = VALIDATOR.run_command
    observed: list[str] = []
    simulated_failures = {"arena_campaign.py", "vscode_fast_build.py"}

    def fake_run_command(command, *, cwd, env, title, dry_run) -> None:
        test_name = Path(command[1]).name
        observed.append(test_name)
        if test_name in simulated_failures:
            raise VALIDATOR.ValidationError(f"simulated failure: {test_name}")

    VALIDATOR.run_command = fake_run_command
    try:
        expect_validation_error(
            lambda: VALIDATOR.run_python_tests(
                argparse.Namespace(dry_run=False, python_jobs=1),
                ROOT,
                {},
            ),
            "2 Python validation check(s) failed",
            "aggregated Python validation failures",
        )
    finally:
        VALIDATOR.run_command = original_run_command

    # The parallel runner must aggregate the same failures from both ends.
    original_captured = VALIDATOR.run_python_check_captured
    parallel_observed: list[str] = []

    def fake_captured(test_script, test_args, root, env):
        parallel_observed.append(Path(test_script).name)
        failed = Path(test_script).name in simulated_failures
        return (1 if failed else 0), f"simulated {'failure' if failed else 'pass'}\n", 0.0

    VALIDATOR.run_python_check_captured = fake_captured
    try:
        expect_validation_error(
            lambda: VALIDATOR.run_python_tests(
                argparse.Namespace(dry_run=False, python_jobs=4),
                ROOT,
                {},
            ),
            "2 Python validation check(s) failed",
            "aggregated parallel Python validation failures",
        )
    finally:
        VALIDATOR.run_python_check_captured = original_captured
    # Checks create their temporary directories under .tmp without making it, so
    # the parallel runner must create it before any check can start.
    with tempfile.TemporaryDirectory(prefix="validation-hardening-tmp-", dir=ROOT / ".tmp") as fresh:
        fresh_root = Path(fresh)
        VALIDATOR.run_python_check_captured = lambda *args: (0, "", 0.0)
        try:
            VALIDATOR.run_python_checks_parallel([(fresh_root / "probe.py", [])], fresh_root, {}, 2)
        finally:
            VALIDATOR.run_python_check_captured = original_captured
        if not (fresh_root / ".tmp").is_dir():
            raise AssertionError("the parallel Python runner must create .tmp before starting checks")

    if sorted(parallel_observed) != sorted(observed):
        raise AssertionError("the parallel Python runner did not run the same checks as the sequential one")

    if not simulated_failures.issubset(observed):
        raise AssertionError(
            "Python validation stopped before reporting failures from both ends of the suite"
        )


def validate_validation_wiring() -> None:
    validator = (ROOT / "tools" / "validation" / "openq4_validate.py").read_text(encoding="utf-8")
    settings_coverage = (ROOT / "tools" / "tests" / "settings_menu_coverage.py").read_text(
        encoding="utf-8"
    )
    push = (ROOT / ".github" / "workflows" / "push-verification.yml").read_text(encoding="utf-8")
    commit = (ROOT / ".github" / "workflows" / "commit-validation.yml").read_text(encoding="utf-8")
    status_ledger = (ROOT / "docs/dev/prey-rebase/status-ledger.md").read_text(encoding="utf-8")

    for token in (
        "positive_int",
        "validate_source_root",
        "validate_game_libs_repo_path",
        "validate_build_dir",
        "validate_no_staged_symlinks",
        "validate_no_staged_casefold_path_collisions",
        "validate_staged_architecture_set",
        "find_legacy_split_game_modules",
        "find_forbidden_staged_legacy_paths",
        "validate_linux_client_runtime_dependencies",
        "validate_linux_dedicated_runtime_dependencies",
        "validate_windows_symbols",
        "validate_no_non_runtime_artifacts",
        "DEFERRED_RELEASE_LANE_TESTS",
        "INHERITED_OPENQ4_ONLY_TESTS",
        "DEFERRED_PREY_API_V7_TESTS",
        "TODO-D9",
        "TODO-RELEASE-LANES",
        "-Dbuild_native_tests=true",
        "test_args",
        "Meson native tests",
        "Install root must not be a symlink",
        "Staged game directory must not be a symlink",
    ):
        if token not in validator:
            raise AssertionError(f"validation runner is missing {token}")

    for context, text in (
        ("validation runner", validator),
        ("push workflow", push),
        ("commit workflow", commit),
    ):
        if "validation_hardening.py" not in text:
            raise AssertionError(f"validation_hardening.py is not wired into {context}")

    if 'os.environ.get("OPENQ4_GAMELIBS_REPO"' not in settings_coverage:
        raise AssertionError("settings menu coverage ignores the configured GameLibs repository")

    # Runtime drivers need a built target package or retail assets. Helpers are
    # exercised by their native harnesses or runtime callers. Keep both out of
    # the argument-free lightweight suite; CI still checks their syntax.
    smoke_wiring_allowlist = {
        # Runtime probes require staged binaries/assets; generators feed Meson native tests.
        "airdefense_performance.py",
        "checkpoint_performance.py",
        "generate_capture_resample_test.py",
        "generate_checkpoint_commit_test.py",
        "generate_checkpoint_preview_test.py",
        "generate_checkpoint_storage_test.py",
        "generate_dict_identity_test.py",
        "generate_save_dict_test.py",
        "mp_bot_walk_replay.py",
        "mp_liquid_air_smoke.py",
        "mp_mvd_quota_smoke.py",
        "mp_mvd_seek_smoke.py",
        "performance_presets_smoke.py",
        "rendering_selection_smoke.py",
        # Stage 2 drivers: each launches a staged client, dedicated server,
        # WSL peer or OpenXR runtime on retail assets; the workflows py_compile
        # them and their production-extraction siblings are wired.
        "arena_sound_runtime.py",
        "presentation_look_runtime.py",
        # Runs presentation_look_runtime.py's reference cases for the operator at
        # the reference desktop; --dry-run prints the plan without launching.
        "presentation_reference_suite.py",
        "mp_wsl_peer_smoke.py",
        # LAN discovery, successive reconnects and retail 2.85 refusal launch a
        # staged dedicated server and client (and the retail Quake4Ded.exe).
        "mp_lan_reconnect_smoke.py",
        "mp_mod_admission_smoke.py",
        "mp_retail_protocol_smoke.py",
        "openxr_lifecycle_runtime.py",
        "savegame_restore_cleanup_runtime.py",
        "savegame_restore_recovery_runtime.py",
        "ui_generated_image_runtime.py",
        # Audio/voice drivers: retail assets, a staged OpenAL Soft provider,
        # ffmpeg or a launched game; their native-compile siblings are wired.
        "audio_asset_inventory.py",
        "audio_center.py",
        "audio_dialogue.py",
        "audio_dialogue_coverage.py",
        "audio_memory_runtime.py",
        "audio_output_recovery_runtime.py",
        "audio_mod_reverb.py",
        "audio_scene_audit.py",
        "audio_streaming.py",
        "audio_subtitles_runtime.py",
        "voice_chat_runtime.py",
        "voice_chat_soak.py",
        "voice_mixed_version.py",
        "german_localization_smoke.py",
        "localization_smoke.py",
        "level_editor_runtime.py",
        "level_editor_authoring.py",
        "mp_bot_gameplay_smoke.py",
        "renderer_classic_colors.py",
        "renderer_font_reload.py",
        "renderer_hdr_highlights.py",
        "renderer_hdr_linear_capture.py",
        "renderer_hdr_linear_compare.py",
        "renderer_image_capture.py",
        "renderer_image_recovery_fixture.py",
        "renderer_pbr_ambient_parity.py",
        "renderer_pbr_diagnostic_parity.py",
        "renderer_pbr_environment_parity.py",
        "renderer_pbr_geometry_parity.py",
        "renderer_pbr_laboratory.py",
        "renderer_pbr_native_gl_parity.py",
        "renderer_pbr_preview.py",
        "renderer_pbr_probe_parity.py",
        "renderer_render_target_lifetime.py",
        "renderer_smaa_orientation.py",
        "renderer_vulkan_arb_programs.py",
        "renderer_vulkan_hdr_gameplay.py",
        "renderer_vulkan_hdr_post.py",
        "renderer_vulkan_hdr_post_compare.py",
        "renderer_vulkan_hdr_scene.py",
        "renderer_vulkan_hdr_scene_compare.py",
        "renderer_vulkan_material_lighting.py",
        "renderer_vulkan_material_programs.py",
        "renderer_vulkan_material_reload.py",
        "renderer_vulkan_pbr_ambient.py",
        "renderer_vulkan_pbr_baked.py",
        "renderer_vulkan_pbr_capacity.py",
        "renderer_vulkan_pbr_cutout.py",
        "renderer_vulkan_pbr_cutout_alpha.py",
        "renderer_vulkan_pbr_diagnostics.py",
        "renderer_vulkan_pbr_fog.py",
        "renderer_vulkan_pbr_geometry.py",
        "renderer_vulkan_pbr_probes.py",
        "renderer_vulkan_pbr_resources.py",
        "renderer_vulkan_pbr_transparency.py",
        "renderer_vulkan_recovery_gameplay.py",
        "ui_choice_scroll_runtime.py",
        "ui_document_canvas.py",
        "ui_document_canvas_mutations.py",
        "ui_document_view_projection.py",
        "ui_focus_reveal.py",
        "ui_popup_placement_runtime.py",
        "ui_scrollbar_runtime.py",
        "ui_system_presets_runtime.py",
        "windows_text_collection_bridge.py",
        "windows_text_session.py",
        "windows_text_store.py",
        # Windows-only runtime smoke needs a staged package; its source
        # contract and workflow cover it outside the portable Python suite.
        "windows_dedicated_server_smoke.py",
        "chat_gameplay_smoke.py",
        "mp_browser_smoke.py",
        "mp_control_smoke.py",
        "mp_duel_queue_smoke.py",
        "mp_match_control_team_join_smoke.py",
        "mp_match_edges_smoke.py",
        "mp_match_side_ballot_smoke.py",
        "mp_liquid_effects_capture.py",
        "mp_remote_weapon_capture.py",
        "mp_match_flow_smoke.py",
        "mp_mvd_smoke.py",
        "mp_pause_lifecycle_smoke.py",
        "mp_pause_world_smoke.py",
        "mp_recording_ownership_smoke.py",
        "mp_roster_smoke.py",
        "mp_round_remote_smoke.py",
        "mp_series_smoke.py",
        "mp_tourney_smoke.py",
        "renderer_shadow_mapping_maps.py",
        "renderer_shadow_mapping_outdoor.py",
        "renderer_shadow_mapping_terrain.py",
        "renderer_shadow_mapping_movers.py",
        "renderer_shadow_mapping_scenes.py",
        "renderer_shadow_mapping_transitions.py",
        "generate_file_memory_test.py",
        # Generated production excerpts are compiled by the Meson native tests.
        "generate_aas_tactical_test.py",
        "generate_bitmsg_test.py",
        "generate_compressor_test.py",
        "mp_view_decoder.py",
        "linux_dedicated_server_smoke.py",
        "linux_dedicated_stock_map_smoke.py",
        "linux_wayland_stock_sp_smoke.py",
        "macos_dedicated_server_smoke.py",
        "windows_dedicated_server_smoke.py",
        "renderer_gameplay_benchmark.py",
        "renderer_validation_matrix.py",
        # Mode comparisons need a staged Vulkan client and retail assets;
        # renderer_overlap_benchmark_test.py checks the evidence parser in CI.
        "renderer_overlap_benchmark.py",
        # Vulkan support evidence runs need a staged client, a GPU and retail
        # assets.
        "renderer_vulkan_qualification.py",
        # Campaign runtime checks require user-supplied retail/expansion assets.
        "campaign_runtime.py",
        "campaign_selection_runtime.py",
        "awakening_m01_cinematic.py",
        "awakening_status_runtime.py",
        "monster_hit_materials.py",
        "mp_bot_audit.py",
        # Skill-ladder matches launch a staged MP server on retail assets;
        # the workflows py_compile it.
        "mp_bot_skill_ladder.py",
        # Isolated bot jump replays launch a staged MP server and client.
        "mp_bot_jump_replay.py",
        # Impulse-death replays launch a staged MP server and client; their
        # policy is exercised without assets by mp_bot_death_policy.py.
        "mp_bot_impulse_replay.py",
        # Replay recorded CTF5 drop and rim states through a staged client on
        # retail assets; the workflows py_compile them.
        "mp_bot_drop_replay.py",
        "mp_bot_rim_replay.py",
        # Stock sound distance measurements launch a staged client on retail assets.
        "sound_distance_runtime.py",
        # Drives a rooted x86_64 Android emulator; the workflows py_compile it.
        "android_emulator_smoke.py",
        # Drives a USB-connected debug phone; the workflows py_compile it.
        "android_device_qualification.py",
        "renderer_milestone_d_acceptance.py",
        "renderer_milestone_d_fixture.py",
        # Requires a staged Vulkan client and installed retail assets.
        "renderer_vulkan_material_capacity.py",
        # Radio graph evidence plays decoded audio through a staged client on
        # retail assets.
        "audio_graphs.py",
        # Need a staged OpenXR client, the built test runtime and retail assets.
        "openxr_vr_smoke.py",
        "openxr_vr_menu_smoke.py",
        "openxr_vr_mp_smoke.py",
        "openxr_objective_markers.py",
        # Imported by the UI harnesses that compile wrap sources; the workflows
        # py_compile it, and it is exercised through those harnesses.
        "wrap_sources.py",
        # The NumPy reference the PBR laboratory oracles import; its fitted
        # kernels are tested natively in PBRMathTest.
        "pbr_reference.py",
        # Awakening campaign drivers launch the staged SP client on the
        # user-supplied expansion assets; awakening_chapter_behavior.py and the
        # *_behavior.py extractions cover their production paths in CI.
        "awakening_alarm_runtime.py",
        "awakening_chapter_followup.py",
        "awakening_finale_runtime.py",
        "awakening_m03_m04_runtime.py",
        "awakening_m05_m06_runtime.py",
        "awakening_m07_runtime.py",
        "awakening_missions_runtime.py",
        "awakening_prison_runtime.py",
        "awakening_route_runtime.py",
        # Content-pack drivers host or join staged binaries with chosen packs.
        "content_pack_split_smoke.py",
        "content_pack_status_smoke.py",
        "lightgrid_pack_load_test.py",
        "loadscreen_format_audit.py",
        # Recorded bot recovery replays launch a staged MP server and client.
        "mp_bot_air_recovery_replay.py",
        "mp_bot_hit_recovery_replay.py",
        "mp_bot_pad_traffic_replay.py",
        # Need a staged OpenXR client, the built test runtime and retail assets.
        "openxr_vr_playspace_smoke.py",
        "openxr_vr_stereo_cost.py",
        "openxr_vr_stereo_share_smoke.py",
        "openxr_vr_temporal_smoke.py",
        # Benchmark and engine-capture drivers need a staged client, a GPU and
        # retail assets.
        "performance_suite.py",
        "ui_scope_performance.py",
        "renderer_debug_capture.py",
        "renderer_stencil_debug_capture.py",
        "renderer_tiled_capture.py",
        "renderer_view_capture.py",
        "renderer_hdr_stock_fallback.py",
        "renderer_motion_blur_qualification.py",
        "renderer_screen_space_effects_qualification.py",
        "renderer_shadow_motion_qualification.py",
        "renderer_temporal_qualification.py",
        "renderer_vulkan_descriptor_pressure.py",
        "renderer_vulkan_pipeline_pressure.py",
        "renderer_vulkan_uniform_pressure.py",
        # Optional Windows evidence helpers imported by
        # renderer_vulkan_presentation.py, whose --self-test is wired.
        "renderer_foreground_observer.py",
        "renderer_presentmon.py",
    }
    deferred_release_lane_tests = set(VALIDATOR.DEFERRED_RELEASE_LANE_TESTS)
    inherited_openq4_only_tests = set(VALIDATOR.INHERITED_OPENQ4_ONLY_TESTS)
    deferred_prey_api_v7_tests = set(VALIDATOR.DEFERRED_PREY_API_V7_TESTS)
    expected_deferred_tests = {
        "linux_arm64_cross_compile.py",
        "linux_arm64_ci_coverage.py",
        "linux_arm64_release_evidence.py",
        "macos_dedicated_server_smoke_contract.py",
        "macos_gamelibs_alignment.py",
        "macos_package_policy.py",
        "macos_signoff_archive.py",
        "macos_support_intake.py",
        "macos_symbolication_policy.py",
        "macos_universal2_release_candidate.py",
        "macos_metal_bridge.py",
    }
    missing_deferred_tests = expected_deferred_tests.difference(deferred_release_lane_tests)
    if missing_deferred_tests:
        raise AssertionError(
            f"TODO-RELEASE-LANES exclusions are incomplete: {sorted(missing_deferred_tests)}"
        )

    discovered_tests = sorted(path.name for path in (ROOT / "tools" / "tests").glob("*.py"))
    if not discovered_tests:
        raise AssertionError("no python tests discovered under tools/tests")
    unknown_allowlist_entries = smoke_wiring_allowlist.difference(discovered_tests)
    if unknown_allowlist_entries:
        raise AssertionError(f"smoke wiring allowlist names missing tests: {sorted(unknown_allowlist_entries)}")
    unknown_deferred_entries = deferred_release_lane_tests.difference(discovered_tests)
    if unknown_deferred_entries:
        raise AssertionError(
            f"TODO-RELEASE-LANES exclusions name missing tests: {sorted(unknown_deferred_entries)}"
        )
    if inherited_openq4_only_tests != {
        "campaign_split_state_transition.py",
        "game_class_allocator_alignment.py",
        "renderer_mp_flat_items.py",
        "renderer_player_visibility.py",
        "settings_menu_coverage.py",
        "ui_embedded_icons.py",
    }:
        raise AssertionError(
            "inherited OpenQ4-only disposition must name the non-applicable campaign, allocator, flat-diffuse, multiplayer visibility, Quake settings-menu, and Quake obituary-icon contracts"
        )
    expected_api_v7_deferrals = {
        "demo_playback.py",
        "mp_bot_navigation.py",
        "multiview_demo.py",
    }
    if deferred_prey_api_v7_tests != expected_api_v7_deferrals:
        raise AssertionError("TODO-D9 test disposition does not match the Prey v7 API deferral")

    active_tests: list[str] = []
    original_run_command = VALIDATOR.run_command
    try:
        VALIDATOR.run_command = lambda command, **_kwargs: active_tests.append(Path(command[1]).name)
        VALIDATOR.run_python_tests(argparse.Namespace(dry_run=True), ROOT, {})
    finally:
        VALIDATOR.run_command = original_run_command
    active_test_set = set(active_tests)
    if active_test_set.intersection(deferred_release_lane_tests):
        raise AssertionError("deferred release-lane tests leaked into active local validation")
    if active_test_set.intersection(inherited_openq4_only_tests):
        raise AssertionError("inherited OpenQ4-only tests leaked into active local validation")
    if active_test_set.intersection(deferred_prey_api_v7_tests):
        raise AssertionError("Prey v7 API-deferred tests leaked into active local validation")
    if "macos_package_robustness.py" not in active_test_set:
        raise AssertionError("ported macOS package robustness checks must remain active")

    uncovered_tests = set(discovered_tests).difference(
        active_test_set,
        smoke_wiring_allowlist,
        deferred_release_lane_tests,
        inherited_openq4_only_tests,
        deferred_prey_api_v7_tests,
    )
    if uncovered_tests:
        raise AssertionError(f"tests have no active, runtime, or deferred disposition: {sorted(uncovered_tests)}")

    for test_name in sorted(active_test_set):
        if test_name not in push:
            raise AssertionError(f"{test_name} is not wired into push workflow smoke checks")
        if test_name not in commit:
            raise AssertionError(f"{test_name} is not wired into commit workflow smoke checks")

    for build_script in (
        "package_nightly.py",
        "package_release.py",
        "stage_windows_runtime.py",
        "sync_icons.py",
    ):
        if build_script not in push or build_script not in commit:
            raise AssertionError(f"{build_script} is not covered by workflow py_compile smoke checks")

    for token in ("TODO-RELEASE-LANES", "basepr", "one `game_<arch>` module"):
        if token not in status_ledger:
            raise AssertionError(f"rebase status ledger is missing validation deferral contract: {token}")

    windows_start = commit.index("\n  windows-x64:")
    windows_end = commit.index("\n  linux-arm64:", windows_start)
    windows_job = commit[windows_start:windows_end]
    openal_step_name = "- name: Prepare OpenAL Soft (Windows)"
    if windows_job.count(openal_step_name) != 1:
        raise AssertionError(f"Expected exactly one {openal_step_name!r} in Windows commit validation")
    openal_start = windows_job.index(openal_step_name)
    openal_end = windows_job.index("\n      - name:", openal_start + len(openal_step_name))
    openal_step = windows_job[openal_start:openal_end]
    # The project prefix is OPENPREY_ with legacy OPENQ4_ aliases, so match the suffixes.
    for token in (
        "tools/build/prepare_windows_openal.ps1",
        '_VS_TARGET_ARCH = "x64"',
        '-Architecture "x64" -OutputRoot $outputRoot',
        "_OPENAL_ROOT=$outputRoot",
    ):
        if token not in openal_step:
            raise AssertionError(f"Windows commit validation is missing OpenAL runtime preparation token {token!r}")
    if "\n        if:" in openal_step:
        raise AssertionError("Windows commit validation conditionally skips OpenAL runtime preparation")
    if windows_job.index(openal_step_name) >= windows_job.index("Run selected validation profile"):
        raise AssertionError("Windows commit validation prepares OpenAL after the build/staging profile")


def wrap_tree_stem(directory: str) -> str:
    return re.sub(r"-[0-9][0-9A-Za-z.]*$", "", directory)


def validate_workflow_wrap_paths() -> None:
    # A workflow step that reads an unpacked wrap tree must name the version the
    # wrap pins. Local checkouts keep old unpacked trees, so a stale path passes
    # locally and fails only on a clean runner: the SDL 3.4.16 bump left the
    # Windows text-store step reading subprojects/SDL3-3.4.10.
    pinned: dict[str, str] = {}
    for wrap in sorted((ROOT / "subprojects").glob("*.wrap")):
        config = configparser.ConfigParser(interpolation=None)
        config.read(wrap, encoding="utf-8")
        for section in config.sections():
            directory = config[section].get("directory")
            if directory:
                pinned[wrap_tree_stem(directory)] = directory
    if "SDL3" not in pinned:
        raise AssertionError("subprojects/sdl3.wrap does not pin an SDL3 directory")

    for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        for match in re.finditer(r"subprojects[/\\]([A-Za-z0-9_.+-]+)", text):
            directory = match.group(1)
            expected = pinned.get(wrap_tree_stem(directory))
            if expected is not None and directory != expected:
                raise AssertionError(
                    f"{workflow.name} reads subprojects/{directory}, but the wrap pins {expected}"
                )


def workflow_jobs(text: str) -> dict[str, str]:
    jobs = text[text.index("\njobs:\n"):]
    starts = list(re.finditer(r"^  ([A-Za-z0-9_-]+):\n", jobs, re.MULTILINE))
    return {
        match.group(1): jobs[match.start():starts[index + 1].start() if index + 1 < len(starts) else len(jobs)]
        for index, match in enumerate(starts)
    }


def validate_ci_job_scope() -> None:
    # script-smoke runs the validator's Python checks once. Build jobs repeat
    # them only on Windows x64 and arm64 macOS OpenGL, and none waits for the
    # smoke job. Pull requests run Commit Validation, so Push Verification
    # runs on pushes to main only.
    push = (ROOT / ".github" / "workflows" / "push-verification.yml").read_text(encoding="utf-8")
    commit = (ROOT / ".github" / "workflows" / "commit-validation.yml").read_text(encoding="utf-8")
    if "\non:\n  push:\n    branches:\n      - main\n  workflow_dispatch:\n" not in push:
        raise AssertionError("Push Verification must run on pushes to main and manual dispatch only")
    if "\non:\n  pull_request:\n  workflow_dispatch:\n" not in commit:
        raise AssertionError("Commit Validation must run on pull requests and manual dispatch")

    push_jobs = workflow_jobs(push)
    commit_jobs = workflow_jobs(commit)
    for workflow, jobs in (("push", push_jobs), ("commit", commit_jobs)):
        for name, body in jobs.items():
            if "needs: script-smoke" in body:
                raise AssertionError(f"{workflow} job {name} waits for script-smoke")

    skip = "--skip-python-tests"
    full_suite = {("push", "windows-build"), ("commit", "windows-x64")}
    skipped = {("push", "windows-arm64-build"), ("commit", "linux-arm64"), ("commit", "windows-arm64"),
               ("commit", "linux-sanitizer"), ("commit", "linux-wayland")}
    for workflow, name in full_suite | skipped:
        body = (push_jobs if workflow == "push" else commit_jobs)[name]
        if ((workflow, name) in skipped) != (skip in body):
            raise AssertionError(f"{workflow} job {name} has the wrong Python check scope")
    for workflow, name, entry in (("push", "posix-builds", "name: macOS OpenGL Push Verification"),
                                  ("commit", "macos-arm64", "bridge_label: OpenGL")):
        body = (push_jobs if workflow == "push" else commit_jobs)[name]
        if body.count("python_tests: true") != 1:
            raise AssertionError(f"{workflow} job {name} must run the Python checks in exactly one entry")
        entry_start = body.index(entry)
        entry_end = body.find("\n          - ", entry_start)
        if "python_tests: true" not in body[entry_start:entry_end if entry_end != -1 else len(body)]:
            raise AssertionError(f"{workflow} job {name} runs the Python checks outside its {entry!r} entry")
        if 'if [[ "${{ matrix.python_tests }}" != "true" ]]; then' not in body or skip not in body:
            raise AssertionError(f"{workflow} job {name} does not skip Python checks for the other entries")

    for workflow, jobs in (("push", push_jobs), ("commit", commit_jobs)):
        smoke = jobs["script-smoke"]
        commands = [line.strip() for line in smoke.splitlines() if line.strip().startswith("python tools/")]
        repeated = sorted({command for command in commands if commands.count(command) > 1})
        if repeated:
            raise AssertionError(f"{workflow} script-smoke repeats {repeated}")


def main() -> None:
    shutil.rmtree(WORK, ignore_errors=True)
    try:
        validate_positive_integer_arguments()
        validate_source_and_build_dir_guards()
        validate_game_libs_repo_guards()
        validate_staged_symlink_guard()
        validate_recursive_non_runtime_scan()
        validate_staged_casefold_collision_guard()
        validate_engine_architecture_mismatch()
        validate_game_module_suffix_guard()
        validate_game_module_architecture_match()
        validate_split_game_module_guard()
        validate_linux_runtime_dependency_guards()
        validate_windows_pdb_architecture_match()
        validate_windows_unified_staged_payload()
        validate_python_test_failure_aggregation()
        validate_validation_wiring()
        validate_workflow_wrap_paths()
        validate_ci_job_scope()
    finally:
        shutil.rmtree(WORK, ignore_errors=True)
    print("validation_hardening: ok")


if __name__ == "__main__":
    main()
