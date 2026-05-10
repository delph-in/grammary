from __future__ import annotations

import sqlite3
from pathlib import Path

from build_ltdb_type_dbs import build_one, has_required_tables


def make_source(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE meta(att TEXT, val TEXT);
            CREATE TABLE types (
              typ TEXT primary key,
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
              todo TEXT
            );
            CREATE TABLE tdl (
              typ TEXT,
              src TEXT,
              line INTEGER,
              kind TEXT,
              tdl TEXT,
              docstring TEXT
            );
            CREATE TABLE typfreq(typ TEXT, freq INTEGER DEFAULT 0);
            CREATE TABLE lex (
              lexid TEXT primary key,
              typ TEXT,
              orth TEXT,
              pred TEXT,
              altpred TEXT,
              carg TEXT,
              altcarg TEXT,
              docstring TEXT
            );
            CREATE TABLE lexfreq(lexid TEXT, word TEXT, freq INTEGER DEFAULT 0);
            CREATE TABLE sent(
              profile TEXT, sid INTEGER, wid INTEGER, word TEXT, lexid TEXT
            );
            """
        )
        conn.executemany(
            "INSERT INTO meta(att, val) VALUES (?, ?)",
            [("GRAMMAR_NAME", "Test Grammar"), ("LICENSE", "MIT")],
        )
        conn.executemany(
            """
            INSERT INTO types(
              typ, parents, children, cat, val, cont, definition, status, arity,
              head, lname, description, criteria, reference, todo
            )
            VALUES (?, ?, ?, '', '', '', '', ?, 0, 0, ?, ?, '', '', '')
            """,
            [
                ("root", "", "rule n_le", "root", "Root", "root description"),
                ("rule", "root", "", "rule", "Rule", "rule description"),
                ("n_le", "root", "dog_n_1", "lex-type", "Noun", "noun type"),
                ("dog_n_1", "n_le", "", "lex-entry", "dog", "dog entry"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO tdl(typ, src, line, kind, tdl, docstring)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "root",
                    "root.tdl",
                    1,
                    "TypeDefinition",
                    "root := *top*.",
                    "root doc",
                ),
                (
                    "rule",
                    "rules.tdl",
                    2,
                    "TypeDefinition",
                    "rule := root.",
                    "rule doc",
                ),
                (
                    "n_le",
                    "lex.tdl",
                    3,
                    "TypeDefinition",
                    "n_le := root.",
                    "noun doc",
                ),
                (
                    "dog_n_1",
                    "lex.tdl",
                    4,
                    "TypeDefinition",
                    "dog_n_1 := n_le.",
                    "dog doc",
                ),
            ],
        )
        conn.executemany(
            "INSERT INTO typfreq(typ, freq) VALUES (?, ?)",
            [("root", 2), ("rule", 1), ("n_le", 1)],
        )
        conn.execute(
            "INSERT INTO lex(lexid, typ, orth) VALUES ('dog_n_1', 'n_le', 'dog')"
        )
        conn.executemany(
            "INSERT INTO lexfreq(lexid, word, freq) VALUES (?, ?, ?)",
            [("dog_n_1", "dog", 3), ("dog_n_1", "dogs", 2)],
        )
        conn.executemany(
            """
            INSERT INTO sent(profile, sid, wid, word, lexid)
            VALUES (?, ?, ?, ?, ?)
            """,
            [("p", 1, 0, "dog", "dog_n_1"), ("p", 2, 0, "dogs", "dog_n_1")],
        )


def test_has_required_tables_rejects_empty_db(tmp_path: Path) -> None:
    db = tmp_path / "empty.db"
    db.touch()
    assert not has_required_tables(db)


def test_build_one_copies_non_lex_types_and_limited_lex_words(tmp_path: Path) -> None:
    src = tmp_path / "source.db"
    out = tmp_path / "compact.sqlite"
    make_source(src)

    build_one(src, out, lex_limit=1, word_limit=1)

    with sqlite3.connect(out) as conn:
        types = conn.execute(
            """
            SELECT typ, status, freq, lex_count
            FROM types
            ORDER BY typ
            """
        ).fetchall()
        assert types == [
            ("n_le", "lex-type", 1, 1),
            ("root", "root", 2, 0),
            ("rule", "rule", 1, 0),
        ]
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM types WHERE typ = 'dog_n_1'"
            ).fetchone()[0]
            == 0
        )
        row = conn.execute(
            "SELECT typ, lexid, orth, freq, words_json FROM lex_type_words"
        ).fetchone()
        assert row[:4] == ("n_le", "dog_n_1", "dog", 5)
        assert '"dog"' in row[4]
        assert '"dogs"' not in row[4]
