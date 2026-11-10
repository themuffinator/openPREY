#!/usr/bin/env bash
set -euo pipefail

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
    echo "This asset script must run inside macOS." >&2
    exit 1
fi

GUEST_HOME="$(require_guest_home)"
export HOME="${GUEST_HOME}"

expand_guest_path() {
    case "$1" in
        "~")
            printf '%s\n' "${GUEST_HOME}"
            ;;
        "~/"*)
            printf '%s/%s\n' "${GUEST_HOME}" "${1#~/}"
            ;;
        *)
            printf '%s\n' "$1"
            ;;
    esac
}

basepath="$(expand_guest_path "${OPENQ4_BASEPATH:-${GUEST_HOME}/openq4-work/Quake4}")"
archive="${OPENQ4_Q4_TAR:-}"
workspace="$(expand_guest_path "${OPENQ4_GUEST_WORKSPACE:-${GUEST_HOME}/openq4-work}")"
incoming="${workspace}/incoming-quake4"

reject_unsafe_tar_entries() {
    local tar_path="$1"
    python3 - "${tar_path}" <<'PY'
import pathlib
import sys
import tarfile
import unicodedata

archive_path = pathlib.Path(sys.argv[1])
forbidden_metadata_names = {
    ".ds_store",
    "__macosx",
    ".fseventsd",
    ".spotlight-v100",
    ".trashes",
    "icon\r",
}
seen_entries = set()
seen_casefold_entries = {}


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def is_macos_metadata_path(parts):
    for part in parts:
        normalized = part.casefold()
        if normalized in forbidden_metadata_names:
            return True
        if normalized.startswith("._") or normalized.endswith(".dsym"):
            return True
    return False


try:
    with tarfile.open(archive_path, "r:*") as archive:
        for member in archive.getmembers():
            raw_entry = member.name
            entry = raw_entry.rstrip("/") if member.isdir() else raw_entry
            parts = entry.split("/")
            if (
                entry in {"", ".", ".."}
                or entry.startswith(("./", "/", "../"))
                or "\\" in entry
                or any(ord(character) < 32 or ord(character) == 127 for character in entry)
                or "/../" in f"/{entry}/"
                or "" in parts
                or any(part in {".", ".."} for part in parts)
            ):
                fail(f"Unsafe asset archive path: {entry!r}")
            if not (member.isfile() or member.isdir()):
                fail(f"Asset archive contains a symlink or special file (including hardlinks): {entry}")
            if is_macos_metadata_path(parts):
                fail(f"Asset archive contains non-runtime macOS metadata/debug entry: {entry}")
            if entry in seen_entries:
                fail(f"Asset archive contains duplicate member: {entry}")
            casefold_entry = unicodedata.normalize("NFC", entry).casefold()
            previous = seen_casefold_entries.get(casefold_entry)
            if previous is not None and previous != entry:
                fail(f"Asset archive contains case-insensitive duplicate entries: {previous}, {entry}")
            seen_entries.add(entry)
            seen_casefold_entries[casefold_entry] = entry
except tarfile.TarError as exc:
    fail(f"Unable to inspect asset archive: {archive_path}: {exc}")
PY

    COPYFILE_DISABLE=1 tar -tf "${tar_path}" | while IFS= read -r entry; do
        case "${entry}" in
            ""|"."|".."|./*|*/./*|*//*|/*|../*|*/../*|*/..|*\\*)
                echo "Unsafe asset archive path: ${entry}" >&2
                exit 1
                ;;
        esac
    done

    COPYFILE_DISABLE=1 tar -tvf "${tar_path}" | while IFS= read -r listing; do
        entry_type="${listing:0:1}"
        case "${entry_type}" in
            -|d)
                ;;
            *)
                echo "Asset archive contains a symlink or special file (including hardlinks): ${listing}" >&2
                exit 1
                ;;
        esac
    done
}

reject_unsafe_tree_entries() {
    local tree="$1"
    local bad_entry
    bad_entry="$(find "${tree}" \( -type l -o \( ! -type f -a ! -type d \) \) -print -quit)"
    if [[ -n "${bad_entry}" ]]; then
        echo "Asset archive contains a symlink or special file: ${bad_entry}" >&2
        exit 1
    fi
}

