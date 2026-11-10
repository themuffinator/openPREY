#!/usr/bin/env python3
"""Behavior contract for Linux physical-host evidence collection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from linux_physical_host_evidence import (
    HOST_FILES,
    collect_linux_host_evidence,
    reject_virtualized_physical_attestation,
)


def command_runner(
    *,
    vm: str = "none",
    container: str = "none",
) -> Any:
    def run(command: tuple[str, ...]) -> dict[str, Any]:
        identifier = vm if command[-1] == "--vm" else container
        detected = identifier != "none"
        return {
            "available": True,
            "returnCode": 0 if detected else 1,
            "identifier": identifier,
            "error": "",
        }

    return run


def file_reader(values: dict[str, str]) -> Any:
    by_path = {HOST_FILES[name]: value for name, value in values.items()}

    def read(path: Path) -> str:
        return by_path.get(path, "")

    return read


def expect_rejection(evidence: dict[str, Any], marker: str) -> None:
    try:
        reject_virtualized_physical_attestation(evidence)
    except RuntimeError as exc:
        if marker not in str(exc):
            raise AssertionError(f"rejection did not identify {marker!r}: {exc}") from exc
    else:
        raise AssertionError("detected virtualization did not reject physical-hardware attestation")


def main() -> None:
    bare_metal = collect_linux_host_evidence(
        command_runner=command_runner(),
        file_reader=file_reader(
            {
                "dmiSysVendor": "Raspberry Pi Foundation",
                "dmiProductName": "Raspberry Pi 5 Model B",
                "deviceTreeModel": "Raspberry Pi 5 Model B Rev 1.0\x00",
                "kernelRelease": "6.8.0-aarch64",
                "cpuInfo": "Features : fp asimd evtstrm aes pmull sha1 sha2 crc32\n",
            }
        ),
    )
    if bare_metal["virtualMachineDetected"]:
        raise AssertionError(f"physical ARM host was classified as virtual: {bare_metal}")
    reject_virtualized_physical_attestation(bare_metal)

    kvm = collect_linux_host_evidence(
        command_runner=command_runner(vm="kvm"),
        file_reader=file_reader({}),
    )
    expect_rejection(kvm, "systemd-detect-virt --vm: kvm")

    qemu_dmi = collect_linux_host_evidence(
        command_runner=command_runner(),
        file_reader=file_reader(
            {
                "dmiSysVendor": "QEMU",
                "dmiProductName": "Standard PC",
            }
        ),
    )
    expect_rejection(qemu_dmi, "DMI identity")

    wsl = collect_linux_host_evidence(
        command_runner=command_runner(),
        file_reader=file_reader({"kernelRelease": "6.6.87.2-microsoft-standard-WSL2"}),
    )
    expect_rejection(wsl, "kernel release")

    cpu_flag = collect_linux_host_evidence(
        command_runner=command_runner(),
        file_reader=file_reader({"cpuInfo": "flags : fpu vme de pse hypervisor tsc\n"}),
    )
    expect_rejection(cpu_flag, "/proc/cpuinfo hypervisor flag")

    container_on_physical = collect_linux_host_evidence(
        command_runner=command_runner(container="docker"),
        file_reader=file_reader({"deviceTreeModel": "Raspberry Pi 5 Model B"}),
    )
    if not container_on_physical["containerDetected"]:
        raise AssertionError("container detection was not recorded")
    if container_on_physical["virtualMachineDetected"]:
        raise AssertionError("a container-only signal was incorrectly classified as a VM")

    print("linux_physical_host_evidence_contract: ok")


if __name__ == "__main__":
    main()
