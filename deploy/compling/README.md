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

### Order of operations

> Just the commands? See `deploy/compling/CHEATSHEET.md`.


Steps 1–4 run on your **build machine**, which must also have SSH access to
compling (step 4 uses rsync/ssh). Step 5 runs on compling. If no single machine
can both build and SSH in, build on one and copy `etc/ltdb/` (app + `web/db`) to
an SSH-capable machine before step 4. Nothing on the server changes until
step 5 — step 4 only stages into `~/ltdb-staging` and `~/db-staging`.

1. **Prerequisites (once):** `bash setup.sh --analyzers`
   — build tools + uv (the `--analyzers` extras only matter on the server, but
   installing them here is harmless).
2. **Build the grammars:** `bash compile.sh`
   — downloads every grammar, compiles with ACE, and fills `build/DBS/` and
   `etc/ltdb/web/db/`. Slow (~hours). Skip if you are shipping *only* the app
   change and are happy to leave the server's grammars as they are (then just
   make sure `etc/ltdb/web/db/` exists — empty is fine; the DB rsync has no
   `--delete`).
   (The analyzer hook and grew `snippets` key are upstream in `fcbond/ltdb`, so
   the `etc/ltdb` that `compile.sh` clones already includes them — no patch step.)
3. **Stage on compling (needs SSH):** `bash scripts/push_to_compling.sh upload`
4. **Install on compling (needs sudo):** `bash ~/ltdb-install.sh --analyzers`
5. **Spanish / FreeLing:** optional, separate — see below.

The analyzer tools (MeCab, jieba, KARMA, FreeLing) install on the **server** in
step 4, not on the build machine. The two commands below are steps 3 and 4 in
detail.

**Step 3 — on a machine that can reach compling:**

```bash
bash scripts/push_to_compling.sh upload
```

Uploads the app code (including the parse-demo analyzer hook —
`web/preprocess.py`, the `/parse` change, the demo toggle), `blurb.md`, and all
grammar DBs, and writes a reference `~/ltdb-install.sh` on the server.

It also uploads the grew-match corpora to `~/db-staging/grew/`: each
`build/DBS/<grammar>-grew/` export (without grew's `_build_grew` cache) plus a
`grew_corpora.json` whose graph paths are rewritten for the server
(`scripts/remote_grew_corpora.py`). The grew-match service reads this directory
directly (`GREW_CORPORA` in `grew-match.service`), so there is no second copy
to install; the running service keeps its already-loaded corpora until step 4
recompiles them and restarts it.

Finally it writes `~/db-staging/current_grammars.txt` (the stems of the DBs
being deployed) and `~/ltdb-stale-check.py`. Step 4 uses them to list files of
superseded grammar versions (e.g. `Norsyg_2602.*` once `Norsyg_2608` exists) in
`~/db-staging`, `~/db-staging/grew` and `/var/www/ltdb/web/db`, and asks before
deleting them. Only an older version of a grammar that is being deployed is
listed; a grammar missing from the manifest is left alone.

Before uploading anything, the script runs the same check locally
(`scripts/clean_stale_grammars.sh`) on `build/DBS` and `etc/ltdb/web/db`
(current = the newest build of each `SHORT_GRAMMAR_NAME` in `build/DBS`) and
asks before deleting. If it removes entries, regenerate `docs/summary.md`.
`scripts/build-ltdb.sh` runs the same check on `build/DBS` right after
building, so a full `compile.sh` normally leaves nothing for the upload to find.

**Step 4 — on compling (needs sudo), after reviewing `~/ltdb-install.sh`:**

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

`push_to_compling.sh` uploads only `web/db`, not `build/` or `scripts/`, so
neither the SRG's own FreeLing→YY wrapper nor `scripts/srg_freeling_yy.py`
(grammary's CLI-based replacement for it — see the "Morphological analyzers"
section of the top-level `README.md` for why the SRG's own wrapper doesn't
run on Ubuntu 24.04+) is on the server. To enable Spanish:

1. `bash scripts/install_freeling.sh` on the server (installs FreeLing 4.2).
2. Copy the SRG's `build/srg/util/` tree somewhere the app can read (e.g.
   `/var/www/ltdb/srg-util/`).
3. Copy `scripts/srg_freeling_yy.py` alongside it (e.g.
   `/var/www/ltdb/srg_freeling_yy.py`).
4. Add to `/var/www/ltdb/.env` and restart `ltdb`:
   ```
   SRG_UTIL_DIR=/var/www/ltdb/srg-util
   SRG_YY_CMD=python3 /var/www/ltdb/srg_freeling_yy.py
   ```

See the "Morphological analyzers" section of the top-level `README.md` for the
full grammar→analyzer table and environment variables.