find_case_insensitive_path_collision() {
    local tree="$1"
    python3 - "${tree}" <<'PY'
import pathlib
import sys
import unicodedata

root = pathlib.Path(sys.argv[1])
seen = {}
for path in sorted(root.rglob("*")):
    rel = path.relative_to(root).as_posix()
    key = unicodedata.normalize("NFC", rel).casefold()
    previous = seen.get(key)
    if previous is not None and previous != rel:
        print(previous)
        print(rel)
        raise SystemExit(0)
    seen[key] = rel
PY
}

reject_case_insensitive_tree_collisions() {
    local tree="$1"
    local label="$2"
    local case_collision
    case_collision="$(find_case_insensitive_path_collision "${tree}")"
    if [[ -n "${case_collision}" ]]; then
        echo "${label} contains a case-insensitive path collision:" >&2
        printf '%s\n' "${case_collision}" >&2
        exit 1
    fi
}

reject_macos_non_runtime_metadata_entries() {
    local tree="$1"
    local label="$2"
    local bad_entry
    bad_entry="$(find "${tree}" \( -iname '.DS_Store' -o -name '._*' -o -iname '__MACOSX' -o -iname '.fseventsd' -o -iname '.Spotlight-V100' -o -iname '.Trashes' -o -name $'Icon\r' -o -iname '*.dSYM' \) -print -quit)"
    if [[ -n "${bad_entry}" ]]; then
        echo "${label} contains non-runtime macOS metadata/debug entry: ${bad_entry}" >&2
        exit 1
    fi
}

require_safe_asset_roots() {
    python3 - "${workspace}" "${basepath}" "${GUEST_HOME}" <<'PY'
import pathlib
import sys
import unicodedata

workspace_raw = sys.argv[1]
basepath_raw = sys.argv[2]
guest_home_raw = sys.argv[3]
workspace = pathlib.Path(workspace_raw).expanduser()
basepath = pathlib.Path(basepath_raw).expanduser()
home = pathlib.Path(guest_home_raw).resolve()
root = pathlib.Path("/")


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def require_absolute_after_expansion(label: str, raw_value: str, path: pathlib.Path) -> None:
    path_text = raw_value
    if any(ord(character) < 32 or ord(character) == 127 for character in path_text):
        fail(f"{label} must not contain control characters: {path_text!r}")
    if "\\" in path_text:
        fail(f"{label} must be a POSIX path without backslashes: {path_text}")
    if not path.is_absolute():
        fail(f"{label} must be an absolute path after ~ expansion: {path_text}")
    segments = path_text.strip("/").split("/") if path_text.strip("/") else []
    if any(segment in {"", ".", ".."} for segment in segments):
        fail(f"{label} must not contain dot or empty path segments: {path_text}")


def resolve(label: str, raw_value: str, path: pathlib.Path) -> pathlib.Path:
    require_absolute_after_expansion(label, raw_value, path)
    if str(path) in {"", ".", ".."}:
        fail(f"{label} must be an explicit directory path: {path}")
    if path.is_symlink():
        fail(f"{label} must not be a symlink: {path}")
    try:
        resolved = path.resolve(strict=False)
    except OSError as exc:
        fail(f"{label} could not be resolved safely: {path}: {exc}")
    if resolved in {root, home}:
        fail(f"{label} must not be the filesystem root or home directory: {resolved}")
    return resolved


def path_key(path: pathlib.Path) -> str:
    return unicodedata.normalize("NFC", path.as_posix().rstrip("/")).casefold()


def path_is_same_or_under(candidate: pathlib.Path, parent: pathlib.Path) -> bool:
    candidate_key = path_key(candidate)
    parent_key = path_key(parent)
    return candidate_key == parent_key or candidate_key.startswith(f"{parent_key}/")


def require_basepath_outside_reserved_workspace_children() -> None:
    reserved_children = ("openQ4", "openQ4-game", "incoming-quake4", "results")
    for child in reserved_children:
        reserved = workspace_resolved / child
        if path_key(basepath_resolved) == path_key(reserved):
            fail(
                "Asset install basepath must not target a reserved workflow directory "
                f"({child}); rsync --delete would remove workflow files."
            )
        if path_is_same_or_under(basepath_resolved, reserved):
            fail(
                "Asset install basepath must not live under a reserved workflow directory "
                f"({child}); rsync --delete would remove workflow files."
            )


workspace_resolved = resolve("OPENQ4_GUEST_WORKSPACE", workspace_raw, workspace)
basepath_resolved = resolve("OPENQ4_BASEPATH", basepath_raw, basepath)
if basepath_resolved == workspace_resolved:
    fail("Asset install basepath must not be the same as the workflow workspace; rsync --delete would remove workflow files.")
try:
    workspace_resolved.relative_to(basepath_resolved)
except ValueError:
    pass
else:
    fail("Asset install basepath must not contain the workflow workspace; rsync --delete would remove workflow files.")
require_basepath_outside_reserved_workspace_children()
PY
}

