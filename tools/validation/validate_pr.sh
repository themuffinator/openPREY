#!/usr/bin/env bash
set -euo pipefail

case "${BASH_SOURCE[0]}" in
    */*) script_dir="${BASH_SOURCE[0]%/*}" ;;
    *) script_dir=. ;;
esac
script_dir="$(CDPATH= cd "${script_dir}" && pwd)"
runner="${script_dir}/openq4_validate.py"

python_cmd=""
if command -v python3 >/dev/null 2>&1; then
    python_cmd="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    python_cmd="$(command -v python)"
else
    echo "Python was not found. Install Python or ensure it is available on PATH." >&2
    exit 1
fi

exec "${python_cmd}" "${runner}" pr "$@"
