"""Build compact per-grammar example databases for the static LTDB mirror."""

from __future__ import annotations

import argparse
import gzip
import heapq
import shutil
import sqlite3
from collections import defaultdict
from pathlib import Path

import orjson


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_DIR = ROOT / "build" / "DBS"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "ltdb" / "db"
DEFAULT_STATUSES = ("lex-type", "rule", "lex-rule", "root")
REQUIRED_SOURCE_TABLES = {"gold", "lex", "lexfreq", "lexind", "sent", "types", "typind"}


def holders(values) -> str:
    """Return a comma-separated string of '?' placeholders for SQL IN clauses."""
    return ",".join("?" for _ in values)


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


def calculate_offset_limit(total: int, limit: int) -> tuple[int, int]:
    """Match LTDB's example sampling: skip first 20%, then take a short sample."""
    if limit >= total:
        return 0, total
    offset = round(total * 0.2)
    if total - offset < limit:
        offset = total - limit
    return offset, limit


def create_schema(conn: sqlite3.Connection) -> None:
    """Create the examples and type_examples tables in the output database."""
    conn.executescript(
        """
        DROP TABLE IF EXISTS type_examples;
        DROP TABLE IF EXISTS examples;

        CREATE TABLE examples (
          example_id  INTEGER PRIMARY KEY,
          profile     TEXT    NOT NULL,
          sid         INTEGER NOT NULL,
          sentence    TEXT    NOT NULL,
          tokens_json TEXT,
          deriv       TEXT,
          mrs         TEXT,
          UNIQUE(profile, sid)
        );

        CREATE TABLE type_examples (
          typ        TEXT    NOT NULL,
          rank       INTEGER NOT NULL,
          example_id INTEGER NOT NULL,
          spans_json TEXT,
          source     TEXT,
          PRIMARY KEY (typ, rank),
          FOREIGN KEY(example_id) REFERENCES examples(example_id)
        );

        CREATE INDEX idx_type_examples_typ ON type_examples(typ);
        """
    )


def get_type_rows(
    conn: sqlite3.Connection, statuses: tuple[str, ...]
) -> list[tuple[str, str]]:
    """Return (typ, status) pairs for all types matching the given statuses."""
    rows = conn.execute(
        f"SELECT typ, status FROM types WHERE status IN ({holders(statuses)}) "
        "ORDER BY status, typ",
        statuses,
    ).fetchall()
    return [(typ, status) for typ, status in rows]


def get_lexids(conn: sqlite3.Connection, typ: str, limit: int = 256) -> list[str]:
    """Return lexids for a lex-type, ordered by descending corpus frequency."""
    rows = conn.execute(
        """
        SELECT lex.lexid
        FROM lex LEFT JOIN lexfreq ON lex.lexid = lexfreq.lexid
        WHERE typ = ?
        ORDER BY COALESCE(freq, 0) DESC
        LIMIT ?
        """,
        (typ, limit),
    ).fetchall()
    return [row[0] for row in rows]


