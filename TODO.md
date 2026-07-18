Make sure we link ltdb to other delph-in things, like matrix, delphin wiki, acknowledge country

## Grew-match snippets

Per-grammar grew snippet HTML files exist for all grammars that currently export
grew corpora: ERG, erg-dict, erg-singlish, SRG, Jacy, INDRA, KRG, NorSource,
wambaya_aux, wambaya_cmp, and zhong_zhs.  Examples in the `.req` files were
seeded from the compiled databases; refine them as needed.

## Treebanks

- SRG treebank: add more profiles from future SRG releases (update `trb` in
  grammary.toml).
- singlish-sg: no gold treebank yet; gold trees would require a treebanking
  campaign.  The ERG's built-in `singlish/` subdirectory has `data/trees/`
  (UWH_nolex_en profile) and is built automatically as `erg-singlish`.

## singlish-sg ACE compilation

`singlish-sg_trunk.dat` is 0 bytes because ACE reports `unify failed at
CAT HEAD PRD` when compiling `build/erg/singlish-sg/config.tdl`.  The
grammar was developed against an older ERG and has type-hierarchy
incompatibilities with ERG 2025.  The LTDB database (23 MB) compiled
successfully and is fully browsable.  Fix requires updating
`fundamentals_sg.tdl` and `lextypes_sg.tdl` to match current ERG types.
