#!/usr/bin/env bash
# gen_server_cfg.sh
#
# Generates a FreeLing server config by appending ServerMode/ServerPort/
# ServerMaxWorkers to the installed es.cfg. Regenerating from the installed
# file (rather than keeping a hand-copied snapshot in this repo) means it
# always tracks whatever FreeLing config is actually on the box. FreeLing's
# CLI --server/--port flags don't work reliably (they're config-file-only
# options in this build despite --help showing CLI aliases), so this is the
# config a server instance must be started with.
#
# Meant to run as a systemd ExecStartPre, immediately before the matching
# `analyze` ExecStart that reads the file it writes.
#
# Usage: gen_server_cfg.sh <port> <output-path>
#
# Environment:
#   FREELINGDIR  FreeLing install prefix (default /usr)

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <port> <output-path>" >&2
  exit 1
fi

port="$1"
out="$2"
freelingdir="${FREELINGDIR:-/usr}"
src_cfg="$freelingdir/share/freeling/config/es.cfg"

if [[ ! -r "$src_cfg" ]]; then
  echo "Error: $src_cfg not found or not readable (set FREELINGDIR?)" >&2
  exit 1
fi

mkdir -p "$(dirname "$out")"
cat "$src_cfg" > "$out"
cat >> "$out" <<EOF
ServerMode=1
ServerPort=$port
ServerMaxWorkers=1
EOF
