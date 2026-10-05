#!/usr/bin/env bash
# compile.sh
#
# Full build: download all grammars, run LTDB, set up grew-match, and
# generate the grammar table and summary.
#
# Usage: ./compile.sh [BUILD_DIR]
#   BUILD_DIR  - output directory for downloaded grammars (default: build)

set -euo pipefail

# Paths
VENV_DIR=".venv"
BUILD="${1:-build}"  # build directory, default 'build'
LTDB="etc/ltdb"


# Step 1: Create .venv if missing
if [ ! -d "$VENV_DIR" ]; then
  echo "🔧 Creating virtual environment with uv..."
  if ! command -v uv &> /dev/null; then
    echo "❌ 'uv' is not installed. Please install it: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
  fi
  uv venv "$VENV_DIR" --python 3.13
fi

# Step 2: Install dependencies
echo "📦 Installing requirements..."
uv pip install -r requirements.txt

# Step 3: Download grammars
echo "🚀 Download grammars"

uv run python scripts/download_grammars.py grammary.toml "${BUILD}"

echo "🩹 Overlay local files"

rsync -rv local/ "${BUILD}/"

## Download treebank archives (grammars with a 'trb' key in grammary.toml)
echo "🌲 Download Treebanks"
uv run python scripts/download_grammars.py --treebanks-only grammary.toml "${BUILD}"

# make directory for external software
mkdir -p etc

# Step 4: Compile with ltdb
echo "🚀 Compile with ltdb"

bash scripts/build-ltdb.sh "${BUILD}"

# Overlay grammary-specific grew snippets into the ltdb etc directory.
# The ltdb repo itself ships only generic snippet templates; per-grammar
# HTML and .req files live in grew_snippets/ and are copied here.
echo "🔧 Installing grew-match snippets"
rsync -rv grew_snippets/ "${LTDB}/etc/grew_snippets/"

# Step 5: Set up grew-match and precompile the grew corpora
# (optional: needs grew/dune from opam; skipped with a warning otherwise)
echo "🌲 Setting up grew-match"
if [ -f "${LTDB}/web/db/grew_corpora.json" ]; then
  bash "${LTDB}/scripts/setup-grew-match.sh" "${LTDB}/web/db/grew_corpora.json" \
    || echo "⚠️ grew-match setup failed (see message above); fix and rerun" \
            "${LTDB}/scripts/setup-grew-match.sh ${LTDB}/web/db/grew_corpora.json"
else
  echo "⚠️ No grew corpora exported; skipping grew-match setup"
fi

# Step 6: Generate grammar table and summary
echo "📋 Generating grammar table"
mkdir -p docs
uv run python scripts/generate_table.py \
  --toml grammary.toml \
  --output docs/grammary.md

echo "📋 Generating grammar summary"
uv run python scripts/make_summary.py \
  --db-dir "${BUILD}/DBS" \
  --ltdb-dir "${LTDB}" \
  --tag latest \
  --output docs/summary.md
echo "Summary written to docs/summary.md"

echo "To see the ltdb:"
echo "cd ${LTDB}; HOME_BLURB_FILE=$(pwd)/blurb.md bash run.sh [--grew-match]"
echo
