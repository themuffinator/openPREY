#!/usr/bin/env bash
set -euo pipefail

action="${1:-build}"
workspace="${OPENQ4_GUEST_WORKSPACE:-${HOME}/openq4-work}"
repo="${workspace}/openQ4"
host_repo="${OPENQ4_HOST_REPO_SHARE:-/mnt/hgfs/openQ4}"
basepath="${OPENQ4_BASEPATH:-}"
stamp="$(date +%Y%m%d-%H%M%S)"
results_root="${workspace}/results"
run_dir="${results_root}/${stamp}-${action}"

if [[ -x "${HOME}/.local/bin/meson" ]]; then
    export PATH="${HOME}/.local/bin:${PATH}"
    export OPENQ4_MESON="${OPENQ4_MESON:-${HOME}/.local/bin/meson}"
fi

mkdir -p "${run_dir}"
exec > >(tee -a "${run_dir}/openq4-linux-mint-workflow.log") 2>&1

sync_tree() {
    local source_dir="$1"
    local target_dir="$2"
    shift 2

    if [[ ! -d "${source_dir}" ]]; then
        echo "Missing source share: ${source_dir}" >&2
        exit 1
    fi

    mkdir -p "${target_dir}"
    rsync -a --delete --delete-excluded "$@" "${source_dir}/" "${target_dir}/"
}

sync_sources() {
    echo "Syncing openQ4 from ${host_repo} to ${repo}"
    sync_tree "${host_repo}" "${repo}" \
        --exclude '/.home/' \
        --exclude '/.install/' \
        --exclude '/.tmp/' \
        --exclude '/.voice_eng/' \
        --exclude '/builddir*/' \
        --exclude '/tmp-game-libs/'

}

build_openq4() {
    cd "${repo}"

    local buildtype="${OPENQ4_BUILDTYPE:-debug}"
    local builddir="${OPENQ4_BUILDDIR:-builddir}"
    local platform_backend="${OPENQ4_PLATFORM_BACKEND:-sdl3}"

    echo "Configuring openQ4 (${buildtype}, backend=${platform_backend})"
    bash tools/build/meson_setup.sh setup --wipe "${builddir}" . \
        --backend ninja \
        --buildtype="${buildtype}" \
        --wrap-mode=forcefallback \
        "-Dplatform_backend=${platform_backend}"

    echo "Compiling openQ4"
    bash tools/build/meson_setup.sh compile -C "${builddir}"

    echo "Staging openQ4 into .install"
    bash tools/build/meson_setup.sh install -C "${builddir}" --no-rebuild --skip-subprojects
}

run_smoke() {
    cd "${repo}"

    resolve_basepath

    if [[ ! -x ".install/openQ4-client_x64" ]]; then
        echo "Missing staged Linux client: ${repo}/.install/openQ4-client_x64" >&2
        echo "Run the build action first." >&2
        exit 1
    fi

    if [[ ! -d "${basepath}/q4base" ]]; then
        echo "Missing Quake 4 asset basepath: ${basepath}" >&2
        echo "Expected ${basepath}/q4base. Update OPENQ4_BASEPATH or the VMware Quake4 shared folder." >&2
        exit 1
    fi

    local uid_value
    uid_value="$(id -u)"
    export DISPLAY="${DISPLAY:-:0}"
    export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/${uid_value}}"

    echo "Running openQ4 renderer smoke on DISPLAY=${DISPLAY}"
    python3 tools/tests/renderer_gameplay_benchmark.py \
        --profile smoke \
        --limit "${OPENQ4_SMOKE_LIMIT:-1}" \
        --settle-frames "${OPENQ4_SMOKE_SETTLE_FRAMES:-10}" \
        --sample-frames "${OPENQ4_SMOKE_SAMPLE_FRAMES:-10}" \
        --timeout "${OPENQ4_SMOKE_TIMEOUT:-300}" \
        --output-dir "${run_dir}/renderer-smoke" \
        --basepath "${basepath}"
}

resolve_basepath() {
    if [[ -n "${basepath}" ]]; then
        return
    fi

    if [[ -d "/mnt/openq4-data/Quake4/q4base" ]]; then
        basepath="/mnt/openq4-data/Quake4"
    else
        basepath="/mnt/hgfs/Quake4"
    fi
}

install_desktop_launcher() {
    cd "${repo}"
    resolve_basepath

    if [[ ! -d ".install" ]]; then
        echo "Missing staged openQ4 runtime: ${repo}/.install" >&2
        echo "Run the build action first." >&2
        exit 1
    fi

    local launcher_args=(
        --install-root "${repo}/.install"
    )
    if [[ -n "${basepath}" ]]; then
        launcher_args+=(--basepath "${basepath}")
    fi

    echo "Installing openQ4 desktop launcher"
    bash tools/linux/install_desktop_launcher.sh "${launcher_args[@]}"
}

publish_results() {
    local host_results="${OPENQ4_HOST_RESULTS_DIR:-${host_repo}/.tmp/vmware-linux-mint-results}/${stamp}-${action}"
    if mkdir -p "${host_results}" >/dev/null 2>&1; then
        rsync -a "${run_dir}/" "${host_results}/" || true
        echo "Copied workflow results to host: ${host_results}"
    else
        echo "Host result copy skipped; ${host_results} is not writable."
    fi
}

case "${action}" in
    sync)
        sync_sources
        ;;
    build)
        sync_sources
        build_openq4
        ;;
    smoke)
        run_smoke
        ;;
    launcher)
        sync_sources
        install_desktop_launcher
        ;;
    all)
        sync_sources
        build_openq4
        run_smoke
        install_desktop_launcher
        ;;
    *)
        echo "Unknown action '${action}'. Expected sync, build, smoke, launcher, or all." >&2
        exit 2
        ;;
esac

publish_results
echo "openQ4 Linux Mint workflow '${action}' complete. Guest results: ${run_dir}"
