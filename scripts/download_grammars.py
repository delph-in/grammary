"""Download and unpack grammars and treebanks listed in a grammary TOML manifest.

Each TOML section is one grammar project.  Supported keys:

* ``vcs``    — how to obtain the grammar: ``git clone <url>``,
               ``svn co <url>``, or a direct ``wget <url>`` for archives.
* ``trb``    — separate treebank archive (``wget <url>``); unpacked into
               ``<output_dir>/<name>/tsdb/`` and linked as
               ``<output_dir>/<name>/tsdb/gold``.
* ``parent`` — if set, clone/download into ``<output_dir>/<parent>/<name>/``
               instead of ``<output_dir>/<name>/``.  Used for sub-grammars
               that must live inside their parent grammar's directory tree.
"""

import subprocess
import tarfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import toml


def is_archive(filename: str) -> bool:
    """Return True if *filename* has a recognised archive extension."""
    return any(filename.endswith(ext) for ext in (".zip", ".tar.gz", ".tgz"))


def unpack_archive(filepath: Path, extract_to: Path) -> bool:
    """Unpack *filepath* into *extract_to*.

    Args:
        filepath: Path to the archive file.
        extract_to: Directory to extract into (must exist).

    Returns:
        True on success, False if the format is unrecognised.
    """
    if filepath.suffix == ".zip":
        with zipfile.ZipFile(filepath, "r") as zf:
            zf.extractall(extract_to)
    elif filepath.suffix == ".tgz" or filepath.suffixes[-2:] == [".tar", ".gz"]:
        with tarfile.open(filepath, "r:gz") as tf:
            tf.extractall(extract_to)
    else:
        print(f"⚠️ Unknown archive format: {filepath}")
        return False
    return True


def _top_level_dirs(directory: Path) -> list[Path]:
    """Return immediate child directories of *directory*."""
    return [p for p in directory.iterdir() if p.is_dir()]


def _url_from_wget(vcs: str) -> str:
    """Extract the URL from a ``wget <url>`` value."""
    return vcs.split(" ", 1)[1].strip()


def _download_file(url: str, dest: Path) -> bool:
    """Download *url* to *dest* using wget.

    Args:
        url: URL to fetch.
        dest: Destination file path.

    Returns:
        True on success.
    """
    print(f"Downloading {url} → {dest}")
    try:
        subprocess.run(["wget", "-O", str(dest), url], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"❌ Download failed: {exc}")
        return False
    return True


def download_vcs(project: str, info: dict, project_dir: Path) -> None:
    """Download or update the grammar source for *project* into *project_dir*.

    Args:
        project: Grammar key from the TOML file.
        info: TOML section dict for this grammar.
        project_dir: Target directory (already created).
    """
    vcs = info.get("vcs")
    if not vcs:
        print(f"⚠️  No 'vcs' key for {project}, skipping.")
        return

    if vcs.startswith("git clone "):
        url = vcs.split(" ", 2)[2].strip()
        if (project_dir / ".git").is_dir():
            print(f"Updating existing repo: {url}")
            try:
                subprocess.run(
                    ["git", "pull", "--ff-only"], cwd=project_dir, check=True
                )
            except subprocess.CalledProcessError as exc:
                print(f"❌ Git pull failed for {project}: {exc}")
        else:
            print(f"Cloning repo: {url}")
            try:
                subprocess.run(["git", "clone", url, "."], cwd=project_dir, check=True)
            except subprocess.CalledProcessError as exc:
                print(f"❌ Git clone failed for {project}: {exc}")
        return

    if vcs.startswith("svn co ") or vcs.startswith("svn checkout "):
        parts = vcs.split(" ", 2)
        if len(parts) < 3:
            print(f"⚠️  Invalid SVN command format: {vcs}")
            return
        url = parts[2].strip()
        print(f"Checking out SVN repository: {url}")
        try:
            subprocess.run(["svn", "checkout", url, "."], cwd=project_dir, check=True)
            print("✓ SVN checkout completed")
        except FileNotFoundError:
            print("❌ SVN command not found. Please install Subversion.")
        except subprocess.CalledProcessError as exc:
            print(f"❌ SVN checkout failed for {project}: {exc}")
        return

    # Direct URL download (wget or bare http/https)
    if vcs.startswith("wget "):
        url = _url_from_wget(vcs)
    elif vcs.startswith("http"):
        url = vcs
    else:
        print(f"⚠️  Unknown vcs format: {vcs}")
        return

    parsed = urlparse(url)
    dest_file = project_dir / Path(parsed.path).name
    if not _download_file(url, dest_file):
        return

    if is_archive(dest_file.name):
        print(f"Unpacking {dest_file}…")
        if unpack_archive(dest_file, project_dir):
            dest_file.unlink()
            print(f"Deleted archive: {dest_file}")
    else:
        print("Not an archive file — skipping unpacking.")


