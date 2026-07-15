#!/usr/bin/env bash
# Push updated LTDB app and ERG databases to compling.upol.cz.
#
# Run this in TWO steps:
#
#   STEP 1 — on this machine:
#     bash scripts/push_to_compling.sh upload
#
#   STEP 2 — on compling (after step 1 finishes):
#     bash ~/ltdb-install.sh
#
set -euo pipefail

SERVER="bond@compling.upol.cz"
LOCAL_APP="etc/ltdb"
LOCAL_DBS="build/DBS"

ERG_FILES=(
  ERG_2025.db
  ERG_2025.dat
  erg-dict_2025.db
  erg-dict_2025.dat
  erg-singlish_2025.db
  erg-singlish_2025.dat
  erg-mal_2025.db
  erg-mal_2025.dat
)

usage() {
  echo "Usage: bash scripts/push_to_compling.sh upload"
  echo ""
  echo "  upload   — push app code and ERG DBs to compling (run on this machine)"
  echo ""
  echo "Then SSH into compling and run:  bash ~/ltdb-install.sh"
  exit 1
}

[[ ${1:-} == "upload" ]] || usage

# ── App code ──────────────────────────────────────────────────────────────────
echo "==> Uploading app code to ~/ltdb-staging/ ..."
rsync -az --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
  --exclude='*.pyc' --exclude='web/db' \
  "$LOCAL_APP/" "$SERVER:~/ltdb-staging/"
echo "    done."

# ── ERG databases ─────────────────────────────────────────────────────────────
echo ""
echo "==> Uploading ERG databases to ~/db-staging/ (~3.3 GB, ~50 min @ 10 Mbps)..."
ssh "$SERVER" "mkdir -p ~/db-staging"
for f in "${ERG_FILES[@]}"; do
  src="$LOCAL_DBS/$f"
  if [[ -f "$src" ]]; then
    echo "    $f ($(du -h "$src" | cut -f1))"
    rsync -az --progress "$src" "$SERVER:~/db-staging/$f"
  else
    echo "    WARNING: $src not found, skipping"
  fi
done
echo "    done."

# ── Write the install script on compling ──────────────────────────────────────
echo ""
echo "==> Writing ~/ltdb-install.sh on compling..."
ssh "$SERVER" 'cat > ~/ltdb-install.sh' << 'REMOTE'
#!/usr/bin/env bash
set -euo pipefail
echo "==> Copying app code to /var/www/ltdb/ ..."
sudo rsync -a --exclude='web/db' ~/ltdb-staging/ /var/www/ltdb/

echo "==> Copying ERG databases to /var/www/ltdb/web/db/ ..."
sudo cp ~/db-staging/*.db ~/db-staging/*.dat /var/www/ltdb/web/db/

echo "==> Fixing ownership and permissions..."
sudo chown -R www-data:www-data /var/www/ltdb/
sudo chmod 644 /var/www/ltdb/web/db/*.db /var/www/ltdb/web/db/*.dat

echo "==> Restarting ltdb service..."
sudo systemctl restart ltdb
sudo systemctl status ltdb --no-pager | head -10

echo ""
echo "Done. https://compling.upol.cz/ltdb"
REMOTE
ssh "$SERVER" "chmod +x ~/ltdb-install.sh"

echo ""
echo "======================================================"
echo " Upload complete."
echo ""
echo " Now SSH into compling and run:"
echo "   bash ~/ltdb-install.sh"
echo "======================================================"
