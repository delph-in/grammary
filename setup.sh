#!/usr/bin/env bash
# setup.sh — Install system prerequisites for the Grammary on Ubuntu/Debian
#
# Run once on a fresh machine before running compile.sh.
# Requires sudo for apt-get; the user-level tools (uv, opam) are installed
# under $HOME.
#
# Usage: bash setup.sh [--grew-match]
#   --grew-match  also install opam + grew for structural tree/DMRS search

set -euo pipefail

GREW_MATCH=0
ANALYZERS=0
for arg in "$@"; do
  case "$arg" in
    --grew-match) GREW_MATCH=1 ;;
    --analyzers) ANALYZERS=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

echo "==> Installing system packages"
sudo apt-get update -qq
sudo apt-get install -y \
    git \
    subversion \
    curl \
    wget \
    rsync \
    python3 \
    build-essential

echo
echo "==> Installing uv (Python package manager)"
if command -v uv &>/dev/null; then
  echo "uv already installed: $(uv --version)"
else
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # Make uv available in the current shell session
  export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
fi

echo
echo "==> Checking Python 3.13 availability via uv"
uv python install 3.13 || echo "(uv will fetch Python 3.13 on first compile.sh run)"

if [[ "$GREW_MATCH" -eq 1 ]]; then
  echo
  echo "==> Installing opam (OCaml package manager) for grew-match"
  if command -v opam &>/dev/null || [ -x "$HOME/.local/bin/opam" ]; then
    echo "opam already installed"
  else
    # Official opam installer (does not require sudo)
    curl -fsSL https://opam.ocaml.org/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi

  echo
  echo "==> Initialising opam and creating an OCaml switch"
  opam init --bare --no-setup -y
  # Create a switch for this project if one does not exist
  if ! opam switch list --short | grep -q "^grammary$"; then
    opam switch create grammary 5.2.0
  fi
  eval "$(opam switch grammary --set-switch --shell=sh)"

  echo
  echo "==> Installing grew and dune via opam"
  opam remote add grew "https://opam.grew.fr" --on-switch grammary 2>/dev/null || true
  opam update --switch grammary -q
  opam install -y --switch grammary dune dream dep2pictlib grew

  echo
  echo "grew installed. Run compile.sh to build grammars and set up grew-match."
  echo "Then: cd etc/ltdb && bash run.sh --grew-match"
else
  echo
  echo "Grew-match NOT installed (re-run with --grew-match to add it)."
fi

if [[ "$ANALYZERS" -eq 1 ]]; then
  echo
  echo "==> Installing optional morphological analyzers for the parse demo"
  # Light, easily-installed analyzers used by the LTDB parse-demo hook
  # (etc/ltdb/web/preprocess.py). Heavier ones are documented, not installed.
  echo "  • MeCab (Japanese / Jacy) via apt"
  sudo apt-get install -y mecab mecab-ipadic-utf8 || \
    echo "    (MeCab install failed; install it manually for Jacy)"
  echo "  • jieba (Chinese / Zhong) into the project venv"
  uv pip install jieba || echo "    (jieba install failed; 'uv pip install jieba')"
  echo
  echo "  Heavier analyzers are optional and must be installed by hand:"
  echo "    - FreeLing 4.2 (Spanish / SRG): https://github.com/delph-in/docs/wiki/SrgTop"
  echo "      then set SRG_YY_CMD to a command that prints a YY lattice for a sentence."
  echo "    - KARMA (Kalaallisut / kal-hpsg): https://github.com/alexhsu-nlp/karma"
  echo "      then set KARMA_CMD (and KARMA_MODE=yy|segment)."
  echo "  The demo degrades gracefully: a grammar whose analyzer is absent still"
  echo "  parses already-segmented input."
else
  echo
  echo "Morphological analyzers NOT installed (re-run with --analyzers to add the"
  echo "light ones: MeCab for Japanese, jieba for Chinese)."
fi

echo
echo "==> Setup complete. Next step:"
echo "    bash compile.sh"
echo
echo "Notes:"
echo "  • ACE (grammar compiler) is downloaded automatically by compile.sh"
echo "  • subversion is required for the gg (German) and hag (Hausa) grammars"
echo "  • grew-match is optional; see etc/ltdb/doc/grew-match.md for details"
echo "  • morphological analyzers for the parse demo are optional; see the"
echo "    'Morphological analyzers' section of README.md (--analyzers installs"
echo "    the light ones: MeCab, jieba)"
