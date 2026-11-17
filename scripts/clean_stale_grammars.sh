#!/usr/bin/env bash
# clean_stale_grammars.sh
#
# Offer to delete local files of superseded grammar versions (e.g.
# Norsyg_2602.* once Norsyg_2608 has been built). "Current" is the newest
# .db of each SHORT_GRAMMAR_NAME in BUILD_DBS; see stale_grammar_files.py.
# Lists the stale .db/.dat/.log files and -grew export directories and asks
# before deleting. Without a terminal it only lists them.
#
# Usage: bash scripts/clean_stale_grammars.sh [--refresh-derived] \
#            BUILD_DBS [DIR ...]
#   --refresh-derived  after a deletion, re-merge the grew corpora into
#                      etc/ltdb/web/db/grew_corpora.json and point out that
#                      docs/summary.md needs regenerating (for use outside
#                      the build, which does both itself afterwards)
#   BUILD_DBS          build output directory that defines the current
#                      versions; also scanned
#   DIR                further directories to scan (e.g. etc/ltdb/web/db)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LTDB_DIR="$REPO_ROOT/etc/ltdb"

refresh_derived=0
if [[ "${1:-}" == "--refresh-derived" ]]; then
  refresh_derived=1
  shift
fi
if [[ $# -lt 1 ]]; then
  echo "Usage: bash scripts/clean_stale_grammars.sh [--refresh-derived]" \
    "BUILD_DBS [DIR ...]" >&2
  exit 1
fi
build_dbs="$1"
if [[ ! -d "$build_dbs" ]]; then
  echo "==> No $build_dbs; skipping the stale-version check."
  exit 0
fi

echo "==> Checking for stale local grammar versions ..."
mapfile -t stale < <(python3 "$REPO_ROOT/scripts/stale_grammar_files.py" \
  --newest-in "$build_dbs" "$@")
if (( ${#stale[@]} == 0 )); then
  echo "    none found."
  exit 0
fi

printf '    %s\n' "${stale[@]}"
reply=n
if [[ -t 0 ]]; then
  read -r -p "    Delete these ${#stale[@]} stale items? [y/N] " reply
else
  echo "    (not a terminal: leaving them in place)"
fi
if [[ "$reply" != [yY]* ]]; then
  echo "    kept."
  exit 0
fi

removed_grew=0
for item in "${stale[@]}"; do
  [[ "$item" == *-grew ]] && removed_grew=1
  rm -rf -- "$item"
done
echo "    deleted."

if (( refresh_derived )); then
  echo "    Regenerate docs/summary.md if it listed them"
  echo "    (scripts/make_summary.py; see compile.sh step 6)."
  # the merged description would otherwise still name the removed export
  if (( removed_grew )) \
      && compgen -G "$build_dbs/*-grew/corpora.json" >/dev/null; then
    echo "    Re-merging grew corpora ..."
    uv run python "$LTDB_DIR/scripts/merge_grew_corpora.py" \
      "$LTDB_DIR/web/db/grew_corpora.json" "$build_dbs"/*-grew/corpora.json
  fi
fi
