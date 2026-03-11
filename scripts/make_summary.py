"""Generate a Markdown grammar summary table from ltdb database files."""

import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path


def summarize_db(path: Path, db_dir: Path) -> dict:
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
        "has_dat": (db_dir / f"{path.stem}.dat").exists(),
    }


def render_table(rows: list[dict], base_url: str) -> str:
    """Render grammar statistics as a Markdown table."""
    if not rows:
        return "_No grammar databases found._\n"
    lines = [
        "| Grammar | Version | Rules | Lexicon | Trees | License | Download |",
        "| ------- | ------- | ----: | ------: | ----: | ------- | -------- |",
    ]
    for r in rows:
        name = f'[{r["name"]}]({r["website"]})' if r["website"] else r["name"]
        stem = r["version"]
        downloads = [f"[db]({base_url}/{stem}.db.xz)"]
        if r["has_dat"]:
            downloads.append(f"[dat]({base_url}/{stem}.dat.xz)")
        lines.append(
            f'| {name} | {stem} | {r["rules"]:,}'
            f' | {r["lexicon"]:,} | {r["trees"]:,} | {r["license"]}'
            f' | {" ".join(downloads)} |'
        )
    return "\n".join(lines) + "\n"


def get_ltdb_info(ltdb_dir: Path) -> str:
    """Return a brief description of the ltdb version used."""
    if not (ltdb_dir / ".git").is_dir():
        return "ltdb (unknown version)"
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(ltdb_dir), "rev-parse", "--short", "HEAD"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
        remote = subprocess.check_output(
            ["git", "-C", str(ltdb_dir), "remote", "get-url", "origin"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip().rstrip(".git")
        return f"[ltdb {commit}]({remote}/commit/{commit})"
    except subprocess.CalledProcessError:
        return "ltdb (unknown version)"


def get_ace_version(ltdb_dir: Path) -> str:
    """Return the ACE version found in the ltdb etc/ directory."""
    candidates = sorted((ltdb_dir / "etc").glob("ace-*/ace"), reverse=True)
    if not candidates:
        return "ACE (unknown version)"
    version = candidates[0].parent.name  # e.g. "ace-0.9.31"
    return version


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
        "--repo",
        default="delph-in/grammary",
        help="GitHub repo (default: delph-in/grammary)",
    )
    parser.add_argument(
        "--ltdb-dir",
        type=Path,
        default=Path("etc/ltdb"),
        help="Path to the ltdb checkout (default: etc/ltdb)",
    )
    parser.add_argument(
        "--output", type=Path, help="Write to this file instead of stdout"
    )
    args = parser.parse_args()

    base_url = (
        f"https://github.com/{args.repo}/releases/download/{args.tag}"
    )

    dbs = sorted(args.db_dir.glob("*.db")) if args.db_dir.is_dir() else []
    rows = [summarize_db(p, args.db_dir) for p in dbs]

    ltdb_info = get_ltdb_info(args.ltdb_dir)
    ace_info = get_ace_version(args.ltdb_dir)

    footer = f"\nBuilt with {ltdb_info} and {ace_info}.\n"
    content = (
        f"# Grammar Summary — {args.tag}\n\n"
        f"{render_table(rows, base_url)}"
        f"{footer}"
    )

    if args.output:
        args.output.write_text(content)
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