def selected_by_lexids(
    conn: sqlite3.Connection,
    lexids: list[str],
    limit: int,
) -> list[tuple[tuple[str, int], list[tuple[int, int]]]]:
    """Select representative sentences for the given lexids via lexind.

    Returns a list of ((profile, sid), [(kara, made)]) pairs ordered by
    sentence length. Uses LTDB's 20%-offset sampling strategy.

    lexind's (kara, made) is the raw-token span pydelphin assigns a
    preterminal; a plain (wid, wid+1) from sent.wid would be wrong for
    any multiword lexical entry, whose raw-token span is wider than
    one and whose wid no longer lines up 1:1 with raw-token position
    (see gold2db.py's preterminal_rows in etc/ltdb).
    """
    if not lexids:
        return []
    count = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM (
          SELECT DISTINCT profile, sid
          FROM lexind
          WHERE lexid IN ({holders(lexids)})
        )
        """,
        lexids,
    ).fetchone()[0]
    offset, limit = calculate_offset_limit(count, limit)
    rows = conn.execute(
        f"""
        SELECT a.profile, a.sid,
               MIN(a.kara) AS kara, MIN(a.made) AS made,
               MAX(b.wid) AS max_wid
        FROM lexind AS a LEFT JOIN sent AS b
          ON a.profile = b.profile AND a.sid = b.sid
        WHERE a.lexid IN ({holders(lexids)})
        GROUP BY a.profile, a.sid
        ORDER BY MAX(b.wid)
        LIMIT ? OFFSET ?
        """,
        lexids + [limit, offset],
    ).fetchall()
    return [((profile, sid), [(kara, made)]) for profile, sid, kara, made, _ in rows]


def selected_by_type(
    conn: sqlite3.Connection,
    typ: str,
    limit: int,
) -> list[tuple[tuple[str, int], list[tuple[int, int]]]]:
    """Select representative sentences for a rule/root type via typind.

    Returns a list of ((profile, sid), [(kara, made)]) pairs ordered by
    sentence length. Uses LTDB's 20%-offset sampling strategy.
    """
    count = conn.execute(
        """
        SELECT COUNT(*)
        FROM (
          SELECT DISTINCT profile, sid
          FROM typind
          WHERE typ = ?
        )
        """,
        (typ,),
    ).fetchone()[0]
    offset, limit = calculate_offset_limit(count, limit)
    rows = conn.execute(
        """
        SELECT a.profile, a.sid,
               MIN(COALESCE(a.kara, 0)) AS kara,
               COALESCE(MIN(a.made), MAX(b.wid) + 1) AS made,
               MAX(b.wid) AS max_wid
        FROM typind AS a LEFT JOIN sent AS b
          ON a.profile = b.profile AND a.sid = b.sid
        WHERE a.typ = ?
        GROUP BY a.profile, a.sid
        ORDER BY MAX(b.wid)
        LIMIT ? OFFSET ?
        """,
        (typ, limit, offset),
    ).fetchall()
    return [((profile, sid), [(kara, made)]) for profile, sid, kara, made, _ in rows]


def sentence_lengths(conn: sqlite3.Connection) -> dict[tuple[str, int], int]:
    """Return token counts for all sentences, keyed by (profile, sid)."""
    return {
        (profile, sid): count
        for profile, sid, count in conn.execute(
            """
            SELECT profile, sid, COUNT(*)
            FROM sent
            GROUP BY profile, sid
            """
        )
    }


def derivation_lengths(conn: sqlite3.Connection) -> dict[tuple[str, int], int]:
    """Return raw derivation lengths, keyed by (profile, sid)."""
    return {
        (profile, sid): length or 0
        for profile, sid, length in conn.execute(
            """
            SELECT profile, sid, LENGTH(deriv)
            FROM gold
            """
        )
    }


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping or adjacent token spans."""
    if not spans:
        return []
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def collect_type_candidates(
    conn: sqlite3.Connection,
    type_rows: list[tuple[str, str]],
    example_lim: int,
    candidate_limit: int,
) -> dict[str, list[tuple[tuple[str, int], list[tuple[int, int]], str]]]:
    """Collect candidate examples for each type before shared selection."""
    limit = max(example_lim, candidate_limit)
    candidates: dict[str, list[tuple[tuple[str, int], list[tuple[int, int]], str]]] = {}
    for typ, status in type_rows:
        if status == "lex-type":
            selected = selected_by_lexids(conn, get_lexids(conn, typ), limit)
        else:
            selected = selected_by_type(conn, typ, limit)
        candidates[typ] = [(key, spans, status) for key, spans in selected]
    return candidates


def shared_example_selection(
    conn: sqlite3.Connection,
    type_rows: list[tuple[str, str]],
    example_lim: int,
    candidate_limit: int,
) -> dict[str, list[tuple[tuple[str, int], list[tuple[int, int]], str]]]:
    """Select a shared sentence set that covers up to example_lim examples per type.

    This is a greedy weighted set-cover approximation. It prefers sentences that
    satisfy rare type needs and mildly penalizes long sentences and huge raw
    derivations, then performs a repair pass for any type still below its target.
    """
    candidates = collect_type_candidates(conn, type_rows, example_lim, candidate_limit)
    by_sentence: dict[
        tuple[str, int], dict[str, tuple[list[tuple[int, int]], str]]
    ] = defaultdict(dict)
    for typ, selected in candidates.items():
        for key, spans, source in selected:
            if typ in by_sentence[key]:
                old_spans, _ = by_sentence[key][typ]
                by_sentence[key][typ] = (merge_spans(old_spans + spans), source)
            else:
                by_sentence[key][typ] = (spans, source)

    lengths = sentence_lengths(conn)
    deriv_lengths = derivation_lengths(conn)
    available = {
        typ: max(1, len(selected)) for typ, selected in candidates.items()
    }
    need = {
        typ: min(example_lim, len(selected)) for typ, selected in candidates.items()
    }
    chosen: dict[str, list[tuple[tuple[str, int], list[tuple[int, int]], str]]] = {
        typ: [] for typ, _ in type_rows
    }
    chosen_keys: dict[str, set[tuple[str, int]]] = defaultdict(set)
    remaining = set(by_sentence)

    def score(
        key: tuple[str, int],
        coverage: dict[str, tuple[list[tuple[int, int]], str]],
    ) -> float:
        gain = 0.0
        for typ in coverage:
            if need.get(typ, 0) > 0 and key not in chosen_keys[typ]:
                gain += 1.0 / available[typ]
        if gain == 0:
            return 0.0
        token_penalty = 1.0 + max(0, lengths.get(key, 0) - 12) / 40.0
        deriv_penalty = 1.0 + deriv_lengths.get(key, 0) / 50000.0
        return gain / (token_penalty * deriv_penalty)

    heap = [
        (-score(key, coverage), key)
        for key, coverage in by_sentence.items()
        if coverage
    ]
    heapq.heapify(heap)
    while any(value > 0 for value in need.values()) and remaining:
        if not heap:
            break
        old_negative_score, key = heapq.heappop(heap)
        if key not in remaining:
            continue
        coverage = by_sentence[key]
        current_score = score(key, coverage)
        if current_score <= 0:
            break
        if current_score < -old_negative_score:
            heapq.heappush(heap, (-current_score, key))
            continue
        for typ, (spans, source) in coverage.items():
            if need.get(typ, 0) <= 0 or key in chosen_keys[typ]:
                continue
            chosen[typ].append((key, spans, source))
            chosen_keys[typ].add(key)
            need[typ] -= 1
        remaining.remove(key)

    for typ, selected in candidates.items():
        if need.get(typ, 0) <= 0:
            continue
        for key, spans, source in selected:
            if need[typ] <= 0:
                break
            if key in chosen_keys[typ]:
                continue
            chosen[typ].append((key, spans, source))
            chosen_keys[typ].add(key)
            need[typ] -= 1
    return chosen


