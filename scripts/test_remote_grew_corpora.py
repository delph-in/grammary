"""Unit tests for scripts/remote_grew_corpora.py."""

from __future__ import annotations

from pathlib import Path

from scripts import remote_grew_corpora as rgc


def _entry(directory: str) -> dict:
    return {"id": Path(directory).name, "directory": directory, "files": ["a.json"]}


def test_reroot_keeps_export_and_corpus_names() -> None:
    corpora = [_entry("/local/build/DBS/NorSource_14-Mar-26-grew/NorSource_trees")]

    rewritten, _ = rgc.reroot_corpora(corpora, "/home/bond/db-staging/grew")

    assert rewritten[0]["directory"] == (
        "/home/bond/db-staging/grew/NorSource_14-Mar-26-grew/NorSource_trees"
    )
    assert rewritten[0]["files"] == ["a.json"]


def test_reroot_lists_each_export_once_in_order() -> None:
    corpora = [
        _entry("/b/ERG_2025-grew/ERG_2025_trees"),
        _entry("/b/ERG_2025-grew/ERG_2025_dmrs"),
        _entry("/b/Norsyg_2608-grew/Norsyg_2608_trees"),
    ]

    _, exports = rgc.reroot_corpora(corpora, "/remote")

    assert exports == [Path("/b/ERG_2025-grew"), Path("/b/Norsyg_2608-grew")]


def test_reroot_does_not_mutate_input() -> None:
    corpora = [_entry("/b/X-grew/X_trees")]

    rgc.reroot_corpora(corpora, "/remote")

    assert corpora[0]["directory"] == "/b/X-grew/X_trees"
