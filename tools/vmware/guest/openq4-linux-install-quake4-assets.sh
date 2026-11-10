#!/usr/bin/env bash
set -euo pipefail

sudo_run() {
    if [[ "${EUID}" -eq 0 ]]; then
        "$@"
        return
    fi

    if sudo -n true >/dev/null 2>&1; then
        sudo "$@"
        return
    fi

    if [[ -z "${OPENQ4_SUDO_PASSWORD:-}" ]]; then
        echo "sudo needs a password. Re-run through Invoke-openQ4LinuxMintWorkflow.ps1 or set OPENQ4_SUDO_PASSWORD." >&2
        exit 1
    fi

    printf '%s\n' "${OPENQ4_SUDO_PASSWORD}" | sudo -S -p '' "$@"
}

mount_hgfs() {
    if mountpoint -q /mnt/hgfs; then
        return
    fi

    sudo_run mkdir -p /mnt/hgfs
    if command -v vmhgfs-fuse >/dev/null 2>&1; then
        sudo_run vmhgfs-fuse .host:/ /mnt/hgfs -o allow_other || sudo_run mount -a
    else
        sudo_run mount -a
    fi
}

root_disk_name() {
    local root_source
    root_source="$(findmnt -n -o SOURCE / || true)"
    if [[ -z "${root_source}" || "${root_source}" != /dev/* ]]; then
        return
    fi

    lsblk -no PKNAME "${root_source}" 2>/dev/null | head -n 1 || true
}

find_data_device() {
    if [[ -n "${OPENQ4_DATA_DEVICE:-}" ]]; then
        printf '%s\n' "${OPENQ4_DATA_DEVICE}"
        return
    fi

    if [[ -e /dev/disk/by-label/OPENQ4DATA ]]; then
        readlink -f /dev/disk/by-label/OPENQ4DATA
        return
    fi

    local root_disk
    root_disk="$(root_disk_name)"

    while read -r name type size_bytes readonly; do
        [[ "${type}" == "disk" ]] || continue
        [[ "${readonly}" == "0" ]] || continue
        [[ "${size_bytes}" -ge $((8 * 1024 * 1024 * 1024)) ]] || continue
        [[ "${name}" != "${root_disk}" ]] || continue

        local device="/dev/${name}"
        if lsblk -nr -o FSTYPE,MOUNTPOINT "${device}" | grep -Eq '[^[:space:]]'; then
            continue
        fi

        printf '%s\n' "${device}"
        return
    done < <(lsblk -bdn -o NAME,TYPE,SIZE,RO)
}

mount_data_disk() {
    local mount_dir="$1"
    sudo_run mkdir -p "${mount_dir}"

    if [[ -e /dev/disk/by-label/OPENQ4DATA ]]; then
        if ! mountpoint -q "${mount_dir}"; then
            sudo_run mount /dev/disk/by-label/OPENQ4DATA "${mount_dir}"
        fi
    else
        local device
        device="$(find_data_device)"
        if [[ -z "${device}" ]]; then
            echo "No safe openQ4 data disk candidate found. Set OPENQ4_DATA_DEVICE=/dev/..." >&2
            exit 1
        fi

        echo "Formatting ${device} as OPENQ4DATA for Quake 4 assets."
        sudo_run mkfs.ext4 -F -L OPENQ4DATA "${device}"
        sudo_run mount "${device}" "${mount_dir}"
    fi

    if ! grep -Eq '^[[:space:]]*LABEL=OPENQ4DATA[[:space:]]+' /etc/fstab; then
        printf '%s\n' "LABEL=OPENQ4DATA ${mount_dir} ext4 defaults,nofail 0 2" | sudo_run tee -a /etc/fstab >/dev/null
    fi

    local current_user="${SUDO_USER:-${USER}}"
    sudo_run mkdir -p "${mount_dir}/Quake4"
    sudo_run chown -R "${current_user}:${current_user}" "${mount_dir}"
}

select_quake4_source() {
    local candidates=()
    if [[ -n "${OPENQ4_Q4_SOURCE:-}" ]]; then
        candidates+=("${OPENQ4_Q4_SOURCE}")
    fi

    candidates+=(
        "/mnt/hgfs/Quake4"
        "/mnt/hgfs/Downloads/Quake 4"
        "/mnt/hgfs/Downloads/Quake4"
        "/mnt/hgfs/Downloads/Q4"
    )

    local candidate
    for candidate in "${candidates[@]}"; do
        if [[ -d "${candidate}/q4base" ]]; then
            printf '%s\n' "${candidate}"
            return
        fi
    done

    echo "No PC Quake 4 source was found. Expected a q4base directory in one of:" >&2
    printf '  %s\n' "${candidates[@]}" >&2
    exit 1
}

install_patch_if_needed() {
    local target_dir="$1"
    local apply_mode="${OPENQ4_APPLY_Q4_PATCH:-auto}"
    local patch_zip="${OPENQ4_Q4_PATCH_ZIP:-/mnt/hgfs/Downloads/quake4_patch_1.4.2-full_win-installer.zip}"

    case "${apply_mode}" in
        never)
            echo "Patch overlay skipped by OPENQ4_APPLY_Q4_PATCH=never."
            return
            ;;
        auto)
            if [[ -f "${target_dir}/CHANGES_14.txt" && -f "${target_dir}/q4base/pak019.pk4" ]]; then
                echo "Quake 4 assets already look patched; patch overlay not needed."
                return
            fi
            ;;
        always)
            ;;
        *)
            echo "Unknown OPENQ4_APPLY_Q4_PATCH='${apply_mode}'. Expected auto, always, or never." >&2
            exit 2
            ;;
    esac

    if [[ ! -f "${patch_zip}" ]]; then
        echo "Patch overlay requested but patch ZIP was not found: ${patch_zip}" >&2
        exit 1
    fi

    if ! command -v 7z >/dev/null 2>&1; then
        echo "Patch overlay needs 7z. Re-run Bootstrap or install p7zip-full/7zip in the guest." >&2
        exit 1
    fi

    local tmp_dir
    tmp_dir="$(mktemp -d)"

    echo "Extracting Quake 4 1.4.2 patch overlay from ${patch_zip}."
    7z e -y "-o${tmp_dir}" "${patch_zip}" Quake4-1.4.2.exe >/dev/null
    7z x -y "-o${tmp_dir}/patch" "${tmp_dir}/Quake4-1.4.2.exe" \
        'q4base/*' 'q4mp/*' 'pb/*' 'CHANGES_14.txt' 'README_*' >/dev/null

    rsync -a "${tmp_dir}/patch/" "${target_dir}/"
    rm -rf "${tmp_dir}"
}

mount_hgfs
data_mount="${OPENQ4_DATA_MOUNT:-/mnt/openq4-data}"
mount_data_disk "${data_mount}"
target="${OPENQ4_Q4_TARGET:-${data_mount}/Quake4}"
source="$(select_quake4_source)"

echo "Installing Quake 4 assets from ${source} to ${target}."
mkdir -p "${target}"
rsync -a --delete \
    --exclude '/.tmp/' \
    --exclude '/CrashReports/' \
    --exclude '/q4base/generated/' \
    --exclude '/q4base/savegames/' \
    --exclude '/q4base/screenshots/' \
    --exclude '/q4mp/screenshots/' \
    "${source}/" "${target}/"

install_patch_if_needed "${target}"

if [[ ! -d "${target}/q4base" ]]; then
    echo "Installed asset directory is missing q4base: ${target}" >&2
    exit 1
fi

echo "Quake 4 asset install complete: ${target}"
du -sh "${target}" || true
