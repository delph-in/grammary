"""Build compact per-grammar type databases for the static LTDB mirror."""

from __future__ import annotations

import argparse
import gzip
import shutil
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_DIR = ROOT / "etc" / "ltdb" / "web" / "db"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "ltdb" / "db"
REQUIRED_SOURCE_TABLES = {"lex", "lexfreq", "meta", "sent", "tdl", "typfreq", "types"}
NON_LEX_STATUSES = ("lex-type", "rule", "lex-rule", "root")


def has_required_tables(path: Path) -> bool:
    """Return True if path looks like an LTDB source database."""
    if path.stat().st_size == 0:
        return False
    with sqlite3.connect(path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    return REQUIRED_SOURCE_TABLES.issubset(tables)


def create_schema(conn: sqlite3.Connection) -> None:
    """Create the compact type DB schema."""
    conn.executescript(
        """
        DROP TABLE IF EXISTS lex_type_words;
        DROP TABLE IF EXISTS types;
        DROP TABLE IF EXISTS meta;

        CREATE TABLE meta (
          att TEXT PRIMARY KEY,
          val TEXT
        );

        CREATE TABLE types (
          typ TEXT PRIMARY KEY,
          parents TEXT,
          children TEXT,
          cat TEXT,
          val TEXT,
          cont TEXT,
          definition TEXT,
          status TEXT,
          arity INTEGER,
          head INTEGER,
          lname TEXT,
          description TEXT,
          criteria TEXT,
          reference TEXT,
          todo TEXT,
          src TEXT,
          line INTEGER,
          kind TEXT,
          tdl TEXT,
          docstring TEXT,
          freq INTEGER DEFAULT 0,
          lex_count INTEGER DEFAULT 0
        );

        CREATE TABLE lex_type_words (
          typ TEXT NOT NULL,
          rank INTEGER NOT NULL,
          lexid TEXT,
          orth TEXT,
          freq INTEGER DEFAULT 0,
          words_json TEXT,
          PRIMARY KEY (typ, rank)
        );

        CREATE INDEX idx_types_status_typ ON types(status, typ);
        CREATE INDEX idx_lex_type_words_typ ON lex_type_words(typ);
        """
    )


def copy_meta(out: sqlite3.Connection) -> None:
    """Copy metadata used by the static grammar shell."""
    out.execute(
        """
        INSERT INTO meta(att, val)
        SELECT att, val FROM src.meta ORDER BY att
        """
    )


def copy_types(out: sqlite3.Connection) -> None:
    """Copy all non-lex-entry types with TDL and corpus frequencies."""
    out.execute(
        """
        WITH first_tdl AS (
          SELECT tdl.*
          FROM src.tdl AS tdl
          JOIN (
            SELECT typ, MIN(rowid) AS rowid
            FROM src.tdl
            GROUP BY typ
          ) AS chosen
            ON tdl.typ = chosen.typ AND tdl.rowid = chosen.rowid
        )
        INSERT INTO types(
          typ, parents, children, cat, val, cont, definition, status, arity,
          head, lname, description, criteria, reference, todo, src, line, kind,
          tdl, docstring, freq, lex_count
        )
        SELECT
          src.types.typ, parents, children, cat, val, cont, definition, status,
          arity, head, lname, description, criteria, reference, todo,
          tdl.src, tdl.line, tdl.kind, tdl.tdl, tdl.docstring,
          COALESCE(typfreq.freq, 0),
          CASE
            WHEN src.types.status = 'lex-type' THEN (
              SELECT COUNT(*) FROM src.lex WHERE lex.typ = src.types.typ
            )
            ELSE 0
          END
        FROM src.types
        LEFT JOIN first_tdl AS tdl ON src.types.typ = tdl.typ
        LEFT JOIN src.typfreq ON src.types.typ = typfreq.typ
        WHERE src.types.status NOT IN ('lex-entry', 'generic-lex-entry')
        ORDER BY src.types.status, src.types.typ
        """
    )


def copy_lex_type_words(
    out: sqlite3.Connection,
    lex_limit: int,
) -> None:
    """Copy a bounded list of representative lexical entries per grammar."""
    out.execute(
        """
        INSERT INTO lex_type_words(typ, rank, lexid, orth, freq, words_json)
        SELECT typ, rank, lexid, orth, freq, '[]'
        FROM (
          SELECT
            selected.typ,
            selected.lexid,
            selected.orth,
            selected.freq,
            ROW_NUMBER() OVER (
              PARTITION BY selected.typ
              ORDER BY selected.freq DESC, selected.orth, selected.lexid
            ) AS rank
          FROM (
            SELECT
              lex.typ,
              lex.lexid,
              lex.orth,
              COALESCE(SUM(lexfreq.freq), 0) AS freq
            FROM src.lex AS lex
            LEFT JOIN src.lexfreq AS lexfreq ON lex.lexid = lexfreq.lexid
            JOIN types ON types.typ = lex.typ AND types.status = 'lex-type'
            GROUP BY lex.typ, lex.lexid, lex.orth
            ORDER BY freq DESC, lex.orth, lex.lexid
            LIMIT ?
          ) AS selected
        )
        ORDER BY typ, rank
        """,
        (lex_limit,),
    )


def build_one(
    src_path: Path,
    out_path: Path,
    lex_limit: int,
) -> None:
    """Build one compact type database from one LTDB source database."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    src = sqlite3.connect(src_path)
    out = sqlite3.connect(tmp_path)
    try:
        create_schema(out)
        out.execute("ATTACH DATABASE ? AS src", (str(src_path),))
        copy_meta(out)
        copy_types(out)
        copy_lex_type_words(out, lex_limit)
        out.commit()
        out.execute("DETACH DATABASE src")
        out.execute("VACUUM")
    finally:
        src.close()
        out.close()
    tmp_path.replace(out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-dir",
        type=Path,
        default=DEFAULT_DB_DIR,
        help="Directory containing LTDB source .db files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for compact grammar DBs.",
    )
    parser.add_argument(
        "--lex-limit",
        type=int,
        default=10000,
        help="Maximum lexical entries retained per grammar.",
    )
    parser.add_argument(
        "--gzip",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Gzip output files (default: on).",
    )
    parser.add_argument(
        "grammars",
        nargs="*",
        help="Optional grammar stems or .db filenames to build.",
    )
    args = parser.parse_args()

    wanted = {g[:-3] if g.endswith(".db") else g for g in args.grammars}
    for src_path in sorted(args.db_dir.glob("*.db")):
        if wanted and src_path.stem not in wanted:
            continue
        if not has_required_tables(src_path):
            print(f"{src_path.name}: skipped, not an LTDB source database")
            continue
        out_path = args.output_dir / f"{src_path.stem}.grammar.sqlite"
        build_one(src_path, out_path, args.lex_limit)
        if args.gzip:
            gz_path = Path(str(out_path) + ".gz")
            with open(out_path, "rb") as f_in, gzip.open(gz_path, "wb", compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)
            out_path.unlink()
            print(f"{src_path.name}: {gz_path.stat().st_size / 1048576:.1f} MiB (gzipped)")
        else:
            print(f"{src_path.name}: {out_path.stat().st_size / 1048576:.1f} MiB")


if __name__ == "__main__":
    main()
