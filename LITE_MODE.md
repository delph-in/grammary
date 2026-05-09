**Plan**

1. **Clean Up Stale Output**
   Delete the partially generated output so measurements start clean:
   ```bash
   rm -rf docs/ltdb/ docs/static/
   ```
   Keep all code changes (freeze script, mirror routes) — they are the work product.

2. **Define The Hybrid Output**
   Target structure:
   ```text
   docs/ltdb/index.html
   docs/ltdb/<grammar>/grammar.html
   docs/ltdb/<grammar>/rules.html
   docs/ltdb/<grammar>/ltypes.html
   docs/ltdb/<grammar>/type/<type>.html
   docs/ltdb/assets/ltdb-examples.js   (+ sql.js/SQLite WASM)
   docs/ltdb/db/<grammar>.examples.sqlite
   ```
   Static pages render grammar/type metadata. Examples load lazily from the
   per-grammar SQLite DB via browser-side SQL.

   Existing Flask static assets may still be emitted by Flask-Frozen under
   `docs/static/`. New mirror-only assets should live under
   `docs/ltdb/assets/`.

3. **Freeze Static Pages With Flask-Frozen**
   The mirror routes already exist in `etc/ltdb/web/routes.py` under the
   `/ltdb/<grm>/` prefix (`mirror_home`, `mirror_grammar`, `mirror_rules`,
   `mirror_ltypes`, `mirror_type`). These are purpose-built for static
   generation: they use grammar-scoped, stable URLs and redirect unsupported
   links to the live LTDB.

   `scripts/freeze_ltdb.py` is already written; run it with:
   ```bash
   cd etc/ltdb
   uv run python ../../scripts/freeze_ltdb.py --destination ../../docs
   ```
   Confirm that CSS/JS assets from the LTDB app land in `docs/ltdb/` correctly
   (Flask-Frozen copies them automatically via the static endpoint). Check that
   no asset paths assume a server prefix.

4. **Change Type Pages To Use Example Placeholders**
   In static mirror pages, do not inline sentence/MRS/tree examples in
   `type.html`. Instead render a bare placeholder:
   ```html
   <section id="examples"
            data-grammar="ERG_2025"
            data-type="n_-_c_le"
            data-db="../../db/ERG_2025.examples.sqlite"></section>
   ```
   The JS loader reads these attributes and fetches examples from the
   per-grammar SQLite DB.

5. **Build Compact Example Databases**
   Add `scripts/build_ltdb_example_dbs.py`. For each grammar `.db` in
   `--db-dir`, write `docs/ltdb/db/<grammar>.examples.sqlite` containing a
   normalized schema so repeated examples are stored only once:
   ```sql
   CREATE TABLE examples (
     example_id  INTEGER PRIMARY KEY,
     profile     TEXT    NOT NULL,
     sid         INTEGER NOT NULL,
     sentence    TEXT    NOT NULL,
     tokens_json TEXT,
     deriv       TEXT,              -- UDF derivation string
     mrs         TEXT,              -- simplemrs string
     UNIQUE(profile, sid)
   );

   CREATE TABLE type_examples (
     typ        TEXT    NOT NULL,
     rank       INTEGER NOT NULL,  -- 1-based display order
     example_id INTEGER NOT NULL,
     spans_json TEXT,              -- type-span data for highlighting
     source     TEXT,              -- lex-type, lex-entry:<lexid>, rule, etc.
     PRIMARY KEY (typ, rank)
     FOREIGN KEY(example_id) REFERENCES examples(example_id)
   );
   CREATE INDEX idx_typ ON type_examples(typ);
   ```
   The script reuses LTDB's example-selection logic: skip the first 20% of
   available examples (per `calculate_offset_limit`), then take up to
   `--example-lim` results ordered by sentence length.

