#!/usr/bin/env bash
# Stage updated LTDB app and the full grammar DB collection on
# compling.upol.cz. This only uploads to the bond-owned staging
# directories below (~/ltdb-staging, ~/db-staging) — nothing under
# /var/www/ltdb is touched, and no sudo is used or required.
#
# It first offers to delete local files of superseded grammar versions
# (build/DBS and etc/ltdb/web/db), so they are not uploaded again.
#
# The grew-match corpora (graph exports + a server-side corpora
# description) go to ~/db-staging/grew, which the grew-match service
# reads directly; it only picks them up when restarted in step 2.
#
# Run this in TWO steps:
#
#   STEP 1 — on this machine:
#     bash scripts/push_to_compling.sh upload
#
#   STEP 2 — on compling, at your own pace (needs sudo; see
#     ~/ltdb-install.sh, written by step 1, for a reference/starting
#     point — review it before running, since a full DB sync can
#     replace grammars that have since been superseded, e.g.
#     NorSource_Nov-06.* if your local build now uses a differently
#     dated snapshot):
#     bash ~/ltdb-install.sh              # deploy app + DBs, recompile
#                                         # and restart grew-match
#     bash ~/ltdb-install.sh --analyzers  # …and install the parse-demo analyzers
#
set -euo pipefail

SERVER="bond@compling.upol.cz"
LOCAL_APP="etc/ltdb"
# already filtered to non-empty .db/.dat/.log by scripts/build-ltdb.sh
# (build/DBS itself can contain empty placeholders for failed builds)
LOCAL_DBS="etc/ltdb/web/db"
# build output; its newest .db per grammar defines the current versions
LOCAL_BUILD_DBS="build/DBS"
LOCAL_BLURB="blurb.md"
# merged grew corpora description written by scripts/build-ltdb.sh
LOCAL_GREW_CORPORA="$LOCAL_DBS/grew_corpora.json"
# must be the directory of GREW_CORPORA in deploy/compling/grew-match.service
REMOTE_GREW_DIR="/home/bond/db-staging/grew"

usage() {
  echo "Usage: bash scripts/push_to_compling.sh upload"
  echo ""
  echo "  upload   — stage app code, blurb.md, all grammar DBs, and the"
  echo "             grew-match corpora on compling (run on this machine;"
  echo "             no sudo)"
  echo ""
  echo "Then, when ready, SSH into compling and move things into place"
  echo "yourself (see ~/ltdb-install.sh, written by this script, for a"
  echo "starting point)."
  exit 1
}

[[ ${1:-} == "upload" ]] || usage

# ── Local stale-version check ─────────────────────────────────────────────────
# Before anything is uploaded, offer to delete local files of superseded
# grammar versions, so they are not uploaded again.
bash scripts/clean_stale_grammars.sh --refresh-derived \
  "$LOCAL_BUILD_DBS" "$LOCAL_DBS"
echo ""

# ── App code ──────────────────────────────────────────────────────────────────
echo "==> Uploading app code to ~/ltdb-staging/ ..."
rsync -az --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
  --exclude='*.pyc' --exclude='web/db' \
  "$LOCAL_APP/" "$SERVER:~/ltdb-staging/"
echo "    done."

# ── Home-page blurb (see fcbond/ltdb's HOME_BLURB_FILE) ────────────────────────
echo ""
echo "==> Uploading blurb.md to ~/ltdb-staging/blurb.md ..."
rsync -az "$LOCAL_BLURB" "$SERVER:~/ltdb-staging/blurb.md"
echo "    done."

# ── All grammar databases ───────────────────────────────────────────────────────
echo ""
echo "==> Uploading all grammar DBs to ~/db-staging/ ($(du -sh "$LOCAL_DBS" | cut -f1))..."
ssh "$SERVER" "mkdir -p ~/db-staging"
rsync -az --progress --include='*.db' --include='*.dat' --include='*.log' \
  --exclude='*' "$LOCAL_DBS/" "$SERVER:~/db-staging/"
echo "    done."

# ── Stale-version check: manifest + helper ─────────────────────────────────────
# ~/ltdb-install.sh uses these to find files of superseded grammar versions
# (e.g. Norsyg_2602.* once Norsyg_2608 exists) and offer to delete them.
# The manifest lists the stem of every grammar DB being deployed.
echo ""
echo "==> Uploading the current-grammar manifest and stale-file helper ..."
manifest_tmp="$(mktemp)"
trap 'rm -f "$manifest_tmp"' EXIT
find "$LOCAL_DBS" -maxdepth 1 -type f -name '*.db' -printf '%f\n' \
  | sed 's/\.db$//' | sort > "$manifest_tmp"
rsync -az "$manifest_tmp" "$SERVER:~/db-staging/current_grammars.txt"
rsync -az scripts/stale_grammar_files.py "$SERVER:~/ltdb-stale-check.py"
echo "    done ($(wc -l < "$manifest_tmp") current grammars)."

