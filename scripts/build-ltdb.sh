#!/bin/bash

### Script to parse the grammars with ltdb

set -e  # Exit immediately on any error

BUILD="${1:-build}"  # Default to 'build' if not prov

DBS="${BUILD}/DBS"   # compiled grammar databases and grew exports

TMPDIR="etc/"

mkdir -p "${TMPDIR}"

LTDBDIR="${TMPDIR}/ltdb"

WEBDB="${LTDBDIR}/web/db"  # where the LTDB app serves the databases from

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

mkdir -p "${DBS}"

for file in $files; do
    echo "Creating ltdb for: $file"
    config_rel=$(get_toml "$file" "['ACE_CONFIG_FILE']")
    if [[ -n "$config_rel" ]]; then
	## only make compatible trees
	uv run python "${LTDBDIR}/scripts/grm2db.py" \
	--outdir "${DBS}" --ace --doctest --grew "${file}" || true
    else
	echo "⚠️ Skipping: missing ACE_CONFIG_FILE"
    fi
    echo
done

echo
echo "🚀 Successfully created the following grammars"
find "${DBS}" -type f -name '*.db' -size +0c -exec du -h {} + | sort -h

echo "🚀 Successfully compiled the following grammars"
find "${DBS}" -type f -name '*.dat' -size +0c -exec du -h {} + | sort -h

echo
echo "🏗️ Copying to ${WEBDB}/"
mkdir -p "${WEBDB}"
find "${WEBDB}" -maxdepth 1 -type f \( -name '*.db' -o -name '*.dat' \) -delete
find "${DBS}" -type f -name '*.db' -size +0c -exec cp {} "${WEBDB}/" \;
find "${DBS}" -type f -name '*.dat' -size +0c -exec cp {} "${WEBDB}/" \;
chmod 644 "${WEBDB}"/*.db "${WEBDB}"/*.dat 2>/dev/null || true

## Merge the grew exports (grm2db.py --grew) into one corpora description
## read by `run.sh --grew-match`.  Graph paths inside each corpora.json are
## absolute, so the export directories themselves stay in ${DBS}.
grew_exports=("${DBS}"/*-grew/corpora.json)
if [ -f "${grew_exports[0]}" ]; then
    echo "🌲 Merging ${#grew_exports[@]} grew exports" \
	 "into ${WEBDB}/grew_corpora.json"
    uv run python - "${WEBDB}/grew_corpora.json" \
	"${grew_exports[@]}" <<'PY'
import json
import sys

merged_path, *corpora_paths = sys.argv[1:]
corpora = []
for path in corpora_paths:
    with open(path) as f:
        corpora.extend(json.load(f))
with open(merged_path, "w") as f:
    json.dump(corpora, f, indent=2)
PY
fi
