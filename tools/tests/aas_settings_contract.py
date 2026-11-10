#!/usr/bin/env python3
"""Guard the Quake 4 AAS 1.08 settings parser/writer round trip."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEST_PATH = "tools/tests/aas_settings_contract.py"


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_bytes().decode("windows-1252")


def function_body(source: str, signature: str, context: str) -> str:
    start = source.find(signature)
    if start < 0:
        raise AssertionError(f"Missing {signature!r} in {context}")
    opening = source.find("{", start + len(signature))
    if opening < 0:
        raise AssertionError(f"Missing body for {signature!r} in {context}")

    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    raise AssertionError(f"Unterminated body for {signature!r} in {context}")


def require(source: str, token: str, context: str) -> None:
    if token not in source:
        raise AssertionError(f"Missing {token!r} in {context}")


def validate_aas_settings_round_trip() -> None:
    source = read("src/aas/AASFile.cpp")

    constructor = function_body(source, "idAASSettings::idAASSettings( void )", "AAS settings constructor")
    require(constructor, "generateAllFaces = false;", "AAS settings constructor")
    require(constructor, "generateTacticalFeatures = false;", "AAS settings constructor")

    parser = function_body(source, "bool idAASSettings::FromParser( idLexer &src )", "AAS settings parser")
    require(parser, 'token == "generateAllFaces"', "AAS 1.08 settings parser")
    require(parser, "ParseBool( src, generateAllFaces )", "AAS 1.08 settings parser")
    require(parser, 'token == "generateTacticalFeatures"', "AAS 1.08 settings parser")
    require(parser, "ParseBool( src, generateTacticalFeatures )", "AAS 1.08 settings parser")

    writer = function_body(source, "bool idAASSettings::WriteToFile( idFile *fp ) const", "AAS settings writer")
    for setting in ("generateAllFaces", "generateTacticalFeatures"):
        require(writer, f'"\\t{setting} = %d\\n", {setting}', "AAS 1.08 settings writer")
        if f'"\\t{setting} = 0\\n"' in writer:
            raise AssertionError(f"AAS settings writer still hardcodes {setting}")


def validate_ci_wiring() -> None:
    validator = read("tools/validation/openq4_validate.py")
    if validator.count("aas_settings_contract.py") != 1:
        raise AssertionError("Local validation must register the AAS settings contract exactly once")

    for workflow_path in (
        ".github/workflows/commit-validation.yml",
        ".github/workflows/push-verification.yml",
    ):
        workflow = read(workflow_path)
        if workflow.count(TEST_PATH) != 2:
            raise AssertionError(f"{workflow_path} must compile and run {TEST_PATH}")
        require(workflow, f"python {TEST_PATH}", workflow_path)


def main() -> None:
    validate_aas_settings_round_trip()
    validate_ci_wiring()
    print("aas_settings_contract: ok")


if __name__ == "__main__":
    main()
