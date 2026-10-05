# The DELPH-IN Grammary: a Curated Repository of Grammars and Treebanks


A collection of grammars, made as accessible as possible. 

The grammars are processed with the <a href='https://github.com/fcbond/ltdb/'>Linguistic Type Data-Base (LTDB)</> and can be accessed here: <https://compling.upol.cz/ltdb>, where you can browse the grammar and interactively parse (and for some grammars generate).

Gathered together and revived by Francis Bond and Dan Flickinger.


## 🗂 Grammary Table

See [docs/grammary.md](docs/grammary.md) for a list of all the grammar repositories (made from grammary.toml).

See [docs/summary.md](docs/summary.md) for a list of all the grammars, with their sizes and links to the compiled ltdb (db) and ace (dat) files.

## Citations

Francis Bond and Dan Flickinger (2026). The DELPH-IN Grammary: a Curated Repository of Grammars and Treebanks. In *15th International Conference on Language Resources and Evaluation* (LREC 2026)

Francis Bond and Dan Flickinger (2026). The DELPH-IN Grammary: a Curated Repository of Grammars and Treebanks (2026.03.15) [Data set]. Zenodo. <https://doi.org/10.5281/zenodo.19040902>

## Releases

Release tags are date-based: `YYYY.MM` (monthly) or `YYYY.MM.DD` (daily).
Pushing a tag triggers the [release workflow](.github/workflows/release.yml), which:

1. Runs `compile.sh` to download all grammars and build the ltdb databases.
2. Deletes any downloaded archives left in `build/` (e.g. `build/burger.7z`)
   before creating the snapshot — so they are not included in the archive.
3. Creates `grammary-{tag}.tar.xz` (xz-compressed for better ratio than gz)
   containing the source code and all compiled databases in `build/DBS/`.
4. Attaches each `*.db` file individually for selective download.
5. Generates `summary-{tag}.md` — a Markdown table of grammar statistics.

```bash
git tag 2026.03.15
git push origin 2026.03.15
```

After the release you should add `grammary-{tag}.tar.xz` to Zenodo by hand.

The build is slow (~hours) because all grammars are downloaded and compiled from
scratch. Re-running the workflow for the same tag is safe: old archives on the
release are replaced before uploading.

To generate a summary locally:

```bash
python scripts/make_summary.py --db-dir build/DBS --tag 2026.03
```

## Setup

Install system prerequisites first, then compile:

```bash
bash setup.sh           # installs git, svn, wget, rsync, uv on Ubuntu/Debian
bash setup.sh --grew-match   # also installs opam + grew for structural search
bash compile.sh
```

`setup.sh` installs:
- `git`, `subversion`, `curl`, `wget`, `rsync`, `build-essential` (via apt)
- `uv` (Python package manager, user-level)
- `--grew-match`: `opam` + an OCaml switch with `grew` and `dune`

ACE (the grammar compiler) is downloaded automatically by `compile.sh` via
`scripts/setup_ace.py` — no manual installation needed.


## Individual commands

### Download grammars with:

$ python scripts/download_grammars.py grammary.toml build

### Compile ltdb (and ACE .dat files) with

$ bash scripts/build-ltdb.sh build

ACE is downloaded automatically on first run. Both `.db` and `.dat` files are
written to `build/DBS/` and copied to `etc/ltdb/web/db/`.

### Build the static LTDB mirror

The GitHub Pages fallback is generated under `docs/ltdb/` from the compiled
databases in `build/DBS/`. The static pages contain grammar/type metadata; type
examples are loaded lazily in the browser from compact per-grammar SQLite files.

```bash
cd etc/ltdb
uv run python ../../scripts/freeze_ltdb.py --destination ../../docs
cd ../..
python scripts/build_ltdb_example_dbs.py --db-dir build/DBS
```

To test the mirror locally:

```bash
python -m http.server -d docs 8000
```

The mirror does not support live parse/generate, full corpus search, or the full
example inventory. Unsupported operations link back to the live LTDB.

### grammary.toml

Grammars are listed in the file `grammary.toml`

 * `vcs` — how to download the grammar: `git clone`, `svn co`, or a direct URL
 * `trb` — separate treebank archive (`wget <url>`), extracted to `tsdb/`
 * `trb_gold` — directory name within the treebank archive to link as `tsdb/gold`
   (needed when the archive contains multiple top-level directories, as with SRG)
 * `parent` — grammar that this one must live inside; cloned to
   `build/<parent>/<name>/` so relative TDL `../` paths resolve correctly
   (e.g. `singlish-sg` lives inside `erg/`)

A project will be used to make as many grammars as it has METADATA files.
Grammars that set `parent` are cloned into `build/<parent>/<name>/` so that
relative paths in their config files can reach the parent grammar's resources.

#### size

Very rough distinctions so that people can have a general idea about how big the grammar is.  More detail can be gotten from the ltdb.

* large: lexicon above 30,000
* medium: lexicon above 5,000
* small: lexicon above 1,000 
* matrix: matrix derived grammar with minimal changes


### Grew-match: searching trees and DMRS

After compilation, the gold treebanks are exported as grew JSON corpora under
`build/DBS/`.  The following grammars currently export treebank corpora:

| Grammar | Trees | Notes |
|---------|------:|-------|
| ERG | 97,650 | main ERG Redwoods treebank |
| erg-dict | 1,508 | ERG dictionary variant |
| erg-singlish | 44 | Singlish sub-grammar of the ERG |
| SRG | 2,677 | Spanish; separate `trb` archive in `grammary.toml` |
| Jacy | 8,797 | Japanese Hinoki treebank |
| INDRA | 2,861 | Indonesian (JATI + Cendana) |
| KRG | 22 | Korean |
| NorSource | 1,202 | Norwegian |
| wambaya\_aux | 718 | Wambaya aux+vc grammar |
| wambaya\_cmp | 717 | Wambaya arg-comp grammar |
| zhong-zhs | 681 | Mandarin Chinese (Simplified) |

To start grew-match alongside the LTDB (requires `--grew-match` setup above):

```bash
cd etc/ltdb
bash run.sh --grew-match
```

Each grammar corpus gets its own snippet pane loaded from
`grew_snippets/<SHORT_GRAMMAR_NAME>.html` (stored in grammary root, synced
into `etc/ltdb/etc/grew_snippets/` by `compile.sh`), with example queries
tailored to that grammar's rule and predicate names.  The generic fallback is
`_default.html`.

For full setup instructions see `etc/ltdb/doc/grew-match.md`.
