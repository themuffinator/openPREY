#!/usr/bin/env python3
"""Regression checks for the focused clang-tidy input-safety lane."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / ".tmp" / "clang-tidy-input-safety-test" / str(os.getpid())
SCRIPT = ROOT / "tools" / "analysis" / "clang_tidy_input_safety.py"
WINDOWS_X64_WARNING_ERRORS = {
    "/we4101",
    "/we4189",
    "/we4267",
    "/we4324",
    "/we4505",
}


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("openq4_clang_tidy_input_safety_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ANALYSIS = load_script()


def check_msvc_sanitization() -> None:
    precompiled = ROOT / "src" / "idlib" / "precompiled.h"
    arguments = [
        "cl",
        "-I..\\src",
        "/FIprecompiled.h",
        "/Yuprecompiled.h",
        "/Fpclient.pch",
        "/source-charset:windows-1252",
        "/execution-charset:windows-1252",
        "-DOPENQ4_INPUT_TEST=1",
        "/std:c++20",
        "/c",
        "../src/framework/UsercmdGen.cpp",
    ]
    sanitized = ANALYSIS.sanitize_compile_arguments(arguments, precompiled)
    joined = " ".join(sanitized).lower()
    for forbidden in ("/yu", "/fp", "/source-charset", "/execution-charset"):
        if forbidden in joined:
            raise AssertionError(f"MSVC analysis command retained incompatible flag {forbidden}")
    expected_include = f"/FI{precompiled.resolve()}"
    if expected_include not in sanitized:
        raise AssertionError("MSVC PCH was not replaced by a textual forced include")
    for retained in ("-DOPENQ4_INPUT_TEST=1", "/std:c++20", "../src/framework/UsercmdGen.cpp"):
        if retained not in sanitized:
            raise AssertionError(f"MSVC analysis command dropped semantic flag {retained}")

    separated = ANALYSIS.sanitize_compile_arguments(
        ["cl", "/Yu", "-DKEEP_AFTER_YU=1", "/FI", "precompiled.h", "/c", "input.cpp"],
        precompiled,
    )
    if "-DKEEP_AFTER_YU=1" not in separated:
        raise AssertionError("standalone /Yu removal consumed the following semantic flag")
    include_index = separated.index("/FI")
    if separated[include_index + 1] != str(precompiled.resolve()):
        raise AssertionError("separated MSVC forced include was not made textual")


def check_posix_sanitization() -> None:
    precompiled = ROOT / "src" / "idlib" / "precompiled.h"
    arguments = [
        "c++",
        "-I../src",
        "-fpch-preprocess",
        "-include",
        "precompiled.h",
        "-Winvalid-pch",
        "-DOPENQ4_INPUT_TEST=1",
        "-std=c++20",
        "-c",
        "../src/framework/UsercmdGen.cpp",
    ]
    sanitized = ANALYSIS.sanitize_compile_arguments(arguments, precompiled)
    for forbidden in ("-fpch-preprocess", "-Winvalid-pch"):
        if forbidden in sanitized:
            raise AssertionError(f"POSIX analysis command retained incompatible flag {forbidden}")
    include_index = sanitized.index("-include")
    if sanitized[include_index + 1] != str(precompiled.resolve()):
        raise AssertionError("POSIX PCH was not replaced by a textual forced include")
    if "-DOPENQ4_INPUT_TEST=1" not in sanitized or "-std=c++20" not in sanitized:
        raise AssertionError("POSIX analysis command dropped semantic flags")


def fake_entry(directory: Path, source: Path, target: str) -> dict[str, object]:
    return {
        "directory": str(directory),
        "arguments": [
            "cl",
            f"-I{target}.p",
            "/FIprecompiled.h",
            "/Yuprecompiled.h",
            f"/Fp{target}.pch",
            "/source-charset:windows-1252",
            "/execution-charset:windows-1252",
            "/std:c++20",
            "/c",
            str(source),
        ],
        "file": str(source),
    }


def check_database_generation() -> None:
    build_dir = WORK / "builddir"
    build_dir.mkdir(parents=True, exist_ok=True)
    sources = tuple(Path(source).resolve() for source in ANALYSIS.PRODUCTION_SOURCES)
    database = []
    for source in sources:
        database.extend(
            (
                fake_entry(build_dir, source, "openQ4-ded_x64.exe"),
                fake_entry(build_dir, source, "openQ4-client_x64.exe"),
            )
        )
    (build_dir / "compile_commands.json").write_text(json.dumps(database), encoding="utf-8")

    generated = ANALYSIS.build_analysis_database(build_dir)
    if len(generated) != len(sources) + 1:
        raise AssertionError("analysis database must contain every production and native safety translation unit")
    production_entries = generated[:-1]
    safety = generated[-1]
    if tuple(Path(entry["file"]).resolve() for entry in production_entries) != sources:
        raise AssertionError("analysis production entries target the wrong sources or order")
    for entry in production_entries:
        if not any("openQ4-client_x64.exe.p" in str(argument) for argument in entry["arguments"]):
            raise AssertionError("analysis did not select the deterministic client compilation command")
    if Path(safety["file"]).resolve() != (ROOT / "tools" / "tests" / "native" / "CoreSafetyTest.cpp").resolve():
        raise AssertionError("analysis safety entry targets the wrong source")
    if any(str(argument).lower().startswith(("/fi", "/yu", "/fp")) for argument in safety["arguments"]):
        raise AssertionError("standalone safety analysis unexpectedly depends on project PCH state")


def check_fail_closed_profile() -> None:
    required_checks = {
        "clang-analyzer-core.*",
        "clang-analyzer-security.*",
        "clang-analyzer-cplusplus.NewDelete*",
        "clang-analyzer-optin.cplusplus.UninitializedObject",
        "clang-analyzer-unix.Malloc",
        "clang-analyzer-deadcode.DeadStores",
    }
    if not required_checks.issubset(set(ANALYSIS.CHECKS)):
        raise AssertionError("focused analyzer profile lost required safety checks")
    if not set(ANALYSIS.REQUIRED_ENABLED_CHECKS).issuperset(
        {
            "clang-analyzer-core.CallAndMessage",
            "clang-analyzer-security.insecureAPI.strcpy",
            "clang-analyzer-cplusplus.NewDelete",
            "clang-analyzer-optin.cplusplus.UninitializedObject",
            "clang-analyzer-unix.Malloc",
            "clang-analyzer-deadcode.DeadStores",
        }
    ):
        raise AssertionError("clang-tidy capability check does not fail closed")

    for header in (
        r"E:\Repositories\openQ4\src\idlib\NumericString.h",
        "/repo/src/idlib/NumericString.h",
        r"E:\Repositories\openQ4\src\idlib\Token.h",
        "/repo/src/idlib/Token.h",
    ):
        if re.match(ANALYSIS.HEADER_FILTER, header) is None:
            raise AssertionError(f"header filter does not match production path style {header!r}")
    if re.match(ANALYSIS.HEADER_FILTER, "/repo/src/idlib/Str.h") is not None:
        raise AssertionError("header filter reaches unrelated production headers")

    command = ANALYSIS.clang_tidy_command("clang-tidy", WORK)
    if "--warnings-as-errors=*" not in command:
        raise AssertionError("clang-tidy diagnostics are not fail-closed")
    header_argument = next((argument for argument in command if argument.startswith("--header-filter=")), "")
    if "NumericString|Token" not in header_argument:
        raise AssertionError("production numeric/token helpers are excluded from header diagnostics")
    expected_sources = {str(Path(source).resolve()) for source in ANALYSIS.PRODUCTION_SOURCES}
    expected_sources.add(str((ROOT / "tools" / "tests" / "native" / "CoreSafetyTest.cpp").resolve()))
    if not expected_sources.issubset(set(command)):
        raise AssertionError("clang-tidy command does not cover every safety translation unit")


def check_output_guard() -> None:
    valid = ANALYSIS.validate_output_dir(ROOT / ".tmp" / "clang-tidy-contract-output")
    if ROOT / ".tmp" not in valid.parents:
        raise AssertionError("valid analysis output escaped .tmp")
    try:
        ANALYSIS.validate_output_dir(ROOT / "builddir" / "clang-tidy-output")
    except ANALYSIS.AnalysisError:
        pass
    else:
        raise AssertionError("analysis output guard accepted a path outside .tmp")


def meson_conditional_body(source: str, condition: str) -> str:
    lines = source.splitlines()
    opening = f"if {condition}"
    start = next((index for index, line in enumerate(lines) if line.strip() == opening), None)
    if start is None:
        raise AssertionError(f"Meson policy is missing {opening!r}")

    depth = 1
    body: list[str] = []
    for line in lines[start + 1 :]:
        statement = line.strip()
        if statement.startswith("if "):
            depth += 1
        elif statement == "endif":
            depth -= 1
            if depth == 0:
                return "\n".join(body)
        body.append(line)
    raise AssertionError(f"Meson policy has an unterminated {opening!r} block")


def check_windows_warning_policy() -> None:
    game_repo = Path(
        os.environ.get("OPENQ4_GAMELIBS_REPO", str(ROOT))
    ).resolve()
    policies = (
        (
            ROOT / "meson.build",
            "cpp.get_argument_syntax() == 'msvc'",
            "is_msvc and host_cpu_family == 'x86_64'",
            "shared_cpp_args",
        ),
    )
    for policy, compiler_condition, architecture_condition, argument_list in policies:
        if not policy.is_file():
            raise AssertionError(f"Windows warning policy source is missing: {policy}")
        source = policy.read_text(encoding="utf-8")
        compiler_body = meson_conditional_body(source, compiler_condition)
        warning_body = meson_conditional_body(compiler_body, architecture_condition)
        assignment = re.search(
            r"cleaned_windows_x64_warning_errors\s*=\s*\[(?P<body>.*?)\]",
            warning_body,
            re.DOTALL,
        )
        if assignment is None:
            raise AssertionError(f"{policy} lost the dedicated Windows x64 warning list")
        configured = set(re.findall(r"['\"](/we\d+)['\"]", assignment.group("body"), re.IGNORECASE))
        missing = sorted(WINDOWS_X64_WARNING_ERRORS - configured)
        if missing:
            raise AssertionError(f"{policy} is missing warning errors: {', '.join(missing)}")
        if f"{argument_list} += cleaned_windows_x64_warning_errors" not in warning_body:
            raise AssertionError(f"{policy} applies the warning list outside {argument_list}")
        conflicts = sorted(
            flag.replace("/we", "/wd")
            for flag in WINDOWS_X64_WARNING_ERRORS
            if flag.replace("/we", "/wd") in source.lower()
        )
        if conflicts:
            raise AssertionError(f"{policy} suppresses gated warnings: {', '.join(conflicts)}")
        if re.search(r"['\"]/WX['\"]", source, re.IGNORECASE):
            raise AssertionError(f"{policy} introduced an unsupported blanket /WX policy")
    source = (ROOT / 'meson.build').read_text(encoding='utf-8')
    assert 'game_common_cpp_args = shared_cpp_args +' in source


def check_ci_wiring() -> None:
    expected_build_dirs = {
        ROOT / ".github" / "workflows" / "commit-validation.yml": ".tmp/validation/pr-builddir",
        ROOT / ".github" / "workflows" / "push-verification.yml": "builddir",
    }
    for workflow, build_dir in expected_build_dirs.items():
        source = workflow.read_text(encoding="utf-8")
        for token in (
            "tools/analysis/clang_tidy_input_safety.py \\",
            "tools/tests/clang_tidy_input_safety.py \\",
            "python tools/tests/clang_tidy_input_safety.py",
            "Run focused input-safety static analysis",
            f"python tools/analysis/clang_tidy_input_safety.py --build-dir {build_dir}",
        ):
            if token not in source:
                raise AssertionError(f"{workflow.name} is missing clang-tidy gate token {token!r}")


def main() -> int:
    try:
        check_msvc_sanitization()
        check_posix_sanitization()
        check_database_generation()
        check_fail_closed_profile()
        check_output_guard()
        check_windows_warning_policy()
        check_ci_wiring()
    finally:
        shutil.rmtree(WORK, ignore_errors=True)
    print("clang-tidy input-safety contract: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
