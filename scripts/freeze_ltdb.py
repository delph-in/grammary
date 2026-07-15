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
LTDB_STATIC_JS = LTDB / "web" / "static" / "js"
MIRROR_ASSETS = ROOT / "assets" / "ltdb"

# JS renderers that live in the ltdb repo and are copied from there.
# Everything else in assets/ltdb/ (sql-wasm, mrs2dmrs) stays in grammary.
_LTDB_JS = ["ltdb-tree.js", "ltdb-mrs.js", "ltdb-examples.js"]


def import_ltdb():
    """Import the vendored LTDB app after putting it on sys.path."""
    sys.path.insert(0, str(LTDB))
    from flask_frozen import Freezer
    from flask_frozen import MissingURLGeneratorWarning
    from web import create_app

    return create_app, Freezer, MissingURLGeneratorWarning


def grammar_stems(db_dir: Path) -> list[str]:
    """Return available grammar stems from an LTDB db directory."""
    stems = []
    for path in sorted(db_dir.glob("*.db")):
        if path.stat().st_size == 0:
            continue
        with sqlite3.connect(path) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        if {"gold", "lexfreq", "meta", "sent", "types"}.issubset(tables):
            stems.append(path.stem)
    return stems


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
    type_mode: str,
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
    def mirror_type_shell():
        if type_mode == "shell":
            yield {}

    @freezer.register_generator
    def mirror_type():
        if type_mode == "shell":
            return
        for grm in grammar_stems(db_dir):
            for query in mirror_type_rows(
                db_dir / f"{grm}.db", statuses, include_lex_entries
            ):
                yield {"grm": grm, "query": query}


def copy_mirror_assets(destination: Path) -> None:
    """Copy mirror-only JS/CSS assets into docs/ltdb/assets.

    JS renderers (ltdb-*.js) are sourced from the vendored ltdb repo so there
    is a single canonical copy.  sql-wasm and mrs2dmrs come from assets/ltdb/.
    """
    out = destination / "ltdb" / "assets"
    out.mkdir(parents=True, exist_ok=True)

    # ltdb JS renderers — authoritative copy lives in etc/ltdb/web/static/js/
    for name in _LTDB_JS:
        src = LTDB_STATIC_JS / name
        if src.is_file():
            shutil.copy2(src, out / name)
        else:
            print(f"WARNING: {src} not found; run build-ltdb.sh first", file=sys.stderr)

    # Remaining assets (sql-wasm, mrs2dmrs) kept in assets/ltdb/
    if MIRROR_ASSETS.is_dir():
        for asset in MIRROR_ASSETS.iterdir():
            if asset.is_file() and asset.name not in _LTDB_JS:
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
    parser.add_argument(
        "--type-mode",
        choices=("shell", "static"),
        default="shell",
        help=(
            "Use one client-rendered type.html shell, or freeze individual type "
            "pages. Default: shell."
        ),
    )
    args = parser.parse_args()

    if not args.db_dir.is_dir():
        parser.error(f"database directory not found: {args.db_dir}")
    args.db_dir = args.db_dir.resolve()
    args.destination = args.destination.resolve()

    os.environ["FULL_LTDB_BASE_URL"] = args.full_ltdb_base_url
    all_non_lex = args.statuses == "all-non-lex"
    statuses = (
        set()
        if all_non_lex
        else {s.strip() for s in args.statuses.split(",") if s.strip()}
    )
    os.environ["STATIC_MIRROR_STATUSES"] = ",".join(sorted(statuses))
    os.environ["STATIC_MIRROR_ALL_NON_LEX"] = "1" if all_non_lex else "0"
    os.environ["STATIC_MIRROR_DYNAMIC_TYPES"] = (
        "1" if args.type_mode == "shell" else "0"
    )
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
    configure_freezer(
        app,
        freezer,
        args.db_dir,
        statuses,
        args.include_lex_entries,
        args.type_mode,
    )
    freezer.freeze()
    copy_mirror_assets(args.destination)


if __name__ == "__main__":
    main()
