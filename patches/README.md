# LTDB patches (pending upstream)

`etc/ltdb/` is a vendored, gitignored checkout of
<https://github.com/fcbond/ltdb>. Local changes to it are not tracked by this
repo, so feature patches we develop against the app are captured here until they
are pushed upstream.

## `ltdb-morph-analyzers.patch`

Adds optional per-grammar **morphological-analyzer / segmenter** support to the
parse demo so grammars that need external tokenization (Japanese→MeCab,
Chinese→jieba, Spanish→FreeLing, Kalaallisut→KARMA) can be parsed from raw text.

- `web/preprocess.py` — new pluggable analyzer registry (ISO-keyed), graceful
  fallback when a tool is absent.
- `web/routes.py` — `/parse` runs `preprocess_for()` before ACE, merges any YY
  flags (`-y --yy-rules`), and returns the analyzer/tokens/note in the JSON.
- `web/templates/demo.html` — an "Analyze" toggle and an analyzer banner.
- `tests/test_preprocess.py`, `tests/test_routes_unit.py` — unit + route tests.

See the "Morphological analyzers" section of the top-level `README.md` for the
grammar→analyzer table and the env vars (`LTDB_ANALYZERS`, `MECAB_BIN`,
`SRG_YY_CMD`, `KARMA_CMD`, `KARMA_MODE`).

Apply to a fresh ltdb checkout and push upstream:

```bash
cd etc/ltdb
git apply ../../patches/ltdb-morph-analyzers.patch
# review, commit, and open a PR against https://github.com/fcbond/ltdb
```

Regenerate after further local edits:

```bash
git -C etc/ltdb add -N web/preprocess.py tests/test_preprocess.py
git -C etc/ltdb diff -- web/preprocess.py web/routes.py web/templates/demo.html \
  tests/test_preprocess.py tests/test_routes_unit.py > patches/ltdb-morph-analyzers.patch
```
