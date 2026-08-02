#!/bin/sh
set -eu

adapter_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$adapter_dir/../../.." && pwd)
python_runner=${HARBOR_PYTHON:-python}
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

cd "$repo_root"
eval "$python_runner \"$adapter_dir/generate.py\" \"$tmp_dir/manifest.json\""
cmp "$tmp_dir/manifest.json" "$adapter_dir/generated/manifest.json"