6. **Decide What Counts As Relevant**
   Default type statuses for the example DB (same as the freeze default):
   ```text
   lex-type, rule, lex-rule, root
   ```
   Additionally include **lex entries**, but only as a secondary source of
   examples for each lex-type page: for every lex-type, collect examples from
   its member lex-entries up to `--lex-example-lim` (default **5**) per
   lex-type. Do not create one type page per lex-entry; lex-entry examples feed
   the parent lex-type page.

   Do not include `generic-lex-entry` by default — they rarely have corpus
   coverage and produce noise.

   Rationale: the live LTDB `sentlim` is 8; 5 is sufficient for an offline
   reference and keeps DB sizes manageable.

7. **Add Browser SQLite Loader**
   Use `sql.js` (WASM build, ~500 KB gzipped) or the lighter
   `sqlite-wasm` package. Bundle/copy the WASM file to
   `docs/ltdb/assets/`. JS flow in `ltdb-examples.js`:
   1. Read `data-grammar` and `data-type` from the placeholder `<section>`.
   2. Fetch the SQLite URL from `data-db`; for type pages this is normally
      `../../db/<grammar>.examples.sqlite`.
   3. Initialise the SQLite WASM engine; open the DB from the fetched buffer.
   4. Join `type_examples` to `examples` for the requested type and render.
   5. Show a "no examples available" message if the fetch fails or returns
      zero rows — do not leave the section silently empty.
   6. Cache opened DBs in a module-level `Map` keyed by grammar name for the
      lifetime of the page. Do not use `sessionStorage`; it is string-only and
      too quota-limited for SQLite buffers. IndexedDB or the Cache API can be
      added later if persistent browser caching is worthwhile.

8. **Choose Raw Versus Precomputed Visualization Data**
   Start conservative:
   - store raw `sentence`, `tokens_json`, `spans_json`, `mrs`, `deriv`
   - render sentence text first (always works)
   - add tree / MRS / DMRS rendering after DB size and browser performance
     are confirmed acceptable

   If browser-side MRS→DMRS conversion proves impractical, precompute
   visualization JSON during the build step and store it in the example DB.

9. **Measure Sizes**
   For each build, report:
   ```text
   Frozen HTML: file count, total bytes, gzip-compressed bytes
   JS+WASM assets: sql.js WASM size (target < 600 KB gzipped)
   Example DB: total bytes across all grammars, largest single grammar DB
   Grand total compressed: must remain < 1 GB (GitHub Pages repo limit)
   ```
   Fail the build (or at least warn loudly) if the grand total exceeds 900 MB.

10. **Verify Locally**
    Start a local static server from `docs/`:
    ```bash
    python -m http.server -d docs 8000
    ```
    Check:
    - index loads and lists all grammars
    - grammar / rules / ltypes pages load
    - type page loads and placeholder section is present
    - examples appear after DB fetch (requires JS; test in a real browser)
    - navigating between two type pages for the same grammar fetches the DB
      only once (verify in Network tab)
    - fetching a non-existent type shows "no examples available", not an error
    - links to unsupported operations go to the live LTDB
    - no Flask server is required at any point

11. **Add Build Documentation**
    Update `README.md`:
    ```bash
    # Build the static mirror from compiled DBs
    cd etc/ltdb
    uv run python ../../scripts/freeze_ltdb.py --destination ../../docs
    cd ../..
    python scripts/build_ltdb_example_dbs.py --db-dir build/DBS

    # Verify locally
    python -m http.server -d docs 8000
    ```
    Document what the mirror does not support: live parse/generate, full
    corpus search, and the full example inventory (capped at 5 per lex-type,
    8 per other types).

12. **Optional GitHub Actions Integration**
    After the local build is stable, extend the release workflow to run both
    build scripts and push the output to GitHub Pages. Keep this separate from
    the first working implementation.

13. **TODO: Prefer Shared Example Sentences**
    The current example DB schema deduplicates stored examples after selection,
    but selection itself should also try to reuse sentences already chosen for
    the grammar. Improve `scripts/build_ltdb_example_dbs.py` so each type first
    looks for examples among already-selected sentences, then fills any
    remaining slots with new sentences. Coordinate lex-type examples and their
    secondary lex-entry examples so lex-entry coverage prefers sentences already
    selected for the parent lex-type or other nearby lexical types where
    possible. This should reduce the total SQLite size while preserving useful
    coverage.
