#!/usr/bin/env bash

set -e  # Exit on error

# Paths
VENV_DIR=".venv"
BUILD="build"


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

rsync -rv local/ build/

## Download the treebank for SRG
echo "🌲 Download Treebanks"
#bash scripts/add-treebanks.sh

# make directory for external software
mkdir -p etc

# Step 4: Compile with ltdb
echo "🚀 Compile with ltdb"

bash scripts/build-ltdb.sh "${BUILD}"

# Step 5: Set up grew-match and precompile the grew corpora
# (optional: needs grew/dune from opam; skipped with a warning otherwise)
echo "🌲 Setting up grew-match"
if [ -f etc/ltdb/web/db/grew_corpora.json ]; then
  bash etc/ltdb/scripts/setup-grew-match.sh etc/ltdb/web/db/grew_corpora.json \
    || echo "⚠️ grew-match setup failed (see message above); fix and rerun" \
            "etc/ltdb/scripts/setup-grew-match.sh etc/ltdb/web/db/grew_corpora.json"
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
  --db-dir build/DBS \
  --ltdb-dir etc/ltdb \
  --tag latest \
  --output docs/summary.md
echo "Summary written to docs/summary.md"

echo "To see the ltdb:"
echo "cd etc/ltdb; bash deploy.sh"
echo
