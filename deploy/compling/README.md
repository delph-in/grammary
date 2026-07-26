# compling.upol.cz deployment snapshot

Exact copies of the files running the live grew-match service on
`compling.upol.cz`, pulled back from the server for version control —
until now they existed only on that one machine. Not applied by any
script; if the server needs rebuilding, these are the reference to
restore from (paths/values are compling-specific throughout, e.g.
`WorkingDirectory=/home/bond/ltdb-staging`).

- `run-grew-match-prod.sh` — installed at
  `~/ltdb-staging/scripts-prod/run-grew-match-prod.sh` on the server.
- `grew-match.service` — installed at
  `/etc/systemd/system/grew-match.service`.
- `grew-match-apache.conf` — installed at
  `/etc/apache2/conf-available/grew-match.conf` (enabled via
  `a2enconf grew-match`).

These predate the generic, environment-variable-driven version of the
runner added to the vendored `ltdb` tool itself
(`etc/ltdb/scripts/run-grew-match-prod.sh`,
`etc/ltdb/grew-match.service.example`,
`etc/ltdb/grew-match-apache.conf.example` — see "Production
deployment" in `etc/ltdb/doc/grew-match.md` for the reasoning behind
every piece of this setup). Migrating compling.upol.cz to the generic
version is optional cleanup, not required — the hardcoded version here
is what is actually running and known to work.

The main LTDB app itself (not grew-match) is deployed via
`scripts/push_to_compling.sh`; see that script's own header comment.
