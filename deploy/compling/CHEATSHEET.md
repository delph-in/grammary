# compling deploy — cheat sheet

Quick command reference. Full explanation: `deploy/compling/README.md`.

## Build machine (also needs SSH to compling)

```bash
bash setup.sh --analyzers                                   # 1. prereqs (once)
bash compile.sh                                             # 2. build grammars (~hours)
bash scripts/push_to_compling.sh upload                     # 3. stage on compling
```

## On compling (needs sudo)

```bash
bash ~/ltdb-install.sh --analyzers    # deploy app + DBs, install analyzers, restart
# (omit --analyzers to deploy app + DBs only)
```

→ https://compling.upol.cz/ltdb

## Notes

- The analyzer hook and grew `snippets` key are upstream in `fcbond/ltdb`, so the
  `etc/ltdb` that `compile.sh` clones already has them — no patch step.
- **App-only, no build?** Skip step 2; just ensure `etc/ltdb/web/db/` exists
  (empty is fine — the DB rsync has no `--delete`).
- **Can't build + SSH on one box?** Build anywhere, copy `etc/ltdb/` (app +
  `web/db`) to an SSH-capable machine, then run steps 3–4 there.
- **Analyzer env** (`/var/www/ltdb/.env`, set by `--analyzers`):
  `LTDB_ANALYZERS=jpn,cmn,kal,spa`; override the venv with `LTDB_PIP=/path/to/pip`.

## Spanish / FreeLing (optional, on compling)

```bash
bash scripts/install_freeling.sh      # install FreeLing 4.2
# copy the SRG's build/srg/util/ tree to e.g. /var/www/ltdb/srg-util/, then:
echo 'SRG_YY_CMD=bash /var/www/ltdb/srg-util/analyze-wrappers/srg-yy.sh' \
  | sudo tee -a /var/www/ltdb/.env
sudo systemctl restart ltdb
```
