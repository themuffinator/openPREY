#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

OPENAL_SOFT_VERSION="1.25.2"
OPENAL_SOFT_ARCHIVE_SHA256="fb27e5839aa11f0e5b9d33756965291fad5d6909ab928ea1f796f4a1a6877894"
OPENAL_SOFT_ARCHIVE_URL="https://github.com/kcat/openal-soft/archive/refs/tags/${OPENAL_SOFT_VERSION}.tar.gz"
OPENAL_SOFT_DYLIB_NAME="libopenal.1.dylib"
OPENAL_SOFT_INSTALL_NAME="@rpath/${OPENAL_SOFT_DYLIB_NAME}"

architecture=""
deployment_target="11.0"
output_root=""
stage_install_dir=""
verify_only=0

usage() {
    cat <<'EOF'
Usage: prepare_macos_openal_soft.sh [options]

Build the pinned OpenAL Soft runtime used by macOS openQ4 packages.

Options:
  --architecture <arm64|x64>       Target architecture (defaults to host)
  --deployment-target <version>    Minimum macOS version (default: 11.0)
  --output-root <directory>        Prepared dependency root
  --stage-install-dir <directory>  Copy runtime, license, and source into a Meson install tree
  --verify-only                    Validate an existing prepared root without rebuilding
  --help                           Show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --architecture)
            architecture="${2:?--architecture requires a value}"
            shift 2
            ;;
        --deployment-target)
            deployment_target="${2:?--deployment-target requires a value}"
            shift 2
            ;;
        --output-root)
            output_root="${2:?--output-root requires a value}"
            shift 2
            ;;
        --stage-install-dir)
            stage_install_dir="${2:?--stage-install-dir requires a value}"
            shift 2
            ;;
        --verify-only)
            verify_only=1
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "OpenAL Soft macOS preparation requires a macOS host." >&2
    exit 1
fi

if [[ ! "${OPENAL_SOFT_ARCHIVE_SHA256}" =~ ^[0-9a-f]{64}$ ]]; then
    echo "OpenAL Soft SHA-256 pin must be exactly 64 lowercase hexadecimal characters." >&2
    exit 1
fi

for required_tool in awk cmake curl grep install_name_tool lipo ninja otool pkg-config shasum tar xargs; do
    if ! command -v "${required_tool}" >/dev/null 2>&1; then
        echo "Required macOS OpenAL Soft build tool is missing from PATH: ${required_tool}" >&2
        exit 1
    fi
done

if [[ -z "${architecture}" ]]; then
    case "$(uname -m)" in
        arm64) architecture="arm64" ;;
        x86_64) architecture="x64" ;;
        *)
            echo "Unsupported macOS host architecture: $(uname -m)" >&2
            exit 1
            ;;
    esac
fi

case "${architecture}" in
    arm64) cmake_architecture="arm64" ;;
    x64) cmake_architecture="x86_64" ;;
    *)
        echo "Unsupported macOS OpenAL Soft architecture: ${architecture}" >&2
        exit 1
        ;;
esac

if [[ ! "${deployment_target}" =~ ^[0-9]+([.][0-9]+){1,2}$ ]]; then
    echo "Invalid macOS deployment target: ${deployment_target}" >&2
    exit 1
fi

if [[ -z "${output_root}" ]]; then
    output_root="${PROJECT_ROOT}/.tmp/openal-soft-macos-${architecture}"
fi

mkdir -p "${PROJECT_ROOT}/.tmp"

sha256_file() {
    shasum -a 256 "$1" | awk '{print tolower($1)}'
}

