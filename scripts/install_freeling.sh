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
#   FREELING_DEB_URL     full URL to a freeling .deb (skip codename detection)
#   FREELING_LANGS_URL   full URL to the freeling-langs .deb
#   FREELING_ICU70_URL   full URL to a libicu70 .deb (for distros, e.g. Ubuntu
#                        24.04 "noble", whose repos only ship a newer libicu
#                        and can't satisfy the jammy-built package's deps)

set -euo pipefail

BASE_URL="https://github.com/TALP-UPC/FreeLing/releases/download/4.2"
# Jammy's libicu70 installs side by side with newer libicu majors (versioned
# .so names, no Conflicts/Breaks against them), so fetching it from the
# archive is a safe way to satisfy FreeLing's dependency on distros that no
# longer ship it.
ICU70_URL="http://archive.ubuntu.com/ubuntu/pool/main/i/icu/libicu70_70.1-2ubuntu1_amd64.deb"

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

# The jammy-built package depends on libicu70, which newer Ubuntu releases
# (e.g. 24.04 "noble") no longer carry in their repos. Fetch it from the
# archive ourselves rather than let apt fail on the unmet dependency.
if ! apt-cache policy libicu70 2>/dev/null | grep -q 'Candidate: [^(]'; then
  icu70_url="${FREELING_ICU70_URL:-$ICU70_URL}"
  echo "==> libicu70 not available via apt; downloading it directly"
  echo "    $icu70_url"
  wget -q -O "$tmpdir/libicu70.deb" "$icu70_url" || {
    echo "Error: failed to download $icu70_url" >&2
    echo "       Set FREELING_ICU70_URL to a libicu70 .deb for your arch." >&2
    exit 1
  }
fi

debs=("$tmpdir/freeling.deb")
[[ -f "$tmpdir/libicu70.deb" ]] && debs+=("$tmpdir/libicu70.deb")
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
# The SRG's own wrapper (build/srg/util/analyze-wrappers/srg-yy.sh) goes
# through FreeLing's Python bindings, which need an exact Python ABI match
# and a libfreeling.so built against the same boost_regex/ICU as the host --
# neither holds on Ubuntu 24.04+. scripts/srg_freeling_yy.py gets the same
# analysis through the plain `analyze` CLI instead, reusing the SRG's own
# (unmodified) tag-override logic.
srg_yy="scripts/srg_freeling_yy.py"
cat <<EOF

==> Next: point the SRG analyzer at FreeLing

$srg_yy reads one sentence on stdin and prints a DELPH-IN YY lattice line,
which the LTDB parse demo feeds to ACE with '-y --yy-rules'. Enable it by
exporting:

    export FREELINGDIR=/usr
    export SRG_YY_CMD="python3 \$(pwd)/$srg_yy"

(Downloaded grammars live under build/, and $srg_yy imports modules straight
from the SRG's build/srg/util/ checkout, so run the export from the repo root
after compile.sh.)

Quick check:
    echo "el perro ladra" | python3 $srg_yy

Then restart the LTDB server; the SRG parse demo will analyze raw Spanish.
EOF
