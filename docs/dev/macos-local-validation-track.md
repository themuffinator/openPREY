# macOS Local Validation Track

This track is for Apple-support work when the maintainer does not have access
to macOS. It proves static contracts, packaging fixtures, support-intake
plumbing, and workflow shape. It does not run openQ4 on macOS and does not
replace the Apple-hardware signoff workflow.

## Static Command

Run the named profile directly:

```bash
python tools/validation/openq4_validate.py macos-static
```

On Windows:

```powershell
powershell -ExecutionPolicy Bypass -File tools/validation/validate_macos_static.ps1
```

On Linux or another POSIX shell:

```bash
bash tools/validation/validate_macos_static.sh
```

The `macos-static` profile runs the normal Python static/policy tests, lints
shell entrypoints when Bash is available, and runs push/PR validation dry-runs
without building or installing. The dry-run coverage is equivalent to checking:

```bash
bash tools/validation/validate_push.sh --dry-run
bash tools/validation/validate_pr.sh --dry-run
```

## What It Covers

- Python static/policy tests for the macOS support plan.
- Synthetic Apple GL 2.1 behavior through
  `tools/tests/macos_apple_gl21_arb2_corridor.py`.
- Synthetic macOS package/archive fixtures through
  `tools/tests/macos_signoff_archive.py`,
  `tools/tests/macos_metal_bridge.py`, and
  `tools/tests/macos_package_robustness.py`.
- Support-data, symbolication, OpenAL, package-layout, matrix, native-backend,
  and GameLibs alignment guardrails.
- CI/workflow syntax and dry-run validation for release-matrix changes.

## Optional Renderer Self-Tests

Renderer self-test binaries are allowed only on available non-macOS hosts. Run
them after a local Windows or Linux build/stage when shared renderer code was
touched:

```bash
python tools/validation/openq4_validate.py macos-static \
  --runtime \
  --runtime-cases renderer-default-safety-selftest \
  --runtime-tiers auto \
  --runtime-basepath "" \
  --runtime-skip-official-pak-validation
```

The `macos-static` profile rejects `--runtime` on macOS. Use the Apple-hardware
workflow in `docs/dev/macos-vm-testing-workflow.md` for actual macOS runtime
evidence.

## Evidence Boundary

Passing this track means the no-platform-access robustness work is internally
consistent. It does not prove Finder behavior, Gatekeeper behavior, input,
audio, display modes, OpenGL/Metal bridge gameplay, issue #98 visual parity, or
complete runtime signoff on Apple hardware.
