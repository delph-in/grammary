"""Tests for the generated static LTDB mirror."""

from __future__ import annotations

from html.parser import HTMLParser
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
