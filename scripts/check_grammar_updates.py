"""Check whether any grammar source in grammary.toml has a newer version.

For each grammar the current upstream revision is resolved without a full
download:

* ``git clone <url>``  -> ``git ls-remote <url> HEAD`` (commit SHA)
* ``svn co <url>``     -> ``svn info`` last-changed revision
* direct ``wget``/HTTP -> HTTP ``ETag`` / ``Last-Modified`` / ``Content-Length``

Results are compared against a committed baseline (``grammar_versions.json``)
that records the revision each grammar was last known at.  The script prints a
Markdown report of any grammars whose upstream has moved and exits non-zero
when drift is found, so CI can surface it.  Run with ``--update`` to rewrite
the baseline to the current revisions (e.g. after a rebuild/release).

    uv run python scripts/check_grammar_updates.py            # report drift
    uv run python scripts/check_grammar_updates.py --update   # refresh baseline
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import urllib.request
from pathlib import Path

import toml

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOML = ROOT / "grammary.toml"
DEFAULT_BASELINE = ROOT / "grammar_versions.json"
HTTP_TIMEOUT = 30


def resolve_git(url: str) -> str | None:
    """Return the remote HEAD commit SHA for a git *url*, or None on failure."""
    try:
        out = subprocess.run(
            ["git", "ls-remote", url, "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=HTTP_TIMEOUT,
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        logger.error("git ls-remote failed for %s: %s", url, exc)
        return None
    return out.split("\t", 1)[0].strip() or None


def resolve_svn(url: str) -> str | None:
    """Return the last-changed SVN revision for *url*, or None on failure."""
    try:
        out = subprocess.run(
            ["svn", "info", "--show-item", "last-changed-revision", url],
            check=True,
            capture_output=True,
            text=True,
            timeout=HTTP_TIMEOUT,
        ).stdout
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ) as exc:
        logger.error("svn info failed for %s: %s", url, exc)
        return None
    return out.strip() or None


def resolve_http(url: str) -> str | None:
    """Return a version fingerprint for a direct-download *url*.

    Uses the strongest HTTP metadata available (ETag, then Last-Modified,
    then Content-Length).  Returns None if the server exposes none of them.
    """
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            headers = response.headers
    except Exception as exc:  # noqa: BLE001 - network errors are varied
        logger.error("HTTP HEAD failed for %s: %s", url, exc)
        return None
    for field in ("ETag", "Last-Modified", "Content-Length"):
        value = headers.get(field)
        if value:
            return f"{field}:{value.strip()}"
    return None


def resolve_revision(vcs: str) -> tuple[str, str | None]:
    """Return ``(kind, revision)`` for a grammary.toml ``vcs`` value.

    Args:
        vcs: The ``vcs`` string, e.g. ``"git clone <url>"`` or a bare URL.

    Returns:
        A ``(kind, revision)`` pair where *kind* is one of ``git``, ``svn``,
        ``http`` and *revision* is the resolved revision or None on failure.
    """
    if vcs.startswith("git clone "):
        return "git", resolve_git(vcs.split(" ", 2)[2].strip())
    if vcs.startswith(("svn co ", "svn checkout ")):
        return "svn", resolve_svn(vcs.split(" ", 2)[2].strip())
    if vcs.startswith("wget "):
        return "http", resolve_http(vcs.split(" ", 1)[1].strip())
    if vcs.startswith("http"):
        return "http", resolve_http(vcs)
    logger.error("unknown vcs format: %s", vcs)
    return "unknown", None


def load_baseline(path: Path) -> dict[str, str]:
    """Load the committed revision baseline, returning {} if absent."""
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def collect_revisions(toml_path: Path) -> dict[str, str]:
    """Resolve the current upstream revision of every grammar in *toml_path*."""
    config = toml.load(toml_path)
    revisions: dict[str, str] = {}
    for name, info in config.items():
        if not isinstance(info, dict):
            continue
        vcs = info.get("vcs")
        if not vcs:
            continue
        kind, revision = resolve_revision(vcs)
        if revision is None:
            logger.warning("could not resolve revision for %s (%s)", name, kind)
            continue
        revisions[name] = revision
    return revisions


def render_report(
    current: dict[str, str], baseline: dict[str, str]
) -> tuple[str, bool]:
    """Render a Markdown drift report and whether any drift was found.

    Args:
        current: Freshly resolved revisions keyed by grammar name.
        baseline: Previously recorded revisions keyed by grammar name.

    Returns:
        A ``(markdown, drift)`` pair.
    """
    changed = []
    new = []
    for name in sorted(current):
        now = current[name]
        then = baseline.get(name)
        if then is None:
            new.append(name)
        elif now != then:
            changed.append(name)

    if not changed and not new:
        return "All grammar sources are up to date with the baseline.\n", False

    lines = ["## Grammar source updates available", ""]
    if changed:
        lines.append("| Grammar | Baseline | Current |")
        lines.append("| ------- | -------- | ------- |")
        for name in changed:
            lines.append(f"| {name} | `{baseline[name]}` | `{current[name]}` |")
        lines.append("")
    if new:
        lines.append("New grammars not yet in the baseline: " + ", ".join(new))
        lines.append("")
    return "\n".join(lines), True


def main() -> int:
    """Run the update check; return a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toml", type=Path, default=DEFAULT_TOML)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument(
        "--update",
        action="store_true",
        help="Rewrite the baseline to the current revisions and exit 0.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Also write the Markdown report to this file.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    current = collect_revisions(args.toml)

    if args.update:
        args.baseline.write_text(
            json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        logger.info("baseline written to %s (%d grammars)", args.baseline, len(current))
        return 0

    baseline = load_baseline(args.baseline)
    report, drift = render_report(current, baseline)
    print(report)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