# ── grew-match corpora ──────────────────────────────────────────────────────────
# The grew-match service reads its corpora straight from $REMOTE_GREW_DIR
# (GREW_CORPORA in deploy/compling/grew-match.service), not from
# /var/www/ltdb. Nothing changes for visitors until grew-match is restarted
# (~/ltdb-install.sh does that), but there is no separate staging copy.
# Graph paths in the corpora description are absolute, so they are
# rewritten for the server; _build_grew (grew's compiled cache) is left
# out and rebuilt there. The description goes up last so it never names
# graphs that have not arrived yet.
echo ""
if [[ -f "$LOCAL_GREW_CORPORA" ]]; then
  echo "==> Uploading grew-match corpora to $REMOTE_GREW_DIR/ ..."
  grew_tmp="$(mktemp -d)"
  trap 'rm -f "$manifest_tmp"; rm -rf "$grew_tmp"' EXIT
  python3 scripts/remote_grew_corpora.py "$LOCAL_GREW_CORPORA" \
    "$REMOTE_GREW_DIR" "$grew_tmp/grew_corpora.json" > "$grew_tmp/exports"
  ssh "$SERVER" "mkdir -p '$REMOTE_GREW_DIR'"
  while IFS= read -r export_dir; do
    rsync -az --exclude='_build_grew' --exclude='corpora.json' \
      "$export_dir/" "$SERVER:$REMOTE_GREW_DIR/$(basename "$export_dir")/"
  done < "$grew_tmp/exports"
  rsync -az "$grew_tmp/grew_corpora.json" \
    "$SERVER:$REMOTE_GREW_DIR/grew_corpora.json"
  echo "    done ($(wc -l < "$grew_tmp/exports") grammar exports)."
else
  echo "==> No $LOCAL_GREW_CORPORA; skipping grew-match corpora."
fi

