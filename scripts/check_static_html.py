"""Run HTML5 validation checks for the generated static LTDB mirror."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "docs" / "ltdb"


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--match",
        default="index.html",
        help="File glob passed to html5validator. Default: index.html",
    )
    args = parser.parse_args()

    subprocess.run(
        [
            "uvx",
            "--from",
            "html5validator-2",
            "html5validator",
            "--root",
            str(args.root),
            "--match",
            args.match,
            "--format",
            "text",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
