#!/usr/bin/env bash
# Stage updated LTDB app and the full grammar DB collection on
# compling.upol.cz. This only uploads to the bond-owned staging
# directories below (~/ltdb-staging, ~/db-staging) — nothing under
# /var/www/ltdb is touched, and no sudo is used or required.
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
#     bash ~/ltdb-install.sh
#
set -euo pipefail

SERVER="bond@compling.upol.cz"
LOCAL_APP="etc/ltdb"
# already filtered to non-empty .db/.dat/.log by scripts/build-ltdb.sh
# (build/DBS itself can contain empty placeholders for failed builds)
LOCAL_DBS="etc/ltdb/web/db"
LOCAL_BLURB="blurb.md"

usage() {
  echo "Usage: bash scripts/push_to_compling.sh upload"
  echo ""
  echo "  upload   — stage app code, blurb.md, and all grammar DBs on"
  echo "             compling (run on this machine; no sudo)"
  echo ""
  echo "Then, when ready, SSH into compling and move things into place"
  echo "yourself (see ~/ltdb-install.sh, written by this script, for a"
  echo "starting point)."
  exit 1
}

[[ ${1:-} == "upload" ]] || usage

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

# ── Write a reference install script on compling ────────────────────────────────
echo ""
echo "==> Writing ~/ltdb-install.sh on compling (reference only — review before running)..."
ssh "$SERVER" 'cat > ~/ltdb-install.sh' << 'REMOTE'
#!/usr/bin/env bash
# Reference install script, written by scripts/push_to_compling.sh.
# Review before running — a full DB sync can leave superseded grammar
# files behind (e.g. NorSource_Nov-06.* if ~/db-staging now has a
# differently dated NorSource snapshot instead); add --delete to the
# web/db rsync below once you've confirmed nothing else depends on them.
set -euo pipefail
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

echo "==> Restarting ltdb service..."
sudo systemctl restart ltdb
sudo systemctl status ltdb --no-pager | head -10

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
echo " ~/ltdb-install.sh for a reviewed-before-you-run starting point."
echo "======================================================"
