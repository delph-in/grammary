# grammary
A collection of grammars, made as accessible as possible

## 🗂 Grammary Table

See [grammary-table.md](grammary-table.md) for a list of all grammars and their settings.

## Setup

You must install `subversion` to get the grammars that use svn

$ bash compile.sh


## Individual commands

### Download grammars with:

$ python scripts/download_grammars.py grammary.toml build

### Compile ltdb with

$ bash scripts/build-ltdb.sh build

### Compile grammars using ace

$ bash scripts/build-ace.sh build

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


