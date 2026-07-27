"""Tests for scripts/build_ltdb_example_dbs.py."""

from __future__ import annotations

import sqlite3

from build_ltdb_example_dbs import (
    build_one,
    calculate_offset_limit,
    create_schema,
    get_sentence_data,
    has_required_tables,
    selected_by_lexids,
    selected_by_type,
    shared_example_selection,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_src(
    sentences: list[dict],
    types: list[dict] | None = None,
    lexind: list[dict] | None = None,
) -> sqlite3.Connection:
    """Create an in-memory source database resembling the LTDB schema.

    Args:
        sentences: List of dicts with keys: profile, sid, wid, word, lexid.
        types: Optional list of dicts with keys: typ, status.
        lexind: Optional list of dicts with keys: profile, sid, lexid, kara,
            made. If omitted, one single-token row (kara=wid, made=wid+1) is
            derived per sentence entry with a lexid -- the common case where
            the lexical entry's raw-token span is the same as its wid. Pass
            this explicitly to test a multiword entry, whose (kara, made)
            span is wider than one and diverges from wid.

    Returns:
        Open in-memory SQLite connection.
    """
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE types (typ TEXT PRIMARY KEY, status TEXT NOT NULL);
        CREATE TABLE lex (lexid TEXT NOT NULL, typ TEXT NOT NULL);
        CREATE TABLE lexfreq (lexid TEXT PRIMARY KEY, freq INTEGER);
        CREATE TABLE sent (
            profile TEXT NOT NULL,
            sid     INTEGER NOT NULL,
            wid     INTEGER NOT NULL,
            word    TEXT NOT NULL,
            lexid   TEXT,
            PRIMARY KEY (profile, sid, wid)
        );
        CREATE TABLE lexind (
            profile TEXT    NOT NULL,
            sid     INTEGER NOT NULL,
            lexid   TEXT    NOT NULL,
            kara    INTEGER,
            made    INTEGER
        );
        CREATE TABLE typind (
            profile TEXT    NOT NULL,
            sid     INTEGER NOT NULL,
            typ     TEXT    NOT NULL,
            kara    INTEGER,
            made    INTEGER
        );
        CREATE TABLE gold (
            profile TEXT    NOT NULL,
            sid     INTEGER NOT NULL,
            sent    TEXT,
            deriv   TEXT,
            mrs     TEXT,
            PRIMARY KEY (profile, sid)
        );
        """
    )
    for s in sentences:
        conn.execute(
            "INSERT INTO sent (profile, sid, wid, word, lexid) VALUES (?,?,?,?,?)",
            (s["profile"], s["sid"], s["wid"], s["word"], s.get("lexid")),
        )
    if lexind is None:
        lexind = [
            {
                "profile": s["profile"],
                "sid": s["sid"],
                "lexid": s["lexid"],
                "kara": s["wid"],
                "made": s["wid"] + 1,
            }
            for s in sentences
            if s.get("lexid")
        ]
    for lx in lexind:
        conn.execute(
            "INSERT INTO lexind (profile, sid, lexid, kara, made) VALUES (?,?,?,?,?)",
            (lx["profile"], lx["sid"], lx["lexid"], lx["kara"], lx["made"]),
        )
    for t in types or []:
        conn.execute(
            "INSERT INTO types (typ, status) VALUES (?,?)", (t["typ"], t["status"])
        )
    return conn


def _make_out() -> sqlite3.Connection:
    """Create an in-memory output database with the example schema."""
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    return conn


# ---------------------------------------------------------------------------
# calculate_offset_limit
# ---------------------------------------------------------------------------


class TestCalculateOffsetLimit:
    def test_limit_exceeds_total_returns_zero_offset(self):
        assert calculate_offset_limit(5, 10) == (0, 5)

    def test_limit_equals_total(self):
        assert calculate_offset_limit(8, 8) == (0, 8)

    def test_standard_skip(self):
        offset, limit = calculate_offset_limit(100, 8)
        assert offset == 20
        assert limit == 8

    def test_remainder_too_small_clamps_offset(self):
        # total=10, limit=9 → 20% offset=2, but 10-2=8 < 9 → clamp to 10-9=1
        offset, limit = calculate_offset_limit(10, 9)
        assert offset == 1
        assert limit == 9

    def test_single_item(self):
        assert calculate_offset_limit(1, 8) == (0, 1)


# ---------------------------------------------------------------------------
# selected_by_lexids
# ---------------------------------------------------------------------------


class TestSelectedByLexids:
    def _setup(self) -> sqlite3.Connection:
        sentences = [
            {"profile": "p1", "sid": 1, "wid": 0, "word": "the", "lexid": "det"},
            {"profile": "p1", "sid": 1, "wid": 1, "word": "cat", "lexid": "cat_n"},
            {"profile": "p1", "sid": 2, "wid": 0, "word": "a",   "lexid": "det"},
            {"profile": "p1", "sid": 2, "wid": 1, "word": "dog", "lexid": "dog_n"},
            {"profile": "p1", "sid": 3, "wid": 0, "word": "big", "lexid": "big_a"},
            {"profile": "p1", "sid": 3, "wid": 1, "word": "cat", "lexid": "cat_n"},
            {"profile": "p1", "sid": 3, "wid": 2, "word": "runs","lexid": "run_v"},
        ]
        return _make_src(sentences)

    def test_returns_sentences_containing_lexid(self):
        conn = self._setup()
        result = selected_by_lexids(conn, ["cat_n"], 10)
        sids = {r[0][1] for r in result}
        assert sids == {1, 3}

    def test_empty_lexids_returns_empty(self):
        conn = self._setup()
        assert selected_by_lexids(conn, [], 10) == []

    def test_span_matches_lexind_single_token(self):
        conn = self._setup()
        result = selected_by_lexids(conn, ["cat_n"], 10)
        for _, spans in result:
            assert spans == [(1, 2)]

    def test_span_matches_lexind_multiword_entry(self):
        # a multiword lexical entry's (kara, made) span is wider than
        # one and does not line up with its wid -- selected_by_lexids
        # must return the real lexind span, not a hardcoded (wid, wid+1)
        sentences = [
            {"profile": "p1", "sid": 1, "wid": 0, "word": "the", "lexid": "det"},
            {"profile": "p1", "sid": 1, "wid": 1, "word": "hikers'", "lexid": "hikers_a2"},
            {"profile": "p1", "sid": 1, "wid": 2, "word": "hut", "lexid": "hut_n1"},
        ]
        lexind = [
            {"profile": "p1", "sid": 1, "lexid": "det", "kara": 0, "made": 1},
            {"profile": "p1", "sid": 1, "lexid": "hikers_a2", "kara": 1, "made": 3},
            {"profile": "p1", "sid": 1, "lexid": "hut_n1", "kara": 3, "made": 4},
        ]
        conn = _make_src(sentences, lexind=lexind)
        result = selected_by_lexids(conn, ["hikers_a2"], 10)
        assert result == [(("p1", 1), [(1, 3)])]

    def test_wid_is_deterministic_min(self):
        # cat_n appears at wid=1 in both sentences; MIN(kara) should
        # always return 1 (kara mirrors wid for single-token entries)
        conn = self._setup()
        result = selected_by_lexids(conn, ["cat_n"], 10)
        for _, spans in result:
            assert spans[0][0] == 1

    def test_limit_respected(self):
        conn = self._setup()
        result = selected_by_lexids(conn, ["cat_n"], 1)
        assert len(result) <= 1

    def test_ordered_by_sentence_length(self):
        conn = self._setup()
        # sid=1 has 2 tokens, sid=3 has 3 tokens → sid=1 first
        result = selected_by_lexids(conn, ["cat_n"], 10)
        sids = [r[0][1] for r in result]
        assert sids == [1, 3]


# ---------------------------------------------------------------------------
# selected_by_type
# ---------------------------------------------------------------------------


class TestSelectedByType:
    def _setup(self) -> sqlite3.Connection:
        sentences = [
            {"profile": "p1", "sid": 1, "wid": 0, "word": "sleeps", "lexid": "sleep_v"},
            {"profile": "p1", "sid": 2, "wid": 0, "word": "the",    "lexid": "det"},
            {"profile": "p1", "sid": 2, "wid": 1, "word": "cat",    "lexid": "cat_n"},
            {"profile": "p1", "sid": 2, "wid": 2, "word": "sleeps", "lexid": "sleep_v"},
        ]
        conn = _make_src(sentences)
        conn.execute(
            "INSERT INTO typind (profile, sid, typ, kara, made) VALUES (?,?,?,?,?)",
            ("p1", 1, "hd_subj_rule", 0, 1),
        )
        conn.execute(
            "INSERT INTO typind (profile, sid, typ, kara, made) VALUES (?,?,?,?,?)",
            ("p1", 2, "hd_subj_rule", 1, 3),
        )
        return conn

    def test_returns_matching_sentences(self):
        conn = self._setup()
        result = selected_by_type(conn, "hd_subj_rule", 10)
        sids = {r[0][1] for r in result}
        assert sids == {1, 2}

    def test_span_reflects_typind_kara_made(self):
        conn = self._setup()
        result = selected_by_type(conn, "hd_subj_rule", 10)
        by_sid = {r[0][1]: r[1] for r in result}
        assert by_sid[1] == [(0, 1)]
        assert by_sid[2] == [(1, 3)]

    def test_null_made_uses_sentence_end(self):
        sentences = [
            {"profile": "p1", "sid": 1, "wid": 0, "word": "runs", "lexid": "run_v"},
            {"profile": "p1", "sid": 1, "wid": 1, "word": "fast", "lexid": "fast_a"},
        ]
        conn = _make_src(sentences)
        conn.execute(
            "INSERT INTO typind (profile, sid, typ, kara, made) VALUES (?,?,?,?,?)",
            ("p1", 1, "some_rule", 0, None),
        )
        result = selected_by_type(conn, "some_rule", 10)
        assert result[0][1] == [(0, 2)]  # made = max(wid)+1 = 2

    def test_ordered_by_sentence_length(self):
        conn = self._setup()
        result = selected_by_type(conn, "hd_subj_rule", 10)
        sids = [r[0][1] for r in result]
        assert sids == [1, 2]

    def test_limit_respected(self):
        conn = self._setup()
        result = selected_by_type(conn, "hd_subj_rule", 1)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# get_sentence_data
# ---------------------------------------------------------------------------


class TestGetSentenceData:
    def test_uses_gold_sentence_when_present(self):
        sentences = [
            {"profile": "p1", "sid": 1, "wid": 0, "word": "hello", "lexid": "hi"},
        ]
        conn = _make_src(sentences)
        conn.execute(
            "INSERT INTO gold (profile, sid, sent, deriv, mrs) VALUES (?,?,?,?,?)",
            ("p1", 1, "Hello.", "deriv_str", "mrs_str"),
        )
        data = get_sentence_data(conn, "p1", 1)
        assert data["sentence"] == "Hello."
        assert data["deriv"] == "deriv_str"
        assert data["mrs"] == "mrs_str"

    def test_falls_back_to_joined_tokens(self):
        sentences = [
            {"profile": "p1", "sid": 1, "wid": 0, "word": "cats", "lexid": "cat_n"},
            {"profile": "p1", "sid": 1, "wid": 1, "word": "run",  "lexid": "run_v"},
        ]
        conn = _make_src(sentences)
        data = get_sentence_data(conn, "p1", 1)
        assert data["sentence"] == "cats run"
        assert data["deriv"] is None


# ---------------------------------------------------------------------------
# build_one (integration)
# ---------------------------------------------------------------------------


class TestBuildOne:
    def test_has_required_tables_rejects_empty_db(self, tmp_path):
        path = tmp_path / "empty.db"
        path.write_bytes(b"")
        assert not has_required_tables(path)

    def test_has_required_tables_accepts_ltdb_shape(self, tmp_path):
        path = tmp_path / "test.db"
        conn = sqlite3.connect(path)
        conn.executescript(
            """
            CREATE TABLE gold (x);
            CREATE TABLE lex (x);
            CREATE TABLE lexfreq (x);
            CREATE TABLE lexind (x);
            CREATE TABLE sent (x);
            CREATE TABLE types (x);
            CREATE TABLE typind (x);
            """
        )
        conn.close()
        assert has_required_tables(path)

    def test_shared_strategy_reuses_sentence_across_types(self, tmp_path):
        src_path = tmp_path / "test.db"
        out_path = tmp_path / "out" / "test.examples.sqlite"
        src = sqlite3.connect(src_path)
        src.executescript(
            """
            CREATE TABLE types (typ TEXT PRIMARY KEY, status TEXT NOT NULL);
            CREATE TABLE lex (lexid TEXT NOT NULL, typ TEXT NOT NULL);
            CREATE TABLE lexfreq (lexid TEXT PRIMARY KEY, freq INTEGER);
            CREATE TABLE sent (profile TEXT, sid INTEGER, wid INTEGER,
                               word TEXT, lexid TEXT, PRIMARY KEY(profile,sid,wid));
            CREATE TABLE lexind (profile TEXT, sid INTEGER, lexid TEXT,
                                 kara INTEGER, made INTEGER);
            CREATE TABLE typind (profile TEXT, sid INTEGER, typ TEXT,
                                 kara INTEGER, made INTEGER);
            CREATE TABLE gold (profile TEXT, sid INTEGER, sent TEXT,
                               deriv TEXT, mrs TEXT, PRIMARY KEY(profile,sid));
            INSERT INTO types VALUES ('type_a', 'rule');
            INSERT INTO types VALUES ('type_b', 'rule');
            INSERT INTO sent VALUES ('p1', 1, 0, 'shared', 'x');
            INSERT INTO sent VALUES ('p1', 2, 0, 'solo', 'y');
            INSERT INTO typind VALUES ('p1', 1, 'type_a', 0, 1);
            INSERT INTO typind VALUES ('p1', 1, 'type_b', 0, 1);
            INSERT INTO typind VALUES ('p1', 2, 'type_a', 0, 1);
            """
        )
        src.commit()
        src.close()

        counts = build_one(
            src_path,
            out_path,
            ("rule",),
            1,
            0,
            strategy="shared",
            candidate_limit=8,
        )

        assert counts["types"] == 2
        assert counts["examples"] == 1
        assert counts["links"] == 2

    def test_shared_selection_repairs_types_not_covered_by_greedy_winner(self):
        conn = _make_src(
            [
                {"profile": "p1", "sid": 1, "wid": 0, "word": "a", "lexid": "a"},
                {"profile": "p1", "sid": 2, "wid": 0, "word": "b", "lexid": "b"},
            ],
            [{"typ": "type_a", "status": "rule"}, {"typ": "type_b", "status": "rule"}],
        )
        conn.execute("INSERT INTO typind VALUES ('p1', 1, 'type_a', 0, 1)")
        conn.execute("INSERT INTO typind VALUES ('p1', 2, 'type_b', 0, 1)")

        selected = shared_example_selection(
            conn,
            [("type_a", "rule"), ("type_b", "rule")],
            example_lim=1,
            candidate_limit=8,
        )

        assert len(selected["type_a"]) == 1
        assert len(selected["type_b"]) == 1

    def test_creates_output_file(self, tmp_path):
        src_path = tmp_path / "test.db"
        out_path = tmp_path / "out" / "test.examples.sqlite"
        src = sqlite3.connect(src_path)
        src.executescript(
            """
            CREATE TABLE types (typ TEXT PRIMARY KEY, status TEXT NOT NULL);
            CREATE TABLE lex (lexid TEXT NOT NULL, typ TEXT NOT NULL);
            CREATE TABLE lexfreq (lexid TEXT PRIMARY KEY, freq INTEGER);
            CREATE TABLE sent (profile TEXT, sid INTEGER, wid INTEGER,
                               word TEXT, lexid TEXT, PRIMARY KEY(profile,sid,wid));
            CREATE TABLE lexind (profile TEXT, sid INTEGER, lexid TEXT,
                                 kara INTEGER, made INTEGER);
            CREATE TABLE typind (profile TEXT, sid INTEGER, typ TEXT,
                                 kara INTEGER, made INTEGER);
            CREATE TABLE gold (profile TEXT, sid INTEGER, sent TEXT,
                               deriv TEXT, mrs TEXT, PRIMARY KEY(profile,sid));
            INSERT INTO types VALUES ('n_-_c_le', 'lex-type');
            INSERT INTO lex VALUES ('cat_n', 'n_-_c_le');
            INSERT INTO sent VALUES ('p1', 1, 0, 'cats', 'cat_n');
            INSERT INTO sent VALUES ('p1', 1, 1, 'run',  'run_v');
            INSERT INTO lexind VALUES ('p1', 1, 'cat_n', 0, 1);
            """
        )
        src.commit()
        src.close()

        counts = build_one(src_path, out_path, ("lex-type",), 8, 5)
        assert out_path.exists()
        assert counts["types"] == 1
        assert counts["examples"] >= 1
        assert counts["bytes"] > 0

    def test_secondary_lex_entries_capped(self, tmp_path):
        src_path = tmp_path / "test.db"
        out_path = tmp_path / "out" / "test.examples.sqlite"
        src = sqlite3.connect(src_path)
        src.executescript(
            """
            CREATE TABLE types (typ TEXT PRIMARY KEY, status TEXT NOT NULL);
            CREATE TABLE lex (lexid TEXT NOT NULL, typ TEXT NOT NULL);
            CREATE TABLE lexfreq (lexid TEXT PRIMARY KEY, freq INTEGER);
            CREATE TABLE sent (profile TEXT, sid INTEGER, wid INTEGER,
                               word TEXT, lexid TEXT, PRIMARY KEY(profile,sid,wid));
            CREATE TABLE lexind (profile TEXT, sid INTEGER, lexid TEXT,
                                 kara INTEGER, made INTEGER);
            CREATE TABLE typind (profile TEXT, sid INTEGER, typ TEXT,
                                 kara INTEGER, made INTEGER);
            CREATE TABLE gold (profile TEXT, sid INTEGER, sent TEXT,
                               deriv TEXT, mrs TEXT, PRIMARY KEY(profile,sid));
            INSERT INTO types VALUES ('n_le', 'lex-type');
            """
        )
        # 10 distinct lexids, each appearing in one unique sentence
        for i in range(10):
            src.execute("INSERT INTO lex VALUES (?,?)", (f"lex{i}", "n_le"))
            src.execute(
                "INSERT INTO sent VALUES (?,?,?,?,?)",
                ("p1", i, 0, f"word{i}", f"lex{i}"),
            )
            src.execute(
                "INSERT INTO lexind VALUES (?,?,?,?,?)",
                ("p1", i, f"lex{i}", 0, 1),
            )
        src.commit()
        src.close()

        lex_lim = 3
        build_one(src_path, out_path, ("lex-type",), 8, lex_lim)
        out = sqlite3.connect(out_path)
        secondary = out.execute(
            "SELECT COUNT(*) FROM type_examples WHERE source LIKE 'lex-entry:%'"
        ).fetchone()[0]
        out.close()
        assert secondary <= lex_lim

    def test_existing_output_overwritten(self, tmp_path):
        src_path = tmp_path / "test.db"
        out_path = tmp_path / "test.examples.sqlite"
        out_path.write_bytes(b"stale")

        src = sqlite3.connect(src_path)
        src.executescript(
            """
            CREATE TABLE types (typ TEXT PRIMARY KEY, status TEXT NOT NULL);
            CREATE TABLE lex (lexid TEXT NOT NULL, typ TEXT NOT NULL);
            CREATE TABLE lexfreq (lexid TEXT PRIMARY KEY, freq INTEGER);
            CREATE TABLE sent (profile TEXT, sid INTEGER, wid INTEGER,
                               word TEXT, lexid TEXT, PRIMARY KEY(profile,sid,wid));
            CREATE TABLE lexind (profile TEXT, sid INTEGER, lexid TEXT,
                                 kara INTEGER, made INTEGER);
            CREATE TABLE typind (profile TEXT, sid INTEGER, typ TEXT,
                                 kara INTEGER, made INTEGER);
            CREATE TABLE gold (profile TEXT, sid INTEGER, sent TEXT,
                               deriv TEXT, mrs TEXT, PRIMARY KEY(profile,sid));
            """
        )
        src.commit()
        src.close()

        build_one(src_path, out_path, ("lex-type",), 8, 5)
        out = sqlite3.connect(out_path)
        tables = {
            r[0]
            for r in out.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        out.close()
        assert "examples" in tables
        assert "type_examples" in tables