validate_prepared_root() {
    local root="$1"
    local runtime="${root}/lib/${OPENAL_SOFT_DYLIB_NAME}"
    local license="${root}/share/licenses/openal-soft/COPYING"
    local pffft_license="${root}/share/licenses/openal-soft/LICENSE-pffft"
    local fmt_license="${root}/share/licenses/openal-soft/LICENSE-fmt"
    local gsl_license="${root}/share/licenses/openal-soft/LICENSE-gsl"
    local source_notice="${root}/share/licenses/openal-soft/SOURCE.md"
    local source_archive="${root}/share/licenses/openal-soft/openal-soft-${OPENAL_SOFT_VERSION}.tar.gz"
    local pkg_config_file="${root}/lib/pkgconfig/openal.pc"

    for required in \
        "${runtime}" \
        "${license}" \
        "${pffft_license}" \
        "${fmt_license}" \
        "${gsl_license}" \
        "${source_notice}" \
        "${source_archive}" \
        "${pkg_config_file}"; do
        if [[ ! -s "${required}" || -L "${required}" ]]; then
            echo "Prepared OpenAL Soft file is missing, empty, or a symlink: ${required}" >&2
            exit 1
        fi
    done

    if [[ ! -x "${runtime}" ]]; then
        echo "Prepared OpenAL Soft runtime is not executable: ${runtime}" >&2
        exit 1
    fi

    local actual_hash
    actual_hash="$(sha256_file "${source_archive}")"
    if [[ "${actual_hash}" != "${OPENAL_SOFT_ARCHIVE_SHA256}" ]]; then
        echo "OpenAL Soft source archive SHA-256 mismatch: ${actual_hash}" >&2
        exit 1
    fi

    local actual_arches
    actual_arches="$(lipo -archs "${runtime}")"
    if [[ "${actual_arches}" != "${cmake_architecture}" ]]; then
        echo "OpenAL Soft runtime architecture mismatch: expected ${cmake_architecture}, found ${actual_arches}" >&2
        exit 1
    fi

    local actual_install_name
    actual_install_name="$(otool -D "${runtime}" | tail -n 1 | xargs)"
    if [[ "${actual_install_name}" != "${OPENAL_SOFT_INSTALL_NAME}" ]]; then
        echo "OpenAL Soft install name mismatch: expected ${OPENAL_SOFT_INSTALL_NAME}, found ${actual_install_name}" >&2
        exit 1
    fi

    for expected_line in \
        'prefix=${pcfiledir}/../..' \
        'exec_prefix=${prefix}' \
        'libdir=${exec_prefix}/lib' \
        'includedir=${prefix}/include'; do
        if ! grep -Fqx "${expected_line}" "${pkg_config_file}"; then
            echo "OpenAL Soft pkg-config metadata is not relocatable (${expected_line}): ${pkg_config_file}" >&2
            exit 1
        fi
    done
}

