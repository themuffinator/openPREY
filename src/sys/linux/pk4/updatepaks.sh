#!/bin/sh
set -eu

usage() {
    echo "usage: $0 <current-pk4-dir> <expanded-source-dir> <new-pk4>" >&2
}

if [ "$#" -ne 3 ]; then
    usage
    exit 2
fi

current_pak_dir=$1
expanded_source_dir=$2
new_pak=$3

if [ ! -d "$current_pak_dir" ]; then
    echo "error: current PK4 directory not found: $current_pak_dir" >&2
    exit 1
fi
if [ ! -d "$expanded_source_dir" ]; then
    echo "error: expanded source directory not found: $expanded_source_dir" >&2
    exit 1
fi
if ! command -v unzip >/dev/null 2>&1; then
    echo "error: unzip is required" >&2
    exit 1
fi
if ! command -v zip >/dev/null 2>&1; then
    echo "error: zip is required" >&2
    exit 1
fi

tmpdir=$(mktemp -d "${TMPDIR:-/tmp}/openq4-updatepaks.XXXXXX")
cleanup() {
    rm -rf "$tmpdir"
}
trap cleanup EXIT HUP INT TERM

echo "current pak files:       $current_pak_dir"
echo "expanded updated source: $expanded_source_dir"
echo "new pak file:            $new_pak"
if [ "${OPENQ4_UPDATEPAKS_ASSUME_YES:-0}" != "1" ]; then
    printf "press enter to continue, or Ctrl-C to abort"
    read _answer
fi

find "$current_pak_dir" -maxdepth 1 -type f -name '*.pk4' -print | sort | while IFS= read -r pak; do
    unzip -Z1 "$pak" > "$tmpdir/$(basename "$pak").log"
done

if ! find "$tmpdir" -maxdepth 1 -type f -name '*.log' | grep -q .; then
    echo "error: no PK4 files found in $current_pak_dir" >&2
    exit 1
fi

cat "$tmpdir"/*.log | sort -u > "$tmpdir/sorted-unique.log"

(
    cd "$expanded_source_dir"
    rm -f -- "$new_pak"
    zip -b "$tmpdir" "$new_pak" -@ < "$tmpdir/sorted-unique.log" >/dev/null
    md5sum "$new_pak"
)

echo "done."
