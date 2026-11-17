"""List grammar files superseded by a newer version of the same grammar.

Nothing in the build or deploy pipeline removes the files of an old grammar
version when its version string changes (``Norsyg_2602`` -> ``Norsyg_2608``),
so they pile up next to the new ones.  This prints every file or grew
export directory in the given directories that belongs to an *older version
of a current grammar*, one path per line.  The current versions come from
either

* ``--manifest FILE``: grammar stems, one per line (as written for the
  server by ``push_to_compling.sh upload``), or
* ``--newest-in DIR``: the most recently built ``.db`` for each
  ``SHORT_GRAMMAR_NAME`` in *DIR* (for the local ``build/DBS``, where build
  times are meaningful).

A stem that is not in the manifest only counts as stale when a current stem
shares its grammar name (the part before the first underscore).  Grammars
that are simply absent from the manifest are left alone, so an incomplete
or empty manifest cannot flag the whole collection.

    python3 stale_grammar_files.py --manifest current_grammars.txt DIR [DIR ...]
    python3 stale_grammar_files.py --newest-in build/DBS build/DBS etc/ltdb/web/db

Uses only the standard library: it is copied to the server and run there.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

FILE_SUFFIXES = (".db", ".dat", ".log")
LOG_TAGS = ("-ace", "-grew")
GREW_DIR_SUFFIX = "-grew"


def grammar_stem(path: Path) -> str | None:
    """Return the grammar stem a build artefact belongs to.

    Args:
        path: A file or directory found next to the grammar databases.

    Returns:
        The stem (e.g. ``Norsyg_2608`` for ``Norsyg_2608-ace.log`` or
        ``Norsyg_2608-grew/``), or None if *path* is not a grammar artefact.
    """
    name = path.name
    if path.is_dir():
        if name.endswith(GREW_DIR_SUFFIX):
            return name.removesuffix(GREW_DIR_SUFFIX)
        return None
    for suffix in FILE_SUFFIXES:
        if not name.endswith(suffix):
            continue
        stem = name.removesuffix(suffix)
        if suffix == ".log":
            for tag in LOG_TAGS:
                stem = stem.removesuffix(tag)
        return stem
    return None


def grammar_name(stem: str) -> str:
    """Return the grammar-name part of *stem* (before the first underscore)."""
    return stem.split("_", 1)[0]


def find_stale(directories: list[Path], current: set[str]) -> list[Path]:
    """Find artefacts of superseded grammar versions.

    Args:
        directories: Directories to scan (not recursively).  Missing or
            unreadable directories are skipped with a logged error.
        current: Stems of the grammar versions that should be kept.

    Returns:
        Sorted paths whose stem is not current but whose grammar name
        matches a current stem.
    """
    current_names = {grammar_name(stem) for stem in current}
    stale: list[Path] = []
    for directory in directories:
        try:
            entries = sorted(directory.iterdir())
        except OSError as exc:
            logger.error("cannot scan %s: %s", directory, exc)
            continue
        for entry in entries:
            stem = grammar_stem(entry)
            if stem is None or stem in current:
                continue
            if grammar_name(stem) in current_names:
                stale.append(entry)
    return stale


def read_manifest(path: Path) -> set[str]:
    """Read the current grammar stems from *path*, ignoring blank lines."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip()}


def short_grammar_name(db: Path) -> str | None:
    """Return the ``SHORT_GRAMMAR_NAME`` recorded in a grammar database.

    Args:
        db: Path to a grammar ``.db`` file.

    Returns:
        The name, or None if *db* is not a readable grammar database
        (e.g. the empty placeholder left by a failed build).
    """
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            row = conn.execute(
                "SELECT val FROM meta WHERE att = 'SHORT_GRAMMAR_NAME'"
            ).fetchone()
    except sqlite3.Error:
        return None
    return row[0] if row and row[0] else None


def newest_stems(directory: Path) -> set[str]:
    """Return the stem of the newest database for each grammar in *directory*.

    Databases are grouped by ``SHORT_GRAMMAR_NAME`` and compared by
    modification time; unreadable databases are ignored.

    Args:
        directory: Build output directory holding the ``.db`` files.

    Returns:
        One stem per grammar name.
    """
    newest: dict[str, Path] = {}
    for db in directory.glob("*.db"):
        name = short_grammar_name(db)
        if name is None:
            continue
        best = newest.get(name)
        if best is None or db.stat().st_mtime > best.stat().st_mtime:
            newest[name] = db
    return {db.stem for db in newest.values()}


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", type=Path, help="file of current stems")
    source.add_argument(
        "--newest-in", type=Path, help="directory whose newest .db files are current"
    )
    parser.add_argument("directories", type=Path, nargs="+", help="where to look")
    args = parser.parse_args()
    logging.basicConfig(format="%(levelname)s: %(message)s")

    if args.manifest:
        current = read_manifest(args.manifest)
    else:
        current = newest_stems(args.newest_in)
    for path in find_stale(args.directories, current):
        print(path)


if __name__ == "__main__":
    main()