if [[ "${verify_only}" -eq 0 ]]; then
    if [[ -e "${output_root}" || -L "${output_root}" ]]; then
        echo "OpenAL Soft output root already exists; remove it or use --verify-only: ${output_root}" >&2
        exit 1
    fi

    work_root="$(mktemp -d "${PROJECT_ROOT}/.tmp/openal-soft-macos-build.XXXXXX")"
    cleanup() {
        rm -rf -- "${work_root}"
    }
    trap cleanup EXIT

    archive_path="${work_root}/openal-soft-${OPENAL_SOFT_VERSION}.tar.gz"
    curl \
        --fail \
        --location \
        --retry 5 \
        --retry-delay 3 \
        --retry-connrefused \
        --connect-timeout 30 \
        --max-time 900 \
        --output "${archive_path}" \
        "${OPENAL_SOFT_ARCHIVE_URL}"
    actual_hash="$(sha256_file "${archive_path}")"
    if [[ "${actual_hash}" != "${OPENAL_SOFT_ARCHIVE_SHA256}" ]]; then
        echo "Downloaded OpenAL Soft SHA-256 mismatch: ${actual_hash}" >&2
        exit 1
    fi

    tar -xzf "${archive_path}" -C "${work_root}"
    source_root="${work_root}/openal-soft-${OPENAL_SOFT_VERSION}"
    if [[ ! -d "${source_root}" ]]; then
        echo "OpenAL Soft archive did not contain the expected source root: ${source_root}" >&2
        exit 1
    fi
    build_root="${work_root}/build"
    prepared_root="${work_root}/prepared"

    cmake \
        -S "${source_root}" \
        -B "${build_root}" \
        -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="${prepared_root}" \
        -DCMAKE_OSX_ARCHITECTURES="${cmake_architecture}" \
        -DCMAKE_OSX_DEPLOYMENT_TARGET="${deployment_target}" \
        -DLIBTYPE=SHARED \
        -DALSOFT_BACKEND_COREAUDIO=ON \
        -DALSOFT_REQUIRE_COREAUDIO=ON \
        -DALSOFT_BACKEND_JACK=OFF \
        -DALSOFT_BACKEND_WAVE=OFF \
        -DALSOFT_EMBED_HRTF_DATA=ON \
        -DALSOFT_EXAMPLES=OFF \
        -DALSOFT_INSTALL_AMBDEC_PRESETS=OFF \
        -DALSOFT_INSTALL_CONFIG=OFF \
        -DALSOFT_INSTALL_EXAMPLES=OFF \
        -DALSOFT_INSTALL_HRTF_DATA=OFF \
        -DALSOFT_INSTALL_UTILS=OFF \
        -DALSOFT_NO_CONFIG_UTIL=ON \
        -DALSOFT_OSX_FRAMEWORK=OFF \
        -DALSOFT_TESTS=OFF \
        -DALSOFT_UPDATE_BUILD_VERSION=OFF \
        -DALSOFT_UTILS=OFF
    cmake --build "${build_root}" --parallel
    cmake --install "${build_root}"

    installed_runtime="${prepared_root}/lib/${OPENAL_SOFT_DYLIB_NAME}"
    if [[ ! -e "${installed_runtime}" ]]; then
        echo "OpenAL Soft build did not install ${OPENAL_SOFT_DYLIB_NAME}." >&2
        exit 1
    fi
    runtime_copy="${work_root}/${OPENAL_SOFT_DYLIB_NAME}"
    cp -L "${installed_runtime}" "${runtime_copy}"
    rm -f "${prepared_root}/lib/libopenal"*.dylib
    mv "${runtime_copy}" "${installed_runtime}"
    install_name_tool -id "${OPENAL_SOFT_INSTALL_NAME}" "${installed_runtime}"
    chmod 0755 "${installed_runtime}"
    cp "${installed_runtime}" "${prepared_root}/lib/libopenal.dylib"

    # CMake expands prefix, libdir, and includedir to the temporary install
    # tree when it configures openal.pc. Make every path-bearing field
    # relocatable before moving the prepared tree so Meson never resolves
    # headers or libraries through the deleted build directory.
    pkg_config_file="${prepared_root}/lib/pkgconfig/openal.pc"
    awk '
        /^prefix=/ { print "prefix=${pcfiledir}/../.."; next }
        /^exec_prefix=/ { print "exec_prefix=${prefix}"; next }
        /^libdir=/ { print "libdir=${exec_prefix}/lib"; next }
        /^includedir=/ { print "includedir=${prefix}/include"; next }
        { print }
    ' "${pkg_config_file}" > "${pkg_config_file}.tmp"
    mv "${pkg_config_file}.tmp" "${pkg_config_file}"

    license_root="${prepared_root}/share/licenses/openal-soft"
    mkdir -p "${license_root}"
    cp "${PROJECT_ROOT}/src/external/openal-soft/COPYING" "${license_root}/COPYING"
    cp "${source_root}/LICENSE-pffft" "${license_root}/LICENSE-pffft"
    cp "${source_root}/fmt-11.2.0/LICENSE" "${license_root}/LICENSE-fmt"
    cp "${source_root}/gsl/LICENSE" "${license_root}/LICENSE-gsl"
    cp "${PROJECT_ROOT}/src/external/openal-soft/SOURCE.md" "${license_root}/SOURCE.md"
    cp "${archive_path}" "${license_root}/openal-soft-${OPENAL_SOFT_VERSION}.tar.gz"

    validate_prepared_root "${prepared_root}"
    mkdir -p "$(dirname "${output_root}")"
    mv "${prepared_root}" "${output_root}"
fi

validate_prepared_root "${output_root}"

if [[ -n "${stage_install_dir}" ]]; then
    framework_root="${stage_install_dir}/Frameworks"
    license_root="${stage_install_dir}/licenses/openal-soft"
    mkdir -p "${framework_root}" "${license_root}"
    cp "${output_root}/lib/${OPENAL_SOFT_DYLIB_NAME}" "${framework_root}/${OPENAL_SOFT_DYLIB_NAME}"
    chmod 0755 "${framework_root}/${OPENAL_SOFT_DYLIB_NAME}"
    for filename in COPYING LICENSE-pffft LICENSE-fmt LICENSE-gsl SOURCE.md "openal-soft-${OPENAL_SOFT_VERSION}.tar.gz"; do
        cp "${output_root}/share/licenses/openal-soft/${filename}" "${license_root}/${filename}"
    done
fi

echo "Prepared OpenAL Soft ${OPENAL_SOFT_VERSION} for macOS ${architecture} at ${output_root}"
