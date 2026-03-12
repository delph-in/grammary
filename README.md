# grammary
A collection of grammars, made as accessible as possible

## 🗂 Grammary Table

See [grammary-table.md](grammary-table.md) for a list of all grammars and their settings.

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
git tag 2026.03
git push origin 2026.03
```

The build is slow (~hours) because all grammars are downloaded and compiled from
scratch. Re-running the workflow for the same tag is safe: old archives on the
release are replaced before uploading.

To generate a summary locally:

```bash
python scripts/make_summary.py --db-dir build/DBS --tag 2026.03
```

## Setup

You must install `subversion` to get the grammars that use svn

$ bash compile.sh


## Individual commands

### Download grammars with:

$ python scripts/download_grammars.py grammary.toml build

### Compile ltdb (and ACE .dat files) with

$ bash scripts/build-ltdb.sh build

ACE is downloaded automatically on first run. Both `.db` and `.dat` files are
written to `build/DBS/` and copied to `etc/ltdb/web/db/`.

### grammary.toml

Grammars are listed in the file `grammary.toml`

 * `vcs` is the way to download the grammar
 * `tree` is the treebank (if it is seperate, we only handle this for the SRG)

A project will be used to make as many grammars as it has METADATA files

#### size

Very rough distinctions so that people can have a general idea about how big the grammar is.  More detail can be gotten from the ltdb.

* large: lexicon above 30,000
* medium: lexicon above 5,000
* small: lexicon above 1,000 
* matrix: matrix derived grammar with minimal changes


### Make grew corpora

*Unfinished*  We are working on making the trees and semantic searchable with grew

First install `grew`: https://grew.fr/usage/install/
and `grewpy`: https://grew.fr/usage/python/


