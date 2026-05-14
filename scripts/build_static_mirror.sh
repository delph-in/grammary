#!/usr/bin/env bash
# Build the static LTDB mirror to a local directory for testing.
#
# Usage:
#   scripts/build_static_mirror.sh [--output DIR] [--db-dir DIR] [--no-gzip]
#
# Defaults:
#   --output   test-output/
#   --db-dir   build/DBS/          (compiled grammar databases)
#   --gzip     on (required for ERG which exceeds GitHub's 100 MB file limit)
#
# After building, serve locally with:
#   python -m http.server -d test-output/ltdb 8000
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT="$REPO_ROOT/test-output"
DB_DIR="$REPO_ROOT/build/DBS"
GZIP_FLAG="--gzip"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)   OUTPUT="$2"; shift 2 ;;
    --db-dir)   DB_DIR="$2"; shift 2 ;;
    --no-gzip)  GZIP_FLAG="--no-gzip"; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ ! -d "$DB_DIR" ]]; then
  echo "DB directory not found: $DB_DIR" >&2
  echo "Run compile.sh first, or pass --db-dir to point at compiled .db files." >&2
  exit 1
fi

echo "==> Output: $OUTPUT"
echo "==> DB source: $DB_DIR"
echo ""

# Step 1: Freeze static HTML pages
echo "[1/3] Freezing HTML pages..."
cd "$REPO_ROOT/etc/ltdb"
uv run python "$REPO_ROOT/scripts/freeze_ltdb.py" \
  --db-dir "$DB_DIR" \
  --destination "$OUTPUT"
cd "$REPO_ROOT"

# Step 2: Build example databases
echo ""
echo "[2/3] Building example databases..."
uv run python scripts/build_ltdb_example_dbs.py \
  --db-dir "$DB_DIR" \
  --output-dir "$OUTPUT/ltdb/db" \
  $GZIP_FLAG

# Step 3: Build type (grammar metadata) databases
echo ""
echo "[3/3] Building type databases..."
uv run python scripts/build_ltdb_type_dbs.py \
  --db-dir "$DB_DIR" \
  --output-dir "$OUTPUT/ltdb/db" \
  $GZIP_FLAG

echo ""
echo "Done. Test locally:"
echo "  python -m http.server -d $OUTPUT/ltdb 8000"
echo ""
echo "Then open: http://localhost:8000/"
