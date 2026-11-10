#!/usr/bin/env bash
set -euo pipefail

log() {
    printf '%s\n' "$*"
}

require_command() {
    local name="$1"
    local hint="$2"
    if ! command -v "${name}" >/dev/null 2>&1; then
        printf 'Missing required command: %s\n%s\n' "${name}" "${hint}" >&2
        exit 1
    fi
}

contains_control_chars() {
    LC_ALL=C printf '%s' "$1" | LC_ALL=C grep -q '[[:cntrl:]]'
}

require_guest_home() {
    local home_value="${OPENQ4_GUEST_HOME:-${HOME:-}}"
    if [[ -z "${home_value}" ]]; then
        echo "HOME must be set or OPENQ4_GUEST_HOME must point to the macOS guest home directory." >&2
        exit 2
    fi
    if contains_control_chars "${home_value}"; then
        echo "OPENQ4_GUEST_HOME/HOME must not contain control characters." >&2
        exit 2
    fi
    case "${home_value}" in
        /*)
            ;;
        *)
            echo "OPENQ4_GUEST_HOME/HOME must be an absolute POSIX path: ${home_value}" >&2
            exit 2
            ;;
    esac
    case "${home_value}" in
        "/"|"."|".."|*\\*|*//*|*/./*|*/../*|*/.|*/..)
            echo "OPENQ4_GUEST_HOME/HOME must be a clean absolute POSIX path: ${home_value}" >&2
            exit 2
            ;;
    esac
    if [[ ! -d "${home_value}" ]]; then
        echo "macOS guest home directory does not exist: ${home_value}" >&2
        exit 2
    fi
    printf '%s\n' "${home_value%/}"
}

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "This bootstrap script must run inside macOS." >&2
    exit 1
fi

GUEST_HOME="$(require_guest_home)"
export HOME="${GUEST_HOME}"

log "Checking Xcode Command Line Tools..."
if ! xcode-select -p >/dev/null 2>&1; then
    cat >&2 <<'EOF'
Xcode Command Line Tools are not installed.
Run this inside the macOS VM, finish the GUI prompt, then rerun bootstrap:

  xcode-select --install
EOF
    exit 1
fi

require_command git "Install Xcode Command Line Tools with: xcode-select --install"
require_command clang "Install Xcode Command Line Tools with: xcode-select --install"
require_command xcrun "Install Xcode Command Line Tools with: xcode-select --install"
require_command plutil "Install Xcode Command Line Tools with: xcode-select --install"
require_command lipo "Install Xcode Command Line Tools with: xcode-select --install"
require_command otool "Install Xcode Command Line Tools with: xcode-select --install"
require_command codesign "Install Xcode Command Line Tools with: xcode-select --install"
require_command python3 "Install Xcode Command Line Tools or Homebrew Python."
require_command rsync "rsync is expected on macOS for source and asset copies."

if command -v brew >/dev/null 2>&1; then
    log "Installing/updating build tools through Homebrew..."
    brew update || true
    brew install cmake ninja pkg-config python git rsync || true
else
    cat <<'EOF'
Homebrew was not found. The workflow can still use a Python Meson/Ninja venv,
but CMake/pkg-config may be missing if the macOS image is minimal.
Install Homebrew from https://brew.sh/ if the build later reports missing tools.
EOF
fi

meson_venv="${GUEST_HOME}/.local/share/openq4-meson-venv"
log "Installing user-local Meson/Ninja into ${meson_venv}..."
python3 -m venv "${meson_venv}"
"${meson_venv}/bin/python" -m pip install --upgrade pip
"${meson_venv}/bin/python" -m pip install --upgrade 'meson>=1.6' ninja
mkdir -p "${GUEST_HOME}/.local/bin"
ln -sf "${meson_venv}/bin/meson" "${GUEST_HOME}/.local/bin/meson"
ln -sf "${meson_venv}/bin/ninja" "${GUEST_HOME}/.local/bin/ninja"

mkdir -p "${GUEST_HOME}/openq4-work/results"

cat <<'EOF'
macOS bootstrap complete.

Expected next host-side command:
  powershell -NoProfile -ExecutionPolicy Bypass -File tools/macos/Invoke-openQ4MacOSWorkflow.ps1 -Action Assets,Sync,Build,Smoke -MacHost <vm-hostname-or-ip>
EOF
