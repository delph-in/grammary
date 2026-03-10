"""Generate a Markdown grammar summary table from ltdb database files."""

import argparse
import sqlite3
import sys
from pathlib import Path


def summarize_db(path: Path) -> dict:
    """Query a single grammar database and return summary statistics."""
    with sqlite3.connect(path) as conn:
        md = dict(conn.execute("SELECT att, val FROM meta").fetchall())
        (rules,) = conn.execute(
            "SELECT COUNT(*) FROM types WHERE status IN ('rule','lex-rule')"
        ).fetchone()
        (lexicon,) = conn.execute(
            "SELECT COUNT(*) FROM types"
            " WHERE status IN ('lex-entry','generic-lex-entry')"
        ).fetchone()
        (trees,) = conn.execute(
            "SELECT COUNT(DISTINCT sid || ',' || profile) FROM sent"
        ).fetchone()
    return {
        "name": md.get("GRAMMAR_NAME", path.stem),
        "version": path.stem,
        "website": md.get("WEBSITE", ""),
        "rules": rules,
        "lexicon": lexicon,
        "trees": trees,
        "license": md.get("LICENSE", ""),
    }


def render_table(rows: list[dict]) -> str:
    """Render grammar statistics as a Markdown table."""
    if not rows:
        return "_No grammar databases found._\n"
    lines = [
        "| Grammar | Version | Rules | Lexicon | Trees | License |",
        "| ------- | ------- | ----: | ------: | ----: | ------- |",
    ]
    for r in rows:
        name = f'[{r["name"]}]({r["website"]})' if r["website"] else r["name"]
        lines.append(
            f'| {name} | {r["version"]} | {r["rules"]:,}'
            f' | {r["lexicon"]:,} | {r["trees"]:,} | {r["license"]} |'
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarise ltdb grammar databases as a Markdown table."
    )
    parser.add_argument(
        "--db-dir",
        type=Path,
        default=Path("build/DBS"),
        help="Directory containing .db files (default: build/DBS)",
    )
    parser.add_argument(
        "--tag", default="unknown", help="Release tag used in the heading"
    )
    parser.add_argument(
        "--output", type=Path, help="Write to this file instead of stdout"
    )
    args = parser.parse_args()

    dbs = sorted(args.db_dir.glob("*.db")) if args.db_dir.is_dir() else []
    rows = [summarize_db(p) for p in dbs]
    content = f"# Grammar Summary — {args.tag}\n\n{render_table(rows)}"

    if args.output:
        args.output.write_text(content)
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
