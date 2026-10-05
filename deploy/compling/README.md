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
