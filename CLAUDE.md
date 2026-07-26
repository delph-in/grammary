# Grammary — Developer Guide

## What This Project Is

A curated repository of DELPH-IN grammars (HPSG/LKB grammars processed by the
Linguistic Type Database, LTDB). Grammars are compiled with ACE and indexed into
SQLite databases. The live LTDB browser is at https://compling.upol.cz/ltdb.

The static mirror ("lite mode") is a frozen subset of the live LTDB, served from
GitHub Pages at `docs/`. It is the offline fallback when the live server is down.

## Key Directories

| Path | Purpose |
|------|---------|
| `etc/ltdb/` | Vendored LTDB Flask app. Treat as a dependency; patch carefully. |
| `etc/ltdb/web/` | Flask routes, DB helpers, templates for the live LTDB. |
| `etc/ltdb/web/db/` | Grammar `.db` files at runtime (symlinked or copied from `build/DBS/`). |
| `build/DBS/` | Compiled grammar databases produced by `compile.sh`. Source of truth for `.db` files. |
| `docs/` | **GitHub Pages root.** Everything published to Pages lives here. Not a docs folder. |
| `docs/ltdb/` | Frozen static LTDB mirror (generated; do not hand-edit). |
| `scripts/` | Build and utility scripts for grammary (not part of the LTDB app). |
| `grammary.toml` | Source of truth for grammar inventory (VCS URLs and release archives). |
| `blurb.md` | Home-page intro shown on the live/static LTDB via `HOME_BLURB_FILE`; not part of the vendored ltdb tool (see below). |
| `deploy/compling/` | Snapshot of files running the live deployment at compling.upol.cz that aren't part of any git-tracked app (grew-match's systemd unit, Apache conf, runner script). See its README. |

## Build Pipeline

1. `compile.sh` — downloads all grammars and runs LTDB build; outputs `.db` files to `build/DBS/`.
2. `scripts/freeze_ltdb.py` — freezes static LTDB pages into `docs/ltdb/` using Flask-Frozen.
3. `scripts/build_ltdb_example_dbs.py` — extracts example data from each grammar `.db`
   into a compact per-grammar SQLite for browser-side lazy loading.

The release workflow (`.github/workflows/release.yml`) automates step 1 on tag push and attaches
each `.db` file individually to the GitHub Release.

## Production Deployment (compling.upol.cz)

`scripts/push_to_compling.sh upload` stages the app code, `blurb.md`, and every grammar DB in
`etc/ltdb/web/db/` into `bond`'s home directory on the server (`~/ltdb-staging`, `~/db-staging`) —
no `sudo`, nothing under `/var/www/ltdb` touched. Moving staged files into place, restarting
`ltdb`, and any `sudo`-gated step is done by hand on the server (the script writes
`~/ltdb-install.sh` there as a reviewed-before-you-run reference, not something to run blindly —
a full DB sync can leave superseded grammar files, e.g. an old dated snapshot of a re-fetched
grammar, behind).

grew-match (structural corpus search) is deployed separately, as its own systemd service under
`bond` (not `www-data` — entirely independent of `/var/www/ltdb`), reverse-proxied by Apache
alongside the existing `/ltdb` proxy. The generic version of that setup — script, systemd unit,
Apache conf, and the reasoning behind each piece — lives in the vendored tool itself
(`etc/ltdb/scripts/run-grew-match-prod.sh`, `etc/ltdb/grew-match.service.example`,
`etc/ltdb/grew-match-apache.conf.example`, and "Production deployment" in
`etc/ltdb/doc/grew-match.md`); `deploy/compling/` has the exact (pre-parameterization) files
actually installed on the server.

## The LTDB App and Mirror Routes

The live LTDB uses session-based routes (`/grammar.html`, `/type/<query>`) that require a server.

The static mirror uses **mirror routes** — a parallel set of Flask routes prefixed `/ltdb/<grm>/`:

| Flask endpoint | URL pattern | Frozen to |
|----------------|-------------|-----------|
| `mirror_home` | `/ltdb/` | `docs/ltdb/index.html` |
| `mirror_grammar` | `/ltdb/<grm>/grammar.html` | per-grammar grammar page |
| `mirror_rules` | `/ltdb/<grm>/rules.html` | per-grammar rules page |
| `mirror_ltypes` | `/ltdb/<grm>/ltypes.html` | per-grammar lex-types page |
| `mirror_type` | `/ltdb/<grm>/type/<query>.html` | per-type page |

These routes are in `etc/ltdb/web/routes.py`. They render the same templates as the live routes
but with stable, grammar-scoped URLs suitable for static hosting. Types not included in the mirror
get links pointing back to the live LTDB.

Which type statuses are frozen is controlled by `--statuses` (default: `lex-type,rule,lex-rule,root`).

## Key Constants in the LTDB App

- `sentlim = 8` (`etc/ltdb/web/db.py`) — maximum sentences shown per type on the live site.
- `lim = 512` — maximum rows for most list queries.
- `STATIC_MIRROR_STATUSES` — env var read by `routes.py`; controls which type pages get
  static-mirror-style links vs. fallback links to the live LTDB.
- `FULL_LTDB_BASE_URL` — env var for the live LTDB base URL used in fallback links.

## What the Mirror Does NOT Support

- Live parse / generate (requires ACE binary and a running server)
- Full corpus search
- Session-based grammar selection
- Full example inventory (the browser SQLite contains a capped sample)

## Grammar Inventory

`grammary.toml` lists every grammar with its VCS URL or release archive. It is the canonical list;
`docs/summary.md` and `docs/grammary.md` are generated from it and from the compiled databases.
