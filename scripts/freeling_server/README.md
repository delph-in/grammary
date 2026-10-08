# FreeLing server mode for the SRG parse-demo preprocessor

`scripts/srg_freeling_yy.py` needs FreeLing's `analyze` CLI twice per
sentence (a tagged pass and a morfo pass — see that script's docstring for
why). A cold `analyze` process takes ~3s to load its dictionaries, so two
calls per sentence costs ~3-6s. Running FreeLing in server mode instead
(dictionaries loaded once, kept warm) cuts each call to ~20ms.

This directory holds what that takes:

- `gen_server_cfg.sh` — regenerates a server config by appending
  `ServerMode`/`ServerPort`/`ServerMaxWorkers` to the installed `es.cfg`, so
  it always tracks whatever FreeLing config is actually on the box rather
  than a snapshot that can go stale. Run as each service's `ExecStartPre`.
- `srg-freeling-tagged.service.example` / `srg-freeling-morfo.service.example`
  — one systemd unit per analysis pass, since a FreeLing server is locked to
  whatever flags (`--rtk --outlv tagged` vs `--outlv morfo`) it started
  with and can't take per-request overrides.

## Why two servers, and why they're always on

Each pass needs different startup flags, so one process can't serve both.
With `--workers 1` each, that's roughly 200-500MB resident per server,
~0.5-1GB total — a flat, bounded cost, paid whether or not anyone is using
the parse demo (deliberately so: see the alternative below).

An idle-timeout (start on first request, stop after N minutes idle) would
avoid paying that cost when nobody's using the demo, at the price of eating
the ~3s cold-start again on the first request after a quiet spell, plus a
watcher process to track idle time. Not implemented here — the flat always-on
cost was the chosen tradeoff for this deployment.

## Why FreeLing's CLI `--server --port` flags aren't used

`analyze --server --port N ...` reliably fails with `Error - Ignoring
unexpected server port number` in this build, regardless of flag order.
`--server`/`-p/--port` turn out to be CLI-only option *names*, but the
running analyzer actually reads server settings from the *config file*
options `ServerMode`/`ServerPort`/`ServerMaxWorkers` (`analyze --help-cf`),
which is why `gen_server_cfg.sh` appends those directly rather than passing
`--server`/`--port` on the command line.

## Why the services set `IPAddressDeny=any` / `IPAddressAllow=localhost`

FreeLing's server always binds `0.0.0.0` — there is no config option to bind
only to loopback. Left alone, both servers would be reachable from the
network, bypassing the LTDB app and `preprocess.py`'s input handling
entirely. These two directives block all network traffic to/from the
service at the systemd/cgroup level except to `localhost`, so only processes
on the same host (`scripts/srg_freeling_yy.py`, via `analyzer_client`) can
ever reach them, independent of any separate firewall configuration.

## Install

```bash
# one-time: generate the configs' first version and sanity-check by hand
# (ExecStartPre regenerates them on every start, so this step is optional)
bash scripts/freeling_server/gen_server_cfg.sh 5031 /tmp/es-tagged-check.cfg

# edit the REPLACE_* placeholders in both .service.example files, then:
sudo cp scripts/freeling_server/srg-freeling-tagged.service.example \
  /etc/systemd/system/srg-freeling-tagged.service
sudo cp scripts/freeling_server/srg-freeling-morfo.service.example \
  /etc/systemd/system/srg-freeling-morfo.service
sudo systemctl daemon-reload
sudo systemctl enable --now srg-freeling-tagged srg-freeling-morfo
sudo systemctl status srg-freeling-tagged srg-freeling-morfo --no-pager

# point the LTDB app at them (default ports already match; only needed if
# you changed the ports in the unit files):
export SRG_FREELING_TAGGED_PORT=5031
export SRG_FREELING_MORFO_PORT=5032
```

Quick check once both are up:

```bash
echo "No quiero creerlo." | analyzer_client 127.0.0.1:5031
```
