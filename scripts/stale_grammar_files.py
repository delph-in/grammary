"""List grammar files superseded by a newer version of the same grammar.

Nothing in the build or deploy pipeline removes the files of an old grammar
version when its version string changes (``Norsyg_2602`` -> ``Norsyg_2608``),
so they pile up next to the new ones.  Given a manifest of the current
grammar stems (one per line, as written by ``push_to_compling.sh upload``)
this prints every file or grew export directory in the given directories
that belongs to an *older version of a current grammar*, one path per line.

A stem that is not in the manifest only counts as stale when a current stem
shares its grammar name (the part before the first underscore).  Grammars
that are simply absent from the manifest are left alone, so an incomplete
or empty manifest cannot flag the whole collection.

    python3 stale_grammar_files.py current_grammars.txt DIR [DIR ...]

Uses only the standard library: it is copied to the server and run there.
"""

from __future__ import annotations

import argparse
import logging
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


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("manifest", type=Path, help="current grammar stems")
    parser.add_argument("directories", type=Path, nargs="+", help="where to look")
    args = parser.parse_args()
    logging.basicConfig(format="%(levelname)s: %(message)s")

    for path in find_stale(args.directories, read_manifest(args.manifest)):
        print(path)


if __name__ == "__main__":
    main()
