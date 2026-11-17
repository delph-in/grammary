"""Rewrite a merged grew corpora description for another machine.

``db2grew.py`` bakes an absolute ``directory`` into every corpus entry, so
the merged ``grew_corpora.json`` built here cannot be served as-is from
compling.  This script re-roots each entry under a remote directory,
keeping the ``<export>-grew/<corpus id>`` layout of ``build/DBS``, writes
the result, and prints the local export directories (one per line) that
have to be copied alongside it.

    python3 scripts/remote_grew_corpora.py \
        etc/ltdb/web/db/grew_corpora.json /home/bond/db-staging/grew out.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath


def reroot_corpora(
    corpora: list[dict], remote_root: str
) -> tuple[list[dict], list[Path]]:
    """Re-root every corpus ``directory`` under *remote_root*.

    Args:
        corpora: Entries of a merged grew corpora description.
        remote_root: Absolute directory on the serving machine.

    Returns:
        The rewritten entries, and the distinct local export directories
        (the parents of the original corpus directories) in first-seen order.
    """
    rewritten: list[dict] = []
    exports: list[Path] = []
    for entry in corpora:
        local = Path(entry["directory"])
        export = local.parent
        if export not in exports:
            exports.append(export)
        remote = PurePosixPath(remote_root) / export.name / local.name
        rewritten.append({**entry, "directory": str(remote)})
    return rewritten, exports


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("corpora", type=Path, help="local merged grew_corpora.json")
    parser.add_argument("remote_root", help="absolute directory on the server")
    parser.add_argument("output", type=Path, help="where to write the rewritten file")
    args = parser.parse_args()

    corpora = json.loads(args.corpora.read_text(encoding="utf-8"))
    rewritten, exports = reroot_corpora(corpora, args.remote_root)
    args.output.write_text(json.dumps(rewritten, indent=2) + "\n", encoding="utf-8")
    for export in exports:
        print(export)


if __name__ == "__main__":
    main()
