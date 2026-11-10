#!/usr/bin/env python3
"""Record best-effort Linux host evidence for physical-hardware signoff.

The inspection deliberately does not claim that software can prove bare metal.
It records several independent host signals and rejects a physical-hardware
attestation when any supported signal positively identifies a VM or emulator.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Callable


CommandRunner = Callable[[tuple[str, ...]], dict[str, Any]]
FileReader = Callable[[Path], str]

HOST_FILES = {
    "hypervisorType": Path("/sys/hypervisor/type"),
    "dmiSysVendor": Path("/sys/class/dmi/id/sys_vendor"),
    "dmiProductName": Path("/sys/class/dmi/id/product_name"),
    "dmiProductVersion": Path("/sys/class/dmi/id/product_version"),
    "dmiBoardVendor": Path("/sys/class/dmi/id/board_vendor"),
    "dmiBoardName": Path("/sys/class/dmi/id/board_name"),
    "deviceTreeModel": Path("/proc/device-tree/model"),
    "deviceTreeHypervisorCompatible": Path("/proc/device-tree/hypervisor/compatible"),
    "kernelRelease": Path("/proc/sys/kernel/osrelease"),
    "cpuInfo": Path("/proc/cpuinfo"),
}

VM_IDENTITY_PATTERN = re.compile(
    r"\b(?:qemu|kvm|vmware|virtualbox|parallels|xen|bochs|bhyve|hyper-v|"
    r"virtual machine|amazon ec2|google compute engine|openstack|digitalocean|"
    r"windows subsystem for linux|wsl)\b",
    re.IGNORECASE,
)


def _clean_text(value: str, limit: int = 4096) -> str:
    return " ".join(value.replace("\x00", " ").split())[:limit]


def _read_host_file(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            return stream.read(256 * 1024)
    except OSError:
        return ""


def _run_command(command: tuple[str, ...]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except FileNotFoundError:
        return {
            "available": False,
            "returnCode": None,
            "identifier": "",
            "error": "command not found",
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "available": False,
            "returnCode": None,
            "identifier": "",
            "error": _clean_text(str(exc), 512),
        }

    return {
        "available": True,
        "returnCode": completed.returncode,
        "identifier": _clean_text(completed.stdout, 512).lower(),
        "error": _clean_text(completed.stderr, 512),
    }


def _positive_systemd_detection(probe: dict[str, Any]) -> bool:
    identifier = str(probe.get("identifier", "")).strip().lower()
    return bool(
        probe.get("available")
        and probe.get("returnCode") == 0
        and identifier
        and identifier != "none"
    )


def _cpu_has_hypervisor_flag(cpu_info: str) -> bool:
    for line in cpu_info.splitlines():
        name, separator, value = line.partition(":")
        if separator and name.strip().lower() in {"flags", "features"}:
            if "hypervisor" in value.lower().split():
                return True
    return False


def collect_linux_host_evidence(
    *,
    command_runner: CommandRunner = _run_command,
    file_reader: FileReader = _read_host_file,
) -> dict[str, Any]:
    """Collect portable, JSON-safe host identity and virtualization signals."""

    vm_probe = command_runner(("systemd-detect-virt", "--vm"))
    container_probe = command_runner(("systemd-detect-virt", "--container"))
    raw_files = {name: file_reader(path) for name, path in HOST_FILES.items()}
    identity = {
        name: _clean_text(value)
        for name, value in raw_files.items()
        if name != "cpuInfo" and _clean_text(value)
    }
    cpu_hypervisor_flag = _cpu_has_hypervisor_flag(raw_files.get("cpuInfo", ""))

    indicators: list[str] = []
    if _positive_systemd_detection(vm_probe):
        indicators.append(f"systemd-detect-virt --vm: {vm_probe['identifier']}")

    hypervisor_type = identity.get("hypervisorType", "")
    if hypervisor_type:
        indicators.append(f"/sys/hypervisor/type: {hypervisor_type}")

    device_tree_hypervisor = identity.get("deviceTreeHypervisorCompatible", "")
    if device_tree_hypervisor:
        indicators.append(
            "/proc/device-tree/hypervisor/compatible: " + device_tree_hypervisor
        )

    dmi_text = " ".join(
        identity.get(name, "")
        for name in (
            "dmiSysVendor",
            "dmiProductName",
            "dmiProductVersion",
            "dmiBoardVendor",
            "dmiBoardName",
        )
    )
    dmi_match = VM_IDENTITY_PATTERN.search(dmi_text)
    if dmi_match:
        indicators.append(f"DMI identity: {_clean_text(dmi_text, 1024)}")

    device_tree_model = identity.get("deviceTreeModel", "")
    if VM_IDENTITY_PATTERN.search(device_tree_model):
        indicators.append(f"device-tree model: {device_tree_model}")

    kernel_release = identity.get("kernelRelease", "")
    if re.search(r"(?:microsoft|\bwsl\b)", kernel_release, re.IGNORECASE):
        indicators.append(f"kernel release: {kernel_release}")

    if cpu_hypervisor_flag:
        indicators.append("/proc/cpuinfo hypervisor flag")

    # Keep the list stable and free of duplicates when two fields collapse to
    # the same rendered value.
    indicators = list(dict.fromkeys(indicators))
    return {
        "schemaVersion": 1,
        "scope": (
            "Best-effort rejection of known VM/emulator indicators; absence of an "
            "indicator does not prove physical hardware and operator attestation remains required."
        ),
        "virtualMachineDetected": bool(indicators),
        "containerDetected": _positive_systemd_detection(container_probe),
        "virtualizationIndicators": indicators,
        "systemdDetectVirt": {
            "vm": vm_probe,
            "container": container_probe,
        },
        "hostIdentity": identity,
        "cpuHypervisorFlag": cpu_hypervisor_flag,
    }


def reject_virtualized_physical_attestation(evidence: dict[str, Any]) -> None:
    """Fail when an operator's physical-host claim conflicts with inspection."""

    if not evidence.get("virtualMachineDetected"):
        return
    indicators = evidence.get("virtualizationIndicators") or ["unspecified indicator"]
    raise RuntimeError(
        "--physical-hardware conflicts with detected VM/emulator evidence: "
        + "; ".join(str(item) for item in indicators)
    )

