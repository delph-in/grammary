"""Build a static LTDB mirror with Frozen-Flask.

The live LTDB app is session driven: users select a grammar and then browse
relative routes such as /grammar.html and /type/foo.  This freezer uses the
mirror routes under /ltdb/ so each grammar has stable static URLs.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
import warnings
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LTDB = ROOT / "etc" / "ltdb"
WEB_DB = LTDB / "web" / "db"
MIRROR_ASSETS = ROOT / "assets" / "ltdb"


def import_ltdb():
    """Import the vendored LTDB app after putting it on sys.path."""
    sys.path.insert(0, str(LTDB))
    from flask_frozen import Freezer
    from flask_frozen import MissingURLGeneratorWarning
    from web import create_app

    return create_app, Freezer, MissingURLGeneratorWarning


def grammar_stems(db_dir: Path) -> list[str]:
    """Return available grammar stems from an LTDB db directory."""
    return sorted(p.stem for p in db_dir.glob("*.db"))


def mirror_type_rows(
    db_path: Path, statuses: set[str], include_lex_entries: bool
) -> list[str]:
    """Return type names worth freezing for one grammar."""
    with sqlite3.connect(db_path) as conn:
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            rows = conn.execute(
                f"SELECT typ FROM types WHERE status IN ({placeholders}) "
                "ORDER BY status, typ",
                sorted(statuses),
            ).fetchall()
        elif not include_lex_entries:
            rows = conn.execute(
                "SELECT typ FROM types "
                "WHERE status NOT IN ('lex-entry', 'generic-lex-entry') "
                "ORDER BY status, typ"
            ).fetchall()
        else:
            rows = conn.execute("SELECT typ FROM types ORDER BY status, typ").fetchall()
    return [row[0] for row in rows]


def configure_freezer(
    app,
    freezer,
    db_dir: Path,
    statuses: set[str],
    include_lex_entries: bool,
) -> None:
    """Register Frozen-Flask URL generators for static LTDB mirror routes."""

    @freezer.register_generator
    def mirror_home():
        yield {}

    @freezer.register_generator
    def mirror_grammar():
        for grm in grammar_stems(db_dir):
            yield {"grm": grm}

    @freezer.register_generator
    def mirror_rules():
        for grm in grammar_stems(db_dir):
            yield {"grm": grm}

    @freezer.register_generator
    def mirror_ltypes():
        for grm in grammar_stems(db_dir):
            yield {"grm": grm}

    @freezer.register_generator
    def mirror_type():
        for grm in grammar_stems(db_dir):
            for query in mirror_type_rows(
                db_dir / f"{grm}.db", statuses, include_lex_entries
            ):
                yield {"grm": grm, "query": query}


def copy_mirror_assets(destination: Path) -> None:
    """Copy mirror-only JS/CSS assets into docs/ltdb/assets."""
    if not MIRROR_ASSETS.is_dir():
        return
    out = destination / "ltdb" / "assets"
    out.mkdir(parents=True, exist_ok=True)
    for asset in MIRROR_ASSETS.iterdir():
        if asset.is_file():
            shutil.copy2(asset, out / asset.name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination",
        type=Path,
        default=ROOT / "docs",
        help="Frozen-Flask destination root. Default: docs/",
    )
    parser.add_argument(
        "--db-dir",
        type=Path,
        default=WEB_DB,
        help="Directory containing LTDB .db files. Default: etc/ltdb/web/db",
    )
    parser.add_argument(
        "--full-ltdb-base-url",
        default="https://compling.upol.cz/ltdb",
        help="Live LTDB URL linked from the static mirror.",
    )
    parser.add_argument(
        "--include-lex-entries",
        action="store_true",
        help="Also freeze lex-entry/generic-lex-entry pages. This is very large.",
    )
    parser.add_argument(
        "--statuses",
        default="lex-type,rule,lex-rule,root",
        help=(
            "Comma-separated type statuses to freeze. Default: "
            "lex-type,rule,lex-rule,root. Use 'all-non-lex' to freeze every "
            "non-lex-entry type."
        ),
    )
    args = parser.parse_args()

    if not args.db_dir.is_dir():
        parser.error(f"database directory not found: {args.db_dir}")
    args.db_dir = args.db_dir.resolve()
    args.destination = args.destination.resolve()

    os.environ["FULL_LTDB_BASE_URL"] = args.full_ltdb_base_url
    statuses = (
        set()
        if args.statuses == "all-non-lex"
        else {s.strip() for s in args.statuses.split(",") if s.strip()}
    )
    os.environ["STATIC_MIRROR_STATUSES"] = ",".join(sorted(statuses))
    create_app, Freezer, missing_url_warning = import_ltdb()
    warnings.filterwarnings("ignore", category=missing_url_warning)
    app = create_app()
    app.config.update(
        FREEZER_DESTINATION=str(args.destination),
        FREEZER_RELATIVE_URLS=True,
        FREEZER_REMOVE_EXTRA_FILES=False,
        FREEZER_IGNORE_MIMETYPE_WARNINGS=True,
    )

    freezer = Freezer(app, with_no_argument_rules=False, log_url_for=False)
    configure_freezer(app, freezer, args.db_dir, statuses, args.include_lex_entries)
    freezer.freeze()
    copy_mirror_assets(args.destination)


if __name__ == "__main__":
    main()
