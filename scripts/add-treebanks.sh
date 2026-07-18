#!/usr/bin/env bash
# add-treebanks.sh
#
# Legacy script: manually download and link the SRG treebank.
# Superseded by the 'trb' key in grammary.toml handled by
# scripts/download_grammars.py.  Kept for reference.
#
# Usage: bash scripts/add-treebanks.sh

set -euo pipefail

echo "⚠️  This script is superseded by scripts/download_grammars.py."
echo "    Run: uv run python scripts/download_grammars.py grammary.toml build"
echo "    The 'trb' key in grammary.toml handles treebank downloads."
exit 0