def get_sentence_data(conn: sqlite3.Connection, profile: str, sid: int) -> dict:
    """Fetch sentence text, tokens, derivation, and MRS for one (profile, sid)."""
    tokens = [
        {"wid": wid, "word": word, "lexid": lexid}
        for wid, word, lexid in conn.execute(
            """
            SELECT wid, word, lexid
            FROM sent
            WHERE profile = ? AND sid = ?
            ORDER BY wid
            """,
            (profile, sid),
        )
    ]
    gold = conn.execute(
        """
        SELECT sent, deriv, mrs
        FROM gold
        WHERE profile = ? AND sid = ?
        LIMIT 1
        """,
        (profile, sid),
    ).fetchone()
    if gold:
        sentence, deriv, mrs = gold
    else:
        sentence, deriv, mrs = " ".join(t["word"] for t in tokens), None, None
    return {
        "sentence": sentence or " ".join(t["word"] for t in tokens),
        "tokens_json": orjson.dumps(tokens).decode(),
        "deriv": deriv,
        "mrs": mrs,
    }


def insert_example(
    out: sqlite3.Connection,
    src: sqlite3.Connection,
    cache: dict[tuple[str, int], int],
    profile: str,
    sid: int,
) -> int:
    """Insert a sentence into the examples table (or look it up) and return its id."""
    key = (profile, sid)
    if key in cache:
        return cache[key]
    data = get_sentence_data(src, profile, sid)
    out.execute(
        """
        INSERT OR IGNORE INTO examples
          (profile, sid, sentence, tokens_json, deriv, mrs)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            profile,
            sid,
            data["sentence"],
            data["tokens_json"],
            data["deriv"],
            data["mrs"],
        ),
    )
    example_id = out.execute(
        "SELECT example_id FROM examples WHERE profile = ? AND sid = ?",
        (profile, sid),
    ).fetchone()[0]
    cache[key] = example_id
    return example_id


def add_type_examples(
    out: sqlite3.Connection,
    src: sqlite3.Connection,
    typ: str,
    selected: list[tuple[tuple[str, int], list[tuple[int, int]]]],
    source: str,
    cache: dict[tuple[str, int], int],
    start_rank: int = 1,
) -> int:
    """Insert type_examples rows for the given selection and return the next rank."""
    rank = start_rank
    seen_examples: set[int] = set()
    for (profile, sid), spans in selected:
        example_id = insert_example(out, src, cache, profile, sid)
        if example_id in seen_examples:
            continue
        seen_examples.add(example_id)
        out.execute(
            """
            INSERT OR IGNORE INTO type_examples
              (typ, rank, example_id, spans_json, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                typ,
                rank,
                example_id,
                orjson.dumps(spans).decode(),
                source,
            ),
        )
        rank += 1
    return rank


