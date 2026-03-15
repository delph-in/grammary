#!/bin/bash

### Script to parse the grammars with ltdb

set -e  # Exit immediately on any error

BUILD="${1:-build}"  # Default to 'build' if not prov

TMPDIR="etc/"

mkdir -p "${TMPDIR}"

LTDBDIR="${TMPDIR}/ltdb"

# Ensure required repositories are available
if [ ! -d "${LTDBDIR}" ]; then
    git clone https://github.com/fcbond/ltdb.git "${LTDBDIR}"
fi

# Ensure ACE binary is available (installs to etc/ltdb/etc/ace-*/)
uv run python "${LTDBDIR}/scripts/setup_ace.py"

get_toml() {
  local file="$1"
  shift
  local key_expr="$*"

  uv run python -c "
import toml, sys
data = toml.load(open('$file', 'r'))
try:
    value = data${key_expr}
    print(value)
except KeyError:
    print('')
"
}



## find METADATA
files=$(find "${BUILD}" -type f -name "METADATA")


for file in $files; do
    echo "Creating ltdb for: $file"
    config_rel=$(get_toml "$file" "['ACE_CONFIG_FILE']")
    if [[ -n "$config_rel" ]]; then
	## only make compatible trees
	uv run python etc/ltdb/scripts/grm2db.py \
	--outdir build/DBS --ace "${file}" || true
    else
	echo "⚠️ Skipping: missing ACE_CONFIG_FILE"
    fi
    echo
done

echo
echo "🚀 Successfully created the following grammars"
find build/DBS -type f -name '*.db' -size +0c -exec du -h {} + | sort -h

echo
echo "🏗️ Copying to etc/ltdb/web/db/"
find build/DBS -type f -name '*.db' -size +0c -exec cp {} etc/ltdb/web/db/ \;
find build/DBS -type f -name '*.dat' -size +0c -exec cp {} etc/ltdb/web/db/ \;
chmod 644 etc/ltdb/web/db/*.db etc/ltdb/web/db/*.dat 2>/dev/null || true