if contains_control_chars "${archive}"; then
    echo "OPENQ4_Q4_TAR must not contain control characters." >&2
    exit 1
fi
if [[ -z "${archive}" || ! -f "${archive}" ]]; then
    echo "OPENQ4_Q4_TAR must point to a Quake 4 asset tar copied to the macOS VM." >&2
    exit 1
fi
if [[ -L "${archive}" ]]; then
    echo "OPENQ4_Q4_TAR must not be a symlink: ${archive}" >&2
    exit 1
fi

require_safe_asset_roots

rm -rf "${incoming}"
mkdir -p "${incoming}" "${basepath}"

echo "Extracting Quake 4 asset archive: ${archive}"
reject_unsafe_tar_entries "${archive}"
COPYFILE_DISABLE=1 tar -xf "${archive}" -C "${incoming}"
reject_unsafe_tree_entries "${incoming}"
reject_macos_non_runtime_metadata_entries "${incoming}" "Asset archive"
reject_case_insensitive_tree_collisions "${incoming}" "Asset archive"

q4base_dirs=()
while IFS= read -r q4base_candidate; do
    q4base_dirs+=("${q4base_candidate}")
done < <(find "${incoming}" -maxdepth 3 -type d -name q4base)

if [[ "${#q4base_dirs[@]}" -eq 0 ]]; then
    echo "Archive did not contain a q4base directory." >&2
    exit 1
fi
if [[ "${#q4base_dirs[@]}" -ne 1 ]]; then
    echo "Archive contained multiple q4base directories; refusing ambiguous asset install." >&2
    printf '  - %s\n' "${q4base_dirs[@]}" >&2
    exit 1
fi

q4base_dir="${q4base_dirs[0]}"
source_root="$(dirname "${q4base_dir}")"
echo "Installing Quake 4 assets from ${source_root} to ${basepath}"
rsync -a --delete \
    --exclude '/.tmp/' \
    --exclude '/CrashReports/' \
    --exclude '/q4base/generated/' \
    --exclude '/q4base/*.cfg' \
    --exclude '/q4base/*.log' \
    --exclude '/q4base/q4key' \
    --exclude '/q4base/quake4key' \
    --exclude '/q4base/savegames/' \
    --exclude '/q4base/screenshots/' \
    --exclude '/q4mp/*.cfg' \
    --exclude '/q4mp/*.log' \
    --exclude '/q4mp/screenshots/' \
    "${source_root}/" "${basepath}/"

if [[ ! -d "${basepath}/q4base" ]]; then
    echo "Installed asset directory is missing q4base: ${basepath}" >&2
    exit 1
fi
reject_unsafe_tree_entries "${basepath}"
reject_macos_non_runtime_metadata_entries "${basepath}" "Installed Quake 4 asset tree"
reject_case_insensitive_tree_collisions "${basepath}" "Installed Quake 4 asset tree"

pk4_count="$(find "${basepath}/q4base" -maxdepth 1 -type f \( -name '*.pk4' -o -name '*.PK4' \) | wc -l | tr -d '[:space:]')"
if [[ "${pk4_count}" == "0" ]]; then
    echo "Installed asset directory has no q4base PK4 files: ${basepath}/q4base" >&2
    exit 1
fi
echo "Installed Quake 4 asset PK4 count: ${pk4_count}"

echo "Quake 4 asset install complete: ${basepath}"
du -sh "${basepath}" || true

case "${archive}" in
    /tmp/openq4-macos-*/*)
        rm -f "${archive}"
        ;;
esac
