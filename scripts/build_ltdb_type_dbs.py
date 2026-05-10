"""Build compact per-grammar type databases for the static LTDB mirror."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import orjson


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


def _holders(count: int) -> str:
    return ",".join("?" for _ in range(count))


def _words_for_lexids(
    src: sqlite3.Connection, lexids: list[str], limit: int
) -> dict[str, str]:
    if not lexids:
        return {}
    rows = src.execute(
        f"""
        SELECT lexid, word, freq
        FROM (
          SELECT lexid, word, COUNT(*) AS freq,
                 ROW_NUMBER() OVER (
                   PARTITION BY lexid
                   ORDER BY COUNT(*) DESC, word
                 ) AS rank
          FROM lexfreq
          WHERE lexid IN ({_holders(len(lexids))})
          GROUP BY lexid, word
        )
        WHERE rank <= ?
        ORDER BY lexid, rank
        """,
        lexids + [limit],
    ).fetchall()
    grouped: dict[str, list[dict[str, int | str]]] = {lexid: [] for lexid in lexids}
    for lexid, word, freq in rows:
        grouped[lexid].append({"word": word, "freq": freq})
    return {lexid: orjson.dumps(words).decode() for lexid, words in grouped.items()}


def copy_lex_type_words(
    src: sqlite3.Connection,
    out: sqlite3.Connection,
    lex_limit: int,
    word_limit: int,
) -> None:
    """Copy a bounded list of representative lexical entries per lexical type."""
    lex_types = [
        row[0]
        for row in out.execute(
            "SELECT typ FROM types WHERE status = 'lex-type' ORDER BY typ"
        )
    ]
    for typ in lex_types:
        rows = src.execute(
            """
            SELECT lex.lexid, lex.orth, COALESCE(SUM(lexfreq.freq), 0) AS freq
            FROM lex
            LEFT JOIN lexfreq ON lex.lexid = lexfreq.lexid
            WHERE lex.typ = ?
            GROUP BY lex.lexid, lex.orth
            ORDER BY freq DESC, lex.orth, lex.lexid
            LIMIT ?
            """,
            (typ, lex_limit),
        ).fetchall()
        words_by_lexid = _words_for_lexids(
            src, [lexid for lexid, _, _ in rows], word_limit
        )
        out.executemany(
            """
            INSERT INTO lex_type_words(typ, rank, lexid, orth, freq, words_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    typ,
                    rank,
                    lexid,
                    orth,
                    freq,
                    words_by_lexid.get(lexid, "[]"),
                )
                for rank, (lexid, orth, freq) in enumerate(rows, start=1)
            ],
        )


def build_one(
    src_path: Path,
    out_path: Path,
    lex_limit: int,
    word_limit: int,
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
        copy_lex_type_words(src, out, lex_limit, word_limit)
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
        help="Maximum lexical entries retained per lexical type.",
    )
    parser.add_argument(
        "--word-limit",
        type=int,
        default=5,
        help="Maximum observed word forms retained per lexical entry.",
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
        build_one(src_path, out_path, args.lex_limit, args.word_limit)
        print(f"{src_path.name}: wrote {out_path}")


if __name__ == "__main__":
    main()