# ── Write a reference install script on compling ────────────────────────────────
echo ""
echo "==> Writing ~/ltdb-install.sh on compling (reference only — review before running)..."
ssh "$SERVER" 'cat > ~/ltdb-install.sh' << 'REMOTE'
#!/usr/bin/env bash
# Reference install script, written by scripts/push_to_compling.sh.
# Review before running. It first lists files of superseded grammar
# versions (e.g. NorSource_Nov-06.* once ~/db-staging has a differently
# dated NorSource snapshot) in staging and in /var/www/ltdb/web/db and
# asks whether to delete them; answering no leaves everything in place.
#
# Usage: bash ~/ltdb-install.sh [--analyzers]
#   --analyzers  also install the optional parse-demo morphological
#                analyzers (MeCab, jieba, KARMA) and enable them in .env.
#                FreeLing/Spanish is heavier and only referenced here.
set -euo pipefail
ANALYZERS=0
[[ "${1:-}" == "--analyzers" ]] && ANALYZERS=1
# Offer to delete files of superseded grammar versions, before anything is
# copied, so they are not re-installed from staging. Only an older version
# of a grammar that is in the current manifest counts; grammars missing
# from the manifest are never listed (see ~/ltdb-stale-check.py).
MANIFEST="$HOME/db-staging/current_grammars.txt"
if [[ -s "$MANIFEST" && -f "$HOME/ltdb-stale-check.py" ]]; then
  echo "==> Checking for stale grammar versions ..."
  mapfile -t stale < <(python3 "$HOME/ltdb-stale-check.py" \
    --manifest "$MANIFEST" \
    "$HOME/db-staging" "$HOME/db-staging/grew" /var/www/ltdb/web/db)
  if (( ${#stale[@]} == 0 )); then
    echo "    none found."
  else
    printf '    %s\n' "${stale[@]}"
    reply=n
    if [[ -t 0 ]]; then
      read -r -p "    Delete these ${#stale[@]} stale items? [y/N] " reply
    else
      echo "    (not a terminal: leaving them in place)"
    fi
    if [[ "$reply" == [yY]* ]]; then
      for item in "${stale[@]}"; do
        # staging is bond's own; /var/www/ltdb needs sudo
        if [[ -w "$(dirname "$item")" ]]; then
          rm -rf -- "$item"
        else
          sudo rm -rf -- "$item"
        fi
      done
      echo "    deleted."
    else
      echo "    kept."
    fi
  fi
fi

echo "==> Copying app code to /var/www/ltdb/ ..."
sudo rsync -a --exclude='web/db' ~/ltdb-staging/ /var/www/ltdb/

echo "==> Copying blurb.md to /var/www/ltdb/ ..."
sudo cp ~/ltdb-staging/blurb.md /var/www/ltdb/blurb.md

echo "==> Copying grammar databases to /var/www/ltdb/web/db/ ..."
sudo rsync -a ~/db-staging/ /var/www/ltdb/web/db/

echo "==> Fixing ownership and permissions..."
sudo chown -R www-data:www-data /var/www/ltdb/
sudo chmod 644 /var/www/ltdb/web/db/*.db /var/www/ltdb/web/db/*.dat

echo "==> Enabling the home-page blurb (idempotent) ..."
if ! sudo grep -q '^HOME_BLURB_FILE=' /var/www/ltdb/.env 2>/dev/null; then
  echo 'HOME_BLURB_FILE=/var/www/ltdb/blurb.md' | sudo tee -a /var/www/ltdb/.env >/dev/null
fi

if [[ "$ANALYZERS" -eq 1 ]]; then
  echo "==> Installing optional parse-demo morphological analyzers ..."
  # Japanese (MeCab) — system package.
  sudo apt-get update -qq
  sudo apt-get install -y mecab mecab-ipadic-utf8 \
    || echo "    (MeCab install failed; Japanese analysis stays unavailable)"

  # Chinese (jieba) + Kalaallisut (KARMA, needs Python >= 3.12) go into the
  # same Python environment the ltdb service runs. Override the guess with
  # LTDB_PIP=/path/to/pip if these paths are wrong for this server.
  PIP="${LTDB_PIP:-}"
  if [[ -z "$PIP" ]]; then
    for cand in /var/www/ltdb/.venv/bin/pip /var/www/ltdb/venv/bin/pip; do
      [[ -x "$cand" ]] && PIP="$cand" && break
    done
  fi
  if [[ -n "$PIP" ]]; then
    echo "    using pip: $PIP"
    sudo "$PIP" install jieba "git+https://github.com/alexhsu-nlp/karma.git" \
      || echo "    (jieba/KARMA install failed; Chinese/Kalaallisut stay unavailable)"
  else
    echo "    ⚠️  Could not find the ltdb service's venv pip; set LTDB_PIP and"
    echo "        re-run, or install by hand into that venv:"
    echo "          <venv>/bin/pip install jieba git+https://github.com/alexhsu-nlp/karma.git"
  fi

  # Turn the analyzers on (idempotent); trim the ISO list to taste.
  if ! sudo grep -q '^LTDB_ANALYZERS=' /var/www/ltdb/.env 2>/dev/null; then
    echo 'LTDB_ANALYZERS=jpn,cmn,kal,spa' | sudo tee -a /var/www/ltdb/.env >/dev/null
  fi

  echo "    Spanish/FreeLing is separate and heavier:"
  echo "      1) bash scripts/install_freeling.sh   (from a grammary checkout)"
  echo "      2) place the SRG's build/srg/util tree where the app can reach it,"
  echo "         e.g. /var/www/ltdb/srg-util/, and copy scripts/srg_freeling_yy.py"
  echo "         alongside it (the SRG's own wrapper needs FreeLing's Python"
  echo "         bindings, which don't run on 24.04+; this one goes through the"
  echo "         analyze CLI instead -- see README.md's analyzer table)"
  echo "      3) add to /var/www/ltdb/.env:"
  echo "         SRG_UTIL_DIR=/var/www/ltdb/srg-util"
  echo "         SRG_YY_CMD=python3 /var/www/ltdb/srg_freeling_yy.py"
fi

echo "==> Restarting ltdb service..."
sudo systemctl restart ltdb
sudo systemctl status ltdb --no-pager | head -10

# grew-match serves ~/db-staging/grew directly (see grew-match.service).
# Compile the corpora first, as bond: the service's own start-up compile
# has to finish inside its readiness wait, which a large changed corpus
# (e.g. the ERG) would overrun.
GREW_CORPORA_FILE="$HOME/db-staging/grew/grew_corpora.json"
if [[ -f "$GREW_CORPORA_FILE" ]] \
    && systemctl cat grew-match.service >/dev/null 2>&1; then
  echo "==> Compiling grew-match corpora (no-op when up to date) ..."
  (
    cd ~/ltdb-staging
    set +u
    source scripts/opam-env.sh
    set -u
    corpusbank=grew_match_quick/local_files/corpusbank
    mkdir -p "$corpusbank"
    cp "$GREW_CORPORA_FILE" "$corpusbank/gmq_corpora.json"
    grew compile -CORPUSBANK "$corpusbank"
  )
  echo "==> Restarting grew-match service..."
  sudo systemctl restart grew-match
  sudo systemctl status grew-match --no-pager | head -10
fi

echo ""
echo "Done. https://compling.upol.cz/ltdb"
REMOTE
ssh "$SERVER" "chmod +x ~/ltdb-install.sh"

echo ""
echo "======================================================"
echo " Staging complete."
echo ""
echo " Nothing under /var/www/ltdb was touched. When ready, SSH into"
echo " compling and move things into place yourself — see"
echo " ~/ltdb-install.sh for a reviewed-before-you-run starting point:"
echo "     bash ~/ltdb-install.sh              # deploy app + DBs, refresh grew-match"
echo "     bash ~/ltdb-install.sh --analyzers  # …and the parse-demo analyzers"
echo "======================================================"
