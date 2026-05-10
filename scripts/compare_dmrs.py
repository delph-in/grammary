"""Compare JS mrsToDmrs output against pydelphin's from_mrs across all example DBs.

Runs pydelphin in-process and sends all MRS strings to a single Node.js process,
so the full corpus (~18k strings) completes in a few minutes rather than hours.

    uv run python scripts/compare_dmrs.py [--db-dir docs/ltdb/db] [--verbose]
    uv run python scripts/compare_dmrs.py --output /tmp/report.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_DIR = ROOT / "docs" / "ltdb" / "db"

# Node script: reads a JSON array of MRS strings from stdin, emits a JSON array
# of {top, links} results (or "BAIL:<msg>" strings on failure).
_NODE_BATCH = """
const L = require({ltdb_mrs!r});
let buf = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', d => buf += d);
process.stdin.on('end', () => {{
  const mrs_list = JSON.parse(buf);
  const results = mrs_list.map(mrs_str => {{
    try {{
      const m = L.parseMrs(mrs_str);
      const d = L.mrsToDmrs(m);
      const links = d.links
        .filter(l => l.from !== 0)
        .map(l => [l.from, l.to, l.rargname, l.post]);
      links.sort();
      return {{top: d.top, links}};
    }} catch(e) {{
      return 'BAIL:' + e.message;
    }}
  }});
  console.log(JSON.stringify(results));
}});
"""


def collect_mrs(db_dir: Path) -> list[tuple[str, str]]:
    """Return [(grammar_name, mrs_str), …] for all grammars with MRS data."""
    rows = []
    for db in sorted(db_dir.glob("*.examples.sqlite")):
        grammar = db.stem.replace(".examples", "")
        conn = sqlite3.connect(db)
        for (mrs,) in conn.execute(
            "SELECT mrs FROM examples WHERE mrs IS NOT NULL AND mrs != ''"
        ):
            rows.append((grammar, mrs))
        conn.close()
    return rows


def run_pydelphin(mrs_list: list[str]) -> list[dict | None]:
    """Convert all MRS strings via pydelphin in-process."""
    sys.path.insert(0, str(ROOT / "etc" / "ltdb"))
    from delphin.codecs import dmrsjson, simplemrs
    from delphin import dmrs as _dmrs

    results = []
    for mrs_str in mrs_list:
        try:
            m = simplemrs.decode(mrs_str)
            d = _dmrs.from_mrs(m)
            j = json.loads(dmrsjson.encode(d))
            links = sorted(
                (l["from"], l["to"], l["rargname"], l["post"]) for l in j["links"]
            )
            results.append({"top": j.get("top"), "links": links})
        except Exception:
            results.append(None)
    return results


def run_node(mrs_list: list[str]) -> list[dict | None]:
    """Convert all MRS strings via the JS module in a single Node process."""
    ltdb_mrs = str(ROOT / "assets" / "ltdb" / "ltdb-mrs.js")
    script = _NODE_BATCH.format(ltdb_mrs=ltdb_mrs)
    r = subprocess.run(
        ["node", "-e", script],
        input=json.dumps(mrs_list),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if r.returncode != 0:
        sys.exit(f"Node process failed:\n{r.stderr[:500]}")
    raw = json.loads(r.stdout)
    results = []
    for item in raw:
        if isinstance(item, str) and item.startswith("BAIL"):
            results.append(None)
        else:
            results.append(item)
    return results


def compare(py: dict, js: dict) -> dict:
    """Return diff dict (empty = match)."""
    py_l = set(tuple(l) for l in py["links"])
    js_l = set(tuple(l) for l in js["links"])
    diffs = {}
    if py["top"] != js["top"]:
        diffs["top"] = {"py": py["top"], "js": js["top"]}
    if py_l != js_l:
        diffs["py_only"] = sorted(py_l - js_l)
        diffs["js_only"] = sorted(js_l - py_l)
    return diffs


def main() -> None:
    """Run the full comparison."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-dir", type=Path, default=DEFAULT_DB_DIR)
    parser.add_argument("--verbose", action="store_true",
                        help="Print every disagreement")
    parser.add_argument("--output", type=Path, default=None,
                        help="Write JSON report to this file")
    args = parser.parse_args()

    print("Collecting MRS strings...", flush=True)
    all_rows = collect_mrs(args.db_dir)
    mrs_strings = [mrs for _, mrs in all_rows]
    grammars = [g for g, _ in all_rows]
    print(f"  {len(mrs_strings)} MRS strings across {len(set(grammars))} grammars")

    print("Running pydelphin...", flush=True)
    py_results = run_pydelphin(mrs_strings)
    py_ok = sum(1 for r in py_results if r is not None)
    print(f"  pydelphin: {py_ok} converted, {len(py_results)-py_ok} bailed")

    print("Running Node.js...", flush=True)
    js_results = run_node(mrs_strings)
    js_ok = sum(1 for r in js_results if r is not None)
    print(f"  node: {js_ok} converted, {len(js_results)-js_ok} bailed")

    # Compare where both succeeded
    totals: dict[str, int] = defaultdict(int)
    by_grammar: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    disagreements: list[dict] = []

    for grammar, mrs_str, py, js in zip(grammars, mrs_strings, py_results, js_results):
        totals["total"] += 1
        by_grammar[grammar]["total"] += 1
        if py is None:
            totals["py_bail"] += 1; by_grammar[grammar]["py_bail"] += 1; continue
        if js is None:
            totals["js_bail"] += 1; by_grammar[grammar]["js_bail"] += 1; continue
        diffs = compare(py, js)
        if not diffs:
            totals["agree"] += 1; by_grammar[grammar]["agree"] += 1
        else:
            totals["disagree"] += 1; by_grammar[grammar]["disagree"] += 1
            rec = {"grammar": grammar, "mrs": mrs_str, "diffs": diffs}
            disagreements.append(rec)
            if args.verbose:
                print(f"  DISAGREE [{grammar}]: {diffs}")

    # Per-grammar summary
    print("\nPer-grammar results:")
    for grammar in sorted(by_grammar):
        g = by_grammar[grammar]
        comparable = g["agree"] + g["disagree"]
        rate = f"{g['agree']/comparable*100:.1f}%" if comparable else "n/a"
        print(
            f"  {grammar}: agree={g['agree']} disagree={g['disagree']} "
            f"py_bail={g.get('py_bail',0)} js_bail={g.get('js_bail',0)} "
            f"({rate})"
        )

    comparable = totals["agree"] + totals["disagree"]
    rate = f"{totals['agree']/comparable*100:.2f}%" if comparable else "n/a"
    print(
        f"\nTOTAL: agree={totals['agree']} disagree={totals['disagree']} "
        f"py_bail={totals['py_bail']} js_bail={totals['js_bail']} "
        f"total={totals['total']}"
    )
    print(f"Agreement rate (where both converted): {rate}")

    if disagreements:
        print(f"\nFirst 3 disagreements:")
        for rec in disagreements[:3]:
            print(f"  [{rec['grammar']}] {rec['diffs']}")

    if args.output:
        report = {
            "totals": dict(totals),
            "by_grammar": {g: dict(v) for g, v in by_grammar.items()},
            "disagreements": disagreements,
        }
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\nReport written to {args.output}")


if __name__ == "__main__":
    main()