def build_one(
    src_path: Path,
    out_path: Path,
    statuses: tuple[str, ...],
    example_lim: int,
    lex_example_lim: int,
    strategy: str = "per-type",
    candidate_limit: int = 64,
) -> dict[str, int]:
    """Build one per-grammar example SQLite from an LTDB source database.

    Returns a dict with counts: types, examples, links, bytes.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    src = sqlite3.connect(src_path)
    out = sqlite3.connect(out_path)
    try:
        src.execute("PRAGMA foreign_keys = ON")
        out.execute("PRAGMA foreign_keys = ON")
        create_schema(out)
        cache: dict[tuple[str, int], int] = {}

        type_rows = get_type_rows(src, statuses)
        if strategy == "shared":
            shared = shared_example_selection(
                src, type_rows, example_lim, candidate_limit
            )
            for typ, _status in type_rows:
                selected = [
                    (key, spans)
                    for key, spans, _source in shared.get(typ, [])
                ]
                source = "shared"
                add_type_examples(out, src, typ, selected, source, cache)
        else:
            for typ, status in type_rows:
                if status == "lex-type":
                    lexids = get_lexids(src, typ)
                    rank = add_type_examples(
                        out,
                        src,
                        typ,
                        selected_by_lexids(src, lexids, example_lim),
                        "lex-type",
                        cache,
                    )
                    if lex_example_lim:
                        used = {
                            row[0]
                            for row in out.execute(
                                "SELECT example_id FROM type_examples WHERE typ = ?",
                                (typ,),
                            )
                        }
                        secondary_count = 0
                        for lexid in lexids:
                            if secondary_count >= lex_example_lim:
                                break
                            selected = selected_by_lexids(src, [lexid], 1)
                            if not selected:
                                continue
                            example_id = insert_example(
                                out,
                                src,
                                cache,
                                selected[0][0][0],
                                selected[0][0][1],
                            )
                            if example_id in used:
                                continue
                            used.add(example_id)
                            rank = add_type_examples(
                                out,
                                src,
                                typ,
                                selected,
                                f"lex-entry:{lexid}",
                                cache,
                                rank,
                            )
                            secondary_count += 1
                else:
                    add_type_examples(
                        out,
                        src,
                        typ,
                        selected_by_type(src, typ, example_lim),
                        status,
                        cache,
                    )

        out.commit()
        out.execute("VACUUM")
        counts = {
            "types": len(type_rows),
            "examples": out.execute("SELECT COUNT(*) FROM examples").fetchone()[0],
            "links": out.execute("SELECT COUNT(*) FROM type_examples").fetchone()[0],
            "bytes": out_path.stat().st_size,
        }
    finally:
        src.close()
        out.close()
    return counts


def main() -> None:
    """CLI entry point: build example SQLite databases for all grammars."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-dir", type=Path, default=DEFAULT_DB_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--example-lim", type=int, default=8)
    parser.add_argument("--lex-example-lim", type=int, default=5)
    parser.add_argument(
        "--strategy",
        choices=("per-type", "shared"),
        default="per-type",
        help="Example selection strategy. Default: per-type.",
    )
    parser.add_argument(
        "--candidate-limit",
        type=int,
        default=64,
        help="Candidate examples per type for --strategy shared. Default: 64.",
    )
    parser.add_argument(
        "--statuses",
        default=",".join(DEFAULT_STATUSES),
        help="Comma-separated type statuses to extract examples for.",
    )
    parser.add_argument(
        "--gzip",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Gzip output files (default: on). Required for files >100 MB.",
    )
    args = parser.parse_args()

    statuses = tuple(s.strip() for s in args.statuses.split(",") if s.strip())
    totals: dict[str, int] = defaultdict(int)
    for src_path in sorted(args.db_dir.glob("*.db")):
        if not has_required_tables(src_path):
            print(f"{src_path.name}: skipped, not an LTDB source database")
            continue
        out_path = args.output_dir / f"{src_path.stem}.examples.sqlite"
        counts = build_one(
            src_path,
            out_path,
            statuses,
            args.example_lim,
            args.lex_example_lim,
            strategy=args.strategy,
            candidate_limit=args.candidate_limit,
        )
        if args.gzip:
            gz_path = Path(str(out_path) + ".gz")
            with open(out_path, "rb") as f_in, gzip.open(gz_path, "wb", compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)
            out_path.unlink()
            counts["bytes"] = gz_path.stat().st_size
        for key, value in counts.items():
            totals[key] += value
        label = ".gz" if args.gzip else ""
        print(
            f"{src_path.name}: {counts['examples']} examples, "
            f"{counts['links']} links, {counts['bytes'] / 1048576:.1f} MiB{label}"
        )
    print(
        f"TOTAL: {totals['examples']} examples, {totals['links']} links, "
        f"{totals['bytes'] / 1048576:.1f} MiB"
    )


if __name__ == "__main__":
    main()
