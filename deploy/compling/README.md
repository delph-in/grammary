# compling.upol.cz deployment snapshot

Files specific to the live grew-match service on `compling.upol.cz`
that aren't tracked anywhere else, pulled back from the server for
version control. Not applied by any script; if the server needs
rebuilding, this is the reference to restore from (paths/values are
compling-specific throughout, e.g.
`WorkingDirectory=/home/bond/ltdb-staging`).

- `grew-match.service` — installed at
  `/etc/systemd/system/grew-match.service`. `ExecStart` points at
  `~/ltdb-staging/scripts/run-grew-match-prod.sh` — the generic,
  environment-variable-driven runner from the vendored `ltdb` tool
  itself (`etc/ltdb/scripts/run-grew-match-prod.sh`), configured here
  via this unit's own `Environment=` lines. Migrated to this from an
  earlier compling-specific hardcoded copy of the script (no longer
  needed, since the generic version now lives in `etc/ltdb` and is
  kept up to date on every `push_to_compling.sh upload`).
- `grew-match-apache.conf` — installed at
  `/etc/apache2/conf-available/grew-match.conf` (enabled via
  `a2enconf grew-match`).

See "Production deployment" in `etc/ltdb/doc/grew-match.md` for the
reasoning behind every piece of this setup, and
`etc/ltdb/grew-match.service.example` /
`etc/ltdb/grew-match-apache.conf.example` for the generic templates
this deployment is an instance of.

The main LTDB app itself (not grew-match) is deployed via
`scripts/push_to_compling.sh`; see that script's own header comment.

## Deploying the app (and parse-demo analyzers)

`scripts/push_to_compling.sh` must run from a machine that has **SSH access to
`bond@compling.upol.cz`** and a checkout of this repo with a built
`etc/ltdb/web/db/`. (If your workstation can't SSH in, pull this repo on a
machine that can and run it there.) It is a two-step, no-surprises flow —
step 1 only stages into `~/ltdb-staging` and `~/db-staging`; nothing under
`/var/www/ltdb` changes until you run the reviewed install script yourself.

**Step 1 — on a machine that can reach compling:**

```bash
bash scripts/push_to_compling.sh upload
```

Uploads the app code (including the parse-demo analyzer hook —
`web/preprocess.py`, the `/parse` change, the demo toggle), `blurb.md`, and all
grammar DBs, and writes a reference `~/ltdb-install.sh` on the server.

**Step 2 — on compling (needs sudo), after reviewing `~/ltdb-install.sh`:**

```bash
bash ~/ltdb-install.sh              # deploy app code + grammar DBs, restart ltdb
bash ~/ltdb-install.sh --analyzers  # …and install the morphological analyzers
```

`--analyzers` installs MeCab (apt), and jieba + KARMA into the ltdb service's
Python env (override the auto-detected venv with `LTDB_PIP=/path/to/pip`), then
adds `LTDB_ANALYZERS=jpn,cmn,kal,spa` to `/var/www/ltdb/.env` and restarts the
service. That enables Japanese, Chinese, and Kalaallisut from raw text.

The analyzer hook degrades gracefully, so deploying the app **before** installing
any analyzer is safe — grammars simply expect pre-segmented input until their
tool is present, and grammars like the ERG are unaffected.

### Spanish / FreeLing (separate, heavier)

`push_to_compling.sh` uploads only `web/db`, not `build/`, so the SRG's
FreeLing→YY wrapper is not on the server. To enable Spanish:

1. `bash scripts/install_freeling.sh` on the server (installs FreeLing 4.2).
2. Copy the SRG's `build/srg/util/` tree somewhere the app can read (e.g.
   `/var/www/ltdb/srg-util/`).
3. Add to `/var/www/ltdb/.env` and restart `ltdb`:
   `SRG_YY_CMD=bash /var/www/ltdb/srg-util/analyze-wrappers/srg-yy.sh`

See the "Morphological analyzers" section of the top-level `README.md` for the
full grammar→analyzer table and environment variables.
