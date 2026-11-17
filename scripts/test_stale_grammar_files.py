"""Unit tests for scripts/stale_grammar_files.py."""

from __future__ import annotations

from pathlib import Path

from scripts import stale_grammar_files as sgf

CURRENT = {"Norsyg_2608", "ERG_2025", "erg-dict_2025"}


def _populate(directory: Path, names: list[str]) -> None:
    for name in names:
        if name.endswith("-grew"):
            (directory / name).mkdir()
        else:
            (directory / name).write_text("x", encoding="utf-8")


def test_old_version_of_current_grammar_is_stale(tmp_path: Path) -> None:
    _populate(
        tmp_path,
        [
            "Norsyg_2602.db",
            "Norsyg_2602.dat",
            "Norsyg_2602.log",
            "Norsyg_2602-ace.log",
            "Norsyg_2602-grew",
            "Norsyg_2608.db",
            "Norsyg_2608-ace.log",
            "Norsyg_2608-grew",
        ],
    )

    stale = sgf.find_stale([tmp_path], CURRENT)

    assert [p.name for p in stale] == [
        "Norsyg_2602-ace.log",
        "Norsyg_2602-grew",
        "Norsyg_2602.dat",
        "Norsyg_2602.db",
        "Norsyg_2602.log",
    ]


def test_grammar_absent_from_manifest_is_left_alone(tmp_path: Path) -> None:
    _populate(tmp_path, ["Jacy_2020.07.20.db", "Jacy_2020.07.20-grew"])

    assert sgf.find_stale([tmp_path], CURRENT) == []


def test_empty_manifest_flags_nothing(tmp_path: Path) -> None:
    _populate(tmp_path, ["Norsyg_2602.db", "ERG_2025.db"])

    assert sgf.find_stale([tmp_path], set()) == []


def test_sub_grammars_are_distinct_from_their_parent(tmp_path: Path) -> None:
    # "erg-mal" is not "ERG" or "erg-dict", so its files are not stale
    _populate(tmp_path, ["erg-mal_2025.db", "ERG_2025.db", "erg-dict_2024.db"])

    stale = sgf.find_stale([tmp_path], CURRENT)

    assert [p.name for p in stale] == ["erg-dict_2024.db"]


def test_non_grammar_entries_are_ignored(tmp_path: Path) -> None:
    _populate(tmp_path, ["grew_corpora.json", "current_grammars.txt"])
    (tmp_path / "Norsyg_2602").mkdir()

    assert sgf.find_stale([tmp_path], CURRENT) == []


def test_missing_directory_is_skipped(tmp_path: Path) -> None:
    _populate(tmp_path, ["Norsyg_2602.db"])

    stale = sgf.find_stale([tmp_path / "absent", tmp_path], CURRENT)

    assert [p.name for p in stale] == ["Norsyg_2602.db"]


def test_read_manifest_ignores_blank_lines(tmp_path: Path) -> None:
    manifest = tmp_path / "current_grammars.txt"
    manifest.write_text("Norsyg_2608\n\n ERG_2025 \n", encoding="utf-8")

    assert sgf.read_manifest(manifest) == {"Norsyg_2608", "ERG_2025"}
