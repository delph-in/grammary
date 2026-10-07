#!/usr/bin/env bash
# install_freeling.sh
#
# Install FreeLing 4.2 (the external morphological analyzer the Spanish Resource
# Grammar relies on) on Ubuntu/Debian, then print how to wire it into the LTDB
# parse demo via SRG_YY_CMD.
#
# FreeLing provides per-distro .deb packages at
#   https://github.com/TALP-UPC/FreeLing/releases/tag/4.2
# This script detects the OS codename, downloads the matching package plus the
# language-data package, and installs them with apt (which resolves deps).
#
# Usage: bash scripts/install_freeling.sh
#
# Environment overrides:
#   FREELING_DEB_URL   full URL to a freeling .deb (skip codename detection)
#   FREELING_LANGS_URL full URL to the freeling-langs .deb

set -euo pipefail

BASE_URL="https://github.com/TALP-UPC/FreeLing/releases/download/4.2"

command -v sudo >/dev/null 2>&1 || {
  echo "Error: sudo is required to install system packages" >&2
  exit 1
}

# --- detect OS codename ----------------------------------------------------
codename=""
if command -v lsb_release >/dev/null 2>&1; then
  codename="$(lsb_release -cs 2>/dev/null || true)"
fi
if [[ -z "$codename" && -r /etc/os-release ]]; then
  # shellcheck disable=SC1091
  codename="$(. /etc/os-release && echo "${VERSION_CODENAME:-}")"
fi
echo "==> Detected OS codename: ${codename:-unknown}"

# --- map codename -> release asset (per the 4.2 release page) --------------
# Unknown/newer releases fall back to the jammy build as a best effort.
case "$codename" in
  jammy)    deb="freeling-4.2.1-jammy-amd64.deb" ;;
  focal)    deb="freeling-4.2-focal-amd64.deb" ;;
  bionic)   deb="freeling-4.2-bionic-amd64.deb" ;;
  bullseye) deb="freeling-4.2.1-bullseye-amd64.deb" ;;
  buster)   deb="freeling-4.2-buster-amd64.deb" ;;
  *)
    deb="freeling-4.2.1-jammy-amd64.deb"
    echo "⚠️  No FreeLing 4.2 package is published for '${codename:-unknown}';" \
         "trying the jammy (22.04) build. If it fails, build from source" \
         "(FreeLing-src-4.2.tar.gz) or set FREELING_DEB_URL."
    ;;
esac

deb_url="${FREELING_DEB_URL:-$BASE_URL/$deb}"
langs_url="${FREELING_LANGS_URL:-$BASE_URL/freeling-langs-4.2.1.deb}"

# --- download + install ----------------------------------------------------
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

echo "==> Downloading FreeLing package"
echo "    $deb_url"
wget -q -O "$tmpdir/freeling.deb" "$deb_url" || {
  echo "Error: failed to download $deb_url" >&2
  echo "       Pick the right asset from $BASE_URL and set FREELING_DEB_URL." >&2
  exit 1
}

echo "==> Downloading FreeLing language data"
if ! wget -q -O "$tmpdir/freeling-langs.deb" "$langs_url"; then
  echo "⚠️  Could not download langs package ($langs_url); the main package may" \
       "already include Spanish data. Continuing."
  rm -f "$tmpdir/freeling-langs.deb"
fi

echo "==> Installing with apt (resolves dependencies)"
sudo apt-get update -qq
debs=("$tmpdir/freeling.deb")
[[ -f "$tmpdir/freeling-langs.deb" ]] && debs+=("$tmpdir/freeling-langs.deb")
sudo apt-get install -y "${debs[@]}"

# --- verify ----------------------------------------------------------------
echo
if command -v analyze >/dev/null 2>&1; then
  echo "✓ FreeLing installed: $(command -v analyze)"
else
  echo "⚠️  'analyze' not found on PATH after install; check the package." >&2
fi

# --- wiring guidance -------------------------------------------------------
srg_yy="build/srg/util/analyze-wrappers/srg-yy.sh"
cat <<EOF

==> Next: point the SRG analyzer at FreeLing

The Spanish Resource Grammar ships a FreeLing->YY wrapper:
    $srg_yy
It reads one sentence per line on stdin and prints DELPH-IN YY tokens, which
the LTDB parse demo feeds to ACE with '-y --yy-rules'. Enable it by exporting:

    export FREELINGDIR=/usr
    export SRG_YY_CMD="bash \$(pwd)/$srg_yy"

(Downloaded grammars live under build/, so run the export from the repo root
after compile.sh, or use an absolute path to the wrapper.)

Quick check:
    echo "el perro ladra" | bash $srg_yy

Then restart the LTDB server; the SRG parse demo will analyze raw Spanish.
EOF
