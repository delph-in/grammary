#!/usr/bin/env bash
# Production runner for grew-match, meant to be the ExecStart of
# grew-match.service (see the unit file alongside this script).
#
# grew_match_quick.py rewrites grew_match/config.json and
# instances/gmq_instance.json on every start (see doc/grew-match.md in
# the ltdb repo), always keying config.json's "instances" map by
# "localhost:<frontend_port>" -- it has no notion of a public domain.
# The frontend's own JS (js/main.js) looks itself up by
# `instances[window.location.host]`, so a browser visiting the public
# URL needs a matching entry with a *publicly reachable* backend URL,
# or it just breaks (undefined lookup). So: start grew_match_quick in
# the background, wait for its backend to answer, then patch
# config.json to add that entry (and the same DELPH-IN Grammary
# branding run.sh applies for local dev), then wait on grew_match_quick
# itself so systemd tracks the whole thing as one unit.
set -euo pipefail

cd /home/bond/ltdb-staging
source scripts/opam-env.sh

CORPORA=/home/bond/db-staging/grew/grew_corpora.json
FRONTEND_PORT=8000
BACKEND_PORT=8899
PUBLIC_HOST="compling.upol.cz"
PUBLIC_BACKEND_URL="https://compling.upol.cz/grew-match-api/"
export LTDB_BASE_URL="https://compling.upol.cz/ltdb"

sleep infinity | uv run python3 grew_match_quick/grew_match_quick.py "$CORPORA" \
    --frontend_port "$FRONTEND_PORT" --backend_port "$BACKEND_PORT" &
GMQ_PID=$!

echo "Waiting for grew-match backend on :${BACKEND_PORT}..."
up=""
for _ in $(seq 30); do
  if curl -s -m 2 -X POST "http://localhost:${BACKEND_PORT}/ping" >/dev/null 2>&1; then
    up=1
    break
  fi
  sleep 2
done
if [ -z "$up" ]; then
  echo "grew-match backend did not come up in time" >&2
  kill "$GMQ_PID" 2>/dev/null || true
  exit 1
fi

echo "Patching grew_match/config.json for the public host..."
python3 - "$PUBLIC_HOST" "$PUBLIC_BACKEND_URL" <<'PY'
import json
import sys

public_host, public_backend_url = sys.argv[1], sys.argv[2]
frontend_dir = "grew_match_quick/local_files/grew_match"

config_path = f"{frontend_dir}/config.json"
with open(config_path) as f:
    cfg = json.load(f)
cfg["snippets_url"] = "snippets/"
cfg.setdefault("instances", {})[public_host] = {
    "backend": public_backend_url,
    "instance": "gmq_instance.json",
}
for instance_cfg in cfg["instances"].values():
    instance_cfg["top_project"] = {
        "website": "https://delph-in.github.io/docs/home/Home/",
        "logo": "https://github.com/delph-in.png",
        "ltdb_url": "https://compling.upol.cz/ltdb",
    }
with open(config_path, "w") as f:
    json.dump(cfg, f, indent=2)

instance_path = f"{frontend_dir}/instances/gmq_instance.json"
with open(instance_path) as f:
    groups = json.load(f)
for group in groups:
    group["id"] = "DELPH-IN Grammary Corpora"
with open(instance_path, "w") as f:
    json.dump(groups, f, indent=2)
PY

echo "grew-match ready: frontend :${FRONTEND_PORT}, backend :${BACKEND_PORT}"
wait "$GMQ_PID"
