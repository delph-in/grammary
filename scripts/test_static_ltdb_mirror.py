"""Tests for the generated static LTDB mirror."""

from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
MIRROR_ROOT = ROOT / "docs" / "ltdb"


class GrammarHrefParser(HTMLParser):
    """Collect grammar row links from the frozen mirror index."""

    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "tr":
            return
        values = dict(attrs)
        if values.get("data-grm") and values.get("data-href"):
            self.hrefs.append(values["data-href"])


def test_static_ltdb_index_grammar_hrefs_exist() -> None:
    """Every grammar row in the frozen index should point at an existing page."""
    index = MIRROR_ROOT / "index.html"
    parser = GrammarHrefParser()
    parser.feed(index.read_text(encoding="utf-8"))

    assert parser.hrefs, "no grammar data-href values found in docs/ltdb/index.html"
    for href in parser.hrefs:
        assert not href.startswith("index.html"), href
        assert "index.html" not in href, href
        assert href.endswith("/grammar.html"), href
        assert (MIRROR_ROOT / href).is_file(), href


def test_ltdb_tree_parser_and_layout() -> None:
    """Exercise the browser tree parser and vertical layout invariants."""
    subprocess.run(["node", "scripts/test_ltdb_tree.js"], cwd=ROOT, check=True)


@pytest.mark.slow
def test_static_ltdb_index_html5_validates() -> None:
    """Run the Nu HTML checker wrapper on the frozen index page."""
    subprocess.run(
        [
            "uvx",
            "--from",
            "html5validator-2",
            "html5validator",
            "--root",
            str(MIRROR_ROOT),
            "--match",
            "index.html",
            "--format",
            "text",
        ],
        check=True,
    )


@pytest.mark.slow
def test_static_ltdb_derivations_parse_as_browser_trees(tmp_path: Path) -> None:
    """Run every stored raw derivation through the browser-side JS parser."""
    derivs = tmp_path / "derivations.jsonl"
    count = 0
    with derivs.open("w", encoding="utf-8") as out:
        for db_path in sorted((MIRROR_ROOT / "db").glob("*.examples.sqlite")):
            import sqlite3

            with sqlite3.connect(db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT example_id, deriv
                    FROM examples
                    WHERE deriv IS NOT NULL AND deriv != ''
                    ORDER BY example_id
                    """
                )
                for example_id, deriv in rows:
                    out.write(
                        json.dumps(
                            {
                                "db": db_path.name,
                                "example_id": example_id,
                                "deriv": deriv,
                            }
                        )
                    )
                    out.write("\n")
                    count += 1

    assert count > 0
    subprocess.run(
        ["node", "scripts/validate_ltdb_derivations.js", str(derivs)],
        cwd=ROOT,
        check=True,
    )
