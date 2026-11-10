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

sudo_env_run() {
    if [[ "${EUID}" -eq 0 ]]; then
        env "$@"
        return
    fi

    if sudo -n true >/dev/null 2>&1; then
        sudo env "$@"
        return
    fi

    if [[ -z "${OPENQ4_SUDO_PASSWORD:-}" ]]; then
        echo "sudo needs a password. Re-run through Invoke-openQ4LinuxMintWorkflow.ps1 or set OPENQ4_SUDO_PASSWORD." >&2
        exit 1
    fi

    printf '%s\n' "${OPENQ4_SUDO_PASSWORD}" | sudo -S -p '' env "$@"
}

required_packages=(
    build-essential
    ca-certificates
    cmake
    curl
    g++
    gcc
    gdb
    git
    libasound2-dev
    libdbus-1-dev
    libdecor-0-dev
    libdrm-dev
    libegl1-mesa-dev
    libfribidi-dev
    libgbm-dev
    libgl1-mesa-dev
    libibus-1.0-dev
    libjack-dev
    libopenal-dev
    libpipewire-0.3-dev
    libpulse-dev
    libthai-dev
    libudev-dev
    libwayland-dev
    libx11-dev
    libxcursor-dev
    libxext-dev
    libxfixes-dev
    libxi-dev
    libxkbcommon-dev
    libxrandr-dev
    libxss-dev
    libxtst-dev
    libxxf86dga-dev
    libxxf86vm-dev
    mesa-utils
    meson
    ninja-build
    open-vm-tools
    open-vm-tools-desktop
    openssh-server
    pkg-config
    python3
    python3-pip
    python3-venv
    rsync
    strace
    xauth
)

optional_packages=(
    7zip
    clang
    libsndio-dev
    p7zip-full
)

export DEBIAN_FRONTEND=noninteractive

echo "Updating apt metadata..."
sudo_env_run DEBIAN_FRONTEND=noninteractive apt-get update

echo "Installing openQ4 Linux build/runtime dependencies..."
sudo_env_run DEBIAN_FRONTEND=noninteractive apt-get install -y "${required_packages[@]}"

for package_name in "${optional_packages[@]}"; do
    if ! sudo_env_run DEBIAN_FRONTEND=noninteractive apt-get install -y "${package_name}"; then
        echo "Optional package '${package_name}' was not available; continuing."
    fi
done

echo "Enabling SSH and VMware tools..."
sudo_run systemctl enable --now ssh || true
sudo_run systemctl enable --now open-vm-tools || true
sudo_run systemctl enable --now vmtoolsd || true

if [[ -f /etc/fuse.conf ]] && ! grep -Eq '^[[:space:]]*user_allow_other\b' /etc/fuse.conf; then
    echo "Enabling user_allow_other for VMware shared-folder mounts."
    printf '%s\n' "user_allow_other" | sudo_run tee -a /etc/fuse.conf >/dev/null
fi

if command -v vmhgfs-fuse >/dev/null 2>&1; then
    sudo_run mkdir -p /mnt/hgfs
    if ! grep -Eq '^[.]host:/[[:space:]]+/mnt/hgfs[[:space:]]+fuse[.]vmhgfs-fuse' /etc/fstab; then
        printf '%s\n' ".host:/ /mnt/hgfs fuse.vmhgfs-fuse allow_other,defaults 0 0" | sudo_run tee -a /etc/fstab >/dev/null
    fi

    if ! mountpoint -q /mnt/hgfs; then
        sudo_run mount -a || sudo_run vmhgfs-fuse .host:/ /mnt/hgfs -o allow_other
    fi
fi

if command -v vmware-hgfsclient >/dev/null 2>&1; then
    echo "Available VMware shared folders:"
    vmware-hgfsclient || true
fi

current_user="${SUDO_USER:-${USER}}"
if id "${current_user}" >/dev/null 2>&1; then
    sudo_run usermod -aG audio,render,video "${current_user}" || true
fi

meson_venv="${HOME}/.local/share/openq4-meson-venv"
echo "Installing user-local Meson for SDL3 subproject support..."
python3 -m venv "${meson_venv}"
"${meson_venv}/bin/python" -m pip install --upgrade pip
"${meson_venv}/bin/python" -m pip install --upgrade 'meson>=1.6'
mkdir -p "${HOME}/.local/bin"
ln -sf "${meson_venv}/bin/meson" "${HOME}/.local/bin/meson"

cat <<'EOF'
Linux Mint bootstrap complete.

Recommended next command from the Windows host:
  powershell -NoProfile -ExecutionPolicy Bypass -File tools/vmware/Invoke-openQ4LinuxMintWorkflow.ps1 -Action Build -GuestUser codex
EOF