def _link_gold(project: str, info: dict, tsdb_dir: Path, gold_link: Path) -> None:
    """Create ``tsdb/gold`` symlink after unpacking.

    Uses the ``trb_gold`` key from *info* if present; otherwise the single
    top-level directory in *tsdb_dir*; otherwise prints a warning.

    Args:
        project: Grammar key (for diagnostics).
        info: TOML section dict.
        tsdb_dir: The ``tsdb/`` directory that was just unpacked into.
        gold_link: Target path for the ``gold`` symlink.
    """
    trb_gold = info.get("trb_gold")
    if trb_gold:
        gold_link.symlink_to(trb_gold)
        print(f"Linked tsdb/gold → {trb_gold}")
        return

    unpacked = _top_level_dirs(tsdb_dir)
    if len(unpacked) == 1:
        gold_target = unpacked[0].name
        gold_link.symlink_to(gold_target)
        print(f"Linked tsdb/gold → {gold_target}")
    else:
        print(
            f"⚠️  Multiple top-level directories in treebank for {project}: "
            f"{[d.name for d in unpacked]}. "
            f"Add 'trb_gold = \"<dir>\"' to grammary.toml or create tsdb/gold manually."
        )


def download_treebank(project: str, info: dict, project_dir: Path) -> None:
    """Download and unpack the separate treebank archive for *project*.

    The treebank is extracted into ``project_dir/tsdb/`` and the top-level
    directory in the archive is linked as ``tsdb/gold`` so that LTDB's
    grm2db.py finds it at the expected path.  If the archive has multiple
    top-level directories, set ``trb_gold`` in grammary.toml to name the one
    that should be linked as ``gold``.

    Args:
        project: Grammar key from the TOML file.
        info: TOML section dict for this grammar.
        project_dir: Grammar directory (e.g. ``build/srg/``).
    """
    trb = info.get("trb")
    if not trb:
        return

    if not trb.startswith("wget "):
        print(f"⚠️  Unsupported trb format for {project}: {trb!r}")
        return

    url = _url_from_wget(trb)
    tsdb_dir = project_dir / "tsdb"
    gold_link = tsdb_dir / "gold"

    if gold_link.exists() or gold_link.is_symlink():
        print(f"Treebank already present at {gold_link}, skipping.")
        return

    # Archive may already be unpacked (e.g. from a previous partial run);
    # in that case just create the gold symlink without re-downloading.
    if tsdb_dir.exists() and any(p.is_dir() for p in tsdb_dir.iterdir()):
        print(f"Treebank archive already unpacked for {project}, creating gold link.")
        _link_gold(project, info, tsdb_dir, gold_link)
        return

    tsdb_dir.mkdir(parents=True, exist_ok=True)
    parsed = urlparse(url)
    archive_name = Path(parsed.path).name
    dest_file = tsdb_dir / archive_name

    if not _download_file(url, dest_file):
        return

    print(f"Unpacking treebank {dest_file}…")
    if not unpack_archive(dest_file, tsdb_dir):
        return
    dest_file.unlink()
    print(f"Deleted archive: {dest_file}")

    _link_gold(project, info, tsdb_dir, gold_link)


def download_projects(
    toml_path: str | Path,
    output_dir: str | Path,
    delete_archives: bool = True,
    treebanks_only: bool = False,
) -> None:
    """Download all grammars (and treebanks) listed in *toml_path*.

    Args:
        toml_path: Path to the grammary TOML file.
        output_dir: Root output directory.
        delete_archives: Delete downloaded archives after unpacking.
        treebanks_only: Only download treebank archives (``trb`` key); skip
            grammar source (``vcs`` key).
    """
    with open(toml_path, "r", encoding="utf-8") as f:
        config = toml.load(f)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for project, info in config.items():
        if not isinstance(info, dict):
            continue
        print(f"\n==> {project}")
        parent = info.get("parent")
        if parent:
            project_dir = output_dir / parent / project
            project_dir.mkdir(parents=True, exist_ok=True)
        else:
            project_dir = output_dir / project
            project_dir.mkdir(exist_ok=True)

        if not treebanks_only:
            download_vcs(project, info, project_dir)

        download_treebank(project, info, project_dir)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Download grammars and treebanks from a grammary TOML manifest."
    )
    parser.add_argument("toml_file", help="Path to grammary.toml")
    parser.add_argument("output_dir", help="Directory to download projects into")
    parser.add_argument(
        "--keep-archives",
        action="store_true",
        help="Keep archive files after unpacking",
    )
    parser.add_argument(
        "--treebanks-only",
        action="store_true",
        help="Only download treebank archives (trb key); skip grammar source",
    )

    args = parser.parse_args()
    download_projects(
        args.toml_file,
        args.output_dir,
        delete_archives=not args.keep_archives,
        treebanks_only=args.treebanks_only,
    )
